"""Managed-actor proofs bind one typed audience identity."""

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ARTIFACTS = Path(__file__).resolve().parents[1] / "spec/v1/artifacts"


class AppletAuthoringProofSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        documents = [json.loads(path.read_text(encoding="utf-8"))
                     for path in (ARTIFACTS / "schemas").glob("*.json")]
        registry = Registry().with_resources(
            (document["$id"], Resource.from_contents(document)) for document in documents
        )
        cls.schema = next(document for document in documents
                          if document["$id"].endswith("/applet-install-authoring.schema.json"))
        cls.validator = Draft202012Validator(
            {"$ref": cls.schema["$id"] + "#/$defs/managed_actor_proof"}, registry=registry
        )
        cls.proof = {
            "kind": "detached_jws",
            "verification_method": "did:web:station.example#notary-key",
            "payload_digest": "sha256:" + "01" * 32,
            "created_at": "2026-09-07T00:00:00.000Z",
            "audience_id": "ak:did_core:web:service.example",
            "jws": "eyJhbGciOiJFZDI1NTE5In0..c2lnbmF0dXJl",
        }

    def test_typed_audience_and_closed_shape(self):
        self.validator.validate(self.proof)
        for audience in (None, [], [self.proof["audience_id"]],
                         "did:web:service.example", "https://service.example"):
            with self.subTest(audience=audience):
                self.assertFalse(self.validator.is_valid({**self.proof, "audience_id": audience}))
        legacy = dict(self.proof)
        legacy["audience"] = legacy.pop("audience_id")
        self.assertFalse(self.validator.is_valid(legacy))
        self.assertFalse(self.validator.is_valid({**self.proof, "audience": "service"}))
        self.assertFalse(self.validator.is_valid({**self.proof, "domain": "service"}))

    def test_request_and_bundle_share_the_registered_identity_binding(self):
        contexts = json.loads((ARTIFACTS / "registry/proof-context-registry.json")
                              .read_text(encoding="utf-8"))["domain_separations"]
        for definition in ("authoring_request", "managed_actor_bundle"):
            schema = self.schema["$defs"][definition]
            self.assertEqual(schema["properties"]["proof"]["$ref"], "#/$defs/managed_actor_proof")
            context = next(row for row in contexts if row["domain"] == schema["x-arkret-signature-domain"])
            self.assertEqual(context["binding_fields"], [
                "context", "payload_digest", "verification_method", "created_at", "audience_id"
            ])


if __name__ == "__main__":
    unittest.main()
