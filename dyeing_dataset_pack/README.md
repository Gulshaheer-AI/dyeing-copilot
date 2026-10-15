# Dyeing copilot dataset pack

Downloaded and inspected on 13 October 2026. This pack contains original downloads, extracted copies, CSV conversions, source metadata and checksums. No research notebooks or MATLAB scripts were executed and no AI model was trained.

## What to open first

| Folder | Acquired data | Use |
|---|---|---|
| 01_sitara_faisalabad | Original 23,864,935-byte supplement; 10 workbook variants and a text file with 35 distinct order records | Local scheduling case; modelled-water demonstration |
| 02_synthetic_thread_dyeing | Original archive, workbook and CSV; 731 daily records × 39 columns | Resource/waste modelling experiments with a visible synthetic-data label |
| 03_industrial_machine_reference | Five extracted article tables, source HTML and original table markup | Machine capacity/power, production constraints and reference cost parameters |
| 04_turkey_published_energy_tables | Ten published tables, including 12-row historical and 7-row newer consumption excerpts | Small real-origin descriptive examples; not a complete training history |
| 05_bangladesh_mill_benchmarks | 15 annual factory records plus an electricity-emissions reference table | Factory-level water/electricity benchmarking |
| 06_restricted_reuse_experiments | Original Mendeley archive and three workbooks | Background research only; keep separate from product training |
| 07_carbonfact_dyeing | 38 dyeing impact-score records, methodology PDFs and licence | Environmental reference values; not production telemetry |

Read `dataset_inventory.json` for detailed profiles, `SHA256SUMS.json` for file integrity, and the source/licence metadata inside each folder. CSV conversion is a format conversion, not an assertion that the source is clean or ready for training.

## Critical findings

### Faisalabad supplement

The original archive was obtained through NCBI's public PMC Open Data archive. It contains 5,757 non-directory members, largely optimisation benchmark code and outputs. Relevant textile spreadsheets were extracted without executing that code. The article metadata reports CC BY.

The text file has 70 nonblank records but only 35 distinct records: the same block is repeated. The exact-deduplicated CSV keeps 35 rows with stable source-row IDs. Workbook variants are alternative/incomplete/output versions of this case, not independent datasets; do not concatenate them to inflate sample size.

The source MATLAB code computes water with fixed 350-unit factors, quantity thresholds and shade codes. Some spreadsheets contain calculated water outputs. Independent measured meter readings have not been established. This is real-origin order information paired with a resource model, not a large metered training dataset.

The unique text records' water-total field sums to 47,950. This differs from the paper's quoted manual example total. Do not claim that the source code or data reproduces the paper's result without reconciling versions, assumptions and errors. Raw versions remain unchanged so that reconciliation is possible.

The text-derived CSV uses conservative `*_source` names. Dates, colour spelling, duration, quantity and water-component units retain their original representation; do not silently treat cloth length as kg. Workbook CSVs use generic positional column names because the workbooks have no header row. The first data row was retained.

### Synthetic operational data

The downloaded file contains every calendar day from 2023-01-01 to 2024-12-31: 731 unique dates and 39 columns. These are daily thread-production aggregates, not individual fabric batches. Resource and waste fields cover production, water, energy, chemicals, fixation, process variables, wastewater and water-quality indicators.

The repository explicitly identifies this dataset as synthetic. `Day_Type` is a synthetic variable, not an independently confirmed industrial fault label. Per-kg values, totals and production often encode direct arithmetic relationships; avoid using a target's derived counterpart as a predictor. Do not present an excellent synthetic fit as real-factory validation.

Original workbook and four research code/notebook files are preserved in the downloaded archive. Source SHA256 values were checked against all five original members.

### Published factory tables

Article tables preserve units, separators and currency strings. Some source headings use kW where consumption is discussed; this needs resolution before treating the value as kWh. Dots in Turkish values may be thousands separators. Do not interpret numeric-looking strings without reviewing the source context.

The Turkey article's published consumption tables have 12 and 7 rows, not a downloadable full 2011–2023 time series. Its second table has 12 corresponding rows but no independent date key: any join requires source verification. The 16-row solar/electricity table is a separate excerpt, not more independent dyeing batches.

The Bangladesh records represent annual whole-factory production, groundwater, electricity and effluent totals. Preserve groundwater units of million litres. They are not batch-level records and cannot identify a dyeing-machine fault.

### Reuse experiment and environmental references

The reuse archive contains three original experimental workbooks. Their sheets include spectra, replicate measurements and averages. A sheet with 3,528 spectral rows does not represent 3,528 independent dyeing batches. No derived training CSVs were produced for these restricted-use files.

Carbonfact values are modelled lifecycle impact scores. A water-impact indicator is not necessarily litres of process water. The full inventory behind the impact scores is not published in the repository. This pack includes only dyeing files and root citation/licence documentation from repository snapshot `170a89a`; the rest of the textile repository is unrelated to the selected scope.

## Sources and licences

| Source | URL | Licence / handling |
|---|---|---|
| Sitara study supplement | https://doi.org/10.7717/peerj-cs.932/supp-1 | CC BY per archived article metadata; retain attribution and source-specific notices |
| NCBI archive access | https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/ | Acknowledge NLM as archive source; no endorsement implied |
| Synthetic thread dataset | https://data.mendeley.com/datasets/wfwxybkpcm/1 | CC BY 4.0; credit contributor Ananya Halder |
| Industrial dyeing case | https://www.mdpi.com/2227-9717/13/11/3572 | CC BY 4.0 article; retain attribution |
| Turkey energy/dyeing article | https://www.mdpi.com/2071-1050/16/18/8152 | CC BY 4.0 article; retain attribution |
| Bangladesh factory study | https://www.mdpi.com/2673-7248/2/4/29 | CC BY 4.0 article; retain attribution |
| Wastewater reuse experiments | https://data.mendeley.com/datasets/pjrcb6rrkn/1 | CC BY-NC-ND 4.0; original files for noncommercial background research, excluded from recommended product training |
| Carbonfact database | https://github.com/carbonfact/lca-database-footwear-apparel | CC BY-SA 4.0; retain licence, credit displayed values and follow ShareAlike for distributed adaptations |

These sources keep their own licences. This is not a blanket MIT-licensed dataset bundle. Redistribution or application training must respect the licence of the chosen source.

## Not obtained

- Leeds Indonesian batik operational data: https://archive.researchdata.leeds.ac.uk/1360/ — restricted access by request; no request was submitted and no data was downloaded.
- The full raw Turkish 2011–2023 history — not available in the downloaded article tables.
- A large, independently metered fabric-batch dataset containing water, thermal energy, chemicals, quality and confirmed anomaly labels — not established by these downloads.

## Verification completed

- ZIP integrity checks passed for all downloaded archives used in the pack.
- All eight Mendeley original file SHA256 values match the repository metadata.
- CSV exports were read back to check row/column counts.
- Original headerless Sitara spreadsheets were read with `header=None`.
- Synthetic dates are unique and cover 731 days.
- Source files were preserved; extracted spreadsheets and reference tables are kept separate.
- No datasets from different factories/processes were merged and no published savings were attributed to our product.

## Next implementation step

Start with the 35 local orders as a scheduling scenario, resolve their field definitions and reconstruct the water model transparently. Use the synthetic data in a separate resource-analysis/model-training demonstration. The first prototype should show exactly which dataset is selected, its observation unit and provenance. A real measured factory dataset is still needed for a credible production waste predictor and realised-savings claim.

