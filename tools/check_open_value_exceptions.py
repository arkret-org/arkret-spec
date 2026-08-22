#!/usr/bin/env python3
"""Verify that every active Event payload empty value schema is explicitly registered."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
CONTRACTS = ARTIFACTS / "registry" / "contract-registry.json"
PAYLOAD_SCHEMA = ARTIFACTS / "schemas" / "event-payload.schema.json"
EXCEPTIONS = ARTIFACTS / "registry" / "open-value-exception-registry.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    contracts = load(CONTRACTS)
    defs = load(PAYLOAD_SCHEMA)["$defs"]
    registry = load(EXCEPTIONS)
    actual: set[tuple[str, str]] = set()
    for row in contracts["event_kind_registry"]["event_kinds"]:
        if row.get("status") != "active":
            continue
        ref = row.get("payload_schema_ref", "")
        marker = "event-payload.schema.json#/$defs/"
        if marker not in ref:
            continue
        payload_def = ref.rsplit("/", 1)[-1]
        value = defs.get(payload_def, {}).get("properties", {}).get("value")
        if value == {}:
            actual.add((row["event_kind"], payload_def))

    declared: set[tuple[str, str]] = set()
    errors: list[str] = []
    for row in registry.get("exceptions", []):
        pair = (row.get("event_kind"), row.get("payload_def"))
        if not all(isinstance(value, str) and value for value in pair):
            errors.append(f"invalid exception identity: {row!r}")
            continue
        if pair in declared:
            errors.append(f"duplicate open-value exception: {pair[0]} -> {pair[1]}")
        declared.add(pair)
        for field in ("selector", "validation_contract", "rationale"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                errors.append(f"{pair[0]} missing {field}")

    for pair in sorted(actual - declared):
        errors.append(f"unregistered open value: {pair[0]} -> {pair[1]}")
    for pair in sorted(declared - actual):
        errors.append(f"stale open-value exception: {pair[0]} -> {pair[1]}")

    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"open-value exception registry clean ({len(actual)} active exceptions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
