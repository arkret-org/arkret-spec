"""Two writes of one Event must not land on the same typed current result.

`check_registries` used to carry this rule, plus the same-row agreement between
an `any_field_present` condition and a `coalesce` subject. Both walked
`cell_writes[]`, and the authority-commit clean break renamed the array to
`result_writes[]`, so both went down with the rest of that loop: every row took
the `continue` above it and nothing past that point ever ran again.

`check_result_write_contracts` closed the per-write grammar during the break but
says nothing about two writes agreeing on a target, so the propositions had no
subject at all until they were ported here. They are the same two rules, with the
same two exceptions, restated in v1 vocabulary:

* a keyed set's atomic remove-then-add (`zh/identity/key-management.md` section
  3.6.1, live on `ak.agent.key.authorize`);
* a provably disjoint condition pair (`foundation.complementary_conditions`,
  whose only caller was the dead loop).

Every mutation reads as a delta against the live baseline, so each test keeps
testing its own proposition as coverage grows.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate

REGISTRY = gate.EVENT_KIND_REGISTRY


def row_of(registry: dict, kind: str) -> dict:
    for row in registry["event_kinds"]:
        if row["event_kind"] == kind:
            return row
    raise AssertionError(f"{kind} is not a registered Event kind")


def any_covered_row(registry: dict, *, exclude: str = "") -> dict:
    """A covered Event kind whose writes already address distinct targets.

    A row that legitimately repeats a target -- the atomic remove-then-add both
    Agent key kinds register -- proves nothing when a test duplicates one of its
    writes, because the gate is meant to allow that shape. Naming those kinds
    one by one went stale the moment a second one landed, so the filter reads
    the property itself.
    """
    for row in registry["event_kinds"]:
        writes = row.get("result_writes")
        if row["event_kind"] == exclude or not writes:
            continue
        targets = [
            json.dumps(
                [write.get("result_family"), write.get("result_selector")],
                sort_keys=True,
            )
            for write in writes
        ]
        if len(set(targets)) == len(targets):
            return row
    raise AssertionError("no covered Event kind with distinct write targets")


class ResultWriteTargetUniquenessTest(unittest.TestCase):
    def _run(self, mutate=None) -> list[str]:
        original_load_json = gate.load_json
        documents = {}
        if mutate is not None:
            document = copy.deepcopy(original_load_json(gate.Lint(), REGISTRY))
            mutate(document)
            documents[REGISTRY.resolve()] = document

        def load_json_with_mutation(lint, path):
            return documents.get(path.resolve(), original_load_json(lint, path))

        gate.load_json = load_json_with_mutation
        try:
            lint = gate.Lint()
            gate.check_result_write_target_uniqueness(lint)
            return lint.errors
        finally:
            gate.load_json = original_load_json

    def _newly_reported(self, mutate) -> list[str]:
        baseline = set(self._run())
        return sorted(set(self._run(mutate)) - baseline)

    # ---- the live baseline ----------------------------------------------

    def test_the_live_registry_is_clean(self) -> None:
        """Absolute on purpose: a gate whose baseline is not zero cannot say
        whether the next edit broke something."""
        self.assertEqual(self._run(), [])

    def test_an_empty_sweep_is_a_failure_not_a_pass(self) -> None:
        """Exactly what the clean break did to the rule's ancestor: the writes
        were still there, under a name it no longer read."""

        def mutate(registry: dict) -> None:
            for row in registry["event_kinds"]:
                if "result_writes" in row:
                    row["cell_writes"] = row.pop("result_writes")

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("inspected no result_writes[] entry", reported[0])

    # ---- the duplicate-target rule ---------------------------------------

    def test_a_repeated_target_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            row = any_covered_row(registry)
            row["result_writes"].append(copy.deepcopy(row["result_writes"][0]))

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("addresses the same (result_family, result_selector)", reported[0])

    def test_a_different_family_on_one_selector_is_not_a_duplicate(self) -> None:
        """The target is the pair, not the key: one Event routinely writes two
        families off the same id."""

        def mutate(registry: dict) -> None:
            row = any_covered_row(registry)
            clone = copy.deepcopy(row["result_writes"][0])
            clone["result_family"] = "realm_genesis"
            row["result_writes"].append(clone)

        self.assertEqual(self._newly_reported(mutate), [])

    def test_the_keyed_set_remove_then_add_pair_stays_legal(self) -> None:
        """`ak.agent.key.authorize` is the live shape: key-management.md 3.6.1
        requires the remove and the add to be one atomic Event."""
        registry = gate.load_json(gate.Lint(), REGISTRY)
        writes = row_of(registry, "ak.agent.key.authorize")["result_writes"]
        kinds = [write["result_projection"]["kind"] for write in writes]
        self.assertIn("keyed_set_add", kinds)
        self.assertTrue(
            {"keyed_set_remove_observed", "keyed_set_remove_dots"} & set(kinds), kinds
        )
        self.assertEqual(self._run(), [])

    def test_two_adds_on_one_keyed_set_are_still_a_duplicate(self) -> None:
        """The exception is the pair, not the projection family. Two adds are two
        indistinguishable ops on one result."""

        def mutate(registry: dict) -> None:
            writes = row_of(registry, "ak.agent.key.authorize")["result_writes"]
            add = next(
                write
                for write in writes
                if write["result_projection"]["kind"] == "keyed_set_add"
            )
            clone = copy.deepcopy(add)
            writes.append(clone)

        reported = self._newly_reported(mutate)
        self.assertTrue(
            any(
                "addresses the same (result_family, result_selector)" in error
                for error in reported
            ),
            reported,
        )

    def test_a_disjoint_condition_pair_stays_legal(self) -> None:
        """Complementary presence tests on one field can never both fire, so the
        two writes never race."""

        def mutate(registry: dict) -> None:
            row = any_covered_row(registry)
            first = row["result_writes"][0]
            clone = copy.deepcopy(first)
            first["condition"] = {"kind": "field_present", "field": "payload.probe"}
            clone["condition"] = {"kind": "field_absent", "field": "payload.probe"}
            row["result_writes"].append(clone)

        self.assertEqual(self._newly_reported(mutate), [])

    def test_a_merely_different_condition_pair_is_not_enough(self) -> None:
        """Two presence tests on two different fields can both hold, and a wrong
        guess here means two writes racing on one result."""

        def mutate(registry: dict) -> None:
            row = any_covered_row(registry)
            first = row["result_writes"][0]
            clone = copy.deepcopy(first)
            first["condition"] = {"kind": "field_present", "field": "payload.probe"}
            clone["condition"] = {"kind": "field_present", "field": "payload.other"}
            row["result_writes"].append(clone)

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("provably disjoint condition", reported[0])

    # ---- the coalesce agreement rule -------------------------------------

    def test_a_coalesce_selector_must_match_its_condition_fields(self) -> None:
        """event-and-patch.md 2.4.2: a mismatch means the result can be required
        on a payload shape whose key cannot be derived."""

        def mutate(registry: dict) -> None:
            write = any_covered_row(registry)[
                "result_writes"
            ][0]
            write["result_selector"] = {
                "kind": "coalesce",
                "fields": ["payload.a", "payload.b"],
            }
            write["condition"] = {
                "kind": "any_field_present",
                "fields": ["payload.b", "payload.a"],
            }

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("item-for-item and in order", reported[0])

    def test_an_agreeing_coalesce_selector_passes(self) -> None:
        def mutate(registry: dict) -> None:
            write = any_covered_row(registry)[
                "result_writes"
            ][0]
            write["result_selector"] = {
                "kind": "coalesce",
                "fields": ["payload.a", "payload.b"],
            }
            write["condition"] = {
                "kind": "any_field_present",
                "fields": ["payload.a", "payload.b"],
            }

        self.assertEqual(self._newly_reported(mutate), [])

    def test_an_unconditional_coalesce_selector_is_not_constrained(self) -> None:
        """The other legitimate use of `any_field_present` -- one result carrying
        several distinct fields under an unconditional selector -- is outside the
        rule, and pinning that keeps the rule from widening by accident."""

        def mutate(registry: dict) -> None:
            write = any_covered_row(registry)[
                "result_writes"
            ][0]
            write["condition"] = {
                "kind": "any_field_present",
                "fields": ["payload.a", "payload.b"],
            }

        self.assertEqual(self._newly_reported(mutate), [])


if __name__ == "__main__":
    unittest.main()
