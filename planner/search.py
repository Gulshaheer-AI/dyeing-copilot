"""Deterministic EDD baseline, category grouping and bounded pairwise local search."""

from dataclasses import dataclass

from planner.contracts import Placement, Schedule, TerminalCleanup, Verification
from planner.evaluator import ResourceUse, evaluate_resources
from planner.scenario import hours, validate_case
from planner.verifier import verify_schedule


def build_schedule(priority, config):
    """Append whole orders to the earliest-finishing permitted virtual machine.

    Processing and pre-cleaning are nonpreemptive within one availability window.
    Space for immediate final cleanup is reserved after every tentative last order.
    Failure is a construction failure, not a proof of global infeasibility.
    """
    placements, problems = [], []
    last = {}
    permissions = {(p.virtual_id, p.from_order_id, p.to_order_id) for p in config.transition_permissions}
    for order in priority:
        choices = []
        compatible = [m for m in config.machines if (order.vessel, order.fabric) in m.compatible_pairs]
        capable = [m for m in compatible if order.quantity <= m.capacity]
        if not capable:
            reason = "over capacity: scenario infeasible without prohibited splitting" if compatible else "no compatible virtual machine"
            problems.append(f"Order {order.order_id}: {reason}.")
            continue
        for machine in capable:
            prev = last.get(machine.virtual_id)
            clean = (not machine.initially_clean) if prev is None else not (
                config.allow_cleaning_exemptions and
                (machine.virtual_id, prev.order_id, order.order_id) in permissions
            )
            cleaning = hours(config.cleaning_hours) if clean else hours(0)
            processing = hours(order.duration_source * config.hours_per_duration_unit)
            reserve = hours(config.cleaning_hours) if config.terminal_cleaning else hours(0)
            earliest = max(order.release, prev.process_end) if prev else order.release
            for window in machine.availability:
                setup = max(earliest, window.start)
                start, end = setup + cleaning, setup + cleaning + processing
                if end <= order.deadline and end + reserve <= window.end:
                    choices.append(Placement(order.order_id, order.quantity, machine.virtual_id,
                                             setup, start, end, clean))
                    break
        if not choices:
            problems.append(f"Order {order.order_id}: no deadline/availability slot in this construction.")
            continue
        chosen = min(choices, key=lambda p: (p.process_end, p.virtual_id))
        placements.append(chosen)
        last[chosen.virtual_id] = chosen
    terminal = tuple(TerminalCleanup(virtual_id, p.process_end, p.process_end + hours(config.cleaning_hours))
                     for virtual_id, p in sorted(last.items())) if config.terminal_cleaning else ()
    return Schedule(tuple(placements), terminal), tuple(problems)


@dataclass(frozen=True)
class PlanResult:
    baseline: Schedule
    proposal: Schedule | None
    baseline_verification: Verification
    proposal_verification: Verification | None
    baseline_resources: ResourceUse | None
    proposal_resources: ResourceUse | None
    construction_errors: tuple[str, ...]
    candidates_checked: int

    @property
    def improvement(self):
        if self.baseline_resources is None or self.proposal_resources is None:
            return None
        return self.baseline_resources.total - self.proposal_resources.total


def plan(orders, config, *, max_passes=3):
    validate_case(orders, config)
    if not 0 <= max_passes <= 10:
        raise ValueError("Use 0–10 bounded local-search passes.")
    priority = tuple(sorted(orders, key=lambda o: (o.deadline, int(o.order_id))))
    baseline, problems = build_schedule(priority, config)
    baseline_check = verify_schedule(orders, config, baseline)
    if problems or not baseline_check.valid:
        return PlanResult(baseline, None, baseline_check, None, None, None, problems, 0)
    baseline_resource = evaluate_resources(orders, config, baseline)
    best_priority, best, best_use = priority, baseline, baseline_resource
    checked = 0

    def candidate(items):
        nonlocal checked
        checked += 1
        schedule, failures = build_schedule(items, config)
        if failures or not verify_schedule(orders, config, schedule).valid:
            return None
        return schedule, evaluate_resources(orders, config, schedule)

    # Grouping only suggests a priority; all assignments and exemptions remain checked.
    for key in (
        lambda o: (o.deadline, o.vessel, o.fabric, o.shade, int(o.order_id)),
        lambda o: (o.vessel, o.fabric, o.shade, o.deadline, int(o.order_id)),
    ):
        items = tuple(sorted(orders, key=key))
        outcome = candidate(items)
        if outcome and outcome[1].total < best_use.total:
            best_priority, (best, best_use) = items, outcome
    for _ in range(max_passes):
        improved = None
        for i in range(len(best_priority)):
            for j in range(i + 1, len(best_priority)):
                items = list(best_priority)
                items[i], items[j] = items[j], items[i]
                outcome = candidate(tuple(items))
                threshold = improved[2].total if improved else best_use.total
                if outcome and outcome[1].total < threshold:
                    improved = (tuple(items), *outcome)
        if improved is None:
            break
        best_priority, best, best_use = improved
    final_check = verify_schedule(orders, config, best)
    if not final_check.valid:
        # Defensive fallback: an invalid candidate must never become a recommendation.
        best, best_use, final_check = baseline, baseline_resource, baseline_check
    return PlanResult(baseline, best, baseline_check, final_check, baseline_resource, best_use, (), checked)
