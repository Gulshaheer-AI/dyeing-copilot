"""Immutable planned-result archives; a separate, session-scoped SQLite store.

Only the save builder evaluates live objects. Reads validate the saved format and
hash; they never rebuild metrics or schedules with subsequently changed rules.
"""
import hashlib
import json
import os
import re
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'dyeing-plan-history-v1'
APPLICATION = 'integrated-recovery+plan-history-v1'
NOTICE = ('Saved planning snapshots for this session. Hosted storage may reset after an app restart '
          'or redeployment. Download a copy to keep it.')


class HistoryError(ValueError):
    """Curated errors only: no database paths, input data or credentials."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def privacy_check(value):
    # Reject, never silently discard, private metadata or a known configured key.
    from dotenv import dotenv_values
    known = [v for k, v in {**dotenv_values(ROOT / '.env'), **os.environ}.items()
             if v and re.search(r'(API_KEY|TOKEN|SECRET|PASSWORD)$', k, re.I) and len(v) >= 8]
    forbidden = {'authorization', 'api_key', 'amd_api_key', 'password', 'access_token', 'refresh_token',
                 'environment', 'environ', 'env_contents', 'headers', 'request_headers', 'response_headers',
                 'raw_response', 'raw_body', 'raw_transport', 'transport_diagnostics', 'session_scope',
                 'session_id', 'scope_hash', 'env', 'dotenv', 'secrets', 'credentials',
                 'raw_transport_diagnostics', 'raw_diagnostics', 'model_response_content'}
    normalized = {re.sub(r'[^a-z0-9]', '', key) for key in forbidden}
    def walk(item):
        if isinstance(item, dict):
            if any(re.sub(r'[^a-z0-9]', '', str(k).lower()) in normalized for k in item):
                raise HistoryError('Snapshot rejected: private metadata is not permitted.')
            for v in item.values(): walk(v)
        elif isinstance(item, list):
            for v in item: walk(v)
    walk(value)
    text = canonical(value)
    if any(secret in text for secret in known) or re.search(
        r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:gh[pousr]_[A-Za-z0-9]{20,}|'
        r'github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{24,})|Bearer\s+\S+|'
        r'(?i:AMD_API_KEY\s*[=:]\s*\S+)', text):
        raise HistoryError('Snapshot rejected: credential-like content is not permitted.')


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class Summary(Model):
    kind: Literal['ordinary', 'recovery']
    method: str = Field(min_length=1, max_length=100)
    priority: str = Field(min_length=1, max_length=100)
    cleaning_count: int = Field(strict=True, ge=0)
    on_time: int = Field(strict=True, ge=0)
    total_orders: int = Field(strict=True, gt=0)
    minimum_slack_hours: str
    verified: Literal[True]


class Event(Model):
    machine_id: str
    machine: str
    order_id: str | None
    activity: Literal['Production', 'Cleaning', 'Terminal cleaning', 'Unavailable', 'Revised outage']
    start: datetime
    end: datetime
    label: str

    @model_validator(mode='after')
    def interval(self):
        if self.start.tzinfo or self.end.tzinfo or self.start >= self.end:
            raise ValueError('Invalid saved scenario-local timeline interval.')
        return self


class Snapshot(Model):
    schema_version: Literal['dyeing-plan-history-v1']
    application_version: Literal['integrated-recovery+plan-history-v1']
    summary: Summary
    package: dict
    input_records: list[dict] | None
    selected_timeline: list[Event] = Field(min_length=1)
    reference_timeline: list[Event] | None
    reference_label: str
    saved_metrics: dict
    explanation: dict | None
    content_fingerprint: str

    @model_validator(mode='after')
    def integrity(self):
        data = self.model_dump(mode='json')
        claimed = data.pop('content_fingerprint')
        if fingerprint(data) != claimed:
            raise ValueError('Saved snapshot integrity mismatch.')
        if (self.package.get('artifact_type') != 'illustrative_selected_backend_schedule_not_factory_instruction'
                or self.package.get('verification', {}).get('valid') is not True
                or not self.package.get('orders') or not self.package.get('schedule')
                or not self.package.get('assumptions') or not self.saved_metrics.get('deadlines')
                or self.summary.on_time > self.summary.total_orders):
            raise ValueError('Malformed saved planning package.')
        if (len(self.package['orders']) != self.summary.total_orders
                or self.saved_metrics['cleaning_counts']['total'] != self.summary.cleaning_count
                or self.saved_metrics['deadlines']['on_time'] != self.summary.on_time
                or len(self.package['schedule']['placements']) != self.summary.total_orders):
            raise ValueError('Inconsistent saved metrics or order identity.')
        privacy_check(data)
        return self


def validate_snapshot(value):
    try:
        out = Snapshot.model_validate(value)
        if len(out.model_dump_json()) > 10_000_000:
            raise HistoryError('Snapshot is too large for local history.')
        return out
    except (ValidationError, TypeError, KeyError, OverflowError):
        raise HistoryError('Unsupported or malformed planning snapshot; it cannot be opened.') from None


def build_snapshot(case, run, *, source=None, bundle=None, answer=None, review=None):
    from app.cp_sat_view import export_backend
    from app.planner_presentation import timeline_rows, recovery_timeline_rows
    from planner.comparison import compare_schedules, deadline_performance
    from planner.scenario import to_json
    from planner.change_requests import digest
    if source is not None:
        from planner.scenario import orders_from_import
        if (source.sha256 != case.source_sha256 or source.filename != case.source_filename
                or digest(orders_from_import(source)) != digest(case.original_orders)):
            raise HistoryError('Input records do not match the selected planning case.')
    # An evidence bundle is optional and only retained with an already valid answer/review.
    explanation = None
    if answer is not None:
        from copilot.selected_workflow import SelectedExplanation
        from copilot.workflow import validate_output
        if bundle is None or answer.fingerprint != bundle['fingerprint']:
            raise HistoryError('Cannot archive a stale explanation.')
        SelectedExplanation.model_validate_json(answer.output.model_dump_json())
        validate_output(answer.output.model_dump_json(), bundle)
        explanation = json.loads(to_json({'output': answer.output.model_dump(), 'question': answer.question,
                                         'receipt': answer.receipt, 'fingerprint': answer.fingerprint}))
    if explanation is None and review is None: bundle = None
    # Canonical export performs current source/schedule/evidence/recovery verification.
    package = json.loads(export_backend(case, run, bundle=bundle, review=review))
    counts = compare_schedules(case.orders, case.config, run.schedule, run.schedule)['cleaning_counts']['proposal']
    deadlines = deadline_performance(case.orders, run.schedule)
    if case.recovery:
        selected = recovery_timeline_rows(case, run.schedule)[0]
        reference = recovery_timeline_rows(case, run.schedule, reference=True)[0]
        label = 'Selected reference planned result (before disruption)'
    else:
        selected = timeline_rows(case.orders, case.config, run.schedule)[0]
        comparison = package['verified_comparison']
        reference = timeline_rows(case.orders, case.config, run.legacy.baseline)[0] if comparison else None
        label = 'Generated deadline-first planned baseline' if comparison else 'No verified baseline was available when saved'
    def freeze(frame):
        if frame is None: return None
        return [dict(row, order_id=row['order_id'] if isinstance(row['order_id'], str) else None,
                     start=row['start'].isoformat(), end=row['end'].isoformat())
                for row in frame.to_dict('records')]
    data = json.loads(to_json({
        'schema_version': SCHEMA, 'application_version': APPLICATION,
        'summary': {'kind': 'recovery' if case.recovery else 'ordinary', 'method': run.origin,
                    'priority': getattr(run, 'option', 'fewer_cleanings') if run.cp_sat else 'legacy_heuristic',
                    'cleaning_count': counts['total'], 'on_time': deadlines['on_time'],
                    'total_orders': len(case.orders), 'minimum_slack_hours': str(min(r['slack_hours'] for r in deadlines['orders'])),
                    'verified': True},
        'package': package, 'input_records': source.records if source is not None else None,
        'selected_timeline': freeze(selected), 'reference_timeline': freeze(reference), 'reference_label': label,
        'saved_metrics': {'cleaning_counts': counts, 'deadlines': deadlines,
                          'comparison': package['verified_comparison'], 'recovery': package['recovery_summary']},
        'explanation': explanation}))
    data['content_fingerprint'] = fingerprint(data)
    return validate_snapshot(data)


def new_scope():
    return secrets.token_urlsafe(32)


def scope_hash(scope):
    if not isinstance(scope, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', scope):
        raise HistoryError('History session is unavailable. Reload the app to begin a new session.')
    return hashlib.sha256(scope.encode()).hexdigest()


class HistoryStore:
    def __init__(self, path=None):
        self.path = Path(path if path is not None else os.environ.get('DYEING_PLAN_HISTORY_DB', ROOT / 'data/plan_history.sqlite3'))
        if self.path.resolve() == (ROOT / 'data/reviews.sqlite3').resolve():
            raise HistoryError('History requires separate storage from supervisor reviews.')
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.connect() as db:
                db.execute('''CREATE TABLE IF NOT EXISTS planning_runs (
                    run_id TEXT PRIMARY KEY, scope_hash TEXT NOT NULL, saved_at TEXT NOT NULL,
                    title TEXT NOT NULL, fingerprint TEXT NOT NULL, snapshot_json TEXT NOT NULL,
                    UNIQUE(scope_hash,fingerprint,title))''')
        except (sqlite3.Error, OSError, ValueError):
            raise HistoryError('Plan history storage is unavailable. Planning and existing downloads still work.') from None

    @contextmanager
    def connect(self):
        db = None
        try:
            db = sqlite3.connect(self.path, timeout=2)
            db.row_factory = sqlite3.Row
            with db: yield db
        except (sqlite3.Error, OSError):
            raise HistoryError('Plan history storage is unavailable. Planning and existing downloads still work.') from None
        finally:
            if db is not None: db.close()

    def save(self, *, scope, snapshot, title=''):
        hashed = scope_hash(scope)
        if not isinstance(title, str) or len(title.strip()) > 120:
            raise HistoryError('Use a history title of at most 120 characters.')
        title = title.strip()
        privacy_check({'title': title})
        snap = validate_snapshot(snapshot.model_dump(mode='json') if isinstance(snapshot, Snapshot) else snapshot)
        if scope in title or scope in snap.model_dump_json():
            raise HistoryError('Session identifiers cannot be included in saved exports.')
        run_id = str(uuid.uuid4())
        saved_at = datetime.now(ZoneInfo('Asia/Karachi')).isoformat()
        with self.connect() as db:
            inserted = db.execute('INSERT OR IGNORE INTO planning_runs VALUES (?,?,?,?,?,?)',
                (run_id, hashed, saved_at, title, snap.content_fingerprint, snap.model_dump_json())).rowcount
            row = db.execute('SELECT run_id,saved_at FROM planning_runs WHERE scope_hash=? AND fingerprint=? AND title=?',
                (hashed, snap.content_fingerprint, title)).fetchone()
        return {'run_id': row['run_id'], 'saved_at': row['saved_at'], 'created': bool(inserted)}

    def get(self, *, scope, run_id):
        hashed = scope_hash(scope)
        with self.connect() as db:
            row = db.execute('SELECT run_id,saved_at,title,fingerprint,snapshot_json FROM planning_runs WHERE scope_hash=? AND run_id=?',
                             (hashed, run_id)).fetchone()
        if row is None: raise HistoryError('Saved run is unavailable in this session.')
        try:
            snapshot = validate_snapshot(json.loads(row['snapshot_json']))
            stamp = datetime.fromisoformat(row['saved_at'])
            uuid.UUID(row['run_id'])
            if stamp.tzinfo is None or snapshot.content_fingerprint != row['fingerprint']:
                raise ValueError
            privacy_check({'title': row['title']})
        except (ValueError, TypeError):
            raise HistoryError('Unsupported or malformed saved run; it cannot be opened.') from None
        output = {'run_id': row['run_id'], 'saved_at': row['saved_at'], 'title': row['title'],
                  'snapshot': snapshot.model_dump(mode='json')}
        if scope in canonical(output):
            raise HistoryError('Session identifiers cannot be included in saved exports.')
        return output

    def list_runs(self, *, scope):
        hashed = scope_hash(scope)
        with self.connect() as db:
            ids = [r['run_id'] for r in db.execute('SELECT run_id FROM planning_runs WHERE scope_hash=? ORDER BY saved_at DESC, rowid DESC', (hashed,))]
        rows = []
        for run_id in ids:
            try:
                row = self.get(scope=scope, run_id=run_id)
                rows.append({k: row[k] for k in ('run_id', 'saved_at', 'title')} | {'summary': row['snapshot']['summary']})
            except HistoryError:
                rows.append({'run_id': run_id, 'title': 'Unsupported or malformed saved run', 'saved_at': '', 'summary': None})
        return rows

    def download(self, *, scope, run_id):
        # Every detail/download lookup is independently scoped. Scope never enters exports.
        row = self.get(scope=scope, run_id=run_id)
        return json.dumps({'artifact_type': 'archived_planned_result_not_actual_execution', **row}, indent=2)
