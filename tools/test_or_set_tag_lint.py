"""Mutation tests for the OR-Set dot source and the two or_set remove projections."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
MODULE_SPEC = importlib.util.spec_from_file_location(
    "lint_artifacts", ROOT / "tools" / "lint_artifacts.py"
)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
lint_artifacts = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(lint_artifacts)


class OrSetTagLintTest(unittest.TestCase):
    def _lint_projection(self, lattice: str, projection: object) -> list[str]:
        lint = lint_artifacts.Lint()
        lint_artifacts.lint_effect_projection(
            lint, Path("registry/contract-registry.json"), "probe", projection, lattice
        )
        return list(lint.errors)

    # dot source

    def test_dot_tag_is_accepted_for_or_set_add(self) -> None:
        self.assertEqual(
            self._lint_projection(
                "or_set",
                {
                    "kind": "or_set_add",
                    "tag": {"dot": True},
                    "value": {"field": "payload"},
                },
            ),
            [],
        )

    def test_bare_event_id_tag_is_rejected(self) -> None:
        failures = self._lint_projection(
            "or_set",
            {
                "kind": "or_set_add",
                "tag": {"envelope_field": "event_id"},
                "value": {"field": "payload"},
            },
        )
        self.assertTrue(
            any("must use" in failure and "dot" in failure for failure in failures),
            failures,
        )

    def test_dot_is_rejected_outside_a_tag_position(self) -> None:
        failures = self._lint_projection(
            "or_set",
            {"kind": "or_set_add", "tag": {"dot": True}, "value": {"dot": True}},
        )
        self.assertTrue(failures)

    def test_dot_must_be_true(self) -> None:
        failures = self._lint_projection(
            "or_set",
            {
                "kind": "or_set_add",
                "tag": {"dot": False},
                "value": {"field": "payload"},
            },
        )
        self.assertTrue(any("must be true" in failure for failure in failures), failures)

    # or_set_remove_observed

    def test_remove_observed_without_match_is_accepted(self) -> None:
        self.assertEqual(
            self._lint_projection("or_set", {"kind": "or_set_remove_observed"}), []
        )

    def test_remove_observed_with_element_match_is_accepted(self) -> None:
        self.assertEqual(
            self._lint_projection(
                "or_set",
                {
                    "kind": "or_set_remove_observed",
                    "match": {
                        "element_field": "target_ref",
                        "source": {"field": "payload.target_ref"},
                    },
                },
            ),
            [],
        )

    def test_remove_observed_match_requires_a_source(self) -> None:
        failures = self._lint_projection(
            "or_set",
            {"kind": "or_set_remove_observed", "match": {"element_field": "target_ref"}},
        )
        self.assertTrue(any("source is required" in f for f in failures), failures)

    def test_remove_observed_rejects_a_non_path_element_field(self) -> None:
        failures = self._lint_projection(
            "or_set",
            {
                "kind": "or_set_remove_observed",
                "match": {
                    "element_field": "items[0].id",
                    "source": {"field": "payload.id"},
                },
            },
        )
        self.assertTrue(any("element_field" in f for f in failures), failures)

    # or_set_remove_dots (partial revoke)

    def test_remove_dots_takes_a_payload_dot_array(self) -> None:
        self.assertEqual(
            self._lint_projection(
                "or_set",
                {"kind": "or_set_remove_dots", "dots": {"field": "payload.observed_dots"}},
            ),
            [],
        )

    def test_remove_dots_requires_the_dots_source(self) -> None:
        errors = self._lint_projection("or_set", {"kind": "or_set_remove_dots"})
        self.assertTrue(any("dots is required" in error for error in errors), errors)

    def test_remove_dots_rejects_an_observed_style_match(self) -> None:
        # The two remove forms are closed and MUST NOT be blended: the removal
        # set is either the payload array or the frozen pre-state, never both.
        errors = self._lint_projection(
            "or_set",
            {
                "kind": "or_set_remove_dots",
                "dots": {"field": "payload.observed_dots"},
                "match": {"element_field": "peer", "source": {"field": "payload.peer"}},
            },
        )
        self.assertTrue(any("unknown member" in error for error in errors), errors)

    def test_remove_dots_is_not_defined_for_other_lattices(self) -> None:
        errors = self._lint_projection(
            "ordered_log",
            {"kind": "or_set_remove_dots", "dots": {"field": "payload.observed_dots"}},
        )
        self.assertTrue(any("must be one of" in error for error in errors), errors)

    def test_remove_observed_is_not_defined_for_other_lattices(self) -> None:
        failures = self._lint_projection(
            "mv_register", {"kind": "or_set_remove_observed"}
        )
        self.assertTrue(failures)


if __name__ == "__main__":
    unittest.main()
