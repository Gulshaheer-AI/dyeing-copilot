"""Read-only facts and fresh verified comparison retrieval. No planner mutation tools."""

import hashlib
import json
from dataclasses import asdict
from decimal import Decimal

from app.resource_analysis import analyze_resources
from app.importer import SOURCE_KEY
from copilot.documents import AUDIT_BOUNDARY, MODEL_EQUATIONS, retrieve_project_sections
from planner.review_package import export_review_package
from planner.scenario import to_json


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def retrieve_recorded_facts(result):
    summary = analyze_resources(result).overall
    facts = {"fact:source.identity": {"value": {"dataset": "Sitara Faisalabad", "filename": result.filename,
             "sha256": result.sha256, "licence": "CC BY per archived article metadata; uploaded-copy rights are not authenticated",
             "input_origin": "bundled_manifest_checked_case" if result.filename == SOURCE_KEY else "uploaded_unverified_copy"},
             "kind": "provenance", "unit": "identity"},
             "fact:recorded.count": {"value": summary.order_count, "kind": "recorded", "unit": "orders"}}
    for field, value in summary.totals.items():
        facts["fact:recorded." + field] = {"value": str(value), "unit": "unresolved source units", "kind": "recorded_modelled"}
    for field, groups in summary.groups.items():
        for index, group in enumerate(groups):
            facts[f"fact:recorded.group.{field}.{index}"] = {"value": json.loads(to_json(group)),
                    "unit": "recorded fields; unresolved source units", "kind": "recorded_group"}
    for record in result.records:
        facts[f"fact:recorded.order.{record['source_row_id']}"] = {"value": json.loads(to_json(record)),
            "unit": "source fields with unresolved quantity/time/water units", "kind": "recorded_order"}
    for row in summary.ranked_orders:
        facts[f"fact:recorded.contribution.{row['source_row_id']}"] = {
            "value": None if row["overall_case_contribution_pct"] is None else str(row["overall_case_contribution_pct"]),
            "unit": "% of recorded total", "kind": "calculated_recorded_share"}
    return facts


def retrieve_comparison(result, config, comparison, *, case=None):
    # Export re-verifies both schedules and recalculates resources instead of trusting cached summaries.
    artifact = json.loads(export_review_package(result, config, comparison, case=case))
    resources = artifact["scenario_resources"]
    facts = {"fact:scenario.config": {"value": artifact["assumptions"], "unit": "hypothetical assumptions", "kind": "assumed"},
             "fact:scenario.verification": {"value": artifact["verification"], "unit": "scenario checks", "kind": "verified_scenario"}}
    for label in ("baseline", "proposal"):
        for field, value in resources[label].items():
            facts[f"fact:scenario.{label}.{field}"] = {"value": value,
                "unit": "events" if field == "cleaning_events" else config.resource_unit, "kind": "modelled_scenario"}
    baseline, proposal = resources["baseline"], resources["proposal"]
    difference = Decimal(baseline["total"]) - Decimal(proposal["total"])
    facts["fact:scenario.difference"] = {"value": str(difference), "unit": config.resource_unit, "kind": "calculated_scenario_difference"}
    facts["fact:scenario.percentage"] = {"value": str(difference * 100 / Decimal(baseline["total"]))
        if Decimal(baseline["total"]) else None, "unit": "% of recalculated baseline", "kind": "calculated_scenario_difference"}
    facts["fact:scenario.cleaning_events_difference"] = {"value": baseline["cleaning_events"] - proposal["cleaning_events"],
        "unit": "events", "kind": "calculated_scenario_difference"}
    changes = artifact["planner_comparison"]
    facts["fact:scenario.change.summary"] = {"value": {"changes": changes["changes"],
        "cleaning_counts": changes["cleaning_counts"], "reconciliation": changes["reconciliation"]},
        "unit": "scenario transition accounting", "kind": "computed_comparison"}
    facts["fact:scenario.deadlines"] = {"value": {label: {k: v for k, v in data.items() if k != "orders"}
        for label, data in changes["deadlines"].items()}, "unit": "orders under scenario deadlines", "kind": "computed_comparison"}
    facts["fact:scenario.terminal_transitions"] = {"value": changes["terminal_transitions"],
        "unit": "scenario terminal cleanup", "kind": "computed_comparison"}
    for row in changes["order_transitions"]:
        facts["fact:scenario.transition." + row["order_id"]] = {"value": row,
            "unit": "scenario order transition; resource difference in modelled source units", "kind": "scenario_order_change"}
    return facts, artifact


def build_evidence(result, question, *, config=None, comparison=None, context_marker=None, case=None):
    facts = retrieve_recorded_facts(result)
    documents, document_hashes = retrieve_project_sections(question)
    scenario, scenario_error = None, None
    if config is not None and comparison is not None:
        try:
            scenario_facts, scenario = retrieve_comparison(result, config, comparison, case=case)
            facts.update(scenario_facts)
        except (ValueError, TypeError, AttributeError):
            scenario_error = "No current comparison passes independent verification. Rerun the simulator."
    config_data = json.loads(to_json(config)) if config is not None else None
    identity = {"evidence_schema_version": "planner-review-v1", "source_sha256": result.sha256, "source_filename": result.filename,
                "scenario_config": config_data, "scenario_artifact": scenario,
                "context_marker": context_marker, "document_hashes": document_hashes}
    bundle = {"fingerprint": fingerprint(identity), "source_fingerprint": result.sha256,
              "scenario_fingerprint": fingerprint({"config": config_data, "artifact": scenario, "marker": context_marker}),
              "document_hashes": document_hashes, "facts": facts, "documents": documents,
              "scenario": scenario, "scenario_error": scenario_error,
              "tool_trace": ["retrieve_recorded_facts", "retrieve_project_sections"] + (["retrieve_comparison"] if scenario else []),
              "limitations": ["Recorded water is modelled, not independently established meter readings.",
                  "Source units remain unresolved; no litres, kg or currency conversion is established.",
                  "Virtual machines and recipe/quality permissions are hypothetical.",
                  "Project documents are not approved machine SOPs and establish no machine safety.",
                  "Monitoring, anomaly detection, training and live safety coverage are not implemented."]}
    bundle["catalog"] = _catalog(bundle)
    return bundle


def _catalog(bundle):
    statements = {}
    def add(key, text, refs):
        statements[key] = {"text": text, "evidence_references": refs}
    add("recorded_boundary", "Recorded resource totals describe modelled source fields with unresolved units; "
        "they are not independent meter readings or a scenario baseline.",
        ["fact:recorded.water_total_source", AUDIT_BOUNDARY])
    add("recorded_components", "The recorded components and total are calculated from the accepted import; source values remain unchanged.",
        ["fact:recorded.water_component_1_source", "fact:recorded.water_component_2_source", "fact:recorded.water_component_3_source"])
    for ref, fact in bundle["facts"].items():
        if fact["kind"] in ("recorded_order", "recorded_group", "calculated_recorded_share"):
            add(ref.removeprefix("fact:").replace(".", "_"),
                "The cited Python fact provides the requested imported record, grouping or contribution; source spellings are preserved.", [ref])
    if bundle["scenario"]:
        add("verified_comparison", "Both schedules pass independent scenario checks; this establishes hypothetical feasibility only.",
            ["fact:scenario.verification", MODEL_EQUATIONS])
        unchanged = Decimal(bundle["facts"]["fact:scenario.difference"]["value"]) == 0
        add("demand_change", "Modelled resource demand remained unchanged under this configuration." if unchanged else
            "Modelled resource demand decreased under the configured assumptions; this is not realised factory savings.",
            ["fact:scenario.difference", "fact:scenario.percentage", "fact:scenario.cleaning_events_difference"])
        add("process_and_cleaning", "The comparison separates quantity-based process terms from sequence-dependent and terminal cleaning demand.",
            ["fact:scenario.baseline.process_a", "fact:scenario.proposal.process_a", "fact:scenario.baseline.process_b",
             "fact:scenario.proposal.process_b", "fact:scenario.baseline.cleaning_before_orders", "fact:scenario.proposal.cleaning_before_orders", MODEL_EQUATIONS])
        add("configured_drivers", "Virtual capacity, operating windows, duration interpretation, initial state, terminal cleanup and exact transition permissions drive the scenario result.",
            ["fact:scenario.config", MODEL_EQUATIONS])
        counts = bundle["facts"]["fact:scenario.change.summary"]["value"]
        deadlines = bundle["facts"]["fact:scenario.deadlines"]["value"]
        a, b = counts["cleaning_counts"]["baseline"], counts["cleaning_counts"]["proposal"]
        change = counts["changes"]
        add("planner_summary",
            f"Cleaning events go from {a['total']} to {b['total']}, including initial and terminal cleanup. "
            f"The baseline has {deadlines['baseline']['on_time']} on-time orders and the proposal has {deadlines['proposal']['on_time']}; "
            f"late orders are {deadlines['baseline']['late']} and {deadlines['proposal']['late']}, respectively, under scenario deadlines. "
            f"Machine assignments change for {change['machine_assignments']} orders and sequence positions for {change['sequence_positions']} orders.",
            ["fact:scenario.change.summary", "fact:scenario.deadlines", "fact:scenario.terminal_transitions"])
        rows = [fact["value"] for fact in bundle["facts"].values() if fact["kind"] == "scenario_order_change"]
        examples = sorted((r for r in rows if r["transition_changed"]),
                          key=lambda r: (r["cleaning_events_difference"] == 0, int(r["order_id"])))[:3]
        reasons = {"initial_dirty": "the machine starts dirty", "configured_initially_clean": "the machine is configured initially clean",
                   "exemptions_disabled": "cleaning exemptions are disabled", "no_exact_permission": "no activated exact directed permission applies",
                   "activated_exact_permission": "an activated exact directed permission applies"}
        def describe(row):
            parts = []
            for label in ("baseline", "proposal"):
                side = row[label]
                predecessor = "the initial state" if side["predecessor"] is None else "order " + side["predecessor"]
                parts.append(f"{label}: follows {predecessor} on {json.dumps(side['machine'])}, "
                             f"position {side['position']}; cleaning {'required' if side['cleaning_required'] else 'not required'} "
                             f"because {reasons[side['rule']]}")
            return f"Order {row['order_id']} — " + "; ".join(parts) + "."
        for row in rows:
            add("planner_order_" + row["order_id"], describe(row), ["fact:scenario.transition." + row["order_id"]])
        if examples:
            add("transition_examples", " ".join(describe(row) for row in examples),
                ["fact:scenario.transition." + row["order_id"] for row in examples])
        else:
            add("transition_examples", "No machine assignment, sequence position or predecessor cleaning transition changed.",
                ["fact:scenario.change.summary"])
    return {"statements": statements,
        "assumptions": {"source_units": "Source quantity, duration and water units remain unresolved.",
            **({"scenario_config": "All virtual equipment, rates, calendars and cleaning permissions are declared scenario assumptions."} if bundle["scenario"] else {})},
        "limitations": {"not_sops": "The retrieved project documents are not approved machine SOPs; machine safety is not established.",
            "no_factory_approval": "A review decision is not factory approval and cannot change permissions or actuate machinery.",
            "limited_scope": "Monitoring, safety monitoring, anomaly detection and consumption-model training remain outside this milestone.",
            "unresolved_source": "Recorded resource units and the authoritative source water-rule version remain unresolved.",
            "unsupported_question": "This question requires facts or approved documentation not available in this evidence bundle."},
        "review_actions": {"inspect_source_records": "Inspect the cited source records and confirm their units and provenance.",
            "validate_scenario_assumptions": "Ask factory specialists to validate capacities, operating calendars, processing times and documented recipe/quality compatibility before any operational use.",
            "request_approved_documentation": "Request approved factory documentation and technical review; these project notes do not authorise machine settings."}}
