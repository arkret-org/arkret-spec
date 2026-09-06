"""Mutation tests for the closed recovery-restricted family allowlist.

zh/authz/event-auth-state-resolution.md sections 9.3.1.4 and 9.5.1 item 2b make
the exit from Bottom layered by family: only families whose write authorization
or business precondition reads the cell itself have nobody left to authorize an
ordinary write, so only those may be recovered. The list is closed, lives in the
registry, and must not silently grow -- least of all to the notary cell, whose
recovery Seal could never be accepted because verifying any Seal reads it.
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
RECOVERY_KIND = core.CONFLICT_RECOVERY_KIND
EXPECTED_ALLOWLIST = [
    "ak.component.fork_resolution.v1",
    "ak.component.invite.live_target.v1",
    "ak.component.realm.authority_root.v1",
]


def _recovery_write(registry: dict) -> dict:
    row = next(row for row in registry["event_kinds"] if row["event_kind"] == RECOVERY_KIND)
    return row["cell_writes"][0]


class ShippedAllowlistTest(unittest.TestCase):
    def test_shipped_allowlist_is_the_closed_three(self) -> None:
        registry = core.parse_json_text(EVENT_REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(
            _recovery_write(registry)["target_cell_family_allowlist"], EXPECTED_ALLOWLIST
        )

    def test_every_allowlisted_family_is_a_written_causal_register(self) -> None:
        registry = core.parse_json_text(EVENT_REGISTRY.read_text(encoding="utf-8"))
        causal = {
            write["cell_family"]
            for row in registry["event_kinds"]
            for write in row.get("cell_writes") or []
            if write.get("lattice") in ("cas_register", "fsm") and write.get("cell_family")
        }
        for family in _recovery_write(registry)["target_cell_family_allowlist"]:
            self.assertIn(family, causal, family)

    def test_notary_cell_is_not_allowlisted(self) -> None:
        registry = core.parse_json_text(EVENT_REGISTRY.read_text(encoding="utf-8"))
        self.assertNotIn(
            core.NOTARY_CELL_FAMILY, _recovery_write(registry)["target_cell_family_allowlist"]
        )


class AllowlistLintTest(unittest.TestCase):
    def _lint_mutated_write(self, mutate) -> list[str]:
        registry = core.parse_json_text(EVENT_REGISTRY.read_text(encoding="utf-8"))
        write = copy.deepcopy(_recovery_write(registry))
        mutate(write)
        lint = core.Lint()
        foundation.lint_conflict_recovery_write(
            lint, EVENT_REGISTRY, f"{RECOVERY_KIND} cell_writes[0]", RECOVERY_KIND, write
        )
        return [str(failure) for failure in lint.errors]

    def test_unmutated_write_passes(self) -> None:
        self.assertEqual(self._lint_mutated_write(lambda write: None), [])

    def test_missing_allowlist_fails(self) -> None:
        failures = self._lint_mutated_write(
            lambda write: write.pop("target_cell_family_allowlist")
        )
        self.assertTrue(any("target_cell_family_allowlist" in f for f in failures), failures)

    def test_empty_allowlist_fails(self) -> None:
        failures = self._lint_mutated_write(
            lambda write: write.update(target_cell_family_allowlist=[])
        )
        self.assertTrue(any("non-empty" in f for f in failures), failures)

    def test_notary_family_is_rejected(self) -> None:
        def mutate(write: dict) -> None:
            write["target_cell_family_allowlist"] = sorted(
                [*EXPECTED_ALLOWLIST, core.NOTARY_CELL_FAMILY]
            )

        failures = self._lint_mutated_write(mutate)
        self.assertTrue(any(core.NOTARY_CELL_FAMILY in f for f in failures), failures)

    def test_unsorted_allowlist_fails(self) -> None:
        failures = self._lint_mutated_write(
            lambda write: write.update(target_cell_family_allowlist=list(reversed(EXPECTED_ALLOWLIST)))
        )
        self.assertTrue(any("sorted" in f for f in failures), failures)

    def test_duplicate_family_fails(self) -> None:
        failures = self._lint_mutated_write(
            lambda write: write.update(
                target_cell_family_allowlist=[EXPECTED_ALLOWLIST[0], *EXPECTED_ALLOWLIST]
            )
        )
        self.assertTrue(any("repeat" in f for f in failures), failures)

    def test_non_canonical_family_fails(self) -> None:
        failures = self._lint_mutated_write(
            lambda write: write.update(target_cell_family_allowlist=["realm.authority_root"])
        )
        self.assertTrue(any("canonical" in f for f in failures), failures)


if __name__ == "__main__":
    unittest.main()
