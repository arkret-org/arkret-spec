#!/usr/bin/env python3
"""Recompute the byte-level transcript KAT for every registered proof context.

``proof-context-registry.json`` pins which fields enter a detached-proof
transcript, but for a long time only ``ak.event_proof.v1`` had canonical bytes to
compare against. Everything else existed as a field-name array plus prose, so two
implementations could disagree on the unsigned projection, on the ``audience``
shape, on whether an absent optional binding field is omitted or written as
``null``, and on whether the context constant lives inside the binding object --
and the disagreement would only surface during interop.

This script derives one accept case and one cross-family reject case per
registered context from the registry itself, so the 63 transcripts are
recomputable rather than transcribed. Every byte in the fixture is produced here:
the JCS strings, the ``payload_digest``, the JWS signing input and the Ed25519
signature over the shared conformance test key.

Usage::

    python tools/regenerate_proof_context_transcript_fixture.py
    python tools/regenerate_proof_context_transcript_fixture.py --check
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from tools.artifact_lint.core import canonical_json  # noqa: E402

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"

REGISTRY = ARTIFACTS / "registry" / "proof-context-registry.json"

SCHEMAS = ARTIFACTS / "schemas"

FIXTURE = ARTIFACTS / "fixtures" / "proof-context-transcript-fixture.json"
VECTOR_REGISTRY = ARTIFACTS / "registry" / "vector-registry.json"

# The single conformance signing key already published by
# crypto-signature-fixture.json and keypackage-write-transcript-fixture.json. A
# second test key would let a verifier "pass" by picking the wrong one.
TEST_KEY = {
    "kid": "did:webvh:z6mkfixture:alice.example#ed25519-2026-05-fixture",
    "private_key_seed": "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8",
    "public_key": "A6EHv_POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg",
    "note": "Public conformance test key only. Production profiles MUST reject this test DID/key domain.",
    "algorithm": "Ed25519",
}

PROTECTED_HEADER = {"alg": "Ed25519"}

# Binding members contributed by the proof itself rather than by the signed
# object body. Everything else in binding_fields names a body member and must
# therefore also appear in the object the payload digest covers.
PROOF_SIDE_FIELDS = frozenset(
    {
        "context",
        "verification_method",
        "created_at",
        "domain",
        "audience",
        "proof_purpose",
        "signature_algorithm",
        "kind",
        "proof_kind",
    }
)

# Binding members that carry the digest of the unsigned projection itself.
SELF_DIGEST_FIELDS = ("payload_digest", "receipt_digest", "event_digest", "envelope_digest")

PROOF_CARRIER_NAMES = ("proofs", "proof", "signature", "signatures", "governance_proof")

# Event envelopes drop four members, not one: encoding.md section 6 removes the
# post-signature projections plus event_id, which is a function of the digest.
EVENT_ENVELOPE_REMOVED = ["actor_kind", "event_id", "proofs", "unsigned"]

# Families whose carrier or digest subject cannot be read off the schema node,
# because the registered node is the proof object itself rather than the object
# the digest covers. `schema_body` false means the node's own properties describe
# the proof, so the body comes from the binding fields alone.
PROJECTION_OVERRIDES: dict[str, dict[str, Any]] = {
    "event_envelope": {
        "subject_pointer": "",
        "removed_members": EVENT_ENVELOPE_REMOVED,
        "schema_body": False,
        "shared_event_envelope": True,
    },
    "principal_server_event_admission": {
        "subject_pointer": "",
        "removed_members": EVENT_ENVELOPE_REMOVED,
        "schema_body": False,
        "shared_event_envelope": True,
    },
    "directory_governance_request": {
        "subject_pointer": "",
        "removed_members": ["governance_proof"],
        "schema_body": False,
    },
    "key_backup_delete_authority": {
        "subject_pointer": "",
        "removed_members": ["proof"],
        "schema_body": False,
    },
}

# The two envelope-digest families reuse the published Event KAT envelope so the
# two fixtures cannot drift into two different canonical Event payloads.
CRYPTO_SIGNATURE_FIXTURE = ARTIFACTS / "fixtures" / "crypto-signature-fixture.json"

CRYPTO_SIGNATURE_VECTOR = "ak.vector.encoding.crypto.ed25519_detached_jws.v1"

# Deterministic body values. Every literal here is reused verbatim from an
# existing fixture so the transcript bodies stay inside the typed-ID, DID and
# timestamp shapes the rest of the artifact lint already enforces.
VALUE_TABLE: dict[str, Any] = {
    "aad_digest": "sha256:bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222",
    "accepted_at": "2026-08-08T00:00:00.000Z",
    "account_authority_id": "ak:did_core:webvh:z6mkfixtureauthorityexample",
    "account_id": "acct_123",
    "account_subject": "sha256:4444444444444444444444444444444444444444444444444444444444444444",
    "actor_id": "ak:did_core:webvh:z6mkfixture",
    "agent_id": "ak:did_core:webvh:z6mkagent",
    "agent_slug": "summary",
    "algorithms": ["ak.hpke_x25519_aead_chacha20poly1305.v1", "ak.mls.v1"],
    "applet_id": "ak:applet:019a6aa0-0000-7000-8000-000000000000",
    "artifact_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "artifact_key": "resolution",
    "attested_at": "2026-05-01T00:00:00.000Z",
    "auth_frontier": ["ak:event:AR8bu-n-kOOB3nRUvYuIEglCX5B-JpFaNTex9gxs_cWY"],
    "auth_state_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "authority_kind": "witness_quorum",
    "authority_set_ref": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
    "authorization_binding_kind": "registration_anchor",
    "authorized_by": "ak:grant:Ae03WQeR-L5LzeW5AmsilSKx5U51QwuIRByzW21YdRz_",
    "backup_id": "ak:backup:0196419b-0000-7000-8000-000000000200",
    "base_url": "https://applet.example",
    "candidate_base_url": "https://target-new.example/",
    "challenge": "agent_pairing_request:01964137-0000-7000-8000-000000000000",
    "challenge_id": "ak:organization_registration_challenge:0000000000000000000000000000000000000000000000000000000000000001",
    "ciphertext": "rsvpAlpha",
    "control_key_digest": "sha256:3333333333333333333333333333333333333333333333333333333333333333",
    "controller_handle": "alice:acme.example",
    "controller_id": "ak:did_core:webvh:z6mkcontroller",
    "created_at": "2026-05-02T00:00:00.000Z",
    "cutover_at": "2026-08-11T02:00:00.000Z",
    "decision": "reject",
    "describe_digest": "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    "device_authorize_event_id": "ak:event:ARELvWOpF6BRrks3DlbQy-9XIE6aAQQumDQp7fA4ApeM",
    "device_id": "ak:device:0192f3a1-4c2b-7d5e-9f10-2a3b4c5d6e7f",
    "device_key_algorithm": "Ed25519",
    "device_public_key": "did:key:z6MkrJVnaZkeFzdQyRo91my9QRBqmbW4cSUCQY4fVn4N1",
    "device_signing_key": "did:key:z6MkrJVnaZkeFzdQyRo91my9QRBqmbW4cSUCQY4fVn4N1",
    "device_status": "authorized",
    "did": "did:webvh:z6mkfixturesubjectexample:subject.example",
    "did_version_id": "1-fixturegenesis",
    "domain": "arkret-event-v1",
    "dpop_jkt": "RmUcxdimV8pkm16cAFWb1EXxQd9Ri-7Dq6qs1u53gWI",
    "expires_at": "2026-08-16T00:05:00.000Z",
    "extension_id": "ak.extension.calendar.v1",
    "frontier": ["ak:event:AR8bu-n-kOOB3nRUvYuIEglCX5B-JpFaNTex9gxs_cWY"],
    "did": "did:webvh:z6mkfixtureacmeexample:acme.example",
    "genesis_unit_kinds": ["ak.realm.create", "ak.device.authorize"],
    "grace_until": "2026-08-11T03:00:00.000Z",
    "handle": "acme",
    "handover_id": "ak:service_route_handover:019b0000-0000-7000-8000-000000000001",
    "holder_trusted_basis": {
        "leaves": [
            "ak:seal:sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        ]
    },
    "hpke_key": "z6LSfixtureFoundingHpkeKey",
    "identity_creation_lease_id": "genesis-lease-fence-0001",
    "issued_at": "2026-05-01T00:00:00.000Z",
    "issuer": "ak:did_core:webvh:z6mkfixtureacmeexample",
    "issuer_service_id": "ak:did_core:webvh:z6mkfixtureregistryexample",
    "key_scope": "realm_history",
    "kind": "realm",
    "lease_fence": 1,
    "local_admin_subject": "ak:did_core:webvh:z6mkfixtureadminexample",
    "log_head_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "method_history_head": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    "mimi": {"supported": True},
    "nonce": "cmVnaXN0cmF0aW9uLW5vbmNlLTAx",
    "not_before": "2026-04-26T00:00:00.000Z",
    "notice_revision": 0,
    "operation": "security_closure.evaluate",
    "operation_id": "ak.peer.events.command.submit.v1",
    "organization_id": "ak:did_core:webvh:z6mkfixtureacmeexample",
    "origin": "https://alice.example.net",
    "pairing_code": "Q7m2Kf9T3vN8xL4pR6sW1a",
    "pcr_realm_id": "ak:realm:AY4dIxVSke8SdwIRtzd0nLP5OqzL02oENbMkSGDf0lu8",
    "principal_id": "ak:did_core:webvh:z6mkfixture",
    "principal_server_id": "ak:did_core:webvh:z6mkfixtureprincipalserverexample",
    "producer_signing_key": "did:key:z6MkrJVnaZkeFzdQyRo91my9QRBqmbW4cSUCQY4fVn4N1",
    "producer_verification_method": "did:webvh:z6mkfixture:alice.example#ed25519-2026-05-fixture",
    "proof_kind": "resolved_verification_method",
    "proof_purpose": "governance_authorization",
    "provider_service_id": "ak:did_core:webvh:z6mkfixtureprincipalserverexample",
    "publisher_id": "ak:did_core:webvh:z6mkfixturepublisherexample",
    "purpose": "managed_agent_control",
    "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
    "reason": "schema_violation",
    "receiver_service_id": "ak:did_core:webvh:z6mkfixtureprincipalexample",
    "recipient_device_id": "ak:device:01964137-1000-7000-8000-000000000012",
    "recipient_principal_id": "ak:did_core:webvh:z6mkfixture",
    "recipient_service_id": "ak:did_core:webvh:z6mkfixtureprincipalacmeexample",
    "recipient_verification_method": "did:webvh:z6mkfixturepairexample:pair.example#device-1",
    "record_sequence": 8,
    "recovery_recipient_id": "ak:did_core:webvh:z6mkfixturepairexample",
    "recovery_session_id": "ak:recovery_session:019a6aa0-0000-7000-8000-000000000099",
    "reducer_profile": "ak.reducer.core.v1",
    "refresh_after": "2026-08-11T02:00:00.000Z",
    "registration_receipt_id": "ak:organization_registration_receipt:7803fcc35ae0683ce13cbdbfed9b30864e5671f96bf7f7a16f6387d7df321d19",
    "registry_service_id": "ak:did_core:webvh:z6mkfixtureregistryexample",
    "request_id": "polreq_01",
    "resolution_event_ref": "did-webvh-entry-sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    "resource_id": "ak:did_core:webvh:z6mkfixtureacmeexample",
    "room_binding_ref": "ak:event:AR8bu-n-kOOB3nRUvYuIEglCX5B-JpFaNTex9gxs_cWY",
    "schema": "ak.schema.event_batch_receipt.v1",
    "schema_profile_refs": ["ak.profile.core_event_store.v1"],
    "scope": "employment",
    "scopes": ["ak.self.account.read.describe.v1", "ak.self.events.read.scan.v1"],
    "security_class": "high_assurance",
    "sender_actor_id": "ak:did_core:webvh:z6mkfixture",
    "sender_device_id": "ak:device:01964137-1000-7000-8000-000000000011",
    "service_id": "ak:did_core:webvh:z6mkTarget",
    "service_kind": "principal_server",
    "share_kind": "realm_history",
    "snapshot_created_at": "2026-04-26T00:00:00.000Z",
    "snapshot_id": "ak:snapshot:01965000-0000-7000-8000-000000000002",
    "source_service_id": "ak:did_core:webvh:z6mkfixturesourceexample",
    "state": "archived",
    "strand_id": "ak:strand:AQ9vwMrZNs64XfX4CVfhG2FPvja_JU2XLAIWCbvWK5kG",
    "subject": "ak:did_core:webvh:z6mkfixture",
    "subject_id": "ak:did_core:webvh:z6mkfixture",
    "supported_profiles": ["ak.profile.calendar_notification_dispatch.v1"],
    "target": "opaque-bridge-target",
    "trust_domain": "ak:trust_domain:did.webvh.alice.example",
    "verification_key_multibase": "z6MkrJVnaZkeFzdQyRo91my9QRBqmbW4cSUCQY4fVn4N1",
    "verification_method": "did:webvh:z6mkfixture:alice.example#ed25519-2026-05-fixture",
    "version_id": "3-zFixtureVersionThree",
    "witness_did": "did:key:z6MkfixtureWitnessA",
    "witness_evidence": ["did:key:z6MkfixtureWitnessA"],
    "witness_id": "ak:did_core:webvh:z6mkfixturewitnessa",
}

# The audience array form is exercised by every optional audience binding; the
# single-value form by every required one. Both shapes therefore appear in the
# corpus without a family having to choose.
AUDIENCE_SINGLE = "ak:did_core:webvh:z6mkfixturepairexample"

AUDIENCE_ARRAY = [
    "ak:did_core:webvh:z6mkfixturepairexample",
    "ak:did_core:webvh:z6mkfixtureprincipalacmeexample",
]


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64u_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def typed_digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


class SchemaIndex:
    """Minimal resolver over artifacts/schemas for property discovery only."""

    def __init__(self) -> None:
        self._documents: dict[str, Any] = {}

    def document(self, file_name: str) -> Any:
        if file_name not in self._documents:
            self._documents[file_name] = json.loads(
                (SCHEMAS / file_name).read_text(encoding="utf-8")
            )
        return self._documents[file_name]

    def node(self, schema_ref: str) -> tuple[str, Any]:
        file_part, _, fragment = schema_ref.partition("#")
        file_name = file_part.removeprefix("schemas/")
        node: Any = self.document(file_name)
        for part in fragment.strip("/").split("/"):
            if not part:
                continue
            if not isinstance(node, dict):
                return file_name, None
            node = node.get(part.replace("~1", "/"))
            if node is None:
                return file_name, None
        return file_name, node

    def merged(self, file_name: str, node: Any, depth: int = 0) -> tuple[dict[str, Any], list[str]]:
        """Properties and required names reachable from a node without branching."""
        if not isinstance(node, dict) or depth > 4:
            return {}, []
        properties: dict[str, Any] = dict(node.get("properties") or {})
        required: list[str] = [name for name in node.get("required") or [] if isinstance(name, str)]
        reference = node.get("$ref")
        if isinstance(reference, str):
            target = reference if not reference.startswith("#") else f"{file_name}{reference}"
            target_file, target_node = self.node(target.removeprefix("./"))
            child_properties, child_required = self.merged(target_file, target_node, depth + 1)
            properties.update(child_properties)
            required.extend(child_required)
        for branch in node.get("allOf") or []:
            child_properties, child_required = self.merged(file_name, branch, depth + 1)
            properties.update(child_properties)
            required.extend(child_required)
        return properties, required


def body_value(name: str, schema: Any, index: SchemaIndex, file_name: str, depth: int = 0) -> Any:
    """A deterministic body value for one schema property."""
    if isinstance(schema, dict):
        if "const" in schema:
            return schema["const"]
        enum = schema.get("enum")
        if isinstance(enum, list) and enum:
            return enum[0]
        declared = schema.get("type")
        if declared == "integer" and name not in VALUE_TABLE:
            return 1
        if declared == "boolean":
            return False
        if declared == "array" and name not in VALUE_TABLE:
            return []
        reference = schema.get("$ref")
        if isinstance(reference, str) and depth < 2:
            target = reference if not reference.startswith("#") else f"{file_name}{reference}"
            target_file, target_node = index.node(target.removeprefix("./"))
            if target_node is not None:
                return body_value(name, target_node, index, target_file, depth + 1)
    if name in VALUE_TABLE:
        return VALUE_TABLE[name]
    if isinstance(schema, dict) and schema.get("type") == "object":
        return {}
    if name.endswith("_digest"):
        return typed_digest(f"ak.fixture.proof_context_transcript.{name}")
    if name.endswith("_at") or name.endswith("_until"):
        return "2026-05-01T00:00:00.000Z"
    if name.endswith("_url"):
        return "https://fixture.example/"
    return f"{name}-fixture-value"


def projection_for(family: str, index: SchemaIndex, schema_ref: str) -> dict[str, Any]:
    """Resolve how the signed object of one family projects to its digest input."""
    file_name, node = index.node(schema_ref)
    properties, required = index.merged(file_name, node)
    override = PROJECTION_OVERRIDES.get(family)
    if override is not None:
        return {
            "subject_pointer": override["subject_pointer"],
            "removed_members": list(override["removed_members"]),
            "carrier": override["removed_members"][0],
            "file_name": file_name,
            "properties": {} if not override.get("schema_body", True) else properties,
            "required": [] if not override.get("schema_body", True) else required,
            "shared_event_envelope": bool(override.get("shared_event_envelope")),
        }

    carriers = [name for name in PROOF_CARRIER_NAMES if name in properties]
    carrier = carriers[0] if carriers else "proofs"
    others = [name for name in properties if name != carrier]
    if len(properties) == 2 and len(others) == 1 and carrier in properties:
        # {"<core>": {...}, "<carrier>": {...}} wrappers digest the core member,
        # not the wrapper minus the carrier.
        core = others[0]
        core_file, core_node = file_name, properties[core]
        reference = core_node.get("$ref") if isinstance(core_node, dict) else None
        if isinstance(reference, str):
            target = reference if not reference.startswith("#") else f"{file_name}{reference}"
            core_file, core_node = index.node(target.removeprefix("./"))
        core_properties, core_required = index.merged(core_file, core_node)
        if core_properties:
            return {
                "subject_pointer": f"/{core}",
                "removed_members": [],
                "carrier": carrier,
                "file_name": core_file,
                "properties": core_properties,
                "required": core_required,
                "shared_event_envelope": False,
            }
        # The sibling is a scalar selector, not the signed body: the digest still
        # covers the object with the carrier removed.
        return {
            "subject_pointer": "",
            "removed_members": [carrier],
            "carrier": carrier,
            "file_name": file_name,
            "properties": properties,
            "required": required,
            "shared_event_envelope": False,
        }
    return {
        "subject_pointer": "",
        "removed_members": [carrier],
        "carrier": carrier,
        "file_name": file_name,
        "properties": properties,
        "required": required,
        "shared_event_envelope": False,
    }


def shared_event_envelope() -> dict[str, Any]:
    """The published Event KAT envelope, so the two fixtures cannot diverge."""
    data = json.loads(CRYPTO_SIGNATURE_FIXTURE.read_text(encoding="utf-8"))
    for vector in data["vectors"]:
        if vector.get("name") == CRYPTO_SIGNATURE_VECTOR:
            return dict(vector["event_without_proofs"])
    raise SystemExit(f"{CRYPTO_SIGNATURE_VECTOR} is missing from crypto-signature-fixture.json")


def build_case(
    row: dict[str, Any],
    index: SchemaIndex,
    signing_key: Ed25519PrivateKey,
) -> dict[str, Any]:
    context = row["context"]
    family = row["object_family"]
    declared = list(row["binding_fields"])

    required_binding = [name for name in declared if not name.endswith("?")]
    optional_binding = [name[:-1] for name in declared if name.endswith("?")]
    # Even index omitted, odd index present: both the omit branch and the
    # keep branch occur for every family that declares more than one optional,
    # and no family silently skips one of the two.
    present_optional = [name for position, name in enumerate(optional_binding) if position % 2 == 1]
    digest_fields = [name for name in required_binding if name in SELF_DIGEST_FIELDS]
    digest_field = digest_fields[0] if digest_fields else None

    projection = projection_for(family, index, row["schema_ref"])
    subject_pointer = projection["subject_pointer"]
    removed_members = projection["removed_members"]
    carrier = projection["carrier"]
    properties = projection["properties"]
    schema_file = projection["file_name"]

    body: dict[str, Any] = {}
    if digest_field is not None:
        if projection["shared_event_envelope"]:
            # The envelope is the digest subject verbatim; producer_* and
            # accepted_at belong to the admission proof, never to the envelope.
            body = shared_event_envelope()
            body.pop("event_id", None)
            inject_binding_fields = False
        else:
            inject_binding_fields = True
            for name in sorted(set(projection["required"])):
                if (
                    name in removed_members
                    or name == carrier
                    or name in PROOF_SIDE_FIELDS
                    or name == digest_field
                ):
                    continue
                body[name] = body_value(name, properties.get(name), index, schema_file)
        if inject_binding_fields:
            for name in required_binding + present_optional:
                if (
                    name in PROOF_SIDE_FIELDS
                    or name in SELF_DIGEST_FIELDS
                    or name in body
                    or (family == "ingress_receipt" and name == "authority_set_ref")
                ):
                    continue
                body[name] = body_value(name, properties.get(name), index, schema_file)

    if family == "ingress_receipt":
        body.update(
            {
                "receipt_id": "ak:receipt:019c0000-0000-7000-8000-000000000014",
                "event_digest": "sha256:" + "14" * 32,
                "qualified_ingress_did": "did:webvh:z6mkfixture:ingress.example",
                "received_at": "2026-05-02T00:00:00.000Z",
                "ingress_frontier": [
                    "ak:event:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
                ],
            }
        )

    case: dict[str, Any] = {
        "vector_id": f"ak.vector.proof_context.transcript.{family}.v1",
        "context": context,
        "object_family": family,
        "defined_in": row["defined_in"],
        "schema_ref": row["schema_ref"],
        "declared_binding_fields": declared,
        "omitted_optional_binding_fields": [
            name for name in optional_binding if name not in present_optional
        ],
    }
    external_binding_values: dict[str, Any] = {}
    if family == "ingress_receipt":
        authority_set_ref = {
            "authority_set_id": "ak.authority_set.realm_admission.v1",
            "authority_set_digest": "sha256:" + "16" * 32,
        }
        external_binding_values["authority_set_ref"] = authority_set_ref
        case["external_binding_sources"] = {
            "authority_set_ref": {
                "source": "companion_authorization_lease.authority_set_ref",
                "value": authority_set_ref,
            }
        }

    if digest_field is None:
        case["unsigned_projection"] = None
        case["unsigned_projection_absent_because"] = (
            "the registered node is the proof transcript itself; binding_fields declares no "
            "digest of a separately signed object, so there is no unsigned projection to pin"
        )
        case["unsigned_object"] = None
        case["unsigned_jcs"] = None
        case["unsigned_digest"] = None
        case["digest_binding_field"] = None
    else:
        proof_stub: Any = {
            "kind": "detached_jws",
            "verification_method": VALUE_TABLE["verification_method"],
            "created_at": VALUE_TABLE["created_at"],
        }
        signed_object: dict[str, Any]
        if subject_pointer:
            signed_object = {subject_pointer.lstrip("/"): dict(body), carrier: proof_stub}
            unsigned_object = dict(body)
        else:
            signed_object = dict(body)
            for member in removed_members:
                if member == "unsigned":
                    signed_object[member] = {"received_at": "2026-05-02T00:00:01.000Z"}
                elif member == "actor_kind":
                    signed_object[member] = "user"
                elif member == "event_id":
                    signed_object[member] = "ak:event:ARELvWOpF6BRrks3DlbQy-9XIE6aAQQumDQp7fA4ApeM"
                elif member in ("proofs", "signatures"):
                    signed_object[member] = [proof_stub]
                else:
                    signed_object[member] = proof_stub
            unsigned_object = {
                name: value for name, value in signed_object.items() if name not in removed_members
            }
        unsigned_jcs = canonical_json(unsigned_object)
        case["unsigned_projection"] = {
            "subject_pointer": subject_pointer,
            "removed_members": removed_members,
            "removed_member_values": {
                member: signed_object[member]
                for member in removed_members
                if member in signed_object
            },
        }
        case["unsigned_object"] = unsigned_object
        case["unsigned_jcs"] = unsigned_jcs
        case["unsigned_digest"] = typed_digest(unsigned_jcs)
        case["digest_binding_field"] = digest_field

    binding: dict[str, Any] = {"context": context}
    for name in required_binding + present_optional:
        if name == "context":
            continue
        if name == digest_field:
            binding[name] = case["unsigned_digest"]
        elif name == "audience":
            binding[name] = AUDIENCE_SINGLE if name in required_binding else list(AUDIENCE_ARRAY)
        elif name in SELF_DIGEST_FIELDS:
            binding[name] = typed_digest(f"ak.fixture.proof_context_transcript.{family}.{name}")
        elif isinstance(case.get("unsigned_object"), dict) and name in case["unsigned_object"]:
            binding[name] = case["unsigned_object"][name]
        elif name in external_binding_values:
            binding[name] = external_binding_values[name]
        else:
            binding[name] = body_value(name, properties.get(name), index, schema_file)

    binding_jcs = canonical_json(binding)
    header_jcs = canonical_json(PROTECTED_HEADER)
    signing_input = f"{b64u(header_jcs.encode('utf-8'))}.{b64u(binding_jcs.encode('utf-8'))}"
    signature = b64u(signing_key.sign(signing_input.encode("ascii")))

    case["protected_header"] = dict(PROTECTED_HEADER)
    case["protected_header_jcs"] = header_jcs
    case["binding_object"] = binding
    case["binding_jcs"] = binding_jcs
    case["signing_input_ascii"] = signing_input
    case["signature"] = signature
    case["detached_jws"] = f"{b64u(header_jcs.encode('utf-8'))}..{signature}"
    case["expected_result"] = "accept"
    return case


def build_negative_case(
    case: dict[str, Any],
    substituted_context: str,
    substituted_family: str,
    signing_key: Ed25519PrivateKey,
) -> dict[str, Any]:
    binding = dict(case["binding_object"])
    binding["context"] = substituted_context
    binding_jcs = canonical_json(binding)
    header_jcs = case["protected_header_jcs"]
    signing_input = f"{b64u(header_jcs.encode('utf-8'))}.{b64u(binding_jcs.encode('utf-8'))}"
    signature = b64u(signing_key.sign(signing_input.encode("ascii")))
    return {
        "name": f"reject_cross_family_context.{case['object_family']}",
        "vector_id": case["vector_id"],
        "object_family": case["object_family"],
        "registered_context": case["context"],
        "substituted_context": substituted_context,
        "substituted_object_family": substituted_family,
        "signed_binding_jcs": binding_jcs,
        "signature": signature,
        "detached_jws": f"{b64u(header_jcs.encode('utf-8'))}..{signature}",
        "expected_result": "reject",
        "expected_reason": "signature_invalid",
    }


def build_document() -> dict[str, Any]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = registry["contexts"]
    index = SchemaIndex()
    signing_key = Ed25519PrivateKey.from_private_bytes(b64u_decode(TEST_KEY["private_key_seed"]))

    cases = [build_case(row, index, signing_key) for row in rows]
    negative_cases = []
    for position, case in enumerate(cases):
        neighbour = rows[(position + 1) % len(rows)]
        negative_cases.append(
            build_negative_case(case, neighbour["context"], neighbour["object_family"], signing_key)
        )

    return {
        "version": registry["version"],
        "suite": "proof_context_transcripts",
        "runner": {
            "kind": "named_suite",
            "entrypoint": "ak.suite.crypto.proof_context_transcripts.v1",
        },
        "generated_by": "tools/regenerate_proof_context_transcript_fixture.py",
        "generated_from": [
            "spec/v1/artifacts/registry/proof-context-registry.json",
            "spec/v1/zh/conformance/encoding.md",
        ],
        "description": (
            "Byte-level detached-JWS transcript KAT for every row of proof-context-registry.json. "
            "Each case pins the unsigned projection, its JCS bytes and digest, the canonical "
            "binding object built under encoding.md section 6.0.2, the JWS signing input and the "
            "Ed25519 signature over the shared conformance test key. Each negative case replays "
            "the same unsigned body under the adjacent object family's context and MUST be "
            "rejected."
        ),
        "transcript_rules": {
            "unsigned_projection": (
                "Delete the proof carrier member itself, never write null; keep every optional "
                "member that is actually present; never insert a default for an absent one."
            ),
            "optional_binding_field_selection": (
                "Fixture convention only, not a wire rule: optional binding fields at an even "
                "index in binding_fields are omitted, odd index are present, so both branches "
                "occur across the corpus."
            ),
            "audience_shape": (
                "A required audience uses the single-string form; an optional audience uses the "
                "array form, so both encodings carry canonical bytes."
            ),
            "context_placement": (
                "The context constant is a member of the binding object under the key 'context'. "
                "It is never a JWS header parameter and never a wire field of the signed object."
            ),
            "negative_context_selection": (
                "The adjacent object family is the next row of proof-context-registry.json, "
                "wrapping from the last row to the first."
            ),
            "negative_case_reading": (
                "negative_cases[i] reuses the unsigned body and binding of cases[i] and differs "
                "only in the context member. Its signature is a real Ed25519 signature over "
                "signed_binding_jcs, so it verifies under the substituted context and MUST NOT "
                "verify against cases[i].binding_jcs, which is what the receiver rebuilds."
            ),
            "signing_input": (
                "base64url(protected_header_jcs) || '.' || base64url(binding_jcs), ASCII. The "
                "detached JWS payload segment stays empty: base64url(protected_header_jcs) || "
                "'..' || signature."
            ),
        },
        "covers_vectors": [case["vector_id"] for case in cases],
        "test_key": dict(TEST_KEY),
        "cases": cases,
        "negative_cases": negative_cases,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail instead of writing")
    args = parser.parse_args(argv)

    document = build_document()
    serialized = json.dumps(document, ensure_ascii=False, indent=2) + "\n"

    vector_registry = json.loads(VECTOR_REGISTRY.read_text(encoding="utf-8"))
    vectors = vector_registry["vectors"]
    by_id = {row["vector_id"]: row for row in vectors}
    vector_registry_changed = False
    for case in document["cases"]:
        vector_id = case["vector_id"]
        if vector_id in by_id:
            continue
        row = {
            "vector_id": vector_id,
            "status": "active",
            "domain": "proof_context",
            "description": (
                f"Transcript KAT for {case['context']}: the registered unsigned "
                "projection, canonical binding bytes, detached JWS, and cross-family "
                "context replay rejection are pinned byte-for-byte."
            ),
            "covers_proof_contexts": [case["context"]],
            "applies_to_fixtures": ["proof-context-transcript-fixture.json"],
            "source_refs": [
                "spec/v1/artifacts/fixtures/proof-context-transcript-fixture.json"
            ],
        }
        vectors.append(row)
        by_id[vector_id] = row
        vector_registry_changed = True
    sorted_vectors = sorted(vectors, key=lambda row: row["vector_id"])
    if sorted_vectors != vectors:
        vector_registry["vectors"] = sorted_vectors
        vector_registry_changed = True
    vector_registry_serialized = json.dumps(vector_registry, ensure_ascii=False, indent=2) + "\n"

    if args.check:
        stale = False
        if not FIXTURE.is_file() or FIXTURE.read_text(encoding="utf-8") != serialized:
            print("proof context transcript fixture is stale", file=sys.stderr)
            stale = True
        if vector_registry_changed:
            print("proof context transcript vector rows are stale", file=sys.stderr)
            stale = True
        if stale:
            return 1
        print("proof context transcript fixture is current")
        return 0

    FIXTURE.write_text(serialized, encoding="utf-8", newline="\n")
    if vector_registry_changed:
        VECTOR_REGISTRY.write_text(vector_registry_serialized, encoding="utf-8", newline="\n")
    print(
        f"regenerated {len(document['cases'])} transcript case(s) and "
        f"{len(document['negative_cases'])} cross-family reject case(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
