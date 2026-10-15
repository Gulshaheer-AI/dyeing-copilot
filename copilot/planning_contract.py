"""Small AMD wire contract. Source spans are generated and reconstructed by Python."""

from typing import Annotated, Literal
from pydantic import Field
from copilot.planning_schema import Strict, InterpretationResponse
from copilot.planning_guard import REF


class WireDeadline(Strict):
    operation: Literal["order_deadline"]
    order_id: str
    deadline: str
    clause_id: str


class WireOutage(Strict):
    operation: Literal["machine_unavailability"]
    machine_id: str
    start: str
    end: str
    clause_id: str


class WireReason(Strict):
    clause_id: str
    reason: str = Field(min_length=1, max_length=500)


class WireResponse(Strict):
    status: Literal["ready", "clarification", "unsupported"]
    changes: list[Annotated[WireDeadline | WireOutage, Field(discriminator="operation")]] = Field(max_length=10)
    clarification_questions: list[str] = Field(max_length=10)
    unsupported_reasons: list[WireReason] = Field(max_length=10)


def source_spans(request):
    # Segmentation only; the model receives no locally generated ready operations.
    starts = [m.start() for m in REF.finditer(request.text)]
    boundaries = sorted(set([0, *starts, len(request.text)]))
    return [{"clause_id": f"c{i}", "start": a, "end": b, "text": request.text[a:b]}
            for i, (a, b) in enumerate(zip(boundaries, boundaries[1:])) if request.text[a:b].strip()]


def reconstruct(content, request):
    wire = WireResponse.model_validate_json(content)
    spans = {s["clause_id"]: s["text"] for s in source_spans(request)}
    def expand(item):
        data = item.model_dump()
        clause_id = data.pop("clause_id")
        if clause_id not in spans:
            raise ValueError("Unknown source clause reference; no changes applied.")
        return {**data, "supporting_excerpt": spans[clause_id]}
    # Existing strict exclusivity, literal references, dates, negation and clause/value
    # association checks run on the reconstructed response, including at application.
    return InterpretationResponse.model_validate({"status": wire.status,
        "changes": [expand(c) for c in wire.changes],
        "clarification_questions": wire.clarification_questions,
        "unsupported_reasons": [expand(r) for r in wire.unsupported_reasons]})


EXAMPLES = [
    {"text": "order 12 deadline 2019-12-22 18:00", "changes": [
        {"operation": "order_deadline", "order_id": "12", "deadline": "2019-12-22T18:00", "clause_id": "c0"}]},
    {"text": "virtual-Pressure-PolyCotton outage from 2019-12-20T08:00:30 to 2019-12-20T16:00:45", "changes": [
        {"operation": "machine_unavailability", "machine_id": "virtual-Pressure-PolyCotton",
         "start": "2019-12-20T08:00:30", "end": "2019-12-20T16:00:45", "clause_id": "c0"}]},
    {"text": "order 11 deadline 2019-12-23T18:00; order 13 deadline 2019-12-24T16:00", "changes": [
        {"operation": "order_deadline", "order_id": "11", "deadline": "2019-12-23T18:00", "clause_id": "c0"},
        {"operation": "order_deadline", "order_id": "13", "deadline": "2019-12-24T16:00", "clause_id": "c1"}]},
]
