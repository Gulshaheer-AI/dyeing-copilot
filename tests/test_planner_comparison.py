import json
import unittest
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock

from app.importer import load_bundled_orders
from copilot.amd import AMDConfig
from copilot.evidence import build_evidence
from copilot.workflow import build_messages, explain, mock_content, validate_output
from planner.comparison import compare_schedules, deadline_performance
from planner.contracts import Schedule
from planner.review_package import export_review_package
from planner.scenario import demo_config, orders_from_import
from planner.search import plan
from test_scheduler import tiny_case


class PlannerComparisonTests(unittest.TestCase):
    def test_tiny_transition_differences_reconcile_with_initial_and_terminal_cleaning(self):
        orders, config = tiny_case()
        planned = plan(orders, config)
        report = compare_schedules(orders, config, planned.baseline, planned.proposal)
        self.assertEqual(report["cleaning_counts"]["baseline"], {"initial": 1, "between_orders": 2, "terminal": 1, "total": 4})
        self.assertEqual(report["cleaning_counts"]["proposal"], {"initial": 1, "between_orders": 1, "terminal": 1, "total": 3})
        self.assertEqual(report["difference"], 10)
        self.assertEqual(sum(r["resource_difference"] for r in report["order_transitions"] + report["terminal_transitions"]), 10)
        self.assertEqual(report["reconciliation"]["process_resource_difference"], 0)
        exempt = [r for r in report["order_transitions"] if not r["proposal"]["cleaning_required"]][0]
        pair = (exempt["proposal"]["machine"], exempt["proposal"]["predecessor"], exempt["order_id"])
        self.assertIn(pair, {(p.virtual_id, p.from_order_id, p.to_order_id) for p in config.transition_permissions})
        self.assertEqual(exempt["proposal"]["rule"], "activated_exact_permission")

    def test_disabled_cleaning_no_change_and_explicit_boundaries(self):
        orders, config = tiny_case(enabled=False)
        result = plan(orders, config)
        report = compare_schedules(orders, config, result.baseline, result.proposal)
        self.assertEqual(report["difference"], 0)
        self.assertTrue(all(not r["transition_changed"] for r in report["order_transitions"]))
        config = replace(config, terminal_cleaning=False,
                         machines=(replace(config.machines[0], initially_clean=True),))
        result = plan(orders, config)
        report = compare_schedules(orders, config, result.baseline, result.proposal)
        self.assertEqual(report["cleaning_counts"]["proposal"], {"initial": 0, "between_orders": 2, "terminal": 0, "total": 2})
        self.assertEqual(report["terminal_transitions"][0]["proposal"]["rule"], "terminal_cleanup_disabled")

    def test_reassignment_and_unused_machine_terminal_accounting(self):
        orders, config = tiny_case(enabled=False)
        orders = orders[:1]
        config = replace(config, transition_permissions=(), machines=(config.machines[0],
            replace(config.machines[0], virtual_id="virtual-other")))
        baseline = plan(orders, config).baseline
        other = next(m.virtual_id for m in config.machines if m.virtual_id != baseline.placements[0].virtual_id)
        proposal = Schedule((replace(baseline.placements[0], virtual_id=other),),
                            (replace(baseline.terminal_cleanups[0], virtual_id=other),))
        report = compare_schedules(orders, config, baseline, proposal)
        self.assertEqual(report["changes"]["machine_assignments"], 1)
        self.assertEqual(sorted(r["cleaning_events_difference"] for r in report["terminal_transitions"]), [-1, 1])
        self.assertEqual(report["difference"], 0)
        self.assertEqual(report["cleaning_counts"]["proposal"]["total"], 2)

    def test_deadline_boundary_late_missing_and_invalid_comparison_rejection(self):
        orders, config = tiny_case(enabled=False)
        baseline = plan(orders, config).baseline
        exact = tuple(replace(o, deadline=p.process_end) for o, p in zip(orders, baseline.placements))
        summary = deadline_performance(exact, baseline)
        self.assertEqual(summary["on_time"], 3)
        self.assertTrue(all(row["slack_hours"] == 0 for row in summary["orders"]))
        late = replace(baseline, placements=(replace(baseline.placements[0], process_end=exact[0].deadline + timedelta(microseconds=1)),))
        summary = deadline_performance(exact, late)
        self.assertEqual((summary["late"], summary["missing"]), (1, 2))
        with self.assertRaisesRegex(ValueError, "independent verification"):
            compare_schedules(orders, config, baseline, late)

    def test_bundled_scenarios_and_review_export(self):
        source = load_bundled_orders()
        for enabled, total_a, total_b, count_a, count_b in ((False, 27300, 27300, 39, 39), (True, 25550, 23800, 34, 29)):
            config = replace(demo_config(source), allow_cleaning_exemptions=enabled)
            result = plan(orders_from_import(source), config)
            package = json.loads(export_review_package(source, config, result))
            report = package["planner_comparison"]
            self.assertEqual(Decimal(report["resources"]["baseline"]["total"]), total_a)
            self.assertEqual(Decimal(report["resources"]["proposal"]["total"]), total_b)
            self.assertEqual((report["cleaning_counts"]["baseline"]["total"], report["cleaning_counts"]["proposal"]["total"]), (count_a, count_b))
            self.assertEqual(report["deadlines"]["baseline"]["on_time"], 35)
            self.assertEqual(report["deadlines"]["proposal"]["late"], 0)
            self.assertEqual(len(report["order_transitions"]), 35)
            self.assertIn("never production approval", package["review_boundary"])
            self.assertEqual(Decimal(package["source"]["recorded_water_total_separate_from_comparison"]), 47950)


class PlannerGroundingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = load_bundled_orders()
        config = replace(demo_config(source), allow_cleaning_exemptions=True)
        cls.result = plan(orders_from_import(source), config)
        cls.bundle = build_evidence(source, "Explain this comparison", config=config, comparison=cls.result)

    def test_transition_statements_match_computed_rows_and_reject_invented_reason(self):
        answer = explain(self.bundle, "Explain this comparison", scope="scenario", mode="mock")
        examples = next(c for c in answer.output.explanation if c.statement_id == "transition_examples")
        for ref in examples.evidence_references:
            row = self.bundle["facts"][ref]["value"]
            self.assertIn("Order " + row["order_id"], examples.text)
            self.assertTrue(row["transition_changed"])
        output = answer.output.model_dump()
        output["explanation"][-1]["text"] += " Similar colour proves washing is unnecessary."
        with self.assertRaisesRegex(ValueError, "unsupported explanatory"):
            validate_output(json.dumps(output), self.bundle)
        output = answer.output.model_dump()
        output["explanation"][-1]["evidence_references"] = ["fact:scenario.transition.999"]
        with self.assertRaises(ValueError):
            validate_output(json.dumps(output), self.bundle)

    def test_requested_order_retrieval_and_missing_transition_explanation_rejection(self):
        question = "Explain order 27 in this scenario comparison"
        envelope = json.loads(build_messages(self.bundle, question)[1]["content"])
        self.assertIn("fact:scenario.transition.27", envelope["facts"])
        self.assertIn("planner_order_27", envelope["catalog"]["statements"])
        answer = explain(self.bundle, question, scope="scenario", mode="mock")
        self.assertIn("planner_order_27", [claim.statement_id for claim in answer.output.explanation])
        content = json.loads(mock_content(self.bundle, question))
        content["explanation"] = content["explanation"][:2]
        response = Mock(status_code=200)
        response.json.return_value = {"model": "test-model", "choices": [{"message": {"content": json.dumps(content)}, "finish_reason": "stop"}]}
        with self.assertRaisesRegex(ValueError, "transition details"):
            explain(self.bundle, question, scope="scenario", config=AMDConfig("test-key", "https://developer.amd.com.cn/radeon/api/v1", "test-model"), transport=Mock(return_value=response))


if __name__ == "__main__":
    unittest.main()
