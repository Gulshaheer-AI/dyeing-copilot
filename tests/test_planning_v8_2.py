from ui_helpers import click as ui_click
from legacy_ui import select_legacy
import hashlib
from preservation import preserved_sha
import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from app.importer import load_bundled_orders
from copilot.planning_contract import reconstruct, source_spans
from copilot.planning_diagnostics import EvaluationDiagnostics
from copilot.planning_interpreter import make_request
from copilot.planning_manual import manual_proposal
from copilot.planning_schema import validate_interpretation
from planner.change_requests import initial_case, preview_changes, apply_and_reschedule, reset_case
from planner.scenario import demo_config
from test_interface import APP

ROOT = Path(__file__).resolve().parents[1]


class PlanningV82Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = load_bundled_orders()
        cls.case = initial_case(source, demo_config(source))

    def test_history_and_protected_files_unchanged(self):
        for filename in ("milestone_8_2_preservation_baseline.json", "milestone_8_2_protected_baseline.json"):
            for name, expected in json.loads((ROOT / "reports" / filename).read_text()).items():
                # Historical full-acquisition files absent from distribution are not
                # listed; every protected app/evidence file must be included.
                self.assertEqual(preserved_sha(ROOT, name), expected, name)

    def test_clause_reconstruction_and_minute_second_precision(self):
        text = "Order 11 deadline 2019-12-23 18:15; order 13 deadline 2019-12-24T17:20:30."
        req = make_request(self.case, text)
        spans = source_spans(req)
        data = {"status": "ready", "changes": [
            {"operation": "order_deadline", "order_id": "11", "deadline": "2019-12-23T18:15", "clause_id": spans[0]["clause_id"]},
            {"operation": "order_deadline", "order_id": "13", "deadline": "2019-12-24 17:20:30", "clause_id": spans[1]["clause_id"]}],
            "clarification_questions": [], "unsupported_reasons": []}
        response = reconstruct(json.dumps(data), req)
        validate_interpretation(response, req)
        for span, change in zip(spans, response.changes):
            self.assertEqual(change.supporting_excerpt, text[span["start"]:span["end"]])
        data["changes"][0]["clause_id"] = spans[1]["clause_id"]
        with self.assertRaises(ValueError):
            validate_interpretation(reconstruct(json.dumps(data), req), req)
        data["changes"][0]["clause_id"] = "invented"
        with self.assertRaisesRegex(ValueError, "clause"):
            reconstruct(json.dumps(data), req)

    def test_swapped_values_rejected_even_with_correct_clause_ids(self):
        req = make_request(self.case, "order 11 deadline 2019-12-23T18:00; order 13 deadline 2019-12-25T19:00")
        data = {"status":"ready", "changes":[
            {"operation":"order_deadline", "order_id":"11", "deadline":"2019-12-25T19:00", "clause_id":"c0"},
            {"operation":"order_deadline", "order_id":"13", "deadline":"2019-12-23T18:00", "clause_id":"c1"}],
            "clarification_questions":[], "unsupported_reasons":[]}
        with self.assertRaises(ValueError):
            validate_interpretation(reconstruct(json.dumps(data), req), req)

    def test_diagnostics_are_bounded_corpus_only_and_credential_screened(self):
        corpus = ROOT / "evaluation/planning_requests_v8_2.json"
        text = json.loads(corpus.read_text())["cases"][0]["text"]
        sink = EvaluationDiagnostics(corpus, limit=2)
        req = make_request(self.case, text)
        sink.capture(req, '{"status":"ready"}', {"origin":"mock"}, "schema error", "private-key")
        self.assertEqual(sink.records[0]["content"], '{"status":"ready"}')
        sink.capture(req, 'Authorization: Bearer private-key', {}, None, 'private-key')
        self.assertIsNone(sink.records[1]["content"])
        self.assertNotIn("private-key", json.dumps(sink.records))
        with self.assertRaises(ValueError):
            sink.capture(req, "bounded", {}, None, "secret")
        with self.assertRaises(ValueError):
            EvaluationDiagnostics(corpus, limit=2).capture(make_request(self.case, "private user text"), "x", {}, None, "secret")

    def test_manual_shared_preview_apply_verify_stale_reset_and_errors(self):
        before = self.case.fingerprint
        answer = manual_proposal(self.case, operation="order_deadline", identifier="12", deadline=datetime(2019,12,23,18,15,30))
        self.assertEqual(answer.receipt["origin"], "manual")
        self.assertFalse(answer.receipt["api_request_performed"])
        preview_changes(self.case, answer)
        self.assertEqual(self.case.fingerprint, before)
        updated, result = apply_and_reschedule(self.case, answer)
        self.assertTrue(result.proposal_verification.valid)
        self.assertEqual(updated.history[-1]["receipt"]["origin"], "manual")
        with self.assertRaisesRegex(ValueError, "Stale"):
            preview_changes(updated, answer)
        self.assertEqual(reset_case(updated).orders, self.case.orders)
        for machine in self.case.config.machines:
            answer = manual_proposal(self.case, operation="machine_unavailability", identifier=machine.virtual_id,
                start=datetime(2019,12,23,8), end=datetime(2019,12,23,12))
            self.assertTrue(preview_changes(self.case, answer))
        for kw in ({"operation":"order_deadline", "identifier":"999", "deadline":datetime(2019,12,23)},
                   {"operation":"order_deadline", "identifier":"12", "deadline":datetime(2019,1,1)},
                   {"operation":"machine_unavailability", "identifier":"virtual-Open-Cotton", "start":datetime(2019,12,23), "end":datetime(2019,12,22)},
                   {"operation":"pressure", "identifier":"virtual-Pressure-PolyCotton"}):
            with self.assertRaises(ValueError):
                manual_proposal(self.case, **kw)

    def test_manual_ui_without_amd_preview_confirmation_reset(self):
        from copilot.amd import AMDConnectionError
        with patch("app.planning_changes_view.load_config", side_effect=AMDConnectionError("Missing config")), \
             patch("copilot.planning_interpreter.request_completion") as api:
            app = AppTest.from_file(APP).run(timeout=40)
            def click(label):
                ui_click(app,label)
            click("Batch scheduling simulator")
            select_legacy(app)
            click("Load demo setup")
            click("Run scenario comparison")
            original = app.session_state["planning_case"]
            next(r for r in app.radio if r.label == "Constraint entry").set_value("Manual controls").run(timeout=40)
            next(s for s in app.selectbox if s.label == "Order ID").set_value("12").run(timeout=40)
            next(d for d in app.date_input if d.label == "Deadline date").set_value(datetime(2019,12,23).date())
            click("Preview manual change")
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["planning_case"], original)
            self.assertTrue(any("Manual constraint proposal" in i.value for i in app.info))
            click("Apply changes and reschedule")
            self.assertFalse(app.exception)
            self.assertTrue(app.session_state["sim_comparison"][1].proposal_verification.valid)
            self.assertEqual(app.session_state["planning_case"].history[-1]["receipt"]["origin"], "manual")
            click("Reset to original scenario and reschedule")
            self.assertEqual(app.session_state["planning_case"].orders, original.orders)
            api.assert_not_called()
