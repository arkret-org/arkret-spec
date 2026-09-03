"""Mutation tests for value-projection identity carrier metadata."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.core import Lint
from tools.artifact_lint.foundation import lint_value_projection


class ValueProjectionIdentityMetadataLintTest(unittest.TestCase):
    def _lint(self, member: dict[str, object]) -> list[str]:
        lint = Lint()
        lint_value_projection(
            lint,
            Path("registry/event-kind-registry.json"),
            "probe.value_projection",
            {"kind": "object", "members": [member]},
        )
        return list(lint.errors)

    def test_actor_projection_metadata_is_accepted(self) -> None:
        self.assertEqual(
            self._lint(
                {
                    "name": "controller_actor_id",
                    "envelope_field": "actor_id",
                    "terminal_category": "actor_id",
                    "subject_class": "actor",
                }
            ),
            [],
        )

    def test_identity_metadata_must_be_complete(self) -> None:
        failures = self._lint(
            {
                "name": "controller_actor_id",
                "envelope_field": "actor_id",
                "terminal_category": "actor_id",
            }
        )
        self.assertTrue(any("must be declared together" in item for item in failures), failures)

    def test_subject_class_must_match_terminal_category(self) -> None:
        failures = self._lint(
            {
                "name": "controller_actor_id",
                "envelope_field": "actor_id",
                "terminal_category": "account_id",
                "subject_class": "actor",
            }
        )
        self.assertTrue(any("for terminal_category='account_id'" in item for item in failures), failures)

    def test_metadata_types_fail_without_crashing(self) -> None:
        failures = self._lint(
            {
                "name": "controller_actor_id",
                "envelope_field": "actor_id",
                "terminal_category": ["actor_id"],
                "subject_class": "actor",
            }
        )
        self.assertTrue(any("terminal_category must be one of" in item for item in failures), failures)


if __name__ == "__main__":
    unittest.main()
