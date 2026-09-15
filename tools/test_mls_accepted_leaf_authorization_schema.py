"""Historical leaf authorization is complete, closed and response-only."""
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


class MlsAcceptedLeafAuthorizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schemas = Path(__file__).resolve().parents[1] / "spec/v1/artifacts/schemas"
        documents = [json.loads(path.read_text(encoding="utf-8")) for path in schemas.glob("*.json")]
        registry = Registry().with_resources((doc["$id"], Resource.from_contents(doc)) for doc in documents)
        cls.schema = next(doc for doc in documents if doc["$id"].endswith("/mls-governance-proof-bundle.schema.json"))
        cls.validator = Draft202012Validator(
            {"$ref": cls.schema["$id"] + "#/$defs/accepted_leaf_authorization"}, registry=registry
        )
        cls.event = "ak:event:AZEvldDJcWI9IRHqP2BMibDDfc59Ax_LwrbsrQmeD6Ml"

    def test_three_closed_branches(self):
        for value in (
            {"leaf_index": 0, "device_authorize_event_id": self.event},
            {"leaf_index": 1, "agent_verification_method": "did:web:agent.example#runtime", "agent_key_authorize_event_id": self.event},
            {"leaf_index": 2},
        ):
            self.validator.validate(value)
            self.assertFalse(self.validator.is_valid({**value, "actor_id": "forbidden"}))

    def test_null_mixed_incomplete_and_out_of_range_are_rejected(self):
        for fields in (
            {"device_authorize_event_id": None},
            {"agent_verification_method": None},
            {"agent_key_authorize_event_id": None},
            {"agent_key_authorize_event_id": self.event},
            {"agent_verification_method": "did:web:agent.example#runtime"},
            {"device_authorize_event_id": self.event, "agent_key_authorize_event_id": self.event},
            {"leaf_index": -1}, {"leaf_index": 4294967296},
        ):
            self.assertFalse(self.validator.is_valid({"leaf_index": 0, **fields}), fields)

    def test_authority_does_not_change_shared_frontier_or_request(self):
        defs = self.schema["$defs"]
        self.assertEqual(set(defs["mls_security_frontier_leaf"]["properties"]), {"leaf_index", "actor_id", "credential_ref"})
        self.assertIn("mls_leaf_authorizations", defs["accepted_artifact_outcome"]["required"])
        self.assertNotIn("mls_leaf_authorizations", defs["accepted_artifact_request_body"]["properties"])


if __name__ == "__main__":
    unittest.main()
