"""Project-owned descriptive audit; never runs downloaded research code."""

from daily.importer import COLUMNS, NUMERIC, UNITS, require_daily


def profile_daily(result):
    d = require_daily(result)
    relationships = {"water_total_vs_kg_times_L_per_kg": ("Total_Water_Consumption_L", "Water_Consumption_L_per_kg", 1),
                     "electricity_total_vs_kg_times_kWh_per_kg": ("Total_Energy_kWh", "Energy_Consumption_kWh_per_kg", 1),
                     "wastewater_total_vs_kg_times_L_per_kg": ("Wastewater_L", "Wastewater_L_per_kg", 1)}
    for prefix in ("Dye_Used", "Salt", "Alkali", "Acid", "Auxiliary"):
        relationships[prefix + "_mass_vs_intensity"] = (prefix + "_kg", prefix + "_g_per_kg", 0.001)
    audit = {}
    for label, (total, intensity, scale) in relationships.items():
        delta = (d[total] - d.Production_Volume_kg * d[intensity] * scale).abs()
        audit[label] = {"mean_absolute_rounding_difference": float(delta.mean()), "max_absolute_rounding_difference": float(delta.max()),
                        "max_relative_difference": float((delta / d[total].where(d[total] != 0)).max())}
    roles = {}
    for c in COLUMNS:
        if c in ("Date", "Month", "Year"):
            role = "calendar identifiers; excluded"
        elif c in ("Day_Type", "Monthly_Demand_Factor"):
            role = "synthetic label/factor; excluded from inputs and ground truth"
        elif c.startswith("Total_"):
            role = "resource total; direct target counterpart; excluded"
        elif c in ("Water_Consumption_L_per_kg", "Energy_Consumption_kWh_per_kg"):
            role = "separate target intensity; excluded from all input features"
        elif c in ("Production_Volume_kg", "Production_Volume_ton"):
            role = "daily production; tonne column is rounded duplicate"
        elif any(word in c for word in ("Waste", "BOD", "COD", "pH")):
            role = "post-process waste/wastewater outcome or derived intensity; excluded"
        elif any(word in c for word in ("Dye_Used", "Salt", "Alkali", "Acid", "Auxiliary")):
            role = "chemical mass/intensity arithmetic counterparts; conservatively excluded"
        else:
            role = "retrospective workload/process observation (fixation conservatively excluded)"
        roles[c] = {"role": role, "unit": UNITS.get(c, "date/category")}
    return {"label": "Synthetic daily thread-dyeing data", "sha256": result.sha256, "rows": len(d), "columns": len(COLUMNS),
            "first_date": str(d.Date.iloc[0].date()), "last_date": str(d.Date.iloc[-1].date()), "field_roles": roles,
            "missing_values": int(d[list(COLUMNS)].isna().sum().sum()), "relationships": audit,
            "numeric_ranges": {c: {"min": float(d[c].min()), "max": float(d[c].max())} for c in NUMERIC},
            "warning": "Arithmetic/rounding audit only. Day_Type is neither a predictor nor anomaly ground truth. No measured factory telemetry."}
