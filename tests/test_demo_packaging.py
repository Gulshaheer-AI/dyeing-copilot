import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.package_demo import ROOT, build, selected_files


class DemoPackagingTests(unittest.TestCase):
    def test_allowlist_excludes_credentials_reviews_restricted_data_and_caches(self):
        names = {p.relative_to(ROOT).as_posix() for p in selected_files()}
        self.assertIn(".env.example", names)
        self.assertIn("artifacts/daily_resource/models.joblib", names)
        self.assertIn("reports/resource_training_protocol.md", names)
        self.assertFalse(any(name == ".env" or "__pycache__" in name or name.startswith(("data/", ".venv/"))
                             or "06_restricted_reuse_experiments" in name for name in names))

    def test_archive_manifests_hashes_and_frozen_model_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "demo.zip"
            summary = build(output=output)
            self.assertGreater(summary["dataset_manifest_entries"], 2)
            with zipfile.ZipFile(output) as archive:
                payload = json.loads(archive.read("dyeing-copilot/PACKAGE_MANIFEST.json"))
                self.assertEqual(len(payload) + 1, summary["files"])
                subset = json.loads(archive.read("dyeing-copilot/dyeing_dataset_pack/SHA256SUMS.json"))
                acquisition = ROOT / "dyeing_dataset_pack/ACQUISITION_SHA256SUMS.json"
                original = json.loads((acquisition if acquisition.exists() else ROOT / "dyeing_dataset_pack/SHA256SUMS.json").read_text())
                self.assertLess(len(subset), len(original))
                for name, entry in subset.items():
                    self.assertEqual(entry, original[name])
                    self.assertEqual(hashlib.sha256(archive.read("dyeing-copilot/dyeing_dataset_pack/" + name)).hexdigest(), entry["sha256"])
                for name in ("models.joblib", "metadata.json", "historical_predictions.csv"):
                    relative = "artifacts/daily_resource/" + name
                    self.assertEqual(archive.read("dyeing-copilot/" + relative), (ROOT / relative).read_bytes())
                self.assertFalse(any("06_restricted_reuse_experiments/" in name or name.endswith("/.env") for name in archive.namelist()))


if __name__ == "__main__":
    unittest.main()
