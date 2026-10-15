"""Reproducible train/validation/test evaluation and trusted local artifact inference."""

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline

from daily.importer import COLUMNS, ROOT, require_daily
from daily.profile import profile_daily

FEATURES = ("Production_Volume_kg", "Machine_Utilization_%", "Number_of_Workers", "Liquor_Ratio_1:x",
            "Temperature_C", "Cycle_Time_hr", "Dye_Batch_Count")
TARGETS = {"water": ("Water_Consumption_L_per_kg", "L/kg"), "electricity": ("Energy_Consumption_kWh_per_kg", "kWh/kg")}
ARTIFACT_DIR = ROOT / "artifacts/daily_resource"
PROTOCOL = ROOT / "reports/resource_training_protocol.md"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def chronological_split(frame):
    if len(frame) < 30 or not frame.Date.is_unique or not frame.Date.is_monotonic_increasing:
        raise ValueError("Training needs at least 30 unique chronologically ordered daily records.")
    a, b = int(len(frame) * .6), int(len(frame) * .6) + int(len(frame) * .2)
    return frame.iloc[:a].copy(), frame.iloc[a:b].copy(), frame.iloc[b:].copy()


def select_predictor(baseline_mae, regression_maes):
    best = min(regression_maes, key=lambda depth: (regression_maes[depth], depth))
    return ("random_forest", best) if regression_maes[best] < baseline_mae else ("training_median", None)


def residual_offset(residuals):
    values = np.sort(np.asarray(residuals, dtype=float))
    if not len(values) or not np.isfinite(values).all():
        raise ValueError("Validation residuals must be finite and nonempty.")
    rank = min(len(values), math.ceil(.95 * (len(values) + 1)))
    return float(max(0, values[rank - 1]))


def train_models(result, output_dir=ARTIFACT_DIR):
    d = require_daily(result)
    train, val, test = chronological_split(d)
    models, results = {}, {}
    for resource, (target, unit) in TARGETS.items():
        baseline = Pipeline([("imputer", SimpleImputer(strategy="median")), ("regressor", DummyRegressor(strategy="median"))])
        baseline.fit(train[list(FEATURES)], train[target])
        baseline_val_mae = float(mean_absolute_error(val[target], baseline.predict(val[list(FEATURES)])))
        candidates, val_maes = {}, {}
        for depth in (3, 5):
            pipe = Pipeline([("imputer", SimpleImputer(strategy="median")), ("regressor", RandomForestRegressor(
                n_estimators=64, max_depth=depth, min_samples_leaf=10, random_state=42, n_jobs=1))])
            pipe.fit(train[list(FEATURES)], train[target])
            candidates[depth] = pipe
            val_maes[depth] = float(mean_absolute_error(val[target], pipe.predict(val[list(FEATURES)])))
        selected, depth = select_predictor(baseline_val_mae, val_maes)
        chosen = candidates[depth] if selected == "random_forest" else baseline
        offset = residual_offset(val[target].to_numpy() - chosen.predict(val[list(FEATURES)]))
        # Everything above is fixed before any test prediction/metric is computed.
        best_depth = min(val_maes, key=lambda k: (val_maes[k], k))
        predictions = chosen.predict(test[list(FEATURES)])
        results[resource] = {"target": target, "unit": unit, "selected": selected, "selected_depth": depth,
            "regression_validation_mae_by_depth": val_maes, "baseline_validation_mae": baseline_val_mae,
            "baseline_test_mae": float(mean_absolute_error(test[target], baseline.predict(test[list(FEATURES)]))),
            "regression_test_mae": float(mean_absolute_error(test[target], candidates[best_depth].predict(test[list(FEATURES)]))),
            "selected_test_mae": float(mean_absolute_error(test[target], predictions)), "residual_offset": offset,
            "test_alert_count": int(np.sum(test[target].to_numpy() > predictions + offset)),
            "test_upper_threshold_exceedance_fraction": float(np.mean(test[target].to_numpy() > predictions + offset))}
        models[resource] = chosen
    metadata = {"protocol": PROTOCOL.read_text(encoding="utf-8"), "protocol_sha256": digest(PROTOCOL.read_bytes()),
        "dataset_sha256": result.sha256, "dataset_filename": result.filename, "provenance": "synthetic_daily_thread_dyeing",
        "features": list(FEATURES), "excluded_fields": sorted(set(COLUMNS) - set(FEATURES)), "sklearn_version": sklearn.__version__,
        "splits": {label: {"count": len(part), "start": str(part.Date.iloc[0].date()), "end": str(part.Date.iloc[-1].date())}
                   for label, part in (("train", train), ("validation", val), ("test", test))},
        "results": results, "profile": profile_daily(result), "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "threshold_method": "upper: prediction + max(0, validation residual at one-based rank ceil(.95*(n_val+1)), capped at n_val)",
        "limitation": "Synthetic retrospective daily analysis, no independent anomaly labels, guaranteed coverage, causal claims or real-factory validation."}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "models.joblib"
    joblib.dump(models, model_path, compress=3)
    metadata["model_sha256"] = digest(model_path.read_bytes())
    metadata["model_version"] = "synthetic-daily-v1-" + digest((result.sha256 + metadata["model_sha256"] + metadata["protocol_sha256"]).encode())[:16]
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    artifact = {"models": models, "metadata": metadata, "artifact_fingerprint": digest((output_dir / "metadata.json").read_bytes())}
    score_daily(result, artifact).to_csv(output_dir / "historical_predictions.csv", index=False)
    return artifact


def load_models(directory=ARTIFACT_DIR):
    directory = Path(directory)
    meta_bytes = (directory / "metadata.json").read_bytes()
    metadata = json.loads(meta_bytes)
    model_bytes = (directory / "models.joblib").read_bytes()
    if digest(model_bytes) != metadata["model_sha256"] or metadata["features"] != list(FEATURES):
        raise ValueError("Daily model artifact integrity/feature contract mismatch. Re-run project training.")
    if metadata["sklearn_version"] != sklearn.__version__ or metadata["protocol_sha256"] != digest(PROTOCOL.read_bytes()):
        raise ValueError("Model environment/protocol changed; regenerate artifacts with the pinned environment.")
    # joblib is loaded only from the project-owned trusted local artifact directory, never a dataset/upload.
    return {"models": joblib.load(directory / "models.joblib"), "metadata": metadata, "artifact_fingerprint": digest(meta_bytes)}


def score_daily(result, artifact):
    d = require_daily(result)
    metadata = artifact["metadata"]
    if metadata["features"] != list(FEATURES):
        raise ValueError("Model feature contract mismatch.")
    rows = []
    train_end = pd.Timestamp(metadata["splits"]["train"]["end"])
    val_end = pd.Timestamp(metadata["splits"]["validation"]["end"])
    for resource, (target, unit) in TARGETS.items():
        predictions = artifact["models"][resource].predict(d[list(FEATURES)])
        for position, (_, record) in enumerate(d.iterrows()):
            observed, predicted = float(record[target]), float(predictions[position])
            upper = predicted + metadata["results"][resource]["residual_offset"]
            phase = "train (fitted history)" if record.Date <= train_end else "validation (calibration history)" if record.Date <= val_end else "test/replay holdout dates"
            eligible = record.Date > val_end
            rows.append({"Date": str(record.Date.date()), "resource": resource, "unit": unit, "observed": observed,
                "predicted": predicted, "upper_threshold": upper, "difference": observed - predicted,
                "excess_over_threshold": observed - upper, "investigation_flag": bool(eligible and observed > upper),
                "phase": phase, "flag_eligible": eligible, "source_csv_line": int(record.source_csv_line)})
    return pd.DataFrame(rows)
