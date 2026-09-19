r"""Mutation tests for the ak:did_core projection-shape gate.

A `did:webvh` DID carries the SCID and the host-and-path in adjacent segments, and
`ak:did_core:webvh:<core>` is a projection of the first one only. Projecting the
second produces a value that satisfies the typed-ID payload pattern
(`[a-z0-9]+:[^\s/?#]+`), satisfies every schema that accepts a did_core, and still
names something no adapter can resolve. Four such values sat in two fixtures, one of
them inside an `expect_valid: true` case.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as lint_fixtures


class DidCoreProjectionShapeLintTest(unittest.TestCase):
    def _lint_text(self, text: str) -> list[str]:
        lint = lint_fixtures.Lint()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-fixture.json"
            path.write_text(text, encoding="utf-8", newline="\n")
            with (
                patch.object(lint_fixtures, "raw_artifact_files", return_value=[path]),
                patch.object(lint_fixtures, "markdown_files", return_value=[]),
            ):
                lint_fixtures.check_did_core_projection_shape(lint)
        return lint.errors

    def test_the_committed_corpus_projects_every_did_core_correctly(self) -> None:
        lint = lint_fixtures.Lint()
        lint_fixtures.check_did_core_projection_shape(lint)
        self.assertEqual(lint.errors, [])

    def test_a_host_projected_as_the_webvh_core_fails(self) -> None:
        # The shape that was committed: `push.example` is the host-and-path segment.
        errors = self._lint_text('{"destination_gateway_id": "ak:did_core:webvh:push.example"}')
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("projects a host-and-path", errors[0])

    def test_a_scid_and_host_pair_projected_as_the_core_fails(self) -> None:
        errors = self._lint_text(
            '{"principal_id": "ak:did_core:webvh:z6mkfixtureprincipal:example.test"}'
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("projects a host-and-path", errors[0])

    def test_a_validated_scid_passes(self) -> None:
        self.assertEqual(
            self._lint_text('{"principal_id": "ak:did_core:webvh:z6mkfixturealice"}'), []
        )

    def test_a_dotted_core_is_fine_for_a_method_that_projects_the_method_specific_id(self) -> None:
        # did:web's core IS the host-and-path, so the webvh rule must not reach it.
        self.assertEqual(self._lint_text('{"issuer_id": "ak:did_core:web:acme.example"}'), [])

    def test_an_unregistered_method_fails(self) -> None:
        errors = self._lint_text('{"issuer_id": "ak:did_core:plc:abcdef"}')
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("no registered DID method", errors[0])

    def test_a_documented_placeholder_is_not_a_value(self) -> None:
        self.assertEqual(self._lint_text("ak:did_core:webvh:<validated-scid>"), [])

    def test_the_rule_table_comes_from_the_adapter_registry(self) -> None:
        rules = lint_fixtures._did_core_core_shape_rules(lint_fixtures.Lint())
        self.assertEqual(rules["webvh"], "<validated-scid>")
        self.assertEqual(rules["web"], "<canonical-method-specific-id>")
        self.assertEqual(rules["key"], "<canonical-multibase-method-specific-id>")


if __name__ == "__main__":
    unittest.main()
