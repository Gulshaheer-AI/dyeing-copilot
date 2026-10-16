"""New frozen corpus. Live interpretation requires an explicit --live flag."""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from dataclasses import replace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.importer import load_bundled_orders
from copilot.amd import load_config,AMDConnectionError
from copilot.planning_guard import local_decision
from copilot.planning_interpreter import interpret,make_request,InterpretationRejected
from planner.scenario import demo_config,to_json
from planner.contracts import Placement,TerminalCleanup,Schedule
from planner.change_requests import initial_case,preview_changes,apply_changes,reset_case
from planner.recovery import select_reference
from planner.recovery_solver import solve_option
from tools.evaluate_planning_requests import normalized

CORPUS=ROOT/'evaluation/planning_requests_integrated_v1.json'
FREEZE=ROOT/'evaluation/interpreter_freeze_integrated_v1.json'
FILES=('copilot/planning_interpreter.py','copilot/planning_schema.py','copilot/planning_guard.py','copilot/planning_contract.py',
    'copilot/amd.py','planner/change_requests.py','planner/recovery.py','planner/recovery_solver.py',
    'tools/evaluate_interpreter_integrated.py','evaluation/planning_requests_integrated_v1.json','evaluation/protocol_integrated_v1.json',
    'reports/integrated_recovery_demo_v1.json')


def hashes():return {n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in FILES}


def contexts():
    source=load_bundled_orders()
    case=initial_case(source,replace(demo_config(source),allow_cleaning_exemptions=True))
    data=json.loads((ROOT/'reports/integrated_recovery_demo_v1.json').read_text(encoding='utf-8'))
    if data['request']['source_sha256']!=source.sha256:raise ValueError('Frozen reference source changed.')
    rows=[]
    for row in data['initial_reference']['placements']:
        row={**row,'quantity':Decimal(row['quantity'])}
        for k in ('cleaning_start','process_start','process_end'):row[k]=datetime.fromisoformat(row[k])
        rows.append(Placement(**row))
    terminal=tuple(TerminalCleanup(t['virtual_id'],datetime.fromisoformat(t['start']),datetime.fromisoformat(t['end'])) for t in data['initial_reference']['terminal_cleanups'])
    schedule=Schedule(tuple(rows),terminal)
    recovery=select_reference(case,SimpleNamespace(case_fingerprint=case.fingerprint,schedule=schedule),datetime(2019,12,1,5))
    return {'full':case,'recovery':recovery}


class Diagnostics:
    """Only this exact non-sensitive bundled corpus; never accept headers/config."""
    def __init__(self,items):self.allowed={r['text'] for r in items};self.records=[]
    def capture(self,request,content,receipt,error,secret):
        if request.text not in self.allowed:raise ValueError('Unapproved diagnostic input.')
        value=json.dumps({'content':content,'receipt':receipt,'error':error})
        blocked=bool(secret and secret in value) or bool(re.search(r'authorization|bearer\s+\S+|api[_ -]?key|sk-[A-Za-z0-9]{12,}',value,re.I))
        self.records.append({'request':request.text,'content':None if blocked else content,
            'receipt':None if blocked else receipt,'validation_error':None if blocked else error,
            'credential_screen':'payload_suppressed' if blocked else 'passed'})


def evaluate(item,case,*,live,config,diagnostics):
    start=perf_counter();request=make_request(case,item['text']);local=local_decision(request)
    row={'id':item['id'],'split':item['split'],'context':item['context'],'text':item['text'],
        'expected_status':item['status'],'expected_route':item['route'],'expected_application':item['application']}
    if local is None and not live:
        return {**row,'route':'amd_not_called','outcome':'deferred_no_live_opt_in','semantic_correct':None,'latency_seconds':0}
    try:
        answer=interpret(request,config=config,diagnostics=diagnostics)
        response=answer.response.model_dump()
        route='local' if answer.receipt['origin']=='local_validation' else 'amd'
        correct=response['status']==item['status'] and normalized(response['changes'])==normalized(item['changes'])
        row.update(route=route,outcome='validated_response',receipt=answer.receipt,response=response,
            semantic_correct=correct,route_correct=route==item['route'])
        before=case.fingerprint
        if response['status']=='ready':
            try:
                preview=preview_changes(case,answer)
                row['preview_without_mutation']=case.fingerprint==before
                updated=apply_changes(case,answer) # explicit evaluation harness confirmation, not the UI
                row.update(application='accepted',application_correct=item['application']=='accepted',preview=preview)
                run=solve_option(updated,'fewer_cleanings',budget_seconds=2)
                row.update(schedule_verified=run.schedule is not None,solver_status=run.cp_sat.stage_a['status'],
                    solver_evidence=run.cp_sat,reset_original_constraints=reset_case(updated).config==case.original_config)
            except ValueError as exc:
                row.update(application='history_conflict' if case.recovery else 'validation_rejection',application_error=str(exc),
                    application_correct=item['application']=='history_conflict' and case.fingerprint==before)
        else:
            row.update(application='blocked',application_correct=item['application']=='blocked',scenario_unchanged=case.fingerprint==before)
        row['complete_workflow_correct']=bool(correct and row.get('route_correct') and row.get('application_correct') and
            (row.get('schedule_verified') if row.get('application')=='accepted' else True))
    except InterpretationRejected as exc:
        row.update(route='amd',outcome='validation_rejection',receipt=exc.receipt,error=str(exc),semantic_correct=False,
            understanding='A rejected output does not establish model understanding.')
    except AMDConnectionError as exc:
        row.update(route='amd',outcome='transport_failure',error=str(exc),semantic_correct=None)
    row['latency_seconds']=perf_counter()-start
    return row


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze',action='store_true');parser.add_argument('--live',action='store_true')
    parser.add_argument('--split',choices=['development','held_out','all'],default='all')
    parser.add_argument('--max-calls',type=int,default=24)
    parser.add_argument('--output',type=Path,default=ROOT/'reports/integrated_interpreter_offline_v1.json')
    args=parser.parse_args()
    if args.freeze:
        with FREEZE.open('x',encoding='utf-8') as f:json.dump({'files':hashes(),'frozen_before_live':True,'repairs':0},f,indent=2)
        print('Interpreter, expected outcomes and reference frozen; no live requests.');return
    if hashes()!=json.loads(FREEZE.read_text(encoding='utf-8'))['files']:raise ValueError('Frozen interpreter/evaluation changed. Create a new version.')
    if args.output.exists():raise ValueError('Output exists; historical outcomes cannot be overwritten.')
    if not 0<=args.max_calls<=24:raise ValueError('At most 24 semantic AMD requests per invocation.')
    items=[i for i in json.loads(CORPUS.read_text(encoding='utf-8'))['cases'] if args.split=='all' or i['split']==args.split]
    cases=contexts();config=load_config() if args.live else None;diagnostics=Diagnostics(items);rows=[];calls=0
    for item in items:
        local=local_decision(make_request(cases[item['context']],item['text']))
        if args.live and local is None:
            if calls>=args.max_calls:
                rows.append({'id':item['id'],'outcome':'skipped_call_bound','route':'amd_not_called'});continue
            calls+=1
        rows.append(evaluate(item,cases[item['context']],live=args.live,config=config,diagnostics=diagnostics))
    def summary(route):
        group=[r for r in rows if r.get('route')==route]
        return {'n':len(group),'first_pass_correct':sum(r.get('semantic_correct') is True for r in group),
            'validation_failures':sum(r['outcome']=='validation_rejection' for r in group),
            'incorrect_refusals':sum(r.get('expected_status')=='ready' and r.get('response',{}).get('status') in ('clarification','unsupported') for r in group),
            'transport_failures':sum(r['outcome']=='transport_failure' for r in group),
            'complete_workflow_correct':sum(r.get('complete_workflow_correct') is True for r in group),
            'application_history_conflicts':sum(r.get('application')=='history_conflict' for r in group),
            'latencies_seconds':[r['latency_seconds'] for r in group]}
    result={'version':'integrated-v1','timestamp_utc':datetime.now(timezone.utc).isoformat(),'live_opt_in':args.live,
        'semantic_amd_calls':calls,'maximum_transport_attempts':calls*2,'repairs':0,
        'local_summary':summary('local'),'amd_summary':summary('amd'),'rows':rows,'diagnostics':diagnostics.records,
        'limits':'No anomaly or industrial safety accuracy. Semantic correctness, application conflicts and verified feasibility are separate.'}
    serialized=to_json(result)
    if config and config.api_key in serialized:raise ValueError('Credential screen blocked the entire evaluation output; nothing saved.')
    with args.output.open('x',encoding='utf-8') as f:f.write(serialized)
    print(json.dumps({'output':str(args.output),'semantic_amd_calls':calls,'local':result['local_summary'],'amd':result['amd_summary']}))


if __name__=='__main__':main()
