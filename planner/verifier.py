"""Independent verification: does not call the planner or its placement helper."""

from collections import Counter

from planner.contracts import Verification
from planner.scenario import hours, validate_case


def verify_schedule(orders, config, schedule):
    errors = []
    try:
        validate_case(orders, config)
    except (ValueError, OverflowError) as exc:
        return Verification((f"Invalid scenario/case: {exc}",))
    expected = {o.order_id: o for o in orders}
    machines = {m.virtual_id: m for m in config.machines}
    counts = Counter(p.order_id for p in schedule.placements)
    for order_id in expected:
        if counts[order_id] != 1:
            errors.append(f"Order {order_id}: must appear exactly once; found {counts[order_id]}.")
    for order_id in counts.keys() - expected.keys():
        errors.append(f"Unknown order {order_id}.")
    permitted = {(p.virtual_id, p.from_order_id, p.to_order_id) for p in config.transition_permissions}
    for p in schedule.placements:
        if p.virtual_id not in machines:
            errors.append(f"Order {p.order_id}: unknown virtual machine {p.virtual_id}.")
    for machine in config.machines:
        entries = sorted((p for p in schedule.placements if p.virtual_id == machine.virtual_id),
                         key=lambda p: (p.cleaning_start, p.process_start, p.order_id))
        previous = None
        previous_end = None
        for p in entries:
            order = expected.get(p.order_id)
            if order is None:
                continue
            prefix = f"Order {p.order_id} on {machine.virtual_id}: "
            if p.quantity != order.quantity:
                errors.append(prefix + "quantity changed.")
            if (order.vessel, order.fabric) not in machine.compatible_pairs:
                errors.append(prefix + "incompatible vessel/fabric assignment.")
            if order.quantity > machine.capacity:
                errors.append(prefix + "over capacity; splitting is prohibited.")
            required = not machine.initially_clean if previous is None else not (
                config.allow_cleaning_exemptions and (machine.virtual_id, previous, p.order_id) in permitted
            )
            if type(p.cleaning_required) is not bool or p.cleaning_required != required:
                errors.append(prefix + "cleaning transition is unauthorised or inconsistent with policy.")
            if p.process_start - p.cleaning_start != (hours(config.cleaning_hours) if required else hours(0)):
                errors.append(prefix + "incorrect cleaning duration.")
            if p.process_end - p.process_start != hours(order.duration_source * config.hours_per_duration_unit):
                errors.append(prefix + "incorrect processing duration.")
            if p.cleaning_start > p.process_start or p.process_start >= p.process_end:
                errors.append(prefix + "invalid timing order.")
            if p.cleaning_start < order.release:
                errors.append(prefix + "starts before release.")
            if p.process_end > order.deadline:
                errors.append(prefix + "delivery deadline missed.")
            if previous_end is not None and p.cleaning_start < previous_end:
                errors.append(prefix + "overlap on virtual machine.")
            if not any(w.start <= p.cleaning_start and p.process_end <= w.end for w in machine.availability):
                errors.append(prefix + "outside operating availability.")
            previous, previous_end = p.order_id, p.process_end
        endings = [t for t in schedule.terminal_cleanups if t.virtual_id == machine.virtual_id]
        expected_endings = 1 if entries and config.terminal_cleaning else 0
        if len(endings) != expected_endings:
            errors.append(f"{machine.virtual_id}: expected {expected_endings} terminal cleaning events, found {len(endings)}.")
        for t in endings:
            if not entries or t.start != entries[-1].process_end or t.end - t.start != hours(config.cleaning_hours):
                errors.append(f"{machine.virtual_id}: invalid terminal cleaning timing.")
            if not any(w.start <= t.start and t.end <= w.end for w in machine.availability):
                errors.append(f"{machine.virtual_id}: terminal cleaning outside availability.")
    if any(t.virtual_id not in machines for t in schedule.terminal_cleanups):
        errors.append("Terminal cleaning references an unknown virtual machine.")
    return Verification(tuple(errors))
