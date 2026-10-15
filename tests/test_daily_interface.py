from ui_helpers import click as ui_click
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from copilot.amd import AMDConnectionError
from copilot.reviews import ReviewStore
from daily.importer import SOURCE_PATH
from test_interface import APP


def click(app, label):
    return ui_click(app,label)


class DailyInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.review_path = Path(self.temp.name) / "reviews.sqlite3"
        self.store_patch = patch("app.copilot_view.ReviewStore", side_effect=lambda: ReviewStore(self.review_path))
        self.config_patch = patch("app.copilot_view.load_config", side_effect=AMDConnectionError("AMD config missing for offline test"))
        self.store_patch.start()
        self.config_patch.start()

    def tearDown(self):
        self.store_patch.stop()
        self.config_patch.stop()
        self.temp.cleanup()

    def open_daily(self):
        app = AppTest.from_file(APP).run(timeout=30)
        click(app, "Open Daily resource monitoring (separate synthetic dataset)")
        self.assertFalse(app.exception)
        return app

    def test_synthetic_view_labels_counts_units_and_no_retraining(self):
        with patch("daily.models.train_models", side_effect=AssertionError("UI must never train")):
            app = self.open_daily()
            self.assertEqual(app.metric[0].value, "731")
            self.assertEqual(app.metric[1].value, "11")
            self.assertTrue(any("Synthetic daily thread-dyeing data" in w.value for w in app.warning))
            self.assertFalse(any("Accepted orders" == m.label for m in app.metric))
            self.assertTrue(any("L/kg" in c.value for c in app.caption))
            app.selectbox[0].set_value("electricity").run()
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[1].value, "3")
            self.assertTrue(any("kWh/kg" in c.value for c in app.caption))

    def test_replay_is_historical_prefix_not_live_and_changes_selected_dates(self):
        app = self.open_daily()
        app.checkbox[0].check().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.selectbox[1].options), 1)
        self.assertTrue(any("no live sensor" in info.value for info in app.info))
        app.slider[0].set_value(2).run()
        self.assertEqual(len(app.selectbox[1].options), 3)
        self.assertEqual(app.selectbox[1].options[-1], "2024-08-09")
        click(app, "Return to Sitara views")
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].label, "Accepted orders")
        self.assertEqual(app.metric[0].value, "35")

    def test_daily_copilot_review_and_day_change_invalidation(self):
        app = self.open_daily()
        app.selectbox[1].set_value("2024-08-09").run()
        app.checkbox[1].check().run()
        self.assertFalse(app.exception)
        next(r for r in app.radio if r.label=='Explanation source').set_value('Mock demonstration (no API call)').run()
        click(app, "Generate grounded explanation")
        self.assertFalse(app.exception)
        self.assertTrue(any("MOCKED" in warning.value for warning in app.warning))
        self.assertTrue(any("fact:daily.upper_threshold" in caption.value for caption in app.caption))
        click(app, "Save recommendation as pending review")
        store = ReviewStore(self.review_path)
        row = store.list_reviews()[0]
        self.assertTrue(row["model_fingerprint"] and row["day_fingerprint"])
        app.selectbox[1].set_value("2024-08-10").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("invalidated" in info.value for info in app.info))
        self.assertTrue(next(b for b in app.button if b.label == "Record review decision").disabled)

    def test_invalid_daily_upload_clears_predictions_and_stale_context(self):
        app = self.open_daily()
        next(r for r in app.radio if r.label=='Daily dataset source').set_value('Upload synthetic daily CSV').run()
        upload = io.BytesIO(SOURCE_PATH.read_bytes() + SOURCE_PATH.read_bytes().splitlines()[1] + b"\n")
        upload.name = "duplicate.csv"
        with patch("streamlit.file_uploader", return_value=upload), patch("app.daily_view.current_models") as models:
            app.run()
            models.assert_not_called()
        self.assertFalse(app.exception)
        self.assertTrue(any("Daily import rejected" in error.value for error in app.error))
        self.assertFalse(any("Flags" in metric.label for metric in app.metric))
        self.assertEqual(len(app.selectbox), 0)

    def test_daily_available_even_if_sitara_import_invalid_and_missing_artifacts_do_not_train(self):
        from app.importer import import_orders
        with patch("app.importer.load_bundled_orders", return_value=import_orders(b"invalid")):
            app = AppTest.from_file(APP).run(timeout=30)
            self.assertTrue(app.error)
            with patch("app.daily_view.current_models", side_effect=OSError("missing artifact")):
                click(app, "Open Daily resource monitoring (separate synthetic dataset)")
            self.assertFalse(app.exception)
            self.assertTrue(any("train_daily_resources.py" in error.value for error in app.error))
            self.assertEqual(app.metric[0].value, "731")


if __name__ == "__main__":
    unittest.main()
