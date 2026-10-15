"""Planner review export extends the existing reverified scenario export."""

import json

from planner.comparison import compare_schedules
from planner.export import export_plan
from planner.scenario import orders_from_import, to_json


def export_review_package(result, config, comparison, *, case=None):
    from planner.change_requests import effective_orders
    artifact = json.loads(export_plan(result, config, comparison, case=case))
    artifact["planner_comparison"] = compare_schedules(effective_orders(result, config, case), config,
                                                       comparison.baseline, comparison.proposal)
    artifact["review_status"] = "no_supervisor_decision_attached"
    artifact["review_boundary"] = "Supervisor acceptance means acceptance for further review, never production approval."
    return to_json(artifact)
