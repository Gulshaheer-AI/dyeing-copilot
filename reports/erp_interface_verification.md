# ERP interface redesign - local verification

Working project: `D:/Projects/dyeing-copilot`. The app files initially matched the published Plan history release `452093be1926180877fe5997b94ed49b61b4744b`. The publication checkout was clean with no index lock or active Git process and was not edited. No push/deployment occurred. Recoverable checkpoint: `checkpoints/erp-interface-before-edit-2026-10-18.zip`.

## Presentation and navigation

Compact blue application header, pale grey background, white bordered panels, restrained teal actions, readable module tiles and native controls. A single Workspace menu opens Production planner (default), Orders, Plan history and Reports. More tools retains recorded resource analysis, synthetic monitoring and the general copilot. Dataset/upload and technical engine settings remain in the sidebar. No fake buttons, new UI framework, modal workflow or animations.

The planner has Planning setup and Planning results, followed by Machine schedule, Changes and recovery, and Review and reports tabs. Illustrative assumptions and permission opt-in remain visible; machine tables and JSON are progressively disclosed. Existing recovery reference/cutoff controls now sit with change requests. Reference selection, explicit planning, interpretation, preview and confirmed application retain separate actions. A missing current recovery result still shows its cutoff and constraints. Protected-work outlines use the existing fixed-placement policy without changing any timestamps or protection rules.

Orders shows only actual recorded fields with compact customer/fabric/vessel filters and complete source details below. Plan history retains its session-only notice, scoped storage and read-only archive. Reports uses the unchanged canonical selected export builder and independent verification, disables missing/stale exports, and links to this session's history. Reports downloads a schedule-only package; matching explanation/review attachments remain in planner review controls. No new global archive or report data was introduced.

Planner control preservation reuses the existing history pause/resume mechanism across modules and keeps hidden timeline controls through the intermediate state between selecting a reference and solving recovery. Native stable keys preserve request text, selected permissions, dates and review notes. Reports' review shortcut applies its target tab after restoring paused controls. No solver or AMD call runs on navigation/filtering/section opening; explicit requests/generation remain required. No history restore action exists.

## Preservation and regression evidence

The baseline `erp_interface_preservation.json` hashes 135 protected files: all planner, copilot and daily modelling code, original datasets and artifacts, plus history storage. All match unchanged. Root dataset checks match all 91 acquisition files; release packaging contains only the existing permitted 33-file dataset subset. The selected-response quantitative_claims exactly [] contract, independent verifier, cleaning permissions, assumptions, objectives, frozen models and canonical export contents are unchanged.

New tests cover canonical Reports export equality, missing/changed-source/stale-result rejection, truthful protected-work display without timestamp mutation, unchanged active plan/request values across modules, machine filter preservation and absence of solver/AMD calls during navigation. Existing UI tests were updated to use the actual More tools route and labelled controls instead of positional selectbox indexes. Existing numerical/model/solver tests remain intact.

Development checks caught and corrected: a module selection widget incorrectly included in retained control keys; a stale test counting the former navigation controls; recovery cutoff hidden before generation; and a machine filter cleared while recovery results were temporarily absent. A later full run exposed retention of a read-only busy-button key; it is excluded. Earlier local test/browser attempts are retained separately, not represented as passing final checks. Browser download comparison was strengthened to read the newest actual download rather than accidentally re-reading the first file.

Final automated results: **195 tests passed** in the working project (170.460 seconds in unittest; final process exit 0). See `erp_interface_test_result.json`, `erp_interface_tests.txt`, `erp_interface_integrity.json` and the separate extracted-package startup/regression receipt. These are automated tests, not browser inspection. `pip check` found no broken requirements. No dependency versions changed.

## Actual browser inspection

Final browser outcome: passed, 26 captured screens, zero Streamlit exceptions, no document-level horizontal overflow. Microsoft Edge 155.0.4283.62 headless via CDP, real rendered Streamlit at 1440px desktop and 680px narrow widths. The reproducible browser tool builds a fresh allowlisted app copy; its review/history databases and downloads stay in disposable local directories, isolated from existing runtime data. AMD credentials are explicitly disabled for this browser run. See `erp_interface_browser.json` and `erp_interface_screenshots/` for the actual final result, captures and browser version.

Journey: first load and disabled Reports download; empty session history; load demo; explicitly enable cleaning permissions; generate; inspect ordinary results and timeline; select verified reference cutoff 2019-12-01 05:00:00; manual outage for virtual-Pressure-PolyCotton from 2019-12-01 12:00:00 to 2019-12-02 12:00:00; preview; apply; inspect independently verified recovery and rendered protected-work chart; switch reference/revised timeline; download current package; save history with no explanation/decision; duplicate-save check; archived selected/reference timelines, assumptions and verification; actual history download; Reports and return to unchanged active plan, assumptions and exact solver receipt; labelled mock explanation, pending/accepted-for-further-review supervisor review and matching actual export; actual Reports download; Orders and More tools navigation; explicit reset. No automatic AMD inference or hidden solve was claimed.

Visual inspection covers first-load layout, results, normal/recovery timeline, change preview, review panel, archive, Orders and Reports at desktop; first load, timeline, recovery, review, archived details and Orders at narrow width. Long tables/charts use contained horizontal scrolling. Native sidebar collapses on narrow widths. No document-level horizontal overflow or Streamlit exceptions were reported in the final browser check. Screenshots remain evidence of planned scenario results, not actual production.

## Limits and delivery

Two reference screenshot images were not available in the received attachment files; the implementation follows the user's written ERP structure with Dyeing Copilot branding. This was local visual/browser verification only. No fresh live AMD call was made; mock review remains labelled and is not counted as live AMD success. Hosted Plan history verification from the previous publication remains a separate unconfirmed result; this redesign does not claim to fix or deploy that hosted release.

Configured teal/white text contrast is 4.98:1 (#0D7D77); navy-blue header/white is 7.82:1 and authored secondary text/white is 7.24:1. These calculations do not constitute a full accessibility audit. A small case and illustrative execution assumptions cannot establish production readiness, approved SOPs, real execution or measured savings. No such claims were added.

ZIP: `dist/dyeing-copilot-erp-interface-v1-2026-10-18.zip`. Existing distribution allowlist, dataset restrictions, frozen artifacts and placeholders-only .env.example are retained. Credentials, .env, runtime databases/user histories, virtual environments, caches, checkpoints, publication checkouts and other distribution ZIPs are excluded. Package and credential receipts are kept outside their own hashed ZIP. Actual changed source/docs/test files are listed in `erp_interface_changed_files.json`.

Run from the working project or extracted dyeing-copilot directory:

```powershell
.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

For a fresh extraction, first create Python 3.11 .venv and install requirements.txt as described in README. Use the renamed controls and sequence in demo_walkthrough.md. No deployment is required for the local demonstration.

Screenshots: [desktop results](erp_interface_screenshots/desktop_results.png),
[narrow timeline](erp_interface_screenshots/narrow_timeline.png),
[recovery with protected work](erp_interface_screenshots/recovery_timeline.png),
[archived result](erp_interface_screenshots/archived_selected_narrow.png),
[review](erp_interface_screenshots/mock_review_accepted.png).
