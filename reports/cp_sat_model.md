# CP-SAT dyeing model v1

This is a joint virtual-machine assignment, immediate-predecessor and timing model,
not factory control. The existing `planner/search.py`, verifier, evaluator and
scenario assumptions are unchanged. Benchmark methods remain offline; the normal
planner selects CP-SAT by default, with an explicit legacy fallback.

## Modelling references and attribution

The implementation was written for this project, informed by these OR-Tools
examples. No example source code or example data were copied:

- [CSLiu2, scheduling with transitions](https://github.com/google/or-tools/blob/stable/examples/contrib/scheduling_with_transitions_sat.py): optional assignment and dummy-node circuits for immediate successors.
- [Google OR-Tools, setup/release/due dates](https://github.com/google/or-tools/blob/stable/examples/python/single_machine_scheduling_with_setup_release_due_dates_sat.py): release/due-date timing and sequence-dependent setup modelling.
- [Google OR-Tools, flexible job shop](https://github.com/google/or-tools/blob/stable/examples/python/flexible_job_shop_sat.py): optional machine alternatives and no-overlap constraints.

OR-Tools is distributed under its [Apache-2.0 licence](https://github.com/google/or-tools/blob/stable/LICENSE).
Dependencies are installed separately; project packaging does not relicense them.
Unlike the transition example's fixed first-start/no-idle equalities, this model
allows idle time and chooses all times freely within explicit calendars. It does
not copy sample setup reductions, horizon assumptions or source formula defects.

## Exact time lattice and limits

Convert timedeltas to integer microseconds using days/seconds/microseconds, never
floating `total_seconds()`. Epoch is the earliest effective release/calendar
boundary. Quantum is the GCD of all boundary offsets, process durations and
cleaning duration. Every constant is divided exactly by that quantum. A second
override can yield second ticks; a microsecond offset can yield microsecond ticks.
No date/duration is rounded. Difference constraints have integral boundaries on
this lattice, so earliest feasible times and maximum minimum slack have lattice
representatives. Hints off this lattice are ignored rather than rounded.

Preserve `scenario.hours` duration interpretation, including its whole-microsecond
requirement. Reject scaled horizons/durations above **2^50 ticks**, at most **200
orders**, **32 machines**, **2000 availability windows**. These conservative
implementation limits avoid unsafe integer expressions and unbounded model size;
unsupported input is an explicit error, not an infeasibility claim. Python's own
datetime/timedelta bounds also apply. No time zone conversion is performed.

## Assignment, cleaning and calendars

For each order i: cleaning start S_i >= release, process start P_i, completion E_i
<= effective deadline, wash boolean C_i, exact duration D_i and cleaning duration W:

`P_i = S_i + W*C_i`, `E_i = P_i + D_i`.

Exactly one compatible, capacity-sufficient machine is selected. Closed machines
offer no alternatives. No split, quantity change, merge or duration reduction is
possible. Optional full-block intervals `[S_i,E_i)` use no-overlap constraints.
One selected availability window must contain both cleaning and processing.

Each machine has one circuit through dummy node 0 and all selected orders.
Unselected nodes self-loop. A dummy self-loop identifies an unused machine. Arc
0->i determines initial cleaning from the configured initial state. Arc i->j
requires `S_j >= E_i` and sets `C_j=0` **only** for an activated exact directed
permission on this machine. Otherwise `C_j=1`. A nonadjacent permission has no
effect. Positive processing duration and circuit ordering establish chronological
adjacency; categories/colour names do not grant exemptions.

Arc i->0 identifies the last order. If terminal cleaning is enabled it occupies
`[E_i,E_i+W)` immediately and must fit one availability window; each used machine
contributes one terminal event. Unused machines contribute none. Terminal fitting
is checked separately from process-window fitting, matching the verifier even for
adjacent calendar windows. Initial and terminal events count even if their
configured time/resource coefficient is zero.

## Two bounded stages and evidence

Stage A minimises `sum(C_i) + terminal_enabled*used_machine_count`. Resource
coefficients do not change: sequence-independent process terms remain constant,
and the existing evaluator calculates the secondary modelled resource score.

After independent verification of Stage A, Stage B fixes that cleaning count and
maximises `min_i(deadline_i-E_i)`. It does not optimise median slack, total slack,
makespan or factory profit. If Stage A is merely FEASIBLE, Stage B is conditional
on that incumbent count, not globally optimal cleaning. Stage-A OPTIMAL proves
only the encoded cleaning objective. Stage-B OPTIMAL proves maximum minimum slack
at the fixed count. Both are required for lexicographic optimality of this model.

Default total budget is **10 seconds**, configurable up to **60**. Model build and
verification time reduce the remaining budget. Stage A receives at most 60% of
the remaining time; Stage B receives what remains after actual Stage-A execution.
One worker, seed **20261015**, relative and absolute gap limits **zero**. Small
wall-clock overhead beyond the solve limit is measured/reported; this is not a
hard real-time kill mechanism. Fixed workers/seed reduce variation, but wall-time
limits and host speed can change feasible incumbents and ties.

Results report per-stage status, integer objective, bound, budget, time and
verification errors; time bounds use the reported tick quantum. Stage A bounds
are lower bounds on cleaning; Stage B bounds are upper bounds on minimum slack.
UNKNOWN/NOT_RUN/MODEL_INVALID never mean infeasible. Only solver INFEASIBLE proves
infeasibility for the encoded constraints. A failed/invalid Stage B retains the
verified Stage-A schedule. Invalid translation is rejected before recommendation.

A fresh verified legacy schedule may supply assignment/time hints and a safe
feasible cleaning upper bound. This does not require EDD success: no incumbent is
needed. An invalid/off-grid hint is ignored. A heuristic fallback is outside the
solver result, requires explicit selection/permission, and has origin
`heuristic_fallback_not_cp_sat`, never CP-SAT success.

## Integration boundary

The immutable AMD/manual apply/reset path still creates the effective case. The
selected-backend screen reruns/revalidates against that exact case after a change;
it cannot display the temporary legacy construction as CP-SAT. Caches/exports bind
source/scenario and effective orders/configuration plus engine/budget/fallback
settings. Failed current solves retain separately labelled previous artifacts.

The existing comparison explanation/review contract assumes verified EDD and a
non-worse legacy proposal. It cannot safely represent EDD failure or arbitrary
CP-SAT incumbents. **CP-SAT schedule explanations and supervisor-review actions
are therefore disabled explicitly**, rather than relabelling solver output.
Recorded-order/daily explanations and AMD constraint interpretation remain intact.
The explicit legacy engine retains its original explanation/review path. CP-SAT
exports include exact schedule, assumptions, override/request history and receipts,
fingerprints, solver evidence, verification and a further-review-only status.
No credentials, machine actuation or real-factory approval are exported.
