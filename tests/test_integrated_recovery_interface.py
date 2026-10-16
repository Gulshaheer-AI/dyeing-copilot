"""Offline Streamlit state checks, explicitly not manual/browser verification."""
import json
import tempfile
import unittest
from datetime import date,time
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from test_interface import APP
from ui_helpers import click as ui_click
from planner.recovery_solver import run_options
from planner.recovery import verify_recovery
from copilot.reviews import ReviewStore


class RecoveryInterfaceTests(unittest.TestCase):
    def test_explicit_reference_manual_preview_apply_options_review_reset_and_passive_navigation(self):
        with tempfile.TemporaryDirectory() as folder, patch('app.selected_copilot_view.ReviewStore',side_effect=lambda:ReviewStore(Path(folder)/'reviews.db')), patch('app.planning_changes_view.interpret') as amd, patch('app.recovery_view.run_options',wraps=run_options) as solver:
            app=AppTest.from_file(APP).run(timeout=40)
            def click(label):ui_click(app,label)
            def radio(label,value):next(w for w in app.radio if w.label==label).set_value(value).run(timeout=40)
            click('Load demo setup')
            next(w for w in app.checkbox if w.key=='sim_permission').check().run(timeout=40)
            click('Generate schedule')
            self.assertEqual(solver.call_count,0)
            next(w for w in app.date_input if w.label=='Replan from date').set_value(date(2019,12,1))
            next(w for w in app.time_input if w.label=='Replan from time').set_value(time(5))
            click('Use current verified plan as reference')
            case=app.session_state['planning_case']
            self.assertIsNotNone(case.recovery);self.assertEqual(solver.call_count,0)
            radio('Constraint entry','Manual controls')
            next(w for w in app.selectbox if w.label=='Constraint type').set_value('Machine outage').run(timeout=40)
            next(w for w in app.selectbox if w.label=='Virtual machine ID').set_value('virtual-Pressure-PolyCotton').run(timeout=40)
            next(w for w in app.date_input if w.label=='Outage start date').set_value(date(2019,12,1))
            next(w for w in app.time_input if w.label=='Outage start time').set_value(time(12))
            next(w for w in app.date_input if w.label=='Outage end date').set_value(date(2019,12,2))
            next(w for w in app.time_input if w.label=='Outage end time').set_value(time(12))
            click('Preview manual change')
            self.assertEqual(app.session_state['planning_case'],case)
            click('Apply changes and reschedule')
            self.assertFalse(app.exception)
            self.assertEqual(solver.call_count,1)
            updated=app.session_state['planning_case'];run=app.session_state['sim_context']['selected_run']
            self.assertTrue(verify_recovery(updated.orders,updated.config,run.schedule,updated.recovery).valid)
            app.run(timeout=40);radio('Timeline plan','Reference — historical, before disruption')
            radio('Plan to inspect and review','deadline_protection')
            self.assertEqual(solver.call_count,1);amd.assert_not_called()
            radio('Selected schedule explanation source','Mock demonstration (no API call)')
            click('Explain this plan');click('Save for supervisor review');click('Record review decision')
            self.assertFalse(app.exception)
            row=ReviewStore(Path(folder)/'reviews.db').list_reviews()[0]
            self.assertEqual(row['status'],'accepted_for_further_review')
            self.assertEqual(json.loads(row['evidence_json'])['scenario']['objective_option'],'deadline_protection')
            radio('Plan to inspect and review','fewer_cleanings')
            self.assertTrue(next(b for b in app.button if b.label=='Record review decision').disabled)
            from planner.backend import LEGACY_ENGINE,CP_ENGINE
            next(w for w in app.selectbox if w.label=='Planning engine').set_value(LEGACY_ENGINE).run(timeout=40)
            self.assertTrue(any('does not preserve simulated execution history' in e.value for e in app.error))
            self.assertIsNone(app.session_state['sim_context']['selected_run'])
            next(w for w in app.selectbox if w.label=='Planning engine').set_value(CP_ENGINE).run(timeout=40)
            self.assertEqual(solver.call_count,1)
            click('Reset to original scenario and reschedule')
            self.assertIsNone(app.session_state['planning_case'].recovery)
            self.assertFalse(app.exception);self.assertEqual(solver.call_count,1);amd.assert_not_called()


if __name__=='__main__':unittest.main()
