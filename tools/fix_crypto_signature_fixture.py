#!/usr/bin/env python3
"""Recompute payload_digest and re-sign the JWS in
crypto-signature-fixture.json after the ULID→UUIDv7 migration changed
the canonical event bytes.

Idempotent: running it twice gives the same result. The fixture's
canonical_event_payload, canonical_binding_payload, protected_header,
and test_private_key_jwk are the inputs; everything else is derived.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)
from cryptography.hazmat.primitives import serialization

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "crypto-signature-fixture.json"


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def canonical_json_str(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def regen_vector(v: dict) -> dict:
    canon = v["canonical_event_payload"].encode("utf-8")
    payload_digest = "sha256:" + hashlib.sha256(canon).hexdigest()
    v["payload_digest"] = payload_digest

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

    # JWS protected header b64u
    proto_canon = canonical_json_str(v["protected_header"])
    v["protected_header_canonical"] = proto_canon
    proto_b64 = b64u(proto_canon.encode("utf-8"))

    # Signing input is "<protected_b64>.<detached_payload_b64u>"
    signing_input = f"{proto_b64}.{v['detached_payload_b64u']}"
    v["jws_signing_input"] = signing_input

    # Sign with Ed25519 private key from JWK
    jwk = v["test_private_key_jwk"]
    if jwk["crv"] != "Ed25519":
        raise SystemExit(f"unsupported crv: {jwk['crv']}")
    d_bytes = b64u_decode(jwk["d"])
    sk = Ed25519PrivateKey.from_private_bytes(d_bytes)
    sig = sk.sign(signing_input.encode("ascii"))
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

    return v


def main() -> int:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for v in data.get("vectors", []):
        regen_vector(v)
    FIXTURE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"updated {FIXTURE.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
