"""Mutation tests for formal non-wire roots and orphan `$defs` reachability."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import schema_roots
from tools.artifact_lint.core import Lint


TARGET = ROOT / "spec" / "v1" / "artifacts" / "schemas" / "time.schema.json"


class SchemaRootReachabilityLintTest(unittest.TestCase):
    def _lint(self, definition: dict | None = None) -> list[str]:
        original = schema_roots.load_json
        target = TARGET.resolve()

        def mutated_load(lint, path):
            value = original(lint, path)
            if definition is not None and path.resolve() == target:
                value = copy.deepcopy(value)
                value["$defs"]["orphan_probe"] = definition
            return value

        schema_roots.load_json = mutated_load
        try:
            lint = Lint()
            schema_roots.check_schema_root_reachability(lint)
            return lint.errors
        finally:
            schema_roots.load_json = original

    def test_current_roots_are_closed(self) -> None:
        self.assertEqual(self._lint(), [])

    def test_new_orphan_definition_fails(self) -> None:
        errors = self._lint({"type": "object", "additionalProperties": False})
        self.assertTrue(any("orphan_probe" in error for error in errors), errors)

    def test_self_reference_cannot_hide_an_orphan(self) -> None:
        errors = self._lint({"$ref": "#/$defs/orphan_probe"})
        self.assertTrue(any("orphan_probe" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
