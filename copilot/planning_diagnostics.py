"""Opt-in bounded diagnostics ONLY for exact bundled non-sensitive evaluation texts."""

import json
import re
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]


class EvaluationDiagnostics:
    def __init__(self, corpus_path, *, limit):
        path = Path(corpus_path).resolve()
        if path != ROOT / "evaluation/planning_requests_v8_2.json":
            raise ValueError("Diagnostics require the bundled v8.2 corpus.")
        self.allowed = {r["text"] for r in json.loads(path.read_text(encoding="utf-8"))["cases"]}
        self.limit, self.records, self.lock = limit, [], Lock()

    def capture(self, request, content, receipt, error, secret):
        from app.importer import load_bundled_orders
        if request.text not in self.allowed or request.source_sha256 != load_bundled_orders().sha256:
            raise ValueError("Diagnostic retention is restricted to bundled non-sensitive evaluation inputs.")
        # No headers/config are accepted. Suppress the entire payload if credential-like
        # content appears; do not persist even a partially redacted credential.
        serialized = json.dumps({"content": content, "receipt": receipt, "error": error})
        blocked = (bool(secret and secret in serialized) or bool(re.search(
            r"authorization|bearer\s+\S+|api[_ -]?key|sk-[A-Za-z0-9]{12,}", serialized, re.I)))
        row = {"request": request.text, "content": None if blocked else content,
               "receipt": None if blocked else receipt, "validation_error": None if blocked else error,
               "credential_screen": "payload_suppressed" if blocked else "passed"}
        with self.lock:
            if len(self.records) >= self.limit:
                raise ValueError("Bounded diagnostic limit reached.")
            self.records.append(row)
