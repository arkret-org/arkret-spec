#!/usr/bin/env python3
"""Execute external Event payload validator profiles and their known-answer cases."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, SchemaError


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
CONTRACTS = ARTIFACTS / "registry" / "contract-registry.json"
PAYLOAD_SCHEMA = ARTIFACTS / "schemas" / "event-payload.schema.json"
PROFILES = ARTIFACTS / "registry" / "payload-validator-profile-registry.json"
SCHEMA_ID_RE = re.compile(r"^ak\.schema\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\.v[0-9]+$")
JSON_SCHEMA_2020_12 = "https://json-schema.org/draft/2020-12/schema"
PROFILE_ID = "ak.validator.json_schema_2020_12_definition.v1"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schema_definition(payload: Any) -> bool:
    if not isinstance(payload, dict) or set(payload) != {"value"}:
        return False
    document = payload.get("value")
    if not isinstance(document, dict):
        return False
    if document.get("$schema") != JSON_SCHEMA_2020_12:
        return False
    if not isinstance(document.get("$id"), str) or SCHEMA_ID_RE.fullmatch(document["$id"]) is None:
        return False
    try:
        Draft202012Validator.check_schema(document)
    except SchemaError:
        return False
    return True


def main() -> int:
    errors: list[str] = []
    contracts = load(CONTRACTS)
    defs = load(PAYLOAD_SCHEMA)["$defs"]
    registry = load(PROFILES)
    if registry.get("known_uncovered_aliases") != []:
        errors.append("retired validator aliases MUST NOT remain in the active registry")
    profiles = registry.get("profiles")
    if not isinstance(profiles, list) or len(profiles) != 1:
        errors.append("payload validator registry MUST contain exactly the schema-definition profile")
        profiles = []

    expected_profile = {
        "event_kind": "ak.schema.define",
        "payload_def": "schema_define_state_payload",
        "validator_profile_id": PROFILE_ID,
        "selector_pointer": "/value/$id",
        "document_pointer": "/value",
        "meta_schema_uri": JSON_SCHEMA_2020_12,
        "document_id_pointer": "/$id",
        "document_id_must_equal_selector": False,
        "unknown_schema_id_behavior": "validate_and_define",
        "failure_code": "schema_violation",
        "fixture_ref": "fixtures/schema-definition-validator-kat.json",
    }
    if profiles and profiles[0] != expected_profile:
        errors.append("schema-definition validator profile does not match the executable contract")

    active = {
        row["event_kind"]: row
        for row in contracts["event_kind_registry"]["event_kinds"]
        if row.get("status") == "active"
    }
    schema_define = active.get("ak.schema.define", {})
    if schema_define.get("payload_schema_ref") != (
        "schemas/event-payload.schema.json#/$defs/schema_define_state_payload"
    ):
        errors.append("ak.schema.define is not bound to schema_define_state_payload")

    payload_def = defs.get("schema_define_state_payload", {})
    if set(payload_def.get("required", [])) != {"value"}:
        errors.append("schema_define_state_payload MUST require value only")
    if payload_def.get("additionalProperties") is not False:
        errors.append("schema_define_state_payload wrapper MUST be closed")

    for name, definition in defs.items():
        value = definition.get("properties", {}).get("value")
        if value == {}:
            errors.append(f"empty Event payload value schema remains: {name}")

    if profiles:
        fixture = load(ARTIFACTS / profiles[0]["fixture_ref"])
        if fixture.get("validator_profile_id") != PROFILE_ID:
            errors.append("schema-definition fixture profile id mismatch")
        cases = fixture.get("cases")
        if not isinstance(cases, list) or not cases:
            errors.append("schema-definition fixture has no cases")
        else:
            names: set[str] = set()
            for case in cases:
                name = case.get("name")
                if not isinstance(name, str) or not name or name in names:
                    errors.append(f"invalid or duplicate schema-definition case name: {name!r}")
                    continue
                names.add(name)
                actual = validate_schema_definition(case.get("payload"))
                expected = case.get("expected_valid")
                if not isinstance(expected, bool):
                    errors.append(f"{name}: expected_valid MUST be boolean")
                elif actual != expected:
                    errors.append(f"{name}: expected_valid={expected}, actual={actual}")
                if expected is False and case.get("expected_failure_code") != "schema_violation":
                    errors.append(f"{name}: invalid case MUST expect schema_violation")

            required_cases = {
                "valid_closed_object_schema",
                "previously_unknown_schema_id_is_a_definition_not_a_dispatch_error",
                "missing_document_id",
                "missing_document",
                "invalid_json_schema_keyword_value",
                "unknown_payload_field",
                "wrong_json_schema_dialect",
            }
            for missing in sorted(required_cases - names):
                errors.append(f"missing schema-definition KAT: {missing}")

    if errors:
        for error in errors:
            print(f"payload-validator-profile-check: {error}")
        return 1
    print(
        "payload-validator-profile-check: immutable ak.schema.define profile and "
        f"{len(cases)} KAT cases passed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
