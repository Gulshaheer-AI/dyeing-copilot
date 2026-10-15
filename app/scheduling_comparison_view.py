"""Cleaning/deadline-first view of independently checked heuristic comparators."""

import pandas as pd
import streamlit as st

from planner.comparison import RULE_LABELS
from planner.comparators import METHODS


def render_method_comparison(report):
    st.subheader("Heuristic comparison: cleaning and deadlines")
    st.caption("Same effective orders and constraints for every method. Grouping is a heuristic comparator, not a real factory planner. Failed constructions are never replaced with EDD.")
    table = []
    for method, row in report["methods"].items():
        counts = row["cleaning_counts"] or {}
        due = row["deadline_performance"] or {}
        table.append({"Method": method, "Construction": row["construction_status"], "Verification": row["verification_status"],
            "Initial cleanings": counts.get("initial"), "Between-order cleanings": counts.get("between_orders"),
            "Terminal cleanings": counts.get("terminal"), "Total cleanings": counts.get("total"),
            "On time": due.get("on_time"), "Missing": due.get("missing"), "Late": due.get("late"),
            "Minimum slack (h)": str(row["slack_hours"]["minimum"]) if row["slack_hours"]["minimum"] is not None else None,
            "Median slack (h)": str(row["slack_hours"]["median"]) if row["slack_hours"]["median"] is not None else None,
            "Runtime (s)": round(row["runtime_seconds"], 6)})
    st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch")
    st.caption("Counts/slack for a failed construction describe its partial artifact only, never a valid recommendation. Missing optimiser proposals have no fabricated metrics. Runtime includes search/construction and verification/accounting; optimiser time includes its internal EDD and candidate checks.")
    for method, difference in report["optimiser_against"].items():
        if difference["eligible"]:
            count = difference["cleaning_events_difference"]
            message = (f"Optimiser uses {count} fewer cleaning events than {method}." if count > 0 else
                       f"Optimiser and {method} have equal cleaning-event counts." if count == 0 else
                       f"{method} uses {-count} fewer cleaning events than optimiser.")
            st.info(message + " Both schedules independently verified; review deadline slack too.")
        else:
            st.warning(f"Optimiser versus {method}: unavailable. {difference['reason']}")
    with st.expander("Comparator method definitions, construction errors and verification"):
        st.json({"definitions": METHODS, "effective_case_fingerprint": report["effective_case_fingerprint"],
            "checks": {name: {k: row[k] for k in ("construction_status", "construction_errors", "verification_status", "verification_errors")}
                       for name, row in report["methods"].items()}})
    valid_pairs = [name for name, value in report["optimiser_against"].items() if value["eligible"]]
    if valid_pairs:
        comparator = st.selectbox("Inspect machine sequence changes against", valid_pairs, key="method_transition_comparator")
        changes = report["optimiser_against"][comparator]["transition_comparison"]
        machine = st.selectbox("Inspect virtual machine", list(changes["machine_sequences"]["baseline"]), key="method_transition_machine")
        st.caption("Compact positional view; time gaps are omitted. Initial and terminal boundaries are included. An arrow is a predecessor link, never proof of recipe compatibility.")
        before = changes["machine_sequences"]["baseline"][machine]
        after = changes["machine_sequences"]["proposal"][machine]
        st.write(f"{comparator}: INITIAL > " + " > ".join(before) + " > TERMINAL" if before else f"{comparator}: unused machine")
        st.write("optimiser: INITIAL > " + " > ".join(after) + " > TERMINAL" if after else "optimiser: unused machine")
        rows = []
        for row in changes["order_transitions"]:
            if machine not in (row["baseline"]["machine"], row["proposal"]["machine"]):
                continue
            rows.append({"Order": row["order_id"], "Changed transition": row["transition_changed"],
                **{f"{label} {key}": RULE_LABELS[row[side][key]] if key == "rule" else row[side][key]
                   for side, label in (("baseline", comparator), ("proposal", "optimiser"))
                   for key in ("machine", "position", "predecessor", "cleaning_required", "rule")}})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        terminal = next(r for r in changes["terminal_transitions"] if r["machine"] == machine)
        st.caption(f"Terminal cleaning: {comparator}={terminal['baseline']['cleaning_required']}, optimiser={terminal['proposal']['cleaning_required']}. Transition accounting reconciles including both boundaries.")
    with st.expander("Secondary modelled resource scores and signed percentages (unresolved units)"):
        st.caption("Invented scenario process terms; not measured consumption or factory savings. Comparator minus optimiser; percentages use that valid comparator's modelled total. Recorded 47,950 is never a savings baseline.")
        st.json({"resources": {name: row["resource"] for name, row in report["methods"].items()},
            "differences": {name: {k: row[k] for k in ("eligible", "resource_difference", "percentage_difference", "sign")}
                            for name, row in report["optimiser_against"].items()}})
