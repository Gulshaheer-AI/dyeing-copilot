"""Strict daily CSV contract; never concatenates with Sitara orders."""

import calendar
import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "dyeing_dataset_pack"
SOURCE_KEY = "02_synthetic_thread_dyeing/csv/Textile_Dyeing_Dataset_Causal_Sheet1.csv"
SOURCE_PATH = PACK / SOURCE_KEY
LABEL = "Synthetic daily thread-dyeing data"
COLUMNS = tuple("Date Month Year Day_Type Monthly_Demand_Factor Production_Volume_ton Production_Volume_kg "
    "Machine_Utilization_% Number_of_Workers Energy_Consumption_kWh_per_kg Total_Energy_kWh "
    "Water_Consumption_L_per_kg Total_Water_Consumption_L Dye_Fixation_Ratio_% Liquor_Ratio_1:x "
    "Temperature_C Cycle_Time_hr Dye_Batch_Count Dye_Used_g_per_kg Dye_Used_kg Salt_g_per_kg Salt_kg "
    "Alkali_g_per_kg Alkali_kg Acid_g_per_kg Acid_kg Auxiliary_g_per_kg Auxiliary_kg Solid_Waste_kg "
    "Solid_Waste_%_of_Production Yarn_Waste_kg Yarn_Waste_%_of_Production Chemical_Waste_kg "
    "Chemical_Waste_kg_per_1000kg Wastewater_L Wastewater_L_per_kg BOD_mg_per_L COD_mg_per_L pH".split())
NUMERIC = tuple(c for c in COLUMNS if c not in ("Date", "Month", "Day_Type"))
UNITS = {c: ("kWh/kg" if c == "Energy_Consumption_kWh_per_kg" else "L/kg" if c in
    ("Water_Consumption_L_per_kg", "Wastewater_L_per_kg") else "tonnes" if c.endswith("_ton") else
    "g/kg" if c.endswith("_g_per_kg") else "kg/1000kg" if c.endswith("_kg_per_1000kg") else
    "kg" if c.endswith("_kg") else "kWh" if c.endswith("_kWh") else "L" if c.endswith("_L") else
    "mg/L" if c.endswith("_mg_per_L") else "%" if "%" in c else "C" if c == "Temperature_C" else
    "hours" if c == "Cycle_Time_hr" else "ratio" if c == "Liquor_Ratio_1:x" else "count/index/dimensionless") for c in NUMERIC}


@dataclass
class DailyImport:
    filename: str
    sha256: str
    frame: pd.DataFrame | None = None
    issues: list[dict] = field(default_factory=list)

    @property
    def valid(self):
        return self.frame is not None and not any(i["severity"] == "error" for i in self.issues)


def import_daily(content: bytes, filename="uploaded_synthetic_daily.csv"):
    result = DailyImport(filename, hashlib.sha256(content).hexdigest())
    def error(line, column, message):
        result.issues.append({"severity": "error", "csv_line": line, "field": column, "message": message})
    try:
        reader = csv.reader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        header = next(reader, [])
        if len(header) != len(COLUMNS) or set(header) != set(COLUMNS):
            error(1, "header", "Require the exact 39 named fields, including unit-bearing column names. No unit conversion is inferred.")
            return result
        rows, dates = [], set()
        for values in reader:
            if not values or all(not v.strip() for v in values):
                continue
            line = reader.line_num
            if len(values) != len(header):
                error(line, "row", "Expected 39 cells.")
                continue
            row = dict(zip(header, values))
            if any(not value.strip() for value in values):
                error(line, "row", "All required fields must be nonempty.")
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["Date"]):
                    raise ValueError
                date = datetime.strptime(row["Date"], "%Y-%m-%d")
                if date in dates:
                    error(line, "Date", "Duplicate daily date; resolve it rather than double-counting or averaging.")
                dates.add(date)
                if row["Month"] != calendar.month_name[date.month] or row["Year"] != str(date.year):
                    error(line, "Month/Year", "Month and Year must agree with Date.")
            except ValueError:
                error(line, "Date", "Use a valid YYYY-MM-DD calendar date.")
            for column in NUMERIC:
                try:
                    value = float(row[column])
                    if not np.isfinite(value) or value < 0:
                        raise ValueError
                    if column in ("Production_Volume_kg", "Production_Volume_ton", "Cycle_Time_hr", "Liquor_Ratio_1:x") and value <= 0:
                        raise ValueError
                    if "%" in column and value > 100 or column == "pH" and value > 14:
                        raise ValueError
                    if column in ("Year", "Number_of_Workers", "Dye_Batch_Count") and value != int(value):
                        raise ValueError
                except (ValueError, OverflowError):
                    error(line, column, "Invalid finite numeric value/range for documented unit " + UNITS[column] + ". Production must be positive.")
            row["source_csv_line"] = line
            rows.append(row)
        if not rows:
            error(None, "rows", "No daily records found.")
        if result.issues:
            return result
        frame = pd.DataFrame(rows)
        for column in NUMERIC:
            frame[column] = pd.to_numeric(frame[column])
        frame["Date"] = pd.to_datetime(frame["Date"], format="%Y-%m-%d")
        frame = frame.sort_values("Date", kind="stable").reset_index(drop=True)
        result.frame = frame
        if len(frame) > 1 and frame.Date.diff().dropna().max() > pd.Timedelta(days=1):
            result.issues.append({"severity": "warning", "csv_line": None, "field": "Date", "message": "Calendar gaps present; records are not interpolated."})
        return result
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        error(None, "file", "Cannot read daily UTF-8 CSV: " + type(exc).__name__)
        return result


def load_bundled_daily():
    result = import_daily(SOURCE_PATH.read_bytes(), SOURCE_KEY)
    expected = json.loads((PACK / "SHA256SUMS.json").read_text(encoding="utf-8"))[SOURCE_KEY]["sha256"]
    if result.sha256 != expected:
        result.issues.append({"severity": "error", "csv_line": None, "field": "checksum", "message": "Bundled daily CSV differs from its manifest."})
        result.frame = None
    return result


def require_daily(result):
    if not isinstance(result, DailyImport) or not result.valid:
        raise ValueError("Require a successfully validated synthetic daily import.")
    return result.frame.copy(deep=True)
