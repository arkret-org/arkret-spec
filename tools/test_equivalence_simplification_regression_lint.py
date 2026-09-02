"""Mutation coverage for the three equivalence-simplification regression gates."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import (
    derived_wire_removals,
    expanded_projections,
    ref_overlay_closure,
)
from tools.artifact_lint.core import Lint


class RefOverlayClosureMutationTest(unittest.TestCase):
    def test_current_schemas_are_closed(self) -> None:
        lint = Lint()
        ref_overlay_closure.check_schema_ref_overlay_closure(lint)
        self.assertEqual(lint.errors, [])

    def test_closed_ref_rejects_an_undeclared_required_overlay(self) -> None:
        docs = {
            "test.schema.json": {
                "$defs": {
                    "base": {
                        "type": "object",
                        "required": ["kept"],
                        "properties": {"kept": {"type": "string"}},
                        "additionalProperties": False,
                    },
                    "overlay": {"$ref": "#/$defs/base", "required": ["invented"]},
                }
            }
        }
        lint = Lint()
        with patch.object(ref_overlay_closure, "load_schema_documents", return_value=docs):
            ref_overlay_closure.check_schema_ref_overlay_closure(lint)
        self.assertTrue(any("requires 'invented' through an overlay" in error for error in lint.errors), lint.errors)

    def test_closed_ref_accepts_a_declared_required_overlay(self) -> None:
        docs = {
            "test.schema.json": {
                "$defs": {
                    "base": {
                        "type": "object",
                        "properties": {"kept": {"type": "string"}},
                        "additionalProperties": False,
                    },
                    "overlay": {"$ref": "#/$defs/base", "required": ["kept"]},
                }
            }
        }
        lint = Lint()
        with patch.object(ref_overlay_closure, "load_schema_documents", return_value=docs):
            ref_overlay_closure.check_schema_ref_overlay_closure(lint)
        self.assertEqual(lint.errors, [])


class ExpandedProjectionMutationTest(unittest.TestCase):
    @staticmethod
    def _mutated_registry(mutate) -> list[str]:
        original = expanded_projections.load_json

        def load(lint, path):
            value = copy.deepcopy(original(lint, path))
            if path == expanded_projections.REGISTRY_PATH:
                mutate(value)
            return value

        lint = Lint()
        with patch.object(expanded_projections, "load_json", load):
            expanded_projections.check_expanded_projection_registry(lint)
        return lint.errors

    def test_current_projection_registry_is_closed(self) -> None:
        lint = Lint()
        expanded_projections.check_expanded_projection_registry(lint)
        self.assertEqual(lint.errors, [])

    def test_missing_injected_source_fails(self) -> None:
        def mutate(registry) -> None:
            row = next(row for row in registry["contexts"] if row["context"] == "ak.agent_runtime_key_possession_proof.v1")
            row.pop("injected_fields")

        errors = self._mutated_registry(mutate)
        self.assertTrue(any("pairing_code" in error and "declare each" in error for error in errors), errors)

    def test_stale_injected_source_fails(self) -> None:
        def mutate(registry) -> None:
            row = next(row for row in registry["contexts"] if row["context"] == "ak.agent_runtime_key_possession_proof.v1")
            row["injected_fields"].append({"field": "challenge", "source": "proof.challenge"})

        errors = self._mutated_registry(mutate)
        self.assertTrue(any("challenge" in error and "already carries" in error for error in errors), errors)


class DerivedWireRemovalMutationTest(unittest.TestCase):
    ROW: ClassVar[dict] = {
        "lock_id": "ak.lock.derived_wire_field_removal.example.v1",
        "ruling": "example",
        "schema": "schemas/example.schema.json",
        "path": "/$defs/carrier",
        "removed": "derived_digest",
        "source": {"field": "source_bytes"},
        "derivation": "sha256(source_bytes)",
        "spec_anchor": "spec/v1/zh/conformance/encoding.md",
    }

    @classmethod
    def _check(cls, properties: dict) -> list[str]:
        docs = {
            "example.schema.json": {
                "$defs": {
                    "carrier": {
                        "type": "object",
                        "properties": properties,
                        "additionalProperties": False,
                    }
                }
            }
        }
        lint = Lint()
        with (
            patch.object(derived_wire_removals, "load_derived_wire_field_removals", return_value=[copy.deepcopy(cls.ROW)]),
            patch.object(derived_wire_removals, "load_schema_documents", return_value=docs),
        ):
            derived_wire_removals.check_derived_wire_field_removals(lint)
        return lint.errors

    def test_current_removal_lock_is_closed(self) -> None:
        lint = Lint()
        derived_wire_removals.check_derived_wire_field_removals(lint)
        self.assertEqual(lint.errors, [])

    def test_removed_member_cannot_reappear(self) -> None:
        errors = self._check({"source_bytes": {"type": "string"}, "derived_digest": {"type": "string"}})
        self.assertTrue(any("carries derived_digest again" in error for error in errors), errors)

    def test_derivation_source_cannot_disappear(self) -> None:
        errors = self._check({"other": {"type": "string"}})
        self.assertTrue(any("must keep declaring source_bytes" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
