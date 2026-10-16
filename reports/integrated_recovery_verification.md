# Integrated recovery release v1

Implemented locally in the industrial-dashboard workspace. The published checkout
was inspected, matched against the runtime before editing, and remains unchanged
on `main...origin/main`. Nothing was pushed or deployed. The recoverable pre-edit
checkpoint is `checkpoints/integrated-recovery-before-edit.zip`; protected pre-edit
code is also archived under `history/integrated_before/`.

## Implemented workflow

The existing full-horizon CP-SAT path remains the default. The optional **Recovery
and alternative objectives** control selects a current independently verified
reference and an explicit scenario-local cutoff. Selection does not solve or infer.
Separate generation/confirmation actions run the bounded two-option backend.
Passive navigation and selection reuse matching results without planning or AMD
calls. Failed current solves cannot become recommendations or current exports.
Legacy-engine selection is blocked while recovery is active: that engine has not
been verified to preserve execution history. It cannot expose an old selected
schedule through the Copilot context. Switching back reuses matching CP options;
reset restores the ordinary full-horizon workflow. Optional two-priority solves
do not silently fall back to a heuristic with different objectives/history rules.

For each reference operation `[start,end)`: completed means `end <= cutoff`;
underway means `start < cutoff < end`; an operation starting exactly at cutoff is
future. Processing and cleaning intervals are represented separately in the audit.
Started/completed pre-cleaning fixes its following placement too: cleaning must
immediately precede that same process, so pausing or transferring that batch would
violate the unchanged model. These boundary commitments are explicitly listed.
Exact fixed machine, quantity, cleaning flag, setup/start/end and prefix arcs are
preserved. Movable cleaning/setup starts at or after cutoff. A started terminal
cleanup remains exact and final on that machine; the existing single-terminal
policy does not permit restarting a completed campaign on it in this horizon.

The unchanged CP model supplies compatibility/capacity, release/deadline,
nonoverlap, immediate directed permissions and single-window setup/process and
terminal availability checks. Its new optional extra-date input includes cutoff
and reference timestamps in the exact GCD integer lattice. No silent rounding,
splitting, rate change, permission invention or resource-formula change was added.
The original independent verifier is unchanged. `planner/recovery.py` separately
adds source-input identity, exact historical operation, prefix and cutoff checks.
Ordinary-valid but historically shifted work is rejected by these added checks.

An outage intersecting fixed work is rejected atomically with:

> This outage overlaps work preserved from the reference plan. Interrupted-batch recovery is not supported.

Deadline overrides remain separate from original records. Deadlines contradicting
fixed completion or placing unstarted work before cutoff are blocked. Interpreting
and previewing do not apply changes; separate confirmation is still required.

## Versioned solver and objectives

`integrated-recovery-cp-v1` builds on the existing CP model without changing the old
default solver version/objectives. **Fewer cleanings** minimises total cleaning
events (initial, between-order, terminal), then maximises minimum deadline buffer
at that count. **More deadline protection** maximises the minimum process-completion
deadline buffer, then minimises cleaning without worsening the achieved buffer.
Both options use identical orders, constraints and protected history. Both include
all orders in the buffer objective, including fixed work.

The displayed total budget is shared equally across the two options; each reserves
60% of remaining solver time for stage A and the remainder for stage B. The maximum
shared budget is 60 seconds; default is 10. Model building is deducted from each
option budget; independent checking and the optional legacy baseline calculation
add end-to-end overhead outside CP solve time. One worker, fixed seed 20261015 and
zero positive gap tolerances are used. Time-bounded runs are not guaranteed to
return identical incumbents on different hardware/load.

Stage B has both incumbent constraints and independent translated-quality guards.
A failed, invalid, unknown or worse candidate retains stage A. A merely feasible
stage A makes stage B conditional on that incumbent, not proof of global primary
optimality. Each receipt reports objective, bound, unit, status, budget, timing,
verification and selected stage. UNKNOWN is never called infeasible. Infeasibility
messages apply to the encoded constraints without inventing an exact causal reason.

## Reference impact and matched evidence

Recovery comparisons use the exact selected reference, never EDD. Each future
process is counted once if its machine, process start or process end changes.
Before/after machine, timestamps and signed completion-time differences are
available; complete reference/revised operation audits separately include cleaning.
The reference predates the disruption and can violate revised availability; its
on-time count uses its own original effective deadlines. Revised counts use the
new deadlines. These are not same-constraint savings comparisons.

Reference/revised timelines retain continuous elapsed time and exact timestamps,
with a cutoff line and revised outage overlay. Existing daily navigation, filters
and full-schedule mode remain available. Grounded selected-schedule evidence now
includes reference/cutoff/origin, objective, preserved operations, actual changed
orders, solver proof/status/bounds, applied request/receipt and fresh verification.
The selected `quantitative_claims: []` schema and exact statement/reference/
assumption/limitation validation remain unchanged. Answers remain catalogue-bound,
not free industrial diagnosis. Reference, cutoff, constraints, option or schedule
changes invalidate mismatched explanation/review/export fingerprints. Acceptance
means further review only; pending is not acceptance.

## Reproducible public-order demonstration

`reports/integrated_recovery_demo_v1.json` is a bounded offline run with explicit
manual origin and mocked explanation/review. Reference: permissions explicitly on;
cutoff **2019-12-01 05:00:00**. Confirmed outage: `virtual-Pressure-PolyCotton`,
**2019-12-01 12:00:00 → 2019-12-02 12:00:00**. Production had already started.

| Priority | Completed preserved | Running protected | Future batches changed | Cleaning before/after | On time before/after | Stages A/B |
|---|---:|---:|---:|---|---|---|
| Fewer cleanings | 3 | 2 | 19 | 28 / 28 | 35 / 35 | OPTIMAL / FEASIBLE |
| More deadline protection | 3 | 2 | 21 | 28 / 30 | 35 / 35 | OPTIMAL / OPTIMAL |

Both pass recovery verification. No cleaning reduction was manufactured. Other
future times can change through reoptimisation/priority choice; no industrial cause
is inferred. The conflict outage **2019-12-01 04:00:00 → 06:00:00** is rejected
before application. Reset restores original orders/configuration and clears recovery.
The saved selected review package has mock explanation origin and acceptance for
further review, never a live API or production-approval claim.

## Offline evaluations

The separately frozen permission manifest specifies three cases on the same full
published source, five seconds per case, one worker/fixed seed. Restricted rules
are every other existing permission in machine/from/to numeric sorted order,
starting at index zero. Historical 26-scenario manifests/results are untouched.

| Permissions | Active listed rules | EDD cleanings | CP cleanings | Verified/on time | Stage A/B |
|---|---:|---:|---:|---|---|
| Disabled | 0 (38 listed, inactive) | 39 | 39 | both / 35 | OPTIMAL / OPTIMAL |
| Restricted | 19 | 37 | 29 | both / 35 | OPTIMAL / OPTIMAL |
| All existing | 38 | 34 | 28 | both / 35 | OPTIMAL / FEASIBLE |

Valid-comparison denominator: **3/3**; solver failures: **0**. The feasible/time-
limited second stage is retained and not relabelled optimal. Full per-case bounds,
deadline details and runtimes are in `permission_sensitivity_integrated_v1.json`.
No additional failed scenarios were invented for this three-case experiment;
separate tests exercise infeasible/UNKNOWN outcomes. Evaluating the same schedule
with doubled per-cleaning cost only rescales its secondary resource score. Cost
is absent from count/slack objectives and cannot establish a different count-optimal
schedule. These are derived scenarios from one small source, not factory trials.

The new interpretation corpus has **34 authored expected outcomes**, saved before
any live execution: **10 development, 24 held-out**. All old exposed corpora/results
remain historical development evidence. The AMD 8.2 interpretation code is unchanged.
The new corpus covers exact single/multiple changes, unknown/extended identifiers,
historical/ambiguous dates, negation, unsupported mixed requests, conflicts and
supported interpretations that Python must reject against execution history.

Offline screening: **15/15 local decisions matched**, explicitly local-validation
origin; **19 supported requests deferred**, not locally fabricated AMD responses.
New live semantic correctness/validation/transport/latency denominator: **0**.
No opt-in live interpretation evaluation was run. Mocked transport integration tests exercise
supported recovery and history rejection separately; they are not held-out accuracy.
The explicit live command in README is frozen, permits at most 24 semantic calls,
at most two transport attempts each, no repair loop, and fresh output only. It
reports local/AMD first pass, incorrect refusal, validation and transport failures,
latency and downstream application/verification separately. Diagnostic retention
is restricted to this non-sensitive corpus and screens credentials. Rejected
answers are not counted as evidence of model understanding. Final-test data/models
were not tuned or retrained.

Each API receipt contains its own transport/inference latency. Per-row
`latency_seconds` and summary latency arrays are end-to-end workflow elapsed time,
including downstream preview/application/solving when performed; they must not be
reported as raw model latency. The offline report has no API latency samples.

## Checks and delivery evidence

The complete regression suite passed **180 tests**; see
`integrated_recovery_release_tests.txt` and `integrated_recovery_release_test_result.json`.
Earlier integration runs/results remain separately recorded. Focused cases cover cutoffs at exact boundaries and
during cleaning/terminal cleaning, exact microseconds, future outages, fixed-history
conflicts/corruption, quantity identity, prefix continuity, both objective guards,
infeasible/UNKNOWN statuses, stale evidence/reviews/exports and the recovery-off
workflow. The offline Streamlit test exercises explicit selection, manual preview,
apply, both options, mock explanation, supervisor decision, stale selection and
reset; passive reruns do not solve or call AMD. This is not browser verification.

Integrity: **91 original dataset checksums**, **35 imported orders**, **731 synthetic
days**, unchanged frozen model metadata/artifacts, unchanged resource evaluator,
verifier, permissions and historical reports/evaluations. `pip check` passes.
Preservation evidence lists changed/archived files and the clean public checkout.
Browser and packaged verification outcomes are recorded separately alongside this
report; only screenshots actually captured are claimed. The final browser runner
disables AMD through placeholder environment overrides and requires visible mock
mode before explanation. Earlier browser-driver attempts used normal local
configuration without service-call instrumentation, so their inference outcomes
and total network-call count are unverified; no successful live inference claim
is made for them. These attempts were not the new held-out evaluation.

Actual Edge browser inspection completed at **1440px desktop and 680px narrow
width**: setup, explicit permission opt-in, exact historical cutoff selection,
fixed-work conflict, exact Pressure-machine selection, manual preview/confirmation,
both priorities, reference/revised timelines, labelled mock explanation, pending
and accepted-for-further-review decisions, stale review after selection change and
reset. Screenshots show readable labels and panels; the continuous timeline scrolls
horizontally at narrow widths. See `integrated_recovery_browser.json` and
`integrated_recovery_screenshots/`. These are actual browser captures, separate
from Streamlit AppTest. Initial browser-driver attempts required corrections for
startup waits and Streamlit's visible segmented fields/accessibility controls;
they were not counted as successful workflow checks.
The actual browser download is retained as
`integrated_recovery_browser_export.json`: verification passes, selected objective
is deadline protection, and the applicable decision is accepted for further review.
Its exact evidence fingerprint is recorded in the browser report. The final
explanation receipt is mock and `quantitative_claims` is exactly `[]`.

The distributable uses the existing allowlist: permitted order/synthetic data and
trusted frozen model artifacts, pinned dependencies, code/tests/docs/history needed
by regression checks. Workspace integrity covers all 91 acquired data files;
packaged runtime integrity covers 33 distributable data payloads, with the original
91-entry acquisition manifest retained separately. Restricted reuse experiments,
credentials, `.env`, virtual environments, caches, review databases, checkpoints,
publication checkout and other ZIPs are excluded. A fresh extracted copy passes
the full 180-test suite, data/model/payload checks and HTTP health/startup checks.
It uses the existing pinned Python environment; a new dependency installation was
not repeated because dependencies are unchanged. The ZIP credential scan covers
known local AMD secrets and high-confidence token/private-key patterns, including
nested archives; it is not a guarantee about arbitrary unknown credentials.
Final build/credential/startup receipts are external to their own hashed ZIP;
the report, regression logs, manifest, checks and reproduction commands are included.

Main additions: `planner/recovery.py`, `planner/recovery_solver.py`,
`app/recovery_view.py`, `app/evaluation_evidence.py`, three focused test modules,
versioned evaluation/demo/browser/package tools, frozen evaluation definitions,
this report and narration. Existing changes are limited to scenario overlay,
optional extra-date CP scaling, selected evidence/export gates, dashboard routing,
timelines/style, packaging, walkthrough/README and historical-test adapters.

## Remaining boundaries

No interrupted batches, splitting, migration, live telemetry, factory approval,
root-cause diagnosis or measured resource/financial savings. Simulated machine
states cannot establish actual execution. Started cleaning commits its batch;
started terminal cleaning closes that machine's campaign. The exact current
single-campaign assumptions are preserved. Recipe/quality permissions, capacities,
durations, calendars, actual completion records and approved SOPs still require
factory validation. Two-priority lexicographic scheduling is bounded and only
claims encoded-objective optimality when solver evidence proves it. Fresh AMD
interpretation reliability remains unmeasured until explicitly opted-in live
evaluation. No production-readiness or completed safety-monitoring claim is made.

Run the extracted folder with Python 3.11: create `.venv`, install pinned
`requirements.txt`, then `.venv/Scripts/python.exe -m streamlit run streamlit_app.py`.
Follow `demo_walkthrough.md`; the concise presentation script is
`reports/integrated_recovery_narration.md`.
