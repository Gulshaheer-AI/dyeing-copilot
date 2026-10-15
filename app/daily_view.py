"""Separate synthetic daily monitoring and historical replay; inference only."""

import hashlib
from pathlib import Path

import pandas as pd
import streamlit as st

from app.copilot_view import render_copilot
from copilot.daily_evidence import retrieve_daily_day
from daily.importer import LABEL, import_daily, load_bundled_daily
from daily.models import ARTIFACT_DIR, FEATURES, load_models, score_daily
from daily.profile import profile_daily


@st.cache_resource
def _load_cached_models(directory, metadata_hash, model_hash):
    return load_models(Path(directory))


def current_models(directory=ARTIFACT_DIR):
    directory = Path(directory)
    # Hashes invalidate cached inference objects when artifacts are replaced; never train here.
    return _load_cached_models(str(directory), hashlib.sha256((directory / "metadata.json").read_bytes()).hexdigest(),
                               hashlib.sha256((directory / "models.joblib").read_bytes()).hexdigest())


def render_daily():
    st.subheader("Daily resource monitoring")
    st.warning(LABEL + " — retrospective daily aggregates; not measured factory telemetry.")
    st.caption("Select a flagged day → inspect values → explain with AMD → save an investigation for supervisor review.")
    mode = st.radio("Daily dataset source", ["Bundled synthetic daily CSV", "Upload synthetic daily CSV"], horizontal=True)
    if mode == "Upload synthetic daily CSV":
        uploaded = st.file_uploader("Synthetic daily CSV (39 documented unit-bearing fields)", type=["csv"])
        if uploaded is None:
            st.session_state.pop("daily_context", None)
            st.info("Choose a separate synthetic daily CSV. Sitara orders are not accepted here.")
            return
        result = import_daily(uploaded.getvalue(), uploaded.name)
    else:
        result = load_bundled_daily()
    if result.issues:
        st.dataframe(pd.DataFrame(result.issues), hide_index=True)
    if not result.valid:
        st.session_state.pop("daily_context", None)
        st.error("Daily import rejected. No predictions or partial daily records are displayed.")
        return
    st.metric("Accepted synthetic daily records", len(result.frame))
    with st.expander("Daily data provenance, profile and limitations"):
        st.caption("Loaded dataset SHA256: " + result.sha256)
        st.write("Daily thread-production aggregates, not fabric batches. Retrospective observations do not establish "
                 "pre-production forecasting, causal optimisation, live monitoring, confirmed waste or machine faults.")
        st.json(profile_daily(result))
    try:
        artifact = current_models()
    except (OSError, ValueError, KeyError) as exc:
        st.session_state.pop("daily_context", None)
        st.error("Daily models are missing or stale. Run .venv/Scripts/python.exe tools/train_daily_resources.py. " + str(exc))
        return
    meta = artifact["metadata"]
    st.caption("Model version: " + meta["model_version"] + " · trained dataset SHA256: " + meta["dataset_sha256"])
    st.caption("Inputs are retrospective observations. Predictions and residuals do not establish waste, faults, safety hazards or recoverable savings.")
    if result.sha256 != meta["dataset_sha256"]:
        st.warning("Loaded hash differs from the training/evaluation dataset. Frozen evaluation below describes the original training dataset; "
                   "uploaded records use saved-model inference, not a new untouched test evaluation. All uploads in this view are labelled synthetic.")
    with st.expander("Frozen evaluation, split dates and threshold method"):
        st.json({"splits": meta["splits"], "evaluation": meta["results"], "threshold_method": meta["threshold_method"]})
        st.caption("No independent anomaly labels: no precision, recall or fault-detection accuracy. Day_Type is excluded from inputs and ground truth. "
                   "The upper expected threshold is empirical validation calibration, not guaranteed interval coverage.")
    resource = st.selectbox("Daily resource", ["water", "electricity"])
    scored = score_daily(result, artifact)
    rows = scored[(scored.resource == resource) & scored.flag_eligible].copy()
    if rows.empty:
        st.session_state.pop("daily_context", None)
        st.info("No loaded dates fall after the saved validation cutoff. Training/calibration days are not treated as unseen test flags.")
        return
    replay = st.checkbox("Replay of synthetic daily records")
    if replay:
        index = st.slider("Replay position (historical dates; not a live sensor)", 0, len(rows) - 1, 0) if len(rows) > 1 else 0
        rows = rows.iloc[:index + 1].copy()
        st.info("Replay of synthetic daily records — historical prefix only; no live sensor connection.")
    chart = rows.set_index(pd.to_datetime(rows.Date))[["observed", "predicted", "upper_threshold"]]
    st.subheader("Dated observed-versus-expected trend")
    st.caption("Resource unit: " + rows.unit.iloc[0] + ". Trend and investigation list show held-out/replay dates only.")
    st.line_chart(chart)
    st.subheader("Investigation flags (unusual consumption)")
    flags = rows[rows.investigation_flag]
    st.metric("Flags in displayed synthetic period", len(flags))
    st.dataframe(flags, hide_index=True, width="stretch")
    with st.expander("All displayed observations and expected values"):
        st.dataframe(rows, hide_index=True, width="stretch")
    flagged_dates = set(flags.Date)
    dates = rows.Date.tolist()
    default = next((i for i, day in enumerate(dates) if day in flagged_dates), 0)
    date = st.selectbox("Selected synthetic day", dates, index=default,
                        help="Defaults to the first flagged day in this displayed period. Flagged dates appear in the investigation table above.")
    context = retrieve_daily_day(result, artifact, date, resource)
    st.session_state.daily_context = context
    st.subheader("Selected-day detail")
    selected = rows[rows.Date == date].iloc[0]
    st.info(date + " · " + ("Investigation flag: observed consumption exceeds the upper threshold." if selected.investigation_flag
                            else "Observed consumption is within the upper threshold."))
    cols = st.columns(4)
    for col, field, label in zip(cols, ("observed", "predicted", "upper_threshold", "difference"),
                                  ("Observed", "Expected", "Upper threshold", "Observed minus expected")):
        col.metric(label + " (" + selected.unit + ")", f"{selected[field]:.6f}")
    with st.expander("Selected-day input conditions and exact evidence"):
        st.json({"synthetic": True, "date": date, "resource": resource, "model_version": meta["model_version"],
                 "prediction": context["prediction"], "retrospective_inputs": context["inputs"]})
    st.caption("Selected-day evidence is also available in the Copilot view. No root cause is inferred from a residual.")
    if st.checkbox("Explain this selected day with AMD copilot"):
        render_copilot(None, daily_context=context)
    st.caption("Source: Ananya Halder, Mendeley Data v1, DOI 10.17632/wfwxybkpcm.1, CC BY 4.0. Original dataset files remain unchanged.")
