import copy
import csv
import io
import unittest
from decimal import Decimal

from app.importer import COLUMNS, ImportResult, import_orders, load_bundled_orders
from app.resource_analysis import GROUP_FIELDS, WATER_FIELDS, analyze_resources


def edited_import(edit):
    rows = copy.deepcopy(load_bundled_orders().records)
    edit(rows)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return import_orders(stream.getvalue().encode(), "edited.csv")


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.result = load_bundled_orders()

    def test_component_totals_reconcile_without_mutating_records(self):
        before = copy.deepcopy(self.result.records)
        report = analyze_resources(self.result)
        self.assertEqual(list(report.overall.totals.values()), [9100, 18200, 20650, 47950])
        self.assertEqual(sum(report.overall.totals[f] for f in WATER_FIELDS[:3]), 47950)
        self.assertEqual(report.overall, report.filtered)
        self.assertEqual(self.result.records, before)

    def test_grouped_counts_and_every_component_reconcile(self):
        for report in (analyze_resources(self.result), analyze_resources(self.result, fabrics=["Cotton"])):
            for summary in (report.overall, report.filtered):
                for field in GROUP_FIELDS:
                    self.assertEqual(sum(r["order_count"] for r in summary.groups[field]), summary.order_count)
                    for water in WATER_FIELDS:
                        self.assertEqual(sum(r[water] for r in summary.groups[field]), summary.totals[water])
        summary = analyze_resources(self.result).overall
        self.assertEqual({r["fabric_type_source"]: r["water_total_source"]
                          for r in summary.groups["fabric_type_source"]}, {"Cotton": 32200, "PolyCotton": 15750})
        self.assertEqual({r["vessel_type_source"]: r["water_total_source"]
                          for r in summary.groups["vessel_type_source"]}, {"Jet": 8400, "Open": 26950, "Pressure": 12600})

    def test_contributions_ranking_ties_and_source_traceability(self):
        rows = analyze_resources(self.result).overall.ranked_orders
        self.assertEqual([r["source_row_id"] for r in rows[:2]], ["27", "35"])
        self.assertEqual([r["rank_in_view"] for r in rows], list(range(1, 36)))
        self.assertEqual([r["water_total_source"] for r in rows], sorted(
            [r["water_total_source"] for r in rows], reverse=True))
        self.assertAlmostEqual(sum(r["overall_case_contribution_pct"] for r in rows), Decimal(100))
        for row in rows:
            self.assertEqual(row["overall_case_contribution_pct"], row["water_total_source"] * 100 / 47950)
            original = self.result.records[int(row["source_row_id"]) - 1]
            self.assertEqual(row["source_csv_line"], original["source_csv_line"])

    def test_filters_intersect_and_keep_overall_denominator(self):
        report = analyze_resources(self.result, customers=["CGU"], fabrics=["Cotton"], vessels=["Open"])
        self.assertEqual(report.overall.totals["water_total_source"], 47950)
        self.assertEqual(report.filtered.order_count, 3)
        self.assertEqual(report.filtered.totals["water_total_source"], 3150)
        self.assertEqual({r["source_row_id"] for r in report.filtered.ranked_orders}, {"1", "2", "3"})
        self.assertAlmostEqual(sum(r["overall_case_contribution_pct"] for r in report.filtered.ranked_orders),
                               Decimal(3150) * 100 / 47950)
        multi = analyze_resources(self.result, customers=["CGU", "Camric"])
        self.assertEqual(multi.filtered.totals["water_total_source"], 8400)

    def test_empty_filter_result_and_zero_water_case(self):
        report = analyze_resources(self.result, customers=["CGU"], fabrics=["PolyCotton"])
        self.assertEqual(report.filtered.order_count, 0)
        self.assertEqual(report.filtered.ranked_orders, [])
        self.assertTrue(all(v == 0 for v in report.filtered.totals.values()))
        self.assertTrue(all(not rows for rows in report.filtered.groups.values()))
        zero = edited_import(lambda rows: [r.update({f: "0" for f in WATER_FIELDS}) for r in rows])
        self.assertTrue(zero.valid)
        report = analyze_resources(zero)
        self.assertTrue(all(r["overall_case_contribution_pct"] is None for r in report.overall.ranked_orders))

    def test_upload_totals_and_decimal_values_are_calculated(self):
        uploaded = edited_import(lambda rows: rows[0].update(
            water_component_1_source="350.25", water_total_source="1050.25"))
        self.assertTrue(uploaded.valid)
        report = analyze_resources(uploaded, customers=["CGU"])
        self.assertEqual(report.overall.totals["water_total_source"], Decimal("47950.25"))
        self.assertEqual(report.filtered.totals["water_total_source"], Decimal("4550.25"))
        self.assertEqual(report.overall.totals[WATER_FIELDS[0]], Decimal("9100.25"))

    def test_failed_empty_and_raw_inputs_rejected(self):
        for bad in (import_orders(b"invalid"), ImportResult("empty", ""), self.result.records):
            with self.subTest(bad=type(bad).__name__), self.assertRaises(ValueError):
                analyze_resources(bad)


if __name__ == "__main__":
    unittest.main()
