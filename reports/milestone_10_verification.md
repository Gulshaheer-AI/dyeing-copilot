# Milestone 10: verified CP-SAT backend

15 October 2026, Python 3.11.9. Started from milestone 9; no milestone 9.1 was
implemented. Recoverable checkpoint: `checkpoints/milestone_9_before_m10.zip`,
SHA256 `4e37d497fbc8fd135ecb4ed6528531c7cec73e92f6acf164a182e5d6a66f8c29`,
identical to the preserved milestone-9 ZIP.

## What changed

Separate `planner/cp_sat.py` jointly chooses assignments, immediate predecessor
arcs and timing; it requires no successful EDD construction. Exact optional
machine/window alternatives, circuits and full cleaning-plus-process blocks model
the existing scenario. Quantities, effective deadlines/releases, compatibility,
capacity, outages, initial/terminal cleaning and directed permissions remain
unchanged. No append-only restriction is imposed on the solver.

The unchanged verifier and evaluator independently check every translated candidate.
Stage A minimises cleaning events including initial/terminal events. Stage B fixes
the verified incumbent count and maximises minimum deadline slack. A merely feasible
Stage A is labelled conditional; failed/UNKNOWN/invalid Stage B retains Stage A.
Bounds, objectives, statuses, zero gap limits, seed, workers, times and verification
are separate fields. UNKNOWN never means infeasible. Only the stated encoded
objective can be called optimal. See [complete model and references](cp_sat_model.md).

Time uses exact GCD-scaled integer microseconds relative to the earliest scenario
boundary. No second/microsecond value is rounded. Conservative range/model-size
limits fail explicitly. Default total budget **10 s**, configurable maximum **60 s**,
shared across build and both stages, one worker, seed **20261015**. Normal solver
shutdown/translation overhead can exceed wall budget by a few milliseconds.

CP-SAT is now the **default** engine after model tests and the preserved-scenario
benchmark passed. **Legacy heuristic (explicit fallback)** remains selectable.
An optional fallback checkbox is off by default; fallback retains its heuristic
origin and CP failure evidence, never a CP-SAT-success label. EDD/grouping controls
are removed from the main planner; old methods, source files and offline benchmarks
remain intact. No existing search behaviour was tuned or replaced in its module.

The original immutable AMD/manual preview/apply/reset panel is unchanged. It still
creates effective constraints and may compute a temporary legacy result. Before
display/export, the selected engine reruns on that exact case; the temporary result
is never presented as CP-SAT. Cache markers include source/scenario and backend
settings; current export checks both case and effective-order/config fingerprints.
A failed current solve preserves previous successful artifacts separately and
prevents current export. Legacy exports identify the explicit fallback engine.

**Integration blocker handled explicitly:** the existing copilot schedule
explanation/review contract needs verified EDD and a non-worse proposal. CP-SAT can
produce solutions when EDD fails, so reusing that contract would mislabel results.
CP-SAT schedule explanation and supervisor-review actions are **disabled with a
visible reason**. Recorded-order/daily copilot use and live AMD constraint
interpretation remain available; the explicit legacy engine retains its original
comparison explanation/review flow. No new live AMD calls were made or claimed.
The CP export contains schedule, assumptions, request/override history and original
response receipts, solver evidence, fingerprints, verification and pending-further-
review status. No factory approval or machinery action is implied.

## Dependency compatibility before changing requirements

A new `.venv-cpsat-check` installed the full candidate pins in a clean environment
before editing project requirements. OR-Tools **9.15.6755** requires protobuf
**>=6.33.1,<6.34** ([official package metadata](https://pypi.org/project/ortools/9.15.6755/)).
Pinned protobuf changed from 7.36.2 to **6.33.6**, with new pins **absl-py 2.3.1**,
**immutabledict 4.2.2**. Streamlit's installed dependency metadata permits protobuf
>=5.26.1,<8. Clean `pip check` passed, solver tests passed, trusted frozen models
loaded, and **all 1,462 saved daily predictions matched** within 1e-12 without
training. NumPy, pandas, scikit-learn and every other old pin stayed unchanged.
Only then were the working requirements/environment updated.

Original requirements bytes are archived as `evaluation/requirements_m9.txt` and
inside the recoverable checkpoint. Historical evaluation files/hashes were **not
rewritten**. Preservation tests now check that exact archive hash and permit only
the four audited dependency changes in current requirements; every other protected
file still uses its historical hash. `milestone_10_dependency_check.json` records
actual clean-environment evidence. A clean install really occurred in this
milestone, unlike earlier package smoke checks using only an existing interpreter.

## Model tests before UI integration

Tiny exhaustive permutation cases compare feasible minimum cleaning counts for
all eight enabled/disabled x initially-clean/dirty x terminal-on/off policies.
Additional tests cover immediate directed adjacency, releases/deadline equality,
cleaning crossing outage boundaries, terminal fitting, closed/unused machines,
capacity, compatibility, joint assignment to two machines, second/microsecond
precision, range rejection, invalid translation/hints, UNKNOWN, Stage-B retention
and a deliberately FEASIBLE Stage-A receipt that must not claim global optimality.

An independent EDD-failure example has two one-hour orders, one machine and one-hour
cleaning: order 1 release 08:00/deadline 10:00, order 2 release 00:00/deadline 11:00.
EDD appends order 1 first and fails to place order 2; CP-SAT places 2 before 1 and
passes the unchanged verifier. This is a synthetic modelling check, not a claim
that the preserved 26-case benchmark adds newly feasible cases.

UI tests cover default CP-SAT, current verified export, disabled legacy explanation,
no benchmark selectors, cached reruns, manual deadline application, infeasible
current solve, previous-result labelling and reset. Routing tests distinguish
UNKNOWN/no-result from explicitly allowed heuristic fallback. Existing heuristic
UI regressions explicitly select the retained legacy engine; obsolete milestone-9
benchmark-selector assertions were adapted to the user's new control layout.

## Frozen 26-scenario benchmark: all outcomes retained

The exact milestone-9 manifest/seeds and assumptions were reused without editing.
`evaluation/cp_sat_freeze_v10.json` froze CP code/scorer and referenced method files
before aggregate results. No frozen code was changed afterwards. New results:
`scheduling_benchmark_v10.json`; compact per-scenario counts, minimum/median slack,
runtimes, bounds and failures: `scheduling_benchmark_v10_summary.json`.
Original milestone-9 outcomes remain untouched. Legacy methods were rerun for
fresh timings, with identical effective orders/configurations for all methods.

| Method | Verified / 26 | Failed/absent schedules |
|---|---:|---:|
| EDD | 24 | 2 |
| Grouping | 5 | 21 |
| Old optimiser | 24 | 2 |
| CP-SAT | **24** | **2 proved encoded INFEASIBLE** |

All **24 verified CP schedules have Stage-A OPTIMAL cleaning counts**. Stage B is
OPTIMAL in **19**, FEASIBLE in **5**; no slack-optimality claim for those five.
The tight order-12 deadline and closed Open machine cases are infeasible for the
encoded constraints. No UNKNOWN occurred in this benchmark; mocked UNKNOWN tests
remain separate from real solver evaluation. No heuristic fallback was used in
the benchmark. Runtime for the whole suite including legacy methods was **62.332389 s**.

| Verified paired denominator | CP fewer cleanings | Equal | CP more | Excluded |
|---|---:|---:|---:|---:|
| Versus EDD: 24 | 9 | 15 | 0 | 2 |
| Versus grouping: 5 | 0 | 5 | 0 | 21 |
| Versus old optimiser: 24 | 8 | 16 | 0 | 2 |

Equal, failed and potentially worse differences are preserved, never clipped or
filtered away. These overlapping scenarios derive from **one small historical
case**, not independent factory datasets or a general accuracy score. CP did not
improve verified feasibility on this particular suite. Fresh legacy runtimes total
0.028633/0.020210/7.920489 s for EDD/grouping/optimiser respectively; runtime
boundaries include each method's own construction/checks and CP's model/solve/checks.
Hints originate from the separately timed old optimiser and are identified.

Full case, permissions disabled: CP cleaning **39**, minimum slack **201 h**,
both objectives OPTIMAL; old optimiser also 39/201 h. Permissions enabled:
CP cleaning **28**, proven optimal for this model, versus old optimiser **29**.
CP Stage B finds minimum slack **123 h**, objective bound **202 h**, FEASIBLE,
versus the old optimiser's **6 h**. This is not proven maximum slack. Machine-readable
records include median slack and every deadline. A 10-second wall limit can change
feasible timing incumbents/ties across runs despite fixed seed/worker count.

## Regression checks

The complete workspace suite passed **147 tests in 114.443 seconds**: all 136
existing tests plus 11 new solver/routing/UI checks. Unit tests with mocked UNKNOWN
or deliberately FEASIBLE receipts are labelled as such; the 26-scenario benchmark
used actual OR-Tools solves. Working and clean-environment `pip check` both passed.
Logs/exit status are in `milestone_10_tests.txt` and `milestone_10_test_result.json`.
The isolated extracted ZIP also passed **147 tests in 112.346 seconds**, with all
33 included original source checksums and every packaged payload verified. Its
Streamlit root and health endpoints returned HTTP 200, then the server was stopped.
These checks reused the newly created clean compatibility environment; no second
venv installation inside the extracted ZIP was performed. Evidence is in
`milestone_10_packaged_regression.json`; the final rebuilt ZIP was checked again
for startup/integrity. Configured credentials were checked absent from all payloads.

## Preservation, packaging and limits

Original datasets, frozen model files/protocol, resource evaluator, verifier,
scenario rules/permissions, legacy optimiser/comparators, AMD client/interpreter
and its manual/local-validation UI remain byte-identical. The only historical
protected runtime-file exception is the authorised requirements change, audited
against its unchanged archive. All historical reports/evaluations remain unchanged.
`milestone_10_integrity.json` records original checksums, freeze/preservation hashes
and checkpoint identity. No agents, frozen-model retraining, GPU migration or measured factory
savings were added. The recorded total remains 47,950 unresolved source units.

Visual/browser verification remains **pending**: no browser tool is available.
Streamlit AppTest is automated, not manual browser inspection. Manually inspect
default/legacy selection, budget/fallback labels, source and permission changes,
AMD/manual preview/apply, current verification, failed-result state, export and
reset. The CP-specific explanation/review limitation must remain visible.

Versioned distribution: `dist/dyeing-copilot-milestone-10.zip`. Trusted frozen
artifacts, source samples/licences, histories and both benchmark versions are
included. Credentials, .env, environments, caches, local review databases and
restricted reuse files are excluded. External publishing/deployment was not done.

## Run and reproduce

From `D:\Projects\dyeing-copilot`:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

Choose **Batch scheduling simulator**, load/review illustrative assumptions and
leave **CP-SAT (default)** selected. Run, inspect both stage statuses/bounds,
cleaning counts/slack and selected-machine sequence. Apply a manual/AMD outage or
deadline, inspect the current selected-backend result, export, then reset. Cleaning
permissions stay opt-in. Use **Legacy heuristic (explicit fallback)** only
explicitly; it retains the original EDD/proposal explanation workflow.

For an extracted ZIP, create `.venv` with `py -3.11 -m venv .venv`, install its
requirements, then use the launch command above. AMD credentials are optional for
local planning; configure `.env` from `.env.example` only for live inference.

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe tools/verify_demo.py
.venv/Scripts/python.exe tools/benchmark_cp_sat.py --output reports/scheduling_benchmark_v10_my_run.json
```

Saved benchmark outcomes cannot be overwritten. Reproductions use the same frozen
model/scenarios but may find different bounded-time timing incumbents. Later search
changes must be separately versioned. This milestone establishes software model
checks, not factory recipe/quality approval, safety certification, realised savings
or production readiness.
