"""Descriptive arithmetic over accepted Sitara imports, with no water-rule inference."""

from dataclasses import dataclass
from decimal import Decimal

from app.importer import ImportResult

WATER_FIELDS = (
    "water_component_1_source", "water_component_2_source",
    "water_component_3_source", "water_total_source",
)
GROUP_FIELDS = ("customer_source", "fabric_type_source", "vessel_type_source")
ZERO = Decimal(0)


@dataclass(frozen=True)
class ResourceSummary:
    order_count: int
    totals: dict[str, Decimal]
    groups: dict[str, list[dict]]
    ranked_orders: list[dict]


@dataclass(frozen=True)
class ResourceAnalysis:
    overall: ResourceSummary
    filtered: ResourceSummary


def _summary(records, overall_total):
    totals = {field: sum((Decimal(r[field]) for r in records), ZERO) for field in WATER_FIELDS}
    groups = {}
    for field in GROUP_FIELDS:
        buckets = {}
        for record in records:
            bucket = buckets.setdefault(record[field], {
                field: record[field], "order_count": 0, **{water: ZERO for water in WATER_FIELDS},
            })
            bucket["order_count"] += 1
            for water in WATER_FIELDS:
                bucket[water] += Decimal(record[water])
        groups[field] = sorted(buckets.values(), key=lambda row: row[field])
    ranked = []
    for rank, record in enumerate(sorted(records, key=lambda r: (
        -Decimal(r["water_total_source"]), int(r["source_row_id"])
    )), 1):
        ranked.append({
            "rank_in_view": rank,
            **{field: record[field] for field in (
                "source_row_id", "source_group_id", "source_csv_line", *GROUP_FIELDS,
                "shade_source", "cloth_length_source",
            )},
            **{water: Decimal(record[water]) for water in WATER_FIELDS},
            "overall_case_contribution_pct": (
                Decimal(record["water_total_source"]) * 100 / overall_total if overall_total else None
            ),
        })
    return ResourceSummary(len(records), totals, groups, ranked)


def analyze_resources(result: ImportResult, *, customers=(), fabrics=(), vessels=()) -> ResourceAnalysis:
    """Accept a successful importer result, never a raw list or failed/empty import.

    Empty filter selections mean all values; different dimensions are intersected.
    Shares always use the full imported case denominator, even in a filtered view.
    Undefined shares for a zero-water case are None. No source records are mutated.
    """
    if not isinstance(result, ImportResult) or not result.valid or len(result.records) != 35:
        raise ValueError("Resource analysis requires a successfully validated 35-order importer result.")
    records = result.records
    overall_total = sum((Decimal(r["water_total_source"]) for r in records), ZERO)
    filters = dict(zip(GROUP_FIELDS, (set(customers), set(fabrics), set(vessels))))
    selected = [r for r in records if all(not values or r[field] in values for field, values in filters.items())]
    return ResourceAnalysis(_summary(records, overall_total), _summary(selected, overall_total))
