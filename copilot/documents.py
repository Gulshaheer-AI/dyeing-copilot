"""Read-only section retrieval from explicitly unapproved project documents."""

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = {"source-audit": ROOT / "reports/source_rule_audit.md",
        "scenario-model": ROOT / "reports/scenario_model.md"}
AUDIT_BOUNDARY = "doc:source-audit#unresolved-assumptions-and-application-boundary"
MODEL_EQUATIONS = "doc:scenario-model#deterministic-equations"


def retrieve_project_sections(question, limit=4, *, documents=None, mandatory=None):
    sections, hashes = {}, {}
    for name, path in (DOCS if documents is None else documents).items():
        content = path.read_text(encoding="utf-8")
        hashes[name] = hashlib.sha256(content.encode()).hexdigest()
        parts = re.split(r"(?m)^## (.+)\n", content)
        for index in range(1, len(parts), 2):
            heading, passage = parts[index], parts[index + 1].strip()
            slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
            ref = f"doc:{name}#{slug}"
            sections[ref] = {"document_id": name, "section": heading,
                             "path": path.relative_to(ROOT).as_posix(), "sha256": hashes[name],
                             "passage": passage, "approved_machine_sop": False}
    mandatory = [AUDIT_BOUNDARY, MODEL_EQUATIONS] if mandatory is None else mandatory
    words = set(re.findall(r"[a-z]{3,}", question.lower()))
    ranked = sorted(sections, key=lambda ref: (-len(words & set(re.findall(
        r"[a-z]{3,}", sections[ref]["section"].lower() + " " + sections[ref]["passage"].lower()))), ref))
    chosen = list(dict.fromkeys(mandatory + ranked))[:limit]
    return {ref: sections[ref] for ref in chosen}, hashes
