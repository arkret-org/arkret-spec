"""Org Genesis certificate shape checks; no authority or crypto admission claim."""

import copy
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "spec/v1/artifacts"


class OrganizationGenesisPublicSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        documents = [json.loads(path.read_text(encoding="utf-8")) for path in (ART / "schemas").glob("*.json")]
        cls.registry = Registry().with_resources((document["$id"], Resource.from_contents(document)) for document in documents)
        cls.operations = json.loads((ART / "schemas/authority-commit-operations.schema.json").read_text(encoding="utf-8"))
        cls.bundle = json.loads((ART / "schemas/realm-authority-bundle.schema.json").read_text(encoding="utf-8"))
        source = json.loads((ART / "fixtures/realm-actor-content-backup-fixture.json").read_text(encoding="utf-8"))["native_source"]
        approval = json.loads((ART / "fixtures/approval-signature-kat-fixture.json").read_text(encoding="utf-8"))["vectors"][0]["approval_signature"]
        # Reuse original typed material without changing any signed fixture.
        # This assembly tests shape only, not Org identity, vote eligibility or authorization.
        cls.service_shape = {
            "event_id": approval["input"]["approval_target"]["event_id"],
            "method_history_evidence": source["origin_resolution"]["method_history_evidence"],
            "producer_resolution": source["origin_resolution"],
        }
        cls.approval = approval
        cls.device_key = source["admission"]["device_public_key_base64url"]

    def validator(self):
        return Draft202012Validator({"$ref": "https://arkret.org/v1/schemas/authority-commit-operations.schema.json#/$defs/organization_genesis_signer_fact"}, registry=self.registry)

    def test_service_and_finite_device_have_one_actual_role(self):
        validator = self.validator()
        validator.validate(self.service_shape)
        finite_service = copy.deepcopy(self.service_shape)
        finite_service["approval_signatures"] = [self.approval]
        validator.validate(finite_service)
        device = copy.deepcopy(finite_service)
        device.pop("producer_resolution")
        device["public_key_base64url"] = self.device_key
        validator.validate(device)
        no_finite = copy.deepcopy(device)
        no_finite.pop("approval_signatures")
        self.assertFalse(validator.is_valid(no_finite))
        both = copy.deepcopy(finite_service)
        both["public_key_base64url"] = self.device_key
        self.assertFalse(validator.is_valid(both))
        neither = copy.deepcopy(self.service_shape)
        neither.pop("producer_resolution")
        self.assertFalse(validator.is_valid(neither))

    def test_null_empty_and_missing_sources_are_not_absence(self):
        validator = self.validator()
        for field in ("method_history_evidence", "approval_signatures", "producer_resolution", "public_key_base64url"):
            row = copy.deepcopy(self.service_shape)
            row[field] = None
            self.assertFalse(validator.is_valid(row), field)
        row = copy.deepcopy(self.service_shape)
        row["approval_signatures"] = []
        self.assertFalse(validator.is_valid(row))
        for field in ("event_id", "method_history_evidence"):
            row = copy.deepcopy(self.service_shape)
            row.pop(field)
            self.assertFalse(validator.is_valid(row), field)

    def test_no_mirrored_commit_event_time_or_permission(self):
        validator = self.validator()
        for field in ("target", "commit_id", "accepted_at", "event", "actor", "verification_method", "current", "verified", "organization_method_history_evidence", "producer_service_resolution"):
            row = copy.deepcopy(self.service_shape)
            row[field] = "unexpected"
            self.assertFalse(validator.is_valid(row), field)

    def test_presence_selector_is_not_native_proof(self):
        # Isolate the actual presence condition, not the complete Event shape.
        # None of these coordinate-only rows is an accepted authority fixture.
        condition = self.bundle["allOf"][-1]
        validator = Draft202012Validator(condition)
        org_candidate = {"genesis_event": {"executed_by": {}, "authorization_ref": "source", "payload": {"object": {"purpose": "principal_control"}}}}
        self.assertFalse(validator.is_valid(org_candidate))
        with_fact = copy.deepcopy(org_candidate)
        with_fact["producer_signer_fact"] = {}
        validator.validate(with_fact)
        for purpose, executor in (("collaboration", True), ("agent_control", True), ("direct_conversation", False), ("principal_control", False)):
            row = {"genesis_event": {"payload": {"object": {"purpose": purpose}}}}
            if executor:
                row["genesis_event"].update({"executed_by": {}, "authorization_ref": "source"})
            validator.validate(row)
            row["producer_signer_fact"] = {}
            self.assertFalse(validator.is_valid(row), (purpose, executor))

    def test_bundle_null_and_single_genesis_owner(self):
        field = self.bundle["properties"]["producer_signer_fact"]
        validator = Draft202012Validator({"$id": self.bundle["$id"], **field}, registry=self.registry)
        self.assertFalse(validator.is_valid(None))
        self.assertEqual(field["$ref"], "./authority-commit-operations.schema.json#/$defs/organization_genesis_signer_fact")
        names = list(self.bundle["properties"])
        self.assertEqual(names[names.index("genesis_commit") + 1], "producer_signer_fact")
        self.assertNotIn("historical_signer_facts", self.bundle["properties"])
        ref = {"$ref": "#/$defs/organization_genesis_signer_fact"}
        self.assertEqual(self.operations["$defs"]["historical_producer_signer_fact"]["oneOf"].count(ref), 1)

    def test_private_handoff_inventory_keeps_its_full_target_model(self):
        inventory = self.operations["$defs"]["realm_authority_handoff_request_body"]["properties"]["historical_signer_facts"]
        self.assertEqual(inventory["items"]["$ref"], "#/$defs/historical_producer_signer_fact_entry")
        self.assertNotIn("maxItems", inventory)
        entry = self.operations["$defs"]["historical_producer_signer_fact_entry"]
        self.assertEqual(entry["required"], ["target", "producer_signer_fact"])


if __name__ == "__main__":
    unittest.main()
