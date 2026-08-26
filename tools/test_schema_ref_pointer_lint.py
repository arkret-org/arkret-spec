"""Mutation tests for complete JSON Schema `$ref` pointer resolution."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.core import Lint
from tools.artifact_lint.schemas import (
    ensure_relative_file,
    ensure_schema_annotation_pointers,
)


TARGET = ROOT / "spec" / "v1" / "artifacts" / "schemas" / "event-payload.schema.json"


class SchemaRefPointerLintTest(unittest.TestCase):
    def test_existing_local_pointer_passes(self) -> None:
        lint = Lint()
        ensure_relative_file(lint, TARGET, TARGET.parent, "#/$defs/digest", "probe")
        self.assertEqual(lint.errors, [])

    def test_missing_local_pointer_fails(self) -> None:
        lint = Lint()
        ensure_relative_file(lint, TARGET, TARGET.parent, "#/$defs/absent_probe", "probe")
        self.assertTrue(any("missing location" in error for error in lint.errors), lint.errors)

    def test_missing_cross_file_pointer_fails(self) -> None:
        lint = Lint()
        ensure_relative_file(
            lint,
            TARGET,
            TARGET.parent,
            "./account-operations.schema.json#/$defs/absent_probe",
            "probe",
        )
        self.assertTrue(any("missing location" in error for error in lint.errors), lint.errors)

    def test_annotation_pointer_resolves_escaped_object_and_array_tokens(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            owner = root / "owner.schema.json"
            target = root / "target.schema.json"
            owner.write_text("{}", encoding="utf-8")
            target.write_text(
                json.dumps({"$defs": {"a/b": {"items": [{"type": "string"}]}}}),
                encoding="utf-8",
            )
            lint = Lint()
            ensure_schema_annotation_pointers(
                lint,
                owner,
                "See target.schema.json#/$defs/a~1b/items/0 for the canonical shape.",
                "probe",
            )
            self.assertEqual(lint.errors, [])

    def test_annotation_pointer_rejects_missing_array_location(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            owner = root / "owner.schema.json"
            target = root / "target.schema.json"
            owner.write_text("{}", encoding="utf-8")
            target.write_text(
                json.dumps({"$defs": {"items": [{"type": "string"}]}}),
                encoding="utf-8",
            )
            lint = Lint()
            ensure_schema_annotation_pointers(
                lint,
                owner,
                "See target.schema.json#/$defs/items/1.",
                "probe",
            )
            self.assertTrue(any("missing location" in error for error in lint.errors), lint.errors)

    def test_annotation_pointer_keeps_dots_inside_tokens_but_not_sentence_period(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            owner = root / "owner.schema.json"
            target = root / "target.schema.json"
            owner.write_text("{}", encoding="utf-8")
            target.write_text(
                json.dumps({"properties": {"field.name": {"type": "string"}}}),
                encoding="utf-8",
            )
            lint = Lint()
            ensure_schema_annotation_pointers(
                lint,
                owner,
                "See target.schema.json#/properties/field.name.",
                "probe",
            )
            self.assertEqual(lint.errors, [])


if __name__ == "__main__":
    unittest.main()
