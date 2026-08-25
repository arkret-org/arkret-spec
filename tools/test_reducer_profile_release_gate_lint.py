"""Mutation tests for the reducer-profile successor release gate."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as lint_module

REGISTRY = lint_module.ARTIFACTS / "registry" / "reducer-profile-registry.json"


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


class ReducerProfileReleaseGateLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = _load(REGISTRY)
        self.real_load_json = lint_module.load_json

    def tearDown(self) -> None:
        lint_module.load_json = self.real_load_json

    def _run(self, registry: object) -> list[str]:
        def fake_load_json(lint: object, path: Path) -> object:
            if path == REGISTRY:
                return registry
            return self.real_load_json(lint, path)

        lint_module.load_json = fake_load_json
        lint = lint_module.Lint()
        lint_module.check_reducer_profile_registry(lint)
        return list(lint.errors)

    def _with_successor(self) -> dict:
        registry = copy.deepcopy(self.registry)
        successor = copy.deepcopy(registry["profiles"][0])
        successor["profile_id"] = "ak.reducer.successor.v1"
        successor["upgrade_edges"] = []
        registry["profiles"].append(successor)
        return registry

    def test_committed_zero_edge_registry_passes(self) -> None:
        self.assertEqual(self._run(self.registry), [])

    def test_zero_edge_snapshot_flag_must_match_registry(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["upgrade_release_gate"]["current_v1_has_active_upgrade_edges"] = True
        errors = self._run(registry)
        self.assertTrue(any("must match the published edge set" in error for error in errors), errors)

    def test_successor_without_inbound_edge_is_rejected(self) -> None:
        errors = self._run(self._with_successor())
        self.assertTrue(any("has no published inbound upgrade edge" in error for error in errors), errors)

    def test_edge_without_complete_vector_bindings_is_rejected(self) -> None:
        registry = self._with_successor()
        registry["upgrade_release_gate"]["current_v1_has_active_upgrade_edges"] = True
        registry["profiles"][0]["upgrade_edges"] = [
            {"target_profile": "ak.reducer.successor.v1", "state_transition": "identity"}
        ]
        errors = self._run(registry)
        self.assertTrue(any("must bind every required upgrade case" in error for error in errors), errors)

    def test_edge_vector_binding_must_reference_active_vector(self) -> None:
        registry = self._with_successor()
        registry["upgrade_release_gate"]["current_v1_has_active_upgrade_edges"] = True
        registry["profiles"][0]["upgrade_edges"] = [
            {
                "target_profile": "ak.reducer.successor.v1",
                "state_transition": "identity",
                "conformance_vectors": {
                    case: "ak.vector.reducer.missing.v1"
                    for case in registry["upgrade_release_gate"]["required_edge_vector_cases"]
                },
            }
        ]
        errors = self._run(registry)
        self.assertTrue(any("must reference an active vector" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
