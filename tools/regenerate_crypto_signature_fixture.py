#!/usr/bin/env python3
"""Regenerate the canonical binding bytes and signatures of crypto-signature-fixture.json.

The fixture holds three detached-signature KATs (Ed25519 and ES256 detached
JWS, raw ML-DSA-65) over canonical proof binding objects, plus nine
algorithm-specific negatives. Edit a vector's ``binding_object`` (or its
protected header), then run this script: it recomputes the RFC 8785 binding
payload, its SHA-256 digest, the detached payload / JWS signing input, and every
signature from the published conformance keys, then refreshes the negatives.

Every signature is deterministic -- Ed25519, RFC 6979 ES256 and
``openssl pkeyutl -pkeyopt deterministic:1`` ML-DSA-65 from the recorded FIPS 204
seed -- so an unchanged fixture regenerates byte for byte. ``--check`` reports
drift without writing. Requires ``cryptography`` and an ``openssl`` (3.5+) with
ML-DSA-65.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, utils

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "crypto-signature-fixture.json"
ED25519 = "ak.vector.encoding.crypto.ed25519_detached_jws.v1"
ES256 = "ak.vector.encoding.crypto.es256_detached_jws.v1"
MLDSA65 = "ak.vector.encoding.crypto.mldsa65_raw_detached_signature.v1"


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def unb64u(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def refresh_binding(vector: dict[str, Any]) -> bytes:
    binding = canonical(vector["binding_object"])
    vector["canonical_binding_payload"] = binding.decode()
    vector["binding_digest"] = digest(binding)
    vector["detached_payload_b64u"] = b64u(binding)
    return binding


def refresh_jws_input(vector: dict[str, Any], binding: bytes) -> bytes:
    header = canonical(vector["protected_header"])
    vector["protected_header_canonical"] = header.decode()
    signing_input = f"{b64u(header)}.{b64u(binding)}".encode()
    vector["jws_signing_input"] = signing_input.decode()
    return signing_input


def sign_ed25519(seed_b64u: str, message: bytes) -> bytes:
    return ed25519.Ed25519PrivateKey.from_private_bytes(unb64u(seed_b64u)).sign(message)


def sign_es256(d_b64u: str, message: bytes) -> bytes:
    key = ec.derive_private_key(int.from_bytes(unb64u(d_b64u), "big"), ec.SECP256R1())
    der = key.sign(message, ec.ECDSA(hashes.SHA256(), deterministic_signing=True))
    r, s = utils.decode_dss_signature(der)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def sign_mldsa65(vector: dict[str, Any], binding: bytes) -> tuple[bytes, bytes]:
    seed_hex = unb64u(vector["keygen_seed_b64u"]).hex()
    with tempfile.TemporaryDirectory(prefix="arkret-mldsa-") as directory:
        temp = Path(directory)
        key, public, message, signature = (temp / name for name in ("key.pem", "pub.der", "msg", "sig"))
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "ML-DSA-65", "-pkeyopt", f"hexseed:{seed_hex}", "-out", str(key)],
            check=True,
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(key), "-pubout", "-outform", "DER", "-out", str(public)],
            check=True,
        )
        message.write_bytes(binding)
        subprocess.run(
            [
                "openssl", "pkeyutl", "-sign", "-rawin", "-inkey", str(key), "-in", str(message),
                "-out", str(signature), "-pkeyopt", "deterministic:1",
            ],
            check=True,
        )
        public_raw = public.read_bytes()[-1952:]
        signature_raw = signature.read_bytes()
    if len(public_raw) != 1952 or len(signature_raw) != 3309:
        raise ValueError("unexpected ML-DSA-65 public key or signature length")
    vector["public_key_b64u"] = b64u(public_raw)
    vector["signature_b64u"] = b64u(signature_raw)
    return public_raw, signature_raw


def regenerate(data: dict[str, Any]) -> None:
    vectors = {vector["name"]: vector for vector in data["vectors"]}
    ed, es, ml = vectors[ED25519], vectors[ES256], vectors[MLDSA65]

    ed_binding = refresh_binding(ed)
    ed_input = refresh_jws_input(ed, ed_binding)
    ed_signature = sign_ed25519(ed["test_private_key_jwk"]["d"], ed_input)
    ed_header = ed_input.decode().split(".", 1)[0]
    ed["proof"]["jws"] = f"{ed_header}..{b64u(ed_signature)}"

    es_binding = refresh_binding(es)
    es_input = refresh_jws_input(es, es_binding)
    es_signature = sign_es256(es["test_private_key_jwk"]["d"], es_input)
    es_header = es_input.decode().split(".", 1)[0]
    es["proof"]["jws"] = f"{es_header}..{b64u(es_signature)}"

    ml_public, ml_signature = sign_mldsa65(ml, refresh_binding(ml))

    cases = {case["name"]: case for case in data["negative_cases"]}
    flipped = bytes([ed_signature[0] ^ 1]) + ed_signature[1:]
    cases["reject_flipped_signature_bit"]["proof_jws"] = f"{ed_header}..{b64u(flipped)}"
    cases["reject_flipped_signature_bit"]["jws_signing_input"] = ed["jws_signing_input"]
    cases["reject_truncated_public_key"]["proof_jws"] = ed["proof"]["jws"]
    cases["reject_non_empty_payload_segment"]["proof_jws"] = f"{ed_header}.e30.{b64u(ed_signature)}"
    # Both header-substitution negatives keep well-formed signature bytes (the
    # valid Ed25519 signature) so rejection must come from alg handling.
    for name in ("reject_alg_none", "reject_alg_key_type_mismatch"):
        header = b64u(canonical(cases[name]["protected_header"]))
        cases[name]["proof_jws"] = f"{header}..{b64u(ed_signature)}"
    cases["reject_es256_truncated_signature"]["proof_jws"] = f"{es_header}..{b64u(es_signature[:-1])}"
    cases["reject_es256_truncated_public_key"]["proof_jws"] = es["proof"]["jws"]
    cases["reject_mldsa65_truncated_signature"]["signature_b64u"] = b64u(ml_signature[:-1])
    cases["reject_mldsa65_truncated_signature"]["public_key_b64u"] = b64u(ml_public)
    cases["reject_mldsa65_truncated_public_key"]["signature_b64u"] = b64u(ml_signature)
    cases["reject_mldsa65_truncated_public_key"]["public_key_b64u"] = b64u(ml_public[:-1])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    args = parser.parse_args(argv)
    original = FIXTURE.read_text(encoding="utf-8")
    data = json.loads(original)
    regenerate(data)
    rendered = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if rendered != original:
            print(f"{FIXTURE.relative_to(ROOT)}: regenerated bytes differ; run without --check")
            return 1
        print(f"{FIXTURE.relative_to(ROOT)}: up to date")
        return 0
    FIXTURE.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"{FIXTURE.relative_to(ROOT)}: regenerated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
