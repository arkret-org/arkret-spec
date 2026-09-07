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

    def test_counter_presence_selects_one_closed_branch(self):
        standard = self.envelope()
        self.validator.validate(standard)
        for counter in (0, 7, 9007199254740991):
            exporter = copy.deepcopy(standard)
            exporter["encryption_context"]["counter"] = counter
            self.validator.validate(exporter)
        for counter in (None, False, -1, "0", 0.5, 9007199254740992, 18446744073709551615):
            with self.subTest(counter=counter):
                invalid = copy.deepcopy(standard)
                invalid["encryption_context"]["counter"] = counter
                self.assertFalse(self.validator.is_valid(invalid))

    def test_epoch_and_extra_fields_obey_canonical_envelope(self):
        value = self.envelope()
        value["encryption_context"]["epoch"] = 9007199254740991
        self.validator.validate(value)
        value["encryption_context"]["epoch"] += 1
        self.assertFalse(self.validator.is_valid(value))
        for context in ({"scheme": "mls_rfc9420"}, {"counter": 0, "unknown": True}):
            value = self.envelope()
            value["encryption_context"].update(context)
            self.assertFalse(self.validator.is_valid(value))


if __name__ == "__main__":
    unittest.main()
