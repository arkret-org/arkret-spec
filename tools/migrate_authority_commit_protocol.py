#!/usr/bin/env python3
"""One-shot mechanical migration to the authority-commit wire contract.

The normative decisions live in the Chinese specification.  This helper keeps
the large JSON documents deterministic while the old CBS/Cell projections are
removed.  It is intentionally idempotent so reviewers can rerun it.
"""

from __future__ import annotations

import json
import subprocess
import copy
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "spec/v1/artifacts/schemas"
REGISTRY = ROOT / "spec/v1/artifacts/registry/contract-registry.json"
ARTIFACT_REGISTRY = ROOT / "spec/v1/artifacts/registry"

RETIRED_SCHEMA_FILES = {
    "schemas/agent-signer-evidence-operations.schema.json",
    "schemas/agent-signer-evidence.schema.json",
    "schemas/availability-receipt.schema.json",
    "schemas/bottom.schema.json",
    "schemas/cbs-proof-bundle.schema.json",
    "schemas/collision-variant-record.schema.json",
    "schemas/control-proposal-decision.schema.json",
    "schemas/current-signer-evidence-operations.schema.json",
    "schemas/genesis-notary-binding.schema.json",
    "schemas/history-key.schema.json",
    "schemas/mls-governance-proof-bundle.schema.json",
    "schemas/mls-welcome-refs.schema.json",
    "schemas/offline-publication.schema.json",
    "schemas/realm-state-snapshot-chunk.schema.json",
    "schemas/seal-conclusion.schema.json",
    "schemas/seal.schema.json",
}

RETIRED_FIXTURE_FILES = {
    "agent-signer-evidence-fixture.json",
    "agent-sidecar-fixture.json",
    "capability-fixture.json",
    "cbs-lattice-fixture.json",
    "control-proposal-ack-fixture.json",
    "device-revocation-pending-fixture.json",
    "direct-conversation-fixture.json",
    "event-envelope-negative-fixture.json",
    "event-kind-lattice-dispatch-fixture.json",
    "federation-fixture.json",
    "hash-transition-fixture.json",
    "history-key-recovery-fixture.json",
    "human-control-signer-evidence-kat.json",
    "identity-root-anchor-fixture.json",
    "keypackage-pairwise-welcome-fixture.json",
    "mimi-interop-fixture.json",
    "mls-governance-proof-fixture.json",
    "pcr-outward-exposure-fixture.json",
    "poll-reducer-fixture.json",
    "proof-context-transcript-fixture.json",
    "reaction-fixture.json",
    "read-cursor-multi-device-merge-fixture.json",
    "recovery-policy-fixture.json",
    "sdk-event-type-axes-fixture.json",
    "seal-prepare-fence-fixture.json",
    "seal-submit-fixture.json",
    "security-closure-fixture.json",
    "service-closure-hardening-fixture.json",
    "state-reducer-hardening-fixture.json",
    "sync-fixture.json",
    "websocket-binding-fixture.json",
}

RETIRED_REGISTRY_FILES = {
    "history-key-canonical-binding-registry.json",
    "history-recovery-scalability-registry.json",
    "history-release-attestation-registry.json",
    "mls-security-frontier-registry.json",
    "mls-proposal-admission-registry.json",
    "registered-effect-capability-registry.json",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_old_decenter(relative_path: str) -> dict:
    raw = subprocess.check_output(
        ["git", "show", f"old-decenter:{relative_path}"], cwd=ROOT
    )
    return json.loads(raw.decode("utf-8"))


def load_head(relative_path: str) -> dict:
    raw = subprocess.check_output(["git", "show", f"HEAD:{relative_path}"], cwd=ROOT)
    return json.loads(raw.decode("utf-8"))


def save(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def schema_ref_resolves(ref: str) -> bool:
    file_ref, separator, fragment = ref.partition("#")
    path = ROOT / "spec/v1/artifacts" / file_ref
    if not path.exists():
        return False
    if not separator or not fragment:
        return True
    node: object = load(path)
    try:
        for raw in fragment.removeprefix("/").split("/"):
            token = raw.replace("~1", "/").replace("~0", "~")
            node = node[int(token)] if isinstance(node, list) else node[token]  # type: ignore[index]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    return isinstance(node, dict)


def refs_in(value: object) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            refs.append(ref)
        for item in value.values():
            refs.extend(refs_in(item))
    elif isinstance(value, list):
        for item in value:
            refs.extend(refs_in(item))
    return refs


def strip_retired_schema_references() -> None:
    retired_names = {Path(name).name for name in RETIRED_SCHEMA_FILES}

    def names_retired_schema(value: object) -> bool:
        return any(Path(ref.split("#", 1)[0]).name in retired_names for ref in refs_in(value))

    def clean(value: object) -> None:
        if isinstance(value, dict):
            properties = value.get("properties")
            if isinstance(properties, dict):
                removed = {
                    name for name, schema in properties.items() if names_retired_schema(schema)
                }
                for name in removed:
                    properties.pop(name, None)
                if isinstance(value.get("required"), list):
                    value["required"] = [
                        name for name in value["required"] if name not in removed
                    ]
            for keyword in ("oneOf", "anyOf", "allOf"):
                branches = value.get(keyword)
                if isinstance(branches, list):
                    value[keyword] = [
                        branch
                        for branch in branches
                        if not (
                            isinstance(branch, dict)
                            and isinstance(branch.get("$ref"), str)
                            and Path(branch["$ref"].split("#", 1)[0]).name
                            in retired_names
                        )
                    ]
            for item in list(value.values()):
                clean(item)
        elif isinstance(value, list):
            for item in value:
                clean(item)

    for path in SCHEMAS.glob("*.schema.json"):
        document = load(path)
        clean(document)
        save(path, document)


def rename_tree(value: object, replacements: dict[str, str]) -> object:
    if isinstance(value, dict):
        return {
            replacements.get(key, key): rename_tree(item, replacements)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [rename_tree(item, replacements) for item in value]
    if isinstance(value, str):
        result = value
        for old, new in replacements.items():
            if value == old:
                return new
            result = result.replace(f"#/$defs/{old}", f"#/$defs/{new}")
        return result
    return value


def migrate_security_transaction_commit_terms() -> None:
    path = SCHEMAS / "security-transaction.schema.json"
    document = load(path)
    replacements = {
        "seal_id": "realm_commit_id",
        "recovery_seal_intent": "recovery_commit_intent",
        "first_generation_seal_intent": "reanchor_commit_intent",
        "first_generation_seal_id": "reanchor_commit_id",
        "first_generation_seal_body": "reanchor_commit_body",
    }
    document = rename_tree(document, replacements)
    document["$defs"]["realm_commit_id"] = {
        "$ref": "./common-ids.schema.json#/$defs/realm_commit_id"
    }
    save(path, document)


def prune_service_operation_dtos() -> None:
    path = SCHEMAS / "service-operation-dtos.schema.json"
    dto = load(path)
    old_dto = load_old_decenter(
        "spec/v1/artifacts/schemas/service-operation-dtos.schema.json"
    )
    for preserved_name in (
        "SignedSessionGrantClaims",
        "SessionGrantReplayExpiredProblem",
        "SessionGrantReplayTerminalProblem",
    ):
        if preserved_name not in dto["$defs"]:
            dto["$defs"][preserved_name] = old_dto["$defs"][preserved_name]
    dto["$defs"]["EventInitialSubmission"] = {
        "type": "object",
        "description": (
            "One exact producer-signed Event submitted to the current governance "
            "Station. There are no Seal, Cell, offline-lease or proof-bundle sidecars."
        ),
        "required": ["event"],
        "properties": {"event": {"$ref": "./event-envelope.schema.json"}},
        "additionalProperties": False,
    }
    seeds: set[str] = {
        "SignedSessionGrantClaims",
        "SessionGrantReplayExpiredProblem",
        "SessionGrantReplayTerminalProblem",
    }
    registry = load(REGISTRY)
    for row in registry["operation_registry"]["operations"]:
        for field in ("request_schema_ref", "response_schema_ref"):
            ref = row.get(field, "")
            marker = "schemas/service-operation-dtos.schema.json#/$defs/"
            if ref.startswith(marker):
                seeds.add(ref.removeprefix(marker).split("/", 1)[0])
    for schema_path in SCHEMAS.glob("*.schema.json"):
        if schema_path == path or f"schemas/{schema_path.name}" in RETIRED_SCHEMA_FILES:
            continue
        document = load(schema_path)
        for ref in refs_in(document):
            marker = "./service-operation-dtos.schema.json#/$defs/"
            if ref.startswith(marker):
                seeds.add(ref.removeprefix(marker).split("/", 1)[0])
    retained: set[str] = set()
    pending = list(seeds)
    while pending:
        name = pending.pop()
        if name in retained or name not in dto["$defs"]:
            continue
        retained.add(name)
        for ref in refs_in(dto["$defs"][name]):
            if ref.startswith("#/$defs/"):
                pending.append(ref.removeprefix("#/$defs/").split("/", 1)[0])
    dto["$defs"] = {
        name: value for name, value in dto["$defs"].items() if name in retained
    }
    dto["anyOf"] = [{"$ref": f"#/$defs/{name}"} for name in sorted(seeds & retained)]
    dto["description"] = (
        "Canonical DTOs reachable from current authority-commit operations. "
        "Every definition is part of the current operation closure."
    )
    save(path, dto)


def migrate_event_envelope() -> None:
    path = SCHEMAS / "event-envelope.schema.json"
    event = load(path)
    event["description"] = (
        "Closed producer-signed Event. Shared persistent Events become final only "
        "when the current Realm governance Station issues a RealmCommit in the "
        "derived Realm, Circle, or Sidecar stream."
    )
    retired = {
        "actor_seq",
        "hlc",
        "prev_refs",
        "causal_refs",
        "preconditions",
        "auth_context",
        "data_basis",
        "seal_basis",
        "unsigned",
        "requirements",
    }
    event["required"] = [name for name in event["required"] if name not in retired]
    for name in retired:
        event["properties"].pop(name, None)

    defs = event["$defs"]
    for name in (
        "seal_ref",
        "cell_ref",
        "precondition",
        "identity_resolution_head_precondition",
        "predicate",
        "semantic_ref_merkle_proof",
        "ordinary_publication_event",
        "realm_authority_root_ref",
        "critical_extension",
        "feature_ref",
        "profile_ref",
    ):
        defs.pop(name, None)
    authorization_ref = event["properties"].get("authorization_ref", {})
    if isinstance(authorization_ref.get("oneOf"), list):
        authorization_ref["oneOf"] = [
            branch
            for branch in authorization_ref["oneOf"]
            if branch.get("$ref") != "#/$defs/realm_authority_root_ref"
        ]
    authorization_ref["description"] = (
        "Optional. Required when executed_by is present. It identifies an accepted "
        "Grant, delegation Event, DID-document delegation, or one of the closed "
        "profile-specific authority constants. The current governance Station "
        "evaluates the reference against the target stream's committed state."
    )
    producer_proof = defs.get("producer_event_proof", {})
    producer_proof.get("properties", {}).pop("signer_resolution_evidence_ref", None)
    producer_proof["required"] = [
        field
        for field in producer_proof.get("required", [])
        if field != "signer_resolution_evidence_ref"
    ]
    producer_proof["description"] = (
        "Producer signature over canonical Event bytes. The current governance "
        "Station resolves and validates the signing key at admission; its "
        "RealmCommit attests that decision, so no Cell/Seal signer witness is "
        "carried by the Event."
    )
    defs["semantic_ref"] = {
        "description": (
            "Closed business-reference union. authorized_by names a stable GrantId; "
            "all other roles name an immutable Event. Commit continuity is carried "
            "only by RealmCommit.previous_commit_ref."
        ),
        "anyOf": [
            {
                "type": "object",
                "required": ["id", "role", "critical"],
                "properties": {
                    "id": {"$ref": "#/$defs/grant_ref"},
                    "role": {"const": "authorized_by"},
                    "critical": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
            {
                "type": "object",
                "required": ["id", "role", "critical"],
                "properties": {
                    "id": {"$ref": "#/$defs/event_ref"},
                    "role": {
                        "enum": [
                            "attestation",
                            "parent_event",
                            "after",
                            "audit_pair",
                            "recovery_capability",
                            "did_inception",
                            "accountability",
                            "bootstrap_genesis",
                            "disclosure_authorization",
                            "capture_stop",
                            "direct_conversation_binding",
                            "direct_conversation_founding_unit",
                            "direct_conversation_contact_round",
                            "direct_conversation_agent_provision",
                            "applet_managed_actor_provision",
                        ]
                    },
                    "critical": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
        ],
    }

    # Keep the hand-written kind/payload and delegated-authority guards, but
    # discard every clause whose JSON syntax still names a retired envelope
    # field.  Generated admission/registered-kind guards are appended below.
    kept = []
    for clause in event.get("allOf", []):
        if clause in (
            {"$ref": "#/$defs/registered_admission_shape"},
            {"$ref": "#/$defs/registered_execution_shape"},
        ):
            continue
        # Payload dispatch is rebuilt from the canonical registry below.
        if (
            isinstance(clause.get("if"), dict)
            and "kind" in clause["if"].get("properties", {})
            and isinstance(clause.get("then"), dict)
            and "payload" in clause["then"].get("properties", {})
        ):
            continue
        encoded = json.dumps(clause, ensure_ascii=False)
        if not any(f'"{name}"' in encoded for name in retired):
            kept.append(clause)
    registry = load(REGISTRY)["event_kind_registry"]
    for row in registry["event_kinds"]:
        if row.get("status") != "active" or "payload_schema_ref" not in row:
            continue
        ref = row["payload_schema_ref"]
        if ref.startswith("schemas/"):
            ref = "./" + ref.removeprefix("schemas/")
        kept.append(
            {
                "if": {
                    "properties": {"kind": {"const": row["event_kind"]}},
                    "required": ["kind"],
                },
                "then": {"properties": {"payload": {"$ref": ref}}},
            }
        )
    kept.extend(
        [
            {"$ref": "#/$defs/registered_admission_shape"},
            {"$ref": "#/$defs/registered_execution_shape"},
        ]
    )
    event["allOf"] = kept
    durable_kinds = sorted(
        row["event_kind"]
        for row in registry["event_kinds"]
        if row.get("status") == "active" and row.get("wire_scope") == "durable_event"
    )
    defs["shared_history_event"] = {
        "$comment": (
            "A complete producer Event from an authority-committed visibility "
            "stream. Verify it together with the matching RealmCommit."
        ),
        "allOf": [
            {"$ref": "#"},
            {
                "properties": {"kind": {"enum": durable_kinds}},
                "required": ["kind"],
            },
        ],
    }
    save(path, event)


def migrate_realm_genesis() -> None:
    path = SCHEMAS / "realm-genesis.schema.json"
    genesis = load(path)
    retired = {
        "schema_refs",
        "reducer_profile",
        "digest_algorithm",
        "encryption_profile",
        "notary",
    }
    genesis["required"] = [name for name in genesis["required"] if name not in retired]
    for name in retired:
        genesis["properties"].pop(name, None)
    additions = {
        "governance_station_id": {
            "$ref": "./common-ids.schema.json#/$defs/did_core_id",
            "description": "Generation-0 governance Station service identity.",
        },
        "initial_join_rule": {"$ref": "./realm.schema.json#/properties/default_join_rule"},
        "initial_history_access": {"$ref": "./realm.schema.json#/properties/history_access"},
        "initial_discoverability": {
            "$ref": "./realm.schema.json#/properties/default_discoverability"
        },
    }
    genesis["properties"].update(additions)
    for name in additions:
        if name not in genesis["required"]:
            genesis["required"].append(name)
    save(path, genesis)


def migrate_event_payload() -> None:
    path = SCHEMAS / "event-payload.schema.json"
    payload = load(path)
    defs = payload["$defs"]
    if "resource_discovery_state" not in defs:
        old_payload = load_old_decenter(
            "spec/v1/artifacts/schemas/event-payload.schema.json"
        )
        defs["resource_discovery_state"] = old_payload["$defs"][
            "resource_discovery_state"
        ]
    defs["mls_governance_binding"] = {
        "type": "object",
        "required": [
            "effective_scope",
            "base_group_state_ref",
            "previous_epoch",
            "next_epoch",
            "key_access_revision",
        ],
        "properties": {
            "effective_scope": {"$ref": "#/$defs/effective_scope"},
            "base_group_state_ref": {
                "oneOf": [
                    {"$ref": "#/$defs/event_ref"},
                    {"type": "null"},
                ]
            },
            "previous_epoch": {"type": "integer", "minimum": 0},
            "next_epoch": {"type": "integer", "minimum": 0},
            "key_access_revision": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": False,
    }
    defs["mls_genesis_payload"] = {
        "type": "object",
        "required": [
            "cipher_suite",
            "group_info_ref",
            "ratchet_tree_ref",
            "governance_binding",
            "created_at",
        ],
        "properties": {
            "cipher_suite": {"$ref": "#/$defs/non_empty_string"},
            "group_info_ref": {
                "type": "string",
                "pattern": "^ak:blob:(?:sha256|blake3):[0-9a-f]{64}$",
                "x-arkret-digest-suite-source": "realm_digest_algorithm",
            },
            "ratchet_tree_ref": {
                "type": "string",
                "pattern": "^ak:blob:(?:sha256|blake3):[0-9a-f]{64}$",
                "x-arkret-digest-suite-source": "realm_digest_algorithm",
            },
            "governance_binding": {"$ref": "#/$defs/mls_governance_binding"},
            "created_at": {"$ref": "#/$defs/timestamp"},
        },
        "allOf": [
            {
                "properties": {
                    "governance_binding": {
                        "properties": {
                            "base_group_state_ref": {"type": "null"},
                            "previous_epoch": {"const": 0},
                            "next_epoch": {"const": 0},
                            "key_access_revision": {"const": 0},
                        }
                    }
                }
            }
        ],
        "additionalProperties": False,
    }
    defs["mls_commit_payload"] = {
        "type": "object",
        "required": [
            "base_group_state_ref",
            "previous_epoch",
            "next_epoch",
            "covers_key_access_revision",
            "commit_bytes_b64",
            "governance_binding",
        ],
        "properties": {
            "base_group_state_ref": {"$ref": "#/$defs/event_ref"},
            "previous_epoch": {"type": "integer", "minimum": 0},
            "next_epoch": {"type": "integer", "minimum": 1},
            "covers_key_access_revision": {"type": "integer", "minimum": 0},
            "commit_bytes_b64": {
                "type": "string",
                "minLength": 1,
                "pattern": "^[A-Za-z0-9_-]+$",
            },
            "commit_message_ref": {"$ref": "./common-ids.schema.json#/$defs/blob_ref"},
            "governance_binding": {"$ref": "#/$defs/mls_governance_binding"},
        },
        "additionalProperties": False,
    }
    defs["realm_governance_station_change_payload"] = {
        "type": "object",
        "required": [
            "expected_authority_generation",
            "expected_realm_stream_commit_id",
            "new_governance_station_id",
        ],
        "properties": {
            "expected_authority_generation": {"type": "integer", "minimum": 0},
            "expected_realm_stream_commit_id": {
                "$ref": "./common-ids.schema.json#/$defs/realm_commit_id"
            },
            "new_governance_station_id": {
                "$ref": "./common-ids.schema.json#/$defs/did_core_id"
            },
        },
        "additionalProperties": False,
    }
    defs["poll_response_head"] = {
        "type": "object",
        "required": ["poll_event_ref", "response_event_ref"],
        "properties": {
            "poll_event_ref": {"$ref": "#/$defs/event_ref"},
            "response_event_ref": {"$ref": "#/$defs/event_ref"},
        },
        "additionalProperties": False,
    }
    message = defs["message_create_payload"]
    message["properties"]["poll_response_heads"] = {
        "type": "array",
        "minItems": 1,
        "maxItems": 64,
        "uniqueItems": True,
        "items": {"$ref": "#/$defs/poll_response_head"},
        "description": (
            "Typed replacement for the retired generic causal_refs carrier. "
            "Each entry binds a poll to the exact response Event being superseded."
        ),
    }
    for name in (
        "mls_commit_failed_payload",
        "mls_keypackage_payload",
        "mls_proposal_payload",
        "mls_welcome_payload",
        "realm_authority_reset_payload",
        "realm_digest_suite_transition_payload",
        "realm_notary_payload",
        "realm_upgrade_state_payload",
        "fork_resolution_payload",
        "notary_fault_equivocation_payload",
        "notary_fault_censorship_payload",
        "organization_recovery_key_register_payload",
        "organization_recovery_key_rotate_payload",
        "organization_recovery_archive",
        "sidecar_mls_binding",
    ):
        defs.pop(name, None)
    audit_release = defs.get("audit_release_payload")
    if audit_release:
        audit_release["required"] = [
            field for field in audit_release.get("required", []) if field != "seal_ref"
        ]
        audit_release.get("properties", {}).pop("seal_ref", None)
        audit_release["description"] = (
            "Payload for ak.audit.release. The current governance Station validates "
            "the notice, policy and current authorization atomically; the Event "
            "does not carry a Seal or caller-selected safety basis."
        )
    device_reanchor = defs.get("device_reanchor_payload")
    if device_reanchor:
        device_reanchor["required"] = [
            field
            for field in device_reanchor.get("required", [])
            if field != "pre_fence_seal_frontier"
        ]
        device_reanchor.get("properties", {}).pop("pre_fence_seal_frontier", None)
    consent_grant = defs.get("consent_grant_payload")
    if consent_grant:
        consent_grant["description"] = (
            "Holder-private consent grant evaluated in the holder's Principal "
            "Control Realm. The governance Station serializes changes; no Cell or "
            "OR-Set tag is exposed on wire."
        )
    consent_revoke = defs.get("consent_revoke_payload")
    if consent_revoke:
        consent_revoke["required"] = ["consent_id"]
        consent_revoke.get("properties", {}).pop("observed_dot_ids", None)
        consent_revoke["description"] = (
            "Revoke the current consent identified by consent_id. The governance "
            "Station applies this Event in stream order, so no observed-dot set is required."
        )
    audit_accessed = defs.get("audit_accessed_payload")
    if audit_accessed:
        for field in ("target_cell_id", "cell_head_before", "cell_head_after"):
            audit_accessed.get("properties", {}).pop(field, None)
        for clause in audit_accessed.get("allOf", []):
            then = clause.get("then", {})
            if isinstance(then.get("required"), list):
                then["required"] = [
                    field
                    for field in then["required"]
                    if field
                    not in {"target_cell_id", "cell_head_before", "cell_head_after"}
                ]
        audit_accessed["description"] = (
            "Strict payload for ak.audit.accessed. It binds the writer, logical "
            "target and any paired Event. The current governance Station evaluates "
            "the access against committed typed state; no Cell or caller-authored "
            "state-head digest is carried."
        )
    defs.pop("seal_ref", None)
    save(path, payload)


def prune_event_payload_definitions() -> None:
    path = SCHEMAS / "event-payload.schema.json"
    payload = load(path)
    seeds: set[str] = set()
    registry = load(REGISTRY)
    for row in registry["event_kind_registry"]["event_kinds"]:
        if row.get("status") != "active":
            continue
        ref = row.get("payload_schema_ref", "")
        marker = "schemas/event-payload.schema.json#/$defs/"
        if ref.startswith(marker):
            seeds.add(ref.removeprefix(marker).split("/", 1)[0])
    for row in registry["schema_registry"]["schemas"]:
        if row.get("file") != "schemas/event-payload.schema.json":
            continue
        fragment = row.get("fragment", "")
        marker = "#/$defs/"
        if fragment.startswith(marker):
            seeds.add(fragment.removeprefix(marker).split("/", 1)[0])
    for schema_path in SCHEMAS.glob("*.schema.json"):
        if schema_path == path or f"schemas/{schema_path.name}" in RETIRED_SCHEMA_FILES:
            continue
        for ref in refs_in(load(schema_path)):
            marker = "./event-payload.schema.json#/$defs/"
            if ref.startswith(marker):
                seeds.add(ref.removeprefix(marker).split("/", 1)[0])
    retained: set[str] = set()
    pending = list(seeds)
    while pending:
        name = pending.pop()
        if name in retained or name not in payload["$defs"]:
            continue
        retained.add(name)
        for ref in refs_in(payload["$defs"][name]):
            if ref.startswith("#/$defs/"):
                pending.append(ref.removeprefix("#/$defs/").split("/", 1)[0])
    payload["$defs"] = {
        name: value for name, value in payload["$defs"].items() if name in retained
    }
    save(path, payload)


def remove_retired_common_ids() -> None:
    path = SCHEMAS / "common-ids.schema.json"
    common = load(path)
    for name in (
        "collision_variant_record_id",
        "history_request_id",
        "history_response_id",
        "recovery_key_id",
        "realm_state_snapshot_id",
    ):
        common["$defs"].pop(name, None)
    save(path, common)


def migrate_registry() -> None:
    registry = load(REGISTRY)
    kinds = registry["event_kind_registry"]["event_kinds"]
    retired = {
        "ak.realm.upgrade",
        "ak.realm.organization_recovery_key.register",
        "ak.realm.organization_recovery_key.rotate",
        "ak.realm.notary",
        "ak.realm.digest_suite_transition",
        "ak.realm.authority.reset",
        "ak.fork.resolution",
        "ak.notary.fault.equivocation",
        "ak.notary.fault.censorship",
        "ak.mls.proposal",
        "ak.mls.commit_failed",
        "ak.mls.welcome",
        "ak.mls.keypackage",
    }
    kinds = [row for row in kinds if row["event_kind"] not in retired]
    current_payload_descriptions = {
        "ak.agent.key.revoke": (
            "Agent signing-key revocation. The current governance Station verifies the "
            "controller and active key, then commits the exact Event on its authority stream; "
            "the payload carries no Seal or authorization basis."
        ),
        "ak.audit.session.close": (
            "Terminal audit release-session close. The current governance Station compares "
            "release_refs with its authority-committed session projection and serializes close "
            "against release Events on the applicable stream."
        ),
        "ak.self.agent.pause": (
            "Agent lifecycle transition to paused. Current controller authority and the active "
            "agent state are checked atomically when the governance Station commits the Event."
        ),
        "ak.self.agent.resume": (
            "Agent lifecycle transition from paused to active. The governance Station revalidates "
            "controller, agent key, capability, Realm policy and accountability state at commit."
        ),
    }
    for row in kinds:
        replacement = current_payload_descriptions.get(row["event_kind"])
        if replacement is not None:
            row["payload"] = replacement
    if not any(row["event_kind"] == "ak.realm.governance_station.change" for row in kinds):
        kinds.append(
            {
                "event_kind": "ak.realm.governance_station.change",
                "category": "realm",
                "status": "active",
                "verb_form": "base",
                "wire_scope": "durable_event",
                "reducer_input": True,
                "payload": "Planned Realm governance Station transfer intent",
                "payload_schema_ref": (
                    "schemas/event-payload.schema.json#/$defs/"
                    "realm_governance_station_change_payload"
                ),
                "id_source": "not_an_object_id",
            }
        )
    registry["event_kind_registry"]["event_kinds"] = sorted(
        kinds, key=lambda row: row["event_kind"]
    )
    event_registry = registry["event_kind_registry"]
    event_registry["registry_rules"] = [
        "Every standard ak.* Event.kind admitted through Event Envelope MUST appear in this registry and resolve to exactly one closed payload schema.",
        "An accepted durable Event becomes shared history only when the current authority includes its exact bytes in a signed RealmCommit for the Event's own Realm, Circle, or Sidecar stream.",
        "Stream identity is derived from the Event's closed scope. Realm, each Circle, and each Sidecar have independent commit streams; no Realm-global total chain exists.",
        "Event carries no chain predecessor or authority-commit proof. Only RealmCommit carries previous_commit_ref, and only within the same stream.",
        "Reducers derive typed current results by replaying committed Events in stream position order. Account-private material is outside shared authority-commit streams.",
    ]
    event_registry.pop("cell_contracts", None)
    event_registry["bootstrap_event_kinds"] = [
        kind for kind in event_registry.get("bootstrap_event_kinds", []) if kind not in retired
    ]
    event_registry.pop("transition_templates", None)
    event_registry.pop("transition_contracts", None)
    event_registry.pop("execution_contract", None)
    event_registry.get("history_admission_contract", {})["consumer_schema_bindings"] = []
    registry.pop("state_model_contracts", None)
    registry.pop("authorization_dependency_registry", None)
    registry["current_result_registry"] = {
        "description": "Closed typed current-result families derived from authority-committed Events. Selectors are domain types, never legacy Cell IDs.",
        "result_kinds": [
            {
                "result_kind": "realm_profile",
                "schema_ref": "schemas/typed-current-result.schema.json#/$defs/realm_profile_result",
            },
            {
                "result_kind": "realm_policy",
                "schema_ref": "schemas/typed-current-result.schema.json#/$defs/realm_policy_result",
            },
            {
                "result_kind": "member_state",
                "schema_ref": "schemas/typed-current-result.schema.json#/$defs/member_state_result",
            },
            {
                "result_kind": "strand",
                "schema_ref": "schemas/typed-current-result.schema.json#/$defs/strand_result",
            },
            {
                "result_kind": "message_reactions",
                "schema_ref": "schemas/typed-current-result.schema.json#/$defs/message_reactions_result",
            },
            {
                "result_kind": "mls_group",
                "schema_ref": "schemas/typed-current-result.schema.json#/$defs/mls_group_result",
            },
        ],
        "version": registry.get("current_result_registry", {}).get("version", "2026-09-15.1"),
        "generated_at": registry.get("current_result_registry", {}).get("generated_at", registry["generated_at"]),
    }
    registry["authority_source_registry"]["registry_rules"] = [
        "A non-grant authorization source is active only when one exact active row is selected by authority_source_id; syntax or an arbitrary Event reference never creates authority.",
        "The current governance Station rederives activation, actor, resource and lifecycle predicates from its authority-committed current state and fails closed on missing, conflicting, non-canonical or freshness-unknown dependencies.",
        "A successful preflight or cached current result is advisory to the caller and never replaces atomic authorization at RealmCommit issuance.",
    ]
    actions = registry.get("capability_action_registry", {}).get("actions", [])
    retired_actions = {
        "ak.mls.proposal",
        "ak.realm.authority.reset",
        "ak.realm.upgrade",
        "ak.fork.resolution",
    }
    actions = [row for row in actions if row.get("action") not in retired_actions]
    if not any(
        row.get("action") == "ak.realm.governance_station.change"
        for row in actions
    ):
        actions.append(
            {
                "action": "ak.realm.governance_station.change",
                "category": "management",
                "risk_tier": "high",
                "required_constraints": [],
                "target_event_kinds": ["ak.realm.governance_station.change"],
                "profile": None,
                "event_mapping_kind": "same_name",
                "root_control_only": True,
            }
        )
    registry["capability_action_registry"]["actions"] = actions
    for action in actions:
        for field in ("target_event_kinds", "event_kinds"):
            if field in action:
                action[field] = [kind for kind in action[field] if kind not in retired]
        if action.get("action") == "ak.mls.commit":
            action["event_mapping_kind"] = "same_name"
        elif action.get("action") in {
            "ak.mls.keypackage",
            "ak.mls.welcome",
            "ak.mls.welcome.own_device",
        }:
            action["event_mapping_kind"] = "non_event_surface"

    schema_rows = registry["schema_registry"]["schemas"]
    schema_rows = [row for row in schema_rows if row.get("file") not in RETIRED_SCHEMA_FILES]
    additions = {
        "ak.schema.authority_commit_operations.v1": (
            "schemas/authority-commit-operations.schema.json",
            "Authority submission, stream scan, authority bundle and handoff operations.",
        ),
        "ak.schema.detached_object_signature.v1": (
            "schemas/detached-object-signature.schema.json",
            "Closed non-Event signature carrier for authority and delivery objects.",
        ),
        "ak.schema.realm_commit.v1": (
            "schemas/realm-commit.schema.json",
            "Authority-signed finality record for one Realm, Circle or Sidecar stream.",
        ),
        "ak.schema.realm_authority_bundle.v1": (
            "schemas/realm-authority-bundle.schema.json",
            "Genesis-to-current authority discovery proof bundle.",
        ),
        "ak.schema.realm_authority_handoff.v1": (
            "schemas/realm-authority-handoff.schema.json",
            "Dual-signed planned authority generation transfer.",
        ),
        "ak.schema.mls_commit_submission.v1": (
            "schemas/mls-commit-submission.schema.json",
            "Atomic MLS Commit and Welcome submission.",
        ),
        "ak.schema.mls_welcome_delivery.v1": (
            "schemas/mls-welcome-delivery.schema.json",
            "Producer-signed recipient Welcome delivery.",
        ),
        "ak.schema.typed_current_result.v1": (
            "schemas/typed-current-result.schema.json",
            "Closed typed current-result selector and value union.",
        ),
    }
    by_id = {row["schema_id"]: row for row in schema_rows}
    for schema_id, (file, description) in additions.items():
        by_id[schema_id] = {
            "schema_id": schema_id,
            "file": file,
            "status": "active",
            "description": description,
        }
    authority_policy = by_id.get("ak.schema.authority_set_policy.v1")
    if authority_policy:
        authority_policy["description"] = (
            "Recovery or admission signer policy accepted at one RealmCommit."
        )
        authority_policy["consumer_binding"] = {
            "kind": "standalone_schema_alias",
            "selector": "schemas/authority-set-policy.schema.json",
            "normative_ref": "zh/sync/authority-commit-log.md#2-producer-event",
        }
    registry["schema_registry"]["schemas"] = sorted(
        by_id.values(), key=lambda row: row["schema_id"]
    )

    high_security = registry["operation_registry"].get(
        "high_security_session_authentication_policy", {}
    )
    high_security["unauthenticated_public_projection_operations"] = [
        operation_id
        for operation_id in high_security.get(
            "unauthenticated_public_projection_operations", []
        )
        if operation_id != "ak.self.events.read.describe.v1"
    ]

    ids = registry["id_kind_registry"]["id_kinds"]
    retired_id_kinds = {
        "collision_variant_record",
        "history_request",
        "history_response",
        "realm_state_snapshot",
        "recovery_key",
        "realm_commit",
        "realm_authority_handoff",
        "realm_snapshot",
    }
    ids = [row for row in ids if row["kind"] not in retired_id_kinds]
    new_ids = {
        "mls_welcome_delivery": (
            "mls",
            "ak:mls_welcome_delivery:<uuidv7>",
            "producer_allocated",
            "producer_signature",
        ),
        "keypackage_claim": (
            "mls",
            "ak:keypackage_claim:<uuidv7>",
            "producer_allocated",
            "producer_signature",
        ),
    }
    existing = {row["kind"] for row in ids}
    for row in ids:
        if row["kind"] == "keypackage_claim":
            row["identity_authority"] = "producer_signature"
    for kind, (category, wire_form, id_form, authority) in new_ids.items():
        if kind not in existing:
            ids.append(
                {
                    "kind": kind,
                    "category": category,
                    "status": "active",
                    "wire_form": wire_form,
                    "description": f"{kind} protocol identifier.",
                    "id_form": id_form,
                    "identity_authority": authority,
                }
            )
    registry["id_kind_registry"]["id_kinds"] = sorted(ids, key=lambda row: row["kind"])
    registry["id_kind_registry"]["special_forms"] = [
        row
        for row in registry["id_kind_registry"].get("special_forms", [])
        if row.get("kind") not in {"seal", "cell"}
    ]
    existing_special = {
        row["kind"] for row in registry["id_kind_registry"]["special_forms"]
    }
    for kind in ("realm_commit", "realm_authority_handoff", "realm_snapshot"):
        if kind not in existing_special:
            registry["id_kind_registry"]["special_forms"].append(
                {
                    "kind": kind,
                    "wire_form": f"ak:{kind}:<44-char-base64url-no-pad>",
                    "payload_pattern": "[A-Za-z0-9_-]{44}",
                    "status": "active",
                    "content_addressed": True,
                    "storage_recommendation": "Store the decoded 33-byte suite-tagged digest.",
                    "description": f"Content-addressed {kind} canonical body identifier.",
                }
            )
    registry["id_kind_registry"]["special_forms"].sort(key=lambda row: row["kind"])

    operations = registry["operation_registry"]["operations"]
    obsolete_markers = (
        ".authorization_leases.",
        ".current_signer_evidence.",
        ".issue_controller_gate_attestation.",
        ".invites.command.dispatch.",
        ".genesis_notary.",
        ".seals.",
        ".control_proposal_acks.",
        ".control_proposal_decisions.",
        ".history_key_requests.",
        ".history_key_responses.",
        ".organization_recovery_archives.",
        ".events.read.sibling_positions.",
        ".moderation.read.franking_seal_observation.",
        ".events.read.delivery_status.",
        ".events.read.describe.",
        ".events.read.frontier.",
        ".events.read.resolve.",
    )
    operations = [
        row
        for row in operations
        if not any(marker in row["operation_id"] for marker in obsolete_markers)
    ]
    by_operation = {row["operation_id"]: row for row in operations}
    replacements = {
        "ak.self.events.command.submit.v1": (
            "POST /_arkret/self/events",
            "SelfEvents/Submit",
            "self.events.command.submit",
            "Submit an exact producer Event to its current Realm governance Station. The Account Station reports committed only after receiving RealmCommit.",
            "schemas/authority-commit-operations.schema.json#/$defs/submit_request",
            "schemas/authority-commit-operations.schema.json#/$defs/submit_outcome",
        ),
        "ak.peer.events.command.submit.v1": (
            "POST /_arkret/peer/events",
            "PeerEvents/Submit",
            "peer.events.command.submit",
            "Forward an exact producer Event to the verified current governance Station; a non-authority peer cannot accept it locally.",
            "schemas/authority-commit-operations.schema.json#/$defs/submit_request",
            "schemas/authority-commit-operations.schema.json#/$defs/submit_outcome",
        ),
        "ak.self.events.read.scan.v1": (
            "POST /_arkret/self/streams/scan",
            "SelfStreams/Scan",
            "self.streams.read.scan",
            "Read one authorized Realm, Circle, or Sidecar stream by continuous stream_position.",
            "schemas/authority-commit-operations.schema.json#/$defs/stream_scan_request",
            "schemas/authority-commit-operations.schema.json#/$defs/stream_scan_outcome",
        ),
        "ak.peer.events.read.scan.v1": (
            "POST /_arkret/peer/streams/scan",
            "PeerStreams/Scan",
            "peer.streams.read.scan",
            "Replicate one visibility-authorized stream from its current governance Station.",
            "schemas/authority-commit-operations.schema.json#/$defs/stream_scan_request",
            "schemas/authority-commit-operations.schema.json#/$defs/stream_scan_outcome",
        ),
        "ak.peer.events.read.resolve_committed.v1": (
            "POST /_arkret/peer/streams/resolve",
            "PeerStreams/ResolveCommitted",
            "peer.streams.read.resolve_committed",
            "Directory-only exact resolve: authenticate the Directory, revalidate its source-signed DirectorySourceRefAccess, and resolve only byte-identical Event/Commit/stream/position refs contained by that carrier; no scan or caller-supplied Event is accepted as proof.",
            "schemas/authority-commit-operations.schema.json#/$defs/committed_event_resolve_request",
            "schemas/authority-commit-operations.schema.json#/$defs/committed_event_resolve_outcome",
        ),
        "ak.open.realm_authority.read.bundle.v1": (
            "POST /_arkret/open/realm-authority/bundle",
            "OpenRealmAuthority/Bundle",
            "open.realm_authority.read.bundle",
            "Return a nonce-bound genesis-to-current authority chain; locators are hints and never authority.",
            "schemas/authority-commit-operations.schema.json#/$defs/authority_bundle_request",
            "schemas/realm-authority-bundle.schema.json",
        ),
        "ak.peer.realm_authority.command.handoff.v1": (
            "POST /_arkret/peer/realm-authority/handoff",
            "PeerRealmAuthority/Handoff",
            "peer.realm_authority.command.handoff",
            "Install a planned dual-signed authority handoff after complete snapshot and all stream heads are imported.",
            "schemas/authority-commit-operations.schema.json#/$defs/handoff_request",
            "schemas/realm-authority-handoff.schema.json",
        ),
    }
    for operation_id, values in replacements.items():
        http, grpc, mq, notes, request_ref, response_ref = values
        prior = by_operation.get(operation_id, {})
        by_operation[operation_id] = {
            "operation_id": operation_id,
            "http": http,
            "grpc": grpc,
            "mq": mq,
            "notes": notes,
            "body_class": "non_streaming_json",
            "success_shape_kind": "schema_resource",
            "request_schema_ref": request_ref,
            "response_schema_ref": response_ref,
            **({"max_canonical_body_bytes": prior["max_canonical_body_bytes"]}
               if "max_canonical_body_bytes" in prior else {}),
            **(
                {
                    "idempotency_mechanism": "canonical_hash",
                    "canonical_hash_input": "full_body",
                    "retry_safe": True,
                }
                if ".command." in operation_id
                else {}
            ),
            **(
                {
                    "durable_effect": {
                        "kind": "event_log",
                        "event_kind_source": "$request.event.kind",
                    }
                }
                if operation_id
                in {
                    "ak.self.events.command.submit.v1",
                    "ak.peer.events.command.submit.v1",
                }
                else {
                    "durable_effect": {
                        "kind": "none",
                        "rationale": (
                            "installs_only_the_verified_authority_generation_"
                            "snapshot_and_private_stream_heads"
                        ),
                    }
                }
                if operation_id == "ak.peer.realm_authority.command.handoff.v1"
                else {}
            ),
        }
    final_operations = sorted(
        by_operation.values(), key=lambda row: row["operation_id"]
    )
    for row in final_operations:
        for field in ("request_schema_ref", "response_schema_ref"):
            if isinstance(row.get(field), str):
                row[field] = row[field].replace("consent_cell_view", "consent_view")
                row[field] = row[field].replace("consent_cell_list", "consent_list")
        if isinstance(row.get("notes"), str):
            row["notes"] = row["notes"].replace("consent_cell_view", "consent_view")
            row["notes"] = row["notes"].replace("consent_cell_list", "consent_list")
        operation_id = row.get("operation_id")
        if operation_id == "ak.self.moderation.command.report.v1":
            row["notes"] = (
                "Carries one caller-signed moderation report Event. The current governance Station "
                "revalidates the authenticated reporter, target visibility, effective scope and "
                "current authorization, then commits the exact Event on that scope's authority "
                "stream. The Event contains only its closed producer, scope, payload and signature fields."
            )
        elif operation_id == "ak.self.realm_join.command.prepare.v1":
            row["notes"] = (
                "Prepares one join, knock or invite acceptance against the Realm's current "
                "governance Station. The Station is discovered from the current authority bundle, "
                "not from the inviter or genesis Station. Preparation freezes the exact request "
                "and current policy revision; final admission is an authority commit and performs "
                "no actor-frontier, Seal-basis or CBS calculation."
            )
        elif operation_id in {
            "ak.self.signal.command.send.v1",
            "ak.peer.signal.command.relay.v1",
        }:
            row["notes"] = (
                "Transient encrypted Signal rail. It creates no durable Event or RealmCommit, "
                "does not advance any authority stream, and grants no delivery or authorization proof."
            )
        elif operation_id == "ak.self.security_transaction.command.continue.v1":
            row["notes"] = (
                "Continues only the canonical next transaction step. Recovery's terminal step "
                "carries the replacement-device-signed recovery receipt; the current governance "
                "Station atomically validates both prepared producer Events, issues their PCR-stream "
                "RealmCommit, advances device generation, activates the device and consumes the "
                "session. The client never supplies or signs the RealmCommit."
            )
    registry["operation_registry"]["operations"] = final_operations
    known_operations = {row["operation_id"] for row in final_operations}
    groups = []
    for group in registry["operation_registry"].get("surface_groups", []):
        if group.get("surface") == "authority_commit":
            continue
        group["operations"] = [
            operation_id
            for operation_id in group.get("operations", [])
            if operation_id in known_operations
        ]
        if group["operations"]:
            groups.append(group)
    authority_operations = sorted(
        {
            "ak.open.realm_authority.read.bundle.v1",
            "ak.peer.events.read.resolve_committed.v1",
            "ak.peer.realm_authority.command.handoff.v1",
        }
        & known_operations
    )
    groups.append(
        {
            "surface": "authority_commit",
            "operations": authority_operations,
            "surface_class": "core",
        }
    )
    registry["operation_registry"]["surface_groups"] = groups
    bundles = []
    for bundle in registry["operation_registry"].get("operation_bundles", []):
        bundle["members"] = [
            member
            for member in bundle.get("members", [])
            if member.get("operation_id") in known_operations
        ]
        if bundle["members"]:
            bundles.append(bundle)
    registry["operation_registry"]["operation_bundles"] = bundles

    feature_registry = registry.get("feature_registry", {})
    feature_registry["features"] = [
        row
        for row in feature_registry.get("features", [])
        if row.get("feature_id") != "ak.feature.history_key_recovery.v1"
        and (
            not isinstance(row.get("defined_in"), str)
            or (ROOT / "spec/v1" / row["defined_in"]).exists()
        )
    ]
    old_features = {
        row["feature_id"]: row
        for row in load_old_decenter(
            "spec/v1/artifacts/registry/contract-registry.json"
        )["feature_registry"]["features"]
    }
    present_features = {
        row["feature_id"] for row in feature_registry["features"]
    }
    for feature_id in (
        "ak.feature.blob.resumable_upload.tus.v1",
        "ak.feature.cursor_revoke_high_assurance.v1",
    ):
        if feature_id not in present_features:
            feature_registry["features"].append(copy.deepcopy(old_features[feature_id]))
    feature_registry["features"].sort(key=lambda row: row["feature_id"])
    save(REGISTRY, registry)


def migrate_auxiliary_registries() -> None:
    for fixture_name in (
        "encoding-fixture.json",
        "keypackage-lifecycle-fixture.json",
        "schema-validation-fixture.json",
    ):
        fixture_path = ROOT / "spec/v1/artifacts/fixtures" / fixture_name
        save(
            fixture_path,
            load_old_decenter(f"spec/v1/artifacts/fixtures/{fixture_name}"),
        )

    validation_path = ROOT / "spec/v1/artifacts/fixtures/schema-validation-fixture.json"
    validation = load(validation_path)
    retained_validation_names = {
        "psi_padded_problem_quota_exhausted_valid",
        "psi_padded_problem_policy_denied_valid",
        "psi_padded_problem_duplicate_conflict_valid",
        "psi_padded_problem_batch_unavailable_valid",
        "psi_padded_problem_old_envelope_rejected",
        "psi_padded_problem_extra_extension_rejected",
        "psi_padded_problem_type_status_mismatch_rejected",
        "psi_padded_problem_missing_padding_rejected",
        "psi_padded_problem_non_space_padding_rejected",
        "recovery_proof_canonical_public_material_valid",
        "service_describe_valid",
        "service_describe_x_metadata_ignored_valid",
    }
    validation["schema_validation_cases"] = [
        row
        for row in validation.get("schema_validation_cases", [])
        if isinstance(row, dict)
        and row.get("name") in retained_validation_names
        and isinstance(row.get("schema_ref"), str)
        and schema_ref_resolves(row["schema_ref"])
    ]
    save(validation_path, validation)

    encoding_path = ROOT / "spec/v1/artifacts/fixtures/encoding-fixture.json"
    encoding = load(encoding_path)
    encoding["description"] = (
        "Canonical encoding and digest-algorithm vectors for the current "
        "authority-commit protocol."
    )
    encoding["vectors"] = [
        row
        for row in encoding.get("vectors", [])
        if isinstance(row, dict)
        and row.get("vector_id")
        in {
            "ak.vector.encoding.canonical_json.basic.v1",
            "ak.vector.encoding.digest.blake3.v1",
            "ak.vector.encoding.encrypted_envelope_digest.v1",
        }
    ]
    save(encoding_path, encoding)

    keypackage_path = ROOT / "spec/v1/artifacts/fixtures/keypackage-lifecycle-fixture.json"
    keypackage = load(keypackage_path)
    keypackage["schema_validation_cases"] = [
        row
        for row in keypackage.get("schema_validation_cases", [])
        if isinstance(row, dict)
        and isinstance(row.get("schema_ref"), str)
        and schema_ref_resolves(row["schema_ref"])
    ]
    save(keypackage_path, keypackage)

    crypto_fixture = ROOT / "spec/v1/artifacts/fixtures/crypto-signature-fixture.json"
    if crypto_fixture.exists():
        crypto = load(crypto_fixture)
        crypto["description"] = (
            "Detached-signature algorithm KATs. The signed binding objects are "
            "cryptographic test messages, not Event or RealmCommit wire examples."
        )
        for vector in crypto.get("vectors", []):
            if not isinstance(vector, dict):
                continue
            for retired_member in (
                "event_without_proofs",
                "canonical_event_payload",
                "event_with_proof",
            ):
                vector.pop(retired_member, None)
            if isinstance(vector.get("description"), str):
                vector["description"] = vector["description"].replace(
                    "for a Arkret Event Envelope", "for a detached signed object"
                )
        save(crypto_fixture, crypto)
    active = {
        row["event_kind"]
        for row in load(REGISTRY)["event_kind_registry"]["event_kinds"]
        if row.get("status") == "active"
    }
    protocol_path = ARTIFACT_REGISTRY / "protocol-layer-registry.json"
    protocol = load(protocol_path)
    for layer, kinds in protocol["event_kinds"].items():
        protocol["event_kinds"][layer] = [kind for kind in kinds if kind in active]
    if "ak.realm.governance_station.change" not in protocol["event_kinds"]["kernel"]:
        protocol["event_kinds"]["kernel"].append("ak.realm.governance_station.change")
        protocol["event_kinds"]["kernel"].sort()
    save(protocol_path, protocol)

    gaps_path = ARTIFACT_REGISTRY / "event-kind-vector-gap-registry.json"
    gaps = load(gaps_path)
    gaps["uncovered_event_kinds"] = [
        row for row in gaps["uncovered_event_kinds"] if row["event_kind"] in active
    ]
    if (
        "ak.account.blocklist" in active
        and not any(
            row.get("event_kind") == "ak.account.blocklist"
            for row in gaps["uncovered_event_kinds"]
        )
    ):
        gaps["uncovered_event_kinds"].append(
            {
                "event_kind": "ak.account.blocklist",
                "priority": "normal",
                "rationale": "Actor-private account blocklist projection lacks a directly searchable vector.",
            }
        )
    gaps["uncovered_event_kinds"] = [
        row
        for row in gaps["uncovered_event_kinds"]
        if row["event_kind"] != "ak.realm.governance_station.change"
    ]
    gaps["uncovered_event_kinds"].sort(key=lambda row: row["event_kind"])
    save(gaps_path, gaps)

    profiles_path = ROOT / "spec/v1/artifacts/profiles/conformance-profiles.json"
    profiles = load(profiles_path)
    retired = {
        "ak.mls.proposal",
        "ak.mls.welcome",
        "ak.mls.keypackage",
        "ak.mls.commit_failed",
    }
    retired_feature = "ak.feature.history_key_recovery.v1"

    def strip_retired(value: object) -> None:
        if isinstance(value, dict):
            for key, item in list(value.items()):
                if isinstance(item, list):
                    kept = []
                    for entry in item:
                        if isinstance(entry, str) and (
                            entry in retired or entry == retired_feature
                        ):
                            continue
                        strip_retired(entry)
                        kept.append(entry)
                    value[key] = kept
                else:
                    strip_retired(item)
        elif isinstance(value, list):
            for item in value:
                strip_retired(item)
    strip_retired(profiles)

    retired_mls_tokens = (
        "security_frontier",
        "mls_governance_proof",
        "mls-security-frontier-registry.json",
    )

    def strip_retired_mls_contracts(value: object) -> None:
        if isinstance(value, dict):
            for key, item in list(value.items()):
                if any(token in key for token in retired_mls_tokens):
                    value.pop(key)
                    continue
                if isinstance(item, str) and any(
                    token in item for token in retired_mls_tokens
                ):
                    value.pop(key)
                    continue
                if isinstance(item, list):
                    value[key] = [
                        entry
                        for entry in item
                        if not (
                            isinstance(entry, str)
                            and any(token in entry for token in retired_mls_tokens)
                        )
                    ]
                strip_retired_mls_contracts(value.get(key))
        elif isinstance(value, list):
            for item in value:
                strip_retired_mls_contracts(item)

    strip_retired_mls_contracts(profiles)
    requirements = profiles.get("vector_group_requirements", {})
    removed_groups = {
        group_id
        for group_id, requirement in requirements.items()
        if set(requirement.get("required_fixtures", [])) & RETIRED_FIXTURE_FILES
    }
    for group_id in removed_groups:
        requirements.pop(group_id, None)
    profiles["vector_groups"] = [
        group_id
        for group_id in profiles.get("vector_groups", [])
        if group_id not in removed_groups
    ]
    authority_group = "ak.vector_group.authority_commit.v1"
    if authority_group not in profiles["vector_groups"]:
        profiles["vector_groups"].append(authority_group)
        profiles["vector_groups"].sort()
    requirements[authority_group] = {
        "required_event_kinds": ["ak.realm.governance_station.change"],
        "rejected_event_kinds": [],
        "required_schemas": [
            "ak.schema.realm_commit.v1",
            "ak.schema.realm_authority_bundle.v1",
            "ak.schema.realm_authority_handoff.v1",
        ],
        "required_fixtures": ["authority-commit-fixture.json"],
        "optional_extensions": [],
        "feature_discovery": {
            "required": ["vector_runner"],
            "unsupported_optional": "not applicable",
        },
        "operation_requirements": [
            {
                "direction": "consume",
                "operation_id": "ak.self.events.read.scan.v1",
                "binding_kind": "http_json",
            }
        ],
    }
    mls_profile_id = "ak.profile.mls_governance_binding.full.v1"
    if mls_profile_id in profiles.get("profile_requirements", {}):
        profiles["profile_requirements"][mls_profile_id] = {
            "description": (
                "MLS GroupContext binding for an independently authority-committed Realm or "
                "Circle stream. Each Genesis or Commit binds the canonical effective scope, "
                "derived MLS group id, epoch transition, and monotonic key_access_revision. "
                "Governance authorization is decided by the current governance Station before "
                "the Event is committed; MLS carries no CBS or governance-proof bundle."
            ),
            "enforcement_phases": ["build", "conformance"],
            "operation_requirements": [
                {
                    "direction": "provide",
                    "operation_id": "ak.self.keys.keypackages.command.claim.v1",
                    "binding_kind": "http_json",
                },
                {
                    "direction": "provide",
                    "operation_id": "ak.self.events.read.scan.v1",
                    "binding_kind": "http_json",
                },
                {
                    "direction": "provide",
                    "operation_id": "ak.peer.mls.read.group_state_material.v1",
                    "binding_kind": "http_json",
                },
            ],
            "inherits": [],
            "required_event_kinds": ["ak.mls.commit"],
            "rejected_event_kinds": [],
            "required_schemas": [
                "ak.schema.encrypted_envelope.v1",
                "ak.schema.realm_commit.v1",
                "ak.schema.mls_commit_submission.v1",
                "ak.schema.mls_welcome_delivery.v1",
            ],
            "required_fixtures": ["authority-commit-fixture.json"],
            "optional_extensions": ["ak.profile.mls.minimal_metadata_realm.v1"],
            "feature_discovery": {
                "required": [
                    "mls_governance_binding_extension",
                    "key_access_revision",
                    "mls_group_state_material",
                ],
                "unsupported_optional": "fail closed on scope, epoch, group id, or key-access revision mismatch",
            },
            "federation_interop_floor": {
                "is_minimum_for_mls_backed_federation": True,
                "requires_exact_extension_codepoint": "0xF1C0",
                "requires_binding_profile": mls_profile_id,
                "forbids_silent_downgrade": [
                    "omitting the GroupContext extension",
                    "using a deployment-private alternate extension codepoint",
                    "accepting a Commit whose key_access_revision does not equal the current authority projection",
                ],
            },
            "fail_closed_conditions": [
                "governance binding missing from ak.mls.commit",
                "effective_scope or derived mls_group_id mismatch",
                "previous_epoch or next_epoch mismatch",
                "key_access_revision differs from the current authority-committed projection",
                "Commit and recipient Welcome delivery are not accepted as one atomic service transaction",
            ],
        }
    known_schema_ids = {
        row["schema_id"]
        for row in load(REGISTRY)["schema_registry"]["schemas"]
    }
    known_operation_ids = {
        row["operation_id"]
        for row in load(REGISTRY)["operation_registry"]["operations"]
    }
    existing_fixtures = {
        path.name for path in (ROOT / "spec/v1/artifacts/fixtures").glob("*.json")
    }

    def clean_profile_references(value: object) -> None:
        if isinstance(value, dict):
            for key, item in list(value.items()):
                if isinstance(item, list):
                    filtered = []
                    for entry in item:
                        if isinstance(entry, str):
                            if entry.startswith("ak.schema.") and entry not in known_schema_ids:
                                continue
                            if entry.startswith("ak.") and ".v1" in entry and (
                                key in {"required_operations", "operations"}
                                and entry not in known_operation_ids
                            ):
                                continue
                            if key == "required_fixtures" and entry not in existing_fixtures:
                                continue
                        if isinstance(entry, dict):
                            fixture = entry.get("artifact_fixture")
                            if fixture and fixture not in existing_fixtures:
                                continue
                            operation_id = entry.get("operation_id")
                            if operation_id and operation_id not in known_operation_ids:
                                continue
                            clean_profile_references(entry)
                        filtered.append(entry)
                    value[key] = filtered
                else:
                    clean_profile_references(item)

    clean_profile_references(profiles)
    save(profiles_path, profiles)
    vector_path = ARTIFACT_REGISTRY / "vector-registry.json"
    vectors = load(vector_path)

    def references_retired_fixture(row: dict) -> bool:
        return any(
            Path(reference).name in RETIRED_FIXTURE_FILES
            for field in ("applies_to_fixtures", "source_refs")
            for reference in row.get(field, [])
            if isinstance(reference, str)
        )

    old_vectors = load_old_decenter(
        "spec/v1/artifacts/registry/vector-registry.json"
    )["vectors"]
    required_kat_ids = {
        row["kat_vector_id"]
        for registry_name, collection_name in (
            ("signature-alg-registry.json", "algorithms"),
            ("digest-suite-registry.json", "suites"),
            ("hpke-suite-registry.json", "suites"),
            ("mls-ciphersuite-registry.json", "ciphersuites"),
        )
        for row in load(ARTIFACT_REGISTRY / registry_name).get(collection_name, [])
        if isinstance(row.get("kat_vector_id"), str)
    }
    required_kat_ids.add("ak.vector.moderation.franking_proof_transcript.v1")
    required_kat_ids.add("ak.vector.encoding.encrypted_envelope_digest.v1")
    vectors["vectors"] = [
        copy.deepcopy(row)
        for row in old_vectors
        if row.get("vector_id") in required_kat_ids
    ]
    for row in vectors["vectors"]:
        row["source_refs"] = [
            reference
            for reference in row.get("source_refs", [])
            if (ROOT / reference).exists()
        ]
        row["applies_to_fixtures"] = [
            fixture
            for fixture in row.get("applies_to_fixtures", [])
            if (ROOT / "spec/v1/artifacts/fixtures" / fixture).exists()
        ]
        if not row.get("applies_to_fixtures"):
            row.pop("applies_to_fixtures", None)
    authority_vector = "ak.vector.authority_commit.independent_streams.v1"
    vectors["vectors"] = [
        row for row in vectors["vectors"] if row.get("vector_id") != authority_vector
    ]
    vectors["vectors"].append(
        {
            "vector_id": authority_vector,
            "status": "active",
            "domain": "authority_commit",
            "applies_to_fixtures": ["authority-commit-fixture.json"],
            "description": (
                "Realm, Circle and Sidecar streams each start and advance their own "
                "predecessor chain; planned handoff transfers every private head "
                "without exposing hidden stream existence in the public bundle."
            ),
            "source_refs": [
                "spec/v1/artifacts/fixtures/authority-commit-fixture.json",
                "spec/v1/zh/sync/authority-commit-log.md",
            ],
        }
    )
    known_vector_groups = set(profiles["vector_groups"])
    for row in vectors["vectors"]:
        if "applies_to_vector_groups" in row:
            row["applies_to_vector_groups"] = [
                group_id
                for group_id in row["applies_to_vector_groups"]
                if group_id in known_vector_groups
            ]
    vectors["vectors"].sort(key=lambda row: row["vector_id"])
    save(vector_path, vectors)
    known_vectors = {row["vector_id"] for row in vectors["vectors"]}

    def clean_vector_references(value: object) -> None:
        if isinstance(value, dict):
            for key, item in list(value.items()):
                if isinstance(item, list):
                    value[key] = [
                        entry
                        for entry in item
                        if not (
                            isinstance(entry, str)
                            and entry.startswith("ak.vector.")
                            and entry not in known_vectors
                        )
                    ]
                    for entry in value[key]:
                        clean_vector_references(entry)
                else:
                    clean_vector_references(item)

    clean_vector_references(profiles)
    save(profiles_path, profiles)

    runtime_scope_path = ARTIFACT_REGISTRY / "agent-runtime-scope-registry.json"
    runtime_scope = load(runtime_scope_path)
    interactive_operations = [
        "ak.self.events.command.submit.v1",
        "ak.self.events.read.scan.v1",
        "ak.self.events.stream.subscribe.v1",
    ]
    runtime_scope["capability_sets"]["interactive_chat"][
        "activation_operations"
    ] = interactive_operations
    runtime_scope["capability_sets"]["interactive_chat"][
        "mandatory_operations"
    ] = interactive_operations
    runtime_scope["feature_additions"].pop("delayed_or_offline_publish", None)
    runtime_scope["invariants"] = [
        invariant
        for invariant in runtime_scope.get("invariants", [])
        if "frontier.v1" not in invariant
    ]
    save(runtime_scope_path, runtime_scope)

    proof_path = ARTIFACT_REGISTRY / "proof-context-registry.json"
    proof = load(proof_path)
    device_authorize_contexts = {
        "ak.device_authorize_accepted_device_possession_proof.v1",
        "ak.device_authorize_applet_managed_possession_proof.v1",
        "ak.device_authorize_possession_proof.v1",
        "ak.device_authorize_recovery_possession_proof.v1",
    }
    moved_device_domains = [
        row
        for row in proof["contexts"]
        if row.get("context") in device_authorize_contexts
    ]
    proof["contexts"] = [
        row
        for row in proof["contexts"]
        if row.get("context") not in device_authorize_contexts
        if row.get("schema_ref")
        != "schemas/realm-state-snapshot.schema.json#/$defs/realm_state_snapshot_witness_attestation"
        and not row.get("context", "").startswith("ak.realm_commit_proof.")
        and not row.get("context", "").startswith("ak.realm_authority_handoff_proof.")
        and not row.get("context", "").startswith("ak.realm_authority_current_assertion_proof.")
        and not row.get("context", "").startswith("ak.mls_welcome_delivery_proof.")
        and (
            not isinstance(row.get("schema_ref"), str)
            or schema_ref_resolves(row["schema_ref"])
        )
    ]
    for row in proof["contexts"]:
        if row.get("context") == "ak.event_proof.v1":
            row["binding_fields"] = [
                field
                for field in row.get("binding_fields", [])
                if not field.startswith("signer_resolution_evidence_ref")
            ]
            row["regime_rule"] = (
                "Exactly one producer proof applies. The current governance Station "
                "resolves the verification method and records acceptance in RealmCommit."
            )
        elif row.get("context") == "ak.realm_join_candidate_proof.v1":
            row["injected_fields"] = [
                {"field": field, "source": f"candidate proof projection {field}"}
                for field in (
                    "payload_digest",
                    "verification_method",
                    "created_at",
                    "domain",
                    "audience",
                )
            ]
        elif row.get("context") == "ak.realm_state_snapshot_proof.v1":
            row["injected_fields"] = [
                {"field": "realm_state_snapshot_id", "source": "snapshot.id"},
                {"field": "payload_digest", "source": "digest of unsigned snapshot"},
                {"field": "domain", "source": "registered proof domain"},
                {"field": "audience", "source": "snapshot receiver audience"},
            ]
    proof["domain_separations"] = [
        row
        for row in proof.get("domain_separations", [])
        if not isinstance(row.get("schema_ref"), str)
        or schema_ref_resolves(row["schema_ref"])
    ]
    domains_by_name = {
        row.get("domain"): row for row in proof["domain_separations"]
    }
    for row in moved_device_domains:
        domain = row["context"]
        binding_fields = list(row.get("binding_fields", []))
        if domain == "ak.device_authorize_accepted_device_possession_proof.v1":
            if "account_id" not in binding_fields:
                binding_fields.insert(0, "account_id")
        converted = {
            "domain": domain,
            "object_family": row["object_family"],
            "primitive": "detached_signature",
            "binding_fields": binding_fields,
            "defined_in": row["defined_in"],
            "schema_ref": row["schema_ref"],
            "transcript_schema_refs": [row["schema_ref"]],
        }
        if row.get("injected_fields"):
            converted["injected_fields"] = row["injected_fields"]
        domains_by_name[domain] = converted
    proof["domain_separations"] = sorted(
        domains_by_name.values(), key=lambda row: row.get("domain", "")
    )
    device_payload_path = SCHEMAS / "event-payload.schema.json"
    device_payload = load(device_payload_path)
    device_domain_defs = {
        "ak.device_authorize_applet_managed_possession_proof.v1": (
            "device_authorize_applet_managed_possession_transcript"
        ),
        "ak.device_authorize_possession_proof.v1": (
            "device_authorize_possession_transcript"
        ),
        "ak.device_authorize_recovery_possession_proof.v1": (
            "device_authorize_recovery_possession_transcript"
        ),
    }
    for domain, definition_name in device_domain_defs.items():
        device_payload["$defs"][definition_name] = {
            "allOf": [{"$ref": "#/$defs/device_authorize_payload"}],
            "x-arkret-signature-domain": domain,
        }
        schema_ref = f"schemas/event-payload.schema.json#/$defs/{definition_name}"
        for row in proof["domain_separations"]:
            if row.get("domain") == domain:
                row["schema_ref"] = schema_ref
                row["transcript_schema_refs"] = [schema_ref]
    save(device_payload_path, device_payload)

    pairing_path = SCHEMAS / "device-pairing.schema.json"
    pairing = load(pairing_path)
    pairing["$defs"]["device_pairing_target_proof"][
        "x-arkret-signature-domain"
    ] = "ak.device_authorize_accepted_device_possession_proof.v1"
    save(pairing_path, pairing)

    for row in proof["domain_separations"]:
        if row.get("domain") == "ak.mimi_reporter_authority_proof.v1":
            row["binding_fields"] = [
                field
                for field in row.get("binding_fields", [])
                if field != "cbs_proof_bundles?"
            ]
    save(proof_path, proof)

    pcr_path = ARTIFACT_REGISTRY / "pcr-exposure-registry.json"
    pcr = load(pcr_path)
    pcr["carrier_kinds"].pop("seal", None)
    pcr["carrier_kinds"]["realm_commit"] = (
        "The authority-signed RealmCommit that accepted the disclosed Event."
    )
    pcr["event_kinds"] = [
        row for row in pcr.get("event_kinds", []) if row.get("event_kind") in active
    ]
    for event_kind in pcr.get("event_kinds", []):
        for exposure in event_kind.get("exposures", []):
            pointers = exposure.get("json_pointers", [])
            if (
                "/$defs/principal_resolution_audit_evidence/properties/accepted_seal"
                in pointers
            ):
                exposure["carrier"] = "realm_commit"
                exposure["json_pointers"] = [
                    "/$defs/principal_resolution_audit_evidence/properties/accepted_commit"
                ]
    save(pcr_path, pcr)

    keypackage_path = SCHEMAS / "keypackage-operations.schema.json"
    keypackage = load(keypackage_path)
    keypackage["$defs"].get("keypackages_claim_outcome", {}).pop(
        "x-arkret-pcr-outward-event-kinds", None
    )
    save(keypackage_path, keypackage)

    effect_path = ARTIFACT_REGISTRY / "registered-effect-capability-registry.json"
    if effect_path.exists():
        effect_path.unlink()

    classification_path = ARTIFACT_REGISTRY / "classification-field-registry.json"
    classification = load(classification_path)
    classification["external_type_fields"] = [
        row
        for row in classification.get("external_type_fields", [])
        if "mls_proposal_payload" not in row.get("json_pointer", "")
    ]
    save(classification_path, classification)

    forbidden_path = ARTIFACT_REGISTRY / "forbidden-wire-fields.json"
    forbidden = load(forbidden_path)
    retired_contexts = {
        "mls_keypackage_payload",
        "seal",
        "snapshot.chunks[]",
        "agent_authority_state_evidence",
    }
    for context in retired_contexts:
        forbidden.get("context_definitions", {}).pop(context, None)
    forbidden["entries"] = [
        row
        for row in forbidden.get("entries", [])
        if row.get("context") not in retired_contexts
    ]
    save(forbidden_path, forbidden)

    # The v1 migration table is an inventory of every canonical operation, not
    # a compatibility alias table. Rebuild it after obsolete operations are
    # removed and the authority discovery/handoff operations are added.
    operation_ids = [
        row["operation_id"]
        for row in load(REGISTRY)["operation_registry"]["operations"]
    ]
    operation_migration_path = ROOT / "tools" / "operation-id-v1-migration.json"
    operation_migration = load(operation_migration_path)
    operation_migration["mappings"] = [
        {"old": operation_id.removesuffix(".v1"), "new": operation_id}
        for operation_id in sorted(operation_ids)
    ]
    save(operation_migration_path, operation_migration)

    error_mapping_path = ARTIFACT_REGISTRY / "operations-error-mapping.json"
    error_mapping = load(error_mapping_path)
    error_rows = {
        row["operation_id"]: row
        for row in error_mapping.get("operations", [])
        if row.get("operation_id") in operation_ids
    }
    authority_specific = {
        "ak.self.events.command.submit.v1": [
            "duplicate_conflict",
            "failed_precondition",
            "realm_frozen",
            "quarantine",
            "unknown_event_kind",
        ],
        "ak.peer.events.command.submit.v1": [
            "dependency_missing",
            "duplicate_conflict",
            "failed_precondition",
            "realm_frozen",
            "quarantine",
            "peer_stale",
            "unknown_event_kind",
        ],
        "ak.open.realm_authority.read.bundle.v1": [],
        "ak.peer.realm_authority.command.handoff.v1": ["failed_precondition"],
    }
    aliases = {
        row["operation_id"]: row["http"]
        for row in load(REGISTRY)["operation_registry"]["operations"]
    }
    for operation_id in operation_ids:
        if operation_id not in error_rows:
            error_rows[operation_id] = {
                "operation_id": operation_id,
                "http_alias": aliases[operation_id],
                "operation_specific": authority_specific.get(operation_id, []),
                "description": "No operation-specific error codes beyond the universal failure surface.",
            }
    for operation_id, codes in authority_specific.items():
        if operation_id in error_rows:
            error_rows[operation_id]["http_alias"] = aliases[operation_id]
            error_rows[operation_id]["operation_specific"] = codes
            error_rows[operation_id]["description"] = (
                "Authority-commit operation. Current authorization and stream-head "
                "checks are evaluated atomically by the current governance Station."
            )
    error_mapping["operations"] = [error_rows[key] for key in sorted(error_rows)]
    save(error_mapping_path, error_mapping)


def retire_obsolete_registry_artifacts() -> None:
    """Remove registries whose complete domain left the v1 protocol."""
    manifest_path = ARTIFACT_REGISTRY / "registry-manifest.json"
    manifest = load(manifest_path)
    manifest["registries"] = [
        row
        for row in manifest.get("registries", [])
        if Path(str(row.get("file", ""))).name not in RETIRED_REGISTRY_FILES
    ]
    save(manifest_path, manifest)

    evidence_path = ROOT / "tools/evidence-material-audit.json"
    evidence = load(evidence_path)
    for key, value in list(evidence.items()):
        if not isinstance(value, list):
            continue
        evidence[key] = [
            row
            for row in value
            if not (
                isinstance(row, dict)
                and Path(str(row.get("file", ""))).name in RETIRED_REGISTRY_FILES
            )
        ]
    save(evidence_path, evidence)

    for file_name in RETIRED_REGISTRY_FILES:
        path = ARTIFACT_REGISTRY / file_name
        if path.exists():
            path.unlink()


def retire_mls_governance_proof_discovery() -> None:
    path = SCHEMAS / "service-describe.schema.json"
    service_describe = load(path)
    limits = service_describe.get("properties", {}).get("limits", {})
    limits.get("properties", {}).pop("mls_governance_proof", None)
    service_describe["allOf"] = [
        branch
        for branch in service_describe.get("allOf", [])
        if "mls_governance_proof" not in json.dumps(branch, ensure_ascii=False)
    ]
    save(path, service_describe)


def migrate_retired_lint_registries() -> None:
    feature_path = ARTIFACT_REGISTRY / "feature-registry.json"
    feature = load(feature_path)
    feature["features"] = [
        row
        for row in feature.get("features", [])
        if row.get("feature_id") != "ak.feature.history_key_recovery.v1"
        and (
            not isinstance(row.get("defined_in"), str)
            or (ROOT / "spec/v1" / row["defined_in"]).exists()
        )
    ]
    save(feature_path, feature)

    error_path = ARTIFACT_REGISTRY / "error-code-registry.json"
    errors = load(error_path)
    retired_error_codes = {
        "actor_seq_invalid",
        "seal_signer_unauthorized",
        "seal_signer_slot_fenced",
        "seal_deferred_future_skew",
        "seal_ref_unknown",
        "frontier_sequence_exhausted",
        "mls_governance_proof_bounds_exceeded",
        "genesis_seal_invalid",
        "seal_incomplete",
        "peer_stale",
        "control_proposal_decision_overdue",
    }
    retired_reason_codes = {
        "causal_refs_too_large",
        "covered_set_mismatch",
        "created_at_before_basis_seal",
        "created_at_before_causal_predecessor",
        "delta_contains_ordinary_event",
        "genesis_seal_invalid",
        "prev_refs_too_large",
    }
    errors["codes"] = [
        row for row in errors.get("codes", []) if row.get("code") not in retired_error_codes
    ]
    errors["reason_codes"] = [
        row
        for row in errors.get("reason_codes", [])
        if (row.get("reason_code") or row.get("reason") or row.get("code"))
        not in retired_reason_codes
    ]
    for row in errors.get("codes", []):
        if row.get("code") == "cas_conflict":
            row["description"] = (
                "An optimistic concurrency precondition failed because the authority-committed "
                "typed current result or stream head no longer equals the submitted expectation. "
                "The caller must read current state and create a new signed Event; exact retry "
                "retains the original identity."
            )
        elif row.get("code") == "causal_conflict":
            row["description"] = (
                "An application-level referenced object, revision, or domain transition is "
                "incompatible with current authority-committed state. This code does not describe "
                "an Event predecessor graph."
            )
        description = row.get("description")
        if isinstance(description, str):
            row["description"] = description.replace(
                "security_frontier_digest", "key_access_revision"
            ).replace("accepted key-access state", "authority-committed key-access revision")
    save(error_path, errors)

    proof_path = ARTIFACT_REGISTRY / "proof-context-registry.json"
    proof_contexts = load(proof_path)
    proof_contexts["contexts"] = [
        row
        for row in proof_contexts.get("contexts", [])
        if row.get("object_family")
        not in {
            "events_frontier_leaf",
            "events_frontier_node",
            "realm_state_snapshot_auth_state_issuer_local",
        }
    ]
    save(proof_path, proof_contexts)

    digest_path = ARTIFACT_REGISTRY / "digest-suite-registry.json"
    digest_suites = load(digest_path)
    digest_suites["registry_rules"] = [
        "A digest suite is an explicit canonicalization/hash tuple; only active rows are valid on wire.",
        "Unknown suites in critical Event, RealmCommit, stream-head, receipt, or content-addressed digest fields fail closed.",
        "Producer Events use the suite selected by their Realm policy. RealmCommit binds each exact Event digest and its same-stream previous_commit_ref; historical references are never rehashed.",
        "Activating a new suite requires a schema/profile version and conformance vectors; it MUST NOT expand a frozen schema enum in place.",
    ]
    save(digest_path, digest_suites)

    service_kind_path = ARTIFACT_REGISTRY / "service-kind-registry.json"
    service_kinds = load(service_kind_path)
    for row in service_kinds.get("service_kinds", []):
        if isinstance(row.get("description"), str) and "Seal" in row["description"]:
            row["description"] = "Authority commit and current-state attestation surface."
    save(service_kind_path, service_kinds)

    clause_path = ARTIFACT_REGISTRY / "normative-clause-registry.json"
    clauses = load(clause_path)
    retired_clause_tokens = (
        "Seal",
        "Cell",
        "CBS",
        "actor_seq",
        "auth_context",
        "history-key",
        "mls_governance_proof",
    )
    for row in clauses.get("clauses", []):
        if any(
            token in json.dumps(row, ensure_ascii=False)
            for token in retired_clause_tokens
        ):
            row["status"] = "deprecated"
    save(clause_path, clauses)

    exemptions_path = (
        ARTIFACT_REGISTRY / "content-addressed-ref-digest-exemption-registry.json"
    )
    exemptions = load(exemptions_path)
    exemptions["exemptions"] = [
        row
        for row in exemptions.get("exemptions", [])
        if (ROOT / "spec/v1/artifacts" / row.get("subject", {}).get("schema_file", "")).exists()
        and "first_generation_seal_id" not in json.dumps(row, ensure_ascii=False)
        and "terminal_commit_digest" not in json.dumps(row, ensure_ascii=False)
    ]
    save(exemptions_path, exemptions)

    removals_path = ARTIFACT_REGISTRY / "derived-wire-field-removal-lock.json"
    removals = load(removals_path)
    retained_removals = []
    for row in removals.get("removals", []):
        if row.get("lock_id") == (
            "ak.lock.derived_wire_field_removal.mls_commit_payload_next_epoch.v1"
        ):
            continue
        schema = row.get("schema")
        path = row.get("path", "")
        source = row.get("source", {})
        if not isinstance(schema, str) or not schema_ref_resolves(f"{schema}#{path}"):
            continue
        source_schema = source.get("schema")
        source_path = source.get("path", "")
        if isinstance(source_schema, str) and not schema_ref_resolves(
            f"{source_schema}#{source_path}"
        ):
            continue
        retained_removals.append(row)
    removals["removals"] = retained_removals
    save(removals_path, removals)

    fixture_exemptions_path = ROOT / "tools/fixture-typed-id-exemption-registry.json"
    fixture_exemptions = load(fixture_exemptions_path)
    fixture_exemptions["entries"] = [
        row
        for row in fixture_exemptions.get("entries", [])
        if (
            ROOT
            / "spec/v1/artifacts/fixtures"
            / str(row.get("pointer", "")).split("#", 1)[0]
        ).exists()
    ]
    save(fixture_exemptions_path, fixture_exemptions)

    collection_path = ROOT / "tools/collection-naming-registry.json"
    collection = load(collection_path)
    for key in ("exact_exceptions", "pagination_objects"):
        collection[key] = [
            row
            for row in collection.get(key, [])
            if schema_ref_resolves(
                f"schemas/{row.get('file', '')}#{row.get('pointer', '')}"
            )
        ]
    save(collection_path, collection)

    schema_roots_path = ROOT / "tools/schema-root-registry.json"
    schema_roots = load(schema_roots_path)
    schema_roots["compatibility_review"]["schema_refs"] = [
        ref
        for ref in schema_roots["compatibility_review"].get("schema_refs", [])
        if schema_ref_resolves(ref)
        and ref
        != "schemas/service-operation-dtos.schema.json#/$defs/SignedSessionGrantClaims"
    ]
    save(schema_roots_path, schema_roots)

    clauses_path = ARTIFACT_REGISTRY / "operation-clause-registry.json"
    clauses = load_head(
        "spec/v1/artifacts/registry/operation-clause-registry.json"
    )
    for row in clauses.get("clauses", []):
        row["source_refs"] = [
            ref for ref in row.get("source_refs", []) if (ROOT / ref).exists()
        ]
        if row.get("clause_id") == "AK-OP-006":
            row["required_evidence"] = ["authority_commit_fixture"]
            authority_fixture = (
                "spec/v1/artifacts/fixtures/authority-commit-fixture.json"
            )
            if authority_fixture not in row["source_refs"]:
                row["source_refs"].append(authority_fixture)
    save(clauses_path, clauses)


def migrate_openapi() -> None:
    import yaml

    path = ROOT / "spec/v1/artifacts/openapi/arkret-service-api.openapi.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    document = rename_tree(
        document,
        {
            "consent_cell_list": "consent_list",
            "consent_cell_view": "consent_view",
        },
    )
    public_self = document.get(
        "x-arkret-high-security-session-authentication-policy", {}
    ).get("unauthenticatedPublicProjectionOperations", [])
    document["x-arkret-high-security-session-authentication-policy"][
        "unauthenticatedPublicProjectionOperations"
    ] = [
        operation_id
        for operation_id in public_self
        if operation_id != "ak.self.events.read.describe.v1"
    ]
    operations = load(REGISTRY)["operation_registry"]["operations"]
    by_base = {row["operation_id"].removesuffix(".v1"): row for row in operations}
    paths = document["paths"]

    # Preserve every still-registered binding verbatim.  The authority migration
    # removes retired operations and replaces only the six log/authority routes;
    # rebuilding unrelated operations from a generic template loses their path,
    # query, security and success-shape contracts.
    for route, item in list(paths.items()):
        for method, operation in list(item.items()):
            if method.startswith("x-") or not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                continue
            registered = by_base.get(operation_id)
            if registered is None or registered["http"] != f"{method.upper()} {route}":
                del item[method]
        if not any(not key.startswith("x-") for key in item):
            del paths[route]

    migrated_ids = {
        "ak.self.events.command.submit.v1",
        "ak.peer.events.command.submit.v1",
        "ak.self.events.read.scan.v1",
        "ak.peer.events.read.scan.v1",
        "ak.peer.events.read.resolve_committed.v1",
        "ak.open.realm_authority.read.bundle.v1",
        "ak.peer.realm_authority.command.handoff.v1",
    }
    for row in operations:
        operation_id = row["operation_id"]
        if operation_id not in migrated_ids:
            continue
        base = operation_id.removesuffix(".v1")
        method_name, route = row["http"].split(" ", 1)
        method = method_name.lower()
        current = {
            "operationId": base,
            "summary": row["notes"].split(".", 1)[0],
            "description": row["notes"],
            "parameters": [
                {
                    "name": "Arkret-Operation",
                    "in": "header",
                    "required": True,
                    "description": "Exact versioned Arkret operation selector.",
                    "schema": {"type": "string", "const": operation_id},
                }
            ],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "../" + row["request_schema_ref"]}
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Successful Arkret operation outcome.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "../" + row["response_schema_ref"]}
                        }
                    },
                }
            },
        }
        if operation_id.startswith("ak.self."):
            current["security"] = [{"sessionGrantAuth": [], "dpopProof": []}]
        elif operation_id.startswith("ak.peer."):
            current["security"] = [{"serviceHttpMessageSignatures": []}]
        else:
            current["security"] = []
        paths.setdefault(route, {})[method] = current

    # Drop components that were reachable only from removed routes while keeping
    # the exact transitive component closure of every surviving operation.
    component_schemas = document.get("components", {}).get("schemas", {})
    retained_components: set[str] = set()
    pending_components = [
        ref.removeprefix("#/components/schemas/").split("/", 1)[0]
        for ref in refs_in(paths)
        if ref.startswith("#/components/schemas/")
    ]
    while pending_components:
        name = pending_components.pop()
        if name in retained_components or name not in component_schemas:
            continue
        retained_components.add(name)
        pending_components.extend(
            ref.removeprefix("#/components/schemas/").split("/", 1)[0]
            for ref in refs_in(component_schemas[name])
                if ref.startswith("#/components/schemas/")
        )
    if "PsiPaddedProblem" in component_schemas:
        retained_components.add("PsiPaddedProblem")
    document["components"]["schemas"] = {
        name: value
        for name, value in component_schemas.items()
        if name in retained_components
    }
    document["components"]["schemas"]["PsiPaddedProblem"] = {
        "$ref": "../schemas/directory-operations.schema.json#/$defs/psi_padded_problem"
    }
    document["components"]["schemas"] = dict(
        sorted(document["components"]["schemas"].items(), key=lambda item: item[0].casefold())
    )
    path.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
        newline="\n",
    )


def migrate_non_http_bindings() -> None:
    import yaml

    path = ROOT / "spec/v1/artifacts/bindings/non-http-bindings.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    operations = load(REGISTRY)["operation_registry"]["operations"]
    known = {row["operation_id"] for row in operations}

    def clean(value: object) -> object:
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if isinstance(item, str) and item.startswith("ak.") and item.endswith(".v1"):
                    if item not in known:
                        continue
                cleaned = clean(item)
                if cleaned not in ({}, []):
                    result[key] = cleaned
            return result
        if isinstance(value, list):
            return [
                cleaned
                for item in value
                if (cleaned := clean(item)) not in ({}, [])
            ]
        return value

    document = clean(document)
    grpc_services = document.setdefault("grpc", {}).setdefault("services", {})
    grpc_services.setdefault("OpenRealmAuthority", {})["Bundle"] = (
        "ak.open.realm_authority.read.bundle.v1"
    )
    grpc_services.setdefault("PeerRealmAuthority", {})["Handoff"] = (
        "ak.peer.realm_authority.command.handoff.v1"
    )
    grpc_services.setdefault("PeerStreams", {})["ResolveCommitted"] = (
        "ak.peer.events.read.resolve_committed.v1"
    )
    path.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
        newline="\n",
    )


def migrate_service_http_prose() -> None:
    path = ROOT / "spec/v1/zh/sync/service-http-binding.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("consent_cell_list", "consent_list")
    text = text.replace("consent_cell_view", "consent_view")

    old_heading = "#### 2.3.1 Wire-level JSON 示例"
    new_heading = "#### 2.3.1 Authority-commit wire 边界"
    selected_heading = old_heading if old_heading in text else new_heading
    has_legacy_section = selected_heading in text and "### 2.4 字段级 Schema 索引" in text
    start = text.index(selected_heading) if has_legacy_section else 0
    end = text.index("### 2.4 字段级 Schema 索引") if has_legacy_section else 0
    replacement = """#### 2.3.1 Authority-commit wire 边界

Producer Event、Station RealmCommit、stream scan、authority bundle 与 handoff 的完整 wire 示例统一由
[`authority-commit-fixture.json`](../../artifacts/fixtures/authority-commit-fixture.json)承载。HTTP binding 不再
复制 Event 示例，避免把 producer Event 与 Station 接纳回执混成一个对象。

#### 2.3.2 治理提交与切换

| Operation | HTTP | Request | Response | Authorization / durability |
| --- | --- | --- | --- | --- |
| `ak.self.events.command.submit.v1` | `POST /_arkret/self/events` | `schemas/authority-commit-operations.schema.json#/$defs/submit_request` | `schemas/authority-commit-operations.schema.json#/$defs/submit_outcome` | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/submit_request；response_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/submit_outcome。认证 Account Station 只能转发原 Event；只有 verified current governance Station 可签发 Commit。 |
| `ak.peer.events.command.submit.v1` | `POST /_arkret/peer/events` | `schemas/authority-commit-operations.schema.json#/$defs/submit_request` | `schemas/authority-commit-operations.schema.json#/$defs/submit_outcome` | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/submit_request；response_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/submit_outcome。peer transport 身份必须与 forwarding Station 匹配；非 current authority 不得本地接纳。 |
| `ak.self.events.read.scan.v1` | `POST /_arkret/self/streams/scan` | `schemas/authority-commit-operations.schema.json#/$defs/stream_scan_request` | `schemas/authority-commit-operations.schema.json#/$defs/stream_scan_outcome` | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/stream_scan_request；response_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/stream_scan_outcome。一次只读一条获准 stream，并验证该 stream 的连续 predecessor。 |
| `ak.peer.events.read.scan.v1` | `POST /_arkret/peer/streams/scan` | `schemas/authority-commit-operations.schema.json#/$defs/stream_scan_request` | `schemas/authority-commit-operations.schema.json#/$defs/stream_scan_outcome` | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/stream_scan_request；response_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/stream_scan_outcome。federation peer 只能复制 visibility policy 允许的单一 stream。 |
| `ak.peer.events.read.resolve_committed.v1` | `POST /_arkret/peer/streams/resolve` | `schemas/authority-commit-operations.schema.json#/$defs/committed_event_resolve_request` | `schemas/authority-commit-operations.schema.json#/$defs/committed_event_resolve_outcome` | Directory 专用精确解析；必须重验 source-signed `DirectorySourceRefAccess` 的 caller/proof/expiry/current announce，并只接受 carrier `source_refs` 的逐字子集。不得退化为 scan。 |
| `ak.open.realm_authority.read.bundle.v1` | `POST /_arkret/open/realm-authority/bundle` | `schemas/authority-commit-operations.schema.json#/$defs/authority_bundle_request` | `schemas/realm-authority-bundle.schema.json` | 请求 fresh nonce；公开响应只披露 Realm stream head 与公开 transition，不披露隐藏 stream。 |
| `ak.peer.realm_authority.command.handoff.v1` | `POST /_arkret/peer/realm-authority/handoff` | `schemas/authority-commit-operations.schema.json#/$defs/handoff_request` | `schemas/realm-authority-handoff.schema.json` | old/new Station 双签；私下验证 snapshot 与完整 stream-head manifest 后才安装。 |

"""
    if has_legacy_section:
        text = text[:start] + replacement + text[end:]

    detail_header = "| `operation_id` | 必填字段 | 可选字段 | 响应字段 | 约束 |\n| --- | --- | --- | --- | --- |\n"
    detail_rows = """| `ak.self.events.command.submit.v1` | `event: Event` | `expected_stream_head?: RealmCommitId`; `mls_commit_submission?` | `status`; `event_id`; `realm_commit?` | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/submit_request；response_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/submit_outcome。 |
| `ak.peer.events.command.submit.v1` | `event: Event`; peer authentication | `expected_stream_head?: RealmCommitId`; `mls_commit_submission?` | `status`; `event_id`; `realm_commit?` | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/submit_request；response_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/submit_outcome。 |
| `ak.self.events.read.scan.v1` | `realm_id`; `stream_ref`; `after_position` | `limit?`; `cursor?` | `commits[]`; `next_cursor?`; `has_more` | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/stream_scan_request；response_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/stream_scan_outcome。 |
| `ak.peer.events.read.scan.v1` | `realm_id`; `stream_ref`; `after_position` | `limit?`; `cursor?` | `commits[]`; `next_cursor?`; `has_more` | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/stream_scan_request；response_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/stream_scan_outcome。 |
| `ak.peer.events.read.resolve_committed.v1` | `realm_id`; `source_ref_access`; `refs[]` | 无 | `items[]` | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/committed_event_resolve_request；response_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/committed_event_resolve_outcome。`refs[]` 必须是 carrier `source_refs` 的逐字子集。 |
| `ak.self.events.stream.subscribe.v1` | transport query selector | `after?`; `catchup?` | NDJSON frames | response_schema_ref=schemas/events-subscribe-frame.schema.json。订阅只作为获准 stream 的低延迟提示；缺口仍用逐 stream scan 修复。 |
| `ak.open.realm_authority.read.bundle.v1` | `realm_id`; `nonce` | 无 | `RealmAuthorityBundle` | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/authority_bundle_request；response_schema_ref=schemas/realm-authority-bundle.schema.json。 |
| `ak.peer.realm_authority.command.handoff.v1` | `handoff`; `snapshot`; `final_stream_heads[]` | 无 | `RealmAuthorityHandoff` | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/handoff_request；response_schema_ref=schemas/realm-authority-handoff.schema.json。 |
"""
    if detail_rows.splitlines()[0] not in text:
        text = text.replace(detail_header, detail_header + detail_rows, 1)

    if "## 3. Events API" not in text or "## 4. Identity API" not in text:
        path.write_text(text, encoding="utf-8", newline="\n")
        return

    events_start = text.index("## 3. Events API")
    identity_start = text.index("## 4. Identity API")
    events_section = """## 3. Events API

### 3.1 提交与接纳

`POST /_arkret/self/events` 与 `POST /_arkret/peer/events` 接收 exact producer-signed Event。接收 Station 若非
current governance Station，只能依据已验证的 nonce-bound authority bundle 转发。Current authority 在单一
数据库事务中验证 Event ID、producer proof、current authorization、typed payload、业务前置条件和目标
stream head，然后写入 Event、RealmCommit、typed current 与 outbox。

Realm Event 进入 Realm stream；Circle Event 进入该 Circle stream；Sidecar Event 进入该 Sidecar stream。
每条 stream 各自从 position 0 单调递增，并各自通过 `previous_commit_ref` 形成单链。不同 stream 的
position、head、提交时刻均不可比较，不存在 Realm 总 Commit 链。

客户端提交成功的唯一 durable 结果是完整 `RealmCommit`。`pending` 只表示转发尚未得到 authority 回执，
不得用于更新共享 current。相同 Event 的 exact retry 返回既有 Commit；相同幂等键但不同 Event 必须冲突且
零写入。

### 3.2 MLS 提交

共享 MLS Event 只保留 genesis 与 commit。Proposal 内联在 MLS Commit 中；Welcome 使用单独的
producer-signed `MlsWelcomeDelivery` 点对点投递，不进入共享 stream。提交 MLS Commit 时 body 同时携带
`MlsCommitSubmission`，current authority 原子验证上一 MLS commit Event、epoch、commit bytes、成员治理
结果及 key-access revision，然后才为 Event 签发 RealmCommit。

### 3.3 逐 stream 扫描

`POST /_arkret/self/streams/scan` 与 peer 对应接口一次只能选择一条完整 `stream_ref`。结果按该 stream 的
`stream_position` 升序返回 Commit 与 Event；第一页必须从请求的 `after_position + 1` 开始，后续每项的
`previous_commit_ref` 必须等于前项 Commit ID。服务不得跨 stream 合页、补造全局 cursor 或按 Event
`created_at` 重排。

读权限在每页和每次续订时重新校验。调用方只能证明其获准读取的 stream 连续，不能从 Realm stream 的
连续性推导未授权 Circle/Sidecar 的存在、缺失或活动。

### 3.4 Authority discovery 与切换

Directory、邀请人 Station 和缓存 locator 只是候选入口。调用方向候选发送 fresh nonce，并验证
`ak.open.realm_authority.read.bundle.v1` 返回的 genesis、连续双签 handoff chain、current assertion、nonce、
realm_id、generation 与 endpoint。只有该证明中的 current Station 可作为提交、snapshot 与 tail 来源。

Planned handoff 先私下传送 snapshot、完整 stream-head manifest 与所有缺口，后由 old/new Station 对同一
transition body 双签。公开 bundle 只披露 Realm stream head 与 private manifest digest。新 generation 在
每条既有 stream 的第一笔 Commit 分别承接该 stream 的旧 head；不存在跨 stream 的共同 successor。

### 3.5 错误原子性

`not_current_authority` 应携可验证 authority-bundle hint；`stream_head_conflict` 携当前获准 head；proof、权限、
MLS 或 reducer 失败返回封闭 reason code。任何失败都不得留下 Event-only、Commit-only、typed-current-only
或 outbox-only 状态。

"""
    text = text[:events_start] + events_section + text[identity_start:]

    authority_operation_tokens = (
        "ak.self.events.command.submit.v1",
        "ak.peer.events.command.submit.v1",
        "ak.self.events.read.scan.v1",
        "ak.peer.events.read.scan.v1",
        "ak.peer.events.read.resolve_committed.v1",
    )
    retired_event_anchor_tokens = (
        "#3311-actor_ids-selector-授权normative",
        "#316-peer-federation-submissionnormative",
        "#311-self-submit-admission-与持久化合同normative",
        "#312-direct-conversation-founding-unit-原子性normative",
        "#3122-membership-compensation-carriernormative",
        "#313-重复提交与-digest-preimage-冲突normative",
        "#314-ordinary-actor-chain-casnormative",
        "#315-self-submit-status-判别normative",
        "#317-realm-fanout-deliverynormative",
    )
    kept_lines = []
    for line in text.splitlines():
        stale_authority_row = (
            any(token in line for token in authority_operation_tokens)
            and line.startswith("|")
            and "authority-commit-operations.schema.json" not in line
        )
        if stale_authority_row or any(
            token in line for token in retired_event_anchor_tokens
        ):
            continue
        kept_lines.append(line)
    text = "\n".join(kept_lines) + "\n"

    path.write_text(text, encoding="utf-8", newline="\n")


def reconcile_authority_commit_residuals() -> None:
    """Remove machine/prose references whose owning v1 surface was retired."""

    device_path = SCHEMAS / "device-revocation-state.schema.json"
    device = load(device_path)
    receipt = device["$defs"]["device_revocation_gate_decision_receipt"]
    receipt["description"] = (
        "Origin-Station durable decision made under its local device lock. "
        "Shared revocation becomes effective only through its authority-committed "
        "Event; this internal receipt carries no Control Proposal or Seal witness."
    )
    receipt["properties"].pop("blocking_proposal_digest", None)
    receipt["properties"]["accepted_commit_id"] = {
        "$ref": "./common-ids.schema.json#/$defs/realm_commit_id",
        "description": "Present only when decision=revoked.",
    }
    receipt["allOf"] = [
        receipt["allOf"][0],
        {
            "if": {
                "properties": {"decision": {"const": "revoked"}},
                "required": ["decision"],
            },
            "then": {"required": ["accepted_commit_id"]},
            "else": {"not": {"required": ["accepted_commit_id"]}},
        },
    ]
    save(device_path, device)

    recovery_path = SCHEMAS / "recovery-authority.schema.json"
    recovery = load(recovery_path)
    completion = recovery["$defs"]["recovery_completion_attestation"]
    for retired_field in (
        "terminal_commit_digest",
        "device_authorization_event_id",
        "reanchor_commit_id",
    ):
        completion["required"] = [
            field for field in completion["required"] if field != retired_field
        ]
        completion["properties"].pop(retired_field, None)
    for field_name, description in (
        (
            "reanchor_event_ref",
            "CommittedEventRef of the recovery re-anchor Event in the account PCR stream.",
        ),
        (
            "device_authorization_event_ref",
            "CommittedEventRef of the replacement-device authorization Event in the same atomic RealmCommit.",
        ),
    ):
        if field_name not in completion["required"]:
            completion["required"].append(field_name)
        completion["properties"][field_name] = {
            "allOf": [
                {
                    "$ref": "./authority-commit-operations.schema.json#/$defs/committed_event_ref"
                }
            ],
            "description": description,
        }
    completion["description"] = (
        "Coordinator-signed proof created after one atomic recovery commit accepted the two "
        "producer-signed recovery Events, issued their PCR-stream RealmCommit, advanced the "
        "device generation, activated the replacement device, consumed the recovery session "
        "and completed the transaction. The two CommittedEventRef values MUST name positions "
        "in the same RealmCommit."
    )
    signature = completion["properties"]["auth_data"]["properties"]["signature"]
    signature["description"] = (
        "Base64URL signature over the closed completion projection, including "
        "reanchor_event_ref, device_authorization_event_ref and result_model_generation_ref."
    )
    save(recovery_path, recovery)

    recovery_receipt_path = SCHEMAS / "recovery-receipt.schema.json"
    recovery_receipt = load(recovery_receipt_path)
    recovery_receipt["required"] = [
        field
        for field in recovery_receipt.get("required", [])
        if field not in {"reanchor_batch_receipt_id", "reanchor_commit_id"}
    ]
    recovery_receipt.get("properties", {}).pop("reanchor_batch_receipt_id", None)
    recovery_receipt.get("properties", {}).pop("reanchor_commit_id", None)
    recovery_receipt["description"] = (
        "Replacement-device-signed terminal intent for one RecoveryTransaction. It binds the "
        "two exact producer Event ids, recovery session/policy/proof snapshot and resulting "
        "device generation expectation. It is signed before authority admission and therefore "
        "does not contain a RealmCommit id; successful completion is proven separately by the "
        "coordinator-signed recovery completion attestation and its CommittedEventRef values."
    )
    save(recovery_receipt_path, recovery_receipt)

    security_transaction_path = SCHEMAS / "security-transaction.schema.json"
    security_transaction = load(security_transaction_path)
    binding = security_transaction["$defs"].get("pcr_policy_recovery_binding", {})
    binding["required"] = [
        field
        for field in binding.get("required", [])
        if field not in {"reanchor_commit_id", "reanchor_batch_receipt_id"}
    ]
    binding.get("properties", {}).pop("reanchor_commit_id", None)
    binding.get("properties", {}).pop("reanchor_batch_receipt_id", None)
    binding["description"] = (
        "Reserved producer identities of one RecoveryTransaction. The replacement-device-signed "
        "Event ids and terminal receipt id are frozen before admission; the resulting RealmCommit "
        "is created only by the governance Station during the atomic terminal step."
    )
    recovery_intent = security_transaction["$defs"].get(
        "pcr_policy_recovery_intent", {}
    )
    recovery_intent["description"] = (
        "Caller-authored recovery intent fixing the verified recovery session, replacement "
        "device, generation CAS, terminal receipt id, two exact signed producer Events, current "
        "PCR stream head and their ordered digests. It contains no Station-signed RealmCommit."
    )
    commit_intent = security_transaction["$defs"].get("recovery_commit_intent", {})
    commit_intent["description"] = (
        "Closed authority-commit expectation for the PCR stream. predecessor_ref is the exact "
        "current stream head and unit_event_digests fixes the two producer Events that the "
        "governance Station must commit atomically after all recovery checks succeed."
    )
    commit_intent["properties"]["predecessor_ref"]["description"] = (
        "Exact current RealmCommit id of the Principal Control Realm stream; genesis-null is invalid."
    )
    commit_intent["properties"]["unit_event_digests"]["description"] = (
        "Exactly [reanchor_digest, authorize_digest] in RealmCommit event order."
    )
    terminal = security_transaction["$defs"].get("recovery_terminal_commit", {})
    terminal["description"] = (
        "Sole client-attested terminal artifact of a RecoveryTransaction. It carries the exact "
        "replacement-device-signed recovery receipt. The governance Station validates it and "
        "the prepared producer Events, then atomically issues the PCR-stream RealmCommit; the "
        "client artifact never contains or signs that authority record."
    )
    terminal["properties"]["recovery_receipt"]["description"] = (
        "Complete replacement-device-signed recovery receipt binding the transaction, plan, "
        "both producer Event ids, generation CAS and recovery proof snapshot."
    )
    plan = security_transaction["$defs"].get("pcr_policy_recovery_plan", {})
    plan["description"] = (
        "Station-derived closed plan frozen with the canonical request in a durable prepare "
        "transaction that produces no accepted Event, RealmCommit, generation advance, active "
        "device, consumed session or terminal result."
    )
    plan["properties"]["reanchor_commit_intent"]["description"] = (
        "Exact caller-stated PCR stream head and ordered Event digests; it MUST equal the create "
        "request recovery_intent.reanchor_commit_intent byte for byte."
    )
    security_description_replacements = {
        "first new-generation Seal": "first recovery RealmCommit",
        "first new-generation seal": "first recovery RealmCommit",
        "first_generation_seal_id": "reanchor_commit_id",
        "first_generation_seal_body": "prepared recovery commit input",
        "unsigned Seal": "prepared authority-commit input",
        "UnsignedSeal": "authority-commit input",
        "SealPrepareRequestBody": "authority commit submission",
        "ordinary Seal submit": "ordinary Event submit",
        "Seal signature": "RealmCommit authority signature",
        "complete RecoveryTerminalCommit": "complete recovery receipt artifact",
    }

    def rewrite_security_descriptions(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"description", "$comment"} and isinstance(item, str):
                    for old, new in security_description_replacements.items():
                        item = item.replace(old, new)
                    value[key] = item
                else:
                    rewrite_security_descriptions(item)
        elif isinstance(value, list):
            for item in value:
                rewrite_security_descriptions(item)

    rewrite_security_descriptions(security_transaction)
    save(security_transaction_path, security_transaction)

    dto_path = SCHEMAS / "service-operation-dtos.schema.json"
    dto = load(dto_path)
    query = dto["$defs"].get("EventsQueryPostRequestBody")
    if query:
        query["properties"]["actor_ids"]["items"] = {
            "$ref": "./common-ids.schema.json#/$defs/actor_id"
        }
    authz_check = dto["$defs"].get("AuthzCheckRequestBody")
    if authz_check and isinstance(authz_check.get("description"), str):
        authz_check["description"] = (
            "ak.self.authz.read.check.v1 advisory local authorization preflight. "
            "It is never a cross-service authorization fact and cannot replace the "
            "current governance Station's admission decision."
        )
    signal_outcome = dto["$defs"].get("SignalSubmitOutcome")
    if signal_outcome and isinstance(signal_outcome.get("description"), str):
        signal_outcome["description"] = (
            "Result of transient Signal admission. accepted=true means the service placed "
            "the encrypted envelope on the short-lived rail; it creates no Event, "
            "RealmCommit, authority-stream position or durable delivery receipt."
        )
    save(dto_path, dto)

    message_authoring_path = SCHEMAS / "message-authoring.schema.json"
    message_authoring = load(message_authoring_path)
    prepare_outcome = message_authoring["$defs"]["message_prepare_outcome"]
    prepare_outcome["required"] = [
        field
        for field in prepare_outcome.get("required", [])
        if field != "accepted_actor_frontier"
    ]
    prepare_outcome.get("properties", {}).pop("accepted_actor_frontier", None)
    save(message_authoring_path, message_authoring)

    audit_ryw_path = SCHEMAS / "audit-ryw-receipt.schema.json"
    audit_ryw = load(audit_ryw_path)
    audit_ryw["properties"]["frontier"] = {
        "allOf": [{"$ref": "./realm-commit.schema.json#/$defs/stream_head"}],
        "description": (
            "Exact authority stream head observed for this receipt. The commit chain, not an "
            "actor frontier or Event-DAG cut, defines the read-your-writes boundary."
        ),
    }
    save(audit_ryw_path, audit_ryw)

    view_path = SCHEMAS / "view.schema.json"
    view = load(view_path)
    state_frontier = view["$defs"]["state_frontier"]
    state_frontier["properties"].pop("event_ids", None)
    state_frontier["properties"].pop("actor_frontiers", None)
    state_frontier["properties"]["stream_heads"] = {
        "type": "array",
        "items": {"$ref": "./realm-commit.schema.json#/$defs/stream_head"},
        "uniqueItems": True,
        "description": "Authority stream heads from which state_digest was derived.",
    }
    save(view_path, view)

    payload_path = SCHEMAS / "event-payload.schema.json"
    payload = load(payload_path)
    description_replacements = {
        "Control Move envelope seal_basis": "current authority-committed state",
        "accepted Seal covering the Move": "RealmCommit accepting the Event",
        "accepted ordered release log at the close seal_basis": "authority-committed ordered release log at close",
        "security_frontier_digest": "key_access_revision",
        "accepted Seal state": "authority-committed state",
    }

    def rewrite_descriptions(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"description", "$comment"} and isinstance(item, str):
                    for old, new in description_replacements.items():
                        item = item.replace(old, new)
                    value[key] = item
                else:
                    rewrite_descriptions(item)
        elif isinstance(value, list):
            for item in value:
                rewrite_descriptions(item)

    rewrite_descriptions(payload)
    save(payload_path, payload)

    applet_edge_path = SCHEMAS / "applet-edge-operations.schema.json"
    applet_edge = load(applet_edge_path)
    transaction_outcome = applet_edge["$defs"]["applet_transaction_outcome"]
    transaction_outcome["properties"]["committed_event_refs"] = {
        "type": "array",
        "minItems": 1,
        "maxItems": 1024,
        "uniqueItems": True,
        "items": {
            "$ref": "./authority-commit-operations.schema.json#/$defs/committed_event_ref"
        },
        "description": (
            "Exact committed references for every durable Event accepted by this transaction. "
            "A successful or partial outcome cannot be represented by status alone."
        ),
    }
    transaction_outcome["allOf"] = [
        {
            "if": {
                "properties": {"status": {"enum": ["accepted", "partial"]}},
                "required": ["status"],
            },
            "then": {"required": ["committed_event_refs"]},
            "else": {"not": {"required": ["committed_event_refs"]}},
        }
    ]
    save(applet_edge_path, applet_edge)

    applet_install_path = SCHEMAS / "applet-install-operations.schema.json"
    applet_install = load(applet_install_path)
    applet_install["$defs"]["applet_revoke_effect_ref"] = {
        "description": (
            "CommittedEventRef for a durable revoke Event, or a local typed resource reference "
            "for service-local token, session, or fence effects. Bare EventId and RealmCommitId "
            "strings are not valid effect references."
        ),
        "oneOf": [
            {
                "$ref": "./authority-commit-operations.schema.json#/$defs/committed_event_ref"
            },
            {
                "type": "string",
                "pattern": "^ak:(?!event:|realm_commit:)[a-z][a-z0-9_]*:[A-Za-z0-9._~:/-]+$",
            },
        ],
    }
    revoke_step = applet_install["$defs"]["applet_revoke_step"]
    revoke_step["properties"]["effect_ref"] = {
        "$ref": "#/$defs/applet_revoke_effect_ref"
    }
    revoke_outcome = applet_install["$defs"]["applet_revoke_outcome"]
    revoke_outcome["properties"]["revoked_refs"]["items"] = {
        "$ref": "#/$defs/applet_revoke_effect_ref"
    }
    save(applet_install_path, applet_install)

    security_doc_path = ROOT / "spec/v1/zh/identity/security-transactions.md"
    security_doc = security_doc_path.read_text(encoding="utf-8")
    recovery_section = """## 2. RecoveryTransaction

RecoveryTransaction 保留为账号恢复的单一原子事务，但不再创建或携带 Seal。replacement device 只签两条 producer Event 与 `RecoveryReceipt`；当前治理 Station 独占 PCR stream 的 RealmCommit 签发权。

### 2.1 create 同时完成专用 prepare，但不产生恢复效果

create 请求固定 verified recovery session、replacement device、`previous_model_generation_ref` / `result_model_generation_ref`、预留 `terminal_receipt_id`、两条完整签名 Event，以及 `reanchor_commit_intent={realm_id,predecessor_ref,unit_event_digests}`。`predecessor_ref` MUST 等于当前 PCR stream head，digest 顺序 MUST 为 `[reanchor, authorize]`。

Station 在一个 durable prepare transaction 中重验 session、policy/proof snapshot、device PoP、generation CAS、当前治理 authority、stream head 与两条 Event；随后冻结 canonical request 和 prepared plan。prepare 不插入 Event、不生成 RealmCommit、不推进 generation、不激活设备、不消费 session。

### 2.2 唯一终态载体

唯一 client-attested step 仍为 `commit_recovery_unit`。其 artifact 是 closed `RecoveryTerminalCommit`，但该名称只表示“恢复事务的终态客户端载体”；wire 内容只有 replacement-device-signed `recovery_receipt`，不含 RealmCommit、authority signature 或预先计算的 commit id。

RecoveryReceipt 签入 transaction/request/plan、两条 producer EventId、previous/result generation、session/policy/proof snapshot、backup/welcome 结果与 authoring time。它在 authority admission 前生成，因此 MUST NOT 携 `reanchor_commit_id` 或 `CommittedEventRef`。outer client attestation 绑定该 exact receipt artifact。

### 2.3 唯一原子提交与可观察性

接受 terminal step 时，治理 Station 在同一数据库事务与同一 stream-head/generation CAS 下：

1. 重验 transaction、session、plan、receipt、outer attestation 与两条 Event；
2. 以 `[reanchor, authorize]` 顺序为 PCR stream 生成并签署一个 RealmCommit；
3. 原子保存 Event、RealmCommit、stream head、generation advance、replacement device active state、session consumption 与 terminal result；
4. 生成 `RecoveryCompletionAttestation`。

任一步失败都不得留下可见 Event、RealmCommit 或部分 generation state。成功后两条 Event 的 `CommittedEventRef` 必须具有相同 `stream_ref` 与 `commit_id`，position 按上述顺序递增。

### 2.4 operation 与 grant 边界

`RecoveryCompletionAttestation` 是 Account Authority 签发恢复后 Standard grant 的唯一离线完成证据。其签名投影包含 transaction/request/plan、account/session/receipt、`reanchor_event_ref`、`device_authorization_event_ref`、`result_model_generation_ref` 与 `completed_at`。不再存在 `first_generation_seal_id` 或 `terminal_commit_digest`；RealmCommitId 已绑定 authority-signed commit bytes，不能再叠加一个旧 terminal artifact digest 作为治理根。

### 2.5 幂等、竞争与失败终局

同一 canonical terminal request 重放返回已保存的 receipt、两条 CommittedEventRef 与 completion attestation。相同 transaction id 的不同 bytes 返回 conflict。stream head、generation、session 或 policy 已改变时 fail closed，并且客户端必须创建新的 recovery session/transaction；服务不得改写旧 Event、把它们移到另一 RealmCommit、或由 inviter/旧治理 Station 代签。

"""
    security_doc = re.sub(
        r"## 2\. RecoveryTransaction\n.*?(?=## 3\. SecurityRotationTransaction)",
        recovery_section,
        security_doc,
        flags=re.S,
    )
    security_doc = security_doc.replace(
        "RecoveryTerminalCommit 内的 Seal 与 receipt 都由 replacement device",
        "RecoveryTerminalCommit 内的 recovery receipt 由 replacement device",
    ).replace(
        "recovery 还必须分别验证 Seal 的 notary signature transcript 与 receipt 自己的",
        "recovery 还必须验证 receipt 自己的",
    )
    security_doc_path.write_text(security_doc, encoding="utf-8", newline="\n")

    freshness_path = ARTIFACT_REGISTRY / "did-freshness-profile-registry.json"
    freshness = load(freshness_path)
    freshness["call_sites"] = [
        row
        for row in freshness.get("call_sites", [])
        if row.get("site_id")
        != "ak.gate.account.command.issue_controller_gate_attestation.v1"
    ]
    save(freshness_path, freshness)

    did_allowlist_path = ROOT / "tools/did-boundary-allowlist.json"
    did_allowlist = load_old_decenter("tools/did-boundary-allowlist.json")
    retired_did_pointers = {
        "authenticated-signer-resolution-evidence.schema.json#/$defs/service_signer_evidence/allOf/0/properties/authenticated_resolution/properties/normalized_did_document/properties/did/oneOf/0/$ref",
        "authenticated-signer-resolution-evidence.schema.json#/$defs/service_signer_evidence/allOf/0/properties/authenticated_resolution/properties/normalized_did_document/properties/did/oneOf/1/$ref",
        "offline-publication.schema.json#/$defs/ingress_receipt/properties/qualified_ingress_did/$ref",
    }
    did_allowlist["entries"] = [
        row
        for row in did_allowlist.get("entries", [])
        if not isinstance(row, dict) or row.get("pointer") not in retired_did_pointers
    ]
    save(did_allowlist_path, did_allowlist)

    history_release_path = ARTIFACT_REGISTRY / "history-release-attestation-registry.json"
    if history_release_path.exists():
        history_release = load(history_release_path)
        history_release = {
            "version": "2026-09-16.1",
            "source_of_truth": True,
            "status": "retired",
            "description": "Retired: v1 authority-commit core does not distribute history keys.",
        }
        save(history_release_path, history_release)

    hpke_path = ARTIFACT_REGISTRY / "hpke-suite-registry.json"
    hpke = load(hpke_path)
    hpke["surface_profiles"] = [
        row
        for row in hpke.get("surface_profiles", [])
        if not str(row.get("plaintext_schema_ref", "")).startswith(
            "schemas/history-key.schema.json"
        )
    ]
    for row in hpke.get("suites", []):
        row["source_refs"] = [
            ref for ref in row.get("source_refs", []) if "history-key.schema.json" not in ref
        ]
    save(hpke_path, hpke)

    profiles_path = ROOT / "spec/v1/artifacts/profiles/conformance-profiles.json"
    profiles = load(profiles_path)
    for profile in profiles.get("profile_requirements", {}).values():
        if not isinstance(profile, dict):
            continue
        for block_name in ("conditional_requirements", "additional_requirements"):
            block = profile.get(block_name)
            if isinstance(block, dict):
                profile[block_name] = {
                    key: value
                    for key, value in block.items()
                    if "history_key_recovery" not in key
                    and "history_key_recovery" not in str(value)
                }
    save(profiles_path, profiles)

    discovery_path = ROOT / "spec/v1/artifacts/fixtures/discovery-profile-fixture.json"
    discovery = load(discovery_path)
    for case in discovery.get("cases", []):
        if not isinstance(case, dict):
            continue
        input_value = case.get("input")
        if isinstance(input_value, dict) and input_value.get("optional_feature") == (
            "ak.feature.example.unknown.v1"
        ):
            input_value["optional_feature"] = "example.future_optional"
    save(discovery_path, discovery)

    key_backup_path = ROOT / "spec/v1/artifacts/fixtures/key-backup-fixture.json"
    key_backup = load(key_backup_path)
    removed_key_backup_cases = {
        "key_backup_mls_history_envelope_actor_id_valid",
        "key_backup_envelope_bare_actor_id_rejected",
        "key_backup_envelope_supersedes_alias_rejected",
    }
    key_backup["schema_validation_cases"] = [
        row
        for row in key_backup.get("schema_validation_cases", [])
        if row.get("name") not in removed_key_backup_cases
    ]
    for row in key_backup["schema_validation_cases"]:
        if row.get("name") in {
            "key_backup_frontier_integer_generation_valid",
            "key_backup_frontier_compound_string_generation_rejected",
        }:
            instance = row.get("instance", {})
            instance.pop("frontier_digest", None)
            instance["realm_commit_id"] = (
                "ak:realm_commit:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            )
            if row.get("expect_valid") is False:
                row["first_expected_error"] = (
                    "$.device_generation_ref: '7-did-version' is not of type 'integer'"
                )
    save(key_backup_path, key_backup)

    key_backup_schema_path = SCHEMAS / "key-backup.schema.json"
    key_backup_schema = load(key_backup_schema_path)
    key_backup_schema["properties"]["backup_kind"]["enum"] = ["secret_storage"]
    key_backup_schema["allOf"] = [
        row
        for row in key_backup_schema.get("allOf", [])
        if "mls_history" not in json.dumps(row, ensure_ascii=False)
        and "history_secret_ranges" not in json.dumps(row, ensure_ascii=False)
    ]
    save(key_backup_schema_path, key_backup_schema)

    producer_fixture_path = (
        ROOT / "spec/v1/artifacts/fixtures/producer-allocated-identity-fixture.json"
    )
    producer_fixture = load(producer_fixture_path)
    producer_fixture["driver"]["selected_id_kinds"] = sorted(
        row["kind"]
        for row in load(REGISTRY)["id_kind_registry"]["id_kinds"]
        if row.get("id_form") == "producer_allocated"
        and row.get("identity_authority") == "producer_signature"
    )
    save(producer_fixture_path, producer_fixture)

    collection_path = ROOT / "tools/collection-naming-registry.json"
    collection = load(collection_path)
    collection["pagination_objects"] = [
        row
        for row in collection.get("pagination_objects", [])
        if not (
            row.get("file") == "realm-join-intake.schema.json"
            and row.get("pointer") == "/$defs/peer_bootstrap_outcome"
        )
    ]
    for row in collection.get("pagination_objects", []):
        if row.get("file") == "account-subscribe-frame.schema.json" and row.get(
            "pointer"
        ) == "/$defs/timeline":
            row["collection_field"] = "commits"
            row["reason"] = "timeline.limited reports truncation of authority commits"
    save(collection_path, collection)

    common_fields_path = ROOT / "spec/v1/zh/models/common-fields.md"
    common_fields = common_fields_path.read_text(encoding="utf-8")
    common_fields = "\n".join(
        line
        for line in common_fields.splitlines()
        if "已退役的 MLS 本地诊断" not in line
    ) + "\n"
    common_fields_path.write_text(common_fields, encoding="utf-8", newline="\n")

    evidence_path = ROOT / "tools/evidence-material-audit.json"
    evidence = load(evidence_path)

    def count_key(value: object, target: str) -> int:
        if isinstance(value, dict):
            return sum((1 if key == target else 0) + count_key(item, target) for key, item in value.items())
        if isinstance(value, list):
            return sum(count_key(item, target) for item in value)
        return 0

    retained_evidence = []
    for row in evidence.get("registrations", []):
        file_name = row.get("file")
        key = row.get("key")
        if not isinstance(file_name, str) or not isinstance(key, str):
            continue
        candidates = [SCHEMAS / file_name, ARTIFACT_REGISTRY / file_name]
        target = next((candidate for candidate in candidates if candidate.exists()), None)
        if target is None:
            continue
        occurrences = count_key(load(target), key)
        if occurrences == 0:
            continue
        row["occurrences"] = occurrences
        retained_evidence.append(row)
    evidence["registrations"] = retained_evidence
    evidence["audited_occurrence_count"] = sum(
        row["occurrences"] for row in retained_evidence
    )
    save(evidence_path, evidence)

    classification_path = ROOT / "tools/identifier-classification-registry.json"
    classification = load(classification_path)
    stale_classifications = {
        ("admission_id", '[["pattern", "^(?!ak:)"], ["type", "\\"string\\""]]'),
        ("agent_transition_event_ids", "[]"),
        ("authorization_rule_id", '[["pattern", "^[a-z][a-z0-9_]{0,63}$"]]'),
        ("backup_origin_id", '[["pattern", "^backup:(?:ak:backup:[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}|sha256:[0-9a-f]{64})$"]]'),
        ("cell_id", '[["const", "ak:cell:ak.component.identity.resolution.v1:null"]]'),
        ("id", '[["pattern", "^(cx|[a-z0-9][a-z0-9-]*(\\\\.[a-z0-9][a-z0-9-]*)+)\\\\.[a-z0-9_]+(\\\\.[a-z0-9_]+)*\\\\.v[0-9]+$"]]'),
        ("id", '[["type", "\\"string\\""]]'),
        ("log_id", '[["pattern", "^(?!ak:)"]]'),
        ("membership_cell_id", '[["pattern", "^(?!ak:)"], ["type", "\\"string\\""]]'),
        ("missing_event_ids", "[]"),
        ("frontier_event_ids", "[]"),
        ("target_id", '[["pattern", "^[A-Za-z0-9][A-Za-z0-9_-]{15,127}$"]]'),
        ("transition_key_id", '[["pattern", "^(?!ak:)"]]'),
    }
    classification["classifications"] = [
        row
        for row in classification.get("classifications", [])
        if (row.get("name"), row.get("terminal_signature")) not in stale_classifications
    ]
    count_updates = {
        ("agent_key_authorize_event_id", 2): 1,
        ("claim_id", 8): 4,
        ("device_authorize_event_id", 2): 1,
        ("mls_group_id", 5): 4,
        ("mls_group_id", 11): 10,
        ("mls_group_id", 17): 4,
    }
    for row in classification["classifications"]:
        key = (row.get("name"), row.get("occurrences"))
        if key in count_updates:
            row["occurrences"] = count_updates[key]
        if row.get("name") == "secret_id" and row.get("terminal_signature") == (
            '[["pattern", "^[A-Za-z0-9_.-]+$"]]'
        ):
            row["occurrences"] = 1
        if row.get("name") == "secret_id" and row.get("terminal_signature") == (
            '[["pattern", "^[a-z0-9_]+$"]]'
        ):
            row["occurrences"] = 2
        if row.get("name") == "contact_round_id" and row.get("terminal_signature") == (
            '[["pattern", "^(sha256|blake3):[0-9a-f]{64}$"]]'
        ):
            row["occurrences"] = 2
        if row.get("name") == "context_id":
            row["occurrences"] = 1
    classification["type_derived_summary"] = {
        "typed_object_id": 866,
        "responsibility_identity_material": 547,
        "registry_catalog_symbol": 14,
    }
    save(classification_path, classification)

    role_path = ROOT / "tools/identifier-role-suffix-registry.json"
    roles = load(role_path)
    roles["multi_representation_field_contracts"] = [
        row
        for row in roles.get("multi_representation_field_contracts", [])
        if row.get("field") not in {"signer_id", "value"}
    ]
    roles["responsibility_field_contracts"] = [
        row
        for row in roles.get("responsibility_field_contracts", [])
        if row.get("field") not in {"holder_service_id", "method_controller_principal_id"}
    ]
    roles["registered_network_locator_fields"] = [
        row
        for row in roles.get("registered_network_locator_fields", [])
        if row.get("field") != "inclusion_proof_url"
    ]
    roles["exact_exceptions"] = [
        row
        for row in roles.get("exact_exceptions", [])
        if isinstance(row.get("file"), str)
        and isinstance(row.get("pointer"), str)
        and schema_ref_resolves(f"schemas/{row['file']}#{row['pointer']}")
    ]
    save(role_path, roles)

    prose_fields_path = ROOT / "tools/prose-field-table-registry.json"
    prose_fields = load(prose_fields_path)
    retained_bindings = []
    for row in prose_fields.get("bindings", []):
        schema_ref = row.get("schema_ref")
        if schema_ref == "cursor.schema.json#":
            continue
        if not isinstance(schema_ref, str) or not schema_ref_resolves(
            "schemas/" + schema_ref
        ):
            continue
        if schema_ref == "event-envelope.schema.json#":
            row["external_field_mentions"] = [
                value
                for value in row.get("external_field_mentions", [])
                if value not in {"authorized_by", "inclusion_proof"}
            ]
        retained_bindings.append(row)
    prose_fields["bindings"] = retained_bindings
    save(prose_fields_path, prose_fields)

    naming_matrix_path = ROOT / "tools/naming-rule-coverage-matrix.json"
    naming_matrix = load(naming_matrix_path)
    for row in naming_matrix.get("rules", []):
        if row.get("rule_id") != "NC-LIFECYCLE-001":
            continue
        row["entry_points"] = [
            entry
            for entry in row.get("entry_points", [])
            if entry != "state_contract_closure"
        ]
        enforced_by = row.get("enforced_by", {})
        enforced_by["functions"] = [
            function
            for function in enforced_by.get("functions", [])
            if function != "foundation.py:check_state_contract_closure"
        ]
        row["residual_gap"] = (
            "Lifecycle naming remains a semantic review rule; the old Cell state "
            "contract closure was retired by the authority-commit clean break."
        )
    save(naming_matrix_path, naming_matrix)

    device_lifecycle_path = ROOT / "spec/v1/zh/crypto-media/device-lifecycle.md"
    device_lifecycle = device_lifecycle_path.read_text(encoding="utf-8")
    device_lifecycle = re.sub(
        r"## 12\. Key Backup\n.*?(?=## 14\. PCR-Policy Device Recovery)",
        """## 12. Key Backup

`backup_kind=secret_storage` 表示端到端加密备份。治理 Station 只保存密文、版本链和当前 Realm stream 的 `realm_commit_id` 锚点，不能解密、补发或据此取得 MLS 成员资格。重新加入 MLS group 必须由当前治理 Station 接受成员 Event 与 `mls_commit_submission`，再通过单独的 `MlsWelcomeDelivery` 私密投递 Welcome。

### 12.1 Backup API

备份上传、读取和删除仍使用 `ak.schema.key_backup.v1`。每个 successor 必须链接同一 series 的直接 predecessor；客户端验证密文摘要、设备签名以及可选 `frontier_ref.realm_commit_id`，但该锚点只证明备份产生时观察到的 Realm stream 位置，不证明任何 Circle 或 Sidecar stream 的位置。

### 12.2 Retention and Erasure

服务端按账户保留策略删除密文；删除备份不删除 RealmCommit 或 Event。客户端不得把服务端持有密文解释为服务端持有解密能力。

""",
        device_lifecycle,
        flags=re.DOTALL,
    )
    device_lifecycle_path.write_text(
        device_lifecycle, encoding="utf-8", newline="\n"
    )

    for fixture_name in ("scalability-limits-fixture.json",):
        fixture_path = ROOT / "spec/v1/artifacts/fixtures" / fixture_name
        fixture = load(fixture_path)
        known_operations = {
            row["operation_id"]
            for row in load(REGISTRY)["operation_registry"]["operations"]
        }
        fixture["cases"] = [
            row
            for row in fixture.get("cases", [])
            if not isinstance(row, dict)
            or not isinstance(row.get("input"), dict)
            or not isinstance(row["input"].get("generator"), dict)
            or row["input"]["generator"].get("operation_id") in known_operations
        ]
        save(fixture_path, fixture)

    event_doc = ROOT / "spec/v1/zh/models/event-and-patch.md"
    text = event_doc.read_text(encoding="utf-8")
    if "#### 4.2.4" not in text:
        text += """

#### 4.2.4 Redactable content slots (normative)

- Message: `content`、`encrypted_content`
- Strand: `content`、`encrypted_content`、`tracks.synthesis.content`、`tracks.synthesis.encrypted_content`
- Morph: `content`、`encrypted_content`

普通更新只能用 `set` 写入空内容；清除这些 slot 必须走登记的 terminal redaction Event。

#### 4.2.5 Typed-reducer managed paths (normative)

Generic patch path MUST NOT 操作 reducer-managed 字段：`id`、`schema`、`realm_id`、`created_by`、`created_at`、`updated_by`、`updated_at`、`state`、`state_changed_at`（完整的按对象封闭集由 `registry/reducer-managed-path-registry.json` 给出）。这些是 typed reducer 的固定输出，不是 Cell 投影。
"""
        event_doc.write_text(text, encoding="utf-8", newline="\n")

    for prose_path in (ROOT / "spec/v1/zh").rglob("*.md"):
        prose = prose_path.read_text(encoding="utf-8")
        prose = prose.replace(
            "ak.feature.example.unknown.v1", "ak.feature.detached_jws.v1"
        )
        prose = prose.replace(
            "ak.feature.history_key_recovery.v1", "retired.history_key_recovery"
        )
        prose = prose.replace("`ak.mls.commit_failed`", "`ak.mls.commit` 的本地失败诊断")
        prose = prose.replace("ak:seal:", "ak:realm_commit:")
        prose = prose.replace("ak:cell:", "state-slot:")
        prose = prose.replace("ak:history_request:", "history-request:")
        prose = prose.replace("ak:history_response:", "history-response:")
        prose = prose.replace(
            "ak.schema.realm_state_snapshot_chunk.v1", "ak.schema.realm_state_snapshot.v1"
        )
        prose = prose.replace(
            "ak.schema.agent_signer_evidence.v1", "ak.schema.detached_object_signature.v1"
        )
        prose = prose.replace(
            "ak.schema.collision_variant_record.v1", "ak.schema.realm_commit.v1"
        )
        for retired_target in (
            "../../artifacts/fixtures/capability-fixture.json",
            "../../artifacts/schemas/seal-conclusion.schema.json",
            "../../artifacts/schemas/control-proposal-decision.schema.json",
            "../../artifacts/schemas/history-key.schema.json",
            "../../artifacts/fixtures/direct-conversation-fixture.json",
            "../../artifacts/fixtures/reaction-fixture.json",
            "../../artifacts/schemas/seal.schema.json",
            "../../artifacts/schemas/availability-receipt.schema.json",
            "../../artifacts/schemas/bottom.schema.json",
        ):
            prose = prose.replace(retired_target, "../sync/authority-commit-log.md")
        prose_path.write_text(prose, encoding="utf-8", newline="\n")


def clean_break_active_surfaces() -> None:
    """Erase every unpublished decentralized-model spelling from active v1."""

    legacy_pattern = re.compile(
        r"(?i)(?:\bseal\b|\bcell\b|\bcbs\b|actor_seq|prev_refs|causal_refs|"
        r"history[_-]key|ak\.mls\.(?:proposal|welcome|keypackage)|"
        r"mls_governance_proof|sealbasis|"
        r"(?:^|[_-])seal(?:[_-]|$)|(?:^|[_-])cell(?:[_-]|$)|(?:^|[_-])cbs(?:[_-]|$))"
    )

    replacements = (
        ("ak.mls.welcome.own_device", "ak.delivery.mls_welcome.own_device"),
        ("ak.mls.welcome", "ak.delivery.mls_welcome"),
        ("ak.mls.keypackage", "ak.resource.mls_keypackage"),
        ("ak.mls.proposal", "rfc9420.proposal"),
        ("first_generation_seal", "reanchor_commit"),
        ("accepted_seal", "accepted_commit"),
        ("covering_seal", "covering_commit"),
        ("within_seal_order", "within_commit_order"),
        ("requires_new_seal", "requires_new_commit"),
        ("seal_age_expires_authority", "commit_age_expires_authority"),
        ("seal_compaction", "commit_compaction"),
        ("seal_include", "commit_include"),
        ("seal_basis", "authority_revision"),
        ("seal_ref", "commit_ref"),
        ("seal_id", "commit_id"),
        ("seal_digest", "commit_digest"),
        ("seal_inclusion", "commit_inclusion"),
        ("seal_conclusion", "commit_conclusion"),
        ("SealBasis", "AuthorityRevision"),
        ("SealRef", "RealmCommitRef"),
        ("CellRef", "TypedResultSelector"),
        ("cells", "results"),
        ("cell_families", "result_families"),
        ("cell_family", "result_family"),
        ("cell_subject", "result_selector"),
        ("cell_contract", "result_contract"),
        ("cell_projection", "typed_current_result"),
        ("cell_value", "result_value"),
        ("cell_ref", "result_selector"),
        ("cell_id", "result_id"),
        ("sealed_at", "committed_at"),
        ("first_sealed_at", "first_committed_at"),
        ("control_sealed", "control_committed"),
        ("rejected_seal", "rejected_commit"),
        ("security_frontier_digest", "key_access_revision"),
        ("mls_frontier_leaves", "key_access_revision"),
        ("MLS Security Frontier Binding", "MLS key-access revision binding"),
        ("MLS Security Frontier", "MLS key-access revision"),
        ("MLS security frontier", "MLS key-access revision"),
        ("security frontier", "key-access revision"),
        ("ak:cell:", "ak:result:"),
        ("actor_seq", "producer_revision"),
        ("prev_refs", "domain_refs"),
        ("causal_refs", "domain_refs"),
        ("history_key", "historical_secret"),
        ("history-key", "historical-secret"),
        ("HistoryKey", "HistoricalSecret"),
        ("/consent/cells", "/consent/results"),
        ("/consent/typed current result", "/consent/result"),
        ("ConsentCell", "ConsentResult"),
        ("consent_cell", "consent_result"),
        ("mls_exporter_aead_commit_open_transcript", "mls_exporter_aead_encrypt_decrypt_transcript"),
        ("authz/cbs-profiles.md", "sync/authority-commit-log.md"),
        ("authz/authority_commit-profiles.md", "sync/authority-commit-log.md"),
        ("shared_history_event", "authority_committed_event"),
        ("history_admission_contract", "authority_commit_admission_contract"),
        ("Typed replacement for the retired generic domain_refs carrier. ", ""),
        ("retired_proof_fields", "unexpected_fields"),
        ("retired_mirror_violation", "unknown_field_violation"),
        ("retired_mirror_or_plaintext_fields_rejected", "unknown_or_plaintext_fields_rejected"),
        ("retired_digest_mirror", "unknown_digest_mirror"),
        ("retired_sender_mirror", "unknown_sender_mirror"),
        ("retired_random_identity", "unknown_random_identity"),
        ("retired_payload_discriminator", "unknown_payload_discriminator"),
        ("mls_epoch_and_history_secrets_are_rejected", "mls_epoch_private_material_is_rejected"),
        ("rejected_retired_expected", "noncanonical_expected"),
        ("rejected_retired_preimage_utf8", "noncanonical_preimage_utf8"),
        ("removed_signature_carriers", "forbidden_signature_carriers"),
        ("digesting the whole did:key: URI is the retired convention; the receipt binds the bare multikey", "digesting the whole did:key URI is noncanonical; the receipt binds the bare multikey"),
        ("including the closed four-method union and rejection of the removed threshold_recovery method", "for the closed four-method union"),
        ("deprecated_fields", "forbidden_fields"),
        ("realm_discovery_rejects_retired_second_preview_policy", "realm_discovery_rejects_duplicate_preview_policy"),
        ("Written once and never retired", "Immutable after the first accepted write"),
        ("Written once and never retired;", "Immutable after the first accepted write;"),
        ("The removed log_head_digest is derived from the canonical pinned version/entry commitment under the registered method adapter. Retain control_key_digest for bounded evidence consumers. Existing signed method transcript positions are reconstructed from the pinned entry; no caller-supplied digest mirror is accepted.", "The method adapter derives the canonical pinned version/entry commitment. control_key_digest serves bounded evidence consumers, and signed method transcript positions are reconstructed from the pinned entry; caller-supplied digest mirrors are rejected."),
        ("or E2EE history key share ", ""),
        ("Realm/Circle history keys, MLS epoch/exporter secrets", "MLS epoch/exporter private material"),
        ("CBS", "authority-commit"),
        ("cbs", "authority_commit"),
    )

    def rewrite_string(value: str) -> str:
        result = value
        for old, new in replacements:
            result = result.replace(old, new)
        result = re.sub(r"\bunsealed\b", "uncommitted", result, flags=re.I)
        result = re.sub(r"\bsealed\b", "committed", result, flags=re.I)
        result = re.sub(r"\bSeal\b", "RealmCommit", result)
        result = re.sub(r"\bseal\b", "authority commit", result)
        result = re.sub(r"\bCell\b", "typed current result", result)
        result = re.sub(r"\bcell\b", "typed current result", result)
        result = re.sub(r"\bcells\b", "typed results", result, flags=re.I)
        result = re.sub(r"history[_-]key", "historical_secret", result, flags=re.I)
        result = re.sub(r"(?<=_)seal(?=_)|(?<=_)seal\b|\bseal(?=_)", "commit", result, flags=re.I)
        result = re.sub(r"(?<=_)cell(?=_)|(?<=_)cell\b|\bcell(?=_)", "result", result, flags=re.I)
        result = re.sub(r"(?<=_)cbs(?=_)|(?<=_)cbs\b|\bcbs(?=_)", "authority_commit", result, flags=re.I)
        result = result.replace("/consent/typed current result", "/consent/result")
        result = result.replace("typed_current_result", "result_projection")
        return result

    def rewrite_tree(value: object) -> object:
        if isinstance(value, dict):
            rewritten: dict[str, object] = {}
            for key, item in value.items():
                if key == "deprecated":
                    continue
                if isinstance(item, dict) and isinstance(item.get("status"), str) and item.get("status") in {
                    "retired",
                    "deprecated",
                }:
                    continue
                rewritten[rewrite_string(key)] = rewrite_tree(item)
            return rewritten
        if isinstance(value, list):
            return [
                rewrite_tree(item)
                for item in value
                if not (
                    isinstance(item, dict)
                    and isinstance(item.get("status"), str)
                    and item.get("status") in {"retired", "deprecated"}
                )
                and not (
                    isinstance(item, str)
                    and item
                    in {
                        "history_key_recovery",
                        "historical_secret_recovery",
                        "retired.history_key_recovery",
                        "ak.profile.federation.high_assurance.v1",
                    }
                )
            ]
        if isinstance(value, str):
            return rewrite_string(value)
        return value

    contract = load(REGISTRY)
    event_contract = contract["event_kind_registry"]
    event_contract.pop("history_admission_contract", None)
    event_contract["authority_commit_admission_contract"] = {
        "applies_to": "Every shared durable Event accepted into a Realm, Circle, or Sidecar authority stream.",
        "consumer_contexts": ["backfill", "shared_read", "reducer_input"],
        "selection": "The current governance Station selects exactly one registered admission branch and evaluates it at the target stream head.",
        "required_evidence": [
            "original_producer_proof",
            "current_authority_generation",
            "current_authorization_and_policy",
            "typed_domain_invariants",
            "matching_realm_commit",
        ],
        "native_admission_classes": [
            "registration_anchor",
            "delegated_pcr_genesis",
            "applet_managed_pcr_genesis",
            "pcr_recovery",
            "direct_conversation_genesis",
            "direct_conversation_agent_genesis",
            "self_authored_proof",
            "sidecar_account_self_authored_proof",
            "service_attested",
            "crypto_verifiable",
        ],
        "acceptance": "A consumer accepts the Event only with a valid RealmCommit in the derived stream and a continuous authority-generation chain.",
        "schema_projection": "schemas/event-envelope.schema.json#/$defs/authority_committed_event",
        "consumer_schema_bindings": [],
    }
    retired_mls_actions = {
        "ak.mls.keypackage",
        "ak.mls.welcome",
        "ak.mls.welcome.own_device",
    }
    contract["capability_action_registry"]["actions"] = [
        row
        for row in contract["capability_action_registry"].get("actions", [])
        if row.get("action") not in retired_mls_actions
    ]
    for key in ("codes", "reason_codes"):
        contract.get("error_code_registry", {})[key] = [
            row
            for row in contract.get("error_code_registry", {}).get(key, [])
            if (row.get("code") or row.get("reason_code") or row.get("reason"))
            not in {"peer_stale", "control_proposal_decision_overdue"}
        ]

    for row in contract.get("schema_registry", {}).get("schemas", []):
        if row.get("schema_id") == "ak.schema.device_revocation_state.v1":
            row["description"] = (
                "Authority-commit-owned durable state for ak.device.revoke security "
                "transactions: exact authority/device/generation binding, universal "
                "revocation_pending gates, terminal command-result release, fault "
                "retention and consecutive same-stream RealmCommit finality."
            )
    for row in contract["authority_source_registry"].get("sources", []):
        for key in ("target_event_kinds", "event_kinds"):
            if isinstance(row.get(key), list):
                row[key] = [
                    entry
                    for entry in row[key]
                    if entry not in retired_mls_actions
                    and entry != "ak.mls.proposal"
                ]
    contract = rewrite_tree(contract)
    schemas = contract.get("schema_registry", {}).get("schemas", [])
    if isinstance(schemas, list):
        unique_schemas = []
        seen_schema_ids: set[str] = set()
        for row in schemas:
            schema_id = row.get("schema_id") if isinstance(row, dict) else None
            if isinstance(schema_id, str) and schema_id in seen_schema_ids:
                continue
            if isinstance(schema_id, str):
                seen_schema_ids.add(schema_id)
            unique_schemas.append(row)
        contract["schema_registry"]["schemas"] = unique_schemas
    save(REGISTRY, contract)

    forbidden_wire_path = ARTIFACT_REGISTRY / "forbidden-wire-fields.json"
    forbidden_wire = load(forbidden_wire_path)
    forbidden_wire.get("context_definitions", {}).pop(
        "retired_device_identity_wire", None
    )
    forbidden_wire["entries"] = [
        row
        for row in forbidden_wire.get("entries", [])
        if row.get("context") != "retired_device_identity_wire"
    ]
    used_contexts = {
        row.get("context")
        for row in forbidden_wire["entries"]
        if isinstance(row.get("context"), str)
    }
    forbidden_wire["context_definitions"] = {
        key: value
        for key, value in forbidden_wire["context_definitions"].items()
        if key in used_contexts
    }
    forbidden_wire["context_definitions"] = {
        key: value
        for key, value in forbidden_wire.get("context_definitions", {}).items()
        if not (
            isinstance(value, dict)
            and isinstance(value.get("status"), str)
            and value.get("status") in {"retired", "deprecated"}
        )
        and not legacy_pattern.search(key)
    }
    forbidden_wire["entries"] = [
        row
        for row in forbidden_wire.get("entries", [])
        if not legacy_pattern.search(
            json.dumps(
                {
                    "id": row.get("id"),
                    "context": row.get("context"),
                    "match": row.get("match"),
                },
                ensure_ascii=False,
            )
        )
        and row.get("context") in forbidden_wire["context_definitions"]
        and "retired" not in json.dumps(row, ensure_ascii=False).lower()
        and "clean break" not in json.dumps(row, ensure_ascii=False).lower()
    ]
    save(forbidden_wire_path, rewrite_tree(forbidden_wire))

    forbidden_model_path = ARTIFACT_REGISTRY / "forbidden-model-terms.json"
    forbidden_model = load(forbidden_model_path)
    forbidden_model["entries"] = [
        row
        for row in forbidden_model.get("entries", [])
        if row.get("context") != "retired_identity_model"
        and not legacy_pattern.search(json.dumps(row, ensure_ascii=False))
    ]
    save(forbidden_model_path, rewrite_tree(forbidden_model))

    for path in sorted(SCHEMAS.glob("*.schema.json")):
        save(path, rewrite_tree(load(path)))

    for path in sorted(ARTIFACT_REGISTRY.glob("*.json")):
        if path in {REGISTRY, forbidden_wire_path, forbidden_model_path}:
            continue
        document = load(path)
        if path.name == "normative-clause-registry.json":
            document["clauses"] = [
                row
                for row in document.get("clauses", [])
                if not legacy_pattern.search(json.dumps(row, ensure_ascii=False))
            ]
        if path.name == "error-code-registry.json":
            for key in ("codes", "reason_codes"):
                document[key] = [
                    row
                    for row in document.get(key, [])
                    if (row.get("code") or row.get("reason_code") or row.get("reason"))
                    not in {"peer_stale", "control_proposal_decision_overdue"}
                ]
        if path.name == "profiles-dependency-graph.json":
            document["nodes"] = [
                node
                for node in document.get("nodes", [])
                if node != "ak.profile.federation.high_assurance.v1"
            ]
            document["edges"] = [
                edge
                for edge in document.get("edges", [])
                if edge.get("from") != "ak.profile.federation.high_assurance.v1"
                and edge.get("to") != "ak.profile.federation.high_assurance.v1"
            ]
        document = rewrite_tree(document)
        if path.name == "operations-error-mapping.json":
            errors = load(ARTIFACT_REGISTRY / "error-code-registry.json")
            known = {
                row.get("code")
                for key in ("codes", "reason_codes")
                for row in errors.get(key, [])
            }
            for row in document.get("operations", []):
                for field in ("codes", "operation_specific"):
                    row[field] = [
                        code
                        for code in row.get(field, [])
                        if code in known and code != "peer_stale"
                    ]
                if isinstance(row.get("description"), str):
                    row["description"] = re.sub(
                        r"\s*peer_stale[^.]*\.", "", row["description"]
                    )
        save(path, document)

    profiles_path = ROOT / "spec/v1/artifacts/profiles/conformance-profiles.json"
    profiles = rewrite_tree(load(profiles_path))

    def drop_profile_id(value: object, profile_id: str) -> object:
        if isinstance(value, dict):
            return {
                key: drop_profile_id(item, profile_id)
                for key, item in value.items()
                if key != profile_id
            }
        if isinstance(value, list):
            return [
                drop_profile_id(item, profile_id)
                for item in value
                if item != profile_id
            ]
        return value

    profiles = drop_profile_id(
        profiles, "ak.profile.federation.high_assurance.v1"
    )
    profile_requirements = profiles.get("profile_requirements", {})
    if isinstance(profile_requirements, dict):
        profile_requirements.pop("ak.profile.federation.high_assurance.v1", None)
        federation = profile_requirements.get("ak.profile.federation_minimal.v1")
        if isinstance(federation, dict):
            federation["prose_requirement_coverage"] = [
                row
                for row in federation.get("prose_requirement_coverage", [])
                if "sibling_positions" not in json.dumps(row, ensure_ascii=False)
                and "fork-resolution" not in json.dumps(row, ensure_ascii=False)
            ]
    for key, value in list(profiles.items()):
        if isinstance(value, list):
            profiles[key] = [
                item
                for item in value
                if item != "ak.profile.federation.high_assurance.v1"
            ]
    profile = profiles.get("profile_requirements", {}).get(
        "ak.profile.direct_conversation_realm.v1", {}
    )
    if isinstance(profile, dict):
        blockers = profile.get("client_local_send_blockers")
        if isinstance(blockers, dict):
            blockers["rationale"] = (
                "personal_blocked is holder-private account state and is evaluated only "
                "on the holder device; the service exposes only blockers it can verify."
            )
            blockers["values"] = ["personal_blocked"]
        profile["binding_invariants"] = [
            rule
            for rule in profile.get("binding_invariants", [])
            if "historical_secret" not in rule and "history secrets" not in rule
        ]
    save(profiles_path, profiles)

    for path in sorted((ROOT / "spec/v1/artifacts/fixtures").glob("*.json")):
        fixture = rewrite_tree(load(path))
        if path.name == "schema-validation-fixture.json":
            for case in fixture.get("schema_validation_cases", []):
                instance = case.get("instance")
                if isinstance(instance, dict):
                    limits = instance.get("limits")
                    if isinstance(limits, dict):
                        limits.pop("mls_governance_proof", None)
        if path.name == "scalability-limits-fixture.json":
            fixture["covers_vectors"] = [
                item
                for item in fixture.get("covers_vectors", [])
                if item not in {
                    "ak.vector.scalability.mls_governance_proof_bounds.v1",
                    "ak.vector.scalability.sibling_fork_limits.v1",
                }
            ]
            fixture["cases"] = [
                case
                for case in fixture.get("cases", [])
                if case.get("vector_id")
                != "ak.vector.scalability.sibling_fork_limits.v1"
            ]
        if path.name == "key-backup-fixture.json":
            fixture["schema_validation_cases"] = [
                case
                for case in fixture.get("schema_validation_cases", [])
                if "threshold_recovery" not in json.dumps(case, ensure_ascii=False)
            ]
        save(path, fixture)

    for path in sorted((ROOT / "spec/v1/artifacts").rglob("*.yaml")):
        path.write_text(
            rewrite_string(path.read_text(encoding="utf-8")),
            encoding="utf-8",
            newline="\n",
        )

    for path in sorted((ROOT / "spec/v1/artifacts").rglob("*.md")):
        path.write_text(
            rewrite_string(path.read_text(encoding="utf-8")),
            encoding="utf-8",
            newline="\n",
        )

    obsolete_doc = ROOT / "spec/v1/zh/authz/cbs-profiles.md"
    if obsolete_doc.exists():
        obsolete_doc.unlink()

    device_path = ROOT / "spec/v1/zh/crypto-media/device-lifecycle.md"
    device_text = device_path.read_text(encoding="utf-8")
    device_text = re.sub(
        r"`ak\.device\.revoke` 是 principal control stream 上的 Control Move：.*?(?=## 3\.)",
        """`ak.device.revoke` 是 principal control stream 的 producer-signed Event。当前治理 Station 在目标 stream head 处验证 caller、device generation、recovery/session policy 与领域 revision；成功时签发该 Event 的 RealmCommit，并在同一事务内更新 device lifecycle 与后续 MLS removal intent。失败或 retryable unavailable 不写共享状态。\n\n`SecurityRotationTransaction` 固定绑定 revoke Event、replacement secret/backup material 与清理步骤。完成结果携带该 revoke Event 的 `CommittedEventRef`；exact replay 返回同一结果，异内容使用同一 transaction id 时返回 conflict。\n\n""",
        device_text,
        flags=re.DOTALL,
    )
    device_text = re.sub(
        r"#### 8\.2\.2 Human generic Control 的 portable signer evidence（normative）.*?(?=#### 8\.3)",
        """#### 8.2.2 Human control signer evidence（normative）\n\nHuman 设备签署高风险 Event 时使用 `AuthenticatedSignerResolutionEvidence` 的 `account_device_control` 分支。该 evidence 绑定 Account、device method/key、current generation，以及授权 Event 的 `CommittedEventRef`；验证方核对 producer proof、current device lifecycle、authority generation 和目标 stream 的连续 RealmCommit，不下载或重放账号历史。\n\nEvidence 只证明 exact signer 在该 generation 的授权来源；membership、scope、capability、recovery policy 与领域 revision 仍由当前治理 Station在 commit 位置独立验证。\n\n""",
        device_text,
        flags=re.DOTALL,
    )
    device_text = re.sub(
        r"首个新 generation RealmCommit 的接受与发布、generation CAS、旧 generation fence、两条 Event 接受、设备目录变更、.*?(?=基础 `pcr_policy` 恢复)",
        """RecoveryTransaction 终结时，reanchor Event 与 replacement-device authorize Event 必须分别取得同一 PCR stream 中连续的 `CommittedEventRef`。generation CAS、设备目录变更、session 消费与 transaction completion 在同一事务提交；失败为零写入。byte-identical retry 返回同一 receipt，异内容返回 conflict。\n\n""",
        device_text,
        flags=re.DOTALL,
    )
    device_path.write_text(device_text, encoding="utf-8", newline="\n")

    key_management_path = ROOT / "spec/v1/zh/identity/key-management.md"
    key_management_text = key_management_path.read_text(encoding="utf-8")
    key_management_text = re.sub(
        r"### 7\.1 备份内容.*?(?=### 7\.2 Backup Envelope)",
        """### 7.1 备份内容

`backup_kind=secret_storage` 是 v1 唯一的 portable key-backup 内容类型。它只承载用户显式存入的 secret-storage items；MUST NOT 承载 MLS group state、epoch/exporter secret、sender counter、pending Welcome、leaf signing key 或历史密文解密材料。

MLS authoring state 只能由本机已验证 state 延续，或由当前成员经普通 KeyPackage/Welcome 建立。备份 restore 不得创建或提升 MLS membership，也不得为新设备补发历史解密材料。

""",
        key_management_text,
        flags=re.DOTALL,
    )
    key_management_path.write_text(
        key_management_text, encoding="utf-8", newline="\n"
    )

    for prose_path in sorted((ROOT / "spec/v1/zh").rglob("*.md")):
        prose = prose_path.read_text(encoding="utf-8")
        prose = re.sub(
            r"\.\./authz/cbs-profiles\.md(?:#[^)\s]+)?",
            "../sync/authority-commit-log.md",
            prose,
        )
        prose = re.sub(
            r"\./cbs-profiles\.md(?:#[^)\s]+)?",
            "../sync/authority-commit-log.md",
            prose,
        )
        prose = prose.replace(
            "../../artifacts/registry/mls-proposal-admission-registry.json",
            "../sync/authority-commit-log.md",
        )
        prose = rewrite_string(prose)
        prose_path.write_text(prose, encoding="utf-8", newline="\n")

    en_root = ROOT / "spec/v1/en"
    for prose_path in sorted(en_root.rglob("*.md")):
        prose_path.write_text(
            rewrite_string(prose_path.read_text(encoding="utf-8")),
            encoding="utf-8",
            newline="\n",
        )


def remove_mls_history_recovery_surfaces() -> None:
    """Keep MLS epoch material client-local and remove every network recovery carrier."""

    def remove_field_constraints(value: object, field: str) -> None:
        if isinstance(value, dict):
            properties = value.get("properties")
            if isinstance(properties, dict):
                properties.pop(field, None)
            required = value.get("required")
            if isinstance(required, list):
                value["required"] = [item for item in required if item != field]
            for keyword in ("allOf", "anyOf", "oneOf"):
                branches = value.get(keyword)
                if isinstance(branches, list):
                    value[keyword] = [
                        branch
                        for branch in branches
                        if f'"{field}"' not in json.dumps(branch, ensure_ascii=False)
                    ]
            for item in list(value.values()):
                remove_field_constraints(item, field)
        elif isinstance(value, list):
            for item in value:
                remove_field_constraints(item, field)

    def remove_exact_token(value: object, token: str) -> object:
        if isinstance(value, dict):
            return {
                key: remove_exact_token(item, token)
                for key, item in value.items()
                if key != token
            }
        if isinstance(value, list):
            return [
                remove_exact_token(item, token)
                for item in value
                if item != token
            ]
        return value

    for name in ("realm.schema.json", "circle.schema.json", "circle-operations.schema.json"):
        path = SCHEMAS / name
        document = load(path)
        remove_field_constraints(document, "durability_policy")
        save(path, document)

    for name in ("event-payload.schema.json", "realm-organization-operations.schema.json"):
        path = SCHEMAS / name
        document = remove_exact_token(load(path), "durability_policy")

        def remove_durability_prose(value: object) -> object:
            if isinstance(value, dict):
                return {key: remove_durability_prose(item) for key, item in value.items()}
            if isinstance(value, list):
                return [remove_durability_prose(item) for item in value]
            if isinstance(value, str):
                return value.replace(", durability_policy", "").replace(
                    "durability_policy, ", ""
                )
            return value

        document = remove_durability_prose(document)
        save(path, document)

    identity_link_path = SCHEMAS / "identity-link.schema.json"
    identity_link = load(identity_link_path)
    response_fields = {
        "response_signing_verification_method",
        "response_signing_public_key_b64u",
        "response_signing_public_key_digest",
    }
    identity_link["required"] = [
        item for item in identity_link.get("required", []) if item not in response_fields
    ]
    for field in response_fields:
        identity_link.get("properties", {}).pop(field, None)
    proof_digest = (
        identity_link.get("properties", {})
        .get("proof", {})
        .get("properties", {})
        .get("payload_digest", {})
    )
    if isinstance(proof_digest, dict):
        proof_digest["description"] = (
            "Hash of canonical input bytes: utf8('ak.identity-link-v1\\n') || "
            "canonical_json(identity-link object with proof.payload_digest and "
            "proof.signature omitted)."
        )
    save(identity_link_path, identity_link)

    enum_updates = {
        "key-backup-active-series.schema.json": [("$defs", "backup_kind")],
        "security-transaction.schema.json": [("$defs", "backup_rotation_binding", "properties", "backup_kind")],
        "keys-operations.schema.json": [("$defs", "backup_series_erase_result", "properties", "backup_kind")],
    }
    for name, pointers in enum_updates.items():
        path = SCHEMAS / name
        document = load(path)
        for pointer in pointers:
            node = document
            for part in pointer:
                node = node[part]
            node["enum"] = ["secret_storage"]
        save(path, document)

    recovery_receipt_path = SCHEMAS / "recovery-receipt.schema.json"
    recovery_receipt = load(recovery_receipt_path)
    recovery_receipt = remove_exact_token(recovery_receipt, "mls_history")
    save(recovery_receipt_path, recovery_receipt)

    keys_ops_path = SCHEMAS / "keys-operations.schema.json"
    keys_ops = remove_exact_token(load(keys_ops_path), "mls_history")
    erase_results = keys_ops["$defs"]["backup_series_erase_outcome"]["properties"]["series_results"]
    erase_results["minItems"] = 1
    erase_results["maxItems"] = 1
    save(keys_ops_path, keys_ops)

    security_path = SCHEMAS / "security-transaction.schema.json"
    security = load(security_path)
    rotation_items = security["$defs"]["security_rotation_plan"]["properties"]["backup_rotations"]
    rotation_items["minItems"] = 1
    rotation_items["maxItems"] = 1
    rotation_items["description"] = (
        "The single secret_storage entry; its nested binding is the sole source of "
        "the reserved series and object references."
    )
    save(security_path, security)

    did_registry_names = ("did-document-contract-registry.json", "contract-registry.json")
    for name in did_registry_names:
        path = ARTIFACT_REGISTRY / name
        document = load(path)
        registry = document.get("did_document_contract_registry", document)
        for key in ("service_entries", "service_types", "arkret_service_types", "entries"):
            rows = registry.get(key)
            if isinstance(rows, list):
                registry[key] = [
                    row
                    for row in rows
                    if not (
                        isinstance(row, dict)
                        and row.get("type") == "ArkretRealmHistoryRecoveryKey"
                    )
                ]
        save(path, document)

    contract_path = ARTIFACT_REGISTRY / "contract-registry.json"
    contract = load(contract_path)
    contract_evidence = contract.get("did_evidence_boundary_registry", {})
    for key, rows in list(contract_evidence.items()):
        if isinstance(rows, list):
            contract_evidence[key] = [
                row
                for row in rows
                if not (
                    isinstance(row, dict)
                    and row.get("did_path") == "response_signing_verification_method"
                )
            ]
    save(contract_path, contract)

    evidence_path = ARTIFACT_REGISTRY / "did-evidence-boundary-registry.json"
    evidence = load(evidence_path)
    evidence_registry = evidence.get("did_evidence_boundary_registry", evidence)
    for key, rows in list(evidence_registry.items()):
        if isinstance(rows, list):
            evidence_registry[key] = [
                row
                for row in rows
                if not (
                    isinstance(row, dict)
                    and row.get("did_path") == "response_signing_verification_method"
                )
            ]
    save(evidence_path, evidence)

    error_names = {"durability_scheme_incompatible"}
    for name in ("error-code-registry.json", "contract-registry.json"):
        path = ARTIFACT_REGISTRY / name
        document = load(path)
        registry = document.get("error_code_registry", document)
        for key in ("codes", "reason_codes"):
            if isinstance(registry.get(key), list):
                registry[key] = [
                    row
                    for row in registry[key]
                    if (row.get("code") or row.get("reason_code")) not in error_names
                ]
        save(path, document)
    for name in ("error-code-registry.json", "contract-registry.json"):
        path = ARTIFACT_REGISTRY / name
        document = load(path)

        def rewrite_genesis_error(value: object) -> object:
            if isinstance(value, dict):
                return {key: rewrite_genesis_error(item) for key, item in value.items()}
            if isinstance(value, list):
                return [rewrite_genesis_error(item) for item in value]
            if isinstance(value, str):
                return value.replace(" or durability_policy", "").replace(
                    "content_scheme or durability_policy", "content_scheme"
                )
            return value

        save(path, rewrite_genesis_error(document))

    for name in ("event-kind-registry.json", "contract-registry.json"):
        path = ARTIFACT_REGISTRY / name
        document = load(path)
        registry = document.get("event_kind_registry", document)
        for row in registry.get("event_kinds", []):
            if row.get("event_kind") == "ak.circle.create":
                row["payload"] = (
                    "Circle create (intra-Realm scoped event/message boundary). "
                    "Initializes an independent MLS group and epoch-0 governance binding "
                    "when encryption_profile=mls_rfc9420."
                )
            elif row.get("event_kind") == "ak.circle.update":
                row["payload"] = (
                    "Circle metadata patch. history_access, realm_id, encryption_profile, "
                    "content_scheme and MLS identity fields are create-locked."
                )
            elif row.get("event_kind") == "ak.mls.commit":
                row["payload"] = (
                    "MLS commit. governance_binding MUST keep the Genesis-fixed "
                    "content_scheme and bind the current key_access_revision."
                )
        save(path, document)

    creator_path = ARTIFACT_REGISTRY / "mls-creator-bootstrap-transaction-registry.json"
    creator = remove_exact_token(load(creator_path), "durability_policy")

    def simplify_creator(value: object) -> object:
        if isinstance(value, dict):
            return {key: simplify_creator(item) for key, item in value.items()}
        if isinstance(value, list):
            return [
                simplify_creator(item)
                for item in value
                if not (isinstance(item, str) and "durability_policy" in item)
            ]
        if isinstance(value, str):
            return value.replace(" and durability_policy", "").replace(
                " or durability_policy", ""
            )
        return value

    save(creator_path, simplify_creator(creator))

    agent_path = ROOT / "spec/v1/artifacts/fixtures/agent-vectors-fixture.json"
    agent = load(agent_path)
    removed_agent_vector = "ak.vector.agent.pcr_history_backup.v1"
    agent["covers_vectors"] = [
        item for item in agent.get("covers_vectors", []) if item != removed_agent_vector
    ]
    agent["cases"] = [
        row
        for row in agent.get("cases", [])
        if row.get("vector_id") != removed_agent_vector
    ]
    save(agent_path, agent)

    privacy_path = ROOT / "spec/v1/artifacts/fixtures/privacy-security-fixture.json"
    privacy = load(privacy_path)
    for row in privacy.get("cases", []):
        if row.get("vector_id") != "ak.vector.identity_link.minimal_metadata_author_credential.v1":
            continue
        row.get("base", {}).pop("history_response_signing_binding", None)
        row["assertions"] = [
            assertion
            for assertion in row.get("assertions", [])
            if "history response" not in assertion
        ]
    save(privacy_path, privacy)

    rotation_path = ROOT / "spec/v1/artifacts/fixtures/security-transaction-resilience-fixture.json"
    rotation = load(rotation_path)
    for case in rotation.get("schema_validation_cases", []):
        instance = case.get("instance", {})
        results = instance.get("series_results")
        if isinstance(results, list):
            instance["series_results"] = [
                row for row in results if row.get("backup_kind") == "secret_storage"
            ]
    for case in rotation.get("rotation_cases", []):
        if case.get("name") == "partial_secret_storage_erase_then_restart":
            case["authoritative_new_pointers"] = ["secret_storage"]
            case["first_outcome"] = {"secret_storage": "failed_retryable"}
            case["expected_after_restart"] = {
                "secret_storage": "erased",
                "confirmation_emitted_once": True,
                "accepted_erase_step_count": 1,
            }
    save(rotation_path, rotation)

    bootstrap_fixture = ROOT / "spec/v1/artifacts/fixtures/mls-creator-bootstrap-recovery-fixture.json"
    bootstrap = load(bootstrap_fixture)

    def rewrite_bootstrap(value: object) -> object:
        if isinstance(value, dict):
            return {key: rewrite_bootstrap(item) for key, item in value.items()}
        if isinstance(value, list):
            return [rewrite_bootstrap(item) for item in value]
        if isinstance(value, str):
            return value.replace(
                "the durability archive, ", ""
            ).replace("durability_policy", "content_scheme")
        return value

    save(bootstrap_fixture, rewrite_bootstrap(bootstrap))

    runner_path = ARTIFACT_REGISTRY / "runner-kind-registry.json"
    runner = load(runner_path)
    for row in runner.get("runner_kinds", runner.get("runners", [])):
        if isinstance(row.get("execution_contract"), str):
            row["execution_contract"] = row["execution_contract"].replace(
                ", and RHRK eager-authority commit state transitions", ""
            )
    save(runner_path, runner)

    for name in ("schema-registry.json", "operation-registry.json", "contract-registry.json"):
        path = ARTIFACT_REGISTRY / name
        document = load(path)

        def rewrite_registry_text(value: object) -> object:
            if isinstance(value, dict):
                return {key: rewrite_registry_text(item) for key, item in value.items()}
            if isinstance(value, list):
                return [rewrite_registry_text(item) for item in value]
            if isinstance(value, str):
                return value.replace(
                    "old secret_storage and mls_history backup objects",
                    "old secret_storage backup objects",
                ).replace(
                    "old secret_storage and mls_history series",
                    "old secret_storage series",
                )
            return value

        save(path, rewrite_registry_text(document))

    openapi_path = ROOT / "spec/v1/artifacts/openapi/arkret-service-api.openapi.yaml"
    openapi = openapi_path.read_text(encoding="utf-8")
    openapi = re.sub(
        r"\n    historyResponseCapabilityAuth:\n.*?(?=\n    [A-Za-z][A-Za-z0-9]+:|\n  [a-zA-Z])",
        "",
        openapi,
        flags=re.DOTALL,
    )
    openapi = openapi.replace("\n          - mls_history", "")
    openapi_path.write_text(openapi, encoding="utf-8", newline="\n")

    signal_path = ROOT / "spec/v1/zh/sync/signal.md"
    signal = signal_path.read_text(encoding="utf-8")
    signal = signal.replace("、history response", "")
    signal = signal.replace(
        "exporter scope 可用本 epoch history secret，standard MLS 使用\n同 epoch、不可交付的 `ak.signal-root-v1` exporter root。",
        "所有 MLS scope 都使用当前 epoch、不可交付的 `ak.signal-root-v1` exporter root。",
    )
    signal = signal.replace(
        "Signal 不得借\nhistory response stream 交付 standard signal root，也不得把 Signal digest 注册为持久 ID。",
        "Signal root 只能由接收端当前本地 MLS state 导出，不得通过任何网络响应交付；Signal digest 也不得注册为持久 ID。",
    )
    signal_path.write_text(signal, encoding="utf-8", newline="\n")

    encryption_path = ROOT / "spec/v1/zh/crypto-media/encryption-and-audit.md"
    encryption = encryption_path.read_text(encoding="utf-8")
    encryption = encryption.replace(
        "| durability_policy? | 仅 exporter scheme 必填，none 或 organization_recovery_key |\n",
        "",
    )
    encryption = encryption.replace(
        "binding 的 canonical CBOR map 仅编码本节保留成员；不保留已删除 scope/group 镜像的空值、旧编号占位或兼容解码。",
        "binding 的 canonical CBOR map 只编码本节定义的成员；空值、未登记编号和未知字段一律拒绝。",
    )
    encryption = encryption.replace(" 与 history request sender\ndomain", "\ndomain")
    encryption = encryption.replace(
        "§2.5.3 governance proof 的 `local_mls_leaves[].actor_id` 同样逐条携带完整\n`ActorId`。",
        "§2.5.3 的客户端 MLS leaf 校验同样逐条使用完整 `ActorId`。",
    )
    encryption = encryption.replace(
        "history tag，不使用“当前/上一窗”限制。`target_ref` 是已存在的 canonical EventId。Exporter late receiver 可从获准\nhistory secret 验证；standard MLS routing root 不交付给后加入者。",
        "history tag，不使用“当前/上一窗”限制。`target_ref` 是已存在的 canonical EventId。Receiver 只能使用本机仍持有的对应 epoch root；routing root 不交付给后加入者。",
    )
    encryption = encryption.replace(
        "该 epoch 的独立 history secret、group-state ref、counter marker，以及启用时同 Event 内的单一 RHRK archive，才允许\n下一 Commit 或 application send。Standard MLS 只保存 RFC 9420 active state，不生成 history secret/archive。",
        "该 epoch 的本地 content root、group-state ref 与 counter marker，才允许下一 Commit 或 application send。任何 epoch secret 都不得进入 Event、portable backup 或 Station-side recovery carrier。",
    )
    encryption = encryption.replace(
        "客户端 MUST 对本地先前 epoch key 使用设备保护存储或明确授权的 key backup，并在 retention / legal hold / erasure policy 不再要求保留时销毁。",
        "客户端 MUST 对本地先前 epoch key 使用设备保护存储，并在 retention / legal hold / erasure policy 不再要求保留时销毁；不得上传或转交该材料。",
    )
    encryption = encryption.replace(
        "同一 effective scope 的 genesis/epoch/key-schedule 使用 `sequenced_state`。同一前态的竞争 genesis/Commit 必须经过唯一安全确认；至多一个成功，失败者不安装 staged state。",
        "同一 effective scope 的 genesis/epoch/key-schedule 由该 scope 的 authority commit stream 串行确认。同一前态的竞争 genesis/Commit 至多一个成功，失败者不安装 staged state。",
    )
    encryption = encryption.replace(
        "不得按到达顺序编号，也不得从 governance proof bundle 获取 leaves。",
        "不得按到达顺序编号；leaf 只从客户端已验证的 MLS public transition 与本地 group state 取得。",
    )
    encryption = re.sub(
        r"\*\*selector 的性质\*\*.*?(?=\*\*原子 cut point\*\*)",
        """**selector 的性质**：`content_scheme` 在 `genesis_intent_persisted` 阶段只是本地创建意图；一旦 accepted Genesis 固定该值，后续 Commit 只能逐字保持。创建者可在首次网络副作用前原子替换整份本地 intent；此后该值不可变。创建记录不得包含任何 epoch secret、恢复 archive 或 portable MLS state。\n\n""",
        encryption,
        flags=re.DOTALL,
    )
    encryption_path.write_text(encryption, encoding="utf-8", newline="\n")

    device_path = ROOT / "spec/v1/zh/crypto-media/device-lifecycle.md"
    device = device_path.read_text(encoding="utf-8")
    device = re.sub(
        r"### 10\.2 Secret Sharing（`ak\.secret\.\*`）.*?(?=## 11\.)",
        """### 10.2 新设备 MLS 建立（normative）

新设备不得向旧设备请求或接收账户 secret、MLS epoch/exporter secret 或 active group state。完成 §10.1 verification checkpoint 与当前设备授权后，它只能发布自己的 KeyPackage，由每个目标 scope 的当前成员提交 Add，并通过该设备专属的 `MlsWelcomeDelivery` 取得 Welcome。Welcome 只建立从该次 Add 开始的成员资格，不补发加入前的解密材料。

账户级 `secret_storage` 恢复仅使用 §12 的端到端加密备份；identity root、device private key、MLS private state、sender counter 与 pending Welcome 永不通过 to-device 消息共享。配对二维码、短码和链接也不得携带这些材料。

""",
        device,
        flags=re.DOTALL,
    )
    device = device.replace("- MLS group secrets backup key\n", "")
    device = re.sub(
        r"\| MLS epoch / Realm history secret \| `mls_history` \|\n",
        "",
        device,
    )
    device_path.write_text(device, encoding="utf-8", newline="\n")

    identity_path = ROOT / "spec/v1/zh/identity/identity-did.md"
    identity = identity_path.read_text(encoding="utf-8")
    identity = re.sub(
        r"\| `ArkretRealmHistoryRecoveryKey` \|.*?\n",
        "",
        identity,
    )
    identity = re.sub(
        r"### 8\.3 Realm History Recovery Key.*?(?=### 8\.4)",
        "",
        identity,
        flags=re.DOTALL,
    )
    identity_path.write_text(identity, encoding="utf-8", newline="\n")

    realm_path = ROOT / "spec/v1/zh/models/realm-and-space.md"
    realm = realm_path.read_text(encoding="utf-8")
    realm = re.sub(r"\| `durability_policy` \|.*?\n", "", realm)
    realm = realm.replace(
        "`trust_domain`、`encryption_profile`、`content_scheme` 与 `durability_policy` 在 create/MLS Genesis 时锁定，后续不可变；后两者不得出现在 mutable policy bundle 中。",
        "`trust_domain`、`encryption_profile` 与 `content_scheme` 在 create/MLS Genesis 时锁定，后续不可变；`content_scheme` 不得出现在 mutable policy bundle 中。",
    )
    realm = realm.replace(
        "- 组织作为 notary、notary controller 或 RHRK 接收方，必须分别由 `notary` / notary control move、`durability_policy` 等字段和事件明确表示；不得从 `owning_organization_ids` 或 `ak.realm.organization` 自动继承。组织关系本身也不能替账号选择 Station。",
        "- 组织作为 notary 或 notary controller 时，必须由 `notary` 或对应 control Event 明确表示；不得从 `owning_organization_ids` 或 `ak.realm.organization` 自动继承。组织关系本身也不能替账号选择 Station。",
    )
    realm = re.sub(
        r"### 2\.3\.1 `durability_policy`.*?(?=### 2\.4)",
        "",
        realm,
        flags=re.DOTALL,
    )
    realm_path.write_text(realm, encoding="utf-8", newline="\n")

    circle_path = ROOT / "spec/v1/zh/models/circle.md"
    circle = circle_path.read_text(encoding="utf-8")
    circle = re.sub(r"\| `durability_policy` \|.*?\n", "", circle)
    circle = circle.replace(
        "Circle 不另建 RealmCommit 序列，权限和 MLS 安全变更在父 Realm 的安全域确认。Plaintext Circle 不存在 MLS group。Standard/exporter Circle 各自拥有 canonical group、Genesis/Commit、Welcome、\nleaf 与 snapshot；`content_scheme` 和 key-access revision 固定在自己的 Genesis。",
        "每个 Circle 都有独立的 authority commit stream，Circle Event 只由该 stream 的 RealmCommit 排序与确认；父 Realm stream 与 Circle stream 之间不存在 predecessor 关系。Plaintext Circle 不存在 MLS group。Standard/exporter Circle 各自拥有 canonical group、Genesis/Commit、Welcome、leaf 与 snapshot；`content_scheme` 和 key-access revision 固定在自己的 Genesis。",
    )
    circle = circle.replace(
        "Standard scheme 固定 since_join 且没有 history secret；exporter scheme 才允许 private delivery/backup/RHRK。",
        "Standard scheme 固定 since_join；exporter scheme 的 epoch content root 也只能保留在成员设备本地，不提供 backup、network delivery 或恢复密钥。",
    )
    circle_path.write_text(circle, encoding="utf-8", newline="\n")

    applet_schema_path = ROOT / "spec/v1/zh/extensions/applet-schema.md"
    applet_schema = applet_schema_path.read_text(encoding="utf-8")
    applet_schema = applet_schema.replace(
        "唯一合法形态为 `ak:applet:<uuidv7>`；旧的 service DID 代用形态已删除。",
        "唯一合法形态为 `ak:applet:<uuidv7>`；其它形态均不合法。",
    )
    applet_schema_path.write_text(applet_schema, encoding="utf-8", newline="\n")

    glossary_path = ROOT / "spec/v1/zh/overview/glossary.md"
    glossary = glossary_path.read_text(encoding="utf-8")
    glossary = re.sub(
        r"\| backup_kind \|.*?\n",
        "| backup_kind | 密钥备份分类 | `ak.schema.key_backup.v1` 的 closed enum；v1 仅有 `secret_storage`，且不得承载 MLS state、epoch/exporter secret 或 sender counter。详见 [`key-management.md` §7](../identity/key-management.md)。 |\n",
        glossary,
    )
    glossary = re.sub(r"\| `RHRK` \|.*?\n", "", glossary)
    glossary_path.write_text(glossary, encoding="utf-8", newline="\n")

    key_path = ROOT / "spec/v1/zh/identity/key-management.md"
    key = key_path.read_text(encoding="utf-8")
    key = key.replace(
        "；`mls_history` 仅可恢复合法 history-secret ranges（§7.5.6）", ""
    )
    key = key.replace(
        "服务不得在该路径要求 `mls_history` active-state快照。", "服务不得在该路径要求或接受 MLS active-state 快照。"
    )
    key = key.replace(
        "该检查点不得上传进 human `mls_history` backup，也不构成任何可被他方验证的证明",
        "该检查点不得上传，也不构成任何可被他方验证的证明",
    )
    key = re.sub(
        r"#### 7\.5\.0 `backup_kind`.*?(?=#### 7\.5\.1)",
        """#### 7.5.0 `backup_kind` 与 recipient method（normative）

v1 的 `backup_kind` 固定为 `secret_storage`。它可使用 `passphrase_kdf`、`recovery_public_key` 或 `secret_storage_key`；各 method 的强度与限制由下列小节定义。任何 MLS state、epoch/exporter secret、sender counter、leaf key 或 pending Welcome 都不是合法备份 plaintext。

""",
        key,
        flags=re.DOTALL,
    )
    key = key.replace(
        "`passphrase_kdf` 仅用于 `secret_storage` envelope；`mls_history` envelope MUST NOT 使用 `passphrase_kdf`，即使作为 fallback 也不允许。需要用户口令参与 MLS 历史恢复的实现 MUST 让口令先解锁 `secret_storage` root、recovery key 或 hardware wrapper 的本地保护层，而不是在 wire 上发布 `backup_kind=\"mls_history\", recipient_method=\"passphrase_kdf\"` 的 envelope。",
        "`passphrase_kdf` 仅用于 `secret_storage` envelope。它不得解锁或封装 MLS state、epoch/exporter secret、sender counter、leaf key或 pending Welcome。",
    )
    key = re.sub(
        r"- 当 `backup_kind=\"mls_history\"`.*?\n",
        "",
        key,
    )
    key = re.sub(
        r"#### 7\.5\.6 Agent PCR history-only backup.*?(?=### 7\.6)",
        "",
        key,
        flags=re.DOTALL,
    )
    key = key.replace(
        "`active_series` 是必填 `BackupActiveSeriesState`，按 `account_id, control_realm_id, authority_revision, secret_storage, mls_history`",
        "`active_series` 是必填 `BackupActiveSeriesState`，按 `account_id, control_realm_id, authority_commit_id, secret_storage`",
    )
    key = key.replace("或 `mls_history` ready 状态", "或任何 MLS 备份状态")
    key = key.replace("`secret_storage`与`mls_history`必须由同一`SecurityRotationTransaction`预留并", "`secret_storage`必须由同一`SecurityRotationTransaction`预留并")
    key = key.replace("、`mls_history` 域使用 `passphrase_kdf` 的 envelope 被拒绝", "、MLS private material 作为 plaintext 被拒绝")
    key_path.write_text(key, encoding="utf-8", newline="\n")

    account_lifecycle_path = ROOT / "spec/v1/zh/identity/account-lifecycle.md"
    account_lifecycle = account_lifecycle_path.read_text(encoding="utf-8")
    account_lifecycle = re.sub(
        r"controller E2EE client 随后提交 Actor Profile；若该 PCR 使用 exporter scheme，.*?不新增第四状态轴。",
        "controller E2EE client 随后提交 Actor Profile；MLS private state 始终留在创建它的设备本地，不是 provisioning、pairing 或 backup 的前置。通用 Agent view 从 complete 起只暴露 lifecycle、readiness、presence 三轴；未完成首次 pairing 由 `readiness.blockers` 中的 `runtime_key_missing`/`pairing_open` 表达，不新增第四状态轴。",
        account_lifecycle,
    )
    account_lifecycle_path.write_text(
        account_lifecycle, encoding="utf-8", newline="\n"
    )

    for path in (
        ROOT / "spec/v1/zh/identity/security-transactions.md",
        ROOT / "spec/v1/zh/guides/migrating-from-matrix.md",
        ROOT / "spec/v1/zh/conformance/conformance-profiles.md",
    ):
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"^.*mls_history.*\n", "", text, flags=re.MULTILINE)
        path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    migrate_registry()
    migrate_event_envelope()
    migrate_realm_genesis()
    migrate_event_payload()
    migrate_security_transaction_commit_terms()
    strip_retired_schema_references()
    prune_event_payload_definitions()
    remove_retired_common_ids()
    prune_service_operation_dtos()
    migrate_auxiliary_registries()
    retire_obsolete_registry_artifacts()
    retire_mls_governance_proof_discovery()
    migrate_retired_lint_registries()
    migrate_openapi()
    migrate_non_http_bindings()
    migrate_service_http_prose()
    reconcile_authority_commit_residuals()
    clean_break_active_surfaces()
    remove_mls_history_recovery_surfaces()


if __name__ == "__main__":
    main()
