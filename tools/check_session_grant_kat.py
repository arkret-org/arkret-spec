#!/usr/bin/env python3
"""Recompute and cross-check the SessionGrant issuer-record KAT.

This checker deliberately lives outside the general artifact lint.  The
SessionGrant token happens to have the same 33-byte length as Event and Realm
tokens, but its first octet is a complete digest-suite wire code, not a Realm
derivation-class/suite nibble pair.
"""

from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
FIXTURE_PATH = ARTIFACTS / "fixtures" / "session-grant-issuance-fixture.json"
CONTRACT_PATH = ARTIFACTS / "registry" / "contract-registry.json"
DIGEST_SUITE_PATH = ARTIFACTS / "registry" / "digest-suite-registry.json"
CLAIMS_SCHEMA_PATH = ARTIFACTS / "schemas" / "service-operation-dtos.schema.json"

GRANT_PREFIX = "ak:session_grant:"
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{44}$")
NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
PRIVATE_JWK_MEMBERS = {"d", "k", "p", "q", "dp", "dq", "qi", "oth"}
VECTOR_OUTPUT_FIELDS = {
    "canonical_preimage_utf8",
    "sha256_digest_hex",
    "suite_wire_code",
    "grant_id",
    "jwt_jti",
}
BINDING_BY_CLASS = {
    "standard": "holder_binding",
    "device_bootstrap": "bootstrap_binding",
    "recovery_restricted": "recovery_binding",
}
BINDING_FIELDS = set(BINDING_BY_CLASS.values())


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _jcs_key(value: str) -> bytes:
    """RFC 8785 sorts property names as UTF-16 code units."""
    return value.encode("utf-16-be", errors="strict")


def jcs_text(value: Any) -> str:
    """Encode the JSON value used by this KAT under the JCS narrowed profile.

    SessionGrant protocol values currently contain strings, booleans, null,
    arrays, objects, and safe JSON integers.  Floats are rejected here instead
    of silently using Python's non-ECMAScript number rendering.
    """

    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        if abs(value) > 9_007_199_254_740_991:
            raise ValueError("JCS integer is outside the interoperable IEEE-754 range")
        return str(value)
    if isinstance(value, float):
        raise ValueError("floating-point values are not supported by this KAT checker")
    if isinstance(value, str):
        # ensure_ascii=False matches JCS string emission; UTF-8 encoding below
        # rejects lone surrogate code points.
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        encoded.encode("utf-8", errors="strict")
        return encoded
    if isinstance(value, list):
        return "[" + ",".join(jcs_text(item) for item in value) + "]"
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("JCS object property names must be strings")
        members = []
        for key in sorted(value, key=_jcs_key):
            members.append(jcs_text(key) + ":" + jcs_text(value[key]))
        return "{" + ",".join(members) + "}"
    raise ValueError(f"unsupported JCS value type: {type(value).__name__}")


def _strict_base64url(value: object, expected_length: int) -> bytes:
    if not isinstance(value, str):
        raise ValueError("must be a string")
    try:
        decoded = base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
    except (ValueError, binascii.Error) as exc:
        raise ValueError("is not valid unpadded Base64URL") from exc
    canonical = base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii")
    if canonical != value:
        raise ValueError("is not canonical unpadded Base64URL")
    if len(decoded) != expected_length:
        raise ValueError(f"must decode to exactly {expected_length} bytes")
    return decoded


def _canonical_public_jwk(value: object) -> tuple[dict[str, Any], str]:
    if not isinstance(value, str):
        raise ValueError("must be a JCS string")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("is not valid JSON") from exc
    if not isinstance(parsed, dict) or not parsed:
        raise ValueError("must parse to a non-empty JWK object")
    private = sorted(PRIVATE_JWK_MEMBERS & set(parsed))
    if private:
        raise ValueError(f"contains private/symmetric JWK member(s): {private}")
    if not isinstance(parsed.get("kty"), str) or not parsed["kty"]:
        raise ValueError("is missing a non-empty kty")
    return parsed, jcs_text(parsed)


def _issuer_contract(contract: dict[str, Any]) -> dict[str, Any]:
    section = contract.get("id_kind_registry")
    if not isinstance(section, dict):
        raise ValueError("contract registry is missing id_kind_registry")
    result = section.get("issuer_record_identity_contract")
    if not isinstance(result, dict):
        raise ValueError("contract registry is missing issuer_record_identity_contract")
    return result


def _suite_from_contract(
    contract: dict[str, Any], digest_registry: dict[str, Any]
) -> dict[str, Any]:
    reference = contract.get("digest_suite_registry_ref")
    if not isinstance(reference, str):
        raise ValueError("issuer contract is missing digest_suite_registry_ref")
    match = re.fullmatch(
        r"registry/digest-suite-registry\.json#/suites/canonical_id=([a-z0-9_.]+)",
        reference,
    )
    if not match:
        raise ValueError("issuer contract has an unsupported digest suite reference")
    suites = digest_registry.get("suites")
    if not isinstance(suites, list):
        raise ValueError("digest suite registry is missing suites")
    matches = [
        row
        for row in suites
        if isinstance(row, dict) and row.get("canonical_id") == match.group(1)
    ]
    if len(matches) != 1:
        raise ValueError(f"digest suite reference resolves to {len(matches)} rows")
    suite = matches[0]
    if suite.get("status") != "active":
        raise ValueError("SessionGrant digest suite must be active")
    if suite.get("canonicalization") != "json_jcs":
        raise ValueError("SessionGrant digest suite must use json_jcs")
    if suite.get("hash_algorithm") != "sha256":
        raise ValueError("SessionGrant v1 digest suite must use sha256")
    if suite.get("digest_length_bytes") != 32:
        raise ValueError("SessionGrant digest suite must produce 32 bytes")
    code = suite.get("wire_code")
    if not isinstance(code, int) or isinstance(code, bool) or not 1 <= code <= 0xEF:
        raise ValueError("SessionGrant digest suite has an invalid uint8 wire_code")
    if code & 0xF0:
        raise ValueError(
            "SessionGrant v1 digest suite wire_code must have a zero high nibble; "
            "the octet is still a full suite code, not a Realm derivation header"
        )
    if contract.get("digest_suite_wire_code") != code:
        raise ValueError("issuer contract digest_suite_wire_code drifts from digest registry")
    return suite


def _contract_field_sets(contract: dict[str, Any]) -> tuple[set[str], set[str]]:
    rows = contract.get("preimage_fields")
    if not isinstance(rows, list) or not rows:
        raise ValueError("issuer contract preimage_fields must be a non-empty array")
    required: set[str] = set()
    optional: set[str] = set()
    for row in rows:
        if not isinstance(row, str) or not row:
            raise ValueError("issuer contract preimage_fields entries must be strings")
        is_optional = row.endswith("?")
        name = row[:-1] if is_optional else row
        if not name or name in required or name in optional:
            raise ValueError(f"duplicate/invalid issuer preimage field {row!r}")
        (optional if is_optional else required).add(name)
    return required, optional


def _claims_closure_errors(
    contract: dict[str, Any], claims_schema: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    required_fields, optional_fields = _contract_field_sets(contract)
    definition = claims_schema.get("$defs", {}).get("SignedSessionGrantClaims")
    if not isinstance(definition, dict):
        return ["claims schema is missing $defs.SignedSessionGrantClaims"]
    properties = definition.get("properties")
    required = definition.get("required")
    if not isinstance(properties, dict) or not isinstance(required, list):
        return ["SignedSessionGrantClaims must declare properties and required"]
    claim_fields = set(properties) - {"kind", "jti"}
    contract_fields = (required_fields | optional_fields) - {"schema"}
    if claim_fields != contract_fields:
        errors.append(
            "preimage/claims closure drift: contract-only="
            f"{sorted(contract_fields - claim_fields)}, claims-only={sorted(claim_fields - contract_fields)}"
        )
    claim_required = set(required) - {"kind", "jti"}
    expected_required = required_fields - {"schema"}
    if claim_required != expected_required:
        errors.append(
            "preimage/claims requiredness drift: contract-only="
            f"{sorted(expected_required - claim_required)}, claims-only={sorted(claim_required - expected_required)}"
        )
    kind = properties.get("kind")
    if not isinstance(kind, dict) or kind.get("const") != "ak.session.grant":
        errors.append("SignedSessionGrantClaims.kind must be fixed to ak.session.grant")
    if definition.get("additionalProperties") is not False:
        errors.append("SignedSessionGrantClaims must be closed with additionalProperties=false")
    return errors


def _resolve_vectors(
    vectors: object, allowed_fields: set[str]
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not isinstance(vectors, list) or not vectors:
        return {}, ["accepted_vectors must be a non-empty array"]
    rows: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(vectors):
        if not isinstance(row, dict):
            errors.append(f"accepted_vectors[{index}] must be an object")
            continue
        name = row.get("name")
        if not isinstance(name, str) or not name:
            errors.append(f"accepted_vectors[{index}].name must be a non-empty string")
            continue
        if name in rows:
            errors.append(f"accepted vector name is duplicated: {name}")
            continue
        rows[name] = row

    resolved: dict[str, dict[str, Any]] = {}
    active: set[str] = set()

    def resolve(name: str) -> dict[str, Any] | None:
        if name in resolved:
            return resolved[name]
        row = rows.get(name)
        if row is None:
            errors.append(f"accepted vector inherits unknown vector {name!r}")
            return None
        if name in active:
            errors.append(f"accepted vector inheritance cycle includes {name}")
            return None
        active.add(name)
        inherited = row.get("inherits")
        own = row.get("issuance_preimage")
        if inherited is None:
            if not isinstance(own, dict):
                errors.append(f"{name}: base vector must declare issuance_preimage")
                value: dict[str, Any] = {}
            else:
                value = copy.deepcopy(own)
        else:
            if not isinstance(inherited, str) or not inherited:
                errors.append(f"{name}.inherits must be a non-empty vector name")
                value = {}
            elif own is not None:
                errors.append(f"{name}: inherited vector must not also declare issuance_preimage")
                value = {}
            else:
                parent = resolve(inherited)
                value = copy.deepcopy(parent) if parent is not None else {}
        override = row.get("override", {})
        omit = row.get("omit", [])
        if not isinstance(override, dict):
            errors.append(f"{name}.override must be an object")
            override = {}
        if not isinstance(omit, list) or any(not isinstance(item, str) for item in omit):
            errors.append(f"{name}.omit must be an array of field names")
            omit = []
        if len(set(omit)) != len(omit):
            errors.append(f"{name}.omit contains duplicate fields")
        overlap = sorted(set(override) & set(omit))
        if overlap:
            errors.append(f"{name}: fields cannot be both overridden and omitted: {overlap}")
        for field, field_value in override.items():
            if field not in allowed_fields:
                errors.append(f"{name}.override names unknown preimage field {field!r}")
            value[field] = copy.deepcopy(field_value)
        for field in omit:
            if field not in allowed_fields:
                errors.append(f"{name}.omit names unknown preimage field {field!r}")
            if field not in value:
                errors.append(f"{name}.omit names absent field {field!r}")
            value.pop(field, None)
        active.remove(name)
        resolved[name] = value
        return value

    for name in rows:
        resolve(name)
    return resolved, errors


def _binding_error(preimage: dict[str, Any]) -> str | None:
    credential_class = preimage.get("credential_class")
    expected = BINDING_BY_CLASS.get(credential_class)
    present = BINDING_FIELDS & set(preimage)
    if expected is None:
        return f"unknown credential_class {credential_class!r}"
    if present != {expected}:
        return f"credential_class {credential_class!r} requires exactly {expected}; found {sorted(present)}"
    return None


def _structural_case_errors(
    fixture: dict[str, Any], resolved: dict[str, dict[str, Any]], allowed_fields: set[str]
) -> list[str]:
    errors: list[str] = []
    cases = fixture.get("tamper_cases")
    if not isinstance(cases, list) or not cases:
        return ["tamper_cases must be a non-empty array"]
    names: set[str] = set()
    for index, case in enumerate(cases):
        ref = f"tamper_cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{ref} must be an object")
            continue
        for field in ("name", "mutate", "expected"):
            if not isinstance(case.get(field), str) or not case[field]:
                errors.append(f"{ref}.{field} must be a non-empty string")
        name = case.get("name")
        if isinstance(name, str):
            if name in names:
                errors.append(f"tamper case name is duplicated: {name}")
            names.add(name)
        base = case.get("base_vector")
        if base is not None and base not in resolved:
            errors.append(f"{ref}.base_vector names unknown accepted vector {base!r}")
        mutate = case.get("mutate")
        if isinstance(mutate, str):
            root = mutate.split(".", 1)[0]
            if root == "session_public_key_member_order_or_whitespace":
                root = "session_public_key"
            if root not in allowed_fields:
                errors.append(f"{ref}.mutate names unknown preimage field/path {mutate!r}")
        if "value_from" in case and not isinstance(case["value_from"], str):
            errors.append(f"{ref}.value_from must be a string")
    return errors


def _negative_binding_case_errors(
    fixture: dict[str, Any], resolved: dict[str, dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    cases = fixture.get("credential_binding_negative_cases")
    if not isinstance(cases, list) or not cases:
        return ["credential_binding_negative_cases must be a non-empty array"]
    for index, case in enumerate(cases):
        ref = f"credential_binding_negative_cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{ref} must be an object")
            continue
        if not all(isinstance(case.get(key), str) and case[key] for key in ("name", "base_vector", "expected")):
            errors.append(f"{ref} must declare non-empty name, base_vector and expected")
            continue
        base = resolved.get(case["base_vector"])
        if base is None:
            errors.append(f"{ref}.base_vector names an unknown accepted vector")
            continue
        candidate = copy.deepcopy(base)
        omit = case.get("omit", [])
        if not isinstance(omit, list) or any(not isinstance(field, str) for field in omit):
            errors.append(f"{ref}.omit must be an array of field names")
            continue
        for field in omit:
            candidate.pop(field, None)
        add = case.get("add_from_vector")
        if add is not None:
            if not isinstance(add, dict) or set(add) != {"field", "vector"}:
                errors.append(f"{ref}.add_from_vector must contain exactly field and vector")
            else:
                source = resolved.get(add.get("vector"))
                field = add.get("field")
                if source is None or not isinstance(field, str) or field not in source:
                    errors.append(f"{ref}.add_from_vector does not resolve to a source field")
                else:
                    candidate[field] = copy.deepcopy(source[field])
        if case.get("expected") != "signed_claims_schema_invalid":
            errors.append(f"{ref}.expected must be signed_claims_schema_invalid")
        if _binding_error(candidate) is None:
            errors.append(f"{ref} does not actually violate the credential binding XOR")
    return errors


def check_documents(
    fixture: dict[str, Any],
    contract_registry: dict[str, Any],
    digest_registry: dict[str, Any],
    claims_schema: dict[str, Any],
) -> list[str]:
    """Return all SessionGrant KAT drift errors for already-loaded documents."""

    errors: list[str] = []
    try:
        contract = _issuer_contract(contract_registry)
        suite = _suite_from_contract(contract, digest_registry)
        required_fields, optional_fields = _contract_field_sets(contract)
    except ValueError as exc:
        return [str(exc)]
    all_fields = required_fields | optional_fields
    errors.extend(_claims_closure_errors(contract, claims_schema))

    id_section = contract_registry.get("id_kind_registry")
    id_rows = id_section.get("id_kinds") if isinstance(id_section, dict) else None
    session_grant_rows = (
        [row for row in id_rows if isinstance(row, dict) and row.get("kind") == "session_grant"]
        if isinstance(id_rows, list)
        else []
    )
    if len(session_grant_rows) != 1:
        errors.append(f"id registry must contain exactly one session_grant row; found {len(session_grant_rows)}")
    else:
        id_row = session_grant_rows[0]
        if id_row.get("id_form") != "suite_tagged_full_digest":
            errors.append(
                "session_grant id_form must be suite_tagged_full_digest, not the Realm nibble-tagged form"
            )
        if id_row.get("identity_authority") != "issuer_record":
            errors.append("session_grant identity_authority must be issuer_record")
        if id_row.get("derivation_contract_ref") != "#/id_kind_registry/issuer_record_identity_contract":
            errors.append("session_grant derivation_contract_ref does not name the issuer-record contract")

    if fixture.get("derivation_contract_ref") != "registry/id-kind-registry.json#/issuer_record_identity_contract":
        errors.append("fixture derivation_contract_ref does not name issuer_record_identity_contract")
    if fixture.get("digest_suite_ref") != contract.get("digest_suite_registry_ref"):
        errors.append("fixture digest_suite_ref drifts from issuer contract")

    canonical_jwk_value = fixture.get("canonical_public_jwk")
    try:
        canonical_jwk, normalized_jwk = _canonical_public_jwk(canonical_jwk_value)
        if normalized_jwk != canonical_jwk_value:
            errors.append("canonical_public_jwk is not its exact JCS encoding")
    except ValueError as exc:
        canonical_jwk, normalized_jwk = {}, ""
        errors.append(f"canonical_public_jwk {exc}")
    equivalents = fixture.get("equivalent_non_canonical_jwk_inputs")
    if not isinstance(equivalents, list) or not equivalents:
        errors.append("equivalent_non_canonical_jwk_inputs must be a non-empty array")
    else:
        for index, value in enumerate(equivalents):
            try:
                parsed, normalized = _canonical_public_jwk(value)
                if parsed != canonical_jwk or normalized != normalized_jwk:
                    errors.append(f"equivalent_non_canonical_jwk_inputs[{index}] does not normalize to canonical_public_jwk")
            except ValueError as exc:
                errors.append(f"equivalent_non_canonical_jwk_inputs[{index}] {exc}")

    resolved, resolution_errors = _resolve_vectors(fixture.get("accepted_vectors"), all_fields)
    errors.extend(resolution_errors)
    rows = {
        row.get("name"): row
        for row in fixture.get("accepted_vectors", [])
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }
    suite_code = suite["wire_code"]
    seen_ids: set[str] = set()
    for name, preimage in resolved.items():
        row = rows[name]
        missing_outputs = sorted(VECTOR_OUTPUT_FIELDS - set(row))
        if missing_outputs:
            errors.append(f"{name}: missing explicit KAT output field(s) {missing_outputs}")
        unknown = sorted(set(preimage) - all_fields)
        missing = sorted(required_fields - set(preimage))
        if unknown:
            errors.append(f"{name}: preimage has unknown field(s) {unknown}")
        if missing:
            errors.append(f"{name}: preimage is missing required field(s) {missing}")
        null_optional = sorted(field for field in optional_fields if preimage.get(field, object()) is None)
        if null_optional:
            errors.append(f"{name}: optional preimage fields must be omitted, not null: {null_optional}")
        if preimage.get("schema") != contract.get("schema"):
            errors.append(f"{name}: preimage schema drifts from issuer contract")
        binding_error = _binding_error(preimage)
        if binding_error:
            errors.append(f"{name}: {binding_error}")
        scopes = preimage.get("scopes")
        if not isinstance(scopes, list) or not scopes or any(not isinstance(scope, str) or not scope for scope in scopes):
            errors.append(f"{name}: scopes must be a non-empty array of non-empty strings")
        elif scopes != sorted(set(scopes), key=lambda scope: scope.encode("utf-8")):
            errors.append(f"{name}: scopes are not byte-wise sorted and unique")
        for field in ("not_before", "expires_at"):
            if not isinstance(preimage.get(field), str) or not TIMESTAMP_RE.fullmatch(preimage[field]):
                errors.append(f"{name}: {field} is not a canonical UTC millisecond timestamp")
        nonce = preimage.get("issuance_nonce")
        if not isinstance(nonce, str) or not NONCE_RE.fullmatch(nonce):
            errors.append(f"{name}: issuance_nonce must be a 43-character Base64URL token")
        else:
            try:
                _strict_base64url(nonce, 32)
            except ValueError as exc:
                errors.append(f"{name}: issuance_nonce {exc}")
        try:
            _, normalized = _canonical_public_jwk(preimage.get("session_public_key"))
            if normalized != preimage.get("session_public_key"):
                errors.append(f"{name}: signed session_public_key is not its exact JCS encoding")
        except ValueError as exc:
            errors.append(f"{name}: session_public_key {exc}")

        try:
            canonical = jcs_text(preimage)
        except ValueError as exc:
            errors.append(f"{name}: cannot JCS-encode preimage: {exc}")
            continue
        if row.get("canonical_preimage_utf8") != canonical:
            errors.append(f"{name}: canonical_preimage_utf8 mismatch")
        digest = hashlib.sha256(canonical.encode("utf-8")).digest()
        if row.get("sha256_digest_hex") != digest.hex():
            errors.append(f"{name}: sha256_digest_hex mismatch")
        if row.get("suite_wire_code") != suite_code:
            errors.append(f"{name}: suite_wire_code does not come from digest-suite registry")
        expected_id = GRANT_PREFIX + base64.urlsafe_b64encode(bytes([suite_code]) + digest).rstrip(b"=").decode("ascii")
        grant_id = row.get("grant_id")
        if grant_id != expected_id:
            errors.append(f"{name}: grant_id mismatch")
        if row.get("jwt_jti") != grant_id:
            errors.append(f"{name}: jwt_jti must equal grant_id")
        if preimage.get("session_id") == grant_id:
            errors.append(f"{name}: session_id must not equal grant_id")
        if isinstance(grant_id, str) and grant_id.startswith(GRANT_PREFIX):
            token = grant_id[len(GRANT_PREFIX) :]
            if not TOKEN_RE.fullmatch(token):
                errors.append(f"{name}: grant_id token must be exactly 44 Base64URL characters")
            else:
                try:
                    decoded = _strict_base64url(token, 33)
                    if decoded[0] != suite_code or decoded[1:] != digest:
                        errors.append(f"{name}: grant_id token is not suite-code || digest")
                except ValueError as exc:
                    errors.append(f"{name}: grant_id token {exc}")
        else:
            errors.append(f"{name}: grant_id has the wrong typed-ID prefix")
        if isinstance(grant_id, str):
            if grant_id in seen_ids:
                errors.append(f"{name}: grant_id duplicates another accepted vector")
            seen_ids.add(grant_id)

        projected_claims = {key: copy.deepcopy(value) for key, value in preimage.items() if key != "schema"}
        projected_claims.update({"kind": "ak.session.grant", "jti": grant_id})
        claim_properties = claims_schema.get("$defs", {}).get("SignedSessionGrantClaims", {}).get("properties", {})
        if set(projected_claims) - set(claim_properties):
            errors.append(f"{name}: resolved preimage cannot project to the closed signed claims schema")

    assertions = fixture.get("jwk_canonicalization")
    if not isinstance(assertions, dict):
        errors.append("jwk_canonicalization must be an object")
    else:
        if assertions.get("all_inputs_parse_to_same_public_jwk") is not True:
            errors.append("jwk_canonicalization must assert equivalent parsed public JWKs")
        if assertions.get("all_inputs_normalize_to") != normalized_jwk:
            errors.append("jwk_canonicalization.all_inputs_normalize_to mismatch")
        base_name = next(iter(resolved), None)
        base_id = rows.get(base_name, {}).get("grant_id") if base_name else None
        if assertions.get("all_inputs_produce_grant_id") != base_id:
            errors.append("jwk_canonicalization.all_inputs_produce_grant_id mismatch")
        if assertions.get("signed_claim_must_equal_canonical_string") is not True:
            errors.append("jwk_canonicalization must require the canonical signed claim string")

    errors.extend(_structural_case_errors(fixture, resolved, all_fields))
    errors.extend(_negative_binding_case_errors(fixture, resolved))
    return errors


def check_repository() -> list[str]:
    return check_documents(
        load_json(FIXTURE_PATH),
        load_json(CONTRACT_PATH),
        load_json(DIGEST_SUITE_PATH),
        load_json(CLAIMS_SCHEMA_PATH),
    )


def main() -> int:
    try:
        errors = check_repository()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"session-grant KAT checker failed to load inputs: {exc}", file=sys.stderr)
        return 1
    for error in errors:
        print(f"session-grant KAT: {error}", file=sys.stderr)
    if errors:
        print(f"session-grant KAT: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("session-grant KAT: accepted vectors and contract closure verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
