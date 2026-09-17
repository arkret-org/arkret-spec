"""A reducer-managed path's owner must name a write authority that exists.

`reducer-managed-path-registry.json` bans a patch path because some other
authority owns the write. `_check_owner` validates that authority: an
`event_kind` owner must be an active Event kind, and a `result_family` owner must
be a family `current-result-registry.json` registers.

The second half had never run. `_declared_cell_families` walked
`event_kinds[].cell_writes[].cell_family`, a pair the authority-commit clean
break renamed to `result_writes[].result_family`, so it returned the empty set on
every run -- and the guard read `and cell_families and owner not in
cell_families`, which short-circuits on an empty set. Three of the four live
`result_family` owners turned out not to exist:

* `space_metadata` is nowhere in `spec/v1/zh/`; the `scope_circle_id` row it
  owned is `create_locked` and its real owner is `ak.space.create`, matching
  every other `create_locked` row in the file;
* `space_parent` and `space_child_scope_policy` are real, prose-backed, and
  unregistered, because the whole Space domain is still part of the uncovered
  `reducer_input` set. They sit in a shrinking ledger with their citations.

Every mutation reads as a delta against the live baseline, so each test keeps
testing its own proposition as the registries grow.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import redactable_fields as gate

REGISTRY = gate.REDUCER_MANAGED_REGISTRY_PATH
FAMILIES = gate.CURRENT_RESULT_REGISTRY_PATH
BASELINE = gate.REDUCER_MANAGED_OWNER_BASELINE

BASELINED_OWNERS = ("space_child_scope_policy", "space_parent")


def object_of(registry: dict, kind: str) -> dict:
    for row in registry["objects"]:
        if row["object_kind"] == kind:
            return row
    raise AssertionError(f"{kind} is not a classified object kind")


def path_row(registry: dict, kind: str, path: str) -> dict:
    for row in object_of(registry, kind)["forbidden_patch_paths"]:
        if row["path"] == path:
            return row
    raise AssertionError(f"{kind} does not forbid {path}")


class ReducerManagedOwnerGateTest(unittest.TestCase):
    def _run(self, mutations: dict | None = None) -> list[str]:
        original_load_json = gate.load_json
        documents = {}
        for path, mutate in (mutations or {}).items():
            document = copy.deepcopy(original_load_json(gate.Lint(), path))
            mutate(document)
            documents[path.resolve()] = document

        def load_json_with_mutation(lint, path):
            return documents.get(path.resolve(), original_load_json(lint, path))

        gate.load_json = load_json_with_mutation
        try:
            lint = gate.Lint()
            gate.check_reducer_managed_path_registry(lint)
            return lint.errors
        finally:
            gate.load_json = original_load_json

    def _newly_reported(self, mutations: dict) -> list[str]:
        baseline = set(self._run())
        return sorted(set(self._run(mutations)) - baseline)

    # ---- the live baseline ----------------------------------------------

    def test_the_live_registries_are_clean(self) -> None:
        """Absolute on purpose: a gate whose baseline is not zero cannot say
        whether the next edit broke something."""
        self.assertEqual(self._run(), [])

    def test_the_scope_circle_id_row_is_owned_by_its_create(self) -> None:
        """The defect the repair caught. `space_metadata` appears in no spec
        file; `realm-and-space.md` section 3.2 carries `scope_circle_id` in the
        signed create object and no later Event kind writes it."""
        registry = gate.load_json(gate.Lint(), REGISTRY)
        row = path_row(registry, "space", "scope_circle_id")
        self.assertEqual(row["basis"], "create_locked")
        self.assertEqual(row["owner_kind"], "event_kind")
        self.assertEqual(row["owner"], "ak.space.create")

    def test_every_baselined_owner_is_still_cited_and_still_unregistered(self) -> None:
        """Pins what the ledger claims against both registries, so a resolution
        that forgets the ledger is caught by the ledger's own test too."""
        registry = gate.load_json(gate.Lint(), REGISTRY)
        families = gate._registered_result_families(gate.Lint())
        baselined = gate._baselined_unregistered_owners(gate.Lint())
        self.assertEqual(tuple(sorted(baselined)), BASELINED_OWNERS)
        for owner, row in baselined.items():
            cited = path_row(registry, row["object_kind"], row["path"])
            self.assertEqual(cited["owner_kind"], "result_family")
            self.assertEqual(cited["owner"], owner)
            self.assertNotIn(owner, families)

    # ---- the gate cannot be silenced by an empty family set --------------

    def test_an_empty_family_registry_is_a_failure_not_a_pass(self) -> None:
        """Exactly what the clean break did: the families were still there,
        under a name this reader no longer walked, and an empty set read as
        'every owner is fine'."""

        def mutate(families: dict) -> None:
            families["result_kinds"] = []

        reported = self._newly_reported({FAMILIES: mutate})
        self.assertTrue(
            any("its silence would mean nothing" in error for error in reported),
            reported,
        )

    def test_the_historical_defect_is_reported_if_it_returns(self) -> None:
        def mutate(registry: dict) -> None:
            row = path_row(registry, "space", "scope_circle_id")
            row["owner_kind"] = "result_family"
            row["owner"] = "space_metadata"

        reported = self._newly_reported({REGISTRY: mutate})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn(
            "current-result-registry.json does not register: 'space_metadata'",
            reported[0],
        )

    # ---- the ledger is an exemption, and it only shrinks ------------------

    def test_an_owner_outside_the_ledger_is_reported(self) -> None:
        """The exemption is per-owner and written down. Drop `space_parent` from
        the ledger and the registry row it covers fails immediately."""

        def mutate(baseline: dict) -> None:
            baseline["owners_without_registered_family"] = [
                row
                for row in baseline["owners_without_registered_family"]
                if row["owner"] != "space_parent"
            ]

        reported = self._newly_reported({BASELINE: mutate})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn(
            "current-result-registry.json does not register: 'space_parent'",
            reported[0],
        )

    def test_a_resolved_owner_must_leave_the_ledger(self) -> None:
        """Registering the family is the whole point of the ledger entry, so it
        must not be possible to register it and keep the exemption."""

        def mutate(families: dict) -> None:
            families["result_kinds"].append(
                {
                    "result_kind": "space_parent",
                    "schema_ref": "schemas/space.schema.json",
                }
            )

        reported = self._newly_reported({FAMILIES: mutate})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("space_parent is now registered", reported[0])

    def test_an_uncited_owner_must_leave_the_ledger(self) -> None:
        """The other way an entry becomes stale: the registry stops citing the
        family at all, and an exemption for nothing is a false record of a
        known gap."""

        def mutate(registry: dict) -> None:
            row = path_row(registry, "space", "parent_space_id")
            row["basis"] = "create_locked"
            row["owner_kind"] = "event_kind"
            row["owner"] = "ak.space.create"

        reported = self._newly_reported({REGISTRY: mutate})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("space_parent is no longer cited", reported[0])

    # ---- the half of the guard that was already live ---------------------

    def test_an_unknown_event_kind_owner_is_still_reported(self) -> None:
        """`_check_owner`'s other branch never died. It is pinned here so the
        repair to its neighbour cannot quietly take it along."""

        def mutate(registry: dict) -> None:
            path_row(registry, "space", "scope_circle_id")["owner"] = "ak.space.invent"

        reported = self._newly_reported({REGISTRY: mutate})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("unknown or inactive event kind: 'ak.space.invent'", reported[0])


if __name__ == "__main__":
    unittest.main()
