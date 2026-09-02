"""Tests for the overlay-closure gate adopted by review `2026-09-02-1959` #5.

`additionalProperties: false` only sees the schema object it sits in. An overlay
that reaches a closed base through `$ref` or `allOf` and then requires a member
the base never declares is dead in both directions: an instance carrying the
member is rejected by the base, and one omitting it is rejected by the overlay.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.ref_overlay_closure import overlay_closure_violations


def docs(overlay: dict, base: dict | None = None) -> dict[str, dict]:
    base = base if base is not None else {
        "type": "object",
        "additionalProperties": False,
        "properties": {"declared": {"type": "string"}},
    }
    return {
        "overlay.schema.json": {"$defs": {"overlay": overlay}},
        "base.schema.json": {"$defs": {"base": base}},
    }


BASE_REF = "./base.schema.json#/$defs/base"


class SchemaRefOverlayClosureLintTest(unittest.TestCase):
    def test_overlay_requiring_a_declared_member_passes(self) -> None:
        overlay = {"$ref": BASE_REF, "required": ["declared"]}
        self.assertEqual(overlay_closure_violations(docs(overlay), "overlay.schema.json"), [])

    def test_overlay_requiring_an_undeclared_member_through_ref_fails(self) -> None:
        overlay = {"$ref": BASE_REF, "required": ["absent"]}
        violations = overlay_closure_violations(docs(overlay), "overlay.schema.json")
        self.assertEqual(len(violations), 1, violations)
        json_path, name, label = violations[0]
        self.assertEqual(name, "absent")
        self.assertIn("$defs.overlay", json_path)
        self.assertIn("base.schema.json", label)

    def test_overlay_requiring_an_undeclared_member_through_allof_fails(self) -> None:
        overlay = {"allOf": [{"$ref": BASE_REF}], "required": ["absent"]}
        violations = overlay_closure_violations(docs(overlay), "overlay.schema.json")
        self.assertEqual([name for _, name, _ in violations], ["absent"])

    def test_pattern_properties_on_the_base_admit_the_member(self) -> None:
        base = {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
            "patternProperties": {"^ak_": {"type": "string"}},
        }
        overlay = {"$ref": BASE_REF, "required": ["ak_extra"]}
        self.assertEqual(
            overlay_closure_violations(docs(overlay, base), "overlay.schema.json"), []
        )

    def test_an_open_base_is_not_a_closure(self) -> None:
        base = {"type": "object", "properties": {"declared": {"type": "string"}}}
        overlay = {"$ref": BASE_REF, "required": ["absent"]}
        self.assertEqual(
            overlay_closure_violations(docs(overlay, base), "overlay.schema.json"), []
        )

    def test_unevaluated_properties_base_is_also_a_closure(self) -> None:
        base = {
            "type": "object",
            "unevaluatedProperties": False,
            "properties": {"declared": {"type": "string"}},
        }
        overlay = {"$ref": BASE_REF, "required": ["absent"]}
        violations = overlay_closure_violations(docs(overlay, base), "overlay.schema.json")
        self.assertEqual([name for _, name, _ in violations], ["absent"])

    def test_shipped_schemas_are_clean(self) -> None:
        from tools.artifact_lint.core import Lint
        from tools.artifact_lint.ref_overlay_closure import check_schema_ref_overlay_closure

        lint = Lint()
        check_schema_ref_overlay_closure(lint)
        self.assertEqual(lint.errors, [])


if __name__ == "__main__":
    unittest.main()
