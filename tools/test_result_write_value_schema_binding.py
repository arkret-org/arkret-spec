"""A `result_writes[]` row must be checkable against the value schema it names.

`value_schema_ref` sat in every row and nothing read it past "does this pointer
resolve to an object". A `value_projection` builds the stored value out of
members named one at a time, so two things the registry already claims were
unverified: that a projected member belongs to the value at all, and that a
whole-value `set` writes everything that value requires.

`ak.member.state` is what that costs. Its ref pointed at
`member_state_result` -- the enclosing envelope, whose own members are
selector/revision/value -- while its projection wrote `membership`, a member of
the value inside. Every other family names a value def; this one named the
envelope, and the row's own notes reasoned about "member_state_result.value"
because the ref could not say it.

The third proposition is one level up: `registry_rules` describes coverage as a
known partial gap and tells the next editor to shrink the note. Nothing read
that either, so it stayed at 12 of 139 across four commits that raised coverage
to 34 -- a source-of-truth registry describing itself wrongly, which no digest
catches because the digest covers whatever the note currently says.

Every mutation test reads as a delta against the live baseline, so each keeps
testing its own proposition while coverage is extended kind by kind.
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
SCHEMAS = ROOT / "spec/v1/artifacts/schemas"
TYPED_CURRENT_RESULT = "schemas/typed-current-result.schema.json"


def row_of(document: dict, kind: str) -> dict:
    for row in document["event_kinds"]:
        if row["event_kind"] == kind:
            return row
    raise AssertionError(f"{kind} is not a registered Event kind")


class ResultWriteValueSchemaBindingTest(unittest.TestCase):
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
            gate.check_result_write_contracts(lint)
            gate.check_result_write_coverage_note(lint)
            return lint.errors
        finally:
            gate.load_json = original_load_json

    def _newly_reported(self, mutations) -> list[str]:
        baseline = set(self._run())
        return sorted(set(self._run(mutations)) - baseline)

    # ---- the live baseline ----------------------------------------------

    def test_the_live_registry_is_clean(self) -> None:
        """Absolute on purpose: a gate whose baseline is not zero cannot say
        whether the next edit broke something."""
        self.assertEqual(self._run(), [])

    def test_every_projected_member_has_a_value_schema_to_check_it(self) -> None:
        registry = gate.load_json(gate.Lint(), EVENT_KINDS)
        seen = 0
        for row in registry["event_kinds"]:
            for index, write in enumerate(row.get("result_writes") or ()):
                projection = write["result_projection"]
                value_projection = projection.get("value_projection") or {}
                if not value_projection.get("members"):
                    continue
                seen += 1
                with self.subTest(kind=row["event_kind"], index=index):
                    self.assertIsNotNone(write.get("value_schema_ref"))
        self.assertGreater(seen, 0)

    def test_member_state_names_a_value_rather_than_its_envelope(self) -> None:
        """The one row that named the envelope, and the extraction that fixed it.

        `member_state_result.properties.value` is now a `$ref` at the same def,
        so the envelope and the registry cannot drift apart again."""
        registry = gate.load_json(gate.Lint(), EVENT_KINDS)
        write = row_of(registry, "ak.member.state")["result_writes"][0]
        self.assertEqual(
            write["value_schema_ref"],
            f"{TYPED_CURRENT_RESULT}#/$defs/member_state_current",
        )
        schema = gate.load_json(gate.Lint(), SCHEMAS / "typed-current-result.schema.json")
        self.assertEqual(
            schema["$defs"]["member_state_result"]["properties"]["value"],
            {"$ref": "#/$defs/member_state_current"},
        )
        self.assertIn("membership", schema["$defs"]["member_state_current"]["properties"])

    # ---- resolving a registered value schema -----------------------------

    def _alternatives(self, ref: str):
        file_ref, _, fragment = ref.partition("#")
        document = gate.load_json(gate.Lint(), gate.ARTIFACTS / file_ref)
        node = gate.resolve_json_pointer(document, f"#{fragment}") if fragment else document
        return gate._value_schema_alternatives(gate.Lint(), file_ref, node)

    def test_a_local_ref_resolves_to_the_value_it_points_at(self) -> None:
        declared, required = self._alternatives(
            f"{TYPED_CURRENT_RESULT}#/$defs/member_state_current"
        )[0]
        self.assertEqual(declared, {"membership", "joined_at"})
        self.assertEqual(required, {"membership"})

    def test_a_whole_file_ref_resolves(self) -> None:
        """`capability_grant` names a schema file, not a `$defs` fragment."""
        declared, required = self._alternatives("schemas/capability-grant.schema.json")[0]
        self.assertIn("revoked_by", declared)
        self.assertIn("updated_at", declared)
        self.assertIn("status", required)

    def test_a_null_branch_is_dropped_rather_than_treated_as_a_shape(self) -> None:
        """`strand_position_value` spells pre-placement as a `null` branch. An
        object projection can never produce it, so it must not weaken the
        required floor of the branch that does describe an object."""
        alternatives = self._alternatives(f"{TYPED_CURRENT_RESULT}#/$defs/strand_position_value")
        self.assertEqual(len(alternatives), 1)
        declared, required = alternatives[0]
        self.assertEqual(declared, {"list_space_id", "rank"})
        self.assertEqual(required, {"list_space_id", "rank"})

    # ---- what the gate refuses -------------------------------------------

    def test_pointing_a_write_back_at_its_result_envelope_is_reported(self) -> None:
        """The exact pre-existing defect: the members of the envelope are not the
        members of the value, and a `set` against the envelope would additionally
        owe it a selector and a revision."""

        def mutate(document):
            write = row_of(document, "ak.member.state")["result_writes"][0]
            write["value_schema_ref"] = f"{TYPED_CURRENT_RESULT}#/$defs/member_state_result"

        reported = self._newly_reported({EVENT_KINDS: mutate})
        self.assertEqual(len(reported), 4, reported)
        self.assertTrue(any("member 'membership' is not declared" in line for line in reported))
        for owed in ("'selector'", "'revision'", "'value'"):
            self.assertTrue(
                any(f"does not write {owed}" in line for line in reported), (owed, reported)
            )

    def test_a_member_the_value_schema_never_declares_is_reported(self) -> None:
        def mutate(document):
            write = row_of(document, "ak.capability.revoke")["result_writes"][0]
            write["result_projection"]["value_projection"]["members"][0]["name"] = "revoked_reason"

        reported = self._newly_reported({EVENT_KINDS: mutate})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("member 'revoked_reason' is not declared", reported[0])

    def test_a_whole_value_set_that_drops_a_required_member_is_reported(self) -> None:
        """`ak.mls.genesis` writes all seven members `mls_group_current` requires;
        a `set` that writes six materialises a value that violates its own
        registered schema on the first replay."""

        def mutate(document):
            projection = row_of(document, "ak.mls.genesis")["result_writes"][0][
                "result_projection"
            ]
            members = projection["value_projection"]["members"]
            projection["value_projection"]["members"] = [
                member for member in members if member["name"] != "epoch"
            ]

        reported = self._newly_reported({EVENT_KINDS: mutate})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("whole-value set but does not write 'epoch'", reported[0])

    def test_a_merge_is_not_held_to_the_required_floor(self) -> None:
        """A `merge` writes only the members it names; the rest belong to the
        already-projected value, so demanding them here would forbid every
        partial write the registry has."""
        registry = gate.load_json(gate.Lint(), EVENT_KINDS)
        write = row_of(registry, "ak.capability.revoke")["result_writes"][0]
        self.assertEqual(write["result_projection"]["kind"], "merge")
        projected = {
            member["name"]
            for member in write["result_projection"]["value_projection"]["members"]
        }
        declared, required = self._alternatives(write["value_schema_ref"])[0]
        self.assertTrue(required - projected, "the fixture stopped exercising the exemption")
        self.assertEqual(self._run(), [])

    def test_a_value_projection_without_a_value_schema_is_reported(self) -> None:
        """Otherwise the whole check is opt-out: drop the ref and the members
        answer to nothing."""

        def mutate(document):
            del row_of(document, "ak.member.state")["result_writes"][0]["value_schema_ref"]

        reported = self._newly_reported({EVENT_KINDS: mutate})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("declares no value_schema_ref", reported[0])

    def test_a_value_schema_with_no_members_at_all_is_reported(self) -> None:
        """A scalar value schema cannot host a `value_projection` at all, and
        saying so is better than silently checking nothing. `agent_status` is a
        bare enum, so it is the shape that has no members to check against."""

        def mutate(document):
            row_of(document, "ak.member.state")["result_writes"][0]["value_schema_ref"] = (
                f"{TYPED_CURRENT_RESULT}#/$defs/agent_status_result/properties/value"
            )

        reported = self._newly_reported({EVENT_KINDS: mutate})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("declares no members", reported[0])

    # ---- the coverage note ------------------------------------------------

    def _note_index(self, document: dict) -> int:
        for index, rule in enumerate(document["registry_rules"]):
            if "COVERAGE IS PARTIAL" in rule:
                return index
        raise AssertionError("the coverage note is gone")

    def test_the_note_counts_the_rows_that_are_there(self) -> None:
        registry = gate.load_json(gate.Lint(), EVENT_KINDS)
        reducer_inputs = [row for row in registry["event_kinds"] if row.get("reducer_input")]
        covered = [row for row in reducer_inputs if row.get("result_writes")]
        note = registry["registry_rules"][self._note_index(registry)]
        self.assertIn(
            f"{len(covered)} of the {len(reducer_inputs)} reducer_input kinds declare it; "
            f"the remaining {len(reducer_inputs) - len(covered)}",
            note,
        )

    def test_a_note_that_lags_the_rows_is_reported(self) -> None:
        """This is the mutation that was true on disk for four commits."""

        def mutate(document):
            index = self._note_index(document)
            document["registry_rules"][index] = document["registry_rules"][index].replace(
                "34 of the 139 reducer_input kinds declare it; the remaining 105",
                "12 of the 139 reducer_input kinds declare it; the remaining 127",
            )

        reported = self._newly_reported({EVENT_KINDS: mutate})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("says 12 of 139 with 127 remaining", reported[0])

    def test_re_enumerating_the_declaring_kinds_is_reported(self) -> None:
        """The enumeration is what went stale; `event_kinds[]` is that list."""

        def mutate(document):
            index = self._note_index(document)
            document["registry_rules"][index] += " Declaring kinds: ak.member.state."

        reported = self._newly_reported({EVENT_KINDS: mutate})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("must not enumerate the declaring kinds", reported[0])

    def test_losing_the_note_is_reported(self) -> None:
        def mutate(document):
            del document["registry_rules"][self._note_index(document)]

        reported = self._newly_reported({EVENT_KINDS: mutate})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("exactly one result_writes[] coverage note, found 0", reported[0])

    def test_an_unparseable_note_is_reported(self) -> None:
        """A note the gate cannot read is a note nobody is checking."""

        def mutate(document):
            index = self._note_index(document)
            document["registry_rules"][index] = (
                "COVERAGE IS PARTIAL AND THIS IS A KNOWN GAP: most kinds still have no contract."
            )

        reported = self._newly_reported({EVENT_KINDS: mutate})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("must state coverage as", reported[0])


if __name__ == "__main__":
    unittest.main()
