"""Accurate selected-engine screen/export; legacy comparison explanations are gated."""
from dataclasses import asdict
import pandas as pd
import altair as alt
import streamlit as st
from planner.change_requests import digest
from planner.comparison import compare_schedules,deadline_performance
from planner.evaluator import evaluate_resources
from planner.verifier import verify_schedule
from planner.scenario import to_json
from planner.recovery import verify_recovery,recovery_summary


def export_backend(case,run,*,bundle=None,review=None):
    if run.case_fingerprint != case.fingerprint or run.effective_fingerprint != digest({'orders':case.orders,'config':case.config}):
        raise ValueError('Stale selected-backend result: source/scenario fingerprint changed.')
    if run.schedule is None or not verify_recovery(case.orders,case.config,run.schedule,case.recovery).valid:
        raise ValueError('No independently verified selected-backend schedule for export.')
    verified=verify_recovery(case.orders,case.config,run.schedule,case.recovery)
    use=evaluate_resources(case.orders,case.config,run.schedule)
    from app.planner_presentation import current_comparison
    comparison=current_comparison(case,run)
    if bundle is not None:
        from copilot.selected_evidence import build_selected_evidence, selected_fingerprint
        identity=bundle['scenario']
        if (identity['case_fingerprint']!=case.fingerprint or identity['schedule_fingerprint']!=digest(run.schedule)
                or identity['backend_origin']!=run.origin):
            raise ValueError('Selected evidence does not match this current schedule.')
        fresh=build_selected_evidence(case,run,'Verify selected export',context_marker=bundle.get('context_marker'))
        if fresh['scenario']!=bundle['scenario'] or selected_fingerprint(bundle)!=bundle['fingerprint']:
            raise ValueError('Selected evidence snapshot is stale or inconsistent.')
    if review is not None and (bundle is None or review['fingerprint']!=bundle['fingerprint'] or review['evidence_json']!=bundle):
        raise ValueError('Review does not match the exact selected evidence snapshot.')
    return to_json({'artifact_type':'illustrative_selected_backend_schedule_not_factory_instruction',
        'backend_origin':run.origin,'source_sha256':case.source_sha256,'source_filename':case.source_filename,
        'scenario_fingerprint':case.fingerprint,'selected_schedule_fingerprint':digest(run.schedule),
        'orders':case.orders,'original_orders':case.original_orders,'assumptions':case.config,
        'deadline_overrides':case.overrides,'change_history_with_interpretation_receipts':case.history,
        'schedule':run.schedule,'cp_sat_result':run.cp_sat,
        'objective_option':getattr(run,'option','fewer_cleanings'),
        'execution_reference':case.recovery,
        'recovery_summary':recovery_summary(case,run.schedule) if case.recovery else None,
        'generated_deadline_first_baseline':run.legacy.baseline if comparison else None,
        'verified_comparison':comparison,
        'verification':{'valid':True,'errors':verified.errors},
        'resources_secondary':{**asdict(use),'total':use.total,'unit':case.config.resource_unit},
        'selected_evidence_fingerprint':bundle['fingerprint'] if bundle else None,
        'selected_evidence_snapshot':bundle,'applicable_review':review,
        'review_status':review['status'] if review else 'no_review_attached',
        'review_boundary':'Pending is not acceptance; accepted means further review only, never production approval.',
        'limitations':'Hypothetical machines/rules; unresolved modelled source units; no factory approval, metered saving or machine control.'})


def render_cp_result(case,run,show_schedule,*,source=None,context_marker=None):
    from app.planner_presentation import current_comparison,result_summary
    from app.dashboard_style import panel_heading
    from app.timeline_view import render_timeline
    from app.planning_changes_view import render_planning_changes
    from app.selected_copilot_view import render_selected_copilot
    if run.schedule is None:
        status=run.cp_sat.stage_a['status'] if run.cp_sat else 'NOT_AVAILABLE'
        st.error('No current verified schedule. '+('The solver proved these constraints infeasible.' if status=='INFEASIBLE' else
            'No solution was found within this run; infeasibility has not been proven.'))
        with st.expander('Change constraints or reset'):
            render_planning_changes(case)
        previous=st.session_state.get('cp_last_success')
        if previous:
            with st.expander('Historical schedule — previous plan only'):
                st.caption('Not verified against current constraints; unavailable for current review or export.')
                st.json({'fingerprint':previous[0],'origin':previous[1].origin,'schedule':previous[1].schedule})
        return
    try:changes=current_comparison(case,run)
    except ValueError as exc:st.error(str(exc));return
    verified=verify_recovery(case.orders,case.config,run.schedule,case.recovery)
    counts=compare_schedules(case.orders,case.config,run.schedule,run.schedule)['cleaning_counts']['proposal']
    deadlines=deadline_performance(case.orders,run.schedule)
    slack=min(r['slack_hours'] for r in deadlines['orders'])
    before=changes['cleaning_counts']['baseline']['total'] if changes else None
    with st.container(key='dashboard_summary'):
        panel_heading(result_summary(before,counts['total'],deadlines['on_time'],len(case.orders)),
            eyebrow='Illustrative scheduling result')
        with st.container(horizontal=True):
            st.badge('Independently verified',icon=':material/verified:',color='primary')
            st.badge(f'Plan version {case.revision}',color='gray')
            if run.origin=='heuristic_fallback_not_cp_sat':st.badge('Heuristic fallback — not CP-SAT success',color='orange')
            elif run.origin=='legacy_heuristic':st.badge('Legacy heuristic',color='gray')
            elif getattr(run.cp_sat,'objective_order',None)=='deadline_protection' and run.cp_sat.primary_optimal:
                st.badge('Maximum minimum deadline buffer proven',color='primary')
            elif run.cp_sat.cleaning_optimal and run.cp_sat.stage_a['status']=='OPTIMAL':
                st.badge('Minimum cleaning count proven',color='primary')
            else:st.badge('Best schedule found within the time limit',color='blue')
    with st.container(horizontal=True,wrap=True,gap='medium'):
        with st.container(key='kpi_cleaning',width=300):
            st.metric('Cleaning events',counts['total'],icon=':material/cleaning_services:',
                delta=counts['total']-before if before is not None else None,delta_color='inverse')
            st.write(f'Deadline-first: {before}' if before is not None else 'No verified baseline')
        with st.container(key='kpi_deadlines',width=300):
            st.metric('Orders on time',f"{deadlines['on_time']} / {len(case.orders)}",icon=':material/task_alt:')
            st.write('Completion meets the effective deadline')
        with st.container(key='kpi_buffer',width=300):
            st.metric('Smallest deadline buffer',f'{slack:,.2f} h',icon=':material/schedule:',
                help='The smallest buffer between completion and delivery deadline')
            st.write('Scenario hours before the tightest deadline')
    with st.container(key='dashboard_counts'):
        if changes:
            comparison=pd.DataFrame([{'Plan':'Deadline-first','Cleaning events':before},
                {'Plan':'Optimised','Cleaning events':counts['total']}])
            base=alt.Chart(comparison).encode(y=alt.Y('Plan:N',sort=['Deadline-first','Optimised'],title=None),
                x=alt.X('Cleaning events:Q',scale=alt.Scale(domain=[0,max(1,max(before,counts['total'])*1.15)]),
                    axis=alt.Axis(tickMinStep=1)),tooltip=['Plan:N','Cleaning events:Q'])
            bars=base.mark_bar(size=22,cornerRadiusEnd=4).encode(color=alt.Color('Plan:N',legend=None,
                scale=alt.Scale(domain=['Deadline-first','Optimised'],range=['#6886A6','#0F8A83'])))
            labels=base.mark_text(align='left',dx=6,fontSize=14,color='#14243B').encode(text='Cleaning events:Q')
            chart=(bars+labels).properties(height=100,background='white').configure_axis(labelFontSize=14,titleFontSize=13,labelColor='#526379',titleColor='#526379',gridColor='#E8EDF3')
            st.altair_chart(chart,width='stretch',theme=None)
            st.write('Generated deadline-first baseline · same effective orders and constraints · both independently verified')
        else:st.write('Recovery uses the explicitly selected historical reference, not EDD.' if case.recovery else 'Comparison chart unavailable: no verified generated deadline-first baseline for this effective scenario.')
    if message:=st.session_state.pop('planning_applied_message',None):st.success(message)
    tabs=st.tabs(['Machine schedule','Request a change','Review & export'],key='planner_result_tabs',on_change='rerun')
    with tabs[0]:
        render_timeline(case,run)
        with st.expander('Detailed schedule and cleaning events'):
            show_schedule('Proposed schedule',run.schedule,case.config,verified)
        if changes:
            with st.expander('What changed against the deadline-first plan?'):
                st.dataframe(pd.DataFrame([{'Machine':m,'Deadline-first':' → '.join(seq),
                    'Proposed':' → '.join(changes['machine_sequences']['proposal'][m])}
                    for m,seq in changes['machine_sequences']['baseline'].items()]),hide_index=True,width='stretch')
                rows=[{'Order':r['order_id'],'Before machine':r['baseline']['machine'],'After machine':r['proposal']['machine'],
                    'Before predecessor':r['baseline']['predecessor'],'After predecessor':r['proposal']['predecessor'],
                    'Before cleaning':r['baseline']['cleaning_required'],'After cleaning':r['proposal']['cleaning_required']}
                    for r in changes['order_transitions'] if r['transition_changed']]
                st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
                st.caption('Only configured directed permissions can remove cleaning; grouping or colour alone grants no exemption.')
    with tabs[1]:
        with st.container(key='dashboard_change'):
            st.subheader('Update the plan',anchor=False)
            render_planning_changes(case)
    with tabs[2]:
        with st.container(key='dashboard_review'):
            st.caption('Acceptance means further review, not production approval.')
            download=st.container()
            bundle,review=render_selected_copilot(case,run,source=source,context_marker=context_marker)
            with download:
                st.download_button('Download planner review package',export_backend(case,run,bundle=bundle,review=review),
                    file_name='dyeing_planner_review_package.json',mime='application/json',type='primary',icon=':material/download:')
                from app.plan_history_view import render_save_history
                render_save_history(case,run,source=source,bundle=bundle,review=review)
    with st.expander('Technical details: solver, modelled resources and audit'):
        if run.cp_sat:
            st.json({k:v for k,v in asdict(run.cp_sat).items() if k not in ('schedule','resources')})
        use=evaluate_resources(case.orders,case.config,run.schedule)
        st.caption('Secondary hypothetical resource score; not measured water or money savings.')
        st.json(to_json({'unit':case.config.resource_unit,'resources':{**asdict(use),'total':use.total}}))
        if changes:st.json(changes)
    st.session_state.cp_last_success=(case.fingerprint,run)
    from app.evaluation_evidence import render_evaluation_evidence
    render_evaluation_evidence(case)
