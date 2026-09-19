#!/usr/bin/env python3
"""Regenerate the constructive did:webvh witness conformance vector."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec/v1/artifacts/fixtures/did-webvh-witness-fixture.json"
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
CONTROLLER_SEED = bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc4"
    "4449c5697b326919703bac031cae7f60"
)
WITNESS_SEEDS = (bytes(range(32, 64)), bytes(range(64, 96)), bytes(range(96, 128)))
WITNESS_INPUT_PREFIX = b"did:webvh witness proof v1\n"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def b58(payload: bytes) -> str:
    number = int.from_bytes(payload, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = ALPHABET[remainder] + encoded
    return "1" * (len(payload) - len(payload.lstrip(b"\x00"))) + encoded


def multihash(payload: bytes) -> str:
    return b58(b"\x12\x20" + hashlib.sha256(payload).digest())


def public_multikey(key: Ed25519PrivateKey) -> str:
    raw = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return "z" + b58(b"\xed\x01" + raw)


def replace_scid(value: Any, scid: str) -> Any:
    if isinstance(value, str):
        return value.replace("{SCID}", scid)
    if isinstance(value, list):
        return [replace_scid(item, scid) for item in value]
    if isinstance(value, dict):
        return {key: replace_scid(item, scid) for key, item in value.items()}
    return value


def build_vector(witness_keys: list[Ed25519PrivateKey]) -> dict[str, Any]:
    controller = Ed25519PrivateKey.from_private_bytes(CONTROLLER_SEED)
    controller_multikey = public_multikey(controller)
    witness_multikeys = [public_multikey(key) for key in witness_keys]
    preliminary = {
        "versionId": "{SCID}",
        "versionTime": "2026-09-19T10:00:00Z",
        "parameters": {
            "method": "did:webvh:1.0",
            "scid": "{SCID}",
            "updateKeys": [controller_multikey],
            "nextKeyHashes": [multihash(controller_multikey.encode("utf-8"))],
            "witness": {
                "threshold": 2,
                "witnesses": [{"id": f"did:key:{value}"} for value in witness_multikeys],
            },
        },
        "state": {
            "id": "did:webvh:{SCID}:witness-vector.example",
            "verificationMethod": [
                {
                    "id": "did:webvh:{SCID}:witness-vector.example#update-key-1",
                    "controller": "did:webvh:{SCID}:witness-vector.example",
                    "type": "Multikey",
                    "publicKeyMultibase": controller_multikey,
                }
            ],
        },
    }
    scid = multihash(canonical(preliminary).encode("utf-8"))
    published = replace_scid(preliminary, scid)
    entry_hash_input = {**published, "versionId": scid}
    version_id = "1-" + multihash(canonical(entry_hash_input).encode("utf-8"))
    published["versionId"] = version_id
    proof_value = "z" + b58(controller.sign(canonical(entry_hash_input).encode("utf-8")))
    published["proof"] = [
        {
            "type": "DataIntegrityProof",
            "cryptosuite": "eddsa-jcs-2022",
            "verificationMethod": f"did:key:{controller_multikey}#{controller_multikey}",
            "proofPurpose": "authentication",
            "proofValue": proof_value,
        }
    ]
    witness_input = WITNESS_INPUT_PREFIX + version_id.encode("utf-8")
    witness_proofs = [
        {
            "type": "DataIntegrityProof",
            "cryptosuite": "eddsa-jcs-2022",
            "verificationMethod": f"did:key:{multikey}#{multikey}",
            "proofPurpose": "assertionMethod",
            "proofValue": "z" + b58(key.sign(witness_input)),
        }
        for key, multikey in zip(witness_keys, witness_multikeys, strict=True)
    ]
    key_rows = []
    for name, key, multikey in zip(("witness_a", "witness_b", "witness_c"), witness_keys, witness_multikeys, strict=True):
        raw = key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        key_rows.append(
            {
                "key_id": name,
                "algorithm": "Ed25519",
                "public_key_multibase": multikey,
                "did": f"did:key:{multikey}",
                "fingerprint": "sha256:" + hashlib.sha256(raw).hexdigest(),
            }
        )
    return {
        "name": "inception_with_two_of_three_valid_witness_proofs",
        "validation_context": {"cryptosuite": "eddsa-jcs-2022"},
        "public_fixture_keys": key_rows,
        "preliminary_entry": preliminary,
        "did_log_entries": [published],
        "did_witness_json": {"versionId": version_id, "proof": witness_proofs[:2]},
        "expected": {
            "decision": "accept",
            "did": published["state"]["id"],
            "scid": scid,
            "version_id": version_id,
            "method_history_head": "sha256:" + hashlib.sha256(canonical(published).encode("utf-8")).hexdigest(),
            "valid_witness_proof_count": 2,
        },
        "mutation_cases": [
            {"name": "controller_signature_bit_flip", "mutation": "flip controller proofValue bit", "expected_reason_code": "did_method_successor_invalid"},
            {"name": "witness_signature_bit_flip", "mutation": "flip witness proofValue bit", "expected_reason_code": "webvh_witness_proof_invalid"},
            {"name": "witness_version_id_mismatch", "mutation": "replace did-witness.json versionId", "expected_reason_code": "webvh_witness_proof_invalid"},
            {"name": "one_valid_proof_is_below_threshold", "mutation": "drop one witness proof", "expected_reason_code": "webvh_witness_threshold_not_met"},
        ],
    }


def replace_placeholders(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, str):
        for old, new in replacements.items():
            value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [replace_placeholders(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: replace_placeholders(item, replacements) for key, item in value.items()}
    return value


def main() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    witness_keys = [Ed25519PrivateKey.from_private_bytes(seed) for seed in WITNESS_SEEDS]
    multikeys = [public_multikey(key) for key in witness_keys]
    data = replace_placeholders(
        data,
        {
            "did:key:z6MkfixtureWitnessA": f"did:key:{multikeys[0]}",
            "did:key:z6MkfixtureWitnessB": f"did:key:{multikeys[1]}",
            "did:key:z6MkfixtureWitnessC": f"did:key:{multikeys[2]}",
            "#z6MkfixtureWitnessA": f"#{multikeys[0]}",
            "#z6MkfixtureWitnessB": f"#{multikeys[1]}",
            "#z6MkfixtureWitnessC": f"#{multikeys[2]}",
        },
    )
    for case in data["method_policy_cases"]:
        case["validation_context"] = {"cryptosuite": "eddsa-jcs-2022"}
    x25519 = "z" + b58(b"\xec\x01" + bytes(range(128, 160)))
    wrong_name = "cryptosuite_incompatible_witness_key_fails_closed"
    if not any(case.get("name") == wrong_name for case in data["method_policy_cases"]):
        data["method_policy_cases"].insert(
            6,
            {
                "name": wrong_name,
                "semantic_outcome": "reject",
                "expected_reason_code": "webvh_witness_parameter_malformed",
                "notes": "The X25519 multikey is decodable and has the right X25519 length, but validation_context selects eddsa-jcs-2022, which requires Ed25519 witness keys.",
                "parameters": {
                    "method": "did:webvh:1.0",
                    "witness": {"threshold": 1, "witnesses": [{"id": f"did:key:{x25519}"}]},
                },
                "validation_context": {"cryptosuite": "eddsa-jcs-2022"},
            },
        )
    data["cryptographic_vectors"] = [build_vector(witness_keys)]
    data["version"] = "2026-09-19.1"
    data["description"] = (
        "Conformance vectors for the did:webvh witness rail. cryptographic_vectors[] contains "
        "a deterministic, field-exact inception whose SCID, versionId, controller proof, witness "
        "proofs and method-history head are independently recomputable. method_policy_cases[] "
        "carry an explicit validation_context.cryptosuite so public-key compatibility is a "
        "testable input rather than prose. Structural policy cases never substitute for the "
        "cryptographic vector."
    )
    FIXTURE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
