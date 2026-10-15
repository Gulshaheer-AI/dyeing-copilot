"""Bounded live held-out evaluation; no fixture-generated responses count as AMD inference."""

import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.importer import load_bundled_orders
from copilot.amd import AMDConnectionError, load_config
from copilot.planning_interpreter import InterpretationRejected, interpret, make_request
from copilot.planning_schema import explicit_datetime
from planner.change_requests import initial_case
from planner.scenario import demo_config

FROZEN_FILES = ("copilot/planning_interpreter.py", "copilot/planning_schema.py", "planner/change_requests.py", "evaluation/planning_requests.json")


def current_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FROZEN_FILES}


def normalized(changes):
    rows = []
    for item in changes:
        row = {k: v for k, v in item.items() if k != "supporting_excerpt"}
        for field in ("start", "end", "deadline"):
            if field in row:
                row[field] = explicit_datetime(row[field]).isoformat()
        rows.append(json.dumps(row, sort_keys=True))
    return sorted(rows)


def evaluate_item(item, case, config):
    started = time.perf_counter()
    row = {"id": item["id"], "request": item["text"], "expected_status": item["status"], "origin": "live_amd_attempt",
           "timestamp_utc": datetime.now(timezone.utc).isoformat()}
    try:
        answer = interpret(make_request(case, item["text"]), config=config)
        actual = answer.response.model_dump()
        row.update(outcome="validated_live_response", response=actual, receipt=answer.receipt,
                   semantic_correct=actual["status"] == item["status"] and normalized(actual["changes"]) == normalized(item["changes"]))
    except InterpretationRejected as exc:
        row.update(outcome="interpretation_validation_rejection", semantic_correct=False, error=str(exc), receipt=exc.receipt)
    except AMDConnectionError as exc:
        row.update(outcome="transport_or_service_failure", semantic_correct=None, error=str(exc))
    row["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    return row


def summary(rows, expected_count):
    attempted = len(rows)
    transport = sum(r["outcome"] == "transport_or_service_failure" for r in rows)
    correct = sum(r.get("semantic_correct") is True for r in rows)
    responses = attempted - transport
    return {"expected_held_out_calls": expected_count, "attempted_logical_calls": attempted,
        "transport_or_service_failures": transport,
        "validated_responses": sum(r["outcome"] == "validated_live_response" for r in rows),
        "interpretation_validation_rejections": sum(r["outcome"] == "interpretation_validation_rejection" for r in rows),
        "semantic_correct": correct, "semantic_correct_over_attempted": f"{correct}/{attempted}",
        "semantic_correct_over_nontransport": f"{correct}/{responses}",
        "handling_by_expected_status": {status: {"correct": sum(r.get("semantic_correct") is True for r in rows if r["expected_status"] == status),
            "attempted": sum(r["expected_status"] == status for r in rows)} for status in ("ready", "clarification", "unsupported")},
        "latency_seconds_all_attempts": {"min": min((r["elapsed_seconds"] for r in rows), default=None),
            "max": max((r["elapsed_seconds"] for r in rows), default=None),
            "mean": round(sum(r["elapsed_seconds"] for r in rows) / attempted, 3) if attempted else None}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true", help="Freeze interpreter hashes before reading live held-out responses")
    parser.add_argument("--live", action="store_true", help="Ten logical calls, maximum two concurrent and two HTTP attempts per call")
    args = parser.parse_args()
    frozen_path = ROOT / "evaluation/interpreter_freeze.json"
    if args.freeze:
        if frozen_path.exists():
            raise ValueError("Interpreter freeze already exists; never replace it after evaluation.")
        frozen_path.write_text(json.dumps({"files": current_hashes(), "frozen_before_live_evaluation": True,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()}, indent=2), encoding="utf-8")
        print("Interpreter and evaluation corpus hashes frozen before live held-out calls.")
    if not args.live:
        return 0
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    if frozen["files"] != current_hashes():
        raise ValueError("Frozen interpreter/corpus changed; evaluation will not run.")
    destination = ROOT / "reports/milestone_8_live_evaluation.json"
    if destination.exists():
        raise ValueError("Live evaluation already recorded. Do not rerun or tune against held-out outcomes.")
    config = load_config()
    data = json.loads((ROOT / "evaluation/planning_requests.json").read_text(encoding="utf-8"))
    items = [item for item in data["cases"] if item["split"] == "held_out"]
    if len(items) != 10:
        raise ValueError("Expected the frozen ten-call held-out set.")
    source = load_bundled_orders()
    case = initial_case(source, demo_config(source))
    rows = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(evaluate_item, item, case, config) for item in items]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            report = {"origin": "live_amd_evaluation", "budget": {"logical_calls": 10, "maximum_http_attempts": 20, "concurrency": 2},
                "source_sha256": source.sha256, "scenario_fingerprint": case.fingerprint,
                "requested_model": config.model, "frozen_files": frozen["files"], "no_tuning_against_held_out": True,
                "summary": summary(rows, len(items)), "results": sorted(rows, key=lambda r: r["id"])}
            destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps({"id": row["id"], "outcome": row["outcome"], "semantic_correct": row.get("semantic_correct"),
                              "elapsed_seconds": row["elapsed_seconds"]}), flush=True)
    print(json.dumps(summary(rows, len(items)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
