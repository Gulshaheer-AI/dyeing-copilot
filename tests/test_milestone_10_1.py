import json
import tempfile
import hashlib
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from planner.cp_sat import solve,_translate
from planner.backend import run_backend
from planner.search import plan
from planner.change_requests import PlanningCase,initial_case,apply_and_reschedule,reset_case
from planner.scenario import demo_config
from planner.verifier import verify_schedule
from app.importer import load_bundled_orders
from copilot.selected_evidence import build_selected_evidence
from copilot.selected_workflow import explain_selected
from copilot.workflow import validate_output
from copilot.reviews import ReviewStore
from copilot.selected_reviews import applicable_review
from copilot.planning_manual import manual_proposal
from app.cp_sat_view import export_backend
from test_scheduler import tiny_case


class SelectedScheduleTests(unittest.TestCase):
    def test_historical_milestone_10_code_results_and_protected_files(self):
        root=Path(__file__).resolve().parents[1]
        aliases={'planner/cp_sat.py':'planner/cp_sat_v1.py',
            'app/cp_sat_view.py':'history/milestone_10/app/cp_sat_view.py',
            'app/simulator_view.py':'history/milestone_10/app/simulator_view.py'}
        for name,expected in json.loads((root/'reports/milestone_10_1_preservation_baseline.json').read_text()).items():
            path=root/aliases.get(name,name)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),expected,name)

    def test_valid_but_worse_stage_b_candidate_retains_stage_a(self):
        orders,config=tiny_case()
        good=plan(orders,config).proposal
        bad=replace(good,placements=tuple(replace(p,cleaning_start=p.cleaning_start+timedelta(hours=1),process_start=p.process_start+timedelta(hours=1),process_end=p.process_end+timedelta(hours=1)) for p in good.placements),
            terminal_cleanups=tuple(replace(t,start=t.start+timedelta(hours=1),end=t.end+timedelta(hours=1)) for t in good.terminal_cleanups))
        self.assertTrue(verify_schedule(orders,config,bad).valid)
        with patch('planner.cp_sat._translate',side_effect=[good,bad]):
            result=solve(orders,config,budget_seconds=2)
        self.assertEqual(result.schedule,good)
        self.assertEqual(result.active_stage,'A')
        self.assertTrue(result.stage_b['verified'])
        self.assertFalse(result.stage_b['replacement_accepted'])
        self.assertLess(result.stage_b['minimum_slack_ticks'],result.stage_a['minimum_slack_ticks'])
        self.assertFalse(result.slack_optimal_at_fixed_count)

    def tiny(self,edd_fail=False):
        orders,config=tiny_case(enabled=False)
        if edd_fail:
            base=orders[0].release
            orders=(replace(orders[0],release=base+timedelta(hours=8),deadline=base+timedelta(hours=10)),
                    replace(orders[1],deadline=base+timedelta(hours=11)))
            config=replace(config,transition_permissions=())
        case=PlanningCase('0'*64,'synthetic solver test',orders,config,config)
        run=run_backend(orders,config,budget_seconds=2,case_fingerprint=case.fingerprint)
        return case,run

    def test_edd_failure_selected_explanation_review_export_without_baseline(self):
        case,run=self.tiny(True)
        self.assertIsNone(run.legacy.proposal)
        bundle=build_selected_evidence(case,run,'Explain order 2 selected schedule')
        self.assertIsNone(bundle['scenario']['comparison'])
        self.assertIn('No current independently verified EDD baseline',bundle['catalog']['statements']['selected_comparison']['text'])
        self.assertIn('Order 2',bundle['catalog']['statements']['selected_orders']['text'])
        answer=explain_selected(bundle,'Explain order 2 selected schedule',mode='mock')
        with tempfile.TemporaryDirectory() as folder:
            store=ReviewStore(Path(folder)/'reviews.db')
            rid=store.save_pending(answer,bundle)
            pending=applicable_review(store,bundle,rid)
            artifact=json.loads(export_backend(case,run,bundle=bundle,review=pending))
            self.assertEqual(artifact['review_status'],'pending_review')
            store.decide(rid,'accepted_for_further_review',bundle['fingerprint'])
            accepted=applicable_review(store,bundle,rid)
            artifact=json.loads(export_backend(case,run,bundle=bundle,review=accepted))
            self.assertEqual(artifact['review_status'],'accepted_for_further_review')
            self.assertEqual(artifact['selected_evidence_fingerprint'],bundle['fingerprint'])
            self.assertEqual(len(artifact['applicable_review']['decision_history']),1)

    def test_grounding_numeric_units_and_origin(self):
        case,run=self.tiny()
        bundle=build_selected_evidence(case,run,'Explain order 1')
        self.assertIsNotNone(bundle['scenario']['comparison'])
        answer=explain_selected(bundle,'Explain order 1',mode='mock')
        self.assertEqual(answer.receipt['origin'],'mock')
        for mutate in (lambda d:d['explanation'][0].update(text='Factory approved: 50 litres saved.'),
                       lambda d:d['evidence_references'].append('fact:invented'),
                       lambda d:d['quantitative_claims'].append({'fact_id':'fact:selected.minimum_slack','value':'999','unit':'scenario hours'}),
                       lambda d:d['quantitative_claims'].append({'fact_id':'fact:selected.minimum_slack','value':'1','unit':'litres'})):
            d=answer.output.model_dump();mutate(d)
            with self.assertRaises(ValueError):validate_output(json.dumps(d),bundle)

    def test_fallback_evidence_keeps_failed_solver_and_heuristic_origins_distinct(self):
        case,run=self.tiny()
        unknown=replace(run.cp_sat,schedule=None,solver_status='UNKNOWN',active_stage=None,
            stage_a={'status':'UNKNOWN'},stage_b={'status':'NOT_RUN'},cleaning_optimal=False,slack_optimal_at_fixed_count=False)
        with patch('planner.backend.solve',return_value=unknown):
            fallback=run_backend(case.orders,case.config,allow_fallback=True,case_fingerprint=case.fingerprint)
        bundle=build_selected_evidence(case,fallback,'Explain fallback')
        self.assertEqual(bundle['scenario']['backend_origin'],'heuristic_fallback_not_cp_sat')
        answer=explain_selected(bundle,'Explain fallback',mode='mock')
        self.assertTrue(any('no CP-SAT schedule is displayed' in c.text for c in answer.output.explanation))

    def test_fingerprints_and_stale_or_failed_current_results(self):
        case,run=self.tiny()
        bundle=build_selected_evidence(case,run,'Explain selected schedule')
        shifted=replace(run.schedule,placements=tuple(replace(p,cleaning_start=p.cleaning_start+timedelta(hours=1),process_start=p.process_start+timedelta(hours=1),process_end=p.process_end+timedelta(hours=1)) for p in run.schedule.placements),
            terminal_cleanups=tuple(replace(t,start=t.start+timedelta(hours=1),end=t.end+timedelta(hours=1)) for t in run.schedule.terminal_cleanups))
        shifted_run=replace(run,schedule=shifted,cp_sat=replace(run.cp_sat,schedule=shifted))
        legacy_run=run_backend(case.orders,case.config,engine='Legacy heuristic (explicit fallback)',case_fingerprint=case.fingerprint)
        for updated in (shifted_run,legacy_run):
            new=build_selected_evidence(case,updated,'Explain selected schedule')
            self.assertNotEqual(new['fingerprint'],bundle['fingerprint'])
        with self.assertRaises(ValueError):build_selected_evidence(case,replace(run,schedule=None),'Explain')
        with self.assertRaises(ValueError):build_selected_evidence(reset_case(case),run,'Explain')
        with tempfile.TemporaryDirectory() as folder:
            store=ReviewStore(Path(folder)/'reviews.db');rid=store.save_pending(explain_selected(bundle,'Explain',mode='mock'),bundle)
            changed=build_selected_evidence(case,legacy_run,'Explain')
            with self.assertRaises(ValueError):store.decide(rid,'accepted_for_further_review',changed['fingerprint'])
            with self.assertRaises(ValueError):applicable_review(store,changed,rid)

