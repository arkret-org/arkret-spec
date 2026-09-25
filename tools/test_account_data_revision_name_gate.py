"""Mutation tests for the canonical account-data CAS revision field."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import account_data_revision_name as gate
from tools.artifact_lint.core import Lint


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class AccountDataRevisionNameGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = {
            path.resolve(): read(path)
            for path in (
                gate.EVENT_SCHEMA,
                gate.OPERATIONS_SCHEMA,
                gate.CONTRACT_REGISTRY,
                gate.KEY_REGISTRY,
                gate.ERROR_MAPPING,
                gate.VECTOR_REGISTRY,
                gate.FIXTURE,
            )
        }

    def run_gate(self, mutate=None) -> list[str]:
        documents = copy.deepcopy(self.documents)
        if mutate is not None:
            mutate(documents)
        original = gate.load_json

        def load_json(lint, path):  # type: ignore[no-untyped-def]
            resolved = Path(path).resolve()
            return documents.get(resolved) if resolved in documents else original(lint, path)

        gate.load_json = load_json
        try:
            lint = Lint()
            gate.check_account_data_revision_name(lint)
            return lint.errors
        finally:
            gate.load_json = original

    def assert_red(self, mutate, marker: str) -> None:
        errors = self.run_gate(mutate)
        self.assertTrue(any(marker in error for error in errors), errors)

    def test_complete_contract_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_old_alias_cannot_replace_canonical_property(self) -> None:
        def mutate(documents: dict) -> None:
            payload = documents[gate.EVENT_SCHEMA.resolve()]["$defs"]["account_data_set_payload"]
            payload["properties"]["expected_revision"] = payload["properties"].pop("expected_server_revision")

        self.assert_red(mutate, "legacy expected_revision alias is forbidden")

    def test_dual_fields_cannot_be_accepted(self) -> None:
        def mutate(documents: dict) -> None:
            documents[gate.EVENT_SCHEMA.resolve()]["$defs"]["account_data_set_payload"]["additionalProperties"] = True

        self.assert_red(mutate, "must remain closed")

    def test_revision_type_cannot_be_weakened(self) -> None:
        def mutate(documents: dict) -> None:
            properties = documents[gate.EVENT_SCHEMA.resolve()]["$defs"]["account_data_set_payload"]["properties"]
            properties["expected_server_revision"] = {"type": "object"}

        self.assert_red(mutate, "non-negative integer")

    def test_agent_draft_guard_cannot_use_shared_name(self) -> None:
        def mutate(documents: dict) -> None:
            branch = documents[gate.EVENT_SCHEMA.resolve()]["$defs"]["account_data_set_payload"]["allOf"][0]
            branch["if"]["properties"]["expected_revision"] = branch["if"]["properties"].pop(
                "expected_server_revision"
            )

        self.assert_red(mutate, "both agent-draft source branches")

    def test_operation_schema_description_is_guarded(self) -> None:
        def mutate(documents: dict) -> None:
            schema = documents[gate.OPERATIONS_SCHEMA.resolve()]
            schema["description"] = schema["description"].replace("expected_server_revision", "expected_revision")

        self.assert_red(mutate, "legacy field name")

    def test_private_effect_contract_is_guarded(self) -> None:
        def mutate(documents: dict) -> None:
            write = documents[gate.CONTRACT_REGISTRY.resolve()]["event_kind_registry"]["actor_private_contracts"]["event_writes"][gate.EVENT_KIND]
            write["concurrency"]["precondition"] = "payload.expected_revision equals current"

        self.assert_red(mutate, "private effect contract uses the shared revision field")

    def test_fixture_cannot_drop_alias_rejection(self) -> None:
        def mutate(documents: dict) -> None:
            fixture = documents[gate.FIXTURE.resolve()]
            fixture["schema_validation_cases"] = [
                case
                for case in fixture["schema_validation_cases"]
                if case["name"] != "account_data_set_expected_revision_alias_rejected"
            ]

        self.assert_red(mutate, "schema cases must be exactly")

    def test_fixture_dual_case_must_carry_both_names(self) -> None:
        def mutate(documents: dict) -> None:
            fixture = documents[gate.FIXTURE.resolve()]
            case = gate._find(
                fixture["schema_validation_cases"], "name", "account_data_set_dual_revision_fields_rejected"
            )
            case["instance"].pop("expected_revision")

        self.assert_red(mutate, "dual-field rejection case")

    def test_runner_invokes_gate(self) -> None:
        source = (ROOT / "tools/artifact_lint/runner.py").read_text(encoding="utf-8")
        self.assertIn("check_account_data_revision_name(lint)", source)


if __name__ == "__main__":
    unittest.main()
