#!/usr/bin/env python3
"""Regression tests for operation string-field classification references."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import gen_operation_string_field_classification as classification


class OperationStringFieldClassificationTests(unittest.TestCase):
    def test_cross_file_recursive_ref_and_percent_decoded_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.json"
            middle_path = root / "middle.json"
            leaf_path = root / "leaf.json"
            source = {
                "$defs": {
                    "status": {"$ref": "middle.json#/$defs/status"},
                }
            }
            middle = {
                "$defs": {
                    "status": {"$ref": "leaf.json#/$defs/open%20status"},
                }
            }
            leaf = {
                "$defs": {
                    "open status": {
                        "type": "string",
                        "pattern": "^[a-z][a-z0-9_]*$",
                        "maxLength": 64,
                    }
                }
            }
            for path, document in (
                (source_path, source),
                (middle_path, middle),
                (leaf_path, leaf),
            ):
                path.write_text(json.dumps(document), encoding="utf-8")

            constraints = classification.effective_constraints(
                source_path,
                source,
                source["$defs"]["status"],
                {source_path.resolve(): source},
            )

        self.assertEqual(constraints["pattern"], "^[a-z][a-z0-9_]*$")
        self.assertEqual(constraints["maxLength"], 64)
        self.assertEqual(
            classification.classify("status", constraints)[0],
            "validated_open_token",
        )

    def test_reference_cycle_terminates_and_remains_unclassified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_path = root / "first.json"
            second_path = root / "second.json"
            first = {"$defs": {"status": {"$ref": "second.json#/$defs/status"}}}
            second = {"$defs": {"status": {"$ref": "first.json#/$defs/status"}}}
            first_path.write_text(json.dumps(first), encoding="utf-8")
            second_path.write_text(json.dumps(second), encoding="utf-8")

            constraints = classification.effective_constraints(
                first_path,
                first,
                first["$defs"]["status"],
                {first_path.resolve(): first},
            )

        self.assertEqual(constraints, {})
        self.assertIsNone(classification.classify("status", constraints)[0])

    def test_remote_and_unreadable_references_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.json"
            source = {}
            documents = {source_path.resolve(): source}

            self.assertIsNone(
                classification.resolve_reference(
                    source_path,
                    "https://example.invalid/schema.json#/$defs/status",
                    documents,
                )
            )
            self.assertIsNone(
                classification.resolve_reference(
                    source_path,
                    "missing.json#/$defs/status",
                    documents,
                )
            )
            for reference in (
                "https://example.invalid/schema.json#/$defs/status",
                "missing.json#/$defs/status",
            ):
                with self.subTest(reference=reference), self.assertRaises(
                    classification.ReferenceResolutionError
                ):
                    classification.effective_constraints(
                        source_path,
                        source,
                        {
                            "$ref": reference,
                            "pattern": "^[a-z]+$",
                            "maxLength": 64,
                        },
                        documents,
                    )

    def test_min_length_alone_does_not_classify_reason_or_status(self) -> None:
        for field in ("reason", "status"):
            with self.subTest(field=field):
                classification_name, _ = classification.classify(
                    field,
                    {"type": "string", "minLength": 1},
                )
                self.assertIsNone(classification_name)


if __name__ == "__main__":
    unittest.main()
