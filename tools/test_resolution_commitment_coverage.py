"""Mutation tests for adapter-derived resolution commitment coverage."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as gate
from tools.artifact_lint.core import Lint

ARTIFACTS = ROOT / "spec/v1/artifacts"
REGISTRY = ROOT / "tools/resolution-commitment-pointer-registry.json"
VECTOR = ARTIFACTS / "fixtures/resolution-commitment-fixture.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ResolutionCommitmentCoverageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = load(REGISTRY)
        self.vector = load(VECTOR)
        self.overrides: dict[Path, object] = {}

    def run_gate(self) -> list[str]:
        original = gate.load_json

        def fake(lint: Lint, path: Path):
            resolved = Path(path).resolve()
            if resolved == REGISTRY.resolve():
                return copy.deepcopy(self.registry)
            if resolved == VECTOR.resolve():
                return copy.deepcopy(self.vector)
            if resolved in self.overrides:
                return copy.deepcopy(self.overrides[resolved])
            return original(lint, path)

        lint = Lint()
        with mock.patch.object(gate, "load_json", side_effect=fake):
            gate.check_resolution_commitment_coverage(lint)
        return lint.errors

    def test_baseline_is_green(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_uncovered_pointer_fails(self) -> None:
        self.registry["pointers"].pop()
        self.assertTrue(any("uncovered resolution commitment" in error for error in self.run_gate()))

    def test_stale_pointer_fails(self) -> None:
        self.registry["pointers"][0]["pointer"] += "/missing"
        self.assertTrue(any("pointer does not resolve" in error for error in self.run_gate()))

    def test_placeholder_version_id_fails(self) -> None:
        row = next(row for row in self.vector["vectors"] if row["evidence_id"] == "agent_inception")
        row["commitment"]["version_id"] = "1-Qmfixtureagentinception"
        self.assertTrue(any("does not recompute" in error for error in self.run_gate()))

    def test_history_head_must_hash_verified_entry(self) -> None:
        row = next(row for row in self.vector["vectors"] if row["evidence_id"] == "schema_service")
        row["commitment"]["method_history_head"] = "sha256:" + "11" * 32
        self.assertTrue(any("does not recompute" in error for error in self.run_gate()))

    def test_scid_must_derive_from_preliminary_entry(self) -> None:
        row = next(row for row in self.vector["vectors"] if row["evidence_id"] == "websocket_service")
        row["preliminary_entry"]["versionTime"] = "2026-09-19T11:00:00Z"
        self.assertTrue(any("SCID does not recompute" in error for error in self.run_gate()))

    def test_fixture_value_must_equal_vector(self) -> None:
        path = ARTIFACTS / "fixtures/agent-vectors-fixture.json"
        document = load(path)
        document["schema_validation_cases"][4]["instance"]["initial_resolution"]["version_id"] = "1-Qmfixtureagentinception"
        self.overrides[path.resolve()] = document
        self.assertTrue(any("differs from evidence agent_inception" in error for error in self.run_gate()))

    def test_runner_and_generator_are_wired(self) -> None:
        runner = (ROOT / "tools/artifact_lint/runner.py").read_text(encoding="utf-8")
        generator = (ROOT / "tools/regenerate_resolution_commitments.py").read_text(encoding="utf-8")
        self.assertIn("check_resolution_commitment_coverage(lint)", runner)
        self.assertIn("resolution-commitment-pointer-registry.json", generator)


if __name__ == "__main__":
    unittest.main()
