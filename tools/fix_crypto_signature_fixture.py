#!/usr/bin/env python3
"""Recompute canonical digests and signatures in crypto-signature-fixture.json.

Idempotent: running it twice gives the same result. The fixture's
canonical_event_payload, canonical_binding_payload, protected_header,
test_private_key_jwk, and keygen_seed_b64u are the inputs; everything else is
derived.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "crypto-signature-fixture.json"


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def canonical_json_str(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sign_jws_input(jwk: dict, signing_input: bytes) -> bytes:
    if jwk.get("crv") == "Ed25519":
        return Ed25519PrivateKey.from_private_bytes(b64u_decode(jwk["d"])).sign(signing_input)
    if jwk.get("crv") == "P-256":
        private_value = int.from_bytes(b64u_decode(jwk["d"]), "big")
        private_key = ec.derive_private_key(private_value, ec.SECP256R1())
        der_signature = private_key.sign(
            signing_input,
            ec.ECDSA(hashes.SHA256(), deterministic_signing=True),
        )
        r, s = utils.decode_dss_signature(der_signature)
        return r.to_bytes(32, "big") + s.to_bytes(32, "big")
    raise SystemExit(f"unsupported crv: {jwk.get('crv')}")


def sign_mldsa65_vector(v: dict, binding_canon: bytes) -> None:
    try:
        from dilithium_py.ml_dsa import ML_DSA_65
    except ImportError as exc:
        raise SystemExit(
            "ML-DSA-65 regeneration requires dilithium-py>=1.4.0"
        ) from exc

    seed = b64u_decode(v["keygen_seed_b64u"])
    public_key, private_key = ML_DSA_65.key_derive(seed)
    recorded_public_key = b64u_decode(v["public_key_b64u"])
    if public_key != recorded_public_key:
        raise SystemExit("ML-DSA-65 derived public key differs from recorded fixture key")
    signature = ML_DSA_65.sign(private_key, binding_canon, deterministic=True)
    if not ML_DSA_65.verify(public_key, binding_canon, signature):
        raise SystemExit("ML-DSA-65 self-verification failed")
    v["signature_b64u"] = b64u(signature)


def regen_vector(v: dict) -> dict:
    event_without_proofs = v.get("event_without_proofs")
    if not isinstance(event_without_proofs, dict):
        raise SystemExit(f"missing event_without_proofs: {v.get('name')}")
    v["canonical_event_payload"] = canonical_json_str(event_without_proofs)
    canon = v["canonical_event_payload"].encode("utf-8")
    payload_digest = "sha256:" + hashlib.sha256(canon).hexdigest()
    v["payload_digest"] = payload_digest

    # event_digest is the digest of the canonical event payload (same bytes as
    # payload_digest). It is embedded in the binding object, the proof, and the
    # event_with_proof proofs, so propagate it before the binding is re-signed.
    event_digest = payload_digest
    v["event_digest"] = event_digest
    if "binding_object" in v and isinstance(v["binding_object"], dict):
        if "event_digest" in v["binding_object"]:
            v["binding_object"]["event_digest"] = event_digest
    if "proof" in v and isinstance(v["proof"], dict) and "event_digest" in v["proof"]:
        v["proof"]["event_digest"] = event_digest
    if "event_with_proof" in v and isinstance(v["event_with_proof"], dict):
        for p in v["event_with_proof"].get("proofs", []):
            if isinstance(p, dict) and "event_digest" in p:
                p["event_digest"] = event_digest

    # binding_digest from canonical_binding_payload (independent, but recompute
    # to be safe)
    binding_canon = v["canonical_binding_payload"].encode("utf-8")
    binding_digest = "sha256:" + hashlib.sha256(binding_canon).hexdigest()
    v["binding_digest"] = binding_digest

    # binding_object.payload_digest mirrors payload_digest; it is also already
    # canonicalized into canonical_binding_payload, so update both consistently
    if "binding_object" in v and isinstance(v["binding_object"], dict):
        v["binding_object"]["payload_digest"] = payload_digest
        # Recanonicalize the binding payload to match the new digest inside it
        new_binding_canon = canonical_json_str(v["binding_object"])
        if new_binding_canon != v["canonical_binding_payload"]:
            v["canonical_binding_payload"] = new_binding_canon
            binding_canon = new_binding_canon.encode("utf-8")
            binding_digest = "sha256:" + hashlib.sha256(binding_canon).hexdigest()
            v["binding_digest"] = binding_digest

    # detached_payload_b64u is base64url(canonical_binding_payload) — it's the
    # "payload" of the JWS, not the event bytes. Recompute.
    v["detached_payload_b64u"] = b64u(binding_canon)

    jwk = v.get("test_private_key_jwk")
    if not isinstance(jwk, dict):
        if v.get("signature_algorithm") == "ML-DSA-65":
            sign_mldsa65_vector(v, binding_canon)
            return v
        raise SystemExit(f"unsupported signature vector: {v.get('name')}")

    # JWS protected header b64u
    proto_canon = canonical_json_str(v["protected_header"])
    v["protected_header_canonical"] = proto_canon
    proto_b64 = b64u(proto_canon.encode("utf-8"))

    # Signing input is "<protected_b64>.<detached_payload_b64u>"
    signing_input = f"{proto_b64}.{v['detached_payload_b64u']}"
    v["jws_signing_input"] = signing_input

    sig = sign_jws_input(jwk, signing_input.encode("ascii"))
    sig_b64 = b64u(sig)

    # Detached JWS: header..signature (note: middle empty because payload is
    # detached)
    detached_jws = f"{proto_b64}..{sig_b64}"

    # Update proof and event_with_proof
    if "proof" in v and isinstance(v["proof"], dict):
        v["proof"]["payload_digest"] = payload_digest
        v["proof"]["jws"] = detached_jws

    if "event_with_proof" in v and isinstance(v["event_with_proof"], dict):
        proofs = v["event_with_proof"].get("proofs", [])
        for p in proofs:
            if isinstance(p, dict):
                p["payload_digest"] = payload_digest
                p["jws"] = detached_jws

    if isinstance(v.get("proof"), dict):
        event_with_proof = copy.deepcopy(event_without_proofs)
        event_with_proof["proofs"] = [copy.deepcopy(v["proof"])]
        v["event_with_proof"] = event_with_proof

    return v


def split_jws(jws: str) -> tuple[str, str, str]:
    parts = jws.split(".")
    if len(parts) != 3:
        raise SystemExit("invalid compact JWS in generated vector")
    return parts[0], parts[1], parts[2]


def find_case(cases: list[dict], name: str) -> dict:
    for case in cases:
        if case.get("name") == name:
            return case
    case = {"name": name}
    cases.append(case)
    return case


def regenerate_negative_cases(data: dict) -> None:
    vectors = {v.get("name"): v for v in data.get("vectors", []) if isinstance(v, dict)}
    ed = vectors["ak.vector.encoding.crypto.ed25519_detached_jws.v1"]
    es = vectors["ak.vector.encoding.crypto.es256_detached_jws.v1"]
    ml = vectors["ak.vector.encoding.crypto.mldsa65_raw_detached_signature.v1"]
    cases = data.setdefault("negative_cases", [])

    ed_header, _, ed_signature = split_jws(ed["proof"]["jws"])
    ed_signature_bytes = bytearray(b64u_decode(ed_signature))
    ed_signature_bytes[0] ^= 0x01
    case = find_case(cases, "reject_flipped_signature_bit")
    case["proof_jws"] = f"{ed_header}..{b64u(bytes(ed_signature_bytes))}"
    case["jws_signing_input"] = ed["jws_signing_input"]
    case["public_key_jwk"] = copy.deepcopy(ed["did_document_fragment"]["publicKeyJwk"])

    case = find_case(cases, "reject_alg_none")
    none_header = canonical_json_str(case["protected_header"]).encode("utf-8")
    case["proof_jws"] = f"{b64u(none_header)}..{ed_signature}"

    case = find_case(cases, "reject_alg_key_type_mismatch")
    mismatch_header = canonical_json_str(case["protected_header"])
    mismatch_input = f"{b64u(mismatch_header.encode('utf-8'))}.{ed['detached_payload_b64u']}"
    mismatch_signature = sign_jws_input(es["test_private_key_jwk"], mismatch_input.encode("ascii"))
    case["proof_jws"] = f"{b64u(mismatch_header.encode('utf-8'))}..{b64u(mismatch_signature)}"
    case["resolved_public_key_jwk"] = copy.deepcopy(ed["did_document_fragment"]["publicKeyJwk"])

    case = find_case(cases, "reject_truncated_public_key")
    case["proof_jws"] = ed["proof"]["jws"]
    truncated_ed = copy.deepcopy(ed["did_document_fragment"]["publicKeyJwk"])
    truncated_ed["x"] = b64u(b64u_decode(truncated_ed["x"])[:-1])
    case["public_key_jwk"] = truncated_ed

    case = find_case(cases, "reject_non_empty_payload_segment")
    case["proof_jws"] = f"{ed_header}.{ed['detached_payload_b64u']}.{ed_signature}"

    es_header, _, es_signature = split_jws(es["proof"]["jws"])
    case = find_case(cases, "reject_es256_truncated_signature")
    case.update(
        {
            "base_vector": es["name"],
            "description": "The ES256 JOSE signature is 63 bytes instead of the required raw 64-byte r||s form.",
            "proof_jws": f"{es_header}..{b64u(b64u_decode(es_signature)[:-1])}",
            "public_key_jwk": copy.deepcopy(es["did_document_fragment"]["publicKeyJwk"]),
            "expected": {
                "decision": "reject",
                "error_code": "invalid_signature",
                "reason": "ES256 detached JWS signatures MUST be exactly 64 raw bytes (r||s)",
            },
        }
    )

    case = find_case(cases, "reject_es256_truncated_public_key")
    truncated_es = copy.deepcopy(es["did_document_fragment"]["publicKeyJwk"])
    truncated_es["x"] = b64u(b64u_decode(truncated_es["x"])[:-1])
    case.update(
        {
            "base_vector": es["name"],
            "description": "The P-256 x coordinate is truncated to 31 bytes while the detached JWS is otherwise valid.",
            "proof_jws": es["proof"]["jws"],
            "public_key_jwk": truncated_es,
            "expected": {
                "decision": "reject",
                "error_code": "invalid_signature",
                "reason": "ES256 verification keys MUST contain valid 32-byte P-256 x and y coordinates",
            },
        }
    )

    case = find_case(cases, "reject_mldsa65_truncated_signature")
    case.update(
        {
            "base_vector": ml["name"],
            "description": "The ML-DSA-65 raw signature is truncated by one byte.",
            "signature_b64u": b64u(b64u_decode(ml["signature_b64u"])[:-1]),
            "public_key_b64u": ml["public_key_b64u"],
            "expected": {
                "decision": "reject",
                "error_code": "invalid_signature",
                "reason": "ML-DSA-65 signatures MUST have the exact FIPS 204 byte length",
            },
        }
    )

    case = find_case(cases, "reject_mldsa65_truncated_public_key")
    case.update(
        {
            "base_vector": ml["name"],
            "description": "The ML-DSA-65 public key is truncated by one byte while the signature is otherwise valid.",
            "signature_b64u": ml["signature_b64u"],
            "public_key_b64u": b64u(b64u_decode(ml["public_key_b64u"])[:-1]),
            "expected": {
                "decision": "reject",
                "error_code": "invalid_signature",
                "reason": "ML-DSA-65 public keys MUST have the exact FIPS 204 byte length",
            },
        }
    )


def main() -> int:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for v in data.get("vectors", []):
        regen_vector(v)
    regenerate_negative_cases(data)
    with FIXTURE.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"updated {FIXTURE.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
