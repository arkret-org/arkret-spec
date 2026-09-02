#!/usr/bin/env python3
"""Check the closed HandleClaim core/status/revocation transcripts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "handle-claim-kat.json"


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(domain: str, value: object) -> str:
    preimage = f"{domain}\n{canonical(value)}".encode()
    return f"sha256:{hashlib.sha256(preimage).hexdigest()}"


def main() -> int:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    core = fixture["core"]
    core_projection = {
        key: value for key, value in core["preimage"].items() if key != "proofs"
    }
    core_digest = digest(core["domain"], core_projection)
    if core_digest != core["expected_digest"]:
        raise SystemExit("HandleClaim core digest drifted")
    if hashlib.sha256(canonical(core_projection).encode()).hexdigest() == core_digest.removeprefix("sha256:"):
        raise SystemExit("HandleClaim core KAT accidentally accepts the bare JCS hash")

    revocation = fixture["revocation"]
    if revocation["preimage"]["claim_digest"] != core_digest:
        raise SystemExit("HandleClaim revocation does not bind the exact core")
    revocation_projection = {
        key: value for key, value in revocation["preimage"].items() if key != "proof"
    }
    if digest(revocation["domain"], revocation_projection) != revocation["expected_digest"]:
        raise SystemExit("HandleClaim revocation digest drifted")

    status = fixture["status"]
    status_claim = status["preimage"]["claim"]
    if status_claim != core["preimage"]:
        raise SystemExit("HandleClaim status does not carry the exact core")
    status_claim_projection = {
        key: value for key, value in status_claim.items() if key != "proofs"
    }
    if digest(core["domain"], status_claim_projection) != core_digest:
        raise SystemExit("HandleClaim status does not bind the exact core")
    status_projection = {
        key: value for key, value in status["preimage"].items() if key != "status_proof"
    }
    if digest(status["domain"], status_projection) != status["expected_digest"]:
        raise SystemExit("HandleClaim status digest drifted")
    if set(status["preimage"]) != {
        "schema", "claim", "status", "as_of", "verifier_id", "verified_at",
        "revocation", "fresh_until", "status_proof",
    }:
        raise SystemExit("HandleClaim status preimage is not closed")
    status_proof = status["preimage"]["status_proof"]
    if (
        status_proof["payload_digest"] != status["expected_digest"]
        or status_proof["domain"] != status["domain"]
        or status_proof["proof_purpose"] != "status_attestation"
    ):
        raise SystemExit("HandleClaim status proof does not bind the exact status transcript")
    if status["preimage"]["revocation"] is not None:
        raise SystemExit("HandleClaim verified status must carry revocation=null")

    proof = fixture["proof_signing_input"]
    if proof["payload_digest"] != core_digest or proof["domain"] != core["domain"]:
        raise SystemExit("HandleClaim proof input does not bind core/domain")
    if set(proof) != {
        "kind", "verification_method", "payload_digest", "created_at",
        "domain", "audience", "proof_purpose",
    }:
        raise SystemExit("HandleClaim proof signing input is not closed")

    expected_negatives = {
        "bare_core_hash", "omitted_nullable_audience", "swapped_proof_role",
        "stale_status", "expired_core", "revoker_account_station_mismatch",
        "revocation_digest_mismatch", "unknown_extension",
    }
    if set(fixture["negative_cases"]) != expected_negatives:
        raise SystemExit("HandleClaim negative coverage drifted")
    print("handle claim KAT: core/status/revocation/proof transcripts OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
