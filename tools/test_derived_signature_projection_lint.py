"""Mutation gates for derived signature projections and PCR generation refs."""

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
    "key-backup.schema.json",
    "key-backup-active-series.schema.json",
    "key-backup-unlock-proof.schema.json",
    "recovery-policy.schema.json",
    "recovery-receipt.schema.json",
    "recovery-authority.schema.json",
    "security-transaction.schema.json",
)


class DerivedSignatureProjectionLintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.documents = {
            name: core.parse_json_text((SCHEMA_DIR / name).read_text(encoding="utf-8"))
            for name in SCHEMA_NAMES
        }

    def _lint(self, name: str | None = None, mutation=None) -> list[str]:
        documents = copy.deepcopy(self.documents)
        if name is not None and mutation is not None:
            mutation(documents[name])
        original_load_json = schemas.load_json

        def load_json_with_mutation(lint, path):
            if path.parent.resolve() == SCHEMA_DIR.resolve() and path.name in documents:
                return documents[path.name]
            return original_load_json(lint, path)

        schemas.load_json = load_json_with_mutation
        try:
            lint = schemas.Lint()
            schemas.check_derived_signature_projection_closure(lint)
            return lint.errors
        finally:
            schemas.load_json = original_load_json

    def test_current_projection_contract_is_closed(self) -> None:
        self.assertEqual(self._lint(), [])

    def test_signed_fields_reintroduction_fails(self) -> None:
        def mutate(schema) -> None:
            schema["properties"]["auth_data"]["properties"]["signed_fields"] = {
                "type": "array"
            }

        errors = self._lint("key-backup.schema.json", mutate)
        self.assertTrue(any("must not reintroduce" in error for error in errors), errors)

    def test_compound_generation_string_reintroduction_fails(self) -> None:
        def mutate(schema) -> None:
            schema["$defs"]["source_commit_ref"]["properties"]["device_generation_ref"] = {
                "type": "string",
                "pattern": "^[1-9][0-9]*-[^\\s]+$",
            }

        errors = self._lint("key-backup-active-series.schema.json", mutate)
        self.assertTrue(any("must reuse recovery-session" in error for error in errors), errors)

    def test_completion_event_digest_mirror_reintroduction_fails(self) -> None:
        def mutate(schema) -> None:
            completion = schema["$defs"]["recovery_completion_attestation"]
            completion["properties"]["device_authorization_event_digest"] = {
                "$ref": "#/$defs/digest"
            }

        errors = self._lint("recovery-authority.schema.json", mutate)
        self.assertTrue(
            any("must not restore removed field device_authorization_event_digest" in error for error in errors),
            errors,
        )

    def test_completion_event_id_omission_from_projection_fails(self) -> None:
        def mutate(schema) -> None:
            signature = schema["$defs"]["recovery_completion_attestation"]["properties"][
                "auth_data"
            ]["properties"]["signature"]
            signature["description"] = "base64url signature over an incomplete projection"

        errors = self._lint("recovery-authority.schema.json", mutate)
        self.assertTrue(
            any("must bind device_authorization_event_ref" in error for error in errors), errors
        )


if __name__ == "__main__":
    unittest.main()
