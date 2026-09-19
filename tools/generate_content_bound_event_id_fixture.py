#!/usr/bin/env python3
"""Validate the deterministic suite-tagged Event-ID known-answer fixture."""

from __future__ import annotations

import base64
import copy
import functools
import hashlib
import json
import textwrap
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec/v1/artifacts"
SCHEMAS = ARTIFACTS / "schemas"
FIXTURE = ARTIFACTS / "fixtures/content-bound-event-id-fixture.json"

# zh/conformance/encoding.md 5 and 6.0.2(a): the Event digest preimage is the
# signed Event body, which is the envelope with these three members deleted.
# Everything else about the envelope still holds, so a preimage that the closed
# envelope schema rejects is not a preimage any implementation can produce.
PREIMAGE_RELAXED_ENVELOPE_MEMBERS = ("event_id", "proofs", "unsigned")
PREIMAGE_ENVELOPE_SCHEMA_ID = (
    "https://arkret.org/v1/schemas/event-envelope-preimage.internal.json"
)


@functools.cache
def schema_registry() -> Registry:
    resources = []
    for path in sorted(SCHEMAS.glob("*.schema.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        schema_id = document.get("$id")
        if isinstance(schema_id, str):
            resources.append((schema_id, Resource.from_contents(document)))
    return Registry().with_resources(resources)


@functools.cache
def envelope_validator() -> Draft202012Validator:
    document = json.loads((SCHEMAS / "event-envelope.schema.json").read_text(encoding="utf-8"))
    relaxed = copy.deepcopy(document)
    relaxed["required"] = [
        member
        for member in relaxed["required"]
        if member not in PREIMAGE_RELAXED_ENVELOPE_MEMBERS
    ]
    relaxed["$id"] = PREIMAGE_ENVELOPE_SCHEMA_ID
    return Draft202012Validator(relaxed, registry=schema_registry())


@functools.cache
def payload_validators() -> dict[str, Draft202012Validator]:
    registry_path = ARTIFACTS / "registry/contract-registry.json"
    rows = json.loads(registry_path.read_text(encoding="utf-8"))
    validators: dict[str, Draft202012Validator] = {}
    for row in rows["event_kind_registry"]["event_kinds"]:
        kind = row.get("event_kind")
        ref = row.get("payload_schema_ref")
        if not isinstance(kind, str) or not isinstance(ref, str) or not ref:
            continue
        relative, _, pointer = ref.partition("#")
        document = json.loads((ARTIFACTS / relative).read_text(encoding="utf-8"))
        node: Any = document
        for token in pointer.strip("/").split("/"):
            if token:
                node = node[token.replace("~1", "/").replace("~0", "~")]
        if not isinstance(node, dict):
            continue
        # Resolve the payload subschema through the shared registry instead of
        # re-rooting it under the document $id. A promoted subschema keeps its
        # sibling "#/$defs/..." references, and those resolve against the
        # promoted root, so every payload schema that reuses a sibling $def
        # raised PointerToNowhere the moment a case first used that kind.
        validators[kind] = Draft202012Validator(
            {"$ref": document["$id"] + "#" + pointer}, registry=schema_registry()
        )
    return validators


def schema_errors(validator: Draft202012Validator, instance: Any) -> list[str]:
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    return [
        ".".join(["$", *(str(bit) for bit in error.path)])
        + ": "
        + textwrap.shorten(error.message, width=200, placeholder=" ...")
        for error in errors
    ]


def validate_preimage(name: str, preimage: Any) -> list[str]:
    """The hashed bytes must be an Event, not merely bytes that hash correctly."""
    if not isinstance(preimage, dict):
        return [f"{name}: digest preimage is not a JSON object"]
    errors = [
        f"{name}: preimage rejected by the Event envelope: {message}"
        for message in schema_errors(envelope_validator(), preimage)[:3]
    ]
    kind = preimage.get("kind")
    validator = payload_validators().get(kind) if isinstance(kind, str) else None
    if validator is None:
        errors.append(f"{name}: kind {kind!r} has no registered payload_schema_ref")
        return errors
    errors.extend(
        f"{name}: preimage payload rejected by {kind}: {message}"
        for message in schema_errors(validator, preimage.get("payload"))[:3]
    )
    return errors


def derive(suite_code: int, digest_hex: str) -> tuple[str, str]:
    digest = bytes.fromhex(digest_hex)
    if len(digest) != 32 or not 0 < suite_code <= 0x0F:
        raise ValueError("v1 Event ID requires a uint4 suite code and 32-byte digest")
    body = bytes((suite_code,)) + digest
    token = base64.urlsafe_b64encode(body).rstrip(b"=").decode("ascii")
    assert len(body) == 33 and len(token) == 44
    return body.hex(), "ak:event:" + token


def main() -> int:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    errors: list[str] = []
    expected_layout = {
        "decoded_length_bytes": 33,
        "reserved_high_nibble": 0,
        "digest_suite_low_nibble": True,
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
            preimage_bytes = case["digest_preimage_canonical_bytes_utf8"].encode("utf-8")
            actual = hashlib.sha256(preimage_bytes).hexdigest()
            if actual != digest_hex:
                errors.append(f"{case['name']}: SHA-256 preimage mismatch")
            try:
                preimage = json.loads(preimage_bytes)
            except json.JSONDecodeError:
                errors.append(f"{case['name']}: digest preimage is not valid canonical JSON")
            else:
                errors.extend(validate_preimage(case["name"], preimage))
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
        "nonzero_event_reserved_nibble_rejected",
        "reserved_suite_code_rejected",
        "unknown_suite_code_rejected",
        "padding_rejected",
        "wrong_decoded_length_rejected",
        "same_event_id_different_canonical_bytes_is_hash_collision",
    }
    required_constructive_cases = {
        "principal_control_realm_id_is_event_derived_and_nonzero_nibble_rejected",
        "human_pcr_genesis_on_a_second_station_derives_a_distinct_realm_id",
        "human_founding_device_authorize_binds_the_derived_realm",
        "same_account_second_genesis_rejected_by_station_account_uniqueness",
    }
    names = {case.get("name") for case in data["cases"]}
    for missing in sorted(required_negative_cases - names):
        errors.append(f"missing negative case: {missing}")
    for missing in sorted(required_constructive_cases - names):
        errors.append(f"missing constructive case: {missing}")
    single_bit_case = next(
        (case for case in data["cases"] if case.get("name") == "full_digest_single_bit_difference_changes_event_id"),
        None,
    )
    if not isinstance(single_bit_case, dict):
        errors.append("missing positive case: full_digest_single_bit_difference_changes_event_id")
    else:
        try:
            first = base64.urlsafe_b64decode(single_bit_case["first_event_id"].split(":", 2)[2] + "==")
            second = base64.urlsafe_b64decode(single_bit_case["second_event_id"].split(":", 2)[2] + "==")
        except (KeyError, ValueError):
            errors.append("single-bit Event-ID case contains an invalid typed ID")
        else:
            differing_bits = sum((left ^ right).bit_count() for left, right in zip(first, second, strict=True))
            if len(first) != 33 or len(second) != 33 or first[0] != second[0] or differing_bits != 1:
                errors.append("single-bit Event-ID case must differ by exactly one digest bit")
    for error in errors:
        print(error)
    if errors:
        return 1
    print("suite-tagged Event-ID fixture: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
