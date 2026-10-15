from ui_helpers import click as ui_click
from legacy_ui import select_legacy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from copilot.amd import AMDConfig, AMDConnectionError
from copilot.planning_schema import Interpretation, InterpretationResponse
from test_interface import APP
from test_planning_requests import fixture


def click(app, label):
    return ui_click(app,label)


class PlanningChangeInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.connection = patch("app.planning_changes_view.load_config", return_value=AMDConfig("offline-test-key", "https://developer.amd.com.cn/radeon/api/v1", "test-model"))
        self.connection.start()

    def tearDown(self):
        self.connection.stop()

    def open_case(self):
        app = AppTest.from_file(APP).run(timeout=40)
        click(app, "Batch scheduling simulator")
        select_legacy(app)
        click(app, "Load demo setup")
        click(app, "Run scenario comparison")
        self.assertFalse(app.exception)
        return app

    def test_interpret_preview_confirm_reset_and_failed_previous_schedule(self):
        app = self.open_case()
        original_case = app.session_state["planning_case"]
        original_schedule = app.session_state["sim_comparison"]
        text = "Change order 12 deadline to 2019-12-22T18:00."
        app.text_area[1].set_value(text).run(timeout=40)
        answer = fixture(original_case, text, [{"operation": "order_deadline", "order_id": "12", "deadline": "2019-12-22T18:00"}])
        with patch("app.planning_changes_view.interpret", return_value=answer) as model:
            click(app, "Interpret planning request with AMD")
            self.assertEqual(app.session_state["planning_case"], original_case)
            self.assertEqual(app.session_state["sim_comparison"], original_schedule)
            self.assertTrue(any("MOCKED interpretation" in w.value for w in app.warning))
            app.run(timeout=40)
            self.assertEqual(model.call_count, 1)
            click(app, "Apply changes and reschedule")
        changed = app.session_state["planning_case"]
        self.assertEqual(changed.orders[11].deadline.isoformat(), "2019-12-22T18:00:00")
        self.assertTrue(app.session_state["sim_comparison"][1].proposal_verification.valid)
        self.assertEqual(len(app.get("download_button")), 2)
        click(app, "Reset to original scenario and reschedule")
        reset = app.session_state["planning_case"]
        self.assertEqual(reset.orders, original_case.orders)
        self.assertEqual(reset.config, original_case.config)
        outage = "virtual-Open-Cotton outage from 2019-01-01T00:00 to 2020-02-01T00:00."
        app.text_area[1].set_value(outage).run(timeout=40)
        answer = fixture(reset, outage, [{"operation": "machine_unavailability", "machine_id": "virtual-Open-Cotton", "start": "2019-01-01T00:00", "end": "2020-02-01T00:00"}])
        with patch("app.planning_changes_view.interpret", return_value=answer):
            click(app, "Interpret planning request with AMD")
            click(app, "Apply changes and reschedule")
        self.assertFalse(app.exception)
        self.assertIsNone(app.session_state["sim_comparison"][1].proposal)
        self.assertTrue(any("previous scenario" in e.label for e in app.expander))
        self.assertEqual(len(app.get("download_button")), 1)  # Audit only, no valid recommendation export.
        self.assertIsNone(app.session_state["sim_context"]["comparison"])

    def test_failure_retry_clarification_and_stale_request(self):
        app = self.open_case()
        original = app.session_state["sim_comparison"]
        app.text_area[1].set_value("Set order 12 deadline to 2019-12-22T18:00.").run(timeout=40)
        with patch("app.planning_changes_view.interpret", side_effect=AMDConnectionError("AMD request timed out.")):
            click(app, "Interpret planning request with AMD")
        self.assertFalse(app.exception)
        self.assertTrue(any(b.label == "Retry planning interpretation" for b in app.button))
        self.assertEqual(app.session_state["sim_comparison"], original)
        def clarification(request, **kwargs):
            return Interpretation(request, InterpretationResponse(status="clarification", changes=[],
                clarification_questions=["What exact historical completion datetime should order 12 use?"], unsupported_reasons=[]),
                {"origin": "mock", "validation": "passed"})
        with patch("app.planning_changes_view.interpret", side_effect=clarification):
            click(app, "Retry planning interpretation")
        self.assertFalse(any(b.label == "Apply changes and reschedule" for b in app.button))
        self.assertEqual(app.session_state["sim_comparison"], original)
        app.text_area[1].set_value("Make order 13 urgent.").run(timeout=40)
        self.assertTrue(any("invalidated" in info.value for info in app.info))
        self.assertFalse(any(b.label == "Apply changes and reschedule" for b in app.button))


if __name__ == "__main__":
    unittest.main()
