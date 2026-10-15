"""Explicit question rehearsal, offline by default; --live makes actual AMD requests."""

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.importer import load_bundled_orders
from copilot.amd import load_config
from copilot.daily_evidence import build_daily_evidence, retrieve_daily_day
from copilot.evidence import build_evidence
from copilot.workflow import explain
from daily.importer import load_bundled_daily
from daily.models import load_models
from planner.scenario import demo_config, orders_from_import
from planner.search import plan


def cases():
    daily = retrieve_daily_day(load_bundled_daily(), load_models(), "2024-08-09", "water")
    orders = load_bundled_orders()
    # Explicit hypothetical test permission, never a factory approval or a model decision.
    scenario = replace(demo_config(orders), allow_cleaning_exemptions=True)
    comparison = plan(orders_from_import(orders), scenario)
    for question in ("Why was this synthetic day flagged?", "What does the upper expected threshold mean?"):
        yield "daily", question, build_daily_evidence(daily, question)
    for question in ("Why did this hypothetical schedule improve?", "Which assumptions require factory confirmation before using this proposal?"):
        yield "scenario", question, build_evidence(orders, question, config=scenario, comparison=comparison)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    mode = "live_amd" if args.live else "mock"
    outcomes = []
    for scope, question, bundle in cases():
        row = {"question": question, "scope": scope, "origin": mode,
               "timestamp_utc": datetime.now(timezone.utc).isoformat(), "fingerprint": bundle["fingerprint"]}
        try:
            answer = explain(bundle, question, scope=scope, mode=mode, config=load_config() if args.live else None)
            row.update(outcome="validated_live_success" if args.live else "mock_validation_passed",
                       receipt=answer.receipt, explanation=answer.output.model_dump())
        except (ValueError, OSError) as exc:
            row.update(outcome="failed_or_rejected", error=str(exc))
        outcomes.append(row)
        print(json.dumps({key: row[key] for key in ("question", "origin", "outcome")}), flush=True)
        path = ROOT / ("reports/milestone_6_live_questions.json" if args.live else "reports/milestone_6_mock_questions.json")
        path.write_text(json.dumps(outcomes, indent=2), encoding="utf-8")
    return int(any(row["outcome"] == "failed_or_rejected" for row in outcomes))


if __name__ == "__main__":
    raise SystemExit(main())
