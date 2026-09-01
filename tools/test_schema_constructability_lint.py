"""Mutation tests for graph-wide JSON Schema constructability analysis."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.constructability import constructability_errors


SCHEMAS = ROOT / "spec" / "v1" / "artifacts" / "schemas"


class SchemaConstructabilityLintTest(unittest.TestCase):
    @staticmethod
    def _messages(documents: dict[str, object]) -> list[str]:
        return [message for _document, message in constructability_errors(documents)]

    def test_current_schema_graph_has_no_empty_language(self) -> None:
        documents = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(SCHEMAS.glob("*.schema.json"))
        }
        self.assertEqual(self._messages(documents), [])

    def test_nested_ref_closed_object_overlay_is_rejected_with_sources(self) -> None:
        documents = {
            "base.schema.json": {
                "$defs": {
                    "closed": {
                        "type": "object",
                        "required": ["id"],
                        "properties": {"id": {"type": "string"}},
                        "additionalProperties": False,
                    }
                }
            },
            "probe.schema.json": {
                "$defs": {"hop": {"$ref": "./base.schema.json#/$defs/closed"}},
                "type": "object",
                "required": ["payload"],
                "properties": {
                    "payload": {
                        "allOf": [
                            {"$ref": "#/$defs/hop"},
                            {
                                "required": ["extra"],
                                "properties": {"extra": {"type": "string"}},
                            },
                        ]
                    }
                },
                "additionalProperties": False,
            },
        }
        messages = self._messages(documents)
        self.assertTrue(any("required property 'extra'" in message for message in messages), messages)
        self.assertTrue(any("base.schema.json#['$defs'].closed" in message for message in messages), messages)
        self.assertTrue(any("properties.payload" in message for message in messages), messages)

    def test_unevaluated_properties_overlay_accepts_ref_declared_members(self) -> None:
        documents = {
            "probe.schema.json": {
                "$defs": {
                    "base": {
                        "type": "object",
                        "required": ["id"],
                        "properties": {"id": {"type": "string"}},
                    }
                },
                "allOf": [
                    {"$ref": "#/$defs/base"},
                    {
                        "type": "object",
                        "required": ["label"],
                        "properties": {"label": {"type": "string"}},
                    },
                ],
                "unevaluatedProperties": False,
            }
        }
        self.assertEqual(self._messages(documents), [])

    def test_nested_required_property_type_intersection_is_rejected(self) -> None:
        documents = {
            "probe.schema.json": {
                "type": "object",
                "required": ["payload"],
                "properties": {
                    "payload": {
                        "allOf": [
                            {"type": "string"},
                            {"$ref": "#/$defs/object_value"},
                        ]
                    }
                },
                "additionalProperties": False,
                "$defs": {"object_value": {"type": "object"}},
            }
        }
        messages = self._messages(documents)
        self.assertTrue(any("no common JSON type" in message for message in messages), messages)

    def test_any_of_with_one_constructible_branch_remains_constructible(self) -> None:
        documents = {
            "probe.schema.json": {
                "anyOf": [
                    {"allOf": [{"type": "string"}, {"type": "object"}]},
                    {"type": "integer", "minimum": 1},
                ]
            }
        }
        messages = self._messages(documents)
        self.assertFalse(any(message.startswith("$ is unconstructible") for message in messages), messages)

    def test_literal_objects_are_not_misread_as_subschemas(self) -> None:
        documents = {
            "probe.schema.json": {
                "type": "object",
                "const": {"type": "not-a-schema", "allOf": False},
                "examples": [{"type": "also-not-a-schema"}],
            }
        }
        self.assertEqual(self._messages(documents), [])


if __name__ == "__main__":
    unittest.main()
