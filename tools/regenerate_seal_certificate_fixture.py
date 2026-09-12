#!/usr/bin/env python3
"""Generate a serialization/signature KAT, not a consensus execution proof."""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from tools.artifact_lint.core import canonical_json
from tools.regenerate_proof_context_transcript_fixture import TEST_KEY


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def digest(value: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode()).hexdigest()


def main() -> None:
    path = ROOT / "spec/v1/artifacts/fixtures/cbs-lattice-fixture.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    vector = next(v for v in fixture["vectors"] if v["name"] == "seal_canonical_no_self_reference")
    body = vector["seal_body"]
    body["configuration_ref"] = "ak:event:AYdKcd4Mb1IzAPoctcZYEVvHLuvqQFdhPu0jBrZv-M0Q"
    body["delta"] = []
    body["command_results"] = []
    transcript = {
        "context": "ak.seal.commit.v1", "seal_digest": digest(body),
    }
    header = b64(canonical_json({"alg": "Ed25519", "kid": TEST_KEY["kid"]}).encode())
    payload = b64(canonical_json(transcript).encode())
    signing_input = (header + "." + payload).encode("ascii")
    key = Ed25519PrivateKey.from_private_bytes(base64.urlsafe_b64decode(TEST_KEY["private_key_seed"] + "="))
    certificate = {
        "verification_method": TEST_KEY["kid"], "payload_digest": digest(transcript),
        "jws": header + ".." + b64(key.sign(signing_input)),
    }
    vector["description"] = "Byte-level body identity and commit certificate KAT. Symbolic predecessor roots are not an execution-validity proof."
    vector["test_key"] = TEST_KEY
    vector["commit_transcript"] = transcript
    vector["certificate"] = certificate
    vector["expected"] = {"id": "ak:seal:" + digest(body),
                          "notary_signature_payload_digest": digest(transcript), "valid_result": "accept"}
    fixture_text = json.dumps(fixture, ensure_ascii=False, indent=2) + "\n"
    if "--check" in sys.argv:
        if path.read_text(encoding="utf-8") != fixture_text:
            raise SystemExit("Seal certificate fixture drift")
    else:
        path.write_text(fixture_text, encoding="utf-8")


if __name__ == "__main__":
    main()
