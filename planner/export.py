"""Export reverified scenario artifacts, without factory-savings claims."""

from dataclasses import asdict
from decimal import Decimal

from planner.evaluator import evaluate_resources
from planner.scenario import MODEL_VERSION, orders_from_import, to_json
from planner.verifier import verify_schedule


def export_plan(result, config, comparison, *, case=None):
    from planner.change_requests import effective_orders
    orders = effective_orders(result, config, case)
    if comparison.proposal is None:
        raise ValueError("No verified proposal is available for export.")
    baseline_check = verify_schedule(orders, config, comparison.baseline)
    proposal_check = verify_schedule(orders, config, comparison.proposal)
    if not baseline_check.valid or not proposal_check.valid:
        raise ValueError("Export rejected: baseline and proposal must both pass independent verification.")
    baseline = evaluate_resources(orders, config, comparison.baseline)
    proposal = evaluate_resources(orders, config, comparison.proposal)
    if proposal.total > baseline.total:
        raise ValueError("Export rejected: proposed schedule is worse than the baseline.")
    return to_json({
        "artifact_type": "illustrative_scheduling_simulator_not_factory_instruction",
        "model_version": MODEL_VERSION,
        "source": {"filename": result.filename, "sha256": result.sha256,
                   "recorded_water_total_separate_from_comparison": sum(
                       (Decimal(r["water_total_source"]) for r in result.records), Decimal(0))},
        "assumptions": config,
        "orders": orders,
        **({"planning_changes": {"scenario_fingerprint": case.fingerprint, "original_orders": case.original_orders,
             "deadline_overrides": case.overrides, "history": case.history}} if case is not None else {}),
        "baseline": comparison.baseline,
        "proposed_schedule": comparison.proposal,
        "verification": {"scope": "scenario_based", "baseline_valid": baseline_check.valid,
                         "proposal_valid": proposal_check.valid, "baseline_errors": baseline_check.errors,
                         "proposal_errors": proposal_check.errors},
        "scenario_resources": {"unit": config.resource_unit,
                               "baseline": {**asdict(baseline), "total": baseline.total},
                               "proposal": {**asdict(proposal), "total": proposal.total},
                               "modelled_difference": baseline.total - proposal.total},
        "limitations": "Virtual machines and assumed recipe/quality permissions only; no global optimality, "
                       "verified factory feasibility, actual water saving or machine control is established.",
    })
