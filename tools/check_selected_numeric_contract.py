"""One bounded live selected-explanation check; historical outcomes are untouched."""
import argparse
import json
import sys
import time
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.importer import load_bundled_orders
from copilot.amd import load_config
from copilot.selected_evidence import build_selected_evidence
from copilot.selected_workflow import explain_selected
from planner.backend import run_backend
from planner.change_requests import initial_case
from planner.scenario import demo_config


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    if not parser.parse_args().live:return
    path=ROOT/'reports/selected_numeric_contract_live_check.json'
    report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),
        'maximum_logical_calls':1,'semantic_repairs':0,
        'transport_attempt_limit':2,'outcome':'started',
        'scope':'One smoke check, not an accuracy evaluation or factory validation.'}
    # Exclusive creation prevents overwriting prior results or rerunning until success.
    with path.open('x',encoding='utf-8') as handle:json.dump(report,handle,indent=2)
    started=time.perf_counter()
    try:
        config=load_config()
        report['requested_model']=config.model
        source=load_bundled_orders()
        case=initial_case(source,demo_config(source))
        run=run_backend(case.orders,case.config,case_fingerprint=case.fingerprint)
        question='Explain order 12 in the selected schedule and what the planner should review.'
        bundle=build_selected_evidence(case,run,question,source=source)
        report.update(evidence_fingerprint=bundle['fingerprint'],
            scenario_fingerprint=case.fingerprint,question=question,
            independently_verified=bundle['scenario']['verification']['valid'])
        answer=explain_selected(bundle,question,config=config)
        report.update(outcome='validated_live',receipt=answer.receipt,
            explanation=answer.output.model_dump())
    except (ValueError,OSError) as exc:
        # Existing API/validation errors are curated; never retain raw responses or config.
        report.update(outcome='failed_or_rejected',error=str(exc),receipt=getattr(exc,'receipt',None))
    report['total_elapsed_seconds']=round(time.perf_counter()-started,3)
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('outcome','receipt','total_elapsed_seconds')}))


if __name__=='__main__':main()
