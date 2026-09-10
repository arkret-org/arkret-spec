"""3PID public material and token-presentation schema contract tests."""

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


SCHEMAS = Path(__file__).resolve().parents[1] / "spec/v1/artifacts/schemas"


class ThirdPartyInviteModesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources = []
        for path in SCHEMAS.glob("*.json"):
            schema = json.loads(path.read_text(encoding="utf-8"))
            resources.append((schema["$id"], Resource.from_contents(schema)))
        cls.registry = Registry().with_resources(resources)
        cls.schema = json.loads((SCHEMAS / "invite.schema.json").read_text(encoding="utf-8"))

    def valid(self, definition, value):
        validator = Draft202012Validator(
            {"$ref": self.schema["$id"] + "#/$defs/" + definition},
            registry=self.registry,
        )
        return validator.is_valid(value)

    def test_public_material_in_both_modes(self):
        common = {
            "token_commitment": "sha256:" + "ab" * 32,
            "verification_id": "ak:did_core:web:ivs.example",
            "verification_public_key": "z6MkVK",
            "max_claims": 1,
        }
        for mode, specific, forbidden in [
            ("offline_token", {"token_salt_id": "salt", "token_entropy_bits": 128},
             {"lookup_table_ref": "slot", "pepper_id": "pepper"}),
            ("lookup", {"lookup_table_ref": "slot", "pepper_id": "pepper"},
             {"token_salt_id": "salt", "token_entropy_bits": 128}),
        ]:
            value = {**common, "oob_code_kind": mode, **specific}
            self.assertTrue(self.valid("third_party_invite", value))
            for field in ["token_commitment", *specific]:
                invalid = copy.deepcopy(value)
                del invalid[field]
                self.assertFalse(self.valid("third_party_invite", invalid), field)
            for field, extra in forbidden.items():
                self.assertFalse(self.valid("third_party_invite", {**value, field: extra}), field)
            for field in ["invite_token", "token_salt", "private_key", "delivery_target"]:
                self.assertFalse(self.valid("third_party_invite", {**value, field: "secret"}))

    def test_short_code_and_method_native_did(self):
        value = {
            "invite_token": "123456",
            "realm_id": "ak:realm:AdkQ-RmB1a8zyc52yl9GWAsodQ_EUle1WAVZqbO7pc19",
            "subject_account_id": {
                "principal_id": "ak:did_core:web:alice.example",
                "station_id": "ak:did_core:web:station.example",
            },
            "subject_did": "did:web:alice.example",
            "claim_nonce": "0123456789abcdef",
        }
        self.assertTrue(self.valid("third_party_invite_present_request_body", value))
        for token in ["12345", "123 456", "a" * 513]:
            self.assertFalse(self.valid("third_party_invite_present_request_body", {**value, "invite_token": token}))
        self.assertFalse(self.valid("third_party_invite_present_request_body", {
            **value, "subject_did": "ak:did_core:web:alice.example",
        }))


if __name__ == "__main__":
    unittest.main()
