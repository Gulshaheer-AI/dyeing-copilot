"""Accurate selected-engine screen/export; legacy comparison explanations are gated."""
from dataclasses import asdict
import pandas as pd
import streamlit as st
from planner.change_requests import digest
from planner.comparison import compare_schedules,deadline_performance
from planner.evaluator import evaluate_resources
from planner.verifier import verify_schedule
from planner.scenario import to_json


def export_backend(case,run):
    if run.case_fingerprint != case.fingerprint or run.effective_fingerprint != digest({'orders':case.orders,'config':case.config}):
        raise ValueError('Stale selected-backend result: source/scenario fingerprint changed.')
    if run.schedule is None or not verify_schedule(case.orders,case.config,run.schedule).valid:
        raise ValueError('No independently verified selected-backend schedule for export.')
    verified=verify_schedule(case.orders,case.config,run.schedule)
    use=evaluate_resources(case.orders,case.config,run.schedule)
    return to_json({'artifact_type':'illustrative_selected_backend_schedule_not_factory_instruction',
        'backend_origin':run.origin,'source_sha256':case.source_sha256,'source_filename':case.source_filename,
        'scenario_fingerprint':case.fingerprint,'selected_schedule_fingerprint':digest(run.schedule),
        'orders':case.orders,'original_orders':case.original_orders,'assumptions':case.config,
        'deadline_overrides':case.overrides,'change_history_with_interpretation_receipts':case.history,
        'schedule':run.schedule,'cp_sat_result':run.cp_sat,
        'verification':{'valid':True,'errors':verified.errors},
        'resources_secondary':{**asdict(use),'total':use.total,'unit':case.config.resource_unit},
        'review_status':'pending_further_review_not_production_approval',
        'limitations':'Hypothetical machines/rules; unresolved modelled source units; no factory approval, metered saving or machine control.'})


def render_cp_result(case,run,show_schedule):
    st.subheader('4. Selected backend schedule')
    if run.cp_sat:
        result=run.cp_sat
        st.caption(f"Stage A: {result.stage_a['status']}; Stage B: {result.stage_b['status']}. "
            f"Cleaning optimality proven: {result.cleaning_optimal}; slack optimal at fixed count: {result.slack_optimal_at_fixed_count}.")
        st.caption(f"Total CP-SAT time {result.timing['total_seconds']:.3f}s of {result.timing['total_budget_seconds']}s shared budget; one worker, fixed seed, zero gap tolerances.")
        if result.stage_b.get('conditional_on_feasible_incumbent'):
            st.warning('Stage B is conditional on a feasible Stage-A cleaning count; global minimum cleaning was not proven.')
        with st.expander('Solver objectives, bounds, exact scaling and verification'):
            st.json({k:v for k,v in asdict(result).items() if k not in ('schedule','resources')})
    if run.origin=='heuristic_fallback_not_cp_sat':
        st.warning('Explicitly permitted HEURISTIC FALLBACK. CP-SAT produced no verified schedule; this is not CP-SAT success.')
    elif run.origin=='cp_sat':
        st.success('CP-SAT schedule independently verified under the displayed scenario rules.')
    if run.schedule is None:
        status=run.cp_sat.stage_a['status'] if run.cp_sat else 'NOT_AVAILABLE'
        st.error('No verified selected-backend schedule. '+('CP-SAT proved the encoded constraints infeasible.' if status=='INFEASIBLE' else
            f'{status} is not proof of infeasibility. Try another bounded budget or explicitly select the legacy fallback.'))
        previous=st.session_state.get('cp_last_success')
        if previous:
            with st.expander('Last successful selected-backend schedule: previous scenario/settings only'):
                st.caption('This retained artifact is not verified for the current constraints and cannot be exported as current.')
                st.json({'fingerprint':previous[0],'origin':previous[1].origin,'schedule':previous[1].schedule})
        return
    verified=verify_schedule(case.orders,case.config,run.schedule)
    if not verified.valid:
        st.error('Independent verification rejected the selected schedule; no recommendation or export.');return
    counts=compare_schedules(case.orders,case.config,run.schedule,run.schedule)['cleaning_counts']['proposal']
    deadlines=deadline_performance(case.orders,run.schedule)
    slack=[r['slack_hours'] for r in deadlines['orders']]
    from statistics import median
    cols=st.columns(3)
    cols[0].metric('Selected schedule cleaning events',counts['total'])
    cols[1].metric('On-time orders',f"{deadlines['on_time']}/{len(case.orders)}")
    cols[2].metric('Minimum deadline slack (h)',str(min(slack)))
    st.caption(f"Initial/between/terminal: {counts['initial']}/{counts['between_orders']}/{counts['terminal']}; median slack {median(slack)} h. Method origin: {run.origin}.")
    machines=sorted({p.virtual_id for p in run.schedule.placements})
    machine=st.selectbox('Inspect selected-backend virtual machine',machines)
    sequence=sorted((p for p in run.schedule.placements if p.virtual_id==machine),key=lambda p:p.cleaning_start)
    st.write('INITIAL > '+' > '.join(p.order_id for p in sequence)+' > TERMINAL')
    st.dataframe(pd.DataFrame([asdict(p) for p in sequence]),hide_index=True,width='stretch')
    with st.expander('Secondary resource score and hypothetical model terms'):
        use=evaluate_resources(case.orders,case.config,run.schedule)
        st.json(to_json({'unit':case.config.resource_unit,'resource_breakdown':{**asdict(use),'total':use.total}}))
    st.subheader('5. Review and export')
    st.info('CP-SAT schedule explanations and supervisor review are disabled in the legacy EDD/proposal copilot workflow: its comparison contract cannot represent an EDD-failing CP-SAT result safely yet. Recorded-order questions and AMD constraint interpretation remain available. No CP-SAT result is relabelled as a legacy proposal.')
    st.button('Explain selected CP-SAT schedule (not yet supported)',disabled=True)
    show_schedule('Selected schedule: '+run.origin,run.schedule,case.config,verified)
    st.download_button('Export selected-backend planner review package (JSON)',export_backend(case,run),
        file_name='cp_sat_planner_review_package.json',mime='application/json')
    st.caption('Acceptance is for further review, never production approval. Source orders and original AMD/manual receipts remain in the export.')
    st.session_state.cp_last_success=(case.fingerprint,run)
