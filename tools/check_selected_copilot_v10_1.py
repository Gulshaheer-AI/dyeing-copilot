"""Two bounded live explanation smoke checks; never overwrite or claim accuracy."""
import argparse
import json
import sys
import tempfile
from datetime import datetime,timedelta
from decimal import Decimal as D
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.importer import load_bundled_orders
from app.cp_sat_view import export_backend
from copilot.amd import load_config,AMDConnectionError
from copilot.planning_manual import manual_proposal
from copilot.reviews import ReviewStore
from copilot.selected_evidence import build_selected_evidence
from copilot.selected_workflow import explain_selected
from copilot.selected_reviews import applicable_review
from planner.backend import run_backend
from planner.change_requests import initial_case,apply_and_reschedule,reset_case,PlanningCase
from planner.scenario import demo_config,Order,Machine,Window,Scenario


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--live',action='store_true');args=parser.parse_args()
    if not args.live:return
    path=ROOT/'reports/milestone_10_1_live_checks.json'
    if path.exists():raise ValueError('Live outcomes already exist; no overwrite or retry-until-success.')
    try:config=load_config()
    except AMDConnectionError as exc:
        path.write_text(json.dumps({'configured':False,'outcome':str(exc),'live_calls':0},indent=2));return
    source=load_bundled_orders();original=initial_case(source,demo_config(source))
    manual=manual_proposal(original,operation='order_deadline',identifier='12',deadline=datetime(2019,12,23,18,15))
    changed,_=apply_and_reschedule(original,manual)
    start=datetime(2020,1,1);finish=start+timedelta(days=3)
    orders=(Order('1',D(10),'Open','Cotton','A',D(1),start+timedelta(hours=8),start+timedelta(hours=10)),
            Order('2',D(10),'Open','Cotton','B',D(1),start,start+timedelta(hours=11)))
    machine=Machine('virtual-synthetic-test',(('Open','Cotton'),),D(10),(Window(start,finish),),False)
    scenario=Scenario('Synthetic EDD-failure fixture','Synthetic software check, not factory data.',(machine,),D(1),D(1),D(350),D('.10'),D('.05'),True,False,())
    synthetic=PlanningCase('0'*64,'synthetic CP-SAT EDD-failure software check',orders,scenario,scenario)
    cases=[('bundled_manual_deadline',changed,source,'Explain order 12 in this selected schedule and its actual comparison.'),
           ('synthetic_edd_failure',synthetic,None,'Explain order 2 and why no EDD comparison or savings can be inferred.')]
    report={'configured':True,'maximum_logical_calls':2,'semantic_repairs':0,'checks':[],'scope':'Live smoke checks of exact-statement grounding, not held-out accuracy or factory validation.'}
    path.write_text(json.dumps(report,indent=2))
    for label,case,src,question in cases:
        row={'case':label,'input_provenance':'public real-origin source with hypothetical constraints' if src else 'tiny synthetic solver fixture',
             'workflow_correct':False}
        try:
            run=run_backend(case.orders,case.config,case_fingerprint=case.fingerprint)
            bundle=build_selected_evidence(case,run,question,source=src)
            answer=explain_selected(bundle,question,config=config)
            with tempfile.TemporaryDirectory(prefix='selected-review-check-',dir=ROOT/'dist') as directory:
                store=ReviewStore(Path(directory)/'review.db');rid=store.save_pending(answer,bundle)
                pending=applicable_review(store,bundle,rid)
                pending_export=json.loads(export_backend(case,run,bundle=bundle,review=pending))
                store.decide(rid,'accepted_for_further_review',bundle['fingerprint'],'Programmatic test confirmation, not production approval.')
                accepted=applicable_review(store,bundle,rid)
                exported=json.loads(export_backend(case,run,bundle=bundle,review=accepted))
                reset=reset_case(case);reset_run=run_backend(reset.orders,reset.config,case_fingerprint=reset.fingerprint)
                reset_bundle=build_selected_evidence(reset,reset_run,question,source=src)
                try:applicable_review(store,reset_bundle,rid);stale_blocked=False
                except ValueError:stale_blocked=True
                row.update(outcome='validated_live',receipt=answer.receipt,evidence_fingerprint=bundle['fingerprint'],
                    explanation=answer.output.model_dump(),comparison_present=bundle['scenario']['comparison'] is not None,
                    pending_status=pending_export['review_status'],accepted_status=exported['review_status'],
                    exported_review_fingerprint=exported['applicable_review']['fingerprint'],
                    source_constraints_restored=reset.orders==case.original_orders and reset.config==case.original_config,
                    stale_review_blocked=stale_blocked,workflow_correct=stale_blocked and pending_export['review_status']=='pending_review' and exported['review_status']=='accepted_for_further_review')
        except (ValueError,OSError) as exc:row.update(outcome='failed_or_rejected',error=str(exc))
        report['checks'].append(row);path.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({k:row.get(k) for k in ('case','outcome','workflow_correct','receipt')}),flush=True)


if __name__=='__main__':main()
