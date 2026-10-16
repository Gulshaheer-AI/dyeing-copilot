"""Immutable simulated execution history; independent of the optimisation model."""
from dataclasses import dataclass,replace,asdict
from datetime import datetime
from planner.change_requests import digest
from planner.verifier import verify_schedule
from planner.contracts import Verification

ORIGIN='simulated from explicitly selected verified reference; not live factory telemetry'


@dataclass(frozen=True)
class Recovery:
    reference_case_fingerprint:str
    reference_orders:tuple
    reference_config:object
    reference:object
    cutoff:datetime
    origin:str=ORIGIN

    @property
    def fingerprint(self):return digest(self)


def operations(schedule,cutoff):
    rows=[]
    def add(key,kind,order,machine,start,end):
        rows.append({'operation_id':key,'kind':kind,'order_id':order,'machine':machine,'start':start,'end':end,
            'state':'completed' if end<=cutoff else 'running' if start<cutoff else 'future'})
    for p in schedule.placements:
        if p.cleaning_required:add('clean:'+p.order_id,'cleaning',p.order_id,p.virtual_id,p.cleaning_start,p.process_start)
        add('process:'+p.order_id,'processing',p.order_id,p.virtual_id,p.process_start,p.process_end)
    for t in schedule.terminal_cleanups:add('terminal:'+t.virtual_id,'terminal cleaning',None,t.virtual_id,t.start,t.end)
    return tuple(rows)


def fixed_placements(recovery):
    # A started prewash commits its immediately following process too.
    return tuple(p for p in recovery.reference.placements if p.cleaning_start<recovery.cutoff)


def select_reference(case,run,cutoff):
    if not isinstance(cutoff,datetime) or cutoff.tzinfo is not None:raise ValueError('Choose an explicit scenario-local cutoff.')
    if run.case_fingerprint!=case.fingerprint or run.schedule is None or not verify_schedule(case.orders,case.config,run.schedule).valid:
        raise ValueError('Choose the current independently verified schedule as reference.')
    reference=Recovery(case.fingerprint,case.orders,case.config,run.schedule,cutoff)
    return replace(case,recovery=reference,revision=case.revision+1,history=case.history+(
        {'action':'select_simulated_reference','reference_fingerprint':reference.fingerprint,'cutoff':cutoff,'origin':ORIGIN},))


def check_history(case,changes=()):
    r=case.recovery
    if r is None:return
    if not verify_schedule(r.reference_orders,r.reference_config,r.reference).valid:raise ValueError('Reference plan is not verified.')
    fixed={p.order_id:p for p in fixed_placements(r)}
    from copilot.planning_schema import Outage,explicit_datetime
    for c in changes:
        if isinstance(c,Outage):
            start,end=explicit_datetime(c.start),explicit_datetime(c.end)
            spans=[(p.cleaning_start,p.process_end) for p in fixed.values() if p.virtual_id==c.machine_id]
            spans.extend((t.start,t.end) for t in r.reference.terminal_cleanups if t.virtual_id==c.machine_id and t.start<r.cutoff)
            if any(start<b and a<end for a,b in spans):
                raise ValueError('This outage overlaps work preserved from the reference plan. Interrupted-batch recovery is not supported.')
    current={o.order_id:o for o in case.orders}
    if set(current)!={o.order_id for o in r.reference_orders}:raise ValueError('Recovery order identity changed.')
    for o in r.reference_orders:
        c=current[o.order_id]
        if replace(c,deadline=o.deadline)!=o:raise ValueError('Recovery cannot change quantities, releases or processing inputs.')
        if o.order_id in fixed and c.deadline<fixed[o.order_id].process_end:
            raise ValueError('Deadline contradicts completion preserved from the reference plan.')
        if o.order_id not in fixed and c.deadline<r.cutoff:
            raise ValueError('Deadline for unstarted work precedes the simulated cutoff.')
    # No rates, compatibility, initial/terminal rules or permission edits in recovery.
    original=asdict(r.reference_config);current_config=asdict(case.config)
    original.pop('machines');current_config.pop('machines')
    if current_config!=original:raise ValueError('Recovery assumptions changed; choose a new reference explicitly.')
    if {m.virtual_id for m in case.config.machines}!={m.virtual_id for m in r.reference_config.machines}:raise ValueError('Recovery machine identity changed.')
    for machine in case.config.machines:
        old=next((m for m in r.reference_config.machines if m.virtual_id==machine.virtual_id),None)
        if old is None or replace(machine,availability=old.availability)!=old:raise ValueError('Recovery machine assumptions changed.')


def verify_recovery(orders,config,schedule,recovery):
    """Fresh ordinary checks PLUS independent exact-history/adjacency checks."""
    errors=list(verify_schedule(orders,config,schedule).errors)
    if recovery is None:return Verification(tuple(errors))
    from types import SimpleNamespace
    try:check_history(SimpleNamespace(orders=orders,config=config,recovery=recovery))
    except ValueError as exc:errors.append('History/input conflict: '+str(exc))
    if not verify_schedule(recovery.reference_orders,recovery.reference_config,recovery.reference).valid:
        errors.append('Unverified reference history.')
    originals={o.order_id:o for o in recovery.reference_orders}
    if {o.order_id for o in orders}!=set(originals):errors.append('Recovery order identity changed.')
    for order in orders:
        previous=originals.get(order.order_id)
        if previous is not None and replace(order,deadline=previous.deadline)!=previous:
            errors.append('Recovery source inputs changed: '+order.order_id)
    old_by={p.order_id:p for p in recovery.reference.placements}
    new_by={p.order_id:p for p in schedule.placements}
    fixed=fixed_placements(recovery);fixed_ids={p.order_id for p in fixed}
    for p in fixed:
        if new_by.get(p.order_id)!=p:errors.append('Fixed assignment/quantity/timestamps/cleaning changed: '+p.order_id)
    for p in schedule.placements:
        if p.order_id not in fixed_ids and p.cleaning_start<recovery.cutoff:errors.append('Movable work precedes cutoff: '+p.order_id)
    for m in recovery.reference_config.machines:
        original=sorted((p for p in fixed if p.virtual_id==m.virtual_id),key=lambda p:p.cleaning_start)
        revised=sorted((p for p in schedule.placements if p.virtual_id==m.virtual_id),key=lambda p:p.cleaning_start)
        if revised[:len(original)]!=original:errors.append('Fixed predecessor continuity changed on '+m.virtual_id)
    observed={r['operation_id']:r for r in operations(schedule,recovery.cutoff)}
    for op in operations(recovery.reference,recovery.cutoff):
        if op['state']!='future' and observed.get(op['operation_id'])!=op:errors.append('Fixed operation changed: '+op['operation_id'])
    # Started terminal cleanup must remain the final cleanup on its original machine.
    for t in recovery.reference.terminal_cleanups:
        if t.start<recovery.cutoff and t not in schedule.terminal_cleanups:errors.append('Started terminal cleanup changed.')
    return Verification(tuple(errors))


def recovery_summary(case,schedule):
    r=case.recovery
    if not verify_recovery(case.orders,case.config,schedule,r).valid:raise ValueError('Recovery summary requires a verified result.')
    from planner.comparison import deadline_performance
    from planner.evaluator import evaluate_resources
    old={p.order_id:p for p in r.reference.placements};rows=[]
    future={op['order_id'] for op in operations(r.reference,r.cutoff) if op['kind']=='processing' and op['state']=='future'}
    for p in schedule.placements:
        before=old[p.order_id]
        if p.order_id in future and (p.virtual_id,p.process_start,p.process_end)!=(before.virtual_id,before.process_start,before.process_end):
            rows.append({'order':p.order_id,'old_machine':before.virtual_id,'new_machine':p.virtual_id,
                'old_start':before.process_start,'new_start':p.process_start,'old_end':before.process_end,'new_end':p.process_end,
                'completion_difference_seconds':(p.process_end-before.process_end).total_seconds()})
    ops=operations(r.reference,r.cutoff)
    return {'reference_fingerprint':r.fingerprint,'cutoff':r.cutoff,'origin':r.origin,
        'completed_batches_preserved':sum(o['kind']=='processing' and o['state']=='completed' for o in ops),
        'running_batches_protected':sum(o['kind']=='processing' and o['state']=='running' for o in ops),
        'future_batches_changed':len(rows),'changes':rows,
        'changed_definition':'Each future process counted once if machine, process start or process end differs; cleaning-only changes listed separately in operation audit.',
        'on_time_before':deadline_performance(r.reference_orders,r.reference)['on_time'],
        'on_time_after':deadline_performance(case.orders,schedule)['on_time'],
        'cleaning_before':evaluate_resources(r.reference_orders,r.reference_config,r.reference).cleaning_events,
        'cleaning_after':evaluate_resources(case.orders,case.config,schedule).cleaning_events,
        'fixed_operations':[o for o in ops if o['state']!='future'],
        'reference_operation_audit':ops,
        'revised_operation_audit':operations(schedule,r.cutoff),
        'boundary_commitments':[p.order_id for p in fixed_placements(r) if p.process_start>=r.cutoff],
        'reference_boundary':'Reference predates the disruption; it may violate the new outage and is not a current recommendation.'}
