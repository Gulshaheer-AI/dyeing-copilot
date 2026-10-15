# Demo distribution and data licences

The default ZIP includes only dataset folders **01_sitara_faisalabad** and
**02_synthetic_thread_dyeing**. Both runtime CSV samples, provenance metadata,
original downloads and audit fixtures are included so import, model inference
and the existing source-audit regression checks work without downloading data.
Research archives are retained as source evidence; no supplied MATLAB, notebooks
or research scripts are executed by this application.

- Sitara: Elahi et al. (2022), *An evolutionary algorithm for multi-objective
  optimization of freshwater consumption in textile dyeing industry*, PeerJ
  Computer Science 8:e932. [Article](https://doi.org/10.7717/peerj-cs.932),
  [supplement](https://doi.org/10.7717/peerj-cs.932/supp-1), CC BY per archived
  article metadata. Original notices remain in the archive. NCBI/NLM provided
  archive access; no endorsement implied. The CSV conversion adds stable IDs
  and removes an exact repeated block; original source values are preserved.
- Synthetic daily data: Ananya Halder, *Synthetic operational dataset and
  ML-MILP code for thread dyeing waste prediction and reverse logistics
  optimization*, [Mendeley Data v1](https://doi.org/10.17632/wfwxybkpcm.1),
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The CSV is a
  format conversion of the original workbook. Included project-generated model
  artifacts were trained on this synthetic data; attribution remains applicable.

Folders 03–07 are omitted; the acquisition-wide inventory/README describes them
for historical context, not as packaged files or application dependencies.
In particular, **06_restricted_reuse_experiments is excluded** (CC BY-NC-ND 4.0).
Use its [source link](https://doi.org/10.17632/pjrcb6rrkn.1) for separately
licensed background research. Other reference-source links and licences remain
in the dataset README/inventory; none is required to start this demo.

The packaged `dyeing_dataset_pack/SHA256SUMS.json` covers only included original
files, retaining their exact checksums. `ACQUISITION_SHA256SUMS.json` preserves
the complete original inventory of 91 checksums; omitted entries are not expected
to exist in the distribution. The workspace's original manifest is never modified.
`PACKAGE_MANIFEST.json` hashes every packaged payload except itself. It checks
integrity, not publisher authentication or a licence grant. Dependencies and
third-party sources retain their own licences; this is not a blanket MIT data bundle.

No `.env`, keys, virtual environment, local review database, caches or Git history
is included. A new review database is created locally when the Copilot is opened.
Only load the included, project-produced model artifacts; never load untrusted
joblib files. The pinned scikit-learn version and training protocol are required.
