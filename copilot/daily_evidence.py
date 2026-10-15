"""Synthetic-day evidence, isolated from Sitara unresolved-unit facts and scenarios."""

import json

from copilot.documents import ROOT, retrieve_project_sections
from copilot.evidence import fingerprint
from daily.importer import LABEL, require_daily
from daily.models import FEATURES, TARGETS, score_daily

CARD_SCOPE = "doc:resource-model#provenance-and-scope"
CARD_LIMIT = "doc:resource-model#investigation-limitations"


def retrieve_daily_day(result, artifact, date, resource):
    if resource not in TARGETS:
        raise ValueError("Choose water or electricity.")
    frame = require_daily(result)
    matches = frame[frame.Date.dt.strftime("%Y-%m-%d") == date]
    if len(matches) != 1:
        raise ValueError("Selected daily date is not present exactly once in this validated import.")
    scored = score_daily(result, artifact)
    prediction = scored[(scored.Date == date) & (scored.resource == resource)].iloc[0].to_dict()
    row = matches.iloc[0]
    # JSON roundtrip removes numpy scalars; no downloaded code/model is executed.
    return json.loads(json.dumps({"dataset_sha256": result.sha256, "dataset_filename": result.filename,
        "model_version": artifact["metadata"]["model_version"], "model_fingerprint": artifact["artifact_fingerprint"],
        "model_training_dataset_sha256": artifact["metadata"]["dataset_sha256"],
        "date": date, "resource": resource, "prediction": prediction,
        "inputs": {field: float(row[field]) for field in FEATURES},
        "evaluation": artifact["metadata"]["results"][resource], "splits": artifact["metadata"]["splits"],
        "threshold_method": artifact["metadata"]["threshold_method"],
        "evaluation_matches_loaded_dataset": result.sha256 == artifact["metadata"]["dataset_sha256"]}, default=str))


def build_daily_evidence(context, question):
    if not context or "prediction" not in context:
        raise ValueError("Select a validated synthetic resource day in Daily resource monitoring first.")
    docs, hashes = retrieve_project_sections(question, documents={"resource-model": ROOT / "reports/resource_model_card.md"},
                                            mandatory=[CARD_SCOPE, CARD_LIMIT])
    p = context["prediction"]
    unit = p["unit"]
    expected_unit = TARGETS[context["resource"]][1]
    if unit != expected_unit:
        raise ValueError("Daily resource/unit context mismatch.")
    facts = {"fact:daily.provenance": {"value": {"label": LABEL, "filename": context["dataset_filename"],
                "sha256": context["dataset_sha256"], "unit_of_observation": "synthetic daily thread-dyeing aggregate",
                "source": "10.17632/wfwxybkpcm.1", "licence": "CC BY 4.0, Ananya Halder",
                "not_measured_factory_telemetry": True}, "unit": "identity", "kind": "synthetic_provenance"},
             "fact:daily.model": {"value": {key: context[key] for key in ("model_version", "model_fingerprint",
                 "model_training_dataset_sha256", "evaluation_matches_loaded_dataset")}, "unit": "model identity", "kind": "synthetic_model"},
             "fact:daily.day": {"value": {"date": context["date"], "resource": context["resource"], "phase": p["phase"]},
                "unit": "daily record", "kind": "synthetic_daily_record"},
             "fact:daily.inputs": {"value": context["inputs"], "unit": "documented feature units; retrospective observations", "kind": "synthetic_daily_inputs"},
             "fact:daily.evaluation": {"value": context["evaluation"], "unit": unit, "kind": "synthetic_evaluation"},
             "fact:daily.threshold_method": {"value": context["threshold_method"], "unit": "method", "kind": "synthetic_threshold"}}
    for field in ("observed", "predicted", "upper_threshold", "difference", "excess_over_threshold"):
        facts["fact:daily." + field] = {"value": str(p[field]), "unit": unit, "kind": "synthetic_consumption_analysis"}
    facts["fact:daily.investigation_flag"] = {"value": p["investigation_flag"], "unit": "investigation boolean, not fault label", "kind": "synthetic_flag"}
    statements = {
        "recorded_boundary": {"text": "This evidence concerns synthetic daily thread-dyeing aggregates, not measured factory telemetry or individual fabric batches.",
                              "evidence_references": ["fact:daily.provenance", CARD_SCOPE]},
        "daily_threshold": {"text": ("The selected synthetic day is flagged because observed consumption exceeds the empirical upper expected threshold."
            if p["investigation_flag"] else "The selected synthetic day has no test investigation flag; check its phase and observed value against the displayed threshold."),
            "evidence_references": ["fact:daily.day", "fact:daily.observed", "fact:daily.predicted", "fact:daily.upper_threshold", "fact:daily.excess_over_threshold", "fact:daily.investigation_flag"]},
        "daily_conditions": {"text": "The displayed workload and process conditions are retrospective observations; they do not establish a causal root cause or a planned production forecast.",
                             "evidence_references": ["fact:daily.inputs", CARD_LIMIT]},
        "daily_calibration": {"text": "The upper threshold is calibrated on validation residuals; model selection and evaluation use chronological separation and do not establish anomaly accuracy.",
                              "evidence_references": ["fact:daily.model", "fact:daily.evaluation", "fact:daily.threshold_method", CARD_LIMIT]},
        "daily_investigation": {"text": "Review the synthetic daily input records, production basis, unit definitions and quality or rework context before attributing consumption to an operational cause.",
                                "evidence_references": ["fact:daily.inputs", "fact:daily.difference", CARD_LIMIT]}}
    identity = {"context": context, "document_hashes": hashes}
    day_hash = fingerprint({"date": context["date"], "resource": context["resource"], "prediction": p, "inputs": context["inputs"]})
    return {"kind": "synthetic_daily", "fingerprint": fingerprint(identity), "source_fingerprint": context["dataset_sha256"],
        "scenario_fingerprint": fingerprint({"model": context["model_fingerprint"], "day": day_hash}),
        "model_fingerprint": context["model_fingerprint"], "day_fingerprint": day_hash, "document_hashes": hashes,
        "facts": facts, "documents": docs, "scenario": None, "scenario_error": None, "daily_context": context,
        "tool_trace": ["retrieve_daily_day", "retrieve_project_sections"],
        "catalog": {"statements": statements, "assumptions": {"source_units": "Only this synthetic context uses documented L/kg or kWh/kg units; Sitara source units remain unresolved.",
            "retrospective": "Inputs are retrospective daily observations; planned-value availability is not established."},
            "limitations": {"not_sops": "The project model card is not an approved machine SOP and establishes no machine safety.",
                "no_factory_approval": "Review acceptance grants no factory approval, recipe change or machine control.",
                "limited_scope": "This is historical synthetic daily analysis, not live sensors, causal optimisation or real-factory validation.",
                "unresolved_source": "There are no independently verified fault/anomaly labels; Day_Type is excluded from predictors and ground truth.",
                "unsupported_question": "The supplied facts cannot establish root causes, recoverable savings or industrial procedures."},
            "review_actions": {"investigate_synthetic_day": "Inspect daily record consistency, production basis, retrospective inputs and quality/rework information; request technical review without assuming a root cause.",
                               "request_approved_documentation": "Request approved factory documentation and qualified review; this model card is not a machine procedure."}}}
