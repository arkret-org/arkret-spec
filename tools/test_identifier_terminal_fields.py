"""Canonical identity carriers reject empty values and another ID namespace."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "spec/v1/artifacts/schemas"


class IdentifierTerminalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in SCHEMAS.glob("*.json")
        }
        cls.registry = Registry().with_resources(
            (document["$id"], Resource.from_contents(document))
            for document in cls.documents.values() if "$id" in document
        )

    def validator(self, file_name, pointer):
        return Draft202012Validator(
            {"$ref": self.documents[file_name]["$id"] + "#" + pointer},
            registry=self.registry,
        )

    def test_agent_participation_response_uses_stable_core_identity(self):
        validator = self.validator("agent-operations.schema.json", "/$defs/agent_participation_response_body")
        body = {"agent_id": "ak:did_core:web:agent.example", "participation_entries": []}
        validator.validate(body)
        for value in ("", "agent.example", "did:web:agent.example", "ak:device:01904100-0000-7000-8000-000000000001"):
            self.assertTrue(list(validator.iter_errors({**body, "agent_id": value})), value)

    def test_keypackage_claim_authorization_coordinates_are_event_ids(self):
        fixture = json.loads((ROOT / "spec/v1/artifacts/fixtures/keypackage-lifecycle-fixture.json").read_text(encoding="utf-8"))
        record = dict(fixture["schema_validation_cases"][2]["instance"])
        # The existing negative case adds an unregistered proof member to an
        # otherwise valid claim record; it is not part of the canonical record.
        record.pop("endpoint_signature")
        event_id = record["device_authorize_event_id"]
        validator = self.validator("keypackage-operations.schema.json", "/$defs/keypackage_claim_record")
        validator.validate(record)
        for field in ("device_authorize_event_id", "agent_key_authorize_event_id"):
            field_validator = self.validator("keypackage-operations.schema.json", "/$defs/keypackage_claim_record/properties/" + field)
            field_validator.validate(event_id)
            for value in ("", "authorize-event", event_id.replace("ak:event:", "ak:message:"), "did:web:agent.example"):
                self.assertTrue(list(field_validator.iter_errors(value)), (field, value))

    def test_space_view_parent_is_nullable_canonical_space_identity(self):
        validator = self.validator("service-operation-dtos.schema.json", "/$defs/SpaceView/properties/parent_space_id")
        fixture = json.loads((ROOT / "spec/v1/artifacts/fixtures/keypackage-lifecycle-fixture.json").read_text(encoding="utf-8"))
        event_id = fixture["schema_validation_cases"][2]["instance"]["device_authorize_event_id"]
        # This check exercises the lexical carrier, not creation provenance.
        validator.validate(event_id.replace("ak:event:", "ak:space:"))
        validator.validate(None)
        for value in ("", event_id, "space-a", "did:web:space.example"):
            self.assertTrue(list(validator.iter_errors(value)), value)

    def test_organization_handle_names_the_stable_organization_core(self):
        validator = self.validator("handle-claim.schema.json", "/$defs/claim_variant")
        validator.validate({"kind": "organization_handle", "organization_id": "ak:did_core:web:organization.example"})
        validator.validate({"kind": "handle_binding"})
        for value in ("", "acme", "organization.example", "did:web:organization.example", "ak:device:01904100-0000-7000-8000-000000000001"):
            self.assertTrue(list(validator.iter_errors({"kind": "organization_handle", "organization_id": value})), value)


if __name__ == "__main__":
    unittest.main()
