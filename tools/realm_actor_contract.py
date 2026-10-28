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
FAMILIES = ["identity", "control", "manager", "status", "device_generation", "device_authorization", "device_revocation_proposals", "profile", "recovery"]
CONTEXTS = ["ak.realm_actor_" + name + "_signature.v1" for name in ["creation", "control_acceptance", "manager_acceptance", "material", "recovery_acceptance"]]


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
    return {**envelope, "signature": b64(key.sign(message))}, message, key.public_key().public_bytes_raw()


def verify(context, unsigned, signature, public_key):
    if set(signature) != {"context", "signature_algorithm", "verification_method", "signed_digest", "created_at", "signature"}:
        return False
    if signature["context"] != context or signature["signature_algorithm"] != "Ed25519" or signature["signed_digest"] != digest(unsigned):
        return False
    try:
        raw = base64.urlsafe_b64decode(signature["signature"] + "==")
        if len(raw) != 64 or b64(raw) != signature["signature"]:
            return False
        envelope = {k: v for k, v in signature.items() if k != "signature"}
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
    selector = {"kind": "realm_actor_recovery", "actor_id": actor()}
    request = {"actor_id": actor(), "purpose": "current", "request_nonce": "B" * 22, "selectors": [selector]}
    source = committed()
    row = {"selector": selector, "source_stream_ref": source["stream_ref"], "revision": {"commit_id": source["commit_id"], "stream_position": source["stream_position"]}, "value": {"kind": "manager_native", "enabled": True, "pending": None}}
    material = {"realm_id": token("realm"), "actor_id": actor(), "purpose": "current", "request_digest": digest(request), "request_nonce": request["request_nonce"], "requester_actor_id": {"kind": "service", "service_id": service}, "governance_generation": "0", "authority_ref": token("event"), "control_stream_head": {"stream_ref": source["stream_ref"], "commit_id": source["commit_id"], "stream_position": source["stream_position"]}, "issued_at": time, "expires_at": "2026-10-19T00:01:00.000Z", "material": {"entries": [{"status": "present", "current_state": row, "source_ref": source}]}}
    def bind_actor(value):
        if isinstance(value, dict):
            if value.get("kind") == "realm" and "realm_actor_id" in value:
                value["realm_actor_id"]["principal_id"] = vector["projected_core_id"]
            for child in value.values(): bind_actor(child)
        elif isinstance(value, list):
            for child in value: bind_actor(child)
    for host in [create, control, manager, material, request]: bind_actor(host)
    material["request_digest"] = digest(request)
    create["recovery"] = {"kind": "manager_native", "enabled": True}
    manager.update(next_resolution=resolution, method_history_evidence=evidence)
    recovery = {"applet_id": applet, "service_id": service, "payload_without_control_signature": {
        "target_actor_id": create["actor_id"], "request_id": "R" * 22, "manager_ref": committed(), "recovery_ref": committed(),
        "expected_control_revision": revision(), "expected_owner_status_revision": revision(), "expected_governance_status_revision": revision(),
        "expected_device_generation_revision": revision(), "expected_generation": 1, "new_generation": 2, "replaces_recovery_ref": None,
        "next_resolution": resolution, "method_history_evidence": {k: evidence[k] for k in ["log_entries", "witness_records"]}, "next_control_method_kid": method, "expires_at": create["expires_at"]}}
    hosts = [create, control, manager, material, recovery]
    refs = ["realm-actor.schema.json#/$defs/creation_transcript", "realm-actor.schema.json#/$defs/control_acceptance_transcript", "realm-actor.schema.json#/$defs/manager_acceptance_transcript", "realm-actor-material.schema.json#/$defs/realm_actor_material_signature_input"]
    refs.append("realm-actor.schema.json#/$defs/recovery_acceptance_transcript")
    cases = []
    for i, (context, host, schema_ref) in enumerate(zip(CONTEXTS, hosts, refs, strict=True)):
        seed = bytes([i + 1]) * 32
        signature, message, pub = sign(context, host, seed, method if i < 2 else "did:webvh:z6mkfixturegovernor:governor.example#fixture", time)
        cases.append({"context": context, "unsigned_schema_ref": "schemas/" + schema_ref, "test_seed_hex": seed.hex(), "public_key_base64url": b64(pub), "unsigned_projection": host, "canonical_hex": canonical(host).hex(), "signature_input_hex": message.hex(), "signature": signature})
    original = cases[0].pop("unsigned_projection")
    cases[0]["candidate"] = {**original, "control_signature": cases[0]["signature"]}
    from tools.realm_actor_mls_contract import handoff_fixture
    return {  "runner": {"kind": "named_suite", "entrypoint": "ak.suite.realm_actor.contract.v1", "in_tree_checker": "tools/test_realm_actor_contract.py"}, "covers_vectors": ["ak.vector.realm_actor.contract.v1"], "generated_by": "tools/regenerate_realm_actor_fixture.py", "description": "Real deterministic Ed25519 transcript KATs and schema-shaped hosts. Signature hosts do not claim native admission. Separate native_recovery vectors verify constructed SCID, predecessor hashes, pre-rotation, W3C eddsa-jcs-2022 proofs and witness signatures; no live resolver, governance trust or production SUT claim. Seeds are public test-only material. MLS claim handoff hosts verify distinct real signers with synthetic ledger digests, not an actual authority import.", "cases": cases, "device_possession": device_possession_fixture(), "native_recovery": native_recovery_fixture(), "mls_claim_handoff": handoff_fixture()}


def device_possession_fixture():
    original = json.loads((ART / "fixtures/pcr-genesis-fixture.json").read_text(encoding="utf-8"))["device_possession"]["canonical_object"]
    names = "device_id device_public_key_did hpke_key algorithms device_key_algorithm authorized_by authorization_binding_kind authorized_generation_ref not_before expires_at scopes".split()
    value = {"actor_id": actor(), **{k: original[k] for k in names}, "applet_id": "ak:applet:0195be74-0000-7000-8000-000000000001", "expected_control_revision": revision(), "expected_device_revision": None}
    value.update(authorized_by=actor()["realm_actor_id"]["principal_id"], authorization_binding_kind="realm_managed_delegation", expires_at="2026-10-20T00:00:00.000Z", scopes=[{"effective_scope": {"kind":"realm", "realm_id":token("realm")}, "actions":["ak.message.create"]}])
    context = "ak.device_authorize_realm_actor_possession_proof.v1"
    message = (context + "\n").encode() + canonical(value)
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    return {"context":context, "transcript":value, "signature_input_hex":message.hex(), "public_key_base64url":b64(key.public_key().public_bytes_raw()), "signature_b64u":b64(key.sign(message))}


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
        self.rows[key] = {"owner": "active", "governance": "active", "generation": 1, "control": "old", "control_revision": self.head, "manager_revision": self.head, "manager_key": "old", "manager": "old-service", "devices": {}, "revoked": set(), "recovery_enabled": True, "recovery_revision": self.head, "pending": None, "cleanup": set()}
        result = ("accepted", self.head)
        self.intents[request_id] = (candidate_digest, result)
        return result

    def business(self, subject, device, *, installed=True, grant=True):
        row = self.rows.get(canonical(subject))
        return bool(row and not row["pending"] and not row["cleanup"] and row["owner"] == row["governance"] == "active" and installed and grant and device not in row["revoked"] and row["devices"].get(device) == row["generation"])

    def rotate(self, subject, expected, new_key, *, old_proof, new_pop, native_continuity):
        row = self.rows[canonical(subject)]
        if row["pending"] or "retired" in (row["owner"], row["governance"]) or expected != row["control_revision"] or not all([old_proof, new_pop, native_continuity]):
            return False
        self.head += 1
        row.update(control=new_key, control_revision=self.head)
        return True

    def transfer(self, subject, expected, *, controller, governance, acceptance, native_transfer=False):
        row = self.rows[canonical(subject)]
        if row["pending"] or row["owner"] != "paused" or row["governance"] == "retired" or row["control"] == row["manager_key"] or row["control_revision"] <= row["manager_revision"] or expected != (row["manager_revision"], row["control_revision"], row["generation"]) or not all([controller, governance, acceptance, native_transfer]):
            return False
        self.head += 1
        row.update(manager="new-service", manager_revision=self.head, control_revision=self.head, manager_key=row["control"], generation=row["generation"] + 1)
        return True

    def recovery_begin(self, subject, request, expected, *, manager, authenticated=True, native_plan=True, pop=True, expired=False, replaces=None, crash=False, intent_digest="fixture-intent"):
        row = self.rows.get(canonical(subject))
        if not row or not authenticated or manager != row["manager"]:
            return "denied"
        ledger_key = (canonical(subject), row["manager_revision"], request)
        ledger = self.private_inventory["outcomes"]
        if ledger_key in ledger:
            return ("accepted", ledger[ledger_key]["begin"]) if ledger[ledger_key]["digest"] == intent_digest else "conflict"
        if not row["recovery_enabled"] or "retired" in (row["owner"], row["governance"]) or expired or not native_plan or not pop:
            return "denied"
        if expected != (row["recovery_revision"], row["control_revision"], row["generation"]):
            return "conflict"
        if replaces != (row["pending"]["begin"] if row["pending"] else None):
            return "conflict"
        if crash:
            return "aborted"
        if row["pending"]:
            ledger[row["pending"]["ledger_key"]]["state"] = "superseded"
        self.head += 1
        row.update(owner="paused", generation=row["generation"] + 1, recovery_revision=self.head)
        row["cleanup"].update(row["devices"])
        row["pending"] = {"begin": self.head, "request": request, "ledger_key": ledger_key, "manager_revision": row["manager_revision"], "control_revision": row["control_revision"], "generation": row["generation"]}
        ledger[ledger_key] = {"begin": self.head, "state": "pending", "digest": intent_digest}
        return ("accepted", self.head)

    def recovery_finish(self, subject, begin, *, manager, authenticated=True, published=True, matches=True, witness=True, crash=False):
        row = self.rows[canonical(subject)]
        pending = row["pending"]
        if not authenticated or manager != row["manager"] or not row["recovery_enabled"] or "retired" in (row["owner"], row["governance"]):
            return False
        if not pending or begin != pending["begin"] or pending["manager_revision"] != row["manager_revision"] or pending["control_revision"] != row["control_revision"] or pending["generation"] != row["generation"]:
            return False
        if not all([published, matches, witness]) or crash:
            return False
        self.head += 1
        row.update(control="recovered", control_revision=self.head, recovery_revision=self.head, pending=None)
        self.private_inventory["outcomes"][pending["ledger_key"]].update(state="completed", terminal=self.head)
        return True

    def recovery_policy(self, subject, enabled, *, expected, allowed=True, retire=False):
        row = self.rows[canonical(subject)]
        if not allowed or expected != row["recovery_revision"] or (enabled == row["recovery_enabled"] and not retire):
            return False
        self.head += 1
        if row["pending"]:
            self.private_inventory["outcomes"][row["pending"]["ledger_key"]].update(state="cancelled", terminal=self.head)
        row.update(recovery_enabled=enabled, recovery_revision=self.head, pending=None)
        if retire:
            row["governance"] = "retired"
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


B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58(raw):
    number, text = int.from_bytes(raw, "big"), ""
    while number:
        number, remainder = divmod(number, 58)
        text = B58[remainder] + text
    return "1" * (len(raw) - len(raw.lstrip(b"\0"))) + text


def unbase58(text):
    number = 0
    for char in text:
        number = number * 58 + B58.index(char)
    return b"\0" * (len(text) - len(text.lstrip("1"))) + number.to_bytes((number.bit_length() + 7) // 8, "big")


def multihash(raw):
    return base58(b"\x12\x20" + hashlib.sha256(raw).digest())


def multikey(key):
    return "z" + base58(b"\xed\x01" + key.public_key().public_bytes_raw())


def native_sign(document, key, created):
    public = multikey(key)
    options = {"type": "DataIntegrityProof", "cryptosuite": "eddsa-jcs-2022", "created": created, "verificationMethod": f"did:key:{public}#{public}", "proofPurpose": "assertionMethod"}
    raw = hashlib.sha256(canonical(options)).digest() + hashlib.sha256(canonical(document)).digest()
    return {**options, "proofValue": "z" + base58(key.sign(raw))}


def native_verify(document, proof, public):
    options = {k: v for k, v in proof.items() if k != "proofValue"}
    if proof.get("type") != "DataIntegrityProof" or proof.get("cryptosuite") != "eddsa-jcs-2022" or proof.get("proofPurpose") != "assertionMethod" or proof.get("verificationMethod") != f"did:key:{public}#{public}":
        raise ValueError("invalid native proof authority")
    raw_key = unbase58(public[1:])
    if public[:1] != "z" or raw_key[:2] != b"\xed\x01" or len(raw_key) != 34 or proof["proofValue"][:1] != "z":
        raise ValueError("invalid multibase key or signature")
    data = hashlib.sha256(canonical(options)).digest() + hashlib.sha256(canonical(document)).digest()
    Ed25519PublicKey.from_public_bytes(raw_key[2:]).verify(unbase58(proof["proofValue"][1:]), data)


def native_recovery_fixture(*, relocate=False, portable=True):
    """Construct a bounded native chain; public test seeds, no live resolver."""
    roots = [Ed25519PrivateKey.from_private_bytes(bytes([70 + i]) * 32) for i in range(5)]
    controls = [Ed25519PrivateKey.from_private_bytes(bytes([80 + i]) * 32) for i in range(3)]
    witness = Ed25519PrivateKey.from_private_bytes(bytes([90]) * 32)
    placeholder = "did:webvh:{SCID}:applet.example:actors:bot"
    document = lambda did, i: {"@context": ["https://www.w3.org/ns/did/v1"], "id": did, "verificationMethod": [{"id": did + f"#control-{i}", "controller": did, "type": "Multikey", "publicKeyMultibase": multikey(controls[i])}], "authentication": [did + f"#control-{i}"]}
    first = {"versionId": "{SCID}", "versionTime": "2026-10-20T00:00:00Z", "parameters": {"method": "did:webvh:1.0", "scid": "{SCID}", "portable": portable, "updateKeys": [multikey(roots[0])], "nextKeyHashes": [multihash(multikey(roots[1]).encode())], "witness": {"threshold": 1, "witnesses": [{"id": "did:key:" + multikey(witness)}]}}, "state": document(placeholder, 0)}
    scid = multihash(canonical(first))
    first = json.loads(json.dumps(first).replace("{SCID}", scid))
    did = placeholder.replace("{SCID}", scid)
    entries, witnesses = [], []
    previous = scid
    for i in range(4):
        entry = first if i == 0 else {"versionId": previous, "versionTime": f"2026-10-20T00:0{i}:00Z", "parameters": {"updateKeys": [multikey(roots[i])], "nextKeyHashes": [multihash(multikey(roots[i + 1]).encode())]}, "state": document(did.replace(":applet.example:", ":hosting.example:") if relocate and i >= 2 else did, min(i, 2))}
        entry["versionId"] = f"{i+1}-" + multihash(canonical(entry))
        entry["proof"] = [native_sign(entry, roots[i], entry["versionTime"])]
        entries.append(entry)
        witnesses.append({"versionId": entry["versionId"], "proof": [native_sign({"versionId": entry["versionId"]}, witness, entry["versionTime"])]})
        previous = entry["versionId"]
    return {"description": "Native inception, lost-control reset, manager transition and new-manager successor. W3C eddsa-jcs-2022 proofs sign the final unsigned log entry; entry hashes separately replace versionId with its predecessor. Each entry consumes a fresh committed key. This bounded reference verifier is not a network resolver or production admission.", "root_test_seeds_hex": [(bytes([70+i])*32).hex() for i in range(5)], "control_test_seeds_hex": [(bytes([80+i])*32).hex() for i in range(3)], "witness_test_seed_hex": (bytes([90])*32).hex(), "did": did, "scid": scid, "log_entries": entries, "witness_records": witnesses}


def verify_native_recovery(vector, accepted_prefix=None, require_witness=True):
    """Independently verify the fixture's native cryptographic relations."""
    entries = vector["log_entries"]
    if not entries or len(entries) > 4096 or len(canonical(entries)) > 1048576:
        raise ValueError("invalid history size")
    if accepted_prefix is not None and entries[:len(accepted_prefix)] != accepted_prefix:
        raise ValueError("accepted history rollback or sibling")
    scid = entries[0]["parameters"]["scid"]
    initial = {k: v for k, v in entries[0].items() if k != "proof"}
    initial["versionId"] = scid
    preliminary = json.loads(json.dumps(initial).replace(scid, "{SCID}"))
    if multihash(canonical(preliminary)) != scid or vector["scid"] != scid:
        raise ValueError("invalid SCID")
    previous, next_hashes, spent = scid, None, set()
    portable = entries[0]["parameters"].get("portable", False)
    previous_did = vector["did"]
    witness_id = entries[0]["parameters"]["witness"]["witnesses"][0]["id"]
    for i, entry in enumerate(entries):
        unsigned = {k: v for k, v in entry.items() if k != "proof"}
        preimage = {**unsigned, "versionId": previous}
        if entry["versionId"] != f"{i+1}-" + multihash(canonical(preimage)):
            raise ValueError("invalid entry hash")
        parameters = entry["parameters"]
        if len(parameters["updateKeys"]) != 1 or len(parameters["nextKeyHashes"]) != 1:
            raise ValueError("invalid recovery key profile")
        key = parameters["updateKeys"][0]
        if key in spent or (next_hashes is not None and multihash(key.encode()) not in next_hashes):
            raise ValueError("invalid pre-rotation")
        if any(multihash(k.encode()) == parameters["nextKeyHashes"][0] for k in spent | {key}):
            raise ValueError("spent next key")
        state = entry["state"]
        if not state["id"].startswith(f"did:webvh:{scid}:") or (i == 0 and state["id"] != vector["did"]):
            raise ValueError("DID/core/locator mismatch")
        if state["id"] != previous_did and not portable:
            raise ValueError("relocation lacks predecessor portability")
        portable = parameters.get("portable", portable)
        if portable is not True:
            raise ValueError("managed DID must retain portability")
        previous_did = state["id"]
        control = state["verificationMethod"][0]
        if control["controller"] != state["id"] or control["id"] not in state["authentication"] or control["publicKeyMultibase"] == key or multihash(control["publicKeyMultibase"].encode()) in parameters["nextKeyHashes"]:
            raise ValueError("control/update key confusion")
        native_verify(unsigned, entry["proof"][0], key)
        if require_witness:
            records = [x for x in vector["witness_records"] if x["versionId"] == entry["versionId"]]
            if len(records) != 1:
                raise ValueError("missing/duplicate witness")
            native_verify({"versionId": entry["versionId"]}, records[0]["proof"][0], witness_id.removeprefix("did:key:"))
        spent.add(key)
        previous, next_hashes = entry["versionId"], parameters["nextKeyHashes"]
    return {"did": previous_did, "method_history_head": digest(entries[-1]), "version_id": previous}
