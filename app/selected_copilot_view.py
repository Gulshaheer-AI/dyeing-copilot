"""Selected CP-SAT explanation and SQLite supervisor review, read-only evidence."""
import json
import sqlite3
import streamlit as st
from copilot.amd import load_config,AMDConnectionError
from copilot.selected_evidence import build_selected_evidence
from copilot.selected_workflow import explain_selected
from copilot.selected_reviews import applicable_review
from copilot.reviews import ReviewStore
from copilot.session import generate_once
from planner.change_requests import digest

STATUS_LABELS={"pending_review":"Pending review","accepted_for_further_review":"Accepted for further review","rejected":"Rejected"}


def render_selected_copilot(case,run,source=None,context_marker=None):
    st.subheader('Explain and review this plan')
    st.caption('Explain the verified plan, changed orders and what a supervisor should review.')
    question=st.text_input('Ask about this plan',value='Explain this selected schedule and what the planner should review.',max_chars=2000)
    try:bundle=build_selected_evidence(case,run,question,source=source,context_marker=context_marker)
    except ValueError as exc:st.error(str(exc));return None,None
    mode_label=st.radio('Selected schedule explanation source',['Live AMD','Mock demonstration (no API call)'],horizontal=True)
    mode='live_amd' if mode_label=='Live AMD' else 'mock'
    signature=digest({'evidence':bundle['fingerprint'],'question':question,'mode':mode})
    stored=st.session_state.get('selected_answer')
    if stored and stored[0]!=signature:
        st.session_state.pop('selected_answer',None);stored=None
        st.info('Previous selected-schedule explanation is stale; generate again.')
    failure=st.session_state.get('selected_failure')
    if failure and failure[0]!=signature:failure=None;st.session_state.pop('selected_failure',None)
    connection=None
    if mode=='mock':st.warning('MOCK demonstration: no AMD inference.')
    else:
        try:connection=load_config()
        except AMDConnectionError as exc:st.caption(str(exc))
    busy=bool(st.session_state.get('selected_inflight'))
    if failure:
        st.error(failure[1]);st.caption('Schedule preserved; retry never switches to mock.')
        if len(failure)>2 and failure[2]:
            with st.expander('Rejected selected-explanation origin receipt'):st.json(failure[2])
    retry=st.button('Retry explanation',disabled=busy or bool(stored) or (mode=='live_amd' and connection is None)) if failure else False
    clicked=st.button('Explain this plan',disabled=busy or bool(stored) or (mode=='live_amd' and connection is None))
    fresh=False
    if clicked or retry:
        try:
            with st.spinner('Waiting for AMD and validating selected evidence...' if mode=='live_amd' else 'Preparing labelled mock...',show_time=True):
                # Separate state keys prevent cross-workflow reuse.
                temporary={'copilot_inflight':st.session_state.get('selected_inflight')} if busy else {}
                st.session_state.selected_inflight=signature
                answer,fresh=generate_once(temporary,signature,lambda:explain_selected(bundle,question,mode=mode,config=connection))
                st.session_state.selected_answer=(signature,answer);stored=(signature,answer)
                st.session_state.pop('selected_failure',None)
        except ValueError as exc:
            st.session_state.selected_failure=(signature,str(exc),getattr(exc,'receipt',None));st.rerun()
        finally:st.session_state.pop('selected_inflight',None)
    if stored:
        answer=stored[1]
        if answer.receipt['origin']=='mock':st.warning('MOCKED explanation: not live AMD inference.')
        elif fresh:st.success('Validated live AMD selected-schedule explanation received.')
        else:st.info('Previously generated live AMD explanation; no API request on this rerun.')
        with st.expander('Selected explanation origin receipt'):st.json(answer.receipt)
        for claim in answer.output.explanation:st.write(claim.text)
        st.write(bundle['catalog']['review_actions'][answer.output.proposed_review_action])
        with st.expander('Selected explanation evidence, assumptions and supporting passages'):
            for key in answer.output.assumptions:st.write(bundle['catalog']['assumptions'][key])
            for key in answer.output.limitations:st.write(bundle['catalog']['limitations'][key])
            for ref in answer.output.evidence_references:
                st.caption(ref)
                if ref in bundle['facts']:st.json(bundle['facts'][ref])
                else:
                    doc=bundle['documents'][ref];st.caption(doc['path']+' / '+doc['section']);st.text(doc['passage'])
    selected_review=None
    st.caption('Review status: Not reviewed' if not st.session_state.get('selected_review_id') else 'Review is tied to this exact plan and evidence.')
    st.caption('Acceptance is for further review only. It cannot change constraints, grant cleaning permission or control equipment.')
    try:
        store=ReviewStore()
        if stored:
            notes=st.text_area('Selected schedule pending-review notes',max_chars=5000)
            if st.button('Save for supervisor review',icon=':material/rate_review:'):
                st.session_state.selected_review_id=store.save_pending(stored[1],bundle,notes)
                current_review=applicable_review(store,bundle,st.session_state.selected_review_id)
                if current_review['status']=='pending_review':
                    st.success('Saved pending review with exact selected-schedule evidence.')
                else:
                    st.info('Existing review retained as '+STATUS_LABELS[current_review['status']]+'; no new pending review or production approval was created.')
        rows=[r for r in store.list_reviews() if json.loads(r['evidence_json']).get('kind')=='selected_schedule']
        if rows:
            ids=[r['id'] for r in rows]
            preferred=st.session_state.get('selected_review_id')
            review_id=st.selectbox('Selected schedule saved review',ids,index=ids.index(preferred) if preferred in ids else 0,
                format_func=lambda key:next(STATUS_LABELS[r['status']]+' / '+r['created_at'] for r in rows if r['id']==key))
            row=next(r for r in rows if r['id']==review_id)
            stale=row['fingerprint']!=bundle['fingerprint']
            if stale:st.caption('Review status: Not reviewed for this plan. The previous review is historical.')
            st.badge(STATUS_LABELS[row['status']]+(' / STALE evidence' if stale else ' / current plan'),
                icon=':material/rate_review:',color='orange' if stale else 'primary' if row['status']=='accepted_for_further_review' else 'red' if row['status']=='rejected' else 'blue')
            st.write('Review status: '+STATUS_LABELS[row['status']]+(' / STALE evidence' if stale else ' / current evidence'))
            decision=st.selectbox('Review decision',['accepted_for_further_review','rejected'],format_func=lambda v: STATUS_LABELS[v])
            notes=st.text_area('Selected schedule decision notes',max_chars=5000)
            if st.button('Record review decision',disabled=stale or row['status']!='pending_review'):
                store.decide(review_id,decision,bundle['fingerprint'],notes);st.rerun()
            if not stale:selected_review=applicable_review(store,bundle,review_id)
            with st.expander('Selected review snapshot and decision history'):
                st.json({'evidence':json.loads(row['evidence_json']),'receipt':json.loads(row['receipt_json']),'decisions':store.decision_history(review_id)})
    except (ValueError,sqlite3.Error,OSError) as exc:st.error('Review unavailable or stale; no scenario state changed.')
    return bundle,selected_review
