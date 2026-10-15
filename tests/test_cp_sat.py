import itertools
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from ortools.sat.python import cp_model
from planner.cp_sat import solve
from planner.scenario import Order, Window, TransitionPermission
from planner.search import plan, build_schedule
from planner.evaluator import evaluate_resources
from planner.verifier import verify_schedule
from test_scheduler import tiny_case


class CPSatTests(unittest.TestCase):
    def test_exhaustive_cleaning_feasibility_and_boundaries(self):
        for enabled, initial, terminal in itertools.product((False,True),repeat=3):
            orders,config=tiny_case(enabled=enabled)
            config=replace(config,terminal_cleaning=terminal,machines=(replace(config.machines[0],initially_clean=initial),))
            exhaustive=[]
            for priority in itertools.permutations(orders):
                s,fail=build_schedule(priority,config)
                if not fail and verify_schedule(orders,config,s).valid:
                    exhaustive.append(evaluate_resources(orders,config,s).cleaning_events)
            result=solve(orders,config,budget_seconds=2)
            self.assertIsNotNone(result.schedule)
            self.assertTrue(result.verification.valid)
            self.assertEqual(result.resources.cleaning_events,min(exhaustive))
            self.assertTrue(result.cleaning_optimal)
            self.assertTrue(result.slack_optimal_at_fixed_count)
            self.assertEqual(result.stage_a['best_bound'],min(exhaustive))

    def test_directed_permission_only_immediate_adjacency(self):
        orders,config=tiny_case()
        # Exact boundaries force 1 > 2 > 3, so 1->3 cannot exempt 3.
        base=orders[0].release
        orders=tuple(replace(o,release=base+timedelta(hours=2*i),deadline=base+timedelta(hours=2*i+2)) for i,o in enumerate(orders))
        config=replace(config,transition_permissions=(TransitionPermission('virtual-test','1','3','test explicit'),))
        result=solve(orders,config,budget_seconds=2)
        self.assertEqual(result.resources.cleaning_events,4)
        self.assertEqual([p.order_id for p in result.schedule.placements],['1','2','3'])
        self.assertTrue(all(p.cleaning_required for p in result.schedule.placements))

    def test_edd_failure_but_joint_schedule_feasible(self):
        orders,config=tiny_case(enabled=False)
        base=orders[0].release
        # EDD appends late-release order 1 first, blocking the earlier slot for 2.
        orders=(replace(orders[0],release=base+timedelta(hours=8),deadline=base+timedelta(hours=10)),
                replace(orders[1],release=base,deadline=base+timedelta(hours=11)))
        config=replace(config,transition_permissions=())
        self.assertIsNone(plan(orders,config).proposal)
        result=solve(orders,config,budget_seconds=2)
        self.assertTrue(result.verification.valid)
        self.assertEqual([p.order_id for p in result.schedule.placements],['2','1'])

    def test_outage_cleaning_and_terminal_must_fit_windows(self):
        orders,config=tiny_case(enabled=False);orders=orders[:1];base=orders[0].release
        config=replace(config,transition_permissions=(),machines=(replace(config.machines[0],availability=(
            Window(base,base+timedelta(hours=1)),Window(base+timedelta(hours=2),base+timedelta(hours=5)))),))
        result=solve(orders,config,budget_seconds=2)
        self.assertEqual(result.schedule.placements[0].cleaning_start,base+timedelta(hours=2))
        self.assertTrue(result.verification.valid)
        config=replace(config,machines=(replace(config.machines[0],availability=(Window(base,base+timedelta(hours=2)),)),))
        self.assertEqual(solve(orders,config,budget_seconds=2).solver_status,'INFEASIBLE')

    def test_closed_unused_compatible_capacity_and_joint_assignments(self):
        orders,config=tiny_case(enabled=False)
        config=replace(config,transition_permissions=(),machines=(replace(config.machines[0],availability=()),
            replace(config.machines[0],virtual_id='virtual-second')))
        result=solve(orders,config,budget_seconds=2)
        self.assertTrue(all(p.virtual_id=='virtual-second' for p in result.schedule.placements))
        self.assertEqual(len(result.schedule.terminal_cleanups),1)
        for machines in ((replace(config.machines[1],capacity=Decimal(1)),),
                         (replace(config.machines[1],compatible_pairs=(('Jet','Other'),)),),
                         (config.machines[0],)):
            result=solve(orders,replace(config,machines=machines),budget_seconds=2)
            self.assertIsNone(result.schedule)
            self.assertEqual(result.solver_status,'INFEASIBLE')
        # Assignments are genuinely variable, with enough capacity for simultaneous slots.
        base=orders[0].release
        orders=tuple(replace(o,deadline=base+timedelta(hours=2)) for o in orders[:2])
        config=replace(config,machines=(config.machines[1],replace(config.machines[1],virtual_id='virtual-third')))
        result=solve(orders,config,budget_seconds=2)
        self.assertTrue(result.verification.valid)
        self.assertEqual(len({p.virtual_id for p in result.schedule.placements}),2)

    def test_seconds_microseconds_and_overflow_no_rounding(self):
        orders,config=tiny_case(enabled=False);orders=orders[:1];base=orders[0].release+timedelta(seconds=17,microseconds=3)
        # Fractional-hour durations resolve exactly to 3600us; an offset of 3us
        # forces the shared time lattice to microsecond precision without rounding.
        config=replace(config,transition_permissions=(),hours_per_duration_unit=Decimal('0.000001'),cleaning_hours=Decimal('0.000001'))
        orders=(replace(orders[0],release=base,deadline=base+timedelta(seconds=1)),)
        result=solve(orders,config,budget_seconds=2)
        self.assertTrue(result.verification.valid)
        p=result.schedule.placements[0]
        self.assertEqual(p.process_end-p.process_start,timedelta(microseconds=3600))
        self.assertEqual(p.cleaning_start,base)
        self.assertEqual(result.scale['tick_microseconds'],1)
        bad=(replace(orders[0],release=datetime(1,1,1,microsecond=1),deadline=datetime(9999,1,1)),)
        with self.assertRaisesRegex(ValueError,'Unsupported exact time range'):
            solve(bad,config,budget_seconds=2)

    def test_unknown_and_stage_b_fallback_not_infeasibility(self):
        orders,config=tiny_case()
        class Unknown:
            def solve(self,model):return cp_model.UNKNOWN
            def status_name(self,status):return 'UNKNOWN'
        with patch('planner.cp_sat._solver',return_value=Unknown()):
            result=solve(orders,config,budget_seconds=2)
        self.assertIsNone(result.schedule)
        self.assertEqual(result.solver_status,'UNKNOWN')
        from planner.cp_sat import _solver
        with patch('planner.cp_sat._solver',side_effect=[_solver(1),Unknown()]):
            result=solve(orders,config,budget_seconds=2)
        self.assertIsNotNone(result.schedule)
        self.assertEqual(result.active_stage,'A')
        self.assertEqual(result.stage_b['status'],'UNKNOWN')
        self.assertFalse(result.slack_optimal_at_fixed_count)
        self.assertTrue(result.verification.valid)

    def test_invalid_translation_rejected_and_invalid_hint_ignored(self):
        orders,config=tiny_case()
        good=plan(orders,config).proposal
        bad=replace(good,placements=good.placements[:1])
        result=solve(orders,config,incumbent=bad,budget_seconds=2)
        self.assertTrue(result.verification.valid)
        self.assertIn('ignored',result.hint)
        with patch('planner.cp_sat._translate',return_value=bad):
            result=solve(orders,config,budget_seconds=2)
        self.assertIsNone(result.schedule)
        self.assertFalse(result.stage_a['verified'])

