"""Generate deterministic primitive KATs, not a native admission simulation."""
import argparse
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from tools.content_history import SCHEME, STRATEGY, aad, b64, content_key, content_root, jcs, key_commitment, root_ref

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "spec/v1/artifacts/fixtures/content-history-fixture.json"
VECTOR = "ak.vector.crypto.content_history.v1"


def build():
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
    return {"runner": {"kind": "named_suite", "entrypoint": "ak.suite.crypto.content_history.v1"}, "generated_by": "python -m tools.generate_content_history_fixture",
            "description": "RFC9420 exporter/ExpandWithLabel, original-byte Ed25519 and AES-GCM KAT. Signature is the explicitly stated primitive transcript, not an accepted Arkret Event or native authority proof. No product or storage durability claim.",
            "covers_vectors": [VECTOR], "event_kinds_covered": ["ak.mls.history_grant"],
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
