import unittest
import zipfile

from app.importer import PACK
from tools.audit_source import audit


class SourceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = audit()

    def test_archive_text_versions_and_original_workbook_inspection(self):
        evidence = self.evidence
        self.assertEqual(evidence["text"]["distinct_rows"], 35)
        self.assertEqual(evidence["text"]["component_totals"], [9100, 18200, 20650])
        with zipfile.ZipFile(PACK / "01_sitara_faisalabad/original_supplement.zip") as archive:
            self.assertEqual(archive.read("Code-and-Dataset/Data_Set.txt"),
                             (PACK / "01_sitara_faisalabad/raw/Data_Set.txt").read_bytes())
        self.assertTrue(evidence["text"]["archive_members"][
            "Code-and-Dataset/Textile_Work/Project/Data_Set.txt"]["matches_local_distinct_records"])
        workbook = evidence["xlsx"]["raw/Code-and-Dataset/Textile_Work/Project/New folder/Data_Set.xlsx"]
        self.assertEqual(workbook["nonempty_rows"], 35)
        self.assertEqual(workbook["formula_count"], 0)
        self.assertEqual(workbook["last_row"]["K35"], "1")

    def test_primary_formula_diagnostic_reconciles_scalar_not_recorded_rows(self):
        evidence = self.evidence
        formula = evidence["primary_formula_reading"]
        self.assertEqual(formula["term_totals"], [9800, 20650, 20650])
        self.assertEqual(formula["total"], 51100)
        self.assertEqual(formula["total"] - evidence["text"]["total"], 3150)
        self.assertEqual(len(formula["differences_from_text"]), 12)
        self.assertEqual(sum(r["formula_minus_recorded"] for r in formula["differences_from_text"]), 3150)


if __name__ == "__main__":
    unittest.main()
