from ui_helpers import click as ui_click
from legacy_ui import select_legacy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from copilot.amd import AMDConnectionError
from copilot.reviews import ReviewStore
from test_interface import APP


def click(app, label):
    return ui_click(app,label)


class CopilotInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "review.sqlite3"
        self.store_patch = patch("app.copilot_view.ReviewStore", side_effect=lambda: ReviewStore(self.path))
        self.config_patch = patch("app.copilot_view.load_config", side_effect=AMDConnectionError("AMD configuration missing; see local setup."))
        self.store_patch.start()
        self.config_patch.start()

    def tearDown(self):
        self.store_patch.stop()
        self.config_patch.stop()
        self.temp.cleanup()

    def open_copilot(self):
        app = AppTest.from_file(APP).run(timeout=30)
        next(r for r in app.radio if r.label=='Workspace').set_value('Copilot').run()
        self.assertFalse(app.exception)
        return app

    def use_mock(self, app):
        next(r for r in app.radio if r.label=='Explanation source').set_value('Mock demonstration (no API call)').run()
        return app

    def test_missing_configuration_is_clear_and_mock_mode_is_explicit(self):
        app = self.open_copilot()
        self.assertTrue(any("configuration missing" in error.value for error in app.error))
        self.assertTrue(next(button for button in app.button if button.label == "Generate grounded explanation").disabled)
        self.use_mock(app)
        click(app, "Generate grounded explanation")
        self.assertFalse(app.exception)
        self.assertTrue(any("MOCKED" in warning.value for warning in app.warning))
        self.assertFalse(any("live AMD response received" in item.value for item in app.success))
        self.assertTrue(any("unresolved source units" in metric.label for metric in app.metric))

    def test_recorded_explanation_and_supervisor_review_persist_without_scenario_changes(self):
        app = self.use_mock(self.open_copilot())
        app.text_input[0].set_value("Describe order 27").run()
        click(app, "Generate grounded explanation")
        self.assertFalse(app.exception)
        self.assertTrue(any("fact:recorded.order.27" in caption.value for caption in app.caption))
        click(app, "Save recommendation as pending review")
        self.assertFalse(app.exception)
        store = ReviewStore(self.path)
        self.assertEqual(store.list_reviews()[0]["status"], "pending_review")
        click(app, "Record review decision")
        self.assertFalse(app.exception)
        self.assertEqual(store.list_reviews()[0]["status"], "accepted_for_further_review")
        self.assertEqual(json.loads(store.list_reviews()[0]["receipt_json"])["origin"], "mock")
        self.assertIsNone(json.loads(store.list_reviews()[0]["evidence_json"])["scenario"])

    def test_scenario_questions_require_current_verified_comparison(self):
        app = self.use_mock(self.open_copilot())
        app.selectbox[0].set_value("Explain this schedule comparison").run()
        click(app, "Generate grounded explanation")
        self.assertFalse(app.exception)
        self.assertTrue(any("verified comparison is required" in item.value for item in app.error))
        self.assertFalse(any(button.label == "Save recommendation as pending review" for button in app.button))

    def test_scenario_survives_view_switch_and_config_changes_invalidate_explanation(self):
        app = AppTest.from_file(APP).run(timeout=30)
        next(r for r in app.radio if r.label=='Workspace').set_value('Scheduling simulator').run()
        select_legacy(app)
        click(app, "Load demo setup")
        click(app, "Run scenario comparison")
        original_text = app.text_area[0].value
        next(r for r in app.radio if r.label=='Workspace').set_value('Copilot').run()
        self.use_mock(app)
        app.selectbox[0].set_value("Explain this schedule comparison").run()
        click(app, "Generate grounded explanation")
        self.assertFalse(app.exception)
        self.assertTrue(any(metric.value == "27300.00" for metric in app.metric))
        click(app, "Save recommendation as pending review")
        next(r for r in app.radio if r.label=='Workspace').set_value('Scheduling simulator').run()
        select_legacy(app)
        self.assertEqual(app.text_area[0].value, original_text)
        raw = json.loads(original_text)
        raw["cleaning_water"] = "351"
        app.text_area[0].set_value(json.dumps(raw)).run()
        next(r for r in app.radio if r.label=='Workspace').set_value('Copilot').run()
        self.assertFalse(app.exception)
        self.assertTrue(any("invalidated" in item.value for item in app.info))
        self.assertTrue(any("STALE evidence" in item.value for item in app.markdown))
        decision = next(button for button in app.button if button.label == "Record review decision")
        self.assertTrue(decision.disabled)
        self.assertFalse(any(button.label == "Save recommendation as pending review" for button in app.button))


if __name__ == "__main__":
    unittest.main()
