from ui_helpers import click as ui_click
import json
import unittest
from datetime import timedelta
from dataclasses import replace
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

from planner.backend import run_backend,CP_ENGINE,LEGACY_ENGINE
from planner.cp_sat import solve,_solver
from planner.search import plan
from planner.change_requests import initial_case
from copilot.planning_manual import manual_proposal
from app.cp_sat_view import export_backend
from app.importer import load_bundled_orders
from planner.scenario import demo_config
from test_scheduler import tiny_case
from test_interface import APP


class CPIntegrationTests(unittest.TestCase):
    def test_unknown_fallback_origin_and_no_silent_substitution(self):
        from ortools.sat.python import cp_model
        orders,config=tiny_case()
        class Unknown:
            def solve(self,model):return cp_model.UNKNOWN
            def status_name(self,status):return 'UNKNOWN'
        with patch('planner.cp_sat._solver',return_value=Unknown()):
            unknown=solve(orders,config,budget_seconds=1)
        with patch('planner.backend.solve',return_value=unknown):
            self.assertIsNone(run_backend(orders,config).schedule)
            fallback=run_backend(orders,config,allow_fallback=True)
            self.assertEqual(fallback.origin,'heuristic_fallback_not_cp_sat')
            self.assertEqual(fallback.cp_sat.stage_a['status'],'UNKNOWN')
        self.assertEqual(run_backend(orders,config,engine=LEGACY_ENGINE).origin,'legacy_heuristic')

    def test_feasible_stage_a_is_conditional_not_global_optimality(self):
        from ortools.sat.python import cp_model
        orders,config=tiny_case()
        class Feasible:
            def __init__(self):self.solver=_solver(1)
            def solve(self,model):self.solver.solve(model);return cp_model.FEASIBLE
            def __getattr__(self,name):return getattr(self.solver,name)
        with patch('planner.cp_sat._solver',side_effect=[Feasible(),_solver(1)]):
            result=solve(orders,config,budget_seconds=2)
        self.assertTrue(result.stage_b['conditional_on_feasible_incumbent'])
        self.assertFalse(result.cleaning_optimal)
        self.assertTrue(result.verification.valid)

    def test_default_ui_manual_override_current_solver_export_reset_and_gate(self):
        app=AppTest.from_file(APP).run(timeout=40)
        def click(label):ui_click(app,label)
        click('Batch scheduling simulator')
        self.assertEqual(next(s for s in app.selectbox if s.label=='Planning engine').value,CP_ENGINE)
        click('Load demo setup');click('Generate schedule')
        self.assertFalse(app.exception)
        case=app.session_state['planning_case'];marker,run=app.session_state['sim_cp_result']
        self.assertEqual(run.origin,'cp_sat');self.assertTrue(run.cp_sat.verification.valid)
        self.assertIsNone(app.session_state['sim_context']['comparison'])
        self.assertFalse(any(s.label=='Inspect machine sequence changes against' for s in app.selectbox))
        self.assertTrue(any(b.label=='Explain this plan' for b in app.button))
        exported=json.loads(export_backend(case,run))
        self.assertEqual(exported['backend_origin'],'cp_sat');self.assertTrue(exported['verification']['valid'])
        app.run(timeout=40);self.assertEqual(app.session_state['sim_cp_result'][0],marker)
        next(r for r in app.radio if r.label=='Constraint entry').set_value('Manual controls').run(timeout=40)
        app.session_state['planning_manual_proposal']=manual_proposal(case,operation='order_deadline',identifier='12',deadline=case.orders[11].release+timedelta(hours=1))
        app.run(timeout=40);click('Apply changes and reschedule')
        self.assertFalse(app.exception)
        changed=app.session_state['planning_case'];newmarker,failed=app.session_state['sim_cp_result']
        self.assertNotEqual(newmarker,marker);self.assertIsNone(failed.schedule)
        self.assertEqual(failed.cp_sat.stage_a['status'],'INFEASIBLE')
        self.assertTrue(any('Historical schedule' in e.label for e in app.expander))
        with self.assertRaises(ValueError):export_backend(changed,run)
        click('Reset to original scenario and reschedule')
        self.assertEqual(app.session_state['planning_case'].orders,case.orders)
        self.assertEqual(app.session_state['sim_cp_result'][1].origin,'cp_sat')

