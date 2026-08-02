#!/usr/bin/env python3
"""Generate the operation DTO string-field classification report.

The operation catalog is intentionally fragment-oriented, so this audit walks
every `$defs` object in operation schema documents. Protocol discriminators
must not silently regress to unconstrained strings:

* closed status/schema/reason sets are enums or consts;
* open status tokens are syntactically validated;
* open reason codes use the shared lower-snake-case, 64-byte profile;
* human-readable reasons remain bounded or non-empty free text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "spec" / "v1" / "artifacts" / "schemas"
REPORT = (
    ROOT
    / "spec"
    / "v1"
    / "artifacts"
    / "reports"
    / "operation-string-field-classification.json"
)
REASON_CODE_PATTERN = "^[a-z][a-z0-9_]{0,63}$"
AUDITED_FIELDS = ("schema", "status", "reason_code", "reason")


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def resolve_pointer(document: Any, reference: str) -> Any:
    if not reference.startswith("#"):
        return None
    node = document
    for token in reference.lstrip("#/").split("/"):
        if not token:
            continue
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or token not in node:
            return None
        node = node[token]
    return node


def effective_constraints(document: dict[str, Any], node: Any) -> dict[str, Any]:
    if not isinstance(node, dict):
        return {}
    result: dict[str, Any] = {}
    reference = node.get("$ref")
    if isinstance(reference, str):
        target = resolve_pointer(document, reference)
        if isinstance(target, dict):
            result.update(effective_constraints(document, target))
    result.update({key: value for key, value in node.items() if key != "$ref"})
    return result


def classify(field: str, constraints: dict[str, Any]) -> tuple[str | None, str]:
    if "const" in constraints:
        return "closed_literal", "JSON Schema const"
    if isinstance(constraints.get("enum"), list):
        return "closed_enum", "JSON Schema enum"

    if field == "reason_code":
        if constraints.get("pattern") != REASON_CODE_PATTERN:
            return None, "open reason_code lacks the canonical syntax profile"
        return "validated_open_reason_code", REASON_CODE_PATTERN

    if field == "reason":
        if not any(key in constraints for key in ("minLength", "maxLength", "pattern", "format")):
            return None, "free-text reason lacks a string boundary"
        return "bounded_free_text", "human-readable text with schema boundary"

    if field in {"schema", "status"}:
        if not any(key in constraints for key in ("minLength", "maxLength", "pattern", "format")):
            return None, f"open {field} lacks a syntax or length boundary"
        return "validated_open_token", "open protocol token with schema boundary"

    return None, "unknown audited field"


def build_report() -> dict[str, Any]:
    paths = sorted(SCHEMAS.glob("*operations.schema.json"))
    paths.append(SCHEMAS / "service-operation-dtos.schema.json")
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    counts: dict[str, int] = {}

    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        for shape, node in sorted((document.get("$defs") or {}).items()):
            if not isinstance(node, dict) or not isinstance(node.get("properties"), dict):
                continue
            for field in AUDITED_FIELDS:
                if field not in node["properties"]:
                    continue
                constraints = effective_constraints(document, node["properties"][field])
                classification, basis = classify(field, constraints)
                target = f"{path.name}#/$defs/{shape}/properties/{field}"
                row = {
                    "schema_file": path.name,
                    "shape": shape,
                    "field": field,
                    "pointer": f"#/$defs/{shape}/properties/{field}",
                    "classification": classification or "unclassified",
                    "basis": basis,
                }
                rows.append(row)
                if classification is None:
                    errors.append(f"{target}: {basis}")
                else:
                    counts[classification] = counts.get(classification, 0) + 1

    rows.sort(key=lambda row: (row["schema_file"], row["pointer"]))
    return {
        "schema": "arkret.operation-string-field-classification.v1",
        "source_of_truth": False,
        "generated_by": "tools/gen_operation_string_field_classification.py",
        "generated_from": [
            "spec/v1/artifacts/schemas/*operations.schema.json",
            "spec/v1/artifacts/schemas/service-operation-dtos.schema.json",
        ],
        "description": (
            "Exhaustive classification of operation DTO schema/status/reason_code/reason "
            "properties into closed literals/enums, validated open protocol tokens, or "
            "bounded human-readable text. Any unconstrained audited string fails generation."
        ),
        "summary": {
            "total_fields": len(rows),
            "by_classification": dict(sorted(counts.items())),
            "unclassified": len(errors),
        },
        "errors": errors,
        "fields": rows,
    }


def expected_text() -> str:
    report = build_report()
    if report["errors"]:
        for error in report["errors"]:
            print(error, file=sys.stderr)
        raise SystemExit(1)
    return dump_json(report)


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "generate"
    expected = expected_text()
    if mode == "check":
        if not REPORT.exists() or REPORT.read_text(encoding="utf-8") != expected:
            print(
                "operation string-field classification drift "
                "(run python tools/gen_operation_string_field_classification.py)",
                file=sys.stderr,
            )
            return 1
        print("operation string-field classification: clean")
        return 0
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(expected, encoding="utf-8", newline="\n")
    print(f"updated {REPORT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
