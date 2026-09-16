"""Closed content branch and canonical-number boundary conformance."""

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


class EncryptedEnvelopeSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schemas = Path(__file__).resolve().parents[1] / "spec/v1/artifacts/schemas"
        resources = []
        for path in schemas.glob("*.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            resources.append((document["$id"], Resource.from_contents(document)))
        cls.validator = Draft202012Validator(
            {"$ref": "https://arkret.org/v1/schemas/encrypted-envelope.schema.json"},
            registry=Registry().with_resources(resources),
        )

    def envelope(self):
        return {
            "version": "1.0",
            "content_type": "application/json",
            "encryption_context": {
                "epoch": 0,
                "group_state_ref": "ak:event:AcWdky_9bM7PKl17K1UxMcj72H3_Ny9PoMhexJ2S-sK0",
            },
            "ciphertext": "AQID",
        }

    def test_standard_context_is_the_only_closed_branch(self):
        standard = self.envelope()
        self.validator.validate(standard)
        with_routing = copy.deepcopy(standard)
        with_routing["encryption_context"]["routing_context"] = {
            "target_ref": "ak:event:AcWdky_9bM7PKl17K1UxMcj72H3_Ny9PoMhexJ2S-sK0",
            "routing_tag": "A" * 43,
        }
        self.validator.validate(with_routing)
        for field, value in (("counter", 0), ("scheme", "mls_rfc9420"), ("unknown", True)):
            with self.subTest(field=field):
                invalid = copy.deepcopy(standard)
                invalid["encryption_context"][field] = value
                self.assertFalse(self.validator.is_valid(invalid))
        for missing in ("epoch", "group_state_ref"):
            with self.subTest(missing=missing):
                invalid = copy.deepcopy(standard)
                del invalid["encryption_context"][missing]
                self.assertFalse(self.validator.is_valid(invalid))

    def test_epoch_and_extra_fields_obey_canonical_envelope(self):
        value = self.envelope()
        value["encryption_context"]["epoch"] = 9007199254740991
        self.validator.validate(value)
        value["encryption_context"]["epoch"] += 1
        self.assertFalse(self.validator.is_valid(value))
        for context in ({"scheme": "mls_rfc9420"}, {"unknown": True}):
            value = self.envelope()
            value["encryption_context"].update(context)
            self.assertFalse(self.validator.is_valid(value))


if __name__ == "__main__":
    unittest.main()
