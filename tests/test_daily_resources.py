import copy
import csv
import io
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from copilot.daily_evidence import build_daily_evidence, retrieve_daily_day
from copilot.evidence import build_evidence
from copilot.reviews import ReviewStore
from copilot.workflow import explain, mock_content, validate_output
from app.importer import load_bundled_orders
from daily.importer import COLUMNS, SOURCE_PATH, import_daily, load_bundled_daily
from daily.models import FEATURES, TARGETS, chronological_split, load_models, residual_offset, score_daily, select_predictor, train_models
from daily.profile import profile_daily


def encode(frame):
    return frame[list(COLUMNS)].to_csv(index=False, date_format="%Y-%m-%d").encode()


class DailyImportTests(unittest.TestCase):
    def setUp(self):
        self.source = load_bundled_daily()

    def test_original_contract_dates_hash_and_separation(self):
        self.assertTrue(self.source.valid)
        self.assertEqual(len(self.source.frame), 731)
        self.assertEqual(len(COLUMNS), 39)
        self.assertEqual(str(self.source.frame.Date.iloc[0].date()), "2023-01-01")
        self.assertEqual(str(self.source.frame.Date.iloc[-1].date()), "2024-12-31")
        self.assertEqual(self.source.sha256, "1e30fdb86b267751b615f6f1c9eb3090c84def01692eef7704da5262bdd82dff")
        with self.assertRaises(ValueError):
            score_daily(load_bundled_orders(), load_models())

    def test_duplicate_dates_rejected_without_silent_deduplication(self):
        frame = pd.concat([self.source.frame, self.source.frame.iloc[[0]]], ignore_index=True)
        result = import_daily(encode(frame))
        self.assertFalse(result.valid)
        self.assertIsNone(result.frame)
        self.assertTrue(any("Duplicate" in i["message"] for i in result.issues))

    def test_invalid_required_units_values_and_zero_production(self):
        for field, value in (("Production_Volume_kg", 0), ("Production_Volume_ton", 0), ("Temperature_C", np.inf),
                             ("Water_Consumption_L_per_kg", -1), ("Machine_Utilization_%", 101), ("pH", 15)):
            frame = self.source.frame.copy()
            frame[field] = frame[field].astype(float)
            frame.loc[0, field] = value
            self.assertFalse(import_daily(encode(frame)).valid, (field, value))
        text = SOURCE_PATH.read_bytes().replace(b"Water_Consumption_L_per_kg", b"Water_Consumption_gallons_per_kg", 1)
        self.assertFalse(import_daily(text).valid)
        self.assertFalse(import_daily(b"bad,header\n1,2\n").valid)
        self.assertFalse(import_daily(b"\xff").valid)

    def test_date_calendar_and_missing_field_validation(self):
        rows = list(csv.DictReader(io.StringIO(SOURCE_PATH.read_text())))
        for field, value in (("Date", "2023-02-30"), ("Date", "01/01/2023"), ("Month", "February"),
                             ("Year", "2024"), ("Day_Type", ""), ("Total_Energy_kWh", "NaN")):
            edited = copy.deepcopy(rows)
            edited[0][field] = value
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, COLUMNS)
            writer.writeheader()
            writer.writerows(edited)
            self.assertFalse(import_daily(buffer.getvalue().encode()).valid, (field, value))

    def test_sorting_and_calendar_gaps_are_explicit(self):
        frame = self.source.frame.iloc[[3, 0, 1]].copy()
        result = import_daily(encode(frame))
        self.assertTrue(result.valid)
        self.assertTrue(result.frame.Date.is_monotonic_increasing)
        self.assertTrue(any(i["severity"] == "warning" for i in result.issues))

    def test_profile_records_arithmetic_counterparts_and_synthetic_label_exclusion(self):
        audit = profile_daily(self.source)
        self.assertAlmostEqual(audit["relationships"]["water_total_vs_kg_times_L_per_kg"]["max_absolute_rounding_difference"], 131.6)
        self.assertIn("excluded", audit["field_roles"]["Day_Type"]["role"])
        self.assertIn("synthetic", audit["label"].lower())


class DailyModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = load_bundled_daily()
        cls.artifact = load_models()

    def test_chronological_split_no_overlap_and_no_target_feature_leakage(self):
        train, val, test = chronological_split(self.source.frame)
        self.assertEqual([len(x) for x in (train, val, test)], [438, 146, 147])
        self.assertLess(train.Date.max(), val.Date.min())
        self.assertLess(val.Date.max(), test.Date.min())
        forbidden = {"Day_Type", "Monthly_Demand_Factor", "Water_Consumption_L_per_kg", "Total_Water_Consumption_L",
                     "Energy_Consumption_kWh_per_kg", "Total_Energy_kWh", "Wastewater_L", "Wastewater_L_per_kg"}
        self.assertFalse(set(FEATURES) & forbidden)
        self.assertEqual(set(FEATURES), set(self.artifact["metadata"]["features"]))
        for pipeline in self.artifact["models"].values():
            np.testing.assert_allclose(pipeline["imputer"].statistics_, train[list(FEATURES)].median().to_numpy())
            self.assertEqual(list(pipeline.feature_names_in_), list(FEATURES))

    def test_baseline_fallback_and_threshold_rank(self):
        self.assertEqual(select_predictor(1, {3: 2, 5: 1}), ("training_median", None))
        self.assertEqual(select_predictor(1, {3: .5, 5: .7}), ("random_forest", 3))
        self.assertEqual(residual_offset(range(10)), 9)
        self.assertEqual(residual_offset([-2, -1]), 0)

    def test_persistence_and_constant_target_actual_fallback(self):
        frame = self.source.frame.iloc[:50].copy()
        frame["Water_Consumption_L_per_kg"] = 50.0
        frame["Energy_Consumption_kWh_per_kg"] = 1.5
        source = import_daily(encode(frame))
        with tempfile.TemporaryDirectory() as directory:
            artifact = train_models(source, directory)
            restored = load_models(directory)
            pd.testing.assert_frame_equal(score_daily(source, artifact), score_daily(source, restored))
            for resource in TARGETS:
                self.assertEqual(artifact["metadata"]["results"][resource]["selected"], "training_median")
            self.assertTrue((Path(directory) / "historical_predictions.csv").is_file())
            path = Path(directory) / "models.joblib"
            path.write_bytes(path.read_bytes() + b"corrupt")
            with self.assertRaisesRegex(ValueError, "integrity"):
                load_models(directory)

    def test_test_target_perturbation_does_not_change_selection_or_calibration(self):
        original = self.source.frame.iloc[:50].copy()
        modified = original.copy()
        modified.loc[modified.index[-10:], "Water_Consumption_L_per_kg"] += 100  # artificial test copy only
        artificial_labels = pd.DataFrame({"Date": modified.Date,
            "artificial_holdout_perturbation": modified.index.isin(modified.index[-10:])})
        self.assertFalse(artificial_labels.iloc[:40].artificial_holdout_perturbation.any())
        with tempfile.TemporaryDirectory() as directory:
            # Separate labelled test copy, outside original data and never a feature/ground-truth source.
            (Path(directory) / "artificial_test_only.csv").write_bytes(encode(modified))
            artificial_labels.to_csv(Path(directory) / "artificial_test_only_labels.csv", index=False)
            a = train_models(import_daily(encode(original)), Path(directory) / "a")
            b = train_models(import_daily(encode(modified)), Path(directory) / "b")
            for resource in TARGETS:
                for field in ("selected", "selected_depth", "residual_offset", "baseline_validation_mae", "regression_validation_mae_by_depth"):
                    self.assertEqual(a["metadata"]["results"][resource][field], b["metadata"]["results"][resource][field])
                np.testing.assert_array_equal(a["models"][resource].predict(original[list(FEATURES)]),
                                              b["models"][resource].predict(original[list(FEATURES)]))
            self.assertNotEqual(a["metadata"]["results"]["water"]["selected_test_mae"], b["metadata"]["results"]["water"]["selected_test_mae"])

    def test_test_flags_units_and_no_in_sample_alerts(self):
        scores = score_daily(self.source, self.artifact)
        self.assertFalse(scores.loc[~scores.flag_eligible, "investigation_flag"].any())
        for resource, expected in (("water", 11), ("electricity", 3)):
            rows = scores[(scores.resource == resource) & scores.flag_eligible]
            self.assertEqual(len(rows), 147)
            self.assertEqual(int(rows.investigation_flag.sum()), expected)
            np.testing.assert_allclose(rows.difference, rows.observed - rows.predicted)
            self.assertTrue((rows.investigation_flag == (rows.observed > rows.upper_threshold)).all())

    def test_loaded_values_drive_predictions_and_observations_without_retraining(self):
        modified = self.source.frame.copy()
        index = modified[modified.Date == pd.Timestamp("2024-08-09")].index[0]
        modified.loc[index, "Water_Consumption_L_per_kg"] += 1
        changed = import_daily(encode(modified))
        a = retrieve_daily_day(self.source, self.artifact, "2024-08-09", "water")
        b = retrieve_daily_day(changed, self.artifact, "2024-08-09", "water")
        self.assertAlmostEqual(b["prediction"]["observed"] - a["prediction"]["observed"], 1)
        self.assertEqual(a["prediction"]["predicted"], b["prediction"]["predicted"])
        self.assertFalse(b["evaluation_matches_loaded_dataset"])


class DailyCopilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source, cls.artifact = load_bundled_daily(), load_models()

    def bundle(self, date="2024-08-09", resource="water"):
        return build_daily_evidence(retrieve_daily_day(self.source, self.artifact, date, resource), "Explain this synthetic day")

    def test_daily_units_numeric_claims_allowed_and_conversions_still_rejected(self):
        for resource, unit in (("water", "L/kg"), ("electricity", "kWh/kg")):
            bundle = self.bundle(resource=resource)
            output = json.loads(mock_content(bundle, "Explain day"))
            output["quantitative_claims"] = [{"fact_id": "fact:daily.observed", "value": bundle["facts"]["fact:daily.observed"]["value"], "unit": unit}]
            self.assertTrue(validate_output(json.dumps(output), bundle))
            output["quantitative_claims"][0]["unit"] = "PKR"
            with self.assertRaises(ValueError):
                validate_output(json.dumps(output), bundle)
        sitara = build_evidence(load_bundled_orders(), "Recorded totals")
        output = json.loads(mock_content(sitara, "Recorded totals"))
        output["quantitative_claims"] = [{"fact_id": "fact:recorded.water_total_source", "value": "47950", "unit": "L/kg"}]
        with self.assertRaises(ValueError):
            validate_output(json.dumps(output), sitara)

    def test_synthetic_provenance_and_flag_explanation_without_root_cause(self):
        bundle = self.bundle()
        answer = explain(bundle, "Why was this day flagged?", scope="daily", mode="mock")
        self.assertEqual(answer.output.proposed_review_action, "investigate_synthetic_day")
        self.assertIn("synthetic", answer.output.explanation[0].text.lower())
        self.assertTrue(bundle["facts"]["fact:daily.investigation_flag"]["value"])
        self.assertFalse(any(ref.startswith("fact:scenario") or ref.startswith("fact:recorded.") for ref in bundle["facts"]))
        self.assertNotIn("Day_Type", bundle["facts"]["fact:daily.inputs"]["value"])
        payload = json.loads(mock_content(bundle, "Explain day"))
        payload["explanation"][1]["text"] = "This proves a machine fault and recoverable water savings."
        with self.assertRaises(ValueError):
            validate_output(json.dumps(payload), bundle)

    def test_dataset_model_day_fingerprints_persist_and_stale_decision_is_rejected(self):
        bundle, next_day = self.bundle(), self.bundle("2024-08-10")
        self.assertNotEqual(bundle["fingerprint"], next_day["fingerprint"])
        modified = copy.deepcopy(bundle["daily_context"])
        modified["model_fingerprint"] = "new-model"
        self.assertNotEqual(bundle["fingerprint"], build_daily_evidence(modified, "Explain day")["fingerprint"])
        modified = copy.deepcopy(bundle["daily_context"])
        modified["dataset_sha256"] = "new-input-dataset"
        self.assertNotEqual(bundle["fingerprint"], build_daily_evidence(modified, "Explain day")["fingerprint"])
        with tempfile.TemporaryDirectory() as directory:
            store = ReviewStore(Path(directory) / "reviews.sqlite3")
            answer = explain(bundle, "Explain this day", scope="daily", mode="mock")
            key = store.save_pending(answer, bundle)
            row = store.list_reviews()[0]
            self.assertEqual(row["model_fingerprint"], bundle["model_fingerprint"])
            self.assertEqual(row["day_fingerprint"], bundle["day_fingerprint"])
            with self.assertRaises(ValueError):
                store.decide(key, "accepted_for_further_review", next_day["fingerprint"])


if __name__ == "__main__":
    unittest.main()
