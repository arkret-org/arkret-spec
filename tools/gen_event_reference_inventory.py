#!/usr/bin/env python3
"""Generate the machine-readable inventory of Event reference schema fields."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "spec/v1/artifacts/schemas"
OUTPUT = ROOT / "spec/v1/artifacts/reports/event-reference-field-inventory.json"


def classify(name: str, schema: Any, file_name: str, path: list[str]) -> str:
    if name == "prev_refs":
        return "complete_event_id"
    if name == "event_digest" or name.endswith("_event_digest") or name.endswith("_event_digests"):
        return "digest_copy_or_commitment"
    if file_name == "event-envelope.schema.json" and path == ["$defs", "external_ref"] and name == "event_id":
        return "external_event_namespace"
    if name == "event_id" or name.endswith("_event_id") or name.endswith("_event_ids") or name.endswith("_event_ref") or name.endswith("_event_refs"):
        return "complete_event_id"
    return "event_reference_shape_unclassified"


def walk(value: Any, path: list[str], rows: list[dict[str, str]], file_name: str) -> None:
    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict):
            for name, schema in properties.items():
                serialized = json.dumps(schema, sort_keys=True) if isinstance(schema, dict) else ""
                if name == "prev_refs" or name == "event_id" or name.endswith("_event_id") or name.endswith("_event_ids") or name.endswith("_event_ref") or name.endswith("_event_refs") or name == "event_digest" or name.endswith("_event_digest") or name.endswith("_event_digests"):
                    rows.append({
                        "schema": file_name,
                        "json_pointer": "/" + "/".join(path + ["properties", name]),
                        "field": name,
                        "classification": classify(name, schema, file_name, path),
                    })
        for key, child in value.items():
            walk(child, path + [key.replace("~", "~0").replace("/", "~1")], rows, file_name)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk(child, path + [str(index)], rows, file_name)


def build_inventory() -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    for path in sorted(SCHEMAS.glob("*.json")):
        walk(json.loads(path.read_text(encoding="utf-8")), [], rows, path.name)
    rows.sort(key=lambda row: (row["schema"], row["json_pointer"]))
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    return {
        "version": "2026-08-22",
        "source_of_truth": False,
        "generated_from": ["schemas/*.json"],
        "generated_by": "tools/gen_event_reference_inventory.py",
        "description": "Complete schema-property inventory for Event ID/ref/digest fields. EventId is itself the complete suite-tagged cryptographic identity; no companion-digest wrapper or truncated identity class exists. External protocol event identifiers are classified separately and never enter the Arkret EventId value space.",
        "counts": counts,
        "fields": rows,
    }


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "generate"
    payload = build_inventory()
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if mode == "check":
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
            print(
                f"generated report drift: {OUTPUT.relative_to(ROOT).as_posix()} "
                "(run python tools/artifact_pipeline.py generate)",
                file=sys.stderr,
            )
            return 1
        print(f"event reference inventory clean ({len(payload['fields'])} fields)")
        return 0
    if mode != "generate":
        print(f"unsupported mode: {mode}", file=sys.stderr)
        return 2
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"updated {OUTPUT.relative_to(ROOT).as_posix()} ({len(payload['fields'])} fields)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
