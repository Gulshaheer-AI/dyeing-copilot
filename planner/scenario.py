"""Explicit scenario contract. These assumptions describe virtual equipment only."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from app.importer import ImportResult

MODEL_VERSION = "illustrative-dyeing-v1"
RESOURCE_UNIT = "modelled source units"


def number(value, label, *, positive=False):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or (positive and result == 0):
            raise InvalidOperation
        return result
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be a finite {'positive' if positive else 'nonnegative'} number.") from exc


def hours(value):
    micros = number(value, "duration") * 3_600_000_000
    if micros != micros.to_integral_value():
        raise ValueError("Durations must resolve to whole microseconds.")
    return timedelta(microseconds=int(micros))


@dataclass(frozen=True)
class Order:
    order_id: str
    quantity: Decimal
    vessel: str
    fabric: str
    shade: str
    duration_source: Decimal
    release: datetime
    deadline: datetime

    def __post_init__(self):
        if not self.order_id.isdigit() or int(self.order_id) <= 0:
            raise ValueError("Order IDs must be positive numeric source row IDs.")
        number(self.quantity, "quantity", positive=True)
        number(self.duration_source, "duration_source", positive=True)
        if self.release.tzinfo or self.deadline.tzinfo or self.release >= self.deadline:
            raise ValueError("Orders require increasing naive scenario-local release/deadline timestamps.")


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime

    def __post_init__(self):
        if self.start.tzinfo or self.end.tzinfo or self.start >= self.end:
            raise ValueError("Availability must be increasing naive scenario-local timestamps.")


@dataclass(frozen=True)
class Machine:
    virtual_id: str
    compatible_pairs: tuple[tuple[str, str], ...]  # (recorded vessel category, fabric)
    capacity: Decimal
    availability: tuple[Window, ...]
    initially_clean: bool

    def __post_init__(self):
        if not self.virtual_id.startswith("virtual-"):
            raise ValueError("Machine IDs must start with 'virtual-'; no actual equipment is represented.")
        number(self.capacity, "capacity", positive=True)
        if type(self.initially_clean) is not bool or not self.compatible_pairs:
            raise ValueError("Machines require compatibility pairs and a boolean initial state; empty availability means closed.")
        if any(len(pair) != 2 or any(not isinstance(value, str) or not value.strip() for value in pair)
               for pair in self.compatible_pairs):
            raise ValueError("Each compatibility pair must contain a vessel category and fabric string.")
        windows = sorted(self.availability, key=lambda w: w.start)
        if list(self.availability) != windows or any(a.end > b.start for a, b in zip(windows, windows[1:])):
            raise ValueError("Availability windows must be sorted and nonoverlapping.")


@dataclass(frozen=True)
class TransitionPermission:
    virtual_id: str
    from_order_id: str
    to_order_id: str
    basis: str


@dataclass(frozen=True)
class Scenario:
    name: str
    assumption_note: str
    machines: tuple[Machine, ...]
    hours_per_duration_unit: Decimal
    cleaning_hours: Decimal
    cleaning_water: Decimal
    process_a_per_quantity: Decimal
    process_b_per_quantity: Decimal
    terminal_cleaning: bool
    allow_cleaning_exemptions: bool
    transition_permissions: tuple[TransitionPermission, ...]
    resource_unit: str = RESOURCE_UNIT
    timezone: str = "Asia/Karachi (scenario local time)"

    def __post_init__(self):
        if not self.name.strip() or not self.assumption_note.strip() or not self.machines:
            raise ValueError("A scenario needs a name, assumptions and virtual machines.")
        if len({m.virtual_id for m in self.machines}) != len(self.machines):
            raise ValueError("Virtual machine IDs must be unique.")
        number(self.hours_per_duration_unit, "hours_per_duration_unit", positive=True)
        for field in ("cleaning_hours", "cleaning_water", "process_a_per_quantity", "process_b_per_quantity"):
            number(getattr(self, field), field)
        hours(self.cleaning_hours)
        if type(self.terminal_cleaning) is not bool or type(self.allow_cleaning_exemptions) is not bool:
            raise ValueError("Cleaning switches must be booleans.")
        if self.resource_unit != RESOURCE_UNIT or self.timezone != "Asia/Karachi (scenario local time)":
            raise ValueError("This model uses modelled source units and Asia/Karachi scenario local time only.")
        ids = {m.virtual_id for m in self.machines}
        keys = set()
        for permission in self.transition_permissions:
            key = (permission.virtual_id, permission.from_order_id, permission.to_order_id)
            if permission.virtual_id not in ids or not permission.basis.strip() or key in keys:
                raise ValueError("Each permission needs a configured virtual machine, explicit basis and unique pair.")
            keys.add(key)


def orders_from_import(result: ImportResult):
    if not isinstance(result, ImportResult) or not result.valid or len(result.records) != 35:
        raise ValueError("Simulation requires a successful complete 35-order importer result.")
    return tuple(Order(
        r["source_row_id"], Decimal(r["cloth_length_source"]), r["vessel_type_source"],
        r["fabric_type_source"], r["shade_source"], Decimal(r["duration_source"]),
        datetime.combine(r["order_date_parsed"], time()),
        datetime.combine(r["delivery_date_parsed"] + timedelta(days=1), time()),
    ) for r in result.records)


def validate_case(orders, config):
    if not orders or len({o.order_id for o in orders}) != len(orders):
        raise ValueError("Planning requires a nonempty set of unique orders.")
    ids = {o.order_id: o for o in orders}
    machines = {m.virtual_id: m for m in config.machines}
    for order in orders:
        hours(order.duration_source * config.hours_per_duration_unit)
    for permission in config.transition_permissions:
        if permission.from_order_id not in ids or permission.to_order_id not in ids:
            raise ValueError("Transition permissions reference orders outside this complete case.")
        if permission.from_order_id == permission.to_order_id:
            raise ValueError("A transition permission must connect distinct orders.")
        for order_id in (permission.from_order_id, permission.to_order_id):
            o = ids[order_id]
            if (o.vessel, o.fabric) not in machines[permission.virtual_id].compatible_pairs:
                raise ValueError("A transition permission uses an incompatible virtual machine.")


def parse_config(text):
    raw = json.loads(text)
    # Dataclass constructors reject unknown or missing fields; no silent key ignoring.
    raw["machines"] = tuple(Machine(
        **{**m, "capacity": number(m["capacity"], "capacity", positive=True),
           "compatible_pairs": tuple(tuple(pair) for pair in m["compatible_pairs"]),
           "availability": tuple(Window(**{key: datetime.fromisoformat(value) for key, value in w.items()})
                                 for w in m["availability"])}
    ) for m in raw["machines"])
    for field in ("hours_per_duration_unit", "cleaning_hours", "cleaning_water",
                  "process_a_per_quantity", "process_b_per_quantity"):
        raw[field] = number(raw[field], field, positive=field == "hours_per_duration_unit")
    raw["transition_permissions"] = tuple(TransitionPermission(**p) for p in raw["transition_permissions"])
    return Scenario(**raw)


def to_json(value):
    return json.dumps(value, default=lambda v: asdict(v) if hasattr(v, "__dataclass_fields__") else str(v), indent=2)


def demo_config(result):
    orders = orders_from_import(result)
    start, end = min(o.release for o in orders), max(o.deadline for o in orders)
    pairs = sorted({(o.vessel, o.fabric) for o in orders})
    machines = tuple(Machine(f"virtual-{vessel}-{fabric}", ((vessel, fabric),), Decimal(5000),
                             (Window(start, end),), False) for vessel, fabric in pairs)
    # These are only proposed illustrative permissions, inactive until explicitly enabled.
    # Matching fields do not establish recipe/quality compatibility.
    permissions = []
    records = {r["source_row_id"]: r for r in result.records}
    for machine in machines:
        for a in orders:
            for b in orders:
                fields = ("fabric_type_source", "vessel_type_source", "shade_source")
                if a != b and (a.vessel, a.fabric) in machine.compatible_pairs and all(
                    records[a.order_id][field] == records[b.order_id][field] for field in fields
                ):
                    permissions.append(TransitionPermission(machine.virtual_id, a.order_id, b.order_id,
                        "Illustrative directed permission: recipe and quality compatibility, including differing "
                        "specifications/depths, is assumed only if explicitly enabled; matching colour is not evidence."))
    return Scenario("Illustrative Sitara demo", "Virtual equipment; 24/7 availability; capacity 5000 source "
        "quantity units; one source duration unit is assumed to be one hour. All rates and permissions "
        "are illustrative, not factory-approved. No splitting, batching or idle-state deterioration.",
        machines, Decimal(1), Decimal(1), Decimal(350), Decimal("0.10"), Decimal("0.05"),
        True, False, tuple(permissions))
