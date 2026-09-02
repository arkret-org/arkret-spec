"""evidence_kind single-source adapter routing gate.

method history evidence carries no adapter_version: the wire evidence_kind reverse-resolves
through did-method-adapter-registry.json method_evidence_kind, which must therefore stay
unique across active adapters and cover exactly the schema branches.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import core, schemas


SCHEMA_PATH = ROOT / "spec" / "v1" / "artifacts" / "schemas" / "identity-resolution.schema.json"
REGISTRY_PATH = ROOT / "spec" / "v1" / "artifacts" / "registry" / "did-method-adapter-registry.json"


class _MutatingLint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = core.parse_json_text(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.registry = core.parse_json_text(REGISTRY_PATH.read_text(encoding="utf-8"))

    def _run(self, schema_mutation=None, registry_mutation=None) -> list[str]:
        schema = copy.deepcopy(self.schema)
        registry = copy.deepcopy(self.registry)
        if schema_mutation is not None:
            schema_mutation(schema)
        if registry_mutation is not None:
            registry_mutation(registry)
        original_load_json = schemas.load_json

        def load_json_with_mutation(lint, path):
            if path.resolve() == SCHEMA_PATH.resolve():
                return schema
            if path.resolve() == REGISTRY_PATH.resolve():
                return registry
            return original_load_json(lint, path)

        schemas.load_json = load_json_with_mutation
        try:
            lint = schemas.Lint()
            schemas.check_did_method_adapter_evidence_kind_routing(lint)
            return lint.errors
        finally:
            schemas.load_json = original_load_json


class EvidenceKindRoutingTest(_MutatingLint):
    def test_current_contract_is_closed(self) -> None:
        self.assertEqual(self._run(), [])

    def test_duplicate_method_evidence_kind_fails(self) -> None:
        def mutate(registry) -> None:
            active = [row for row in registry["adapters"] if row.get("status") == "active"]
            active[1]["method_evidence_kind"] = active[0]["method_evidence_kind"]

        errors = self._run(registry_mutation=mutate)
        self.assertTrue(any("reuses method_evidence_kind" in error for error in errors), errors)

    def test_adapter_version_reintroduction_fails(self) -> None:
        def mutate(schema) -> None:
            branch = schema["$defs"]["did_key_method_history_evidence"]
            branch["properties"]["adapter_version"] = {"const": "did:key:1"}
            branch["required"].insert(0, "adapter_version")

        errors = self._run(schema_mutation=mutate)
        self.assertTrue(any("adapter_version must be derived from evidence_kind" in error for error in errors), errors)

    def test_branch_kind_without_active_adapter_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["did_key_method_history_evidence"]["properties"]["evidence_kind"]["const"] = "did_key_orphan"

        errors = self._run(schema_mutation=mutate)
        self.assertTrue(any("does not reverse-resolve" in error for error in errors), errors)
        self.assertTrue(any("has no $defs/method_history_evidence branch" in error for error in errors), errors)

    def test_inactive_adapter_kind_is_not_routable(self) -> None:
        def mutate(registry) -> None:
            for row in registry["adapters"]:
                if row.get("method_evidence_kind") == "did_web_document":
                    row["status"] = "retired"

        errors = self._run(registry_mutation=mutate)
        self.assertTrue(any("'did_web_document' does not reverse-resolve" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
