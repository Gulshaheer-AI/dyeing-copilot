"""Explicit, cached option solving and simulated recovery controls."""
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from planner.change_requests import digest
from planner.recovery import select_reference, recovery_summary, verify_recovery
from planner.recovery_solver import run_options, OPTIONS, VERSION


def render_options(case, source, budget, settings, show_schedule):
    from app.cp_sat_view import render_cp_result
    cache = st.session_state.get('integrated_options')
    current = None
    if cache and cache[0] == case.fingerprint:
        current = cache[2].get(st.session_state.get('integrated_choice', 'fewer_cleanings'))
    old = st.session_state.get('sim_cp_result')
    if current is None and old and old[1].case_fingerprint == case.fingerprint:
        current = old[1]
    with st.expander('Recovery and alternative objectives', expanded=case.recovery is not None):
        st.write('Optional: compare two planning priorities, or protect work already started in a simulated reference plan.')
        st.caption('Optional comparisons use CP-SAT only. Legacy fallback remains available in the standard full-horizon workflow; it does not implement these objective and history checks.')
        if st.button('Compare both plan options', type='primary', key='compare_integrated'):
            st.session_state.integrated_mode = True
            st.session_state.integrated_solve_requested = True
        if current and current.schedule is not None:
            default = min(p.process_start for p in current.schedule.placements) + timedelta(hours=1)
            st.caption('Select this current verified schedule as the reference. This is simulated execution, not factory telemetry.')
            with st.form('select_recovery_reference'):
                day = st.date_input('Replan from date', value=default.date())
                clock = st.time_input('Replan from time', value=default.time(), step=timedelta(seconds=1))
                confirm = st.form_submit_button('Use current verified plan as reference')
            if confirm:
                try:
                    st.session_state.planning_case = select_reference(case, current, datetime.combine(day, clock))
                    st.session_state.integrated_mode = True
                    st.session_state.pop('integrated_options', None)
                    st.session_state.pop('selected_answer', None)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        if case.recovery:
            st.write(f'**Replan from {case.recovery.cutoff:%Y-%m-%d %H:%M:%S}** · Simulated execution')
            st.caption('Completed and running work stays exact. A started cleaning also commits its immediately following batch; batches cannot be interrupted.')
    if not st.session_state.get('integrated_mode') and case.recovery is None:
        return False
    if st.button('Generate schedule', type='primary', icon=':material/calendar_month:', key='integrated_generate'):
        st.session_state.integrated_solve_requested = True
    signature = digest({'case': case.fingerprint, 'settings': settings, 'version': VERSION})
    if st.session_state.pop('integrated_solve_requested', False):
        try:
            with st.spinner('Comparing priorities and independently checking protected history…', show_time=True):
                runs = run_options(case, budget_seconds=budget)
            st.session_state.integrated_options = (case.fingerprint, signature, runs)
        except (ValueError, OverflowError) as exc:
            st.session_state.pop('integrated_options', None)
            st.error('Input/history conflict or unsupported model range: ' + str(exc))
    cache = st.session_state.get('integrated_options')
    if not cache or cache[:2] != (case.fingerprint, signature):
        st.info('No current recovery/option result. Generate schedule explicitly; previous schedules remain historical.')
        from app.planning_changes_view import render_planning_changes
        render_planning_changes(case)
        return True
    runs = cache[2]
    rows = []
    from planner.comparison import deadline_performance
    for name, run in runs.items():
        result = run.cp_sat
        performance = deadline_performance(case.orders, run.schedule) if run.schedule else None
        rows.append({'Priority': OPTIONS[name], 'Verified': run.schedule is not None,
            'Stage A': result.stage_a['status'], 'Stage B': result.stage_b['status'],
            'Cleaning events': result.resources.cleaning_events if run.schedule else None,
            'Orders on time': performance['on_time'] if performance else None,
            'Smallest buffer (hours)': min(x['slack_hours'] for x in performance['orders']) if performance else None,
            'Primary objective proven': result.primary_optimal, 'Secondary objective proven': result.secondary_optimal})
    st.dataframe(pd.DataFrame(rows)[['Priority','Verified','Cleaning events','Orders on time','Smallest buffer (hours)']], hide_index=True, width='stretch')
    with st.expander('Both option receipts: objectives, bounds and verification'):
        from planner.scenario import to_json
        st.json(to_json({name:run.cp_sat for name,run in runs.items()}))
    a, b = runs.values()
    if a.schedule is not None and a.schedule == b.schedule:
        st.info('Both priorities produced the same verified plan. No difference is implied.')
    elif a.schedule is not None and b.schedule is not None:
        st.caption('Different valid options under identical effective constraints and fixed history; select one for explanation, review and export.')
    selected = st.radio('Plan to inspect and review', list(OPTIONS), format_func=OPTIONS.get,
        key='option_selection_' + signature[:16])
    st.session_state.integrated_choice = selected
    run = runs[selected]
    marker = digest({'options': signature, 'selected': selected, 'schedule': run.schedule})
    st.session_state.sim_context.update(marker=marker, selected_run=run if run.schedule else None)
    if run.schedule and case.recovery:
        summary = recovery_summary(case, run.schedule)
        with st.container(key='recovery_summary'):
            st.subheader('Recovery impact', anchor=False)
            st.write(f"{summary['completed_batches_preserved']} completed batches preserved · {summary['running_batches_protected']} running batches protected · {summary['future_batches_changed']} future batches changed")
            st.write(f"Orders on time: reference {summary['on_time_before']} → revised {summary['on_time_after']}. Cleaning events: {summary['cleaning_before']} → {summary['cleaning_after']}.")
            st.caption(summary['reference_boundary'])
            with st.expander('Before/after batch changes and protected operations'):
                st.dataframe(pd.DataFrame(summary['changes']), hide_index=True, width='stretch')
                st.json(summary)
    render_cp_result(case, run, show_schedule, source=source, context_marker=marker)
    return True
