"""Mutation tests for the key-backup envelope source-anchor closure."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import key_backup_envelope_source_anchor as gate
from tools.artifact_lint.core import Lint


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class KeyBackupEnvelopeSourceAnchorGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = {
            gate.ENVELOPE_SCHEMA.resolve(): read(gate.ENVELOPE_SCHEMA),
            gate.ACTIVE_SERIES_SCHEMA.resolve(): read(gate.ACTIVE_SERIES_SCHEMA),
            gate.CONTRACT_REGISTRY.resolve(): read(gate.CONTRACT_REGISTRY),
            gate.FIXTURE.resolve(): read(gate.FIXTURE),
        }

    def run_gate(self, mutate=None) -> list[str]:
        documents = copy.deepcopy(self.documents)
        if mutate is not None:
            mutate(documents)
        original = gate.load_json

        def load_json(lint, path):  # type: ignore[no-untyped-def]
            resolved = Path(path).resolve()
            if resolved in documents:
                return documents[resolved]
            return original(lint, path)

        gate.load_json = load_json
        try:
            lint = Lint()
            gate.check_key_backup_envelope_source_anchor(lint)
            return lint.errors
        finally:
            gate.load_json = original

    def assert_red(self, mutate, marker: str) -> None:
        errors = self.run_gate(mutate)
        self.assertTrue(any(marker in error for error in errors), errors)

    @staticmethod
    def schema_row(documents: dict) -> dict:
        rows = documents[gate.CONTRACT_REGISTRY.resolve()]["schema_registry"]["schemas"]
        return gate._find(rows, "schema_id", gate.SCHEMA_ID)

    def test_complete_contract_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_source_ref_alias_fails(self) -> None:
        def mutate(documents: dict) -> None:
            schema = documents[gate.ENVELOPE_SCHEMA.resolve()]
            schema["properties"]["source_ref"] = schema["properties"].pop("source_commit_ref")

        self.assert_red(mutate, "source_commit_ref property is missing")

    def test_optional_source_cannot_become_required(self) -> None:
        def mutate(documents: dict) -> None:
            documents[gate.ENVELOPE_SCHEMA.resolve()]["required"].append("source_commit_ref")

        self.assert_red(mutate, "must remain optional")

    def test_full_committed_event_ref_member_fails(self) -> None:
        def mutate(documents: dict) -> None:
            anchor = documents[gate.ENVELOPE_SCHEMA.resolve()]["properties"]["source_commit_ref"]
            anchor["properties"]["committed_event_ref"] = {"type": "object"}

        self.assert_red(mutate, "exactly two members")

    def test_realm_commit_id_cannot_weaken(self) -> None:
        def mutate(documents: dict) -> None:
            anchor = documents[gate.ENVELOPE_SCHEMA.resolve()]["properties"]["source_commit_ref"]
            anchor["properties"]["realm_commit_id"] = {"type": "string"}

        self.assert_red(mutate, "strong RealmCommitId")

    def test_generation_cannot_become_string(self) -> None:
        def mutate(documents: dict) -> None:
            anchor = documents[gate.ENVELOPE_SCHEMA.resolve()]["properties"]["source_commit_ref"]
            anchor["properties"]["device_generation_ref"] = {"type": "string"}

        self.assert_red(mutate, "positive integer PCR generation")

    def test_source_anchor_cannot_be_open(self) -> None:
        def mutate(documents: dict) -> None:
            documents[gate.ENVELOPE_SCHEMA.resolve()]["properties"]["source_commit_ref"]["additionalProperties"] = True

        self.assert_red(mutate, "must remain closed")

    def test_builder_cannot_accept_committed_event_ref(self) -> None:
        def mutate(documents: dict) -> None:
            builder = self.schema_row(documents)["authoring_contract"]["successor_builder_input"]
            builder["forbidden_inputs"].remove("CommittedEventRef")

        self.assert_red(mutate, "forbidden-input set is incomplete")

    def test_post_signature_alias_rewrite_cannot_be_allowed(self) -> None:
        def mutate(documents: dict) -> None:
            signing = self.schema_row(documents)["authoring_contract"]["signature_transcription"]
            signing["post_signature_alias_rewrite"] = "allowed"

        self.assert_red(mutate, "post-signature alias rewriting")

    def test_predecessor_chain_cannot_merge_with_source(self) -> None:
        def mutate(documents: dict) -> None:
            predecessor = self.schema_row(documents)["authoring_contract"]["predecessor_chain"]
            predecessor["independent_from_source_commit_ref"] = False

        self.assert_red(mutate, "predecessor chain must remain independent")

    def test_fixture_cannot_drop_string_generation_rejection(self) -> None:
        def mutate(documents: dict) -> None:
            fixture = documents[gate.FIXTURE.resolve()]
            fixture["schema_validation_cases"] = [
                case
                for case in fixture["schema_validation_cases"]
                if case.get("name") != "key_backup_envelope_string_generation_rejected"
            ]

        self.assert_red(mutate, "schema fixture omits")

    def test_fixture_cannot_drop_optional_source_case(self) -> None:
        def mutate(documents: dict) -> None:
            fixture = documents[gate.FIXTURE.resolve()]
            fixture["schema_validation_cases"] = [
                case
                for case in fixture["schema_validation_cases"]
                if case.get("name") != "key_backup_envelope_source_commit_ref_omitted_valid"
            ]

        self.assert_red(mutate, "schema fixture omits")

    def test_schema_predecessor_rules_cannot_disappear(self) -> None:
        def mutate(documents: dict) -> None:
            schema = documents[gate.ENVELOPE_SCHEMA.resolve()]
            schema["allOf"] = [
                rule
                for rule in schema["allOf"]
                if rule.get("if", {}).get("properties", {}).get("series_seq", {}).get("minimum") != 1
            ]

        self.assert_red(mutate, "predecessor rules must remain independent")

    def test_runner_invokes_gate(self) -> None:
        source = (ROOT / "tools/artifact_lint/runner.py").read_text(encoding="utf-8")
        self.assertIn("check_key_backup_envelope_source_anchor(lint)", source)


if __name__ == "__main__":
    unittest.main()
