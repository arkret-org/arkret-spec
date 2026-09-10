"""Authenticated current principal results exclude audit and authorization carriers."""
import copy
import json
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]

class CurrentPrincipalSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        documents = [json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "spec/v1/artifacts/schemas").glob("*.json")]
        cls.registry = Registry().with_resources((x["$id"], Resource.from_contents(x)) for x in documents)

    def validator(self, name):
        return Draft202012Validator({"$ref": "https://arkret.org/v1/schemas/identity-resolution.schema.json#/$defs/" + name}, registry=self.registry)

    def request(self):
        return {"request_id": "ak:request:01964137-0000-7000-8000-000000000001", "account_id": {"principal_id": "ak:did_core:web:alice.example", "station_id": "ak:did_core:web:station.example"}}

    def outcome(self):
        return {**self.request(), "principal_control_realm_id": "ak:realm:AZocxLUuB-7lfxVbVJzNCcxSEn-aDa07Di6MnigFwGfd", "resolution_projection": {"did": "did:web:alice.example", "method_history_head": "sha256:" + "a" * 64, "version_id": "synthetic-jcs-sha256:" + "a" * 64, "resolution_event_ref": "ak:event:ARf0hBMoVkQqflOWgdkxNzM3DDLeIZcTJgfcuk16MrSh", "updated_at": "2026-09-10T00:00:00.000Z"}}

    def test_request_requires_exact_account_and_no_audit_selector(self):
        validator = self.validator("current_principal_request_body")
        request = self.request()
        validator.validate(request)
        for key in request:
            changed = copy.deepcopy(request)
            del changed[key]
            self.assertFalse(validator.is_valid(changed))
        request["history_depth"] = 0
        self.assertFalse(validator.is_valid(request))

    def test_success_requires_pcr_and_complete_projection(self):
        validator = self.validator("current_principal_outcome")
        outcome = self.outcome()
        validator.validate(outcome)
        for key in outcome:
            changed = copy.deepcopy(outcome)
            del changed[key]
            self.assertFalse(validator.is_valid(changed))
        for key in outcome["resolution_projection"]:
            changed = copy.deepcopy(outcome)
            del changed["resolution_projection"][key]
            self.assertFalse(validator.is_valid(changed))

    def test_result_rejects_closure_and_lease(self):
        validator = self.validator("current_principal_outcome")
        for key in ["method_history_evidence", "projection_attestation", "accepted_seal", "expires_at", "profile", "observed_at"]:
            changed = self.outcome()
            changed[key] = None
            self.assertFalse(validator.is_valid(changed))

if __name__ == "__main__":
    unittest.main()
