from ui_helpers import click as ui_click
from legacy_ui import select_legacy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from copilot.amd import AMDConfig, AMDConnectionError
from copilot.reviews import ReviewStore
from copilot.workflow import explain as grounded_explain
from test_interface import APP


def click(app, label):
    return ui_click(app,label)


class PlannerWorkflowInterfaceTests(unittest.TestCase):
    def test_failure_retry_keeps_schedule_and_changed_evidence_clears_error(self):
        with tempfile.TemporaryDirectory() as directory, patch("app.copilot_view.ReviewStore", side_effect=lambda: ReviewStore(Path(directory) / "reviews.db")), \
                patch("app.copilot_view.load_config", return_value=AMDConfig("test-key", "https://developer.amd.com.cn/radeon/api/v1", "test-model")):
            app = AppTest.from_file(APP).run(timeout=30)
            click(app, "Batch scheduling simulator")
            select_legacy(app)
            click(app, "Load demo setup")
            click(app, "Run scenario comparison")
            original = app.session_state["sim_comparison"]
            self.assertTrue(any(x.value == "4. What changed?" for x in app.subheader))
            click(app, "Explain this comparison with AMD copilot")
            def request(bundle, question, **kwargs):
                return grounded_explain(bundle, question, scope=kwargs["scope"], mode="mock")
            with patch("app.copilot_view.explain", side_effect=AMDConnectionError("AMD request timed out; retry manually.")) as generated:
                click(app, "Generate grounded explanation")
                self.assertFalse(app.exception)
                self.assertTrue(any("timed out" in e.value for e in app.error))
                self.assertTrue(any(b.label == "Retry explanation" and not b.disabled for b in app.button))
                self.assertEqual(app.session_state["sim_comparison"], original)
                self.assertFalse(any("Validated live AMD" in s.value for s in app.success))
                # Callable return is supplied separately to simulate a subsequent validated response.
                generated.side_effect = request
                click(app, "Retry explanation")
                self.assertFalse(app.exception)
                self.assertEqual(generated.call_count, 2)
                self.assertTrue(any("MOCKED EXPLANATION" in w.value for w in app.warning))
                self.assertEqual(app.session_state["sim_comparison"], original)
                app.run()
                self.assertEqual(generated.call_count, 2)
                self.assertTrue(next(b for b in app.button if b.label == "Generate grounded explanation").disabled)
                next(s for s in app.selectbox if s.label=='Question topic').set_value("Which assumptions drive this result?").run()
                self.assertFalse(any(b.label == "Retry explanation" for b in app.button))
                generated.side_effect = AMDConnectionError("AMD request timed out; retry manually.")
                click(app, "Generate grounded explanation")
                self.assertTrue(any(b.label == "Retry explanation" for b in app.button))
                next(s for s in app.selectbox if s.label=='Question topic').set_value("Explain this schedule comparison").run()
                self.assertFalse(any(b.label == "Retry explanation" for b in app.button))
                self.assertFalse(any("timed out" in e.value for e in app.error))


if __name__ == "__main__":
    unittest.main()
