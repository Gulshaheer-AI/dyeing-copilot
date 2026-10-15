# Milestone 8.1: planning interpreter reliability

Verified **15 October 2026, Asia/Karachi**, Python 3.11.9. This is a focused change
to interpretation/grounding, local clarification and honest origin reporting.
Explicit preview/confirmation, source preservation, scheduling rules, resource
formulas and the independent verifier remain intact. No agents, model training
or infrastructure migration were added.

## Milestone 8 remains historical evidence

All original `evaluation/*.json` files from milestone 8, its evaluation script,
verification report, live evaluation, demo/audit, integrity/startup receipts and
test logs were hashed before editing. Their original bytes and **6/10** result
are unchanged; `milestone_8_1_preservation_baseline.json` records the hashes and
regression tests check them. The milestone-8 ZIP remains unchanged as a source
snapshot. Its frozen files describe that historical version, not current code.

Previously exposed h01/h05/h06/h10 are now **development regression cases only**.
Passing them is not a new held-out accuracy score. No original report or outcome
was rewritten to remove the Pressure false positive or clarification misses.

## Reliability changes

`copilot/planning_guard.py` separates exact known machine identifiers from the
surrounding instructions before checking protected words. A literal known
`virtual-Pressure-PolyCotton` is masked as an identifier; “change pressure” outside
it is still blocked. Whole-token boundaries prevent masking a known prefix inside
an unknown extended ID. Unknown references are identified explicitly, without
fuzzy mapping or guessing. Actual pressure/temperature/cleaning/capacity/rate/
formula/compatibility/recipe requests remain excluded, including supported edits
mixed with those instructions.

Before inference, deterministic checks return specific clarification for unknown
IDs, slash/relative dates, urgency without a datetime, invalid/reversed intervals,
conflicting/duplicate edits, negation and unclear associations. These decisions
have `origin = local_validation`, `actual_model = null` and
`api_request_performed = false`. They need no credentials and never become ready
changes. The UI labels them **Local validation only — no AMD inference or API
request was performed**, including reused decisions. Supported inputs still go to
the participant AMD service; local checks do not fabricate a ready proposal.

Grounding now checks **ID-first clauses**, not just a full-request quote containing
all IDs/dates. Each order's deadline and each machine's own start/end pair must
match its clause, and the exact supporting excerpt must include that identified
clause through its associated dates. Every operation must be represented exactly
once. Swapped dates, swapped machine intervals, omitted operations and conflicting
values are rejected even when the model quotes the entire request verbatim.

The practical supported form is one explicit operation clause per ID, for example
`order 12 deadline datetime` and `virtual-ID unavailable from datetime to datetime`.
Several clauses can be separated by punctuation or explicit repeated IDs. Distinct
overlapping intervals for the same machine remain supported. A checked
`order 12 deadline from <current> to <new>` form is supported. Plural/anaphoric
“orders 12 and 13 ... respectively”, conditionals, negated edits and unclear date
associations request clarification instead of inferring a mapping. This is a
bounded grammar check, not general natural-language semantic proof.

`InterpretationRequest` now includes version **8.1**, invalidating old cached
request signatures. The AMD prompt requests correctly associated, complete exact
excerpts and distinguishes identifiers containing Pressure from pressure-setting
instructions. Strict schemas and post-inference validation remain in place.
Source/scenario fingerprint checks and the separate **Apply changes and reschedule**
action still guard application. Non-ready decisions cannot be applied.

## New frozen evaluation

`evaluation/planning_requests_v8_1.json` and `protocol_v8_1.json` were created
**before implementation/tuning**: **20 development cases and 12 fresh held-out
cases**. None of the new held-out requests reuses an old complete request. The
development set covers every existing machine, actual protected-setting changes,
negation, two-order/two-machine associations, conflicts and known old failures.

Before any held-out inference, `interpreter_freeze_v8_1.json` fixed the hashes of
the schema, guard, prompt/interpreter, application logic, corpus, protocol and
evaluation scorer. The evaluator refuses overwritten outcomes or changed frozen
files. **No prompt/guard/scorer changes followed inspection of held-out results.**
Only subsequent UI wording, tests, documentation and packaging work occurred.

`tools/evaluate_planning_requests_v8_1.py --live` exercised all 12 cases with at
most two concurrent tasks. **Six were handled locally, six made actual AMD calls.**
Each AMD call returned HTTP 200 on one attempt. Requested model:
`DeepSeek-V4-Flash`; actual server-reported model: `self-dploy/DeepSeek-V4-Flash`.
AMD request timestamps span **2026-10-14 23:17:51–23:18:08 UTC**, or **15 October
04:17:51–04:18:08 Asia/Karachi**. Receipts and full accepted structures/application
audits are in `milestone_8_1_live_evaluation.json`.

| Measure | Actual result |
|---|---|
| Local clarification | **4/4 correct**, no AMD calls |
| Local unsupported/mixed refusal | **2/2 correct**, no AMD calls |
| AMD interpretations matching expected structured outcomes | **3/6 (50%)** |
| AMD admitted responses | 4/6: three correct ready proposals, one incorrect unsupported refusal |
| AMD validation rejections | **2/6** |
| Transport/service failures | **0/6** |
| Complete workflow correctness | **9/12 (75%)** |
| Actual ready proposals previewed/applied/independently verified/reset | **3/3** |

For ready cases, complete correctness includes exact status/operation/value/route
matching, preview without mutation, explicit **test-harness confirmation**,
verified baseline/proposal under effective constraints, unchanged IDs/quantities
and reset to original orders/configuration. This is an application test, not
production approval. For non-ready cases it includes correct refusal/clarification,
blocked application and unchanged scenario. Local decisions and AMD interpretation
are separate denominators; **9/12 is not AMD accuracy**. It is not directly
comparable with milestone 8's ten all-AMD requests.

Failures are retained, not counted as successful understanding:

- **fresh02**, two order deadlines: validation rejected a non-exact unsupported
  reason excerpt. No edits were applied. The rejection does **not** establish
  that AMD correctly associated the dates.
- **fresh05**, a valid order-8 minute-precision deadline: AMD incorrectly returned
  unsupported, claiming seconds were required. The schema permits minute precision.
  Its structure/excerpt passed validation, but the expected semantic outcome did
  not; this is a **model interpretation mistake**, counted incorrect and unapplied.
- **fresh06**, a Jet-PolyCotton outage: validation rejected a non-exact change
  excerpt. No edits were applied and no understanding is credited.

Raw rejected payloads are not retained, only curated errors and original response
receipts. Therefore no raw-model semantic score is inferred for rejections. Fixture
tests proving swapped-value rejection also do not prove live model comprehension.

Latency, including evaluation/application overhead:

| Route | n | Min | Mean | Max |
|---|---:|---:|---:|---:|
| Local workflow | 6 | 0.049540 s | 0.071838 s | 0.100088 s |
| AMD workflow | 6 | 4.879680 s | 6.828906 s | 9.716160 s |
| All workflows | 12 | 0.049540 s | 3.450372 s | 9.716160 s |

Local screening receipts measure the guard alone (about 0.000091–0.000631 seconds);
the table includes context construction, validation and blocked-application checks.
Successful AMD receipt latency excludes preview/planning/reset overhead. Small
sample sizes, conservative grammar and model refusals remain material limitations.

## Required examples

**Actual live Pressure-machine example (fresh01)**:

```text
virtual-Pressure-PolyCotton is unavailable from 2019-12-23T09:15 to 2019-12-23T14:45.
```

AMD returned a correct ready outage proposal. Actual receipt: HTTP 200, one
attempt, `self-dploy/DeepSeek-V4-Flash`, **2026-10-14T23:17:51.113043+00:00**, **5.459 s**.
The preview left the original case unchanged; explicit test confirmation applied
the interval, both schedules independently verified, all 35 IDs/quantities remained,
and reset restored the original constraints. No source file changed. This does
not claim a resource improvement or factory saving.

**Local clarification example (fresh07)**:

```text
virtual-Open-Cotton-77 unavailable from 2019-12-23T09:00 to 2019-12-23T12:00.
```

The local guard identified unknown ID `virtual-Open-Cotton-77`, requested an exact
configured ID and made **no AMD request**. Its receipt is `local_validation`, no
model ID, `api_request_performed = false`, **0.000272 s** guard time. No fuzzy
prefix mapping or application occurred. Both examples, their original receipts
and the Pressure application audit are in `milestone_8_1_examples.json`. Opening
or replaying those records is not new live inference.

## Tests, integrity and packaging

Commands:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe tools/verify_demo.py
```

**All 123 tests passed in the workspace (97.847 seconds) and again in an isolated
extracted ZIP (100.304 seconds)**: all 114 existing tests plus nine focused new
checks. Both packaging checks also passed separately. New tests cover all four machine IDs including
Pressure, real setting changes, exact/prefix reference handling, local operation
without credentials, negation, conflicting/unclear instructions, swapped deadlines,
swapped machine intervals despite exact whole-request excerpts, the four exposed
old regressions and Pressure preview/confirm/verified/reset UI states. HTTP
transports/interpretations in unit tests are mocked and labelled; AppTest is not
live AMD evaluation or manual browser verification.

All **91 dataset-manifest checksums match**. Every milestone-8 protected file,
including all planner modules, resource evaluator, independent verifier, training
protocol/model card, requirements and frozen joblib/metadata/historical predictions,
is unchanged. `milestone_8_1_integrity.json` records preservation/freeze checks.
No original monitoring model or resource assumption was retrained or adjusted.

Changed implementation: `copilot/planning_schema.py`, `copilot/planning_interpreter.py`,
new `copilot/planning_guard.py`, `app/planning_changes_view.py`; added reliability
tests and the v8.1 evaluation tool/protocol/corpus/freeze. The existing transport
retry test now uses a supported request, since ambiguous urgency is correctly
handled before inference. Documentation and packaging versions/allowlists were
updated. Original milestone-8 evaluation files/scorer/results remain untouched.

The new ZIP is `dist/dyeing-copilot-milestone-8-1.zip`; earlier ZIPs are preserved.
It includes trusted artifacts, source samples/attribution, versioned evaluation
records and original preservation-test evidence. Credentials, `.venv`, caches,
local review databases, checkpoints and restricted reuse data remain excluded.
Pinned dependencies are installed separately; this is not an offline Python bundle.

The extracted package verified all **33 included original source checksums**, every
payload hash, 35 accepted orders and 731 synthetic days with the unchanged frozen
model. Its Streamlit server returned **HTTP 200** for root and health, body `ok`,
then was stopped. No credentials were present in the extracted project; the
configured key was also checked absent from ZIP payloads. Raw extracted-test/
startup evidence is in `milestone_8_1_packaged_regression.json`. The final ZIP was
rebuilt with completed reports and checked again for integrity/startup. These
checks used the existing pinned interpreter; a fresh dependency installation was
not performed. HTTP startup is separate from visual inspection.

## Browser status, demonstration and remaining limits

**Visual/browser inspection remains pending**: no browser inspection tool is
available. Automated AppTest exercises request → preview → apply → verified
schedule → reset, including a Pressure machine and an honestly mocked origin.
The actual live evaluation exercises that flow programmatically. Neither is
manual browser verification. Before presenting, manually check preview readability,
origin labels, explicit confirmation, stale invalidation, reset and exported audits.

From `D:\Projects\dyeing-copilot`:

```powershell
.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

Open the printed local URL, choose **Batch scheduling simulator**, load assumptions
and run comparison. Enter the Pressure example above in the planning-change panel.
Interpret, inspect the preview/receipt, then separately **Apply changes and
reschedule**. Check verification and export, then **Reset to original scenario
and reschedule**. Enter the unknown `-77` example to see local clarification with
no API call. Fresh live responses are not guaranteed to repeat the recorded example.

The clause checker intentionally rejects plural/anaphoric, conditional, negated,
non-ISO or otherwise unclear prose. It does not understand every possible phrasing
or prove arbitrary free-text semantics. Correct clause/value binding does not prove
the user's unstated intent; explicit human preview/confirmation remains necessary.
AMD still has incorrect refusals and exact-excerpt failures in this small fresh
test. Broader reliability improvements need new development and another untouched
evaluation. Changes remain session-local unless exported/saved in review snapshots.
No factory approval, approved SOP, safety certification, realised savings or
production-readiness claim is made.
