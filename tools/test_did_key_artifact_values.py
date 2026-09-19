"""Mutation tests for did:key values and the constructive witness vector."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as fixture_gate
from tools.artifact_lint import test_material as value_gate
from tools.artifact_lint.core import Lint

FIXTURE = ROOT / "spec/v1/artifacts/fixtures/did-webvh-witness-fixture.json"


class DidKeyArtifactValuesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.body = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.value_overrides: dict[Path, object] = {}

    def witness_errors(self) -> list[str]:
        original = fixture_gate.load_json

        def fake(lint: Lint, path: Path):
            if Path(path).resolve() == FIXTURE.resolve():
                return copy.deepcopy(self.body)
            if Path(path).resolve() in self.value_overrides:
                return copy.deepcopy(self.value_overrides[Path(path).resolve()])
            return original(lint, path)

        lint = Lint()
        with mock.patch.object(fixture_gate, "load_json", side_effect=fake):
            fixture_gate.check_did_webvh_witness_fixture(lint)
        return lint.errors

    def value_errors(self) -> list[str]:
        original = value_gate.load_json

        def fake(lint: Lint, path: Path):
            if Path(path).resolve() == FIXTURE.resolve():
                return copy.deepcopy(self.body)
            if Path(path).resolve() in self.value_overrides:
                return copy.deepcopy(self.value_overrides[Path(path).resolve()])
            return original(lint, path)

        lint = Lint()
        with mock.patch.object(value_gate, "load_json", side_effect=fake):
            value_gate.check_did_key_artifact_values(lint)
        return lint.errors

    def test_baselines_are_green(self) -> None:
        self.assertEqual(self.witness_errors(), [])
        self.assertEqual(self.value_errors(), [])

    def test_positive_placeholder_did_key_fails(self) -> None:
        case = self.body["method_policy_cases"][0]
        case["parameters"]["witness"]["witnesses"][0]["id"] = "did:key:z6MkfixtureWitnessA"
        self.assertTrue(any("does not decode" in error for error in self.value_errors()))

    def test_negative_invalid_key_requires_exact_case_contract(self) -> None:
        case = next(case for case in self.body["method_policy_cases"] if case["name"] == "undecodable_did_key_witness_fails_closed")
        case["expected_reason_code"] = "webvh_witness_proof_invalid"
        self.assertTrue(any("does not decode" in error for error in self.value_errors()))

    def test_case_must_name_cryptosuite(self) -> None:
        del self.body["method_policy_cases"][0]["validation_context"]
        self.assertTrue(any("validation_context" in error for error in self.witness_errors()))

    def test_recovery_label_cannot_masquerade_as_did_key(self) -> None:
        path = ROOT / "spec/v1/artifacts/fixtures/recovery-transcript-fixture.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        case = next(case for case in body["cases"] if case["kind"] == "recovery_unlock")
        case["source_proof"]["recovery_secret_ref"] = "did:key:z6MkfixtureRecovery"
        self.value_overrides[path.resolve()] = body
        self.assertTrue(any("opaque policy label" in error for error in self.value_errors()))

    def test_decodable_wrong_algorithm_case_is_required(self) -> None:
        self.body["method_policy_cases"] = [
            case for case in self.body["method_policy_cases"]
            if case["name"] != "cryptosuite_incompatible_witness_key_fails_closed"
        ]
        self.assertTrue(any("cryptosuite-incompatible" in error or "malformed" in error for error in self.witness_errors()))

    def test_controller_signature_mutation_fails(self) -> None:
        proof = self.body["cryptographic_vectors"][0]["did_log_entries"][0]["proof"][0]
        proof["proofValue"] = proof["proofValue"][:-1] + ("1" if proof["proofValue"][-1] != "1" else "2")
        self.assertTrue(any("controller proof" in error for error in self.witness_errors()))

    def test_witness_signature_mutation_fails(self) -> None:
        proof = self.body["cryptographic_vectors"][0]["did_witness_json"]["proof"][0]
        proof["proofValue"] = proof["proofValue"][:-1] + ("1" if proof["proofValue"][-1] != "1" else "2")
        self.assertTrue(any("proof[0] does not verify" in error for error in self.witness_errors()))

    def test_witness_version_binding_mutation_fails(self) -> None:
        self.body["cryptographic_vectors"][0]["did_witness_json"]["versionId"] += "x"
        self.assertTrue(any("must bind" in error for error in self.witness_errors()))

    def test_runner_wires_both_gates(self) -> None:
        source = (ROOT / "tools/artifact_lint/runner.py").read_text(encoding="utf-8")
        self.assertIn("check_did_webvh_witness_fixture(lint)", source)
        self.assertIn("check_did_key_artifact_values(lint)", source)


if __name__ == "__main__":
    unittest.main()
