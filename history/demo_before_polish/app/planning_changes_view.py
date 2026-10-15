"""Interpret → preview → explicit apply, within the existing planner workflow."""

from datetime import datetime, timedelta
import streamlit as st
from copilot.planning_manual import manual_proposal

from copilot.amd import AMDConnectionError, load_config
from copilot.planning_interpreter import interpret, interpret_once, make_request
from copilot.planning_guard import local_decision
from planner.change_requests import (apply_and_reschedule, digest, initial_case, preview_changes, reset_case)
from planner.search import plan


def prepare_case(result, config):
    signature = digest({"source": result.sha256, "filename": result.filename, "base_config": config})
    if st.session_state.get("planning_base_signature") != signature:
        previous = st.session_state.get("planning_last_success")
        if previous and previous[0].source_sha256 != result.sha256:
            st.session_state.pop("planning_last_success", None)
        st.session_state.planning_base_signature = signature
        st.session_state.planning_case = initial_case(result, config)
        st.session_state.pop("planning_interpretation", None)
        st.session_state.pop("planning_failure", None)
    return st.session_state.planning_case


def render_planning_changes(case):
    with st.expander("Planning change request — interpret, preview and confirm"):
        st.caption("Local checks clarify unknown references/dates and block unsupported edits before any API call. "
                   "AMD interprets only supported machine outages and order completion deadlines. "
                   "Use exact IDs and YYYY-MM-DD HH:MM[:SS] in historical scenario time (minutes or seconds). Parsing changes nothing. "
                   "Cleaning permissions, capacities, compatibility and rates cannot be changed here.")
        entry_mode = st.radio("Constraint entry", ["AMD request", "Manual controls"], horizontal=True, key="planning_entry_mode")
        manual_answer = None
        if entry_mode == "Manual controls":
            st.caption("Manual entry: no AMD inference. Preview first; separate confirmation is still required. The confirmation applies the displayed preview, not unsubmitted form edits.")
            operation = st.selectbox("Constraint type", ["Order completion deadline", "Machine outage"], key="manual_operation")
            if operation == "Order completion deadline":
                identifier = st.selectbox("Order ID", [o.order_id for o in case.orders], key="manual_order")
                default = next(o.deadline for o in case.orders if o.order_id == identifier)
            else:
                identifier = st.selectbox("Virtual machine ID", [m.virtual_id for m in case.config.machines], key="manual_machine")
                default = min(o.release for o in case.orders)
            with st.form("manual_constraint_form"):
                day = st.date_input("Deadline date" if operation == "Order completion deadline" else "Outage start date", default.date(), key=f"manual_date_{operation}_{identifier}")
                clock = st.time_input("Deadline time" if operation == "Order completion deadline" else "Outage start time", default.time(), step=timedelta(seconds=1), key=f"manual_time_{operation}_{identifier}")
                values = {"deadline": datetime.combine(day, clock)}
                if operation == "Machine outage":
                    end_day = st.date_input("Outage end date", default.date(), key=f"manual_end_date_{identifier}")
                    end_time = st.time_input("Outage end time", (default + timedelta(hours=1)).time(), step=timedelta(seconds=1), key=f"manual_end_time_{identifier}")
                    values = {"start": datetime.combine(day, clock), "end": datetime.combine(end_day, end_time)}
                submitted = st.form_submit_button("Preview manual change")
            if submitted:
                try:
                    st.session_state.planning_manual_proposal = manual_proposal(case, operation=("order_deadline" if operation == "Order completion deadline" else "machine_unavailability"), identifier=identifier, **values)
                except ValueError as exc:
                    st.session_state.pop("planning_manual_proposal", None)
                    st.error(str(exc))
            manual_answer = st.session_state.get("planning_manual_proposal")
            if manual_answer and manual_answer.request.scenario_fingerprint != case.fingerprint:
                st.session_state.pop("planning_manual_proposal", None)
                manual_answer = None
                st.info("Manual preview invalidated by changed source/scenario. Preview again.")
        busy = bool(st.session_state.get("planning_inflight"))
        stored, fresh = None, False
        if entry_mode == "AMD request":
            if "planning_request_text" not in st.session_state:
                st.session_state.planning_request_text = st.session_state.get("planning_saved_text", "")
            text = st.text_area("Describe an outage or explicit deadline change", key="planning_request_text", max_chars=4000,
                placeholder="Make virtual-Open-Cotton unavailable from 2019-12-20 08:00 to 2019-12-20 18:00.")
            st.session_state.planning_saved_text = text
            request = make_request(case, text) if text.strip() else None
            signature = digest(request.model_dump()) if request else None
            stored = st.session_state.get("planning_interpretation")
            if stored and stored[0] != signature:
                st.session_state.pop("planning_interpretation", None)
                stored = None
                st.info("Previous proposal invalidated by changed request/source/scenario. Interpret again.")
            failure = st.session_state.get("planning_failure")
            if failure and failure[0] != signature:
                st.session_state.pop("planning_failure", None)
                failure = None
            connection = None
            local = local_decision(request) if request else None
            try:
                if local is None:
                    connection = load_config()
            except AMDConnectionError as exc:
                st.caption(str(exc))
            busy = bool(st.session_state.get("planning_inflight"))
            if failure:
                st.error(failure[1])
                st.caption("No constraints or schedules changed. Retry never switches to mock mode.")
                if len(failure) > 2 and failure[2]:
                    with st.expander("Rejected interpretation response receipt"):
                        st.json(failure[2])
            retry = st.button("Retry planning interpretation", disabled=entry_mode != "AMD request" or busy or (connection is None and local is None) or request is None) if failure else False
            slot = st.empty()
            clicked = slot.button("Interpret planning request with AMD", disabled=entry_mode != "AMD request" or busy or request is None or (connection is None and local is None) or bool(stored),
                help="Local decisions make no API call. Supported changes are interpreted by AMD.")
            fresh = False
            if clicked or retry:
                slot.empty()
                slot.button("Checking request locally…" if local is not None else "Waiting for AMD interpretation…", disabled=True, key="planning_waiting")
                try:
                    with st.spinner("Checking locally; no AMD call…" if local is not None else "Interpreting with AMD; scenario remains unchanged…", show_time=True):
                        answer, fresh = interpret_once(st.session_state, request, lambda: interpret(request, config=connection))
                    stored = (signature, answer)
                    st.session_state.pop("planning_failure", None)
                except ValueError as exc:
                    st.session_state.planning_failure = (signature, str(exc), getattr(exc, "receipt", None))
                    st.rerun()
                finally:
                    slot.empty()
        if entry_mode == "Manual controls":
            stored = (None, manual_answer) if manual_answer else None
        if stored:
            answer = stored[1]
            if answer.receipt["origin"] == "manual":
                st.info("Manual constraint proposal: no AMD inference or API request was performed. Confirm the previewed values.")
            elif answer.receipt["origin"] == "local_validation":
                st.info("Local validation only — no AMD inference or API request was performed.")
            elif answer.receipt["origin"] == "mock":
                st.warning("MOCKED interpretation transport — not live AMD inference.")
            elif fresh:
                st.success("Validated live AMD interpretation received. Not yet applied.")
            else:
                st.info("Previously generated live interpretation; this rerun made no API request. Not yet applied.")
            st.text("Original request: " + answer.request.text)
            with st.expander("Interpretation, supporting excerpts and origin receipt"):
                st.json({"proposal": answer.response.model_dump(), "receipt": answer.receipt,
                         "source_sha256": answer.request.source_sha256, "scenario_fingerprint": answer.request.scenario_fingerprint})
            if answer.response.status == "clarification":
                st.info("Clarification needed; no changes can be applied.")
                for question in answer.response.clarification_questions:
                    st.text(question)
            elif answer.response.status == "unsupported":
                st.warning("Unsupported request; no partial changes can be applied.")
                for reason in answer.response.unsupported_reasons:
                    st.text(reason.reason + " — request excerpt: " + reason.supporting_excerpt)
            else:
                try:
                    preview = preview_changes(case, answer)
                    st.write("Before/after constraint preview (not applied)")
                    for row in preview:
                        st.write(row["constraint"] + " · " + row["id"])
                        st.text("Before: " + str(row["before"]) + "\nAfter: " + str(row["after"]))
                    if not preview:
                        st.info("These explicit changes have no effect on current constraints (for example, outage outside availability).")
                    if st.button("Apply changes and reschedule", disabled=busy):
                        with st.spinner("Applying atomically and independently verifying the rerun…"):
                            updated, comparison = apply_and_reschedule(case, answer)
                        st.session_state.planning_case = updated
                        st.session_state.sim_comparison = (updated.fingerprint, comparison)
                        st.session_state.pop("planning_interpretation", None)
                        st.session_state.pop("planning_manual_proposal", None)
                        st.session_state.pop("copilot_answer", None)
                        st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        if case.history:
            st.caption(f"Applied scenario revision {case.revision}; deadline overrides remain separate from the original orders.")
            if st.button("Reset to original scenario and reschedule", disabled=busy):
                updated = reset_case(case)
                with st.spinner("Restoring original constraints and verifying…"):
                    comparison = plan(updated.orders, updated.config)
                st.session_state.planning_case = updated
                st.session_state.sim_comparison = (updated.fingerprint, comparison)
                st.session_state.pop("planning_interpretation", None)
                st.session_state.pop("planning_manual_proposal", None)
                st.session_state.pop("copilot_answer", None)
                st.rerun()
            with st.expander("Applied changes, deadline provenance and reset history"):
                st.json({"history": case.history, "deadline_overrides": case.overrides, "scenario_fingerprint": case.fingerprint})
    return case
