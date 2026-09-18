#!/usr/bin/env python3
"""Regenerate the byte-exact moderation franking-proof signature fixture."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from tools.artifact_lint.core import canonical_json  # noqa: E402

FIXTURE = ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "franking-proof-transcript-fixture.json"
DOMAIN = "ak.franking_proof.signature.v1"
PRIVATE_SEED = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"
PUBLIC_KEY = "A6EHv_POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg"


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def build_fixture() -> dict[str, Any]:
    payload = {
        "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
        "event_id": "ak:event:AR8bu-n-kOOB3nRUvYuIEglCX5B-JpFaNTex9gxs_cWY",
        "received_by": "ak:did_core:webvh:z6mkfixtureprincipalexample",
        "verification_method": "did:webvh:z6mkfixture:principal.example#ed25519-2026-05-fixture",
        "received_at": "2026-05-02T00:00:00.000Z",
        "replay_nonce": "ZnJhbmtpbmctbm9uY2UtMDE",
    }
    transcript = {"domain": DOMAIN, **payload}
    transcript_jcs = canonical_json(transcript)
    seed = base64.urlsafe_b64decode(PRIVATE_SEED + "=" * (-len(PRIVATE_SEED) % 4))
    private_key = Ed25519PrivateKey.from_private_bytes(seed)
    signature = b64u(private_key.sign(transcript_jcs.encode("utf-8")))

    mutations: list[dict[str, Any]] = []
    replacements: dict[str, Any] = {
        "domain": "ak.franking_proof.signature.invalid.v1",
        "realm_id": "ak:realm:AY4dIxVSke8SdwIRtzd0nLP5OqzL02oENbMkSGDf0lu8",
        "event_id": "ak:event:AYPZ73QecBPnUvir4K5wgH_jtDMWOCIHOY7rhzIZ5vUK",
        "received_by": "ak:did_core:webvh:z6mkotherprincipalexample",
        "verification_method": "did:webvh:z6mkfixture:principal.example#rotated-key",
        "received_at": "2026-05-02T00:00:01.000Z",
        "replay_nonce": "ZnJhbmtpbmctbm9uY2UtMDI",
    }
    for field in transcript:
        mutated = dict(transcript)
        mutated[field] = replacements[field]
        mutations.append(
            {
                "field": field,
                "transcript": mutated,
                "expected_result": "reject_signature_invalid",
            }
        )

    return {
        "suite": "franking_proof_transcript",
        "vector_id": "ak.vector.moderation.franking_proof_transcript.v1",
        "runner": {
            "kind": "named_suite",
            "entrypoint": "ak.suite.moderation.franking_proof_transcript.v1",
        },
        "generated_by": "tools/regenerate_franking_proof_transcript_fixture.py",
        "domain": DOMAIN,
        "schema_ref": "schemas/moderation-evidence.schema.json#/$defs/franking_proof",
        "test_key": {
            "algorithm": "Ed25519",
            "private_key_seed": PRIVATE_SEED,
            "public_key": PUBLIC_KEY,
            "note": "Public conformance test key only: the private key ships with the specification, so a valid signature over it proves nothing about the signer. Registered in artifacts/registry/test-material-registry.json; formal verification, authorization and trust-admission paths MUST refuse it and the reserved identifiers it uses. See zh/identity/did-usage-and-verification.md section 8.",
        },
        "case": {
            "source_payload": {**payload, "signature": signature},
            "removed_members": ["signature"],
            "transcript": transcript,
            "transcript_jcs": transcript_jcs,
            "transcript_digest": "sha256:" + hashlib.sha256(transcript_jcs.encode("utf-8")).hexdigest(),
            "signature_b64u": signature,
            "expected_result": "accept",
            "bound_field_mutations": mutations,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build_fixture(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not FIXTURE.is_file() or FIXTURE.read_text(encoding="utf-8") != rendered:
            print(f"generated fixture drift: {FIXTURE.relative_to(ROOT).as_posix()}", file=sys.stderr)
            return 1
        return 0
    FIXTURE.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
