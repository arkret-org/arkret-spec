"""Closed historical device evidence and required publication coordinates."""

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


class DeviceHistoryEvidenceSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        artifacts = Path(__file__).resolve().parents[1] / "spec/v1/artifacts"
        resources = []
        for path in (artifacts / "schemas").glob("*.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            resources.append((document["$id"], Resource.from_contents(document)))
        cls.registry = Registry().with_resources(resources)
        cases = json.loads((artifacts / "fixtures/schema-validation-fixture.json").read_text(encoding="utf-8"))["schema_validation_cases"]
        cls.core = next(case["instance"] for case in cases if case["name"] == "account_identity_closure_device_attestation_valid")

    def validator(self, ref):
        return Draft202012Validator({"$ref": "https://arkret.org/v1/schemas/" + ref}, registry=self.registry)

    def attestation(self):
        return {"attestation": copy.deepcopy(self.core), "proof": {
            "verification_method": "did:web:ps.example#signing-1",
            "created_at": self.core["attested_at"], "jws": "AA",
        }}

    def test_device_history_evidence_is_a_closed_distinct_branch(self):
        validator = self.validator("authenticated-signer-resolution-evidence.schema.json")
        value = {
            "kind": "account_device", "signer_id": self.core["account_id"]["principal_id"],
            "verification_method": "did:webvh:z6mkfixture:account.example#" + self.core["device_id"],
            "device_projection_attestation": self.attestation(),
            "attester_signer_evidence_ref": "ak:signer_evidence:sha256:" + "a" * 64,
        }
        validator.validate(value)
        for field in value:
            missing = copy.deepcopy(value)
            del missing[field]
            self.assertFalse(validator.is_valid(missing), field)
        value["normalized_did_document"] = {}
        self.assertFalse(validator.is_valid(value))

    def test_query_and_current_evidence_require_retained_coordinate(self):
        for schema, value in [
            ("keys-operations.schema.json#/$defs/query_device_record", {
                "algorithms": {}, "trust_algorithms": [],
                "device_projection_attestation": self.attestation(),
            }),
            ("current-signer-evidence-operations.schema.json#/$defs/account_device_evidence", {
                "sender_kind": "account_device", "account_id": self.core["account_id"],
                "device_id": self.core["device_id"], "device_projection_attestation": self.attestation(),
            }),
        ]:
            validator = self.validator(schema)
            self.assertFalse(validator.is_valid(value))
            value["signer_evidence_ref"] = "ak:signer_evidence:sha256:" + "b" * 64
            validator.validate(value)
            value["signer_evidence_digest"] = "sha256:" + "b" * 64
            self.assertFalse(validator.is_valid(value))

    def test_authorization_closure_requires_closed_kind_scope_action_coordinates(self):
        validator = self.validator("seal.schema.json#/$defs/authorization_closure")
        event_id = "ak:event:AfumWbbDTAdHm6EJcwrgFczGIei511I72WryaaMIPtpV"
        value = {
            "command_event_id": event_id,
            "dependency_kind": "realm_controller_assignment",
            "authorization_event_id": event_id,
            "generation_event_id": event_id,
            "scope_ref": {"kind": "realm", "realm_id": "ak:realm:AdkQ-RmB1a8zyc52yl9GWAsodQ_EUle1WAVZqbO7pc19"},
            "actions": ["ak.message.create"], "frontier": [],
        }
        validator.validate(value)
        for kind in (None, "lifecycle", "circle_active", "consent_grant"):
            invalid = copy.deepcopy(value)
            if kind is None:
                del invalid["dependency_kind"]
            else:
                invalid["dependency_kind"] = kind
            self.assertFalse(validator.is_valid(invalid), kind)
        invalid = copy.deepcopy(value)
        invalid["actions"] = ["ak.message.edit"]
        self.assertFalse(validator.is_valid(invalid))
        invalid["actions"] = ["ak.self.agent.command.pause.v1"]
        self.assertFalse(validator.is_valid(invalid))
        invalid = copy.deepcopy(value)
        invalid["scope_ref"] = {"kind": "realm_genesis"}
        self.assertFalse(validator.is_valid(invalid))

    def test_dependency_schema_is_derived_from_the_closed_registry(self):
        from tools.artifact_pipeline import check_authorization_dependency_schema
        self.assertEqual(check_authorization_dependency_schema(), [])


if __name__ == "__main__":
    unittest.main()
