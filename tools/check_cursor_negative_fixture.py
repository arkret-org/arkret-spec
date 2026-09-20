#!/usr/bin/env python3
"""Validate the cursor negative fixture's pre-decode size vector.

The production Rust decoder computes its encoded-body ceiling as
``MAX_ENCODED_SIZE.div_ceil(3) * 4`` before attempting base64url decode.
This gate mirrors that formula for the normative 4096-byte cursor body cap and
requires the shipped oversized vector to cross it with syntactically valid
unpadded base64url.
"""

from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "cursor-negative-fixture.json"
PREFIX = "ak:cursor:"
MAX_DECODED_BODY_BYTES = 4096
MAX_ENCODED_BODY_CHARS = ((MAX_DECODED_BODY_BYTES + 2) // 3) * 4
VECTOR_ID = "ak.vector.encoding.reject_invalid_cursor.core.v1"
CASE_ID = "oversized_token"
BASE64URL_RE = re.compile(r"[A-Za-z0-9_-]+")


def validation_errors(document: Any) -> list[str]:
    errors: list[str] = []
    vectors = document.get("vectors") if isinstance(document, dict) else None
    vector = next(
        (
            row
            for row in vectors or []
            if isinstance(row, dict) and row.get("vector_id") == VECTOR_ID
        ),
        None,
    )
    if vector is None:
        return [f"missing vector {VECTOR_ID}"]
    cases = vector.get("cases")
    case = next(
        (
            row
            for row in cases or []
            if isinstance(row, dict) and row.get("name") == CASE_ID
        ),
        None,
    )
    if case is None:
        return [f"missing case {CASE_ID}"]

    token = case.get("input_cursor")
    if not isinstance(token, str) or not token.startswith(PREFIX):
        return [f"{CASE_ID}.input_cursor must start with {PREFIX!r}"]
    encoded = token[len(PREFIX) :]
    if BASE64URL_RE.fullmatch(encoded) is None:
        errors.append(f"{CASE_ID} must use only the unpadded base64url alphabet")
    if len(encoded) <= MAX_ENCODED_BODY_CHARS:
        errors.append(
            f"{CASE_ID} encoded body is {len(encoded)} chars; production pre-decode "
            f"size branch requires > {MAX_ENCODED_BODY_CHARS}"
        )
    try:
        decoded = base64.b64decode(encoded, altchars=b"-_", validate=True)
    except ValueError as error:
        errors.append(f"{CASE_ID} is not valid base64url: {error}")
    else:
        if len(decoded) <= MAX_DECODED_BODY_BYTES:
            errors.append(
                f"{CASE_ID} decodes to {len(decoded)} bytes, not more than "
                f"{MAX_DECODED_BODY_BYTES}"
            )
    if case.get("expected_reason_code") != "invalid_cursor":
        errors.append(f"{CASE_ID} must retain expected_reason_code=invalid_cursor")
    violation = case.get("violation")
    if not isinstance(violation, str) or "before any decode work" not in violation:
        errors.append(f"{CASE_ID} must retain the pre-decode rejection contract")
    return errors


def main() -> int:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    errors = validation_errors(document)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    encoded_len = len(document["vectors"][0]["cases"][0]["input_cursor"]) - len(PREFIX)
    print(
        "cursor negative oversized vector: "
        f"PASS ({encoded_len} valid base64url chars > {MAX_ENCODED_BODY_CHARS} pre-decode cap)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
