"""Explicit engine routing; heuristic fallback never acquires a CP-SAT label."""
from dataclasses import dataclass
from planner.cp_sat import solve
from planner.search import plan
from planner.verifier import verify_schedule
from planner.change_requests import digest

CP_ENGINE='CP-SAT (default)'
LEGACY_ENGINE='Legacy heuristic (explicit fallback)'


@dataclass(frozen=True)
class BackendRun:
    schedule: object | None
    origin: str
    cp_sat: object | None
    legacy: object
    effective_fingerprint: str
    case_fingerprint: str | None


def run_backend(orders,config,*,engine=CP_ENGINE,budget_seconds=10,legacy=None,allow_fallback=False,case_fingerprint=None):
    if engine not in (CP_ENGINE,LEGACY_ENGINE):
        raise ValueError('Unknown scheduling backend.')
    legacy=legacy if legacy is not None else plan(orders,config)
    fingerprint=digest({'orders':orders,'config':config})
    candidate=legacy.proposal
    if candidate is not None and not verify_schedule(orders,config,candidate).valid:
        candidate=None
    if engine==LEGACY_ENGINE:
        return BackendRun(candidate,'legacy_heuristic' if candidate is not None else 'no_verified_schedule',None,legacy,fingerprint,case_fingerprint)
    result=solve(orders,config,budget_seconds=budget_seconds,incumbent=candidate)
    if result.schedule is not None:
        return BackendRun(result.schedule,'cp_sat',result,legacy,fingerprint,case_fingerprint)
    if allow_fallback and candidate is not None:
        return BackendRun(candidate,'heuristic_fallback_not_cp_sat',result,legacy,fingerprint,case_fingerprint)
    return BackendRun(None,'no_verified_schedule',result,legacy,fingerprint,case_fingerprint)
