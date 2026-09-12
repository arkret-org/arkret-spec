"""Closed wire regression and cross-carrier signature reconstruction checks."""
import base64
import copy
import json
import unittest
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tools.artifact_lint.core import canonical_json

ARTIFACTS = Path(__file__).resolve().parents[1] / "spec/v1/artifacts"


def read(path):
    return json.loads((ARTIFACTS / path).read_text(encoding="utf-8"))


class SimplificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        docs = [json.loads(p.read_text(encoding="utf-8")) for p in (ARTIFACTS / "schemas").glob("*.json")]
        cls.registry = Registry().with_resources((d["$id"], Resource.from_contents(d)) for d in docs)
        cls.cases = {c["name"]: c for c in read("fixtures/schema-validation-fixture.json")["schema_validation_cases"]}

    def validator(self, ref):
        return Draft202012Validator({"$ref": "https://arkret.org/v1/" + ref}, registry=self.registry)

    def test_genesis_binding_is_unique_and_cannot_change_epoch(self):
        case = self.cases["mls_genesis_payload_blake3_realm_suite_valid"]
        value = case["instance"]
        validator = self.validator(case["schema_ref"])
        validator.validate(value)
        for key in ["mls_group_id", "effective_scope", "epoch"]:
            self.assertFalse(validator.is_valid(dict(value, **{key: None})), key)
        for key in ["realm_id", "circle_id", "sidecar_id", "mls_group_id"]:
            changed = copy.deepcopy(value)
            changed["governance_binding"][key] = "legacy"
            self.assertFalse(validator.is_valid(changed), key)
        for key in ["previous_epoch", "next_epoch"]:
            changed = copy.deepcopy(value)
            changed["governance_binding"][key] = 1
            self.assertFalse(validator.is_valid(changed), key)

    def test_challenge_has_no_mutable_context_echo(self):
        validator = self.validator("schemas/account-operations.schema.json#/$defs/identity_binding_challenge_outcome")
        value = {"request_id": "ak:request:01964137-0000-7000-8000-000000000010", "challenge_id": "challenge-00000000000001", "challenge": "A" * 43, "purpose": "account_binding_and_pcr_genesis", "issued_at": "2026-09-12T00:00:00.000Z", "expires_at": "2026-09-12T00:05:00.000Z"}
        validator.validate(value)
        for key in ["account_subject", "principal_id", "lease_fence", "dpop_jkt", "origin", "operation_digest", "log_head_digest", "initial_session_request_digest"]:
            self.assertFalse(validator.is_valid(dict(value, **{key: "legacy"})), key)

    def test_contact_dm_remains_independent_of_consent(self):
        self.validator("schemas/contact-operations.schema.json#/$defs/contact_scope").validate("direct_message")
        shape = read("schemas/consent-operations.schema.json")["$defs"]["consent_request_request_body"]
        self.assertIn("consent_scope", shape["required"])
        scope = shape["properties"]["consent_scope"]
        self.assertNotIn("default", scope)
        self.assertFalse(self.validator("schemas/consent-operations.schema.json#/$defs/consent_scope").is_valid("direct_message"))

    def test_media_signature_reconstructs_the_same_seven_fields_in_both_carriers(self):
        value = copy.deepcopy(self.cases["media_livekit_opaque_token_valid"]["instance"])
        fields = ["realm_id", "call_id", "focus_id", "actor_id", "device_id", "participant_id", "expires_at"]
        transcript = {k: value["participant_binding"][k] if k == "expires_at" else value[k] for k in fields}
        key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
        def signing_bytes(t):
            return b"ak.media.participant_binding.v1\0" + canonical_json(t).encode()
        signature = key.sign(signing_bytes(transcript))
        value["participant_binding"]["sig"] = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        self.validator("schemas/service-operation-dtos.schema.json#/$defs/CallMediaTokenExchangeOutcome").validate(value)
        roster = {k: value[k] for k in ["focus_id", "actor_id", "device_id", "participant_id"]}
        roster["participant_binding"] = value["participant_binding"]
        reconstructed = {"realm_id": value["realm_id"], "call_id": value["call_id"], **{k: roster[k] for k in roster if k != "participant_binding"}, "expires_at": roster["participant_binding"]["expires_at"]}
        self.assertEqual(transcript, reconstructed)
        key.public_key().verify(signature, signing_bytes(reconstructed))
        for field in fields:
            changed = dict(reconstructed, **{field: "different"})
            with self.assertRaises(InvalidSignature):
                key.public_key().verify(signature, signing_bytes(changed))

    def test_single_authority_configuration_and_ack_vectors(self):
        vector = next(v for v in read("fixtures/cbs-lattice-fixture.json")["vectors"] if v["name"] == "single_authority_configuration")
        cases = vector["cases"] + read("fixtures/control-proposal-ack-fixture.json")["cases"][:3]
        for case in cases:
            with self.subTest(case=case["name"]):
                self.assertEqual(self.validator(case["schema_ref"]).is_valid(case["instance"]), case["expect_valid"])

    def test_retired_operations_are_not_advertised(self):
        operations = {o["operation_id"] for o in read("registry/operation-registry.json")["operations"]}
        for op in ["ak.self.seals.read.membership_authority.v1", "ak.gate.account.command.issue_identity_abandonment_challenge.v1", "ak.find.directory.push.command.register.v1"]:
            self.assertNotIn(op, operations)

    def test_membership_removal_uses_digest_and_reports_the_evaluated_snapshot(self):
        scope = self.cases["mls_genesis_payload_blake3_realm_suite_valid"]["instance"]["governance_binding"]["effective_scope"]
        request = {"effective_scope": scope, "mls_group_id": base64.urlsafe_b64encode(scope["realm_id"].encode()).decode().rstrip("="), "seal_basis": {"leaves": ["ak:seal:sha256:" + "1" * 64]}, "base_group_state_ref": "ak:event:" + "A" * 44, "epoch": 0, "mls_leaf_set_digest": "sha256:" + "2" * 64}
        validator = self.validator("schemas/mls-governance-proof-bundle.schema.json#/$defs/membership_removal_request_body")
        validator.validate(request)
        self.assertFalse(validator.is_valid(dict(request, local_mls_leaves=[])))
        self.assertFalse(validator.is_valid(dict(request, mls_leaf_set_digest="blake3:" + "2" * 64)))
        outcome = {"account_id": {"principal_id": "ak:did_core:web:alice.example", "station_id": "ak:did_core:web:station.example"}, "query_digest": "sha256:" + "3" * 64, "remove_leaf_indices": [], **{k: request[k] for k in ["seal_basis", "base_group_state_ref", "epoch"]}}
        validator = self.validator("schemas/mls-governance-proof-bundle.schema.json#/$defs/membership_removal_outcome")
        validator.validate(outcome)
        for field in ["seal_basis", "base_group_state_ref", "epoch"]:
            changed = dict(outcome)
            changed.pop(field)
            self.assertFalse(validator.is_valid(changed), field)

    def test_dpop_advertisement_has_no_detached_session_fallback(self):
        ref = "schemas/service-describe.schema.json#/properties/auth_metadata/properties/did_binding_methods"
        validator = self.validator(ref)
        validator.validate(["session_dpop"])
        validator.validate(["session_dpop", "session_http_signature"])
        for method in ["session_grant", "detached_jws", "bearer"]:
            self.assertFalse(validator.is_valid([method]), method)


if __name__ == "__main__":
    unittest.main()
