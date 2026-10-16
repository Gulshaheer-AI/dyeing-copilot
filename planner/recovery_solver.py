"""Versioned lexicographic options on the existing exact CP model, not EDD placement."""
import math
from dataclasses import dataclass
from time import perf_counter
from ortools.sat.python import cp_model
from planner.cp_sat import _build,_translate,_solver,micros,minimum_slack_ticks,CPSatResult,MAX_BUDGET
from planner.backend import BackendRun
from planner.change_requests import digest
from planner.search import plan
from planner.evaluator import evaluate_resources
from planner.recovery import fixed_placements,check_history,verify_recovery

VERSION='integrated-recovery-cp-v1'
OPTIONS={'fewer_cleanings':'Fewer cleanings','deadline_protection':'More deadline protection'}


@dataclass(frozen=True)
class OptionResult(CPSatResult):
    objective_order:str='fewer_cleanings'
    primary_optimal:bool=False
    secondary_optimal:bool=False


@dataclass(frozen=True)
class OptionRun(BackendRun):
    option:str='fewer_cleanings'
    recovery:object=None


def _history_constraints(model,variables,orders,config,epoch,quantum,recovery):
    if recovery is None:return
    setup,start,end,wash,presences,arcs,count,slack=variables
    index={o.order_id:i for i,o in enumerate(orders)}
    machines={m.virtual_id:mi for mi,m in enumerate(config.machines)}
    def tick(d):
        value=micros(d-epoch)
        if value%quantum:raise ValueError('Recovery time is off the exact integer lattice.')
        return value//quantum
    fixed=fixed_placements(recovery);ids={p.order_id for p in fixed}
    for i,o in enumerate(orders):
        if o.order_id not in ids:model.add(setup[i]>=tick(recovery.cutoff))
    for p in fixed:
        i,mi=index[p.order_id],machines[p.virtual_id]
        if (mi,i) not in presences:model.add(False);continue
        model.add(presences[mi,i]==1)
        for variable,date in ((setup[i],p.cleaning_start),(start[i],p.process_start),(end[i],p.process_end)):
            model.add(variable==tick(date))
        model.add(wash[i]==int(p.cleaning_required))
    for mid,mi in machines.items():
        prefix=sorted((p for p in fixed if p.virtual_id==mid),key=lambda p:p.cleaning_start)
        previous=None
        for p in prefix:
            i=index[p.order_id]
            edge=arcs[mi].get((previous,i))
            if edge is None:model.add(False)
            else:model.add(edge==1)
            previous=i
        for t in recovery.reference.terminal_cleanups:
            if t.virtual_id==mid and t.start<recovery.cutoff:
                edge=arcs[mi].get((previous,None))
                if edge is None:model.add(False)
                else:model.add(edge==1)


def solve_option(case,option,*,budget_seconds=10):
    if option not in OPTIONS:raise ValueError('Unknown objective option.')
    if isinstance(budget_seconds,bool) or not math.isfinite(budget_seconds) or not 0<budget_seconds<=MAX_BUDGET:
        raise ValueError('Option budget must be positive and at most 60 seconds.')
    check_history(case)
    began=perf_counter();r=case.recovery
    dates=[] if r is None else [r.cutoff]+[d for p in r.reference.placements for d in (p.cleaning_start,p.process_start,p.process_end)]+[d for t in r.reference.terminal_cleanups for d in (t.start,t.end)]
    model,variables,epoch,quantum,horizon=_build(case.orders,case.config,extra_dates=dates)
    _history_constraints(model,variables,case.orders,case.config,epoch,quantum,r)
    *_,count,slack=variables
    if model.validate():raise ValueError('Integrated CP model validation failed.')
    build=perf_counter()-began
    def run(primary,seconds):
        solver=_solver(seconds);started=perf_counter();status=solver.solve(model)
        record={'status':solver.status_name(status),'objective_name':primary,'objective':None,'best_bound':None,
            'objective_unit':'events' if primary=='cleaning' else f'{quantum} microsecond ticks',
            'wall_seconds':perf_counter()-started,'budget_seconds':seconds,'verified':False,'verification_errors':[],
            'relative_gap_limit':0,'absolute_gap_limit':0}
        candidate=None;verified=None;use=None
        if status in (cp_model.FEASIBLE,cp_model.OPTIMAL):
            record.update(objective=solver.value(count if primary=='cleaning' else slack),best_bound=solver.best_objective_bound)
            candidate=_translate(solver,variables,case.orders,case.config,epoch,quantum)
            verified=verify_recovery(case.orders,case.config,candidate,r)
            record['verification_errors']=list(verified.errors)
            if verified.valid:
                use=evaluate_resources(case.orders,case.config,candidate)
                if use.cleaning_events!=solver.value(count):record['verification_errors'].append('Independent cleaning count mismatch.');candidate=None
                elif minimum_slack_ticks(case.orders,candidate,quantum)!=solver.value(slack):record['verification_errors'].append('Independent deadline buffer mismatch.');candidate=None
                else:record['verified']=True
            else:candidate=None
        return record,candidate,verified,use
    a={'status':'NOT_RUN'};b={'status':'NOT_RUN','replacement_accepted':False};selected=None;verified=None;use=None;active=None
    remaining=budget_seconds-(perf_counter()-began)
    first='cleaning' if option=='fewer_cleanings' else 'buffer'
    if remaining>0:
        model.minimize(count) if first=='cleaning' else model.maximize(slack)
        a,selected,verified,use=run(first,remaining*.6)
        if selected is not None:
            active='A';best_count=use.cleaning_events;floor=minimum_slack_ticks(case.orders,selected,quantum)
            a.update(cleaning_count=best_count,minimum_slack_ticks=floor)
            b.update(primary_incumbent=a['objective'],conditional_on_feasible_incumbent=a['status']!='OPTIMAL')
            model.add(slack>=floor)
            if first=='cleaning':model.add(count==best_count);model.maximize(slack)
            else:model.add(count<=best_count);model.minimize(count)
            remaining=budget_seconds-(perf_counter()-began)
            if remaining>0:
                record,candidate,check,resources=run('buffer' if first=='cleaning' else 'cleaning',remaining)
                b.update(record)
                if candidate is not None:
                    buffer=minimum_slack_ticks(case.orders,candidate,quantum)
                    if stage_b_acceptable(option,best_count,floor,resources.cleaning_events,buffer):
                        selected,verified,use,active=candidate,check,resources,'B';b['replacement_accepted']=True
                    else:b['rejection_reason']='Translated second-stage candidate worsened the incumbent; Stage A retained.'
    primary_optimal=a.get('verified',False) and a['status']=='OPTIMAL'
    secondary_optimal=active=='B' and b.get('verified',False) and b['status']=='OPTIMAL'
    result=OptionResult(selected,b['status'] if active=='B' else a['status'],active,a,b,verified,use if selected else None,
        {'total_seconds':perf_counter()-began,'build_seconds':build,'total_budget_seconds':budget_seconds,'workers':1,'seed':20261015},
        {'epoch':epoch.isoformat(),'tick_microseconds':quantum,'horizon_ticks':horizon},
        primary_optimal if first=='cleaning' else False,secondary_optimal if first=='cleaning' else False,
        'No successful EDD construction required.',VERSION,option,primary_optimal,secondary_optimal)
    legacy=plan(case.orders,case.config)
    return OptionRun(selected,'cp_sat' if selected else 'no_verified_schedule',result,legacy,
        digest({'orders':case.orders,'config':case.config}),case.fingerprint,option,r)


def stage_b_acceptable(option,count,buffer,new_count,new_buffer):
    return new_buffer>=buffer and (new_count==count if option=='fewer_cleanings' else new_count<=count)


def run_options(case,*,budget_seconds=10):
    if isinstance(budget_seconds,bool) or not math.isfinite(budget_seconds) or not 0<budget_seconds<=60:raise ValueError('Shared options budget must be positive and at most 60 seconds.')
    # Each option has a bounded two-stage budget; no unbounded repairs/retries.
    return {option:solve_option(case,option,budget_seconds=budget_seconds/2) for option in OPTIONS}
