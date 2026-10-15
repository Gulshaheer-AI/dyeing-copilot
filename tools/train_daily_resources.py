"""Project-owned reproducible training. Does not execute downloaded research code."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from daily.importer import import_daily, load_bundled_daily
from daily.models import ARTIFACT_DIR, train_models


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, help="Optional separate synthetic daily CSV with the same unit contract")
    parser.add_argument("--output-dir", type=Path, default=ARTIFACT_DIR)
    args = parser.parse_args()
    source = load_bundled_daily() if args.csv is None else import_daily(args.csv.read_bytes(), str(args.csv))
    if not source.valid:
        print(json.dumps(source.issues, indent=2))
        return 1
    artifact = train_models(source, args.output_dir)
    print(json.dumps({key: artifact["metadata"][key] for key in ("model_version", "dataset_sha256", "splits", "results")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
