"""Agent key selectors retain one lexical contract before and after projection."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SCHEMAS = Path(__file__).resolve().parents[1] / "spec/v1/artifacts/schemas"
CARRIERS = [
    ("event-payload.schema.json", "/$defs/agent_key_id"),
    ("event-payload.schema.json", "/$defs/agent_key_authorize_payload/properties/key_id"),
    ("event-payload.schema.json", "/$defs/agent_key_authorize_payload/properties/supersedes/items/properties/key_id"),
    ("event-payload.schema.json", "/$defs/agent_key_revoke_payload/properties/key_id"),
    ("agent-operations.schema.json", "/$defs/agent_key_authorization_state/properties/key_id"),
    ("agent-authority-evidence.schema.json", "/$defs/agent_key_authorization/properties/agent_key_id"),
    ("current-state.schema.json", "/$defs/current_agent_key/properties/selector/properties/agent_key_id"),
]


class AgentKeyIdentifierProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = {path.name: json.loads(path.read_text(encoding="utf-8"))
                         for path in SCHEMAS.glob("*.json")}
        cls.registry = Registry().with_resources(
            (document["$id"], Resource.from_contents(document))
            for document in cls.documents.values()
        )

    def accepts(self, file, pointer, value):
        document = self.documents[file]
        validator = Draft202012Validator(
            {"$ref": document["$id"] + "#" + pointer}, registry=self.registry
        )
        return validator.is_valid(value)

    def test_all_carriers_share_bounded_namespace_and_existing_vocabulary(self):
        prefix = "did:web:example.org#"
        cases = [("runtime-key_1:main", True), ("a" * 256, True),
                 (prefix + "k" * (256 - len(prefix)), True),
                 (prefix + "🦀" * (256 - len(prefix)), True),
                 ("", False), ("ak:key:example", False), ("a" * 257, False),
                 (prefix + "k" * (257 - len(prefix)), False),
                 (" ", False), ("local key", False), ("local#fragment", False),
                 ("local\n", False), (prefix + "key\n", False)]
        for file, pointer in CARRIERS:
            for value, expected in cases:
                with self.subTest(file=file, pointer=pointer, value=value):
                    self.assertEqual(self.accepts(file, pointer, value), expected)

    def test_projection_references_the_event_terminal_without_redeclaration(self):
        key = self.documents["agent-operations.schema.json"]["$defs"][
            "agent_key_authorization_state"]["properties"]["key_id"]
        self.assertEqual(key, {"$ref": "./event-payload.schema.json#/$defs/agent_key_id"})

    def test_paired_event_and_projection_acceptance_never_diverges(self):
        samples = ["key-1", "a" * 256, "a" * 257, "ak:key:example",
                   "did:web:" + "a" * 250 + ".example#runtime-key", "value with spaces"]
        for value in samples:
            event = self.accepts("event-payload.schema.json", "/$defs/agent_key_id", value)
            for file, pointer in CARRIERS[1:]:
                with self.subTest(value=value, file=file, pointer=pointer):
                    self.assertEqual(event, self.accepts(file, pointer, value))


if __name__ == "__main__":
    unittest.main()
