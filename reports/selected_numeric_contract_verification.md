# Selected-schedule numeric contract fix

Date: 2026-10-15. Focused correction only; no scheduling calculations changed.

## Change

`copilot/selected_workflow.py` now supplies a selected-only Pydantic schema requiring `quantitative_claims` with exactly zero items. The prompt explicitly requires `[]`: numbers already occur in Python-generated, exactly validated catalogue statements. The response is checked against this schema before the unchanged shared `validate_output` grounding checks. Missing or nonempty claims are rejected, never removed or rewritten. Rejections retain their origin receipt.

Exact statement text, citations, assumptions, limitations, required selected statements and review-action checks remain enforced. Other explanation workflows retain the existing shared numeric-claim schema and validator. No datasets, models, formulas, permissions or planner code changed.

## Automated verification

- Four new regressions passed (`tests/test_selected_numeric_contract.py`): selected model-facing schema and valid empty output; reproduction of the original unsupported numeric/unit-conversion rejection; rejection of even a correctly grounded separate numeric copy only in the selected workflow; and continued rejection of unsupported statements, citations, assumptions, limitations and missing required statements.
- Full suite: **158 tests passed in 53.739 seconds**. Output: `selected_numeric_contract_tests.txt`.
- Read-only dataset/model integrity check passed; details: `selected_numeric_contract_integrity.json`.
- All historical report files captured before testing and `copilot/workflow.py` remain byte-for-byte unchanged; hashes: `selected_numeric_contract_preservation.json`.

Reproduce local checks:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p test_selected_numeric_contract.py -v
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe tools/verify_demo.py
```

## Separate live check

One bounded logical request was made using existing participant AMD configuration after the tests passed. No semantic repair, mock fallback or repeat-until-success was used. The client retained its existing maximum of two transport attempts; the actual request succeeded on **attempt 1**, HTTP 200.

- Timestamp: **2026-10-15T13:41:53.253824+00:00**.
- Requested model: `DeepSeek-V4-Flash`.
- Actual reported model: `self-dploy/DeepSeek-V4-Flash`.
- Inference latency: **31.395 seconds**.
- Outcome: **validated live AMD explanation**, with `quantitative_claims: []`.
- Case: bundled orders and existing illustrative scenario; independently verified selected schedule; question asks about order 12 and planner review.
- New evidence fingerprint, validated explanation and receipt: `selected_numeric_contract_live_check.json`. Historical failure reports were preserved unchanged. Credentials and authorization headers were not recorded.

`tools/check_selected_numeric_contract.py --live` is the project-owned check, intentionally refusing to overwrite its outcome or rerun until success. This single smoke check is not a reliability score or factory validation. No browser inspection was performed for this focused contract fix.
