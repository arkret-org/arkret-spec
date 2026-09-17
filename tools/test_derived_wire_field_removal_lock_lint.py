"""Tests for the derived-wire-field removal lock adopted by review `2026-09-02-1959` #9.

The lock is deliberately dumb: it works only on exact `(schema, path, removed)`
rows a ruling named, never on field-name semantics. These tests pin both halves
of each row -- the removed member stays gone, and the member it is recomputed
from stays declared -- plus the row-shape rules that keep the lock hand-auditable.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.core import Lint
from tools.artifact_lint.derived_wire_removals import (
    check_derived_wire_field_removals,
    load_derived_wire_field_removals,
)

LOCK = json.loads(
    (ROOT / "spec" / "v1" / "artifacts" / "registry" / "derived-wire-field-removal-lock.json")
    .read_text(encoding="utf-8")
)

ROW = {
    "lock_id": "ak.lock.derived_wire_field_removal.example_count.v1",
    "ruling": "2026-09-02-1951 A1",
    "schema": "schemas/circle-operations.schema.json",
    "path": "/$defs/example_view",
    "removed": "member_count",
    "source": {"field": "member_ids"},
    "derivation": "member_count := len(member_ids)",
    "spec_anchor": "spec/v1/zh/models/circle.md",
}

DOCS = {
    "circle-operations.schema.json": {
        "$defs": {
            "example_view": {
                "type": "object",
                "properties": {"member_ids": {"type": "array"}},
                "required": ["member_ids"],
            }
        }
    }
}


def lock_with(*rows: dict) -> dict:
    document = {key: copy.deepcopy(value) for key, value in LOCK.items() if key != "removals"}
    document["removals"] = [copy.deepcopy(row) for row in rows]
    return document


def run(document: dict, docs: dict | None = None) -> list[str]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "lock.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        lint = Lint()
        check_derived_wire_field_removals(lint, path, copy.deepcopy(docs if docs is not None else DOCS))
        return [str(error) for error in lint.errors]


def load(document: dict) -> tuple[list[dict], list[str]]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "lock.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        lint = Lint()
        rows = load_derived_wire_field_removals(lint, path)
        return rows, [str(error) for error in lint.errors]


class DerivedWireFieldRemovalLockLintTest(unittest.TestCase):
    def test_deleted_member_absent_and_source_present_passes(self) -> None:
        self.assertEqual(run(lock_with(ROW)), [])

    def test_restored_member_in_properties_fails(self) -> None:
        docs = copy.deepcopy(DOCS)
        docs["circle-operations.schema.json"]["$defs"]["example_view"]["properties"][
            "member_count"
        ] = {"type": "integer"}
        errors = run(lock_with(ROW), docs)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("carries member_count again", errors[0])

    def test_restored_member_only_in_required_fails(self) -> None:
        docs = copy.deepcopy(DOCS)
        docs["circle-operations.schema.json"]["$defs"]["example_view"]["required"].append(
            "member_count"
        )
        errors = run(lock_with(ROW), docs)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("carries member_count again", errors[0])

    def test_dropped_source_member_fails(self) -> None:
        docs = copy.deepcopy(DOCS)
        view = docs["circle-operations.schema.json"]["$defs"]["example_view"]
        view["properties"] = {}
        view["required"] = []
        errors = run(lock_with(ROW), docs)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("must keep declaring member_ids", errors[0])

    def test_moved_carrier_fails_instead_of_passing_silently(self) -> None:
        errors = run(lock_with(ROW), {"circle-operations.schema.json": {"$defs": {}}})
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("no longer resolves", errors[0])

    def test_source_equal_to_the_removed_member_is_rejected(self) -> None:
        row = {**ROW, "source": {"field": "member_count"}}
        rows, errors = load(lock_with(row))
        self.assertEqual(rows, [])
        self.assertTrue(any("must not be the removed member itself" in e for e in errors), errors)

    def test_ruling_naming_a_repository_path_is_rejected(self) -> None:
        row = {**ROW, "ruling": "arkret-work/tasks/spec-open/2026-09-02-1951.md"}
        rows, errors = load(lock_with(row))
        self.assertEqual(rows, [])
        self.assertTrue(any("never a repository path" in e for e in errors), errors)

    def test_duplicate_triple_is_rejected(self) -> None:
        second = {**ROW, "lock_id": "ak.lock.derived_wire_field_removal.example_count_two.v1"}
        rows, errors = load(lock_with(ROW, second))
        self.assertEqual(len(rows), 1)
        self.assertTrue(any("duplicate (schema, path, removed)" in e for e in errors), errors)

    def test_sibling_digest_row_belongs_to_the_other_owner(self) -> None:
        # 4.0.1 sibling digests are locked by CONTENT_ADDRESSED_REF_MIRROR_REMOVALS;
        # one deletion has exactly one lock.
        row = {
            **ROW,
            "lock_id": "ak.lock.derived_wire_field_removal.file_transfer_content_digest.v1",
            "schema": "schemas/file-transfer.schema.json",
            "path": "",
            "removed": "content_digest",
            "source": {"field": "blob_ref"},
            "derivation": "content_digest := digest carried by the content-addressed blob_ref",
            "spec_anchor": "spec/v1/zh/models/file-transfer.md",
        }
        rows, errors = load(lock_with(row))
        self.assertEqual(rows, [])
        self.assertTrue(any("one deletion has one lock" in e for e in errors), errors)

    def test_row_keys_must_keep_their_declared_order(self) -> None:
        reordered = {key: ROW[key] for key in reversed(list(ROW))}
        rows, errors = load(lock_with(reordered))
        self.assertEqual(rows, [])
        self.assertTrue(any("keys must be exactly" in e for e in errors), errors)

    def test_spec_anchor_must_resolve(self) -> None:
        row = {**ROW, "spec_anchor": "spec/v1/zh/models/does-not-exist.md"}
        rows, errors = load(lock_with(row))
        self.assertEqual(rows, [])
        self.assertTrue(any("spec_anchor must point at" in e for e in errors), errors)

    def test_shipped_lock_is_clean(self) -> None:
        lint = Lint()
        check_derived_wire_field_removals(lint)
        self.assertEqual(lint.errors, [])


if __name__ == "__main__":
    unittest.main()
