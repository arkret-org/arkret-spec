#!/usr/bin/env python3
"""Generate executable digest-suite genesis and transition vectors."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from blake3 import blake3


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "spec" / "v1" / "artifacts" / "fixtures"
OUTPUT = FIXTURES / "hash-transition-fixture.json"


def jcs(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def blake3_digest(value: bytes) -> str:
    return "blake3:" + blake3(value).hexdigest()


def digest_raw(digest: str) -> bytes:
    return bytes.fromhex(digest.split(":", 1)[1])


def control_leaf_preimage(digest: str) -> bytes:
    return b"\x00" + digest.encode("utf-8")


def event_id(digest: str, code: int) -> str:
    raw = bytes([code]) + bytes.fromhex(digest.split(":", 1)[1])
    return "ak:event:" + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def accepted_event(preimage: dict[str, object], digest: str, identifier: str, jws: str) -> dict[str, object]:
    event = dict(preimage)
    event["event_id"] = identifier
    event["proofs"] = [{
        "kind": "detached_jws",
        "verification_method": "did:webvh:z6mkfixture:alice.example#key-1",
        "event_digest": digest,
        "created_at": preimage["created_at"],
        "signer_resolution_evidence_ref": "ak:signer_evidence:sha256:" + "1" * 64,
        "jws": jws,
    }]
    return event


def availability_receipt(
    event: dict[str, object],
    realm_id: str,
    expires_at: str,
    created_at: str,
    jws: str,
) -> dict[str, object]:
    event_bytes = jcs(event)
    bytes_preimage = b"ak.availability_event_bytes.v1\x00" + event_bytes.encode()
    bytes_digest = sha256(bytes_preimage)
    core = {
        "realm_id": realm_id,
        "event_id": event["event_id"],
        "bytes_digest": bytes_digest,
        "holder_service_id": "ak:did_core:webvh:z6mkholder",
        "retention_expires_at": expires_at,
        "holder_signer_evidence_ref": "ak:signer_evidence:sha256:" + "2" * 64,
    }
    payload_digest = sha256(jcs(core).encode())
    transcript = {
        "context": "ak.availability_receipt_proof.v1",
        "payload_digest": payload_digest,
        **core,
        "verification_method": "did:webvh:z6mkholder:holder.example#key-1",
        "created_at": created_at,
    }
    content = {
        **core,
        "signature": {
            "kind": "detached_jws",
            "verification_method": "did:webvh:z6mkholder:holder.example#key-1",
            "payload_digest": payload_digest,
            "created_at": created_at,
            "jws": jws,
        },
    }
    return {
        "accepted_event_canonical_bytes_utf8": event_bytes,
        "bytes_digest_preimage_hex": bytes_preimage.hex(),
        "bytes_digest": bytes_digest,
        "receipt_core_canonical_bytes_utf8": jcs(core),
        "signature_payload_digest": payload_digest,
        "signature_transcript_canonical_bytes_utf8": jcs(transcript),
        "receipt_canonical_bytes_utf8": jcs(content),
        "receipt_digest": sha256(jcs(content).encode()),
    }


def main() -> None:
    source = json.loads((FIXTURES / "content-bound-event-id-fixture.json").read_text(encoding="utf-8"))
    base_event = json.loads(source["cases"][1]["digest_preimage_canonical_bytes_utf8"])
    create = json.loads(source["cases"][1]["digest_preimage_canonical_bytes_utf8"])
    create["payload"]["object"]["digest_algorithm"] = "blake3"
    create_bytes = jcs(create)
    create_digest = sha256(create_bytes.encode())
    create_event_id = event_id(create_digest, 1)
    create_realm_id = "ak:realm:" + create_event_id.rsplit(":", 1)[1]
    genesis_state_leaf = jcs({
        "cell": "ak:cell:ak.component.realm.digest_suite.v1:null",
        "state": {"revision_event_id": create_event_id, "value": "blake3"},
    })
    genesis_control_root = blake3_digest(control_leaf_preimage(create_digest))
    genesis_state_root = blake3_digest(b"\x00" + genesis_state_leaf.encode())
    genesis_body = {
        "realm_id": create_realm_id,
        "predecessor_ref": None,
        "delta": [create_digest],
        "control_event_set_root": genesis_control_root,
        "state_root": genesis_state_root,
        "notary_seq": 0,
        "availability_receipt_digests": [],
        "sealed_at": "2026-08-06T00:00:02.000Z",
        "hlc": "0198943a5000-0000-aabbccdd",
    }
    genesis_body["configuration_ref"] = create_event_id
    genesis_body["command_results"] = [{"event_digest": create_digest, "unit_event_digests": [create_digest], "outcome": "committed",
        "result_digest": blake3_digest(jcs({"event_digest": create_digest, "unit_event_digests": [create_digest], "outcome": "committed",
            "effects": [{"cell_id": json.loads(genesis_state_leaf)["cell"], "state": json.loads(genesis_state_leaf)["state"]}],
            "reason_code": None}).encode())}]
    genesis_body_bytes = jcs(genesis_body)
    genesis_seal_digest = blake3_digest(genesis_body_bytes.encode())

    realm_id = source["cases"][1]["derived_realm_id"]
    base_seal_id = "ak:seal:sha256:" + "3" * 64
    snapshot = {
        "realm_id": realm_id,
        "seal_basis": {"leaves": [base_seal_id]},
        "state_root": "sha256:" + "4" * 64,
    }
    snapshot_bytes = jcs(snapshot)
    realm_state_snapshot_commitment = sha256(snapshot_bytes.encode())
    transition = {
        "actor_id": "ak:did_core:webvh:z6mkfixture",
        "actor_seq": 1,
        "created_at": "2026-08-07T00:00:00.000Z",
        "kind": "ak.realm.digest_suite_transition",
        "payload": {
            "from_digest_algorithm": "sha256",
            "to_digest_algorithm": "blake3",
            "transition_realm_state_snapshot_ref": "ak:realm_state_snapshot:01989123-4567-7abc-8def-0123456789ab",
            "realm_state_snapshot_commitment": realm_state_snapshot_commitment,
        },
        "prev_refs": [source["cases"][1]["derived_event_id"]],
        "realm_id": realm_id,
        "scope_ref": {"kind": "realm", "realm_id": realm_id},
        "seal_basis": {"leaves": [base_seal_id]},
    }
    transition_bytes = jcs(transition)
    transition_digest = sha256(transition_bytes.encode())
    transition_event_id = event_id(transition_digest, 1)
    transition_accepted = accepted_event(
        transition, transition_digest, transition_event_id, "EEEE..FFFF"
    )
    transition_receipt = availability_receipt(
        transition_accepted,
        realm_id,
        "2026-09-06T00:00:00.000Z",
        "2026-08-07T00:00:01.000Z",
        "GGGG..HHHH",
    )
    previous_leaf = jcs({
        "cell": "ak:cell:ak.component.realm.digest_suite.v1:null",
        "state": {"revision_event_id": source["cases"][1]["derived_event_id"], "value": "sha256"},
    })
    next_leaf = jcs({
        "cell": "ak:cell:ak.component.realm.digest_suite.v1:null",
        "state": {"revision_event_id": transition_event_id, "value": "blake3"},
    })
    previous_root = sha256(b"\x00" + previous_leaf.encode())
    next_root = blake3_digest(b"\x00" + next_leaf.encode())
    covered = sorted([transition_digest, source["cases"][1]["event_digest"]])
    transition_control_leaf_preimages = [control_leaf_preimage(digest) for digest in covered]
    transition_control_leaf_digests = [
        blake3(preimage).digest() for preimage in transition_control_leaf_preimages
    ]
    control_root = blake3_digest(b"\x01" + b"".join(transition_control_leaf_digests))
    transition_body = {
        "realm_id": realm_id,
        "predecessor_ref": base_seal_id,
        "delta": [transition_digest],
        "control_event_set_root": control_root,
        "state_root": next_root,
        "notary_seq": 1,
        "availability_receipt_digests": [transition_receipt["receipt_digest"]],
        "previous_state_root": previous_root,
        "previous_digest_algorithm": "sha256",
        "sealed_at": "2026-08-07T00:00:02.000Z",
        "hlc": "019899606c00-0000-aabbccdd",
    }
    transition_body["configuration_ref"] = source["cases"][1]["derived_event_id"]
    transition_body["command_results"] = [{"event_digest": transition_digest, "unit_event_digests": [transition_digest], "outcome": "committed",
        "result_digest": blake3_digest(jcs({"event_digest": transition_digest, "unit_event_digests": [transition_digest], "outcome": "committed",
            "effects": [{"cell_id": json.loads(next_leaf)["cell"], "state": json.loads(next_leaf)["state"]}],
            "reason_code": None}).encode())}]
    transition_body_bytes = jcs(transition_body)
    transition_seal_digest = blake3_digest(transition_body_bytes.encode())
    successor = {
        "actor_id": "ak:did_core:webvh:z6mkfixture",
        "actor_seq": 2,
        "created_at": "2026-08-08T00:00:00.000Z",
        "kind": "ak.realm.freeze",
        "payload": {"object": {"frozen": True}},
        "prev_refs": [transition_event_id],
        "realm_id": realm_id,
        "scope_ref": {"kind": "realm", "realm_id": realm_id},
        "seal_basis": {"leaves": ["ak:seal:" + transition_seal_digest]},
    }
    successor_bytes = jcs(successor)
    successor_digest = blake3_digest(successor_bytes.encode())

    fixture = {
        "generated_by": "tools/generate_hash_transition_fixture.py",
        "scope": "Byte-level suite transition over an isolated registered digest Cell. Symbolic surrounding state and signatures are not a complete Realm execution or cryptographic signature proof.",
        "profile": "ak.profile.hash_transition.v1",
        "version": "2026-08-24",
        "runner": {"kind": "named_suite", "entrypoint": "ak.suite.encoding.hash_transition.v1"},
        "covers_vectors": [
            "ak.vector.hash_transition.dual_root_recompute.v1",
            "ak.vector.hash_transition.fail_closed.v1",
        ],
        "cases": [
            {
                "name": "blake3_genesis_bridge",
                "create_event_digest_preimage_canonical_bytes_utf8": create_bytes,
                "create_event_digest": create_digest,
                "create_event_id": create_event_id,
                "declared_initial_live_suite": "blake3",
                "genesis_availability_receipt_digests": [],
                "genesis_availability_negative_mutation": "non_empty_receipt_commitment",
                "state_leaf_preimage_canonical_bytes_utf8": genesis_state_leaf,
                "state_leaf_preimage_hex": (b"\x00" + genesis_state_leaf.encode()).hex(),
                "state_root": genesis_state_root,
                "control_event_leaf_preimage_hex": control_leaf_preimage(create_digest).hex(),
                "control_event_set_root": genesis_control_root,
                "seal_body_canonical_bytes_utf8": genesis_body_bytes,
                "seal_id": "ak:seal:" + genesis_seal_digest,
                "notary_signature_payload_digest": blake3_digest(jcs({"context": "ak.seal.commit.v1", "seal_digest": genesis_seal_digest, "configuration_ref": genesis_body["configuration_ref"], "notary_seq": 0, "view": 0}).encode()),
                "expected": {"accepted_live_suite": "blake3", "decision": "accept"},
            },
            {
                "name": "dual_root_recompute",
                "vector_id": "ak.vector.hash_transition.dual_root_recompute.v1",
                "old_suite": "sha256",
                "new_suite": "blake3",
                "snapshot_canonical_bytes_utf8": snapshot_bytes,
                "realm_state_snapshot_commitment": realm_state_snapshot_commitment,
                "transition_event_digest_preimage_canonical_bytes_utf8": transition_bytes,
                "transition_event_digest": transition_digest,
                "transition_event_id": transition_event_id,
                "transition_availability_receipt": transition_receipt,
                "previous_state_leaf_preimage_canonical_bytes_utf8": previous_leaf,
                "previous_state_leaf_preimage_hex": (b"\x00" + previous_leaf.encode()).hex(),
                "previous_state_root": previous_root,
                "next_state_leaf_preimage_canonical_bytes_utf8": next_leaf,
                "next_state_leaf_preimage_hex": (b"\x00" + next_leaf.encode()).hex(),
                "state_root": next_root,
                "control_event_set_root": control_root,
                "control_event_leaf_preimages_hex": [
                    preimage.hex() for preimage in transition_control_leaf_preimages
                ],
                "seal_body_canonical_bytes_utf8": transition_body_bytes,
                "seal_id": "ak:seal:" + transition_seal_digest,
                "notary_signature_payload_digest": blake3_digest(jcs({"context": "ak.seal.commit.v1", "seal_digest": transition_seal_digest, "configuration_ref": transition_body["configuration_ref"], "notary_seq": 1, "view": 0}).encode()),
                "successor_event_digest_preimage_canonical_bytes_utf8": successor_bytes,
                "successor_event_digest": successor_digest,
                "successor_event_id": event_id(successor_digest, 2),
                "expected": {"accepted_live_suite": "blake3", "decision": "accept"},
            },
            {
                "name": "transition_fail_closed_matrix",
                "vector_id": "ak.vector.hash_transition.fail_closed.v1",
                "variants": [
                    "missing_previous_state_root", "previous_root_wrong_suite",
                    "previous_digest_algorithm_is_profile_id", "new_root_wrong_suite",
                    "transition_event_uses_new_suite", "transition_receipt_uses_new_suite",
                    "transition_seal_id_uses_old_suite", "transition_seal_payload_digest_uses_old_suite",
                    "transition_control_event_set_root_uses_old_suite",
                    "multiple_same_realm_predecessors",
                    "transition_seal_contains_multiple_transition_moves",
                    "transition_seal_mixes_ordinary_move", "genesis_live_suite_inferred_from_create_event_digest",
                    "realm_state_snapshot_commitment_mismatch", "suite_identity_mismatch", "strength_downgrade",
                    "previous_state_root_on_non_transition_seal", "old_suite_security_command_after_transition",
                ],
                "expected": {"decision": "rejected_seal", "atomic": True, "state_unchanged": True},
            },
        ],
    }
    OUTPUT.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
