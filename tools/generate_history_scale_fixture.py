#!/usr/bin/env python3
"""Generate direct-traversal history recovery KATs and bounded scale recipes."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import hmac
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "spec/v1/artifacts/schemas"
REGISTRY_DIR = ROOT / "spec/v1/artifacts/registry"
OUTPUT = ROOT / "spec/v1/artifacts/fixtures/history-key-recovery-fixture.json"

ZERO = b"\x00"
TRAVERSAL_INTENT_DOMAIN = b"ak.history-governance-traversal-intent-v1"
AVAILABILITY_BYTES_DOMAIN = b"ak.availability_event_bytes.v1"
SOURCE_AGENT_OBSERVATION_DOMAIN = b"ak.history-source-agent-observation-v1"
ARCHIVE_REPLICA_DOMAIN = b"ak.organization-recovery-archive-replica-v1"
MAX_REQUEST_EPOCHS = 65_536

SERVICE_DID = "did:key:z6MkfixtureService"
SERVICE_CORE = "ak:did_core:key:z6MkfixtureService"
SERVICE_ACTOR = {"kind": "service", "service_id": SERVICE_CORE}
SERVICE_METHOD = SERVICE_DID + "#key-1"
EXPIRES = "2026-08-28T00:00:00.000Z"


def jcs(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def domain_digest(domain: bytes, value: Any) -> str:
    return sha256(domain + ZERO + jcs(value))


def b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac.new(salt or b"\x00" * 32, ikm, hashlib.sha256).digest()


def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    output = b""
    block = b""
    counter = 1
    while len(output) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        output += block
        counter += 1
    return output[:length]


def hpke_labeled_extract(suite_id: bytes, salt: bytes, label: bytes, ikm: bytes) -> bytes:
    return hkdf_extract(salt, b"HPKE-v1" + suite_id + label + ikm)


def hpke_labeled_expand(
    suite_id: bytes, prk: bytes, label: bytes, info: bytes, length: int
) -> bytes:
    labeled_info = length.to_bytes(2, "big") + b"HPKE-v1" + suite_id + label + info
    return hkdf_expand(prk, labeled_info, length)


def detached_jws(
    key: Ed25519PrivateKey,
    context: str,
    unsigned: dict[str, Any],
    binding_fields: list[str],
    verification_method: str,
    created_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload_digest = sha256(jcs(unsigned))
    binding = {
        "context": context,
        "payload_digest": payload_digest,
        **{field: unsigned[field] for field in binding_fields},
        "verification_method": verification_method,
        "created_at": created_at,
    }
    protected = b64u(jcs({"alg": "Ed25519"}))
    payload = b64u(jcs(binding))
    signature = key.sign((protected + "." + payload).encode("ascii"))
    proof = {
        "kind": "detached_jws",
        "verification_method": verification_method,
        "payload_digest": payload_digest,
        "created_at": created_at,
        "jws": protected + ".." + b64u(signature),
    }
    transcript = {
        "context": context,
        "unsigned_jcs_b64u": b64u(jcs(unsigned)),
        "payload_digest": payload_digest,
        "binding_jcs_b64u": b64u(jcs(binding)),
        "detached_payload_b64u": payload,
        "signing_input_ascii": protected + "." + payload,
    }
    return proof, transcript


def event_id(label: str) -> str:
    return "ak:event:" + b64u(b"\x01" + hashlib.sha256(label.encode("utf-8")).digest())


REALM = "ak:realm:" + event_id("history-scale-realm-create").split(":", 2)[2]
CIRCLE = "ak:circle:" + event_id("history-circle-scope-create").split(":", 2)[2]
GROUP = b64u(REALM.encode("utf-8"))


def seal_ref(label: str | int) -> str:
    return "ak:seal:sha256:" + hashlib.sha256(str(label).encode("utf-8")).hexdigest()


def digest_marker(byte: int) -> str:
    return "sha256:" + f"{byte:02x}" * 32


def basis(*leaves: str) -> dict[str, Any]:
    return {"leaves": sorted(leaves)}


class SchemaSet:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}
        for path in SCHEMA_DIR.glob("*.json"):
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and isinstance(value.get("$id"), str):
                self.store[value["$id"]] = value

    def validator(self, filename: str, definition: str | None = None) -> Draft202012Validator:
        schema = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        target = schema
        if definition is not None:
            target = {
                "$schema": schema["$schema"],
                "$id": schema["$id"],
                "$defs": schema["$defs"],
                "$ref": f"#/$defs/{definition}",
            }
        resolver = RefResolver(base_uri=schema["$id"], referrer=target, store=self.store)
        return Draft202012Validator(target, resolver=resolver)


def build_signer_evidence(schemas: SchemaSet) -> dict[str, Any]:
    history_head = "did-key-head-fixture"
    version_id = "did-key-v1"
    normalized_document = {
        "did": SERVICE_DID,
        "contexts": ["https://www.w3.org/ns/did/v1"],
        "controller_dids": [],
        "also_known_as": [],
        "verification_methods": [
            {
                "verification_method": SERVICE_METHOD,
                "controller_did": SERVICE_DID,
                "verification_method_suite": "Multikey",
                "public_key_material": {"publicKeyMultibase": "z6MkfixtureService"},
                "extensions": [],
            }
        ],
        "authentication": [{"verification_method": SERVICE_METHOD}],
        "assertion_methods": [{"verification_method": SERVICE_METHOD}],
        "key_agreements": [],
        "capability_invocations": [],
        "capability_delegations": [],
        "services": [],
        "metadata": {},
        "extensions": [],
    }
    evidence = {
        "kind": "service",
        "signer_id": SERVICE_CORE,
        "verification_method": SERVICE_METHOD,
        "authenticated_resolution": {
            "service_id": SERVICE_CORE,
            "service_kind": "station",
            "method_history_evidence": {
                "evidence_kind": "did_key_expansion",
                "boundary": {
                    "from_method_history_head": history_head,
                    "from_version_id": version_id,
                    "to_method_history_head": history_head,
                    "to_version_id": version_id,
                },
                "evidence": {
                    "kind": "ak.did.binding_evidence.v1",
                    "method": "key",
                    "document_digest": digest_marker(0x42),
                    "method_proofs": [],
                },
            },
            "normalized_did_document": normalized_document,
        },
    }
    schemas.validator("authenticated-signer-resolution-evidence.schema.json").validate(evidence)
    evidence_digest = sha256(jcs(evidence))
    return {
        "evidence": evidence,
        "evidence_ref": "ak:signer_evidence:" + evidence_digest,
        "evidence_digest": evidence_digest,
        "canonical_bytes": len(jcs(evidence)),
    }


def detached_proof(payload_digest: str) -> dict[str, Any]:
    return {
        "kind": "detached_jws",
        "verification_method": SERVICE_METHOD,
        "payload_digest": payload_digest,
        "created_at": "2026-08-21T00:00:00.000Z",
        "jws": "e30..c2ln",
    }


def build_dependency_kat(schemas: SchemaSet, signer: dict[str, Any]) -> dict[str, Any]:
    accepted_event = {
        "event_id": event_id("availability-event"),
        "actor_kind": "principal",
        "proofs": [{"kind": "producer_event", "event_digest": digest_marker(0x51)}],
    }
    bytes_digest = sha256(AVAILABILITY_BYTES_DOMAIN + ZERO + jcs(accepted_event))
    receipt_core = {
        "realm_id": REALM,
        "event_id": accepted_event["event_id"],
        "bytes_digest": bytes_digest,
        "holder_service_id": SERVICE_CORE,
        "retention_expires_at": EXPIRES,
        "holder_signer_evidence_ref": signer["evidence_ref"],
    }
    receipt = {**receipt_core, "signature": detached_proof(sha256(jcs(receipt_core)))}
    receipt_digest = sha256(jcs(receipt))
    schemas.validator("availability-receipt.schema.json").validate(receipt)

    rows = [
        {
            "selector": {"kind": "availability_receipt", "content_digest": receipt_digest},
            "availability_receipt": receipt,
        },
        {
            "selector": {
                "kind": "authenticated_signer_resolution_evidence",
                "content_digest": signer["evidence_digest"],
            },
            "authenticated_signer_resolution_evidence": signer["evidence"],
        },
    ]
    rows.sort(key=lambda row: (row["selector"]["kind"].encode("utf-8"), jcs(row["selector"])))
    outcome = {"items": rows, "missing_selectors": []}
    schemas.validator("service-operation-dtos.schema.json", "GovernanceDependencyResolveOutcome").validate(outcome)
    return {
        "accepted_event_without_unsigned": accepted_event,
        "availability_event_bytes_digest": bytes_digest,
        "availability_receipt": receipt,
        "availability_receipt_digest": receipt_digest,
        "resolve_outcome": outcome,
        "negative_cases": [
            {
                "name": "selector_branch_mismatch",
                "mutation": "pair an authenticated_signer_resolution_evidence selector with availability_receipt",
                "expected": "schema_violation",
            },
            {
                "name": "signer_evidence_digest_mismatch",
                "mutation": "change complete signer evidence while preserving selector.content_digest",
                "expected": "dependency_missing",
            },
        ],
    }


def traversal_case() -> dict[str, Any]:
    base_a, base_b = seal_ref("base-a"), seal_ref("base-b")
    middle_a, middle_b = seal_ref("middle-a"), seal_ref("middle-b")
    target_a, target_b = seal_ref("target-a"), seal_ref("target-b")
    return {
        "trusted_history_base_basis": basis(base_a, base_b),
        "trusted_current_basis": basis(middle_a, middle_b),
        "target_basis": basis(target_a, target_b),
        "seals": [
            {"seal_ref": base_a, "predecessor_refs": [], "delta_event_refs": [event_id("base-a-create")]},
            {"seal_ref": base_b, "predecessor_refs": [], "delta_event_refs": [event_id("base-b-create")]},
            {"seal_ref": middle_a, "predecessor_refs": [base_a], "delta_event_refs": [event_id("epoch-0")]},
            {"seal_ref": middle_b, "predecessor_refs": [base_b], "delta_event_refs": [event_id("member-join")]},
            {"seal_ref": target_a, "predecessor_refs": [middle_a], "delta_event_refs": [event_id("epoch-1")]},
            {"seal_ref": target_b, "predecessor_refs": [middle_b], "delta_event_refs": [event_id("policy-ratchet")]},
        ],
    }


def traversal_errors(case: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    by_ref: dict[str, dict[str, Any]] = {}
    for row in case.get("seals", []):
        ref = row.get("seal_ref")
        if ref in by_ref:
            errors.append("duplicate_seal_descriptor")
        elif isinstance(ref, str):
            by_ref[ref] = row
    base = set(case["trusted_history_base_basis"]["leaves"])
    current = set(case["trusted_current_basis"]["leaves"])
    target = set(case["target_basis"]["leaves"])
    visited: set[str] = set()
    consumed_base: set[str] = set()
    queue = list(sorted(target))
    while queue:
        ref = queue.pop()
        if ref in visited:
            continue
        visited.add(ref)
        row = by_ref.get(ref)
        if row is None:
            errors.append("dependency_missing")
            continue
        if ref in base:
            consumed_base.add(ref)
            continue
        predecessors = row.get("predecessor_refs", [])
        if not predecessors:
            errors.append("interval_stops_before_base")
        queue.extend(predecessors)
    if consumed_base != base:
        errors.append("base_leaf_not_consumed")
    if not current.issubset(visited):
        errors.append("trusted_current_not_dominated")
    if set(by_ref) != visited:
        errors.append("surplus_descriptor")
    control_refs = [event for ref in visited for event in by_ref.get(ref, {}).get("delta_event_refs", [])]
    if len(control_refs) != len(set(control_refs)):
        errors.append("duplicate_control_event")
    return sorted(set(errors))


def traversal_negative_cases(case: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def run(name: str, expected: str, mutation: Any) -> None:
        value = copy.deepcopy(case)
        mutation(value)
        actual = traversal_errors(value)
        if expected not in actual:
            raise AssertionError(f"direct traversal negative {name} missed {expected}: {actual}")
        results.append({"name": name, "expected_error": expected, "actual_errors": actual})

    run("hidden_predecessor", "dependency_missing", lambda value: value["seals"].pop(2))
    run(
        "target_does_not_dominate_current",
        "trusted_current_not_dominated",
        lambda value: value.__setitem__("trusted_current_basis", basis(seal_ref("concurrent"))),
    )
    run(
        "branch_stops_before_base",
        "interval_stops_before_base",
        lambda value: value["seals"][-1].__setitem__("predecessor_refs", []),
    )
    run(
        "base_leaf_not_consumed",
        "base_leaf_not_consumed",
        lambda value: value.__setitem__(
            "trusted_history_base_basis",
            basis(*value["trusted_history_base_basis"]["leaves"], seal_ref("unused-base")),
        ),
    )
    run(
        "surplus_descriptor",
        "surplus_descriptor",
        lambda value: value["seals"].append(
            {"seal_ref": seal_ref("surplus"), "predecessor_refs": [], "delta_event_refs": []}
        ),
    )
    return results


def build_traversal_replay_kat() -> dict[str, Any]:
    """Build the deterministic two-Seal replay KAT inputs.

    The Event and Seal canonical bytes are constructed by the shared SDK at
    run time.  Keeping only the fixed signing inputs and expected historical
    descriptor here makes the vector small without turning it into a prose-only
    assertion.  The two different Event variants deliberately share a claimed
    digest; this is a symbolic resolver-ingestion collision, not a generated
    SHA-256 collision.
    """
    actor_did = "did:web:replay-kat.example"
    actor_id = "ak:did_core:web:replay-kat.example"
    notary_actor_id = {"kind": "service", "service_id": actor_id}
    verification_method = actor_did + "#notary-key-1"
    historical_public_key_b64u = "0EqyMnQrtKs6E2i9RhXk5tAiSrcaAWuvhSCjMsl3hzc"
    current_public_key_b64u = "oJql9HpnWYAv-VX43C0qFKXJnSO-l_hkEn_5ODRVpPA"
    historical_descriptor = {
        "actor_id": notary_actor_id,
        "verification_method": verification_method,
        "key_kind": "ed25519_raw32",
        "jose_algorithm": "Ed25519",
        "frozen_public_key_b64u": historical_public_key_b64u,
        "frozen_public_key_digest": "sha256:10ba682c8ad13513971e8b56881aab8bd702bb807796eca81932c735a94d6e6d",
    }
    current_descriptor = {
        **historical_descriptor,
        "frozen_public_key_b64u": current_public_key_b64u,
        "frozen_public_key_digest": "sha256:1325b850c2871916eae203f0efc3c8987f64e5e3cdb27679e6d1fa97808357e6",
    }
    return {
        "version": "2026-08-31",
        "digest_suite": "sha256",
        "topology": {
            "seal_count": 2,
            "shape": "genesis_then_successor",
            "trusted_history_base": "genesis",
            "trusted_current": "genesis",
            "target": "successor",
        },
        "signing_inputs": {
            "actor_did": actor_did,
            "actor_id": actor_id,
            "verification_method": verification_method,
            "historical_seed_b64u": b64u(b"\x11" * 32),
            "current_seed_b64u": b64u(b"\x22" * 32),
            "historical_descriptor": historical_descriptor,
            "current_same_method_descriptor": current_descriptor,
        },
        "cases": [
            {
                "name": "historical_frozen_notary_signature_positive",
                "successor_signature_key": "historical",
                "expected": "verified",
                "expected_replayed_seal_count": 2,
                "expected_committed_successor_count": 1,
                "expected_notary_projection": historical_descriptor,
            },
            {
                "name": "ambiguous_delta_resolver_response",
                "injection": {
                    "claimed_digest": digest_marker(0xA7),
                    "variant_a_content_mutation": "payload.variant=a",
                    "variant_b_content_mutation": "payload.variant=b",
                    "real_hash_collision_claimed": False,
                },
                "expected": "material_rejected_before_variant_selection",
                "expected_replayed_seal_count": 0,
                "expected_committed_successor_count": 0,
            },
            {
                "name": "current_key_same_method_substitution",
                "successor_signature_key": "current",
                "expected": "signature_rejected_against_predecessor_frozen_key",
                "expected_method_id_equal": True,
                "expected_public_key_bytes_equal": False,
                "expected_committed_successor_count": 0,
                "predecessor_replay_may_have_occurred": True,
            },
        ],
        "wire_reason_code": None,
        "late_collision_policy_vector": "ak.vector.cbs_lattice.sealed_control_move_full_digest_collision.v1",
        "data_events_in_delta": False,
    }


def ratchet_outcome(current: str | None, proposed: str) -> str:
    if current is None and proposed in {"since_join", "all_history_for_current_members"}:
        return "accepted_create"
    if current == proposed:
        return "duplicate_noop"
    if current == "all_history_for_current_members" and proposed == "since_join":
        return "accepted_narrow"
    return "failed_precondition"


def build_traversal_kat(schemas: SchemaSet) -> dict[str, Any]:
    case = traversal_case()
    if traversal_errors(case):
        raise AssertionError(f"positive traversal case failed: {traversal_errors(case)}")
    intent = {
        "kind": "ak.history_governance.traversal_intent",
        "profile": "member_history_delivery",
        "effective_scope": {"kind": "realm", "realm_id": REALM},
        "mls_group_id": GROUP,
        "trusted_history_base_basis": case["trusted_history_base_basis"],
        "trusted_current_basis": case["trusted_current_basis"],
        "target_basis": case["target_basis"],
        "request_digest": digest_marker(0x61),
        "requested_ranges": [{"from_epoch": 0, "to_epoch": 1}],
        "authorization_incarnation": {
            "kind": "realm",
            "realm_membership_incarnation_ref": event_id("member-incarnation"),
        },
        "retention": {"kind": "request_expiring", "expires_at": EXPIRES},
    }
    retention = {
        "traversal_intent": intent,
        "traversal_intent_digest": domain_digest(TRAVERSAL_INTENT_DOMAIN, intent),
    }
    schemas.validator("history-key.schema.json", "history_governance_traversal_intent").validate(intent)
    schemas.validator("history-key.schema.json", "history_governance_traversal_retention").validate(retention)

    rhrk_intent = {
        "kind": "ak.history_governance.traversal_intent",
        "profile": "organization_recovery_archive",
        "effective_scope": {"kind": "realm", "realm_id": REALM},
        "mls_group_id": GROUP,
        "trusted_history_base_basis": case["trusted_history_base_basis"],
        "trusted_current_basis": case["trusted_current_basis"],
        "target_basis": case["target_basis"],
        "requested_ranges": [{"from_epoch": 1, "to_epoch": 1}],
        "archive_authorization_tuple": {
            "recovery_key_id": "ak:recovery_key:019c0000-0000-7000-8000-000000000001",
            "key_agreement_ref": SERVICE_DID + "#x25519-1",
            "method_controller_principal_id": SERVICE_CORE,
            "holder_service_id": SERVICE_CORE,
            "holder_signing_ref": SERVICE_METHOD,
            "accepted_key_evidence_ref": event_id("accepted-key-evidence"),
            "holder_trusted_basis": case["trusted_history_base_basis"],
        },
        "container_event_ref": event_id("archive-container"),
        "retention": {"kind": "archive_lifetime"},
    }
    schemas.validator("history-key.schema.json", "history_governance_traversal_intent").validate(rhrk_intent)
    invalid_rhrk = copy.deepcopy(rhrk_intent)
    invalid_rhrk["requested_ranges"].append({"from_epoch": 2, "to_epoch": 2})
    rhrk_error_count = len(
        list(schemas.validator("history-key.schema.json", "history_governance_traversal_intent").iter_errors(invalid_rhrk))
    )
    if rhrk_error_count == 0:
        raise AssertionError("RHRK multi-range negative unexpectedly schema-valid")
    request_base = {
        "request_id": "ak:history_request:019c0000-0000-7000-8000-000000000001",
        "kind": "ak.history_key.request",
        "effective_scope": {"kind": "realm", "realm_id": REALM},
        "requester_actor_id": SERVICE_ACTOR,
        "requester_sender_domain": SERVICE_DID,
        "requester_authorization_incarnation": intent["authorization_incarnation"],
        "trusted_history_base_basis": case["trusted_history_base_basis"],
        "trusted_current_basis": case["trusted_current_basis"],
        "requested_ranges": [{"from_epoch": 0, "to_epoch": 1}],
        "recipient_hpke_public_key": b64u(b"\x77" * 32),
        "expires_at": EXPIRES,
    }
    endpoint_cases = [
        {
            "profile": "ordinary_human",
            "endpoint": {
                "kind": "ordinary_human",
                "requester_device_id": "ak:device:019c0000-0000-7000-8000-000000000001",
                "requester_device_authorize_event_id": event_id("requester-device-authorize"),
                "requester_device_generation_ref": 7,
            },
        },
        {
            "profile": "agent",
            "endpoint": {
                "kind": "agent",
                "requester_agent_id": SERVICE_CORE,
                "requester_agent_verification_method": SERVICE_METHOD,
                "requester_agent_key_authorize_event_id": event_id("requester-agent-authorize"),
            },
        },
        {
            "profile": "minimal_metadata",
            "endpoint": {"kind": "minimal_metadata"},
        },
    ]
    request_validator = schemas.validator("history-key.schema.json", "history_key_request_signing_input")
    for endpoint_case in endpoint_cases:
        candidate = {
            **request_base,
            "requester_author_profile": endpoint_case["profile"],
            "requester_endpoint_authorization": endpoint_case["endpoint"],
        }
        request_validator.validate(candidate)
    mismatched_endpoint = {
        **request_base,
        "requester_author_profile": "ordinary_human",
        "requester_endpoint_authorization": {"kind": "minimal_metadata"},
    }
    endpoint_mismatch_error_count = len(list(request_validator.iter_errors(mismatched_endpoint)))
    if endpoint_mismatch_error_count == 0:
        raise AssertionError("history requester endpoint/profile mismatch unexpectedly schema-valid")
    return {
        "member_retention": retention,
        "direct_cut": case,
        "negative_cases": traversal_negative_cases(case),
        "history_access_ratchet": [
            {"from": None, "to": "all_history_for_current_members", "actual": ratchet_outcome(None, "all_history_for_current_members")},
            {"from": "all_history_for_current_members", "to": "since_join", "actual": ratchet_outcome("all_history_for_current_members", "since_join")},
            {"from": "since_join", "to": "since_join", "actual": ratchet_outcome("since_join", "since_join")},
            {"from": "since_join", "to": "all_history_for_current_members", "actual": ratchet_outcome("since_join", "all_history_for_current_members")},
        ],
        "requester_endpoint_authorization": {
            "positive_cases": endpoint_cases,
            "profile_mismatch_negative": {
                "expected": "schema_violation",
                "actual_error_count": endpoint_mismatch_error_count,
            },
            "t1_rule": "resolve the exact requester-signed endpoint locator at first enqueue; never substitute the current session endpoint",
        },
        "since_join_lineage": {
            "membership_incarnation_ref": intent["authorization_incarnation"]["realm_membership_incarnation_ref"],
            "add_proposal_ref": event_id("requester-winning-add-proposal"),
            "add_target_authorization_incarnation": intent["authorization_incarnation"],
            "winning_commit_ref": event_id("requester-winning-add-commit"),
            "winning_commit_proposal_refs": [event_id("requester-winning-add-proposal")],
            "winning_commit_next_epoch": 1,
            "expected_join_epoch": 1,
            "forbidden_derivations": ["joined_at", "received_at", "latest_epoch", "current_session_device"],
        },
        "organization_recovery_intent": rhrk_intent,
        "rhrk_non_singleton_negative": {
            "expected": "schema_violation",
            "actual_error_count": rhrk_error_count,
        },
    }


def checked_epoch_budget(epoch_count: int, journal: dict[str, int]) -> None:
    if epoch_count < 1 or epoch_count > MAX_REQUEST_EPOCHS:
        if journal != {"journal_rows": 0, "resolved_objects": 0, "outbox_writes": 0}:
            raise AssertionError("epoch budget was checked after a side effect")
        raise ValueError(f"max_total_requested_epochs exceeded: {epoch_count}>{MAX_REQUEST_EPOCHS}")


def build_scale_recipe(epoch_count: int, journal: dict[str, int] | None = None) -> dict[str, Any]:
    probe = journal if journal is not None else {
        "journal_rows": 0,
        "resolved_objects": 0,
        "outbox_writes": 0,
    }
    checked_epoch_budget(epoch_count, probe)
    rolling = b"\x00" * 32
    canonical_bytes = 0
    max_live = 0
    with tempfile.TemporaryDirectory(prefix="arkret-history-traversal-") as directory:
        db = sqlite3.connect(Path(directory) / "traversal.sqlite3")
        db.execute("CREATE TABLE queue(epoch INTEGER PRIMARY KEY)")
        db.execute("CREATE TABLE visited(epoch INTEGER PRIMARY KEY)")
        db.execute("INSERT INTO queue(epoch) VALUES(?)", (epoch_count,))
        probe["journal_rows"] += 1
        while True:
            row = db.execute("SELECT epoch FROM queue ORDER BY epoch DESC LIMIT 1").fetchone()
            if row is None:
                break
            epoch = int(row[0])
            db.execute("DELETE FROM queue WHERE epoch=?", (epoch,))
            if db.execute("SELECT 1 FROM visited WHERE epoch=?", (epoch,)).fetchone() is not None:
                continue
            db.execute("INSERT INTO visited(epoch) VALUES(?)", (epoch,))
            descriptor = {
                "seal_ref": seal_ref(epoch),
                "predecessor_refs": [] if epoch == 0 else [seal_ref(epoch - 1)],
                "delta_control_event_refs": [] if epoch == 0 else [event_id(f"epoch-{epoch - 1}")],
            }
            raw = jcs(descriptor)
            rolling = hashlib.sha256(rolling + raw).digest()
            canonical_bytes += len(raw)
            max_live = max(max_live, len(raw))
            probe["journal_rows"] += 1
            probe["resolved_objects"] += 1 + (0 if epoch == 0 else 2)
            if epoch > 0:
                db.execute("INSERT OR IGNORE INTO queue(epoch) VALUES(?)", (epoch - 1,))
                probe["journal_rows"] += 1
        visited = int(db.execute("SELECT COUNT(*) FROM visited").fetchone()[0])
        db.close()
    return {
        "epoch_count": epoch_count,
        "verified_epoch_count": epoch_count,
        "visited_seal_count": visited,
        "resolved_control_event_count": epoch_count,
        "resolved_availability_receipt_count": epoch_count,
        "registry_snapshot_count": 1,
        "signer_evidence_distinct_count": 2,
        "streaming_storage": "temporary_sqlite_work_queue_and_visited",
        "max_live_descriptor_bytes": max_live,
        "descriptor_canonical_bytes": canonical_bytes,
        "descriptor_stream_aggregate_digest": "sha256:" + rolling.hex(),
        "journal_rows_written": probe["journal_rows"],
        "outbox_write_count": probe["outbox_writes"],
    }


def build_source_agent_observation_digest_kat(schemas: SchemaSet) -> dict[str, Any]:
    preimage = {
        "response_id": "ak:history_response:019c0000-0000-7000-8000-000000000001",
        "effective_scope": {"kind": "realm", "realm_id": REALM},
        "source_actor_id": SERVICE_ACTOR,
        "source_sender_domain": "history.example",
        "request_digest": digest_marker(0x41),
        "request_receipt_digest": digest_marker(0x42),
        "expires_at": EXPIRES,
        "content": {
            "kind": "ak.history_key.response_manifest",
            "chunks": [
                {
                    "chunk_response_id": "ak:history_response:019c0000-0000-7000-8000-000000000002",
                    "chunk_index": 0,
                    "covered_epoch_range": {"from_epoch": 0, "to_epoch": 0},
                }
            ],
        },
    }
    evidence_a = {
        "source_signer_evidence_ref": "ak:signer_evidence:" + digest_marker(0x51),
    }
    evidence_b = {
        "source_signer_evidence_ref": "ak:signer_evidence:" + digest_marker(0x52),
    }
    expected = domain_digest(SOURCE_AGENT_OBSERVATION_DOMAIN, preimage)
    schemas.validator(
        "history-key.schema.json", "history_source_agent_observation_input"
    ).validate(preimage)
    return {
        "domain": SOURCE_AGENT_OBSERVATION_DOMAIN.decode("ascii"),
        "preimage": preimage,
        "signing_input_a": {**preimage, **evidence_a},
        "signing_input_b": {**preimage, **evidence_b},
        "expected_digest": expected,
        "mutating_only_evidence_coordinates_keeps_digest": expected,
        "mutating_content_changes_digest": domain_digest(
            SOURCE_AGENT_OBSERVATION_DOMAIN,
            {**preimage, "source_sender_domain": "mutated.example"},
        ),
    }


def build_response_capability_kat() -> dict[str, Any]:
    capability = base64.urlsafe_b64encode(bytes(range(32))).rstrip(b"=").decode("ascii")
    preimage = {"response_capability_b64u": capability}
    return {
        "domain": "ak.history-response-capability-commitment-v1",
        "decoded_length": 32,
        "response_capability_b64u": capability,
        "commitment_preimage": preimage,
        "expected_response_capability_commitment": domain_digest(
            b"ak.history-response-capability-commitment-v1", preimage
        ),
        "surface": {
            "read": "POST /_arkret/self/history-key-responses/read",
            "ack": "POST /_arkret/self/history-key-responses/ack",
            "authorization_scheme": "Arkret-History-Capability",
            "request_locator_in_path_query_or_body": False,
        },
        "negative_cases": [
            "padded_base64url_rejected",
            "decoded_length_not_32_rejected",
            "unknown_expired_gc_and_unauthorized_same_not_found_shape",
            "stream_a_capability_cannot_read_or_ack_stream_b",
            "stream_a_capability_cannot_consume_stream_b_ack_token",
            "commitment_collision_resampled_before_any_durable_write",
            "exact_create_retry_returns_byte_identical_sealed_capability",
        ],
    }


def build_response_stream_kat(schemas: SchemaSet) -> dict[str, Any]:
    signer_digest = digest_marker(0x51)
    signing_input = {
        "response_id": "ak:history_response:019c0000-0000-7000-8000-000000000301",
        "effective_scope": {"kind": "realm", "realm_id": REALM},
        "source_actor_id": SERVICE_ACTOR,
        "source_sender_domain": SERVICE_DID,
        "source_signer_evidence_ref": "ak:signer_evidence:" + signer_digest,
        "request_digest": digest_marker(0x41),
        "request_receipt_digest": digest_marker(0x42),
        "expires_at": EXPIRES,
        "content": {
            "kind": "ak.history_key.response_manifest",
            "chunks": [{
                "chunk_response_id": "ak:history_response:019c0000-0000-7000-8000-000000000302",
                "chunk_index": 0,
                "covered_epoch_range": {"from_epoch": 0, "to_epoch": 1},
            }],
        },
    }
    send_request = {
        **signing_input,
        "source_proof": detached_proof(sha256(jcs(signing_input))),
    }
    receipt_unsigned = {
        "response_id": signing_input["response_id"],
        "source_record_digest": domain_digest(
            b"ak.history-source-record-v1", send_request
        ),
        "record_digest": digest_marker(0x61),
        "sequence": 7,
        "accepted_at": "2026-08-23T00:00:01.000Z",
        "manifest_admission_digest": digest_marker(0x62),
        "release_attestation_digest": None,
    }
    receipt_digest = domain_digest(
        b"ak.history-response-send-receipt-v1", receipt_unsigned
    )
    first_receipt = {
        **receipt_unsigned,
        "receipt_digest": receipt_digest,
        "service_proof": detached_proof(
            sha256(jcs({**receipt_unsigned, "receipt_digest": receipt_digest}))
        ),
    }
    lost_unsigned = {
        "sequence": 8,
        "cursor": "response-cursor-8",
        "response_id": "ak:history_response:019c0000-0000-7000-8000-000000000303",
        "record_digest": digest_marker(0x63),
        "lost_at": "2026-08-23T00:00:02.000Z",
        "release_service_signer_evidence_ref": "ak:signer_evidence:" + signer_digest,
    }
    lost_record = {
        **lost_unsigned,
        "service_proof": detached_proof(sha256(jcs(lost_unsigned))),
    }
    lost_record_digest = domain_digest(
        b"ak.history-response-lost-record-v1", lost_unsigned
    )
    list_outcome = {
        "entries": [{"kind": "lost", "lost_record": lost_record}],
        "ack_token": "response-ack-token-8",
        "limited": False,
    }
    ack_request = {
        "ack_token": list_outcome["ack_token"],
        "high_water_cursor": lost_record["cursor"],
        "entries": [{
            "kind": "lost",
            "sequence": lost_record["sequence"],
            "response_id": lost_record["response_id"],
            "lost_record_digest": lost_record_digest,
            "status": "service_record_lost",
        }],
    }
    ack_outcome = {"acked_through_cursor": lost_record["cursor"]}

    for definition, instance in (
        ("history_key_response_send_request", send_request),
        ("history_key_response_send_receipt", first_receipt),
        ("history_key_response_list_outcome", list_outcome),
        ("history_key_response_ack_request", ack_request),
        ("history_key_response_ack_outcome", ack_outcome),
    ):
        schemas.validator("history-key.schema.json", definition).validate(instance)

    changed_content = copy.deepcopy(send_request)
    changed_content["content"]["chunks"][0]["covered_epoch_range"]["to_epoch"] = 2
    bad_source = copy.deepcopy(send_request)
    bad_source["source_sender_domain"] = "did:key:z6MkWrongSource"
    out_of_order_ack = copy.deepcopy(ack_request)
    out_of_order_ack["entries"] = [
        {**ack_request["entries"][0], "sequence": 9},
        ack_request["entries"][0],
    ]
    return {
        "wire_instances": {
            "manifest_send": send_request,
            "first_send_receipt": first_receipt,
            "sequence_ordered_list": list_outcome,
            "ack_request": ack_request,
            "ack_outcome": ack_outcome,
        },
        "byte_exact": {
            "first_receipt_jcs_b64u": b64u(jcs(first_receipt)),
            "exact_retry_receipt_jcs_b64u": b64u(jcs(first_receipt)),
            "exact_retry_is_byte_identical": True,
        },
        "ledger_steps": [
            {"step": "initial", "large_records": 0, "compact_receipts": 0, "acked_through": None},
            {"step": "accepted_send", "large_records": 1, "compact_receipts": 1, "next_sequence": 8},
            {"step": "exact_retry", "large_records": 1, "compact_receipts": 1, "returned_first_receipt": True},
            {"step": "high_water_ack", "large_records": 0, "compact_receipts": 1, "acked_through": "response-cursor-8"},
            {"step": "request_expiry", "large_records": 0, "compact_receipts": 0},
        ],
        "negative_cases": [
            {"name": "same_id_different_content", "input": changed_content, "expected": "duplicate_conflict_zero_writes"},
            {"name": "bad_source", "input": bad_source, "expected": "dependency_missing_zero_writes"},
            {"name": "out_of_order_ack", "input": out_of_order_ack, "expected": "schema_or_semantic_reject_zero_writes"},
        ],
    }


def base58btc(value: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded
    leading_zeroes = len(value) - len(value.lstrip(b"\x00"))
    return "1" * leading_zeroes + (encoded or "1")


def build_rhrk_registration_rotation_kat(
    schemas: SchemaSet, durability: dict[str, Any]
) -> dict[str, Any]:
    archive = durability["archive"]
    register_tuple = {
        key: archive[key]
        for key in (
            "recovery_key_id", "method_controller_principal_id", "holder_service_id",
            "key_agreement_ref", "holder_signing_ref", "hpke_suite",
            "frozen_public_key_b64u",
        )
    }
    trusted_basis = archive["holder_trusted_basis"]

    def holder_acceptance(
        key_tuple: dict[str, Any], holder_basis: dict[str, Any]
    ) -> dict[str, Any]:
        unsigned = {
            "realm_id": REALM,
            "new_key_tuple": key_tuple,
            "holder_trusted_basis": holder_basis,
        }
        proof = detached_proof(sha256(jcs(unsigned)))
        proof["verification_method"] = key_tuple["holder_signing_ref"]
        return {**unsigned, "holder_proof": proof}

    register_payload = {
        "realm_id": REALM,
        "new_key_tuple": register_tuple,
        "holder_trusted_basis": trusted_basis,
        "holder_acceptance": holder_acceptance(register_tuple, trusted_basis),
    }
    rotate_tuple = {
        **register_tuple,
        "recovery_key_id": "ak:recovery_key:019c0000-0000-7000-8000-000000000122",
        "key_agreement_ref": "did:web:rhrk-holder.example#x25519-2",
        "frozen_public_key_b64u": b64u(b"\x06" * 32),
    }
    def event_from_template(kind: str, payload: dict[str, Any], label: str, actor_seq: int) -> dict[str, Any]:
        event = copy.deepcopy(durability["container_event"])
        event.update({
            "event_id": event_id(label),
            "kind": kind,
            "actor_id": {
                "kind": "account",
                "account_id": {
                    "principal_id": register_tuple["method_controller_principal_id"],
                    "station_id": register_tuple["holder_service_id"],
                },
            },
            "actor_seq": actor_seq,
            "payload": payload,
        })
        event.pop("station_id", None)
        event["proofs"][0]["verification_method"] = register_tuple["holder_signing_ref"]
        event["proofs"][0]["event_digest"] = sha256(jcs({k: v for k, v in event.items() if k != "proofs"}))
        return event

    register_event = event_from_template(
        "ak.realm.organization_recovery_key.register", register_payload, "rhrk-register", 8
    )
    register_event_digest = register_event["proofs"][0]["event_digest"]
    accepted_key_evidence_seal_ref = seal_ref("rhrk-register-accepted-key-evidence")
    accepted_key_evidence_seal = {
        "seal_id": accepted_key_evidence_seal_ref,
        "body": {
            "realm_id": REALM,
            "predecessor_refs": trusted_basis["leaves"],
            "delta": [register_event_digest],
            "covered_event_digests": [register_event_digest],
            "control_event_set_root": sha256(jcs([register_event_digest])),
            "state_root": sha256(jcs({
                "cell_id": "ak:cell:ak.component.realm.organization_recovery_key.v1:null",
                "value": {
                    "key_tuple": register_tuple,
                    "accepted_key_evidence_ref": register_event["event_id"],
                    "holder_trusted_basis": trusted_basis,
                },
            })),
            "notary_seq": 1,
            "sealed_at": "2026-08-23T00:00:03.000Z",
        },
        "covered_event_refs": [register_event["event_id"]],
        "expected": "accepted",
    }
    rotate_trusted_basis = basis(accepted_key_evidence_seal_ref)
    current_projected_tuple = {
        "key_tuple": register_tuple,
        "accepted_key_evidence_ref": register_event["event_id"],
        "holder_trusted_basis": trusted_basis,
    }
    rotate_payload = {
        "realm_id": REALM,
        "expected_previous_key_evidence_ref": register_event["event_id"],
        "expected_previous_key_evidence_seal_ref": accepted_key_evidence_seal_ref,
        "new_key_tuple": rotate_tuple,
        "holder_trusted_basis": rotate_trusted_basis,
        "holder_acceptance": holder_acceptance(rotate_tuple, rotate_trusted_basis),
    }
    rotate_event = event_from_template(
        "ak.realm.organization_recovery_key.rotate", rotate_payload, "rhrk-rotate", 9
    )
    rotate_event["preconditions"] = [{
        "cell_id": "ak:cell:ak.component.realm.organization_recovery_key.v1:null",
        "predicate": {"op": "head_eq", "value": current_projected_tuple},
    }]
    rotate_event["proofs"][0]["event_digest"] = sha256(
        jcs({key: value for key, value in rotate_event.items() if key != "proofs"})
    )
    schemas.validator("event-payload.schema.json", "organization_recovery_key_register_payload").validate(register_payload)
    schemas.validator("event-payload.schema.json", "organization_recovery_key_rotate_payload").validate(rotate_payload)
    schemas.validator("event-envelope.schema.json").validate(register_event)
    schemas.validator("event-envelope.schema.json").validate(rotate_event)

    def did_document(key_tuple: dict[str, Any]) -> dict[str, Any]:
        raw = base64.urlsafe_b64decode(key_tuple["frozen_public_key_b64u"] + "=")
        return {
            "id": key_tuple["method_controller_principal_id"],
            "verificationMethod": [{
                "id": key_tuple["key_agreement_ref"],
                "type": "Multikey",
                "controller": key_tuple["method_controller_principal_id"],
                "publicKeyMultibase": "z" + base58btc(b"\xec\x01" + raw),
            }],
            "keyAgreement": [key_tuple["key_agreement_ref"]],
        }

    return {
        "model": "accepted register/rotate Event provenance plus holder_trusted_basis; reducer effectiveness is replay-derived",
        "did_documents": {
            "register": did_document(register_tuple),
            "rotate": did_document(rotate_tuple),
        },
        "events": {"register": register_event, "rotate": rotate_event},
        "accepted_key_evidence_seal": accepted_key_evidence_seal,
        "projected_rotate_op": {
            "cell_id": "ak:cell:ak.component.realm.organization_recovery_key.v1:null",
            "to": {
                "key_tuple": rotate_tuple,
                "accepted_key_evidence_ref": rotate_event["event_id"],
                "holder_trusted_basis": rotate_trusted_basis,
            },
        },
        "reducer_effective_tuples": [
            {"after": "register", "key_tuple": register_tuple, "accepted_key_evidence_ref": register_event["event_id"], "holder_trusted_basis": trusted_basis},
            {"after": "rotate", "key_tuple": rotate_tuple, "accepted_key_evidence_ref": rotate_event["event_id"], "holder_trusted_basis": rotate_trusted_basis},
        ],
        "concurrency_cases": [
            {
                "name": "same_seal_sibling_is_rejected_before_join",
                "basis": current_projected_tuple,
                "expected": "rejected_seal",
                "reason": "cas_conflict",
                "accepted_writes": 0,
            },
            {
                "name": "incomparable_accepted_branches_join_bottom",
                "basis": current_projected_tuple,
                "expected": "bottom",
                "read_status": "failed_bottom",
            },
        ],
        "negative_mutations": [
            {"name": "wrong_curve", "target": "/did_documents/register/verificationMethod/0/publicKeyMultibase", "mutation": "replace x25519-pub multicodec with ed25519-pub", "expected": "durability_recovery_recipient_unverified"},
            {"name": "wrong_method_type", "target": "/did_documents/register/verificationMethod/0/type", "value": "JsonWebKey2020", "expected": "durability_recovery_recipient_unverified"},
            {"name": "wrong_key_length", "target": "/did_documents/register/verificationMethod/0/publicKeyMultibase", "mutation": "truncate raw key to 31 bytes", "expected": "durability_recovery_recipient_unverified"},
            {"name": "wrong_controller", "target": "/did_documents/register/verificationMethod/0/controller", "value": "ak:did_core:web:other.example", "expected": "durability_recovery_recipient_unverified"},
            {"name": "wrong_holder_proof_domain", "target": "/events/register/payload/holder_acceptance/holder_proof", "mutation": "verify under a non-registered proof context", "expected": "proof_invalid"},
            {"name": "holder_tuple_mismatch", "target": "/events/register/payload/holder_acceptance/new_key_tuple/recovery_key_id", "mutation": "change duplicated field", "expected": "failed_precondition"},
            {"name": "register_before_realm_create", "target": "/events/register", "expected": "failed_precondition"},
            {"name": "rotate_before_register", "target": "/events/rotate", "expected": "failed_precondition"},
            {"name": "rotate_missing_head_eq", "target": "/events/rotate/preconditions", "mutation": "remove the signed whole-value CAS", "expected": "failed_precondition"},
            {"name": "rotate_stale_head_eq", "target": "/events/rotate/preconditions/0/predicate/value", "mutation": "replace the complete current tuple", "expected": "failed_precondition"},
            {"name": "rotate_provenance_event_mismatch", "target": "/events/rotate/payload/expected_previous_key_evidence_ref", "mutation": "change current provenance Event while preserving head_eq", "expected": "failed_precondition"},
            {"name": "rotate_provenance_seal_mismatch", "target": "/events/rotate/payload/expected_previous_key_evidence_seal_ref", "mutation": "cite a Seal that does not make the predecessor Event effective", "expected": "failed_precondition"},
        ],
        "explicit_non_requirement": "DID service designation is neither required nor evaluated; the accepted tuple supplies the exact method id",
        "forbidden_members": ["service_selected_effectiveness_locator", "history_proof_transport_object"],
    }


def build_rhrk_durable_before_gc_kat(schemas: SchemaSet) -> dict[str, Any]:
    source_core = "ak:did_core:web:rhrk-source.example"
    source_method = "did:web:rhrk-source.example#ed25519-1"
    holder_core = "ak:did_core:web:rhrk-holder.example"
    holder_method = "did:web:rhrk-holder.example#ed25519-1"
    holder_key_agreement = "did:web:rhrk-holder.example#x25519-1"
    replicated_at = "2026-08-23T00:00:00.000Z"
    accepted_at = "2026-08-23T00:00:01.000Z"
    proof_created_at = "2026-08-23T00:00:02.000Z"
    epoch = 7

    source_signing_key = Ed25519PrivateKey.from_private_bytes(b"\x44" * 32)
    holder_signing_key = Ed25519PrivateKey.from_private_bytes(b"\x55" * 32)
    source_public_key = source_signing_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    holder_public_key = holder_signing_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )

    recipient_private_bytes = b"\x11" * 32
    ephemeral_private_bytes = b"\x22" * 32
    recipient_private = X25519PrivateKey.from_private_bytes(recipient_private_bytes)
    ephemeral_private = X25519PrivateKey.from_private_bytes(ephemeral_private_bytes)
    recipient_public = recipient_private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    enc = ephemeral_private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )

    effective_scope = {"kind": "realm", "realm_id": REALM}
    holder_trusted_basis = basis(seal_ref("rhrk-holder-trusted-basis"))
    accepted_key_evidence_ref = event_id("rhrk-accepted-key-evidence")
    transition_bytes = b"arkret rhrk archive fixture commit epoch 7"
    transition_digest = sha256(transition_bytes)
    archive_public = {
        "effective_scope": effective_scope,
        "mls_group_id": GROUP,
        "epoch": epoch,
        "transition_digest": transition_digest,
        "recovery_key_id": "ak:recovery_key:019c0000-0000-7000-8000-000000000121",
        "method_controller_principal_id": holder_core,
        "holder_service_id": holder_core,
        "key_agreement_ref": holder_key_agreement,
        "holder_signing_ref": holder_method,
        "hpke_suite": "ak.hpke_x25519_aead_chacha20poly1305.v1",
        "frozen_public_key_b64u": b64u(recipient_public),
        "accepted_key_evidence_ref": accepted_key_evidence_ref,
        "holder_trusted_basis": holder_trusted_basis,
    }
    plaintext = {
        "kind": "ak.organization_recovery.archive_plaintext",
        "history_secret_b64u": b64u(b"\x33" * 32),
    }
    info = jcs(archive_public)
    plaintext_bytes = jcs(plaintext)

    kem_suite_id = b"KEM" + (0x0020).to_bytes(2, "big")
    hpke_suite_id = (
        b"HPKE"
        + (0x0020).to_bytes(2, "big")
        + (0x0001).to_bytes(2, "big")
        + (0x0003).to_bytes(2, "big")
    )
    dh = ephemeral_private.exchange(recipient_private.public_key())
    kem_context = enc + recipient_public
    eae_prk = hpke_labeled_extract(kem_suite_id, b"", b"eae_prk", dh)
    shared_secret = hpke_labeled_expand(
        kem_suite_id, eae_prk, b"shared_secret", kem_context, 32
    )
    psk_id_hash = hpke_labeled_extract(hpke_suite_id, b"", b"psk_id_hash", b"")
    info_hash = hpke_labeled_extract(hpke_suite_id, b"", b"info_hash", info)
    key_schedule_context = b"\x00" + psk_id_hash + info_hash
    secret = hpke_labeled_extract(hpke_suite_id, shared_secret, b"secret", b"")
    key = hpke_labeled_expand(hpke_suite_id, secret, b"key", key_schedule_context, 32)
    base_nonce = hpke_labeled_expand(
        hpke_suite_id, secret, b"base_nonce", key_schedule_context, 12
    )
    exporter_secret = hpke_labeled_expand(
        hpke_suite_id, secret, b"exp", key_schedule_context, 32
    )
    ciphertext = ChaCha20Poly1305(key).encrypt(base_nonce, plaintext_bytes, info)
    recovered_plaintext = ChaCha20Poly1305(key).decrypt(base_nonce, ciphertext, info)
    if recovered_plaintext != plaintext_bytes:
        raise AssertionError("RHRK archive HPKE round trip failed")
    archive = {**archive_public, "enc": b64u(enc), "ciphertext": b64u(ciphertext)}

    governance_binding = {
        "binding_version": 1,
        "encoding_profile": "cbor-deterministic-rfc8949-v1",
        "realm_id": REALM,
        "effective_scope": effective_scope,
        "mls_group_id": GROUP,
        "previous_epoch": epoch - 1,
        "next_epoch": epoch,
        "security_frontier_digest": digest_marker(0x71),
        "content_scheme": "mls_exporter_aead_v1",
        "durability_policy": "organization_recovery_key",
        "binding_profile": "ak.profile.mls_governance_binding.full.v1",
        "reducer_profile": "ak.reducer.default.v1",
    }
    container_payload = {
        "mls_group_id": GROUP,
        "base_epoch": epoch - 1,
        "base_epoch_ref": event_id("rhrk-base-epoch"),
        "proposal_refs": [],
        "next_epoch": epoch,
        "commit_bytes_b64": b64u(transition_bytes),
        "commit_message_ref": "ak:blob:" + transition_digest,
        "governance_binding": governance_binding,
        "organization_recovery_archive": archive,
    }
    container_event_core = {
        "kind": "ak.mls.commit",
        "realm_id": REALM,
        "scope_ref": effective_scope,
        "actor_id": {"kind": "service", "service_id": source_core},
        "actor_seq": 7,
        "created_at": replicated_at,
        "prev_refs": [container_payload["base_epoch_ref"]],
        "refs": [],
        "seal_basis": basis(seal_ref("rhrk-source-accepted-basis")),
        "payload": container_payload,
    }
    container_event_digest = sha256(jcs(container_event_core))
    container_event_ref = "ak:event:" + b64u(b"\x01" + bytes.fromhex(container_event_digest[7:]))
    source_evidence_digest = digest_marker(0x72)
    event_binding = {
        "context": "ak.event_proof.v1",
        "event_digest": container_event_digest,
        "actor_id": container_event_core["actor_id"],
        "verification_method": source_method,
        "signer_resolution_evidence_ref": "ak:signer_evidence:" + source_evidence_digest,
        "created_at": replicated_at,
    }
    event_protected = b64u(jcs({"alg": "Ed25519"}))
    event_payload = b64u(jcs(event_binding))
    event_signature = source_signing_key.sign(
        (event_protected + "." + event_payload).encode("ascii")
    )
    container_event = {
        "event_id": container_event_ref,
        **container_event_core,
        "proofs": [
            {
                "kind": "detached_jws",
                "verification_method": source_method,
                "event_digest": container_event_digest,
                "created_at": replicated_at,
                "signer_resolution_evidence_ref": "ak:signer_evidence:" + source_evidence_digest,
                "jws": event_protected + ".." + b64u(event_signature),
            }
        ],
    }

    archive_tuple = {
        field: archive[field]
        for field in (
            "recovery_key_id",
            "key_agreement_ref",
            "method_controller_principal_id",
            "holder_service_id",
            "holder_signing_ref",
            "accepted_key_evidence_ref",
            "holder_trusted_basis",
        )
    }
    target_basis = basis(seal_ref("rhrk-winning-archive-transition"))
    traversal_intent = {
        "kind": "ak.history_governance.traversal_intent",
        "profile": "organization_recovery_archive",
        "effective_scope": effective_scope,
        "mls_group_id": GROUP,
        "trusted_history_base_basis": holder_trusted_basis,
        "trusted_current_basis": holder_trusted_basis,
        "target_basis": target_basis,
        "requested_ranges": [{"from_epoch": epoch, "to_epoch": epoch}],
        "archive_authorization_tuple": archive_tuple,
        "container_event_ref": container_event_ref,
        "retention": {"kind": "archive_lifetime"},
    }
    traversal_retention = {
        "traversal_intent": traversal_intent,
        "traversal_intent_digest": domain_digest(TRAVERSAL_INTENT_DOMAIN, traversal_intent),
    }

    replica_unsigned = {
        "kind": "ak.organization_recovery.archive_replica",
        "archive": archive,
        "container_event_ref": container_event_ref,
        "history_traversal_retention": traversal_retention,
        "source_id": source_core,
        "holder_service_id": holder_core,
        "replicated_at": replicated_at,
    }
    replica_proof, replica_proof_transcript = detached_jws(
        source_signing_key,
        "ak.organization_recovery_archive_replica_proof.v1",
        replica_unsigned,
        [
            "kind",
            "archive",
            "container_event_ref",
            "history_traversal_retention",
            "source_id",
            "holder_service_id",
            "replicated_at",
        ],
        source_method,
        proof_created_at,
    )
    replica = {**replica_unsigned, "service_proof": replica_proof}
    archive_replica_digest = domain_digest(ARCHIVE_REPLICA_DOMAIN, replica_unsigned)

    receipt_unsigned = {
        "archive_replica_digest": archive_replica_digest,
        "holder_service_id": holder_core,
        "archive_sequence": 1,
        "accepted_at": accepted_at,
    }
    receipt_proof, receipt_proof_transcript = detached_jws(
        holder_signing_key,
        "ak.organization_recovery_archive_replica_receipt_proof.v1",
        receipt_unsigned,
        ["archive_replica_digest", "holder_service_id", "archive_sequence", "accepted_at"],
        holder_method,
        proof_created_at,
    )
    first_receipt = {**receipt_unsigned, "service_proof": receipt_proof}
    list_query = {
        "effective_scope": effective_scope,
        "recovery_key_id": archive["recovery_key_id"],
        "key_agreement_ref": archive["key_agreement_ref"],
        "accepted_key_evidence_ref": accepted_key_evidence_ref,
        "holder_trusted_basis": holder_trusted_basis,
        "from_epoch": epoch,
        "to_epoch": epoch,
        "byte_limit": 65536,
    }
    list_item = {
        "archive_sequence": 1,
        "archive_replica_digest": archive_replica_digest,
        "archive": archive,
        "container_event_ref": container_event_ref,
        "history_traversal_retention": traversal_retention,
    }
    list_outcome = {"items": [list_item], "limited": False}

    validators = [
        ("history-key.schema.json", "organization_recovery_archive_plaintext", plaintext),
        ("event-payload.schema.json", "organization_recovery_archive", archive),
        ("event-payload.schema.json", "mls_commit_payload", container_payload),
        ("event-envelope.schema.json", None, container_event),
        ("history-key.schema.json", "archive_authorization_tuple", archive_tuple),
        ("history-key.schema.json", "history_governance_traversal_retention", traversal_retention),
        ("history-key.schema.json", "organization_recovery_archive_replica", replica),
        ("history-key.schema.json", "organization_recovery_archive_replica_outcome", first_receipt),
        ("history-key.schema.json", "organization_recovery_archive_list_query", list_query),
        ("history-key.schema.json", "organization_recovery_archive_list_outcome", list_outcome),
    ]
    for filename, definition, instance in validators:
        schemas.validator(filename, definition).validate(instance)

    archive_digest = domain_digest(b"ak.organization-recovery-archive-v1", archive)
    tuple_digest = domain_digest(b"ak.organization-recovery-archive-tuple-v1", archive_tuple)
    coverage_coordinate = {
        "effective_scope": effective_scope,
        "mls_group_id": GROUP,
        "epoch": epoch,
        "container_event_ref": container_event_ref,
        "archive_authorization_tuple_digest": tuple_digest,
    }
    ledger_initial = {
        "coverage_coordinate": coverage_coordinate,
        "durable_holder_acceptance": False,
        "exact_holder_reread": False,
        "covered_epochs": [],
        "local_history_secret_present": True,
    }
    ledger_after_accept = {
        **ledger_initial,
        "durable_holder_acceptance": True,
        "archive_replica_digest": archive_replica_digest,
        "first_receipt_digest": sha256(jcs(first_receipt)),
    }
    ledger_final = {
        **ledger_after_accept,
        "exact_holder_reread": True,
        "covered_epochs": [epoch],
        "exact_archive_digest": archive_digest,
        "exact_container_event_ref": container_event_ref,
        "exact_traversal_intent_digest": traversal_retention["traversal_intent_digest"],
    }
    ledger_after_gc = {**ledger_final, "local_history_secret_present": False}

    return {
        "vector_id": "ak.vector.history_key.organization_recovery_archive_durable_before_gc.v1",
        "classification": "service_behavior",
        "schema_validated_instances": [
            {"name": definition or "event_envelope", "schema": filename}
            for filename, definition, _ in validators
        ],
        "signing_keys": {
            "source_ed25519_seed_b64u": b64u(b"\x44" * 32),
            "source_ed25519_public_key_b64u": b64u(source_public_key),
            "holder_ed25519_seed_b64u": b64u(b"\x55" * 32),
            "holder_ed25519_public_key_b64u": b64u(holder_public_key),
        },
        "hpke_transcript": {
            "suite": "ak.hpke_x25519_aead_chacha20poly1305.v1",
            "base_vector_ref": "ak.vector.hpke.x25519_chacha20poly1305_base.v1",
            "mode": "base",
            "sequence_number": 0,
            "recipient_private_key_b64u": b64u(recipient_private_bytes),
            "recipient_public_key_b64u": b64u(recipient_public),
            "ephemeral_private_key_b64u": b64u(ephemeral_private_bytes),
            "enc_b64u": b64u(enc),
            "info_jcs_b64u": b64u(info),
            "aad_jcs_b64u": b64u(info),
            "plaintext": plaintext,
            "plaintext_jcs_b64u": b64u(plaintext_bytes),
            "dh_b64u": b64u(dh),
            "kem_context_b64u": b64u(kem_context),
            "shared_secret_b64u": b64u(shared_secret),
            "key_schedule_context_b64u": b64u(key_schedule_context),
            "secret_b64u": b64u(secret),
            "key_b64u": b64u(key),
            "base_nonce_b64u": b64u(base_nonce),
            "exporter_secret_b64u": b64u(exporter_secret),
            "ciphertext_b64u": b64u(ciphertext),
            "opened_plaintext_jcs_b64u": b64u(recovered_plaintext),
        },
        "archive_authorization_tuple": archive_tuple,
        "transition_provenance": {
            "transition_kind": "ak.mls.commit",
            "mls_transition_bytes_b64u": b64u(transition_bytes),
            "mls_transition_digest": transition_digest,
            "accepted_key_evidence_ref": accepted_key_evidence_ref,
            "holder_trusted_basis": holder_trusted_basis,
            "winning_target_basis": target_basis,
            "container_event_ref": container_event_ref,
            "container_event_digest": container_event_digest,
        },
        "archive": archive,
        "container_event": container_event,
        "container_event_producer_bytes_b64u": b64u(jcs(container_event_core)),
        "container_event_proof_transcript": {
            "context": "ak.event_proof.v1",
            "binding_jcs_b64u": b64u(jcs(event_binding)),
            "detached_payload_b64u": event_payload,
            "signing_input_ascii": event_protected + "." + event_payload,
        },
        "replica": replica,
        "replica_proof_transcript": replica_proof_transcript,
        "first_receipt": first_receipt,
        "first_receipt_jcs_b64u": b64u(jcs(first_receipt)),
        "receipt_proof_transcript": receipt_proof_transcript,
        "barrier_query": list_query,
        "barrier_resolve_outcome": list_outcome,
        "exact_reread_assertions": {
            "archive_replica_digest": archive_replica_digest,
            "archive": archive,
            "container_event_ref": container_event_ref,
            "history_traversal_retention": traversal_retention,
            "archive_sequence": 1,
        },
        "coverage_ledger": {
            "initial": ledger_initial,
            "after_first_accept": ledger_after_accept,
            "after_exact_reread": ledger_final,
            "after_local_gc": ledger_after_gc,
        },
        "steps": [
            {
                "name": "gc_before_durable_acceptance",
                "action": "gc_local_history_secret",
                "expected_decision": "failed_precondition",
                "expected_ledger": ledger_initial,
            },
            {
                "name": "first_holder_replica_acceptance",
                "action": "peer_replicate_archive",
                "input": replica,
                "expected_receipt": first_receipt,
                "expected_ledger": ledger_after_accept,
            },
            {
                "name": "exact_duplicate_replica",
                "action": "peer_replicate_archive",
                "input": replica,
                "expected_receipt_jcs_b64u": b64u(jcs(first_receipt)),
                "expected_new_archive_sequence_count": 0,
                "expected_ledger": ledger_after_accept,
            },
            {
                "name": "barrier_resolve_exact_reread",
                "action": "self_list_organization_recovery_archives",
                "input": list_query,
                "expected_outcome": list_outcome,
                "expected_ledger": ledger_final,
            },
            {
                "name": "gc_after_exact_reread",
                "action": "gc_local_history_secret",
                "expected_decision": "accepted",
                "expected_ledger": ledger_after_gc,
                "expected_holder_reread_after_gc": list_outcome,
            },
        ],
        "negative_mutations": [
            {
                "name": "barrier_missing_archive_replica_digest",
                "mutation": "remove archive_replica_digest from barrier_resolve_outcome item",
                "expected_decision": "schema_violation",
            },
            {
                "name": "barrier_archive_replica_digest_substitution",
                "mutation": {"archive_replica_digest": archive_digest},
                "expected_decision": "failed_precondition",
            },
            {
                "name": "same_semantic_archive_changed_replicated_at",
                "mutation": {"replicated_at": "2026-08-23T00:00:03.000Z"},
                "expected_decision": "conflict",
                "expected_new_archive_sequence_count": 0,
            },
            {
                "name": "barrier_archive_bytes_mismatch",
                "mutation": "flip one ciphertext octet in barrier_resolve_outcome",
                "expected_decision": "failed_precondition",
                "expected_ledger": ledger_after_accept,
            },
        ],
        "forbidden_artifacts": [
            "private_database_row_shape",
            "share_event",
            "availability_receipt",
            "threshold_target_set",
            "renewal_state_machine",
            "remote_archive_gc",
            "portable_active_mls_state",
        ],
    }


def build_sections() -> dict[str, Any]:
    schemas = SchemaSet()
    signer = build_signer_evidence(schemas)
    dependency = build_dependency_kat(schemas, signer)
    traversal = build_traversal_kat(schemas)
    durability = build_rhrk_durable_before_gc_kat(schemas)
    scale = [build_scale_recipe(26_298), build_scale_recipe(65_536)]
    probe = {"journal_rows": 0, "resolved_objects": 0, "outbox_writes": 0}
    reason = None
    try:
        build_scale_recipe(65_537, probe)
    except ValueError as exc:
        reason = str(exc)
    if reason is None or probe != {"journal_rows": 0, "resolved_objects": 0, "outbox_writes": 0}:
        raise AssertionError("65,537 negative did not reject before every side effect")
    return {
        "direct_traversal_kat": traversal,
        "direct_traversal_replay_kat": build_traversal_replay_kat(),
        "authenticated_signer_resolution_evidence_kat": signer,
        "governance_dependency_resolve_kat": dependency,
        "history_source_agent_observation_digest_kat": build_source_agent_observation_digest_kat(schemas),
        "history_response_capability_kat": build_response_capability_kat(),
        "response_stream_cases": build_response_stream_kat(schemas),
        "organization_recovery_archive_durable_before_gc_kat": durability,
        "rhrk_registration_rotation_kat": build_rhrk_registration_rotation_kat(schemas, durability),
        "streaming_direct_traversal_scale_kats": scale,
        "streaming_direct_traversal_scale_negative_kats": [{
            "epoch_count": 65_537,
            "expected": "max_total_requested_epochs exceeded",
            "actual_reason": reason,
            "rejected_before_staging": True,
            **probe,
        }],
        "direct_traversal_scale_generator_contract": {
            "generator": "tools/generate_history_scale_fixture.py",
            "traversal_intent_digest": "SHA256(UTF8('ak.history-governance-traversal-intent-v1')||0x00||JCS(intent))",
            "streaming_storage": "temporary SQLite work queue plus visited set; one canonical descriptor is live at a time",
            "fixture_storage": "small replayable open-set cut, dependency objects and aggregate scale summaries only",
            "proof_transport": "none; standard Event, Seal and governance-dependency resolve carry retained objects",
            "prewrite_budget": MAX_REQUEST_EPOCHS,
        },
    }


def render() -> str:
    fixture = json.loads(OUTPUT.read_text(encoding="utf-8"))
    rhrk_durability_vector = (
        "ak.vector.history_key.organization_recovery_archive_durable_before_gc.v1"
    )
    covers_vectors = fixture.get("covers_vectors")
    if not isinstance(covers_vectors, list):
        raise ValueError("history fixture covers_vectors must be an array")
    if rhrk_durability_vector not in covers_vectors:
        covers_vectors.append(rhrk_durability_vector)
    for case in fixture.get("scope_and_endpoint_kats", []):
        for scope_case in (case.get("realm"), case.get("circle")):
            if isinstance(scope_case, dict):
                effective_scope = scope_case.get("effective_scope")
                if isinstance(effective_scope, dict):
                    effective_scope["realm_id"] = REALM
                    if effective_scope.get("kind") == "realm":
                        scope_key = effective_scope.get("realm_id")
                    elif effective_scope.get("kind") == "circle":
                        effective_scope["circle_id"] = CIRCLE
                        scope_key = CIRCLE
                    else:
                        raise ValueError("history scope/group KAT has an unknown scope kind")
                    if not isinstance(scope_key, str) or not scope_key:
                        raise ValueError("history scope/group KAT omits its canonical scope key")
                    scope_key_bytes = scope_key.encode("utf-8")
                    scope_case["effective_scope_key_hex"] = scope_key_bytes.hex()
                    scope_case["expected_mls_group_id"] = b64u(scope_key_bytes)
        if case.get("name") == "standard_fresh_endpoint_floor":
            seed = bytes.fromhex(case["seed_hex"])
            inputs = case["inputs"]
            winning = inputs["winning_add_epoch"]
            post = inputs["post_admission_commit_epochs"]
            transition_epochs = [winning, *post]
            case["deterministic_model"] = {
                "algorithm": "ak.standard-fresh-endpoint-model.v1",
                "seed_use": "seed is used only as the fixed initial model domain input; it is not an MLS key, Welcome, Commit, or ciphertext seed",
                "initial_state": {"admitted": False, "current_epoch": None},
                "steps": [
                    *[
                        {"operation": "application_before_admission", "epoch": epoch, "result": "reject"}
                        for epoch in inputs["pre_admission_epochs"]
                    ],
                    {"operation": "winning_add_welcome_admission", "epoch": winning, "result": "admit_and_decrypt"},
                    *[
                        {"operation": "sequential_commit", "epoch": epoch, "requires_previous_epoch": epoch - 1, "result": "advance_and_decrypt"}
                        for epoch in post
                    ],
                ],
                "transition_tag_formula": "SHA256(seed || 0x00 || UTF8(operation) || uint64be(epoch))",
                "transition_tags": [
                    {
                        "epoch": epoch,
                        "operation": "winning_add_welcome_admission" if epoch == winning else "sequential_commit",
                        "sha256_hex": hashlib.sha256(
                            seed
                            + ZERO
                            + (b"winning_add_welcome_admission" if epoch == winning else b"sequential_commit")
                            + epoch.to_bytes(8, "big")
                        ).hexdigest(),
                    }
                    for epoch in transition_epochs
                ],
                "reject_if": ["application epoch precedes winning Add/Welcome", "first admitted transition is not the winning Add/Welcome", "Commit epoch is not previous_epoch + 1"],
            }
    if "ak.vector.history_key.frontier_traversal_split.v1" not in fixture.get("covers_vectors", []):
        raise ValueError("history fixture does not register the direct-traversal split vector")
    fixture.pop("mailbox_cases", None)
    fixture.update(build_sections())
    fixture["version"] = "2026-09-02"
    fixture["runner"] = {
        "kind": "named_suite",
        "entrypoint": "ak.suite.crypto.history_key_recovery.v1",
        "scale_generator": "tools/generate_history_scale_fixture.py",
    }
    return json.dumps(fixture, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != output:
            print(f"stale generated fixture: {OUTPUT.relative_to(ROOT)}")
            return 1
        print(f"generated fixture is current: {OUTPUT.relative_to(ROOT)}")
        return 0
    OUTPUT.write_text(output, encoding="utf-8", newline="\n")
    print(f"updated {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
