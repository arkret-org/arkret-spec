"""Mutation tests for the KeyPackage write transcript contract gate."""

from __future__ import annotations

import copy
import base64
import json
import sys
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as lint_artifacts
from tools.regenerate_keypackage_write_transcript_fixture import rebuild

FIXTURE = ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "keypackage-write-transcript-fixture.json"


class KeyPackageWriteTranscriptLintTest(unittest.TestCase):
    def _lint_mutation(self, mutate) -> list[str]:
        original_load_json = lint_artifacts.load_json
        fixture = original_load_json(lint_artifacts.Lint(), FIXTURE)
        mutated = copy.deepcopy(fixture)
        mutate(mutated)

        def load_json_with_mutation(lint, path):
            if path.resolve() == FIXTURE.resolve():
                return mutated
            return original_load_json(lint, path)

        lint_artifacts.load_json = load_json_with_mutation
        try:
            lint = lint_artifacts.Lint()
            lint_artifacts.check_keypackage_write_transcript_fixture(lint)
            return lint.errors
        finally:
            lint_artifacts.load_json = original_load_json

    @staticmethod
    def _case(fixture, name):
        return next(case for case in fixture["cases"] if case["name"] == name)

    @staticmethod
    def _resign(fixture, case) -> None:
        canonical = lint_artifacts.canonical_json(case["unsigned_request"])
        signing_input = (case["domain"] + canonical).encode("utf-8")
        seed_text = fixture["test_key"]["private_key_seed"]
        seed = base64.urlsafe_b64decode(seed_text + "=" * (-len(seed_text) % 4))
        signature = Ed25519PrivateKey.from_private_bytes(seed).sign(signing_input)
        case["canonical_jcs"] = canonical
        case["signing_input_base64url"] = base64.urlsafe_b64encode(signing_input).rstrip(b"=").decode("ascii")
        case["signature"] = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")

    def test_unmodified_fixture_passes(self) -> None:
        lint = lint_artifacts.Lint()
        lint_artifacts.check_keypackage_write_transcript_fixture(lint)
        self.assertEqual(lint.errors, [])

    def test_removed_owner_field_fails_schema(self) -> None:
        def mutate(fixture):
            case = self._case(fixture, "revoke_with_reason")
            case["unsigned_request"]["owner_account_id"] = {
                "principal_id": "ak:did_core:did:webvh:z6mkfixtureagentexample:agent.example",
                "station_id": "ak:did_core:did:webvh:z6mkfixtureps:ps.example",
            }
            self._resign(fixture, case)

        errors = self._lint_mutation(mutate)
        self.assertTrue(
            any(
                "owner_account_id" in error and "Additional properties" in error
                for error in errors
            ),
            errors,
        )
        self.assertFalse(any("canonical_jcs" in error or "does not verify" in error for error in errors), errors)

    def test_did_in_nested_recipient_core_field_fails_schema(self) -> None:
        def mutate(fixture):
            case = self._case(fixture, "consume_single_claim")
            receipt = case["unsigned_request"][
                "recipient_durable_receipt"
            ]
            receipt["recipient_principal_id"] = "did:webvh:z6mkfixtureagentexample:agent.example"
            self._resign(fixture, case)

        errors = self._lint_mutation(mutate)
        self.assertTrue(any("recipient_principal_id" in error and "does not match" in error for error in errors), errors)
        self.assertFalse(any("canonical_jcs" in error or "does not verify" in error for error in errors), errors)

    def test_case_cannot_switch_operation(self) -> None:
        def mutate(fixture):
            case = self._case(fixture, "revoke_with_reason")
            case["operation_id"] = "ak.self.keys.keypackages.command.consume.v1"
            case["domain"] = case["operation_id"] + "\n"
            self._resign(fixture, case)

        errors = self._lint_mutation(mutate)
        self.assertTrue(any("registered transcript operation" in error for error in errors), errors)

    def test_private_seed_must_derive_public_key(self) -> None:
        def mutate(fixture):
            fixture["test_key"]["private_key_seed"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

        errors = self._lint_mutation(mutate)
        self.assertTrue(any("does not derive" in error for error in errors), errors)

    def test_stale_canonical_jcs_fails(self) -> None:
        def mutate(fixture):
            self._case(fixture, "revoke_with_reason")["canonical_jcs"] += " "

        errors = self._lint_mutation(mutate)
        self.assertTrue(any("canonical_jcs" in error for error in errors), errors)

    def test_stale_signing_input_fails(self) -> None:
        def mutate(fixture):
            self._case(fixture, "revoke_with_reason")["signing_input_base64url"] = "AA"

        errors = self._lint_mutation(mutate)
        self.assertTrue(any("signing_input_base64url" in error for error in errors), errors)

    def test_invalid_signature_fails(self) -> None:
        def mutate(fixture):
            self._case(fixture, "revoke_with_reason")["signature"] = base64.urlsafe_b64encode(
                b"\x00" * 64
            ).rstrip(b"=").decode("ascii")

        errors = self._lint_mutation(mutate)
        self.assertTrue(any("signature does not verify" in error for error in errors), errors)

    def test_regenerator_updates_invalid_case_transcript_without_repairing_signature(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        case = copy.deepcopy(self._case(fixture, "revoke_with_reason"))
        case["name"] = "intentionally_invalid_signature"
        case["expect_invalid_signature"] = True
        case["canonical_jcs"] = "stale"
        case["signing_input_base64url"] = "c3RhbGU"
        case["signature"] = "AA"
        fixture["negative_cases"].append(case)

        rebuilt, changed = rebuild(fixture)
        rebuilt_case = rebuilt["negative_cases"][-1]
        expected_canonical = lint_artifacts.canonical_json(case["unsigned_request"])
        expected_input = (case["domain"] + expected_canonical).encode("utf-8")

        self.assertIn(case["name"], changed)
        self.assertEqual(rebuilt_case["canonical_jcs"], expected_canonical)
        self.assertEqual(
            rebuilt_case["signing_input_base64url"],
            base64.urlsafe_b64encode(expected_input).rstrip(b"=").decode("ascii"),
        )
        self.assertEqual(rebuilt_case["signature"], "AA")


if __name__ == "__main__":
    unittest.main()
