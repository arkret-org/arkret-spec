"""Regression tests for required-member order relative to local properties."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import safety


class RequiredPropertiesOrderLintTest(unittest.TestCase):
    def _run(self, required: list[str]) -> list[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = Path(temp_dir)
            schema_root = artifacts / "schemas"
            schema_root.mkdir()
            (schema_root / "test.schema.json").write_text(
                json.dumps(
                    {
                        "$defs": {
                            "nested_array": {
                                "type": "array",
                                "items": {
                                    "allOf": [
                                        {
                                            "then": {
                                                "type": "object",
                                                "required": required,
                                                "properties": {
                                                    "alpha": {"type": "string"},
                                                    "optional": {"type": "string"},
                                                    "beta": {"type": "string"},
                                                },
                                                "additionalProperties": False,
                                            }
                                        }
                                    ]
                                },
                            }
                        },
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

    def test_required_members_in_properties_order_pass(self) -> None:
        self.assertEqual(self._run(["alpha", "beta"]), [])

    def test_required_members_out_of_properties_order_fail(self) -> None:
        errors = self._run(["beta", "alpha"])
        self.assertTrue(
            any(
                "locally declared members MUST follow properties order" in error
                for error in errors
            ),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
