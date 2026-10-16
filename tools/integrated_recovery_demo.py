"""Bounded, offline public-order recovery example; no AMD requests."""
import argparse
import json
import sys
import tempfile
from dataclasses import replace
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.importer import load_bundled_orders
from planner.scenario import demo_config,to_json
from planner.change_requests import initial_case,apply_changes,preview_changes,reset_case
from planner.backend import run_backend
from planner.recovery import select_reference,recovery_summary,verify_recovery
from planner.recovery_solver import run_options
from copilot.planning_manual import manual_proposal
from copilot.selected_evidence import build_selected_evidence
from copilot.selected_workflow import explain_selected
from copilot.reviews import ReviewStore
from copilot.selected_reviews import applicable_review
from app.cp_sat_view import export_backend


def reference_case():
    source=load_bundled_orders()
    case=initial_case(source,replace(demo_config(source),allow_cleaning_exemptions=True))
    run=run_backend(case.orders,case.config,budget_seconds=10,case_fingerprint=case.fingerprint)
    if run.schedule is None:raise ValueError('No verified initial reference; example not fabricated.')
    return source,select_reference(case,run,datetime(2019,12,1,5)),run


def build_demo():
    source,case,reference=reference_case()
    proposal=manual_proposal(case,operation='machine_unavailability',identifier='virtual-Pressure-PolyCotton',
        start=datetime(2019,12,1,12),end=datetime(2019,12,2,12))
    preview=preview_changes(case,proposal)
    updated=apply_changes(case,proposal) # explicit offline harness confirmation
    runs=run_options(updated,budget_seconds=10)
    rows={}
    for option,run in runs.items():
        rows[option]={'solver':run.cp_sat,'verified':run.schedule is not None,
            'summary':recovery_summary(updated,run.schedule) if run.schedule else None}
    chosen=runs['fewer_cleanings']
    artifact=None
    if chosen.schedule:
        bundle=build_selected_evidence(updated,chosen,'Explain recovery changes and preserved work',source=source)
        answer=explain_selected(bundle,'Explain recovery changes and preserved work',mode='mock')
        with tempfile.TemporaryDirectory() as folder:
            store=ReviewStore(Path(folder)/'review.db')
            rid=store.save_pending(answer,bundle,'Offline demonstration; further review only.')
            store.decide(rid,'accepted_for_further_review',bundle['fingerprint'])
            artifact=json.loads(export_backend(updated,chosen,bundle=bundle,review=applicable_review(store,bundle,rid)))
    conflict=manual_proposal(case,operation='machine_unavailability',identifier='virtual-Pressure-PolyCotton',
        start=datetime(2019,12,1,4),end=datetime(2019,12,1,6))
    try:preview_changes(case,conflict);conflict_error='NOT_REJECTED'
    except ValueError as exc:conflict_error=str(exc)
    reset=reset_case(updated)
    return {'version':'integrated-recovery-v1','execution_origin':'offline simulated reference; no telemetry',
        'live_amd_calls':0,'explanation_origin':'mock','initial_reference':reference.schedule,
        'reference_case':case,'request':proposal.request.model_dump(),'receipt':proposal.receipt,
        'preview':preview,'explicit_offline_harness_confirmation':True,'options':rows,
        'review_export':artifact,'conflict_request':conflict.request.text,'conflict_error':conflict_error,
        'reset_original_constraints':reset.recovery is None and reset.config==case.original_config and reset.orders==case.original_orders}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'reports/integrated_recovery_demo_v1.json')
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Output exists; choose a fresh versioned output.')
    result=build_demo()
    with args.output.open('x',encoding='utf-8') as f:f.write(to_json(result))
    print(json.dumps({'output':str(args.output),'verified':{k:v['verified'] for k,v in result['options'].items()},
        'conflict_rejected':result['conflict_error']!='NOT_REJECTED','live_amd_calls':0}))


if __name__=='__main__':main()
