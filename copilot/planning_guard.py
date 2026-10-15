"""Deterministic refusal/clarification and narrow clause grounding; never emits ready edits."""

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from copilot.planning_schema import ISO, InterpretationResponse, explicit_datetime

REF = re.compile(r"\border\s*#?\s*(\d+)\b|(?<![\w-])(virtual-[A-Za-z0-9_-]+)", re.I)
PROTECTED = r"cleaning|washing|wash|compatib\w*|capacit\w*|rates?|formulas?|pressure|temperature|chemicals?|recipes?"
OUTAGE = r"unavailab|outage|offline|\bdown\b|maintenance|out of service"
DEADLINE = r"deadline|complete|completion|finish|\bdue\b|deliver"


def instructions_without_known_ids(request):
    text = request.text
    for machine in sorted(request.machines, key=lambda m: len(m.machine_id), reverse=True):
        # Full token boundaries: a known ID is never removed from an unknown extended ID.
        text = re.sub(r"(?<![\w-])" + re.escape(machine.machine_id) + r"(?![\w-])", "[KNOWN_MACHINE_ID]", text)
    return text


class NeedsClarification(ValueError):
    pass


@dataclass(frozen=True)
class Binding:
    operation: str
    identifier: str
    dates: tuple
    core_excerpt: str

    @property
    def key(self):
        return (self.operation, self.identifier, *self.dates)


def bindings(request):
    """Recognize explicit ID-first clauses solely to check association, not interpret edits."""
    orders = {o.order_id: o for o in request.orders}
    refs = list(REF.finditer(request.text))
    if not refs:
        raise NeedsClarification("Name an exact known machine ID or an order ID, and supply explicit ISO datetimes.")
    result = []
    for i, ref in enumerate(refs):
        end = refs[i + 1].start() if i + 1 < len(refs) else len(request.text)
        clause = request.text[ref.start():end]
        tokens = list(re.finditer(ISO, clause))
        try:
            dates = [explicit_datetime(t.group()) for t in tokens]
        except ValueError:
            raise NeedsClarification("A calendar datetime is invalid. Use YYYY-MM-DD HH:MM[:SS].") from None
        if ref.group(1):
            order_id = ref.group(1)
            if not re.search(DEADLINE, clause, re.I) or not dates:
                raise NeedsClarification(f"Give order {order_id} an explicit completion deadline: order {order_id} deadline YYYY-MM-DD HH:MM. Urgency alone is insufficient.")
            if len(dates) == 2 and re.search(r"\bfrom\s+" + ISO + r"\s+to\s+" + ISO, clause, re.I):
                if dates[0] != datetime.fromisoformat(orders[order_id].deadline):
                    raise NeedsClarification(f"The stated original deadline for order {order_id} does not match the scenario; state one new deadline explicitly.")
                deadline = dates[1]
            elif len(dates) == 1:
                deadline = dates[0]
            else:
                raise NeedsClarification(f"Conflicting or ambiguous deadlines for order {order_id}; state one new datetime in its own clause.")
            if deadline <= datetime.fromisoformat(orders[order_id].release):
                raise NeedsClarification(f"Order {order_id}'s completion deadline must be later than its release {orders[order_id].release}.")
            result.append(Binding("order_deadline", order_id, (deadline,), clause[:tokens[-1].end()]))
        else:
            machine = ref.group(2)
            if not re.search(OUTAGE, clause, re.I) or not dates or len(dates) % 2:
                raise NeedsClarification(f"Give {machine} an explicit outage start and end in its own clause: unavailable from YYYY-MM-DD HH:MM to YYYY-MM-DD HH:MM.")
            for j in range(0, len(dates), 2):
                separator = clause[tokens[j].end():tokens[j + 1].start()]
                if not re.fullmatch(r"\s*(?:to|until)\s*", separator, re.I) or dates[j] >= dates[j + 1]:
                    raise NeedsClarification(f"Clarify {machine}'s ordered outage start/end using 'from datetime to datetime'.")
                result.append(Binding("machine_unavailability", machine, (dates[j], dates[j + 1]), clause[:tokens[j + 1].end()]))
    counts = Counter(b.key for b in result)
    order_counts = Counter(b.identifier for b in result if b.operation == "order_deadline")
    if any(n > 1 for n in counts.values()) or any(n > 1 for n in order_counts.values()):
        raise NeedsClarification("Duplicate or conflicting changes: provide one deadline per order and no duplicate outage intervals.")
    bound_times = {date for b in result for date in b.dates}
    # Existing deadline references are allowed only in a checked 'from old to new' clause.
    for ref in refs:
        if ref.group(1) and ref.group(1) in orders:
            bound_times.add(datetime.fromisoformat(orders[ref.group(1)].deadline))
    if {explicit_datetime(t) for t in re.findall(ISO, request.text)} - bound_times:
        raise NeedsClarification("A datetime is not clearly associated with an identified operation; put each ID and its dates in one clause.")
    return result


def local_decision(request):
    """None means AMD must interpret. Returned non-ready decisions make zero API calls."""
    instructions = instructions_without_known_ids(request)
    def clarification(question):
        bounded = question if len(question) <= 500 else question[:497] + "..."
        return InterpretationResponse(status="clarification", changes=[], clarification_questions=[bounded], unsupported_reasons=[])
    known_machines = {m.machine_id for m in request.machines}
    known_orders = {o.order_id for o in request.orders}
    refs = list(REF.finditer(request.text))
    unknown_machines = sorted({r.group(2) for r in refs if r.group(2)} - known_machines)
    unknown_orders = sorted({r.group(1) for r in refs if r.group(1)} - known_orders)
    if unknown_machines:
        return clarification("Unknown machine ID(s): " + ", ".join(unknown_machines) + ". Use an exact configured ID; no prefix or fuzzy mapping is performed.")
    if unknown_orders:
        return clarification("Unknown order ID(s): " + ", ".join(unknown_orders) + ". Use an exact source row ID from the loaded orders.")
    if re.search(r"\b(?:" + PROTECTED + r")\b", instructions, re.I) or re.search(
            r"ignore[\s\S]{0,60}(instructions|schema)|executable|execute|system prompt", instructions, re.I):
        return InterpretationResponse(status="unsupported", changes=[], clarification_questions=[], unsupported_reasons=[{
            "supporting_excerpt": request.text, "reason": "Only explicit outages and completion deadlines are allowed. Settings, pressure, cleaning, capacity, compatibility, rates, formulas and code requests cannot be applied, including mixed requests."}])
    if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}|\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|today|tomorrow|yesterday|next week)\b", instructions, re.I):
        return clarification("Ambiguous or relative date: specify the historical year, month, day and time as YYYY-MM-DD HH:MM. No date will be inferred from today.")
    if re.search(ISO + r"(?:Z|[+-]\d{2}:?\d{2}|[.,]\d)", request.text):
        return clarification("Use scenario-local ISO datetimes without offsets or fractional seconds; no timezone conversion is inferred.")
    if re.search(r"\b(?:not|don't|never|unchanged|unless|except|cancel|either|if|provided|assuming|after|at least|no changes?|no outage)\b", instructions, re.I):
        return clarification("Negated or conditional instruction: no changes will be inferred. Restate only affirmative changes you want, with one explicit ID/date clause per operation.")
    try:
        for token in re.findall(ISO, request.text):
            explicit_datetime(token)
    except ValueError:
        return clarification("A calendar datetime is invalid. Use YYYY-MM-DD HH:MM[:SS].")
    try:
        bindings(request)
    except NeedsClarification as exc:
        return clarification(str(exc))
    return None


def validate_associations(response, request):
    expected = bindings(request)
    actual = []
    for change in response.changes:
        if change.operation == "order_deadline":
            key = (change.operation, change.order_id, explicit_datetime(change.deadline))
        else:
            key = (change.operation, change.machine_id, explicit_datetime(change.start), explicit_datetime(change.end))
        matches = [b for b in expected if b.key == key]
        if len(matches) != 1 or matches[0].core_excerpt not in change.supporting_excerpt:
            raise ValueError("Incorrect or ambiguous date-to-operation association; quote the identified clause with its own dates. No changes applied.")
        actual.append(key)
    if Counter(actual) != Counter(b.key for b in expected):
        raise ValueError("The response does not match every explicitly associated operation; no partial application.")
