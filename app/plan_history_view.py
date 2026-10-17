"""Read-only session history. This view never calls a planner or review database."""
from datetime import datetime, timedelta
import json

import altair as alt
import pandas as pd
import streamlit as st

from app.plan_history import HistoryError, HistoryStore, NOTICE, build_snapshot, new_scope
from app.planner_presentation import clip_timeline

PRIORITIES = {'fewer_cleanings': 'Fewer cleanings', 'deadline_protection': 'More deadline protection',
              'legacy_heuristic': 'Legacy heuristic (no CP-SAT priority)'}


def retain_planner_widgets(state):
    # Streamlit normally deletes widget-owned values when their page is hidden.
    # Self-assignment detaches these existing values from that cleanup; no value,
    # case, constraint, selected priority or schedule is changed/restored/replanned.
    prefixes = ('sim_', 'planning_', 'integrated_', 'option_selection_', 'timeline_',
                'recovery_timeline_', 'selected_', 'manual_', 'planner_result_tabs')
    for key in list(state):
        if key.startswith(prefixes) and key not in ('integrated_generate',):
            state[key] = state[key]


def pause_planner_controls(state):
    """Remember control values, not a plan, while the separate page is open."""
    prefixes = ('sim_config', 'sim_permission', 'planning_backend', 'option_selection_', 'timeline_',
                'recovery_timeline_', 'manual_', 'planning_entry_', 'planning_request_', 'selected_question',
                'selected_explanation_mode', 'planner_result_tabs', 'history_save_title')
    controls = {k: state[k] for k in list(state) if k.startswith(prefixes)}
    # Non-widget copies are authoritative if a frontend sends cleared widgets on navigation.
    if 'sim_saved_config' in state: controls['sim_config'] = state['sim_saved_config']
    if 'sim_saved_permission' in state: controls['sim_permission'] = state['sim_saved_permission']
    state['_history_paused_controls'] = controls


def resume_planner_controls(state):
    # This only preserves the controls of the active session left open earlier.
    # It never reads an archive or writes case/schedule/constraints from a snapshot.
    for key, value in state.pop('_history_paused_controls', {}).items():
        state[key] = value


def session_scope():
    if '_plan_history_scope' not in st.session_state:
        st.session_state._plan_history_scope = new_scope()
    return st.session_state._plan_history_scope


def render_save_history(case, run, *, source=None, bundle=None, review=None):
    st.caption('Save this verified planned result without an explanation or review decision.')
    title = st.text_input('History title (optional)', max_chars=120, key='history_save_title')
    if st.button('Save to history', icon=':material/history:'):
        try:
            answer = None
            stored = st.session_state.get('selected_answer')
            if stored and bundle and stored[1].fingerprint == bundle['fingerprint']:
                answer = stored[1]
            # Never attach an automatically listed global supervisor review to session history.
            if not review or review['id'] != st.session_state.get('selected_review_id'):
                review = None
            snapshot = build_snapshot(case, run, source=source, bundle=bundle, answer=answer, review=review)
            saved = HistoryStore().save(scope=session_scope(), snapshot=snapshot, title=title)
            st.success(('Saved to plan history.' if saved['created'] else 'Already saved. Existing history entry retained.')
                       + ' Open Plan history in the sidebar to inspect it.')
        except HistoryError as exc:
            st.error('Could not save this planning snapshot. ' + str(exc))
        except (ValueError, TypeError, KeyError):
            st.error('Could not save this planning snapshot. Check storage availability and ensure any attached evidence is current and contains no private information. Planning and downloads are unchanged.')
    st.caption(NOTICE)


def archived_frame(snapshot, reference=False):
    rows = snapshot['reference_timeline' if reference else 'selected_timeline']
    if not rows: return None
    frame = pd.DataFrame(rows)
    frame['start'] = pd.to_datetime(frame.start)
    frame['end'] = pd.to_datetime(frame.end)
    return frame


def saved_time(value):
    return datetime.fromisoformat(value).strftime('%d %b %Y %H:%M:%S %z') if value else 'Unavailable'


def render_archived_timeline(row):
    snap = row['snapshot']
    options = ['Selected planned result']
    if snap['reference_timeline']: options.append(snap['reference_label'])
    selected = st.radio('Archived timeline', options, key='history_variant_' + row['run_id'], horizontal=True)
    frame = archived_frame(snap, selected != options[0])
    ids = list(dict.fromkeys(frame.machine_id))
    names = {r.machine_id: r.machine for r in frame.itertuples()}
    machines = st.multiselect('Archived machines', ids, default=ids, format_func=names.get,
                             key='history_machines_' + row['run_id'])
    if not machines:
        st.info('Select an archived machine.'); return
    lo, hi = frame.start.min().to_pydatetime(), frame.end.max().to_pydatetime()
    cutoff = snap['package'].get('execution_reference')
    default = datetime.fromisoformat(cutoff['cutoff']) if cutoff else lo
    default = min(max(default, lo), hi)
    full = st.checkbox('Show full archived schedule', key='history_full_' + row['run_id'])
    chosen = st.date_input('Archived date', value=default.date(), min_value=lo.date(), max_value=hi.date(),
                           key='history_date_' + row['run_id'], disabled=full)
    start = lo if full else max(lo, datetime.combine(chosen or default.date(), datetime.min.time()))
    end = hi if full else min(hi, start + timedelta(days=1))
    st.write(f'{start:%d %b %Y %H:%M:%S} to {end:%d %b %Y %H:%M:%S} | Saved scenario-local time, Asia/Karachi')
    if end <= start: st.info('No activity in this window.'); return
    data = clip_timeline(frame, start, end, machines)
    if data.empty: st.info('No planned activity in this window.'); return
    data['exact_start'] = data.start.map(lambda d: d.isoformat())
    data['exact_end'] = data.end.map(lambda d: d.isoformat())
    data['centre'] = data.visible_start + (data.visible_end - data.visible_start) / 2
    data['show_label'] = (data.visible_end - data.visible_start).dt.total_seconds() / (end - start).total_seconds() >= .025
    base = alt.Chart(data).encode(
        y=alt.Y('machine:N', sort=[names[m] for m in machines], title=None,
                axis=alt.Axis(labelLimit=0, labelFontSize=14)),
        x=alt.X('visible_start:T', title='Saved planned time', scale=alt.Scale(domain=[start.isoformat(), end.isoformat()]),
                axis=alt.Axis(format='%d %b %H:%M' if full else '%H:%M', labelFontSize=13)), x2='visible_end:T',
        tooltip=['order_id:N', 'machine_id:N', 'activity:N', 'exact_start:N', 'exact_end:N'])
    palette = {'Production': '#0F8A83', 'Cleaning': '#EDBA54', 'Terminal cleaning': '#B98128',
               'Unavailable': '#D7DDE5', 'Revised outage': '#A1AAB8'}
    bars = base.mark_bar(size=30, cornerRadius=3).encode(
        color=alt.Color('activity:N', scale=alt.Scale(domain=list(palette), range=list(palette.values())), title=None))
    labels = base.transform_filter((alt.datum.activity == 'Production') & alt.datum.show_label).mark_text(
        color='white', fontSize=13, clip=True).encode(x='centre:T', text='label:N')
    with st.container(horizontal=True, wrap=False):
        st.altair_chart((bars + labels).properties(height=max(250, 72 * len(machines)), background='white'),
                        width=860, theme=None)
    st.caption('Saved planned results; continuous time, with exact original timestamps in hover. Scroll horizontally on narrow screens.')


def render_plan_history():
    st.subheader('Plan history')
    st.write(NOTICE)
    st.caption('Read-only planned results. Opening an archive does not change the active planner. No restore action is provided.')
    try:
        scope = session_scope()
        store = HistoryStore()
        rows = store.list_runs(scope=scope)
        if not rows:
            st.info('No saved plans in this session. Generate a verified plan, then select Save to history in Review & export.')
            return
        st.dataframe(pd.DataFrame([{
            'Title': r['title'] or 'Untitled plan', 'Saved time': saved_time(r['saved_at']),
            'Type': r['summary']['kind'].title() if r['summary'] else 'Unavailable',
            'Priority': PRIORITIES.get(r['summary']['priority'], r['summary']['priority']) if r['summary'] else '',
            'Cleanings': r['summary']['cleaning_count'] if r['summary'] else None,
            'On time / total': f"{r['summary']['on_time']} / {r['summary']['total_orders']}" if r['summary'] else '',
            'Verification': 'Verified when saved' if r['summary'] else 'Malformed/unsupported'} for r in rows]),
            hide_index=True, width='stretch')
        run_id = st.selectbox('Saved run', [r['run_id'] for r in rows],
            format_func=lambda v: next((r['title'] or 'Untitled plan') + ' | ' + saved_time(r['saved_at']) for r in rows if r['run_id'] == v),
            key='history_open_run')
        row = store.get(scope=scope, run_id=run_id)
        snap = row['snapshot']; summary = snap['summary']
        st.subheader(row['title'] or 'Untitled planned result')
        st.caption('Archived planned result | ' + saved_time(row['saved_at']) + ' | Verified when saved')
        a, b, c = st.columns(3)
        a.metric('Saved cleaning events', summary['cleaning_count'])
        b.metric('Saved orders on time', f"{summary['on_time']} / {summary['total_orders']}")
        c.metric('Saved minimum buffer', summary['minimum_slack_hours'] + ' h',
                 help='The smallest saved buffer between planned completion and the effective delivery deadline.')
        st.write('Planning priority: ' + PRIORITIES.get(summary['priority'], summary['priority']) + ' | Method: ' + summary['method'])
        if summary['kind'] == 'recovery':
            st.info('Recovery completed/running labels are simulated states relative to the saved reference cutoff, not actual factory execution. The pre-disruption reference need not satisfy revised constraints.')
            st.write('Saved reference cutoff: ' + snap['package']['execution_reference']['cutoff'])
        render_archived_timeline(row)
        with st.expander('Saved inputs and assumptions'):
            st.write(f"{summary['total_orders']} input orders | source SHA256: {snap['package']['source_sha256']}")
            st.json({'assumptions': snap['package']['assumptions'], 'input_records': snap['input_records'],
                     'original_orders': snap['package']['original_orders'], 'effective_orders': snap['package']['orders']})
        with st.expander('Saved changes, confirmed constraints and recovery'):
            st.json({k: snap['package'].get(k) for k in ('deadline_overrides', 'change_history_with_interpretation_receipts',
                     'execution_reference', 'recovery_summary')})
        with st.expander('Saved verification, solver status and metrics'):
            st.json({'verification': snap['package']['verification'], 'solver': snap['package']['cp_sat_result'],
                     'metrics': snap['saved_metrics'], 'schema_version': snap['schema_version'],
                     'application_version': snap['application_version'], 'fingerprint': snap['content_fingerprint']})
        with st.expander('Available saved explanation and review evidence'):
            st.caption('Supervisor acceptance means further review only, never production approval.')
            if snap['explanation'] is None and snap['package']['applicable_review'] is None:
                st.write('No explanation or supervisor review was attached. Neither is required to save a plan.')
            else: st.json({'explanation': snap['explanation'], 'review': snap['package']['applicable_review'],
                           'evidence': snap['package']['selected_evidence_snapshot']})
        st.download_button('Download saved review package (JSON)', store.download(scope=scope, run_id=run_id),
                           file_name='dyeing_saved_plan_' + run_id + '.json', mime='application/json', type='primary')
    except (HistoryError, ValueError, KeyError, TypeError):
        st.error('Saved history is unavailable or malformed in this session. The active planner and its existing downloads are unchanged.')
