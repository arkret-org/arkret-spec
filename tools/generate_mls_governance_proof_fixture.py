#!/usr/bin/env python3
"""Generate the deterministic MLS governance proof verifier/materializer fixture."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "mls-governance-proof-fixture.json"
EMPTY_SHA256 = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
CHUNK_DOMAIN = b"arkret-mls-governance-proof-chunk-v1\n"
BUNDLE_DOMAIN = b"arkret-mls-governance-proof-bundle-v1\n"
REQUEST_DOMAIN = b"arkret-mls-governance-proof-request-v1\n"


def canonical_bytes(value: Any) -> bytes:
    """JCS-equivalent encoding for this fixture's integer/ASCII-only values."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_raw(value: bytes) -> bytes:
    return hashlib.sha256(value).digest()


def wire_digest(value: bytes) -> str:
    return "sha256:" + sha256_raw(value).hex()


def digest_raw(value: str) -> bytes:
    prefix, hex_value = value.split(":", 1)
    if prefix != "sha256":
        raise ValueError(f"fixture requires sha256, got {prefix}")
    return bytes.fromhex(hex_value)


def b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def public_jwk(private_key: Ed25519PrivateKey, kid: str) -> dict[str, str]:
    public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "kty": "OKP",
        "crv": "Ed25519",
        "x": b64u(public),
        "alg": "Ed25519",
        "use": "sig",
        "kid": kid,
    }


def detached_jws(private_key: Ed25519PrivateKey, kid: str, payload: bytes) -> str:
    protected = b64u(canonical_bytes({"alg": "Ed25519", "kid": kid}))
    signing_input = protected.encode("ascii") + b"." + b64u(payload).encode("ascii")
    return protected + ".." + b64u(private_key.sign(signing_input))


def merkle_root_from_leaf_data(items: list[bytes]) -> str:
    if not items:
        return EMPTY_SHA256
    level = [sha256_raw(b"\x00" + item) for item in items]
    while len(level) > 1:
        next_level: list[bytes] = []
        for index in range(0, len(level), 2):
            if index + 1 == len(level):
                next_level.append(level[index])
            else:
                next_level.append(sha256_raw(b"\x01" + level[index] + level[index + 1]))
        level = next_level
    return "sha256:" + level[0].hex()


def four_leaf_root_and_proofs(digests: list[str]) -> tuple[str, list[list[str]]]:
    if len(digests) != 4:
        raise ValueError("this compact fixture intentionally uses exactly four chunks")
    leaves = [sha256_raw(b"\x00" + digest_raw(value)) for value in digests]
    left = sha256_raw(b"\x01" + leaves[0] + leaves[1])
    right = sha256_raw(b"\x01" + leaves[2] + leaves[3])
    root = sha256_raw(b"\x01" + left + right)
    as_wire = lambda value: "sha256:" + value.hex()
    proofs = [
        [as_wire(leaves[1]), as_wire(right)],
        [as_wire(leaves[0]), as_wire(right)],
        [as_wire(leaves[3]), as_wire(left)],
        [as_wire(leaves[2]), as_wire(left)],
    ]
    return as_wire(root), proofs


def derive_event_id(digest_wire: str) -> str:
    """encoding.md section 4.0: suite code plus all 32 digest octets."""
    suite, digest_hex = digest_wire.split(":", 1)
    suite_code = {"sha256": 0x01, "blake3": 0x02}.get(suite)
    digest = bytes.fromhex(digest_hex)
    if suite_code is None or len(digest) != 32:
        raise ValueError("v1 Event ID requires an active suite and 32-byte digest")
    body = bytes((suite_code,)) + digest
    token = base64.urlsafe_b64encode(body).rstrip(b"=").decode("ascii")
    if len(body) != 33 or len(token) != 44:
        raise AssertionError("Event ID encoding length drift")
    return token


def fixture_derived_id(kind: str, label: str) -> str:
    """Build a stable suite-tagged Event-derived identifier for fixture context."""
    digest = "sha256:" + hashlib.sha256(
        b"ak.mls-governance-proof.fixture-id.v1\n" + label.encode("utf-8")
    ).hexdigest()
    return f"ak:{kind}:{derive_event_id(digest)}"


def build_event(
    *,
    actor_seq: int,
    member_did: str,
    previous_event_id: str | None,
    realm_id: str,
    scope_ref: dict[str, str],
    actor_did: str,
    verification_method: str,
    signing_key: Ed25519PrivateKey,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    cell_subject = member_did.replace(":", "%3A")
    state_cell = f"ak:cell:ak.component.member.state.v1:{cell_subject}"
    producer_event: dict[str, Any] = {
        "kind": "ak.member.state",
        "realm_id": realm_id,
        "scope_ref": deepcopy(scope_ref),
        "actor_id": actor_did,
        "actor_seq": actor_seq,
        "created_at": f"2026-07-15T00:00:0{actor_seq}Z",
        "hlc": f"019809f4a80{actor_seq}-0000-a1b2c3d4",
        "prev_refs": [] if previous_event_id is None else [previous_event_id],
        "refs": [],
        "payload": {
            "realm_id": realm_id,
            "actor_id": member_did,
            "membership": "join",
            "delivery_status": "unroutable",
        },
    }
    # section 6: the digest preimage removes proofs/unsigned/actor_kind/event_id;
    # section 4.0 then derives event_id from that digest, so compute in that order.
    digest_source = deepcopy(producer_event)
    event_digest = wire_digest(canonical_bytes(digest_source))
    producer_event["event_id"] = "ak:event:" + derive_event_id(event_digest)
    event_id = producer_event["event_id"]
    proof_created_at = producer_event["created_at"]
    binding = {
        "context": "ak.event-proof-v1",
        "event_digest": event_digest,
        "actor_id": actor_did,
        "verification_method": verification_method,
        "created_at": proof_created_at,
    }
    proof = {
        "kind": "detached_jws",
        "verification_method": verification_method,
        "event_digest": event_digest,
        "created_at": proof_created_at,
        "jws": detached_jws(signing_key, verification_method, canonical_bytes(binding)),
    }
    accepted_event = deepcopy(producer_event)
    accepted_event["proofs"] = [proof]
    state_leaf = {
        "cell": state_cell,
        "state": {"value": "join"},
    }
    kat = {
        "event_id": event_id,
        "producer_event_canonical_bytes": len(canonical_bytes(digest_source)),
        "producer_event_digest": event_digest,
        "proof_binding_canonical_bytes": len(canonical_bytes(binding)),
        "proof_binding_sha256": wire_digest(canonical_bytes(binding)),
    }
    return accepted_event, event_digest, {"state_leaf": state_leaf, "kat": kat}


def mutation_case(
    name: str,
    operation: str,
    stage: str,
    reason_code: str,
    *,
    parameters: dict[str, Any] | None = None,
    recommit: str = "transport",
) -> dict[str, Any]:
    return {
        "name": name,
        "mutation": {
            "operation": operation,
            "parameters": parameters or {},
            "recommit": recommit,
        },
        "expected": {
            "decision": "reject_epoch",
            "failure_stage": stage,
            "reason_code": reason_code,
            "verified_bundle_persisted": False,
            "epoch_advanced": False,
        },
    }


def materializer_case(
    name: str,
    operation: str,
    error_code: str | None,
    *,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    accepted = error_code is None
    return {
        "name": name,
        "source_mutation": {"operation": operation, "parameters": parameters or {}},
        "expected": {
            "decision": "materialize" if accepted else "reject_request",
            "error_code": error_code,
            "response_count": 4 if accepted else 0,
            "partial_manifest_emitted": False,
        },
    }


def build_fixture() -> dict[str, Any]:
    actor_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("11" * 32))
    notary_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("22" * 32))
    actor_did = "did:webvh:z6mkfixtureadminexample:admin.example"
    actor_vm = actor_did + "#key-1"
    notary_did = "did:webvh:z6mkfixturenotaryexample:notary.example"
    notary_vm = notary_did + "#key-1"
    realm_id = fixture_derived_id("realm", "governance-realm")
    effective_scope = {"kind": "realm", "realm_id": realm_id}

    event_specs = [
        (0, "did:webvh:z6mkfixturebobexample:bob.example"),
        (1, "did:webvh:z6mkfixturecarolexample:carol.example"),
    ]
    event_rows = []
    previous_event_id = None
    for actor_seq, member_did in event_specs:
        event_row = build_event(
            actor_seq=actor_seq,
            member_did=member_did,
            previous_event_id=previous_event_id,
            realm_id=realm_id,
            scope_ref=effective_scope,
            actor_did=actor_did,
            verification_method=actor_vm,
            signing_key=actor_key,
        )
        event_rows.append(event_row)
        previous_event_id = event_row[0]["event_id"]
    events_by_digest = sorted(
        [(digest, event, extra) for event, digest, extra in event_rows],
        key=lambda row: row[0],
    )
    covered_digests = [row[0] for row in events_by_digest]
    frontier_events = [row[1] for row in events_by_digest]
    control_state = sorted(
        [row[2]["state_leaf"] for row in event_rows],
        key=lambda row: row["cell"],
    )

    control_event_set_root = merkle_root_from_leaf_data(
        [digest_raw(value) for value in covered_digests]
    )
    state_root = merkle_root_from_leaf_data([canonical_bytes(value) for value in control_state])
    completeness_leaf = {
        "actor_id": actor_did,
        "from_seq": 0,
        "to_seq": 1,
        "event_digests": [event_rows[0][1], event_rows[1][1]],
    }
    completeness_root = merkle_root_from_leaf_data([canonical_bytes(completeness_leaf)])
    mls_leaf_entries = sorted(
        [
            {
                "leaf_index": index,
                "principal_id": member_did,
                "credential_ref": f"{member_did}#device-1",
            }
            for index, (_, member_did) in enumerate(event_specs)
        ],
        key=canonical_bytes,
    )
    mls_leaf_set_digest = wire_digest(canonical_bytes(mls_leaf_entries))
    security_frontier_cell_entries = sorted(
        [
            {
                "cell_family": "ak.component.member.state.v1",
                "cell_subject": member_did,
                "projected_value_digest": wire_digest(canonical_bytes("join")),
            }
            for _, member_did in event_specs
        ],
        key=lambda row: (
            row["cell_family"].encode("utf-8"),
            canonical_bytes(row["cell_subject"]),
            row["projected_value_digest"],
        ),
    )
    security_frontier_input = {
        "profile_id": "ak.security_frontier.v1",
        "effective_scope": deepcopy(effective_scope),
        "cell_entries": security_frontier_cell_entries,
        "mls_leaf_set_digest": mls_leaf_set_digest,
    }
    security_frontier_digest = wire_digest(canonical_bytes(security_frontier_input))
    seal_body = {
        "realm_id": realm_id,
        "predecessor_refs": [],
        "delta": covered_digests,
        "covered_event_digests": covered_digests,
        "control_event_set_root": control_event_set_root,
        "state_root": state_root,
        "completeness_root": completeness_root,
        "notary_seq": 0,
        "sealed_at": "2026-07-15T00:00:02.000Z",
        "hlc": "019809f4a802-0000-d4c3b2a1",
    }
    seal_digest = wire_digest(canonical_bytes(seal_body))
    seal_id = "ak:seal:" + seal_digest

    governance_binding = {
        "binding_version": 1,
        "encoding_profile": "cbor-deterministic-rfc8949-v1",
        "realm_id": realm_id,
        "effective_scope": deepcopy(effective_scope),
        "mls_group_id": "Z3JvdXAtMDE",
        "previous_epoch": 41,
        "next_epoch": 42,
        "security_frontier_digest": security_frontier_digest,
        "binding_profile": "ak.profile.mls_governance_binding.full.v1",
        "reducer_profile": "ak.reducer.core.v1",
    }

    seal = {"id": seal_id, **seal_body}
    seal["notary_signature"] = {
        "verification_method": notary_vm,
        "payload_digest": seal_digest,
        "created_at": seal_body["sealed_at"],
        "jws": detached_jws(notary_key, notary_vm, canonical_bytes(seal_body)),
    }

    proof_identity = {
        "realm_id": realm_id,
        "effective_scope": deepcopy(effective_scope),
        "mls_group_id": governance_binding["mls_group_id"],
        "previous_epoch": governance_binding["previous_epoch"],
        "next_epoch": governance_binding["next_epoch"],
        "binding_profile": governance_binding["binding_profile"],
        "reducer_profile": governance_binding["reducer_profile"],
        "trusted_anchor_seal_id": seal_id,
    }
    proof_request_digest = wire_digest(REQUEST_DOMAIN + canonical_bytes(proof_identity))

    collection_rows = [
        ("seal_path", [seal]),
        ("covered_event_digests", covered_digests),
        ("control_state", control_state),
        ("frontier_events", frontier_events),
    ]
    chunks: list[dict[str, Any]] = []
    for index, (collection, items) in enumerate(collection_rows):
        digest_input = {
            "chunk_index": index,
            "collection": collection,
            "start_index": 0,
            "items": items,
        }
        chunks.append(
            {
                **digest_input,
                "chunk_digest": wire_digest(CHUNK_DOMAIN + canonical_bytes(digest_input)),
                "chunk_proof": [],
            }
        )
    chunks_root, proofs = four_leaf_root_and_proofs(
        [chunk["chunk_digest"] for chunk in chunks]
    )
    for chunk, proof in zip(chunks, proofs, strict=True):
        chunk["chunk_proof"] = proof

    total_item_bytes = sum(
        len(canonical_bytes(item))
        for _, items in collection_rows
        for item in items
    )
    manifest = {
        "manifest_version": 1,
        "chunk_count": 4,
        "chunks_root": chunks_root,
        "total_item_bytes": total_item_bytes,
        "collection_totals": {
            "seal_path": 1,
            "covered_event_digests": 2,
            "control_state": 2,
            "frontier_events": 2,
        },
        "max_response_bytes": 4194304,
        "max_total_item_bytes": 268435456,
        "max_items_per_chunk": {
            "seal_path": 128,
            "covered_event_digests": 8192,
            "control_state": 1024,
            "frontier_events": 32,
        },
    }
    response_header = {
        "bundle_version": 1,
        "proof_request_digest": proof_request_digest,
        "materialization_profile": "complete_control_state_v1",
        "realm_id": realm_id,
        "effective_scope": deepcopy(effective_scope),
        "reducer_profile": governance_binding["reducer_profile"],
        "trusted_anchor_seal_id": seal_id,
        "accepted_seal_id": seal_id,
        "chunk_manifest": manifest,
    }
    bundle_digest = wire_digest(BUNDLE_DOMAIN + canonical_bytes(response_header))
    responses = [
        {**deepcopy(response_header), "bundle_digest": bundle_digest, "chunk": deepcopy(chunk)}
        for chunk in chunks
    ]
    requests = []
    for index in range(4):
        request = {**deepcopy(proof_identity), "chunk_index": index}
        if index:
            request["expected_bundle_digest"] = bundle_digest
        requests.append(request)

    unknown_seal = "ak:seal:sha256:" + "f0" * 32
    extra_digest = "sha256:" + "f1" * 32
    extra_event_id = fixture_derived_id("event", "extra-frontier-event")
    verifier_cases = [
        {
            "name": "valid_complete_bundle",
            "mutation": {"operation": "none", "parameters": {}, "recommit": "none"},
            "expected": {
                "decision": "accept_epoch",
                "failure_stage": None,
                "reason_code": None,
                "verified_bundle_persisted": True,
                "epoch_advanced": True,
                "verified_bundle_digest": bundle_digest,
            },
        },
        mutation_case("self_reported_anchor_is_not_trust", "replace_anchor", "anchor_trust", "state_mismatch", parameters={"seal_id": unknown_seal}),
        mutation_case("broken_seal_path", "break_seal_path", "seal_path", "state_mismatch"),
        mutation_case("forked_seal_path", "fork_seal_path", "seal_path", "state_mismatch"),
        mutation_case("wrong_notary_authority", "replace_notary_method", "seal_authority", "signature_invalid"),
        mutation_case("missing_covered_digest", "remove_collection_item", "covered_set", "state_mismatch", parameters={"collection": "covered_event_digests", "index": 0}),
        mutation_case("extra_covered_digest", "append_collection_item", "covered_set", "state_mismatch", parameters={"collection": "covered_event_digests", "value": extra_digest}),
        mutation_case("duplicate_covered_digest", "duplicate_collection_item", "covered_set", "state_mismatch", parameters={"collection": "covered_event_digests", "index": 0}),
        mutation_case("covered_digest_order", "reverse_collection", "covered_set", "state_mismatch", parameters={"collection": "covered_event_digests"}),
        mutation_case("missing_state_leaf", "remove_collection_item", "state_root", "state_mismatch", parameters={"collection": "control_state", "index": 0}),
        mutation_case("extra_state_leaf", "append_state_leaf", "state_root", "state_mismatch"),
        mutation_case("duplicate_state_leaf", "duplicate_collection_item", "state_root", "state_mismatch", parameters={"collection": "control_state", "index": 0}),
        mutation_case("state_leaf_order", "reverse_collection", "state_root", "state_mismatch", parameters={"collection": "control_state"}),
        mutation_case("missing_frontier_event", "remove_collection_item", "membership_frontier", "state_mismatch", parameters={"collection": "frontier_events", "index": 0}),
        mutation_case("extra_frontier_event", "append_frontier_event", "membership_frontier", "state_mismatch", parameters={"event_id": extra_event_id}),
        mutation_case("duplicate_frontier_event", "duplicate_collection_item", "membership_frontier", "state_mismatch", parameters={"collection": "frontier_events", "index": 0}),
        mutation_case("frontier_event_order", "reverse_collection", "membership_frontier", "state_mismatch", parameters={"collection": "frontier_events"}),
        mutation_case("frontier_cross_realm_scope", "replace_frontier_effective_scope", "membership_frontier", "state_mismatch", parameters={"realm_id": fixture_derived_id("realm", "foreign-governance-realm")}),
        mutation_case("frontier_event_proof_invalid", "flip_frontier_signature_bit", "membership_frontier", "signature_invalid"),
        mutation_case("chunks_root_mismatch", "flip_chunks_root_bit", "chunk_commitment", "digest_mismatch", recommit="none"),
        mutation_case("missing_chunk", "remove_chunk", "chunk_sequence", "state_mismatch", parameters={"chunk_index": 2}, recommit="none"),
        mutation_case("duplicate_chunk", "duplicate_chunk", "chunk_sequence", "state_mismatch", parameters={"chunk_index": 1}, recommit="none"),
        mutation_case("chunk_order", "swap_chunks", "chunk_sequence", "state_mismatch", parameters={"left": 1, "right": 2}, recommit="none"),
        mutation_case("binding_realm_mismatch", "replace_binding_realm", "binding", "governance_binding_mismatch"),
        mutation_case("binding_group_mismatch", "replace_binding_group", "binding", "governance_binding_mismatch"),
        mutation_case("binding_previous_epoch_mismatch", "replace_binding_previous_epoch", "binding", "governance_binding_mismatch"),
        mutation_case("binding_next_epoch_mismatch", "replace_binding_next_epoch", "binding", "governance_binding_mismatch"),
        mutation_case("binding_profile_mismatch", "replace_binding_profile", "binding", "profile_unsupported"),
        mutation_case("binding_reducer_mismatch", "replace_binding_reducer", "binding", "profile_unsupported"),
        mutation_case("security_frontier_digest_mismatch", "replace_security_frontier_digest", "security_frontier", "governance_binding_mismatch"),
        mutation_case("unrelated_capability_does_not_change_frontier", "append_unrelated_capability", "security_frontier", "unexpected_frontier_change"),
        mutation_case("active_leaf_revoke_missing_from_frontier", "remove_active_leaf_revoke", "security_frontier", "governance_binding_mismatch"),
    ]
    materializer_cases = [
        materializer_case("valid_materialization", "none", None),
        materializer_case("unknown_anchor", "replace_request_anchor", "mls_governance_anchor_unreachable", parameters={"seal_id": unknown_seal}),
        materializer_case("unreachable_anchor", "detach_anchor_from_ancestry", "mls_governance_anchor_unreachable"),
        materializer_case("missing_seal_material", "remove_accepted_seal", "frontier_unavailable"),
        materializer_case("forked_seal_source", "fork_accepted_seal", "state_mismatch"),
        materializer_case("unauthorized_notary_source", "revoke_notary_before_sealed_at", "signature_invalid"),
        materializer_case("missing_covered_event_source", "remove_covered_event", "state_mismatch"),
        materializer_case("bottom_control_cell_source", "insert_bottom_diagnostic", "failed_bottom"),
        materializer_case("scope_visibility_denied", "deny_scope_visibility", "not_found"),
        materializer_case("logical_bundle_over_bound", "delegate_companion_limit_plus_one", "mls_governance_proof_bounds_exceeded"),
    ]

    return {
        "profile": "ak.profile.mls_governance_binding.full.v1",
        "version": "2026-08-02",
        "suite": "mls_governance_proof_bundle",
        "generated_by": "tools/generate_mls_governance_proof_fixture.py",
        "runner": {
            "kind": "named_suite",
            "entrypoint": "ak.suite.mls.governance_proof_bundle.v1",
        },
        "consumer_contracts": [
            {
                "role": "sdk_proof_verifier",
                "entrypoint": "ak.suite.mls.governance_proof_bundle.verify.v1",
                "inputs": ["trust_context", "commit_context", "expected_acquisition", "verifier_cases"],
                "required_output_fields": [
                    "case_name",
                    "schema_result",
                    "decision",
                    "failure_stage",
                    "reason_code",
                    "verified_bundle_digest",
                    "epoch_advanced",
                ],
            },
            {
                "role": "server_materializer",
                "entrypoint": "ak.suite.mls.governance_proof_bundle.materialize.v1",
                "inputs": ["source_state", "requests", "materializer_cases"],
                "required_output_fields": [
                    "case_name",
                    "decision",
                    "error_code",
                    "response_count",
                    "bundle_digest",
                    "chunk_digests",
                    "peak_buffer_bytes",
                    "partial_manifest_emitted",
                ],
            },
        ],
        "covers_vectors": [
            "ak.vector.mls.governance_proof.verifier.v1",
            "ak.vector.mls.governance_proof.materializer.v1",
        ],
        "required_companion_vectors": [
            "ak.vector.scalability.mls_governance_proof_bounds.v1"
        ],
        "schema_ref": "../schemas/mls-governance-proof-bundle.schema.json",
        "trust_context": {
            "trusted_anchor_seal_ids": [seal_id],
            "authorized_notary_methods": [notary_vm],
            "verification_keys": {
                actor_vm: public_jwk(actor_key, actor_vm),
                notary_vm: public_jwk(notary_key, notary_vm),
            },
            "verification_time": "2026-07-15T00:00:03.000Z",
        },
        "commit_context": {
            "transcript_authenticated_governance_binding": governance_binding,
            "expected_realm_id": realm_id,
            "expected_effective_scope": effective_scope,
            "expected_mls_group_id": governance_binding["mls_group_id"],
            "expected_previous_epoch": 41,
            "expected_next_epoch": 42,
            "expected_binding_profile": governance_binding["binding_profile"],
            "expected_reducer_profile": governance_binding["reducer_profile"],
            "current_or_pending_mls_leaf_entries": mls_leaf_entries,
            "mls_leaf_set_digest": mls_leaf_set_digest,
        },
        "source_state": {
            "proof_identity": proof_identity,
            "accepted_seals": [seal],
            "covered_events": [row[0] for row in event_rows],
            "joined_control_state": control_state,
            "bottom_diagnostics": [],
            "scope_visibility": "authorized",
        },
        "requests": requests,
        "expected_acquisition": {
            "responses": responses,
            "accept_only_after_response_count": 4,
            "cache_keys": {
                "acquisition_index": [proof_request_digest, seal_id],
                "manifest": bundle_digest,
                "chunks": [chunk["chunk_digest"] for chunk in chunks],
                "forbidden_bundle_key": seal_id,
            },
        },
        "known_answer": {
            "empty_sha256_root": EMPTY_SHA256,
            "event_steps": [row[2]["kat"] for row in event_rows],
            "control_event_set_root": control_event_set_root,
            "state_leaf_canonical_bytes": [len(canonical_bytes(value)) for value in control_state],
            "state_root": state_root,
            "completeness_leaf_canonical_bytes": len(canonical_bytes(completeness_leaf)),
            "completeness_root": completeness_root,
            "security_frontier_input_canonical_bytes": len(canonical_bytes(security_frontier_input)),
            "security_frontier_cell_entries": security_frontier_cell_entries,
            "mls_leaf_set_digest": mls_leaf_set_digest,
            "security_frontier_digest": security_frontier_digest,
            "seal_canonical_bytes": len(canonical_bytes(seal_body)),
            "seal_digest": seal_digest,
            "proof_identity_canonical_bytes": len(canonical_bytes(proof_identity)),
            "proof_request_digest": proof_request_digest,
            "chunk_canonical_bytes": [
                len(
                    canonical_bytes(
                        {
                            "chunk_index": chunk["chunk_index"],
                            "collection": chunk["collection"],
                            "start_index": chunk["start_index"],
                            "items": chunk["items"],
                        }
                    )
                )
                for chunk in chunks
            ],
            "chunk_digests": [chunk["chunk_digest"] for chunk in chunks],
            "chunks_root": chunks_root,
            "total_item_bytes": total_item_bytes,
            "bundle_header_canonical_bytes": len(canonical_bytes(response_header)),
            "bundle_digest": bundle_digest,
        },
        "verifier_cases": verifier_cases,
        "materializer_cases": materializer_cases,
        "runner_rules": [
            "Each response MUST pass the proof Bundle schema before semantic verification.",
            "A verifier mutation with recommit=transport rebuilds chunk digests, proofs, chunks_root, manifest totals and bundle_digest so the named semantic stage, rather than stale transport bytes, is exercised.",
            "A verifier mutation with recommit=none preserves the original commitments and MUST fail at the transport stage.",
            "The materializer MUST reproduce every known-answer digest and all four response objects byte-for-byte after canonicalization.",
            "No reject case may persist a verified Bundle, advance the MLS epoch, or emit a partial manifest.",
            "The two required companion limit matrices MUST run in the same profile certification job; generated limit+1 cases MUST NOT allocate from declared sizes.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail when the checked-in fixture is stale")
    args = parser.parse_args()
    rendered = json.dumps(build_fixture(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != rendered:
            print(f"stale generated fixture: {OUTPUT.relative_to(ROOT)}")
            return 1
        print(f"generated fixture is current: {OUTPUT.relative_to(ROOT)}")
        return 0
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
