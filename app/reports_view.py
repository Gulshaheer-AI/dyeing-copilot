"""Shortcuts to canonical, freshly checked exports; no planning or AMD calls."""
import streamlit as st


def current_report(result, state):
    from app.cp_sat_view import export_backend
    context = state.get('sim_context') or {}
    case, run = context.get('case'), context.get('selected_run')
    if case is None or run is None or case.source_sha256 != result.sha256:
        raise ValueError('Generate a verified plan for the current dataset first.')
    # This canonical builder checks scenario identity and independently verifies.
    return export_backend(case, run)


def open_module(view, tab=None):
    st.session_state.pending_view = view
    if tab is not None:
        st.session_state.pending_planner_tab = tab
    st.rerun()


def render_reports(result):
    st.subheader('Reports')
    st.write('Review packages for planned results. No actual production or measured consumption is implied.')
    with st.container(key='reports_current'):
        st.subheader('Current planning result', anchor=False)
        try:
            payload = current_report(result, st.session_state)
        except ValueError as exc:
            payload = None
            st.info(str(exc))
        st.download_button('Download current schedule review package', payload or '',
            file_name='dyeing_planner_review_package.json', mime='application/json',
            disabled=payload is None, type='primary', icon=':material/download:')
        st.caption('Schedule-only canonical package. To attach a matching explanation or supervisor decision, use Review and reports in the planner. Acceptance means further review only.')
        if st.button('Open planner review controls', icon=':material/rate_review:'):
            open_module('Scheduling simulator', 'Review and reports')
    with st.container(key='reports_archive'):
        st.subheader('Archived planning reports', anchor=False)
        st.write('Open a saved run to inspect its original assumptions, timelines and verification, then download its saved JSON package.')
        if st.button('Browse this session’s plan history', icon=':material/history:'):
            open_module('Plan history')
        from app.plan_history import NOTICE
        st.caption(NOTICE)
