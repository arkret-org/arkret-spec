"""Generate deterministic primitive KATs, not a native admission simulation."""
import argparse
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from tools.content_history import SCHEME, STRATEGY, aad, b64, content_key, content_root, jcs, key_commitment, root_ref, hpke_seal, grant_header, mnemonic_backup_key, did_key

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "spec/v1/artifacts/fixtures/content-history-fixture.json"
VECTOR = "ak.vector.crypto.content_history.v1"


def build():
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
    original = jcs({"outer_event": outer, "envelope": envelope})
    mnemonic = " ".join(["abandon"] * 23 + ["art"])
    recipient_secret, recipient_public = mnemonic_backup_key(mnemonic)
    cut = {"event_id": event_ref, "commit_id": "ak:realm_commit:" + b64(b"\x01" + bytes([0x43]) * 32),
           "stream_ref": coordinate["effective_scope"], "stream_position": 0}
    request_ref = "ak:event:" + b64(b"\x01" + bytes([0x42]) * 32)
    grant = {"recipient": context["producer"], "recipient_hpke_key_base64url": b64(recipient_public),
             "recipient_key_event_ref": request_ref, "history_cut": cut,
             "expires_at": "2026-11-08T00:15:00.000Z", "entries": []}
    hpke_cases = []
    for index, selected_key in enumerate((key, root)):
        selector = {"kind": "content_key", "source_event_ref": event_ref, "content_path": "/payload"} if index == 0 else {
            "kind": "epoch_root", "root_context": coordinate, "root_ref": context["root_ref"], "closed_epoch_cut": cut}
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
    return {"runner": {"kind": "named_suite", "entrypoint": "ak.suite.crypto.content_history.v1"}, "generated_by": "python -m tools.generate_content_history_fixture",
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
            "kat": {"exporter_secret_hex": exporter_secret.hex(), "root_context": coordinate, "root_hex": root.hex(),
                    "content_context": context, "key_hex": key.hex(), "aad_hex": associated.hex(), "outer_event": outer,
                    "envelope": envelope, "plaintext_hex": plaintext.hex(), "primitive_original_transcript_hex": original.hex(),
                    "signing_seed_hex": bytes(range(32)).hex(), "signature_base64url": b64(signer.sign(original)),
                    "original_digest": "sha256:" + hashlib.sha256(original).hexdigest()}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != encoded:
            raise SystemExit("content history KAT drift")
        print("content history deterministic KAT: PASS")
    else:
        OUTPUT.write_text(encoded, encoding="utf-8", newline="\n")
        print("content-history-fixture.json generated")


if __name__ == "__main__":
    main()
