#!/usr/bin/env python3
"""Recompute the first-device bootstrap digests and closed machine contract."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "spec/v1/artifacts/fixtures/device-bootstrap-fixture.json"
SESSION_FIXTURE_PATH = ROOT / "spec/v1/artifacts/fixtures/session-grant-issuance-fixture.json"
PRINCIPAL_SCHEMA_PATH = ROOT / "spec/v1/artifacts/schemas/principal-operations.schema.json"
AGENT_SCHEMA_PATH = ROOT / "spec/v1/artifacts/schemas/agent-operations.schema.json"
EVENT_SCHEMA_PATH = ROOT / "spec/v1/artifacts/schemas/event-envelope.schema.json"
SERVICE_SCHEMA_PATH = ROOT / "spec/v1/artifacts/schemas/service-operation-dtos.schema.json"
CONTRACT_REGISTRY_PATH = ROOT / "spec/v1/artifacts/registry/contract-registry.json"
PROOF_CONTEXT_REGISTRY_PATH = ROOT / "spec/v1/artifacts/registry/proof-context-registry.json"

EVENT_ID_RE = re.compile(r"^ak:event:[A-Za-z0-9_-]{44}$")
JKT_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def jcs(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_typed(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def b58decode(value: str) -> bytes:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = 0
    for char in value:
        number = number * 58 + alphabet.index(char)
    body = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return b"\0" * (len(value) - len(value.lstrip("1"))) + body


def resolve_session_vectors(fixture: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {row["name"]: row for row in fixture["accepted_vectors"]}
    resolved: dict[str, dict[str, Any]] = {}

    def one(name: str) -> dict[str, Any]:
        if name in resolved:
            return resolved[name]
        row = rows[name]
        value = dict(row.get("issuance_preimage") or one(row["inherits"]))
        value.update(row.get("override", {}))
        for field in row.get("omit", []):
            value.pop(field, None)
        resolved[name] = value
        return value

    for name in rows:
        one(name)
    return resolved


def replace_pointer(value: dict[str, Any], pointer: str, replacement: Any) -> dict[str, Any]:
    result = json.loads(json.dumps(value))
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]
    target: Any = result
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    final = parts[-1]
    if isinstance(target, list):
        target[int(final)] = replacement
    else:
        target[final] = replacement
    return result


def check_documents(
    fixture: dict[str, Any],
    session_fixture: dict[str, Any],
    principal_schema: dict[str, Any],
    agent_schema: dict[str, Any],
    event_schema: dict[str, Any],
    service_schema: dict[str, Any],
    contract_registry: dict[str, Any],
    proof_context_registry: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    founding = fixture.get("founding_batch", {})
    event_ids = founding.get("event_ids")
    if not isinstance(event_ids, list) or len(event_ids) != 2 or len(set(event_ids)) != 2:
        errors.append("founding_event_ids must contain exactly two distinct Event IDs")
        event_ids = []
    elif any(not isinstance(value, str) or not EVENT_ID_RE.fullmatch(value) for value in event_ids):
        errors.append("founding_event_ids must contain Event IDs, never digests")
    value = {"event_ids": event_ids}
    canonical = jcs(value)
    digest_input = "ak.device-bootstrap.founding-batch.v1\n" + canonical
    if founding.get("canonical_value_utf8") != canonical:
        errors.append("founding canonical_value_utf8 mismatch")
    if founding.get("digest_input_utf8") != digest_input:
        errors.append("founding digest_input_utf8 mismatch")
    expected_founding_digest = sha256_typed(digest_input.encode("utf-8"))
    if founding.get("expected_digest") != expected_founding_digest:
        errors.append("founding_batch_digest mismatch")
    for row in founding.get("negative_vectors", []):
        candidate = row.get("event_ids")
        if row.get("must_reject"):
            if isinstance(candidate, list) and len(candidate) == 2 and len(set(candidate)) == 2 and all(
                isinstance(item, str) and EVENT_ID_RE.fullmatch(item) for item in candidate
            ):
                errors.append(f"{row.get('name')}: must_reject vector is schema-admissible")
        elif row.get("must_not_equal_expected"):
            actual = sha256_typed(("ak.device-bootstrap.founding-batch.v1\n" + jcs({"event_ids": candidate})).encode())
            if actual == expected_founding_digest:
                errors.append(f"{row.get('name')}: negative digest equals valid digest")

    device = fixture.get("device_key", {})
    try:
        raw = bytes.fromhex(device["raw_public_key_hex"])
    except Exception:
        raw = b""
        errors.append("raw_public_key_hex is invalid")
    if len(raw) != 32:
        errors.append("device public key must decode to exactly 32 bytes")
    if device.get("expected_digest") != sha256_typed(raw):
        errors.append("device_key_digest mismatch")
    try:
        multibase_raw = b58decode(device["public_key_multibase"][1:])
        if multibase_raw != b"\xed\x01" + raw:
            errors.append("multibase key does not encode Ed25519 multicodec plus raw key")
        encoded_raw = base64.urlsafe_b64decode(device["public_key_base64url"] + "=")
        if encoded_raw != raw:
            errors.append("base64url key does not encode the same raw key")
    except Exception as exc:
        errors.append(f"device key encoding cannot be decoded: {exc}")
    for row in device.get("negative_vectors", []):
        if sha256_typed(row.get("input_utf8", "").encode()) == device.get("expected_digest"):
            errors.append(f"{row.get('name')}: text digest equals raw-key digest")

    holder = fixture.get("holder", {})
    jwk = holder.get("public_jwk")
    canonical_jwk = jcs(jwk)
    if holder.get("canonical_thumbprint_input_utf8") != canonical_jwk:
        errors.append("holder canonical JWK mismatch")
    expected_jkt = b64url(hashlib.sha256(canonical_jwk.encode()).digest())
    if holder.get("expected_jkt") != expected_jkt or holder.get("credential_cnf_jkt") != expected_jkt:
        errors.append("holder_jkt must equal RFC7638 cnf.jkt")
    if not JKT_RE.fullmatch(expected_jkt):
        errors.append("holder_jkt must be 43-character unpadded base64url")

    request = fixture.get("enroll_request", {})
    request_def = agent_schema.get("$defs", {}).get("account_device_enroll_request_body", {})
    if set(request) != set(request_def.get("required", [])) or set(request) - set(request_def.get("properties", {})):
        errors.append("enroll request fixture does not equal the closed required request shape")
    event = request.get("authorize_event_preimage", {})
    event_def = event_schema.get("$defs", {}).get("device_authorize_event_preimage", {})
    if set(event) != set(event_def.get("required", [])) or set(event) - set(event_def.get("properties", {})):
        errors.append("authorize Event fixture does not equal the closed required preimage shape")
    if request.get("device_id") != event.get("payload", {}).get("device_id"):
        errors.append("request device_id does not match Event payload device_id")
    if event.get("kind") != "ak.device.authorize" or event.get("actor_seq") != 1 or event.get("refs") != []:
        errors.append("authorize Event fixed fields drift")
    if len(event.get("prev_refs", [])) != 1 or event.get("prev_refs", [None])[0] != event_ids[0]:
        errors.append("authorize Event predecessor must equal founding realm.create Event ID")
    binding = event.get("payload", {}).get("enrollment_authority_binding", {})
    if binding.get("kind") != "service_attested" or event.get("executed_by") != binding.get("authority_did"):
        errors.append("authorize Event authority binding mismatch")
    if event.get("authorization_ref") != binding.get("authorization_ref"):
        errors.append("authorize Event delegation reference mismatch")
    identity = fixture.get("event_identity", {})
    without_id = {key: value for key, value in event.items() if key != "event_id"}
    canonical_event = jcs(without_id)
    if identity.get("canonical_preimage_utf8") != canonical_event:
        errors.append("authorize Event identity preimage mismatch")
    digest = hashlib.sha256(canonical_event.encode()).digest()
    derived_event_id = "ak:event:" + b64url(bytes([identity.get("suite_wire_code", -1)]) + digest)
    if identity.get("expected_event_id") != derived_event_id or event.get("event_id") != derived_event_id:
        errors.append("authorize Event ID recomputation mismatch")
    if event_ids and event_ids[1] != derived_event_id:
        errors.append("founding_event_ids[1] must equal derived authorize Event ID")

    request_vector = fixture.get("canonical_request", {})
    canonical_request = jcs(request)
    if request_vector.get("derived_digest_fields_removed") != []:
        errors.append("v1 enroll request must declare no derived digest fields")
    if request_vector.get("canonical_request_utf8") != canonical_request:
        errors.append("canonical_request_utf8 mismatch")
    expected_request_digest = sha256_typed(canonical_request.encode())
    if request_vector.get("expected_digest") != expected_request_digest:
        errors.append("canonical_request_digest mismatch")
    for row in request_vector.get("negative_vectors", []):
        try:
            mutated = replace_pointer(request, row["json_pointer"], row["replacement"])
        except Exception as exc:
            errors.append(f"{row.get('name')}: invalid mutation pointer: {exc}")
            continue
        if row.get("must_not_equal_expected"):
            if sha256_typed(jcs(mutated).encode()) == expected_request_digest:
                errors.append(f"{row.get('name')}: mutated request digest equals valid digest")
        if row.get("must_reject_closed_schema"):
            if set(mutated) <= set(request_def.get("properties", {})):
                errors.append(f"{row.get('name')}: closed-schema negative adds no unknown request member")

    transaction = fixture.get("bootstrap_transaction", {})
    schema_states = principal_schema.get("$defs", {}).get("device_bootstrap_transaction_state", {}).get("enum")
    if transaction.get("states") != schema_states or schema_states != ["pending", "accepted", "cancelled", "expired"]:
        errors.append("bootstrap transaction state set/order drift")
    if transaction.get("forbidden_terminal_state") in schema_states:
        errors.append("bootstrap transaction admits forbidden fifth state")

    issue = fixture.get("session_grant_issue_request", {})
    issue_def = service_schema.get("$defs", {}).get("SessionGrantRequestBody", {})
    bootstrap_def = service_schema.get("$defs", {}).get("SessionGrantDeviceBootstrapRequest", {})
    expected_bootstrap_fields = {
        "mode",
        "authorize_event_preimage",
        "founding_event_ids",
        "founding_batch_digest",
    }
    if issue_def.get("properties", {}).get("device_bootstrap_request", {}).get("$ref") != (
        "#/$defs/SessionGrantDeviceBootstrapRequest"
    ):
        errors.append("SessionGrantRequestBody does not own the closed device_bootstrap_request")
    if set(bootstrap_def.get("required", [])) != expected_bootstrap_fields or set(
        bootstrap_def.get("properties", {})
    ) != expected_bootstrap_fields:
        errors.append("SessionGrantDeviceBootstrapRequest closed field set drift")
    bootstrap_request = issue.get("device_bootstrap_request", {})
    if bootstrap_request.get("authorize_event_source") != (
        "#/enroll_request/authorize_event_preimage"
    ):
        errors.append("session-grant issue KAT does not source the exact enroll Event preimage")
    if bootstrap_request.get("founding_event_ids") != event_ids:
        errors.append("session-grant issue founding_event_ids drift from digest KAT")
    if bootstrap_request.get("founding_batch_digest") != expected_founding_digest:
        errors.append("session-grant issue founding_batch_digest drift from digest KAT")
    if issue.get("device_id") != request.get("device_id") or issue.get("principal_id") != event.get("actor_id"):
        errors.append("session-grant issue principal/device binding drifts from enroll request")
    forbidden = set(issue.get("issuer_derived_fields_forbidden", []))
    expected_forbidden = {
        "transaction_id",
        "holder_jkt",
        "canonical_request_digest",
        "device_key_digest",
        "allowed_operation_ids",
        "credential_expires_at",
        "bootstrap_transaction_expires_at",
    }
    if forbidden != expected_forbidden or forbidden & set(bootstrap_def.get("properties", {})):
        errors.append("issuer-derived bootstrap fields are not closed out of the issue request")
    schema_text = jcs(issue_def)
    if (
        issue.get("proof_kind") != "pre_registration_handoff"
        or '"const":"pre_registration_handoff"' not in schema_text
        or '"device_bootstrap_request"' not in schema_text
    ):
        errors.append("pre_registration_handoff/device_bootstrap request XOR is not machine-bound")
    refresh_text = service_schema.get("$defs", {}).get("SessionGrantRefreshRequestBody", {}).get(
        "description", ""
    )
    for required_text in ("device_bootstrap", "accepted", "standard", "supersed"):
        if required_text not in refresh_text:
            errors.append(f"refresh bootstrap-promotion contract missing {required_text}")
    for row in issue.get("negative_vectors", []):
        if row.get("must_reject_closed_schema") and row.get("extra_bootstrap_field") in bootstrap_def.get(
            "properties", {}
        ):
            errors.append(f"{row.get('name')}: issuer-derived field is schema-admissible")
        if row.get("name") == "non_handoff_proof_with_bootstrap_request" and row.get("proof_kind") == (
            "pre_registration_handoff"
        ):
            errors.append("non-handoff bootstrap negative vector does not change proof kind")
        if row.get("must_reject_binding") and not row.get("replace_second_with_first"):
            errors.append(f"{row.get('name')}: binding negative is not executable")

    try:
        bootstrap_preimage = resolve_session_vectors(session_fixture)["device_bootstrap_binding_is_identity_material"]
        bootstrap = bootstrap_preimage["bootstrap_binding"]
        if bootstrap.get("founding_event_ids") != event_ids:
            errors.append("SessionGrant bootstrap founding_event_ids drift from bootstrap KAT")
        if bootstrap.get("founding_batch_digest") != expected_founding_digest:
            errors.append("SessionGrant bootstrap founding_batch_digest drift from bootstrap KAT")
        if bootstrap.get("device_key_digest") != device.get("expected_digest"):
            errors.append("SessionGrant bootstrap device_key_digest drift from bootstrap KAT")
        if bootstrap.get("canonical_request_digest") != expected_request_digest:
            errors.append("SessionGrant bootstrap canonical_request_digest drift from bootstrap KAT")
        if bootstrap.get("holder_jkt") != expected_jkt or bootstrap_preimage.get("cnf", {}).get("jkt") != expected_jkt:
            errors.append("SessionGrant bootstrap holder_jkt/cnf.jkt drift from bootstrap KAT")
    except Exception as exc:
        errors.append(f"cannot resolve SessionGrant bootstrap vector: {exc}")

    fence = fixture.get("decision_fence", {})
    decision_request = fence.get("request", {})
    request_without_digest = fence.get("request_without_digest", {})
    decision_request_def = principal_schema.get("$defs", {}).get("device_bootstrap_decision_request", {})
    if set(decision_request) != set(decision_request_def.get("required", [])) or set(
        decision_request
    ) - set(decision_request_def.get("properties", {})):
        errors.append("decision request fixture does not equal the closed required shape")
    if {key: value for key, value in decision_request.items() if key != "decision_request_digest"} != (
        request_without_digest
    ):
        errors.append("decision request digest omission is not exact")
    canonical_decision_request = jcs(request_without_digest)
    expected_decision_request_digest = sha256_typed(canonical_decision_request.encode("utf-8"))
    if fence.get("canonical_request_utf8") != canonical_decision_request:
        errors.append("decision request canonical bytes mismatch")
    if (
        fence.get("expected_request_digest") != expected_decision_request_digest
        or decision_request.get("decision_request_digest") != expected_decision_request_digest
    ):
        errors.append("decision_request_digest mismatch")
    if decision_request.get("requested_decision") not in {"cancelled", "expired"}:
        errors.append("decision request may only ask for cancelled or expired")
    if decision_request.get("founding_event_ids") != event_ids:
        errors.append("decision request founding Event IDs drift from founding KAT")
    if decision_request.get("founding_batch_digest") != expected_founding_digest:
        errors.append("decision request founding digest drift from founding KAT")
    if decision_request.get("canonical_request_digest") != expected_request_digest:
        errors.append("decision request enrollment digest drift from enrollment KAT")

    receipt_core = fence.get("receipt_core", {})
    canonical_receipt = jcs(receipt_core)
    receipt_digest_input = "ak.device-bootstrap.decision-receipt.v1\n" + canonical_receipt
    expected_receipt_digest = sha256_typed(receipt_digest_input.encode("utf-8"))
    if fence.get("receipt_canonical_utf8") != canonical_receipt:
        errors.append("decision receipt canonical bytes mismatch")
    if fence.get("receipt_digest_input_utf8") != receipt_digest_input:
        errors.append("decision receipt digest input mismatch")
    if fence.get("expected_receipt_digest") != expected_receipt_digest:
        errors.append("decision receipt digest mismatch")
    for field in (
        "account_authority_id",
        "transaction_id",
        "principal_id",
        "device_id",
        "grant_id",
        "canonical_request_digest",
        "founding_event_ids",
        "founding_batch_digest",
        "bootstrap_transaction_expires_at",
    ):
        if receipt_core.get(field) != decision_request.get(field):
            errors.append(f"decision receipt {field} does not bind the request")
    if receipt_core.get("decision") != decision_request.get("requested_decision"):
        errors.append("decision receipt decision does not bind requested_decision")

    proof = fence.get("proof", {})
    proof_binding = fence.get("proof_binding", {})
    expected_binding = {
        "context": "ak.device-bootstrap-decision-receipt-proof-v1",
        "payload_digest": expected_receipt_digest,
        "principal_server_id": receipt_core.get("principal_server_id"),
        "account_authority_id": receipt_core.get("account_authority_id"),
        "transaction_id": receipt_core.get("transaction_id"),
        "verification_method": proof.get("verification_method"),
        "created_at": receipt_core.get("decided_at"),
        "audience": receipt_core.get("account_authority_id"),
    }
    if proof_binding != expected_binding:
        errors.append("decision receipt proof binding fields mismatch")
    canonical_proof_binding = jcs(expected_binding)
    if fence.get("proof_binding_canonical_utf8") != canonical_proof_binding:
        errors.append("decision receipt proof binding canonical bytes mismatch")
    if (
        proof.get("kind") != "detached_jws"
        or proof.get("payload_digest") != expected_receipt_digest
        or proof.get("created_at") != receipt_core.get("decided_at")
        or proof.get("audience") != receipt_core.get("account_authority_id")
        or proof.get("proof_purpose") != "issuer_attestation"
    ):
        errors.append("decision receipt proof envelope does not bind receipt/audience/time")
    receipt_proof_def = principal_schema.get("$defs", {}).get(
        "device_bootstrap_decision_receipt_proof", {}
    )
    if set(proof) != set(receipt_proof_def.get("required", [])) or set(proof) - set(
        receipt_proof_def.get("properties", {})
    ):
        errors.append("decision receipt proof does not equal the closed required schema")
    try:
        protected, empty, signature = proof["jws"].split(".")
        if empty:
            errors.append("decision receipt JWS payload segment must be detached")
        header = json.loads(b64url_decode(protected))
        if header != {"alg": "Ed25519", "kid": proof["verification_method"]}:
            errors.append("decision receipt protected JWS header mismatch")
        public_jwk = fence["receipt_signer"]["public_jwk"]
        if public_jwk.get("kty") != "OKP" or public_jwk.get("crv") != "Ed25519":
            errors.append("decision receipt signing key is not Ed25519")
        key = Ed25519PublicKey.from_public_bytes(b64url_decode(public_jwk["x"]))
        signing_input = (protected + "." + b64url(canonical_proof_binding.encode("utf-8"))).encode("ascii")
        key.verify(b64url_decode(signature), signing_input)
    except (KeyError, ValueError, InvalidSignature, json.JSONDecodeError) as exc:
        errors.append(f"decision receipt detached JWS verification failed: {exc}")

    contexts = {
        row.get("context"): row for row in proof_context_registry.get("contexts", [])
    }
    registered_context = contexts.get("ak.device-bootstrap-decision-receipt-proof-v1", {})
    if registered_context.get("object_family") != "device_bootstrap_decision_receipt" or (
        registered_context.get("binding_fields")
        != [
            "payload_digest",
            "principal_server_id",
            "account_authority_id",
            "transaction_id",
            "verification_method",
            "created_at",
            "audience",
        ]
    ):
        errors.append("decision receipt proof context registry drift")

    races = {row.get("name"): row for row in fence.get("race_vectors", [])}
    if races.get("accepted_before_cancel") != {
        "name": "accepted_before_cancel",
        "winner": "accepted",
        "cancel_replays": "accepted",
        "new_event_writes_after_winner": 0,
    }:
        errors.append("accepted-before-cancel exact replay/zero-write vector drift")
    for name, decision, reason in (
        ("cancel_before_submit", "cancelled", "bootstrap_transaction_cancelled"),
        ("expiry_before_submit", "expired", "bootstrap_transaction_expired"),
    ):
        row = races.get(name, {})
        if (
            row.get("winner") != decision
            or row.get("submit_rejects") != reason
            or row.get("new_event_writes_after_winner") != 0
        ):
            errors.append(f"{name} terminal tombstone vector drift")
    if races.get("network_indeterminate") != {
        "name": "network_indeterminate",
        "coauth_state_after": "pending",
        "coauth_state_writes": 0,
    }:
        errors.append("network-indeterminate must leave Coauth pending with zero writes")
    retention = fence.get("retention", {})
    if retention != {
        "decision_rows_pruned_in_v1": False,
        "canonical_outcome_bytes_retained": True,
        "exact_replay_is_byte_identical": True,
        "different_request_bytes": "bootstrap_decision_conflict",
    }:
        errors.append("decision fence exact replay/tombstone retention vector drift")

    restricted = fence.get("restricted_authorization", {})
    exact_allowlist = [
        "ak.gate.account.command.enroll_device",
        "ak.gate.account.command.cancel_device_bootstrap",
        "ak.self.events.command.submit",
        "ak.self.events.read.resolve",
    ]
    if (
        restricted.get("credential_class") != "device_bootstrap"
        or restricted.get("binding_preserved") is not True
        or restricted.get("allowed_operation_ids") != exact_allowlist
        or restricted.get("initial_batch_event_ids_source") != "#/founding_batch/event_ids"
    ):
        errors.append("DeviceBootstrap restricted authorization vector drift")
    operations = {
        row.get("operation_id"): row
        for row in contract_registry.get("operation_registry", {}).get("operations", [])
        if isinstance(row, dict)
    }
    decision_operation = operations.get("ak.peer.device_bootstrap.command.decide", {})
    if (
        decision_operation.get("http") != "POST /_arkret/peer/device-bootstrap-decisions"
        or decision_operation.get("idempotency_mechanism") != "idempotency_key"
        or decision_operation.get("uncertain_outcome", {}).get("strategy") != "replay_same_operation"
    ):
        errors.append("device-bootstrap decision operation identity/replay contract drift")
    submit_notes = operations.get("ak.self.events.command.submit", {}).get("notes", "")
    for token in ("credential_class", "bootstrap_binding", "four-operation", "founding_batch_digest"):
        if token not in submit_notes:
            errors.append(f"self events restricted bootstrap notes missing {token}")

    return errors


def main() -> int:
    errors = check_documents(
        load_json(FIXTURE_PATH),
        load_json(SESSION_FIXTURE_PATH),
        load_json(PRINCIPAL_SCHEMA_PATH),
        load_json(AGENT_SCHEMA_PATH),
        load_json(EVENT_SCHEMA_PATH),
        load_json(SERVICE_SCHEMA_PATH),
        load_json(CONTRACT_REGISTRY_PATH),
        load_json(PROOF_CONTEXT_REGISTRY_PATH),
    )
    if errors:
        for error in errors:
            print(f"device-bootstrap KAT: {error}")
        return 1
    print("device-bootstrap KAT: digests, Event preimage, issue/promotion, four-state transaction, cross-service decision fence, signed receipt and restricted authorization verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
