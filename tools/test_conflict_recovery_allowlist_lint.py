"""No Event kind may reset or retarget an arbitrary typed current result.

`ak.conflict.recovery` was the escape hatch: a kind that named its target in the
payload (`cell_ref`) and wrote a `reset` projection over whatever it pointed at.
It is retired, and the registry must never register it again.

The rule used to be enforced by `foundation.lint_conflict_recovery_write`, a
function whose only production caller was the `cell_writes[]` loop of
`check_registries` -- dead since the authority-commit clean break, so for the
whole break the only thing keeping that function alive was this test calling it
directly. A gate with no caller proves nothing about the registry.

In v1 the proposition is carried by the closed sets of
`check_result_write_contracts`: `cell_ref` is not a member of `result_writes[]`,
and `reset` is not a `result_projection.kind`. These tests drive the live gate so
that both closures stay the thing that actually rejects the shape.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import core, proof_context_schemas as gate

REGISTRY = gate.EVENT_KIND_REGISTRY


class RetiredRecoveryKindTest(unittest.TestCase):
    def test_the_retired_kind_has_no_registration(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertNotIn(
            core.CONFLICT_RECOVERY_KIND,
            {row["event_kind"] for row in registry["event_kinds"]},
        )


class DynamicResetRejectionTest(unittest.TestCase):
    def _run(self, mutate=None) -> list[str]:
        original_load_json = gate.load_json
        documents = {}
        if mutate is not None:
            document = copy.deepcopy(original_load_json(core.Lint(), REGISTRY))
            mutate(document)
            documents[REGISTRY.resolve()] = document

        def load_json_with_mutation(lint, path):
            return documents.get(path.resolve(), original_load_json(lint, path))

        gate.load_json = load_json_with_mutation
        try:
            lint = core.Lint()
            gate.check_result_write_contracts(lint)
            return lint.errors
        finally:
            gate.load_json = original_load_json

    def _newly_reported(self, mutate) -> list[str]:
        baseline = set(self._run())
        return sorted(set(self._run(mutate)) - baseline)

    @staticmethod
    def _first_write(registry: dict) -> dict:
        """Any registered write will do, except the one row whose whole shape is
        pinned byte for byte (`ak.agent.key.authorize` write 0): mutating that
        one reports the pin as well and stops these tests from saying which
        closure did the rejecting."""
        for row in registry["event_kinds"]:
            if row["event_kind"] == "ak.agent.key.authorize":
                continue
            for write in row.get("result_writes") or ():
                return write
        raise AssertionError("no result_writes[] row in the registry")

    def test_the_live_registry_is_clean(self) -> None:
        self.assertEqual(self._run(), [])

    def test_a_payload_named_target_is_rejected(self) -> None:
        """`cell_ref` was how the recovery kind picked its target at runtime.
        The closed member set is what rejects it now."""

        def mutate(registry: dict) -> None:
            self._first_write(registry)["cell_ref"] = {
                "field": "payload.target_cell_id"
            }

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("has unknown member(s) ['cell_ref']", reported[0])

    def test_a_reset_projection_is_rejected(self) -> None:
        """The other half: even with a registered target, `reset` is not a
        projection any Event kind may declare."""

        def mutate(registry: dict) -> None:
            self._first_write(registry)["result_projection"] = {"kind": "reset"}

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("result_projection.kind must be one of", reported[0])


if __name__ == "__main__":
    unittest.main()
