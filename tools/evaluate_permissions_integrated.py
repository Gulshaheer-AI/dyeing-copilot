"""Frozen, offline permission sensitivity; never alters existing permissions."""
import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.importer import load_bundled_orders
from planner.scenario import demo_config,to_json
from planner.change_requests import initial_case,digest
from planner.recovery_solver import solve_option,VERSION
from planner.comparison import deadline_performance,compare_schedules
from planner.verifier import verify_schedule
from planner.evaluator import evaluate_resources

MANIFEST=ROOT/'evaluation/permission_sensitivity_integrated_v1.json'
RESULT=ROOT/'reports/permission_sensitivity_integrated_v1.json'


def sha(name):return hashlib.sha256((ROOT/name).read_bytes()).hexdigest()


def files():return {n:sha(n) for n in ('planner/recovery_solver.py','planner/recovery.py','planner/cp_sat.py','planner/scenario.py','planner/verifier.py','planner/evaluator.py','tools/evaluate_permissions_integrated.py')}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze',action='store_true')
    args=parser.parse_args();source=load_bundled_orders();config=demo_config(source)
    permissions=sorted(config.transition_permissions,key=lambda p:(p.virtual_id,int(p.from_order_id),int(p.to_order_id)))
    if args.freeze:
        definition={'version':VERSION,'source_sha256':source.sha256,'seed':20261015,'workers':1,'budget_seconds_per_case':5,
            'restricted_definition':'Every other existing permission in machine/from/to numeric sorted order, starting at index 0.',
            'scenarios':[{'id':'disabled','active':False,'permissions':permissions},
                {'id':'restricted','active':True,'permissions':permissions[::2]},
                {'id':'all_existing','active':True,'permissions':permissions}],
            'frozen_files':files(),'scope':'Three scenarios from one small published case; not independent factory datasets.'}
        with MANIFEST.open('x',encoding='utf-8') as f:f.write(to_json(definition))
        print('Permission scenarios and code frozen before aggregate results.');return
    frozen=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if frozen['frozen_files']!=files() or frozen['source_sha256']!=source.sha256:raise ValueError('Frozen inputs changed. Version separately.')
    if RESULT.exists():raise ValueError('Never overwrite historical evaluation.')
    from planner.scenario import TransitionPermission
    rows=[]
    for definition in frozen['scenarios']:
        cfg=replace(config,allow_cleaning_exemptions=definition['active'],transition_permissions=tuple(TransitionPermission(**p) for p in definition['permissions']))
        case=initial_case(source,cfg);start=perf_counter();run=solve_option(case,'fewer_cleanings',budget_seconds=5)
        baseline=run.legacy.baseline;baseline_ok=verify_schedule(case.orders,cfg,baseline).valid
        verified=run.schedule is not None
        row={'id':definition['id'],'permission_count':len(cfg.transition_permissions),'permissions_enabled':cfg.allow_cleaning_exemptions,
            'effective_fingerprint':digest({'orders':case.orders,'config':cfg}),'baseline_verified':baseline_ok,
            'solver_verified':verified,'stage_a':run.cp_sat.stage_a,'stage_b':run.cp_sat.stage_b,'runtime_seconds':perf_counter()-start,
            'baseline_deadlines':deadline_performance(case.orders,baseline) if baseline_ok else None,
            'selected_deadlines':deadline_performance(case.orders,run.schedule) if verified else None,
            'comparison':compare_schedules(case.orders,cfg,baseline,run.schedule) if baseline_ok and verified else None}
        if verified:
            use=evaluate_resources(case.orders,cfg,run.schedule)
            cost2=evaluate_resources(case.orders,replace(cfg,cleaning_water=cfg.cleaning_water*2),run.schedule)
            row['cost_rescaling_only']={'cleaning_events_unchanged':use.cleaning_events==cost2.cleaning_events,
                'original_score':use.total,'double_cleaning_cost_score':cost2.total,
                'note':'Same schedule evaluated twice. Per-cleaning cost changes the secondary resource score, not the count/slack objectives or permissions.'}
        rows.append(row)
    with RESULT.open('x',encoding='utf-8') as f:f.write(to_json({'manifest_sha256':sha(MANIFEST.relative_to(ROOT)),
        'offline':True,'live_amd_calls':0,'rows':rows,'valid_comparison_denominator':sum(r['comparison'] is not None for r in rows),
        'failures_retained':sum(not r['solver_verified'] for r in rows),'limitations':frozen['scope']}))
    print(json.dumps({'output':str(RESULT),'verified':sum(r['solver_verified'] for r in rows),'n':len(rows)}))


if __name__=='__main__':main()
