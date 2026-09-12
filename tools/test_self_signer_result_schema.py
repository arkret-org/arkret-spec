"""Unified self signing keys preserve distinct peer and historical contracts."""
import copy
import json
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "spec/v1/artifacts/schemas"

class SelfSignerResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in SCHEMAS.glob("*.json")}
        cls.registry = Registry().with_resources((x["$id"], Resource.from_contents(x)) for x in cls.documents.values())

    def validator(self, name, file="signer-key-operations.schema.json"):
        return Draft202012Validator({"$ref": self.documents[file]["$id"] + "#/$defs/" + name}, registry=self.registry)

    def request(self, mode="current_admission", sender="agent"):
        actor = {"kind": "account", "account_id": {"principal_id": "ak:did_core:web:alice.example", "station_id": "ak:did_core:web:station.example"}}
        selector = {"verification_mode": mode, "sender_kind": sender, "actor": actor, "verification_method": "did:web:alice.example#runtime"}
        if sender == "account_device":
            selector["device_id"] = "ak:device:01964137-0000-7000-8000-000000000001"
            selector["verification_method"] = "did:web:alice.example#" + selector["device_id"]
        if mode == "historical_event":
            selector["event_id"] = "ak:event:ARf0hBMoVkQqflOWgdkxNzM3DDLeIZcTJgfcuk16MrSh"
        return {"request_id": "ak:request:01964137-0000-7000-8000-000000000001", "realm_id": "ak:realm:AZocxLUuB-7lfxVbVJzNCcxSEn-aDa07Di6MnigFwGfd", "recipient_account_id": actor["account_id"], "queries": [selector]}

    def test_all_four_modes_are_closed_and_receiver_is_not_selectable(self):
        for mode in ["current_admission", "historical_event"]:
            for sender in ["account_device", "agent"]:
                request = self.request(mode, sender)
                self.validator("query_request_body").validate(request)
                request["queries"][0]["receiver_id"] = "ak:did_core:web:third.example"
                self.assertFalse(self.validator("query_request_body").is_valid(request))

    def test_device_requires_actual_device_and_method(self):
        request = self.request("historical_event", "account_device")
        for field in ["device_id", "verification_method", "actor", "event_id"]:
            changed = copy.deepcopy(request)
            del changed["queries"][0][field]
            self.assertFalse(self.validator("query_request_body").is_valid(changed))

    def test_self_64_and_peer_16_are_distinct(self):
        request = self.request()
        prototype = request["queries"][0]
        request["queries"] = []
        for index in range(64):
            selector = copy.deepcopy(prototype)
            selector["verification_method"] += str(index)
            request["queries"].append(selector)
        self.validator("query_request_body").validate(request)
        request["queries"].append(prototype)
        self.assertFalse(self.validator("query_request_body").is_valid(request))
        peer = self.request()
        del peer["queries"][0]["verification_mode"]
        peer["known_agent_state_digests"] = []
        self.validator("query_request", "current-signer-evidence-operations.schema.json").validate(peer)
        self.assertFalse(self.validator("query_request_body").is_valid(peer))
        prototype = peer["queries"][0]
        peer["queries"] = []
        for index in range(17):
            selector = copy.deepcopy(prototype)
            selector["verification_method"] += str(index)
            peer["queries"].append(selector)
        self.assertFalse(self.validator("query_request", "current-signer-evidence-operations.schema.json").is_valid(peer))

    def test_historical_device_has_no_fabricated_authorization_or_source_ref(self):
        selector = self.request("historical_event", "account_device")["queries"][0]
        result = {"selector": selector, "status": "resolved", "key": {"public_key_b64u": "A" * 43}, "accepted_at": "2026-09-10T00:00:00.000Z"}
        validator = self.validator("historical_account_device_result")
        validator.validate(result)
        changed = copy.deepcopy(result)
        changed["key"]["authorization_ref"] = selector["event_id"]
        self.assertFalse(validator.is_valid(changed))
        result["signer_evidence_ref"] = "ak:signer_evidence:sha256:" + "a" * 64
        self.assertFalse(validator.is_valid(result))

    def test_historical_agent_retains_authorization_without_source_provenance(self):
        selector = self.request("historical_event")["queries"][0]
        result = {"selector": selector, "status": "resolved", "key": {"public_key_b64u": "A" * 43, "authorization_ref": selector["event_id"]}, "accepted_at": "2026-09-10T00:00:00.000Z"}
        validator = self.validator("historical_agent_result")
        validator.validate(result)
        del result["key"]["authorization_ref"]
        self.assertFalse(validator.is_valid(result))

    def test_no_old_self_contract_or_sync_bundle(self):
        self.assertNotIn("self_query_request_body", self.documents["current-signer-evidence-operations.schema.json"]["$defs"])
        self.assertNotIn("query_request_body", self.documents["agent-signer-evidence-operations.schema.json"]["$defs"])
        self.assertNotIn("agent_signer_evidence_bundle", self.documents["account-subscribe-frame.schema.json"]["properties"])

if __name__ == "__main__":
    unittest.main()
