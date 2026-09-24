#!/usr/bin/env python3
"""Regenerate the six detached-object signature byte known-answer cases."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
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
    sig = b64u(Ed25519PrivateKey.from_private_bytes(seed).sign(signature_input))
    carrier = dict(envelope)
    carrier["sig"] = sig
    derived = {
        "unsigned_projection": copy.deepcopy(unsigned_projection),
        "unsigned_jcs_utf8_hex": unsigned_bytes.hex(),
        "expected_signed_digest": signed_digest,
        "signature_envelope_without_sig": envelope,
        "prefix_bytes_hex": prefix.hex(),
        "signature_input_hex": signature_input.hex(),
        "public_key_b64u": public_key(seed),
        "expected_sig": sig,
    }
    return carrier, derived


def authority_basis(
    kind: str,
    coordinate: dict,
    controller_did: str,
    verification_method: str,
    public_key_b64u: str,
    test_key_ref: str,
) -> dict:
    return {
        "basis_kind": kind,
        "coordinate": coordinate,
        "resolved_controller_did": controller_did,
        "authorized_verification_method": verification_method,
        "public_key_b64u": public_key_b64u,
        "test_key_ref": test_key_ref,
    }


def build_fixture() -> dict:
    realm_commit_unsigned = {
        "commit_id": COMMIT_ID,
        "realm_id": REALM_ID,
        "stream_ref": {"kind": "realm", "realm_id": REALM_ID},
        "stream_position": 0,
        "previous_commit_ref": None,
        "event_ref": EVENT_ID,
        "governance_generation": 1,
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
        "from_generation": 1,
        "to_generation": 2,
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
        "current_generation": 2,
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
        "snapshot_id": SNAPSHOT_ID,
        "realm_id": REALM_ID,
        "governance_generation": 2,
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
        "ciphertext_b64": "AQIDBA",
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
                {"governance_generation": 1, "service_id": OLD_SERVICE},
                "did:webvh:z6mkfixturestationa:station-a.example",
                OLD_VM,
                commit_derived["public_key_b64u"],
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
                {"generation": 1, "service_id": OLD_SERVICE},
                "did:webvh:z6mkfixturestationa:station-a.example",
                OLD_VM,
                old_derived["public_key_b64u"],
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
                {"generation": 2, "service_id": NEW_SERVICE},
                "did:webvh:z6mkfixturestationb:station-b.example",
                NEW_VM,
                new_derived["public_key_b64u"],
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
                {"current_generation": 2, "current_service_id": NEW_SERVICE},
                "did:webvh:z6mkfixturestationb:station-b.example",
                NEW_VM,
                assertion_derived["public_key_b64u"],
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
                {"governance_generation": 2, "service_id": NEW_SERVICE},
                "did:webvh:z6mkfixturestationb:station-b.example",
                NEW_VM,
                snapshot_derived["public_key_b64u"],
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
                welcome_derived["public_key_b64u"],
                "conformance_ed25519_fixture_key",
            ),
            "expected_result": "accept",
        },
    ]
    return {
        "suite": "detached_object_signature_transcripts",
        "fixture_kind": "cryptographic_known_answer",
        "runner": {
            "kind": "named_suite",
            "entrypoint": "ak.suite.detached_object_signature_transcripts.v1",
        },
        "version": "2026-09-24",
        "schema": "arkret.detached-object-signature-kat-fixture.v1",
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
                "public_key_b64u": public_key(KEY_A_SEED),
                "production_use": "forbidden",
            },
            {
                "test_key_ref": "rfc8032_test_1_ed25519_key",
                "private_seed_hex": KEY_B_SEED.hex(),
                "public_key_b64u": public_key(KEY_B_SEED),
                "production_use": "forbidden",
            },
        ],
        "cases": cases,
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
