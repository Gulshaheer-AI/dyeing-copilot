import copy
import hashlib
import json
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

from app.importer import load_bundled_orders
from copilot.amd import AMDConfig
from copilot.evidence import build_evidence
from copilot.planning_interpreter import (InterpretationRejected, interpret, interpret_once, make_request, messages)
from copilot.planning_schema import Interpretation, InterpretationResponse, validate_interpretation
from planner.change_export import export_change_audit
from planner.change_requests import apply_changes, apply_and_reschedule, initial_case, preview_changes, reset_case, subtract_interval
from planner.evaluator import evaluate_resources
from planner.review_package import export_review_package
from planner.scenario import Window, demo_config
from planner.search import plan
from planner.verifier import verify_schedule

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evaluation/planning_requests.json"


def fixture(case, text, changes):
    response = InterpretationResponse.model_validate_json(json.dumps({"status": "ready", "changes": [
        {**change, "supporting_excerpt": text} for change in changes], "clarification_questions": [], "unsupported_reasons": []}))
    return Interpretation(make_request(case, text), response, {"origin": "mock", "actual_model": None, "purpose": "offline_test"})


class PlanningRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = load_bundled_orders()
        cls.case = initial_case(cls.source, demo_config(cls.source))

    def deadline(self, day="2019-12-22T18:00"):
        return fixture(self.case, "Change order 12 deadline to " + day + ".",
                       [{"operation": "order_deadline", "order_id": "12", "deadline": day}])

    def test_frozen_corpus_and_development_contract_only(self):
        protocol = json.loads((ROOT / "evaluation/frozen_protocol.json").read_text())
        self.assertEqual(hashlib.sha256(DATA.read_bytes()).hexdigest(), protocol["request_corpus_sha256"])
        cases = json.loads(DATA.read_text())["cases"]
        self.assertEqual(len(cases), 30)
        self.assertEqual(sum(c["split"] == "held_out" for c in cases), 10)
        # No held-out responses/examples are used for development assertions.
        for item in [c for c in cases if c["split"] == "development"]:
            with self.subTest(item=item["id"]):
                output = {"status": item["status"], "changes": [{**c, "supporting_excerpt": item["text"]} for c in item["changes"]],
                          "clarification_questions": ["Provide exact references and ISO datetimes."] if item["status"] == "clarification" else [],
                          "unsupported_reasons": [{"supporting_excerpt": item["text"], "reason": "Outside permitted operations."}] if item["status"] == "unsupported" else []}
                parsed = InterpretationResponse.model_validate_json(json.dumps(output))
                self.assertEqual(validate_interpretation(parsed, make_request(self.case, item["text"])).status, item["status"])

    def test_preview_no_mutation_atomic_apply_and_separate_provenance(self):
        before = copy.deepcopy(self.case)
        answer = self.deadline()
        preview = preview_changes(self.case, answer)
        self.assertEqual(self.case, before)
        self.assertEqual(preview[0]["before"], "2019-12-21 00:00:00")
        changed, result = apply_and_reschedule(self.case, answer)
        self.assertEqual(self.case, before)
        self.assertEqual(changed.original_orders, before.original_orders)
        self.assertEqual(changed.orders[11].deadline, datetime(2019, 12, 22, 18))
        self.assertEqual(changed.overrides[0].supporting_excerpt, answer.request.text)
        self.assertEqual(changed.history[0]["receipt"]["origin"], "mock")
        self.assertTrue(result.proposal_verification.valid)
        package = json.loads(export_review_package(self.source, changed.config, result, case=changed))
        self.assertEqual(package["orders"][11]["deadline"], "2019-12-22 18:00:00")
        bundle = build_evidence(self.source, "Explain comparison", config=changed.config, comparison=result, case=changed)
        self.assertIsNotNone(bundle["scenario"])

    def test_stale_reset_and_source_rejection(self):
        answer = self.deadline()
        changed = apply_changes(self.case, answer)
        with self.assertRaisesRegex(ValueError, "Stale"):
            apply_changes(changed, answer)
        restored = reset_case(changed)
        self.assertEqual(restored.orders, self.case.original_orders)
        self.assertEqual(restored.config, self.case.original_config)
        self.assertNotEqual(restored.fingerprint, self.case.fingerprint)
        with self.assertRaises(ValueError):
            apply_changes(restored, answer)
        with self.assertRaises(ValueError):
            apply_changes(replace(self.case, source_sha256="0" * 64), answer)

    def test_interval_subtraction_overlap_boundaries_and_empty_machine(self):
        day = datetime(2019, 12, 20)
        windows = (Window(day, day + timedelta(days=1)),)
        first = subtract_interval(windows, day + timedelta(hours=2), day + timedelta(hours=10))
        overlap = subtract_interval(first, day + timedelta(hours=8), day + timedelta(hours=12))
        self.assertEqual(overlap, (Window(day, day + timedelta(hours=2)), Window(day + timedelta(hours=12), day + timedelta(days=1))))
        self.assertEqual(subtract_interval(windows, day - timedelta(days=1), day), windows)
        self.assertEqual(subtract_interval(windows, day, day + timedelta(days=2)), ())
        text = "virtual-Open-Cotton outage from 2019-01-01T00:00 to 2020-02-01T00:00."
        answer = fixture(self.case, text, [{"operation": "machine_unavailability", "machine_id": "virtual-Open-Cotton", "start": "2019-01-01T00:00", "end": "2020-02-01T00:00"}])
        changed, result = apply_and_reschedule(self.case, answer)
        self.assertEqual(next(m for m in changed.config.machines if m.virtual_id == "virtual-Open-Cotton").availability, ())
        self.assertIsNone(result.proposal)
        audit = json.loads(export_change_audit(self.source, changed, result))
        self.assertIn("not_proven_globally_infeasible", audit["status"])
        self.assertFalse(audit["verification"]["baseline"]["valid"])

    def test_effective_deadline_verifier_and_terminal_availability(self):
        old = plan(self.case.orders, self.case.config)
        p = old.proposal.placements[0]
        text = f"Change order {p.order_id} deadline to {self.case.orders[int(p.order_id)-1].release:%Y-%m-%dT%H:%M}."
        # At release is rejected before application.
        answer = fixture(self.case, text, [{"operation": "order_deadline", "order_id": p.order_id, "deadline": self.case.orders[int(p.order_id)-1].release.isoformat()}])
        with self.assertRaises(ValueError):
            apply_changes(self.case, answer)
        order = next(o for o in self.case.orders if o.order_id == p.order_id)
        deadline = order.release + timedelta(hours=1)
        answer = fixture(self.case, f"Order {p.order_id} must finish by {deadline:%Y-%m-%dT%H:%M}.",
                         [{"operation": "order_deadline", "order_id": p.order_id, "deadline": deadline.isoformat()}])
        changed = apply_changes(self.case, answer)
        self.assertFalse(verify_schedule(changed.orders, changed.config, old.proposal).valid)
        tail = old.proposal.terminal_cleanups[0]
        text = f"{tail.virtual_id} outage from {tail.start:%Y-%m-%dT%H:%M} to {tail.end:%Y-%m-%dT%H:%M}."
        answer = fixture(self.case, text, [{"operation": "machine_unavailability", "machine_id": tail.virtual_id, "start": tail.start.isoformat(), "end": tail.end.isoformat()}])
        changed, rerun = apply_and_reschedule(self.case, answer)
        self.assertIn("terminal cleaning outside availability", " ".join(verify_schedule(changed.orders, changed.config, old.proposal).errors))
        if rerun.proposal:
            self.assertTrue(verify_schedule(changed.orders, changed.config, rerun.proposal).valid)

    def test_unknown_unsupported_conflicting_and_ungrounded_changes_rejected_atomically(self):
        good = self.deadline()
        for modify in (lambda r: r["changes"].append(dict(r["changes"][0])),
                       lambda r: r["changes"][0].update(order_id="999"),
                       lambda r: r["changes"][0].update(supporting_excerpt="invented"),
                       lambda r: r["changes"][0].update(deadline="2026-10-15T10:00"),
                       lambda r: r["changes"][0].update(capacity=9000),
                       lambda r: r["changes"][0].update(operation="enable_cleaning")):
            data = good.response.model_dump()
            modify(data)
            with self.assertRaises(ValueError):
                response = InterpretationResponse.model_validate_json(json.dumps(data))
                apply_changes(self.case, replace(good, response=response))
        mixed_text = good.request.text + " Disable cleaning."
        mixed = replace(good, request=make_request(self.case, mixed_text))
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            apply_changes(self.case, mixed)
        unknown = replace(good, request=make_request(self.case, good.request.text + " Also order 999 is urgent."))
        with self.assertRaisesRegex(ValueError, "Unknown"):
            apply_changes(self.case, unknown)

    def test_schema_origin_injection_and_duplicate_interpretation_guard(self):
        answer = self.deadline()
        response = Mock(status_code=200)
        response.json.return_value = {"model": "actual-test-model", "choices": [{"message": {"content": json.dumps({"status":"ready", "changes":[{"operation":"order_deadline", "order_id":"12", "deadline":"2019-12-22T18:00", "clause_id":"c1"}], "clarification_questions":[], "unsupported_reasons":[]})}, "finish_reason": "stop"}]}
        transport = Mock(return_value=response)
        config = AMDConfig("private-test-key", "https://developer.amd.com.cn/radeon/api/v1", "test-model")
        accepted = interpret(answer.request, config=config, transport=transport)
        self.assertEqual(accepted.receipt["origin"], "mock")
        self.assertEqual(accepted.receipt["actual_model"], "actual-test-model")
        self.assertNotIn("private-test-key", json.dumps(accepted.receipt))
        state, generate = {}, Mock(return_value=accepted)
        self.assertTrue(interpret_once(state, answer.request, generate)[1])
        self.assertFalse(interpret_once(state, answer.request, generate)[1])
        self.assertEqual(generate.call_count, 1)
        with self.assertRaises(ValueError):
            interpret_once({"planning_inflight": "other"}, answer.request, generate)
        encoded = json.loads(response.json.return_value["choices"][0]["message"]["content"])
        encoded["execute_python"] = "print('unsafe')"
        response.json.return_value["choices"][0]["message"]["content"] = json.dumps(encoded)
        with self.assertRaises(InterpretationRejected) as rejected:
            interpret(answer.request, config=config, transport=transport)
        self.assertEqual(rejected.exception.receipt["validation"], "rejected")
        self.assertEqual(messages(answer.request)[0]["role"], "system")


if __name__ == "__main__":
    unittest.main()
