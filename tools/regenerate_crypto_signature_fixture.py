#!/usr/bin/env python3
"""Regenerate the canonical chain and signatures in the crypto fixture."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, utils


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "crypto-signature-fixture.json"
WEBSOCKET_FIXTURE = (
    ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "websocket-binding-fixture.json"
)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def unb64u(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def digest(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def event_id(event_digest: str) -> str:
    return "ak:event:" + b64u(b"\x01" + bytes.fromhex(event_digest.removeprefix("sha256:")))


def refresh_common(vector: dict[str, object]) -> bytes:
    for key in ("event_without_proofs", "event_with_proof"):
        candidate = vector.get(key)
        if isinstance(candidate, dict) and candidate.get("refs") == []:
            candidate.pop("refs")
        if isinstance(candidate, dict) and candidate.get("causal_refs") == []:
            candidate.pop("causal_refs")
    event = dict(vector["event_without_proofs"])
    for field in ("unsigned", "event_id", "proofs"):
        event.pop(field, None)
    event_bytes = canonical(event)
    event_digest = digest(event_bytes)
    vector["canonical_event_payload"] = event_bytes.decode()
    vector["event_digest"] = event_digest

    derived_event_id = event_id(event_digest)
    vector["event_without_proofs"]["event_id"] = derived_event_id
    if isinstance(vector.get("event_with_proof"), dict):
        vector["event_with_proof"]["event_id"] = derived_event_id

    binding = vector["binding_object"]
    binding["event_digest"] = event_digest
    binding["actor_id"] = event["actor_id"]
    binding_bytes = canonical(binding)
    vector["canonical_binding_payload"] = binding_bytes.decode()
    vector["binding_digest"] = digest(binding_bytes)
    vector["detached_payload_b64u"] = b64u(binding_bytes)

    proof = vector.get("proof")
    if isinstance(proof, dict):
        proof["event_digest"] = event_digest
    with_proof = vector.get("event_with_proof")
    if isinstance(with_proof, dict):
        for embedded_proof in with_proof.get("proofs", []):
            embedded_proof["event_digest"] = event_digest
    return binding_bytes


def refresh_jws(vector: dict[str, object], binding_bytes: bytes) -> bytes:
    header_bytes = canonical(vector["protected_header"])
    vector["protected_header_canonical"] = header_bytes.decode()
    signing_input = f"{b64u(header_bytes)}.{b64u(binding_bytes)}".encode()
    vector["jws_signing_input"] = signing_input.decode()
    return signing_input


def refresh_ed25519(vector: dict[str, object], signing_input: bytes) -> bytes:
    seed = unb64u(vector["test_private_key_jwk"]["d"])
    signature = ed25519.Ed25519PrivateKey.from_private_bytes(seed).sign(signing_input)
    jws = f"{signing_input.decode().split('.', 1)[0]}..{b64u(signature)}"
    vector["proof"]["jws"] = jws
    vector["event_with_proof"]["proofs"][0]["jws"] = jws
    return signature


def refresh_es256(vector: dict[str, object], signing_input: bytes) -> bytes:
    private_value = int.from_bytes(unb64u(vector["test_private_key_jwk"]["d"]), "big")
    private_key = ec.derive_private_key(private_value, ec.SECP256R1())
    der = private_key.sign(
        signing_input,
        ec.ECDSA(hashes.SHA256(), deterministic_signing=True),
    )
    r, s = utils.decode_dss_signature(der)
    signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    jws = f"{signing_input.decode().split('.', 1)[0]}..{b64u(signature)}"
    vector["proof"]["jws"] = jws
    vector["event_with_proof"]["proofs"][0]["jws"] = jws
    return signature


def refresh_mldsa65(vector: dict[str, object], binding_bytes: bytes) -> tuple[bytes, bytes]:
    seed_hex = unb64u(vector["keygen_seed_b64u"]).hex()
    with tempfile.TemporaryDirectory(prefix="arkret-mldsa-") as directory:
        temp = Path(directory)
        private_key = temp / "private.pem"
        public_key = temp / "public.der"
        message = temp / "message.bin"
        signature = temp / "signature.bin"
        subprocess.run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "ML-DSA-65",
                "-pkeyopt",
                f"hexseed:{seed_hex}",
                "-out",
                str(private_key),
            ],
            check=True,
        )
        subprocess.run(
            [
                "openssl",
                "pkey",
                "-in",
                str(private_key),
                "-pubout",
                "-outform",
                "DER",
                "-out",
                str(public_key),
            ],
            check=True,
        )
        message.write_bytes(binding_bytes)
        subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-sign",
                "-rawin",
                "-inkey",
                str(private_key),
                "-in",
                str(message),
                "-out",
                str(signature),
                "-pkeyopt",
                "deterministic:1",
            ],
            check=True,
        )
        public_raw = public_key.read_bytes()[-1952:]
        signature_raw = signature.read_bytes()
    if len(public_raw) != 1952 or len(signature_raw) != 3309:
        raise ValueError("unexpected ML-DSA-65 public key or signature length")
    vector["public_key_b64u"] = b64u(public_raw)
    vector["signature_b64u"] = b64u(signature_raw)
    return public_raw, signature_raw


def refresh_negative_cases(
    data: dict[str, object],
    ed_vector: dict[str, object],
    ed_signature: bytes,
    es_vector: dict[str, object],
    es_signature: bytes,
    ml_public: bytes,
    ml_signature: bytes,
) -> None:
    cases = {case["name"]: case for case in data["negative_cases"]}
    ed_header = ed_vector["jws_signing_input"].split(".", 1)[0]
    es_header = es_vector["jws_signing_input"].split(".", 1)[0]
    flipped = bytes([ed_signature[0] ^ 1]) + ed_signature[1:]
    cases["reject_flipped_signature_bit"]["proof_jws"] = f"{ed_header}..{b64u(flipped)}"
    cases["reject_flipped_signature_bit"]["jws_signing_input"] = ed_vector["jws_signing_input"]
    cases["reject_truncated_public_key"]["proof_jws"] = ed_vector["proof"]["jws"]
    cases["reject_non_empty_payload_segment"]["proof_jws"] = (
        f"{ed_header}.e30.{b64u(ed_signature)}"
    )
    for name in ("reject_alg_none", "reject_alg_key_type_mismatch"):
        header = b64u(canonical(cases[name]["protected_header"]))
        cases[name]["proof_jws"] = f"{header}..{b64u(ed_signature)}"

    cases["reject_es256_truncated_signature"]["proof_jws"] = (
        f"{es_header}..{b64u(es_signature[:-1])}"
    )
    cases["reject_es256_truncated_public_key"]["proof_jws"] = es_vector["proof"]["jws"]
    cases["reject_mldsa65_truncated_signature"]["signature_b64u"] = b64u(ml_signature[:-1])
    cases["reject_mldsa65_truncated_signature"]["public_key_b64u"] = b64u(ml_public)
    cases["reject_mldsa65_truncated_public_key"]["signature_b64u"] = b64u(ml_signature)
    cases["reject_mldsa65_truncated_public_key"]["public_key_b64u"] = b64u(ml_public[:-1])


def sync_websocket_fixture(event_with_proof: dict[str, object]) -> None:
    data = json.loads(WEBSOCKET_FIXTURE.read_text(encoding="utf-8"))
    admitted = copy.deepcopy(event_with_proof)
    for case in data.get("frame_schema_cases", []):
        wire = case.get("wire_utf8")
        if not isinstance(wire, str):
            continue
        frame = json.loads(wire)
        payload = frame.get("payload", {})
        if payload.get("kind") == "event" and isinstance(payload.get("payload"), dict):
            payload["payload"] = admitted
            case["wire_utf8"] = canonical(frame).decode()
    WEBSOCKET_FIXTURE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def main() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    authority_ref = "ak:seal:sha256:" + "1" * 64
    signer_evidence_ref = "ak:signer_evidence:sha256:" + "e" * 64
    for vector in data["vectors"]:
        for field in ("event_without_proofs", "event_with_proof"):
            event = vector.get(field)
            if isinstance(event, dict) and "actor_id" in event:
                event["actor_id"] = {
                    "kind": "account",
                    "account_id": {
                        "principal_id": "ak:did_core:webvh:z6mkfixture",
                        "station_id": "ak:did_core:webvh:z6mkfixturestationexample",
                    },
                }
                event.pop("station_id", None)
                event.pop("seal_ref", None)
                event.setdefault("auth_context", {})["authority_refs"] = [authority_ref]
                for proof in event.get("proofs", []):
                    proof["signer_resolution_evidence_ref"] = signer_evidence_ref
        proof = vector.get("proof")
        if isinstance(proof, dict):
            proof["signer_resolution_evidence_ref"] = signer_evidence_ref
        binding = vector.get("binding_object")
        if isinstance(binding, dict):
            binding["signer_resolution_evidence_ref"] = signer_evidence_ref
    vectors = {vector["name"]: vector for vector in data["vectors"]}
    ed = vectors["ak.vector.encoding.crypto.ed25519_detached_jws.v1"]
    es = vectors["ak.vector.encoding.crypto.es256_detached_jws.v1"]
    ml = vectors["ak.vector.encoding.crypto.mldsa65_raw_detached_signature.v1"]

    ed_binding = refresh_common(ed)
    es_binding = refresh_common(es)
    ml_binding = refresh_common(ml)
    ed_signature = refresh_ed25519(ed, refresh_jws(ed, ed_binding))
    es_signature = refresh_es256(es, refresh_jws(es, es_binding))
    ml_public, ml_signature = refresh_mldsa65(ml, ml_binding)
    refresh_negative_cases(data, ed, ed_signature, es, es_signature, ml_public, ml_signature)

    FIXTURE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    sync_websocket_fixture(ed["event_with_proof"])
    print("crypto signature fixture regenerated")


if __name__ == "__main__":
    main()
