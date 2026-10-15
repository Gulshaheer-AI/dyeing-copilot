# Sitara source water-rule audit

Audited 13 October 2026. **The recorded text case totals 47,950 in unresolved source units.** An independent arithmetic reading of one complete MATLAB primary formula produces **51,100** on its matching input workbook. This reconciles the scalar difference numerically, but does not establish why the authors supplied different order-level values, which version is authoritative, or that we have reproduced the study. No supplied MATLAB or other research code was executed. No values were corrected or adjusted.

## Evidence and method

All paths below are relative to `dyeing_dataset_pack/01_sitara_faisalabad/`, unless prefixed otherwise.

- `original_supplement.zip`: read archive members as text/bytes, including every `.m` file under `Code-and-Dataset/Textile_Work/` and both `Data_Set.txt` members. No extraction or execution was needed.
- `raw/Data_Set.txt` and `csv/text_records_exact_deduplicated_35.csv`: compared every distinct source value, counted records and summed components.
- All six original `.xlsx` variants under `raw/Code-and-Dataset/Textile_Work/`: inspected their sheet XML and shared strings, including numeric date cells. The inspected sheets contain no Excel formulas. Date interpretation also uses the pack's existing CSV conversions. The four legacy `.xls` output variants were inspected through their existing positional CSV conversions and the pack's workbook profiles, without running research software or regenerating workbooks.
- `article/PMC9044317.1.xml`: inspected the article's data description, production-method paragraphs, Table 13, Table 16 and results prose. This is the locally archived article, not a new retrieval.
- Reproduce the inspection with `.venv/Scripts/python.exe tools/audit_source.py`. The project-owned script reads source text/XML and reports evidence to stdout. Its small independent calculation describes the primary formula only; it does not sort orders, optimise anything, or feed values into the application.

Attribution: Elahi et al. (2022), *An evolutionary algorithm for multi-objective optimization of freshwater consumption in textile dyeing industry*, PeerJ Computer Science 8:e932, [article](https://doi.org/10.7717/peerj-cs.932), [supplement](https://doi.org/10.7717/peerj-cs.932/supp-1). CC BY per archived metadata; archive access NCBI/NLM, without endorsement.

## Supported column meanings

The text has 15 whitespace-separated fields. The selected CSV adds `source_row_id` ahead of them. Workbooks omit the text's leading group number; consequently workbook positions differ.

| Text position / CSV field | Workbook position | Supported interpretation and limits |
|---|---|---|
| Added `source_row_id` | None | Stable CSV record identity, 1–35; not an original machine or batch identifier. |
| 1 / `source_group_id` | None | Repeated group labels 1–7, aligned with customer/date blocks. They cannot uniquely identify the 35 orders. Business semantics beyond grouping are unconfirmed. |
| 2–3 / order and delivery dates | A–B | Order-place and delivery dates, supported by article field description, workbook dates and Table 13 delivery dates. Text uses DD-MM-YYYY; article tables use month/day/year. |
| 4 / customer | C | Company name; Table 13 agrees with the customer blocks. Preserve source spelling. |
| 5 / fabric type | D | Cotton or PolyCotton. |
| 6 / fabric specification | E | Article describes cloth quality; strings such as `76x68x30x30` are present. The individual dimensions and units are not defined here. |
| 7 / cloth length | F | Table 13 explicitly describes cloth length. Workbook F supplies the quantity threshold in the code. No demonstrated mass conversion or reliable length unit is supplied. |
| 8–9 / shade and shade depth | G–H | Recorded colour and light/medium/dark description. Spelling varies; `Mdedium` is retained. |
| 10 / vessel type | I | Open, Jet or Pressure. Article Table 13 has vessel numbers instead. These categorical values do not identify physical machines or establish capacity. |
| 11 / duration | J | Consistent with the article's dyeing-time field and source `time_check.m`; values generally 10 or 20. This is not verified measured runtime, and its unit remains unresolved for this application. |
| 12–14 / three water components | No direct input equivalents | Three recorded numeric fields; they sum exactly to text position 15 on all 35 distinct records. Article lists vessel-washing freshwater, dyeing hard water and fabric-cleaning freshwater in that order. This supports a tentative positional reading, not a verified component data dictionary or meter boundary. The UI keeps generic component names. |
| 15 / water total | O in output variants only | Sum of recorded components in the text. Output-workbook O is written by a different calculation after rearrangement; it is not a direct copy of text totals. |

The complete 13-column workbook adds K (colour code), L (an urgent-order flag tested by code) and M (vessel-category number inferred by matching I). These must not be confused with the text's water components. K code `1` corresponds to Black. Other observed codes are Gray 2, Brown 3, Choclate 4, NevyBlue 5, Blue 6, RoyalBlue 7, Green 8, Yellow 9, Orange 10, Red 11, Beige 12, Turqius 13 and Burgundy 14. K describes colour, not shade depth. M values align with Open 1, Pressure 2, Jet 3; they still do not establish machine IDs. L is zero throughout the complete input examined.

## Dataset versions

The ZIP contains **two** text members:

| Archive member | Bytes | Nonblank records | Distinct records |
|---|---:|---:|---:|
| `Code-and-Dataset/Data_Set.txt` | 8,536 | 70 | 35 |
| `Code-and-Dataset/Textile_Work/Project/Data_Set.txt` | 4,267 | 35 | 35 |

The local `raw/Data_Set.txt` matches the 70-record member, and its distinct ordered records match the 35-record member exactly. Thus the dataset README's repeated-block observation applies to the selected local text version; not every archived text version is doubled. Deduplication does not explain the paper discrepancy: either distinct case totals 47,950; summing the doubled case would give 95,900.

| Workbook family (under `Textile_Work/`) | Profile | Finding |
|---|---|---|
| Root and `Project/Data_Set.xlsx` | 35 × 11, 154 missing cells each | Identical incomplete variants. Missing attributes cannot be treated as additional orders or silently filled for production analysis. |
| `Project/New folder/Data_Set.xlsx` and `Data_Set_2.xlsx` | 35 × 13, no missing cells | Identical complete versions; used for the primary-formula arithmetic below. |
| `Textile/Data_Set.xlsx` | 35 × 13, no missing cells | Separate byte version of the case. |
| `Project/New folder/Data_Set_1.xlsx` | 23 × 13 | Incomplete order set. |
| `Project/New folder/Data_set1.xls`, `Data_set11.xls`, `Data_set22.xls` | 35 × 15 each | Reordered output versions; each CSV's O column sums to 45,850. |
| `Textile/Data_set2.xls` | 35 × 23 | Output with extra dates; O also sums to 45,850. |

These are versions, not independent samples. There are also differences such as fabric-specification strings between text and workbook records (e.g. the final text block uses `80x80x60x60`, while complete workbook rows use `80x80x80x80`). Matching row count does not establish complete identity or common provenance.

## How the primary calculation works

Read `Code-and-Dataset/Textile_Work/Project/New folder/RD.m` inside the ZIP, lines 18–40. The corresponding branch in `Project/RD.m`, lines 24–46, uses the same arithmetic.

For each input row in its existing order:

1. F quantity above **2,100** gives `CoM = 2`; otherwise `CoM = 1`. Exactly 2,100 stays in the lower branch. The code is a two-level step function, not a general load/capacity calculation.
2. Start with `saveable_water = washing_water = cloth_water = 1`.
3. If K colour code is **1 (Black)**, set `saveable_water = 0` and both other multipliers to **2**.
4. Otherwise, if the current K equals the **next row's** K, set `saveable_water = 0`; both other multipliers remain 1.
5. Row result = `350 × saveable_water + 350 × CoM × cloth_water + 350 × CoM × washing_water`.

The paper states a vessel wash uses 350 L and black needs two washes. That is evidence for the intended model, not proof of the text fields' units or metering. There is no calibration or justification here for the universal factor across vessel categories, the 2,100 threshold, or treating both process terms the same for Black. Cloth mass, energy, recipe, depth, vessel category and delivery date do not enter this arithmetic. Code later groups equal K values; it does not establish fabric/recipe compatibility or use H depth to order light-to-dark.

Sequence matters only through equality to the next colour code in this branch. In the complete original input, adjacent Green rows 14/15 and Red rows 18/19 trigger this rule on rows **14 and 18**. The final row is Black, so this particular ordering bypasses next-row access at the boundary.

## Reconciling 47,950 and 51,100

The recorded components total **9,100 + 18,200 + 20,650 = 47,950**. A direct arithmetic reading of the primary branch on the complete 35-row input gives model terms **9,800 + 20,650 + 20,650 = 51,100**. Without the two adjacent equal-code exemptions, that formula would total 51,800; the exemptions account for 700. No arbitrary correction was applied.

The twelve differing row totals are below. IDs refer to the selected text CSV's stable source rows; the workbook uses the matching order sequence for this diagnostic.

| Source row | Recorded text total | Primary-formula reading | Formula minus text |
|---|---:|---:|---:|
| 4 | 1,400 | 1,050 | −350 |
| 8 | 700 | 1,400 | 700 |
| 13 | 1,050 | 1,400 | 350 |
| 14 | 1,750 | 1,400 | −350 |
| 15 | 700 | 1,050 | 350 |
| 17 | 1,400 | 1,750 | 350 |
| 18 | 1,750 | 1,400 | −350 |
| 19 | 1,400 | 1,750 | 350 |
| 20 | 1,050 | 1,400 | 350 |
| 27 | 2,100 | 2,800 | 700 |
| 31 | 1,400 | 1,750 | 350 |
| 35 | 2,100 | 2,800 | 700 |
| **Total across all 35 orders** | **47,950** | **51,100** | **3,150** |

Text component 2 matches `350 × CoM` for all rows, including Black. The code doubles both corresponding process terms for Black. Text component 3 has extra factors for Burgundy row 4 and Black rows 13, 20, 27 and 35, but not Black row 8. Text component 1 is zero on Black rows and some later same/family-colour rows, including rows 15/19 rather than the code's preceding rows 14/18, and NevyBlue rows 17/31 despite different preceding colour codes. These are observations, not validated alternative wash rules.

**What is resolved:** the paper's manual scalar 51,100 can be obtained from a specific formula/input variant, and its 3,150 difference from the text is decomposed order by order.

**What remains unresolved:** there is no version history, authoritative component dictionary or explanation for the text's exemptions and Black/Burgundy treatment. A scalar match cannot prove this was the exact calculation used in publication. We cannot identify a defensible correction to the text or an authoritative unified water model. The application therefore continues to sum the validated recorded values only.

## Inconsistencies and implementation concerns

- `Textile/dplot.m` line 24 subtracts **2,800** from `sum(waterusage)` without explaining a boundary or physical basis. `Project/New folder/dplot.m` line 24 does not. The runtime source audit applies neither subtraction.
- Root `Textile_Work/RD.m` lines 29–44 uses `CoM` without assigning it, and calculates primary water only when quantity exceeds 2,100. With the script's `clear all`, this is an apparent implementation error; it is not a reproducible baseline as written.
- The non-Black path reads `current_color + 1` even in a loop ending at `in`. A final non-Black row would read past the array. The complete input's final Black row happens to avoid this branch; reordered cases need not.
- After both columns of `waterusage` exist, MATLAB `sum(waterusage)` returns separate column totals, not one scalar. The later plotting/subtraction code can therefore operate on a vector. There is no clear scalar baseline/proposal contract.
- `RD.m` reads binary `.xlsx` with `fileread`/line splitting in some variants, then separately calls `xlsread`; that text read is not a valid spreadsheet parser. Bare `xlsread('Data_Set')` also makes the chosen version dependent on the current directory/file resolution.
- Date code requests `dd/mm/yyyy` despite mixed stored/date representations. `Textile/time_check.m` lines 9–19 derives duration from `10 × CoM`, uses the first row's start date, and adds extra output dates. Numeric serials and text formatting require reconciliation before treating those outputs as valid delivery checks. None is imported as a measured duration or schedule.
- Output O values include unexplained variation: the first consecutive Gray rows include a 3,700-quantity row with 1,750 while another 4,200-quantity Gray row has 1,400. Stored output values alone cannot establish successful execution of the current formula or deadline compliance.
- The paper's results prose gives **43,050** for its no-urgent-order result, but Table 16 gives **43,000**. Table 16's urgent subcomponents **31,900 + 13,470 = 45,370**, not its displayed **44,900**. These internal arithmetic/version inconsistencies prevent treating published aggregates as a clean reproduction target. They are attributed research values, not this project's results.

## Unresolved assumptions and application boundary

Physical units and measurement boundaries of the selected text components, cloth-length units, any mass conversion, meaning of the cloth specification, exact time units, vessel capacities and physical machine identities, transition approval rules, availability/maintenance constraints and the authority of the competing source versions all remain unresolved. The article mixes freshwater, hard/process water and wastewater terminology; their boundaries are not established by the text total.

Milestone 2 provides descriptive sums, groupings and contributions only. It does not run the source model, normalise by kg, relabel source units as litres, judge higher totals as waste, optimise orders, train a model or claim savings. Filtering selects recorded rows and does not recompute their sequence-dependent fields.
