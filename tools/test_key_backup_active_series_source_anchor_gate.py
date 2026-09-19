"""Mutation tests for the active-series canonical source-anchor closure."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import key_backup_active_series_source_anchor as gate
from tools.artifact_lint.core import Lint


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class KeyBackupActiveSeriesSourceAnchorGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = {
            gate.ACTIVE_SERIES_SCHEMA.resolve(): read(gate.ACTIVE_SERIES_SCHEMA),
            gate.KEYS_OPERATIONS_SCHEMA.resolve(): read(gate.KEYS_OPERATIONS_SCHEMA),
            gate.EVENT_PAYLOAD_SCHEMA.resolve(): read(gate.EVENT_PAYLOAD_SCHEMA),
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
            gate.check_key_backup_active_series_source_anchor(lint)
            return lint.errors
        finally:
            gate.load_json = original

    def assert_red(self, mutate, marker: str) -> None:
        errors = self.run_gate(mutate)
        self.assertTrue(any(marker in error for error in errors), errors)

    def test_complete_contract_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_source_ref_alias_fails(self) -> None:
        def mutate(documents: dict) -> None:
            schema = documents[gate.ACTIVE_SERIES_SCHEMA.resolve()]
            schema["properties"]["source_ref"] = schema["properties"].pop("source_commit_ref")
            schema["required"][schema["required"].index("source_commit_ref")] = "source_ref"

        self.assert_red(mutate, "require source_commit_ref exactly once")

    def test_full_committed_event_ref_members_fail(self) -> None:
        def mutate(documents: dict) -> None:
            anchor = documents[gate.ACTIVE_SERIES_SCHEMA.resolve()]["$defs"]["source_commit_ref"]
            anchor["properties"]["commit_ref"] = {"type": "object"}

        self.assert_red(mutate, "exactly two members")

    def test_realm_commit_id_cannot_weaken_to_object(self) -> None:
        def mutate(documents: dict) -> None:
            anchor = documents[gate.ACTIVE_SERIES_SCHEMA.resolve()]["$defs"]["source_commit_ref"]
            anchor["properties"]["realm_commit_id"] = {"type": "object"}

        self.assert_red(mutate, "strong RealmCommitId")

    def test_source_anchor_cannot_be_open(self) -> None:
        def mutate(documents: dict) -> None:
            documents[gate.ACTIVE_SERIES_SCHEMA.resolve()]["$defs"]["source_commit_ref"]["additionalProperties"] = True

        self.assert_red(mutate, "must remain closed")

    def test_projection_cannot_reuse_payload_name(self) -> None:
        def mutate(documents: dict) -> None:
            projection = documents[gate.KEYS_OPERATIONS_SCHEMA.resolve()]["$defs"]["backup_active_series_state"]
            projection["properties"]["source_commit_ref"] = projection["properties"].pop("authority_commit_id")
            projection["required"][projection["required"].index("authority_commit_id")] = "source_commit_ref"

        self.assert_red(mutate, "projection provenance")

    def test_registry_must_pin_canonical_shape(self) -> None:
        def mutate(documents: dict) -> None:
            registry = documents[gate.CONTRACT_REGISTRY.resolve()]["event_kind_registry"]["event_kinds"]
            row = gate._find(registry, "event_kind", gate.EVENT_KIND)
            row["payload"] = "Key backup active series selection."
            row["result_writes"][0]["notes"] = "Active series selection."

        self.assert_red(mutate, "does not pin source_commit_ref")

    def test_fixture_cannot_drop_legacy_alias_rejection(self) -> None:
        def mutate(documents: dict) -> None:
            fixture = documents[gate.FIXTURE.resolve()]
            fixture["schema_validation_cases"] = [
                case
                for case in fixture["schema_validation_cases"]
                if case.get("name") != "key_backup_active_series_source_ref_alias_rejected"
            ]

        self.assert_red(mutate, "schema fixture omits")

    def test_runner_invokes_gate(self) -> None:
        source = (ROOT / "tools/artifact_lint/runner.py").read_text(encoding="utf-8")
        self.assertIn("check_key_backup_active_series_source_anchor(lint)", source)


if __name__ == "__main__":
    unittest.main()
