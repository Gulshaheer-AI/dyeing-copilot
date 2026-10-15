# Milestone 9: scheduling comparators and reproducible evaluation

15 October 2026, Python 3.11.9. Heuristic scenario comparisons only; no factory
savings or production-readiness claim. No agents, model training, new cleaning
permissions, revised formulas or changes to the existing optimiser were introduced.

## Methods and fair comparison

`planner/comparators.py` adds `scheduling-comparators-v1`:

- **EDD**: completion deadline, then numeric source row ID. Existing append-only
  placement builder and independent verifier.
- **Grouping**: recorded vessel, fabric, exact shade label, deadline, then numeric
  source row ID. Label ordering is lexicographic solely for determinism; **no
  light-to-dark or colour-depth interpretation** is used. Source fields map through
  the unchanged `orders_from_import`; vessel is a category, not a machine ID.
  Grouping grants no exemption. Only existing activated exact directed permissions
  can remove a cleaning event. This comparator is not a real factory planner.
- **Optimiser**: unchanged `planner.search.plan`, default three bounded swap passes,
  including its existing two grouped candidates. It still stops when EDD fails.
  No candidate, objective, rate, placement or fallback behaviour was changed.

Every method receives identical **effective** orders/configuration, including
manual/AMD deadline overrides and outage-subtracted availability. Fresh independent
checks precede resource scoring and paired differences. Construction/verification
failures are reported separately; incomplete artifacts retain partial counts/slack
and missing-order details, but have **no resource score or eligible comparison**.
Grouping failures are never replaced with EDD. An absent optimiser proposal has
unavailable metrics, not its partial EDD artifact masquerading as a proposal.

Runtime is sequential CPU wall time including construction/search, verification
and accounting. Optimiser time includes its internal EDD and candidate checks;
there is no subtraction to make it look faster. Timings vary by host/load. The UI
caches measured reports by exact scenario fingerprint and checks they match the
displayed planner artifacts. Planning-change code and AMD interpretation are unchanged.

## Fixed scenario suite and actual results

`evaluation/scheduling_scenarios_v9.json` was saved **before inspecting aggregate
results**, with explicit source IDs, dates, outages and sampling seeds. The manifest
and method/scorer/placement/evaluator/verifier hashes were frozen in
`scheduling_freeze_v9.json` before the run. No frozen file or scenario was tuned
afterwards. A second run to a separate output reproduced all 26 scenario artifacts,
metrics and statuses exactly except host-dependent runtimes; integrity evidence
records both file hashes without replacing the original result. The machine-readable result is `reports/scheduling_benchmark_v9.json`:
full effective orders/configuration, definitions, schedules, runtime, deadline/slack
rows, verification errors, all cleaning boundaries and signed paired differences.

There are **26 scenarios derived from one 35-order case**, not 26 independent
factory datasets. Twelve subsets use base seeds 901/902 plus sizes 6/12/20
(actual seeds 907/913/921/908/914/922), with explicit selected IDs stored. Subsets
retain original quantities and only applicable existing permissions; the strict
35-order public importer is unchanged. Other cases explicitly label deadline,
calendar and outage perturbations. Only those named constraints change; capacities,
rates, processing, initial/terminal rules and permission definitions stay fixed.

| Method | Valid / 26 | Construction failures | Verification failures | No proposal to verify | Total method time |
|---|---:|---:|---:|---:|---:|
| EDD | 24 | 2 | 2 | 0 | 0.024734 s |
| Grouping | 5 | 21 | 21 | 0 | 0.016745 s |
| Unchanged optimiser | 24 | 2 | 0 | 2 | 7.402687 s |

Failure counts overlap: a failed partial construction also fails completeness
verification. All 26 scenarios were reported; zero scenario-level exceptions.
The measured suite took **7.632193 seconds**; maximum single optimiser run was
**1.143825 seconds**. Aggregate eligible comparisons:

- Against EDD: **24/26 eligible**, two excluded; optimiser uses fewer cleaning
  events in **7/24**, equal in **17/24**, more in **0/24**.
- Against grouping: **5/26 eligible**, 21 excluded; **all five match** the optimiser.
  No evidence here establishes an advantage over valid grouping schedules.
- Zero differences remain in the results. Negative differences are supported and
  regression-tested, although none occurred in this suite. Signed counts across
  overlapping derived cases must not be extrapolated to a factory saving.

The naive category-first grouping often schedules a later-release category member
before an earlier-deadline member on the same append-only machine. Those
constructions miss orders; no repair or post-result comparator tuning was added.
This is an informative failed heuristic comparator, not a stronger demonstrated
planner. Heuristic failure alone is not proof of global infeasibility.

### Full source case

Permissions **disabled**: EDD and optimiser both have **39** events (4 initial,
31 between-order, 4 terminal), **35/35 on time**, minimum/median slack **201/469 h**.
Permissions **enabled**: EDD **34** events (4/26/4), optimiser **29** (4/21/4), both
**35/35 on time**, but minimum/median slack changes from **201/469 h** to **6/242 h**.
The lower-cleaning proposal has substantially less deadline buffer: planners must
review that trade-off. Neither result establishes factory recipe compatibility.

Grouping fails in both full cases, completing only 25/35 orders; its partial
29/21 event counts cannot be compared as savings. Secondary modelled totals remain
27,300/27,300 disabled and 25,550/23,800 enabled, in **modelled source units**.
The separate recorded total remains **47,950 unresolved source units**.

## Screen, review and export

The five-step workflow now leads with a three-method table: construction and
verification, initial/between/terminal cleaning, on-time/late/missing orders,
minimum/median completion slack and runtime. The selected-machine positional view
shows predecessor/rule changes without stretching a chart across months of idle
time. Both initial and terminal boundaries are visible. Invalid grouping is
explicitly unavailable as a paired comparison; its errors remain expandable.

Modelled resource scores, invented process terms and signed percentages are
expandable secondary details. Percentages use each **valid recalculated comparator**,
never the recorded 47,950. Existing AMD explanations still cover the original
verified EDD/proposal comparison; this milestone does not expand the statement
catalogue to claim AMD evaluated grouping. Manual/AMD changes retain preview,
confirmation, stale protection, reset and independent verification.

The existing planner-review export now includes `heuristic_comparators`, with
method definitions, both valid and failed artifacts, effective-case fingerprint,
timings and checks; its original EDD/proposal fields remain intact. Acceptance
remains acceptance for further review, never production approval.

## Checks, packaging and remaining limits

New meaningful checks cover deterministic grouping, no category-based exemption,
initial/terminal accounting, slack, grouping failure despite valid EDD, exclusion
denominators, negative differences, effective deadline overrides, source-ID/quantity
preservation and applicable subset permissions. A Streamlit AppTest checks the
headline, failed grouping, compact sequence controls, applying a manual override
to every method, failed construction and reset. The full workspace suite passed **136 tests** (129 existing plus seven new),
in **50.428 seconds**. `pip check` passed. Full-suite logs and structured exit status
are in `milestone_9_tests.txt` and `milestone_9_test_result.json`.
All **136 tests also passed in the isolated extracted ZIP (49.414 seconds)**.
All 33 included source hashes and every packaged payload matched. Streamlit
health/root both returned HTTP 200; the server was stopped. These automated
results are in `milestone_9_packaged_regression.json`. A fresh dependency
installation was not performed: checks used the pinned existing interpreter.
The final ZIP was rebuilt with completed reports and checked again for startup
and payload integrity. The configured credential was checked absent from its
payloads; no local review database or `.env` is included.

`milestone_9_preservation_baseline.json` fixes 67 historical/interpreter/planner/
daily/artifact files before editing. All match; all 91 dataset checksums match.
The 8.2 interpreter and UI, historical results/evaluations, frozen models,
resource formulas, cleaning permissions and optimiser remain byte-identical.
New implementation files: `planner/comparators.py`, `app/scheduling_comparison_view.py`,
`tools/benchmark_scheduling.py`; modified `app/simulator_view.py` for read-only
comparisons/export/headlines, packaging tools and current documentation. Added
versioned manifest/freeze/results, comparator/accounting/UI tests and integrity logs.

**Visual/browser inspection remains pending**: no browser tool is available.
AppTest is automated UI verification, not manual browser inspection. No new live
AMD calls were needed or claimed in milestone 9. Inspect navigation, both permission
modes, partial grouping/error panels, per-machine transitions, manual/AMD overrides,
export and reset in a browser before presenting.

The suite is small, overlapping, scenario-derived and uses assumed availability,
durations, capacities, initial states and recipe/quality permissions. Minimum slack
is descriptive, not robustness certification. Grouping is often infeasible under
this append-only construction. The optimiser is not globally optimal and cannot
recover from EDD failure. No litres/PKR savings, safety approval, independent
factory validation or production reliability is established.

## Reproduce and run

From `D:\Projects\dyeing-copilot`:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe tools/verify_demo.py
.venv/Scripts/python.exe tools/benchmark_scheduling.py --output reports/scheduling_benchmark_v9_my_run.json
.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

The benchmark refuses overwritten outputs or changed frozen definitions. A new
output reproduces the fixed scenarios with fresh host-dependent timings; do not
tune this version against the saved results. Any later search improvement needs
a new version and comparison against these preserved results.

Choose **Batch scheduling simulator**, load/review assumptions, run comparison,
inspect cleaning/deadline table and a selected machine's predecessor changes.
Activate exemptions only explicitly if demonstrating that separate illustrative
case; note reduced deadline slack. Expand resource detail if needed. Preview/apply
an override, inspect refreshed comparisons, export and reset.

Distributable: `dist/dyeing-copilot-milestone-9.zip`. In the extracted
`dyeing-copilot` directory, run `py -3.11 -m venv .venv`, install with
`.venv/Scripts/python.exe -m pip install -r requirements.txt`, then use the launch
command above. Copy `.env.example` to `.env` and supply participant AMD values only
if using live inference; manual entry/comparators need no credentials. ZIPs exclude
credentials, local review databases, caches, environments and restricted reuse data;
sample data licences and setup remain documented in README/DISTRIBUTION_DATA.md.
