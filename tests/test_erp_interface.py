"""UI-only regression checks: canonical exports, truthful overlays and routing."""
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.reports_view import current_report
from app.cp_sat_view import export_backend
from app.timeline_view import protected_work
from app.planner_presentation import timeline_rows
from planner.recovery import Recovery
import test_planner_presentation as presentation

ROOT = Path(__file__).resolve().parents[1]


class ERPReportTests(unittest.TestCase):
    def test_report_is_canonical_and_rejects_missing_stale_or_changed_source(self):
        case, run = presentation.TimelineTests().fixture()
        source = SimpleNamespace(sha256=case.source_sha256)
        state = {'sim_context': {'case': case, 'selected_run': run}}
        self.assertEqual(current_report(source, state), export_backend(case, run))
        with self.assertRaises(ValueError): current_report(source, {})
        with self.assertRaises(ValueError): current_report(SimpleNamespace(sha256='different'), state)
        changed = replace(case, revision=case.revision + 1)
        with self.assertRaises(ValueError):
            current_report(source, {'sim_context': {'case': changed, 'selected_run': run}})

    def test_protected_outline_uses_existing_fixed_work_and_preserves_times(self):
        case, run = presentation.TimelineTests().fixture()
        frame, _, _ = timeline_rows(case.orders, case.config, run.schedule)
        original = frame.copy(deep=True)
        first = min(run.schedule.placements, key=lambda p: p.cleaning_start)
        cutoff = first.cleaning_start + timedelta(microseconds=1)
        reference = Recovery(case.fingerprint, case.orders, case.config, run.schedule, cutoff)
        flags = protected_work(frame, reference)
        for row, flag in zip(frame.itertuples(), flags):
            if row.order_id == first.order_id and row.activity in ('Production', 'Cleaning'):
                self.assertTrue(flag)
            if row.activity == 'Unavailable': self.assertFalse(flag)
        self.assertFalse(any(protected_work(frame, None)))
        self.assertTrue(frame.equals(original))


class ERPNavigationTests(unittest.TestCase):
    def test_modules_preserve_plan_forms_and_never_call_solver_or_amd(self):
        from streamlit.testing.v1 import AppTest
        from planner.backend import run_backend
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {
            'DYEING_PLAN_HISTORY_DB': str(Path(folder) / 'private.sqlite3'),
            'AMD_API_KEY': 'PASTE_OFFLINE', 'AMD_BASE_URL': 'PASTE_OFFLINE', 'AMD_MODEL': 'PASTE_OFFLINE'
        }), patch('app.simulator_view.run_backend', wraps=run_backend) as solve, \
                patch('app.planning_changes_view.interpret') as interpret, \
                patch('app.selected_copilot_view.explain_selected') as explain:
            app = AppTest.from_file(str(ROOT / 'streamlit_app.py'), default_timeout=45).run()
            def navigate(value):
                next(r for r in app.radio if r.label == 'Workspace').set_value(value).run()
                self.assertFalse(app.exception)
            navigate('Reports')
            self.assertTrue(next(b for b in app.get('download_button') if b.label == 'Download current schedule review package').disabled)
            navigate('Scheduling simulator')
            next(b for b in app.button if b.label == 'Load demo setup').click().run()
            next(c for c in app.checkbox if c.key == 'sim_permission').check().run()
            next(b for b in app.button if b.label == 'Generate schedule').click().run()
            self.assertFalse(app.exception)
            before = app.session_state['sim_cp_result']
            case = app.session_state['planning_case']
            machine_ids=[m.virtual_id for m in case.config.machines]
            self.assertEqual(next(m for m in app.multiselect if m.key=='timeline_machines').value,machine_ids)
            app.run()
            self.assertEqual(next(m for m in app.multiselect if m.key=='timeline_machines').value,machine_ids)
            next(t for t in app.text_area if t.key == 'planning_request_text').set_value('Make order 12 urgent').run()
            for module in ('Orders', 'Reports', 'Plan history', 'More tools', 'Scheduling simulator'):
                navigate(module)
            self.assertEqual(app.session_state['sim_cp_result'], before)
            self.assertEqual(app.session_state['planning_case'], case)
            self.assertTrue(app.session_state['sim_permission'])
            self.assertEqual(next(t for t in app.text_area if t.key == 'planning_request_text').value, 'Make order 12 urgent')
            self.assertEqual(solve.call_count, 1)
            interpret.assert_not_called()
            explain.assert_not_called()
