import csv
import io
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from app.importer import COLUMNS, PACK, SOURCE_PATH, import_orders, load_bundled_orders


class ImporterTests(unittest.TestCase):
    def setUp(self):
        self.content = SOURCE_PATH.read_bytes()
        self.rows = list(csv.DictReader(io.StringIO(self.content.decode("utf-8"))))

    def encode(self, rows=None, header=COLUMNS):
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(self.rows if rows is None else rows)
        return buffer.getvalue().encode("utf-8")

    def assert_rejected(self, content, field):
        result = import_orders(content)
        self.assertFalse(result.valid)
        self.assertEqual(result.records, [])
        self.assertTrue(any(i["field"] == field and i["severity"] == "error" for i in result.issues))

    def test_bundled_case_and_source_preservation(self):
        result = load_bundled_orders()
        self.assertTrue(result.valid)
        self.assertEqual(len(result.records), 35)
        self.assertEqual({r["source_row_id"] for r in result.records}, {str(i) for i in range(1, 36)})
        self.assertEqual(sum(Decimal(r["water_total_source"]) for r in result.records), 47950)
        self.assertEqual(result.records[0]["order_date_parsed"], date(2019, 11, 10))
        self.assertEqual(result.records[13]["order_date_parsed"], date(2020, 1, 2))
        for original, imported in zip(self.rows, result.records):
            self.assertEqual(original, {c: imported[c] for c in COLUMNS})
        self.assertEqual(result.records[4]["shade_depth_source"], "Mdedium")
        self.assertTrue(any("Mdedium" in i["message"] for i in result.issues))

    def test_repeated_block_is_counted_once_and_repeat_calls_do_not_accumulate(self):
        content = self.encode(self.rows * 2)
        for _ in range(2):
            result = import_orders(content)
            self.assertTrue(result.valid)
            self.assertEqual(result.input_rows, 70)
            self.assertEqual(result.duplicates_removed, 35)
            self.assertEqual(len(result.records), 35)

    def test_csv_matches_all_distinct_original_text_records(self):
        text = (PACK / "01_sitara_faisalabad/raw/Data_Set.txt").read_text(encoding="utf-8")
        original = [tuple(line.split()) for line in text.splitlines() if line.strip()]
        self.assertEqual(len(original), 70)
        distinct = list(dict.fromkeys(original))
        self.assertEqual(len(distinct), 35)
        self.assertEqual(distinct, [tuple(row[c] for c in COLUMNS[1:]) for row in self.rows])

    def test_conflicting_id_and_duplicate_payload(self):
        self.rows[1]["source_row_id"] = "1"
        self.assert_rejected(self.encode(), "source_row_id")
        self.rows[1] = {**self.rows[0], "source_row_id": "2"}
        self.assert_rejected(self.encode(), "source_row_id")

    def test_invalid_dates_and_delivery_order(self):
        for value in ("11/10/2019", "31-02-2019", "2019-11-10", "1-11-2019"):
            with self.subTest(value=value):
                self.rows[0]["order_date_source"] = value
                self.assert_rejected(self.encode(), "order_date_source")
        self.rows[0]["order_date_source"] = "10-11-2019"
        self.rows[0]["delivery_date_source"] = "09-11-2019"
        self.assert_rejected(self.encode(), "delivery_date_source")

    def test_numeric_validation(self):
        for column, values in {
            "cloth_length_source": ["0", "-1", "NaN", "Infinity", "unknown"],
            "duration_source": ["0", "-1"],
            "water_component_1_source": ["-1", "NaN", "Infinity"],
        }.items():
            original = self.rows[0][column]
            for value in values:
                with self.subTest(column=column, value=value):
                    self.rows[0][column] = value
                    self.assert_rejected(self.encode(), column)
            self.rows[0][column] = original

    def test_water_sum_mismatch(self):
        self.rows[0]["water_total_source"] = "1051"
        self.assert_rejected(self.encode(), "water_total_source")

    def test_missing_value_invalid_id_and_missing_order(self):
        self.rows[0]["customer_source"] = " "
        self.assert_rejected(self.encode(), "customer_source")
        self.rows[0]["customer_source"] = "CGU"
        for value in ("0", "1.0", "bad"):
            self.rows[0]["source_row_id"] = value
            self.assert_rejected(self.encode(), "source_row_id")
        self.assert_rejected(self.encode(self.rows[1:]), "row_count")

    def test_bad_header_encoding_and_row_width(self):
        self.assert_rejected(self.encode(header=COLUMNS[:-1]), "header")
        self.assert_rejected(b"\xff", "file")
        self.assert_rejected(self.content + b"one,two\n", "row")
        self.assert_rejected(b'"unterminated', "file")

    def test_bom_reordered_columns_and_blank_lines(self):
        result = import_orders(b"\xef\xbb\xbf" + self.encode(header=tuple(reversed(COLUMNS))) + b"\n\n")
        self.assertTrue(result.valid)
        self.assertEqual(len(result.records), 35)

    def test_bundled_checksum_mismatch_blocks_import(self):
        with patch("app.importer.Path.read_bytes", return_value=self.encode() + b"\n"):
            result = load_bundled_orders()
        self.assertFalse(result.valid)
        self.assertEqual(result.records, [])
        self.assertEqual(result.issues[-1]["field"], "checksum")


if __name__ == "__main__":
    unittest.main()
