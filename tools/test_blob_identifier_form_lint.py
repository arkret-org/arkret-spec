"""Mutation tests for metadata BlobId versus content-addressed BlobRef closure."""

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
    "common-ids.schema.json",
    "blob.schema.json",
    "call-recording-artifact.schema.json",
)


class BlobIdentifierFormLintTest(unittest.TestCase):
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
            if path.parent.resolve() == SCHEMA_DIR.resolve() and path.name in documents:
                return documents[path.name]
            return original_load_json(lint, path)

        schemas.load_json = load_json_with_mutation
        try:
            lint = schemas.Lint()
            schemas.check_blob_identifier_form_closure(lint)
            return lint.errors
        finally:
            schemas.load_json = original_load_json

    def test_current_forms_are_disjoint(self) -> None:
        self.assertEqual(self._lint(), [])

    def test_blob_ref_uuid_union_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["blob_ref"]["pattern"] = (
                r"^ak:blob:(?:[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}|(?:sha256|blake3):[0-9a-f]{64})$"
            )

        errors = self._lint("common-ids.schema.json", mutate)
        self.assertTrue(any("content-addressed form only" in error for error in errors), errors)

    def test_blob_metadata_content_ref_identity_fails(self) -> None:
        def mutate(schema) -> None:
            schema["required"].append("blob_ref")
            schema["properties"]["blob_ref"] = {
                "$ref": "./common-ids.schema.json#/$defs/blob_ref"
            }

        errors = self._lint("blob.schema.json", mutate)
        self.assertTrue(any("must not restore" in error for error in errors), errors)

    def test_nested_recording_digest_restore_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["recording_encryption"]["properties"]["ciphertext_digest"] = {
                "$ref": "#/$defs/digest"
            }

        errors = self._lint("call-recording-artifact.schema.json", mutate)
        self.assertTrue(any("derive the ciphertext commitment" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
