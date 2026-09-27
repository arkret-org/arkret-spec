"""The existing Call lifecycle carrier separates genesis from later deltas."""
import json
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
        {"$schema": document["$schema"], "$id": document["$id"], **subschema},
        registry=Registry().with_resources(resources),
    )


class CallCurrentGenesisSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        current = json.loads((SCHEMAS / "typed-current-result.schema.json").read_text(encoding="utf-8"))
        events = json.loads((SCHEMAS / "event-payload.schema.json").read_text(encoding="utf-8"))
        cls.current = validator(current, current["$defs"]["call_state_result"]["properties"]["value"])
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


if __name__ == "__main__":
    unittest.main()
