#!/usr/bin/env python3
"""Regenerate the searchable operation/schema index in service-http-binding.md."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "spec/v1/artifacts/registry/contract-registry.json"
DOCUMENT = ROOT / "spec/v1/zh/sync/service-http-binding.md"
BEGIN = "<!-- BEGIN GENERATED OPERATION FIELD TABLE -->"
END = "<!-- END GENERATED OPERATION FIELD TABLE -->"


def escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = [
        "| Operation | HTTP | Required | Optional | Constraints |",
        "| --- | --- | --- | --- | --- |",
    ]
    operations = catalog["operation_registry"]["operations"]
    for operation in sorted(operations, key=lambda row: row["operation_id"]):
        refs = []
        request_ref = operation.get("request_schema_ref")
        response_ref = operation.get("response_schema_ref")
        if request_ref:
            refs.append(f"request_schema_ref={request_ref}")
        if response_ref:
            refs.append(f"response_schema_ref={response_ref}")
        constraints = "; ".join(refs) if refs else "registry-declared non-JSON or shared binding"
        rows.append(
            f"| `{escape(operation['operation_id'])}` | `{escape(operation.get('http', '-'))}` | - | - | {escape(constraints)} |"
        )
    generated = BEGIN + "\n" + "\n".join(rows) + "\n" + END
    text = DOCUMENT.read_text(encoding="utf-8")
    prefix, remainder = text.split(BEGIN, 1)
    _, suffix = remainder.split(END, 1)
    DOCUMENT.write_text(prefix + generated + suffix, encoding="utf-8", newline="\n")
    print(f"updated {DOCUMENT.relative_to(ROOT).as_posix()} ({len(operations)} operations)")


if __name__ == "__main__":
    main()
