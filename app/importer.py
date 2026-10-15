"""Read-only importer for the documented Sitara text-derived CSV contract."""

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "dyeing_dataset_pack"
SOURCE_KEY = "01_sitara_faisalabad/csv/text_records_exact_deduplicated_35.csv"
SOURCE_PATH = PACK / SOURCE_KEY
COLUMNS = (
    "source_row_id", "source_group_id", "order_date_source", "delivery_date_source",
    "customer_source", "fabric_type_source", "fabric_specification_source",
    "cloth_length_source", "shade_source", "shade_depth_source", "vessel_type_source",
    "duration_source", "water_component_1_source", "water_component_2_source",
    "water_component_3_source", "water_total_source",
)
NUMBER_COLUMNS = ("cloth_length_source", "duration_source", *COLUMNS[12:])


@dataclass
class ImportResult:
    filename: str
    sha256: str
    input_rows: int = 0
    duplicates_removed: int = 0
    records: list[dict] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)

    @property
    def valid(self):
        return not any(issue["severity"] == "error" for issue in self.issues)

    def issue(self, severity, row, column, message):
        self.issues.append(dict(severity=severity, csv_line=row, field=column, message=message))


def import_orders(content: bytes, filename: str = "uploaded.csv") -> ImportResult:
    """Validate an entire case atomically; never publish partially valid records.

    Each call replaces the case. Exact repeated rows are removed with a warning;
    conflicting IDs and repeated order payloads under different IDs are errors.
    All original cell strings are retained alongside explicit parsed dates.
    """
    result = ImportResult(filename=filename, sha256=hashlib.sha256(content).hexdigest())
    try:
        reader = csv.reader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        header = next(reader, [])
        if len(header) != len(COLUMNS) or set(header) != set(COLUMNS):
            result.issue("error", 1, "header", "Use the 16-column Sitara text-derived CSV header. "
                         "Missing: " + str(sorted(set(COLUMNS) - set(header))) + "; unexpected: "
                         + str(sorted(set(header) - set(COLUMNS))))
            return result
        seen_rows, seen_ids, seen_payloads = set(), set(), set()
        candidates = []
        for values in reader:
            line = reader.line_num
            if not values or all(not cell.strip() for cell in values):
                continue
            result.input_rows += 1
            if len(values) != len(header):
                result.issue("error", line, "row", f"Expected 16 cells, found {len(values)}.")
                continue
            row = dict(zip(header, values))
            exact_key = tuple(row[column] for column in COLUMNS)
            if exact_key in seen_rows:
                result.duplicates_removed += 1
                result.issue("warning", line, "row", "Exact repeated row removed; counted once.")
                continue
            seen_rows.add(exact_key)
            for column, value in row.items():
                if not value.strip():
                    result.issue("error", line, column, "Required source value is empty.")
            ids = {}
            for column in COLUMNS[:2]:
                if not re.fullmatch(r"[1-9][0-9]*", row[column]):
                    result.issue("error", line, column, "Use a positive integer source identifier.")
                else:
                    ids[column] = int(row[column])
            row_id = ids.get("source_row_id")
            if row_id is not None:
                if row_id in seen_ids:
                    result.issue("error", line, "source_row_id", "Conflicting rows share this ID; resolve before import.")
                seen_ids.add(row_id)
            payload = tuple(row[column] for column in COLUMNS[1:])
            if payload in seen_payloads:
                result.issue("error", line, "source_row_id", "Same order values occur under another ID; review the duplicate.")
            seen_payloads.add(payload)
            dates = {}
            for column in ("order_date_source", "delivery_date_source"):
                try:
                    if not re.fullmatch(r"\d{2}-\d{2}-\d{4}", row[column]):
                        raise ValueError
                    dates[column] = datetime.strptime(row[column], "%d-%m-%Y").date()
                except ValueError:
                    result.issue("error", line, column, "Use a valid date in DD-MM-YYYY format.")
            if len(dates) == 2 and dates["delivery_date_source"] < dates["order_date_source"]:
                result.issue("error", line, "delivery_date_source", "Delivery date precedes order date.")
            numbers = {}
            for column in NUMBER_COLUMNS:
                try:
                    value = Decimal(row[column])
                    positive = column in ("cloth_length_source", "duration_source")
                    if not value.is_finite() or value < 0 or (positive and value == 0):
                        raise InvalidOperation
                    numbers[column] = value
                except InvalidOperation:
                    rule = "positive" if column in ("cloth_length_source", "duration_source") else "nonnegative"
                    result.issue("error", line, column, f"Use a finite {rule} number; units remain unresolved.")
            water_columns = COLUMNS[12:]
            if all(column in numbers for column in water_columns):
                if sum(numbers[column] for column in water_columns[:3]) != numbers["water_total_source"]:
                    result.issue("error", line, "water_total_source", "Total must equal the three source water components.")
            if row["shade_depth_source"] == "Mdedium":
                result.issue("warning", line, "shade_depth_source", "Source spelling 'Mdedium' retained; confirm before future mapping.")
            elif row["shade_depth_source"] not in ("Light", "Medium", "Dark"):
                result.issue("warning", line, "shade_depth_source", "Unrecognised shade depth retained; review source spelling.")
            candidates.append({**row, "order_date_parsed": dates.get("order_date_source"),
                               "delivery_date_parsed": dates.get("delivery_date_source"),
                               "source_csv_line": line})
        if len(candidates) != 35:
            result.issue("error", None, "row_count", f"This milestone requires 35 distinct orders; found {len(candidates)}.")
        if result.valid:
            result.records = candidates
    except (UnicodeDecodeError, csv.Error) as exc:
        result.issue("error", None, "file", f"Cannot read UTF-8 CSV: {exc}")
        result.records = []
    return result


def load_bundled_orders() -> ImportResult:
    content = SOURCE_PATH.read_bytes()
    result = import_orders(content, SOURCE_KEY)
    expected = json.loads((PACK / "SHA256SUMS.json").read_text(encoding="utf-8"))[SOURCE_KEY]["sha256"]
    if result.sha256 != expected:
        result.issue("error", None, "checksum", "Bundled CSV differs from the dataset manifest; restore the original file.")
        result.records = []
    return result
