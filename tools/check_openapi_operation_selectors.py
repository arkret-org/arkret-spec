#!/usr/bin/env python3
"""Materialize and verify the mandatory Arkret-Operation OpenAPI header.

The operation catalog remains the source of operation identities.  This tool
projects each OpenAPI ``operationId`` into an exact, required request header;
it does not create aliases or perform version negotiation.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = ROOT / "spec/v1/artifacts/openapi/arkret-service-api.openapi.yaml"
OPERATION_ID = re.compile(r"^      operationId: (ak\.[a-z0-9_.]+\.v1)$")
METHOD = re.compile(r"^    (get|post|put|delete|patch|head|options|trace):$")


def operation_ranges(lines: list[str]) -> list[tuple[int, int, str]]:
    ranges: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        match = OPERATION_ID.fullmatch(line)
        if not match:
            continue
        start = index
        while start >= 0 and not METHOD.fullmatch(lines[start]):
            start -= 1
        if start < 0:
            raise SystemExit(f"operationId outside an HTTP method at line {index + 1}")
        end = index + 1
        while end < len(lines):
            if METHOD.fullmatch(lines[end]) or re.match(r"^  /", lines[end]):
                break
            end += 1
        ranges.append((index, end, match.group(1)))
    return ranges


def selector_lines(operation_id: str) -> list[str]:
    return [
        "      - name: Arkret-Operation",
        "        in: header",
        "        required: true",
        "        description: Exact versioned operation selector; validated before body parsing.",
        "        schema:",
        "          type: string",
        f"          const: {operation_id}",
    ]


def expected_text() -> str:
    lines = OPENAPI.read_text(encoding="utf-8").splitlines()
    ranges = operation_ranges(lines)
    for operation_index, end, operation_id in reversed(ranges):
        block = lines[operation_index:end]
        if any(line == "      - name: Arkret-Operation" for line in block):
            continue
        parameters_index = next(
            (index for index in range(operation_index + 1, end) if lines[index] == "      parameters:"),
            None,
        )
        if parameters_index is None:
            insertion = ["      parameters:", *selector_lines(operation_id)]
            lines[operation_index + 1 : operation_index + 1] = insertion
        else:
            lines[parameters_index + 1 : parameters_index + 1] = selector_lines(operation_id)
    return "\n".join(lines) + "\n"


def validate(text: str) -> list[str]:
    lines = text.splitlines()
    errors: list[str] = []
    for operation_index, end, operation_id in operation_ranges(lines):
        block = lines[operation_index:end]
        header_indexes = [
            index for index, line in enumerate(block) if line == "      - name: Arkret-Operation"
        ]
        if len(header_indexes) != 1:
            errors.append(f"{operation_id}: expected exactly one Arkret-Operation header")
            continue
        header = block[header_indexes[0] : header_indexes[0] + 7]
        if "        required: true" not in header:
            errors.append(f"{operation_id}: Arkret-Operation must be required")
        if f"          const: {operation_id}" not in header:
            errors.append(f"{operation_id}: Arkret-Operation const must equal operationId")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("generate", "check"))
    args = parser.parse_args()
    expected = expected_text()
    if args.mode == "generate":
        OPENAPI.write_text(expected, encoding="utf-8")
    errors = validate(expected if args.mode == "generate" else OPENAPI.read_text(encoding="utf-8"))
    if args.mode == "check" and OPENAPI.read_text(encoding="utf-8") != expected:
        errors.append("OpenAPI selector projection drift; run this tool in generate mode")
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"OpenAPI operation selectors: ok ({len(operation_ranges(expected.splitlines()))} operations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
