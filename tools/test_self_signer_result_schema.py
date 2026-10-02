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

    def committed_ref(self, event_id="ak:event:ARf0hBMoVkQqflOWgdkxNzM3DDLeIZcTJgfcuk16MrSh", position=12):
        return {
            "event_id": event_id,
            "commit_id": "ak:realm_commit:ARNRmzDi2r78zveOLmoHOb6AephFMwVuGE1fwXmCoeo4",
            "stream_ref": {"kind": "realm", "realm_id": "ak:realm:AZocxLUuB-7lfxVbVJzNCcxSEn-aDa07Di6MnigFwGfd"},
            "stream_position": position,
        }

    def key(self):
        return {
            "public_key_b64u": "A" * 43,
            "authorization_ref": self.committed_ref(
                "ak:event:Ae6YFfDokA1FLUx_l-MhAbSvTvoys2ZpRPmqFwrWjd9g", 7
            ),
            "revision": {
                "commit_id": "ak:realm_commit:AQPhm6Di_JMyu-JM932ww_EvyQU0dIIEO2ykFmYb9nD5",
                "stream_position": 15,
            },
            "governance_generation": 4,
        }

    def request(self, mode="current_admission", sender="agent"):
        actor = {"kind": "account", "account_id": {"principal_id": "ak:did_core:web:alice.example", "station_id": "ak:did_core:web:station.example"}}
        selector = {"verification_mode": mode, "sender_kind": sender, "actor": actor, "verification_method": "did:web:alice.example#runtime"}
        if sender == "account_device":
            selector["device_id"] = "ak:device:01964137-0000-7000-8000-000000000001"
            selector["verification_method"] = "did:web:alice.example#" + selector["device_id"]
        if mode == "historical_event":
            selector["committed_event_ref"] = self.committed_ref()
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
        for field in ["device_id", "verification_method", "actor", "committed_event_ref"]:
            changed = copy.deepcopy(request)
            del changed["queries"][0][field]
            self.assertFalse(self.validator("query_request_body").is_valid(changed))

    def test_self_query_is_bounded_at_64_selectors(self):
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

    def test_historical_device_requires_independent_authorization_and_revision(self):
        selector = self.request("historical_event", "account_device")["queries"][0]
        result = {"selector": selector, "status": "resolved", "key": self.key(), "accepted_at": "2026-09-10T00:00:00.000Z"}
        validator = self.validator("historical_account_device_outcome")
        validator.validate(result)
        self.assertNotEqual(result["key"]["authorization_ref"], selector["committed_event_ref"])
        for field in ["authorization_ref", "revision", "governance_generation"]:
            changed = copy.deepcopy(result)
            del changed["key"][field]
            self.assertFalse(validator.is_valid(changed))
        result["signer_evidence_ref"] = "ak:signer_evidence:sha256:" + "a" * 64
        self.assertFalse(validator.is_valid(result))

    def test_historical_agent_retains_independent_authorization_coordinate(self):
        selector = self.request("historical_event")["queries"][0]
        result = {"selector": selector, "status": "resolved", "key": self.key(), "accepted_at": "2026-09-10T00:00:00.000Z"}
        validator = self.validator("historical_agent_outcome")
        validator.validate(result)
        del result["key"]["authorization_ref"]
        self.assertFalse(validator.is_valid(result))

    def test_bare_event_id_is_not_a_historical_coordinate(self):
        request = self.request("historical_event")
        selector = request["queries"][0]
        selector["event_id"] = selector.pop("committed_event_ref")["event_id"]
        self.assertFalse(self.validator("query_request_body").is_valid(request))

    def test_current_selector_rejects_a_committed_coordinate(self):
        request = self.request()
        request["queries"][0]["committed_event_ref"] = self.committed_ref()
        self.assertFalse(self.validator("query_request_body").is_valid(request))

    def test_human_current_is_key_only_and_cannot_cross_branches(self):
        selector = self.request("current_admission", "account_device")["queries"][0]
        result = {"selector": selector, "status": "resolved", "key": {"public_key_b64u": "A" * 43}}
        self.validator("current_outcome").validate(result)
        for field, value in self.key().items():
            if field == "public_key_b64u":
                continue
            changed = copy.deepcopy(result)
            changed["key"][field] = value
            self.assertFalse(self.validator("current_outcome").is_valid(changed))
        for mode, sender in [("current_admission", "agent"), ("historical_event", "agent"), ("historical_event", "account_device")]:
            changed = copy.deepcopy(result)
            changed["selector"] = self.request(mode, sender)["queries"][0]
            if mode == "historical_event":
                changed["accepted_at"] = "2026-09-10T00:00:00.000Z"
            fragment = "current_outcome" if mode == "current_admission" else "historical_" + sender + "_outcome"
            self.assertFalse(self.validator(fragment).is_valid(changed))

    def test_contact_endpoint_is_closed_and_only_for_accepted_humans(self):
        row = {"peer": {"kind": "human", "account_id": self.request()["recipient_account_id"]},
               "state": "accepted", "granted_to_peer_scopes": [], "granted_by_peer_scopes": [], "bidirectional_scopes": [],
               "next_prepare_input": {"contact_round_id": "sha256:" + "1" * 64, "version": 2,
                                      "predecessor_event_ref": self.committed_ref()["event_id"]},
               "peer_endpoint": {"contact_event_ref": self.committed_ref()["event_id"],
                                 "device_id": "ak:device:01964137-0000-7000-8000-000000000001"}}
        validator = self.validator("contact_list_row", "contact-operations.schema.json")
        validator.validate(row)
        for field in ["contact_event_ref", "device_id"]:
            changed = copy.deepcopy(row)
            del changed["peer_endpoint"][field]
            self.assertFalse(validator.is_valid(changed))
        changed = copy.deepcopy(row)
        changed["peer_endpoint"]["authorization_ref"] = self.committed_ref()
        self.assertFalse(validator.is_valid(changed))
        for state in ["pending_outgoing", "pending_incoming", "rejected", "expired", "tombstoned"]:
            changed = copy.deepcopy(row)
            changed["state"] = state
            del changed["next_prepare_input"]
            changed["request_event_ref"] = self.committed_ref()["event_id"]
            self.assertFalse(validator.is_valid(changed))

    def test_no_sync_bundle_on_the_subscribe_frame(self):
        self.assertNotIn("agent_signer_evidence_bundle", self.documents["account-subscribe-frame.schema.json"]["properties"])

if __name__ == "__main__":
    unittest.main()
