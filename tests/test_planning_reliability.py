from ui_helpers import click as ui_click
from legacy_ui import select_legacy
import hashlib
from preservation import preserved_sha
import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from app.importer import load_bundled_orders
from copilot.amd import AMDConfig, AMDConnectionError
from copilot.planning_guard import local_decision
from copilot.planning_interpreter import interpret, make_request
from copilot.planning_schema import InterpretationResponse, validate_interpretation
from planner.change_requests import initial_case, apply_and_reschedule, preview_changes, reset_case
from planner.scenario import demo_config
from test_interface import APP
from test_planning_requests import fixture

ROOT = Path(__file__).resolve().parents[1]


class PlanningReliabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = load_bundled_orders()
        cls.case = initial_case(source, demo_config(source))

    def test_preserved_milestone_8_files_and_new_development_contract(self):
        baseline = json.loads((ROOT / "reports/milestone_8_1_preservation_baseline.json").read_text())
        for name, digest in baseline.items():
            self.assertEqual(preserved_sha(ROOT, name), digest, name)
        protocol = json.loads((ROOT / "evaluation/protocol_v8_1.json").read_text())
        data_path = ROOT / "evaluation/planning_requests_v8_1.json"
        self.assertEqual(hashlib.sha256(data_path.read_bytes()).hexdigest(), protocol["corpus_sha256"])
        data = json.loads(data_path.read_text())
        self.assertEqual(sum(r["split"] == "held_out" for r in data["cases"]), 12)
        for item in [r for r in data["cases"] if r["split"] == "development"]:
            with self.subTest(id=item["id"]):
                request = make_request(self.case, item["text"])
                decision = local_decision(request)
                if item["route"] == "local":
                    self.assertEqual(decision.status, item["status"])
                else:
                    self.assertIsNone(decision)
                    answer = fixture(self.case, item["text"], item["changes"])
                    self.assertEqual(validate_interpretation(answer.response, request).status, "ready")

    def test_every_known_machine_allowed_but_actual_pressure_instruction_blocked(self):
        for machine in self.case.config.machines:
            text = f"{machine.virtual_id} outage from 2019-12-20T08:00 to 2019-12-20T16:00."
            self.assertIsNone(local_decision(make_request(self.case, text)))
            answer = fixture(self.case, text, [{"operation":"machine_unavailability", "machine_id":machine.virtual_id,
                "start":"2019-12-20T08:00", "end":"2019-12-20T16:00"}])
            validate_interpretation(answer.response, answer.request)
        for text in ("Change pressure on virtual-Pressure-PolyCotton.", "Set temperature on virtual-Pressure-PolyCotton.",
                     "virtual-Pressure-PolyCotton outage from 2019-12-20T08:00 to 2019-12-20T16:00. Disable cleaning."):
            self.assertEqual(local_decision(make_request(self.case, text)).status, "unsupported")

    def test_unknown_extended_identifier_and_relative_date_are_local_not_amd(self):
        for text, expected in (("virtual-Pressure-PolyCotton-99 unavailable from 2019-12-20T08:00 to 2019-12-20T16:00.", "virtual-Pressure-PolyCotton-99"),
                               ("Set order 120 deadline to 2019-12-22T18:00.", "120"),
                               ("Make order 12 urgent by Friday.", "historical")):
            with patch("copilot.planning_interpreter.request_completion") as api, patch("copilot.planning_interpreter.load_config", side_effect=AssertionError("Local checks need no key")):
                answer = interpret(make_request(self.case, text))
            api.assert_not_called()
            self.assertEqual(answer.receipt["origin"], "local_validation")
            self.assertFalse(answer.receipt["api_request_performed"])
            self.assertIsNone(answer.receipt["actual_model"])
            self.assertIn(expected, answer.response.clarification_questions[0])

    def test_negation_conflicts_and_unclear_associations_cannot_be_applied(self):
        for text in ("Do not change order 12’s deadline.", "Don't change order 12 deadline to 2019-12-22T18:00.",
                     "Order 12 deadline 2019-12-22T18:00, but not order 13 deadline 2019-12-28T12:00.",
                     "Set order 12 deadline to 2019-12-22T18:00 and to 2019-12-23T18:00.",
                     "Set deadlines for orders 12 and 13 respectively to 2019-12-22T18:00 and 2019-12-28T12:00."):
            answer = interpret(make_request(self.case, text))
            self.assertEqual(answer.response.status, "clarification")
            with self.assertRaises(ValueError):
                preview_changes(self.case, answer)

    def test_swapped_deadlines_rejected_even_with_exact_entire_request_excerpt(self):
        text = "Set order 12 deadline to 2019-12-22T18:00. Set order 13 deadline to 2019-12-28T12:00."
        changes = [{"operation":"order_deadline","order_id":"12","deadline":"2019-12-22T18:00"},
                   {"operation":"order_deadline","order_id":"13","deadline":"2019-12-28T12:00"}]
        answer = fixture(self.case, text, changes)
        validate_interpretation(answer.response, answer.request)
        swapped = answer.response.model_dump()
        swapped["changes"][0]["deadline"], swapped["changes"][1]["deadline"] = swapped["changes"][1]["deadline"], swapped["changes"][0]["deadline"]
        with self.assertRaisesRegex(ValueError, "association"):
            validate_interpretation(InterpretationResponse.model_validate_json(json.dumps(swapped)), answer.request)
        changed, comparison = apply_and_reschedule(self.case, answer)
        self.assertTrue(comparison.proposal_verification.valid)
        self.assertEqual(reset_case(changed).orders, self.case.orders)

    def test_multiple_machines_distinct_intervals_cannot_swap(self):
        text = "virtual-Open-Cotton outage from 2019-12-20T01:00 to 2019-12-20T05:00; virtual-Jet-Cotton outage from 2019-12-21T07:00 to 2019-12-21T13:00."
        answer = fixture(self.case, text, [
            {"operation":"machine_unavailability","machine_id":"virtual-Open-Cotton","start":"2019-12-20T01:00","end":"2019-12-20T05:00"},
            {"operation":"machine_unavailability","machine_id":"virtual-Jet-Cotton","start":"2019-12-21T07:00","end":"2019-12-21T13:00"}])
        validate_interpretation(answer.response, answer.request)
        data = answer.response.model_dump()
        data["changes"][0]["machine_id"], data["changes"][1]["machine_id"] = data["changes"][1]["machine_id"], data["changes"][0]["machine_id"]
        with self.assertRaisesRegex(ValueError, "association"):
            validate_interpretation(InterpretationResponse.model_validate_json(json.dumps(data)), answer.request)

    def test_old_exposed_failures_are_development_regressions_only(self):
        old = json.loads((ROOT / "evaluation/planning_requests.json").read_text())
        for item in [c for c in old["cases"] if c["id"] in ("h01", "h05", "h06", "h10")]:
            request = make_request(self.case, item["text"])
            if item["status"] == "ready":
                self.assertIsNone(local_decision(request))
                validate_interpretation(fixture(self.case, item["text"], item["changes"]).response, request)
            else:
                with patch("copilot.planning_interpreter.request_completion") as api:
                    answer = interpret(request)
                api.assert_not_called()
                self.assertEqual(answer.response.status, item["status"])

    def test_local_ui_without_configuration_never_reports_live_success(self):
        with patch("app.planning_changes_view.load_config", side_effect=AMDConnectionError("Missing config")), \
             patch("copilot.planning_interpreter.request_completion") as api:
            app = AppTest.from_file(APP).run(timeout=40)
            ui_click(app,"Batch scheduling simulator")
            select_legacy(app)
            next(b for b in app.button if b.label == "Load demo setup").click().run(timeout=40)
            app.text_area[1].set_value("Set order 120 deadline to 2019-12-22T18:00.").run(timeout=40)
            next(b for b in app.button if b.label == "Interpret planning request with AMD").click().run(timeout=40)
            self.assertFalse(app.exception)
            self.assertTrue(any("Local validation only" in info.value for info in app.info))
            self.assertFalse(any("Validated live AMD" in s.value for s in app.success))
            self.assertFalse(any(b.label == "Apply changes and reschedule" for b in app.button))
            api.assert_not_called()

    def test_pressure_ui_preview_confirm_verified_schedule_and_reset(self):
        with patch("app.planning_changes_view.load_config", return_value=AMDConfig("offline-test-key", "https://developer.amd.com.cn/radeon/api/v1", "test-model")):
            app = AppTest.from_file(APP).run(timeout=40)
            def click(label):
                ui_click(app,label)
            click("Batch scheduling simulator")
            select_legacy(app)
            click("Load demo setup")
            click("Run scenario comparison")
            original = app.session_state["planning_case"]
            text = "virtual-Pressure-PolyCotton unavailable from 2019-12-20T08:00 to 2019-12-20T16:00."
            app.text_area[1].set_value(text).run(timeout=40)
            answer = fixture(original, text, [{"operation":"machine_unavailability", "machine_id":"virtual-Pressure-PolyCotton",
                                               "start":"2019-12-20T08:00", "end":"2019-12-20T16:00"}])
            with patch("app.planning_changes_view.interpret", return_value=answer):
                click("Interpret planning request with AMD")
                self.assertEqual(app.session_state["planning_case"], original)
                self.assertTrue(any("MOCKED interpretation" in w.value for w in app.warning))
                click("Apply changes and reschedule")
            self.assertFalse(app.exception)
            self.assertTrue(app.session_state["sim_comparison"][1].proposal_verification.valid)
            self.assertNotEqual(app.session_state["planning_case"].config, original.config)
            click("Reset to original scenario and reschedule")
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["planning_case"].orders, original.orders)
            self.assertEqual(app.session_state["planning_case"].config, original.config)
            self.assertTrue(app.session_state["sim_comparison"][1].proposal_verification.valid)


if __name__ == "__main__":
    unittest.main()
