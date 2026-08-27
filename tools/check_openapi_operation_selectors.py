#!/usr/bin/env python3
"""Materialize and verify the conditional Arkret-Operation OpenAPI header.

OpenAPI ``operationId`` identifies a stable, unversioned endpoint family.
The operation catalog remains the source of exact versioned contracts.  This
tool projects every family member into an optional request header schema; the
runtime requires that header only when authenticated endpoint context leaves
more than one exact versioned operation_id candidate.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = ROOT / "spec/v1/artifacts/openapi/arkret-service-api.openapi.yaml"
REGISTRY = ROOT / "spec/v1/artifacts/registry/contract-registry.json"
OPERATION_ID = re.compile(r"^      operationId: (ak\.[a-z0-9_.]+)$")
VERSIONED_OPERATION_ID = re.compile(r"^(ak\.[a-z0-9_.]+)\.v([1-9][0-9]*)$")
METHOD = re.compile(r"^    (get|post|put|delete|patch|head|options|query|trace):$")


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


def operation_candidates() -> dict[str, list[str]]:
    document = json.loads(REGISTRY.read_text(encoding="utf-8"))
    result: dict[str, list[str]] = {}
    for row in document["operation_registry"]["operations"]:
        operation_id = row["operation_id"]
        match = VERSIONED_OPERATION_ID.fullmatch(operation_id)
        if match is None:
            raise SystemExit(f"versioned operation_id required: {operation_id}")
        result.setdefault(match.group(1), []).append(operation_id)
    return {endpoint_id: sorted(set(ids)) for endpoint_id, ids in result.items()}


def selector_lines(candidates: list[str]) -> list[str]:
    lines = [
        "      - name: Arkret-Operation",
        "        in: header",
        "        required: false",
        "        description: Exact operation_id selector; required only when endpoint context cannot select one version.",
        "        schema:",
        "          type: string",
    ]
    if len(candidates) == 1:
        lines.append(f"          const: {candidates[0]}")
    else:
        lines.append("          enum:")
        lines.extend(f"          - {candidate}" for candidate in candidates)
    return lines


def header_end(lines: list[str], start: int, operation_end: int) -> int:
    index = start + 1
    while index < operation_end:
        line = lines[index]
        if line.startswith("      - ") or (line.startswith("      ") and not line.startswith("        ")):
            break
        index += 1
    return index


def expected_text() -> str:
    lines = OPENAPI.read_text(encoding="utf-8").splitlines()
    candidates_by_endpoint = operation_candidates()
    ranges = operation_ranges(lines)
    for operation_index, end, endpoint_id in reversed(ranges):
        candidates = candidates_by_endpoint.get(endpoint_id)
        if not candidates:
            raise SystemExit(f"OpenAPI endpoint identity is not backed by a registered operation: {endpoint_id}")
        block = lines[operation_index:end]
        header_index = next(
            (index for index in range(operation_index + 1, end) if lines[index] == "      - name: Arkret-Operation"),
            None,
        )
        if header_index is not None:
            existing_end = header_end(lines, header_index, end)
            lines[header_index:existing_end] = selector_lines(candidates)
            continue
        parameters_index = next(
            (index for index in range(operation_index + 1, end) if lines[index] == "      parameters:"),
            None,
        )
        if parameters_index is None:
            insertion = ["      parameters:", *selector_lines(candidates)]
            lines[operation_index + 1 : operation_index + 1] = insertion
        else:
            lines[parameters_index + 1 : parameters_index + 1] = selector_lines(candidates)
    return "\n".join(lines) + "\n"


def validate(text: str) -> list[str]:
    lines = text.splitlines()
    candidates_by_endpoint = operation_candidates()
    errors: list[str] = []
    for operation_index, end, endpoint_id in operation_ranges(lines):
        block = lines[operation_index:end]
        header_indexes = [
            index for index, line in enumerate(block) if line == "      - name: Arkret-Operation"
        ]
        if len(header_indexes) != 1:
            errors.append(f"{endpoint_id}: expected exactly one Arkret-Operation header")
            continue
        header_start = operation_index + header_indexes[0]
        header = lines[header_start:header_end(lines, header_start, end)]
        if "        required: false" not in header:
            errors.append(f"{endpoint_id}: Arkret-Operation must be optional in static OpenAPI")
        candidates = candidates_by_endpoint.get(endpoint_id, [])
        expected = selector_lines(candidates)
        if header != expected:
            errors.append(f"{endpoint_id}: Arkret-Operation schema must enumerate its exact operation_id versions")
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
