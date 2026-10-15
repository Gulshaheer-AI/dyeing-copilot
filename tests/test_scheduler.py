import copy
import itertools
import json
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal as D

from app.importer import import_orders, load_bundled_orders
from planner.contracts import Schedule
from planner.evaluator import evaluate_resources
from planner.export import export_plan
from planner.scenario import (Machine, Order, Scenario, TransitionPermission, Window, demo_config,
                              hours, orders_from_import, parse_config, to_json)
from planner.search import build_schedule, plan
from planner.verifier import verify_schedule


def tiny_case(*, enabled=True):
    start = datetime(2020, 1, 1)
    end = start + timedelta(days=3)
    orders = tuple(Order(str(i), D(10), "Open", "Cotton", shade, D(1), start, end)
                   for i, shade in enumerate(("A", "B", "A"), 1))
    machine = Machine("virtual-test", (("Open", "Cotton"),), D(10), (Window(start, end),), False)
    rules = tuple(TransitionPermission(machine.virtual_id, a, b, "Synthetic test-only recipe/quality permission")
                  for a, b in (("1", "3"), ("3", "1")))
    config = Scenario("Tiny synthetic", "Synthetic orders and virtual machine, not factory evidence.",
                      (machine,), D(1), D(1), D(10), D(1), D(2), True, enabled, rules)
    return orders, config


class SchedulerTests(unittest.TestCase):
    def test_known_improvement_and_exhaustive_single_machine_optimum(self):
        orders, config = tiny_case()
        result = plan(orders, config)
        self.assertTrue(result.baseline_verification.valid)
        self.assertTrue(result.proposal_verification.valid)
        self.assertEqual([p.order_id for p in result.baseline.placements], ["1", "2", "3"])
        self.assertEqual(result.baseline_resources.total, 130)
        self.assertEqual(result.proposal_resources.total, 120)
        self.assertEqual(result.improvement, 10)
        exhaustive = []
        for priority in itertools.permutations(orders):
            schedule, errors = build_schedule(priority, config)
            self.assertFalse(errors)
            self.assertTrue(verify_schedule(orders, config, schedule).valid)
            exhaustive.append(evaluate_resources(orders, config, schedule).total)
        self.assertEqual(len(exhaustive), 6)
        self.assertEqual(min(exhaustive), 120)
        self.assertEqual(result.proposal_resources.total, min(exhaustive))

    def test_no_improvement_without_explicit_permission(self):
        orders, config = tiny_case(enabled=False)
        result = plan(orders, config)
        self.assertEqual(result.improvement, 0)
        self.assertEqual(result.baseline, result.proposal)
        self.assertTrue(all(p.cleaning_required for p in result.proposal.placements))
        # Even identical colours confer no exemption with no exact configured pair.
        result = plan(orders, replace(config, allow_cleaning_exemptions=True, transition_permissions=()))
        self.assertEqual(result.improvement, 0)

    def test_infeasible_deadline_has_no_resource_comparison(self):
        orders, config = tiny_case(enabled=False)
        orders = (replace(orders[0], deadline=orders[0].release + timedelta(minutes=90)),)
        config = replace(config, transition_permissions=())
        result = plan(orders, config)
        self.assertIsNone(result.proposal)
        self.assertIsNone(result.improvement)
        self.assertIsNone(result.baseline_resources)
        self.assertFalse(result.baseline_verification.valid)
        self.assertIn("deadline/availability", " ".join(result.construction_errors))

    def test_over_capacity_is_infeasible_without_splitting(self):
        orders, config = tiny_case()
        orders = tuple(replace(o, quantity=D(11)) if o.order_id == "2" else o for o in orders)
        result = plan(orders, config)
        self.assertIsNone(result.proposal)
        self.assertIn("over capacity", " ".join(result.construction_errors))
        self.assertFalse(result.baseline_verification.valid)

    def test_independent_verifier_rejects_incompatible_and_unknown_assignment(self):
        orders, config = tiny_case()
        valid = plan(orders, config).baseline
        wrong = replace(config.machines[0], virtual_id="virtual-wrong", compatible_pairs=(("Jet", "PolyCotton"),))
        config = replace(config, machines=(*config.machines, wrong))
        for virtual_id, expected in (("virtual-wrong", "incompatible"), ("virtual-unknown", "unknown virtual machine")):
            tampered = replace(valid, placements=(replace(valid.placements[0], virtual_id=virtual_id), *valid.placements[1:]))
            errors = verify_schedule(orders, config, tampered).errors
            self.assertIn(expected, " ".join(errors))

    def test_independent_verifier_rejects_changed_quantity_duplicate_and_missing(self):
        orders, config = tiny_case()
        valid = plan(orders, config).baseline
        cases = (
            (replace(valid, placements=(replace(valid.placements[0], quantity=D(9)), *valid.placements[1:])), "quantity changed"),
            (replace(valid, placements=valid.placements + (valid.placements[0],)), "exactly once"),
            (replace(valid, placements=valid.placements[1:]), "exactly once"),
        )
        for tampered, expected in cases:
            self.assertIn(expected, " ".join(verify_schedule(orders, config, tampered).errors))
            with self.assertRaises(ValueError):
                evaluate_resources(orders, config, tampered)

    def test_independent_verifier_rejects_overlap_release_duration_and_deadline(self):
        orders, config = tiny_case()
        valid = plan(orders, config).baseline
        first = valid.placements[0]
        tampered = replace(valid, placements=(first, replace(valid.placements[1],
            cleaning_start=first.cleaning_start, process_start=first.process_start, process_end=first.process_end),
            valid.placements[2]))
        self.assertIn("overlap", " ".join(verify_schedule(orders, config, tampered).errors))
        later_release = (replace(orders[0], release=orders[0].release + timedelta(hours=1)), *orders[1:])
        self.assertIn("before release", " ".join(verify_schedule(later_release, config, valid).errors))
        early_deadline = (replace(orders[0], deadline=orders[0].release + timedelta(minutes=90)), *orders[1:])
        self.assertIn("deadline missed", " ".join(verify_schedule(early_deadline, config, valid).errors))
        altered_duration = (replace(orders[0], duration_source=D(2)), *orders[1:])
        self.assertIn("processing duration", " ".join(verify_schedule(altered_duration, config, valid).errors))

    def test_final_non_black_and_terminal_boundary(self):
        orders, config = tiny_case()
        schedule, errors = build_schedule(orders, config)
        self.assertFalse(errors)
        self.assertEqual(orders[-1].shade, "A")
        self.assertEqual(schedule.terminal_cleanups[0].start, schedule.placements[-1].process_end)
        self.assertEqual(evaluate_resources(orders, config, schedule).terminal_cleaning, 10)
        self.assertFalse(verify_schedule(orders, config, replace(schedule, terminal_cleanups=())).valid)
        config = replace(config, terminal_cleaning=False)
        schedule, errors = build_schedule(orders, config)
        self.assertFalse(errors)
        self.assertEqual(schedule.terminal_cleanups, ())
        self.assertEqual(evaluate_resources(orders, config, schedule).total, 120)

    def test_verifier_rejects_unauthorised_cleaning_exemption(self):
        orders, config = tiny_case()
        proposal = plan(orders, config).proposal
        self.assertTrue(any(not p.cleaning_required for p in proposal.placements))
        check = verify_schedule(orders, replace(config, allow_cleaning_exemptions=False), proposal)
        self.assertIn("unauthorised", " ".join(check.errors))

    def test_availability_windows_and_release_are_enforced(self):
        orders, config = tiny_case()
        one = (replace(orders[0], duration_source=D(2)),)
        start = orders[0].release
        machine = replace(config.machines[0], availability=(
            Window(start, start + timedelta(hours=3)),
            Window(start + timedelta(hours=6), start + timedelta(hours=12)),
        ))
        config = replace(config, machines=(machine,), transition_permissions=())
        result = plan(one, config)
        self.assertTrue(result.proposal_verification.valid)
        self.assertEqual(result.proposal.placements[0].cleaning_start, start + timedelta(hours=6))
        self.assertEqual(result.proposal.terminal_cleanups[0].end, start + timedelta(hours=10))
        closed = replace(config, machines=(replace(machine, availability=(machine.availability[0],)),))
        self.assertIsNone(plan(one, closed).proposal)
        shifted = replace(result.proposal, placements=(replace(result.proposal.placements[0],
            cleaning_start=start + timedelta(hours=2), process_start=start + timedelta(hours=3),
            process_end=start + timedelta(hours=5)),))
        self.assertIn("outside operating availability", " ".join(verify_schedule(one, config, shifted).errors))

    def test_initial_clean_state_and_duration_interpretation_are_explicit(self):
        orders, config = tiny_case()
        config = replace(config, machines=(replace(config.machines[0], initially_clean=True),),
                         hours_per_duration_unit=D("0.5"))
        result = plan(orders, config)
        first = result.baseline.placements[0]
        self.assertFalse(first.cleaning_required)
        self.assertEqual(first.cleaning_start, first.process_start)
        self.assertEqual(first.process_end - first.process_start, timedelta(minutes=30))
        self.assertEqual(result.baseline_resources.cleaning_events, 3)

    def test_configuration_validation_and_roundtrip(self):
        _, config = tiny_case()
        self.assertEqual(parse_config(to_json(config)), config)
        for kwargs in ({"cleaning_water": D(-1)}, {"hours_per_duration_unit": D(0)},
                       {"resource_unit": "litres"}, {"allow_cleaning_exemptions": "yes"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                replace(config, **kwargs)
        with self.assertRaises(ValueError):
            replace(config.machines[0], virtual_id="actual-machine")
        with self.assertRaises(ValueError):
            replace(config.machines[0], availability=tuple(reversed((
                Window(datetime(2020, 1, 1), datetime(2020, 1, 2)),
                Window(datetime(2020, 1, 3), datetime(2020, 1, 4))))))

    def test_validated_complete_import_only_and_no_recorded_water_in_scenario_orders(self):
        with self.assertRaises(ValueError):
            orders_from_import(import_orders(b"invalid"))
        result = load_bundled_orders()
        before = copy.deepcopy(result.records)
        orders = orders_from_import(result)
        self.assertEqual(len(orders), 35)
        self.assertEqual(orders[0].release, datetime(2019, 11, 10))
        self.assertEqual(orders[0].deadline, datetime(2019, 12, 31))
        self.assertNotIn("water", str(orders[0]))
        plan(orders, demo_config(result), max_passes=0)
        self.assertEqual(result.records, before)

    def test_full_case_determinism_same_evaluator_and_export_reverification(self):
        result = load_bundled_orders()
        orders, config = orders_from_import(result), demo_config(result)
        comparison = plan(orders, config)
        again = plan(orders, config)
        self.assertEqual(comparison, again)
        self.assertTrue(comparison.baseline_verification.valid)
        self.assertTrue(comparison.proposal_verification.valid)
        self.assertEqual(comparison.baseline_resources.total, D(27300))
        self.assertEqual(comparison.improvement, 0)
        artifact = json.loads(export_plan(result, config, comparison))
        self.assertTrue(artifact["verification"]["proposal_valid"])
        self.assertEqual(artifact["source"]["recorded_water_total_separate_from_comparison"], "47950")
        self.assertEqual(len(artifact["proposed_schedule"]["placements"]), 35)
        tampered = replace(comparison, proposal=replace(comparison.proposal, placements=comparison.proposal.placements[:-1]))
        with self.assertRaises(ValueError):
            export_plan(result, config, tampered)

    def test_full_case_explicit_permissions_lower_cleaning_only(self):
        result = load_bundled_orders()
        orders = orders_from_import(result)
        config = replace(demo_config(result), allow_cleaning_exemptions=True)
        comparison = plan(orders, config)
        self.assertTrue(comparison.proposal_verification.valid)
        self.assertEqual(comparison.improvement, 1750)
        self.assertEqual(comparison.baseline_resources.total, 25550)
        self.assertEqual(comparison.proposal_resources.total, 23800)
        self.assertEqual(comparison.baseline_resources.process_a, comparison.proposal_resources.process_a)
        self.assertEqual(comparison.baseline_resources.process_b, comparison.proposal_resources.process_b)
        self.assertEqual({p.order_id: p.quantity for p in comparison.baseline.placements},
                         {p.order_id: p.quantity for p in comparison.proposal.placements})


if __name__ == "__main__":
    unittest.main()
