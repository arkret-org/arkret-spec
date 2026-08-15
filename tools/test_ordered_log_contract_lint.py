"""Mutation tests for the ordered-log sparse actor-sequence contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import foundation as lint_artifacts


class OrderedLogContractLintTest(unittest.TestCase):
    def _lint(self, issuer_seq: object) -> list[str]:
        lint = lint_artifacts.Lint()
        lint_artifacts.lint_effect_projection(
            lint,
            Path("registry/contract-registry.json"),
            "probe",
            {
                "kind": "append",
                "value": {"field": "payload"},
                "issuer_seq": issuer_seq,
            },
            "ordered_log",
        )
        return list(lint.errors)

    def test_actor_seq_projection_is_accepted(self) -> None:
        self.assertEqual(self._lint({"envelope_field": "actor_seq"}), [])

    def test_cell_local_constant_is_rejected(self) -> None:
        failures = self._lint({"const": 0})
        self.assertTrue(any("sparse" in item for item in failures), failures)

    def test_payload_counter_is_rejected(self) -> None:
        failures = self._lint({"field": "payload.issuer_seq"})
        self.assertTrue(any("actor_seq" in item for item in failures), failures)


if __name__ == "__main__":
    unittest.main()
