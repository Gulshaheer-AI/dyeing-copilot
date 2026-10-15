"""Explicit live selected-day explanation; offline tests never call this command."""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from copilot.amd import load_config
from copilot.daily_evidence import build_daily_evidence, retrieve_daily_day
from copilot.workflow import explain
from daily.importer import load_bundled_daily
from daily.models import load_models, score_daily


def main():
    started = time.perf_counter()
    outcome = {"origin": "live_amd", "timestamp_utc": datetime.now(timezone.utc).isoformat(), "actual_model": None,
               "outcome": "unverified", "secrets_logged": False}
    try:
        config = load_config()
        outcome["requested_model"] = config.model
        source, artifact = load_bundled_daily(), load_models()
        scores = score_daily(source, artifact)
        flagged = scores[scores.investigation_flag]
        day = flagged.iloc[0] if len(flagged) else scores[scores.flag_eligible].iloc[0]
        context = retrieve_daily_day(source, artifact, day.Date, day.resource)
        question = "Why was this synthetic resource day flagged, and what should a supervisor investigate without inventing a root cause?"
        bundle = build_daily_evidence(context, question)
        outcome.update(selected_day=context["date"], resource=context["resource"], dataset_sha256=source.sha256,
                       model_version=context["model_version"], evidence_fingerprint=bundle["fingerprint"])
        answer = explain(bundle, question, scope="daily", config=config)
        outcome.update(answer.receipt)
        outcome.update(outcome="validated_live_success", evidence_references=answer.output.evidence_references)
    except (ValueError, OSError) as exc:
        outcome.update(outcome="live_attempt_failed_or_rejected", error=str(exc))
    outcome["total_smoke_seconds"] = round(time.perf_counter() - started, 3)
    (ROOT / "reports/daily_amd_live_smoke.json").write_text(json.dumps(outcome, indent=2), encoding="utf-8")
    print(json.dumps(outcome, indent=2))
    return 0 if outcome["outcome"] == "validated_live_success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
