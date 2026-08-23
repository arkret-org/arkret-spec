"""Mutation tests for canonical prepared-draft and device-pairing sources."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import core, schemas

SCHEMA_DIR = ROOT / "spec" / "v1" / "artifacts" / "schemas"
SCHEMA_NAMES = (
    "principal-operations.schema.json",
    "contact-operations.schema.json",
    "agent-operations.schema.json",
)


class CanonicalWireSourceLintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.documents = {
            name: core.parse_json_text((SCHEMA_DIR / name).read_text(encoding="utf-8"))
            for name in SCHEMA_NAMES
        }

    def _lint(self, schema_name=None, mutation=None) -> list[str]:
        documents = copy.deepcopy(self.documents)
        if schema_name is not None and mutation is not None:
            mutation(documents[schema_name])
        original_load_json = schemas.load_json

        def load_json_with_mutation(lint, path):
            if path.name in documents and path.parent.resolve() == SCHEMA_DIR.resolve():
                return documents[path.name]
            return original_load_json(lint, path)

        schemas.load_json = load_json_with_mutation
        try:
            lint = schemas.Lint()
            schemas.check_canonical_wire_source_closure(lint)
            return lint.errors
        finally:
            schemas.load_json = original_load_json

    def test_current_schemas_use_canonical_sources(self) -> None:
        self.assertEqual(self._lint(), [])

    def test_draft_event_id_mirror_fails(self) -> None:
        def mutate(schema) -> None:
            draft = schema["$defs"]["prepared_event_draft"]
            draft["properties"]["event_id"] = {"type": "string"}

        errors = self._lint("principal-operations.schema.json", mutate)
        self.assertTrue(any("define only bytes and typed digest" in error for error in errors), errors)

    def test_new_sidecar_id_mirror_fails(self) -> None:
        def mutate(schema) -> None:
            branch = schema["$defs"]["sidecar_ensure_outcome"]["oneOf"][0]
            branch["properties"]["sidecar_id"] = {"type": "string"}

        errors = self._lint("principal-operations.schema.json", mutate)
        self.assertTrue(any("Sidecar new prepare duplicates" in error for error in errors), errors)

    def test_device_signature_mirror_fails(self) -> None:
        def mutate(schema) -> None:
            pair = schema["$defs"]["account_device_pair_request_body"]
            pair["properties"]["device_signature"] = {"type": "object"}

        errors = self._lint("agent-operations.schema.json", mutate)
        self.assertTrue(any("device pair commit duplicates" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
