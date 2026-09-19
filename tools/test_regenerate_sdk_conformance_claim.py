"""Tests for deterministic SDK conformance claim regeneration."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.core import canonical_json
from tools.regenerate_sdk_conformance_claim import (
    CLAIM_DOMAIN,
    CLAIM_FIXTURE,
    CONTRACT,
    KEY_FIXTURE,
    _b64u_decode,
    _did_key_public_bytes,
    main,
    rebuild,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class SdkConformanceClaimRegeneratorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load(CONTRACT)
        self.claim = load(CLAIM_FIXTURE)
        self.key_fixture = load(KEY_FIXTURE)

    def test_committed_positive_claim_is_reproducible(self) -> None:
        rebuilt, changed = rebuild(self.contract, self.claim, self.key_fixture)
        self.assertEqual(changed, [])
        self.assertEqual(rebuilt, self.claim)

    def test_contract_edit_recomputes_all_current_bindings_and_preserves_wrong_binding(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["sdk_conformance_contract"]["regenerator_probe"] = "changed"

        rebuilt, changed = rebuild(contract, self.claim, self.key_fixture)
        positive = rebuilt["schema_validation_cases"][0]["instance"]
        body = {key: value for key, value in positive.items() if key != "proof"}
        signature = _b64u_decode(positive["proof"]["signature"])
        public_key = _did_key_public_bytes(positive["proof"]["kid"])

        self.assertEqual(len(changed), len(rebuilt["schema_validation_cases"]) - 1)
        self.assertNotEqual(
            positive["contract_digest"],
            self.claim["schema_validation_cases"][0]["instance"]["contract_digest"],
        )
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature,
            CLAIM_DOMAIN + canonical_json(body).encode("utf-8"),
        )
        expected_digest = positive["contract_digest"]
        for case in rebuilt["schema_validation_cases"]:
            instance = case["instance"]
            overrides = case.get("regeneration_overrides", {})
            if "contract_digest" in overrides:
                self.assertEqual(instance["contract_digest"], overrides["contract_digest"], case["name"])
            elif case.get("contract_binding_expect_valid", True):
                self.assertEqual(instance["contract_digest"], expected_digest, case["name"])
            else:
                self.assertNotEqual(instance["contract_digest"], expected_digest, case["name"])
            proof = instance["proof"]
            if "signature" in overrides:
                self.assertEqual(proof["signature"], overrides["signature"], case["name"])
                continue
            body = {key: value for key, value in instance.items() if key != "proof"}
            Ed25519PublicKey.from_public_bytes(_did_key_public_bytes(proof["kid"])).verify(
                _b64u_decode(proof["signature"]),
                CLAIM_DOMAIN + canonical_json(body).encode("utf-8"),
            )

    def test_negative_case_regeneration_overrides_are_preserved(self) -> None:
        rebuilt, _ = rebuild(self.contract, self.claim, self.key_fixture)
        cases = {case["name"]: case for case in rebuilt["schema_validation_cases"]}
        zero = cases["zero_revision_and_digest_rejected"]
        self.assertEqual(
            zero["instance"]["contract_digest"],
            cases["valid_signed_artifact_bound_claim"]["instance"]["contract_digest"],
        )
        bad_signature = cases["bad_signature_semantic_rejected"]
        self.assertEqual(bad_signature["instance"]["proof"]["signature"], "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")

    def test_wrong_published_seed_is_refused_before_signing(self) -> None:
        key_fixture = copy.deepcopy(self.key_fixture)
        key_fixture["test_key"]["private_key_seed"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        with self.assertRaisesRegex(ValueError, "does not derive the fixture public key"):
            rebuild(self.contract, self.claim, key_fixture)

    def test_check_and_write_use_temporary_files_and_lf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            contract_path = temp / "conformance-profiles.json"
            fixture_path = temp / "sdk-conformance-claim-fixture.json"
            key_path = temp / "franking-proof-transcript-fixture.json"
            contract = copy.deepcopy(self.contract)
            contract["sdk_conformance_contract"]["regenerator_probe"] = "changed"
            contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8", newline="\n")
            fixture_path.write_text(
                json.dumps(self.claim, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            key_path.write_text(
                json.dumps(self.key_fixture, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            args = [
                "--contract",
                str(contract_path),
                "--fixture",
                str(fixture_path),
                "--key-fixture",
                str(key_path),
            ]

            self.assertEqual(main(["--check", *args]), 1)
            stale = fixture_path.read_bytes()
            self.assertEqual(main(args), 0)
            self.assertNotEqual(fixture_path.read_bytes(), stale)
            self.assertEqual(main(["--check", *args]), 0)
            self.assertNotIn(b"\r\n", fixture_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
