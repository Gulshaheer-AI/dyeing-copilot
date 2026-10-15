"""Evidence-grounded AMD explanation; supervisor actions remain separate UI events."""

import json
import sqlite3

import streamlit as st

from copilot.amd import AMDConnectionError, load_config
from copilot.evidence import build_evidence, fingerprint
from copilot.reviews import ReviewStore
from copilot.workflow import explain
from copilot.daily_evidence import build_daily_evidence
from copilot.session import generate_once

QUESTIONS = {
    "Questions about imported orders and recorded analysis": ("recorded", "Explain the recorded resource totals and their limitations."),
    "Explain this schedule comparison": ("scenario", "Explain this schedule comparison."),
    "Why did demand change or remain unchanged?": ("scenario", "Why did resource demand change or remain unchanged in this scenario?"),
    "Which assumptions drive this result?": ("scenario", "Which assumptions drive this scenario result?"),
    "What must a factory validate before use?": ("scenario", "What must a factory validate before using this proposal?"),
}


def render_copilot(result, *, daily_context=None):
    st.subheader("Copilot and supervisor review")
    st.caption("Read-only evidence workflow. Numbers come from Python; AMD selects supported statements and citations. "
               "These documents are project notes, not approved machine SOPs. Monitoring and safety scope remain incomplete.")
    topics = dict(QUESTIONS)
    selected_context=st.session_state.get('sim_context',{})
    if result is not None and selected_context.get('source_sha256')==result.sha256 and selected_context.get('selected_run') is not None:
        topics={'Explain selected schedule':('selected','Explain the selected schedule.'),**topics}
    selected_daily = daily_context or st.session_state.get("daily_context")
    if selected_daily:
        daily_topics = {"Explain selected synthetic resource day": ("daily", "Explain why this synthetic daily resource record was flagged or not flagged."),
                        "What does the threshold mean?": ("daily", "What does the upper expected consumption threshold mean, and what are its limitations?"),
                        "What should a supervisor investigate for this synthetic day?": ("daily", "What information should a supervisor investigate for this synthetic resource day?")}
        topics = daily_topics if daily_context is not None else {**topics, **daily_topics}
    requested = st.session_state.pop("copilot_requested_topic", None)
    if requested in topics:
        st.session_state.copilot_topic = requested
    if st.session_state.get("copilot_topic") not in topics:
        st.session_state.copilot_topic = next(iter(topics))
    topic = st.selectbox("Question topic", list(topics), key="copilot_topic")
    st.caption("Supported answers select evidence-backed statements about these records, thresholds and scenarios. "
               "This is not unrestricted diagnosis or approved safety guidance.")
    scope, default_question = topics[topic]
    if scope=='selected':
        from app.selected_copilot_view import render_selected_copilot
        render_selected_copilot(selected_context['case'],selected_context['selected_run'],source=result,context_marker=selected_context.get('marker'))
        return
    custom = st.text_input("Optional specific question (for example: describe order 27 or customer CGU)", max_chars=2000)
    question = custom.strip() or default_question
    mode_label = st.radio("Explanation source", ["Live AMD", "Mock demonstration (no API call)"], horizontal=True)
    mode = "live_amd" if mode_label == "Live AMD" else "mock"
    context = st.session_state.get("sim_context", {})
    if result is None or context.get("source_sha256") != result.sha256:
        context = {}
    if scope == "daily":
        bundle = build_daily_evidence(selected_daily, question)
        st.warning("Synthetic daily thread-dyeing data — retrospective analysis; not measured factory telemetry or individual batches.")
    else:
        bundle = build_evidence(result, question, config=context.get("config"), comparison=context.get("comparison"),
                                context_marker=context.get("marker"), case=context.get("case"))
    current = fingerprint({"bundle": bundle["fingerprint"], "question": question, "scope": scope, "mode": mode})
    stored = st.session_state.get("copilot_answer")
    failure = st.session_state.get("copilot_failure")
    if failure and failure[0] != current:
        st.session_state.pop("copilot_failure", None)
        failure = None
    if stored and stored[0] != current:
        st.session_state.pop("copilot_answer", None)
        stored = None
        st.info("Previous explanation invalidated by changed evidence, question or mode. Generate a current explanation.")
    if scope == "daily":
        columns = st.columns(4)
        for col, ref in zip(columns, ("observed", "predicted", "upper_threshold", "difference")):
            fact = bundle["facts"]["fact:daily." + ref]
            col.metric(ref.replace("_", " ").capitalize() + " (" + fact["unit"] + ")", fact["value"])
    else:
        total = bundle["facts"]["fact:recorded.water_total_source"]
        st.metric("Recorded modelled total (unresolved source units)", total["value"])
    if bundle["scenario"]:
        columns = st.columns(4)
        for column, ref, label in zip(columns, ("baseline.total", "proposal.total", "difference", "percentage"),
                                      ("Scenario baseline", "Scenario proposal", "Scenario difference", "Difference / recalculated baseline")):
            fact = bundle["facts"]["fact:scenario." + ref]
            column.metric(label + " (" + fact["unit"] + ")", fact["value"] if fact["value"] is not None else "undefined")
    elif scope != "daily":
        st.info(bundle["scenario_error"] or "No current verified comparison. Recorded-data questions are available; run the simulator for scenario questions.")
    connection = None
    if mode == "mock":
        st.warning("MOCK DEMONSTRATION — deterministic test content; no AMD inference is performed.")
    else:
        try:
            connection = load_config()
            st.caption("AMD participant configuration loaded. Live success is reported only after an accepted response.")
        except AMDConnectionError as exc:
            st.error(str(exc))
    fresh = False
    if failure:
        st.error(failure[1])
        st.caption("The computed schedules are preserved. Retry uses the current evidence; no mock fallback is performed.")
    retry = st.button("Retry explanation", disabled=bool(stored or st.session_state.get("copilot_inflight")
                      or (mode == "live_amd" and connection is None))) if failure else False
    action = st.empty()
    generate = action.button("Generate grounded explanation", disabled=bool(stored or st.session_state.get("copilot_inflight")
                      or (mode == "live_amd" and connection is None)))
    if retry or generate:
        action.empty()
        action.button("Waiting for explanation…", disabled=True, key="copilot_waiting")
        try:
            with st.spinner("Waiting for AMD and validating evidence…" if mode == "live_amd" else "Preparing labelled mock demonstration…", show_time=True):
                answer, fresh = generate_once(st.session_state, current,
                    lambda: explain(bundle, question, scope=scope, mode=mode, config=connection))
            stored = (current, answer)
            st.session_state.pop("copilot_failure", None)
        except ValueError as exc:
            # All workflow errors are curated; raw provider responses/schema input are never shown.
            st.session_state.pop("copilot_answer", None)
            st.session_state.copilot_failure = (current, str(exc))
            stored = None
            st.rerun()
        finally:
            action.empty()
    if stored:
        answer = stored[1]
        if answer.receipt["origin"] == "mock":
            st.warning("MOCKED EXPLANATION — not successful live AMD inference.")
        elif fresh:
            st.success("Validated live AMD response received.")
        else:
            st.info("CACHED validated AMD response — this rerun made no new inference request. Original receipt follows.")
        with st.expander("Response origin, model and request receipt"):
            st.json(answer.receipt)
        for claim in answer.output.explanation:
            st.write(claim.text)
        with st.expander("Explanation assumptions and limitations"):
            for field in ("assumptions", "limitations"):
                st.subheader(field.capitalize())
                for key in getattr(answer.output, field):
                    st.write(bundle["catalog"][field][key])
        st.subheader("Proposed review action")
        st.write(bundle["catalog"]["review_actions"][answer.output.proposed_review_action])
        with st.expander("Referenced Python facts and supporting passages"):
            for claim in answer.output.explanation:
                st.caption("Evidence: " + ", ".join(claim.evidence_references))
            for ref in answer.output.evidence_references:
                st.caption(ref)
                if ref in bundle["facts"]:
                    st.json(bundle["facts"][ref])
                else:
                    doc = bundle["documents"][ref]
                    st.caption(doc["path"] + " · " + doc["section"] + " · SHA256 " + doc["sha256"])
                    st.text(doc["passage"])
    with st.expander("Current evidence snapshot (read-only)"):
        st.json(bundle)
    st.subheader("Supervisor review")
    st.caption("Accepting for further review does not approve factory use, enable exemptions or actuate equipment. "
               "Historical snapshots are retained; stale items cannot receive a decision.")
    try:
        store = ReviewStore()
        if stored:
            notes = st.text_area("Optional notes for pending review", max_chars=5000)
            if st.button("Save recommendation as pending review"):
                store.save_pending(stored[1], bundle, notes)
                st.success("Saved pending review with exact evidence snapshot.")
        reviews = store.list_reviews()
        if reviews:
            selected = st.selectbox("Saved review", [row["id"] for row in reviews], format_func=lambda key: next(
                row["created_at"] + " · " + row["status"] + " · " + json.loads(row["receipt_json"])["origin"]
                for row in reviews if row["id"] == key))
            row = next(row for row in reviews if row["id"] == selected)
            stale = row["fingerprint"] != bundle["fingerprint"]
            st.write("Status: " + row["status"] + (" · STALE evidence" if stale else " · current evidence"))
            with st.expander("Saved evidence, explanation and decision history"):
                st.json({"snapshot": json.loads(row["evidence_json"]), "explanation": json.loads(row["answer_json"]),
                         "receipt": json.loads(row["receipt_json"]), "pending_notes": row["notes"],
                         "decisions": store.decision_history(selected)})
            decision = st.selectbox("Review decision", ["accepted_for_further_review", "rejected"])
            notes = st.text_area("Optional decision notes", max_chars=5000)
            if st.button("Record review decision", disabled=stale or row["status"] != "pending_review"):
                store.decide(selected, decision, bundle["fingerprint"], notes)
                st.success("Decision saved for further review only; scenario permissions remain unchanged.")
                st.rerun()
    except (ValueError, sqlite3.Error, OSError):
        st.error("Could not save/read this review, or it is stale/already decided. No scenario state was changed.")
