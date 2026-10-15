"""Read-only dataset, model and optional packaged-payload integrity checks."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root=ROOT):
    pack = root / "dyeing_dataset_pack"
    manifest = json.loads((pack / "SHA256SUMS.json").read_text(encoding="utf-8"))
    for name, entry in manifest.items():
        path = (pack / name).resolve()
        if not path.is_relative_to(pack.resolve()) or sha(path) != entry["sha256"] or path.stat().st_size != entry["bytes"]:
            raise ValueError("Dataset integrity failed: " + name)
    payloads = 0
    if (root / "PACKAGE_MANIFEST.json").exists():
        payload = json.loads((root / "PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
        for name, entry in payload.items():
            path = (root / name).resolve()
            if not path.is_relative_to(root.resolve()) or sha(path) != entry["sha256"] or path.stat().st_size != entry["bytes"]:
                raise ValueError("Packaged payload integrity failed: " + name)
        payloads = len(payload)
    # Imports resolve paths relative to installed project files, not an original workstation.
    from app.importer import load_bundled_orders
    from daily.importer import load_bundled_daily
    from daily.models import load_models
    orders, daily, artifact = load_bundled_orders(), load_bundled_daily(), load_models()
    if not orders.valid or not daily.valid:
        raise ValueError("Bundled importer rejected the samples")
    if artifact["artifact_fingerprint"] != "a9ceca69c82ee1b7b52b3f5516f77262b7ed16ad7e57e7ad4f8d874cfac0a035":
        raise ValueError("Frozen milestone 5 metadata changed")
    protected = ["app/importer.py", "app/resource_analysis.py", "daily/models.py", "requirements.txt",
                 "reports/resource_training_protocol.md", "reports/resource_model_card.md"]
    protected += [p.relative_to(root).as_posix() for p in (root / "planner").glob("*.py")]
    protected += ["artifacts/daily_resource/" + name for name in ("models.joblib", "metadata.json", "historical_predictions.csv")]
    return {"dataset_checksums_matched": len(manifest), "packaged_payloads_verified": payloads,
            "accepted_orders": len(orders.records), "accepted_synthetic_days": len(daily.frame),
            "model_version": artifact["metadata"]["model_version"], "frozen_metadata_sha256": artifact["artifact_fingerprint"],
            "protected_files": {name: sha(root / name) for name in sorted(protected)}}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
