"""Mutation tests for schema-aware cell-subject path linting."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import core, schemas


class CellSubjectPathLintTest(unittest.TestCase):
    def _lint_mutated_registry(self, mutate) -> list[str]:
        event_schema_path = (
            ROOT
            / "spec"
            / "v1"
            / "artifacts"
            / "schemas"
            / "event-envelope.schema.json"
        )
        registry_path = (
            ROOT
            / "spec"
            / "v1"
            / "artifacts"
            / "registry"
            / "event-kind-registry.json"
        )
        event_schema = core.parse_json_text(
            event_schema_path.read_text(encoding="utf-8")
        )
        registry = core.parse_json_text(
            registry_path.read_text(encoding="utf-8")
        )
        mutated = copy.deepcopy(registry)
        mutate(mutated)

        original_load_json = schemas.load_json

        def load_json_with_mutation(lint, path):
            if path.resolve() == registry_path.resolve():
                return mutated
            return original_load_json(lint, path)

        schemas.load_json = load_json_with_mutation
        try:
            lint = schemas.Lint()
            schemas.check_composite_subject_terminal_types(
                lint, event_schema_path, event_schema
            )
            return lint.errors
        finally:
            schemas.load_json = original_load_json

    def test_missing_single_field_endpoint_fails_closed(self) -> None:
        def mutate(registry):
            row = next(
                row
                for row in registry["event_kinds"]
                if row["event_kind"] == "ak.actor.discovery"
            )
            row["cell_writes"][0]["cell_subject"]["field"] = "payload.missing_id"

        errors = self._lint_mutated_registry(mutate)
        self.assertTrue(
            any(
                "payload.missing_id" in error
                and "has no schema endpoint" in error
                for error in errors
            ),
            errors,
        )

    def test_coalesce_requires_at_least_one_schema_endpoint(self) -> None:
        def mutate(registry):
            row = next(
                row
                for row in registry["event_kinds"]
                if row["event_kind"] == "ak.policy.action"
            )
            row["cell_writes"][0]["cell_subject"]["fields"] = [
                "payload.missing_policy_id",
                "payload.missing_action_id",
            ]

        errors = self._lint_mutated_registry(mutate)
        self.assertTrue(
            any("coalesce fields have no schema endpoint" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
