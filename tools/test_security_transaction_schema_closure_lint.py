"""Mutation tests for canonical security-transaction intent and progress."""

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

    def test_step_order_drift_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["security_rotation_step"]["enum"].reverse()

        errors = self._lint(mutate)
        self.assertTrue(
            any("must declare the canonical order" in error for error in errors),
            errors,
        )

    def test_per_step_accepted_wrapper_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["accepted_revoke"] = {
                "$ref": "#/$defs/accepted_step"
            }

        errors = self._lint(mutate)
        self.assertTrue(
            any("per-step accepted wrapper" in error for error in errors),
            errors,
        )

    def test_resource_derived_next_step_fails(self) -> None:
        def mutate(schema) -> None:
            schema["properties"]["next_required_step"] = {"type": "string"}

        errors = self._lint(mutate)
        self.assertTrue(any("derived next_required_step" in error for error in errors), errors)

    def test_create_caller_plan_digest_fails(self) -> None:
        def mutate(schema) -> None:
            create = schema["$defs"]["recovery_create_request"]
            create["properties"]["prepared_plan_digest"] = {"$ref": "#/$defs/digest"}

        errors = self._lint(mutate)
        self.assertTrue(any("caller-supplied prepared_plan_digest" in error for error in errors), errors)

    def test_continue_derived_step_fails(self) -> None:
        def mutate(schema) -> None:
            request = schema["$defs"]["continue_request"]
            request["properties"]["expected_next_step"] = {"type": "string"}

        errors = self._lint(mutate)
        self.assertTrue(any("derived expected_next_step" in error for error in errors), errors)

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
