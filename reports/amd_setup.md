# AMD Token Factory setup

Milestone 4 uses the participant-provided AMD base URL, key and model. No endpoint/model defaults or unrelated-provider fallback are supplied. The existing local `.env` was preserved; its key was not displayed or written to reports.

## API format and configuration

The [AMD contest Radeon guide](https://github.com/AMD-DEV-CONTEST/Radeon-hackathon-2026-07/blob/main/Radeon-Cloud-User%20Guide/README.md) describes copying the base URL, model name and key from the participant model dialog. Its model API uses JSON POST to the base plus `/chat/completions`, with Bearer authorization, `model` and `messages`. The [Radeon API reference](https://amd-aim.github.io/radeon-cloud-docs/api/chat-completions/) documents the message roles, response shape and errors. These references were checked on 14 October 2026.

The adapter supports the documented shared Radeon HTTPS base paths `/radeon/api/v1` and `/radeon/v1` on `developer.amd.com.cn`. It rejects unrelated hosts, embedded URL credentials, query strings and redirects. A different participant/dedicated endpoint requires its own verified integration; it is not guessed or substituted.

From the project root in PowerShell:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements.txt
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
```

Edit `.env` locally, copying all three values exactly from your participant model detail/Quickstart:

```dotenv
AMD_API_KEY=PASTE_PARTICIPANT_KEY_HERE
AMD_BASE_URL=PASTE_PARTICIPANT_BASE_URL_HERE
AMD_MODEL=PASTE_PARTICIPANT_MODEL_ID_HERE
```

The base URL excludes `/chat/completions`. Do not substitute an example model from public documentation for your participant selection. Environment variables take precedence over `.env`. Dotenv parsing does not execute code or modify the process environment. `.env` and `.env.*` are ignored by Git; `.env.example` is explicitly allowed. Keys never enter the evidence, receipt or SQLite snapshots.

## Run and inspect

```powershell
.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

Select **Copilot**. Recorded-data questions work without a scenario: try `Describe order 27`, `Show customer CGU recorded totals`, or the default recorded-resource question. Values come directly from Python facts, preserving source units and spellings.

For schedule questions, first load/review assumptions and run a verified comparison in **Scheduling simulator**. Switch to Copilot, choose a comparison, demand-change, assumption or factory-validation topic, then generate. Simulator inputs survive view switching; the model cannot change them. Invalid/missing comparisons cannot support scenario answers, while recorded questions remain available.

## Live, mock and cached labels

**Live AMD** is the default. Configuration is checked before enabling generation. A successful live label requires a real HTTP response that passes schema/evidence validation. The UI shows actual model, timestamp, latency and validation status.

**Mock demonstration (no API call)** is an explicit, prominently labelled alternative. It runs deterministic content through the same validator/rendering/review path, with no inference. Injected test HTTP transports are also labelled mock. Live failures never silently fall back to a mock.

Reused live answers are labelled **CACHED**, with the original receipt; a UI rerun is not a new request. Source/configuration/document changes invalidate explanations. Historical SQLite snapshots remain visible but cannot be decided when stale.

## Read-only workflow and output contract

One controlled workflow executes read-only functions for recorded facts, freshly verified comparison details and project-document sections. It sends relevant evidence to AMD in a data envelope and makes one logical completion request, with at most one transient retry. It exposes no model-invoked planner, configuration, permission, review-write or machine-control tools. Imported strings, question text and document passages are data, not instructions.

Pydantic validates explanation items, evidence references, assumptions, limitations, proposed review action and optional numeric claims. AMD selects and orders **fact-conditioned supported statements** and copies their text/references. Free-form generated prose is intentionally rejected: exact matching prevents unsupported numeric synonyms, settings instructions and semantic approval/savings assertions that a numeric blacklist would miss. This limits open-ended explanation style and is a deliberate milestone constraint.

Numeric claims must equal a cited Python scalar fact with its exact unit. Invented references, inconsistent numbers, litres/PKR conversions, extra action fields, unsupported prose and missing boundary limitations are rejected. Headline numbers are rendered from Python, never model replacements. Differences and percentages use the recalculated baseline; a zero baseline has an undefined percentage.

Supporting passages come from the source audit and scenario-model documents, with identifiable section IDs, paths and SHA256 hashes. These are **not approved machine SOPs** and establish no machine safety or pressure/temperature/chemical-setting permission. Monitoring, anomaly detection and consumption-model training are not implemented.

## Supervisor review

Save a validated live or visibly mocked recommendation as **pending review**, with optional notes. `data/reviews.sqlite3` persists the exact source/scenario/evidence fingerprints, complete evidence snapshot, question, structured explanation, origin/receipt and notes. The database is ignored by Git.

Current pending items can be **accepted_for_further_review** or **rejected**. Decisions have separate timestamps/notes; duplicate saves are idempotent and replayed/stale decisions are blocked. Acceptance only routes further review: it cannot approve factory use, enable exemptions or actuate equipment.

This is a local prototype store, without production multi-user authentication, role separation or a tamper-evident governance service. Those capabilities are not claimed.

## Failure behavior

Connection timeout is 5 seconds and read timeout 45 seconds. There are at most two attempts with 0.5-second backoff. Only connection/timeouts and transient 408/429/502/503/504 responses retry. Configuration/authentication/access/model errors do not. These socket inactivity limits are not a hard total wall-clock deadline; overhead and retries can take longer.

Curated errors identify configuration, key/access, quota, backend or connectivity issues without raw response bodies, headers or exceptions. Redirects, malformed/truncated responses and unexpected tool calls are rejected. Validation failures are not automatically regenerated. A failure accepts no new explanation; correct configuration or check the participant dashboard/connectivity and retry explicitly.

## Live smoke test

```powershell
.venv/Scripts/python.exe tools/smoke_amd.py
```

This explicitly calls AMD for the verified, exemption-disabled bundled comparison and validates its answer. It writes a secret-free receipt to `reports/amd_live_smoke.json`, replacing the previous receipt with the latest outcome. Failure exits nonzero. It makes no SQLite decision or simulator-permission change.

A live end-to-end response was validated on **14 October 2026 at 00:49:59 Asia/Karachi** (request time). Requested model: `DeepSeek-V4-Flash`; actual server-reported model: `self-dploy/DeepSeek-V4-Flash`; HTTP 200, one attempt, **33.18-second request latency**. Earlier shorter-timeout attempts failed and were not counted as success. See [receipt](amd_live_smoke.json) and [verification](milestone_4_verification.md). One success does not guarantee future service availability or production readiness.
