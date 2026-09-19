#!/usr/bin/env python3
"""Recompute the SDK conformance contract digest and positive claim proofs.

The signed fixture binds the complete ``sdk_conformance_contract`` object. Any
contract edit therefore changes its digest and invalidates every positive claim
case. Regeneration uses the published conformance Ed25519 fixture seed; before
signing, the derived public key is checked against both the fixture key and the
claim's ``did:key`` verification method so this tool cannot silently sign with
unrelated material.

Only cases explicitly marked ``expect_valid`` are updated. Negative cases are
left unchanged, including intentionally bad digests and signatures.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from tools.artifact_lint.core import canonical_json  # noqa: E402

CONTRACT = ROOT / "spec" / "v1" / "artifacts" / "profiles" / "conformance-profiles.json"
CLAIM_FIXTURE = (
    ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "sdk-conformance-claim-fixture.json"
)
KEY_FIXTURE = (
    ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "franking-proof-transcript-fixture.json"
)
CLAIM_DOMAIN = b"arkret-sdk-conformance-claim-v1\n"
GENERATED_BY = "tools/regenerate_sdk_conformance_claim.py"
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b64u_decode(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception as exc:
        raise ValueError("published conformance seed is not valid base64url") from exc


def _b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _did_key_public_bytes(value: Any) -> bytes:
    if not isinstance(value, str) or not value.startswith("did:key:z"):
        raise ValueError("positive claim proof.kid must be an Ed25519 did:key URL")
    multibase = value.split("did:key:", 1)[1].split("#", 1)[0]
    number = 0
    for char in multibase[1:]:
        index = _BASE58_ALPHABET.find(char)
        if index < 0:
            raise ValueError("positive claim proof.kid is not valid base58btc")
        number = number * 58 + index
    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big")
    leading = len(multibase[1:]) - len(multibase[1:].lstrip("1"))
    decoded = b"\x00" * leading + decoded
    if not decoded.startswith(b"\xed\x01") or len(decoded) != 34:
        raise ValueError("positive claim proof.kid does not carry an Ed25519 public key")
    return decoded[2:]


def _published_signing_key(key_fixture: dict[str, Any]) -> Ed25519PrivateKey:
    test_key = key_fixture.get("test_key")
    if not isinstance(test_key, dict):
        raise ValueError("published key fixture has no test_key object")
    seed_text = test_key.get("private_key_seed")
    if not isinstance(seed_text, str):
        raise ValueError("published key fixture has no private_key_seed")
    seed = _b64u_decode(seed_text)
    if len(seed) != 32:
        raise ValueError("published conformance Ed25519 seed must be 32 bytes")
    signing_key = Ed25519PrivateKey.from_private_bytes(seed)
    public_key = signing_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    published_public = test_key.get("public_key")
    if not isinstance(published_public, str) or _b64u_decode(published_public) != public_key:
        raise ValueError("published conformance seed does not derive the fixture public key")
    return signing_key


def rebuild(
    contract_document: dict[str, Any],
    claim_fixture: dict[str, Any],
    key_fixture: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Return a rebuilt claim fixture and the names of changed positive cases."""
    contract = contract_document.get("sdk_conformance_contract")
    if not isinstance(contract, dict):
        raise ValueError("conformance-profiles.json has no sdk_conformance_contract object")
    if not isinstance(contract.get("contract_digest_computation"), str):
        raise ValueError("sdk_conformance_contract does not declare contract_digest_computation")

    cases = claim_fixture.get("schema_validation_cases")
    if not isinstance(cases, list):
        raise ValueError("claim fixture schema_validation_cases must be an array")
    positive_cases = [case for case in cases if isinstance(case, dict) and case.get("expect_valid")]
    if not positive_cases:
        raise ValueError("claim fixture has no expect_valid case to regenerate")

    signing_key = _published_signing_key(key_fixture)
    public_key = signing_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    digest = "sha256:" + hashlib.sha256(canonical_json(contract).encode("utf-8")).hexdigest()
    rebuilt = copy.deepcopy(claim_fixture)
    changed: list[str] = []

    for case in rebuilt["schema_validation_cases"]:
        if not isinstance(case, dict) or not case.get("expect_valid"):
            continue
        name = case.get("name", "<unnamed>")
        instance = case.get("instance")
        if not isinstance(instance, dict):
            raise ValueError(f"positive claim case {name} has no instance object")
        issuer = instance.get("issuer")
        proof = instance.get("proof")
        if not isinstance(issuer, dict) or not isinstance(proof, dict):
            raise ValueError(f"positive claim case {name} has no issuer/proof object")
        if proof.get("signature_algorithm") != "Ed25519":
            raise ValueError(f"positive claim case {name} is not an Ed25519 claim")
        kid = proof.get("kid")
        if kid != issuer.get("verification_method"):
            raise ValueError(f"positive claim case {name} proof.kid differs from issuer verification method")
        if _did_key_public_bytes(kid) != public_key:
            raise ValueError(f"published conformance seed does not derive {name} proof.kid")

        before = (instance.get("contract_digest"), proof.get("signature"))
        instance["contract_digest"] = digest
        body = {key: value for key, value in instance.items() if key != "proof"}
        proof["signature"] = _b64u(
            signing_key.sign(CLAIM_DOMAIN + canonical_json(body).encode("utf-8"))
        )
        after = (instance["contract_digest"], proof["signature"])
        if before != after:
            changed.append(str(name))

    rebuilt["generated_by"] = GENERATED_BY
    return rebuilt, changed


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail instead of writing")
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--fixture", type=Path, default=CLAIM_FIXTURE)
    parser.add_argument("--key-fixture", type=Path, default=KEY_FIXTURE)
    args = parser.parse_args(argv)

    fixture = _read_json(args.fixture)
    rebuilt, changed = rebuild(
        _read_json(args.contract),
        fixture,
        _read_json(args.key_fixture),
    )
    rendered = json.dumps(rebuilt, ensure_ascii=False, indent=2) + "\n"
    current = args.fixture.read_text(encoding="utf-8")
    if args.check:
        if current != rendered:
            print(
                f"SDK conformance claim fixture is stale: {changed or ['rendering or metadata']}",
                file=sys.stderr,
            )
            return 1
        print("SDK conformance claim fixture is current")
        return 0

    args.fixture.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"regenerated {len(changed)} positive claim case(s): {changed}" if changed else "no change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
