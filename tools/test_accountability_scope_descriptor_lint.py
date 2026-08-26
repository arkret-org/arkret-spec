"""Mutation test for the accountability string-set descriptor lint boundary."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import foundation, schemas
from tools.artifact_lint.core import Lint

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
ACCOUNTABILITY_SCHEMA = ARTIFACTS / "schemas" / "accountability-grant.schema.json"
EVENT_SCHEMA = ARTIFACTS / "schemas" / "event-envelope.schema.json"
EVENT_REGISTRY = ARTIFACTS / "registry" / "event-kind-registry.json"


class AccountabilityScopeDescriptorLintTest(unittest.TestCase):
    def test_descriptor_and_schema_mutations_fail_closed(self) -> None:
        original_foundation_load_json = foundation.load_json
        original_schemas_load_json = schemas.load_json
        schema = copy.deepcopy(original_schemas_load_json(Lint(), ACCOUNTABILITY_SCHEMA))
        array_variant = schema["properties"]["accountability_scope"]["oneOf"][1]
        del array_variant["minItems"]
        del array_variant["uniqueItems"]
        array_variant["items"] = {"type": "string", "enum": ["employment"]}

        registry = copy.deepcopy(original_foundation_load_json(Lint(), EVENT_REGISTRY))
        row = next(
            row
            for row in registry["event_kinds"]
            if row["event_kind"] == "ak.identity.accountability_grant"
        )
        components = row["cell_writes"][0]["cell_subject"]["components"]
        components[2]["unexpected"] = True
        components.append(
            {
                "kind": "unknown_component",
                "field": "payload.accountability_scope",
            }
        )

        replacements = {
            ACCOUNTABILITY_SCHEMA.resolve(): schema,
            EVENT_REGISTRY.resolve(): registry,
        }

        def load_json_with_mutation(lint, path):
            replacement = replacements.get(path.resolve())
            if replacement is not None:
                return replacement
            return original_schemas_load_json(lint, path)

        lint = Lint()
        foundation.load_json = load_json_with_mutation
        schemas.load_json = load_json_with_mutation
        try:
            foundation.check_registries(lint)
            event_schema = original_schemas_load_json(lint, EVENT_SCHEMA)
            schemas.check_composite_subject_terminal_types(lint, EVENT_SCHEMA, event_schema)
        finally:
            foundation.load_json = original_foundation_load_json
            schemas.load_json = original_schemas_load_json

        diagnostics = "\n".join(lint.errors)
        for expected in (
            "unknown member(s) ['unexpected']",
            ".kind must be 'select'",
            "array schema must declare minItems >= 1",
            "array schema must declare uniqueItems: true",
            "string and array item variants must share one element schema",
        ):
            self.assertIn(expected, diagnostics)

        lint_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "tools" / "artifact_lint").glob("*.py")
        )
        self.assertNotIn("finding 09", lint_source.lower())


if __name__ == "__main__":
    unittest.main()
