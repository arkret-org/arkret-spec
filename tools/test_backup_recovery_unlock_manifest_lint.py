"""Mutation tests for the RecoverySession frozen unlock manifest contract."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.fixtures import (
    backup_recovery_unlock_manifest_contract_errors,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec/v1/artifacts/fixtures/history-key-recovery-fixture.json"
SCALABILITY = ROOT / "spec/v1/artifacts/registry/history-recovery-scalability-registry.json"
CONTRACT = ROOT / "spec/v1/artifacts/registry/contract-registry.json"
VECTORS = ROOT / "spec/v1/artifacts/registry/vector-registry.json"


class BackupRecoveryUnlockManifestLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.scalability = json.loads(SCALABILITY.read_text(encoding="utf-8"))
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.operation_ids = {
            row["operation_id"]
            for row in contract["operation_registry"]["operations"]
        }
        self.vectors = json.loads(VECTORS.read_text(encoding="utf-8"))

    def errors(self) -> list[str]:
        return backup_recovery_unlock_manifest_contract_errors(
            self.fixture,
            self.scalability,
            self.operation_ids,
            self.vectors,
        )

    def test_committed_300_scope_vector_is_complete(self) -> None:
        self.assertEqual(self.errors(), [])

    def test_ordinary_limit_cannot_return_to_256(self) -> None:
        self.scalability["backup_access"]["ordinary_download"][
            "config_max_principal_download_limit"
        ] = 256
        self.assertTrue(any("16..64" in error for error in self.errors()))

    def test_underprovisioned_session_rate_is_rejected(self) -> None:
        self.fixture["backup_recovery_unlock_manifest_kat"][
            "computed_recovery_rate"
        ]["minimum_unlocks_per_minute"] = 20
        self.assertTrue(any("cannot complete" in error for error in self.errors()))

    def test_recovery_unlocks_cannot_charge_the_ordinary_counter(self) -> None:
        self.fixture["backup_recovery_unlock_manifest_kat"]["quota_outcome"][
            "ordinary_24h_principal_counter_after"
        ] = 301
        self.assertTrue(any("only per-object" in error for error in self.errors()))

    def test_batch_unlock_operation_is_rejected(self) -> None:
        self.operation_ids.add("ak.self.keys.backups.command.unlock_batch.v1")
        self.assertTrue(any("no batch surface" in error for error in self.errors()))

    def test_verified_manifest_cannot_mutate(self) -> None:
        manifest = self.fixture["backup_recovery_unlock_manifest_kat"]["frozen_manifest"]
        manifest["mutable_after_verified"] = True
        self.assertTrue(any("immutable allowance" in error for error in self.errors()))


if __name__ == "__main__":
    unittest.main()
