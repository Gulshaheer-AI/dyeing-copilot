import copy
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app.plan_history import HistoryError, HistoryStore, build_snapshot, new_scope, validate_snapshot
from app.plan_history_view import archived_frame
from planner.backend import run_backend, LEGACY_ENGINE
from planner.change_requests import PlanningCase
from planner.recovery import select_reference
from planner.recovery_solver import solve_option
from planner.evaluator import evaluate_resources
from copilot.selected_evidence import build_selected_evidence
from copilot.selected_workflow import explain_selected
from test_scheduler import tiny_case


def fixture():
    orders, config = tiny_case(enabled=False)
    case = PlanningCase('0' * 64, 'synthetic history test', orders, config, config)
    run = run_backend(orders, config, engine=LEGACY_ENGINE, case_fingerprint=case.fingerprint)
    return case, run


class PlanHistoryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = HistoryStore(Path(self.folder.name) / 'history.db')
        self.scope, self.other = new_scope(), new_scope()
        self.case, self.run = fixture()
        self.snap = build_snapshot(self.case, self.run)

    def save(self, **kwargs):
        return self.store.save(scope=self.scope, snapshot=self.snap, **kwargs)

    def test_round_trip_metrics_and_no_explanation(self):
        saved = self.save(title='First plan')
        row = self.store.get(scope=self.scope, run_id=saved['run_id'])
        self.assertEqual(row['snapshot'], self.snap.model_dump(mode='json'))
        self.assertIsNotNone(datetime.fromisoformat(row['saved_at']).tzinfo)
        self.assertEqual(row['snapshot']['summary']['cleaning_count'], evaluate_resources(self.case.orders, self.case.config, self.run.schedule).cleaning_events)
        self.assertEqual(row['snapshot']['summary']['on_time'], 3)
        self.assertIsNone(row['snapshot']['explanation'])
        self.assertIsNone(row['snapshot']['package']['selected_evidence_snapshot'])
        self.assertIsNone(row['snapshot']['package']['applicable_review'])
        frame = archived_frame(row['snapshot'])
        first = next(p for p in self.run.schedule.placements if p.order_id == '1')
        production = frame[(frame.order_id == '1') & (frame.activity == 'Production')].iloc[0]
        self.assertEqual(production.start.to_pydatetime(), first.process_start)
        self.assertEqual(production.end.to_pydatetime(), first.process_end)

    def test_active_edits_do_not_change_snapshot(self):
        saved = self.save()
        before = self.store.download(scope=self.scope, run_id=saved['run_id'])
        edited = replace(self.case, config=replace(self.case.config, cleaning_water=self.case.config.cleaning_water + 1))
        self.assertNotEqual(edited.fingerprint, self.case.fingerprint)
        self.assertEqual(before, self.store.download(scope=self.scope, run_id=saved['run_id']))
        with self.assertRaises(ValueError): build_snapshot(edited, self.run)

    def test_idempotency_title_and_scope(self):
        a = self.save(title=' Plan '); b = self.save(title='Plan')
        self.assertTrue(a['created']); self.assertFalse(b['created'])
        self.assertEqual(a['run_id'], b['run_id']); self.assertEqual(a['saved_at'], b['saved_at'])
        c = self.save(title='Other title')
        self.assertNotEqual(a['run_id'], c['run_id'])
        self.assertEqual(len(self.store.list_runs(scope=self.scope)), 2)
        other = self.store.save(scope=self.other, snapshot=self.snap, title='Plan')
        self.assertNotEqual(a['run_id'], other['run_id'])
        self.assertEqual(len(self.store.list_runs(scope=self.other)), 1)

    def test_session_isolation_including_download_and_sql_injection(self):
        saved = self.save()
        self.assertEqual(self.store.list_runs(scope=self.other), [])
        for method in (self.store.get, self.store.download):
            with self.assertRaises(HistoryError): method(scope=self.other, run_id=saved['run_id'])
            with self.assertRaises(HistoryError): method(scope=self.scope, run_id="' OR 1=1 --")
        exported = self.store.download(scope=self.scope, run_id=saved['run_id'])
        self.assertNotIn(self.scope, exported); self.assertNotIn('scope_hash', exported)
        self.assertNotIn('session_id', exported)
        with self.assertRaises(HistoryError): self.save(title=self.scope)

    def test_empty_and_newest_first(self):
        self.assertEqual(self.store.list_runs(scope=self.scope), [])
        a = self.save(title='A'); b = self.save(title='B')
        self.assertEqual([r['run_id'] for r in self.store.list_runs(scope=self.scope)], [b['run_id'], a['run_id']])

    def test_recovery_snapshot_and_exact_reference(self):
        case = select_reference(self.case, self.run, self.case.orders[0].release + timedelta(hours=1.5))
        run = solve_option(case, 'deadline_protection', budget_seconds=2)
        snap = build_snapshot(case, run)
        self.assertEqual(snap.summary.kind, 'recovery')
        self.assertEqual(snap.summary.priority, 'deadline_protection')
        self.assertEqual(snap.package['execution_reference']['cutoff'], str(case.recovery.cutoff))
        self.assertEqual(snap.package['execution_reference']['reference'], json.loads(__import__('planner.scenario', fromlist=['to_json']).to_json(case.recovery.reference)))
        self.assertTrue(snap.reference_timeline)
        self.assertEqual(snap.saved_metrics['recovery']['running_batches_protected'], 1)

    def test_valid_explanation_optional_and_stale_rejected(self):
        bundle = build_selected_evidence(self.case, self.run, 'Explain plan')
        answer = explain_selected(bundle, 'Explain plan', mode='mock')
        snap = build_snapshot(self.case, self.run, bundle=bundle, answer=answer)
        self.assertEqual(snap.explanation['output']['quantitative_claims'], [])
        self.assertEqual(snap.explanation['receipt']['origin'], 'mock')
        with self.assertRaises(HistoryError): build_snapshot(self.case, self.run, answer=answer)
        from copilot.reviews import ReviewStore
        from copilot.selected_reviews import applicable_review
        store = ReviewStore(Path(self.folder.name) / 'review.db')
        review_id = store.save_pending(answer, bundle)
        reviewed = build_snapshot(self.case, self.run, bundle=bundle, answer=answer,
                                  review=applicable_review(store, bundle, review_id))
        self.assertEqual(reviewed.package['review_status'], 'pending_review')
        self.assertIn('Pending is not acceptance', reviewed.package['review_boundary'])

    def test_malformed_unsupported_and_corrupt_storage(self):
        for change in ({'schema_version': 'future-v99'}, {'content_fingerprint': 'wrong'}, {'unexpected': 'field'}):
            data = self.snap.model_dump(mode='json'); data.update(change)
            with self.assertRaises(HistoryError): validate_snapshot(data)
        saved = self.save()
        with sqlite3.connect(self.store.path) as db:
            db.execute('UPDATE planning_runs SET snapshot_json=? WHERE run_id=?', ('{broken', saved['run_id']))
        db.close()
        self.assertIsNone(self.store.list_runs(scope=self.scope)[0]['summary'])
        with self.assertRaises(HistoryError): self.store.download(scope=self.scope, run_id=saved['run_id'])

    def test_storage_errors_and_configurable_path(self):
        blocked = Path(self.folder.name) / 'file'; blocked.write_text('not a directory')
        with self.assertRaises(HistoryError): HistoryStore(blocked / 'history.db')
        with patch.dict('os.environ', {'DYEING_PLAN_HISTORY_DB': str(Path(self.folder.name) / 'configured.db')}):
            self.assertEqual(HistoryStore().path.name, 'configured.db')
        with patch('app.plan_history.sqlite3.connect', side_effect=sqlite3.OperationalError('private path')):
            with self.assertRaises(HistoryError) as e: self.store.list_runs(scope=self.scope)
            self.assertNotIn('private path', str(e.exception))

    def test_credentials_private_fields_and_title_exclusion(self):
        from app.plan_history import privacy_check
        with patch.dict('os.environ', {'AMD_API_KEY': 'private-test-secret-123456789'}):
            for value in ({'notes': 'private-test-secret-123456789'}, {'raw_response': 'diagnostic'},
                          {'environment': {'a': 'b'}}, {'Authorization': 'Bearer example'}, {'session_id': self.scope}):
                with self.assertRaises(HistoryError): privacy_check(value)
            with self.assertRaises(HistoryError): self.save(title='private-test-secret-123456789')


class HistoryInterfaceTests(unittest.TestCase):
    def test_navigation_resumes_controls_not_archived_plan(self):
        from app.plan_history_view import pause_planner_controls, resume_planner_controls
        case, run = fixture()
        state = {'sim_config': 'old frontend', 'sim_saved_config': 'exact original assumptions',
                 'sim_permission': True, 'sim_saved_permission': True, 'planning_case': case,
                 'sim_cp_result': ('marker', run), 'option_selection_test': 'deadline_protection'}
        pause_planner_controls(state)
        state['sim_config'] = ''; state['sim_permission'] = False
        with patch.object(HistoryStore, 'get', side_effect=AssertionError('No archive may be restored')):
            resume_planner_controls(state)
        self.assertEqual(state['sim_config'], 'exact original assumptions')
        self.assertTrue(state['sim_permission'])
        self.assertIs(state['planning_case'], case)
        self.assertIs(state['sim_cp_result'][1], run)
        self.assertEqual(state['option_selection_test'], 'deadline_protection')

    def test_history_is_read_only_active_session_and_storage_failure(self):
        from streamlit.testing.v1 import AppTest
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'DYEING_PLAN_HISTORY_DB': str(Path(folder) / 'history.db')}):
            app = AppTest.from_file(str(root / 'streamlit_app.py'), default_timeout=45).run()
            next(b for b in app.button if b.label == 'Load demo setup').click().run()
            next(w for w in app.checkbox if w.label == 'Use illustrative cleaning permissions').check().run()
            next(b for b in app.button if b.label == 'Generate schedule').click().run(timeout=45)
            self.assertFalse(app.exception)
            case = app.session_state['planning_case']
            run = app.session_state['sim_cp_result']
            next(b for b in app.button if b.label == 'Save to history').click().run()
            self.assertTrue(any('Saved to plan history' in s.value for s in app.success))
            next(w for w in app.radio if w.label == 'Workspace').set_value('Plan history').run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['planning_case'], case)
            self.assertEqual(app.session_state['sim_cp_result'], run)
            self.assertTrue(app.session_state['sim_permission'])
            self.assertTrue(any('Archived planned result' in s.value for s in app.caption))
            next(w for w in app.radio if w.label == 'Workspace').set_value('Scheduling simulator').run(timeout=45)
            self.assertEqual(app.session_state['sim_cp_result'], run)
            with patch('app.plan_history.sqlite3.connect', side_effect=sqlite3.OperationalError()):
                next(b for b in app.button if b.label == 'Save to history').click().run()
                self.assertFalse(app.exception)
                self.assertTrue(any('Could not save' in s.value for s in app.error))
            self.assertEqual(app.session_state['sim_cp_result'], run)
