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
    "agent-membership-cascade.schema.json",
    "account-data-encrypted-value.schema.json",
    "event-batch-receipt.schema.json",
    "key-backup.schema.json",
    "key-backup-active-series.schema.json",
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

    def test_contact_draft_kind_specialization_fails(self) -> None:
        def mutate(schema) -> None:
            branch = schema["$defs"]["contact_operation_outcome"]["oneOf"][0]
            branch["properties"]["event_draft"] = {
                "allOf": [
                    {"$ref": "./principal-operations.schema.json#/$defs/prepared_event_draft"},
                    {"properties": {"kind": {"const": "contact.request"}}},
                ]
            }

        errors = self._lint("contact-operations.schema.json", mutate)
        self.assertTrue(any("direct generic draft reference" in error for error in errors), errors)

    def test_cleanup_status_mirror_fails(self) -> None:
        def mutate(schema) -> None:
            record = schema["$defs"]["agent_cleanup_record"]
            record["properties"]["status"] = {"type": "string"}

        errors = self._lint("agent-membership-cascade.schema.json", mutate)
        self.assertTrue(any("derive status" in error for error in errors), errors)

    def test_account_data_digest_mirror_fails(self) -> None:
        def mutate(schema) -> None:
            schema["properties"]["ciphertext_digest"] = {"type": "object"}

        errors = self._lint("account-data-encrypted-value.schema.json", mutate)
        self.assertTrue(any("duplicates local digests" in error for error in errors), errors)

    def test_receipt_item_digest_mirror_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["event_receipt_item"]["properties"]["event_digest"] = {"type": "object"}

        errors = self._lint("event-batch-receipt.schema.json", mutate)
        self.assertTrue(any("derive event_digest from event_id" in error for error in errors), errors)

    def test_receipt_frontier_mirror_fails(self) -> None:
        def mutate(schema) -> None:
            schema["properties"]["frontier"] = {"type": "object"}

        errors = self._lint("event-batch-receipt.schema.json", mutate)
        self.assertTrue(any("must not claim an unscoped partial frontier" in error for error in errors), errors)

    def test_special_scope_digest_mirror_fails(self) -> None:
        def mutate(schema) -> None:
            scope = schema["$defs"]["device_reanchor_scope"]
            scope["properties"]["reanchor_digest"] = {"type": "string"}

        errors = self._lint("event-batch-receipt.schema.json", mutate)
        self.assertTrue(any("derive typed Event digests" in error for error in errors), errors)

    def test_key_backup_generation_string_fails(self) -> None:
        def mutate(schema) -> None:
            schema["properties"]["frontier_ref"]["properties"]["device_generation_ref"] = {
                "type": "string",
            }

        errors = self._lint("key-backup.schema.json", mutate)
        self.assertTrue(any("canonical PCR generation integer" in error for error in errors), errors)

    def test_governance_descriptor_digest_mirror_fails(self) -> None:
        def mutate(schema) -> None:
            descriptors = schema["$defs"]["typed_proof_material"]["properties"]["event_ids"]
            descriptors["items"] = {
                "type": "object",
                "required": ["event_id"],
                "properties": {
                    "event_id": {"$ref": "./common-ids.schema.json#/$defs/event_id"}
                },
                "additionalProperties": False,
            }

        errors = self._lint("mls-governance-proof-bundle.schema.json", mutate)
        self.assertTrue(any("direct EventId set" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
