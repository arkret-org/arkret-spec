"""Mutation tests for security-transaction step and prepared-material closure."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import core, schemas

SCHEMA = (
    ROOT
    / "spec"
    / "v1"
    / "artifacts"
    / "schemas"
    / "security-transaction.schema.json"
)


class SecurityTransactionSchemaClosureLintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = core.parse_json_text(SCHEMA.read_text(encoding="utf-8"))

    def _lint(self, mutation=None) -> list[str]:
        schema = copy.deepcopy(self.schema)
        if mutation is not None:
            mutation(schema)
        original_load_json = schemas.load_json

        def load_json_with_mutation(lint, path):
            if path.resolve() == SCHEMA.resolve():
                return schema
            return original_load_json(lint, path)

        schemas.load_json = load_json_with_mutation
        try:
            lint = schemas.Lint()
            schemas.check_security_transaction_schema_closure(lint)
            return lint.errors
        finally:
            schemas.load_json = original_load_json

    def test_current_schema_is_closed(self) -> None:
        self.assertEqual(self._lint(), [])

    def test_step_without_variant_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["any_step"]["enum"].append("orphan_probe")

        errors = self._lint(mutate)
        self.assertTrue(
            any("has no $defs/accepted_orphan_probe" in error for error in errors),
            errors,
        )

    def test_step_without_tuple_consumer_fails(self) -> None:
        def mutate(schema) -> None:
            tuple_def = schema["$defs"]["pcr_policy_accepted_steps"]
            tuple_def["prefixItems"] = tuple_def["prefixItems"][1:]

        errors = self._lint(mutate)
        self.assertTrue(
            any("is not consumed by any *_accepted_steps tuple" in error for error in errors),
            errors,
        )

    def test_orphan_prepared_material_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["prepared_orphan_probe"] = {
                "type": "object",
                "additionalProperties": False,
            }

        errors = self._lint(mutate)
        self.assertTrue(any("orphan prepared material" in error for error in errors), errors)

    def test_non_plan_reference_does_not_hide_orphan_prepared_material(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["prepared_orphan_probe"] = {
                "type": "object",
                "additionalProperties": False,
            }
            schema["$defs"]["non_plan_probe"] = {
                "$ref": "#/$defs/prepared_orphan_probe"
            }

        errors = self._lint(mutate)
        self.assertTrue(any("orphan prepared material" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
