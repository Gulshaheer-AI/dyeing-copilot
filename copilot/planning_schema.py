"""Strict, non-executable interpretation contract, separate from explanations."""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ISO = r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?"


def explicit_datetime(value):
    if not isinstance(value, str) or not re.fullmatch(ISO, value):
        raise ValueError("Use an explicit YYYY-MM-DD HH:MM[:SS] scenario-local datetime; no relative dates or timezone conversion.")
    return datetime.fromisoformat(value)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class KnownOrder(Strict):
    order_id: str
    release: str
    deadline: str


class KnownMachine(Strict):
    machine_id: str
    availability: list[dict[str, str]]


class InterpretationRequest(Strict):
    interpreter_version: Literal["8.2"] = "8.2"
    text: str = Field(min_length=1, max_length=4000)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scenario_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    timezone: Literal["Asia/Karachi scenario local time"] = "Asia/Karachi scenario local time"
    orders: list[KnownOrder]
    machines: list[KnownMachine]
    permitted_operations: list[Literal["machine_unavailability", "order_deadline"]] = ["machine_unavailability", "order_deadline"]


class Outage(Strict):
    operation: Literal["machine_unavailability"]
    machine_id: str
    start: str
    end: str
    supporting_excerpt: str = Field(min_length=1, max_length=4000)

    @field_validator("start", "end")
    @classmethod
    def dates(cls, value):
        return explicit_datetime(value).isoformat()


class Deadline(Strict):
    operation: Literal["order_deadline"]
    order_id: str
    deadline: str
    supporting_excerpt: str = Field(min_length=1, max_length=4000)

    @field_validator("deadline")
    @classmethod
    def dates(cls, value):
        return explicit_datetime(value).isoformat()


class UnsupportedReason(Strict):
    supporting_excerpt: str = Field(min_length=1, max_length=4000)
    reason: str = Field(min_length=1, max_length=500)


class InterpretationResponse(Strict):
    status: Literal["ready", "clarification", "unsupported"]
    changes: list[Annotated[Outage | Deadline, Field(discriminator="operation")]] = Field(max_length=10)
    clarification_questions: list[str] = Field(max_length=10)
    unsupported_reasons: list[UnsupportedReason] = Field(max_length=10)

    @model_validator(mode="after")
    def exclusive(self):
        if self.status == "ready" and (not self.changes or self.clarification_questions or self.unsupported_reasons):
            raise ValueError("Ready requires changes only.")
        if self.status == "clarification" and (self.changes or not self.clarification_questions or self.unsupported_reasons):
            raise ValueError("Clarification requires questions and no changes.")
        if self.status == "unsupported" and (self.changes or not self.unsupported_reasons or self.clarification_questions):
            raise ValueError("Unsupported requires reasons and no changes.")
        if any(not q.strip() or len(q) > 500 for q in self.clarification_questions):
            raise ValueError("Clarification questions must be nonempty and bounded.")
        return self


@dataclass(frozen=True)
class Interpretation:
    request: InterpretationRequest
    response: InterpretationResponse
    receipt: dict


def exact_reference(identifier, text):
    return bool(re.search(r"(?<![\w-])" + re.escape(identifier) + r"(?![\w-])", text))


def validate_interpretation(response, request):
    # Revalidate even typed instances at the application boundary.
    response = InterpretationResponse.model_validate_json(response.model_dump_json())
    text = request.text
    for reason in response.unsupported_reasons:
        if reason.supporting_excerpt not in text:
            raise ValueError("Unsupported reason must quote the original request.")
    if response.status != "ready":
        return response
    from copilot.planning_guard import local_decision, validate_associations
    decision = local_decision(request)
    if decision is not None:
        if decision.status == "unsupported":
            raise ValueError("Unsupported request: " + decision.unsupported_reasons[0].reason)
        raise ValueError(decision.clarification_questions[0])
    if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}|\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|today|tomorrow|yesterday)\b", text, re.I):
        raise ValueError("Ambiguous/relative dates require clarification; use absolute historical ISO datetimes.")
    if re.search(ISO + r"(?:Z|[+-]\d{2}:?\d{2}|[.,]\d)", text):
        raise ValueError("Use explicit scenario-local datetimes without timezone conversion or fractional seconds.")
    # Reject partial acceptance of mixed unsupported/instruction-injection requests.
    machines = {m.machine_id: m for m in request.machines}
    orders = {o.order_id: o for o in request.orders}
    mentioned_machines = set(re.findall(r"\bvirtual-[A-Za-z0-9_-]+", text))
    mentioned_orders = set(re.findall(r"\border\s*#?\s*(\d+)\b", text, re.I))
    if mentioned_machines - set(machines) or mentioned_orders - set(orders):
        raise ValueError("Unknown machine/order reference requires clarification; references are never silently mapped.")
    seen, deadlines, covered_machines, covered_orders, accounted_times = set(), set(), set(), set(), set()
    for change in response.changes:
        excerpt = change.supporting_excerpt
        if excerpt not in text:
            raise ValueError("Every change must quote an exact supporting excerpt.")
        times = {explicit_datetime(token) for token in re.findall(ISO, excerpt)}
        if isinstance(change, Outage):
            if change.machine_id not in machines or not exact_reference(change.machine_id, excerpt):
                raise ValueError("Unknown or unsupported machine reference; do not guess a mapping.")
            start, end = explicit_datetime(change.start), explicit_datetime(change.end)
            if start >= end or start not in times or end not in times:
                raise ValueError("Outage requires ordered, explicit start/end datetimes supported by the text.")
            if not re.search(r"unavailab|outage|offline|\bdown\b|maintenance|out of service", excerpt, re.I):
                raise ValueError("Outage intent is not supported by the excerpt.")
            key = (change.operation, change.machine_id, start, end)
            accounted_times.update((start, end))
            covered_machines.add(change.machine_id)
        else:
            if change.order_id not in orders or not re.search(r"\border\s*#?\s*" + re.escape(change.order_id) + r"\b", excerpt, re.I):
                raise ValueError("Unknown or unsupported order reference; do not guess a mapping.")
            deadline = explicit_datetime(change.deadline)
            if deadline not in times or deadline <= datetime.fromisoformat(orders[change.order_id].release):
                raise ValueError("Completion deadline must be explicit in the text and later than release.")
            if not re.search(r"deadline|complete|completion|finish|\bdue\b|deliver", excerpt, re.I):
                raise ValueError("An urgency label alone is not an explicit deadline.")
            if change.order_id in deadlines:
                raise ValueError("Duplicate/conflicting deadline changes require clarification.")
            deadlines.add(change.order_id)
            accounted_times.add(deadline)
            for previous in re.findall(r"\bfrom\s+(" + ISO + r")", excerpt, re.I):
                if explicit_datetime(previous) == datetime.fromisoformat(orders[change.order_id].deadline):
                    accounted_times.add(explicit_datetime(previous))
            key = (change.operation, change.order_id, deadline)
            covered_orders.add(change.order_id)
        if key in seen:
            raise ValueError("Duplicate changes require clarification; overlapping distinct outages are allowed.")
        seen.add(key)
    if mentioned_machines - covered_machines or mentioned_orders - covered_orders:
        raise ValueError("The proposal omits a referenced constraint; clarify the complete request.")
    if {explicit_datetime(token) for token in re.findall(ISO, text)} - accounted_times:
        raise ValueError("Unaccounted datetime or conflicting constraint requires clarification; no partial application.")
    validate_associations(response, request)
    return response
