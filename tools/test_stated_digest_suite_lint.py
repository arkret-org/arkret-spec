"""Mutation tests for domain-selectable Blob versus fixed-SHA digest sources."""

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
    "security-transaction.schema.json",
    "event-payload.schema.json",
    "service-operation-dtos.schema.json",
    "erasure-verification-stub.schema.json",
    "realm-genesis.schema.json",
)


class StatedDigestSuiteLintTest(unittest.TestCase):
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
            schemas.check_stated_digest_suite_sources(lint)
            return lint.errors
        finally:
            schemas.load_json = original_load_json

    def test_current_suite_sources_are_closed(self) -> None:
        self.assertEqual(self._lint(), [])

    def test_prepared_event_draft_multi_suite_alias_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["prepared_event_draft"]["properties"]["event_digest"]["$ref"] = "#/$defs/digest"

        errors = self._lint("principal-operations.schema.json", mutate)
        self.assertTrue(any("fixed current-v1 SHA-256" in error for error in errors), errors)

    def test_prepared_event_draft_realm_selector_restore_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["prepared_event_draft"]["properties"]["event_digest"][
                "x-arkret-digest-suite-source"
            ] = "realm_digest_algorithm"

        errors = self._lint("principal-operations.schema.json", mutate)
        self.assertTrue(any("must not restore a Realm-selected" in error for error in errors), errors)

    def test_prepared_plan_realm_suite_fails(self) -> None:
        def mutate(schema) -> None:
            schema["properties"]["prepared_plan_digest"]["$ref"] = "#/$defs/digest"

        errors = self._lint("security-transaction.schema.json", mutate)
        self.assertTrue(any("fixed sha256_digest" in error for error in errors), errors)

    def test_mls_blob_sha256_narrowing_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["mls_genesis_payload"]["properties"]["group_info_ref"]["pattern"] = (
                "^ak:blob:sha256:[0-9a-f]{64}$"
            )

        errors = self._lint("event-payload.schema.json", mutate)
        self.assertTrue(any("admit sha256 and blake3" in error for error in errors), errors)

    def test_founding_descriptor_digest_restore_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["founding_device_descriptor"]["properties"]["device_key_digest"] = {
                "$ref": "./account-operations.schema.json#/$defs/sha256_digest"
            }

        errors = self._lint("realm-genesis.schema.json", mutate)
        self.assertTrue(any("must not restore derived device_key_digest" in error for error in errors), errors)

    def test_realm_commit_fact_digest_is_fixed_sha256(self) -> None:
        schema = core.parse_json_text((SCHEMA_DIR / "realm-commit.schema.json").read_text())
        self.assertEqual(schema["properties"]["producer_signer_fact_digest"]["$ref"], "./account-operations.schema.json#/$defs/sha256_digest")
        digest = core.parse_json_text((SCHEMA_DIR / "account-operations.schema.json").read_text())["$defs"]["sha256_digest"]
        self.assertEqual(digest["pattern"], "^sha256:[0-9a-f]{64}$")



if __name__ == "__main__":
    unittest.main()
