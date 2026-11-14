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

    def test_accepted_prefix_cardinality_drift_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["security_rotation_accepted_steps"]["maxItems"] = 6

        errors = self._lint(mutate)
        self.assertTrue(
            any("maxItems must equal step count" in error for error in errors),
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

    def test_redundant_accepted_output_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["accepted_step"]["properties"]["output_digest"] = {
                "$ref": "#/$defs/digest"
            }

        errors = self._lint(mutate)
        self.assertTrue(any("only acceptor and accepted_at" in error for error in errors), errors)

    def test_open_backup_material_wrapper_fails(self) -> None:
        def mutate(schema) -> None:
            plan = schema["$defs"]["backup_rotation_plan"]
            plan["properties"]["encrypted_backup_material"] = {
                "$ref": "./recovery-authority.schema.json#/$defs/canonical_public_material"
            }

        errors = self._lint(mutate)
        self.assertTrue(any("only binding, envelopes and active unit" in error for error in errors), errors)

    def test_resource_derived_next_step_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["security_rotation_transaction"]["properties"]["next_required_step"] = {"type": "string"}

        errors = self._lint(mutate)
        self.assertTrue(any("derived next_required_step" in error for error in errors), errors)

    def test_reintroduced_wire_state_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["security_rotation_transaction"]["properties"]["state"] = {
                "enum": ["pending", "running", "completed", "aborted", "expired"]
            }

        errors = self._lint(mutate)
        self.assertTrue(
            any("derived state" in error for error in errors),
            errors,
        )

    def test_create_caller_plan_digest_fails(self) -> None:
        def mutate(schema) -> None:
            create = schema["$defs"]["recovery_create_request_body"]
            create["properties"]["prepared_plan_digest"] = {"$ref": "#/$defs/digest"}

        errors = self._lint(mutate)
        self.assertTrue(any("caller-supplied prepared_plan_digest" in error for error in errors), errors)

    def test_continue_derived_step_fails(self) -> None:
        def mutate(schema) -> None:
            request = schema["$defs"]["security_transaction_continue_request_body"]
            request["properties"]["expected_next_step"] = {"type": "string"}

        errors = self._lint(mutate)
        self.assertTrue(any("derived expected_next_step" in error for error in errors), errors)

    def test_continue_must_require_attestation(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["security_transaction_continue_request_body"]["required"].remove("client_attestation")

        errors = self._lint(mutate)
        self.assertTrue(any("client-attested terminal step" in error for error in errors), errors)

    def test_continue_kind_blind_index_gate_fails(self) -> None:
        def mutate(schema) -> None:
            request = schema["$defs"]["security_transaction_continue_request_body"]
            request["allOf"] = [{"if": {"required": ["client_attestation"]}}]

        errors = self._lint(mutate)
        self.assertTrue(any("kind-blind terminal indexes" in error for error in errors), errors)

    def test_continue_kind_blind_maximum_fails(self) -> None:
        def mutate(schema) -> None:
            request = schema["$defs"]["security_transaction_continue_request_body"]
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

    def test_recovery_old_plan_cannot_return(self) -> None:
        def mutate(schema):
            schema["$defs"]["pcr_policy_recovery_plan"] = {"type": "object"}
        self.assertTrue(any("must not restore" in error for error in self._lint(mutate)))

    def test_recovery_outer_attestation_cannot_return(self) -> None:
        def mutate(schema):
            schema["$defs"]["client_step_attestation"]["properties"]["step"] = {"enum": ["local_commit", "commit_recovery_unit"]}
        self.assertTrue(any("Rotation local_commit only" in error for error in self._lint(mutate)))

    def test_rotation_output_cannot_accept_a_receipt_id(self) -> None:
        def mutate(schema):
            schema["$defs"]["client_step_attestation"]["properties"]["output_ref"] = {"$ref": "#/$defs/receipt_id"}
        self.assertTrue(any("reserved SHA-256 local_commit" in error for error in self._lint(mutate)))

    def test_recovery_create_cannot_drop_receipt(self) -> None:
        def mutate(schema):
            schema["$defs"]["recovery_create_request_body"]["required"].remove("recovery_receipt")
        self.assertTrue(any("sole signed recovery_receipt" in error for error in self._lint(mutate)))

    def test_recovery_result_cannot_be_partial(self) -> None:
        def mutate(schema):
            schema["$defs"]["recovery_transaction_completion"]["required"].remove("completion_attestation")
        self.assertTrue(any("real completion" in error for error in self._lint(mutate)))

    def test_missing_recovery_schema_case_fails(self) -> None:
        def mutate(fixture):
            fixture["schema_validation_cases"] = [row for row in fixture["schema_validation_cases"] if row["name"] != "single_submit_recovery_receipt"]
        self.assertTrue(any("schema cases are incomplete" in error for error in self._lint(fixture_mutation=mutate)))

    def test_bad_real_receipt_signature_fails(self) -> None:
        def mutate(fixture):
            fixture["single_submit_recovery_kat"]["receipt"]["signature_proof"]["signature"] = "A" * 86
        self.assertTrue(any("KAT invalid" in error for error in self._lint(fixture_mutation=mutate)))

    def test_changed_real_completion_bytes_fails(self) -> None:
        def mutate(fixture):
            fixture["single_submit_recovery_kat"]["expected_outcome"]["completion_attestation"]["new_model_generation_ref"] += 1
        self.assertTrue(any("output mismatch" in error for error in self._lint(fixture_mutation=mutate)))

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
