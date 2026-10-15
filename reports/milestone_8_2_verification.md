# Milestone 8.2: planning interpretation and manual constraints

Verified 15 October 2026, Python 3.11.9. Focused changes only: the AMD wire
contract, bounded evaluation diagnostics and structured manual constraint entry.
No agents, training, monitoring features or infrastructure migration were added.

## Preservation and implementation

The 24 historical evaluation/evidence/scorer files listed in
`milestone_8_2_preservation_baseline.json` retain their original bytes. Milestone 8
remains **6/10**, milestone 8.1 remains **3/6 AMD, 6/6 local, 9/12 complete flow**.
All previously exposed cases are development regressions now. Existing ZIPs are
preserved. The 22 protected files in `milestone_8_2_protected_baseline.json`, all
91 original dataset checksums, frozen models, original resource formulas,
cleaning assumptions, optimiser and independent verifier are unchanged.

The request version is 8.2, invalidating earlier cached request signatures.
`copilot/planning_contract.py` defines a strict, small wire schema. Python
segments the original text at literal ID references into immutable clause IDs
and character spans. AMD supplies operations, IDs, explicit values and clause IDs;
it no longer copies long excerpts. Python reconstructs exact original passages,
then runs the unchanged reference/date/negation/unsupported-operation and complete
clause/value association checks. A correct clause ID alone does not establish a
correct value association. Wrong IDs, swapped dates, omitted edits, unknown
clause references and extra schema fields remain rejected. All changes are
revalidated at preview/application and bound to the exact source/scenario.

**Minute and second precision are both valid**, with `T` or space:
`YYYY-MM-DD HH:MM[:SS]`. There is no timezone conversion or interpretation relative
to today. The prompt includes three concise development examples: a deadline,
a Pressure-machine outage and two different deadlines. Only referenced orders'
release/current-deadline details are sent alongside known IDs and machine windows;
unnecessary source hashes, repeated request metadata and unrelated order dates
were removed from the model context. Fingerprints remain enforced locally.

Local screening still returns only clarification/refusal, never ready AMD edits.
AMD remains responsible for interpreting supported natural-language requests.
Pressure protection is unchanged: exact known IDs are identifiers; an instruction
to change pressure is unsupported. Mixed unsupported edits remain wholly blocked.

## Manual workflow

In the existing planning-change panel, **Constraint entry → Manual controls**
offers a known order and date/time deadline, or a known virtual machine and
date/time outage interval. Seconds are supported. The helper constructs an explicit
manual request from the selected controls, validates it, and uses the same
`preview_changes` / separate **Apply changes and reschedule** / independent verifier /
reset / exported provenance path. It does not call AMD, needs no credentials and
records `origin=manual`, `actual_model=null`, `api_request_performed=false`.
Manual results are never counted as AMD successes. One manual edit is previewed
at a time; repeat after application for another edit. Confirmation applies the
displayed preview, not unsubmitted form edits. Stale proposals are rejected.
Original files and orders remain immutable; deadline overrides stay separate.

## Diagnostics and security boundary

`EvaluationDiagnostics` is opt-in for the exact bundled non-sensitive v8.2 corpus
and bundled source hash only, with a bounded record count. Model response content,
validation errors and origin receipts are checked for the actual credential and
credential-like text before retention. A suspicious payload is suppressed entirely.
Headers and configuration are never accepted by the diagnostic sink. Arbitrary
user requests are not logged. Diagnostics are separate report files, never ordinary
UI error content. Credential screening is a conservative safeguard, not a general
secret-classification guarantee. Transport/incomplete responses rejected inside
the existing AMD client have no retained raw body; accepted completion content is
captured before/alongside interpreter validation.

Evidence files:

- `milestone_8_2_development.json` and `_development_diagnostics.json`.
- `milestone_8_2_live_evaluation.json` and `_live_diagnostics.json`.
- `evaluation/planning_requests_v8_2.json`, `protocol_v8_2.json` and
  `interpreter_freeze_v8_2.json`.

## Honest live evaluation

The new corpus/protocol were authored before development inference: six exposed
8.1 development regressions, **12 separately authored fresh supported requests**
and six fresh local clarification/refusal cases. All six development calls passed
the new contract and full flow. No additional tuning was needed. The final
interpreter, guard, schema, contract, diagnostic/manual helper, scorer, corpus and
application logic were hashed before the held-out run. No frozen file changed
after inspection of held-out results. Outcomes are append-only at the run level:
the evaluator refuses existing outcomes, post-freeze development and changed
frozen files. It reserves the outcome file before service calls. There were
**zero semantic repair requests** and no held-out reruns.

Participant configuration was reused unchanged. Requested model:
`DeepSeek-V4-Flash`; actual reported model: `self-dploy/DeepSeek-V4-Flash`.
Held-out request receipts start between **2026-10-15T02:52:57.866498+00:00** and
**02:54:49.810625+00:00**. All 12 supported requests actually reached AMD.

| Separate measure | Actual result |
|---|---|
| Development regressions, live AMD | 6/6; not a held-out accuracy score |
| Fresh supported, first structured response correct | **12/12** |
| Supported responses rejected by validation | **0/12** |
| Incorrect AMD clarification/refusal | **0/12** |
| Final transport/service failures | **0/12** |
| Local clarification | **4/4**, zero API calls |
| Local unsupported/mixed/injection refusal | **2/2**, zero API calls |
| Complete supported preview/apply/verified/reset flow | **12/12** |
| Complete local blocked-application flow | **6/6** |
| Manual automated fixtures | Separate; excluded from AMD denominators |

Here “first structured response” means no semantic repair or second interpreted
answer. It does **not** mean every first HTTP attempt succeeded: `new05`, `new07`
and `new10` needed two transport attempts under the unchanged bounded client.
There were **15 HTTP attempts for 12 logical AMD calls**, nine succeeding on their
first attempt and three after a transient failure. Receipts do not retain the
specific first-attempt failure class, so timeout versus transient HTTP status
cannot be distinguished retrospectively. No inference success was fabricated.

| Workflow latency including validation/planning/reset | n | Minimum | Mean | Maximum |
|---|---:|---:|---:|---:|
| Development AMD | 6 | 7.820075 s | 16.134481 s | 28.451767 s |
| Fresh AMD | 12 | 6.177589 s | 21.824976 s | 66.161006 s |
| Fresh local | 6 | 0.023878 s | 0.070147 s | 0.105270 s |

Service receipts separately record inference latency (5.611–65.686 seconds),
attempt count, HTTP status and actual model ID. The full-flow score requires
exact normalized operations/status/route, preview without mutation, explicit
**test-harness** confirmation, both independently verified schedules, unchanged
IDs/quantities and reset. Local cases require blocked application and no mutation.
A validation rejection would score incorrect, not proof of model understanding.
All diagnostic payloads in this run passed credential screening.

## Automated checks, packaging and browser status

The workspace full suite passed **129 tests** (123 existing plus six focused
tests), in 39.136 seconds, including clause reconstruction, minute/second precision, wrong clause
IDs, swapped values, bounded/screened diagnostics, history preservation, manual
validation/stale handling and AppTest preview/apply/verified/reset without AMD.
Existing tests cover all four IDs, negation, protected mixed edits, wrong
associations, unavailable/terminal-cleaning/deadline checks, failed construction,
last-success preservation, retries, exports and explanation grounding.
The transport fixture was updated to the new wire shape; historical internal
fixtures and evaluation scorers remain unchanged. `pip check` passed.

Integrity evidence: `milestone_8_2_integrity.json`. Model/data checks and protected
hashes pass. Packaging checks use the pinned existing interpreter, not a new
dependency installation. All 129 tests also passed in the isolated extracted ZIP (39.134 seconds). Its
33 included source checksums and every packaged payload matched, both Streamlit
health/root returned HTTP 200, and the server was stopped. The configured
credential was checked absent from all ZIP payloads. Extracted ZIP
regression/startup results are recorded
in `milestone_8_2_packaged_regression.json` and `_packaged_checks.json`.

**Visual/browser inspection remains pending**: no browser inspection tool is
available. AppTest and actual live programmatic application checks are not manual
browser verification. Manually check both entry modes, origin labels, preview
readability, separate apply, view switching/stale invalidation, reset and audit
downloads before presenting.

Changed implementation: `copilot/planning_interpreter.py`, `planning_schema.py`,
new `planning_contract.py`, `planning_diagnostics.py`, `planning_manual.py`,
`app/planning_changes_view.py`; new v8.2 evaluator/corpus/protocol/freeze/tests and
reports; packaging/README instructions. No planner/daily/model files changed.

The versioned distributable is `dist/dyeing-copilot-milestone-8-2.zip`. It includes
trusted frozen artifacts, original source samples/attribution, historical evidence
and screened evaluation diagnostics. It excludes `.env`, credentials, virtual
environments, caches, local supervisor databases and restricted reuse experiments.

## Reproduce and demonstrate

From `D:\Projects\dyeing-copilot`:

```powershell
.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

For the extracted ZIP, open PowerShell in its `dyeing-copilot` directory:

```powershell
py -3.11 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env with participant AMD_API_KEY, AMD_BASE_URL and AMD_MODEL.
# Manual controls work without AMD configuration.
.venv/Scripts/python.exe tools/verify_demo.py
.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

1. Open the printed URL. Choose **Batch scheduling simulator**, load illustrative
   assumptions, review the opt-in rules and **Run scenario comparison**.
2. Open **Planning change request**. In AMD mode enter the actual live-tested
   request: `virtual-Pressure-PolyCotton maintenance from 2019-12-26T09:10:15 until
   2019-12-26T12:40:30.` Interpret and inspect the reconstructed excerpt/receipt.
3. Separately apply, check independent verification, export, then reset.
4. Choose **Manual controls**, order **12**, deadline **2019-12-23 18:15**.
   Preview (no change), inspect the manual origin, apply, verify, export and reset.
5. AMD-mode `Order 17 must finish on Friday.` returns local clarification with
   no API call. Refreshing stored evidence is not a fresh live inference.

Offline regression/integrity commands are `python -m unittest discover -s tests -v`,
`python -m pip check` and `python tools/verify_demo.py` using the project venv.
Live evaluator outcomes already exist; the tool intentionally refuses reruns.

## Remaining limitations

No incorrect interpretation remained in this small fresh set; that does not
establish general reliability. The finite ID-first association grammar still
requests clarification for negation, conditional/plural/anaphoric/ambiguous prose
and non-ISO dates. Clause checking cannot prove unstated intent. Human confirmation
remains essential. Live latency and retried transports can disrupt a demo.
There is no arbitrary industrial diagnosis, factory approval, approved SOP, safety
certification, autonomous control, realised saving or production-readiness claim.
Changes remain session-local unless exported/reviewed. Manual entry is an explicit
alternative, never a silent fallback following an AMD error.
