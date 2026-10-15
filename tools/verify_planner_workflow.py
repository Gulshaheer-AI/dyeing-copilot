"""Check unchanged/default and explicitly opt-in illustrative planner cases; never train."""

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.importer import load_bundled_orders
from copilot.evidence import build_evidence
from copilot.workflow import explain
from planner.review_package import export_review_package
from planner.scenario import demo_config, orders_from_import, to_json
from planner.search import plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Makes two real AMD requests, no fallback")
    args = parser.parse_args()
    source = load_bundled_orders()
    reports = []
    for enabled in (False, True):
        config = replace(demo_config(source), allow_cleaning_exemptions=enabled)
        comparison = plan(orders_from_import(source), config)
        package = json.loads(export_review_package(source, config, comparison))
        question = "Explain this schedule comparison, specific changed cleaning transitions and what the planner must review before use."
        bundle = build_evidence(source, question, config=config, comparison=comparison)
        row = {"illustrative_permissions_enabled": enabled, "review_package": package, "evidence_fingerprint": bundle["fingerprint"]}
        try:
            answer = explain(bundle, question, scope="scenario", mode="live_amd" if args.live else "mock")
            row.update(receipt=answer.receipt, explanation=answer.output.model_dump(), outcome="validated_live" if args.live else "validated_mock")
        except (ValueError, OSError) as exc:
            row.update(outcome="failed_or_rejected", error=str(exc))
        reports.append(row)
        destination = ROOT / ("reports/milestone_7_live_checks.json" if args.live else "reports/milestone_7_scenario_checks.json")
        destination.write_text(to_json(reports), encoding="utf-8")
        print(json.dumps({"permissions": enabled, "outcome": row["outcome"],
                          "difference": package["planner_comparison"]["difference"], "receipt": row.get("receipt")}), flush=True)
    return int(any(row["outcome"] == "failed_or_rejected" for row in reports))


if __name__ == "__main__":
    raise SystemExit(main())
