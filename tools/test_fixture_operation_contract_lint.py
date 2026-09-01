"""Regression tests for fixture-to-operation-schema contract closure."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
CONTRACT_REGISTRY = ARTIFACTS / "registry" / "contract-registry.json"
PCR_FIXTURE = ARTIFACTS / "fixtures" / "pcr-outward-exposure-fixture.json"
SESSION_FIXTURE = ARTIFACTS / "fixtures" / "auth-session-proof-fixture.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class FixtureOperationContractLintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        registry = load(CONTRACT_REGISTRY)
        cls.operations = {
            row["operation_id"]: row
            for row in registry["operation_registry"]["operations"]
        }

    def run_fixture(self, path: Path, data: Any) -> list[str]:
        lint = fixtures.Lint()
        fixtures.check_fixture_operation_contracts(
            lint,
            path,
            data,
            self.operations,
        )
        return list(lint.errors)

    def test_committed_contract_cases_pass(self) -> None:
        self.assertEqual(self.run_fixture(PCR_FIXTURE, load(PCR_FIXTURE)), [])
        self.assertEqual(self.run_fixture(SESSION_FIXTURE, load(SESSION_FIXTURE)), [])

    def test_stale_public_resolution_required_fields_fail(self) -> None:
        fixture = copy.deepcopy(load(PCR_FIXTURE))
        fixture["cases"][0]["expected_required_fields"] = [
            "principal_id",
            "station_id",
            "resolution_projection",
            "method_history_evidence",
            "projection_attestation",
        ]
        errors = self.run_fixture(PCR_FIXTURE, fixture)
        self.assertTrue(
            any("expected_required_fields must exactly equal" in error for error in errors),
            errors,
        )

    def test_bare_principal_in_accepted_device_proof_fails(self) -> None:
        fixture = copy.deepcopy(load(SESSION_FIXTURE))
        proof = fixture["cases"][0]["request"]["accepted_device_possession_proof"]
        account_id = proof.pop("account_id")
        proof["principal_id"] = account_id["principal_id"]
        errors = self.run_fixture(SESSION_FIXTURE, fixture)
        self.assertTrue(
            any("cases[0].request fails" in error for error in errors),
            errors,
        )

    def test_request_digest_binding_cannot_drift_from_transcript(self) -> None:
        fixture = copy.deepcopy(load(SESSION_FIXTURE))
        fixture["cases"][0]["request"]["accepted_device_possession_proof"][
            "session_intent_digest"
        ] = "sha256:" + "6" * 64
        errors = self.run_fixture(SESSION_FIXTURE, fixture)
        self.assertTrue(
            any("target digest does not equal expected_digest" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
