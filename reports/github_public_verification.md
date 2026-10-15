# Public repository preparation

The industrial-dashboard application is published from a reviewed subset of the existing distribution allowlist. The original development workspace is retained separately. No existing local Git history existed, and the target public GitHub repository had no refs; its default branch was main.

The public checkout passed all **166 tests in 116.327 seconds**, including packaging, scheduling/verifier, importer, numeric-contract, AMD/manual preview and review regressions. Integrity checks matched all **33 distributable dataset entries**, accepted **35 orders** and **731 synthetic days**, and retained the frozen monitoring model. No new model evaluation, solver tuning or live AMD call was performed.

Only original distributable folders 01 and 02, trusted frozen models, application/tests/tools, required regression evidence and useful current documentation are selected. Fifty-six redundant distribution artifacts were omitted, including duplicate screenshots and local run logs. One existing industrial-dashboard screenshot is embedded in the judge-facing README. Some historical reports/source snapshots remain because preservation regressions require their exact bytes.

The public data manifest is the existing distributable subset; the acquisition-wide manifest is preserved separately. Application, planner, verifier, AMD interpretation and evidence validation files match the source workspace. The selected explanation still requires quantitative_claims: [].

Git attributes disable line-ending conversion to preserve checksum-protected files. New publication files pass git diff --check; 155 pre-existing whitespace warnings remain in original source/reference/test fixtures, intentionally not rewritten. Requirements and model artifacts are unchanged. Credentials, virtual environments, caches, review databases, dist ZIPs, checkpoints and restricted reuse datasets are excluded. The model ignore exception is specific to the trusted bundled models.joblib.

Known local AMD/Git credentials and high-confidence token/private-key patterns were checked without printing values, including 6,002 nested archive members. The selected/tracked file set is explicit in PUBLIC_DISTRIBUTION.json. Before push, the outgoing Git blobs are scanned too; any detected actual credential blocks publication. Git authentication was verified for push permission without exposing its credential. Push uses the ordinary main branch without force or rewriting remote history.

This report describes repository checks, not a new industrial-performance or inference evaluation. See the existing source audit, scenario/model documents and industrial-dashboard verification for the underlying evidence and limitations.
