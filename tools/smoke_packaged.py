"""Extract the ZIP in an isolated workspace folder and check its actual startup."""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, default=ROOT / "dist/dyeing-copilot-milestone-10-1.zip")
    parser.add_argument("--tests", action="store_true", help="Also run all offline checks in the extracted copy")
    parser.add_argument("--output",type=Path,default=ROOT / "reports/milestone_10_1_packaged_checks.json")
    args = parser.parse_args()
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    # Temporary cleanup is confined to a newly created directory under the workspace.
    with tempfile.TemporaryDirectory(prefix="packaged-check-", dir=destination) as directory:
        extracted = Path(directory).resolve()
        if not extracted.is_relative_to(destination.resolve()):
            raise ValueError("Unsafe temporary extraction path")
        with zipfile.ZipFile(args.zip) as archive:
            for member in archive.namelist():
                if not (extracted / member).resolve().is_relative_to(extracted):
                    raise ValueError("Unsafe ZIP path")
            archive.extractall(extracted)
        project = extracted / "dyeing-copilot"
        env = {key: value for key, value in os.environ.items()
               if key not in ("AMD_API_KEY", "AMD_BASE_URL", "AMD_MODEL", "PYTHONPATH")}
        checked = subprocess.run([sys.executable, "tools/verify_demo.py"], cwd=project, env=env,
                                 capture_output=True, text=True, check=True)
        outcome = {"extracted_integrity": json.loads(checked.stdout), "uses_existing_pinned_interpreter": True,
                   "clean_venv_dependency_install": "not performed", "browser_verification": "not performed by this startup check; see separate browser report",
                   "credentials_in_extracted_project": (project / ".env").exists()}
        if args.tests:
            tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                                   cwd=project, env=env, capture_output=True, text=True)
            outcome["offline_tests_exit_code"] = tests.returncode
            outcome["offline_tests_summary"] = tests.stderr.splitlines()[-4:]
            if tests.returncode:
                print(tests.stderr)
                raise ValueError("Extracted regression checks failed")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        process = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
            "--server.headless", "true", "--server.address", "127.0.0.1", "--server.port", str(port),
            "--browser.gatherUsageStats", "false"], cwd=project, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            deadline = time.monotonic() + 20
            while True:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=2) as response:
                        outcome["health_status"] = response.status
                        outcome["health_body"] = response.read().decode()
                    break
                except OSError:
                    if time.monotonic() > deadline or process.poll() is not None:
                        raise ValueError("Packaged server did not start") from None
                    time.sleep(.25)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
                outcome["root_http_status"] = response.status
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    args.output.write_text(json.dumps(outcome, indent=2), encoding="utf-8")
    print(json.dumps(outcome, indent=2))


if __name__ == "__main__":
    main()
