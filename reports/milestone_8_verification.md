# Milestone 8: AMD planning change requests

Implemented and verified on **15 October 2026, Asia/Karachi**, Python 3.11.9.
This is explicit, user-confirmed constraint editing in an illustrative simulator,
not autonomous planning, factory approval or realised savings.

## Recoverable milestone-7 checkpoint

Before editing, `checkpoints/milestone_7_before_m8.zip` was created and checked.
Its SHA256 is `c69205e0d68eb8ac67fd81e156823ea1cd7f0e99d8d6ac723f8d378c3011a4c9`,
identical to the existing milestone-7 distributable. Metadata is in
`checkpoints/milestone_7_checkpoint.json`. It includes application code, pinned
dependencies, documentation, trusted frozen models and required source/audit data.
Credentials and review databases are excluded; the current `.env` and local
database were not modified. Unrelated/restricted dataset files remain untouched
in the workspace. The checkpoint is local and not duplicated inside the new ZIP.

To recover, extract the checkpoint into a **new folder**, for example
`Expand-Archive -LiteralPath checkpoints/milestone_7_before_m8.zip -DestinationPath recovery/milestone_7`.
Run the recovered `dyeing-copilot/streamlit_app.py` from its own root using the
existing trusted interpreter or a fresh environment with its requirements.
Keep the current workspace intact; supply participant configuration locally if
live inference is needed. Do not overwrite `.env` or a review database during recovery.

## Implemented workflow

The existing five steps remain. Under machine/rule review, expand **Planning
change request — interpret, preview and confirm**. Live AMD interpretation is
separate from the exact-statement explanation catalog. It can return only:

- Machine unavailability over an explicit start/end interval.
- An identified order's explicit completion deadline.
- Clarification questions or excerpt-backed unsupported reasons, with no changes.

The request includes exact known order/machine IDs, effective releases/deadlines,
availability, historical scenario time and permitted operations. Strict Pydantic
schemas forbid extra fields and executable operations. Python validates IDs,
absolute datetimes, exact supporting excerpts, operation intent, interval order,
duplicate/conflicting deadlines, duplicated changes and omitted references/dates.
Distinct overlapping outages are supported. Unknown references are not mapped.
Relative weekdays, urgency without a deadline and slash dates cannot become ready
changes. Only absolute ISO dates with minute/second precision, no offsets or
fractional seconds, are accepted. Prose dates require clarification; today's date
is never used to resolve historical inputs.

The original request, interpretation, supporting excerpts, response origin and
an understandable before/after preview are displayed. Parsing and preview do not
modify constraints. **Apply changes and reschedule** is a separate explicit action.
The proposal is bound to source identity and the complete scenario/revision
fingerprint. Changed source/configuration/text invalidates it, and application
independently rejects stale proposals. The request's known-ID/date context is
also checked against the actual effective case at application time.

Application builds immutable copies and commits only after all changes validate
and rescheduling completes. A failed schedule construction still retains the new
constraints and truthful failure result; it does not become a recommendation.
Deadline overrides are separate from imported orders, with original/previous
deadline, request fingerprint and exact excerpt provenance. Histories retain the
original text, validated proposal, receipt and before/current fingerprints.
These overlays and previous successful schedules live in the current Streamlit
session; use the audit export to retain them across restarts. Existing supervisor
review snapshots also persist the expanded evidence when saved through Copilot.

**Reset to original scenario and reschedule** restores the source deadlines and
configuration loaded before these natural-language edits, retaining reset history
and advancing the revision to invalidate earlier proposals. It does not silently
change the original illustrative cleaning permission checkbox. Editing the base
configuration starts a new original case; it is separate from this AMD workflow.

## Scheduling, verification and export

Outages subtract half-open intervals `[start,end)` from the existing windows.
Sequential subtraction correctly handles overlap, touching boundaries, multiple
windows, out-of-window no-ops and complete closure. A machine may now have an
empty availability tuple, displayed as closed. Machines are not removed and
compatibility/capacity/rate/cleaning policy are not changed.

The original planner/search, resource evaluator and independent verifier files
are unchanged. They receive the effective order deadlines and revised windows.
Processing and terminal cleanup must fit those windows. Exports and comparison
evidence use the same effective orders and independently reverify them. Original
IDs, quantities and source records remain intact.

If construction fails, the last successful schedule is separately retained and
labelled **previous scenario, not valid for revised constraints**. There is no
current proposal/resource recommendation; construction failure is not reported as
proof of global infeasibility. Current scenario-specific explanations are blocked
without a verified comparison. A failed-construction audit remains downloadable.

**Export change request audit (JSON)** includes original request/proposal, applied
history, origin receipts, source/scenario fingerprints, original/effective orders
and assumptions, deadline provenance, construction errors, both verification
results and schedules where available. **Export planner review package** remains
available for verified comparisons and includes these overlays. No credentials
are exported. Supervisor acceptance remains **for further review**, never production approval.

## Frozen evaluation protocol and actual live outcomes

`evaluation/planning_requests.json` contains **30 hand-authored requests**, fixed
before interpreter implementation/live evaluation: **20 development**, **10 held out**.
Cases cover single/multiple edits, historical ISO dates, overlapping outages,
urgency, weekdays/slash dates, unknown identifiers, conflicts, forbidden cleaning/
capacity/compatibility/rate changes and instruction injection. Development tests
exercise hand-authored expected structures; they are not model-accuracy tests.
`evaluation/frozen_protocol.json` fixes the corpus hash and live budget.

Before live calls, `evaluation/interpreter_freeze.json` fixed hashes of the prompt,
schemas/validator, application logic and corpus. **No interpreter changes or
tuning were made after inspecting held-out responses.** No monitoring model was
trained/retrained. `tools/evaluate_planning_requests.py --live` ran exactly ten
logical requests, at most two concurrent, with the existing two-attempt maximum.
It refuses to overwrite the recorded evaluation or run if frozen hashes differ.

Actual receipts: requested `DeepSeek-V4-Flash`, server-reported
`self-dploy/DeepSeek-V4-Flash`, **HTTP 200 / one attempt for all ten**. Calls started
14 October 2026 21:40:38–21:41:11 UTC, corresponding to **15 October 02:40:38–02:41:11
Asia/Karachi**. Full secret-free outcomes/receipts are in
`milestone_8_live_evaluation.json`.

| End-to-end expected handling | Correct validated outcomes | Attempts |
|---|---:|---:|
| Ready, exact structured edits | 2 | 3 |
| Clarification | 2 | 5 |
| Unsupported / injection refusal | 2 | 2 |
| Overall | **6** | **10** |

**Validated end-to-end semantic correctness: 6/10 (60%)**, both over all attempts
and non-transport attempts. There were **zero transport/service failures**, six
accepted responses and **four Python validation rejections**. All six accepted
responses matched their expected status/normalized operations. That conditional
observation is not industrial accuracy or evidence of general language reliability.
End-to-end elapsed latency was **3.941–19.657 seconds**, mean **7.378 seconds**.

The rejected cases matter:

- **h01**: a maintenance outage on `virtual-Pressure-PolyCotton` was rejected by
  the conservative protected-word check because the identifier contains
  `Pressure`. This is a **validator false positive**, not evidence of a transport
  failure. The response was schema-valid/ready but later parameter correctness
  was not assessed after this early guard. This known limitation is deliberately
  recorded without changing the frozen validator using held-out feedback.
- **h05**: the model returned ready for ambiguous slash dates; Python rejected it.
- **h06**: the model returned ready despite unknown order `120`; Python rejected it.
- **h10**: the model returned ready despite unknown machine suffix `-99`; Python rejected it.

Rejected raw payloads were not retained, only curated rejection reasons and real
response receipts. Thus **pure model semantic accuracy is not claimed**; the
main metric covers the complete validated workflow. The three clarification
misses and the conservative false positive are remaining usability limitations.
Future improvements require fresh development work and a new untouched evaluation
set; no held-out case was retried or tuned away here. No rejected response could
be previewed/applied. The UI offers an explicit retry/reformulation path without
silently switching to mock mode or altering the computed schedule.

## Tests, integrity and changed files

Commands run:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p "test_planning_request*.py" -v
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe tools/verify_demo.py
```

**114 tests passed in 87.879 seconds**: all 105 existing tests plus nine new tests.
The new checks cover development contract/schema/reference validation, unsupported
and injected fields, preview without mutation, atomic failure, stale/reset/source
rejection, interval subtraction/overlap/closure, effective deadline checking,
terminal cleanup availability, provenance/review export, origin receipts,
duplicate interpretation prevention, and Streamlit interpretation/confirmation/
retry/reset/previous-schedule states. Mock transports are visibly labelled; none
of these tests counts as live AMD evaluation. Initial fixture/export assertions
were corrected before final regression: complete closure must cover the actual
2020-01-31 horizon, and audits must explicitly serialize verification `valid` flags.

`pip check` passed. **All 91 dataset checksum entries match**. Frozen joblib,
metadata, historical predictions, model card/protocol and resource/search/verifier
hashes remain unchanged. Three previously protected modules changed deliberately:
`planner/scenario.py` permits empty availability; `planner/export.py` and
`planner/review_package.py` accept a source-matched effective planning case.
`milestone_8_integrity.json` records hashes/checkpoint identity and confirms frozen
interpreter hashes still match after evaluation. Existing default/opt-in scenario
regressions retain milestone-7 totals and rules.

Added: `copilot/planning_schema.py`, `copilot/planning_interpreter.py`,
`planner/change_requests.py`, `planner/change_export.py`, `app/planning_changes_view.py`,
two planning-request test modules, frozen evaluation files and
`tools/evaluate_planning_requests.py`. Updated: the three planner modules above,
`app/simulator_view.py`, `app/copilot_view.py`, `copilot/evidence.py`, documentation
and packaging allowlists/receipt paths. Existing exact-statement explanation
validation and AMD HTTP adapter/configuration are preserved.

The packaging allowlist includes the evaluation corpus/freeze files and milestone-8
reports, and writes `dist/dyeing-copilot-milestone-8.zip` without overwriting earlier
ZIPs or the checkpoint. Both packaging checks passed again. An isolated extracted
copy verified all **33 included original data hashes**, loaded **35 orders and
731 synthetic days** with the same frozen model, and returned **HTTP 200** for
the root page and `/_stcore/health` (`ok`). This used existing pinned dependencies,
not a fresh dependency installation. `milestone_8_packaged_checks.json` records
the additional integrity/startup check; the full 114-test suite ran in the workspace.
After making failed-audit proposal verification explicitly “not performed”, the
seven new non-UI checks and two packaging checks were rerun successfully.

## Reproducible historical demonstration

Start from `D:\Projects\dyeing-copilot`:

```powershell
.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

Open the local URL → **Batch scheduling simulator** → **Load illustrative demo
assumptions** → review → **Run scenario comparison**. Leave cleaning exemptions off.
Open the planning-change panel and enter this request, using actual loaded IDs:

```text
virtual-Jet-PolyCotton outage from 2019-12-21T01:00 to 2019-12-21T11:00. Change order 11 deadline to 2019-12-24T17:00.
```

Click **Interpret planning request with AMD**. Inspect the original text, receipt
and preview: the machine's 2019-11-10–2020-01-31 window splits around the outage;
order 11's completion deadline changes from **2019-12-21 00:00** to **2019-12-24
17:00**. Neither change is applied yet. Click **Apply changes and reschedule**.
Inspect verification and export the change audit. **Reset to original scenario
and reschedule** restores the original constraints.

This exact request was accepted in live case h03. Replaying its already-generated
validated response against the matching original fingerprint produced a verified
35-order schedule, preserved source records and a **zero** baseline/proposal
resource difference. `milestone_8_demo.json` and `milestone_8_demo_change_audit.json`
record that application check, explicitly labelled **replay, no new inference**.
A fresh UI call is not guaranteed to repeat that response or latency.

For clarification, try “Make order 12 urgent”; for scope refusal, “Enable cleaning
exemptions for all red orders.” For construction-failure handling, an explicit
`virtual-Open-Cotton` outage covering 2019-01-01 through 2020-02-01 removes its
availability; inspect the retained previous-scenario schedule and failure audit.

## Remaining limits and browser status

**Browser/visual inspection remains pending**: no browser inspection tool is
available. Streamlit AppTest is automated application-state testing, not manual
browser inspection. Manually check preview readability, disabled controls,
spinner/Retry, view switching, stale proposals after edits/uploads, application,
reset, previous-scenario labels and downloaded audit contents before presenting.

The interpreter has the explicit 60% validated held-out result and the known
Pressure-name false positive. It is conservative, ISO-only and rejects mixed or
partially supported requests. Scenario edits are session-local unless exported
or included in a saved review snapshot. No production authentication, approved
machine SOPs, real equipment control, quality certification, global feasibility
proof, measured-factory validation or factory savings is established. No GPU VM,
new training, cleaning-rule edits or resource-formula changes were introduced.
