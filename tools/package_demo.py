"""Build an allowlisted, checksum-verified local demo ZIP. Never reads credentials."""

import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FOLDERS = ("01_sitara_faisalabad", "02_synthetic_thread_dyeing")
OUTPUT = ROOT / "dist/dyeing-copilot-integrated-recovery-v1-2026-10-16.zip"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def selected_files(root=ROOT):
    # A public checkout can deliberately omit redundant local milestone logs.
    # Its reviewed subset stays inside the workspace distribution allowlist.
    public = root / 'PUBLIC_DISTRIBUTION.json'
    if public.exists():
        names=json.loads(public.read_text(encoding='utf-8'))['files']
        paths=[root/name for name in names]
        if any(not p.resolve().is_relative_to(root.resolve()) or not p.is_file() for p in paths):
            raise ValueError('Invalid public distribution file selection.')
        return sorted(set(paths))
    paths = []
    paths.append(root / '.streamlit/config.toml')
    for name in ("streamlit_app.py", "requirements.txt", "README.md", ".env.example", ".gitignore",
                 "Dyeing_Copilot_Implementation_Plan.md", "demo_walkthrough.md", "DISTRIBUTION_DATA.md"):
        paths.append(root / name)
    for folder in ("app", "copilot", "daily", "planner", "tools", "tests"):
        paths.extend((root / folder).rglob("*.py"))
    report_docs = [f"milestone_{i}_verification.md" for i in range(1, 11)] + [
        "milestone_10_1_verification.md", "cp_sat_model.md", "milestone_8_1_verification.md", "milestone_8_2_verification.md", "amd_setup.md", "resource_model_card.md", "resource_training_protocol.md", "scenario_model.md", "source_rule_audit.md"]
    paths.extend(root / "reports" / name for name in report_docs)
    for name in ('demo_polish_verification.md','demo_polish_integrity.json',
                 'demo_polish_tests.txt','demo_polish_preservation.json','demo_polish_initial_tests.txt',
                 'selected_numeric_contract_verification.md','selected_numeric_contract_live_check.json',
                 'selected_numeric_contract_integrity.json','selected_numeric_contract_tests.txt',
                 'selected_numeric_contract_preservation.json'):
        paths.append(root / 'reports' / name)
    for name in ('demo_polish_packaged_checks.json','demo_polish_credentials_check.json','demo_polish_changed_files.json'):
        if (root / 'reports' / name).exists():paths.append(root / 'reports' / name)
    for name in ('industrial_dashboard_verification.md','industrial_dashboard_integrity.json',
                 'industrial_dashboard_preservation.json','industrial_dashboard_tests.txt','industrial_dashboard_browser.json',
                 'industrial_dashboard_packaged_checks.json','industrial_dashboard_credentials_check.json'):
        if (root / 'reports' / name).exists():paths.append(root / 'reports' / name)
    if (root / 'reports/industrial_dashboard_changed_files.json').exists():
        paths.append(root / 'reports/industrial_dashboard_changed_files.json')
    paths.extend((root / 'reports/industrial_dashboard_screenshots').glob('*.png'))
    paths.extend((root / 'reports').glob('integrated_recovery_*.md'))
    paths.extend((root / 'reports').glob('integrated_recovery_*.json'))
    paths.extend((root / 'reports').glob('integrated_recovery_*.txt'))
    paths.extend((root / 'reports').glob('integrated_interpreter_*.json'))
    paths.extend((root / 'reports').glob('permission_sensitivity_integrated_*.json'))
    browser_report=root/'reports/integrated_recovery_browser.json'
    if browser_report.exists():
        for screen in json.loads(browser_report.read_text(encoding='utf-8')).get('screens',[]):
            if not screen['name'].startswith('failed_'):
                path=(root/screen['path']).resolve()
                if not path.is_relative_to((root/'reports/integrated_recovery_screenshots').resolve()):
                    raise ValueError('Invalid integrated screenshot path.')
                paths.append(path)
    for name in ("amd_live_smoke.json", "daily_amd_live_smoke.json", "milestone_6_live_questions.json",
                 "milestone_6_mock_questions.json", "milestone_6_restricted_network_attempts.json", "milestone_6_integrity.json",
                 "milestone_6_packaged_regression.json", "milestone_7_scenario_checks.json",
                 "milestone_7_live_checks.json", "milestone_7_integrity.json", "milestone_7_startup.json",
                 "milestone_8_live_evaluation.json", "milestone_8_integrity.json", "milestone_8_demo.json",
                 "milestone_8_demo_change_audit.json", "milestone_8_packaged_checks.json",
                 "milestone_8_tests.txt", "milestone_8_tests_initial.txt",
                 "milestone_8_1_preservation_baseline.json", "milestone_8_1_live_evaluation.json",
                 "milestone_8_1_integrity.json", "milestone_8_1_examples.json", "milestone_8_1_packaged_regression.json"):
        path = root / "reports" / name
        if path.exists():
            paths.append(path)
    # Preserve historical evidence required by all versioned regression tests.
    for filename in ("milestone_8_2_preservation_baseline.json", "milestone_9_preservation_baseline.json", "milestone_10_preservation_baseline.json", "milestone_10_1_preservation_baseline.json"):
        baseline = root / "reports" / filename
        if baseline.exists():
            paths.extend(root / name for name in json.loads(baseline.read_text()).keys())
    for name in ("milestone_8_2_preservation_baseline.json", "milestone_8_2_protected_baseline.json",
                 "milestone_8_2_development.json", "milestone_8_2_development_diagnostics.json",
                 "milestone_8_2_live_evaluation.json", "milestone_8_2_live_diagnostics.json",
                 "milestone_8_2_integrity.json", "milestone_8_2_packaged_regression.json",
                 "milestone_8_2_test_result.json", "milestone_8_2_tests.txt",
                 "milestone_9_preservation_baseline.json", "scheduling_benchmark_v9.json",
                 "milestone_9_integrity.json", "milestone_9_test_result.json", "milestone_9_tests.txt",
                 "milestone_9_packaged_regression.json", "milestone_10_preservation_baseline.json",
                 "milestone_10_dependency_check.json", "milestone_10_integrity.json",
                 "scheduling_benchmark_v10.json", "scheduling_benchmark_v10_summary.json",
                 "milestone_10_tests.txt", "milestone_10_test_result.json", "milestone_10_packaged_regression.json",
                 "milestone_10_1_preservation_baseline.json", "milestone_10_1_integrity.json",
                 "milestone_10_1_tests.txt", "milestone_10_1_test_result.json", "milestone_10_1_live_checks.json",
                 "scheduling_benchmark_v10_1.json", "milestone_10_1_initial_packaged_failure.json",
                 "milestone_10_1_packaged_regression.json"):
        if (root / "reports" / name).exists():
            paths.append(root / "reports" / name)
    paths.extend((root / "evaluation").glob("*.json"))
    paths.append(root / "evaluation/requirements_m9.txt")
    paths.extend((root / "history").rglob("*.py"))
    for name in ("models.joblib", "metadata.json", "historical_predictions.csv"):
        paths.append(root / "artifacts/daily_resource" / name)
    pack = root / "dyeing_dataset_pack"
    for folder in DATA_FOLDERS:
        paths.extend(p for p in (pack / folder).rglob("*") if p.is_file())
    paths.extend(pack / name for name in ("README.md", "dataset_inventory.json"))
    # Keep external build/scan/startup receipts outside their own hashed ZIP.
    # The verification report, reproducible tools and regression logs remain inside.
    external=lambda p: p.name.startswith('integrated_recovery_') and p.name.endswith((
        '_packaged_checks.json','_credentials_check.json','_package_build.json','_delivery.json'))
    return sorted(set(p for p in paths if "__pycache__" not in p.parts and not external(p)))


def build(root=ROOT, output=OUTPUT):
    pack = root / "dyeing_dataset_pack"
    original = json.loads((pack / "SHA256SUMS.json").read_text(encoding="utf-8"))
    subset = {key: value for key, value in original.items() if key.split("/")[0] in DATA_FOLDERS}
    for key, entry in subset.items():
        data = (pack / key).read_bytes()
        if sha(data) != entry["sha256"] or len(data) != entry["bytes"]:
            raise ValueError("Original dataset integrity failed: " + key)
    payload = {p.relative_to(root).as_posix(): p.read_bytes() for p in selected_files(root)}
    payload["dyeing_dataset_pack/SHA256SUMS.json"] = json.dumps(subset, indent=2).encode()
    # Keep the acquisition-wide inventory/manifest as evidence, clearly separate from the runtime subset.
    acquisition = pack / "ACQUISITION_SHA256SUMS.json"
    payload["dyeing_dataset_pack/ACQUISITION_SHA256SUMS.json"] = (
        acquisition if acquisition.exists() else pack / "SHA256SUMS.json").read_bytes()
    for name in payload:
        parts = Path(name).parts
        if ("06_restricted_reuse_experiments" in parts or any(p in parts for p in (".venv", "data", ".git", "__pycache__"))
                or name.endswith((".sqlite3", ".db", ".pyc")) or Path(name).name == ".env"):
            raise ValueError("Forbidden distribution path: " + name)
    manifest = {name: {"sha256": sha(data), "bytes": len(data)} for name, data in sorted(payload.items())}
    payload["PACKAGE_MANIFEST.json"] = json.dumps(manifest, indent=2).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(payload.items()):
            info = zipfile.ZipInfo("dyeing-copilot/" + name, date_time=(2026, 10, 14, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=9)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC check failed")
        for name, entry in manifest.items():
            if sha(archive.read("dyeing-copilot/" + name)) != entry["sha256"]:
                raise ValueError("Packaged checksum failed: " + name)
    return {"zip": str(output), "bytes": output.stat().st_size, "sha256": sha(output.read_bytes()),
            "files": len(payload), "dataset_manifest_entries": len(subset), "restricted_data_included": False}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
