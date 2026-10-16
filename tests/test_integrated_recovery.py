import json
import unittest
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch
from planner.backend import run_backend,LEGACY_ENGINE
from planner.change_requests import PlanningCase,apply_changes,preview_changes,reset_case
from planner.recovery import select_reference,operations,verify_recovery,recovery_summary
from planner.recovery_solver import solve_option,stage_b_acceptable
from copilot.planning_manual import manual_proposal
from test_scheduler import tiny_case
from pathlib import Path
import tempfile


class RecoveryTests(unittest.TestCase):
    def fixture(self,offset=1.5):
        orders,config=tiny_case(enabled=False)
        case=PlanningCase('0'*64,'synthetic recovery fixture',orders,config,config)
        run=run_backend(orders,config,engine=LEGACY_ENGINE,case_fingerprint=case.fingerprint)
        return select_reference(case,run,orders[0].release+timedelta(hours=offset))

    def test_running_completed_exact_boundaries_and_corruption(self):
        for cutoff in (0,1,1.5,2,2.5,6,6.5,7):
            with self.subTest(cutoff=cutoff):
                case=self.fixture(cutoff);run=solve_option(case,'fewer_cleanings',budget_seconds=2)
                self.assertIsNotNone(run.schedule)
                self.assertTrue(verify_recovery(case.orders,case.config,run.schedule,case.recovery).valid)
                for old in case.recovery.reference.placements:
                    if old.cleaning_start<case.recovery.cutoff:
                        self.assertIn(old,run.schedule.placements)
                if cutoff>0:
                    old=run.schedule.placements[0]
                    damaged=replace(run.schedule,placements=(replace(old,process_start=old.process_start+timedelta(seconds=1)),)+run.schedule.placements[1:])
                    self.assertFalse(verify_recovery(case.orders,case.config,damaged,case.recovery).valid)

    def test_future_outage_atomic_preview_and_reference_impact(self):
        case=self.fixture();base=case.orders[0].release
        proposal=manual_proposal(case,operation='machine_unavailability',identifier='virtual-test',start=base+timedelta(hours=2),end=base+timedelta(hours=4))
        original=case.fingerprint
        self.assertTrue(preview_changes(case,proposal));self.assertEqual(case.fingerprint,original)
        updated=apply_changes(case,proposal)
        run=solve_option(updated,'fewer_cleanings',budget_seconds=2)
        summary=recovery_summary(updated,run.schedule)
        self.assertEqual(summary['running_batches_protected'],1)
        self.assertEqual(summary['future_batches_changed'],2)
        self.assertEqual(summary['cleaning_before'],summary['cleaning_after'])
        with self.assertRaisesRegex(ValueError,'Stale'):apply_changes(updated,proposal)
        self.assertIsNone(reset_case(updated).recovery)

    def test_cleaning_commitment_outage_and_history_deadline_conflicts(self):
        case=self.fixture(.5);base=case.orders[0].release
        for start,end in ((.25,.75),(1.5,2)):
            proposal=manual_proposal(case,operation='machine_unavailability',identifier='virtual-test',start=base+timedelta(hours=start),end=base+timedelta(hours=end))
            with self.assertRaisesRegex(ValueError,'Interrupted-batch'):preview_changes(case,proposal)
        proposal=manual_proposal(case,operation='order_deadline',identifier='1',deadline=base+timedelta(hours=1))
        with self.assertRaisesRegex(ValueError,'preserved'):apply_changes(case,proposal)

    def test_two_options_quality_guards_and_infeasible_status(self):
        case=self.fixture()
        for option in ('fewer_cleanings','deadline_protection'):
            run=solve_option(case,option,budget_seconds=2)
            self.assertTrue(run.cp_sat.verification.valid)
            self.assertEqual(run.cp_sat.objective_order,option)
            self.assertFalse(stage_b_acceptable(option,4,10,4,9))
        self.assertFalse(stage_b_acceptable('fewer_cleanings',4,10,5,11))
        base=case.orders[0].release
        p=manual_proposal(case,operation='order_deadline',identifier='2',deadline=base+timedelta(hours=2))
        failed=solve_option(apply_changes(case,p),'deadline_protection',budget_seconds=2)
        self.assertIsNone(failed.schedule);self.assertEqual(failed.cp_sat.stage_a['status'],'INFEASIBLE')

    def test_unknown_is_not_infeasible_and_stage_b_worse_is_retained(self):
        from ortools.sat.python import cp_model
        class Unknown:
            def solve(self,model):return cp_model.UNKNOWN
            def status_name(self,status):return 'UNKNOWN'
        with patch('planner.recovery_solver._solver',return_value=Unknown()):
            result=solve_option(self.fixture(),'fewer_cleanings',budget_seconds=2)
        self.assertIsNone(result.schedule);self.assertEqual(result.cp_sat.stage_a['status'],'UNKNOWN')
        # A verified but worse buffer must be rejected independently of model constraints.
        case=self.fixture();good=solve_option(case,'deadline_protection',budget_seconds=2).schedule
        movable=[p for p in good.placements if p.cleaning_start>=case.recovery.cutoff]
        bad=replace(good,placements=tuple(replace(p,cleaning_start=p.cleaning_start+timedelta(hours=1),process_start=p.process_start+timedelta(hours=1),process_end=p.process_end+timedelta(hours=1)) if p in movable else p for p in good.placements),terminal_cleanups=tuple(replace(t,start=t.start+timedelta(hours=1),end=t.end+timedelta(hours=1)) for t in good.terminal_cleanups))
        self.assertTrue(verify_recovery(case.orders,case.config,bad,case.recovery).valid)
        with patch('planner.recovery_solver._translate',side_effect=[good,bad]):
            result=solve_option(case,'deadline_protection',budget_seconds=2)
        self.assertEqual(result.schedule,good);self.assertEqual(result.cp_sat.active_stage,'A')

    def test_independent_history_check_rejects_ordinary_valid_shift_and_source_changes(self):
        from planner.verifier import verify_schedule
        case=self.fixture();original=case.recovery.reference
        shifted=replace(original,placements=tuple(replace(p,cleaning_start=p.cleaning_start+timedelta(hours=1),process_start=p.process_start+timedelta(hours=1),process_end=p.process_end+timedelta(hours=1)) for p in original.placements),terminal_cleanups=tuple(replace(t,start=t.start+timedelta(hours=1),end=t.end+timedelta(hours=1)) for t in original.terminal_cleanups))
        self.assertTrue(verify_schedule(case.orders,case.config,shifted).valid)
        self.assertFalse(verify_recovery(case.orders,case.config,shifted,case.recovery).valid)
        changed=(replace(case.orders[0],quantity=case.orders[0].quantity-1),)+case.orders[1:]
        self.assertTrue(any('source inputs changed' in e for e in verify_recovery(changed,case.config,original,case.recovery).errors))

    def test_recovery_grounding_review_export_and_stale_identity(self):
        from copilot.selected_evidence import build_selected_evidence
        from copilot.selected_workflow import explain_selected
        from copilot.reviews import ReviewStore
        from copilot.selected_reviews import applicable_review
        from app.cp_sat_view import export_backend
        from app.planner_presentation import current_comparison,recovery_timeline_rows
        case=self.fixture();run=solve_option(case,'fewer_cleanings',budget_seconds=2)
        bundle=build_selected_evidence(case,run,'Explain recovery changes')
        self.assertIsNone(bundle['scenario']['comparison']);self.assertIsNone(current_comparison(case,run))
        self.assertEqual(bundle['scenario']['recovery_summary']['running_batches_protected'],1)
        answer=explain_selected(bundle,'Explain recovery changes',mode='mock')
        self.assertEqual(answer.output.quantitative_claims,[])
        self.assertEqual(answer.receipt['origin'],'mock')
        with tempfile.TemporaryDirectory() as folder:
            store=ReviewStore(Path(folder)/'reviews.db');rid=store.save_pending(answer,bundle)
            pending=applicable_review(store,bundle,rid)
            artifact=json.loads(export_backend(case,run,bundle=bundle,review=pending))
            self.assertEqual(artifact['review_status'],'pending_review')
            self.assertIsNone(artifact['generated_deadline_first_baseline'])
            self.assertEqual(artifact['execution_reference']['origin'],case.recovery.origin)
            store.decide(rid,'accepted_for_further_review',bundle['fingerprint'])
            accepted=applicable_review(store,bundle,rid)
            self.assertEqual(json.loads(export_backend(case,run,bundle=bundle,review=accepted))['review_status'],'accepted_for_further_review')
            other=solve_option(case,'deadline_protection',budget_seconds=2)
            fresh=build_selected_evidence(case,other,'Explain recovery changes')
            self.assertNotEqual(fresh['fingerprint'],bundle['fingerprint'])
            with self.assertRaises(ValueError):applicable_review(store,fresh,rid)
            with self.assertRaises(ValueError):export_backend(case,other,bundle=bundle,review=accepted)
        for stale in (reset_case(case),replace(case,recovery=replace(case.recovery,cutoff=case.recovery.cutoff+timedelta(microseconds=1)))):
            with self.assertRaises(ValueError):build_selected_evidence(stale,run,'Explain')
            with self.assertRaises(ValueError):export_backend(stale,run)
        with self.assertRaises(ValueError):build_selected_evidence(case,replace(run,option='deadline_protection'),'Explain')
        frame,_,_=recovery_timeline_rows(case,run.schedule)
        for p in run.schedule.placements:
            row=frame[(frame.order_id==p.order_id)&(frame.activity=='Production')].iloc[0]
            self.assertEqual((row.start.to_pydatetime(),row.end.to_pydatetime()),(p.process_start,p.process_end))
        p=manual_proposal(case,operation='machine_unavailability',identifier='virtual-test',start=case.orders[0].release+timedelta(hours=2),end=case.orders[0].release+timedelta(hours=4))
        updated=apply_changes(case,p);changed=solve_option(updated,'fewer_cleanings',budget_seconds=2)
        for ref in (True,False):
            frame,_,_=recovery_timeline_rows(updated,changed.schedule,reference=ref)
            self.assertEqual(len(frame[frame.activity=='Revised outage']),1)

    def test_exact_microsecond_cutoff_is_not_rounded(self):
        case=self.fixture();case=replace(case,recovery=replace(case.recovery,cutoff=case.recovery.cutoff+timedelta(microseconds=1)))
        run=solve_option(case,'fewer_cleanings',budget_seconds=2)
        self.assertEqual(run.cp_sat.scale['tick_microseconds'],1)
        self.assertTrue(verify_recovery(case.orders,case.config,run.schedule,case.recovery).valid)

    def test_recovery_question_boundary_and_order_specific_facts(self):
        from copilot.selected_evidence import build_selected_evidence
        case=self.fixture();run=solve_option(case,'fewer_cleanings',budget_seconds=2)
        for question in ('Diagnose the root cause of this outage','Recommend pressure and temperature settings','How many litres did we save?','Explain order 999'):
            with self.subTest(question=question),self.assertRaises(ValueError):build_selected_evidence(case,run,question)
        bundle=build_selected_evidence(case,run,'Explain order 1 and its deadline buffer')
        self.assertIn('Order 1',bundle['catalog']['statements']['selected_orders']['text'])
        self.assertTrue(bundle['scenario']['verification']['valid'])


if __name__=='__main__':unittest.main()
