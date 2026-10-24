"""The existing Call lifecycle carrier separates genesis from later deltas."""
import json
import copy
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SCHEMAS = Path(__file__).resolve().parents[1] / "spec/v1/artifacts/schemas"


def validator(document, subschema):
    resources = []
    for path in SCHEMAS.glob("*.json"):
        content = json.loads(path.read_text(encoding="utf-8"))
        if "$id" in content:
            resources.append((content["$id"], Resource.from_contents(content)))
    return Draft202012Validator(
        {"$schema": document["$schema"], "$id": document["$id"], "$defs": document.get("$defs", {}), **subschema},
        registry=Registry().with_resources(resources),
    )


class CallCurrentGenesisSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        current = json.loads((SCHEMAS / "current-state.schema.json").read_text(encoding="utf-8"))
        events = json.loads((SCHEMAS / "event-payload.schema.json").read_text(encoding="utf-8"))
        cls.current = validator(current, current["$defs"]["current_call_state"]["properties"]["value"])
        cls.create = validator(events, events["$defs"]["call_create_payload"])
        cls.delta = validator(events, events["$defs"]["call_state_payload"]["properties"]["state_transition"])

    def test_creation_current_allows_only_explicit_null_and_the_three_initial_states(self):
        for state in ["scheduled", "ringing", "connecting"]:
            self.current.validate({"from": None, "to": state})
        for state in ["active", "ended", "missed", "failed", "cancelled"]:
            self.assertFalse(self.current.is_valid({"from": None, "to": state}))
        for value in [{"to": "ringing"}, {"from": None, "to": "ringing", "call_id": "extra"}]:
            self.assertFalse(self.current.is_valid(value))

    def test_creation_structure_leaves_known_noninitial_states_to_the_registered_semantic_refusal(self):
        for state in ["scheduled", "ringing", "connecting", "active", "ended", "missed", "failed", "cancelled"]:
            self.create.validate({"initial_state": state})
        self.assertFalse(self.create.is_valid({"initial_state": "unknown"}))
        self.assertFalse(self.create.is_valid({"initial_state": "ringing", "call_id": "extra"}))

    def test_later_event_deltas_still_require_a_nonnull_predecessor(self):
        self.delta.validate({"from": "connecting", "to": "active"})
        self.current.validate({"from": "connecting", "to": "active"})
        self.assertFalse(self.delta.is_valid({"from": None, "to": "ringing"}))

    def test_creation_writer_registry_points_at_the_genesis_aware_current(self):
        artifacts = SCHEMAS.parent
        for name in ["contract-registry.json", "event-kind-registry.json"]:
            registry = json.loads((artifacts / "registry" / name).read_text(encoding="utf-8"))
            def find_create(value):
                if isinstance(value, dict):
                    if value.get("event_kind") == "ak.call.create":
                        return value
                    for child in value.values():
                        found = find_create(child)
                        if found is not None:
                            return found
                elif isinstance(value, list):
                    for child in value:
                        found = find_create(child)
                        if found is not None:
                            return found
                return None
            writer = find_create(registry)["state_writes"][0]
            self.assertEqual(writer["value_schema_ref"],
                             "schemas/current-state.schema.json#/$defs/current_call_state/properties/value")


class CallActorIdentitySchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        events = json.loads((SCHEMAS / "event-payload.schema.json").read_text(encoding="utf-8"))
        operations = json.loads((SCHEMAS / "call-invitation-operations.schema.json").read_text(encoding="utf-8"))
        cls.roster = validator(events, events["$defs"]["call_state_payload"]["properties"]["roster_delta"])
        cls.binding = validator(events, events["$defs"]["participant_binding"])
        cls.refresh = validator(operations, operations["$defs"]["refresh_join_context"])
        signal = json.loads((SCHEMAS / "call-signal-plaintext.schema.json").read_text(encoding="utf-8"))
        cls.signal = validator(signal, signal)
        cls.actor = {"kind": "account", "account_id": {
            "principal_id": "ak:did_core:web:alice.example",
            "station_id": "ak:did_core:web:station.example",
        }}
        cls.device = "ak:device:01964137-0000-7000-8000-000000000001"

    def test_join_and_leave_use_complete_actor_and_real_device(self):
        join = {"op": "join", "participant": {"actor_id": self.actor, "device_id": self.device}}
        leave = {"op": "leave", "actor_id": self.actor, "device_id": self.device,
                 "expected_revision": {"commit_id": "ak:realm_commit:" + "A" * 44, "stream_position": 3}}
        self.roster.validate(join)
        self.roster.validate(leave)
        for value, owner in [(join, "participant"), (leave, None)]:
            invalid = copy.deepcopy(value)
            target = invalid[owner] if owner else invalid
            target["actor_id"] = self.actor["account_id"]["principal_id"]
            self.assertFalse(self.roster.is_valid(invalid))
            target["actor_id"] = {"kind": "account", "account_id": {
                "principal_id": self.actor["account_id"]["principal_id"]}}
            self.assertFalse(self.roster.is_valid(invalid))

    def test_refresh_uses_accepted_participant_without_private_receipt(self):
        refresh = {"kind": "refresh", "participant_id": "ak:rtc_participant:01964137-0000-7000-8000-000000000001"}
        self.refresh.validate(refresh)
        refresh["subject_binding"] = {}
        self.assertFalse(self.refresh.is_valid(refresh))
        self.assertFalse(self.refresh.is_valid({"kind": "refresh"}))

    def test_moderation_targets_the_same_full_actor_namespace(self):
        signal = {"kind": "ak.call.signal", "payload_sequence": "1",
                  "call_id": "ak:call:" + "A" * 44, "signal_kind": "moderation", "sequence": "1",
                  "data": {"action": "kick", "target_actor_id": self.actor, "target_device_id": self.device}}
        self.signal.validate(signal)
        signal["data"]["target_actor_id"] = self.actor["account_id"]["principal_id"]
        self.assertFalse(self.signal.is_valid(signal))

    def test_public_binding_rejects_retired_private_commitment(self):
        binding = {"expires_at": "2026-10-17T00:05:00.000Z", "issuer_kid": "did:web:media.example#key", "signature": "AA"}
        self.binding.validate(binding)
        binding["subject_binding_digest"] = "sha256:" + "00" * 32
        self.assertFalse(self.binding.is_valid(binding))

    def test_participant_signature_binds_full_station_and_device(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.exceptions import InvalidSignature

        fields = {"actor_id": self.actor, "device_id": self.device,
                  "realm_id": "ak:realm:" + "A" * 44, "call_id": "ak:call:" + "A" * 44,
                  "focus_id": "fra-1", "participant_id": "ak:rtc_participant:01964137-0000-7000-8000-000000000001",
                  "expires_at": "2026-10-17T00:05:00.000Z", "issuer_kid": "did:web:media.example#key",
                  "media": {"audio": True, "video": False, "screen": False}}
        def transcript(value):
            return b"ak.media.participant_binding.v1\0" + json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        key = Ed25519PrivateKey.from_private_bytes(bytes([11]) * 32)
        signature = key.sign(transcript(fields))
        key.public_key().verify(signature, transcript(fields))
        for mutation in ["station", "device", "media"]:
            changed = copy.deepcopy(fields)
            if mutation == "station":
                changed["actor_id"]["account_id"]["station_id"] = "ak:did_core:web:other.example"
            elif mutation == "device":
                changed["device_id"] = "ak:device:01964137-0000-7000-8000-000000000002"
            else:
                changed["media"]["screen"] = True
            with self.assertRaises(InvalidSignature):
                key.public_key().verify(signature, transcript(changed))


if __name__ == "__main__":
    unittest.main()
