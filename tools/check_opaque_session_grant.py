"""Recompute opaque credentials and execute issuer-ledger conformance cases."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from referencing import Registry, Resource

from tools.session_grant_reference import (
    GrantError, IssuerLedger, ath, canonical_public_jwk, credential_digest,
    grant_ref, jcs_text, secret_from_random, sign_dpop, strict_base64url,
    validate_metadata, verify_dpop,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec/v1/artifacts"
FIXTURE_PATH = ARTIFACTS / "fixtures/session-grant-issuance-fixture.json"
CONTRACT_PATH = ARTIFACTS / "registry/contract-registry.json"
CLAIMS_SCHEMA_PATH = ARTIFACTS / "schemas/service-operation-dtos.schema.json"
COMMON_IDS_PATH = ARTIFACTS / "schemas/common-ids.schema.json"
REQUIRED_CASES = {
    "issue_response_loss_restart_exact_replay", "same_identity_different_intent",
    "replay_revalidates_current_holder", "replay_after_expiry", "replay_after_revoke",
    "refresh_response_loss_restart_exact_replay", "refresh_changed_intent_cannot_fork",
    "recovery_cannot_refresh", "cross_issuer_same_id_isolated", "cross_audience_rejected",
    "known_request_result_gc_fails_closed", "superseded_credential_not_normal_authority",
}
REQUIRED_METADATA = {
    "id", "issuer_id", "account_id", "audience_id", "scopes", "not_before", "expires_at",
    "session_id", "session_public_key", "cnf_jkt", "credential_class", "holder_binding",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validator(definition: str, metadata_schema: dict[str, Any], common_ids: dict[str, Any]) -> jsonschema.Draft202012Validator:
    resources = {
        path.resolve().as_uri(): Resource.from_contents(load_json(path))
        for path in (ARTIFACTS / "schemas").glob("*.schema.json")
    }
    resources[CLAIMS_SCHEMA_PATH.resolve().as_uri()] = Resource.from_contents(metadata_schema)
    resources[COMMON_IDS_PATH.resolve().as_uri()] = Resource.from_contents(common_ids)
    registry = Registry().with_resources(resources.items())
    source, fragment = definition.split("#", 1)
    return jsonschema.Draft202012Validator({"$ref": (ARTIFACTS / source).resolve().as_uri() + "#" + fragment}, registry=registry)


def _contract_errors(registry: dict[str, Any], schema: dict[str, Any], common: dict[str, Any]) -> list[str]:
    errors = []
    section = registry.get("id_kind_registry", {})
    contract = section.get("issuer_record_identity_contract", {})
    expected = {
        "id_form": "issuer_allocated", "identity_authority": "issuer_record",
        "record_identity_fields": ["issuer_id", "id"], "secret_bytes": 32,
        "secret_encoding": "base64url_no_padding",
        "secret_schema_ref": "schemas/common-ids.schema.json#/$defs/session_grant_secret",
        "reference_schema_ref": "schemas/common-ids.schema.json#/$defs/session_grant_ref",
        "metadata_schema_ref": "schemas/service-operation-dtos.schema.json#/$defs/SessionGrantMetadata",
    }
    for name, value in expected.items():
        if contract.get(name) != value:
            errors.append(f"issuer contract {name} must be {value!r}")
    for name in ("preimage_fields", "digest_suite_wire_code", "digest_suite_registry_ref"):
        if name in contract:
            errors.append(f"retired issuer derivation field remains: {name}")
    rows = [row for row in section.get("id_kinds", []) if row.get("kind") == "session_grant"]
    if len(rows) != 1 or rows[0].get("id_form") != "issuer_allocated" or rows[0].get("identity_authority") != "issuer_record":
        errors.append("session_grant row must have one issuer-allocated issuer-record identity")
    defs = schema.get("$defs", {})
    if "SignedSessionGrantClaims" in defs:
        errors.append("retired SignedSessionGrantClaims remains reachable")
    metadata = defs.get("SessionGrantMetadata", {})
    if not REQUIRED_METADATA <= set(metadata.get("required", [])):
        errors.append("SessionGrantMetadata omits required authority material")
    if metadata.get("additionalProperties") is not False:
        errors.append("SessionGrantMetadata must be closed")
    if {"jti", "issuance_nonce", "kind"} & set(metadata.get("properties", {})):
        errors.append("SessionGrantMetadata carries retired credential claims")
    reference = common.get("$defs", {}).get("session_grant_ref", {})
    if set(reference.get("required", [])) != {"issuer_id", "id"} or reference.get("additionalProperties") is not False:
        errors.append("portable SessionGrantRef must close issuer_id and id")
    return errors


def run_ledger_cases(fixture: dict[str, Any]) -> list[str]:
    errors = []
    vectors = {row["name"]: row for row in fixture["accepted_vectors"]}
    cases = fixture.get("ledger_cases")
    if not isinstance(cases, list) or not cases:
        return ["ledger_cases must execute non-empty state transitions"]
    names = [case.get("name") for case in cases if isinstance(case, dict)]
    if len(names) != len(set(names)) or not REQUIRED_CASES <= set(names):
        errors.append("ledger_cases must cover every required replay/refresh/issuer transition once")
    for case in cases:
        ledger = IssuerLedger()
        outcomes: dict[int, dict[str, Any]] = {}
        steps = case.get("steps")
        if not isinstance(steps, list) or not steps:
            errors.append(f"{case.get('name')}: empty steps")
            continue
        for index, step in enumerate(steps):
            label = f"{case.get('name')}[{index}]"
            if step.get("op") == "restart":
                ledger = IssuerLedger.restore(json.loads(json.dumps(ledger.export())))
                continue
            if step.get("op") == "forget_outcome":
                ledger.operations[(step["issuer_id"], "issue", step["request_id"])] = None
                continue
            expected = step.get("expect")
            if not isinstance(expected, str) or not expected:
                errors.append(f"{label}: missing executable expected result")
                continue
            result = None
            try:
                row = vectors[step["vector"]]
                metadata = copy.deepcopy(row["metadata"])
                random_source = lambda size, row=row: bytes.fromhex(row["random_bytes_hex"])
                if step["op"] == "issue":
                    result = ledger.issue(metadata, step["request_id"], step["intent"], step["now"], holder_current=step["holder_current"], random_source=random_source)
                elif step["op"] == "refresh":
                    predecessor = vectors[step["predecessor"]]
                    result = ledger.refresh(predecessor["metadata"]["issuer_id"], predecessor["session_grant"], metadata, step["intent"], step["now"], holder_current=step["holder_current"], random_source=random_source)
                elif step["op"] == "revoke":
                    ledger.revoke(row["session_grant_ref"], caller_current=True)
                elif step["op"] == "introspect":
                    result = ledger.introspect(step.get("issuer_id", metadata["issuer_id"]), row["session_grant"], step.get("audience_id", metadata["audience_id"]), step.get("now", "2026-08-08T12:00:00.000Z"))
                else:
                    raise GrantError("unknown_operation")
                actual = "success"
            except GrantError as exc:
                actual = str(exc)
            except (KeyError, ValueError, TypeError) as exc:
                errors.append(f"{label}: malformed case: {exc}")
                continue
            if actual != expected:
                errors.append(f"{label}: expected {expected}, got {actual}")
            if isinstance(result, dict):
                outcomes[index] = result
            if "same_outcome_as" in step and result != outcomes.get(step["same_outcome_as"]):
                errors.append(f"{label}: replay changed the exact persisted outcome")
            if "expect_records" in step and len(ledger.records) != step["expect_records"]:
                errors.append(f"{label}: unexpected durable record count")
            if "expect_draws" in step and ledger.draws != step["expect_draws"]:
                errors.append(f"{label}: replay consumed fresh randomness")
    return errors


def check_proofs(fixture: dict[str, Any], schema: dict[str, Any], common: dict[str, Any]) -> list[str]:
    errors = []
    row = fixture["dpop_kat"]
    expected = sign_dpop(bytes.fromhex(row["public_test_seed_hex"]), row["session_grant"], row["method"], row["uri"], row["iat"], row["jti"], row["nonce"])
    if row["proof_jwt"] != expected or row["expected_ath"] != ath(row["session_grant"]):
        errors.append("DPoP signing input/signature/ASCII ath KAT drift")
    metadata = fixture["accepted_vectors"][0]["metadata"]
    try:
        verify_dpop(row["proof_jwt"], row["session_grant"], metadata, row["method"], row["uri"], row["iat"], set(), row["nonce"])
    except GrantError as exc:
        errors.append(f"DPoP positive: {exc}")
    possession = fixture["accepted_device_possession"]
    proof = copy.deepcopy(possession["proof"])
    signature = strict_base64url(proof.pop("signature"), 64)
    signing = (proof["context"] + "\n" + jcs_text(proof)).encode()
    if signing.decode() != possession["signing_input_utf8"]:
        errors.append("accepted-device signing input drift")
    expected_digest = "sha256:" + hashlib.sha256(jcs_text(possession["intent"]).encode()).hexdigest()
    if proof["session_intent_digest"] != expected_digest:
        errors.append("accepted-device complete issue intent digest mismatch")
    try:
        Ed25519PublicKey.from_public_bytes(strict_base64url(possession["public_key_b64u"], 32)).verify(signature, signing)
    except InvalidSignature:
        errors.append("accepted-device signature invalid")
    if proof["holder_jkt"] != metadata["cnf_jkt"] or proof["account_id"] != metadata["account_id"]:
        errors.append("accepted-device authority/transport holder mismatch")
    validator_ = validator("schemas/service-operation-dtos.schema.json#/$defs/AcceptedDevicePossessionProof", schema, common)
    errors.extend("accepted-device schema: " + error.message for error in validator_.iter_errors(possession["proof"]))
    return errors


def check_documents(fixture: dict[str, Any], contract_registry: dict[str, Any],
                    metadata_schema: dict[str, Any], common_ids: dict[str, Any]) -> list[str]:
    errors = _contract_errors(contract_registry, metadata_schema, common_ids)
    if fixture.get("identity_contract_ref") != "registry/id-kind-registry.json#/issuer_record_identity_contract":
        errors.append("fixture identity_contract_ref drift")
    if {"derivation_contract_ref", "digest_suite_ref", "jwk_canonicalization"} & set(fixture):
        errors.append("retired issuance preimage/JWT fixture contract remains")
    canonical_jwk = fixture.get("canonical_public_jwk")
    try:
        parsed, canonical = canonical_public_jwk(canonical_jwk)
        if canonical != canonical_jwk:
            errors.append("canonical_public_jwk is not exact JCS")
        inputs = fixture.get("equivalent_non_canonical_jwk_inputs")
        if not isinstance(inputs, list) or len(inputs) < 2:
            errors.append("equivalent public JWK inputs must be exercised")
        else:
            for item in inputs:
                candidate, normalized = canonical_public_jwk(item)
                if candidate != parsed or normalized != canonical:
                    errors.append("equivalent JWK input changes the parsed public key")
    except (GrantError, TypeError) as exc:
        errors.append(f"canonical_public_jwk: {exc}")
    validators = {
        "metadata": validator("schemas/service-operation-dtos.schema.json#/$defs/SessionGrantMetadata", metadata_schema, common_ids),
        "secret": validator("schemas/common-ids.schema.json#/$defs/session_grant_secret", metadata_schema, common_ids),
        "ref": validator("schemas/common-ids.schema.json#/$defs/session_grant_ref", metadata_schema, common_ids),
    }
    rows = fixture.get("accepted_vectors")
    if not isinstance(rows, list) or len(rows) < 4:
        return errors + ["accepted_vectors must exercise independent human/Agent/recovery/issuer records"]
    by_name = {}
    seen_refs = set()
    for row in rows:
        try:
            name = row["name"]
            if name in by_name:
                errors.append(f"duplicate accepted vector {name}")
            by_name[name] = row
            metadata = row["metadata"]
            validate_metadata(metadata)
            secret = secret_from_random(bytes.fromhex(row["random_bytes_hex"]))
            ref = grant_ref(metadata["issuer_id"], metadata["id"])
            expected = {
                "canonical_metadata_utf8": jcs_text(metadata), "session_grant": secret,
                "session_grant_ref": ref, "credential_digest": credential_digest(secret), "dpop_ath": ath(secret),
            }
            for field, value in expected.items():
                if row.get(field) != value:
                    errors.append(f"{name}: {field} mismatch")
            for kind, document in (("metadata", metadata), ("secret", secret), ("ref", ref)):
                errors.extend(f"{name} {kind} schema: {error.message}" for error in validators[kind].iter_errors(document))
            if (metadata["issuer_id"], metadata["id"]) in seen_refs:
                errors.append(f"{name}: duplicate issuer-scoped identity")
            seen_refs.add((metadata["issuer_id"], metadata["id"]))
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"accepted vector invalid: {exc}")
    negatives = fixture.get("credential_binding_negative_cases")
    if not isinstance(negatives, list) or len(negatives) < 6:
        errors.append("credential binding negatives must execute all holder/class closures")
    else:
        for case in negatives:
            try:
                candidate = copy.deepcopy(by_name[case["base_vector"]]["metadata"])
                for field in case.get("omit", []):
                    candidate.pop(field, None)
                candidate.update(copy.deepcopy(case.get("set", {})))
                if validators["metadata"].is_valid(candidate):
                    errors.append(f"{case['name']}: invalid credential binding passed actual schema")
            except (KeyError, TypeError) as exc:
                errors.append(f"malformed binding negative: {exc}")
    errors.extend(run_ledger_cases(fixture))
    errors.extend(check_proofs(fixture, metadata_schema, common_ids))
    return errors
