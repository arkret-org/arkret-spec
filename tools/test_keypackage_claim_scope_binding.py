"""Prove exact pending-claim target binding without asserting native admission."""
from copy import deepcopy
import base64
import json
import unittest

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tools.artifact_lint.core import ARTIFACTS
from tools.generate_mimi_key_material_fixture import jcs
from tools.mls_scope import canonical_mls_group_id, verify_claim_scope


class KeypackageClaimScopeBindingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lifecycle = json.loads((ARTIFACTS / "fixtures/keypackage-lifecycle-fixture.json").read_text(encoding="utf-8"))
        cls.schema = json.loads((ARTIFACTS / "schemas/keypackage-operations.schema.json").read_text(encoding="utf-8"))
        docs = [json.loads(p.read_text(encoding="utf-8")) for p in (ARTIFACTS / "schemas").glob("*.json")]
        cls.registry = Registry().with_resources((d["$id"], Resource.from_contents(d)) for d in docs)

    def request(self):
        return deepcopy(self.lifecycle["schema_validation_cases"][0]["instance"])

    def validator(self, name):
        return Draft202012Validator({"$ref": self.schema["$id"] + "#/$defs/" + name}, registry=self.registry)

    def test_both_signed_carriers_require_closed_executable_scope(self):
        for name, body in [("keypackages_claim_request_body", self.request()),
                           ("peer_keypackages_claim_fields", deepcopy(self.lifecycle["unsigned_selector_transcripts"][0]["unsigned_request"]))]:
            validator = self.validator(name)
            self.assertEqual(list(validator.iter_errors(body)), [])
            for scope in [None, {"kind": "realm_genesis"}, {"kind": "realm_control", "realm_id": body["intended_realm_id"]},
                          {"kind": "realm", "realm_id": body["intended_realm_id"], "extra": True}]:
                changed = deepcopy(body)
                changed["effective_scope"] = scope
                self.assertTrue(list(validator.iter_errors(changed)), (name, scope))
            del body["effective_scope"]
            self.assertTrue(list(validator.iter_errors(body)), name)

    def test_pending_realm_circle_and_sidecar_targets_remain_exact_without_welcome(self):
        request = self.request()
        realm = request["intended_realm_id"]
        scopes = [{"kind": "realm", "realm_id": realm},
                  {"kind": "circle", "realm_id": realm, "circle_id": realm.replace("ak:realm:", "ak:circle:")},
                  {"kind": "sidecar", "realm_id": realm, "sidecar_id": realm.replace("ak:realm:", "ak:sidecar:")}]
        groups = set()
        for scope in scopes:
            request["effective_scope"] = scope
            request["mls_group_id"] = canonical_mls_group_id(scope)
            self.assertEqual(list(self.validator("keypackages_claim_request_body").iter_errors(request)), [])
            verify_claim_scope(request)
            groups.add(request["mls_group_id"])
        self.assertEqual(len(groups), 3)

    def test_wrong_realm_group_missing_or_changed_scope_fails(self):
        original = self.request()
        verify_claim_scope(original)
        for changed in [
            {**original, "intended_realm_id": "ak:realm:other"},
            {**original, "mls_group_id": "A" * 43},
            {**original, "effective_scope": None},
            {**original, "effective_scope": {"kind": "realm_genesis"}},
            {key: value for key, value in original.items() if key != "effective_scope"},
        ]:
            with self.assertRaises(ValueError):
                verify_claim_scope(changed)

    def test_direct_uses_original_realm_scope(self):
        request = self.request()
        request["claim_purpose"] = "direct_conversation"
        request["strand_id"] = request["intended_realm_id"].replace("ak:realm:", "ak:strand:")
        request["pair_key"] = "sha256:" + "11" * 32
        request["last_resort_allowed"] = False
        self.assertEqual(list(self.validator("keypackages_claim_request_body").iter_errors(request)), [])
        verify_claim_scope(request)
        request["effective_scope"] = {"kind": "circle", "realm_id": request["intended_realm_id"],
                                      "circle_id": request["intended_realm_id"].replace("ak:realm:", "ak:circle:")}
        request["mls_group_id"] = canonical_mls_group_id(request["effective_scope"])
        self.assertTrue(list(self.validator("keypackages_claim_request_body").iter_errors(request)))
        with self.assertRaises(ValueError):
            verify_claim_scope(request)

    def test_consistent_scope_and_group_rebinding_still_breaks_original_signature(self):
        f = json.loads((ARTIFACTS / "fixtures/mimi-key-material-claim-fixture.json").read_text(encoding="utf-8"))
        request = f["request"]
        auth = request["requester_authorization"]
        transcript = {"authorization": {k: v for k, v in auth.items() if k not in ("kind", "signature")},
                      "request": {k: v for k, v in request.items() if k not in ("requester_authorization", "service_binding")},
                      "service_binding": request["service_binding"]}
        def unb64(value):
            return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        key = Ed25519PublicKey.from_public_bytes(unb64(f["participant_public_key"]))
        signature = unb64(auth["signature"]["signature"])
        domain = b"ak.peer-keypackage-claim-authorization-v1\n"
        key.verify(signature, domain + jcs(transcript))
        changed = deepcopy(transcript)
        changed["request"]["effective_scope"] = {"kind": "circle", "realm_id": request["intended_realm_id"],
            "circle_id": request["intended_realm_id"].replace("ak:realm:", "ak:circle:")}
        changed["request"]["mls_group_id"] = canonical_mls_group_id(changed["request"]["effective_scope"])
        verify_claim_scope(changed["request"])
        with self.assertRaises(InvalidSignature):
            key.verify(signature, domain + jcs(changed))


if __name__ == "__main__":
    unittest.main()
