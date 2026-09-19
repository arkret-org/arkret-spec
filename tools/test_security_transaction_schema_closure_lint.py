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
FIXTURE = (
    ROOT
    / "spec"
    / "v1"
    / "artifacts"
    / "fixtures"
    / "security-transaction-resilience-fixture.json"
)


class SecurityTransactionSchemaClosureLintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = core.parse_json_text(SCHEMA.read_text(encoding="utf-8"))
        cls.fixture = core.parse_json_text(FIXTURE.read_text(encoding="utf-8"))

    def _lint(self, mutation=None, fixture_mutation=None) -> list[str]:
        schema = copy.deepcopy(self.schema)
        fixture = copy.deepcopy(self.fixture)
        if mutation is not None:
            mutation(schema)
        if fixture_mutation is not None:
            fixture_mutation(fixture)
        original_load_json = schemas.load_json

        def load_json_with_mutation(lint, path):
            if path.resolve() == SCHEMA.resolve():
                return schema
            if path.resolve() == FIXTURE.resolve():
                return fixture
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

    def test_reintroduced_wire_state_fails(self) -> None:
        def mutate(schema) -> None:
            schema["properties"]["state"] = {
                "enum": ["pending", "running", "completed", "aborted", "expired"]
            }

        errors = self._lint(mutate)
        self.assertTrue(
            any("derived state" in error for error in errors),
            errors,
        )

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

    def test_continue_must_require_attestation(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["continue_request"]["required"].remove("client_attestation")

        errors = self._lint(mutate)
        self.assertTrue(any("client-attested terminal step" in error for error in errors), errors)

    def test_continue_kind_blind_index_gate_fails(self) -> None:
        def mutate(schema) -> None:
            request = schema["$defs"]["continue_request"]
            request["allOf"] = [{"if": {"required": ["client_attestation"]}}]

        errors = self._lint(mutate)
        self.assertTrue(any("kind-blind terminal indexes" in error for error in errors), errors)

    def test_continue_kind_blind_maximum_fails(self) -> None:
        def mutate(schema) -> None:
            request = schema["$defs"]["continue_request"]
            request["properties"]["expected_accepted_step_count"]["maximum"] = 4

        errors = self._lint(mutate)
        self.assertTrue(any("kind-blind maximum" in error for error in errors), errors)

    def test_orphan_prepared_material_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["prepared_orphan_probe"] = {
                "type": "object",
                "additionalProperties": False,
            }

        errors = self._lint(mutate)
        self.assertTrue(any("orphan prepared material" in error for error in errors), errors)

    def test_prepared_event_unit_mirror_fails(self) -> None:
        def mutate(schema) -> None:
            unit = schema["$defs"]["prepared_event_unit"]
            unit["properties"]["destination_id"] = {"type": "string"}

        errors = self._lint(mutate)
        self.assertTrue(any("define only request and request_digest" in error for error in errors), errors)

    def test_recovery_commit_intent_minimum_cardinality_drift_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["recovery_commit_intent"]["properties"]["unit_event_digests"]["minItems"] = 1

        errors = self._lint(mutate)
        self.assertTrue(any("minItems must be 2" in error for error in errors), errors)

    def test_recovery_commit_intent_maximum_cardinality_drift_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["recovery_commit_intent"]["properties"]["unit_event_digests"]["maxItems"] = 3

        errors = self._lint(mutate)
        self.assertTrue(any("maxItems must be 2" in error for error in errors), errors)

    def test_recovery_commit_intent_duplicate_digest_gate_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["recovery_commit_intent"]["properties"]["unit_event_digests"]["uniqueItems"] = False

        errors = self._lint(mutate)
        self.assertTrue(any("must require distinct digests" in error for error in errors), errors)

    def test_recovery_commit_intent_digest_suite_drift_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["recovery_commit_intent"]["properties"]["unit_event_digests"]["items"]["pattern"] = "^.+$"

        errors = self._lint(mutate)
        self.assertTrue(any("must contain only SHA-256 digests" in error for error in errors), errors)

    def test_recovery_commit_intent_order_description_drift_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["recovery_commit_intent"]["properties"]["unit_event_digests"]["description"] = "Two digests."

        errors = self._lint(mutate)
        self.assertTrue(any("must declare the canonical order" in error for error in errors), errors)

    def test_recovery_terminal_commit_extra_realm_commit_material_fails(self) -> None:
        def mutate(schema) -> None:
            terminal = schema["$defs"]["recovery_terminal_commit"]
            terminal["properties"]["realm_commit_id"] = {"$ref": "#/$defs/realm_commit_id"}

        errors = self._lint(mutate)
        self.assertTrue(any("must define only recovery_receipt" in error for error in errors), errors)

    def test_missing_recovery_commit_intent_fixture_mutation_fails(self) -> None:
        def mutate(fixture) -> None:
            fixture["schema_validation_cases"] = [
                case
                for case in fixture["schema_validation_cases"]
                if case["name"] != "recovery_commit_intent_rejects_one_digest"
            ]

        errors = self._lint(fixture_mutation=mutate)
        self.assertTrue(any("mutation cases are incomplete" in error for error in errors), errors)

    def test_recovery_digest_order_fixture_drift_fails(self) -> None:
        def mutate(fixture) -> None:
            case = next(
                row
                for row in fixture["recovery_terminal_commit_cases"]
                if row["name"] == "swapped_event_digest_order_differs_from_the_frozen_plan"
            )
            case["submitted_order"] = case["frozen_order"]

        errors = self._lint(fixture_mutation=mutate)
        self.assertTrue(any("must reverse the frozen canonical order" in error for error in errors), errors)

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
