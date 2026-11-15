#!/usr/bin/env python3
"""Regenerate the six detached-object signature byte known-answer cases."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURE = ROOT / "spec/v1/artifacts/fixtures/detached-object-signature-kat-fixture.json"

KEY_A_SEED = bytes(range(32))
KEY_B_SEED = bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc4"
    "4449c5697b326919703bac031cae7f60"
)

REALM_ID = "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5"
EVENT_ID = "ak:event:AQJmSg1s9QyzppFeJL40dN92YVHZeLdBBt3UWHa9XNOD"
COMMIT_ID = "ak:realm_commit:ARNRmzDi2r78zveOLmoHOb6AephFMwVuGE1fwXmCoeo4"


def fixture_content_address(kind: str) -> str:
    """Return a stable suite-0x01 content-address token for a fixture-only ID.

    These KATs pin signature bytes, not the referenced body's digest, so the
    token only has to be a registered wire form: header byte 0x01 (the fixed
    v1 sha256 suite) followed by SHA-256 of a fixed per-kind label.
    """

    body = b"\x01" + hashlib.sha256(f"ak.fixture.detached_object_signature.{kind}.v1".encode("utf-8")).digest()
    return f"ak:{kind}:" + base64.urlsafe_b64encode(body).rstrip(b"=").decode("ascii")


HANDOFF_ID = fixture_content_address("realm_authority_handoff")
SNAPSHOT_ID = fixture_content_address("realm_snapshot")
OLD_SERVICE = "ak:did_core:webvh:z6mkfixturestationa"
NEW_SERVICE = "ak:did_core:webvh:z6mkfixturestationb"
PRODUCER_SERVICE = "ak:did_core:webvh:z6mkfixturealice"
OLD_VM = "did:webvh:z6mkfixturestationa:station-a.example#assertion-fixture"
NEW_VM = "did:webvh:z6mkfixturestationb:station-b.example#assertion-fixture"
PRODUCER_VM = "did:webvh:z6mkfixturealice:alice.example#device-fixture"


def b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def jcs(value: object) -> bytes:
    """RFC 8785 bytes for this fixture's string/integer/boolean/null domain."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def public_key(seed: bytes) -> str:
    return b64u(Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes_raw())


def make_signature(
    context: str,
    unsigned_projection: dict,
    verification_method: str,
    seed: bytes,
) -> tuple[dict, dict]:
    unsigned_bytes = jcs(unsigned_projection)
    signed_digest = "sha256:" + hashlib.sha256(unsigned_bytes).hexdigest()
    envelope = {
        "context": context,
        "signature_algorithm": "Ed25519",
        "verification_method": verification_method,
        "signed_digest": signed_digest,
        "created_at": "2026-09-20T00:00:00.000Z",
    }
    prefix = (context + "\n").encode("utf-8")
    signature_input = prefix + jcs(envelope)
    signature = b64u(Ed25519PrivateKey.from_private_bytes(seed).sign(signature_input))
    carrier = dict(envelope)
    carrier["signature"] = signature
    derived = {
        "unsigned_projection": copy.deepcopy(unsigned_projection),
        "unsigned_jcs_utf8_hex": unsigned_bytes.hex(),
        "expected_signed_digest": signed_digest,
        "signature_envelope_without_sig": envelope,
        "prefix_bytes_hex": prefix.hex(),
        "signature_input_hex": signature_input.hex(),
        "public_key_base64url": public_key(seed),
        "expected_sig": signature,
    }
    return carrier, derived


def authority_basis(
    kind: str,
    coordinate: dict,
    controller_did: str,
    verification_method: str,
    public_key_base64url: str,
    test_key_ref: str,
) -> dict:
    return {
        "basis_kind": kind,
        "coordinate": coordinate,
        "resolved_controller_did": controller_did,
        "authorized_verification_method": verification_method,
        "public_key_base64url": public_key_base64url,
        "test_key_ref": test_key_ref,
    }


OWNER_TRANSFER_CONTEXT = "ak.realm_owner_transfer_acceptance_signature.v1"
OWNER_TRANSFER_PRINCIPAL_DID = json.loads((ROOT / "spec/v1/artifacts/fixtures/resolution-commitment-fixture.json").read_text(encoding="utf-8"))["vectors"][3]["commitment"]["did"]
OWNER_TRANSFER_PRINCIPAL_CORE = "ak:did_core:webvh:" + OWNER_TRANSFER_PRINCIPAL_DID.split(":", 3)[2]
OWNER_TRANSFER_DEVICE = "ak:device:0199bbbb-bbbb-7bbb-8bbb-bbbbbbbbbbbb"
OWNER_TRANSFER_VM = OWNER_TRANSFER_PRINCIPAL_DID + "#" + OWNER_TRANSFER_DEVICE
OWNER_TRANSFER_ACTOR = {"kind": "account", "account_id": {
    "principal_id": OWNER_TRANSFER_PRINCIPAL_CORE, "station_id": "ak:did_core:web:successor-station.example"}}
OWNER_TRANSFER_AUTHOR = {"kind": "account", "account_id": {
    "principal_id": OWNER_TRANSFER_PRINCIPAL_CORE, "station_id": "ak:did_core:web:station.example"}}
OWNER_TRANSFER_AUTHOR_VM = OWNER_TRANSFER_PRINCIPAL_DID + "#ak:device:0199bbbb-bbbb-7bbb-8bbb-bbbbbbbbbbbc"
OWNER_TRANSFER_CASES = [(name, "accept") for name in ("accepted_human", "scope_omitted")] + [
    (name, "reject") for name in (
        "legacy_string", "open_map", "explicit_null", "wrong_context", "wrong_algorithm",
        "changed_actor_resigned_outer", "changed_scope_resigned_outer", "changed_root_resigned_outer",
        "changed_patch_resigned_outer", "author_key_as_acceptance", "wrong_key", "wrong_station",
        "wrong_device", "generation_changed", "revoked_device", "deactivated_account", "left_member",
        "future_device", "expired_device", "acceptance_before_device_window",
        "scope_empty", "scope_unknown", "scope_wildcard", "scope_null", "owned_agent_root",
        "service_root", "realm_actor_root", "stale_root", "returned_controller_new_epoch",
        "counter_overflow", "modified_outer_signature",
    )]


def owner_transfer_intent(event: dict) -> dict:
    return {"scope_ref": copy.deepcopy(event["scope_ref"]), "actor_id": copy.deepcopy(event["actor_id"]),
            "payload_without_successor_acceptance": {key: copy.deepcopy(event["payload"][key])
                 for key in ("realm_id", "expected_state_digest", "patch")}}


def sign_owner_transfer_event(event: dict) -> dict:
    """Reference current-controller signature; all seeds are public KAT material."""
    from tools.regenerate_crypto_signature_fixture import refresh_jws_input
    body = {k: copy.deepcopy(v) for k, v in event.items() if k not in ("event_id", "producer_proof")}
    digest = "sha256:" + hashlib.sha256(jcs(body)).hexdigest()
    binding = {"context": "ak.event_proof.v1", "event_digest": digest, "actor_id": body["actor_id"],
               "verification_method": OWNER_TRANSFER_AUTHOR_VM, "created_at": body["created_at"]}
    signing_input = refresh_jws_input({"protected_header": {"alg": "Ed25519"}}, jcs(binding))
    proof = {"kind": "detached_jws", "verification_method": OWNER_TRANSFER_AUTHOR_VM,
             "event_digest": digest, "created_at": body["created_at"],
             "jws": signing_input.decode().split(".")[0] + ".." + b64u(
                 Ed25519PrivateKey.from_private_bytes(KEY_A_SEED).sign(signing_input))}
    return {**body, "event_id": "ak:event:" + b64u(b"\x01" + hashlib.sha256(jcs(body)).digest()),
            "producer_proof": proof}


def owner_transfer_source_resolution(alternate=False):
    """Typed did:web document-bound evidence; HTTPS authority is a qualified input."""
    did, vm = "did:web:successor-station.example", "did:web:successor-station.example#assertion-1"
    doc = {"did": did, "contexts": ["https://www.w3.org/ns/did/v1"], "controller_dids": [did],
        "also_known_as": [], "verification_methods": [{"verification_method": vm, "controller_did": did,
            "verification_method_suite": "JsonWebKey2020", "public_key_material": {"publicKeyJwk": {
                "kty": "OKP", "crv": "Ed25519", "x": public_key(KEY_A_SEED)}}, "extensions": []}],
        "authentication": [], "assertion_methods": [{"verification_method": vm}],
        "key_agreements": [], "capability_invocations": [], "capability_delegations": [],
        "services": [{"uri": did+"#arkret", "protocol_names": ["ArkretService"],
            "endpoint": "https://successor-station.example/", "extensions": [{"name": "service_kind", "value": "station"}]}],
        "metadata": {}, "extensions": [{"name": "x_fixture_observation", "value": "alternate"}] if alternate else []}
    digest = "sha256:" + hashlib.sha256(jcs(doc)).hexdigest()
    version = "synthetic-jcs-sha256:" + digest[7:]
    return {"service_id": "ak:did_core:web:successor-station.example", "service_kind": "station",
        "method_history_evidence": {"evidence_kind": "did_web_document", "boundary": {
            "from_method_history_head": digest, "to_method_history_head": digest,
            "from_version_id": version, "to_version_id": version}, "evidence": {
                "kind": "ak.did.binding_evidence.v1", "method": "web", "document_digest": digest, "method_proofs": []}},
        "normalized_did_document": doc}


def owner_transfer_source_attestation(source, intent, attested_at="2026-09-20T00:00:00.000Z", expires_at="2026-09-20T00:00:30.000Z"):
    from tools.regenerate_crypto_signature_fixture import refresh_jws_input
    alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    number, encoded = int.from_bytes(b"\xed\x01" + Ed25519PrivateKey.from_private_bytes(KEY_B_SEED).public_key().public_bytes_raw(), 'big'), ''
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded
    core = {"account_id": copy.deepcopy(source["actor_id"]["account_id"]), "device_id": source["device_id"],
        "device_signing_key_did": "did:key:z"+encoded, "hpke_key": b64u(bytes(range(32))),
        "device_authorize_event_id": source["authorization_event_ref"],
        "authorized_generation_ref": source["authorized_generation_ref"], "device_status": "active",
        "attested_at": attested_at, "expires_at": expires_at,
        "authorization_window": {"not_before": source["not_before"], "expires_at": source["expires_at"]},
        "owner_transfer_acceptance_intent_digest": "sha256:" + hashlib.sha256(jcs(intent)).hexdigest()}
    vm = "did:web:successor-station.example#assertion-1"
    binding = {"context": "ak.device_projection_attestation_proof.v1", "payload_digest": "sha256:" + hashlib.sha256(jcs({"attestation":core})).hexdigest()}
    for field in ("account_id", "device_id", "device_signing_key_did", "hpke_key", "device_authorize_event_id",
                  "authorized_generation_ref", "device_status", "attested_at", "expires_at", "owner_transfer_acceptance_intent_digest"):
        binding[field] = core[field]
    binding.update(verification_method=vm,created_at=attested_at)
    signing_input=refresh_jws_input({"protected_header":{"alg":"Ed25519"}},jcs(binding))
    proof={"verification_method":vm,"created_at":attested_at,"jws":signing_input.decode().split('.')[0]+'..'+b64u(Ed25519PrivateKey.from_private_bytes(KEY_A_SEED).sign(signing_input))}
    return {"attestation":core,"proof":proof}


OWNER_TRANSFER_TRANSPORT_CASES = [("original_source", "accept"), ("fresh_source_same_intent", "accept")] + [
    (name, "reject") for name in ("candidate_before_source", "candidate_after_source_expiry", "future_source", "old_source_expired", "fresh_source_expired", "c_row_ref_on_a_wrapper",
        "c_signature_changed", "c_intent_digest_changed", "ordinary_c_row_for_owner", "contact_query", "batch_query")]


def owner_transfer_transport(event, source):
    intent=owner_transfer_intent(event)
    attestation=owner_transfer_source_attestation(source,intent)
    origin_wrapper={"device_projection_attestation":copy.deepcopy(attestation),"service_resolution":owner_transfer_source_resolution()}
    wrapper={"device_projection_attestation":attestation,"service_resolution":owner_transfer_source_resolution(True)}
    fresh={"device_projection_attestation":owner_transfer_source_attestation(source,intent,"2026-09-20T00:00:01.000Z","2026-09-20T00:00:31.000Z"),"service_resolution":owner_transfer_source_resolution(True)}
    ref=lambda value:'ak:signer_evidence:sha256:'+hashlib.sha256(jcs(value)).hexdigest()
    query={"request_id":"ak:request:0199cccc-cccc-7ccc-8ccc-cccccccccccc","requester_account_id":copy.deepcopy(event['actor_id']['account_id']),
        "purpose":"realm_owner_transfer_acceptance","relationship_basis":{"kind":"realm_membership","realm_id":event['realm_id']},
        "device_keys":[{"account_id":copy.deepcopy(source['actor_id']['account_id']),"device_ids":[source['device_id']]}],
        "owner_transfer_acceptance":{"intent":intent,"acceptance":copy.deepcopy(event['payload']['successor_acceptance'])}}
    body=lambda evidence:{"branch":"authority_forward","event_submission":{"event":copy.deepcopy(event)},"successor_device_evidence":copy.deepcopy(evidence)}
    before,after=body(wrapper),body(fresh)
    stable=lambda value:{k:v for k,v in value.items() if k not in ('producer_device_evidence','successor_device_evidence')}
    return {"boundary":"Actual C-signature bytes and typed reference wrappers. did:web HTTPS retrieval/authority and both source document observations are qualified inputs, not native DID history or peer HTTP execution. Primary producer authority is checked separately by the original ingress.",
        "query":query,"origin_wrapper":origin_wrapper,"peer_row_signer_evidence_ref":ref(origin_wrapper),
        "evidence":wrapper,"evidence_ref":ref(wrapper),"fresh_evidence":fresh,"fresh_evidence_ref":ref(fresh),
        "forward_body":before,"fresh_forward_body":after,
        "stable_business_digest":"sha256:"+hashlib.sha256(jcs(stable(before))).hexdigest(),
        "full_http_body_digest":"sha256:"+hashlib.sha256(jcs(before)).hexdigest(),
        "fresh_full_http_body_digest":"sha256:"+hashlib.sha256(jcs(after)).hexdigest(),
        "cases":[{"name":name,"expected_result":result} for name,result in OWNER_TRANSFER_TRANSPORT_CASES],
        "retention_boundary":"archive_input_coordinates are pre-acceptance reference inputs. Native admission must atomically bind the actual resulting Event/RealmCommit and original W1 full wrapper/ref, and handoff its complete opaque management-state set; this KAT does not manufacture a successful native Commit, private archive or handoff.",
        "archive_input_coordinates":{"event_id":event['event_id'],"intent_digest":"sha256:"+hashlib.sha256(jcs(intent)).hexdigest(),
            "successor_proof_digest":"sha256:"+hashlib.sha256(jcs(event['payload']['successor_acceptance'])).hexdigest(),"successor_evidence_ref":ref(wrapper)}}


def owner_transfer_fixture() -> dict:
    root = {"controller_actor_id": copy.deepcopy(OWNER_TRANSFER_AUTHOR), "controller_epoch": 4,
            "authority_generation": "2", "authority_event_ref": EVENT_ID}
    event = {"kind": "ak.realm.owner.transfer", "realm_id": REALM_ID,
             "scope_ref": {"kind": "realm", "realm_id": REALM_ID},
             "actor_id": copy.deepcopy(OWNER_TRANSFER_AUTHOR), "created_at": "2026-09-20T00:00:00.000Z",
             "payload": {"realm_id": REALM_ID, "expected_state_digest": "sha256:" + hashlib.sha256(jcs(root)).hexdigest(),
                         "patch": {"controller_actor_id": copy.deepcopy(OWNER_TRANSFER_ACTOR)}}}
    acceptance, derived = make_signature(OWNER_TRANSFER_CONTEXT, owner_transfer_intent(event), OWNER_TRANSFER_VM, KEY_B_SEED)
    event["payload"]["successor_acceptance"] = acceptance
    event = sign_owner_transfer_event(event)
    result = {"boundary": "Real independent Ed25519 signatures and schema-bound finite intent. Current Account/Device/root authority, membership and lifecycle below are explicit qualified reference inputs, not native PCR, remote directory, storage or HTTP proof.",
            "event": event, "acceptance": acceptance, **derived, "prestate_root": root,
            "outer_signer_basis": {"actor_id": copy.deepcopy(OWNER_TRANSFER_AUTHOR),
                "verification_method": OWNER_TRANSFER_AUTHOR_VM, "public_key_base64url": public_key(KEY_A_SEED)},
            "successor_source": {"actor_id": copy.deepcopy(OWNER_TRANSFER_ACTOR), "principal_kind": "human",
                "device_id": OWNER_TRANSFER_DEVICE, "authorization_event_ref": EVENT_ID,
                "authorized_generation_ref": 7, "current_generation_ref": 7,
                "device_status": "accepted", "account_status": "active", "membership": "join",
                "not_before": "2026-09-20T00:00:00.000Z", "expires_at": "2026-09-20T01:00:00.000Z",
                "verification_method": OWNER_TRANSFER_VM, "public_key_base64url": public_key(KEY_B_SEED),
                "scopes": ["ak.realm.owner.transfer"]},
            "cases": [{"name": name, "expected_result": expected} for name, expected in OWNER_TRANSFER_CASES]}
    result["evaluation_at"] = event["created_at"]
    result["transport"] = owner_transfer_transport(event, result["successor_source"])
    return result


def build_fixture() -> dict:
    realm_commit_unsigned = {
        "commit_id": COMMIT_ID,
        "realm_id": REALM_ID,
        "stream_ref": {"kind": "realm", "realm_id": REALM_ID},
        "stream_position": 0,
        "previous_commit_ref": None,
        "event_ref": EVENT_ID,
        "governance_generation": "1",
        "authority_ref": EVENT_ID,
        "committed_at": "2026-09-20T00:00:00.000Z",
    }
    commit_sig, commit_derived = make_signature(
        "ak.realm_commit_signature.v1", realm_commit_unsigned, OLD_VM, KEY_A_SEED
    )
    realm_commit_host = dict(realm_commit_unsigned, signature=commit_sig)

    handoff_unsigned = {
        "handoff_id": HANDOFF_ID,
        "realm_id": REALM_ID,
        "from_generation": "1",
        "to_generation": "2",
        "from_service_id": OLD_SERVICE,
        "to_service_id": NEW_SERVICE,
        "final_stream_heads_digest": "sha256:" + "1" * 64,
        "snapshot_ref": SNAPSHOT_ID,
        "change_event_ref": EVENT_ID,
        "change_commit_id": COMMIT_ID,
    }
    old_sig, old_derived = make_signature(
        "ak.realm_authority_handoff_old_signature.v1",
        handoff_unsigned,
        OLD_VM,
        KEY_A_SEED,
    )
    new_sig, new_derived = make_signature(
        "ak.realm_authority_handoff_new_acceptance_signature.v1",
        handoff_unsigned,
        NEW_VM,
        KEY_B_SEED,
    )
    handoff_host = dict(
        handoff_unsigned,
        old_authority_signature=old_sig,
        new_authority_acceptance_signature=new_sig,
    )

    assertion_unsigned = {
        "realm_id": REALM_ID,
        "current_generation": "2",
        "current_service_id": NEW_SERVICE,
        "last_handoff_ref": HANDOFF_ID,
        "realm_stream_head": {
            "stream_ref": {"kind": "realm", "realm_id": REALM_ID},
            "stream_position": 0,
            "commit_id": COMMIT_ID,
        },
        "nonce": "AAAAAAAAAAAAAAAAAAAAAA",
        "expires_at": "2026-09-20T00:05:00.000Z",
    }
    assertion_sig, assertion_derived = make_signature(
        "ak.realm_authority_current_assertion_signature.v1",
        assertion_unsigned,
        NEW_VM,
        KEY_B_SEED,
    )
    assertion_host = dict(assertion_unsigned, signature=assertion_sig)

    snapshot_unsigned = {
        "purpose": "full_recovery",
        "snapshot_id": SNAPSHOT_ID,
        "realm_id": REALM_ID,
        "governance_generation": "2",
        "visible_stream_heads": [
            {
                "stream_ref": {"kind": "realm", "realm_id": REALM_ID},
                "stream_position": 0,
                "commit_id": COMMIT_ID,
            }
        ],
        "current_state_entries": [],
        "retention_and_history_floor": {
            "history_access": "since_join",
            "stream_floors": [],
        },
        "created_at": "2026-09-20T00:00:00.000Z",
    }
    snapshot_sig, snapshot_derived = make_signature(
        "ak.realm_snapshot_signature.v1", snapshot_unsigned, NEW_VM, KEY_B_SEED
    )
    snapshot_host = dict(snapshot_unsigned, signature=snapshot_sig)

    welcome_unsigned = {
        "welcome_id": "ak:mls_welcome_delivery:0199aaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa",
        "realm_id": REALM_ID,
        "effective_scope": {"kind": "realm", "realm_id": REALM_ID},
        "commit_event_ref": EVENT_ID,
        "recipient_actor_id": {"kind": "service", "service_id": NEW_SERVICE},
        "recipient_endpoint": {
            "kind": "device",
            "device_id": "ak:device:0199bbbb-bbbb-7bbb-8bbb-bbbbbbbbbbbb",
        },
        "keypackage_claim_ref": "ak:keypackage_claim:0199cccc-cccc-7ccc-8ccc-cccccccccccc",
        "ciphertext_base64url": "AQIDBA",
    }
    welcome_sig, welcome_derived = make_signature(
        "ak.mls_welcome_delivery_signature.v1",
        welcome_unsigned,
        PRODUCER_VM,
        KEY_A_SEED,
    )
    welcome_host = dict(welcome_unsigned, producer_proof=welcome_sig)

    cases = [
        {
            "case_id": "realm_commit",
            "context": "ak.realm_commit_signature.v1",
            "schema_ref": "schemas/realm-commit.schema.json",
            "signature_member": "signature",
            "excluded_signature_members": ["signature"],
            "host_object": realm_commit_host,
            **commit_derived,
            "test_key_ref": "conformance_ed25519_fixture_key",
            "authority_basis": authority_basis(
                "governance_generation_current_station",
                {"governance_generation": "1", "service_id": OLD_SERVICE},
                "did:webvh:z6mkfixturestationa:station-a.example",
                OLD_VM,
                commit_derived["public_key_base64url"],
                "conformance_ed25519_fixture_key",
            ),
            "expected_result": "accept",
        },
        {
            "case_id": "realm_authority_handoff_old",
            "context": "ak.realm_authority_handoff_old_signature.v1",
            "schema_ref": "schemas/realm-authority-handoff.schema.json",
            "signature_member": "old_authority_signature",
            "excluded_signature_members": [
                "old_authority_signature",
                "new_authority_acceptance_signature",
            ],
            "host_object": handoff_host,
            **old_derived,
            "test_key_ref": "conformance_ed25519_fixture_key",
            "authority_basis": authority_basis(
                "handoff_old_current_at_frozen_cut",
                {"generation": "1", "service_id": OLD_SERVICE},
                "did:webvh:z6mkfixturestationa:station-a.example",
                OLD_VM,
                old_derived["public_key_base64url"],
                "conformance_ed25519_fixture_key",
            ),
            "expected_result": "accept",
        },
        {
            "case_id": "realm_authority_handoff_new_acceptance",
            "context": "ak.realm_authority_handoff_new_acceptance_signature.v1",
            "schema_ref": "schemas/realm-authority-handoff.schema.json",
            "signature_member": "new_authority_acceptance_signature",
            "excluded_signature_members": [
                "old_authority_signature",
                "new_authority_acceptance_signature",
            ],
            "host_object": handoff_host,
            **new_derived,
            "test_key_ref": "rfc8032_test_1_ed25519_key",
            "authority_basis": authority_basis(
                "handoff_new_after_verified_import",
                {"generation": "2", "service_id": NEW_SERVICE},
                "did:webvh:z6mkfixturestationb:station-b.example",
                NEW_VM,
                new_derived["public_key_base64url"],
                "rfc8032_test_1_ed25519_key",
            ),
            "expected_result": "accept",
        },
        {
            "case_id": "realm_authority_current_assertion",
            "context": "ak.realm_authority_current_assertion_signature.v1",
            "schema_ref": "schemas/realm-authority-bundle.schema.json#/$defs/current_assertion",
            "signature_member": "signature",
            "excluded_signature_members": ["signature"],
            "host_object": assertion_host,
            **assertion_derived,
            "test_key_ref": "rfc8032_test_1_ed25519_key",
            "authority_basis": authority_basis(
                "verified_chain_current_station",
                {"current_generation": "2", "current_service_id": NEW_SERVICE},
                "did:webvh:z6mkfixturestationb:station-b.example",
                NEW_VM,
                assertion_derived["public_key_base64url"],
                "rfc8032_test_1_ed25519_key",
            ),
            "expected_result": "accept",
        },
        {
            "case_id": "realm_snapshot",
            "context": "ak.realm_snapshot_signature.v1",
            "schema_ref": "schemas/realm-state-snapshot.schema.json",
            "signature_member": "signature",
            "excluded_signature_members": ["signature"],
            "host_object": snapshot_host,
            **snapshot_derived,
            "test_key_ref": "rfc8032_test_1_ed25519_key",
            "authority_basis": authority_basis(
                "current_bundle_generation_station",
                {"governance_generation": "2", "service_id": NEW_SERVICE},
                "did:webvh:z6mkfixturestationb:station-b.example",
                NEW_VM,
                snapshot_derived["public_key_base64url"],
                "rfc8032_test_1_ed25519_key",
            ),
            "expected_result": "accept",
        },
        {
            "case_id": "mls_welcome_delivery",
            "context": "ak.mls_welcome_delivery_signature.v1",
            "schema_ref": "schemas/mls-welcome-delivery.schema.json",
            "signature_member": "producer_proof",
            "excluded_signature_members": ["producer_proof"],
            "host_object": welcome_host,
            **welcome_derived,
            "test_key_ref": "conformance_ed25519_fixture_key",
            "authority_basis": authority_basis(
                "winning_commit_event_exact_producer",
                {
                    "commit_event_ref": EVENT_ID,
                    "producer_actor_id": {
                        "kind": "service",
                        "service_id": PRODUCER_SERVICE,
                    },
                },
                "did:webvh:z6mkfixturealice:alice.example",
                PRODUCER_VM,
                welcome_derived["public_key_base64url"],
                "conformance_ed25519_fixture_key",
            ),
            "expected_result": "accept",
        },
    ]
    return {

        "runner": {
            "kind": "named_suite",
            "entrypoint": "ak.suite.detached_object_signature_transcripts.v1",
        },


        "vector_id": "ak.vector.detached_object_signature_transcripts.v1",
        "covers_vectors": ["ak.vector.detached_object_signature_transcripts.v1"],
        "security_evidence": [
            {
                "vector_id": "ak.vector.detached_object_signature_transcripts.v1",
                "clause_id": "AK-NC-062",
                "decision_points": [
                    {
                        "id": "welcome_unsigned_projection_is_complete_and_digest_is_recomputed",
                        "requirement": "The Welcome verifier removes only producer_proof, canonicalizes the complete remaining closed host object, and compares its independently recomputed SHA-256 digest before trusting the signature.",
                        "evidence": [
                            "/cases/5/unsigned_projection",
                            "/cases/5/expected_signed_digest",
                        ],
                    },
                    {
                        "id": "welcome_context_prefix_and_envelope_are_byte_exact",
                        "requirement": "The exact context plus one LF prefixes the RFC 8785 JCS five-member envelope, and Ed25519 verifies over those reconstructed bytes.",
                        "evidence": ["/cases/5/prefix_bytes_hex", "/cases/5/signature_input_hex"],
                    },
                    {
                        "id": "welcome_signer_is_the_exact_commit_producer",
                        "requirement": "The structured authority basis binds commit_event_ref to the winning Commit Event's exact producer actor, verified method and public key rather than a governance, recipient or claim-service key.",
                        "evidence": ["/cases/5/authority_basis"],
                    },
                ],
            }
        ],
        "test_material_warning": "Published conformance-only private seeds; MUST NOT be used in production.",
        "test_keys": [
            {
                "test_key_ref": "conformance_ed25519_fixture_key",
                "private_seed_hex": KEY_A_SEED.hex(),
                "public_key_base64url": public_key(KEY_A_SEED),
                "production_use": "forbidden",
            },
            {
                "test_key_ref": "rfc8032_test_1_ed25519_key",
                "private_seed_hex": KEY_B_SEED.hex(),
                "public_key_base64url": public_key(KEY_B_SEED),
                "production_use": "forbidden",
            },
        ],
        "cases": cases,
        "owner_transfer": owner_transfer_fixture(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = json.dumps(build_fixture(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not FIXTURE.is_file() or FIXTURE.read_text(encoding="utf-8") != expected:
            print(f"STALE: {FIXTURE.relative_to(ROOT)}")
            return 1
        print("PASSED: detached-object signature KAT is current")
        return 0
    FIXTURE.write_text(expected, encoding="utf-8", newline="\n")
    print(f"updated {FIXTURE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
