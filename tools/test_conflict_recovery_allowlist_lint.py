"""Mutation tests for the registered sole-recovery family list.

zh/authz/event-auth-state-resolution.md section 9.3.1.4 makes the exit from
Bottom layered by family: where the write's own authorization or business
precondition reads the cell itself, Bottom leaves nobody able to author an
ordinary write, so recovery is the only exit. The list names that group, lives in
the registry rather than in prose alone, and must keep the notary cell out --
verifying any Seal reads that cell, so listing it would imply an exit that does
not exist. The list never restricts which cells a recovery may target.
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
    "ak.component.mls.epoch.v1",
    "ak.component.realm.authority_root.v1",
]


def _recovery_write(registry: dict) -> dict:
    row = next(row for row in registry["event_kinds"] if row["event_kind"] == RECOVERY_KIND)
    return row["cell_writes"][0]


class ShippedAllowlistTest(unittest.TestCase):
    def test_shipped_list_is_the_registered_four(self) -> None:
        registry = core.parse_json_text(EVENT_REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(
            _recovery_write(registry)["sole_recovery_families"], EXPECTED_ALLOWLIST
        )

    def test_every_allowlisted_family_is_a_written_causal_register(self) -> None:
        registry = core.parse_json_text(EVENT_REGISTRY.read_text(encoding="utf-8"))
        causal = {
            write["cell_family"]
            for row in registry["event_kinds"]
            for write in row.get("cell_writes") or []
            if write.get("lattice") in ("cas_register", "fsm") and write.get("cell_family")
        }
        for family in _recovery_write(registry)["sole_recovery_families"]:
            self.assertIn(family, causal, family)

    def test_notary_cell_is_not_allowlisted(self) -> None:
        registry = core.parse_json_text(EVENT_REGISTRY.read_text(encoding="utf-8"))
        self.assertNotIn(
            core.NOTARY_CELL_FAMILY, _recovery_write(registry)["sole_recovery_families"]
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
            lambda write: write.pop("sole_recovery_families")
        )
        self.assertTrue(any("sole_recovery_families" in f for f in failures), failures)

    def test_empty_allowlist_fails(self) -> None:
        failures = self._lint_mutated_write(
            lambda write: write.update(sole_recovery_families=[])
        )
        self.assertTrue(any("non-empty" in f for f in failures), failures)

    def test_notary_family_is_rejected(self) -> None:
        def mutate(write: dict) -> None:
            write["sole_recovery_families"] = sorted(
                [*EXPECTED_ALLOWLIST, core.NOTARY_CELL_FAMILY]
            )

        failures = self._lint_mutated_write(mutate)
        self.assertTrue(any(core.NOTARY_CELL_FAMILY in f for f in failures), failures)

    def test_unsorted_allowlist_fails(self) -> None:
        failures = self._lint_mutated_write(
            lambda write: write.update(sole_recovery_families=list(reversed(EXPECTED_ALLOWLIST)))
        )
        self.assertTrue(any("sorted" in f for f in failures), failures)

    def test_duplicate_family_fails(self) -> None:
        failures = self._lint_mutated_write(
            lambda write: write.update(
                sole_recovery_families=[EXPECTED_ALLOWLIST[0], *EXPECTED_ALLOWLIST]
            )
        )
        self.assertTrue(any("repeat" in f for f in failures), failures)

    def test_non_canonical_family_fails(self) -> None:
        failures = self._lint_mutated_write(
            lambda write: write.update(sole_recovery_families=["realm.authority_root"])
        )
        self.assertTrue(any("canonical" in f for f in failures), failures)


if __name__ == "__main__":
    unittest.main()
