"""Read-only timeline and comparison transformations for verified schedules."""
from datetime import timedelta
import pandas as pd
from planner.change_requests import digest
from planner.comparison import compare_schedules
from planner.verifier import verify_schedule


def machine_name(identifier):
    parts=identifier.removeprefix('virtual-').split('-')
    return ' — '.join(parts)


def current_comparison(case,run):
    if (run.case_fingerprint!=case.fingerprint or
            run.effective_fingerprint!=digest({'orders':case.orders,'config':case.config})):
        raise ValueError('This result belongs to a previous plan. Generate a current schedule.')
    from planner.recovery import verify_recovery
    if run.schedule is None or not verify_recovery(case.orders,case.config,run.schedule,case.recovery).valid:
        raise ValueError('A current independently verified schedule is required.')
    if case.recovery is not None:return None
    baseline=run.legacy.baseline if run.legacy is not None else None
    if baseline is None or not verify_schedule(case.orders,case.config,baseline).valid:return None
    return compare_schedules(case.orders,case.config,baseline,run.schedule)


def timeline_rows(orders,config,schedule):
    """Keep exact exported datetimes; grey blocks are complements of availability."""
    if not verify_schedule(orders,config,schedule).valid:
        raise ValueError('Cannot display an unverified schedule as current.')
    starts=[p.cleaning_start for p in schedule.placements]
    ends=[p.process_end for p in schedule.placements]+[t.end for t in schedule.terminal_cleanups]
    lo,hi=min(starts),max(ends)
    rows=[]
    def add(machine,order,kind,start,end,label):
        if end>start:rows.append({'machine_id':machine,'machine':machine_name(machine),
            'order_id':order,'activity':kind,'start':start,'end':end,'label':label})
    for p in schedule.placements:
        if p.cleaning_required:add(p.virtual_id,p.order_id,'Cleaning',p.cleaning_start,p.process_start,'')
        add(p.virtual_id,p.order_id,'Production',p.process_start,p.process_end,'#'+p.order_id)
    for t in schedule.terminal_cleanups:
        add(t.virtual_id,None,'Terminal cleaning',t.start,t.end,'')
    for m in config.machines:
        cursor=lo
        for w in sorted(m.availability,key=lambda w:w.start):
            start,end=max(lo,w.start),min(hi,w.end)
            if end<=start:continue
            if start>cursor:add(m.virtual_id,None,'Unavailable',cursor,start,'')
            cursor=max(cursor,end)
        if cursor<hi:add(m.virtual_id,None,'Unavailable',cursor,hi,'')
    return pd.DataFrame(rows),lo,hi


def clip_timeline(frame,start,end,machines):
    """Clip only drawn edges; retain original timestamps for hover and auditing."""
    if end<=start:raise ValueError('Choose an end after the start.')
    visible=frame[frame.machine_id.isin(machines)&(frame.end>start)&(frame.start<end)].copy()
    visible['visible_start']=visible.start.clip(lower=start)
    visible['visible_end']=visible.end.clip(upper=end)
    return visible


def recovery_timeline_rows(case,schedule,*,reference=False):
    from planner.recovery import verify_recovery
    from planner.change_requests import subtract_interval
    if not verify_recovery(case.orders,case.config,schedule,case.recovery).valid:
        raise ValueError('Recovery history verification failed; timeline is unavailable.')
    r=case.recovery
    if r is None:return timeline_rows(case.orders,case.config,schedule)
    frame,lo,hi=timeline_rows(r.reference_orders,r.reference_config,r.reference) if reference else timeline_rows(case.orders,case.config,schedule)
    lo=min(lo,r.cutoff);hi=max(hi,r.cutoff+timedelta(microseconds=1))
    outages=[]
    for old in r.reference_config.machines:
        remaining=old.availability
        new=next(m for m in case.config.machines if m.virtual_id==old.virtual_id)
        for w in new.availability:remaining=subtract_interval(remaining,w.start,w.end)
        for w in remaining:
            if w.start<hi and w.end>lo:
                outages.append({'machine_id':old.virtual_id,'machine':machine_name(old.virtual_id),'order_id':None,
                    'activity':'Revised outage','start':w.start,'end':w.end,'label':''})
    if outages:frame=pd.concat([frame,pd.DataFrame(outages)],ignore_index=True)
    return frame,lo,hi


def useful_window(frame,lo,hi,machines):
    activity=frame[(frame.activity!='Unavailable')&frame.machine_id.isin(machines)]
    start=activity.start.min().to_pydatetime() if not activity.empty else lo
    return start,min(hi,start+timedelta(hours=24))


def result_summary(baseline_count,proposed_count,on_time,total):
    if baseline_count is None:change='Verified plan ready. Baseline comparison unavailable.'
    else:
        difference=baseline_count-proposed_count
        change=(f'{abs(difference)} {"fewer" if difference>0 else "more"} cleaning{"s" if abs(difference)!=1 else ""}.'
            if difference else 'No change in cleaning count.')
    delivery=f'All {total} orders on time.' if on_time==total else f'{on_time} of {total} orders on time.'
    return change+' '+delivery


def shift_day(start,lo,hi,offset):
    """Clamp day navigation without changing underlying event timestamps."""
    return min(max(start+timedelta(days=offset),lo),max(lo,hi-timedelta(microseconds=1)))
