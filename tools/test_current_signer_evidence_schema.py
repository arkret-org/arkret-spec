"""Closed-schema regressions for cold-recipient current signer evidence."""

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


SCHEMAS = Path(__file__).resolve().parents[1] / "spec/v1/artifacts/schemas"
SCHEMA_ID = "https://arkret.org/v1/schemas/current-signer-evidence-operations.schema.json"


class CurrentSignerEvidenceSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources = []
        for path in SCHEMAS.glob("*.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            resources.append((document["$id"], Resource.from_contents(document)))
        registry = Registry().with_resources(resources)
        cls.request_validator = Draft202012Validator(
            {"$ref": f"{SCHEMA_ID}#/$defs/query_request"}, registry=registry
        )
        cls.outcome_validator = Draft202012Validator(
            {"$ref": f"{SCHEMA_ID}#/$defs/query_outcome"}, registry=registry
        )

    def request(self):
        return {
            "request_id": "ak:request:019b0000-0000-7000-8000-000000000001",
            "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
            "recipient_account_id": {
                "principal_id": "ak:did_core:webvh:z6mkrecipient",
                "station_id": "ak:did_core:webvh:z6mkstation-b",
            },
            "queries": [
                {
                    "sender_kind": "account_device",
                    "account_id": {
                        "principal_id": "ak:did_core:webvh:z6mksender",
                        "station_id": "ak:did_core:webvh:z6mkstation-a",
                    },
                    "device_id": "ak:device:019b0000-0000-7000-8000-000000000002",
                }
            ],
        }

    def outcome(self):
        request = self.request()
        return {
            "response": {
                **{key: request[key] for key in (
                    "request_id", "realm_id", "recipient_account_id",
                )},
                "evidences": [],
            },

        }

    def test_request_has_no_caller_or_transport_authority_fields(self):
        request = self.request()
        self.request_validator.validate(request)
        for forbidden in (
            "source_service_id", "verifier_id", "issuer_id", "session_grant",
            "key_package", "producer_key", "operation_id", "request_digest", "challenge",
        ):
            mutated = copy.deepcopy(request)
            mutated[forbidden] = "ak:did_core:webvh:z6mkattacker"
            self.assertFalse(self.request_validator.is_valid(mutated), forbidden)

    def test_selector_branches_are_closed_and_exclusive(self):
        request = self.request()
        ordinary = request["queries"][0]
        for mutation in (
            {**ordinary, "actor": ordinary["account_id"]},
            {**ordinary, "verification_method": "did:webvh:z6mksender#runtime"},
            {**ordinary, "sender_kind": "agent"},
        ):
            mutated = copy.deepcopy(request)
            mutated["queries"] = [mutation]
            self.assertFalse(self.request_validator.is_valid(mutated))

        agent = {
            "sender_kind": "agent",
            "actor": {
                "kind": "account",
                "account_id": ordinary["account_id"],
            },
            "verification_method": "did:webvh:z6mksender#runtime",
        }
        request["queries"] = [agent]
        self.request_validator.validate(request)
        for forbidden in ("account_id", "device_id", "device_projection_attestation"):
            mutated = copy.deepcopy(request)
            mutated["queries"][0][forbidden] = ordinary.get(forbidden, {})
            self.assertFalse(self.request_validator.is_valid(mutated))
        service = copy.deepcopy(request)
        service["queries"][0]["actor"] = {
            "kind": "service",
            "service_id": ordinary["account_id"]["station_id"],
        }
        self.assertFalse(self.request_validator.is_valid(service))

    def test_response_is_closed_around_exact_context_and_empty_opaque_result(self):
        outcome = self.outcome()
        self.outcome_validator.validate(outcome)
        for forbidden in (
            "unknown_selector", "unauthorized_target", "wrong_station", "failure_reason",
        ):
            mutated = copy.deepcopy(outcome)
            mutated["response"][forbidden] = True
            self.assertFalse(self.outcome_validator.is_valid(mutated), forbidden)
        mutated = copy.deepcopy(outcome)
        mutated["response"]["evidences"] = [
            {
                "sender_kind": "account_device",
                "account_id": self.request()["queries"][0]["account_id"],
                "device_id": self.request()["queries"][0]["device_id"],
                "authenticated_signer_evidence": {},
                "dependencies": [],
            }
        ]
        self.assertFalse(self.outcome_validator.is_valid(mutated))


if __name__ == "__main__":
    unittest.main()
