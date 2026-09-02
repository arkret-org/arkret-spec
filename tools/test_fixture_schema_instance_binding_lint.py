"""Tests for the fixture schema-instance binding gate.

`check_declared_schema_fixture_instances` only claims fixture objects that name
their own schema. An object without that member has no schema landing point at
all, so it survives every field deletion its schema makes. This gate binds those
objects by exact JSON Pointer; these tests pin that a stale pointer, an embedded
JSON string, and a double-owned instance are all failures rather than skips.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as fixtures_module
from tools.artifact_lint.core import Lint

REGISTRY = json.loads(
    (ROOT / "tools" / "fixture-schema-instance-binding-registry.json").read_text(encoding="utf-8")
)
FIXTURES = ROOT / "spec" / "v1" / "artifacts" / "fixtures"


class FixtureSchemaInstanceBindingLintTest(unittest.TestCase):
    def run_with(self, registry: dict) -> list[str]:
        original = fixtures_module.load_json

        def fake_load_json(lint, path):
            if path == fixtures_module.FIXTURE_SCHEMA_INSTANCE_BINDING_PATH:
                return registry
            return original(lint, path)

        fixtures_module.load_json = fake_load_json
        try:
            lint = Lint()
            fixtures_module.check_fixture_schema_instance_bindings(lint)
            return [str(error) for error in lint.errors]
        finally:
            fixtures_module.load_json = original

    def test_shipped_registry_is_clean(self) -> None:
        self.assertEqual(self.run_with(REGISTRY), [])

    def test_registry_is_not_empty(self) -> None:
        # An empty registry would pass every check while covering nothing.
        self.assertTrue(REGISTRY["bindings"])

    def test_every_binding_targets_a_shipped_fixture(self) -> None:
        for row in REGISTRY["bindings"]:
            self.assertTrue((FIXTURES / row["fixture"]).is_file(), row["fixture"])

    def test_stale_pointer_fails(self) -> None:
        registry = {
            **REGISTRY,
            "bindings": [{**REGISTRY["bindings"][0], "pointer": "/no_such_member"}],
        }
        errors = self.run_with(registry)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("no longer resolves", errors[0])

    def test_embedded_json_string_is_decoded_before_validating(self) -> None:
        row = next(r for r in REGISTRY["bindings"] if r.get("decode") == "json_string")
        # Without the decode mode the raw string is not an object, so the gate
        # must not silently accept it.
        registry = {**REGISTRY, "bindings": [{k: v for k, v in row.items() if k != "decode"}]}
        errors = self.run_with(registry)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("fails", errors[0])

    def test_non_string_value_declared_as_json_string_fails(self) -> None:
        row = next(r for r in REGISTRY["bindings"] if r.get("decode") != "json_string")
        registry = {**REGISTRY, "bindings": [{**row, "decode": "json_string"}]}
        errors = self.run_with(registry)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("not a string", errors[0])

    def test_unknown_decode_mode_fails(self) -> None:
        registry = {**REGISTRY, "bindings": [{**REGISTRY["bindings"][0], "decode": "base64"}]}
        errors = self.run_with(registry)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("unknown decode mode", errors[0])

    def test_duplicate_binding_fails(self) -> None:
        registry = {**REGISTRY, "bindings": [REGISTRY["bindings"][0], REGISTRY["bindings"][0]]}
        errors = self.run_with(registry)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("duplicate binding", errors[0])

    def test_stub_rationale_fails(self) -> None:
        registry = {**REGISTRY, "bindings": [{**REGISTRY["bindings"][0], "why": "n/a"}]}
        errors = self.run_with(registry)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("why must say", errors[0])

    def test_instance_that_names_its_own_schema_is_rejected(self) -> None:
        # Already owned by check_declared_schema_fixture_instances; a second
        # owner lets the two disagree.
        registry = {
            **REGISTRY,
            "bindings": [
                {
                    "fixture": "agent-vectors-fixture.json",
                    "pointer": "/schema_validation_cases/8/instance",
                    "schema_ref": "schemas/agent-operations.schema.json",
                    "why": "synthetic row used only to prove the double-ownership guard fires",
                }
            ],
        }
        errors = self.run_with(registry)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("already owned", errors[0])

    def test_empty_bindings_list_fails(self) -> None:
        errors = self.run_with({**REGISTRY, "bindings": []})
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("non-empty list", errors[0])


if __name__ == "__main__":
    unittest.main()
