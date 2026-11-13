"""Generate deterministic primitive KATs, not a native admission simulation."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from tools.content_history import SCHEME, STRATEGY, aad, b64, content_key, content_root, jcs, key_commitment, root_ref, hpke_seal, grant_header, mnemonic_backup_key, did_key
from tools.content_backup_source import protections_digest, signing_bytes

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "spec/v1/artifacts/fixtures/content-history-fixture.json"
SOURCE_OUTPUT = ROOT / "spec/v1/artifacts/fixtures/content-backup-source-fixture.json"
VECTOR = "ak.vector.crypto.content_history.v1"
SOURCE_VECTOR = "ak.vector.crypto.content_backup_source.v1"


def attachment_receive_vector(coordinate, root, body_context, outer, signer, grant, recipient_public):
    """Frozen primitive bytes with native original/state authority as external premises."""
    from tools.artifact_lint.blob_content_key import exporter
    descriptors, objects = [], []
    for index in range(2):
        context = {"effective_scope": coordinate["effective_scope"],
                   "genesis_event_ref": coordinate["genesis_event_ref"], "epoch": coordinate["epoch"],
                   "scheme": "ak.blob.whole_file_aead.v1",
                   "encryption_algorithm": "mls_exporter_aead_aes_256_gcm",
                   "content_key_salt": b64(bytes([170 + index]) * 32), "producer": body_context["producer"]}
        key = exporter(root, context, "sha256")
        plain = b"original attachment " + bytes([48 + index])
        descriptor = {"encrypted": True, "scheme": context["scheme"],
                      "encryption_algorithm": context["encryption_algorithm"],
                      "key_ref": {"algorithm": "MLS", "group_state_ref": coordinate["group_state_ref"]},
                      "content_key_salt": context["content_key_salt"], "nonce": b64((index + 1).to_bytes(12, "big")),
                      "size_bytes": len(plain), "media_type": "text/plain", "producer": context["producer"],
                      "key_commitment": key_commitment(key, context)}
        header = {**{field: descriptor[field] for field in
                     ("scheme", "key_ref", "content_key_salt", "nonce", "size_bytes", "media_type", "producer", "key_commitment")},
                  "alg": context["encryption_algorithm"], "epoch": coordinate["epoch"],
                  "purpose": "blob-attachment", "aead_profile": coordinate["cipher_suite"]}
        associated = jcs(header)
        ciphertext = AESGCM(key).encrypt((index + 1).to_bytes(12, "big"), plain, associated)
        descriptor["blob_ref"] = "ak:blob:sha256:" + hashlib.sha256(ciphertext).hexdigest()
        descriptors.append(descriptor)
        objects.append({"context": context, "key_hex": key.hex(), "plaintext_hex": plain.hex(),
                        "aad_hex": associated.hex(), "ciphertext_base64url": b64(ciphertext)})
    block = {"kind": "ak.content.text", "body": "authorized parent body", "format": "plain", "attachments": descriptors}
    context = {**body_context, "content_key_salt": b64(bytes([174]) * 32)}
    body_key = content_key(root, context)
    envelope = {"version": "1.0", "content_type": "application/vnd.arkret.message+json", "encryption_scheme": SCHEME,
                "encryption_context": {"epoch": coordinate["epoch"], "group_state_ref": coordinate["group_state_ref"],
                    "root_ref": context["root_ref"], "content_key_salt": context["content_key_salt"],
                    "key_commitment": key_commitment(body_key, context),
                    "protection": {"root_refs": [context["root_ref"]],
                        "blob_refs": [d["blob_ref"] for d in descriptors],
                        "backup_refs": ["ak:backup:019a0000-0000-7000-8000-000000000001"]}}}
    envelope["ciphertext"] = b64(AESGCM(body_key).encrypt(bytes(12), jcs(block), aad(outer, envelope, context)))
    original = {**outer, "payload": {"encrypted_content": envelope}}
    digest = hashlib.sha256(jcs(original)).digest()
    original["event_id"] = "ak:event:" + b64(b"\x01" + digest)
    transcript = jcs({"original": original})
    selected = copy.deepcopy(grant)
    selected["history_cut"] = {**selected["history_cut"], "event_id": original["event_id"], "stream_position": 1}
    selected["entries"] = []
    for index, (path, key) in enumerate([
            ("/payload/encrypted_content", body_key),
            ("/payload/encrypted_content/attachments/0", bytes.fromhex(objects[0]["key_hex"]))]):
        selector = {"kind": "content_key", "source_event_ref": original["event_id"], "content_path": path}
        selected["entries"].append({"selector": selector, "sealed_key_base64url": b64(hpke_seal(
            bytes([180 + index]) * 32, recipient_public, grant_header(selected, selector), key))})
    return {"qualification": "Primitive Ed25519 over the explicitly named transcript, HPKE, pointer and AEAD bytes only. Native Event/Commit acceptance, source-at-cut, original producer/MLS authority, current read/disclose and durable nonce/replay are external obligations, not fixture booleans.",
            "original": original, "primitive_transcript_hex": transcript.hex(),
            "primitive_signature_base64url": b64(signer.sign(transcript)),
            "parent_context": context, "parent_plaintext": block, "grant": selected, "objects": objects,
            "expected_selected_path": "/payload/encrypted_content/attachments/0"}


def backup_source_encoding(outer, producer, signer, method, body, metadata, plaintexts, service_method):
    """Actual primitive signatures and content IDs, without native admission claims."""
    event = copy.deepcopy(outer)
    event['payload'] = {'strand_id': 'ak:strand:AT3ARBdH1FM6GjXK9ulTx-YMvQOXys39dlUzZV6KyID9',
                        'track_name': 'discussion', 'encrypted_content': body, 'encrypted_metadata': metadata}
    digest = hashlib.sha256(jcs(event)).digest()
    event['event_id'] = 'ak:event:' + b64(b'\x01' + digest)
    binding = {'context': 'ak.event_proof.v1', 'event_digest': 'sha256:' + digest.hex(),
               'actor_id': event['actor_id'], 'verification_method': method, 'created_at': event['created_at']}
    event['producer_proof'] = {key: binding[key] for key in ['event_digest', 'verification_method', 'created_at']}
    event['producer_proof'].update({'kind': 'detached_jws', 'jws': b64(b'{"alg":"Ed25519"}') + '..' + b64(signer.sign(jcs(binding)))})
    slots = [{'content_path': '/payload/' + key, 'protection': event['payload'][key]['encryption_context']['protection']}
             for key in ['encrypted_content', 'encrypted_metadata']]
    origin = producer['actor_id']['account_id']['station_id']
    service_seed = bytes([233]) * 32
    service = Ed25519PrivateKey.from_private_bytes(service_seed)
    attestation = {'event_ref': event['event_id'], 'event_original_digest': 'sha256:' + hashlib.sha256(jcs(event)).hexdigest(),
                   'producer': producer, 'effective_scope': event['scope_ref'],
                   'destination_service_id': 'ak:did_core:web:governor.example', 'protections_digest': protections_digest(slots),
                   'verification_method': service_method, 'attested_at': '2026-11-08T00:00:01.000Z',
                   'expires_at': '2026-11-08T00:05:01.000Z'}
    transcript = signing_bytes(attestation)
    attestation['signature'] = {'kid': service_method, 'signature_algorithm': 'Ed25519', 'signature': b64(service.sign(transcript))}
    return {'event': event, 'attestation': attestation, 'producer': producer,
            'origin_key': {'station_id': origin, 'verification_method': service_method,
                           'public_key_base64url': b64(service.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))},
            'signing_hex': transcript.hex(), 'producer_binding_hex': jcs(binding).hex(),
            'service_signing_seed_hex': service_seed.hex(),
            'plaintexts_hex': {k: v.hex() for k, v in plaintexts.items()},
            'qualification': 'Real primitive Ed25519, content ID and AES-GCM bytes only; no native root PUT, Service method history, physical durability, allowed atomic unit or current signer qualification is asserted.'}


def build(include_sources=False):
    governance = json.loads((ROOT / "spec/v1/artifacts/fixtures/mls-governance-binding-closure-fixture.json").read_text(encoding="utf-8"))
    external_binding = {"encoding": "MlsGroupBinding deterministic CBOR without prefix",
                        "carrier": "FramedContent.authenticated_data",
                        "group_context_extension": "inherited exact accepted base bytes",
                        "cases": governance["cases"][0]["accepted"][:3]}
    event_ref = "ak:event:" + b64(b"\x01" + bytes([0x41]) * 32)
    realm = "ak:realm:" + event_ref.split(":", 2)[2]
    actor = {"kind": "account", "account_id": {"principal_id": "ak:did_core:webvh:z6mkfixture", "station_id": "ak:did_core:webvh:z6mkfixturestationexample"}}
    signer = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    public = signer.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    coordinate = {"effective_scope": {"kind": "realm", "realm_id": realm}, "genesis_event_ref": event_ref,
                  "epoch": "12", "group_state_ref": event_ref,
                  "cipher_suite": "MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519",
                  "encryption_backup_strategy": STRATEGY, "backup_strategy_ref": event_ref}
    exporter_secret = bytes(range(32, 64))
    root = content_root(exporter_secret, coordinate)
    context = {"root_context": coordinate, "root_ref": root_ref(root, coordinate), "purpose": "event_body",
               "encryption_scheme": SCHEME, "encryption_algorithm": "aes128_gcm",
               "producer": {"actor_id": actor, "endpoint": {"kind": "device", "device_id": "ak:device:019a0000-0000-7000-8000-000000000001"}, "authorization_event_ref": event_ref, "signature_key_base64url": b64(public)},
               "content_key_salt": b64(bytes(range(64, 96)))}
    key = content_key(root, context)
    envelope = {"version": "1.0", "content_type": "application/json", "encryption_scheme": SCHEME,
                "encryption_context": {"epoch": "12", "group_state_ref": event_ref, "content_key_salt": context["content_key_salt"], "root_ref": context["root_ref"], "key_commitment": key_commitment(key, context), "protection": {"root_refs": [context["root_ref"]], "blob_refs": [], "backup_refs": ["ak:backup:019a0000-0000-7000-8000-000000000001"]}}}
    outer = {"kind": "ak.message.create", "realm_id": realm, "scope_ref": coordinate["effective_scope"], "actor_id": actor, "created_at": "2026-11-08T00:00:00.000Z"}
    plaintext = jcs({"text": "original recoverable content"})
    associated = aad(outer, envelope, context)
    envelope["ciphertext"] = b64(AESGCM(key).encrypt(bytes(12), plaintext, associated))
    metadata_context = {**context, "content_key_salt": b64(bytes(range(96, 128)))}
    metadata_key = content_key(root, metadata_context)
    metadata_envelope = copy.deepcopy(envelope)
    metadata_envelope["content_type"] = "application/vnd.arkret.message-metadata+json"
    metadata_envelope["encryption_context"].update({
        "content_key_salt": metadata_context["content_key_salt"],
        "key_commitment": key_commitment(metadata_key, metadata_context),
    })
    metadata_plaintext = jcs({"title": "original metadata"})
    metadata_aad = aad(outer, metadata_envelope, metadata_context)
    metadata_envelope["ciphertext"] = b64(AESGCM(metadata_key).encrypt(bytes(12), metadata_plaintext, metadata_aad))
    human_producer = copy.deepcopy(context['producer'])
    human_outer = {**outer, 'actor_id': human_producer['actor_id']}
    agent_signer = Ed25519PrivateKey.from_private_bytes(bytes([234]) * 32)
    agent = {'actor_id': {'kind': 'account', 'account_id': {'principal_id': 'ak:did_core:web:agent.example',
             'station_id': human_producer['actor_id']['account_id']['station_id']}},
             'endpoint': {'kind': 'agent_runtime', 'verification_method': 'did:web:agent.example#runtime-key'},
             'authorization_event_ref': event_ref,
             'signature_key_base64url': b64(agent_signer.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))}
    agent_outer = {**outer, 'actor_id': agent['actor_id']}
    source_plaintexts = {'encrypted_content': jcs({'kind': 'ak.content.text', 'body': 'original recoverable content', 'format': 'plain'}),
                         'encrypted_metadata': jcs({'fields': {'title': 'original metadata'}})}
    def source_envelopes(source_outer, producer, first_salt):
        result = []
        for index, (source_context, source_envelope, source_plaintext) in enumerate([
                (context, envelope, source_plaintexts['encrypted_content']), (metadata_context, metadata_envelope, source_plaintexts['encrypted_metadata'])]):
            slot = {**source_context, 'producer': producer, 'content_key_salt': b64(bytes([first_salt + index]) * 32)}
            slot_key = content_key(root, slot)
            encoded = copy.deepcopy(source_envelope)
            if index == 0:
                encoded['content_type'] = 'application/vnd.arkret.message+json'
            encoded['encryption_context'].update({'content_key_salt': slot['content_key_salt'],
                                                   'key_commitment': key_commitment(slot_key, slot)})
            encoded['ciphertext'] = b64(AESGCM(slot_key).encrypt(bytes(12), source_plaintext, aad(source_outer, encoded, slot)))
            result.append(encoded)
        return result
    service_method = 'did:webvh:z6mkfixturestationexample:station.example#service-key-fixture'
    human_source = backup_source_encoding(human_outer, human_producer, signer,
        'did:webvh:z6mkfixture:alice.example#ak:device:019a0000-0000-7000-8000-000000000001',
        *source_envelopes(human_outer, human_producer, 242), source_plaintexts, service_method)
    agent_source = backup_source_encoding(agent_outer, agent, agent_signer, agent['endpoint']['verification_method'],
        *source_envelopes(agent_outer, agent, 240), source_plaintexts, service_method)
    original = jcs({"outer_event": outer, "envelope": envelope})
    source_event = {**outer, "payload": {"encrypted_content": envelope, "encrypted_metadata": metadata_envelope}}
    source_event["event_id"] = "ak:event:" + b64(b"\x01" + hashlib.sha256(jcs(source_event)).digest())
    mnemonic = " ".join(["abandon"] * 23 + ["art"])
    recipient_secret, recipient_public = mnemonic_backup_key(mnemonic)
    cut = {"event_id": event_ref, "commit_id": "ak:realm_commit:" + b64(b"\x01" + bytes([0x43]) * 32),
           "stream_ref": coordinate["effective_scope"], "stream_position": 0}
    request_ref = "ak:event:" + b64(b"\x01" + bytes([0x42]) * 32)
    grant = {"recipient": context["producer"], "recipient_hpke_key_base64url": b64(recipient_public),
             "recipient_key_event_ref": request_ref,
             "history_cut": {**cut, "event_id": source_event["event_id"], "stream_position": 1},
             "expires_at": "2026-11-08T00:15:00.000Z", "entries": []}
    hpke_cases = []
    for index, selected_key in enumerate((key, root)):
        selector = {"kind": "content_key", "source_event_ref": source_event["event_id"], "content_path": "/payload/encrypted_content"} if index == 0 else {
            "kind": "epoch_root", "root_context": coordinate, "root_ref": context["root_ref"], "closed_epoch_cut": grant["history_cut"]}
        info = grant_header(grant, selector)
        ephemeral = bytes([128 + index]) * 32
        sealed = hpke_seal(ephemeral, recipient_public, info, selected_key)
        grant["entries"].append({"selector": selector, "sealed_key_base64url": b64(sealed)})
        hpke_cases.append({"ephemeral_private_hex": ephemeral.hex(), "info_hex": info.hex(), "plaintext_hex": selected_key.hex(), "sealed_hex": sealed.hex()})
    root_item = {"item_kind": "content_epoch_root", "secret_id": "root_12", "root_context": coordinate,
                 "root_ref": context["root_ref"], "root_base64url": b64(root)}
    backup = {"backup_id": envelope["encryption_context"]["protection"]["backup_refs"][0], "actor_id": actor,
              "backup_kind": "secret_storage", "backup_version": "kb_content_roots", "series_id": "ak:backup_series:019a0000-0000-7000-8000-000000000001",
              "series_sequence": 0, "created_at": outer["created_at"],
              "source_commit_ref": {"realm_commit_id": cut["commit_id"], "device_generation_ref": 1},
              "recovery_policy_ref": {"policy_id": "ak:policy:019a0000-0000-7000-8000-000000000001", "policy_version": 1},
              "encryption": {"recipient_method": "recovery_public_key", "recipient_key_ref": did_key(recipient_public, b"\xec\x01"), "hpke_suite": "ak.hpke_x25519_aead_chacha20poly1305.v1", "aead": {"name": "chacha20_poly1305"}},
              "domain_separation": {"subdomain": "key_backup"},
              "contents": [{k: v for k, v in root_item.items() if k != "root_base64url"}],
              "signature_proof": {"device_id": context["producer"]["endpoint"]["device_id"], "verification_method": did_key(public, b"\xed\x01"), "signature_algorithm": "Ed25519", "device_authorize_event_id": event_ref}}
    bag = {"schema": "ak.schema.key_backup_plaintext.v1", **{k: backup[k] for k in ("backup_id", "backup_kind", "series_id", "series_sequence")}, "items": [root_item]}
    backup_aad = jcs({"schema": "ak.schema.key_backup.v1", "actor_id": actor, "device_id": None,
                      **{k: backup[k] for k in ("backup_kind", "backup_version", "created_at")},
                      "item_kinds": ["content_epoch_root"], "recipient_method": "recovery_public_key", "recipient_key_ref": backup["encryption"]["recipient_key_ref"]})
    backup_info = jcs({k: backup[k] for k in ("backup_id", "series_id", "series_sequence", "actor_id", "backup_kind", "backup_version", "created_at")})
    sealed_backup = hpke_seal(bytes([133]) * 32, recipient_public, backup_info, jcs(bag), backup_aad)
    backup["encryption"]["aead"]["enc"] = b64(sealed_backup[:32])
    backup["ciphertext"] = b64(sealed_backup[32:])
    backup["ciphertext_digest"] = "sha256:" + hashlib.sha256(sealed_backup[32:]).hexdigest()
    backup_signature_transcript = jcs(backup)
    backup["signature_proof"]["signature"] = b64(signer.sign(backup_signature_transcript))
    replacement = {**context["producer"], "endpoint": {"kind": "device", "device_id": "ak:device:019a0000-0000-7000-8000-000000000002"},
                   "authorization_event_ref": request_ref, "signature_key_base64url": b64(Ed25519PrivateKey.from_private_bytes(bytes([211]) * 32).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))}
    preparation_cut = {**cut, "event_id": request_ref, "stream_position": 1}
    empty_inventory = {"actor_id": actor, "replacement": replacement, "authorization_event_ref": request_ref,
                       "pcr_cut": preparation_cut, "entries": []}
    pending = {"state": "pending", "replacement": replacement, "pcr_cut": preparation_cut}
    prepared = {**pending, "state": "prepared", "inventory_blob_ref": "ak:blob:sha256:" + hashlib.sha256(jcs(empty_inventory)).hexdigest()}
    result = {"runner": {"kind": "named_suite", "entrypoint": "ak.suite.crypto.content_history.v1"}, "generated_by": "python -m tools.generate_content_history_fixture",
            "description": "RFC9420 exporter/ExpandWithLabel, original-byte Ed25519 and AES-GCM KAT. Signature is the explicitly stated primitive transcript, not an accepted Arkret Event or native authority proof. No product or storage durability claim.",
            "covers_vectors": [VECTOR], "event_kinds_covered": ["ak.mls.history_grant", "ak.mls.history_request", "ak.mls.history_recovery"],
            "recovery_preparation_encoding": {"authorization_event_ref": request_ref, "pending": pending, "prepared": prepared,
                                               "pending_jcs_hex": jcs(pending).hex(), "prepared_jcs_hex": jcs(prepared).hex(),
                                               "empty_inventory": empty_inventory, "inventory_jcs_hex": jcs(empty_inventory).hex(),
                                               "qualification": "Serialization-only coordinates; no native unit, empty-census completeness, Blob durability or current-holder authority is claimed."},
            "recovery_checkpoint": {"state": "ready", "pcr_cut": grant["history_cut"], "coverage_head_digest": "sha256:" + "1" * 64,
                                    "restored_event_count": "1", "cleanup_completed": True, "replacement": grant["recipient"],
                                    "inventory_blob_ref": "ak:blob:sha256:" + "2" * 64, "cleanup_blob_ref": "ak:blob:sha256:" + "3" * 64,
                                    "cleanup_inventory_digest": "sha256:" + "4" * 64},
            "hpke_grant": {"mnemonic": mnemonic, "recipient_private_hex": recipient_secret.hex(), "grant": grant, "entries": hpke_cases},
            "public_recovery_wire": json.loads((ROOT / "tools/content-history-public-wire.json").read_text(encoding="utf-8")),
            "external_recovery_binding": external_binding,
            "root_backup": {"envelope": backup, "plaintext": bag, "info_hex": backup_info.hex(), "aad_hex": backup_aad.hex(), "signing_hex": backup_signature_transcript.hex()},
            "security_evidence": [{"clause_id": "AK-NC-011", "vector_id": VECTOR, "decision_points": [
                {"id": "registered_scheme_and_original_crypto_binding", "requirement": "Unknown construction or changed original metadata/ciphertext fails closed; reconstructed domain-separated keys cannot decrypt across endpoint, purpose, epoch or strategy basis.", "evidence": ["/kat/envelope", "/kat/aad_hex", "/kat/key_hex", "/kat/signature_base64url"]}
            ]}],
            "local_message_authoring": {
                "strand_id": "ak:strand:AT3ARBdH1FM6GjXK9ulTx-YMvQOXys39dlUzZV6KyID9",
                "track_name": "discussion",
                "content": {
                    "kind": "mls", "encrypted_content": envelope, "encrypted_metadata": metadata_envelope,
                    "encryption_context": {
                        "scheme": SCHEME, "effective_scope": coordinate["effective_scope"],
                        "sender_domain": jcs(actor).decode(), "producer": context["producer"],
                        "outer_event_digest": "sha256:" + hashlib.sha256(jcs(outer)).hexdigest(),
                    },
                },
            },
            "metadata_kat": {"content_context": metadata_context, "key_hex": metadata_key.hex(),
                             "aad_hex": metadata_aad.hex(), "plaintext_hex": metadata_plaintext.hex(),
                             "envelope": metadata_envelope},
            "kat": {"exporter_secret_hex": exporter_secret.hex(), "root_context": coordinate, "root_hex": root.hex(),
                    "content_context": context, "key_hex": key.hex(), "aad_hex": associated.hex(), "outer_event": outer,
                    "source_event": source_event,
                    "envelope": envelope, "plaintext_hex": plaintext.hex(), "primitive_original_transcript_hex": original.hex(),
                    "signing_seed_hex": bytes(range(32)).hex(), "signature_base64url": b64(signer.sign(original)),
                    "original_digest": "sha256:" + hashlib.sha256(original).hexdigest()}}
    from tools.recovery_scope_cleanup import fixture as retirement_fixture
    # The recovering subject keeps its original PCR. Only this independent
    # ordinary Realm is eligible for the fixture's governance handoff.
    retirement_genesis = 'ak:event:' + b64(b'\x01' + bytes([209]) * 32)
    result['scope_retirement'] = retirement_fixture(replacement, {
        'effective_scope': {'kind': 'realm', 'realm_id': 'ak:realm:' + retirement_genesis.split(':', 2)[2]},
        'genesis_event_ref': retirement_genesis,
        'base_group_state_ref': 'ak:event:' + b64(b'\x01' + bytes([210]) * 32),
        'epoch': coordinate['epoch'], 'old_leaves': []}, preparation_cut)
    from tools.recovery_scope_cleanup import combination_fixture
    result['scope_retirement']['combination_boundaries'] = combination_fixture(result['scope_retirement'])
    result['attachment_key_receive'] = attachment_receive_vector(coordinate, root, context, outer, signer, grant, recipient_public)
    if include_sources:
        result['content_backup_source_encoding'] = {'human': human_source, 'agent': agent_source}
    return result


def source_fixture(document):
    cases = document.pop('content_backup_source_encoding')
    return {'runner': {'kind': 'named_suite', 'entrypoint': 'ak.suite.crypto.content_backup_source.v1'},
            'generated_by': 'python -m tools.generate_content_history_fixture',
            'description': 'Independent original Event, producer/service Ed25519, root AEAD and backup-source binding primitives. No native root PUT, physical retention, method-native Service qualification or allowed atomic-unit assertion.',
            'covers_vectors': [SOURCE_VECTOR], 'event_kinds_covered': ['ak.message.create'],
            'root_context': document['kat']['root_context'], 'root_hex': document['kat']['root_hex'],
            'cases': [{'name': name, **case, 'assertions': ['original Event content ID and real producer signature verify',
                'separate origin service signature and full original digest verify',
                'registered body and metadata decrypt with distinct keys',
                'validly re-signed wrong bindings, metadata omission, foreign Station and expiry reject']} for name, case in cases.items()],
            'security_evidence': [{'clause_id': 'AK-NC-131', 'vector_id': SOURCE_VECTOR,
                'decision_points': [{'id': 'explicit_origin_backup_source_binding',
                    'requirement': 'Real original producer and service Ed25519 bytes bind exact original Event, actual endpoint, scope, destination, every registered protection slot and bounded observation window; native role and storage remain external.',
                    'evidence': ['/cases/0', '/cases/1']}]}]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    document = build(include_sources=True)
    source = source_fixture(document)
    for path, value in [(OUTPUT, document), (SOURCE_OUTPUT, source)]:
        encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        if args.check:
            if path.read_text(encoding="utf-8") != encoded:
                raise SystemExit(f"{path.name}: deterministic KAT drift")
            print(f"{path.name}: deterministic KAT PASS")
        else:
            path.write_text(encoded, encoding="utf-8", newline="\n")
            print(f"{path.name} generated")


if __name__ == "__main__":
    main()
