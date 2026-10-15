"""Fresh frozen v8.2 evaluation: local screening, AMD results and full scheduling flow separately."""

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
from copilot.planning_diagnostics import EvaluationDiagnostics
from copilot.planning_interpreter import InterpretationRejected, interpret, make_request
from planner.change_export import export_change_audit
from planner.change_requests import apply_and_reschedule, initial_case, preview_changes, reset_case
from planner.scenario import demo_config
from planner.verifier import verify_schedule
from tools.evaluate_planning_requests import normalized

FROZEN_FILES = ("copilot/planning_interpreter.py", "copilot/planning_schema.py", "copilot/planning_guard.py",
                "copilot/planning_contract.py", "copilot/planning_diagnostics.py", "copilot/planning_manual.py",
                "planner/change_requests.py", "evaluation/planning_requests_v8_2.json", "evaluation/protocol_v8_2.json",
                "tools/evaluate_planning_requests_v8_2.py")


def hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FROZEN_FILES}


def evaluate_item(item, case, source, config, diagnostics):
    started = time.perf_counter()
    row = {"id": item["id"], "request": item["text"], "expected_status": item["status"], "expected_route": item["route"],
           "timestamp_utc": datetime.now(timezone.utc).isoformat(), "workflow_correct": False}
    try:
        answer = interpret(make_request(case, item["text"]), config=config, diagnostics=diagnostics)
        actual = answer.response.model_dump()
        route = "local" if answer.receipt["origin"] == "local_validation" else "amd"
        matched = actual["status"] == item["status"] and normalized(actual["changes"]) == normalized(item["changes"])
        row.update(outcome="validated_response", route=route, receipt=answer.receipt, response=actual,
                   validated_semantic_correct=matched, route_correct=route == item["route"])
        before = case.fingerprint
        if actual["status"] == "ready":
            preview = preview_changes(case, answer)
            preview_unchanged = before == case.fingerprint
            # Explicit test-harness confirmation, not autonomous application or production approval.
            updated, comparison = apply_and_reschedule(case, answer)
            valid = (comparison.proposal is not None and verify_schedule(updated.orders, updated.config, comparison.baseline).valid
                     and verify_schedule(updated.orders, updated.config, comparison.proposal).valid)
            reset = reset_case(updated)
            reset_ok = reset.orders == case.original_orders and reset.config == case.original_config
            same_orders = [(o.order_id, o.quantity) for o in updated.orders] == [(o.order_id, o.quantity) for o in case.orders]
            row.update(preview=preview, preview_without_mutation=preview_unchanged, explicit_test_confirmation=True,
                       schedule_verified=bool(valid), reset_original_constraints=reset_ok, order_ids_quantities_preserved=same_orders,
                       applied_audit=json.loads(export_change_audit(source, updated, comparison)))
            flow = preview_unchanged and valid and reset_ok and same_orders
        else:
            try:
                apply_and_reschedule(case, answer)
                blocked = False
            except ValueError:
                blocked = True
            flow = blocked and case.fingerprint == before
            row.update(application_blocked=blocked, scenario_unchanged=case.fingerprint == before)
        row["workflow_correct"] = bool(matched and route == item["route"] and flow)
    except InterpretationRejected as exc:
        row.update(outcome="validation_rejection", route="amd", receipt=exc.receipt, error=str(exc),
                   validated_semantic_correct=False, model_understanding="not_established_by_rejection")
    except AMDConnectionError as exc:
        row.update(outcome="transport_or_service_failure", route="amd", error=str(exc), validated_semantic_correct=None)
    except ValueError as exc:
        row.update(outcome="workflow_failure", error=str(exc))
    row["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    return row


def group_summary(rows):
    return {"n": len(rows), "validated_correct": sum(r.get("validated_semantic_correct") is True for r in rows),
        "workflow_correct": sum(r["workflow_correct"] for r in rows),
        "validation_rejections": sum(r["outcome"] == "validation_rejection" for r in rows),
        "incorrect_refusals": sum(r.get("expected_status") == "ready" and r.get("response", {}).get("status") in ("unsupported", "clarification") for r in rows),
        "transport_or_service_failures": sum(r["outcome"] == "transport_or_service_failure" for r in rows),
        "mean_total_seconds": round(sum(r["elapsed_seconds"] for r in rows) / len(rows), 6) if rows else None,
        "min_total_seconds": min((r["elapsed_seconds"] for r in rows), default=None),
        "max_total_seconds": max((r["elapsed_seconds"] for r in rows), default=None)}


def summary(rows):
    return {"complete_workflow": group_summary(rows),
            "local_decisions": group_summary([r for r in rows if r.get("route") == "local"]),
            "amd_interpretation": group_summary([r for r in rows if r.get("route") == "amd"]),
            "actual_amd_logical_calls": sum(r.get("route") == "amd" for r in rows),
            "accepted_amd_ready": sum(r.get("route") == "amd" and r.get("response", {}).get("status") == "ready" for r in rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    freeze = ROOT / "evaluation/interpreter_freeze_v8_2.json"
    devpath = ROOT / "reports/milestone_8_2_development.json"
    if args.freeze:
        if freeze.exists() or not devpath.exists():
            raise ValueError("Freeze requires prior live development and must not overwrite a freeze.")
        freeze.write_text(json.dumps({"version": "8.2", "files": hashes(), "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "frozen_before_live_evaluation": True}, indent=2), encoding="utf-8")
        print("Final interpreter/scorer frozen.")
    if not args.live and not args.development:
        return
    if args.live and args.development:
        raise ValueError("Choose one phase.")
    frozen = json.loads(freeze.read_text()) if args.live else None
    if args.development and freeze.exists():
        raise ValueError("No tuning/development calls after freeze.")
    if frozen and frozen["files"] != hashes():
        raise ValueError("Frozen implementation changed; held-out evaluation blocked.")
    path = ROOT / "reports/milestone_8_2_live_evaluation.json" if args.live else devpath
    if path.exists():
        raise ValueError("Results already exist. No overwrite or repeated success retries.")
    corpus_path = ROOT / "evaluation/planning_requests_v8_2.json"
    corpus = json.loads(corpus_path.read_text())
    protocol = json.loads((ROOT / "evaluation/protocol_v8_2.json").read_text())
    if hashlib.sha256(corpus_path.read_bytes()).hexdigest() != protocol["corpus_sha256"]:
        raise ValueError("Corpus changed.")
    items = [r for r in corpus["cases"] if r["split"] == ("held_out" if args.live else "development")]
    if args.live and (sum(r["route"] == "amd" for r in items) < 12 or len(items) != 18):
        raise ValueError("At least twelve supported AMD requests plus six local cases required.")
    config = load_config()
    source = load_bundled_orders()
    case = initial_case(source, demo_config(source))
    from copilot.planning_guard import local_decision
    if any((local_decision(make_request(case, r["text"])) is None) != (r["route"] == "amd") for r in items):
        raise ValueError("Unexpected route: supported cases must actually reach AMD.")
    diagnostics = EvaluationDiagnostics(corpus_path, limit=len(items))
    rows = []
    # Reserve the outcome before calling the service, including interrupted runs.
    path.write_text(json.dumps({"status": "in_progress", "results": []}), encoding="utf-8")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(evaluate_item, item, case, source, config, diagnostics) for item in items]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            report = {"version": "8.2", "phase": "held_out" if args.live else "development_regression",
                "source_sha256": source.sha256, "scenario_fingerprint": case.fingerprint,
                "frozen_files": frozen["files"] if frozen else None, "semantic_repair_requests": 0,
                "maximum_concurrency": 2, "summary": summary(rows), "results": sorted(rows, key=lambda r: r["id"])}
            path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            diagnostic_path = ROOT / ("reports/milestone_8_2_live_diagnostics.json" if args.live else "reports/milestone_8_2_development_diagnostics.json")
            diagnostic_path.write_text(json.dumps({"scope": "bundled non-sensitive evaluation only; not ordinary user error logs",
                "records": diagnostics.records}, indent=2), encoding="utf-8")
            print(json.dumps({"id": row["id"], "route": row.get("route"), "outcome": row["outcome"],
                "workflow_correct": row["workflow_correct"], "elapsed_seconds": row["elapsed_seconds"]}), flush=True)
    print(json.dumps(summary(rows), indent=2))


if __name__ == "__main__":
    main()
