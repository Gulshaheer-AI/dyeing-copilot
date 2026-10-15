"""Fixed one-case-derived scheduling suite. No training or assumption tuning."""

import argparse
import hashlib
import json
import platform
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.importer import load_bundled_orders
from planner.change_requests import digest, subtract_interval
from planner.comparators import compare_methods, METHODS, VERSION
from planner.scenario import demo_config, orders_from_import, to_json

MANIFEST = ROOT / "evaluation/scheduling_scenarios_v9.json"
FROZEN = ("planner/comparators.py", "planner/search.py", "planner/evaluator.py", "planner/verifier.py",
          "planner/scenario.py", "planner/comparison.py", "tools/benchmark_scheduling.py")


def instantiate(definition, source):
    originals = orders_from_import(source)
    ids = set(definition["order_ids"])
    if not ids or len(ids) != len(definition["order_ids"]) or not ids <= {o.order_id for o in originals}:
        raise ValueError("Invalid internal subset IDs; public importer is not relaxed.")
    overrides = definition["deadline_overrides"]
    if not set(overrides) <= ids:
        raise ValueError("Override outside benchmark subset.")
    orders = tuple(replace(o, deadline=datetime.fromisoformat(overrides[o.order_id])) if o.order_id in overrides else o
                   for o in originals if o.order_id in ids)
    base = demo_config(source)
    config = replace(base, allow_cleaning_exemptions=definition["permissions_enabled"],
        transition_permissions=tuple(p for p in base.transition_permissions if p.from_order_id in ids and p.to_order_id in ids))
    machines = list(config.machines)
    for outage in definition["outages"]:
        if outage["machine_id"] not in {m.virtual_id for m in machines}:
            raise ValueError("Unknown outage machine.")
        machines = [replace(m, availability=subtract_interval(m.availability, datetime.fromisoformat(outage["start"]),
                    datetime.fromisoformat(outage["end"]))) if m.virtual_id == outage["machine_id"] else m for m in machines]
    return orders, replace(config, machines=tuple(machines))


def aggregate(rows):
    result = {"scenario_count": len(rows), "independent_factory_datasets": 0, "methods": {}, "paired": {}}
    for name in METHODS:
        methods = [r["comparison"]["methods"][name] for r in rows if "comparison" in r]
        result["methods"][name] = {"reported": len(methods),
            "valid": sum(m["eligible_for_comparison"] for m in methods),
            "construction_failures": sum(m["construction_status"] != "complete" for m in methods),
            "verification_failures": sum(m["verification_status"] == "failed" for m in methods),
            "not_verified": sum(m["verification_status"] == "not_available" for m in methods),
            "total_runtime_seconds": sum(m["runtime_seconds"] for m in methods)}
    for name in ("edd", "grouping"):
        eligible = [r["comparison"]["optimiser_against"][name] for r in rows if "comparison" in r and r["comparison"]["optimiser_against"][name]["eligible"]]
        counts = [p["cleaning_events_difference"] for p in eligible]
        result["paired"][name] = {"eligible_denominator": len(eligible), "excluded": len(rows) - len(eligible),
            "optimiser_fewer_cleanings": sum(n > 0 for n in counts), "equal_cleanings": sum(n == 0 for n in counts),
            "optimiser_more_cleanings": sum(n < 0 for n in counts), "signed_cleaning_events_difference_sum": sum(counts)}
    result["scenario_errors"] = sum("error" in r for r in rows)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/scheduling_benchmark_v9.json")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Do not overwrite frozen results; choose a new --output path for reproduction.")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source = load_bundled_orders()
    if source.sha256 != manifest["source_sha256"] or digest(demo_config(source)) != manifest["base_config_fingerprint"]:
        raise ValueError("Bundled source/assumptions differ from fixed benchmark.")
    frozen = json.loads((ROOT / "evaluation/scheduling_freeze_v9.json").read_text(encoding="utf-8"))
    current = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in (*FROZEN, "evaluation/scheduling_scenarios_v9.json")}
    if current != frozen["files"]:
        raise ValueError("Versioned benchmark implementation/manifest changed.")
    started = perf_counter()
    rows = []
    for definition in manifest["scenarios"]:
        row = {"id": definition["id"], "definition": definition}
        try:
            orders, config = instantiate(definition, source)
            row.update(effective_orders=orders, effective_config=config, comparison=compare_methods(orders, config).report)
        except ValueError as exc:
            row["error"] = str(exc)
        rows.append(row)
        print(json.dumps({"id": row["id"], "statuses": {k: v["construction_status"] for k, v in row.get("comparison", {}).get("methods", {}).items()},
            "error": row.get("error")}), flush=True)
    report = {"version": VERSION, "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "frozen_files": frozen["files"], "source_sha256": source.sha256, "method_definitions": METHODS,
        "python_version": platform.python_version(), "platform": platform.platform(), "runtime_seconds": perf_counter() - started,
        "limitations": "26 deterministic scenarios derived from one 35-order historical case; not independent datasets or factory validation. Sequential CPU timings vary by host. No tuning or assumption changes from results.",
        "summary": aggregate(rows), "scenarios": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation: no historical outcome can be silently overwritten.
    with args.output.open("x", encoding="utf-8") as file:
        file.write(to_json(report))
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
