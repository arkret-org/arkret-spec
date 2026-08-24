"""Mutation tests for complete JSON Schema `$ref` pointer resolution."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.core import Lint
from tools.artifact_lint.schemas import ensure_relative_file


TARGET = ROOT / "spec" / "v1" / "artifacts" / "schemas" / "event-payload.schema.json"


class SchemaRefPointerLintTest(unittest.TestCase):
    def test_existing_local_pointer_passes(self) -> None:
        lint = Lint()
        ensure_relative_file(lint, TARGET, TARGET.parent, "#/$defs/digest", "probe")
        self.assertEqual(lint.errors, [])

    def test_missing_local_pointer_fails(self) -> None:
        lint = Lint()
        ensure_relative_file(lint, TARGET, TARGET.parent, "#/$defs/absent_probe", "probe")
        self.assertTrue(any("missing location" in error for error in lint.errors), lint.errors)

    def test_missing_cross_file_pointer_fails(self) -> None:
        lint = Lint()
        ensure_relative_file(
            lint,
            TARGET,
            TARGET.parent,
            "./account-operations.schema.json#/$defs/absent_probe",
            "probe",
        )
        self.assertTrue(any("missing location" in error for error in lint.errors), lint.errors)


if __name__ == "__main__":
    unittest.main()
