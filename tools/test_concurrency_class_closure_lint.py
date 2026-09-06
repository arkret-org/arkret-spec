"""Mutation tests for the concurrency_class closure gate (cba-profiles.md section 2).

concurrency_class stops being an editing convention once a rule relaxes
serialization by reading it. Two things then have to hold mechanically: every
sealed control kind declares one, and no cell family carries both a barrier and a
non-barrier promise, since those say opposite things about the same cell. The one
exemption is an object genesis whose subject comes from the Event's own id, which
can only ever mint a fresh cell.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import core, foundation

EVENT_REGISTRY = ROOT / "spec" / "v1" / "artifacts" / "registry" / "event-kind-registry.json"


def _row(registry: dict, kind: str) -> dict:
    return next(row for row in registry["event_kinds"] if row["event_kind"] == kind)


class ConcurrencyClassClosureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = core.parse_json_text(EVENT_REGISTRY.read_text(encoding="utf-8"))

    def _lint(self, mutate=None) -> list[str]:
        registry = copy.deepcopy(self.registry)
        if mutate is not None:
            mutate(registry)
        lint = core.Lint()
        foundation.check_concurrency_class_closure(lint, registry, EVENT_REGISTRY)
        return [str(error) for error in lint.errors]

    def test_shipped_registry_passes(self) -> None:
        self.assertEqual(self._lint(), [])

    def test_missing_concurrency_class_fails(self) -> None:
        def mutate(registry: dict) -> None:
            _row(registry, "ak.realm.notary").pop("concurrency_class")

        failures = self._lint(mutate)
        self.assertTrue(any("without a concurrency_class" in f for f in failures), failures)

    def test_barrier_and_non_barrier_on_one_family_fails(self) -> None:
        def mutate(registry: dict) -> None:
            _row(registry, "ak.realm.profile")["concurrency_class"] = "exclusive"
            _row(registry, "ak.realm.alias")["cell_writes"][0]["cell_family"] = (
                "ak.component.realm.profile.v1"
            )

        failures = self._lint(mutate)
        self.assertTrue(
            any("opposite serialization promises" in f for f in failures), failures
        )

    def test_moderation_writes_are_barriers_because_authorization_reads_them(self) -> None:
        """cba-profiles.md section 2: authorization reads it, so it is a barrier.

        capabilities.md 18.1 lets a grant subject be a condition selector over
        moderation state, so a merge_safe classification would let a moderation
        decision share a frozen predecessor with a write its own outcome governs.
        """
        for kind in ("ak.moderation.decision", "ak.moderation.decision.lift"):
            row = _row(self.registry, kind)
            self.assertEqual(row["concurrency_class"], "security_barrier", kind)
            self.assertEqual(
                [write["cell_family"] for write in row["cell_writes"]],
                ["ak.component.moderation_state.v1"],
                kind,
            )

    def test_object_genesis_barrier_is_exempt(self) -> None:
        """ak.call.create is a barrier genesis keyed by its own event id."""
        families = {
            write.get("cell_family")
            for write in _row(self.registry, "ak.call.create")["cell_writes"]
        }
        self.assertIn("ak.component.call.state.v1", families)
        self.assertEqual(
            _row(self.registry, "ak.call.create")["concurrency_class"], "security_barrier"
        )
        self.assertEqual(_row(self.registry, "ak.call.state")["concurrency_class"], "exclusive")
        self.assertEqual(self._lint(), [])

    def test_genesis_exemption_is_lost_when_the_subject_stops_being_the_event_id(self) -> None:
        def mutate(registry: dict) -> None:
            for write in _row(registry, "ak.call.create")["cell_writes"]:
                if write.get("cell_family") == "ak.component.call.state.v1":
                    write["cell_subject"] = {"kind": "typed_id", "field": "payload.call_id"}

        failures = self._lint(mutate)
        self.assertTrue(
            any("ak.component.call.state.v1" in f for f in failures), failures
        )


if __name__ == "__main__":
    unittest.main()
