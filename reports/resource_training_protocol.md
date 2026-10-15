# Frozen synthetic daily resource evaluation protocol

Declared before fitting, settings selection or test evaluation for milestone 5.

Predict the published water L/kg and electricity kWh/kg intensities independently, as retrospective daily aggregates. Allow only Production_Volume_kg, Machine_Utilization_%, Number_of_Workers, Liquor_Ratio_1:x, Temperature_C, Cycle_Time_hr and Dye_Batch_Count. These are retrospective workload/process observations, not documented plans. No causal optimisation or pre-production forecasts are claimed.

Exclude both resource targets, their totals/counterparts, wastewater, waste quantities/intensities, BOD/COD/pH, chemicals, fixation, duplicate tonne production, calendar fields, Monthly_Demand_Factor and Day_Type. No target-derived cost or synthetic label is used. Schema/arithmetic profiling is descriptive; full-source audit summaries do not tune the model.

Sort by unique calendar date. First floor(0.60n) rows train; next floor(0.20n) validate; remaining rows test. Fit all preprocessing/estimators on train only. Compare a training-median DummyRegressor to one RandomForestRegressor family: 64 trees, depths 3 and 5, minimum leaf size 10, random seed 42, one CPU job. Select depth by validation MAE, then select the regressor only if its validation MAE is strictly better than the median baseline. Otherwise keep the baseline. Do not refit on validation.

Calibrate one upper expected threshold on selected-model validation residuals observed minus predicted. Use sorted residual at rank min(n_val, ceil(0.95*(n_val+1))), one-based, and clamp the resulting offset at zero. Upper threshold = prediction + offset. Strict observed > threshold is an investigation flag on test dates only. This is an empirical one-sided validation calibration, not a two-sided prediction interval or guaranteed conformal coverage: validation is also used for model selection and the daily series need not be exchangeable.

Freeze features, fitted pipelines, selection and residual offsets before test evaluation. Evaluate median, selected regression setting and retained predictor on the untouched final test period once. Report MAE in target units and test flag counts, without precision/recall, fault accuracy, causal root causes or recoverable savings. No anomalies are injected into the training/evaluation dataset.
