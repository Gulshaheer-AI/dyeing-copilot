from ui_helpers import click as ui_click
from legacy_ui import select_legacy
import csv
import io
import json
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app.importer import COLUMNS, import_orders
from test_interface import APP
from test_resource_analysis import edited_import


def click(app, label):
    return ui_click(app,label)


def metric_values(app):
    return {metric.label: metric.value for metric in app.metric}


class SimulatorInterfaceTests(unittest.TestCase):
    def open_simulator(self):
        app = AppTest.from_file(APP).run(timeout=30)
        next(r for r in app.radio if r.label=='Workspace').set_value('Scheduling simulator').run()
        select_legacy(app)
        self.assertFalse(app.exception)
        return app

    def test_assumptions_are_required_and_planning_uses_complete_case(self):
        app = AppTest.from_file(APP).run(timeout=30)
        next(r for r in app.radio if r.label=="Workspace").set_value("Orders").run()
        app.multiselect[0].select("CGU").run()
        next(r for r in app.radio if r.label=='Workspace').set_value('Scheduling simulator').run()
        select_legacy(app)
        self.assertEqual(len(app.multiselect), 0)
        self.assertEqual(len(app.get("download_button")), 0)
        self.assertNotIn("Recalculated baseline (modelled source units)", metric_values(app))
        click(app, "Load demo setup")
        self.assertEqual(len(app.json), 1)
        self.assertFalse(next(c for c in app.checkbox if c.key=="sim_permission").value)
        self.assertNotIn("Recalculated baseline (modelled source units)", metric_values(app))
        click(app, "Run scenario comparison")
        self.assertFalse(app.exception)
        values = metric_values(app)
        self.assertEqual(values["Recorded source total — separate reference only"], "47,950")
        self.assertEqual(values["Recalculated baseline (modelled source units)"], "27,300.00")
        self.assertEqual(values["Scenario reduction (modelled source units)"], "0.00")
        schedule_frames = [frame.value for frame in app.dataframe
                           if "order_id" in frame.value.columns and "quantity" in frame.value.columns]
        self.assertEqual([len(frame) for frame in schedule_frames], [35, 35])
        self.assertEqual(len(app.get("download_button")), 1)

    def test_permission_activation_and_config_changes_clear_previous_results(self):
        app = self.open_simulator()
        click(app, "Load demo setup")
        next(c for c in app.checkbox if c.key=="sim_permission").check().run()
        click(app, "Run scenario comparison")
        self.assertFalse(app.exception)
        self.assertEqual(metric_values(app)["Recalculated baseline (modelled source units)"], "25,550.00")
        self.assertEqual(metric_values(app)["Recalculated proposal (modelled source units)"], "23,800.00")
        self.assertEqual(metric_values(app)["Scenario reduction (modelled source units)"], "1,750.00")
        next(c for c in app.checkbox if c.key=="sim_permission").uncheck().run()
        self.assertNotIn("Scenario reduction (modelled source units)", metric_values(app))
        self.assertEqual(len(app.get("download_button")), 0)
        app.text_area[0].set_value("invalid JSON").run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertEqual(len(app.get("download_button")), 0)

    def test_over_capacity_displays_failed_verification_without_comparison(self):
        app = self.open_simulator()
        click(app, "Load demo setup")
        raw = json.loads(app.text_area[0].value)
        for machine in raw["machines"]:
            machine["capacity"] = "1"
        app.text_area[0].set_value(json.dumps(raw)).run()
        click(app, "Run scenario comparison")
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertNotIn("Scenario reduction (modelled source units)", metric_values(app))
        self.assertEqual(len(app.get("download_button")), 0)

    def test_uploaded_case_resets_config_and_drives_scenario_quantities(self):
        app = self.open_simulator()
        click(app, "Load demo setup")
        click(app, "Run scenario comparison")
        result = edited_import(lambda rows: rows[0].update(cloth_length_source="2100"))
        text = io.StringIO()
        writer = csv.DictWriter(text, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result.records)
        upload = io.BytesIO(text.getvalue().encode())
        upload.name = "changed-quantity.csv"
        with patch("streamlit.file_uploader", return_value=upload):
            next(r for r in app.radio if r.label=='Import source').set_value('Upload Sitara CSV').run()
            self.assertEqual(app.text_area[0].value, "")
            self.assertEqual(len(app.get("download_button")), 0)
            click(app, "Load demo setup")
            click(app, "Run scenario comparison")
        self.assertFalse(app.exception)
        self.assertEqual(metric_values(app)["Recorded source total — separate reference only"], "47,950")
        self.assertEqual(metric_values(app)["Recalculated baseline (modelled source units)"], "27,315.00")

    def test_invalid_import_blocks_simulator(self):
        with patch("app.importer.load_bundled_orders", return_value=import_orders(b"invalid")):
            app = AppTest.from_file(APP).run(timeout=30)
        self.assertFalse(app.exception)
        self.assertEqual(len(app.radio), 2)
        self.assertEqual(len(app.get("download_button")), 0)
        self.assertNotIn("Recorded source total — separate reference only", metric_values(app))


if __name__ == "__main__":
    unittest.main()
