"""Executable Realm actor contract helpers; not a production implementation."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "spec/v1/artifacts"
FAMILIES = ["identity", "control", "manager", "status", "device_generation", "device_authorization", "device_revocation_proposals", "profile"]
CONTEXTS = ["ak.realm_actor_" + name + "_signature.v1" for name in ["creation", "control_acceptance", "manager_acceptance", "material"]]


def canonical(value):
    """JCS for these fixtures' restricted integer/string/boolean domain."""
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def token(kind, byte=1):
    return "ak:" + kind + ":" + b64(bytes([1]) + bytes([byte]) * 32)


def actor(byte=1):
    return {"kind": "realm", "realm_actor_id": {"realm_id": token("realm", byte), "principal_id": "ak:did_core:webvh:zRealmActorFixture"}}


def committed(byte=2, position=0):
    return {"event_id": token("event", byte), "commit_id": token("realm_commit", byte + 1), "stream_ref": {"kind": "realm_control", "realm_id": token("realm")}, "stream_position": position}


def revision(byte=3, position=0):
    return {"commit_id": token("realm_commit", byte), "stream_position": position}


def sign(context, unsigned, seed, method, created_at):
    envelope = {"context": context, "signature_algorithm": "Ed25519", "verification_method": method, "signed_digest": digest(unsigned), "created_at": created_at}
    message = (context + "\n").encode() + canonical(envelope)
    key = Ed25519PrivateKey.from_private_bytes(seed)
    return {**envelope, "sig": b64(key.sign(message))}, message, key.public_key().public_bytes_raw()


def verify(context, unsigned, signature, public_key):
    if set(signature) != {"context", "signature_algorithm", "verification_method", "signed_digest", "created_at", "sig"}:
        return False
    if signature["context"] != context or signature["signature_algorithm"] != "Ed25519" or signature["signed_digest"] != digest(unsigned):
        return False
    try:
        raw = base64.urlsafe_b64decode(signature["sig"] + "==")
        if len(raw) != 64 or b64(raw) != signature["sig"]:
            return False
        envelope = {k: v for k, v in signature.items() if k != "sig"}
        Ed25519PublicKey.from_public_bytes(public_key).verify(raw, (context + "\n").encode() + canonical(envelope))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def signature_fixture():
    time = "2026-10-19T00:00:00.000Z"
    vector = next(x for x in json.loads((ART / "fixtures/resolution-commitment-fixture.json").read_text(encoding="utf-8"))["vectors"] if x["evidence_id"] == "agent_inception")
    resolution = vector["commitment"]
    did = resolution["did"]
    method = did + "#update-key-1"
    evidence = {"evidence_kind": "webvh_log", "boundary": {"from_method_history_head": resolution["method_history_head"], "from_version_id": resolution["version_id"], "to_method_history_head": resolution["method_history_head"], "to_version_id": resolution["version_id"]}, "evidence": {"kind": "ak.did.binding_evidence.v1", "method": "webvh", "document_digest": "sha256:" + "1" * 64, "method_proofs": []}, "log_entries": [vector["verified_entry"]], "witness_records": []}
    applet = "ak:applet:0195be74-0000-7000-8000-000000000001"
    service = "ak:did_core:webvh:zAppletFixture"
    create = {"schema": "ak.schema.realm_actor_create.v1", "actor_id": actor(), "applet_id": applet, "service_id": service, "actor_role": "bot", "request_id": "A" * 22, "creation_scope": {"kind": "realm", "realm_id": token("realm")}, "registration_ref": token("event", 5), "creation_authorization_ref": token("grant", 6), "initial_resolution": resolution, "method_history_evidence": evidence, "control_method_kid": method, "expires_at": "2026-10-19T00:01:00.000Z"}
    control = {"actor_id": actor(), "expected_revision": revision(), "next_resolution": resolution, "method_history_evidence": evidence, "next_control_method_kid": method}
    manager = {"actor_id": actor(), "applet_id": applet, "expected_manager_revision": revision(), "expected_control_revision": revision(7, 4), "expected_device_generation_revision": revision(), "expected_generation": 1, "new_generation": 2, "new_service_id": "ak:did_core:webvh:zNewAppletFixture", "new_registration_ref": token("event", 8), "management_authorization_ref": token("grant", 9)}
    selector = {"kind": "realm_actor_device_authorization", "actor_id": actor(), "device_id": "ak:device:0195be74-0000-7000-8000-000000000001"}
    request = {"actor_id": actor(), "purpose": "current", "request_nonce": "B" * 22, "selectors": [selector]}
    material = {"realm_id": token("realm"), "actor_id": actor(), "purpose": "current", "request_digest": digest(request), "request_nonce": request["request_nonce"], "requester_actor_id": {"kind": "service", "service_id": service}, "governance_generation": 0, "authority_ref": token("event"), "control_stream_head": {"stream_ref": committed()["stream_ref"], "commit_id": committed()["commit_id"], "stream_position": 0}, "issued_at": time, "expires_at": "2026-10-19T00:01:00.000Z", "result": {"entries": [{"status": "never_written", "selector": selector}]}}
    def bind_actor(value):
        if isinstance(value, dict):
            if value.get("kind") == "realm" and "realm_actor_id" in value:
                value["realm_actor_id"]["principal_id"] = vector["projected_core_id"]
            for child in value.values(): bind_actor(child)
        elif isinstance(value, list):
            for child in value: bind_actor(child)
    for host in [create, control, manager, material, request]: bind_actor(host)
    material["request_digest"] = digest(request)
    hosts = [create, control, manager, material]
    refs = ["realm-actor.schema.json#/$defs/creation_transcript", "realm-actor.schema.json#/$defs/control_acceptance_transcript", "realm-actor.schema.json#/$defs/manager_acceptance_transcript", "realm-actor-material.schema.json#/$defs/unsigned_outcome"]
    cases = []
    for i, (context, host, schema_ref) in enumerate(zip(CONTEXTS, hosts, refs, strict=True)):
        seed = bytes([i + 1]) * 32
        signature, message, pub = sign(context, host, seed, method if i < 2 else "did:webvh:z6mkfixturegovernor:governor.example#fixture", time)
        cases.append({"context": context, "unsigned_schema_ref": "schemas/" + schema_ref, "test_seed_hex": seed.hex(), "public_key_b64u": b64(pub), "unsigned_projection": host, "canonical_hex": canonical(host).hex(), "signature_input_hex": message.hex(), "signature": signature})
    original = cases[0].pop("unsigned_projection")
    cases[0]["candidate"] = {**original, "control_signature": cases[0]["signature"]}
    return {"version": "2026-10-19.1", "suite": "realm_actor_signature_transcripts", "fixture_kind": "semantic", "runner": {"kind": "named_suite", "entrypoint": "ak.suite.realm_actor.contract.v1", "in_tree_checker": "tools/test_realm_actor_contract.py"}, "covers_vectors": ["ak.vector.realm_actor.contract.v1"], "generated_by": "tools/regenerate_realm_actor_fixture.py", "description": "Real deterministic Ed25519 transcript KATs and schema-shaped hosts. The resolution is recomputable from the registered adapter fixture; these signature hosts do not claim native WebVH admission, governance trust or a production SUT. Seeds are public test-only material.", "cases": cases, "device_possession": device_possession_fixture()}


def device_possession_fixture():
    original = json.loads((ART / "fixtures/pcr-genesis-fixture.json").read_text(encoding="utf-8"))["device_possession"]["canonical_object"]
    names = "device_id device_public_key_did hpke_key algorithms device_key_algorithm authorized_by authorization_binding_kind authorized_generation_ref not_before expires_at scopes".split()
    value = {"actor_id": actor(), **{k: original[k] for k in names}, "applet_id": "ak:applet:0195be74-0000-7000-8000-000000000001", "expected_control_revision": revision(), "expected_device_revision": None}
    value.update(authorized_by=actor()["realm_actor_id"]["principal_id"], authorization_binding_kind="realm_managed_delegation", expires_at="2026-10-20T00:00:00.000Z", scopes=[{"effective_scope": {"kind":"realm", "realm_id":token("realm")}, "actions":["ak.message.create"]}])
    context = "ak.device_authorize_realm_actor_possession_proof.v1"
    message = (context + "\n").encode() + canonical(value)
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    return {"context":context, "transcript":value, "signature_input_hex":message.hex(), "public_key_b64u":b64(key.public_key().public_bytes_raw()), "signature_b64u":b64(key.sign(message))}


class ControlModel:
    """Reference acceptance state over independently verified authority inputs."""
    def __init__(self, realm_id):
        self.realm_id = realm_id
        self.head = None
        self.rows = {}
        self.intents = {}
        self.tenure = 0
        self.private_inventory = {name: {} for name in ["events", "commits", "current", "did_evidence", "signer_facts", "security_intents", "quota", "ghost_tuples", "nonces", "outcomes", "device_queues", "mls_claims", "cursors"]}

    def create(self, subject, request_id, candidate_digest, *, verified, allowed, expired=False, applet_id="fixture-applet"):
        key = canonical(subject)
        if not verified or subject.get("kind") != "realm" or subject["realm_actor_id"]["realm_id"] != self.realm_id:
            return "rejected"
        request_id = (applet_id, request_id)
        if request_id in self.intents:
            previous = self.intents[request_id]
            return previous[1] if previous[0] == candidate_digest else "conflict"
        if not verified or not allowed or expired or subject.get("kind") != "realm" or subject["realm_actor_id"]["realm_id"] != self.realm_id or key in self.rows:
            return "rejected"
        self.head = 0 if self.head is None else self.head + 1
        self.rows[key] = {"owner": "active", "governance": "active", "generation": 1, "control": "old", "control_revision": self.head, "manager_revision": self.head, "manager_key": "old", "manager": "old-service", "devices": {}, "revoked": set()}
        result = ("accepted", self.head)
        self.intents[request_id] = (candidate_digest, result)
        return result

    def business(self, subject, device, *, installed=True, grant=True):
        row = self.rows.get(canonical(subject))
        return bool(row and row["owner"] == row["governance"] == "active" and installed and grant and device not in row["revoked"] and row["devices"].get(device) == row["generation"])

    def rotate(self, subject, expected, new_key, *, old_proof, new_pop, native_continuity):
        row = self.rows[canonical(subject)]
        if "retired" in (row["owner"], row["governance"]) or expected != row["control_revision"] or not all([old_proof, new_pop, native_continuity]):
            return False
        self.head += 1
        row.update(control=new_key, control_revision=self.head)
        return True

    def transfer(self, subject, expected, *, controller, governance, acceptance):
        row = self.rows[canonical(subject)]
        if row["owner"] != "paused" or row["governance"] == "retired" or row["control"] == row["manager_key"] or row["control_revision"] <= row["manager_revision"] or expected != (row["manager_revision"], row["control_revision"], row["generation"]) or not all([controller, governance, acceptance]):
            return False
        self.head += 1
        row.update(manager="new-service", manager_revision=self.head, manager_key=row["control"], generation=row["generation"] + 1)
        return True

    def export(self):
        return copy.deepcopy(self.__dict__)

    @classmethod
    def handoff(cls, export, actual_import, required_private_sections):
        if not required_private_sections or export != actual_import:
            raise ValueError("incomplete actual import")
        model = cls(export["realm_id"])
        model.__dict__ = copy.deepcopy(actual_import)
        model.tenure += 1
        return model
