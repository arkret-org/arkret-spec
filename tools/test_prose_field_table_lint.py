"""Tests for the prose field table gate adopted by review `2026-09-04-2153`.

`member_roster_entry` was renamed in the schema while the `client-sync.md` field
table and the schema's own descriptions kept the old row, and nothing compared
the two spellings. These cases pin the three failure shapes the gate has to
catch — a renamed row, a missing row and a permuted order — plus the table
assignment that keeps nested tables in one document from claiming each other.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.prose_field_tables import (
    _described_names,
    field_tables,
    locate_tables,
    operation_note_field_drift,
)


def table(*names: str) -> str:
    rows = "\n".join(f"| `{name}` | `Id` | MUST | note |" for name in names)
    return "| field | type | required | note |\n| --- | --- | --- | --- |\n" + rows


class ProseFieldTableLintTest(unittest.TestCase):
    def test_field_table_reads_backticked_first_column(self) -> None:
        found = field_tables(table("actor_id", "membership", "subject_account_id"))
        self.assertEqual(found, [(1, ["actor_id", "membership", "subject_account_id"])])

    def test_table_whose_first_column_is_prose_is_not_a_field_table(self) -> None:
        text = "| field | type |\n| --- | --- |\n| plain text | x |\n| more | y |\n| rows | z |"
        self.assertEqual(field_tables(text), [])

    def test_renamed_row_is_still_matched_to_its_binding(self) -> None:
        text = table("actor_id", "membership", "subject_id", "identity_event_ids")
        declared = ["actor_id", "membership", "subject_account_id", "identity_event_ids"]
        located = locate_tables(text, [declared])
        self.assertIsNotNone(located[0])
        self.assertIn("subject_id", located[0][1])
        self.assertNotEqual(located[0][1], declared)

    def test_exact_tables_are_claimed_before_overlapping_ones(self) -> None:
        text = (
            table("device_id", "display_name", "platform", "push_gateway_url")
            + "\n\n"
            + table("device_id", "platform", "push_gateway_url")
        )
        wide = ["device_id", "display_name", "platform", "push_gateway_url"]
        narrow = ["device_id", "platform", "push_gateway_url"]
        located = locate_tables(text, [wide, narrow])
        self.assertEqual(located[0][1], wide)
        self.assertEqual(located[1][1], narrow)

    def test_permuted_order_is_reported_as_a_different_list(self) -> None:
        declared = ["start", "end", "timezone"]
        located = locate_tables(table("start", "timezone", "end"), [declared])
        self.assertEqual(set(located[0][1]), set(declared))
        self.assertNotEqual(located[0][1], declared)

    def test_unmatched_binding_resolves_to_nothing(self) -> None:
        located = locate_tables(table("alpha_id", "beta_id", "gamma_id"), [["one_id", "two_id"]])
        self.assertIsNone(located[0])

    def test_described_names_reads_the_object_and_its_properties(self) -> None:
        node = {
            "description": "Gates on subject_account_id.",
            "properties": {
                "handle_claims": {"description": "MUST be omitted unless subject_id is disclosed."},
                "subject_account_id": {"type": "object"},
            },
        }
        self.assertEqual(
            _described_names(node), {"subject_account_id", "subject_id"}
        )

    def test_operation_notes_reject_member_from_an_unrelated_schema(self) -> None:
        documents = {
            "operation.schema.json": {
                "$defs": {
                    "request": {"type": "object", "properties": {"request_id": {}}},
                    "response": {"type": "object", "properties": {"status": {}}},
                }
            },
            "other.schema.json": {
                "type": "object",
                "properties": {"retired_member": {}},
            },
        }
        operation = {
            "operation_id": "ak.test.command.run.v1",
            "request_schema_ref": "schemas/operation.schema.json#/$defs/request",
            "response_schema_ref": "schemas/operation.schema.json#/$defs/response",
            "notes": "The request_id is stable and retired_member is returned.",
        }
        errors = operation_note_field_drift(
            [operation], documents, {"operations": {}}
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("retired_member", errors[0])

    def test_operation_note_cross_object_exemption_is_exact(self) -> None:
        documents = {
            "operation.schema.json": {
                "type": "object",
                "properties": {"request_id": {}},
            },
            "other.schema.json": {
                "type": "object",
                "properties": {"audit_record_id": {}},
            },
        }
        operation = {
            "operation_id": "ak.test.command.run.v1",
            "request_schema_ref": "schemas/operation.schema.json#",
            "notes": "The audit_record_id names a separately retained audit object.",
        }
        exemptions = {
            "operations": {"ak.test.command.run.v1": ["audit_record_id"]}
        }
        self.assertEqual(
            operation_note_field_drift([operation], documents, exemptions), []
        )
        operation["notes"] = "No external field is named."
        errors = operation_note_field_drift([operation], documents, exemptions)
        self.assertEqual(len(errors), 1)
        self.assertIn("make no such cross-object mention", errors[0])


if __name__ == "__main__":
    unittest.main()
