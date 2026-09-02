"""Tests for the expanded-projection gate adopted by review `2026-09-02-1959` #6.

A binding field that is not in the transcript's own wire leaf has to come from
somewhere; the registry must name that source. The gate is a bijection, not a
one-way check: an undeclared expansion is a hidden field, and a declaration for a
field that is already on the wire (or is not a binding field at all) is stale.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.core import Lint
from tools.artifact_lint.expanded_projections import _compare, _declared_injections

PATH = Path("registry/proof-context-registry.json")
LABEL = "contexts[0] ak.example_proof.v1"
KEY = "injected_fields"


def compare(binding: set[str], wire: set[str], declared: dict[str, str]) -> list[str]:
    lint = Lint()
    _compare(lint, PATH, LABEL, KEY, binding, wire, declared)
    return [str(error) for error in lint.errors]


class ExpandedProjectionRegistryLintTest(unittest.TestCase):
    def test_binding_fields_all_on_the_wire_pass(self) -> None:
        self.assertEqual(compare({"issuer", "created_at"}, {"issuer", "created_at"}, {}), [])

    def test_declared_expansion_covers_an_off_wire_field(self) -> None:
        self.assertEqual(
            compare(
                {"issuer", "operation_id"},
                {"issuer"},
                {"operation_id": "constant ak.find.directory.read.v1"},
            ),
            [],
        )

    def test_undeclared_expansion_fails(self) -> None:
        errors = compare({"issuer", "operation_id"}, {"issuer"}, {})
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("operation_id", errors[0])
        self.assertIn("never declares", errors[0])

    def test_declaration_for_a_field_already_on_the_wire_is_stale(self) -> None:
        errors = compare({"issuer"}, {"issuer"}, {"issuer": "request.issuer"})
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("already carries", errors[0])

    def test_declaration_for_a_non_binding_field_is_foreign(self) -> None:
        errors = compare({"issuer"}, {"issuer"}, {"unrelated": "request.unrelated"})
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("not binding fields", errors[0])

    def test_injection_entries_must_be_field_source_pairs(self) -> None:
        lint = Lint()
        self.assertEqual(
            _declared_injections(
                lint, PATH, LABEL, [{"field": "operation_id", "source": "constant ak.x.v1"}], KEY
            ),
            {"operation_id": "constant ak.x.v1"},
        )
        self.assertEqual(lint.errors, [])

    def test_injection_entry_with_extra_members_fails(self) -> None:
        lint = Lint()
        self.assertIsNone(
            _declared_injections(
                lint,
                PATH,
                LABEL,
                [{"field": "operation_id", "source": "constant ak.x.v1", "note": "why"}],
                KEY,
            )
        )
        self.assertEqual(len(lint.errors), 1)

    def test_injection_entry_with_a_stub_source_fails(self) -> None:
        lint = Lint()
        self.assertIsNone(
            _declared_injections(lint, PATH, LABEL, [{"field": "x", "source": "n/a"}], KEY)
        )
        self.assertEqual(len(lint.errors), 1)

    def test_duplicate_field_declaration_fails(self) -> None:
        lint = Lint()
        self.assertIsNone(
            _declared_injections(
                lint,
                PATH,
                LABEL,
                [
                    {"field": "operation_id", "source": "constant ak.x.v1"},
                    {"field": "operation_id", "source": "request.operation_id"},
                ],
                KEY,
            )
        )
        self.assertEqual(len(lint.errors), 1)

    def test_shipped_registry_is_clean(self) -> None:
        from tools.artifact_lint.expanded_projections import check_expanded_projection_registry

        lint = Lint()
        check_expanded_projection_registry(lint)
        self.assertEqual(lint.errors, [])


if __name__ == "__main__":
    unittest.main()
