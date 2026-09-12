"""Reject arbitrary Cell reset and the retired recovery kind."""
from pathlib import Path
import json
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.artifact_lint import core, foundation
PATH = ROOT / "spec/v1/artifacts/registry/event-kind-registry.json"
class DynamicResetRejectionTest(unittest.TestCase):
    def test_retired_kind_has_no_registration(self):
        registry = json.loads(PATH.read_text(encoding="utf-8"))
        self.assertNotIn(core.CONFLICT_RECOVERY_KIND, {r["event_kind"] for r in registry["event_kinds"]})
    def test_no_kind_can_reset_an_arbitrary_cell(self):
        for kind in [core.CONFLICT_RECOVERY_KIND, "ak.realm.policy", "ak.message.create"]:
            lint = core.Lint()
            foundation.lint_conflict_recovery_write(lint, PATH, kind, kind, {"cell_ref": {"field": "payload.target_cell_id"}, "effect_projection": {"kind": "reset"}})
            self.assertTrue(lint.errors)
if __name__ == "__main__":
    unittest.main()
