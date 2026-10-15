"""Explicit live AMD end-to-end smoke; records only secret-free outcome metadata."""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.importer import load_bundled_orders
from copilot.amd import load_config
from copilot.evidence import build_evidence
from copilot.workflow import explain
from planner.scenario import demo_config, orders_from_import
from planner.search import plan


def main():
    outcome = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "origin": "live_amd",
               "outcome": "unverified", "secrets_logged": False, "actual_model": None}
    started = time.perf_counter()
    try:
        config = load_config()
        outcome["requested_model"] = config.model
        result = load_bundled_orders()
        scenario = demo_config(result)  # Exemptions remain disabled.
        comparison = plan(orders_from_import(result), scenario)
        question = "Explain this schedule comparison and why resource demand remained unchanged."
        bundle = build_evidence(result, question, config=scenario, comparison=comparison)
        answer = explain(bundle, question, scope="scenario", config=config)
        outcome.update(answer.receipt)
        outcome.update(outcome="validated_live_success", fingerprint=bundle["fingerprint"],
                       evidence_references=answer.output.evidence_references)
    except ValueError as exc:
        outcome["outcome"] = "live_attempt_failed_or_rejected"
        outcome["error"] = str(exc)  # All connection/validation errors are curated and contain no raw body.
    outcome["total_smoke_seconds"] = round(time.perf_counter() - started, 3)
    (ROOT / "reports/amd_live_smoke.json").write_text(json.dumps(outcome, indent=2), encoding="utf-8")
    print(json.dumps(outcome, indent=2))
    return 0 if outcome["outcome"] == "validated_live_success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
