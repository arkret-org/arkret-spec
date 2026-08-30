#!/usr/bin/env python3
"""Regenerate the byte-exact recovery-session factor transcript fixture."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
OUTPUT = ARTIFACTS / "fixtures" / "recovery-transcript-fixture.json"
SHARED_KEY = ARTIFACTS / "fixtures" / "keypackage-write-transcript-fixture.json"


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_b64u(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def common(kind: str) -> dict[str, object]:
    return {
        "schema": "ak.identity.recovery_proof.v1",
        "kind": kind,
        "account_id": {
            "principal_id": "ak:did_core:webvh:z6mkfixtureprincipalexample",
            "principal_server_id": "ak:did_core:webvh:z6mkfixtureserviceexample",
        },
        "request_id": "ak:request:019b6a40-0000-7000-8000-000000000000",
        "session_grant_id": "ak:session_grant:ARZh3t6pUePAQHfZ8vZbYERKa2BqFWV_dynfVmrmHA_N",
        "session_grant_cnf_jkt": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "requesting_device_id": "ak:device:019b6a40-0000-7000-8000-000000000001",
        "trust_domain": "ak:trust_domain:recovery-fixture",
        "policy_id": "ak:policy:019b6a40-0000-7000-8000-000000000002",
        "policy_version": 7,
        "recovery_session_id": "ak:recovery_session:019b6a40-0000-7000-8000-000000000003",
        "identity_model": "pcr_policy",
        "model_generation_ref": 19,
        "publication_authority_context_digest": "sha256:" + "11" * 32,
        "challenge": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "expires_at": "2026-08-23T09:30:00.000Z",
        "created_at": "2026-08-23T09:00:00.000Z",
    }


def proof_inputs() -> list[tuple[str, dict[str, object], list[str]]]:
    return [
        (
            "did_root",
            {
                "kind": "did_root",
                "challenge": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "verification_method": "did:key:z6MkfixtureRoot#z6MkfixtureRoot",
                "signature_algorithm": "Ed25519",
                "signature": "PLACEHOLDER",
            },
            ["signature"],
        ),
        (
            "recovery_unlock",
            {
                "kind": "recovery_unlock",
                "challenge": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "recovery_secret_ref": "did:key:z6MkfixtureRecovery#z6MkfixtureRecovery",
                "verification_method": "did:key:z6MkfixtureRecovery#z6MkfixtureRecovery",
                "signature_algorithm": "Ed25519",
                "unlock_commitment": "sha256:" + "22" * 32,
                "signature": "PLACEHOLDER",
            },
            ["signature", "unlock_commitment"],
        ),
        (
            "device_quorum",
            {
                "kind": "device_quorum",
                "challenge": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "threshold": 2,
                "signatures": [
                    {
                        "device_id": "ak:device:019b6a40-0000-7000-8000-000000000004",
                        "verification_method": "did:key:z6MkfixtureDeviceA#z6MkfixtureDeviceA",
                        "signature_algorithm": "Ed25519",
                        "signature": "PLACEHOLDER",
                    },
                    {
                        "device_id": "ak:device:019b6a40-0000-7000-8000-000000000005",
                        "verification_method": "did:key:z6MkfixtureDeviceB#z6MkfixtureDeviceB",
                        "signature_algorithm": "Ed25519",
                        "signature": "PLACEHOLDER",
                    },
                ],
            },
            ["signatures/*/signature"],
        ),
        (
            "trusted_recovery_service",
            {
                "kind": "trusted_recovery_service",
                "challenge": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "service_id": "ak:did_core:web:recovery.example",
                "audience": "ak:did_core:webvh:z6mkfixtureserviceexample",
                "verification_method": "did:web:recovery.example#recovery-1",
                "signature_algorithm": "Ed25519",
                "attestation_ref": "ak:attestation:019b6a40-0000-7000-8000-000000000006",
                "signature": "PLACEHOLDER",
            },
            ["signature"],
        ),
        (
            "threshold_recovery",
            {
                "kind": "threshold_recovery",
                "challenge": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "threshold": 2,
                "share_releases": [
                    {
                        "share_id": "share-a",
                        "holder_id": "ak:did_core:web:holder-a.example",
                        "transcript_digest": "sha256:" + "33" * 32,
                        "verification_method": "did:web:holder-a.example#recovery-1",
                        "signature_algorithm": "Ed25519",
                        "signature": "PLACEHOLDER",
                    },
                    {
                        "share_id": "share-b",
                        "holder_id": "ak:did_core:web:holder-b.example",
                        "transcript_digest": "sha256:" + "44" * 32,
                        "verification_method": "did:web:holder-b.example#recovery-1",
                        "signature_algorithm": "Ed25519",
                        "signature": "PLACEHOLDER",
                    },
                ],
            },
            ["share_releases/*/signature"],
        ),
    ]


def project(kind: str, proof: dict[str, object]) -> dict[str, object] | None:
    if kind == "did_root":
        return None
    body = copy.deepcopy(proof)
    if kind == "recovery_unlock":
        body.pop("signature")
        body.pop("unlock_commitment")
    elif kind == "device_quorum":
        for row in body["signatures"]:
            row.pop("signature")
    elif kind == "trusted_recovery_service":
        body.pop("signature")
    elif kind == "threshold_recovery":
        for row in body["share_releases"]:
            row.pop("signature")
    return body


def main() -> None:
    test_key = json.loads(SHARED_KEY.read_text(encoding="utf-8"))["test_key"]
    signing_key = Ed25519PrivateKey.from_private_bytes(decode_b64u(test_key["private_key_seed"]))
    cases = []
    inputs = proof_inputs()
    for index, (kind, proof, removed) in enumerate(inputs):
        transcript = common(kind)
        body = project(kind, proof)
        if body is not None:
            transcript["proof_body"] = body
        jcs = canonical_json(transcript)
        signature = b64u(signing_key.sign(jcs.encode("utf-8")))
        if kind in {"did_root", "recovery_unlock", "trusted_recovery_service"}:
            proof["signature"] = signature
        elif kind == "device_quorum":
            for row in proof["signatures"]:
                row["signature"] = signature
        else:
            for row in proof["share_releases"]:
                row["signature"] = signature
        replay_kind = inputs[(index + 1) % len(inputs)][0]
        replay = copy.deepcopy(transcript)
        replay["kind"] = replay_kind
        cases.append(
            {
                "kind": kind,
                "transcript_schema_ref": (
                    "schemas/recovery-session.schema.json#/$defs/did_root_transcript"
                    if kind == "did_root"
                    else "schemas/recovery-session.schema.json#/$defs/generic_recovery_transcript"
                ),
                "source_proof": proof,
                "removed_signature_carriers": removed,
                "transcript": transcript,
                "transcript_jcs": jcs,
                "transcript_digest": "sha256:" + hashlib.sha256(jcs.encode("utf-8")).hexdigest(),
                "signature_b64u": signature,
                "expected_result": "accept",
                "cross_factor_replay": {
                    "replayed_kind": replay_kind,
                    "transcript": replay,
                    "expected_result": "reject_signature_invalid",
                },
            }
        )
    fixture = {
        "version": "2026-08-23.2",
        "generated_by": "tools/regenerate_recovery_transcript_fixture.py",
        "domain": "ak.identity.recovery_proof.v1",
        "description": "Byte-exact signing transcripts for all five recovery factors. The verifier reconstructs these bytes from stored session state and the submitted proof; clients never submit a transcript object.",
        "test_key": test_key,
        "runner": {
            "kind": "known_answer_tests",
            "entrypoint": "ak.suite.identity.recovery_transcript.v1",
        },
        "covers_vectors": ["ak.vector.identity.recovery_transcript.v1"],
        "cases": cases,
    }
    OUTPUT.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
