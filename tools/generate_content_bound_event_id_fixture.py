#!/usr/bin/env python3
"""Validate the deterministic suite-tagged Event-ID known-answer fixture."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec/v1/artifacts/fixtures/content-bound-event-id-fixture.json"


def derive(suite_code: int, digest_hex: str) -> tuple[str, str]:
    digest = bytes.fromhex(digest_hex)
    if len(digest) != 32 or not 0 < suite_code < 0xF0:
        raise ValueError("v1 Event ID requires an assigned suite code and 32-byte digest")
    body = bytes((suite_code,)) + digest
    token = base64.urlsafe_b64encode(body).rstrip(b"=").decode("ascii")
    assert len(body) == 33 and len(token) == 44
    return body.hex(), "ak:event:" + token


def main() -> int:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    errors: list[str] = []
    expected_layout = {
        "decoded_length_bytes": 33,
        "suite_code_offset": 0,
        "digest_offset": 1,
        "digest_length_bytes": 32,
        "base64url_suffix_length": 44,
        "typed_event_id_length": 53,
        "lexical_pattern": r"^ak:event:[A-Za-z0-9_-]{44}$",
        "canonical_reencode_required": True,
    }
    if data.get("layout") != expected_layout:
        errors.append("Event-ID layout metadata mismatch")
    for case in data["cases"]:
        digest_wire = case.get("event_digest")
        suite_code = case.get("suite_wire_code")
        if not isinstance(digest_wire, str) or not isinstance(suite_code, int):
            continue
        _, digest_hex = digest_wire.split(":", 1)
        if "digest_preimage_canonical_bytes_utf8" in case and digest_wire.startswith("sha256:"):
            actual = hashlib.sha256(case["digest_preimage_canonical_bytes_utf8"].encode("utf-8")).hexdigest()
            if actual != digest_hex:
                errors.append(f"{case['name']}: SHA-256 preimage mismatch")
        body_hex, event_id = derive(suite_code, digest_hex)
        if case.get("event_id_bytes_hex") != body_hex:
            errors.append(f"{case['name']}: body bytes mismatch")
        if case.get("derived_event_id") != event_id:
            errors.append(f"{case['name']}: derived Event ID mismatch")
        derived_object_id = case.get("derived_object_id")
        if isinstance(derived_object_id, str) and derived_object_id.split(":", 2)[2] != event_id.split(":", 2)[2]:
            errors.append(f"{case['name']}: retyped object token mismatch")
        derived_realm_id = case.get("derived_realm_id")
        if isinstance(derived_realm_id, str) and derived_realm_id.split(":", 2)[2] != event_id.split(":", 2)[2]:
            errors.append(f"{case['name']}: retyped Realm token mismatch")
    required_negative_cases = {
        "suite_code_mismatch_rejected",
        "invalid_zero_suite_code_rejected",
        "reserved_suite_code_rejected",
        "unknown_suite_code_rejected",
        "padding_rejected",
        "wrong_decoded_length_rejected",
        "same_event_id_different_canonical_bytes_is_hash_collision",
    }
    names = {case.get("name") for case in data["cases"]}
    for missing in sorted(required_negative_cases - names):
        errors.append(f"missing negative case: {missing}")
    for error in errors:
        print(error)
    if errors:
        return 1
    print("suite-tagged Event-ID fixture: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
