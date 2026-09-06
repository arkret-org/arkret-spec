"""Mutation tests for the apply_patch base-producer gate.

An apply_patch needs a base value, and event-auth-state-resolution.md section
9.3.1.2 rules out closing the gap with a registered initial_value: the base has to
come from a registered create or genesis write. A family whose only writer is the
patch itself has no defined pre-state, so the first patch quietly becomes the
object's definition. Four such families exist today and are frozen in a baseline
that only shrinks.
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
BASELINE = ROOT / "tools" / "patch-base-producer-baseline.json"
KNOWN = {
    "ak.component.circle.metadata.v1",
    "ak.component.strand.metadata.v1",
    "ak.component.strand.tracks.v1",
    "ak.component.view.update.v1",
}


def _row(registry: dict, kind: str) -> dict:
    return next(row for row in registry["event_kinds"] if row["event_kind"] == kind)


class ApplyPatchBaseProducerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = core.parse_json_text(EVENT_REGISTRY.read_text(encoding="utf-8"))

    def _lint(self, mutate=None) -> list[str]:
        registry = copy.deepcopy(self.registry)
        if mutate is not None:
            mutate(registry)
        lint = core.Lint()
        foundation.check_apply_patch_base_producers(lint, registry, EVENT_REGISTRY)
        return [str(error) for error in lint.errors]

    def test_shipped_registry_matches_the_baseline(self) -> None:
        self.assertEqual(self._lint(), [])

    def test_baseline_lists_exactly_the_known_four(self) -> None:
        baseline = core.parse_json_text(BASELINE.read_text(encoding="utf-8"))
        listed = {
            entry["cell_family"] for entry in baseline["families_without_base_producer"]
        }
        self.assertEqual(listed, KNOWN)

    def test_a_new_unproduced_family_fails(self) -> None:
        def mutate(registry: dict) -> None:
            write = _row(registry, "ak.space.update")["cell_writes"][0]
            write["cell_family"] = "ak.component.space.patch_only.v1"

        failures = self._lint(mutate)
        self.assertTrue(
            any("ak.component.space.patch_only.v1" in f for f in failures), failures
        )

    def test_a_family_that_gains_a_producer_must_leave_the_baseline(self) -> None:
        def mutate(registry: dict) -> None:
            _row(registry, "ak.strand.create")["cell_writes"][0]["cell_family"] = (
                "ak.component.strand.metadata.v1"
            )

        failures = self._lint(mutate)
        self.assertTrue(any("only shrinks" in f for f in failures), failures)

    def test_the_healthy_pairs_stay_healthy(self) -> None:
        producers: dict[str, set[str]] = {}
        patchers: dict[str, set[str]] = {}
        for row in self.registry["event_kinds"]:
            for write in row.get("cell_writes") or []:
                family = write.get("cell_family")
                kind = (write.get("effect_projection") or {}).get("kind")
                if not family:
                    continue
                if kind == "apply_patch":
                    patchers.setdefault(family, set()).add(row["event_kind"])
                elif kind in ("set", "append", "transition"):
                    producers.setdefault(family, set()).add(row["event_kind"])
        produced = {f for f in patchers if producers.get(f)}
        self.assertEqual(set(patchers) - produced, KNOWN)
        self.assertIn("ak.component.space.metadata.v1", produced)
        self.assertIn("ak.component.realm.authority_root.v1", produced)


if __name__ == "__main__":
    unittest.main()
