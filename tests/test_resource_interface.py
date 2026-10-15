import io
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from test_interface import APP
from test_resource_analysis import edited_import
from app.importer import COLUMNS
from app.resource_analysis import WATER_FIELDS
import csv


def metrics(app):
    return {metric.label: metric.value for metric in app.metric}


class ResourceInterfaceTests(unittest.TestCase):
    def open_analysis(self):
        app = AppTest.from_file(APP).run(timeout=30)
        next(r for r in app.radio if r.label=='Workspace').set_value('Resource analysis').run()
        self.assertFalse(app.exception)
        return app

    def test_totals_filters_breakdowns_and_ranking(self):
        app = self.open_analysis()
        values = metrics(app)
        self.assertEqual(values["Overall imported case: Recorded modelled water total"], "47,950")
        self.assertEqual(values["Filtered view: Recorded modelled water total"], "47,950")
        for i, total in enumerate(("9,100", "18,200", "20,650"), 1):
            self.assertEqual(values[f"Overall imported case: Recorded water component {i}"], total)
        self.assertEqual(len(app.dataframe[-1].value), 35)
        self.assertEqual(app.dataframe[-1].value.iloc[0]["source_row_id"], "27")
        app.multiselect[0].select("CGU").run()
        self.assertEqual(metrics(app)["Overall imported case: Recorded modelled water total"], "47,950")
        self.assertEqual(metrics(app)["Filtered view: Recorded modelled water total"], "4,550")
        self.assertEqual(len(app.dataframe[-1].value), 4)
        self.assertAlmostEqual(app.dataframe[-1].value["overall_case_contribution_pct"].sum(), 4550 * 100 / 47950)
        app.multiselect[2].select("Open").run()
        self.assertEqual(metrics(app)["Filtered view: Recorded modelled water total"], "3,150")
        app.multiselect[1].select("PolyCotton").run()
        self.assertFalse(app.exception)
        self.assertEqual(metrics(app)["Filtered view: Recorded modelled water total"], "0")
        self.assertEqual(metrics(app)["Overall imported case: Recorded modelled water total"], "47,950")

    def test_uploaded_case_drives_screen_and_invalid_upload_clears_analysis(self):
        result = edited_import(lambda rows: rows[0].update(water_component_1_source="351", water_total_source="1051"))
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result.records)
        uploaded = io.BytesIO(buffer.getvalue().encode())
        uploaded.name = "edited.csv"
        app = self.open_analysis()
        with patch("streamlit.file_uploader", return_value=uploaded):
            next(r for r in app.radio if r.label=='Import source').set_value('Upload Sitara CSV').run()
        self.assertFalse(app.exception)
        self.assertEqual(metrics(app)["Overall imported case: Recorded modelled water total"], "47,951")
        invalid = io.BytesIO(b"invalid")
        invalid.name = "bad.csv"
        with patch("streamlit.file_uploader", return_value=invalid):
            app.run()
        self.assertFalse(app.exception)
        self.assertEqual(metrics(app)["Accepted orders"], "0")
        self.assertFalse(any("water total" in label for label in metrics(app)))
        self.assertEqual(len(app.error), 1)

    def test_zero_total_displays_undefined_contributions(self):
        result = edited_import(lambda rows: [r.update({f: "0" for f in WATER_FIELDS}) for r in rows])
        with patch("app.importer.load_bundled_orders", return_value=result):
            app = self.open_analysis()
        self.assertFalse(app.exception)
        self.assertEqual(metrics(app)["Overall imported case: Recorded modelled water total"], "0")
        self.assertTrue(app.dataframe[-1].value["overall_case_contribution_pct"].isna().all())


if __name__ == "__main__":
    unittest.main()
