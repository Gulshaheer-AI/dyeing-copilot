"""Milestone 10.1: same preserved 26 cases, fresh legacy timings, bounded CP-SAT."""
import argparse
import hashlib
import json
import platform
import sys
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.importer import load_bundled_orders
from planner.cp_sat import solve,VERSION,SEED
from planner.comparators import compare_methods
from planner.comparison import compare_schedules,deadline_performance
from planner.scenario import to_json
from tools.benchmark_scheduling import instantiate,aggregate

FILES=('planner/cp_sat.py','tools/benchmark_cp_sat_v10_1.py','evaluation/scheduling_scenarios_v9.json',
       'planner/search.py','planner/comparators.py','planner/verifier.py','planner/evaluator.py','planner/scenario.py')


def hashes():
    return {n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in FILES}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'reports/scheduling_benchmark_v10_1.json')
    args=parser.parse_args()
    freeze=ROOT/'evaluation/cp_sat_freeze_v10_1.json'
    if args.freeze:
        with freeze.open('x',encoding='utf-8') as file:
            file.write(json.dumps({'version':VERSION,'files':hashes(),'budget_seconds':10,'workers':1,'seed':SEED,
                'gap_limits':{'relative':0,'absolute':0},'stage_a_budget_fraction':0.6,
                'historical_manifest_unchanged':True,'no_post_result_tuning':True},indent=2))
        print('CP-SAT implementation and benchmark frozen before aggregate results.')
        return
    frozen=json.loads(freeze.read_text())
    if hashes()!=frozen['files']:
        raise ValueError('Frozen benchmark files changed; version changes separately.')
    if args.output.exists():
        raise ValueError('Output exists; use a different --output; never overwrite historical evaluation.')
    source=load_bundled_orders()
    manifest=json.loads((ROOT/'evaluation/scheduling_scenarios_v9.json').read_text())
    if source.sha256!=manifest['source_sha256']:
        raise ValueError('Source differs from fixed scenarios.')
    started=perf_counter();rows=[]
    # Reserve the output before any solves so interrupted evaluations are visible.
    with args.output.open('x',encoding='utf-8') as file:file.write('{"status":"in_progress"}')
    for definition in manifest['scenarios']:
        orders,config=instantiate(definition,source)
        old=compare_methods(orders,config)
        cp=solve(orders,config,budget_seconds=frozen['budget_seconds'],incumbent=old.original_plan.proposal)
        row={'id':definition['id'],'definition':definition,'effective_orders':orders,'effective_config':config,
             'comparison':old.report,'cp_sat':asdict(cp),'differences':{}}
        for method,baseline in old.report['methods'].items():
            eligible=cp.schedule is not None and baseline['eligible_for_comparison']
            difference=None
            if eligible:
                # Retrieve actual Schedule objects from the preserved artifacts.
                from planner.contracts import Schedule,Placement,TerminalCleanup
                original=baseline['schedule']
                schedule=Schedule(tuple(Placement(**p) for p in original['placements']),tuple(TerminalCleanup(**t) for t in original['terminal_cleanups']))
                details=compare_schedules(orders,config,schedule,cp.schedule)
                difference={'cleaning_events':details['reconciliation']['cleaning_events_difference'],
                    'minimum_slack_hours':min(r['slack_hours'] for r in details['deadlines']['proposal']['orders'])-min(r['slack_hours'] for r in details['deadlines']['baseline']['orders']),
                    'resource_score':details['difference'],'percentage':details['percentage_difference']}
            row['differences'][method]={'eligible':eligible,'comparator_minus_cp_cleaning_positive_is_less':difference}
        if cp.schedule is not None:
            row['cp_deadlines']=deadline_performance(orders,cp.schedule)
            row['cp_counts']=compare_schedules(orders,config,cp.schedule,cp.schedule)['cleaning_counts']['proposal']
        rows.append(row)
        summary={'n':len(rows),'verified_cp':sum(r['cp_sat']['schedule'] is not None for r in rows),
            'cp_statuses':{s:sum(r['cp_sat']['solver_status']==s for r in rows) for s in sorted({r['cp_sat']['solver_status'] for r in rows})},
            'cleaning_optimal':sum(r['cp_sat']['cleaning_optimal'] for r in rows),'legacy':aggregate(rows),'pairs':{}}
        for method in ('edd','grouping','optimiser'):
            values=[r['differences'][method]['comparator_minus_cp_cleaning_positive_is_less']['cleaning_events'] for r in rows if r['differences'][method]['eligible']]
            summary['pairs'][method]={'eligible':len(values),'excluded':len(rows)-len(values),
                'cp_fewer':sum(v>0 for v in values),'equal':sum(v==0 for v in values),'cp_more':sum(v<0 for v in values)}
        report={'version':VERSION,'frozen':frozen,'source_sha256':source.sha256,'python':platform.python_version(),
            'platform':platform.platform(),'ortools_version':__import__('ortools').__version__,
            'total_runtime_seconds':perf_counter()-started,'summary':summary,'scenarios':rows,
            'limits':'One historical source case, 26 overlapping illustrative scenarios. All outcomes including unknown/infeasible/equal/worse retained; no factory validation. CP has no implicit heuristic fallback in this benchmark.'}
        args.output.write_text(to_json(report),encoding='utf-8')
        print(json.dumps({'id':row['id'],'cp':cp.solver_status,'stage_a':cp.stage_a['status'],'stage_b':cp.stage_b['status'],
            'verified':cp.schedule is not None,'cleanings':cp.resources.cleaning_events if cp.resources else None,'seconds':cp.timing['total_seconds']}),flush=True)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
