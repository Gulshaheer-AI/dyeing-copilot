# Illustrative dyeing scheduling scenario, version 1

Model identifier: `illustrative-dyeing-v1`. Implemented in `planner/`, independently of the recorded resource-analysis modules. This is a configurable simulator, not an authoritative reconstruction of the study or a factory production plan. All machines, capacities, calendars, duration interpretations, rates and transition approvals are scenario assumptions.

## Recorded data and scenario inputs

The importer is unchanged. The application adapter accepts only a successful, complete 35-order importer result. It copies stable source row ID, recorded cloth quantity, vessel category, fabric, shade, duration value and parsed dates into immutable scenario orders. It does **not** pass any recorded water fields to the scheduler or evaluator. Tiny synthetic orders can be constructed separately for tests; they do not enlarge the Sitara dataset.

The unchanged recorded case total remains **47,950 in unresolved source units**. Recorded water components remain available in Resource analysis and are never replaced by scenario values. Uploaded cases retain their own recorded totals. No recorded total is used to calculate the scenario difference:

`scenario difference = evaluated baseline total − evaluated proposed total`

Both totals use the **same orders, configuration, evaluator, verifier, initial state and final-cleaning boundary**. No PKR or realised savings are inferred.

## Explicit demo assumptions

Nothing is planned until a configuration is supplied and the comparison is run. **Load illustrative demo assumptions** generates a configuration for the complete imported case and shows its effective JSON before planning. It is editable. The default configuration is:

| Setting | Illustrative assumption and provenance |
|---|---|
| Machines | One virtual machine per observed vessel/fabric pair. For the bundled case: `virtual-Open-Cotton`, `virtual-Jet-Cotton`, `virtual-Jet-PolyCotton`, `virtual-Pressure-PolyCotton`. These are invented resources, not factory equipment. |
| Compatibility | Each demo machine permits its one recorded `(vessel category, fabric)` pair. Custom machines can list multiple explicit pairs. Vessel category is not a physical machine ID. |
| Capacity | 5,000 **source quantity units** per virtual machine; invented for illustration. No conversion to mass or documented machine capacity is asserted. Every order must fit whole; no splitting, merging or simultaneous batching. |
| Availability | Continuous 24/7 availability from the earliest imported release date to the latest imported delivery-date boundary. Multiple sorted, nonoverlapping windows can be configured to represent closures. No real maintenance history is known. |
| Release | Start of the recorded order-place date, 00:00 in Asia/Karachi scenario local time. This is an interpretation, not established shop-floor release telemetry. Cleaning also waits until release. |
| Deadline | 00:00 on the day after the recorded delivery date. Process completion must be at or before this boundary. End-of-delivery-day interpretation is assumed. |
| Duration | One numeric source duration unit is assumed to equal **one hour**, so values 10/20 become 10/20 scenario hours. This does not resolve the original duration unit or verify approved production time. |
| Initial state | Each used virtual machine starts dirty (`initially_clean = false`), requiring cleaning before its first order. A configured initially-clean machine needs no first-order wash. |
| Cleaning event | 350 modelled source units and one scenario hour per required wash. The number 350 is inspired by the study's wash factor, but its use here, universality and timing are illustrative. It is not a conversion of the recorded fields to litres. |
| Process term A | `0.10 × source quantity`, in modelled source units. Invented rate, not an empirical fit or recorded component. |
| Process term B | `0.05 × source quantity`, in modelled source units. Invented rate, not an empirical fit or recorded component. |
| End boundary | One immediate final cleaning event per used virtual machine, even if the last order is non-Black. Included in both time/availability and resource totals. Unused machines have no cleaning events. |
| Idle state | State persists across idle time and availability gaps. No extra ageing, restart or idle-consumption rule is assumed. This is a limitation. |
| Resource/time labels | Only `modelled source units` and Asia/Karachi scenario local time are supported in version 1. There is no litre, kg or energy-unit selection. |

Recipe IDs and quality compatibility are missing from the dataset. The demo lists **inactive, directed order-pair permissions** between matching recorded vessel/fabric/shade categories, with a basis explicitly assuming recipe/quality compatibility. For the bundled case there are 38 such directed permissions. Specification and depth can differ; matching colour does **not** establish that exemption is safe. The list is a proposed scenario assumption only.

The user must explicitly activate the checkbox permitting the **listed** exemptions before any is applied. It controls the effective `allow_cleaning_exemptions` flag, even if a different value appears in the editable JSON. The effective JSON is displayed before running. An exemption requires both activation **and** an exact configured `(virtual_id, from_order_id, to_order_id)` permission. Colour matching alone in the planner/evaluator grants no exemption. Deleting the pair or disabling activation requires cleaning. The checkbox is permission for this hypothetical simulation, not a factory SOP approval.

## Deterministic equations

For order `i`, let `q_i` be its unchanged numeric source quantity, `d_i` its numeric source duration, and `h` the configured hours per duration unit:

`processing_hours_i = d_i × h`

`process_A_i = q_i × rate_A`

`process_B_i = q_i × rate_B`

These process terms are sequence independent. They do not use measured resource fields, Black multipliers, the audited 2,100 threshold, inferred recipe changes or output quality. They are generic scenario terms with assumed boundaries; A/B must not be relabelled as the text components.

For each machine's chronological sequence, let `clean_i` be 1 if a wash is required before the order and 0 otherwise:

- First order: `clean_i = 0` only when that virtual machine is explicitly configured initially clean.
- Later order: `clean_i = 0` only when activation is enabled and the exact previous-to-current directed permission exists for that machine.
- Every other transition: `clean_i = 1`, regardless of colour, fabric spelling, Black status or perceived similarity.

`pre_order_cleaning = sum(clean_i) × cleaning_water`

`terminal_cleaning = used_machine_count × cleaning_water` when terminal cleaning is enabled; otherwise zero.

`scenario total = sum(process_A_i) + sum(process_B_i) + pre_order_cleaning + terminal_cleaning`

Each required wash occupies `cleaning_hours` on its assigned machine. No wash is attributed by looking past the final row. Initial/terminal rules are identical in baseline and proposal; no unexplained 2,800 subtraction, special end-order adjustment or source-code defect is copied. The source primary formula remains a separate diagnostic in `tools/audit_source.py`, documented in [source_rule_audit.md](source_rule_audit.md); it is not the runtime scenario model.

## Time, capacity and allocation

All orders are nonpreemptive and occupy their machine from pre-cleaning start to process completion. Each complete block must lie in one availability window. Cleaning and processing cannot overlap another order on that virtual machine. An allowed exemption makes cleaning start equal processing start, with no cleaning demand/time.

The baseline sorts the complete case by delivery deadline, then numeric stable source row ID. For each order it appends to the compatible machine with enough capacity and the earliest feasible finish, breaking ties by virtual machine ID. It finds the first availability window satisfying release, deadline, processing and cleaning requirements. It reserves enough space for immediate terminal cleanup after each tentative final order. Final cleanup begins immediately at the last order's process completion and must fit availability; the order's delivery deadline applies to process completion, not subsequent machine cleanup.

An order above all compatible capacities is explicitly reported as infeasible without prohibited splitting. Missing compatibility and unavailable deadline slots are reported. If this EDD construction fails, the application displays failed verification and the incomplete construction, with **no comparison, proposal or export**. Greedy EDD failure does not prove global infeasibility when a different allocation/order might succeed; version 1 abstains instead of solving that harder feasibility problem.

## Improvement search and independent verification

The planner first retains a verified EDD baseline. It then tries two category-grouping priority orders (deadline-first grouping and category-first grouping), followed by up to three best-improving pairwise-swap passes. Every candidate is rebuilt using compatibility/capacity/windows and independently verified. Only strict decreases in the same evaluated resource total are accepted. Infeasible candidates are discarded. If nothing improves, the proposal remains the baseline and the displayed difference is zero. No global optimality is claimed for the 35-order case.

`planner/verifier.py` does not call the planner or its placement helper. It checks the schedule against the original immutable order set and configuration:

- Every expected ID appears exactly once, with no unknown IDs and unchanged quantities.
- Virtual machine identity, vessel/fabric compatibility and whole-order capacity are valid.
- Processing duration and cleaning duration match configured interpretation/rules.
- Required cleaning is present; exemptions exactly match an activated permission or configured first-order clean state.
- No occupancy overlap occurs; cleaning cannot precede release, process completion cannot miss deadline, and occupation fits operating availability.
- Every used machine has exactly the configured final cleanup, at the correct boundary and within availability. No unknown terminal machine or extra cleanup is accepted.

The resource evaluator refuses invalid schedules. Export verifies **both** schedules again and recomputes both resource summaries instead of trusting previously displayed numbers. A lower-resource invalid artifact is never exportable as a valid proposal.

## Export and reproduction

The JSON download contains the model identifier, imported source filename/SHA256, separately labelled recorded total, complete scenario assumptions (including permissions and activation), input orders/releases/deadlines, baseline, proposal, timing, cleaning-required flags, terminal-cleaning events, both resource summaries and fresh scenario-verification status. It explicitly denies factory validation and machine-control authority. Changes to configuration or source hash invalidate the displayed comparison and download until a new run.

Run `.venv/Scripts/python.exe -m streamlit run streamlit_app.py`, select **Scheduling simulator**, load the assumptions, inspect the effective configuration, optionally activate the listed illustrative permissions, and run. Planning always uses all 35 accepted orders; filters on Orders/Resource analysis do not apply. See [milestone_3_verification.md](milestone_3_verification.md) for exact reproducible results and test evidence.
