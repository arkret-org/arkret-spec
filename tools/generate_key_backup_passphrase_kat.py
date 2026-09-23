"""Recompute the v1 passphrase key-backup KAT.

Requires argon2-cffi and PyNaCl. This generator uses Python crypto libraries
independently of the Rust producer and Cotest runner.
"""

import base64
import hashlib
import hmac
import json
import subprocess
from pathlib import Path

from argon2.low_level import Type, hash_secret_raw
from nacl.bindings import crypto_aead_xchacha20poly1305_ietf_encrypt


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec/v1/artifacts/fixtures/key-backup-hardening-fixture.json"
VECTOR_ID = "ak.vector.key_backup.passphrase_kdf_kat.v1"
PROFILE = "ak.aead.xchacha20_poly1305.v1"


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def jcs(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def subkey(root: bytes, info: str) -> bytes:
    prk = hmac.new(bytes(32), root, hashlib.sha256).digest()
    return hmac.new(prk, info.encode("utf-8") + b"\x01", hashlib.sha256).digest()


def main() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    passphrase = "correct horse battery staple"
    salt = bytes(range(16))
    nonce_salt = bytes(range(16, 32))
    actor_id = {
        "kind": "account",
        "account_id": {
            "principal_id": "ak:did_core:webvh:z6mkfixture",
            "station_id": "ak:did_core:web:station.example",
        },
    }
    binding = {
        "backup_id": "ak:backup:01964137-0000-7000-8000-000000000000",
        "actor_id": actor_id,
        "device_id": None,
        "backup_kind": "secret_storage",
        "backup_version": "kb_1",
        "created_at": "2026-08-24T00:00:00.000Z",
        "subdomain": "recovery_vault",
        "item_kinds": ["private_account_state"],
        "recipient_method": "passphrase_kdf",
    }
    plaintext = {
        "backup_kind": "secret_storage",
        "items": [{
            "item_kind": "private_account_state",
            "secret_id": "account.state",
            "secret_b64u": "c2VjcmV0LW9uZQ",
            "secret_generation": 3,
        }],
    }
    aad = {key: binding[key] for key in (
        "actor_id", "device_id", "backup_kind", "backup_version",
        "created_at", "item_kinds", "recipient_method",
    )}
    aad["schema"] = "ak.schema.key_backup.v1"
    nonce_transcript = {key: binding[key] for key in (
        "backup_id", "actor_id", "device_id", "backup_kind",
        "backup_version", "created_at",
    )}
    nonce_transcript.update({
        "aead": "xchacha20_poly1305",
        "aead_profile": PROFILE,
        "nonce_salt": b64u(nonce_salt),
    })
    aad_bytes = jcs(aad)
    nonce_bytes = jcs(nonce_transcript)
    plaintext_bytes = jcs(plaintext)
    algorithms = []
    for name, params in (
        ("argon2id", {"memory_kib": 65536, "iterations": 3, "parallelism": 1}),
        ("pbkdf2", {"iterations": 600000, "digest_algorithm": "sha512"}),
    ):
        if name == "argon2id":
            root = hash_secret_raw(passphrase.encode(), salt, time_cost=3,
                                   memory_cost=65536, parallelism=1, hash_len=32,
                                   type=Type.ID, version=19)
        else:
            root = hashlib.pbkdf2_hmac("sha512", passphrase.encode(), salt, 600000, 32)
        aead_key = subkey(root, "arkret-key-backup/secret_storage/recovery_vault/v1")
        commitment_key = subkey(root, "arkret-key-backup/secret_storage/commitment/v1")
        nonce_key = subkey(root, "arkret-key-backup-aead-nonce-v1")
        nonce = hmac.new(nonce_key, nonce_bytes, hashlib.sha256).digest()[:24]
        ciphertext = crypto_aead_xchacha20poly1305_ietf_encrypt(
            plaintext_bytes, aad_bytes, nonce, aead_key)
        algorithms.append({
            "name": name,
            "kdf": {
                "name": name,
                "salt": b64u(salt),
                "params": params,
                **({"degraded_profile_reason": "platform_memory_hard_kdf_unavailable"}
                   if name == "pbkdf2" else {}),
            },
            "expected": {
                "root_key_hex": root.hex(),
                "aead_key_hex": aead_key.hex(),
                "commitment_key_hex": commitment_key.hex(),
                "nonce_key_hex": nonce_key.hex(),
                "key_commitment": "sha256:" + hashlib.sha256(commitment_key).hexdigest(),
                "nonce_b64u": b64u(nonce),
                "ciphertext_b64u": b64u(ciphertext),
                "ciphertext_digest": "sha256:" + hashlib.sha256(ciphertext).hexdigest(),
            },
        })
    case = {
        "name": "passphrase_kdf_kat",
        "vector_id": VECTOR_ID,
        "kind": "passphrase_kdf_crypto",
        "passphrase_utf8": passphrase,
        "binding": binding,
        "salt_b64u": b64u(salt),
        "nonce_salt_b64u": b64u(nonce_salt),
        "aad_canonical_json": aad_bytes.decode(),
        "nonce_transcript_canonical_json": nonce_bytes.decode(),
        "plaintext_canonical_json": plaintext_bytes.decode(),
        "algorithms": algorithms,
        "assertions": [
            "Argon2id v0x13 and PBKDF2-HMAC-SHA512 at the v1 floors derive the exact 32-byte roots",
            "HKDF-SHA256 keys, raw-key commitment, deterministic nonce, AAD and XChaCha20-Poly1305 ciphertext match the pinned bytes",
            "Wrong passphrase, modified parameters, commitment, nonce or AAD are rejected",
        ],
    }
    fixture["cases"] = [row for row in fixture["cases"] if row.get("vector_id") != VECTOR_ID]
    fixture["cases"].append(case)
    fixture["version"] = "2026-09-24.4"
    FIXTURE.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    subprocess.run(["node", "tools/regenerate_key_backup_hardening_kat.mjs"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
