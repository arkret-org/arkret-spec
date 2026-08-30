"""Regression tests for duplicate JSON Schema ``required`` members."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import safety


class RequiredMemberUniquenessLintTest(unittest.TestCase):
    def _run(self, required: list[str]) -> list[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = Path(temp_dir)
            schema_root = artifacts / "schemas"
            schema_root.mkdir()
            (schema_root / "test.schema.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "required": required,
                        "properties": {
                            "principal_id": {"type": "string"},
                            "station_id": {"type": "string"},
                        },
                        "additionalProperties": False,
                    }
                ),
                encoding="utf-8",
            )

            original_artifacts = safety.ARTIFACTS
            safety.ARTIFACTS = artifacts
            try:
                lint = safety.Lint()
                safety.check_field_order(lint)
                return lint.errors
            finally:
                safety.ARTIFACTS = original_artifacts

    def test_unique_required_members_pass(self) -> None:
        self.assertEqual(
            self._run(["principal_id", "station_id"]),
            [],
        )

    def test_duplicate_required_member_fails(self) -> None:
        errors = self._run(
            ["principal_id", "station_id", "station_id"]
        )
        self.assertTrue(
            any("duplicate member(s): ['station_id']" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
