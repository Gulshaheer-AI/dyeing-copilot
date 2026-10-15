"""Joint assignment, adjacency and timing. Independently checked CP-SAT backend.

Original implementation informed by Google's OR-Tools examples; see
reports/cp_sat_model.md for references and modelling differences. No sample code
or sample datasets were copied. Existing verifier/evaluator remain authoritative.
"""

import math
from dataclasses import dataclass
from datetime import timedelta
from functools import reduce
from time import perf_counter

from ortools.sat.python import cp_model

from planner.contracts import Placement, Schedule, TerminalCleanup
from planner.evaluator import evaluate_resources
from planner.scenario import hours, validate_case
from planner.verifier import verify_schedule

VERSION = "cp-sat-dyeing-v2-slack-guard"
DEFAULT_BUDGET = 10.0
MAX_BUDGET = 60.0
SEED = 20261015


def micros(delta):
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def minimum_slack_ticks(orders, schedule, quantum):
    ends = {p.order_id: p.process_end for p in schedule.placements}
    slack_us = min(micros(o.deadline - ends[o.order_id]) for o in orders)
    if slack_us % quantum:
        raise ValueError("Translated deadline slack is off the exact solver lattice.")
    return slack_us // quantum


@dataclass(frozen=True)
class CPSatResult:
    schedule: Schedule | None
    solver_status: str
    active_stage: str | None
    stage_a: dict
    stage_b: dict
    verification: object | None
    resources: object | None
    timing: dict
    scale: dict
    cleaning_optimal: bool
    slack_optimal_at_fixed_count: bool
    hint: str
    version: str = VERSION


def _build(orders, config):
    validate_case(orders, config)
    if len(orders) > 200 or len(config.machines) > 32 or sum(len(m.availability) for m in config.machines) > 2000:
        raise ValueError("CP-SAT v1 supports at most 200 orders, 32 machines and 2000 availability windows.")
    dates = [d for o in orders for d in (o.release, o.deadline)] + [d for m in config.machines for w in m.availability for d in (w.start,w.end)]
    epoch = min(dates)
    offsets = [micros(d-epoch) for d in dates]
    durations = [micros(hours(o.duration_source*config.hours_per_duration_unit)) for o in orders]
    cleaning = micros(hours(config.cleaning_hours))
    quantum = reduce(math.gcd, offsets + durations + [cleaning])
    horizon = max(offsets)//quantum
    if horizon > 2**50 or max(durations + [cleaning])//quantum > 2**50:
        raise ValueError("Unsupported exact time range: scaled horizon/duration exceeds conservative 2^50 tick limit; no rounding applied.")
    def tick(date):
        return micros(date-epoch)//quantum
    model = cp_model.CpModel()
    setup, start, end, wash = {}, {}, {}, {}
    for i,o in enumerate(orders):
        setup[i] = model.new_int_var(tick(o.release),tick(o.deadline),f"setup_{i}")
        start[i] = model.new_int_var(tick(o.release),tick(o.deadline),f"start_{i}")
        end[i] = model.new_int_var(tick(o.release),tick(o.deadline),f"end_{i}")
        wash[i] = model.new_bool_var(f"wash_{i}")
        model.add(start[i] == setup[i] + cleaning//quantum*wash[i])
        model.add(end[i] == start[i]+durations[i]//quantum)
    assigned = {i: [] for i in range(len(orders))}
    presences, arcs_by_machine, used = {}, {}, []
    permissions = {(p.virtual_id,p.from_order_id,p.to_order_id) for p in config.transition_permissions}
    for mi,machine in enumerate(config.machines):
        candidates = [i for i,o in enumerate(orders) if (o.vessel,o.fabric) in machine.compatible_pairs and o.quantity <= machine.capacity and machine.availability]
        empty = model.new_bool_var(f"unused_{mi}")
        used.append(empty.Not())
        arcs, saved, intervals = [(0,0,empty)], {}, []
        for i in candidates:
            p = model.new_bool_var(f"assigned_{mi}_{i}")
            presences[mi,i] = p
            assigned[i].append(p)
            arcs.append((i+1,i+1,p.Not()))
            first, last = model.new_bool_var(f"first_{mi}_{i}"),model.new_bool_var(f"last_{mi}_{i}")
            saved[None,i],saved[i,None] = first,last
            arcs.extend([(0,i+1,first),(i+1,0,last)])
            model.add_implication(first,p); model.add_implication(last,p)
            model.add(wash[i] == int(not machine.initially_clean)).only_enforce_if(first)
            intervals.append(model.new_optional_interval_var(setup[i],durations[i]//quantum+cleaning//quantum*wash[i],end[i],p,f"block_{mi}_{i}"))
            windows = []
            for wi,w in enumerate(machine.availability):
                inside = model.new_bool_var(f"window_{mi}_{i}_{wi}")
                windows.append(inside)
                model.add(setup[i] >= tick(w.start)).only_enforce_if(inside)
                model.add(end[i] <= tick(w.end)).only_enforce_if(inside)
            model.add(sum(windows) == p)
            if config.terminal_cleaning:
                endings = []
                for wi,w in enumerate(machine.availability):
                    inside = model.new_bool_var(f"terminal_window_{mi}_{i}_{wi}")
                    endings.append(inside)
                    model.add(end[i] >= tick(w.start)).only_enforce_if(inside)
                    model.add(end[i]+cleaning//quantum <= tick(w.end)).only_enforce_if(inside)
                model.add(sum(endings) == last)
        model.add(sum(presences[mi,i] for i in candidates) == 0).only_enforce_if(empty)
        model.add(sum(presences[mi,i] for i in candidates) >= 1).only_enforce_if(empty.Not())
        for i in candidates:
            for j in candidates:
                if i == j:
                    continue
                follows = model.new_bool_var(f"arc_{mi}_{i}_{j}")
                saved[i,j] = follows
                arcs.append((i+1,j+1,follows))
                model.add_implication(follows,presences[mi,i]);model.add_implication(follows,presences[mi,j])
                model.add(setup[j] >= end[i]).only_enforce_if(follows)
                exempt = config.allow_cleaning_exemptions and (machine.virtual_id,orders[i].order_id,orders[j].order_id) in permissions
                model.add(wash[j] == int(not exempt)).only_enforce_if(follows)
        model.add_circuit(arcs)
        model.add_no_overlap(intervals)
        arcs_by_machine[mi] = saved
    for ps in assigned.values():
        model.add(sum(ps) == 1)  # Empty compatible/capable set encodes infeasibility.
    count = model.new_int_var(0,len(orders)+len(config.machines),"cleaning_count")
    model.add(count == sum(wash.values()) + (sum(used) if config.terminal_cleaning else 0))
    slack = model.new_int_var(0,horizon,"minimum_deadline_slack")
    model.add_min_equality(slack,[tick(o.deadline)-end[i] for i,o in enumerate(orders)])
    return model, (setup,start,end,wash,presences,arcs_by_machine,count,slack), epoch, quantum, horizon


def _translate(solver, variables, orders, config, epoch, quantum):
    setup,start,end,wash,presences,arcs,_,_ = variables
    def date(v):
        return epoch+timedelta(microseconds=solver.value(v)*quantum)
    placements, terminal = [], []
    for (mi,i),p in presences.items():
        if not solver.boolean_value(p):
            continue
        machine,order = config.machines[mi],orders[i]
        placements.append(Placement(order.order_id,order.quantity,machine.virtual_id,date(setup[i]),date(start[i]),date(end[i]),solver.boolean_value(wash[i])))
        if config.terminal_cleaning and solver.boolean_value(arcs[mi][i,None]):
            terminal.append(TerminalCleanup(machine.virtual_id,date(end[i]),date(end[i])+hours(config.cleaning_hours)))
    return Schedule(tuple(sorted(placements,key=lambda p:(p.virtual_id,p.cleaning_start))),tuple(sorted(terminal,key=lambda t:t.virtual_id)))


def _solver(seconds):
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = SEED
    solver.parameters.relative_gap_limit = 0
    solver.parameters.absolute_gap_limit = 0
    return solver


def solve(orders, config, *, budget_seconds=DEFAULT_BUDGET, incumbent=None):
    if isinstance(budget_seconds,bool) or not math.isfinite(budget_seconds) or not 0 < budget_seconds <= MAX_BUDGET:
        raise ValueError(f"CP-SAT total budget must be positive and at most {MAX_BUDGET} seconds.")
    began = perf_counter()
    model,variables,epoch,quantum,horizon = _build(orders,config)
    setup,start,end,wash,presences,arcs,count,slack = variables
    hint = "not supplied"
    if incumbent is not None:
        check = verify_schedule(orders,config,incumbent)
        if check.valid and all(micros(d-epoch)%quantum == 0 for p in incumbent.placements for d in (p.cleaning_start,p.process_start,p.process_end)):
            indexed = {o.order_id:i for i,o in enumerate(orders)}
            by_id = {p.order_id:p for p in incumbent.placements}
            for i,o in enumerate(orders):
                p = by_id[o.order_id]
                for v,d in ((setup[i],p.cleaning_start),(start[i],p.process_start),(end[i],p.process_end)):
                    model.add_hint(v,micros(d-epoch)//quantum)
                model.add_hint(wash[i],int(p.cleaning_required))
            for (mi,i),p in presences.items():
                model.add_hint(p,int(by_id[orders[i].order_id].virtual_id == config.machines[mi].virtual_id))
            # A verified feasible upper bound excludes no better cleaning solution.
            model.add(count <= evaluate_resources(orders,config,incumbent).cleaning_events)
            hint = "verified heuristic assignment/time hint and feasible cleaning upper bound"
        else:
            hint = "ignored: invalid or off-grid incumbent; never required for construction"
    validation = model.validate()
    if validation:
        raise ValueError("CP-SAT model rejected before solve: "+validation)
    build_seconds = perf_counter()-began
    stage_a,stage_b = {"status":"NOT_RUN"},{"status":"NOT_RUN"}
    selected,verification,resource,active = None,None,None,None

    def run(stage,remaining):
        solver = _solver(remaining)
        t = perf_counter(); status = solver.solve(model); elapsed = perf_counter()-t
        record = {"status":solver.status_name(status),"wall_seconds":elapsed,"budget_seconds":remaining,
            "objective":None,"best_bound":None,"verified":False,"verification_errors":[],
            "relative_gap_limit":0,"absolute_gap_limit":0}
        candidate,check,use = None,None,None
        if status in (cp_model.FEASIBLE,cp_model.OPTIMAL):
            record["objective"] = solver.value(count if stage == "A" else slack)
            record["best_bound"] = solver.best_objective_bound
            candidate = _translate(solver,variables,orders,config,epoch,quantum)
            check = verify_schedule(orders,config,candidate)
            record["verification_errors"] = list(check.errors)
            if check.valid:
                use = evaluate_resources(orders,config,candidate)
                if use.cleaning_events != solver.value(count):
                    record["verification_errors"] = ["Solver objective and independent event count differ."]
                    candidate = None
                else:
                    record["verified"] = True
            else:
                candidate = None
        elif status == cp_model.INFEASIBLE:
            record["best_bound"] = None
        # UNKNOWN, MODEL_INVALID and NOT_RUN are never described as infeasible.
        return record,candidate,check,use

    remaining = budget_seconds-(perf_counter()-began)
    if remaining > 0:
        model.minimize(count)
        stage_a,selected,verification,resource = run("A",remaining*0.6)
        if selected is not None:
            active = "A"
            best_count = resource.cleaning_events
            incumbent_slack = minimum_slack_ticks(orders, selected, quantum)
            stage_a["minimum_slack_ticks"] = incumbent_slack
            stage_b = {"status":"NOT_RUN", "fixed_cleaning_count":best_count,
                "minimum_slack_floor_ticks":incumbent_slack,"replacement_accepted":False,
                "conditional_on_feasible_incumbent":stage_a["status"] != "OPTIMAL"}
            remaining = budget_seconds-(perf_counter()-began)
            if remaining > 0:
                model.add(count == best_count)
                model.add(slack >= incumbent_slack)
                model.clear_hints()
                model.maximize(slack)
                record,candidate,check,use = run("B",remaining)
                stage_b.update(record)
                if candidate is not None:
                    translated_slack = minimum_slack_ticks(orders, candidate, quantum)
                    stage_b["minimum_slack_ticks"] = translated_slack
                    # Verification alone does not establish incumbent quality.
                    if use.cleaning_events == best_count and translated_slack >= incumbent_slack:
                        selected,verification,resource,active = candidate,check,use,"B"
                        stage_b["replacement_accepted"] = True
                    else:
                        stage_b["rejection_reason"] = "Translated candidate worsens Stage-A slack or changes its cleaning count; Stage A retained."
    if selected is None:
        resource = None
    return CPSatResult(selected,stage_b["status"] if active == "B" else stage_a["status"],active,
        stage_a,stage_b,verification,resource,{"total_seconds":perf_counter()-began,"build_seconds":build_seconds,
        "total_budget_seconds":budget_seconds,"workers":1,"seed":SEED},
        {"epoch":epoch.isoformat(),"tick_microseconds":quantum,"horizon_ticks":horizon},
        stage_a.get("verified",False) and stage_a["status"] == "OPTIMAL",
        active == "B" and stage_b.get("verified",False) and stage_b["status"] == "OPTIMAL",hint)
