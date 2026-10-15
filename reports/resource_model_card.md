# Synthetic daily resource model card

## Provenance and scope

Synthetic daily thread-dyeing data: Ananya Halder, Mendeley Data version 1, DOI 10.17632/wfwxybkpcm.1, CC BY 4.0. The downloaded CSV has 731 daily aggregates and 39 fields covering 2023–2024. These are not fabric batches or measured factory telemetry. Original files remain immutable. This model is a retrospective software demonstration, not a production forecast, causal optimiser, fault detector or safety system.

## Features and leakage exclusions

Inputs: Production_Volume_kg, Machine_Utilization_%, Number_of_Workers, Liquor_Ratio_1:x, Temperature_C, Cycle_Time_hr, Dye_Batch_Count. These are recorded retrospective workload/process observations; no planned-value availability is established. Day_Type is excluded from both predictors and anomaly ground truth. Both water/electricity targets, their total counterparts, wastewater, wastes, chemical quantities/intensities, fixation, duplicate tonne production, calendar fields and Monthly_Demand_Factor are excluded. See resource_training_protocol.md and the artifact metadata for the complete field-role audit and exclusions.

## Training and thresholds

The [frozen protocol](resource_training_protocol.md) predates fitting and test evaluation. Chronological partitions are **438 train** days (2023-01-01–2024-03-13), **146 validation** days (2024-03-14–2024-08-06), and **147 test** days (2024-08-07–2024-12-31). No date crosses partitions. All fitted objects use train only. The validation set selects hyperparameters and whether to retain regression or the median; no validation refit occurs. Test MAE and alert counts are computed only after these choices and thresholds are frozen.

Each resource uses a separate pipeline with train-fitted median SimpleImputer and either a train-median DummyRegressor or a RandomForestRegressor (64 trees, depths 3/5, minimum leaf size 10, seed 42, one job). Missing required source values are rejected; the imputer records train-only preprocessing and is not an excuse to accept incomplete inputs. Both resources selected depth 3 on validation. Baseline fallback remains implemented and tested; it was not needed on this dataset. See the [scikit-learn leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html) and [regressor contract](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html).

| Resource / unit | Median validation MAE | RF depth 3 / depth 5 validation MAE | Median test MAE | Retained RF test MAE | Test investigation flags |
|---|---:|---:|---:|---:|---:|
| Water, L/kg | 4.550205 | 3.304158 / 3.351911 | 4.081122 | **3.556394** | **11 / 147** |
| Electricity, kWh/kg | 0.084322 | 0.071939 / 0.071951 | 0.072133 | **0.066272** | **3 / 147** |

The targets are the published intensity columns, retained rather than silently recomputed from rounded totals. No total-resource model is fitted. Water and electricity predictors exclude each other's targets/totals as well as their own. The seven allowed features are fixed identically for the two separate pipelines; there are no learned anomaly labels.

For validation residuals `r = observed − predicted`, sort the 146 residuals and select one-based rank `min(n_val, ceil(.95*(n_val+1))) = 140`. Offset is `max(0, residual[140])`. Upper expected threshold = predicted intensity + offset. Offsets are **6.0765502479835405 L/kg** and **0.16006723187095195 kWh/kg**. Observed > upper is a flag, only on dates after the validation cutoff. Training/calibration dates are labelled fitted/calibration history and are not treated as unseen test alerts. This is a one-sided empirical threshold, not a two-sided prediction interval or guaranteed conformal coverage: validation also selects the model and the series need not be exchangeable.

Test exceedance fractions are approximately 7.48% for water and 2.04% for electricity, not anomaly accuracy. No precision, recall, fault-detection accuracy or independent fault labels exist. No injected anomalies were used for model selection or these reported results; any artificial test-copy perturbations are separate software checks.

## Data profile and arithmetic audit

CSV SHA256: `1e30fdb86b267751b615f6f1c9eb3090c84def01692eef7704da5262bdd82dff`. There are 731 unique consecutive dates, no missing source cells, and 39 named fields. Per-day water totals nearly equal production kg × published water L/kg: mean absolute rounding difference **41.964542 L**, maximum **131.6 L**. Electricity counterparts differ by mean **3.186590 kWh**, maximum **11.662 kWh**. Tonnes × 1000 differs from kg by up to about **5 kg**. These relationships motivate exclusions, not conversion/repair of the source values.

The project-owned profile records all field roles and numeric ranges in artifacts/daily_resource/metadata.json. Resource totals are arithmetic counterparts; water/electricity intensities are separate targets. Production tonnes duplicates rounded kg. Dye, salt, alkali, acid and auxiliary masses/intensities form arithmetic counterpart pairs. Wastewater, solid/yarn/chemical waste and their normalised quantities are post-process outcomes or derived fields; BOD/COD/pH are water-quality observations. Fixation is conservatively excluded as a downstream observation. Calendar identifiers, Monthly_Demand_Factor and Day_Type are synthetic context/labels excluded from modelling. Only the seven stated retrospective workload/process observations are allowed inputs.

Profiling the source/schema and arithmetic relationships is descriptive data auditing; these summaries do not select model settings or thresholds. No downloaded notebooks, research training scripts or their reported fits are executed or reused.

## Investigation limitations

A flagged synthetic day exceeds its model's empirical upper expected threshold. A residual does not prove waste, a machine fault, a safety hazard, a causal root cause or recoverable savings. There are no independent anomaly labels, so precision, recall and fault-detection accuracy are not reported. A supervisor should inspect the daily production basis, resource definitions, process observations, recording consistency and quality/rework context. This document is not an approved machine SOP and authorises no temperature, pressure, chemical, recipe or machine-control change.

## Reproduction and persistence

Run `.venv/Scripts/python.exe tools/train_daily_resources.py` to create project-owned pipelines, metadata and historical predictions under artifacts/daily_resource, outside the dataset pack. The model version for this run is **synthetic-daily-v1-3bb6653352e92acf**. Version identity hashes the input dataset, saved model bytes and frozen protocol. Metadata also records dependency versions, creation time, split dates, feature/exclusion lists, profiles, validation choices, test metrics, residual offsets and model SHA256. Artifact fingerprints include the exact metadata bytes; retraining can invalidate reviews even if the deterministic estimator version remains unchanged.

The interface caches loaded artifacts by current metadata/model-file hashes and never trains on reruns. Load-time checks reject inconsistent model hashes, feature contracts, scikit-learn versions or changed training protocols. Only trusted locally generated joblib files are loaded; never substitute downloaded/untrusted pickle artifacts. Local hashes are integrity checks, not protection against an attacker who can rewrite the workspace and manifest together.

Historical replay is **Replay of synthetic daily records**, not a live sensor connection. It shows a prefix of loaded dates after the saved validation cutoff without fitting or updating thresholds. A changed uploaded synthetic CSV is scored with saved predictors; the displayed frozen evaluation still belongs to the original training dataset and is explicitly marked as such. There is no new untouched-test evaluation claim for uploads. Dataset, model, selected-day/input/prediction and documentation fingerprints bind explanations and review items to their exact evidence.
