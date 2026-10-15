"""Inspect source data as bytes/XML/text only. Never execute supplement code.

Run from the project root: .venv/Scripts/python.exe tools/audit_source.py
Outputs evidence to stdout; no dataset files are written.
"""

import csv
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "dyeing_dataset_pack/01_sitara_faisalabad"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def inspect_xlsx(path):
    with zipfile.ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(item.itertext()) for item in ET.fromstring(
                archive.read("xl/sharedStrings.xml")
            ).findall("s:si", NS)]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows, formula_count = [], 0
        for row in sheet.findall("s:sheetData/s:row", NS):
            values = {}
            for cell in row.findall("s:c", NS):
                value = cell.findtext("s:v", default="", namespaces=NS)
                if cell.get("t") == "s" and value:
                    value = strings[int(value)]
                elif cell.get("t") == "inlineStr":
                    value = "".join(cell.find("s:is", NS).itertext())
                formula_count += cell.find("s:f", NS) is not None
                if value:
                    values[cell.get("r")] = value
            if values:
                rows.append(values)
        return {"nonempty_rows": len(rows), "formula_count": formula_count,
                "first_row": rows[0], "last_row": rows[-1]}


def audit():
    raw = (SOURCE / "raw/Data_Set.txt").read_bytes()
    text_rows = [tuple(line.split()) for line in raw.decode().splitlines() if line.strip()]
    unique = list(dict.fromkeys(text_rows))
    total = sum(int(row[-1]) for row in unique)
    evidence = {
        "text": {"nonblank_rows": len(text_rows), "distinct_rows": len(unique),
                 "component_totals": [sum(int(row[i]) for row in unique) for i in (11, 12, 13)],
                 "total": total, "paper_manual_minus_text": 51100 - total},
        "xlsx": {}, "csv_variants": {}, "matlab": {},
    }
    for path in sorted((SOURCE / "raw").rglob("*.xlsx")):
        evidence["xlsx"][path.relative_to(SOURCE).as_posix()] = inspect_xlsx(path)
    for path in sorted((SOURCE / "csv/Code-and-Dataset").rglob("*.csv")):
        with path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        item = {"rows": len(rows), "columns": len(rows[0]),
                "missing_cells": sum(value == "" for row in rows for value in row.values()),
                "colour_codes": dict(Counter((row["source_column_07"].strip(), row["source_column_11"])
                                             for row in rows))}
        item["colour_codes"] = {str(key): count for key, count in item["colour_codes"].items()}
        if "source_column_15" in rows[0]:
            item["column_15_total"] = sum(int(row["source_column_15"]) for row in rows if row["source_column_15"])
        evidence["csv_variants"][path.relative_to(SOURCE).as_posix()] = item
    # Independent arithmetic reading of the primary formula, not execution of RD.m.
    # Uses the complete 13-column input, without sorting or any adjustment constants.
    input_path = SOURCE / "csv/Code-and-Dataset/Textile_Work/Project/New folder/Data_Set_Sheet1.csv"
    with input_path.open(encoding="utf-8", newline="") as stream:
        inputs = list(csv.DictReader(stream))
    terms, differences = [], []
    for index, row in enumerate(inputs):
        multiplier = 2 if int(row["source_column_06"]) > 2100 else 1
        black = row["source_column_11"] == "1"
        next_equal = index + 1 < len(inputs) and row["source_column_11"] == inputs[index + 1]["source_column_11"]
        saveable = 0 if black or next_equal else 350
        cloth = washing = multiplier * 350 * (2 if black else 1)
        terms.append((saveable, cloth, washing))
        recorded = int(unique[index][-1])
        if saveable + cloth + washing != recorded:
            differences.append({"source_row_id": index + 1, "formula_total": saveable + cloth + washing,
                                "recorded_total": recorded,
                                "formula_minus_recorded": saveable + cloth + washing - recorded})
    evidence["primary_formula_reading"] = {
        "input": input_path.relative_to(SOURCE).as_posix(),
        "term_totals": [sum(row[i] for row in terms) for i in range(3)],
        "total": sum(sum(row) for row in terms), "differences_from_text": differences,
        "boundary_note": "Final input row is black and bypasses next-row access; other endings may fail.",
    }
    with zipfile.ZipFile(SOURCE / "original_supplement.zip") as archive:
        archived_text = archive.read("Code-and-Dataset/Textile_Work/Project/Data_Set.txt")
        evidence["text"]["matches_archived_bytes"] = raw == archived_text
        evidence["text"]["archive_members"] = {}
        for name in archive.namelist():
            if name.endswith("Data_Set.txt"):
                data = archive.read(name)
                rows = [tuple(line.split()) for line in data.decode().splitlines() if line.strip()]
                evidence["text"]["archive_members"][name] = {
                    "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                    "nonblank_rows": len(rows), "matches_local_distinct_records": rows == unique,
                }
        for name in archive.namelist():
            if "Textile_Work/" in name and name.endswith(".m"):
                data = archive.read(name)
                evidence["matlab"][name] = {"sha256": hashlib.sha256(data).hexdigest(),
                    "lines": data.decode().splitlines()}
    article = ET.parse(SOURCE / "article/PMC9044317.1.xml")
    table = article.find(".//table-wrap[@id='table-13']//table")
    evidence["paper_table_13"] = [[" ".join(cell.itertext()).strip() for cell in row]
                                  for row in table.findall(".//tr")]
    return evidence


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(audit(), indent=2))
