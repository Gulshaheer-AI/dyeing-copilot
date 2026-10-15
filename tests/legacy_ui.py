"""Existing heuristic UI regressions explicitly choose the retained fallback."""
from planner.backend import LEGACY_ENGINE


def select_legacy(app):
    next(s for s in app.selectbox if s.label=='Planning engine').set_value(LEGACY_ENGINE).run(timeout=40)
