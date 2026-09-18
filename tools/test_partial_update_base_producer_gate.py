"""A partial update must land on a value some registered write created.

Two gates are covered here, both recovered from the authority-commit clean
break's dead list.

`check_partial_update_base_producers` was `check_apply_patch_base_producers`.
It read `cell_writes[].cell_family` / `effect_projection`, all renamed, and it
was called only from inside `if any("cell_writes" in row ...)`, a condition no
row has satisfied since the break -- so it did not merely read nothing, it was
never entered. `models/views.md` section 3.2 still argues the rule in full: an
update that lands on a typed current result nobody wrote has no pre-state, the
current-value contract forbids a registered `initial_value`, and `null` MUST NOT
be read as implicit initialization. `apply_patch` is not in the v1 projection
closed set, but `merge` is, and the same sentence covers it verbatim.

`check_result_family_write_agreement` is what survives of
`check_concurrency_class_closure`, which compared `execution` / `state_model` /
`value_shape` across the writers of one family. The break removed all three
members, so it compared three absent values on an absent array. Its one live
rule -- the retired-`concurrency_class` row guard -- moved to the removed-field
guards in `check_registries`; its proposition, that a family's writers agree on
one contract, is spelled in v1 as one `value_schema_ref` per family.

Every mutation reads as a delta against the live baseline.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate

EVENT_KIND_REGISTRY = gate.EVENT_KIND_REGISTRY
BASELINE = gate.PATCH_BASE_PRODUCER_BASELINE


def row_of(registry: dict, kind: str) -> dict:
    for row in registry["event_kinds"]:
        if row["event_kind"] == kind:
            return row
    raise AssertionError(f"{kind} is not a registered Event kind")


def write_of(registry: dict, kind: str, family: str) -> dict:
    for write in row_of(registry, kind).get("result_writes") or ():
        if write["result_family"] == family:
            return write
    raise AssertionError(f"{kind} declares no write of {family}")


class _GateHarness(unittest.TestCase):
    check = None

    def _run(self, mutate=None, mutate_baseline=None) -> list[str]:
        original_load_json = gate.load_json
        documents = {}
        if mutate is not None:
            document = copy.deepcopy(
                original_load_json(gate.Lint(), EVENT_KIND_REGISTRY)
            )
            mutate(document)
            documents[EVENT_KIND_REGISTRY.resolve()] = document
        if mutate_baseline is not None:
            baseline = copy.deepcopy(original_load_json(gate.Lint(), BASELINE))
            mutate_baseline(baseline)
            documents[BASELINE.resolve()] = baseline

        def load_json_with_mutation(lint, path):
            return documents.get(path.resolve(), original_load_json(lint, path))

        gate.load_json = load_json_with_mutation
        try:
            lint = gate.Lint()
            type(self).check(lint)
            return lint.errors
        finally:
            gate.load_json = original_load_json

    def _newly_reported(self, mutate=None, mutate_baseline=None) -> list[str]:
        baseline = set(self._run())
        return sorted(set(self._run(mutate, mutate_baseline)) - baseline)


class PartialUpdateBaseProducerTest(_GateHarness):
    check = staticmethod(gate.check_partial_update_base_producers)

    # ---- the live baseline ----------------------------------------------

    def test_the_live_registry_is_clean(self) -> None:
        self.assertEqual(self._run(), [])

    def test_the_baseline_ledger_is_empty(self) -> None:
        """`decisions/0029` emptied it on the day it was opened, and the file
        says it only shrinks. A non-empty ledger here is a live defect that
        someone chose to record rather than fix."""
        baseline = gate.load_json(gate.Lint(), BASELINE)
        self.assertEqual(baseline["families_without_base_producer"], [])

    def test_every_partial_update_family_has_a_whole_value_producer(self) -> None:
        registry = gate.load_json(gate.Lint(), EVENT_KIND_REGISTRY)
        updated: set[str] = set()
        produced: set[str] = set()
        for row in registry["event_kinds"]:
            for write in row.get("result_writes") or ():
                family = write["result_family"]
                if write["result_projection"]["kind"] in gate._PARTIAL_UPDATE_PROJECTIONS:
                    updated.add(family)
                elif gate._is_base_producer(write["result_projection"]):
                    produced.add(family)
        self.assertEqual(
            updated,
            {"capability_grant", "consent", "mls_group", "realm_authority_root"},
        )
        self.assertLessEqual(updated, produced)

    def test_a_keyed_set_family_is_not_asked_for_a_base(self) -> None:
        """`agent_key` has no `set` writer and needs none: a keyed set begins
        empty and `keyed_set_add` is its genesis. A gate that demanded a base
        here would be demanding one the family's own contract denies. The revoke
        ruling added `keyed_set_remove_observed` beside the authorize pair; it is
        a removal too, so it changes nothing about the base question."""
        registry = gate.load_json(gate.Lint(), EVENT_KIND_REGISTRY)
        projections = {
            write["result_projection"]["kind"]
            for row in registry["event_kinds"]
            for write in row.get("result_writes") or ()
            if write["result_family"] == "agent_key"
        }
        self.assertEqual(
            projections,
            {"keyed_set_add", "keyed_set_remove_dots", "keyed_set_remove_observed"},
        )
        self.assertEqual(self._run(), [])

    def test_only_set_and_the_genesis_edge_count_as_producers(self) -> None:
        self.assertTrue(gate._is_base_producer({"kind": "set", "value": {"field": "payload"}}))
        self.assertTrue(
            gate._is_base_producer(
                {"kind": "transition", "from": {"const": None}, "to": {"const": "recording"}}
            )
        )
        self.assertFalse(
            gate._is_base_producer(
                {"kind": "transition", "from": {"const": "active"}, "to": {"const": "paused"}}
            )
        )
        self.assertFalse(
            gate._is_base_producer(
                {"kind": "transition", "from": {"field": "payload.from"}, "to": {"const": "x"}}
            )
        )
        self.assertFalse(gate._is_base_producer({"kind": "keyed_set_add"}))

    # ---- the gate cannot be silenced by renaming its input ---------------

    def test_an_empty_sweep_is_a_failure_not_a_pass(self) -> None:
        def mutate(registry: dict) -> None:
            for row in registry["event_kinds"]:
                if "result_writes" in row:
                    row["cell_writes"] = row.pop("result_writes")

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("inspected no result_writes[] entry", reported[0])

    # ---- the rules ------------------------------------------------------

    def test_a_partial_update_with_no_producer_at_all_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            row = row_of(registry, "ak.mls.genesis")
            row["result_writes"] = [
                write
                for write in row["result_writes"]
                if write["result_family"] != "mls_group"
            ]

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("no registered write produces a base value for it", reported[0])

    def test_a_producer_that_writes_no_whole_value_does_not_count(self) -> None:
        """An `ak.mls.genesis` that only added to a keyed set would leave the
        commit's `merge` with nothing to merge into."""

        def mutate(registry: dict) -> None:
            write = write_of(registry, "ak.mls.genesis", "mls_group")
            write["result_projection"] = {"kind": "keyed_set_add", "tag": {"dot": True}}

        reported = self._newly_reported(mutate)
        # The missing base, and the fact that what is left writes no whole value.
        self.assertEqual(len(reported), 2, reported)
        self.assertTrue(
            any("none of them writes a whole value" in error for error in reported),
            reported,
        )

    def test_a_producer_on_a_different_selector_shape_is_reported(self) -> None:
        """A base written to a different object is not this update's base."""

        def mutate(registry: dict) -> None:
            write = write_of(registry, "ak.mls.genesis", "mls_group")
            write["result_selector"] = {"kind": "id:realm", "field": "payload.realm_id"}

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn(
            "a base value has to be written to the same object the update addresses",
            reported[0],
        )

    # ---- the ledger only shrinks ----------------------------------------

    def test_a_recorded_gap_is_not_reported_twice(self) -> None:
        def mutate(registry: dict) -> None:
            row = row_of(registry, "ak.mls.genesis")
            row["result_writes"] = [
                write
                for write in row["result_writes"]
                if write["result_family"] != "mls_group"
            ]

        def mutate_baseline(baseline: dict) -> None:
            baseline["families_without_base_producer"] = [
                {"result_family": "mls_group", "note": "test fixture"}
            ]

        self.assertEqual(self._newly_reported(mutate, mutate_baseline), [])

    def test_a_ledger_entry_that_no_longer_applies_is_reported(self) -> None:
        """The ledger is a record of live defects, not a list of names nobody
        prunes; an entry that has been fixed has to leave."""

        def mutate_baseline(baseline: dict) -> None:
            baseline["families_without_base_producer"] = [
                {"result_family": "mls_group", "note": "test fixture"}
            ]

        reported = self._newly_reported(None, mutate_baseline)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("now has a registered base-value producer", reported[0])

    def test_a_ledger_entry_for_a_family_nobody_updates_is_reported(self) -> None:
        def mutate_baseline(baseline: dict) -> None:
            baseline["families_without_base_producer"] = [
                {"result_family": "call_roster", "note": "test fixture"}
            ]

        reported = self._newly_reported(None, mutate_baseline)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("is no longer the target of any partial update write", reported[0])


class ResultFamilyWriteAgreementTest(_GateHarness):
    check = staticmethod(gate.check_result_family_write_agreement)

    def test_the_live_registry_is_clean(self) -> None:
        self.assertEqual(self._run(), [])

    def test_a_row_may_omit_the_value_schema_ref(self) -> None:
        """`realm_history_access` is written by four rows and only one names a
        `value_schema_ref`: the other three are genesis transitions, which write
        no projection members and so have nothing to declare. Agreement is
        checked among the rows that declare one, not presence."""
        registry = gate.load_json(gate.Lint(), EVENT_KIND_REGISTRY)
        refs = [
            write.get("value_schema_ref")
            for row in registry["event_kinds"]
            for write in row.get("result_writes") or ()
            if write["result_family"] == "realm_history_access"
        ]
        self.assertGreater(len(refs), 1)
        self.assertIn(None, refs)
        self.assertEqual(self._run(), [])

    def test_two_writers_naming_different_value_schemas_are_reported(self) -> None:
        def mutate(registry: dict) -> None:
            write = write_of(registry, "ak.capability.revoke", "capability_grant")
            write["value_schema_ref"] = (
                "schemas/typed-current-result.schema.json#/$defs/mls_group_value"
            )

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("do not agree on what the family's value is", reported[0])
        # Both spellings and their writers are named, so the reader can tell
        # which row moved without opening the registry.
        self.assertIn("ak.capability.revoke", reported[0])
        self.assertIn("ak.capability.grant", reported[0])


class RetiredRowFieldGuardTest(unittest.TestCase):
    """The one live rule `check_concurrency_class_closure` had.

    It sat at the top of that function, ahead of the dead write loop, so
    deleting the function without moving it would have quietly dropped the only
    thing it still did. It now lives with the other removed-field guards in
    `check_registries`, and this test is what says so.
    """

    def _run(self, mutate=None) -> list[str]:
        from tools.artifact_lint import foundation

        original_load_json = foundation.load_json
        path = foundation.ARTIFACTS / "registry" / "event-kind-registry.json"
        documents = {}
        if mutate is not None:
            document = copy.deepcopy(original_load_json(foundation.Lint(), path))
            mutate(document)
            documents[path.resolve()] = document

        def load_json_with_mutation(lint, target):
            return documents.get(target.resolve(), original_load_json(lint, target))

        foundation.load_json = load_json_with_mutation
        try:
            lint = foundation.Lint()
            foundation.check_registries(lint)
            return lint.errors
        finally:
            foundation.load_json = original_load_json

    def test_a_row_carrying_concurrency_class_is_reported(self) -> None:
        baseline = set(self._run())

        def mutate(registry: dict) -> None:
            registry["event_kinds"][0]["concurrency_class"] = "security"

        reported = sorted(set(self._run(mutate)) - baseline)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("carries removed typed-state fields", reported[0])
        self.assertIn("concurrency_class", reported[0])


if __name__ == "__main__":
    unittest.main()
