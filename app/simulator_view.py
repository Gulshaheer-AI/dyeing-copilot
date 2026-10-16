"""UI for a complete-case, explicitly configured illustrative simulator."""

import hashlib
import json
from dataclasses import asdict, replace
from decimal import Decimal

import pandas as pd
import streamlit as st

from planner.evaluator import evaluate_resources
from planner.backend import CP_ENGINE, LEGACY_ENGINE, run_backend
from planner.cp_sat import VERSION as CP_VERSION
from app.cp_sat_view import render_cp_result
from planner.change_requests import digest
from planner.scenario import demo_config, orders_from_import, parse_config, to_json, validate_case
from planner.search import plan
from planner.comparison import RULE_LABELS, compare_schedules
from planner.review_package import export_review_package
from planner.change_export import export_change_audit
from app.planning_changes_view import prepare_case, render_planning_changes


def _show_schedule(label, schedule, config, verification):
    st.subheader(label)
    if verification.valid:
        st.success("PASS — scenario-based completeness, quantity, capacity, compatibility, timing and cleaning checks.")
    else:
        st.error("FAIL — this schedule is not a valid proposal.")
        for error in verification.errors:
            st.write(error)
    placements = sorted(schedule.placements, key=lambda p: (p.virtual_id, p.cleaning_start))
    st.dataframe(pd.DataFrame([asdict(p) for p in placements]), hide_index=True, width="stretch")
    events = [{"virtual_id": p.virtual_id, "order_id": p.order_id, "event": "before order",
               "start": p.cleaning_start, "end": p.process_start, "modelled_source_units": config.cleaning_water}
              for p in placements if p.cleaning_required]
    events.extend({"virtual_id": t.virtual_id, "order_id": None, "event": "terminal cleaning",
                   "start": t.start, "end": t.end, "modelled_source_units": config.cleaning_water}
                  for t in schedule.terminal_cleanups)
    st.caption("Cleaning events, including final-machine cleanup. These are simulated, not recorded events.")
    st.dataframe(pd.DataFrame(events, columns=["virtual_id", "order_id", "event", "start", "end", "modelled_source_units"]),
                 hide_index=True, width="stretch")


def render_legacy_simulator(result):
    st.subheader("Scheduling simulator")
    st.warning("Illustrative scenario · virtual machines and assumed cleaning rules · not production approval or factory savings.")
    st.caption("Load orders → review machines and cleaning rules → run comparison → inspect changes → review and export")
    st.subheader("1. Load orders")
    st.write(f"Loaded {len(result.records)} validated orders from {result.filename}. Planning uses the complete case.")
    if st.button("Review imported orders"):
        st.session_state.pending_view = "Orders"
        st.rerun()
    recorded = sum((Decimal(r["water_total_source"]) for r in result.records), Decimal(0))
    st.metric("Recorded source total — separate reference only", f"{recorded:,f}")
    with st.expander("Methodology, provenance and limits"):
        st.write("Both schedules use the same resource formula and assumptions. The recorded total is a separate reference, "
                 "never the baseline for the scenario difference. Descriptive filters do not reduce the planning case. "
                 "Source quantity/duration/water units remain unresolved. Times are Asia/Karachi scenario local time. "
                 "Recipe and quality compatibility are not established. Colour alone grants no cleaning exemption. "
                 "The independent verifier checks both schedules; the search does not establish global optimality. "
                 "See reports/scenario_model.md for equations and source_rule_audit.md for source limitations.")
    st.subheader("2. Review machines and cleaning rules")
    if st.session_state.get("sim_source") != result.sha256:
        st.session_state.sim_source = result.sha256
        st.session_state.sim_config = ""
        st.session_state.sim_permission = False
        st.session_state.sim_saved_config = ""
        st.session_state.sim_saved_permission = False
        st.session_state.pop("sim_comparison", None)
    # Non-widget copies survive switching to Copilot; model code never writes these.
    if "sim_config" not in st.session_state:
        st.session_state.sim_config = st.session_state.get("sim_saved_config", "")
    if "sim_permission" not in st.session_state:
        st.session_state.sim_permission = st.session_state.get("sim_saved_permission", False)
    if st.button("Load demo setup"):
        st.session_state.sim_config = to_json(demo_config(result))
        st.session_state.sim_permission = False
        st.session_state.pop("sim_comparison", None)
    with st.expander("Edit illustrative scenario configuration"):
        text = st.text_area("Scenario configuration (editable JSON)", key="sim_config", height=350)
    permitted = st.checkbox("Explicitly permit the listed cleaning exemptions for this illustrative scenario; "
                            "recipe and quality compatibility are assumed, not verified.", key="sim_permission")
    st.session_state.sim_saved_config = text
    st.session_state.sim_saved_permission = permitted
    st.session_state.sim_context = {"source_sha256": result.sha256, "config": None, "comparison": None,
        "marker": hashlib.sha256((text + str(permitted)).encode()).hexdigest()}
    st.caption("This checkbox controls the effective allow_cleaning_exemptions flag. Without activation, all "
               "between-order transitions require cleaning. It grants no real factory approval. "
               "Edit machines, windows, capacity, rates and exact directed permissions in the JSON. "
               "See reports/scenario_model.md for equations and the configuration contract.")
    if "planning_backend" not in st.session_state:
        st.session_state.planning_backend = st.session_state.get("saved_backend_engine", CP_ENGINE)
    engine = st.session_state.planning_backend
    st.session_state.saved_backend_engine = engine
    budget = 10.0
    fallback = False
    if engine == CP_ENGINE:
        with st.expander("CP-SAT solve budget and explicit fallback"):
            budget = st.number_input("Total CP-SAT budget (seconds)", min_value=0.01, max_value=60.0, value=st.session_state.get("saved_cp_budget", 10.0), step=1.0)
            fallback = st.checkbox("Explicitly allow labelled heuristic fallback if CP-SAT has no verified schedule", value=st.session_state.get("saved_cp_fallback", False))
        st.session_state.saved_cp_budget = budget
        st.session_state.saved_cp_fallback = fallback
    backend_settings = digest({"engine": engine, "budget": budget, "fallback": fallback,
                             "solver_version": CP_VERSION if engine==CP_ENGINE else "legacy-v1"})
    if st.session_state.get("selected_backend_settings") != backend_settings:
        st.session_state.selected_backend_settings = backend_settings
        st.session_state.pop("copilot_answer", None)
    if not text.strip():
        st.info("Load demo setup or enter a complete configuration. No planning is run automatically.")
        return
    try:
        config = replace(parse_config(text), allow_cleaning_exemptions=permitted)
        orders = orders_from_import(result)
        validate_case(orders, config)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        st.error(f"Invalid scenario configuration: {exc}")
        return
    case = render_planning_changes(prepare_case(result, config))
    config, orders = case.config, case.orders
    st.caption("Effective assumptions — inspect before planning")
    st.dataframe(pd.DataFrame([{"Virtual machine": m.virtual_id,
        "Compatible vessel / fabric": "; ".join(" / ".join(pair) for pair in m.compatible_pairs),
        "Capacity (source quantity unit)": str(m.capacity), "Initially clean": m.initially_clean,
        "Operating availability": "; ".join(f"{w.start} to {w.end}" for w in m.availability) or "No available windows — closed in this scenario"}
        for m in config.machines]), hide_index=True, width="stretch")
    st.write(f"Assumed duration: {config.hours_per_duration_unit} hour(s) per source duration unit. "
             f"Each required cleaning: {config.cleaning_hours} hour(s), {config.cleaning_water} modelled source units. "
             f"Terminal cleaning: {config.terminal_cleaning}. Cleaning exemptions active: {config.allow_cleaning_exemptions}. "
             f"Listed directed permissions: {len(config.transition_permissions)}.")
    st.caption(f"Assumed process rates per source quantity unit: A = {config.process_a_per_quantity}, B = {config.process_b_per_quantity}. "
               "Initial cleaning state and availability are listed above; no actual factory machines are represented.")
    with st.expander("Full effective assumptions and exact cleaning permissions (review before running)"):
        st.json(to_json(config))
    st.info("Capacity and timing checks are scenario-based. Duration is interpreted using the displayed "
            "hours_per_duration_unit; this does not establish the source duration unit. No order is split or merged.")
    signature = case.fingerprint
    st.session_state.sim_context["config"] = config
    st.session_state.sim_context["case"] = case
    st.session_state.sim_context["marker"] = signature
    st.subheader("3. Run comparison")
    if st.button("Run scenario comparison"):
        try:
            with st.spinner("Constructing and independently checking scenario schedules…"):
                comparison = plan(orders, config)
            st.session_state.sim_comparison = (signature, comparison)
            st.session_state.pop("sim_cp_result", None)
        except (ValueError, OverflowError) as exc:
            st.error(f"Cannot simulate this configuration: {exc}")
            st.session_state.pop("sim_comparison", None)
    stored = st.session_state.get("sim_comparison")
    if not stored or stored[0] != signature:
        st.caption("Run the comparison after reviewing these assumptions. Configuration changes invalidate previous results.")
        return
    comparison = stored[1]
    st.session_state.sim_context["comparison"] = comparison if comparison.proposal is not None else None
    if case.history:
        try:
            st.download_button("Export change request audit (JSON)", export_change_audit(result, case, comparison),
                file_name="planning_change_request_audit.json", mime="application/json")
        except ValueError as exc:
            st.error(str(exc))
    if engine == CP_ENGINE:
        backend_marker = digest({"scenario": signature, "settings": backend_settings})
        st.session_state.sim_context["marker"] = backend_marker
        st.session_state.sim_context["comparison"] = None
        st.session_state.sim_context["backend_block_reason"] = "Selected CP-SAT engine: legacy EDD/proposal explanation contract is disabled."
        cached = st.session_state.get("sim_cp_result")
        if not cached or cached[0] != backend_marker or getattr(getattr(cached[1],'cp_sat',None),'version',None) != CP_VERSION:
            try:
                with st.spinner("Solving CP-SAT stages and independently verifying the selected result..."):
                    run = run_backend(orders, config, engine=engine, budget_seconds=budget, legacy=comparison, allow_fallback=fallback, case_fingerprint=signature)
            except (ValueError, OverflowError) as exc:
                st.error(f"CP-SAT cannot model this input: {exc}. No infeasibility or CP-SAT success is claimed. Explicitly select the legacy engine if appropriate.")
                return
            st.session_state.sim_cp_result = (backend_marker, run)
        else:
            run = cached[1]
        st.session_state.sim_context['selected_run'] = run if run.schedule is not None else None
        render_cp_result(case, run, _show_schedule, source=result, context_marker=backend_marker)
        return
    st.subheader("4. What changed?")
    st.caption("Selected engine: legacy heuristic (explicit fallback), not a CP-SAT result. Benchmark EDD/grouping controls are offline only.")
    if comparison.proposal is None:
        st.error("No feasible baseline was found by the earliest-deadline construction. No resource comparison "
                 "or recommendation is available. This heuristic failure is not a proof that every possible schedule is infeasible.")
        for error in comparison.construction_errors:
            st.write(error)
        _show_schedule("Incomplete baseline construction — not a recommendation", comparison.baseline,
                       config, comparison.baseline_verification)
        previous = st.session_state.get("planning_last_success")
        if previous and previous[0].fingerprint != case.fingerprint:
            with st.expander("Last successful schedule — previous scenario, not valid for these revised constraints"):
                old_case, old_comparison = previous
                st.caption("Previous scenario fingerprint: " + old_case.fingerprint)
                st.caption("This retained schedule has not passed the revised deadlines/availability and is not a current recommendation.")
                st.dataframe(pd.DataFrame([asdict(p) for p in old_comparison.proposal.placements]), hide_index=True)
        return
    try:
        changes = compare_schedules(orders, config, comparison.baseline, comparison.proposal)
    except ValueError as exc:
        st.error(str(exc))
        st.session_state.sim_context["comparison"] = None
        return
    st.session_state.planning_last_success = (case, comparison)
    # Independent fresh accounting, rather than trusting cached planner summaries.
    before = evaluate_resources(orders, config, comparison.baseline)
    after = evaluate_resources(orders, config, comparison.proposal)
    with st.expander("EDD comparison resource detail: hypothetical modelled source units"):
        columns = st.columns(3)
        columns[0].metric("Recalculated baseline (modelled source units)", f"{before.total:,f}")
        columns[1].metric("Recalculated proposal (modelled source units)", f"{after.total:,f}")
        columns[2].metric("Scenario reduction (modelled source units)", f"{changes['difference']:,f}")
        percentage = changes["percentage_difference"]
        st.metric("Difference / recalculated baseline", f"{percentage:.4f}%" if percentage is not None else "Undefined (zero baseline)")
        if changes["difference"] == 0:
            st.info("No improvement found: proposal equals the baseline under these assumptions.")
        st.caption(f"Checked {comparison.candidates_checked} candidate priorities using category grouping and "
                   "up to three passes of pairwise swaps. Global optimality is not claimed for the full case.")
        st.dataframe(pd.DataFrame([
            {"scenario": label, **asdict(use), "total": use.total}
            for label, use in (("baseline", before), ("proposal", after))
        ]), hide_index=True, width="stretch")
    st.caption(f"Cleaning events: baseline {sum(p.cleaning_required for p in comparison.baseline.placements) + len(comparison.baseline.terminal_cleanups)}; "
               f"proposal {sum(p.cleaning_required for p in comparison.proposal.placements) + len(comparison.proposal.terminal_cleanups)}. "
               "Includes initial and terminal cleaning under these assumptions.")
    st.dataframe(pd.DataFrame([{"Schedule": label, **count} for label, count in changes["cleaning_counts"].items()]), hide_index=True)
    st.subheader("Deadline performance")
    st.caption("Scenario deadlines compare process completion with the configured delivery-date boundary; terminal cleanup is checked separately.")
    st.dataframe(pd.DataFrame([{"Schedule": label, **{k: v for k, v in data.items() if k != "orders"}}
                              for label, data in changes["deadlines"].items()]), hide_index=True)
    st.write(f"Changed machine assignments: {changes['changes']['machine_assignments']}; "
             f"sequence positions: {changes['changes']['sequence_positions']}; "
             f"predecessors: {changes['changes']['predecessors']}; "
             f"order cleaning requirements: {changes['changes']['cleaning_requirements']}; "
             f"timings: {changes['changes']['timings']}.")
    with st.expander("All EDD machine sequences and changed transitions"):
        st.dataframe(pd.DataFrame([{"Virtual machine": machine,
            "Baseline order sequence": " → ".join(sequence),
            "Proposed order sequence": " → ".join(changes["machine_sequences"]["proposal"][machine])}
            for machine, sequence in changes["machine_sequences"]["baseline"].items()]), hide_index=True, width="stretch")
        transitions = []
        for row in changes["order_transitions"]:
            if row["transition_changed"]:
                transitions.append({"Order": row["order_id"], **{f"{side} {key}": RULE_LABELS[row[side][key]] if key == "rule" else row[side][key]
                    for side in ("baseline", "proposal") for key in ("machine", "position", "predecessor", "cleaning_required", "rule")},
                    "Cleaning event difference": row["cleaning_events_difference"], "Modelled resource difference": row["resource_difference"]})
        if transitions:
            st.dataframe(pd.DataFrame(transitions), hide_index=True, width="stretch")
        else:
            st.info("No machine, sequence or predecessor cleaning transitions changed.")
        st.caption("Rule labels describe configured initial state or activated exact directed permissions; they do not establish colour or recipe compatibility.")
    with st.expander("All transitions, terminal cleanup, machine sequences and deadline detail"):
        st.json(changes)
    st.success("Transition accounting reconciles with both resource totals, including initial and terminal cleaning.")
    st.subheader("5. Review and export")
    st.caption("Review capacity, calendars, durations, initial/terminal rules and documented recipe/quality permissions with factory specialists. "
               "Supervisor acceptance is acceptance for further review, never production approval.")
    if st.button("Explain this comparison with AMD copilot"):
        st.session_state.copilot_requested_topic = "Explain this schedule comparison"
        st.session_state.pending_view = "Copilot"
        st.rerun()
    _show_schedule("Baseline: earliest deadline with stable source-row-ID ties", comparison.baseline,
                   config, comparison.baseline_verification)
    _show_schedule("Proposed scenario schedule", comparison.proposal, config, comparison.proposal_verification)
    # Export re-verifies both artifacts and recalculates both resource summaries.
    try:
        exported = to_json({**json.loads(export_review_package(result, config, comparison, case=case)),
                            "backend_origin": "legacy_heuristic_explicit_fallback"})
    except ValueError as exc:
        st.error(str(exc))
        return
    st.download_button("Export planner review package (JSON)", exported,
                       file_name="dyeing_planner_review_package.json", mime="application/json",
                       help="Planner review package: both schedules, assumptions, all transition changes and fresh verification; not production approval.")


def render_simulator(result):
    """Production planner: existing engine, explicit generation and cached results."""
    from app.planner_presentation import machine_name
    from app.dashboard_style import context_note
    context_note('Published orders · Illustrative machines and cleaning rules')
    if st.session_state.get('sim_source')!=result.sha256:
        st.session_state.sim_source=result.sha256
        for key in ('sim_config','sim_saved_config','sim_comparison','sim_cp_result','selected_answer','selected_failure'):
            st.session_state.pop(key,None)
        st.session_state.sim_permission=False
        st.session_state.sim_saved_permission=False
        st.session_state.integrated_mode=False
        st.session_state.pop('integrated_options',None)
    if 'sim_config' not in st.session_state:st.session_state.sim_config=st.session_state.get('sim_saved_config','')
    if 'sim_permission' not in st.session_state:st.session_state.sim_permission=st.session_state.get('sim_saved_permission',False)
    if 'planning_backend' not in st.session_state:st.session_state.planning_backend=st.session_state.get('saved_backend_engine',CP_ENGINE)
    # Legacy workflow remains explicitly available, without comparator controls in the main planner.
    with st.sidebar.expander('Planning engine and technical settings'):
        engine=st.selectbox('Planning engine',[CP_ENGINE,LEGACY_ENGINE],key='planning_backend')
        budget=st.number_input('Total CP-SAT budget (seconds)',min_value=0.01,max_value=60.0,
            value=st.session_state.get('saved_cp_budget',10.0),step=1.0)
        fallback=st.checkbox('Explicitly allow labelled heuristic fallback if CP-SAT has no verified schedule',
            value=st.session_state.get('saved_cp_fallback',False))
    st.session_state.saved_backend_engine=engine
    st.session_state.saved_cp_budget=budget
    st.session_state.saved_cp_fallback=fallback
    if engine==LEGACY_ENGINE:
        current=st.session_state.get('planning_case')
        if current is not None and current.source_sha256==result.sha256 and current.recovery is not None:
            reason='Execution-aware recovery requires CP-SAT. The legacy engine does not preserve simulated execution history; switch back to CP-SAT or reset the original scenario.'
            st.session_state.sim_context={'source_sha256':result.sha256,'config':current.config,'case':current,
                'marker':digest({'case':current.fingerprint,'blocked_engine':engine}),
                'comparison':None,'selected_run':None,'backend_block_reason':reason}
            st.error(reason)
            with st.expander('Reset or inspect constraint requests'):
                render_planning_changes(current)
            return
        render_legacy_simulator(result)
        return
    settings=digest({'engine':engine,'budget':budget,'fallback':fallback,'solver_version':CP_VERSION})
    st.session_state.selected_backend_settings=settings
    setup=st.sidebar if st.session_state.get('sim_comparison') else st
    with setup.container(key='dashboard_setup' if setup is st else 'sidebar_setup'):
        if setup is st:
            from app.dashboard_style import panel_heading
            panel_heading('Build your dyeing production plan',f'{len(result.records)} published orders are ready. Load the demo machines and review the cleaning rules to begin.')
        with setup.expander('Machines and cleaning rules',expanded=not bool(st.session_state.get('sim_comparison'))):
            if setup is not st:st.metric('Orders to schedule',len(result.records))
            if st.button('Load demo setup',icon=':material/settings:',type='primary' if not st.session_state.sim_config.strip() else 'secondary'):
                st.session_state.sim_config=to_json(demo_config(result))
                st.session_state.sim_permission=False
                st.session_state.pop('sim_comparison',None)
            permitted=st.checkbox('Use illustrative cleaning permissions',key='sim_permission')
            st.write('Allows the listed compatible order transitions to skip cleaning in this demo. These permissions need factory review.')
            with st.expander('Configuration and methodology'):
                text=st.text_area('Scenario configuration (editable JSON)',key='sim_config',height=300)
                st.caption('Virtual machines, source-quantity capacities and assumed durations; no actual factory equipment. Recorded resource totals are separate from scenario calculations.')
            st.session_state.sim_saved_config=text
            st.session_state.sim_saved_permission=permitted
            if not text.strip():
                st.button('Generate schedule',type='primary',disabled=True)
                st.session_state.sim_context={'source_sha256':result.sha256,'config':None,'comparison':None,'marker':digest(text)}
                return
            try:
                base_config=replace(parse_config(text),allow_cleaning_exemptions=permitted)
                validate_case(orders_from_import(result),base_config)
            except (ValueError,TypeError,KeyError,AttributeError,OverflowError) as exc:
                st.error(f'Invalid scenario configuration: {exc}')
                st.session_state.sim_context={'source_sha256':result.sha256,'config':None,'comparison':None,'marker':digest(text)}
                return
            case=prepare_case(result,base_config)
            st.dataframe(pd.DataFrame([{'Machine':machine_name(m.virtual_id),'Machine ID':m.virtual_id,'Vessel / fabric':'; '.join(' / '.join(p) for p in m.compatible_pairs),
                'Capacity (source quantity)':str(m.capacity),'Initially clean':m.initially_clean} for m in case.config.machines]),hide_index=True,width='stretch')
            st.caption(f'Each required cleaning takes {case.config.cleaning_hours} assumed hours. Terminal cleaning: {case.config.terminal_cleaning}.')
            with st.expander('Full assumptions, calendars and exact cleaning permissions'):st.json(to_json(case.config))
    marker=digest({'scenario':case.fingerprint,'settings':settings})
    st.session_state.sim_context={'source_sha256':result.sha256,'config':case.config,'case':case,'comparison':None,'marker':marker}
    from app.recovery_view import render_options
    if render_options(case,result,budget,settings,_show_schedule):return
    if setup.button('Generate schedule',type='primary',icon=':material/calendar_month:'):
        with st.spinner('Planning and independently verifying…',show_time=True):
            comparison=plan(case.orders,case.config)
        st.session_state.sim_comparison=(case.fingerprint,comparison)
        st.session_state.pop('sim_cp_result',None)
    stored=st.session_state.get('sim_comparison')
    if not stored or stored[0]!=case.fingerprint:
        st.info('Review the machines and rules, then select Generate schedule. Changes to assumptions require a fresh plan.')
        return
    cached=st.session_state.get('sim_cp_result')
    if not cached or cached[0]!=marker or getattr(getattr(cached[1],'cp_sat',None),'version',None)!=CP_VERSION:
        try:
            with st.spinner('Solving and independently verifying…',show_time=True):
                run=run_backend(case.orders,case.config,engine=engine,budget_seconds=budget,legacy=stored[1],
                    allow_fallback=fallback,case_fingerprint=case.fingerprint)
        except (ValueError,OverflowError) as exc:st.error(f'Cannot model this plan: {exc}');return
        st.session_state.sim_cp_result=(marker,run)
        # Reflow setup into the sidebar immediately after the first solve.
        # The verified result is cached, so this rerun cannot solve again.
        st.rerun()
    else:run=cached[1]
    st.session_state.sim_context['selected_run']=run if run.schedule is not None else None
    render_cp_result(case,run,_show_schedule,source=result,context_marker=marker)
