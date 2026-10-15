"""Change-request audit includes failed constructions honestly; never credentials."""

import json

from planner.review_package import export_review_package
from planner.scenario import to_json
from planner.verifier import verify_schedule


def export_change_audit(result, case, comparison):
    from planner.change_requests import effective_orders
    orders = effective_orders(result, case.config, case)
    checks = {"baseline": verify_schedule(orders, case.config, comparison.baseline)}
    if comparison.proposal is not None:
        checks["proposal"] = verify_schedule(orders, case.config, comparison.proposal)
    artifact = {"artifact_type": "planning_change_request_audit_not_production_approval",
        "source": {"sha256": result.sha256, "filename": result.filename},
        "scenario_fingerprint": case.fingerprint, "original_assumptions": case.original_config,
        "effective_assumptions": case.config, "original_orders": case.original_orders,
        "effective_orders": orders, "deadline_overrides_with_provenance": case.overrides,
        "change_history": case.history, "verification": {
            "baseline": {"performed": True, "valid": checks["baseline"].valid, "errors": checks["baseline"].errors},
            "proposal": {"performed": "proposal" in checks, "valid": checks["proposal"].valid if "proposal" in checks else None,
                         "errors": checks["proposal"].errors if "proposal" in checks else (),
                         "note": "independently verified" if "proposal" in checks else "No proposal was constructed; verification not performed."}},
        "construction_errors": comparison.construction_errors,
        "status": "verified_comparison" if all(c.valid for c in checks.values()) and comparison.proposal is not None else "heuristic_construction_failed_not_proven_globally_infeasible",
        "baseline": comparison.baseline, "proposal": comparison.proposal,
        "review_boundary": "Acceptance is for further review, never production approval."}
    if comparison.proposal is not None:
        artifact["review_package"] = json.loads(export_review_package(result, case.config, comparison, case=case))
    return to_json(artifact)
