#!/usr/bin/env python3
"""Generate direct-traversal history recovery KATs and bounded scale recipes."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, RefResolver

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "spec/v1/artifacts/schemas"
REGISTRY_DIR = ROOT / "spec/v1/artifacts/registry"
OUTPUT = ROOT / "spec/v1/artifacts/fixtures/history-key-recovery-fixture.json"

ZERO = b"\x00"
TRAVERSAL_INTENT_DOMAIN = b"ak.history-governance-traversal-intent-v1"
REGISTRY_SNAPSHOT_DOMAIN = b"ak.governance-registry-snapshot-v1"
REGISTRY_ARTIFACT_DOMAIN = b"ak.governance-registry-artifact-v1"
AVAILABILITY_BYTES_DOMAIN = b"ak.availability-event-bytes-v1"
SOURCE_AGENT_OBSERVATION_DOMAIN = b"ak.history-source-agent-observation-v1"
MAX_REQUEST_EPOCHS = 65_536

SERVICE_DID = "did:key:z6MkfixtureService"
SERVICE_CORE = "ak:did_core:key:z6MkfixtureService"
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


def event_id(label: str) -> str:
    return "ak:event:" + b64u(b"\x01" + hashlib.sha256(label.encode("utf-8")).digest())


REALM = "ak:realm:" + event_id("history-scale-realm-create").split(":", 2)[2]
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


def walk_refs(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "$ref" and isinstance(child, str):
                yield child
            else:
                yield from walk_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_refs(child)


def replay_schema_closure() -> list[Path]:
    pending = [SCHEMA_DIR / "event-envelope.schema.json", SCHEMA_DIR / "event-payload.schema.json"]
    seen: set[Path] = set()
    while pending:
        path = pending.pop().resolve()
        if path in seen:
            continue
        if path.parent != SCHEMA_DIR.resolve() or not path.is_file():
            raise ValueError(f"schema closure escaped or is missing: {path}")
        seen.add(path)
        value = json.loads(path.read_text(encoding="utf-8"))
        for ref in walk_refs(value):
            locator = ref.split("#", 1)[0]
            if not locator or "://" in locator:
                continue
            target = (path.parent / locator).resolve()
            if target.parent != SCHEMA_DIR.resolve() or not target.name.endswith(".schema.json"):
                raise ValueError(f"non-schema local ref in replay closure: {path.name} -> {ref}")
            pending.append(target)
    return sorted(seen, key=lambda path: path.name.encode("utf-8"))


def registry_artifact_descriptor(kind: str, artifact_id: str, canonical_value: Any) -> dict[str, Any]:
    return {
        "artifact_kind": kind,
        "artifact_id": artifact_id,
        "content_digest": sha256(REGISTRY_ARTIFACT_DOMAIN + ZERO + jcs(canonical_value)),
    }


def build_registry_kat(schemas: SchemaSet) -> dict[str, Any]:
    contract = json.loads((REGISTRY_DIR / "contract-registry.json").read_text(encoding="utf-8"))
    proof_context = json.loads((REGISTRY_DIR / "proof-context-registry.json").read_text(encoding="utf-8"))
    closure = replay_schema_closure()
    schema_descriptors = [
        registry_artifact_descriptor(
            "replay_json_schema",
            f"schemas/{path.name}",
            json.loads(path.read_text(encoding="utf-8")),
        )
        for path in closure
    ]
    schema_manifest = {
        "kind": "ak.governance.replay_schema_manifest",
        "root_schema_artifact_ids": [
            "schemas/event-envelope.schema.json",
            "schemas/event-payload.schema.json",
        ],
        "artifacts": schema_descriptors,
    }
    manifest_descriptor = registry_artifact_descriptor(
        "replay_schema_manifest",
        "governance-replay-schema-manifest",
        schema_manifest,
    )
    snapshot_core = {
        "kind": "ak.governance.registry_snapshot",
        "artifacts": [
            registry_artifact_descriptor("contract_registry", "registry/contract-registry.json", contract),
            registry_artifact_descriptor(
                "proof_context_registry", "registry/proof-context-registry.json", proof_context
            ),
            manifest_descriptor,
        ],
    }
    snapshot = {
        **snapshot_core,
        "snapshot_digest": sha256(REGISTRY_SNAPSHOT_DOMAIN + ZERO + jcs(snapshot_core)),
    }
    schemas.validator("governance-registry-snapshot.schema.json").validate(snapshot)
    schemas.validator(
        "governance-registry-snapshot.schema.json", "governance_replay_schema_manifest"
    ).validate(schema_manifest)

    sample_path = min(closure, key=lambda path: len(jcs(json.loads(path.read_text(encoding="utf-8")))))
    sample_value = json.loads(sample_path.read_text(encoding="utf-8"))
    sample_descriptor = next(
        descriptor for descriptor in schema_descriptors if descriptor["artifact_id"] == f"schemas/{sample_path.name}"
    )
    sample_artifact = {
        "descriptor": sample_descriptor,
        "canonical_bytes_b64u": b64u(jcs(sample_value)),
    }
    schemas.validator(
        "governance-registry-snapshot.schema.json", "governance_registry_artifact"
    ).validate(sample_artifact)
    return {
        "snapshot": snapshot,
        "schema_manifest_summary": {
            "root_schema_artifact_ids": schema_manifest["root_schema_artifact_ids"],
            "artifact_count": len(schema_descriptors),
            "artifact_descriptor_aggregate_digest": sha256(jcs(schema_descriptors)),
            "largest_artifact_canonical_bytes": max(
                len(jcs(json.loads(path.read_text(encoding="utf-8")))) for path in closure
            ),
        },
        "sample_registry_artifact": sample_artifact,
    }


def build_signer_evidence(schemas: SchemaSet) -> dict[str, Any]:
    history_head = "did-key-head-fixture"
    version_id = "did-key-v1"
    normalized_document = {
        "id": SERVICE_DID,
        "verificationMethod": [{"id": SERVICE_METHOD, "controller": SERVICE_DID}],
    }
    record = {
        "record": {
            "service_id": SERVICE_CORE,
            "service_kind": "principal_server",
            "full_id": SERVICE_DID,
            "method_history_head": history_head,
            "version_id": version_id,
            "resolution_event_ref": "did-key-full-id-sha256:" + "31" * 32,
            "record_sequence": 0,
            "previous_record_digest": None,
            "current_record_url": "https://service.example/_arkret/open/services/service/resolution",
            "base_url": "https://service.example/",
            "describe_digest": digest_marker(0x32),
            "issued_at": "2026-08-21T00:00:00.000Z",
            "refresh_after": "2026-08-22T00:00:00.000Z",
            "expires_at": "2026-08-29T00:00:00.000Z",
        },
        "proof": {
            "verification_method": SERVICE_METHOD,
            "created_at": "2026-08-21T00:00:00.000Z",
            "jws": "c2ln",
        },
    }
    evidence = {
        "kind": "service",
        "signer_id": SERVICE_CORE,
        "verification_method": SERVICE_METHOD,
        "authenticated_resolution": {
            "service_resolution_record": record,
            "method_history_evidence": {
                "adapter_version": "did:key:1",
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


def build_dependency_kat(schemas: SchemaSet, registry: dict[str, Any], signer: dict[str, Any]) -> dict[str, Any]:
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
        "holder_id": SERVICE_CORE,
        "retention_expires_at": EXPIRES,
        "holder_signer_evidence_ref": signer["evidence_ref"],
        "holder_signer_evidence_digest": signer["evidence_digest"],
    }
    receipt = {**receipt_core, "signature": detached_proof(sha256(jcs(receipt_core)))}
    availability = {"receipt": receipt, "receipt_digest": sha256(jcs(receipt))}
    schemas.validator("availability-receipt.schema.json").validate(availability)

    snapshot = registry["snapshot"]
    artifact = registry["sample_registry_artifact"]
    rows = [
        {
            "selector": {"kind": "availability_receipt", "content_digest": availability["receipt_digest"]},
            "availability_receipt": availability,
        },
        {
            "selector": {
                "kind": "authenticated_signer_resolution_evidence",
                "content_digest": signer["evidence_digest"],
            },
            "authenticated_signer_resolution_evidence": signer["evidence"],
        },
        {
            "selector": {"kind": "governance_registry_snapshot", "content_digest": snapshot["snapshot_digest"]},
            "governance_registry_snapshot": snapshot,
        },
        {
            "selector": {"kind": "governance_registry_artifact", "descriptor": artifact["descriptor"]},
            "governance_registry_artifact": artifact,
        },
    ]
    rows.sort(key=lambda row: (row["selector"]["kind"].encode("utf-8"), jcs(row["selector"])))
    outcome = {"items": rows, "missing_selectors": []}
    schemas.validator("service-operation-dtos.schema.json", "GovernanceDependencyResolveOutcome").validate(outcome)
    return {
        "accepted_event_without_unsigned": accepted_event,
        "availability_event_bytes_digest": bytes_digest,
        "availability_receipt": availability,
        "resolve_outcome": outcome,
        "negative_cases": [
            {
                "name": "selector_branch_mismatch",
                "mutation": "pair an authenticated_signer_resolution_evidence selector with availability_receipt",
                "expected": "schema_violation",
            },
            {
                "name": "registry_artifact_digest_mismatch",
                "mutation": "change decoded canonical artifact bytes without changing descriptor.content_digest",
                "expected": "dependency_missing",
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


def ratchet_outcome(current: str | None, proposed: str) -> str:
    if current is None and proposed in {"since_join", "all_history_for_current_members"}:
        return "accepted_create"
    if current == proposed:
        return "duplicate_noop"
    if current == "all_history_for_current_members" and proposed == "since_join":
        return "accepted_narrow"
    return "failed_precondition"


def build_traversal_kat(schemas: SchemaSet, registry: dict[str, Any]) -> dict[str, Any]:
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
        "registry_snapshot_digest": registry["snapshot"]["snapshot_digest"],
        "traversal_admission_registry_digest": digest_marker(0x62),
        "retention": {"kind": "request_expiring", "expires_at": EXPIRES},
    }
    retention = {
        "traversal_intent": intent,
        "traversal_intent_digest": domain_digest(TRAVERSAL_INTENT_DOMAIN, intent),
    }
    schemas.validator("history-key.schema.json", "history_governance_traversal_intent").validate(intent)
    schemas.validator("history-key.schema.json", "history_governance_traversal_retention").validate(retention)

    rrk_intent = {
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
            "holder_principal_id": SERVICE_CORE,
            "holder_service_id": SERVICE_CORE,
            "holder_signing_ref": SERVICE_METHOD,
            "accepted_key_evidence_ref": event_id("accepted-key-evidence"),
            "holder_trusted_basis": case["trusted_history_base_basis"],
        },
        "container_event_ref": event_id("archive-container"),
        "registry_snapshot_digest": registry["snapshot"]["snapshot_digest"],
        "traversal_admission_registry_digest": digest_marker(0x62),
        "retention": {"kind": "archive_lifetime"},
    }
    schemas.validator("history-key.schema.json", "history_governance_traversal_intent").validate(rrk_intent)
    invalid_rrk = copy.deepcopy(rrk_intent)
    invalid_rrk["requested_ranges"].append({"from_epoch": 2, "to_epoch": 2})
    rrk_error_count = len(
        list(schemas.validator("history-key.schema.json", "history_governance_traversal_intent").iter_errors(invalid_rrk))
    )
    if rrk_error_count == 0:
        raise AssertionError("RRK multi-range negative unexpectedly schema-valid")
    request_base = {
        "request_id": "ak:history_request:019c0000-0000-7000-8000-000000000001",
        "kind": "ak.history_key.request",
        "effective_scope": {"kind": "realm", "realm_id": REALM},
        "requester_actor_id": SERVICE_CORE,
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
            "profile": "native_agent",
            "endpoint": {
                "kind": "native_agent",
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
        "organization_recovery_intent": rrk_intent,
        "rrk_non_singleton_negative": {
            "expected": "schema_violation",
            "actual_error_count": rrk_error_count,
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
        "source_actor_id": SERVICE_CORE,
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
        "source_signer_evidence_digest": digest_marker(0x51),
    }
    evidence_b = {
        "source_signer_evidence_ref": "ak:signer_evidence:" + digest_marker(0x52),
        "source_signer_evidence_digest": digest_marker(0x52),
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


def build_sections() -> dict[str, Any]:
    schemas = SchemaSet()
    registry = build_registry_kat(schemas)
    signer = build_signer_evidence(schemas)
    dependency = build_dependency_kat(schemas, registry, signer)
    traversal = build_traversal_kat(schemas, registry)
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
        "governance_registry_artifact_kat": registry,
        "authenticated_signer_resolution_evidence_kat": signer,
        "governance_dependency_resolve_kat": dependency,
        "history_source_agent_observation_digest_kat": build_source_agent_observation_digest_kat(schemas),
        "history_response_capability_kat": build_response_capability_kat(),
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
            "registry_snapshot_digest": "SHA256(UTF8('ak.governance-registry-snapshot-v1')||0x00||JCS({kind,artifacts}))",
            "registry_artifact_digest": "SHA256(UTF8('ak.governance-registry-artifact-v1')||0x00||decoded canonical bytes)",
            "streaming_storage": "temporary SQLite work queue plus visited set; one canonical descriptor is live at a time",
            "fixture_storage": "small replayable open-set cut, dependency objects and aggregate scale summaries only",
            "proof_transport": "none; standard Event, Seal and governance-dependency resolve carry retained objects",
            "prewrite_budget": MAX_REQUEST_EPOCHS,
        },
    }


def render() -> str:
    fixture = json.loads(OUTPUT.read_text(encoding="utf-8"))
    for case in fixture.get("scope_and_endpoint_kats", []):
        for scope_case in (case.get("realm"), case.get("circle")):
            if isinstance(scope_case, dict):
                effective_scope = scope_case.get("effective_scope")
                if isinstance(effective_scope, dict):
                    effective_scope["realm_id"] = REALM
    if "ak.vector.history_key.frontier_traversal_split.v1" not in fixture.get("covers_vectors", []):
        raise ValueError("history fixture does not register the direct-traversal split vector")
    fixture.pop("mailbox_cases", None)
    fixture["response_stream_cases"] = [
        {
            "name": "manifest_precedes_chunk_admission",
            "expected": "manifest admission completes direct traversal and T0 before the manifest record is accepted; a chunk without that exact admission is dependency_missing with zero writes",
        },
        {
            "name": "manifest_all_or_nothing_t0_admission",
            "expected": "the service replays the complete retained base-to-target Seal cut, Control Moves and registered dependencies, derives winners/current monotone history policy/join floor, and writes one manifest_admission_digest or nothing",
        },
        {
            "name": "single_continuous_chunk_range",
            "expected": "each chunk_index maps to exactly one manifest descriptor and one continuous epoch range already authorized by direct replay",
        },
        {
            "name": "compact_exact_retry_ledger_until_expiry",
            "expected": "the first accepted send freezes one small HistoryKeyResponseSendReceipt; exact retry returns byte-identical bytes and high-water ack removes the large response record while retaining the compact receipt ledger through expiry",
        },
    ]
    fixture["rrk_registration_rotation_kat"] = {
        "model": "register-or-rotate Event provenance plus holder_trusted_basis; reducer effectiveness is replay-derived",
        "required_replay": "archive-lifetime direct traversal derives the effective key tuple and exact winning archive transition from standard Seal/Event/dependency closure",
        "forbidden_members": [
            "service_selected_effectiveness_locator",
            "history_proof_transport_object",
        ],
        "negative_cases": [
            "register_before_realm_create",
            "holder_trusted_basis_replaced_by_service",
            "archive_evidence_event_not_reducer_effective",
            "rrk_requested_range_not_singleton",
            "closure_outside_holder_authorized_control_metadata",
        ],
    }
    fixture.update(build_sections())
    fixture["version"] = "2026-08-21"
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
    OUTPUT.write_text(output, encoding="utf-8")
    print(f"updated {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
