"""Owned permission and quantity names retain their original closed contracts."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


SCHEMAS = Path(__file__).resolve().parents[1] / "spec/v1/artifacts/schemas"


class OwnedFieldNamingContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = {path.name: json.loads(path.read_text(encoding="utf-8"))
                         for path in SCHEMAS.glob("*.json")}
        cls.registry = Registry().with_resources(
            (document["$id"], Resource.from_contents(document))
            for document in cls.documents.values()
        )

    def validator(self, filename, pointer):
        return Draft202012Validator(
            {"$ref": self.documents[filename]["$id"] + "#" + pointer},
            registry=self.registry,
        )

    def test_stored_preview_policy_uses_permission_and_rejects_request_alias(self):
        validator = self.validator("event-payload.schema.json",
                                   "/$defs/preview_policy_payload/properties/value/properties/history")
        base = {"range": "event_stubs", "content": "none"}
        validator.validate(base)
        for value in (True, False):
            validator.validate({**base, "member_events_allowed": value})
        for invalid in ({**base, "include_member_events": True},
                        {**base, "member_events_allowed": "true"}):
            self.assertFalse(validator.is_valid(invalid), invalid)

    def test_account_profile_update_constructs_with_canonical_target_only(self):
        from tools.generate_call_current_fixture import event

        validator = self.validator("account-operations.schema.json",
                                   "/$defs/account_update_profile_request_body")
        payload = {"actor_profile_id": "ak:actor_profile:" + "A" * 44,
                   "patch": {"display_name": "Updated"}}
        validator.validate({"profile_event": {"event": event(payload, 1, "ak.profile.update")}})
        legacy = {"target_ref": payload["actor_profile_id"], "patch": payload["patch"]}
        for invalid in (legacy, {**payload, "target_ref": payload["actor_profile_id"]}):
            self.assertFalse(validator.is_valid({
                "profile_event": {"event": event(invalid, 1, "ak.profile.update")}}))

    def test_did_service_extension_uses_owned_name_and_keeps_standard_members(self):
        validator = self.validator("service-operation-dtos.schema.json", "/$defs/ServiceDidEndpoint")
        endpoint = {"id": "did:web:station.example#arkret", "type": "ArkretService",
                    "service_kind": "station", "serviceEndpoint": "https://station.example/"}
        validator.validate(endpoint)
        legacy = copy.deepcopy(endpoint)
        legacy["serviceKind"] = legacy.pop("service_kind")
        self.assertFalse(validator.is_valid(legacy))
        self.assertFalse(validator.is_valid({**endpoint, "serviceKind": "station"}))
        marker = self.documents["service-operation-dtos.schema.json"]["$defs"]["ServiceDidEndpoint"][
            "x-arkret-external-literal-object"]
        self.assertEqual(set(marker["external_properties"]), {"id", "type", "serviceEndpoint"})

    def test_audit_count_preserves_bounds_default_and_closed_request(self):
        validator = self.validator("identity-resolution.schema.json",
                                   "/$defs/principal_resolution_audit_request_body")
        base = {"account_id": {"principal_id": "ak:did_core:web:alice.example",
                               "station_id": "ak:did_core:web:station.example"}}
        validator.validate(base)
        for value in (0, 1, 256):
            validator.validate({**base, "max_predecessor_event_count": value})
        for value in (-1, 257, 1.5, True):
            self.assertFalse(validator.is_valid({**base, "max_predecessor_event_count": value}))
        self.assertFalse(validator.is_valid({**base, "history_depth": 1}))

    def test_governance_signature_count_keeps_quorum_branch_requirement(self):
        fixture = json.loads((SCHEMAS.parent / "fixtures/organization-registration-fixture.json").read_text())
        instance = next(case["instance"] for case in fixture["schema_validation_cases"]
                        if case["name"] == "ensure_with_governance_quorum_valid")
        validator = self.validator("service-operation-dtos.schema.json", "/$defs/OrganizationControlProof")
        proof = instance["control_proof"]
        validator.validate(proof)
        for replacement in (None, 1, True):
            invalid = copy.deepcopy(proof)
            if replacement is None:
                del invalid["min_signature_count"]
            else:
                invalid["min_signature_count"] = replacement
            self.assertFalse(validator.is_valid(invalid), invalid)
        invalid = copy.deepcopy(proof)
        invalid["quorum_threshold"] = invalid.pop("min_signature_count")
        self.assertFalse(validator.is_valid(invalid))

    def test_quota_burst_counts_operations_and_keeps_rate_dependencies(self):
        validator = self.validator("grant-constraint.schema.json", "")
        base = {"constraint_kind": "quota", "constraint_subkind": "rate", "effect": "allow",
                "max_operation_count": 10, "period": "PT1M", "constraint_scope": "per_actor"}
        validator.validate(base)
        validator.validate({**base, "burst_operation_count": 2})
        self.assertFalse(validator.is_valid({**base, "burst": 2}))
        for dependency in ("max_operation_count", "period"):
            invalid = {**base, "burst_operation_count": 2}
            del invalid[dependency]
            self.assertFalse(validator.is_valid(invalid))

    def test_device_quorum_policy_and_proof_keep_one_device_count_name(self):
        validator = self.validator("recovery-policy.schema.json", "/$defs/recovery_method/oneOf/2")
        devices = ["ak:device:01964137-0000-7000-8000-00000000000" + str(index)
                   for index in (1, 2)]
        policy = {"kind": "device_quorum", "min_device_count": 2, "member_ids": devices}
        validator.validate(policy)
        legacy = {"kind": "device_quorum", "k": 2, "member_ids": devices}
        self.assertFalse(validator.is_valid(legacy))
        fixture = json.loads((SCHEMAS.parent / "fixtures/recovery-transcript-fixture.json").read_text())
        proof = next(case["source_proof"] for case in fixture["cases"]
                     if case["kind"] == "device_quorum")
        validator = self.validator("recovery-session.schema.json", "/$defs/device_quorum_proof")
        validator.validate(proof)
        legacy = copy.deepcopy(proof)
        legacy["threshold"] = legacy.pop("min_device_count")
        self.assertFalse(validator.is_valid(legacy))

    def test_signature_and_approver_thresholds_name_their_counted_subjects(self):
        cases = (
            ("authority-set-policy.schema.json", "/properties/authorization_rules/items",
             {"rule_id": "device_quorum", "issuer_role": "identity_recovery",
              "allowed_actions": ["ak.device.reanchor"],
              "issuers": [{"verification_method": "did:key:z6Mkfixture#key"}],
              "min_signature_count": 1}, "min_signature_count", "threshold"),
            ("policy.schema.json", "/$defs/management_review_requirement",
             {"approver_actor_ids": [{"kind": "account", "account_id": {
                 "principal_id": "ak:did_core:web:alice.example",
                 "station_id": "ak:did_core:web:station.example"}}],
              "min_approver_count": 1, "max_age_seconds": 300}, "min_approver_count", "threshold"),
            ("event-payload.schema.json", "/$defs/policy_action_document",
             {"action": "ak.realm.profile", "approval_required": True,
              "min_approver_count": 1, "policy_scope": "ak:realm:" + "A" * 44},
             "min_approver_count", "approval_quorum"),
        )
        for filename, pointer, value, name, old_name in cases:
            with self.subTest(filename=filename):
                validator = self.validator(filename, pointer)
                validator.validate(value)
                legacy = copy.deepcopy(value)
                legacy[old_name] = legacy.pop(name)
                self.assertFalse(validator.is_valid(legacy))

    def test_quantity_fields_declare_count_roles_and_preserve_units(self):
        cases = (
            ("account-subscribe-frame.schema.json", "/$defs/account_filter/properties/max_window_event_count", 100),
            ("account-subscribe-frame.schema.json", "/$defs/realm_stream_window/properties/max_window_event_count", 100),
            ("applet-package.schema.json", "/$defs/limits/properties/max_transaction_count_per_minute", 120),
            ("space.schema.json", "/properties/fields/properties/max_active_strand_count", 2),
            ("push-operations.schema.json", "/$defs/counts/properties/unread_increment_count", 1),
            ("event-payload.schema.json", "/$defs/realm_discovery_payload/properties/value/properties/anti_enumeration/properties/member_count_hysteresis/properties/absolute_count", 2),
            ("service-describe.schema.json", "/properties/rate_limit_policy/properties/entries/items/properties/burst_request_count", 5),
        )
        for filename, pointer, value in cases:
            with self.subTest(filename=filename, pointer=pointer):
                self.validator(filename, pointer).validate(value)
                self.assertFalse(self.validator(filename, pointer).is_valid(True))
                node = self.documents[filename]
                for token in pointer.split("/")[1:]:
                    node = node[token]
                self.assertEqual(node["x-arkret-member-role"], "count")


if __name__ == "__main__":
    unittest.main()
