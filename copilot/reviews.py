"""SQLite review decisions are isolated from scenario permissions and machine controls."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from copilot.evidence import fingerprint
from copilot.workflow import validate_output

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data/reviews.sqlite3"


class ReviewStore:
    def __init__(self, path=DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    source_fingerprint TEXT NOT NULL, scenario_fingerprint TEXT NOT NULL,
                    question TEXT NOT NULL, evidence_json TEXT NOT NULL, answer_json TEXT NOT NULL,
                    receipt_json TEXT NOT NULL, notes TEXT NOT NULL, status TEXT NOT NULL
                    CHECK(status IN ('pending_review','accepted_for_further_review','rejected'))
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY, review_id TEXT NOT NULL REFERENCES reviews(id),
                    decided_at TEXT NOT NULL, decision TEXT NOT NULL, notes TEXT NOT NULL
                );
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(reviews)")}
            for column in ("model_fingerprint", "day_fingerprint"):
                if column not in columns:
                    db.execute(f"ALTER TABLE reviews ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def save_pending(self, answer, bundle, notes=""):
        if answer.fingerprint != bundle["fingerprint"]:
            raise ValueError("Cannot save a stale explanation.")
        validate_output(answer.output.model_dump_json(), bundle)
        if len(notes) > 5000:
            raise ValueError("Review notes must be at most 5000 characters.")
        identity = fingerprint({"answer": answer.output.model_dump(), "receipt": answer.receipt,
                                "question": answer.question, "fingerprint": answer.fingerprint})
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO reviews (id,created_at,fingerprint,source_fingerprint,scenario_fingerprint,"
                       "question,evidence_json,answer_json,receipt_json,notes,status,model_fingerprint,day_fingerprint) "
                       "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                identity, datetime.now(timezone.utc).isoformat(), bundle["fingerprint"],
                bundle["source_fingerprint"], bundle["scenario_fingerprint"], answer.question,
                json.dumps(bundle, sort_keys=True), answer.output.model_dump_json(),
                json.dumps(answer.receipt, sort_keys=True), notes, "pending_review",
                bundle.get("model_fingerprint", ""), bundle.get("day_fingerprint", "")))
        return identity

    def decide(self, review_id, decision, current_fingerprint, notes=""):
        if decision not in ("accepted_for_further_review", "rejected") or len(notes) > 5000:
            raise ValueError("Invalid review decision or notes.")
        with self.connect() as db:
            changed = db.execute("UPDATE reviews SET status=? WHERE id=? AND status='pending_review' AND fingerprint=?",
                                 (decision, review_id, current_fingerprint)).rowcount
            if changed != 1:
                raise ValueError("Review is stale, already decided or unavailable; no decision was changed.")
            db.execute("INSERT INTO decisions(review_id,decided_at,decision,notes) VALUES (?,?,?,?)",
                       (review_id, datetime.now(timezone.utc).isoformat(), decision, notes))

    def list_reviews(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM reviews ORDER BY created_at DESC LIMIT 50")]

    def decision_history(self, review_id):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM decisions WHERE review_id=? ORDER BY id", (review_id,))]
