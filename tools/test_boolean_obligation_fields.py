"""Verify owned obligation booleans reject old and ambiguous wire names."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "spec/v1/artifacts/schemas"


class ObligationFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in SCHEMAS.glob("*.json")
        }
        cls.registry = Registry().with_resources(
            (document["$id"], Resource.from_contents(document))
            for document in cls.documents.values()
            if "$id" in document
        )

    def validator(self, file_name, pointer):
        return Draft202012Validator(
            {"$ref": self.documents[file_name]["$id"] + "#" + pointer},
            registry=self.registry,
        )

    def test_registration_obligations_keep_default_and_reject_aliases(self):
        for definition, field in [
            ("account_registration_verification_policy", "verification_required"),
            ("account_registration_invitation_policy", "invitation_required"),
        ]:
            with self.subTest(field=field):
                validator = self.validator("account-operations.schema.json", "/$defs/" + definition)
                validator.validate({})
                validator.validate({field: False})
                validator.validate({field: True})
                for invalid in ({"required": True}, {field: True, "required": True}, {field: 1}, {field: None}):
                    self.assertTrue(list(validator.iter_errors(invalid)), invalid)
                properties = self.documents["account-operations.schema.json"]["$defs"][definition]["properties"]
                self.assertIs(properties[field]["default"], False)
                self.assertEqual(properties[field]["x-arkret-member-role"], "obligation")

    def test_preview_token_obligations_preserve_required_binding(self):
        pointer = "/$defs/preview_policy_payload/properties/value/properties/token"
        validator = self.validator("event-payload.schema.json", pointer)
        valid = {"token_required": True, "target_digest_binding_required": True}
        validator.validate({})
        validator.validate(valid)
        for invalid in (
            {"required": True},
            {"bind_target_digest": True},
            {**valid, "required": True},
            {**valid, "bind_target_digest": True},
            {"target_digest_binding_required": False},
            {"token_required": "true"},
        ):
            self.assertTrue(list(validator.iter_errors(invalid)), invalid)

    def test_field_definition_uses_an_explicit_obligation(self):
        validator = self.validator("applet-edge-operations.schema.json", "/$defs/field_definition")
        validator.validate({"value_kind": "string"})
        validator.validate({"value_kind": "string", "field_required": True})
        validator.validate({"value_kind": "string", "field_required": False})
        for invalid in (
            {"field_required": True},
            {"value_kind": "string", "required": True},
            {"value_kind": "string", "field_required": False, "required": False},
            {"value_kind": "string", "field_required": "false"},
        ):
            self.assertTrue(list(validator.iter_errors(invalid)), invalid)


if __name__ == "__main__":
    unittest.main()
