"""Mutation coverage for the Current<Family> bijection and Result prohibition."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import naming_contracts
from tools.artifact_lint.core import ARTIFACTS

SCHEMA = ARTIFACTS / "schemas" / "current-state.schema.json"
REGISTRY = ARTIFACTS / "registry" / "current-state-registry.json"
OTHER_SCHEMA = ARTIFACTS / "schemas" / "keys-operations.schema.json"


class CurrentStateNamingTest(unittest.TestCase):
    def _run(self, mutations=None) -> list[str]:
        mutations = mutations or {}
        original_load_json = naming_contracts.load_json
        documents = {}
        for path, mutate in mutations.items():
            document = copy.deepcopy(original_load_json(naming_contracts.Lint(), path))
            mutate(document)
            documents[path.resolve()] = document

        def load_json_with_mutation(lint, path):
            return documents.get(path.resolve(), original_load_json(lint, path))

        naming_contracts.load_json = load_json_with_mutation
        try:
            lint = naming_contracts.Lint()
            naming_contracts.check_current_state_naming(lint)
            return lint.errors
        finally:
            naming_contracts.load_json = original_load_json

    def test_registry_derived_names_pass(self) -> None:
        self.assertEqual(self._run(), [])

    def test_envelope_renamed_away_from_its_kind_fails(self) -> None:
        def mutate(schema):
            schema["$defs"]["strand_snapshot"] = schema["$defs"].pop("current_strand")

        errors = self._run({SCHEMA: mutate})
        self.assertTrue(any("`$defs/current_strand` envelope" in e for e in errors), errors)

    def test_unregistered_result_envelope_fails(self) -> None:
        def mutate(schema):
            schema["$defs"]["current_invented"] = {"type": "object"}

        errors = self._run({SCHEMA: mutate})
        self.assertTrue(any("no registered state_kind" in e for e in errors), errors)

    def test_schema_ref_pointing_off_the_derived_name_fails(self) -> None:
        def mutate(registry):
            registry["state_kinds"][0]["schema_ref"] = (
                "schemas/current-state.schema.json#/$defs/realm_authority_root_outcome"
            )

        errors = self._run({REGISTRY: mutate})
        self.assertTrue(any("must resolve to" in e for e in errors), errors)

    def test_result_tail_in_another_schema_fails(self) -> None:
        def mutate(schema):
            schema["$defs"]["backup_series_erase_result"] = {"type": "object"}

        errors = self._run({OTHER_SCHEMA: mutate})
        self.assertTrue(
            any("not a protocol type role" in e for e in errors), errors
        )

    def test_the_runner_actually_executes_the_check(self) -> None:
        """The standard runner must execute the naming contract."""
        runner_source = (ROOT / "tools" / "artifact_lint" / "runner.py").read_text(encoding="utf-8")
        self.assertIn("check_current_state_naming(lint)", runner_source)

    def test_registered_envelope_missing_from_root_fails(self) -> None:
        def mutate(schema):
            schema["oneOf"] = [branch for branch in schema["oneOf"]
                               if branch["$ref"] != "#/$defs/current_realm_archive"]

        errors = self._run({SCHEMA: mutate})
        self.assertTrue(any("missing from root oneOf" in error for error in errors), errors)

    def test_unregistered_root_envelope_fails(self) -> None:
        def mutate(schema):
            schema["oneOf"].append({"$ref": "#/$defs/invented_result"})

        errors = self._run({SCHEMA: mutate})
        self.assertTrue(any("unregistered current envelopes in root" in error for error in errors), errors)

    def test_duplicate_root_envelope_fails(self) -> None:
        def mutate(schema):
            schema["oneOf"].append(dict(schema["oneOf"][0]))

        errors = self._run({SCHEMA: mutate})
        self.assertTrue(any("repeats an envelope" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
