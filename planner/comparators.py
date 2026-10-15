"""Versioned read-only comparators; the existing optimiser remains unchanged."""

from dataclasses import asdict, dataclass
from decimal import Decimal
from statistics import median
from time import perf_counter

from planner.comparison import compare_schedules, deadline_performance
from planner.evaluator import evaluate_resources
from planner.scenario import validate_case
from planner.search import build_schedule, plan
from planner.verifier import verify_schedule
from planner.change_requests import digest

VERSION = "scheduling-comparators-v1"
METHODS = {
    "edd": "Deadline ascending, numeric source-row ID tie; existing append-only placement builder.",
    "grouping": "Recorded vessel, fabric, exact shade category (lexicographic labels), deadline, numeric source-row ID. No colour-depth ordering or new exemptions.",
    "optimiser": "Unchanged planner.search.plan: EDD, two grouped priorities and up to three pairwise-swap passes; stops if EDD construction fails.",
}


@dataclass(frozen=True)
class ComparisonRun:
    original_plan: object
    report: dict


def grouping_priority(orders):
    return tuple(sorted(orders, key=lambda o: (o.vessel, o.fabric, o.shade, o.deadline, int(o.order_id))))


def summarise(method, orders, config, schedule, failures, elapsed):
    check = verify_schedule(orders, config, schedule) if schedule is not None else None
    valid = schedule is not None and not failures and check.valid
    deadlines = deadline_performance(orders, schedule) if schedule is not None else None
    slacks = [r["slack_hours"] for r in deadlines["orders"] if r["slack_hours"] is not None] if deadlines else []
    # Count even partial construction artifacts, but never score/compare them as valid.
    counts = None
    if schedule is not None:
        initial = between = 0
        for machine in config.machines:
            rows = sorted((p for p in schedule.placements if p.virtual_id == machine.virtual_id), key=lambda p: p.cleaning_start)
            initial += sum(p.cleaning_required for p in rows[:1])
            between += sum(p.cleaning_required for p in rows[1:])
        counts = {"initial": initial, "between_orders": between, "terminal": len(schedule.terminal_cleanups),
                  "total": initial + between + len(schedule.terminal_cleanups)}
    resource = evaluate_resources(orders, config, schedule) if valid else None
    if resource is not None and resource.cleaning_events != counts["total"]:
        raise ValueError("Comparator cleaning accounting does not reconcile.")
    return {"method": method, "definition": METHODS[method],
        "construction_status": "complete" if schedule is not None and not failures else "failed" if schedule is not None else "not_constructed",
        "construction_errors": list(failures), "verification_status": "passed" if check and check.valid else "failed" if check else "not_available",
        "verification_errors": list(check.errors) if check else [], "eligible_for_comparison": bool(valid),
        "runtime_seconds": elapsed, "cleaning_counts": counts,
        "deadline_performance": deadlines, "slack_hours": {"minimum": min(slacks) if slacks else None,
            "median": median(slacks) if slacks else None, "completed_orders": len(slacks)},
        "resource": {**asdict(resource), "total": resource.total, "unit": config.resource_unit} if resource else None,
        "schedule": asdict(schedule) if schedule else None}


def compare_methods(orders, config):
    """All three methods receive exactly the same effective orders and constraints.

    Wall times include construction/search and fresh verification/accounting. The
    optimiser also includes its internal EDD/candidate checks; no time is subtracted.
    No invalid or failed comparator is substituted with another method.
    """
    validate_case(orders, config)
    rows, schedules = {}, {}
    for method, priority in (("edd", tuple(sorted(orders, key=lambda o: (o.deadline, int(o.order_id))))),
                             ("grouping", grouping_priority(orders))):
        started = perf_counter()
        schedule, failures = build_schedule(priority, config)
        rows[method] = summarise(method, orders, config, schedule, failures, 0)
        rows[method]["runtime_seconds"] = perf_counter() - started
        schedules[method] = schedule
    started = perf_counter()
    original = plan(orders, config)
    rows["optimiser"] = summarise("optimiser", orders, config, original.proposal, original.construction_errors, 0)
    rows["optimiser"]["runtime_seconds"] = perf_counter() - started
    schedules["optimiser"] = original.proposal
    differences = {}
    for method in ("edd", "grouping"):
        eligible = rows[method]["eligible_for_comparison"] and rows["optimiser"]["eligible_for_comparison"]
        changes = compare_schedules(orders, config, schedules[method], schedules["optimiser"]) if eligible else None
        differences[method] = {"eligible": eligible,
            "reason": None if eligible else "Both methods must construct complete independently verified schedules; no substitution.",
            "cleaning_events_difference": changes["reconciliation"]["cleaning_events_difference"] if changes else None,
            "resource_difference": changes["difference"] if changes else None,
            "percentage_difference": changes["percentage_difference"] if changes else None,
            "sign": "comparator minus optimiser; negative means comparator used fewer events/resources",
            "transition_comparison": changes}
    return ComparisonRun(original, {"version": VERSION, "effective_case_fingerprint": digest({"orders": orders, "config": config}),
        "order_count": len(orders), "methods": rows, "optimiser_against": differences,
        "scope": "Heuristic comparators under illustrative assumptions, not real factory planners. Resource scores are secondary, in unresolved modelled source units."})
