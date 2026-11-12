"""Native Realm Actor content-backup reference checks.

These checks never establish native PG/HTTP durability.

All state inputs below are independently supplied accepted-cut material. The
reference signatures bind those inputs; they do not create native authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey

from tools.content_history import b64, unb64, hpke_seal, hpke_open, content_root, root_ref, verify_root_index
from tools.realm_actor_contract import (canonical, digest, token, committed, native_recovery_fixture,
    verify_native_recovery, base58, unbase58, sign, verify)

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "spec/v1/artifacts"
SUITE = "ak.hpke_x25519_aead_chacha20poly1305.v1"
PUT = "ak.self.keys.backups.resource.replace.v1"
NATIVE_BACKUP_OPERATIONS = [PUT, "ak.self.keys.backups.read.list.v1",
    "ak.self.keys.backups.command.issue_unlock_challenge.v1", "ak.self.keys.backups.command.unlock.v1"]
NATIVE_AUTH = {"kind", "manager_ref", "recovery_ref", "recipient_ref", "device_generation"}
NATIVE_FORBIDDEN = {"source_commit_ref", "recovery_policy_ref", "custodian_actor_id", "custody_authorization_ref", "kdf", "expires_at"}


def unsigned_envelope(envelope):
    result = copy.deepcopy(envelope)
    result["signature_proof"].pop("signature", None)
    return result


def envelope_bytes(envelope):
    return canonical(unsigned_envelope(envelope))


def backup_aad(envelope):
    """Existing base plus native auth_binding only; Account/Agent bytes stay unchanged."""
    value = {"schema": "ak.schema.key_backup.v1", **{name: envelope[name] for name in ("actor_id", "backup_kind", "backup_version", "created_at")}}
    value.update(device_id=envelope.get("device_id"),
        item_kinds=sorted({item["item_kind"] for item in envelope["contents"]}, key=lambda x: x.encode()),
        recipient_method=envelope["encryption"]["recipient_method"])
    if "recipient_key_ref" in envelope["encryption"]:
        value["recipient_key_ref"] = envelope["encryption"]["recipient_key_ref"]
    if envelope["actor_id"].get("kind") == "realm":
        value["auth_binding"] = envelope["auth_binding"]
    for name, extension in envelope["domain_separation"].get("aead_aad_extensions", {}).items():
        if not name.startswith("x_") or name in value:
            raise ValueError("invalid AAD extension")
        value[name] = extension
    return canonical(value)


def backup_info(envelope):
    return canonical({name: envelope[name] for name in ("backup_id", "series_id", "series_sequence", "actor_id", "backup_kind", "backup_version", "created_at")})


def check_recipient(descriptor, history, declaration_index):
    """Resolve the exact original native declaration, never today's DID document."""
    if set(descriptor) != {"key_agreement_ref", "hpke_suite", "public_key_base64url"} or descriptor["hpke_suite"] != SUITE:
        raise ValueError("invalid native recipient descriptor")
    verify_native_recovery(history)
    if not 0 <= declaration_index < len(history["log_entries"]):
        raise ValueError("missing original declaration history")
    doc = history["log_entries"][declaration_index]["state"]
    method = descriptor["key_agreement_ref"]
    if method not in doc.get("keyAgreement", []):
        raise ValueError("recipient is not an original keyAgreement method")
    methods = [row for row in doc["verificationMethod"] if row["id"] == method]
    if len(methods) != 1 or methods[0]["controller"] != doc["id"]:
        raise ValueError("ambiguous recipient controller")
    encoded = methods[0]["publicKeyMultibase"]
    raw = unbase58(encoded[1:]) if encoded.startswith("z") else b""
    public = unb64(descriptor["public_key_base64url"])
    if len(public) != 32 or raw != b"\xec\x01" + public or "z" + base58(raw) != encoded:
        raise ValueError("recipient differs from the exact X25519 method")
    X25519PrivateKey.from_private_bytes(bytes([101]) * 32).exchange(X25519PublicKey.from_public_bytes(public))
    return public


def validate_native_shape(envelope):
    actor = envelope.get("actor_id", {})
    encryption = envelope.get("encryption", {})
    proof = envelope.get("signature_proof", {})
    auth = envelope.get("auth_binding", {})
    if (actor.get("kind") != "realm" or set(actor) != {"kind", "realm_actor_id"}
            or set(actor["realm_actor_id"]) != {"realm_id", "principal_id"}
            or encryption.get("recipient_method") != "realm_actor_recovery"
            or encryption.get("hpke_suite") != SUITE
            or set(encryption) != {"recipient_method", "recipient_key_ref", "hpke_suite", "aead"}
            or set(encryption["aead"]) != {"name", "enc"}
            or encryption["aead"]["name"] != "chacha20_poly1305"
            or NATIVE_FORBIDDEN.intersection(envelope)
            or set(auth) != NATIVE_AUTH or auth.get("kind") != "realm_device"
            or type(auth.get("device_generation")) is not int or auth["device_generation"] < 1
            or set(proof) != {"device_id", "verification_method", "signature_algorithm", "device_authorize_event_id", "signature"}
            or proof.get("device_id") != envelope.get("device_id")
            or proof.get("signature_algorithm") != "Ed25519"
            or envelope.get("backup_kind") != "secret_storage"
            or len(envelope.get("contents", [])) != 1
            or envelope["contents"][0].get("item_kind") != "content_epoch_root"):
        raise ValueError("not a closed native root-only backup")
    expected_ref = {"event_id", "commit_id", "stream_ref", "stream_position"}
    for name in ["manager_ref", "recovery_ref", "recipient_ref"]:
        reference = auth[name]
        if (not isinstance(reference, dict) or set(reference) != expected_ref
                or type(reference["stream_position"]) is not int or reference["stream_position"] < 0
                or reference["stream_ref"] != {"kind": "realm_control", "realm_id": actor["realm_actor_id"]["realm_id"]}
                or not isinstance(reference["event_id"], str) or not reference["event_id"].startswith("ak:event:")
                or not isinstance(reference["commit_id"], str) or not reference["commit_id"].startswith("ak:realm_commit:")):
            raise ValueError("native auth source is not an exact earlier realm-control original")
    scope = envelope["contents"][0]["root_context"]["effective_scope"]
    if (scope.get("kind") not in {"realm", "circle"}
            or set(scope) != ({"kind", "realm_id"} if scope["kind"] == "realm" else {"kind", "realm_id", "circle_id"})
            or scope["realm_id"] != actor["realm_actor_id"]["realm_id"]):
        raise ValueError("root belongs to another exact native scope")
    if not isinstance(envelope["series_sequence"], int) or isinstance(envelope["series_sequence"], bool) or envelope["series_sequence"] < 0:
        raise ValueError("invalid packet sequence")
    if (envelope["series_sequence"] == 0) != ("supersedes_id" not in envelope and "supersedes_digest" not in envelope):
        raise ValueError("missing packet predecessor")


def sign_envelope(envelope, seed):
    envelope["signature_proof"].pop("signature", None)
    envelope["signature_proof"]["signature"] = b64(Ed25519PrivateKey.from_private_bytes(seed).sign(envelope_bytes(envelope)))
    return envelope


def seal(envelope, plaintext, recipient_public, ephemeral_seed, signer_seed):
    envelope = copy.deepcopy(envelope)
    enc = X25519PrivateKey.from_private_bytes(ephemeral_seed).public_key().public_bytes_raw()
    envelope["encryption"]["aead"]["enc"] = b64(enc)
    sealed = hpke_seal(ephemeral_seed, recipient_public, backup_info(envelope), canonical(plaintext), backup_aad(envelope))
    envelope["ciphertext"] = b64(sealed[32:])
    envelope["ciphertext_digest"] = "sha256:" + hashlib.sha256(sealed[32:]).hexdigest()
    return sign_envelope(envelope, signer_seed)


def open_backup(envelope, recipient_private, author_public):
    validate_native_shape(envelope)
    signature = unb64(envelope["signature_proof"]["signature"])
    Ed25519PublicKey.from_public_bytes(author_public).verify(signature, envelope_bytes(envelope))
    ciphertext = unb64(envelope["ciphertext"])
    if "sha256:" + hashlib.sha256(ciphertext).hexdigest() != envelope["ciphertext_digest"]:
        raise ValueError("ciphertext digest mismatch")
    plain = hpke_open(recipient_private, unb64(envelope["encryption"]["aead"]["enc"]) + ciphertext,
        backup_info(envelope), backup_aad(envelope))
    value = json.loads(plain)
    verify_root_index(envelope, value)
    return value


def series_key(actor, scope, kind="secret_storage"):
    if (actor.get("kind") != "realm" or scope.get("kind") not in {"realm", "circle"}
            or actor["realm_actor_id"]["realm_id"] != scope.get("realm_id") or kind != "secret_storage"):
        raise ValueError("invalid exact native series scope")
    return canonical([actor, scope, kind])


def series_bytes(record):
    value = copy.deepcopy(record)
    value["signature_proof"].pop("signature", None)
    return canonical(value)


def http_base(method, uri, headers, parameters):
    """RFC 9421 covered lines for the existing native Device body operation."""
    from urllib.parse import urlsplit
    authority = urlsplit(uri).netloc
    components = ["@method", "@target-uri", "@authority", "arkret-operation", "arkret-managed-device", "destination-service-id", "content-digest", "idempotency-key"]
    values = {"@method": method, "@target-uri": uri, "@authority": authority, **headers}
    lines = ['"' + component + '": ' + values[component] for component in components]
    lines.append('"@signature-params": ' + parameters)
    return "\n".join(lines).encode()


def admit_packet(envelope, current, pointer, author_public, existing=None):
    """Reference admission against independently qualified current-cut inputs.

    No native storage, actual disclosure, installation or durable-write claim.
    """
    validate_native_shape(envelope)
    if (author_public != unb64(current["device_public_key_base64url"])
            or envelope["actor_id"] != current["actor_id"]
            or envelope["device_id"] != current["device_id"]
            or envelope["signature_proof"]["device_authorize_event_id"] != current["authorization_event_id"]
            or envelope["signature_proof"]["verification_method"] != current["verification_method"]
            or envelope["auth_binding"]["device_generation"] != current["device_generation"]
            or "retired" in [current["owner_status"],current["governance_status"]]):
        raise ValueError("original requester Device credential is no longer active")
    # Caller freshness/HTTP authentication is independent input qualification.
    # Exact accepted retry precedes current epoch/recipient/business re-admission.
    if existing is not None and envelope["backup_id"] == existing["backup_id"]:
        if envelope != existing:
            raise ValueError("duplicate_conflict: immutable full-packet retry changed")
        return "exact_retry"
    Ed25519PublicKey.from_public_bytes(author_public).verify(unb64(envelope["signature_proof"]["signature"]), envelope_bytes(envelope))
    if "sha256:" + hashlib.sha256(unb64(envelope["ciphertext"])).hexdigest() != envelope["ciphertext_digest"]:
        raise ValueError("bad ciphertext digest")
    context = envelope["contents"][0]["root_context"]
    scope = context["effective_scope"]
    if (envelope["actor_id"] != current["actor_id"] or scope != current["effective_scope"]
            or context != current["root_context"] or current["pending"] is not None
            or current["owner_status"] != "active" or current["governance_status"] != "active"
            or PUT not in current["actions"] or current["device_id"] != envelope["device_id"]
            or current["authorization_event_id"] != envelope["signature_proof"]["device_authorize_event_id"]
            or current["verification_method"] != envelope["signature_proof"]["verification_method"]
            or current["device_generation"] != envelope["auth_binding"]["device_generation"]
            or envelope["encryption"]["recipient_key_ref"] != current["recipient"]["key_agreement_ref"]
            or any(envelope["auth_binding"][name] != current[name] for name in ["manager_ref", "recovery_ref", "recipient_ref"])):
        raise ValueError("native packet differs from its current authority cut")
    # The accepted pointer retains selection-time Recovery provenance.
    # Its original signature/authority is independently qualified by the caller.
    # The new packet above must bind current Recovery; manager/recipient remain current.
    # Identity recovery.enabled is deliberately not a business-publication gate.
    if (series_key(envelope["actor_id"], scope) != series_key(pointer["actor_id"], pointer["effective_scope"])
            or envelope["series_id"] != pointer["active_series_id"]
            or any(pointer[name] != current[name] for name in ["manager_ref", "recipient_ref"])):
        raise ValueError("native packet differs from the exact scope pointer")
    if existing is not None:
        if (envelope["series_id"] != existing["series_id"]
                or envelope["series_sequence"] != existing["series_sequence"] + 1
                or envelope.get("supersedes_id") != existing["backup_id"]
                or envelope.get("supersedes_digest") != digest(unsigned_envelope(existing))):
            raise ValueError("packet predecessor conflict")
    elif envelope["series_sequence"] != 0:
        raise ValueError("missing exact predecessor")
    return {"backup_id": envelope["backup_id"], "ciphertext_digest": envelope["ciphertext_digest"]}


def select_series(record, previous, current, manager_public):
    proof = record["signature_proof"]
    if manager_public != unb64(current["manager_public_key_base64url"]):
        raise ValueError("series signer is not the independently qualified manager Service")
    if set(proof) != {"verification_method", "signature_algorithm", "signature"} or proof["signature_algorithm"] != "Ed25519":
        raise ValueError("native series requires the actual manager Service")
    Ed25519PublicKey.from_public_bytes(manager_public).verify(unb64(proof["signature"]), series_bytes(record))
    if (record["actor_id"] != current["actor_id"] or record["effective_scope"] != current["effective_scope"]
            or current["pending"] is not None or "retired" in [current["owner_status"], current["governance_status"]]
            or proof["verification_method"] != current["manager_method"]
            or any(record[name] != current[name] for name in ["manager_ref", "recovery_ref", "recipient_ref"])):
        raise ValueError("series differs from current manager/recipient/scope")
    if previous is None:
        if record["series_pointer_version"] != 1 or record["previous_series_ids"]:
            raise ValueError("invalid first scope pointer")
    elif (series_key(record["actor_id"], record["effective_scope"]) != series_key(previous["actor_id"], previous["effective_scope"])
            or record["series_pointer_version"] != previous["series_pointer_version"] + 1
            or record["previous_series_ids"] != previous["previous_series_ids"] + [previous["active_series_id"]]
            or record["active_series_id"] in record["previous_series_ids"]):
        raise ValueError("pointer CAS or scope predecessor mismatch")
    return copy.deepcopy(record)


def fixture():
    """Deterministic primitive KATs with explicit non-native reference inputs."""
    old = json.loads((ART / "fixtures/content-history-fixture.json").read_text(encoding="utf-8"))
    private = bytes([171]) * 32
    public = X25519PrivateKey.from_private_bytes(private).public_key().public_bytes_raw()
    next_private = bytes([172]) * 32
    next_public = X25519PrivateKey.from_private_bytes(next_private).public_key().public_bytes_raw()
    history = native_recovery_fixture(content_backup_public_keys=[public, public, next_public])
    check = verify_native_recovery(history)
    governance = governance_fixture()
    realm_id = governance["history"]["genesis"]["commit"]["realm_id"]
    subject = {"kind": "realm", "realm_actor_id": {"realm_id": realm_id,
        "principal_id": "ak:did_core:webvh:" + history["scid"]}}
    recipient = {"key_agreement_ref": history["did"] + "#content-backup", "hpke_suite": SUITE,
        "public_key_base64url": b64(public)}
    check_recipient(recipient, history, 0)
    next_recipient = {**recipient, "public_key_base64url": b64(next_public)}
    check_recipient(next_recipient, history, 2)
    device_seed = bytes([141]) * 32
    manager_seed = bytes([151]) * 32
    manager_key = Ed25519PrivateKey.from_private_bytes(manager_seed)
    manager_method = "did:web:manager.example#signing-1"
    device = "ak:device:019a0000-0000-7000-8000-000000000011"
    method = history["did"] + "#" + device
    scope = {"kind": "realm", "realm_id": subject["realm_actor_id"]["realm_id"]}
    references = {"manager_ref": committed(51, 1), "recovery_ref": committed(53, 2), "recipient_ref": committed(55, 0)}
    for ref in references.values():
        ref["stream_ref"]["realm_id"] = scope["realm_id"]
    context = copy.deepcopy(old["root_backup"]["plaintext"]["items"][0]["root_context"])
    context.update(effective_scope=scope, genesis_event_ref=token("event", 61),
        group_state_ref=token("event", 62), backup_strategy_ref=governance["history"]["genesis"]["event"]["event_id"])
    exporter = bytes.fromhex(old["kat"]["exporter_secret_hex"])
    root = content_root(exporter, context)
    entry = {"item_kind": "content_epoch_root", "secret_id": "root_12", "root_context": context,
        "root_ref": root_ref(root, context), "root_base64url": b64(root)}
    packet = {"backup_id": "ak:backup:019a0000-0000-7000-8000-000000000011",
        "actor_id": subject, "device_id": device, "backup_kind": "secret_storage", "backup_version": "kb_content_roots",
        "series_id": "ak:backup_series:019a0000-0000-7000-8000-000000000011", "series_sequence": 0,
        "created_at": "2026-11-08T00:00:00.000Z", "auth_binding": {"kind": "realm_device", **references, "device_generation": 1},
        "encryption": {"recipient_method": "realm_actor_recovery", "recipient_key_ref": recipient["key_agreement_ref"],
            "hpke_suite": SUITE, "aead": {"name": "chacha20_poly1305"}},
        "domain_separation": {"subdomain": "key_backup"},
        "contents": [{name: value for name, value in entry.items() if name != "root_base64url"}],
        "signature_proof": {"device_id": device, "verification_method": method, "signature_algorithm": "Ed25519",
            "device_authorize_event_id": token("event", 63)}}
    plaintext = {"schema": "ak.schema.key_backup_plaintext.v1",
        **{name: packet[name] for name in ["backup_id", "backup_kind", "series_id", "series_sequence"]}, "items": [entry]}
    sources = admission_fixture(packet, {"effective_scope": scope}, recipient, history, device_seed)
    references = {name: original_reference(sources["create_material"]) for name in ["manager_ref", "recovery_ref", "recipient_ref"]}
    packet["auth_binding"].update(references)
    packet["signature_proof"]["device_authorize_event_id"] = sources["device_authorize_ref"]["event_id"]
    packet = seal(packet, plaintext, public, bytes([181]) * 32, device_seed)
    current = {"actor_id": subject, "effective_scope": scope, "root_context": context,
        "device_id": device, "authorization_event_id": sources["device_authorize_ref"]["event_id"], "verification_method": method,
        "device_generation": 1, "recipient": recipient, **references, "recovery_enabled": True,
        "pending": None, "owner_status": "active", "governance_status": "active", "actions": [PUT],
        "manager_method": manager_method,
        "device_public_key_base64url": b64(Ed25519PrivateKey.from_private_bytes(device_seed).public_key().public_bytes_raw()),
        "manager_public_key_base64url": b64(manager_key.public_key().public_bytes_raw())}
    pointer = {"schema": "ak.schema.key_backup_active_series.v1", "actor_id": subject,
        "effective_scope": scope, "backup_kind": "secret_storage", "active_series_id": packet["series_id"],
        "series_pointer_version": 1, "previous_series_ids": [], **references,
        "issued_at": "2026-11-07T00:00:00.000Z", "signature_proof": {
            "verification_method": manager_method, "signature_algorithm": "Ed25519"}}
    pointer["signature_proof"]["signature"] = b64(manager_key.sign(series_bytes(pointer)))
    metadata = {"actor_id": subject, "device_id": device, "authorization_event_id": sources["device_authorize_ref"]["event_id"],
        "applet_id": "ak:applet:019a0000-0000-7000-8000-000000000011", "effective_scope": scope,
        "nonce": b64(bytes([201]) * 16)}
    import base64
    headers = {"arkret-operation": PUT, "arkret-managed-device": b64(canonical(metadata)),
        "destination-service-id": governance["history"]["genesis_resolution"]["service_id"],
        "content-digest": "sha-256=:" + base64.b64encode(hashlib.sha256(canonical(packet)).digest()).decode() + ":",
        "idempotency-key": "arkret-key-backup-" + hashlib.sha256(canonical(packet)).hexdigest()}
    components = ["@method", "@target-uri", "@authority", "arkret-operation", "arkret-managed-device", "destination-service-id", "content-digest", "idempotency-key"]
    device_public = Ed25519PrivateKey.from_private_bytes(device_seed).public_key().public_bytes_raw()
    kid = "did:key:z" + base58(b"\xed\x01" + device_public)
    kid += "#" + kid.removeprefix("did:key:")
    parameters = "(" + " ".join('"' + name + '"' for name in components) + ");created=1794096000;expires=1794096300;keyid=\"" + kid + "\";alg=\"ed25519\""
    uri = "https://governor.example/_arkret/self/keys/backups/" + packet["backup_id"]
    http = http_base("PUT", uri, headers, parameters)
    from tools.realm_actor_contract import signature_fixture
    transfer = copy.deepcopy(signature_fixture()["cases"][2]["unsigned_projection"])
    transfer.update(actor_id=subject, new_service_id="ak:did_core:web:new-manager.example", next_content_backup_recipient=next_recipient)
    for name in ["expected_manager_revision","expected_control_revision","expected_device_generation_revision"]:
        transfer[name] = {"commit_id":references["manager_ref"]["commit_id"],"stream_position":references["manager_ref"]["stream_position"]}
    admission = {"backup_id": packet["backup_id"], "envelope_digest": digest(packet), "ciphertext_digest": packet["ciphertext_digest"],
        "realm_actor_id": subject["realm_actor_id"], "effective_scope": scope, "device_id": device,
        "device_authorize_ref": sources["device_authorize_ref"], "device_generation": 1,
        "device_public_key_base64url": b64(device_public), **references,
        "accepted_at": "2026-11-08T00:00:00.000Z", "service_id": sources["origin_resolution"]["service_id"],
        "governance_generation": "0", "authority_ref": governance["history"]["genesis"]["event"]["event_id"]}
    admission_signature, admission_bytes, admission_public = sign("ak.realm_actor_content_backup_admission_signature.v1", admission,
        bytes.fromhex(sources["governor_seed_hex"]), sources["governor_history"]["did"]+"#control-0", admission["accepted_at"])
    admission["signature"] = admission_signature
    native_source = {"admission": admission, "device_authorization": sources["device_authorization"], "origin_resolution": sources["origin_resolution"], "governance_history": governance["history"]}
    series_event, _, _ = signed_reference_event("ak.key_backup.active_series", {"kind":"service", "service_id":"ak:did_core:web:manager.example"},
        pointer,{"kind":"realm_control","realm_id":realm_id},manager_seed,manager_method,"2026-11-07T00:00:01.000Z",
        sources["device_authorization"]["event"]["applet_id"])
    series_fact={"kind":"realm_recovery_service","event_id":series_event["event_id"],"actor_id":series_event["actor_id"],
        "target_actor_id":subject,"verification_method":manager_method,"public_key_base64url":b64(manager_key.public_key().public_bytes_raw()),
        "accepted_at":series_event["created_at"],"applet_id":series_event["applet_id"],"registration_epoch":digest({"applet_id":series_event["applet_id"]}),
        "registration_ref":committed(11,0),"manager_ref":references["manager_ref"],"recovery_ref":references["recovery_ref"]}
    series_source=attach_reference_commit(series_event,series_fact,bytes.fromhex(sources["governor_seed_hex"]),
        sources["governor_history"]["did"]+"#control-0",admission["authority_ref"],2,sources["device_authorize_ref"]["commit_id"])
    entries=[{"kind":"backup","backup":packet,"native_source":native_source},
        {"kind":"series","effective_scope":scope,"record":pointer,"source_ref":original_reference(series_source),"source":series_source},
        {"kind":"recipient","recipient_ref":references["recipient_ref"],"content_backup_recipient":recipient,"declaration":sources["create_material"]}]
    entries.sort(key=lambda entry:canonical(inventory_identity(entry)))
    full_manifest={"realm_actor_id":subject["realm_actor_id"],"manager_ref":references["manager_ref"],"archive_revision":3,"entries":entries}
    inventory_cut={name:full_manifest[name] for name in ["realm_actor_id","manager_ref","archive_revision"]}
    inventory_cut["inventory_digest"]=digest(full_manifest)
    offer={**inventory_cut,"new_service_id":"ak:did_core:web:new-manager.example","next_content_backup_recipient":next_recipient,
        "expires_at":"2026-11-08T00:05:00.000Z","nonce":b64(bytes([221])*32)}
    offer_signature,offer_bytes,offer_public=sign("ak.realm_actor_content_backup_offer_signature.v1",offer,bytes([152])*32,
        "did:web:new-manager.example#signing-1","2026-11-08T00:00:01.000Z")
    offer["signature"]=offer_signature
    handover_plain={"offer_digest":digest(offer),"inventory_manifest":full_manifest,"recipient_keys":[{
        "recipient_ref":references["recipient_ref"],"content_backup_recipient":recipient,"private_key_base64url":b64(private)}],
        "challenge_base64url":b64(bytes([222])*32)}
    handover_sealed=hpke_seal(bytes([184])*32,next_public,handover_info(offer),canonical(handover_plain),canonical(offer))
    sealed={"offer":offer,"hpke_suite":SUITE,"enc":b64(handover_sealed[:32]),"ciphertext_base64url":b64(handover_sealed[32:])}
    importer=ImportedArchiveReference()
    confirmation=importer.import_and_confirm(sealed,next_private,bytes([152])*32,inventory_cut,"2026-11-08T00:00:02.000Z")
    transfer["content_backup_inventory_digest"]=inventory_cut["inventory_digest"]
    transfer["content_backup_handover_digest"]=confirmation["handover_digest"]
    acceptance,transfer_bytes,transfer_public=sign("ak.realm_actor_manager_acceptance_signature.v1",transfer,bytes([152])*32,
        "did:web:new-manager.example#signing-1","2026-11-08T00:00:03.000Z")
    offer_case={"context":"ak.realm_actor_content_backup_offer_signature.v1",
        "unsigned_schema_ref":"schemas/keys-operations.schema.json#/$defs/realm_actor_content_backup_handover_offer_signature_input",
        "unsigned_projection":{name:value for name,value in offer.items() if name!="signature"},"signature":offer_signature,
        "public_key_base64url":b64(offer_public),"test_seed_hex":(bytes([152])*32).hex(),
        "canonical_hex":canonical({name:value for name,value in offer.items() if name!="signature"}).hex(),"signature_input_hex":offer_bytes.hex()}
    confirmation_input={name:value for name,value in confirmation.items() if name!="signature"}
    confirmation_bytes=b"ak.realm_actor_content_backup_confirmation_signature.v1\n"+canonical({name:value for name,value in confirmation["signature"].items() if name!="signature"})
    confirmation_case={"context":"ak.realm_actor_content_backup_confirmation_signature.v1",
        "unsigned_schema_ref":"schemas/keys-operations.schema.json#/$defs/realm_actor_content_backup_handover_confirmation_signature_input",
        "unsigned_projection":confirmation_input,"signature":confirmation["signature"],"public_key_base64url":b64(offer_public),
        "test_seed_hex":(bytes([152])*32).hex(),"canonical_hex":canonical(confirmation_input).hex(),"signature_input_hex":confirmation_bytes.hex()}

    metadata={name:packet[name] for name in ["backup_id","actor_id","backup_kind","backup_version","series_id","series_sequence",
        "created_at","ciphertext_digest","encryption","device_id","auth_binding"]}
    metadata["encryption"]={name:packet["encryption"][name] for name in ["recipient_method","recipient_key_ref","hpke_suite"]}
    head_state={"realm_actor_id":subject["realm_actor_id"],"effective_scope":scope,**references,
        "authority_commit_id":series_source["commit"]["commit_id"],"secret_storage":{"state":"active",
            "active_series_id":pointer["active_series_id"],"series_pointer_version":pointer["series_pointer_version"]}}
    head_response={"purpose":"series_predecessor","realm_actor_id":subject["realm_actor_id"],"effective_scope":scope,
        "active_series":head_state,"items":[{"metadata":metadata,"admission":admission}]}
    native_current={"selector":{"kind":"realm_actor_key_backup_active_series","actor_id":subject,"effective_scope":scope,"backup_kind":"secret_storage"},
        "source_stream_ref":series_source["commit"]["stream_ref"],"revision":{"commit_id":series_source["commit"]["commit_id"],"stream_position":series_source["commit"]["stream_position"]},
        "value":{name:pointer[name] for name in ["active_series_id","series_pointer_version","manager_ref","recovery_ref","recipient_ref"]}}
    result = {"runner": {"kind": "named_suite", "entrypoint": "ak.suite.realm_actor.content_backup.v1",
            "in_tree_checker": "tools/test_realm_actor_backup_contract.py"},
        "generated_by": "tools/regenerate_realm_actor_backup_fixture.py",
        "covers_vectors": ["ak.vector.realm_actor.content_backup.v1"],
        "description": "Real deterministic RFC9180 X25519/HKDF-SHA256/ChaCha20Poly1305, Ed25519 envelope/HTTP/manager signatures and exact native DID keyAgreement history. Public test seeds only. Current cuts/source coordinates are explicitly reference inputs, not native PG/HTTP admission or physical durability, import completeness, authority qualification or production acceptance. Lifecycle tests execute byte and reference-state refusals; runtime qualification remains separately required.",
        "native_history": history, "original_recipient_declaration_index": 0,
        "recipient": recipient, "next_recipient": next_recipient,
        "test_material": {"archive_private_hex": private.hex(), "next_archive_private_hex": next_private.hex(),
            "ephemeral_private_hex": (bytes([181]) * 32).hex(), "device_seed_hex": device_seed.hex(),
            "manager_seed_hex": manager_seed.hex(), "device_public_base64url": b64(device_public),
            "manager_public_base64url": b64(manager_key.public_key().public_bytes_raw()),
            "exporter_secret_hex": exporter.hex()},
        "native_packet": packet, "plaintext": plaintext, "current_reference_cut": current, "active_series": pointer,
        "admission_case": {"context": "ak.realm_actor_content_backup_admission_signature.v1",
            "unsigned_schema_ref": "schemas/keys-operations.schema.json#/$defs/realm_actor_content_backup_admission_signature_input",
            "unsigned_projection": {name:value for name,value in admission.items() if name != "signature"},
            "signature": admission_signature, "public_key_base64url": b64(admission_public),
            "canonical_hex": canonical({name:value for name,value in admission.items() if name != "signature"}).hex(),
            "signature_input_hex": admission_bytes.hex(), "test_seed_hex": sources["governor_seed_hex"]},
        "native_source": native_source, "original_authority_reference": sources,
        "native_put_response": {"status":"accepted", "backup_id": packet["backup_id"], "ciphertext_digest": packet["ciphertext_digest"], "admission": admission},
        "archive_inventory":full_manifest,"inventory_cut":inventory_cut,
        "device_head_response":head_response,"device_unlock_response":{"backup":packet,"admission":admission},
        "native_current":native_current,"native_current_entry":{"status":"present","current_state":native_current,"source_ref":original_reference(series_source)},
        "manager_unlock_response":{"backup":packet,"native_source":native_source},
        "handover_offer_case":offer_case,"handover_confirmation_case":confirmation_case,
        "private_handover":{"sealed":sealed,"plaintext":handover_plain,"confirmation":confirmation,
            "info_hex":handover_info(offer).hex(),"aad_hex":canonical(offer).hex(),"ephemeral_test_seed_hex":(bytes([184])*32).hex()},
        "schema_validation_cases": native_schema_cases(packet, pointer, recipient),
        "kat": {"root_hex": root.hex(), "info_hex": backup_info(packet).hex(), "aad_hex": backup_aad(packet).hex(),
            "plaintext_hex": canonical(plaintext).hex(), "signature_input_hex": envelope_bytes(packet).hex(),
            "series_signature_input_hex": series_bytes(pointer).hex(),
            "account_info_hex": backup_info(old["root_backup"]["envelope"]).hex(),
            "account_aad_hex": backup_aad(old["root_backup"]["envelope"]).hex()},
        "http": {"method": "PUT", "uri": uri, "headers": headers, "signature_parameters": parameters,
            "signature_input_hex": http.hex(), "signature_base64url": b64(Ed25519PrivateKey.from_private_bytes(device_seed).sign(http))},
        "manager_handover": {"acceptance_input": transfer, "acceptance": acceptance,
            "signature_input_hex": transfer_bytes.hex(), "new_manager_public_base64url": b64(transfer_public)},
    }
    result["decision_cases"] = execute_decision_cases(result)
    return result


class ArchiveReference:
    """In-memory reference effects; explicitly not a durable native database."""
    def __init__(self):
        self.packets = {}
        self.publications = {}

    def put(self, packet, current, pointer, author_public):
        previous = self.packets.get(packet["backup_id"])
        if previous is None:
            candidates = [row for row in self.packets.values() if row["series_id"] == packet["series_id"]
                and series_key(row["actor_id"], row["contents"][0]["root_context"]["effective_scope"]) ==
                    series_key(packet["actor_id"], packet["contents"][0]["root_context"]["effective_scope"])]
            previous = max(candidates, key=lambda row: row["series_sequence"], default=None)
        result = admit_packet(packet, current, pointer, author_public, previous)
        self.packets[packet["backup_id"]] = copy.deepcopy(packet)
        if result == "exact_retry":
            result = {name: packet[name] for name in ["backup_id", "ciphertext_digest"]}
        return result

    def acknowledge(self, packet, result, issuer_public):
        verify_device_put_response(packet, result, issuer_public)
        if self.packets.get(packet["backup_id"]) != packet:
            raise ValueError("no matching physical reference packet; preparation is not publication")
        self.publications[packet["backup_id"]] = copy.deepcopy(result)

    def dependencies(self, root_context, root):
        refs = [identity for identity, packet in self.packets.items() if identity in self.publications and
            packet["contents"][0]["root_context"] == root_context and packet["contents"][0]["root_ref"] == root]
        if not refs:
            raise ValueError("root awaits a real matching publication acknowledgement")
        return sorted(refs)

    def list_exact_scope(self, actor, scope):
        wanted = series_key(actor, scope)
        return [copy.deepcopy(packet) for packet in self.packets.values() if
            series_key(packet["actor_id"], packet["contents"][0]["root_context"]["effective_scope"]) == wanted]


def execute_decision_cases(data):
    """Recompute crypto/reference outcomes, never physical custody or process isolation."""
    packet=data["native_packet"]
    public=unb64(data["test_material"]["device_public_base64url"])
    private=bytes.fromhex(data["test_material"]["archive_private_hex"])
    opened=open_backup(packet,private,public)
    if opened!=data["plaintext"]:raise ValueError("original archive key opened another root")
    try:
        open_backup(packet,bytes([183])*32,public)
    except InvalidTag:
        unrelated_key_refused=True
    else:
        raise ValueError("an unrelated private key opened the manager archive packet")
    store=ArchiveReference()
    store.packets[packet["backup_id"]]=copy.deepcopy(packet)
    root=data["plaintext"]["items"][0]
    try:
        store.dependencies(root["root_context"],root["root_ref"])
    except ValueError:
        frozen_only_refused=True
    else:
        raise ValueError("a locally frozen packet invented a publication acknowledgement")
    if store.publications:raise ValueError("failed reference lookup altered publication state")
    store.acknowledge(packet,data["native_put_response"],unb64(data["admission_case"]["public_key_base64url"]))
    refs=store.dependencies(root["root_context"],root["root_ref"])
    point="AK-SDK-010/native_archive_recipient_is_manager_only_and_publication_is_not_faked_by_local_freeze"
    return [
        {"name":"native_archive_recipient_requires_original_independent_private_key",
            "covers_decision_points":[point],
            "expected":{"original_archive_key_opens_root_ref":root["root_ref"],"unrelated_private_key_refused":unrelated_key_refused,
                "boundary":"Crypto key separation only; manager vault/process isolation requires runtime audit."}},
        {"name":"native_local_freeze_needs_verified_reference_admission_before_publication",
            "covers_decision_points":[point],
            "expected":{"local_freeze_without_ack_refused":frozen_only_refused,"verified_reference_admission_backup_refs":refs,
                "boundary":"Signed reference admission and in-memory effects only; not a production PUT or physical durability claim."}},
    ]


def derive_native_series_current_key(realm_actor_id, effective_scope, backup_kind):
    """Closed family locator; not a producer authorization or generic hash API."""
    if (not isinstance(realm_actor_id, dict) or set(realm_actor_id) != {"realm_id", "principal_id"}
            or any(not isinstance(value,str) or not value for value in realm_actor_id.values())
            or not isinstance(effective_scope, dict)
            or effective_scope.get("kind") not in {"realm", "circle"}
            or effective_scope.get("realm_id") != realm_actor_id["realm_id"]
            or set(effective_scope) != ({"kind", "realm_id"} if effective_scope["kind"] == "realm" else {"kind", "realm_id", "circle_id"})
            or any(not isinstance(value,str) or not value for value in effective_scope.values())
            or backup_kind != "secret_storage"):
        raise ValueError("native current key requires the exact RealmActorId and scope")
    preimage = b"ak.current_key.realm_actor_key_backup_active_series.v1\n" + canonical([realm_actor_id, effective_scope, backup_kind])
    return preimage, b64(hashlib.sha256(preimage).digest())


def native_schema_cases(packet, pointer, recipient):
    cases = [
        {"name": "native_root_packet_valid", "schema_ref": "schemas/key-backup.schema.json", "expect_valid": True, "instance": copy.deepcopy(packet)},
        {"name": "native_scope_series_valid", "schema_ref": "schemas/key-backup-active-series.schema.json", "expect_valid": True, "instance": copy.deepcopy(pointer)},
        {"name": "native_archive_recipient_valid", "schema_ref": "schemas/realm-actor.schema.json#/$defs/content_backup_recipient", "expect_valid": True, "instance": copy.deepcopy(recipient)},
    ]
    for name in ["source_commit_ref", "recovery_policy_ref", "custodian_actor_id", "custody_authorization_ref"]:
        value = copy.deepcopy(packet)
        value[name] = None
        cases.append({"name": "native_packet_forbids_" + name, "schema_ref": "schemas/key-backup.schema.json", "expect_valid": False, "instance": value})
    for name, expiry in [("timestamp", "2026-11-09T00:00:00.000Z"), ("null", None)]:
        value = copy.deepcopy(packet)
        value["expires_at"] = expiry
        cases.append({"name": "native_packet_forbids_expiry_" + name, "schema_ref": "schemas/key-backup.schema.json", "expect_valid": False, "instance": value})
    for name in ["old_generation_alias", "mixed_account_subject", "mixed_recipient", "agent_author", "extra_auth", "two_root_items", "aead_nonce"]:
        value=copy.deepcopy(packet)
        if name=="old_generation_alias": value["auth_binding"]["device_generation_ref"]=value["auth_binding"].pop("device_generation")
        if name=="mixed_account_subject": value["actor_id"]={"kind":"account","account_id":{"principal_id":"ak:did_core:web:alice.example","station_id":"ak:did_core:web:station.example"}}
        if name=="mixed_recipient": value["encryption"]["recipient_method"]="recovery_public_key"
        if name=="agent_author": value["signature_proof"]["agent_authorization_event_ref"]=token("event",88)
        if name=="extra_auth": value["auth_binding"]["unregistered"]=True
        if name=="two_root_items": value["contents"]*=2
        if name=="aead_nonce": value["encryption"]["aead"]["nonce"]=b64(bytes(12))
        cases.append({"name":"native_packet_rejects_"+name,"schema_ref":"schemas/key-backup.schema.json","expect_valid":False,"instance":value})
    for name in ["source_commit_ref", "custodian_actor_id", "custody_authorization_ref"]:
        value=copy.deepcopy(pointer);value[name]=None
        cases.append({"name":"native_series_forbids_"+name,"schema_ref":"schemas/key-backup-active-series.schema.json","expect_valid":False,"instance":value})
    value=copy.deepcopy(pointer);value["signature_proof"]["device_authorize_event_id"]=token("event",88)
    cases.append({"name":"native_series_rejects_human_device_author","schema_ref":"schemas/key-backup-active-series.schema.json","expect_valid":False,"instance":value})
    from tools.artifact_lint.core import Lint, jsonschema_errors
    for case in cases:
        lint=Lint()
        errors=jsonschema_errors(lint,ART/"fixtures/realm-actor-content-backup-fixture.json",case["schema_ref"],case["instance"])
        if lint.errors or bool(errors)==case["expect_valid"]:
            raise ValueError("native schema case does not have its declared result: "+case["name"])
        if errors:case["first_expected_error"]=errors[0]
    return cases


def signed_reference_event(kind, actor, payload, scope, seed, method, at, applet):
    """Construct real wire bytes/signatures, not an accepted native transaction."""
    event = {"kind": kind, "scope_ref": scope, "actor_id": actor,
        "created_at": at, "payload": copy.deepcopy(payload)}
    if "realm_id" in scope:
        event["realm_id"] = scope["realm_id"]
    if applet is not None:
        event["applet_id"] = applet
    if kind == "ak.realm.actor.create":
        event["authorization_ref"] = payload["creation_authorization_ref"]
    event_digest = digest(event)
    event["event_id"] = "ak:event:" + b64(b"\x01" + bytes.fromhex(event_digest.removeprefix("sha256:")))
    binding = {"context": "ak.event_proof.v1", "event_digest": event_digest, "actor_id": actor,
        "verification_method": method, "created_at": at}
    header = b64(canonical({"alg": "Ed25519"}))
    signing = (header + "." + b64(canonical(binding))).encode()
    event["producer_proof"] = {"kind": "detached_jws", "verification_method": method,
        "event_digest": event_digest, "created_at": at,
        "jws": header + ".." + b64(Ed25519PrivateKey.from_private_bytes(seed).sign(signing))}
    return event, binding, signing


def attach_reference_commit(event, fact, governor_seed, governor_method, authority_ref, position, previous=None):
    realm = event.get("realm_id", "ak:realm:" + event["event_id"].removeprefix("ak:event:"))
    stream_kind = "realm" if event["scope_ref"]["kind"] == "realm_genesis" else event["scope_ref"]["kind"]
    commit = {"realm_id": realm, "stream_ref": {"kind": stream_kind, "realm_id": realm},
        "stream_position": position, "previous_commit_ref": previous, "event_ref": event["event_id"],
        "governance_generation": "0", "authority_ref": authority_ref,
        "committed_at": event["created_at"], "producer_signer_fact_digest": digest(fact)}
    commit["commit_id"] = "ak:realm_commit:" + b64(b"\x01" + hashlib.sha256(canonical(commit)).digest())
    signature, _, _ = sign("ak.realm_commit_signature.v1", commit, governor_seed, governor_method, commit["committed_at"])
    commit["signature"] = signature
    return {"event": event, "commit": commit, "producer_signer_fact": fact}


def original_reference(material):
    commit = material["commit"]
    return {"event_id": commit["event_ref"], "commit_id": commit["commit_id"],
        "stream_ref": commit["stream_ref"], "stream_position": commit["stream_position"]}


def station_resolution(history):
    """Exact normalized projection of this fixture's actually verified native log."""
    verify_native_recovery(history)
    state = history["log_entries"][-1]["state"]
    normalized = {"did": state["id"], "contexts": state["@context"], "controller_dids": [], "also_known_as": [],
        "verification_methods": [{"verification_method": row["id"], "controller_did": row["controller"],
            "verification_method_suite": row["type"], "public_key_material": {"publicKeyMultibase": row["publicKeyMultibase"]},
            "extensions": []} for row in state["verificationMethod"]],
        "authentication": [{"verification_method": value} for value in state["authentication"]],
        "assertion_methods": [], "key_agreements": [], "capability_invocations": [], "capability_delegations": [],
        "services": [{"uri": row["id"], "protocol_names": [row["type"]], "endpoint": row["serviceEndpoint"],
            "extensions": [{"name": "serviceKind", "value": row["serviceKind"]}]} for row in state["service"]],
        "metadata": {}, "extensions": []}
    head = history["log_entries"][-1]
    version = head["versionId"]
    proof = {"kind": "webvh_log", "history_head": version, "witnesses": [],
        "witness_proofs_digest": digest(history["witness_records"])}
    return {"service_id": "ak:did_core:webvh:" + history["scid"], "service_kind": "station",
        "normalized_did_document": normalized, "method_history_evidence": {"evidence_kind": "webvh_log",
            "boundary": {"from_method_history_head": digest(head), "from_version_id": version,
                "to_method_history_head": digest(head), "to_version_id": version},
            "evidence": {"kind": "ak.did.binding_evidence.v1", "method": "webvh", "document_digest": digest(normalized), "method_proofs": [proof]},
            "log_entries": history["log_entries"], "witness_records": history["witness_records"]}}


def admission_fixture(packet, current, recipient, history, device_seed, authorized_actions=None):
    """A non-Event custody receipt with independent real original proof bytes."""
    from tools.realm_actor_contract import signature_fixture
    governance = governance_fixture()
    governor_history = governance["issuer_history"]
    resolution = governance["history"]["genesis_resolution"]
    governor_seed = bytes([100]) * 32
    governor_method = governor_history["did"] + "#control-0"
    actor = packet["actor_id"]
    scope = {"kind": "realm_control", "realm_id": actor["realm_actor_id"]["realm_id"]}
    candidate = copy.deepcopy(signature_fixture()["cases"][0]["candidate"])
    candidate.update(actor_id=actor, creation_scope=current["effective_scope"], service_id="ak:did_core:web:manager.example")
    candidate["recovery"]["content_backup_recipient"] = recipient
    candidate["expires_at"] = "2026-11-06T00:01:00.000Z"
    candidate.pop("control_signature")
    control_seed = bytes([80]) * 32
    candidate["control_signature"], _, _ = sign("ak.realm_actor_creation_signature.v1", candidate,
        control_seed, history["did"] + "#control-0", "2026-11-06T00:00:00.000Z")
    applet = candidate["applet_id"]
    create, _, _ = signed_reference_event("ak.realm.actor.create", {"kind": "service", "service_id": candidate["service_id"]},
        candidate, scope, bytes([151]) * 32, "did:web:manager.example#signing-1", "2026-11-06T00:00:00.000Z",
        applet)
    service_fact = {"event_id": create["event_id"], "actor": create["actor_id"],
        "verification_method": "did:web:manager.example#signing-1", "accepted_at": create["created_at"],
        "key": {"public_key_base64url": b64(Ed25519PrivateKey.from_private_bytes(bytes([151]) * 32).public_key().public_bytes_raw()),
            "applet_id": applet, "registration_epoch": digest({"applet_id": applet}),
            "registration_ref": committed(11, 0), "authorization_ref": committed(12, 1), "effective_scope": scope}}
    create_material = attach_reference_commit(create, service_fact, governor_seed, governor_method, governance["history"]["genesis"]["event"]["event_id"], 0)
    create_ref = original_reference(create_material)
    device_public = Ed25519PrivateKey.from_private_bytes(device_seed).public_key().public_bytes_raw()
    welcome_public = X25519PrivateKey.from_private_bytes(bytes([183]) * 32).public_key().public_bytes_raw()
    authorize = {"device_id": packet["device_id"], "device_public_key_did": "did:key:z" + base58(b"\xed\x01"+device_public),
        "hpke_key": "z"+base58(b"\xec\x01"+welcome_public), "algorithms": ["Ed25519"], "device_key_algorithm": "Ed25519",
        "authorized_by": actor["realm_actor_id"]["principal_id"], "authorization_binding_kind": "realm_managed_delegation",
        "authorized_generation_ref": 1, "not_before": "2026-11-07T00:00:00.000Z", "expires_at": "2026-11-09T00:00:00.000Z",
        "scopes": [{"effective_scope": current["effective_scope"], "actions": list(NATIVE_BACKUP_OPERATIONS if authorized_actions is None else authorized_actions)},
            {"effective_scope":{"kind":"circle","realm_id":actor["realm_actor_id"]["realm_id"],"circle_id":token("circle",89)},"actions":list(NATIVE_BACKUP_OPERATIONS)}], "applet_id": applet,
        "expected_control_revision": {"commit_id":create_ref["commit_id"], "stream_position":0}, "expected_device_revision": None}
    possession = {"actor_id": actor, **authorize}
    possession_bytes = b"ak.device_authorize_realm_actor_possession_proof.v1\n"+canonical(possession)
    authorize["device_signature"] = b64(Ed25519PrivateKey.from_private_bytes(device_seed).sign(possession_bytes))
    event, binding, event_signing = signed_reference_event("ak.device.authorize", actor, authorize, scope, control_seed,
        history["did"]+"#control-0", "2026-11-07T00:00:00.000Z", applet)
    fact = {"kind":"realm_control", "event_id": event["event_id"], "actor_id": actor,
        "verification_method": history["did"]+"#control-0", "public_key_base64url":b64(Ed25519PrivateKey.from_private_bytes(control_seed).public_key().public_bytes_raw()),
        "accepted_at":event["created_at"], "control_event_ref":create_ref}
    authorization = attach_reference_commit(event,fact,governor_seed,governor_method,governance["history"]["genesis"]["event"]["event_id"],1,create_ref["commit_id"])
    device_ref = original_reference(authorization)
    return {"create_material":create_material, "device_authorization":authorization,
        "device_authorize_ref":device_ref, "origin_resolution":resolution, "governor_history":governor_history,
        "governor_seed_hex":governor_seed.hex(), "possession_input_hex":possession_bytes.hex(),
        "producer_binding_hex":canonical(binding).hex(), "producer_jws_signing_hex":event_signing.hex()}


def governance_fixture():
    """A real, RealmId-bound original chain without online/current wrappers."""
    issuer_history = native_recovery_fixture(seed_offset=20, station_endpoint="https://governor.example/")
    issuer_history["log_entries"] = issuer_history["log_entries"][:1]
    issuer_history["witness_records"] = issuer_history["witness_records"][:1]
    resolution = station_resolution(issuer_history)
    human_seed = bytes([191]) * 32
    human_device = "ak:device:019a0000-0000-7000-8000-000000000021"
    actor = {"kind": "account", "account_id": {"principal_id": "ak:did_core:web:founder.example", "station_id": resolution["service_id"]}}
    method = "did:web:founder.example#" + human_device
    payload = {"object": {"schema": "ak.schema.realm_genesis.v1", "purpose": "collaboration",
        "genesis_salt": b64(bytes([211]) * 32), "trust_domain": "ak:trust_domain:governor.example",
        "security_class": "standard", "governance_station_id": resolution["service_id"],
        "initial_join_rule": "invite", "initial_history_access": "since_join",
        "initial_encryption_backup_strategy": "ak.encryption_backup.epoch_content_roots.v1", "initial_discoverability": "listed"}}
    event, _, _ = signed_reference_event("ak.realm.create",actor,payload,{"kind":"realm_genesis"},human_seed,method,
        "2026-11-05T00:00:00.000Z",None)
    auth = committed(213,0);auth["stream_ref"]["kind"]="realm"
    fact = {"event_id":event["event_id"],"actor":actor,"device_id":human_device,"verification_method":method,
        "accepted_at":event["created_at"],"key":{"public_key_base64url":b64(Ed25519PrivateKey.from_private_bytes(human_seed).public_key().public_bytes_raw()),
            "authorization_ref":auth,"revision":{"commit_id":auth["commit_id"],"stream_position":0},"governance_generation":"0"}}
    original = attach_reference_commit(event,fact,bytes([100])*32,issuer_history["did"]+"#control-0",event["event_id"],0)
    return {"history":{"genesis":original,"genesis_resolution":resolution,"authority_transitions":[]},
        "issuer_history":issuer_history,"human_test_seed_hex":human_seed.hex()}


def resolution_public(resolution, method):
    evidence = resolution["method_history_evidence"]
    if evidence.get("evidence_kind") != "webvh_log":
        raise ValueError("this deterministic native source KAT requires original WebVH evidence")
    entries = evidence["log_entries"]
    history = {"did":entries[0]["state"]["id"],"scid":entries[0]["parameters"]["scid"],
        "log_entries":entries,"witness_records":evidence["witness_records"]}
    verify_native_recovery(history)
    if station_resolution(history) != resolution:
        raise ValueError("original service resolution projection differs from its native evidence")
    methods = [row for row in resolution["normalized_did_document"]["verification_methods"] if row["verification_method"] == method]
    if len(methods) != 1:
        raise ValueError("historical issuer method unavailable")
    multibase = methods[0]["public_key_material"]["publicKeyMultibase"]
    public = unbase58(multibase.removeprefix("z"))
    if not multibase.startswith("z") or len(public) != 34 or public[:2] != b"\xed\x01":
        raise ValueError("issuer key is not original Ed25519")
    return public[2:]


def verify_reference_original(material, issuer_resolution):
    event, commit, fact = material["event"], material["commit"], material.get("producer_signer_fact")
    preimage = {name:value for name,value in event.items() if name not in {"event_id","producer_proof","unsigned"}}
    original_digest=digest(preimage)
    if event["event_id"] != "ak:event:"+b64(b"\x01"+bytes.fromhex(original_digest.removeprefix("sha256:"))):
        raise ValueError("original Event content identity mismatch")
    if ("producer_signer_fact_digest" in commit) != (fact is not None):
        raise ValueError("original fact presence differs from signed Commit")
    if fact is None or digest(fact) != commit["producer_signer_fact_digest"] or fact["event_id"] != event["event_id"]:
        raise ValueError("original producer fact is unavailable or changed")
    actor = fact.get("actor_id",fact.get("actor"))
    if actor != event.get("executed_by",event["actor_id"]):
        raise ValueError("fact has another original producer")
    public = unb64(fact.get("public_key_base64url",fact.get("key",{}).get("public_key_base64url","")))
    proof = event["producer_proof"]
    binding = {"context":"ak.event_proof.v1","event_digest":original_digest,"actor_id":event["actor_id"],
        "verification_method":proof["verification_method"],"created_at":proof["created_at"]}
    for optional in ["domain","audience"]:
        if optional in proof:binding[optional]=proof[optional]
    header, empty, signature=proof["jws"].split(".")
    if (empty or json.loads(unb64(header)) != {"alg":"Ed25519"}
            or proof["event_digest"] != original_digest or proof["verification_method"] != fact["verification_method"]):
        raise ValueError("original producer proof binding mismatch")
    Ed25519PublicKey.from_public_bytes(public).verify(unb64(signature),(header+"."+b64(canonical(binding))).encode())
    unsigned={name:value for name,value in commit.items() if name not in {"signature","commit_id"}}
    if commit["commit_id"] != "ak:realm_commit:"+b64(b"\x01"+hashlib.sha256(canonical(unsigned)).digest()):
        raise ValueError("original Commit identity mismatch")
    realm=event.get("realm_id","ak:realm:"+event["event_id"].removeprefix("ak:event:"))
    if commit["event_ref"] != event["event_id"] or commit["realm_id"] != realm or commit["stream_ref"]["realm_id"] != realm:
        raise ValueError("original Event and Commit scope mismatch")
    unsigned={name:value for name,value in commit.items() if name != "signature"}
    issuer=resolution_public(issuer_resolution,commit["signature"]["verification_method"])
    if not verify("ak.realm_commit_signature.v1",unsigned,commit["signature"],issuer):
        raise ValueError("original governance Commit signature invalid")
    return original_reference(material)


def verify_governance_history(history, admission):
    original=history["genesis"]
    resolution=history["genesis_resolution"]
    verify_reference_original(original,resolution)
    event,commit=original["event"],original["commit"]
    realm="ak:realm:"+event["event_id"].removeprefix("ak:event:")
    if (event["kind"] != "ak.realm.create" or event["scope_ref"] != {"kind":"realm_genesis"}
            or event.get("realm_id") is not None or commit["stream_ref"] != {"kind":"realm","realm_id":realm}
            or commit["stream_position"] != 0 or commit["previous_commit_ref"] is not None
            or commit["governance_generation"] != "0" or commit["authority_ref"] != event["event_id"]
            or admission["realm_actor_id"]["realm_id"] != realm
            or event["payload"]["object"]["governance_station_id"] != resolution["service_id"]):
        raise ValueError("native custody governance history is not RealmId-rooted")
    resolutions={0:resolution};authority=event["event_id"]
    for index,transition in enumerate(history["authority_transitions"]):
        if transition["from_resolution"] != resolutions[index]:
            raise ValueError("governance transition starts from another original authority")
        source=transition["original"];handoff=transition["handoff"]
        verify_reference_original(source,resolutions[index])
        target=transition["to_resolution"]
        if (source["event"]["kind"] != "ak.realm.governance_station.change"
                or source["commit"]["governance_generation"] != str(index)
                or source["commit"]["authority_ref"] != authority
                or handoff["from_generation"] != str(index) or handoff["to_generation"] != str(index+1)
                or handoff["realm_id"] != realm or handoff["from_service_id"] != resolutions[index]["service_id"]
                or handoff["to_service_id"] != target["service_id"]
                or handoff["change_event_ref"] != source["event"]["event_id"]
                or handoff["change_commit_id"] != source["commit"]["commit_id"]):
            raise ValueError("governance handoff is not a consecutive original transition")
        body={name:value for name,value in handoff.items() if name not in {"handoff_id","old_authority_signature","new_authority_acceptance_signature"}}
        if handoff["handoff_id"] != "ak:realm_authority_handoff:"+b64(b"\x01"+hashlib.sha256(canonical(body)).digest()):
            raise ValueError("handoff identity mismatch")
        for field,context,service in [("old_authority_signature","ak.realm_authority_handoff_old_signature.v1",resolutions[index]),
                ("new_authority_acceptance_signature","ak.realm_authority_handoff_new_acceptance_signature.v1",target)]:
            signed_body = {**body, "handoff_id": handoff["handoff_id"]}
            if not verify(context,signed_body,handoff[field],resolution_public(service,handoff[field]["verification_method"])):
                raise ValueError("handoff original signature invalid")
        resolutions[index+1]=target;authority=handoff["handoff_id"]
    generation=int(admission["governance_generation"])
    if (generation != len(history["authority_transitions"]) or admission["authority_ref"] != authority
            or admission["service_id"] != resolutions[generation]["service_id"]
            or admission["accepted_at"] < original["commit"]["committed_at"]):
        raise ValueError("native admission issuer tenure differs from immutable history")
    return resolutions


def verify_native_device_operation(authorization, resolution, actor, device_id, generation, scope, operation, accepted_at):
    """Check an operation against a real original, at an independently supplied cut."""
    ref=verify_reference_original(authorization,resolution)
    event=authorization["event"];payload=event["payload"]
    if (operation not in NATIVE_BACKUP_OPERATIONS or event["kind"] != "ak.device.authorize"
            or event["actor_id"] != actor or actor.get("kind") != "realm"
            or event["scope_ref"] != {"kind":"realm_control","realm_id":actor["realm_actor_id"]["realm_id"]}
            or payload["authorization_binding_kind"] != "realm_managed_delegation"
            or payload["device_id"] != device_id or payload["authorized_generation_ref"] != generation
            or not payload["not_before"] <= accepted_at < payload["expires_at"]
            or not any(row["effective_scope"] == scope and operation in row["actions"] for row in payload["scopes"])):
        raise ValueError("original Device authorization does not permit this operation in this exact scope")
    public=unbase58(payload["device_public_key_did"].removeprefix("did:key:z"))
    if len(public) != 34 or public[:2] != b"\xed\x01":
        raise ValueError("original Device key is not Ed25519")
    possession={"actor_id":event["actor_id"],**{name:value for name,value in payload.items() if name != "device_signature"}}
    Ed25519PublicKey.from_public_bytes(public[2:]).verify(unb64(payload["device_signature"]),
        b"ak.device_authorize_realm_actor_possession_proof.v1\n"+canonical(possession))
    return ref,public[2:]


def verify_native_receipt(packet, native_source):
    if set(native_source) != {"admission","device_authorization","origin_resolution","governance_history"}:
        raise ValueError("immutable native source is missing or mixed")
    admission=native_source["admission"]
    resolutions=verify_governance_history(native_source["governance_history"],admission)
    resolution=resolutions[int(admission["governance_generation"])]
    if native_source["origin_resolution"] != resolution:
        raise ValueError("native receipt issuer evidence differs from its historical tenure")
    signature=admission["signature"]
    if signature["created_at"] != admission["accepted_at"] or not verify("ak.realm_actor_content_backup_admission_signature.v1",
            {name:value for name,value in admission.items() if name != "signature"},signature,
            resolution_public(resolution,signature["verification_method"])):
        raise ValueError("native receipt signature invalid")
    authorization=native_source["device_authorization"]
    context=packet["contents"][0]["root_context"]
    ref,public=verify_native_device_operation(authorization,resolutions[int(authorization["commit"]["governance_generation"])],
        packet["actor_id"],packet["device_id"],admission["device_generation"],context["effective_scope"],PUT,admission["accepted_at"])
    if ref != admission["device_authorize_ref"]:
        raise ValueError("original native Device authorization differs from the receipt")
    if b64(public) != admission["device_public_key_base64url"]:
        raise ValueError("receipt did not preserve the original Device public key")
    validate_native_shape(packet)
    Ed25519PublicKey.from_public_bytes(public).verify(unb64(packet["signature_proof"]["signature"]),envelope_bytes(packet))
    if (admission["envelope_digest"] != digest(packet) or admission["backup_id"] != packet["backup_id"]
            or admission["ciphertext_digest"] != packet["ciphertext_digest"]
            or admission["realm_actor_id"] != packet["actor_id"]["realm_actor_id"]
            or admission["device_id"] != packet["device_id"] or admission["effective_scope"] != context["effective_scope"]
            or packet["signature_proof"]["device_authorize_event_id"] != ref["event_id"]
            or any(packet["auth_binding"][name] != admission[name] for name in NATIVE_AUTH-{"kind"})):
        raise ValueError("native receipt does not bind this exact signed packet and authorized scope")
    return copy.deepcopy(admission)


def inventory_identity(entry):
    kind=entry["kind"]
    if kind=="backup":return [kind,entry["backup"]["backup_id"]]
    if kind=="series":return [kind,entry["effective_scope"],entry["record"]["active_series_id"],entry["record"]["series_pointer_version"]]
    if kind=="recipient":return [kind,entry["recipient_ref"]]
    raise ValueError("unregistered archive inventory entry")


def verify_inventory(manifest, expected_cut):
    if set(manifest)!={"realm_actor_id","manager_ref","archive_revision","entries"}:
        raise ValueError("invalid full archive manifest")
    if any(manifest[name]!=expected_cut[name] for name in ["realm_actor_id","manager_ref","archive_revision"]) or digest(manifest)!=expected_cut["inventory_digest"]:
        raise ValueError("archive differs from independently frozen full namespace cut")
    identities=[canonical(inventory_identity(entry)) for entry in manifest["entries"]]
    if identities!=sorted(identities) or len(set(identities))!=len(identities):
        raise ValueError("archive inventory ordering or duplicate typed identity")
    declarations={}
    packets={}
    for entry in manifest["entries"]:
        if entry["kind"]=="backup":
            packet=entry["backup"]
            if packet["actor_id"]["realm_actor_id"]!=manifest["realm_actor_id"]:raise ValueError("foreign archive backup")
            verify_native_receipt(packet,entry["native_source"])
            packets[packet["backup_id"]]=packet
        elif entry["kind"]=="recipient":
            declaration=entry["declaration"]
            if original_reference(declaration)!=entry["recipient_ref"]:raise ValueError("recipient declaration coordinates changed")
            event=declaration["event"];payload=event["payload"]
            if event["kind"]=="ak.realm.actor.create":
                actual=payload["recovery"]["content_backup_recipient"]
                if "recovery_begin" in entry:raise ValueError("unexpected recovery begin")
            elif event["kind"]=="ak.realm.actor.manager.change":
                actual=payload["next_content_backup_recipient"]
                if "recovery_begin" in entry:raise ValueError("unexpected recovery begin")
            elif event["kind"]=="ak.realm.actor.control.reset":
                begin=entry.get("recovery_begin")
                if begin is None or original_reference(begin)!=payload["recovery_begin_ref"]:
                    raise ValueError("missing exact accepted replacement begin")
                actual=begin["event"]["payload"]["next_content_backup_recipient"]
            else:raise ValueError("not a recipient declaration writer")
            if actual!=entry["content_backup_recipient"]:raise ValueError("recipient declaration body mismatch")
            history=payload["method_history_evidence"]
            vector={"did":history["log_entries"][0]["state"]["id"],"scid":history["log_entries"][0]["parameters"]["scid"],
                "log_entries":history["log_entries"],"witness_records":history["witness_records"]}
            check_recipient(actual,vector,len(vector["log_entries"])-1)
            declarations[canonical(entry["recipient_ref"])]=actual
    # All non-backup original sources are verified against the immutable native
    # governance history retained with their associated first-PUT packet.
    histories=[entry["native_source"]["governance_history"] for entry in manifest["entries"] if entry["kind"]=="backup"]
    if not histories and manifest["entries"]:raise ValueError("reference inventory lacks an independently rooted original authority")
    for entry in manifest["entries"]:
        if entry["kind"]=="backup":
            packet=entry["backup"]
            descriptor=declarations.get(canonical(packet["auth_binding"]["recipient_ref"]))
            if descriptor is None or descriptor["key_agreement_ref"]!=packet["encryption"]["recipient_key_ref"]:
                raise ValueError("missing original recipient declaration")
        else:
            material=entry["source"] if entry["kind"]=="series" else entry["declaration"]
            generation=int(material["commit"]["governance_generation"])
            history=histories[0]
            resolution=history["genesis_resolution"] if generation==0 else history["authority_transitions"][generation-1]["to_resolution"]
            reference=verify_reference_original(material,resolution)
            if entry["kind"]=="series":
                record=entry["record"];fact=material["producer_signer_fact"]
                if (reference!=entry["source_ref"] or material["event"]["kind"]!="ak.key_backup.active_series"
                        or material["event"]["payload"]!=record or entry["effective_scope"]!=record["effective_scope"]
                        or record["actor_id"]["realm_actor_id"]!=manifest["realm_actor_id"]
                        or fact.get("kind")!="realm_recovery_service" or fact["target_actor_id"]!=record["actor_id"]
                        or any(fact[name]!=record[name] for name in ["manager_ref","recovery_ref"])):
                    raise ValueError("scope-series record lacks its exact manager original")
                if not verify_record_signature(record,unb64(fact["public_key_base64url"])):
                    raise ValueError("scope-series original signature invalid")
    return packets,declarations


def verify_record_signature(record,public):
    try:Ed25519PublicKey.from_public_bytes(public).verify(unb64(record["signature_proof"]["signature"]),series_bytes(record))
    except (ValueError, InvalidSignature, KeyError, TypeError):return False
    return True


def handover_info(offer):
    projection={name:offer[name] for name in ["realm_actor_id","manager_ref","new_service_id","inventory_digest"]}
    projection["offer_digest"]=digest(offer)
    return b"ak.realm_actor_content_backup_handover.v1\n"+canonical(projection)


def handover_response(challenge,offer_digest,inventory_digest,handover_digest):
    import hmac
    if len(challenge)!=32:raise ValueError("private challenge must be exactly 32 bytes")
    projection={"offer_digest":offer_digest,"inventory_digest":inventory_digest,"handover_digest":handover_digest}
    return b64(hmac.new(challenge,b"ak.realm_actor_content_backup_handover_confirmation.v1\n"+canonical(projection),"sha256").digest())


def open_handover(sealed,next_private,new_service_public,expected_cut,now):
    offer=sealed["offer"]
    if (sealed["hpke_suite"]!=SUITE or offer["expires_at"]<=now
            or len(unb64(offer["nonce"]))!=32
            or any(offer[name]!=expected_cut[name] for name in ["realm_actor_id","manager_ref","archive_revision","inventory_digest"])):
        raise ValueError("handover offer/cut/expiry mismatch")
    if not verify("ak.realm_actor_content_backup_offer_signature.v1",{name:value for name,value in offer.items() if name!="signature"},
            offer["signature"],new_service_public):raise ValueError("new Service offer signature invalid")
    derived=X25519PrivateKey.from_private_bytes(next_private).public_key().public_bytes_raw()
    if b64(derived)!=offer["next_content_backup_recipient"]["public_key_base64url"]:
        raise ValueError("new manager does not own the offered independent archive key")
    raw=hpke_open(next_private,unb64(sealed["enc"])+unb64(sealed["ciphertext_base64url"]),handover_info(offer),canonical(offer))
    plain=json.loads(raw)
    if set(plain)!={"offer_digest","inventory_manifest","recipient_keys","challenge_base64url"} or plain["offer_digest"]!=digest(offer):
        raise ValueError("handover plaintext differs from exact signed offer")
    packets,declarations=verify_inventory(plain["inventory_manifest"],expected_cut)
    keys={}
    for entry in plain["recipient_keys"]:
        identity=canonical(entry["recipient_ref"])
        descriptor=entry["content_backup_recipient"]
        if identity in keys or declarations.get(identity)!=descriptor:raise ValueError("extra/duplicate/mismatched private recipient")
        private=unb64(entry["private_key_base64url"])
        if len(private)!=32 or b64(X25519PrivateKey.from_private_bytes(private).public_key().public_bytes_raw())!=descriptor["public_key_base64url"]:
            raise ValueError("imported private/public recipient mismatch")
        keys[identity]=private
    if set(keys)!=set(declarations):raise ValueError("missing original private recipient custody")
    for packet in packets.values():
        identity=canonical(packet["auth_binding"]["recipient_ref"])
        source=next(entry["native_source"] for entry in plain["inventory_manifest"]["entries"] if entry["kind"]=="backup" and entry["backup"]["backup_id"]==packet["backup_id"])
        original_public=unb64(source["admission"]["device_public_key_base64url"])
        open_backup(packet,keys[identity],original_public)
    if len(unb64(plain["challenge_base64url"]))!=32:raise ValueError("missing actual transfer challenge")
    return plain


class ImportedArchiveReference:
    """An in-memory import boundary; actual durable retention requires SUT tests."""
    def __init__(self):self.imports={}

    def import_and_confirm(self,sealed,next_private,new_service_seed,expected_cut,now):
        public=Ed25519PrivateKey.from_private_bytes(new_service_seed).public_key().public_bytes_raw()
        plain=open_handover(sealed,next_private,public,expected_cut,now)
        identity=digest(sealed["offer"])
        old=self.imports.get(identity)
        if old is not None and old!=plain:raise ValueError("immutable transfer intent changed")
        self.imports[identity]=copy.deepcopy(plain)
        response={"offer_digest":identity,"inventory_digest":expected_cut["inventory_digest"],"handover_digest":digest(plain)}
        response["challenge_response_base64url"]=handover_response(unb64(plain["challenge_base64url"]),**response)
        response["signature"],_,_=sign("ak.realm_actor_content_backup_confirmation_signature.v1",response,new_service_seed,
            sealed["offer"]["signature"]["verification_method"],now)
        return response


def verify_confirmation(confirmation,offer,plain,new_service_public):
    import hmac
    expected={"offer_digest":digest(offer),"inventory_digest":digest(plain["inventory_manifest"]),"handover_digest":digest(plain)}
    if any(confirmation[name]!=value for name,value in expected.items()):raise ValueError("confirmation bound to another offer/cut/transfer")
    actual=handover_response(unb64(plain["challenge_base64url"]),**expected)
    if not hmac.compare_digest(actual,confirmation["challenge_response_base64url"]):raise ValueError("new manager did not answer the exact decrypted challenge")
    if not verify("ak.realm_actor_content_backup_confirmation_signature.v1",{name:value for name,value in confirmation.items() if name!="signature"},
            confirmation["signature"],new_service_public):raise ValueError("new Service confirmation signature invalid")
    return expected["handover_digest"]


def verify_device_put_response(packet,response,issuer_public):
    """Cross-message primitive check; live SDK transport qualification is separate.

    issuer_public is already independently qualified by the owning Station/audit
    caller. This function never performs current DID/governance discovery.
    """
    if not isinstance(response,dict) or set(response)!={"status","backup_id","ciphertext_digest","admission"} or response.get("status") not in {"accepted","duplicate"}:
        raise ValueError("native request cannot consume the Account-only reply or private authority source")
    admission=response["admission"]
    unsigned={name:value for name,value in admission.items() if name!="signature"}
    if not verify("ak.realm_actor_content_backup_admission_signature.v1",unsigned,admission["signature"],issuer_public):
        raise ValueError("original immutable native receipt signature invalid")
    if (any(response[name]!=packet[name] for name in ["backup_id","ciphertext_digest"])
            or admission["backup_id"]!=packet["backup_id"] or admission["envelope_digest"]!=digest(packet)
            or admission["ciphertext_digest"]!=packet["ciphertext_digest"]
            or admission["realm_actor_id"]!=packet["actor_id"]["realm_actor_id"]
            or admission["device_id"]!=packet["device_id"]
            or admission["effective_scope"]!=packet["contents"][0]["root_context"]["effective_scope"]
            or admission["device_authorize_ref"]["event_id"]!=packet["signature_proof"]["device_authorize_event_id"]
            or any(admission[name]!=packet["auth_binding"][name] for name in NATIVE_AUTH-{"kind"})):
        raise ValueError("native reply belongs to another original PUT")
    Ed25519PublicKey.from_public_bytes(unb64(admission["device_public_key_base64url"])).verify(
        unb64(packet["signature_proof"]["signature"]),envelope_bytes(packet))
    return copy.deepcopy(admission)
