import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app.importer import import_orders

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


class InterfaceTests(unittest.TestCase):
    def test_default_display_filters_and_detail(self):
        app = AppTest.from_file(APP).run(timeout=30)
        self.assertFalse(app.exception)
        next(r for r in app.radio if r.label=="Workspace").set_value("Orders").run()
        self.assertEqual(app.metric[0].value, "35")
        orders = next(f.value for f in app.dataframe if "source_row_id" in f.value.columns)
        self.assertEqual(len(orders), 35)
        self.assertEqual(orders.iloc[0]["shade_source"], "Gray")
        self.assertEqual(orders.iloc[-1]["source_row_id"], "35")
        app.multiselect[0].select("CGU").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(next(f.value for f in app.dataframe if "source_row_id" in f.value.columns)), 4)
        app.selectbox[0].select("2").run()
        detail = app.table[0].value
        self.assertEqual(detail.loc[detail["Field"] == "shade_source", "Value"].iloc[0], "Choclate")
        app.multiselect[1].select("PolyCotton").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(next(f.value for f in app.dataframe if "source_row_id" in f.value.columns)), 0)

    def test_invalid_import_displays_errors_without_orders(self):
        with patch("app.importer.load_bundled_orders", return_value=import_orders(b"invalid")):
            app = AppTest.from_file(APP).run(timeout=30)
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "0")
        self.assertEqual(len(app.error), 1)
        self.assertEqual(len(app.selectbox), 0)

    def test_upload_mode_waits_for_file_without_stale_records(self):
        app = AppTest.from_file(APP).run(timeout=30)
        next(r for r in app.radio if r.label=='Import source').set_value('Upload Sitara CSV').run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe), 0)
        self.assertEqual(len(app.metric), 0)


if __name__ == "__main__":
    unittest.main()
