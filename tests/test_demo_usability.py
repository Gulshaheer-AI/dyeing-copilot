from ui_helpers import click as ui_click
from legacy_ui import select_legacy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from copilot.amd import AMDConnectionError
from copilot.reviews import ReviewStore
from copilot.session import generate_once
from test_interface import APP


def click(app, label):
    return ui_click(app,label)


class RequestSessionTests(unittest.TestCase):
    def test_duplicate_signature_reuses_exact_answer_and_changed_signature_calls_again(self):
        state, generate = {}, Mock(side_effect=[object(), object()])
        answer, fresh = generate_once(state, "evidence-question-mode-A", generate)
        self.assertTrue(fresh)
        reused, fresh = generate_once(state, "evidence-question-mode-A", generate)
        self.assertIs(reused, answer)
        self.assertFalse(fresh)
        self.assertEqual(generate.call_count, 1)
        changed, fresh = generate_once(state, "changed-day-or-config", generate)
        self.assertIsNot(changed, answer)
        self.assertTrue(fresh)
        self.assertEqual(generate.call_count, 2)

    def test_inflight_block_and_timeout_never_cache_success(self):
        generate = Mock()
        with self.assertRaisesRegex(ValueError, "already running"):
            generate_once({"copilot_inflight": "first"}, "second", generate)
        generate.assert_not_called()
        state = {"copilot_answer": ("old", object())}
        with self.assertRaisesRegex(ValueError, "timed out"):
            generate_once(state, "new", Mock(side_effect=AMDConnectionError("AMD request timed out")))
        self.assertNotIn("copilot_answer", state)
        self.assertNotIn("copilot_inflight", state)


class DemoNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch("app.copilot_view.ReviewStore", side_effect=lambda: ReviewStore(Path(self.temp.name) / "review.db")),
                        patch("app.copilot_view.load_config", side_effect=AMDConnectionError("AMD configuration missing for offline test"))]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.temp.cleanup()

    def test_daily_entry_defaults_to_flag_and_review_entry_keeps_selected_day(self):
        app = AppTest.from_file(APP).run(timeout=30)
        click(app, "Open Daily resource monitoring (separate synthetic dataset)")
        self.assertEqual(app.selectbox[1].value, "2024-08-09")
        self.assertTrue(any("exceeds the upper threshold" in x.value for x in app.info))
        self.assertTrue(any("Upper threshold (L/kg)" == m.label for m in app.metric))
        click(app, "Copilot and supervisor review")
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[0].value, "Explain selected synthetic resource day")
        self.assertTrue(any("Observed (L/kg)" == m.label for m in app.metric))
        next(r for r in app.radio if r.label=='Explanation source').set_value('Mock demonstration (no API call)').run()
        click(app, "Generate grounded explanation")
        app.run()
        self.assertTrue(next(b for b in app.button if b.label == "Generate grounded explanation").disabled)
        self.assertTrue(any("MOCKED" in x.value for x in app.warning))
        app.selectbox[0].set_value("What does the threshold mean?").run()
        self.assertFalse(next(b for b in app.button if b.label == "Generate grounded explanation").disabled)

    def test_scheduling_entry_and_explanation_handoff_preserve_verified_comparison(self):
        app = AppTest.from_file(APP).run(timeout=30)
        click(app, "Batch scheduling simulator")
        select_legacy(app)
        click(app, "Load demo setup")
        click(app, "Run scenario comparison")
        self.assertFalse(app.exception)
        self.assertTrue(any("baseline 39; proposal 39" in x.value for x in app.caption))
        click(app, "Explain this comparison with AMD copilot")
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[0].value, "Explain this schedule comparison")
        self.assertTrue(any(m.value == "27300.00" for m in app.metric))
        click(app, "Batch scheduling simulator")
        select_legacy(app)
        self.assertFalse(app.exception)
        self.assertTrue(any(m.value == "27,300.00" for m in app.metric))


if __name__ == "__main__":
    unittest.main()
