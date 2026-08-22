#!/usr/bin/env python3
"""Check the explicit active Event-kind vector-gap backlog."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
REGISTRY = ARTIFACTS / "registry" / "event-kind-vector-gap-registry.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def evidence_text() -> str:
    paths = [
        *sorted((ARTIFACTS / "fixtures").glob("*.json")),
        ARTIFACTS / "registry" / "vector-registry.json",
        ROOT / "spec" / "v1" / "zh" / "conformance" / "conformance-vectors.md",
        ARTIFACTS / "profiles" / "conformance-profiles.json",
    ]
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def main() -> int:
    event_registry = load(ARTIFACTS / "registry" / "event-kind-registry.json")
    active = {
        row["event_kind"]
        for row in event_registry["event_kinds"]
        if row.get("status") == "active"
    }
    text = evidence_text()
    computed = {
        kind
        for kind in active
        if not any(
            token in text
            for token in (
                kind,
                kind.replace(".", "_"),
                "_".join(kind.split(".")[-2:]),
            )
        )
    }
    rows = load(REGISTRY).get("uncovered_event_kinds", [])
    declared = {row.get("event_kind") for row in rows}
    errors: list[str] = []
    if len(declared) != len(rows):
        errors.append("duplicate or missing event_kind in vector-gap registry")
    if declared != computed:
        errors.append(
            f"vector-gap registry drift: missing={sorted(computed - declared)}, "
            f"stale={sorted(declared - computed)}"
        )
    for index, row in enumerate(rows):
        if row.get("priority") not in {"normal", "high", "critical"}:
            errors.append(f"row {index} has invalid priority")
        if not isinstance(row.get("rationale"), str) or not row["rationale"].strip():
            errors.append(f"row {index} has no rationale")
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"event-kind vector-gap registry clean ({len(rows)} explicit gaps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
