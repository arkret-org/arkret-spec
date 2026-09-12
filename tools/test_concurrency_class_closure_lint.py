"""Mutation checks for the single registered execution/model authority."""
from __future__ import annotations
import copy
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.artifact_lint import core, foundation
PATH = ROOT / "spec/v1/artifacts/registry/event-kind-registry.json"

class ExecutionClosureTest(unittest.TestCase):
    def setUp(self):
        self.registry = core.parse_json_text(PATH.read_text(encoding="utf-8"))

    def errors(self, registry):
        lint = core.Lint()
        foundation.check_concurrency_class_closure(lint, registry, PATH)
        return lint.errors

    def test_canonical_contract_is_consistent(self):
        self.assertEqual(self.errors(self.registry), [])

    def test_security_cannot_use_causal_join(self):
        row = next(r for r in self.registry["event_kinds"] if r["event_kind"] == "ak.realm.notary")
        row["cell_writes"][0]["state_model"] = "causal_register"
        self.assertTrue(self.errors(self.registry))

    def test_one_family_cannot_change_execution_between_writers(self):
        row = next(r for r in self.registry["event_kinds"] if r["event_kind"] == "ak.space.update")
        write = next(w for w in row["cell_writes"] if w["execution"] == "data")
        write.update(execution="security", state_model="sequenced_state")
        self.assertTrue(self.errors(self.registry))

    def test_removed_execution_override_is_rejected(self):
        self.registry["event_kinds"][0]["concurrency_class"] = "merge_safe"
        self.assertTrue(self.errors(self.registry))

if __name__ == "__main__":
    unittest.main()
