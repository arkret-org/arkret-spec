"""Mutation tests for the writer direction of the typed current result contract.

`check_result_write_contracts` closes write -> family: a `result_writes[]` row
may only name a registered family. This file covers the other direction, which
is the one that actually decayed under `cell_writes[]` -- a family can carry a
closed selector/value schema, a resolvable `$defs` entry and a prose paragraph,
and still have no Event kind that produces it. Nothing in the pipeline used to
say so.

Every mutation test here reads as a delta against the live baseline rather than
as an absolute error count, so each one keeps testing its own proposition while
`result_writes[]` coverage is extended kind by kind.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate

EVENT_KINDS = gate.EVENT_KIND_REGISTRY
FAMILIES = gate.CURRENT_RESULT_REGISTRY


class ResultFamilyWriterGateTest(unittest.TestCase):
    def _run(self, mutations=None) -> list[str]:
        mutations = mutations or {}
        original_load_json = gate.load_json
        documents = {}
        for path, mutate in mutations.items():
            document = copy.deepcopy(original_load_json(gate.Lint(), path))
            mutate(document)
            documents[path.resolve()] = document

        def load_json_with_mutation(lint, path):
            return documents.get(path.resolve(), original_load_json(lint, path))

        gate.load_json = load_json_with_mutation
        try:
            lint = gate.Lint()
            gate.check_every_result_family_has_a_writer(lint)
            return lint.errors
        finally:
            gate.load_json = original_load_json

    def _newly_reported(self, mutations) -> list[str]:
        """Families this mutation makes writer-less, over whatever the baseline is."""
        baseline = set(self._run())
        return sorted(set(self._run(mutations)) - baseline)

    def _writers_of(self, family: str) -> list[str]:
        registry = gate.load_json(gate.Lint(), EVENT_KINDS)
        return [
            row["event_kind"]
            for row in registry["event_kinds"]
            if any(
                write.get("result_family") == family
                for write in row.get("result_writes") or ()
            )
        ]

    def test_the_live_registries_leave_no_family_unwritten(self) -> None:
        """Every registered family has at least one Event kind that produces it.

        This one is deliberately absolute. It is the whole point of the gate, and
        a registered family nobody writes is exactly the shell the gate exists to
        refuse.
        """
        self.assertEqual(self._run(), [])

    def test_a_family_that_loses_its_only_writer_is_reported(self) -> None:
        """Dropping the write makes the family a shell, and the gate must say so."""
        family = "realm_genesis"
        self.assertEqual(
            self._writers_of(family),
            ["ak.realm.create"],
            "fixture assumption: realm_genesis is written by exactly one kind",
        )

        def drop_the_write(registry):
            for row in registry["event_kinds"]:
                if row["event_kind"] != "ak.realm.create":
                    continue
                row["result_writes"] = [
                    write
                    for write in row["result_writes"]
                    if write.get("result_family") != family
                ]
                if not row["result_writes"]:
                    del row["result_writes"]

        reported = self._newly_reported({EVENT_KINDS: drop_the_write})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn(repr(family), reported[0])
        self.assertIn("no Event kind declares", reported[0])

    def test_a_family_registered_without_a_writer_is_reported(self) -> None:
        """Registering a family is not enough; someone has to produce it."""

        def register_an_unwritten_family(registry):
            registry["result_kinds"].append(
                {
                    "result_kind": "hypothetical_family",
                    "schema_ref": (
                        "schemas/typed-current-result.schema.json"
                        "#/$defs/realm_profile_result"
                    ),
                }
            )

        reported = self._newly_reported({FAMILIES: register_an_unwritten_family})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("'hypothetical_family'", reported[0])

    def test_a_second_writer_keeps_the_family_covered(self) -> None:
        """One writer is the floor, not the ceiling: extra writers stay silent."""

        def add_a_redundant_writer(registry):
            for row in registry["event_kinds"]:
                if row["event_kind"] != "ak.realm.restore":
                    continue
                row["result_writes"] = [
                    {
                        "result_family": "realm_genesis",
                        "result_selector": None,
                        "result_projection": {
                            "kind": "set",
                            "value": {"field": "payload.object"},
                        },
                    }
                ]

        self.assertEqual(self._newly_reported({EVENT_KINDS: add_a_redundant_writer}), [])

    def test_a_write_that_names_no_family_stops_counting_as_a_writer(self) -> None:
        """A row missing `result_family` writes nothing, so its family goes bare.

        `check_result_write_contracts` separately reports the malformed row. The
        two findings are complementary, not duplicates: one says the row is
        ill-formed, this one says the family it was supposed to cover is now
        produced by nobody. Suppressing this one would let a typo silently
        uncover a family.
        """

        def blank_the_family(registry):
            for row in registry["event_kinds"]:
                for write in row.get("result_writes") or ():
                    if write.get("result_family") == "realm_history_access":
                        del write["result_family"]

        reported = self._newly_reported({EVENT_KINDS: blank_the_family})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("'realm_history_access'", reported[0])


if __name__ == "__main__":
    unittest.main()
