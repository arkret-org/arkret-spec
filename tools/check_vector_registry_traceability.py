#!/usr/bin/env python3
"""Hold every active conformance vector to traceable machine fixture evidence.

This mirrors Cotest's strict vector registry gate
(`cotest/src/conformance/vector_registry_gate.rs`,
`COTEST_VECTOR_REGISTRY_GATE_STRICT=1`) so that the spec release gate and the
certification gate reach the same verdict on the same registry:

* an `active` row MUST name at least one `spec/v1/artifacts/fixtures/` source_ref;
  a row whose evidence is prose or a clause registry alone is "active doc-only"
  and fails;
* every fixture source_ref of an active row MUST exist, be listed in
  `reports/fixture-digests.json` with a lowercase SHA-256 equal to the file's
  CRLF-normalized digest, and carry the vector id through a `vector_id`,
  `negative_cases_vector_id`, `name` or `covers_vectors` member somewhere in
  the document;
* `reserved` and `unsupported` rows are non-gating but MUST carry a non-empty
  description stating why, and any other status fails.

A vector that is still a current obligation but has no machine fixture belongs
in `reserved` with its activation condition, not in `active`.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
VECTOR_REGISTRY = ARTIFACTS / "registry" / "vector-registry.json"
FIXTURE_DIGESTS = ARTIFACTS / "reports" / "fixture-digests.json"
FIXTURE_PREFIX = "spec/v1/artifacts/fixtures/"
ARTIFACT_PREFIX = "spec/v1/artifacts/"
EVIDENCE_MEMBERS = ("vector_id", "negative_cases_vector_id", "name")
NON_GATING_STATUSES = ("reserved", "unsupported")


def fixture_digest_hex(data: bytes) -> str:
    """Producer-compatible fixture digest: CRLF and lone CR normalize to LF."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def collect_vector_evidence(value: Any, vector_id: str, pointer: str = "") -> list[str]:
    """Return JSON pointers of every member that binds `vector_id` inside one fixture."""
    found: list[str] = []
    if isinstance(value, dict):
        for member in EVIDENCE_MEMBERS:
            if value.get(member) == vector_id:
                found.append(f"{pointer or '/'} via {member}")
        covers = value.get("covers_vectors")
        if isinstance(covers, list) and vector_id in covers:
            found.append(f"{pointer or '/'} via covers_vectors")
        for key, child in value.items():
            token = str(key).replace("~", "~0").replace("/", "~1")
            found.extend(collect_vector_evidence(child, vector_id, f"{pointer}/{token}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(collect_vector_evidence(child, vector_id, f"{pointer}/{index}"))
    return found


def load_fixture_digests(path: Path) -> dict[str, str] | None:
    if not path.is_file():
        return None
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        row["path"]: row["sha256"]
        for row in report.get("files", [])
        if isinstance(row, dict) and isinstance(row.get("path"), str) and isinstance(row.get("sha256"), str)
    }


def row_errors(
    row: dict[str, Any],
    root: Path,
    digests: dict[str, str] | None,
    fixture_cache: dict[str, Any],
) -> list[str]:
    vector_id = row.get("vector_id")
    status = row.get("status")
    source_refs = row.get("source_refs") if isinstance(row.get("source_refs"), list) else []
    fixture_refs = [ref for ref in source_refs if isinstance(ref, str) and ref.startswith(FIXTURE_PREFIX)]

    if status in NON_GATING_STATUSES:
        description = row.get("description")
        if not isinstance(description, str) or not description.strip():
            return [f"{vector_id}: {status} vector rows require a description reason"]
        return []
    if status != "active":
        return [f"{vector_id}: unsupported registry status {status!r}"]
    if not fixture_refs:
        return [
            f"{vector_id}: active doc-only registry entry has no artifact fixture source_ref; "
            "attach machine fixture evidence, or move the row to reserved with its reason "
            "and activation condition, or delete it"
        ]

    errors: list[str] = []
    for fixture_ref in fixture_refs:
        path = root / fixture_ref
        if not path.is_file():
            errors.append(f"{vector_id}: {fixture_ref} (file not found)")
            continue
        raw = path.read_bytes()
        if digests is None:
            errors.append(f"{vector_id}: {fixture_ref} (fixture digest report reports/fixture-digests.json not found)")
            continue
        expected = digests.get(fixture_ref)
        if expected is None:
            errors.append(f"{vector_id}: {fixture_ref} (not listed in reports/fixture-digests.json)")
            continue
        if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
            errors.append(f"{vector_id}: {fixture_ref} (reports/fixture-digests.json sha256 is malformed)")
            continue
        actual = fixture_digest_hex(raw)
        if actual != expected:
            errors.append(f"{vector_id}: {fixture_ref} (fixture digest drift: expected {expected}, actual {actual})")
            continue
        if fixture_ref not in fixture_cache:
            fixture_cache[fixture_ref] = json.loads(raw.decode("utf-8"))
        if not collect_vector_evidence(fixture_cache[fixture_ref], vector_id):
            errors.append(
                f"{vector_id}: {fixture_ref} (vector_id not found via vector_id, "
                "negative_cases_vector_id, name, or covers_vectors)"
            )
    return errors


def registry_errors(registry: dict[str, Any], root: Path, digests: dict[str, str] | None) -> list[str]:
    errors: list[str] = []
    fixture_cache: dict[str, Any] = {}
    for row in registry.get("vectors", []):
        if isinstance(row, dict):
            errors.extend(row_errors(row, root, digests, fixture_cache))
    return errors


def main() -> int:
    registry = json.loads(VECTOR_REGISTRY.read_text(encoding="utf-8"))
    errors = registry_errors(registry, ROOT, load_fixture_digests(FIXTURE_DIGESTS))
    rows = [row for row in registry.get("vectors", []) if isinstance(row, dict)]
    if errors:
        for error in errors:
            print(f"vector-registry traceability: {error}", file=sys.stderr)
        print(f"vector registry traceability: FAIL ({len(errors)} error(s) over {len(rows)} rows)")
        return 1
    active = sum(1 for row in rows if row.get("status") == "active")
    print(
        f"vector registry traceability: every one of {active} active rows is fixture-backed "
        f"({len(rows) - active} non-gating rows carry a reason)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
