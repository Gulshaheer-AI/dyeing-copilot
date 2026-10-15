# Industrial dashboard visual update

Presentation-only update. Checkpoint: `checkpoints/industrial-dashboard-before-edit.zip`.

Supported Streamlit theme settings provide the grey page, navy sidebar, teal actions, 16px base type and rounded controls. White panels and restrained accents use authored classes and documented container-key CSS hooks; no generated class selectors are used. All dynamic custom-HTML text is escaped. Native Material icons, metrics and badges retain accessible control labels.

The first-load setup uses a dynamic order count, **Load demo setup**, and **Use illustrative cleaning permissions**, initially disabled. Result summary and zero-based comparison chart are generated from the current verified comparison, including zero/worse/unavailable cases. Solver evidence gates the compact optimality badge. KPI cards distinguish cleaning, deadlines and smallest buffer.

The machine panel defaults to approximately 24 hours starting with actual activity, including initial cleaning, with previous/next-day controls, date selection and full horizon. All machines retain their full names; the chart scrolls horizontally at narrow widths. Actual exported timestamps remain unchanged; unavailable spans remain grey and inactivity is explicitly reported. Change/review tabs retain confirmation, retries, reset, stale protections and matching exports.

Browser screenshots and independent automated checks are reported separately below. No live AMD calls are part of this presentation update. Planner, verifier, data, formulas, permissions, interpreter and selected numeric-contract files are protected by `industrial_dashboard_preservation.json` and existing regression checks.


## Real browser inspection

Installed Microsoft Edge **155.0.4283.45**, running headless against the local Streamlit server, was driven through CDP mouse events. This is a real browser, separate from Streamlit AppTest. **Fourteen screenshots** were captured; visual inspection covered the listed screen types across desktop **1440px**, narrow **680px**, and phone **390px** widths.

- First-load setup: desktop and narrow, permissions off, no automatic planning or inference.
- Generated result: desktop and narrow; result-first summary, cards, zero-based comparison and tabs.
- Machine activity: desktop, narrow and phone; full machine names, readable order IDs, daily axis, wrapped day/filter controls and an unclipped legend. Blank rows identify machines with no production/cleaning. Idle time was not compressed or filled.
- Request a change and Review & export: desktop/narrow, with additional phone review inspection. The copied outage example wraps; the primary download remains readable. A historical review was visibly stale and its decision action disabled.
- Explicit opt-in and Generate schedule: real browser displayed **34 deadline-first versus 28 optimised cleanings**, **35/35 on time** and **123h smallest buffer** in that bounded illustrative run. The disabled-permission run displayed **39 versus 39**, **35/35**, **201h**. These are observations of calculated scenario results, not hardcoded presentation values or measured savings. Bounded solver results may vary.

Visual inspection found and fixed result-first reflow, narrow KPI-label clipping, a full-schedule control squeezed by columns, and a phone legend clipped by the chart's axis margin. Native wrapping containers, responsive tick density and a separate wrapping colour legend resolve those issues. The chart retains the exact Python event timestamps in hover/data and uses a truthful continuous time axis.

Screenshots are in `reports/industrial_dashboard_screenshots/`; browser receipt: `industrial_dashboard_browser.json`. Browser checks covered rendering, setup generation, tab changes and permission opt-in. Apply/reset/review persistence and AMD/manual previews are additionally exercised by automated AppTest, not claimed as live browser AMD inference. **No live AMD calls** were made in this update.

## Preservation and implementation

All **35 captured planner/copilot/frozen-artifact hashes** match. Integrity checks matched **91 original dataset checksums**, accepted **35 orders** and **731 synthetic days**, and preserved the frozen model version. The verifier, CP-SAT objectives, resource formulas, datasets, permissions, AMD interpretation/validation and `quantitative_claims: []` contract are unchanged.

Existing changed files are enumerated in `industrial_dashboard_changed_files.json`. Core presentation files: `.streamlit/config.toml`, `streamlit_app.py`, `app/simulator_view.py`, `app/cp_sat_view.py`, `app/planner_presentation.py`, `app/timeline_view.py`, `app/planning_changes_view.py`, `app/selected_copilot_view.py`; new `app/dashboard_style.py` and `tests/test_industrial_dashboard.py`. UI tests use renamed Load demo setup controls, and the passive-rerun test now exercises previous/next-day navigation. Packaging and walkthrough/README are updated. Panel/navigation styling uses documented container keys; secondary caption styling uses a narrowly scoped semantic hook in the pinned Streamlit version, never generated classes.

The fresh allowlisted ZIP is `dist/dyeing-copilot-industrial-dashboard-2026-10-16.zip`, with frozen models, native theme, documentation and screenshots. Credentials, local reviews, virtual environments, caches and restricted reuse files are excluded. The runtime and model architecture remain unchanged. Broader browser/device combinations and live AMD service behaviour are outside this visual check; existing service validation and mocked failure tests remain in the suite.


## Automated verification

The final workspace suite passed **166 tests in 76.725 seconds**. This includes the four retained numeric-contract regressions, existing scheduling/importer/AMD/manual/review workflows, three new visual-presentation checks (summary boundary cases, earliest-activity/day-window clamping and HTML escaping), and the expanded passive-rerun/day-control check. See `industrial_dashboard_tests.txt` and `industrial_dashboard_integrity.json`.

No model training or dependency changes occurred. An extracted-package regression/startup check is recorded separately after packaging. No live AMD call was made; mocked tests are not live inference verification.


## Packaged application

The extracted credential-free ZIP passed **all 166 tests in 70.992 seconds**, verified **33 packaged dataset entries** and **280 payload hashes**, and returned **HTTP 200** for both the Streamlit health and root endpoints. This extraction/startup check is separate from real browser inspection of the workspace app; the startup tool itself does not inspect a browser. It reused the existing pinned interpreter; a new dependency install was not repeated.

The local-key scan found no configured credential in any ZIP member, without printing it. No `.env`, databases, caches, virtual environments or restricted reuse files were present. ZIP CRC checks passed. See `industrial_dashboard_credentials_check.json`, `industrial_dashboard_packaged_checks.json` and `industrial_dashboard_package.json`. The final documentation/receipt rebuild receives a separate manifest/startup check in `industrial_dashboard_final_packaged_checks.json`.

New verification tooling: `tools/inspect_dashboard_browser.py` captures local Edge screenshots without AMD calls. `tools/smoke_packaged.py` reports startup separately from browser verification. Original reports and older ZIPs remain untouched.

Launch the existing workspace:

```powershell
cd D:\Projects\dyeing-copilot
.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

For a fresh extracted copy, use Python 3.11, create `.venv`, install `requirements.txt`, and run the same Streamlit command. Open http://localhost:8501. The README provides the full setup and participant AMD configuration; `.env` must be supplied locally for live inference.
