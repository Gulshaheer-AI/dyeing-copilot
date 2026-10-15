"""Explicit form values, not local natural-language interpretation or AMD inference."""

from datetime import datetime, timezone
from copilot.planning_interpreter import make_request
from copilot.planning_schema import Interpretation, InterpretationResponse, validate_interpretation


def manual_proposal(case, *, operation, identifier, deadline=None, start=None, end=None):
    def iso(value):
        if not isinstance(value, datetime) or value.tzinfo is not None or value.microsecond:
            raise ValueError("Use explicit scenario-local datetime controls (minute or second precision).")
        return value.isoformat()
    if operation == "order_deadline":
        change = {"operation": operation, "order_id": identifier, "deadline": iso(deadline)}
        text = f"order {identifier} deadline {change['deadline']}"
    elif operation == "machine_unavailability":
        change = {"operation": operation, "machine_id": identifier, "start": iso(start), "end": iso(end)}
        text = f"{identifier} outage from {change['start']} to {change['end']}"
    else:
        raise ValueError("Unsupported manual operation.")
    request = make_request(case, text)
    response = InterpretationResponse.model_validate({"status": "ready", "changes": [{**change, "supporting_excerpt": text}],
        "clarification_questions": [], "unsupported_reasons": []})
    response = validate_interpretation(response, request)
    return Interpretation(request, response, {"origin": "manual", "actual_model": None,
        "api_request_performed": False, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "validation": "passed", "purpose": "structured_manual_constraint_entry", "interpreter_version": "8.2"})
