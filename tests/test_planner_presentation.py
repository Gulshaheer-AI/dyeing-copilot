import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch

from app.cp_sat_view import export_backend
from app.planner_presentation import timeline_rows,clip_timeline,current_comparison,machine_name
from copilot.reviews import ReviewStore
from planner.backend import run_backend
from planner.change_requests import PlanningCase
from planner.scenario import Window
from streamlit.testing.v1 import AppTest
from test_scheduler import tiny_case
from test_interface import APP
from ui_helpers import click


class TimelineTests(unittest.TestCase):
    def fixture(self,enabled=True):
        orders,config=tiny_case(enabled=enabled)
        base=orders[0].release
        machine=replace(config.machines[0],availability=(Window(base,base+timedelta(hours=3)),
            Window(base+timedelta(hours=5),base+timedelta(days=3))))
        closed=replace(machine,virtual_id='virtual-closed',availability=())
        config=replace(config,machines=(machine,closed))
        case=PlanningCase('0'*64,'synthetic presentation fixture',orders,config,config)
        run=run_backend(orders,config,budget_seconds=2,case_fingerprint=case.fingerprint)
        return case,run

    def test_timeline_matches_export_exactly_including_terminal_and_outages(self):
        case,run=self.fixture()
        frame,lo,hi=timeline_rows(case.orders,case.config,run.schedule)
        exported=json.loads(export_backend(case,run))
        for p in exported['schedule']['placements']:
            production=frame[(frame.order_id==p['order_id'])&(frame.activity=='Production')].iloc[0]
            self.assertEqual(production.start.to_pydatetime(),datetime.fromisoformat(p['process_start']))
            self.assertEqual(production.end.to_pydatetime(),datetime.fromisoformat(p['process_end']))
            cleaning=frame[(frame.order_id==p['order_id'])&(frame.activity=='Cleaning')]
            self.assertEqual(len(cleaning),int(p['cleaning_required']))
            if p['cleaning_required']:
                self.assertEqual(cleaning.iloc[0].start.to_pydatetime(),datetime.fromisoformat(p['cleaning_start']))
                self.assertEqual(cleaning.iloc[0].end,production.start)
        terminal=frame[frame.activity=='Terminal cleaning']
        self.assertEqual(len(terminal),len(exported['schedule']['terminal_cleanups']))
        for t in exported['schedule']['terminal_cleanups']:
            row=terminal[terminal.machine_id==t['virtual_id']].iloc[0]
            self.assertEqual(row.start.to_pydatetime(),datetime.fromisoformat(t['start']))
            self.assertEqual(row.end.to_pydatetime(),datetime.fromisoformat(t['end']))
        unavailable=frame[(frame.activity=='Unavailable')&(frame.machine_id=='virtual-test')]
        self.assertEqual(len(unavailable),1)
        self.assertEqual(unavailable.iloc[0].start,case.orders[0].release+timedelta(hours=3))
        closed=frame[frame.machine_id=='virtual-closed'].iloc[0]
        self.assertEqual((closed.start,closed.end),(lo,hi))
        self.assertTrue(exported['verified_comparison']['reconciliation']['passed'])
        self.assertIsNotNone(exported['generated_deadline_first_baseline'])

    def test_clipping_changes_display_edges_only(self):
        case,run=self.fixture()
        frame,lo,hi=timeline_rows(case.orders,case.config,run.schedule)
        original=frame.copy(deep=True)
        selected=clip_timeline(frame,lo+timedelta(minutes=30),hi,['virtual-test'])
        self.assertEqual(selected.iloc[0].start,frame.iloc[0].start)
        self.assertGreaterEqual(selected.visible_start.min(),lo+timedelta(minutes=30))
        self.assertTrue(frame.equals(original))
        with self.assertRaises(ValueError):clip_timeline(frame,hi,lo,['virtual-test'])
        self.assertEqual(machine_name('virtual-Jet-Cotton'),'Jet — Cotton')

    def test_comparison_rejects_changed_scenario_identity(self):
        case,run=self.fixture()
        self.assertIsNotNone(current_comparison(case,run))
        changed_orders=tuple(replace(o,deadline=o.deadline+timedelta(days=1)) for o in case.orders)
        changed=PlanningCase(case.source_sha256,case.source_filename,changed_orders,case.config,case.config)
        with self.assertRaises(ValueError):current_comparison(changed,run)
        with self.assertRaises(ValueError):export_backend(changed,run)

    def test_no_valid_edd_does_not_invent_comparison(self):
        orders,config=tiny_case(enabled=False);base=orders[0].release
        orders=(replace(orders[0],release=base+timedelta(hours=8),deadline=base+timedelta(hours=10)),
            replace(orders[1],deadline=base+timedelta(hours=11)))
        config=replace(config,transition_permissions=())
        case=PlanningCase('0'*64,'EDD-failure fixture',orders,config,config)
        run=run_backend(orders,config,budget_seconds=2,case_fingerprint=case.fingerprint)
        self.assertIsNotNone(run.schedule)
        self.assertIsNone(current_comparison(case,run))
        self.assertIsNone(json.loads(export_backend(case,run))['generated_deadline_first_baseline'])


class ProductionPlannerInterfaceTests(unittest.TestCase):
    def test_default_and_reruns_never_submit_or_resolve(self):
        with tempfile.TemporaryDirectory() as directory,patch('app.selected_copilot_view.ReviewStore',
                side_effect=lambda:ReviewStore(Path(directory)/'review.db')),patch('app.simulator_view.run_backend',wraps=run_backend) as solver,\
                patch('app.planning_changes_view.interpret') as interpreter,patch('app.selected_copilot_view.explain_selected') as explainer:
            app=AppTest.from_file(APP).run(timeout=40)
            self.assertFalse(app.exception)
            self.assertEqual(next(r for r in app.radio if r.label=='Workspace').value,'Scheduling simulator')
            self.assertTrue(next(b for b in app.button if b.label=='Generate schedule').disabled)
            self.assertEqual(solver.call_count,0)
            click(app,'Load demo setup')
            self.assertFalse(next(c for c in app.checkbox if c.key=='sim_permission').value)
            click(app,'Generate schedule')
            self.assertFalse(app.exception)
            first=app.session_state['sim_cp_result']
            self.assertEqual([t.label for t in app.tabs],['Machine schedule','Changes and recovery','Review and reports'])
            self.assertEqual(solver.call_count,1)
            click(app,'Next day')
            click(app,'Previous day')
            self.assertEqual(solver.call_count,1)
            self.assertEqual(app.session_state['sim_cp_result'],first)
            next(c for c in app.checkbox if c.label=='Show full schedule').check().run(timeout=40)
            app.run(timeout=40)
            self.assertFalse(app.exception)
            self.assertEqual(solver.call_count,1)
            self.assertEqual(app.session_state['sim_cp_result'],first)
            interpreter.assert_not_called();explainer.assert_not_called()
            next(c for c in app.checkbox if c.key=='sim_permission').check().run(timeout=40)
            self.assertFalse(any(m.label=='Cleaning events' for m in app.metric))
            click(app,'Generate schedule')
            self.assertFalse(app.exception)
            self.assertEqual(solver.call_count,2)
            self.assertTrue(app.session_state['planning_case'].config.allow_cleaning_exemptions)
            self.assertTrue(app.session_state['sim_cp_result'][1].cp_sat.verification.valid)
