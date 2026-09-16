"""Own-Station service binding results stay closed, purpose-bound and evidence-free."""
import copy
import json
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]

class ServiceBindingResultSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        documents = [json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "spec/v1/artifacts/schemas").glob("*.json")]
        cls.registry = Registry().with_resources((x["$id"], Resource.from_contents(x)) for x in documents)

    def validator(self, file_name, name):
        return Draft202012Validator({"$ref": f"https://arkret.org/v1/schemas/{file_name}#/$defs/{name}"}, registry=self.registry)

    def account(self):
        return {"principal_id": "ak:did_core:web:alice.example", "station_id": "ak:did_core:web:station.example"}

    def signer(self):
        return {"actor_id": {"kind": "service", "service_id": "ak:did_core:web:station.example"}, "verification_method": "did:web:station.example#seal-key-1", "key_kind": "ed25519_raw32", "jose_algorithm": "Ed25519", "frozen_public_key_b64u": "a" * 43}

    def media_request(self):
        return {"request_id": "ak:request:01964137-0000-7000-8000-000000000011", "realm_id": "ak:realm:AZocxLUuB-7lfxVbVJzNCcxSEn-aDa07Di6MnigFwGfd"}

    def media_outcome(self):
        return {**self.media_request(), "route": {"service_id": "ak:did_core:web:media.example", "service_kind": "media_service", "did": "did:web:media.example", "method_history_head": "sha256:" + "c" * 64, "version_id": "synthetic-jcs-sha256:" + "c" * 64, "resolution_event_ref": "did-web-document-sha256:" + "c" * 64, "base_url": "https://media.example/"}, "signing_keys": [{"verification_method": "did:web:media.example#key-1", "public_key_b64u": "d" * 42 + "A"}], "observed_at": "2026-09-10T00:00:00.000Z", "expires_at": "2026-09-10T00:05:00.000Z"}

    def assert_every_member_required(self, validator, instance):
        validator.validate(instance)
        for key in instance:
            changed = copy.deepcopy(instance)
            del changed[key]
            self.assertFalse(validator.is_valid(changed), key)

    def test_media_request_carries_no_caller_supplied_service_identity(self):
        validator = self.validator("media-service-binding-result.schema.json", "media_service_binding_request_body")
        self.assert_every_member_required(validator, self.media_request())
        for key in ["service_id", "did", "base_url", "candidate_origins", "method_history_evidence"]:
            changed = self.media_request()
            changed[key] = None
            self.assertFalse(validator.is_valid(changed), key)

    def test_media_outcome_binds_route_keys_and_reuse_window(self):
        validator = self.validator("media-service-binding-result.schema.json", "media_service_binding_outcome")
        self.assert_every_member_required(validator, self.media_outcome())
        for key in self.media_outcome()["route"]:
            changed = self.media_outcome()
            del changed["route"][key]
            self.assertFalse(validator.is_valid(changed), key)
        for keys in ([], [{"verification_method": "did:web:media.example#key-%d" % index, "public_key_b64u": "d" * 42 + "A"} for index in range(17)]):
            changed = self.media_outcome()
            changed["signing_keys"] = keys
            self.assertFalse(validator.is_valid(changed), len(keys))
        changed = self.media_outcome()
        changed["signing_keys"] = [changed["signing_keys"][0], copy.deepcopy(changed["signing_keys"][0])]
        self.assertFalse(validator.is_valid(changed))
        changed = self.media_outcome()
        changed["signing_keys"][0]["authorization_ref"] = "ak:event:ARf0hBMoVkQqflOWgdkxNzM3DDLeIZcTJgfcuk16MrSh"
        self.assertFalse(validator.is_valid(changed))
        for key in ["method_history_evidence", "normalized_did_document", "describe", "backend_token", "media_key"]:
            changed = self.media_outcome()
            changed[key] = None
            self.assertFalse(validator.is_valid(changed), key)

    def test_route_projection_rejects_unnormalized_entry_and_event_handle(self):
        validator = self.validator("media-service-binding-result.schema.json", "media_service_binding_outcome")
        for base_url in ["https://media.example", "https://media.example/path", "http://media.example/", "https://media.example/?a=1"]:
            changed = self.media_outcome()
            changed["route"]["base_url"] = base_url
            self.assertFalse(validator.is_valid(changed), base_url)
        for ref in ["ak:event:ARf0hBMoVkQqflOWgdkxNzM3DDLeIZcTJgfcuk16MrSh", "sha256:" + "c" * 64, "did-web-document-sha256:" + "C" * 64]:
            changed = self.media_outcome()
            changed["route"]["resolution_event_ref"] = ref
            self.assertFalse(validator.is_valid(changed), ref)

if __name__ == "__main__":
    unittest.main()
