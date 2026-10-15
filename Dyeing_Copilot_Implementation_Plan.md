# Dyeing Copilot: hackathon implementation roadmap

Prepared 13 October 2026. Planning document, not an implemented or trained system.

## Product decision

Build a decision-support copilot for a dyehouse production supervisor. It ingests orders and resource records, identifies unusual consumption where measurements exist, proposes a feasible lower-water batch schedule, explains the evidence, and records supervisor decisions.

The first commercial outcome is less avoidable resource consumption while preserving delivery commitments and quality. Dyeing is a promising focus, but higher profit than weaving remains a hypothesis to test with factory costs.

Hackathon priorities:

1. Reliable import, provenance and resource calculations.
2. Feasible scheduling with explicit cleaning-water assumptions.
3. AMD-powered evidence explanation and supervisor review.
4. Learned consumption prediction only if the data audit supports it.

Machine-failure prediction and live safety monitoring need separate sensor data. Chemical, temperature and pressure settings remain operator-controlled. The MVP can retrieve documented safety procedures; it cannot establish that a machine is safe from batch totals.

## Data sources and verified access status

| Source | Evidence and status | Intended use | Limitation |
|---|---|---|---|
| [S1: Faisalabad dyeing study](https://pmc.ncbi.nlm.nih.gov/articles/PMC9044317/) and [supplement DOI](https://doi.org/10.7717/peerj-cs.932/supp-1) | Article inspected; supplement advertised but bulk download not obtained. Published example has 35 orders. | Local scheduling case and possible measured water records. | Raw schema, row count and measurement provenance still require inspection. |
| [S2: Mendeley thread-dyeing dataset](https://data.mendeley.com/datasets/wfwxybkpcm/1) | Repository description verified; file bytes not inspected. Explicitly synthetic daily operational data, with resource and waste variables. CC BY 4.0. | Supplemental software and scenario tests. | Neither measured factory data nor a fabric-batch dataset. |
| [S3: industrial dyeing optimisation study](https://www.mdpi.com/2227-9717/13/11/3572) / [author preprint](https://www.preprints.org/manuscript/202510.1450) | Published paper identified; author preprint inspected. Real industrial case with machine/resource parameters. | Machine-allocation methodology and reference tables. | Not a confirmed downloadable batch training dataset. |
| [S4: Carbonfact repository](https://github.com/carbonfact/lca-database-footwear-apparel) | README inspected. Dyeing impact scores and methodology; full inventories are not published there. CC BY-SA 4.0. | Optional environmental reference panel. | Modelled LCA values are not measured batch consumption or anomaly labels. |
| [S5: Leeds batik operational data](https://archive.researchdata.leeds.ac.uk/1360/) | Real water-use and batch-size records; restricted access, response within 10 working days. | Longer-term research candidate. | Access delay and different production process make it unsuitable as the hackathon dependency. |
| [S6: wastewater-reuse experiments](https://data.mendeley.com/datasets/pjrcb6rrkn/1) | Experimental dyeing/reuse study; CC BY-NC-ND 4.0. | Background research only. | Not production telemetry; exclude from the commercial/MIT demo data bundle. |

The S1 study reports a modelled comparison of 51,100 L against 43,050 L. This is prior research, not our performance. Reproduce only after reconstructing its assumptions. Do not claim all wash-water reduction is total factory-water reduction.

Do not merge sources into one training table merely because they contain columns named water or energy. Preserve process, time resolution, units, measurement boundaries and provenance. Keep third-party datasets under their own licences; licensing application code MIT does not relicense data.

## Implementation steps

### Step 1 — Audit the data before building the model

Timebox initial access and profiling to roughly 2–3 hours. Try the publisher's legitimate supplement download route. If unavailable, use article tables for a limited scheduling scenario; do not present them as complete raw production logs.

For every acquired file record: source URL/DOI, version, retrieval date, checksum, licence, measured/synthetic/modelled status, row count, unit of observation, field definitions, missing values and duplicated records. Inspect archives before extracting and do not execute supplied research code.

Determine whether water values are metered, manually recorded, calculated from fixed rules, or simulated. Check whether electricity means kWh, power means kW, steam means kg, and thermal energy means MJ. A water-impact score is not litres consumed. Check decimal/thousands separators and dates explicitly.

Deliverable: a data audit listing which capabilities each dataset supports.

Exit decision:

- Enough independent measured records and relevant predictors: proceed to consumption-model training.
- Small scheduling table or formula-generated targets: build scheduling and transparent rule-based analysis; report this honestly.
- Synthetic records: use a separate scenario-testing mode and label all associated metrics synthetic.

### Step 2 — Freeze the MVP scope

User: production supervisor; secondary viewer: factory owner.

Workflow: import records → inspect data quality → analyse resource use → compare feasible schedules → explain recommendation → supervisor approves/rejects → export proposed plan.

Core demo: water consumption and avoidable cleaning demand. Include energy or chemicals only where compatible measurements exist. Safety is document-supported guidance, not automatic machine control.

Exclude ERP replacement, camera defect detection, live PLC integration, complex multi-tenant billing, autonomous recipe changes and broad predictive maintenance. These are later extensions.

Deliverable: one acceptance checklist and one demo story.

### Step 3 — Create the project and environment

Use Python, pandas, FastAPI and Pydantic. Use Streamlit for the initial interface; a separate frontend is optional after the workflow works. Use SQLite for the hackathon unless a shared deployment needs PostgreSQL. Keep analysis and scheduling as reusable Python modules outside the UI.

Suggested folders: app/, analytics/, planner/, copilot/, data/raw/, data/processed/, knowledge/, tests/, reports/. Raw files remain immutable. Use environment variables for model credentials and an example environment file without secrets. Pin dependencies after a working setup is verified.

Store source metadata with each dataset, source-row identifiers with each record, model versions with predictions and scenario assumptions with every schedule comparison.

Deliverable: application skeleton, environment instructions and repository structure. No external repository or deployment is created by this planning document.

### Step 4 — Define the data contracts and importer

Separate three input types:

| Input | Main fields |
|---|---|
| Orders and machines | order_id, available_at, due_at, fabric_type, shade, recipe_id, quantity and quantity_unit, machine_id, compatible_recipes, min/max_load, approved processing_time |
| Measured consumption | batch_id/date, resource type, measured value/unit, measurement boundary, actual duration, accepted/rejected output, rework and reference to source row |
| Configuration | permitted transitions/cleaning procedures, utility prices and units, quality constraints, approved SOPs, source and approval date |

Unavailable fields remain missing. Do not invent capacity, temperature, energy or machine assignments to make a real dataset look complete. If a scenario supplies an assumption, flag it separately.

Import CSV first. Add Excel once the CSV workflow is reliable. Validate positive quantities, valid dates, order uniqueness, compatible units, meter resets and machine references. Present actionable import errors. Prevent double-counting repeat uploads.

Deliverable: validated records and a data-quality panel.

### Step 5 — Implement deterministic resource analytics

Calculate only supported KPIs: litres/kg, electricity kWh/kg, steam kg/kg or thermal MJ/kg, chemical mass/kg, rework rate and machine load utilisation. Preserve resource totals and distinguish input kg from accepted-output kg. Cloth length cannot be converted to kg without documented width/GSM or measured mass.

Compare like-for-like groups: fabric, shade depth/recipe, machine and load range. Show sample counts. Start with a historical median and variation range calculated from training/history records only.

Distinguish three labels: invalid data, unusual consumption, and confirmed waste. A high value is an investigation opportunity; quality requirements or rework may explain it. No causal root-cause claims from correlation alone.

Deliverable: traceable calculations, per-record comparisons and evidence-based flags.

### Step 6 — Train and evaluate the consumption model, if supported

Train a small tabular regressor to estimate expected water use from pre-batch information. Begin with a matched-group median baseline, then compare a regularised linear model and one tree-based model. Avoid deep learning or LLM fine-tuning for sparse tabular records.

Candidate features: quantity, fabric, shade depth, recipe and machine/load characteristics actually present. Candidate target: measured water consumed. Electricity is a separate model only if measured records exist.

Exclude actual water, water-derived cost, actual wastewater proxies and post-batch outcomes from pre-batch predictors. For a retrospective model using actual duration, label it retrospective. Identify duplicated/formula-generated targets before training.

Where dates permit, split chronologically into train/validation/test, approximately 60/20/20. Keep repeated orders/batches together; fit imputers/encoders on training data only. If undated, use group-aware holdouts and state the limitation. Do not train an ML model just to split 35 orders into tiny subsets.

Measure MAE in litres, WAPE and errors by process/machine. Compare with the simple baseline. Estimate a prediction interval from quantile models or validation residuals and measure its coverage. Abstain for unsupported recipes or unfamiliar conditions. Prediction error is not savings, and an unusual residual is not a confirmed fault.

Deliverable: model card, reproducible training script and untouched-test metrics. If ML does not outperform the baseline, retain the baseline and document the result.

### Step 7 — Build a feasible batch schedule planner

Start with the supplied historical sequence or an earliest-due-date baseline, and assess it with the same feasibility checker and resource model used for candidate schedules.

Implement a compatibility-aware greedy planner plus local swaps. It can search for opportunities to group compatible work or reduce expensive cleanings, subject to approved transition rules. Do not assume every light-to-dark transition may skip washing.

Hard constraints: order release dates, due dates where feasible, machine compatibility, load capacity, processing plus cleaning time, maintenance windows and fixed/in-progress work. Grouping orders requires matching approved recipe and quality requirements. Never remove an order or reduce quantity to report savings.

Build an independent verifier for order completeness, capacity, compatibility, timing and transition requirements. If deadlines cannot be met, return an explicit infeasible case. Do not conceal missed delivery dates with a low resource score.

For tiny cases, compare the heuristic with exhaustive search. Add a solver only if the heuristic and checker are already working; an optimiser is not required to be a trained model.

Calculate litres saved with the explicit transition model and distinguish cleaning water from process water. If timing or transition costs are missing, label the output an assumption-based planning scenario. Do not claim reproduction of the original paper until its calculations match.

Deliverable: baseline and proposed schedules, verified constraints, objective components and reproducible scenario results.

### Step 8 — Implement costs and honest savings estimates

Use user-configured marginal utility prices with visible units and dates. Water cost may include pumping, treatment and wastewater disposal; fixed charges do not automatically disappear when litres decrease.

Estimated operating-cost difference = water-volume difference × marginal water cost + electricity difference × electricity price + separately measured thermal-energy difference × its marginal cost.

Do not double-count gas/steam and derived thermal energy. Add quality/rework costs only where supported. Avoid summing overlapping anomaly opportunities and schedule savings. Show the original utility/resource units even when displaying PKR scenarios.

Historical benchmarking, modelled schedule improvement and verified factory savings remain three separate result categories. Recurring monthly savings need a justified production-volume assumption, not arbitrary extrapolation.

Deliverable: transparent cost calculator, assumptions and sensitivity scenarios.

### Step 9 — Connect the AMD-powered copilot

The current event page points participants to an AMD Token Factory API. First verify the endpoint documentation, available model, quotas and a live request in the participant account; no credentials have been accessed or endpoint tested here. Use this event-provided path for the industry MVP if it satisfies the current rules. An own vLLM/ROCm deployment is a fallback, or a separate requirement if entering the Evolus partner track.

Give the model tools to read calculated facts, retrieve relevant SOP passages, compare verified schedules and create draft review tasks. It must not invent resource numbers, utility tariffs, machine limits or feasible schedules. Require structured output validated with Pydantic: observation, evidence references, uncertainty, possible causes, recommended review action and approval requirement.

Use one controlled orchestration workflow. LangGraph is optional if useful for state and approval; several debating agents add no necessary value here. RAG means retrieving documents at answer time, not training the language model on factory data.

Every operational recommendation links to calculations or an approved document. If no relevant SOP exists, state that and request technical review. Clearly label any written demo SOP as illustrative. Store decisions and prevent a model response from changing machine controls.

Deliverable: live AMD-generated explanation, model/runtime identification and reproducible request evidence without keys.

### Step 10 — Build the operator interface

Four views are enough:

1. Overview: measured totals, coverage, quality issues and ranked investigation opportunities.
2. Batch/order detail: input conditions, actual/expected values where available, source rows, supporting explanation and uncertainty.
3. Planning: original and proposed schedule, water/cost comparison, assumptions and constraint verification.
4. Review: approve/reject proposed actions with notes and export; approval records a decision rather than actuating machinery.

Use persistent badges for measured, synthetic, literature/modelled and assumed inputs. Keep safety guidance separate from resource evidence. Display data timestamps and user-facing plain language.

Deliverable: complete input-to-decision demo, not only chat and charts.

### Step 11 — Test the claims that matter

Required checks: unit conversion and zero-output cases; duplicate/missing records; leakage prevention; schedule completeness and constraints; infeasible cases; missing SOPs; model timeout; unsupported numeric claims and replayed approvals.

Build a frozen evaluation set before tuning thresholds. Consumption-model accuracy uses held-out measured records. Anomaly precision/recall requires independent labels; unlabelled real records cannot produce trustworthy detection accuracy. Synthetic injected anomalies may test the pipeline but must have separate scores.

Test explanations against a fixed fact bundle: numeric consistency, source support, uncertainty and absence of unapproved settings. Measure latency and model calls per analysed case. A future factory pilot must verify interventions and preserved quality before claiming realised profit.

Deliverable: evaluation report containing denominators, data provenance, baselines and limitations.

### Step 12 — Prepare and submit

Demo narrative: supervisor imports records → sees evidence → inspects a resource issue or cleaning opportunity → compares a verified schedule → receives the AMD-powered explanation → approves a proposed plan → exports it.

Prepare a runnable README, public-code release with no secrets, sample data whose licence permits distribution, environment instructions, deployment/demo access, presentation and video according to current submission requirements. Keep backup screenshots/video and an explicitly labelled cached explanation for outages; the live AMD path must actually work.

Pitch differentiation: local process relevance, defensible recommendations, explicit quality/delivery constraints and measured/modelled provenance. A borrowed paper result remains attributed prior research. Our numbers come only from our reproducible evaluation.

## Build schedule and checkpoints

These are internal targets in Pakistan time, not verified submission cutoffs. Check the participant dashboard because public event descriptions have shown differing online end dates.

| Date | Priority | Checkpoint |
|---|---|---|
| Oct 13 evening | Dataset audit, scope and AMD API smoke test | Decide which inputs are genuinely available; do not spend the night chasing inaccessible files. |
| Oct 14 | Importer, resource calculations and baseline | One record can be traced from source to displayed metric. |
| Oct 15 | Planner/checker; model training if data supports it | Produce a feasible comparison; do not force ML if records are insufficient. |
| Oct 16 | Copilot, SOP retrieval and interface | Complete one live input-to-approval workflow. |
| Oct 17 | Frozen evaluation, deployment and pitch/video | Submission-ready build; stop adding features. |
| Oct 18 | Buffer only if actual cutoff allows | Repairs and rehearsal, not a dependency for completion. |

If time becomes tight, cut optional energy models, chemical analysis, rich authentication and multilingual output first. Preserve correct calculations, feasibility verification, data labels, working AMD inference and a clear demo.

## What we may claim

| Evidence | Appropriate claim |
|---|---|
| Independent measured holdout | Consumption-prediction error on the named dataset. |
| Measured orders evaluated with explicit cost rules | Modelled water/cost difference under stated assumptions. |
| Synthetic scenarios | Software behaviour on simulated scenarios. |
| Published research | Authors' reported result, with attribution. |
| Factory intervention with comparable production and maintained quality | Verified pilot improvement within the observed scope. |

## First build session

Resolve the S1 supplement, profile acquired records and create the data contracts. In parallel in the ordinary workflow, verify the participant-provided AMD API documentation and access. Select the exact demo dataset only after this audit. Current research has inspected the article and its tables, but no consumption model, planner, app, AMD endpoint or factory pilot has been implemented.

## Technical and event references

- [AMD hackathon brief and technology FAQ](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii)
- [AMD ROCm vLLM inference guidance](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/inference/vllm.html)
- [scikit-learn quantile prediction intervals](https://scikit-learn.org/stable/auto_examples/ensemble/plot_gradient_boosting_quantile.html)

