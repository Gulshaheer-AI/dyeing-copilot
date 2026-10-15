"""Read-only comparison accounting; never changes schedules or scenario rules."""

from dataclasses import asdict
from decimal import Decimal

from planner.evaluator import evaluate_resources
from planner.verifier import verify_schedule

RULE_LABELS = {"initial_dirty": "configured dirty initial state",
    "configured_initially_clean": "configured clean initial state", "exemptions_disabled": "exemptions disabled",
    "no_exact_permission": "no activated exact directed permission", "activated_exact_permission": "activated exact directed permission",
    "configured_terminal_cleanup": "configured final cleanup", "terminal_cleanup_disabled": "final cleanup disabled",
    "unused_machine": "unused machine"}


def deadline_performance(orders, schedule):
    """Compare process completion with scenario deadlines, not actual deliveries."""
    placements = {p.order_id: p for p in schedule.placements}
    rows = []
    for order in sorted(orders, key=lambda o: int(o.order_id)):
        placement = placements.get(order.order_id)
        end = placement.process_end if placement else None
        delta = order.deadline - end if end else None
        slack = ((Decimal(delta.days * 86400 + delta.seconds) + Decimal(delta.microseconds) / 1_000_000) / 3600) if delta is not None else None
        rows.append({"order_id": order.order_id, "deadline": order.deadline,
                     "completion": end, "slack_hours": slack,
                     "status": "missing" if end is None else "on_time" if end <= order.deadline else "late"})
    return {"on_time": sum(r["status"] == "on_time" for r in rows),
            "late": sum(r["status"] == "late" for r in rows),
            "missing": sum(r["status"] == "missing" for r in rows), "orders": rows}


def _transitions(schedule, config):
    snapshots, terminals, sequences = {}, {}, {}
    permissions = {(p.virtual_id, p.from_order_id, p.to_order_id) for p in config.transition_permissions}
    for machine in config.machines:
        entries = sorted((p for p in schedule.placements if p.virtual_id == machine.virtual_id),
                         key=lambda p: (p.cleaning_start, p.process_start, int(p.order_id)))
        sequences[machine.virtual_id] = [p.order_id for p in entries]
        previous = None
        for position, p in enumerate(entries, 1):
            if previous is None:
                reason = "initial_dirty" if p.cleaning_required else "configured_initially_clean"
            elif p.cleaning_required:
                reason = "exemptions_disabled" if not config.allow_cleaning_exemptions else "no_exact_permission"
            elif (machine.virtual_id, previous.order_id, p.order_id) in permissions:
                reason = "activated_exact_permission"
            else:
                raise ValueError("Unexplained exemption; comparison rejected.")
            snapshots[p.order_id] = {"machine": machine.virtual_id, "position": position,
                "predecessor": previous.order_id if previous else None,
                "cleaning_required": p.cleaning_required, "rule": reason,
                "cleaning_start": p.cleaning_start, "process_start": p.process_start, "completion": p.process_end}
            previous = p
        terminals[machine.virtual_id] = {"predecessor": previous.order_id if previous else None,
            "cleaning_required": bool(entries and config.terminal_cleaning),
            "rule": "configured_terminal_cleanup" if entries and config.terminal_cleaning else
                    "terminal_cleanup_disabled" if entries else "unused_machine"}
    return snapshots, terminals, sequences


def compare_schedules(orders, config, baseline, proposal):
    checks = [verify_schedule(orders, config, schedule) for schedule in (baseline, proposal)]
    if not all(check.valid for check in checks):
        raise ValueError("Comparison rejected: both schedules must pass independent verification.")
    resources = [evaluate_resources(orders, config, schedule) for schedule in (baseline, proposal)]
    before, before_terminal, before_sequences = _transitions(baseline, config)
    after, after_terminal, after_sequences = _transitions(proposal, config)
    rows = []
    for order in sorted(orders, key=lambda o: int(o.order_id)):
        a, b = before[order.order_id], after[order.order_id]
        difference = int(a["cleaning_required"]) - int(b["cleaning_required"])
        rows.append({"order_id": order.order_id, "quantity": order.quantity, "baseline": a, "proposal": b,
            "machine_changed": a["machine"] != b["machine"], "position_changed": a["position"] != b["position"],
            "predecessor_changed": (a["machine"], a["predecessor"]) != (b["machine"], b["predecessor"]),
            "timing_changed": any(a[k] != b[k] for k in ("cleaning_start", "process_start", "completion")),
            "transition_changed": any(a[k] != b[k] for k in ("machine", "position", "predecessor", "cleaning_required")),
            "cleaning_events_difference": difference, "resource_difference": difference * config.cleaning_water})
    terminal_rows = [{"machine": m.virtual_id, "baseline": before_terminal[m.virtual_id],
        "proposal": after_terminal[m.virtual_id], "cleaning_events_difference":
        int(before_terminal[m.virtual_id]["cleaning_required"]) - int(after_terminal[m.virtual_id]["cleaning_required"])}
        for m in config.machines]
    for row in terminal_rows:
        row["resource_difference"] = row["cleaning_events_difference"] * config.cleaning_water
    accounting = {}
    for label, snapshots, terminal, use in zip(("baseline", "proposal"), (before, after),
                                              (before_terminal, after_terminal), resources):
        initial = sum(s["predecessor"] is None and s["cleaning_required"] for s in snapshots.values())
        between = sum(s["predecessor"] is not None and s["cleaning_required"] for s in snapshots.values())
        final = sum(s["cleaning_required"] for s in terminal.values())
        if (initial + between + final != use.cleaning_events
                or (initial + between) * config.cleaning_water != use.cleaning_before_orders
                or final * config.cleaning_water != use.terminal_cleaning):
            raise ValueError("Cleaning-event accounting failed to reconcile.")
        accounting[label] = {"initial": initial, "between_orders": between, "terminal": final,
                             "total": initial + between + final}
    total_difference = resources[0].total - resources[1].total
    event_difference = sum(r["cleaning_events_difference"] for r in rows + terminal_rows)
    transition_difference = sum((r["resource_difference"] for r in rows + terminal_rows), Decimal(0))
    process_difference = (resources[0].process_a + resources[0].process_b
                          - resources[1].process_a - resources[1].process_b)
    if (event_difference != resources[0].cleaning_events - resources[1].cleaning_events
            or transition_difference + process_difference != total_difference):
        raise ValueError("Transition differences failed to reconcile with resource totals.")
    return {"comparison_version": "planner-review-v1", "unit": config.resource_unit,
        "resources": {label: {**asdict(use), "total": use.total}
                      for label, use in zip(("baseline", "proposal"), resources)},
        "difference": total_difference,
        "percentage_difference": total_difference * 100 / resources[0].total if resources[0].total else None,
        "difference_sign": "baseline minus proposal; positive means less scenario demand",
        "cleaning_counts": accounting, "deadlines": {"baseline": deadline_performance(orders, baseline),
                                                       "proposal": deadline_performance(orders, proposal)},
        "changes": {"machine_assignments": sum(r["machine_changed"] for r in rows),
                    "sequence_positions": sum(r["position_changed"] for r in rows),
                    "predecessors": sum(r["predecessor_changed"] for r in rows),
                    "cleaning_requirements": sum(r["cleaning_events_difference"] != 0 for r in rows),
                    "timings": sum(r["timing_changed"] for r in rows)},
        "machine_sequences": {"baseline": before_sequences, "proposal": after_sequences},
        "order_transitions": rows, "terminal_transitions": terminal_rows,
        "reconciliation": {"passed": True, "cleaning_events_difference": event_difference,
                           "transition_resource_difference": transition_difference,
                           "process_resource_difference": process_difference, "total_difference": total_difference},
        "verification": {"baseline_valid": checks[0].valid, "proposal_valid": checks[1].valid}}
