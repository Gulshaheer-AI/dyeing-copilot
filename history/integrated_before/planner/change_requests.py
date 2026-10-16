"""Immutable scenario overlays and atomic, explicit application of validated requests."""

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone

from copilot.planning_schema import Outage, explicit_datetime, validate_interpretation
from planner.scenario import Window, orders_from_import, to_json
from planner.search import plan


def digest(value):
    return hashlib.sha256(json.dumps(json.loads(to_json(value)), sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class DeadlineOverride:
    order_id: str
    deadline: datetime
    previous_deadline: datetime
    request_fingerprint: str
    supporting_excerpt: str


@dataclass(frozen=True)
class PlanningCase:
    source_sha256: str
    source_filename: str
    original_orders: tuple
    original_config: object
    config: object
    overrides: tuple = ()
    history: tuple = ()
    revision: int = 0

    @property
    def orders(self):
        overrides = {o.order_id: o.deadline for o in self.overrides}
        return tuple(replace(o, deadline=overrides.get(o.order_id, o.deadline)) for o in self.original_orders)

    @property
    def fingerprint(self):
        return digest(self)


def initial_case(result, config):
    return PlanningCase(result.sha256, result.filename, orders_from_import(result), config, config)


def subtract_interval(windows, start, end):
    """Half-open outage [start,end); disjoint/overlapping exclusions compose exactly."""
    if start >= end:
        raise ValueError("Outage start must precede end.")
    remaining = []
    for window in windows:
        if end <= window.start or start >= window.end:
            remaining.append(window)
        else:
            if window.start < start:
                remaining.append(Window(window.start, start))
            if end < window.end:
                remaining.append(Window(end, window.end))
    return tuple(remaining)


def apply_changes(case, interpretation):
    if interpretation.request.scenario_fingerprint != case.fingerprint or interpretation.request.source_sha256 != case.source_sha256:
        raise ValueError("Stale proposal: source/scenario fingerprint changed. Interpret the request again.")
    from copilot.planning_interpreter import make_request
    if interpretation.request != make_request(case, interpretation.request.text):
        raise ValueError("Proposal context does not match the effective case.")
    response = validate_interpretation(interpretation.response, interpretation.request)
    if response.status != "ready":
        raise ValueError("Only a fully validated ready proposal can be applied.")
    machines = {m.virtual_id: m for m in case.config.machines}
    deadlines = {o.order_id: o.deadline for o in case.orders}
    overrides = list(case.overrides)
    request_id = digest(interpretation.request.model_dump())
    # Local immutable copies only; no caller state is committed until all operations succeed.
    for change in response.changes:
        if isinstance(change, Outage):
            machine = machines[change.machine_id]
            machines[change.machine_id] = replace(machine, availability=subtract_interval(machine.availability,
                explicit_datetime(change.start), explicit_datetime(change.end)))
        else:
            overrides.append(DeadlineOverride(change.order_id, explicit_datetime(change.deadline),
                deadlines[change.order_id], request_id, change.supporting_excerpt))
    config = replace(case.config, machines=tuple(machines[m.virtual_id] for m in case.config.machines))
    history = {"action": "applied_changes", "applied_at_utc": datetime.now(timezone.utc).isoformat(),
        "original_request": interpretation.request.text, "request": interpretation.request.model_dump(),
        "proposal": response.model_dump(), "receipt": interpretation.receipt,
        "before_fingerprint": case.fingerprint, "request_fingerprint": request_id}
    updated = replace(case, config=config, overrides=tuple(overrides), history=case.history + (history,), revision=case.revision + 1)
    # Exercise all effective Order constructors before committing anything.
    updated.orders
    return updated


def preview_changes(case, interpretation):
    updated = apply_changes(case, interpretation)
    preview = []
    for before, after in zip(case.config.machines, updated.config.machines):
        if before.availability != after.availability:
            preview.append({"constraint": "machine availability", "id": before.virtual_id,
                "before": [{"start": str(w.start), "end": str(w.end)} for w in before.availability],
                "after": [{"start": str(w.start), "end": str(w.end)} for w in after.availability]})
    for before, after in zip(case.orders, updated.orders):
        if before.deadline != after.deadline:
            preview.append({"constraint": "completion deadline", "id": before.order_id,
                            "before": str(before.deadline), "after": str(after.deadline)})
    return preview


def apply_and_reschedule(case, interpretation):
    updated = apply_changes(case, interpretation)
    return updated, plan(updated.orders, updated.config)


def reset_case(case):
    return replace(case, config=case.original_config, overrides=(), revision=case.revision + 1,
        history=case.history + ({"action": "reset_to_original", "before_fingerprint": case.fingerprint,
                                "applied_at_utc": datetime.now(timezone.utc).isoformat()},))


def effective_orders(result, config, case=None):
    original = orders_from_import(result)
    if case is None:
        return original
    if (case.source_sha256 != result.sha256 or case.source_filename != result.filename
            or case.original_orders != original or case.config != config):
        raise ValueError("Effective planning case does not match this source/configuration.")
    return case.orders
