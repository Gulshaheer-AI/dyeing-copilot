# Plan history - local verification

Implemented in D:\Projects\dyeing-copilot, the current integrated-recovery working project. The separate public checkout publication/github is unchanged. No push or deployment occurred. Recoverable pre-edit code: checkpoints/plan-history-before-edit.zip. Protected pre-edit hashes: plan_history_preservation.json.

## Delivered behaviour

Save to history sits beside the existing review-package download. A freshly verified ordinary, CP-SAT fallback/legacy or recovery result can be saved without AMD inference, an explanation or a supervisor decision. Canonical export_backend supplies exact effective/original orders, source identity, assumptions, selected schedule, available verified deadline-first baseline or recovery reference, constraints/request receipts, cutoff, solver stages/bounds and independent verification. Missing ordinary baselines remain explicitly unavailable. No baseline is invented.

Schema dyeing-plan-history-v1 and application integrated-recovery+plan-history-v1 identify the snapshot. UUID run ID, timezone-aware Asia/Karachi save timestamp, optional trimmed title and a SHA256 content fingerprint accompany immutable JSON. Existing cleaning/deadline summary builders and exact timeline transformations run only at save time. Reads validate the saved schema/hash and render saved values; they never evaluate a changed model/configuration. A repeated snapshot and title in the same session returns the same ID and timestamp. A different title or session is a distinct save.

Plan history lists only this session's runs newest first. Selected versus baseline/reference timelines use frozen timestamps and continuous daily/full-horizon axes, with separate archived control keys. Expanders show saved inputs/assumptions, confirmed changes and recovery information, solver/verification and any valid explanation/review. Download uses another scoped lookup and contains no session identifier. The history page has no restore-into-planner action.

## Storage and privacy

Separate SQLite planning_runs table in data/plan_history.sqlite3 (or DYEING_PLAN_HISTORY_DB). Parameterised save/detail/list/download queries always require a random opaque browser-session scope; only its SHA256 is stored. UNIQUE(scope_hash,fingerprint,title) provides atomic deduplication. Session identifiers are forbidden in exported content. Every detail/download rechecks scope, schema and content integrity. Unsupported or damaged rows show a curated error; no raw database path or input values appear in errors.

The module never lists the supervisor-review database. An already available matching explanation is validated by the unchanged selected/shared validators, including quantitative_claims exactly []. A supervisor record is eligible only if matching and explicitly saved by this session. Pending is not acceptance; acceptance means further review, never production approval. Neither evidence nor a decision is required.

Known configured secrets, private-key/token patterns, credential/authorization fields, environment contents and raw transport metadata are rejected rather than silently dropped. This is a bounded credential screen, not a guarantee that arbitrary unknown plain text can always be recognised as a secret. No credentials, environment or raw transport diagnostics are intentionally stored. Runtime databases/uploaded records remain outside Git and release ZIPs through existing data/SQLite exclusions and the distribution allowlist. Custom storage should use a private runtime path. No account system or public archive was added.

Visible notice: Saved planning snapshots for this session. Hosted storage may reset after an app restart or redeployment. Download a copy to keep it.

A new browser session has no access to a previous session's runs. Local SQLite may remain on disk after session loss, but cross-session recovery and permanent cloud retention are not promised. No authenticated/tamper-proof audit service, retention/deletion management or production access-control system is claimed.

## Automated checks

Full regression suite: 192 passed (plan_history_tests.txt and plan_history_test_result.json). Twelve focused history tests cover round trip and computed metrics, exact timeline times, no explanation requirement, later active edits, duplicate/title behaviour, newest-first/empty state, cross-session list/detail/download and SQL injection, explicit session-token export rejection, recovery/reference/priority/cutoff preservation, valid/mock explanation and pending review, stale/unsupported/malformed data, storage errors/configured paths, credential exclusion, and returning to the same active planning state.

History navigation preserves live control values while Streamlit hides their widgets. This is a session-control fix, not a restore of archived data: it never reads a snapshot to update the active case, constraints or solver result. A focused regression simulates the frontend clearing controls, then confirms the original permissions, configuration, priority and identical case/run objects remain. Native tabs and explicit question/source keys preserve review interaction. No automatic scheduling/inference occurs on history navigation.

Root integrity: all 91 original dataset checksums pass; 35 orders and 731 synthetic daily records load. Frozen metadata SHA256 a9ceca69c82ee1b7b52b3f5516f77262b7ed16ad7e57e7ad4f8d874cfac0a035. All protected planner, copilot, model artifact, importer and dependency hashes match the pre-edit baseline (plan_history_integrity.json). pip check reports no broken requirements. No dependency, optimiser objective, formula, cleaning permission, dataset, frozen model, AMD interpretation/numeric validation or independent-verifier code changed.

## Actual browser inspection

Real Microsoft Edge headless through CDP, desktop 1440px and narrow 680px. This is distinct from Streamlit AppTest. The reproducible journey is tools/inspect_plan_history_browser.py; actual outcome and captures are recorded in plan_history_browser.json and plan_history_screenshots/.

Journey: empty session history, load setup, explicitly enable illustrative permissions, generate verified plan, open Review & export, save without any explanation/review, prevent duplicate save, browse history, inspect selected and baseline archived timelines/verification, download JSON, then return to the unchanged active planner. The downloaded schedule/scenario match the active export; no session identifier is exported. The observed saved illustrative case contains 28 cleaning events and 35/35 on-time orders. These are computed planning scenario results, not actual factory production or resource consumption.

The final fresh-server pass also passed typed-title round trip, identical solver receipt after returning (no hidden replan), and duplicate prevention after returning. Seven screenshots were captured. Zero Streamlit exceptions were present. See the actual final browser receipt for individual outcomes. Initial browser attempts exposed hidden-widget cleanup/empty configuration on return, fixed by preserving only active control values; initial diagnostics stay local and are excluded from the distributable. A later check was interrupted by live code reloading during development; final browser verification uses a fresh server. No raw diagnostic or user archive is included in a release.

AMD calls for this release: zero; no live inference claim. Archive tests use explicitly mocked explanations where needed. Ordinary planning is browser-tested; recovery archival and session isolation are tested automatically, not claimed as additional browser journeys. No hosted-app check or deployment was performed.

## Packaging and changed files

New: app/plan_history.py (schema/build/store), app/plan_history_view.py (save and read-only page), tests/test_plan_history.py, tools/inspect_plan_history_browser.py.
Updated: streamlit_app.py routing/control retention; app/cp_sat_view.py history controls/native tabs; app/simulator_view.py legacy export adapter; app/selected_copilot_view.py stable question/source widget keys; app/timeline_view.py remembered filter defaults; tools/package_demo.py versioned allowlist; README.md and demo_walkthrough.md. Existing .gitignore already covers runtime data and SQLite files, so no unnecessary ignore changes were made.

Versioned credential-free ZIP: dist/dyeing-copilot-plan-history-v1-2026-10-17.zip. Existing redistribution restrictions and frozen model/data manifests remain in force. Only final browser captures and selected reports are added; no database, session scope, uploaded user snapshot, .env, venv, checkpoint, publication folder or nested release ZIP is included. Post-build hash/credential/package startup results are saved separately as plan_history_package_build.json, plan_history_credentials_check.json and plan_history_packaged_checks.json to avoid circular package hashes.

## Run and demonstrate

```powershell
cd D:\Projects\dyeing-copilot
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Open http://localhost:8501. Production planner -> Load demo setup -> review rules -> Generate schedule -> Review & export -> optional History title -> Save to history -> sidebar Plan history -> inspect archived timelines -> Download saved review package (JSON) -> sidebar Production planner. Recovery plans use the same save action after their independent verification. No explanation or review is required. No restore action or real execution/resource claims are introduced.
