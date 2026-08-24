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
    "contact-operations.schema.json",
    "direct-conversation-operations.schema.json",
    "service-operation-dtos.schema.json",
)


class ContactEventIdDigestMirrorLintTest(unittest.TestCase):
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
            schemas.check_event_id_digest_mirror_removals(lint)
            return lint.errors
        finally:
            schemas.load_json = original_load_json

    def test_current_contact_contract_is_closed(self) -> None:
        self.assertEqual(self._lint(), [])

    def test_request_digest_mirror_reintroduction_fails(self) -> None:
        def mutate(schema) -> None:
            core = schema["$defs"]["request_acceptance_receipt_core"]
            core["properties"]["request_digest"] = {
                "$ref": "./principal-operations.schema.json#/$defs/digest"
            }

        errors = self._lint("contact-operations.schema.json", mutate)
        self.assertTrue(any("request_digest must be derived" in error for error in errors), errors)

    def test_current_head_digest_mirror_reintroduction_fails(self) -> None:
        def mutate(schema) -> None:
            proof = schema["$defs"]["contact_current_proof"]
            proof["properties"]["head_digest"] = {
                "$ref": "./principal-operations.schema.json#/$defs/digest"
            }

        errors = self._lint("contact-operations.schema.json", mutate)
        self.assertTrue(any("head_digest must be derived" in error for error in errors), errors)

    def test_mirror_signed_event_digest_reintroduction_fails(self) -> None:
        def mutate(schema) -> None:
            receipt = schema["$defs"]["peer_contact_mirror_receipt"]
            receipt["required"].append("signed_event_digest")

        errors = self._lint("contact-operations.schema.json", mutate)
        self.assertTrue(any("signed_event_digest must be derived" in error for error in errors), errors)

    def test_founding_receipt_provision_digest_reintroduction_fails(self) -> None:
        def mutate(schema) -> None:
            branch = schema["$defs"]["direct_conversation_founding_acceptance_receipt"][
                "properties"
            ]["authorization_core"]["oneOf"][1]
            branch["properties"]["agent_provision_digest"] = {
                "$ref": "./principal-operations.schema.json#/$defs/digest"
            }

        errors = self._lint("direct-conversation-operations.schema.json", mutate)
        self.assertTrue(any("agent_provision_digest must be derived" in error for error in errors), errors)

    def test_founding_submission_provision_digest_reintroduction_fails(self) -> None:
        def mutate(schema) -> None:
            branch = schema["$defs"]["DirectConversationFoundingAuthorityEvidence"]["oneOf"][1]
            branch["required"].append("agent_provision_digest")

        errors = self._lint("service-operation-dtos.schema.json", mutate)
        self.assertTrue(any("agent_provision_digest must be derived" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
