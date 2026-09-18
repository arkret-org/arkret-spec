"""The Direct Conversation binding is a set of endorsements, not a first-writer slot.

`ak.direct_conversation.bound` sat `reducer_input: true` with no registered
write while its own payload description said "Immutable after the first accepted
write". Read as a claim about the RESULT, that sentence produces a write-once
set on `pair_key` -- one participant endorses, the other is refused. Read as a
claim about the BINDING, which is what
`identity/contact-and-direct-conversation.md` section 8.3 actually says, it
produces an add-only keyed set whose elements are both participants'
endorsements of one binding, with a different semantic `binding_digest` refused
before projection.

Nothing mechanical distinguishes those two readings, and the second one only
became checkable when the write was registered. These propositions are what the
registration bought.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate

ARTIFACTS = gate.ARTIFACTS
KIND = "ak.direct_conversation.bound"
FAMILY = "direct_conversation_binding"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class DirectConversationBindingFamilyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = _load(gate.EVENT_KIND_REGISTRY)
        cls.results = _load(ARTIFACTS / "schemas" / "typed-current-result.schema.json")
        cls.payloads = _load(ARTIFACTS / "schemas" / "event-payload.schema.json")
        cls.row = next(
            row for row in cls.registry["event_kinds"] if row["event_kind"] == KIND
        )
        cls.write = cls.row["result_writes"][0]

    # ---- the set ---------------------------------------------------------

    def test_the_kind_registers_one_add_only_write(self) -> None:
        self.assertEqual(len(self.row["result_writes"]), 1)
        self.assertEqual(self.write["result_family"], FAMILY)
        self.assertEqual(self.write["result_projection"]["kind"], "keyed_set_add")

    def test_the_element_tag_is_the_event_dot(self) -> None:
        """A bare event_id would collide the moment one Event carries two writes."""
        self.assertEqual(self.write["result_projection"]["tag"], {"dot": True})
        entry = self.results["$defs"][f"{FAMILY}_endorsement_entry"]
        self.assertEqual(
            entry["properties"]["tag_id"], {"$ref": "#/$defs/canonical_event_dot"}
        )

    def test_the_element_value_is_the_whole_signed_payload(self) -> None:
        self.assertEqual(self.write["result_projection"]["value"], {"field": "payload"})
        entry = self.results["$defs"][f"{FAMILY}_endorsement_entry"]
        self.assertEqual(
            entry["properties"]["value"],
            {"$ref": "./event-payload.schema.json#/$defs/direct_conversation_bound_payload"},
        )

    def test_nothing_in_v1_removes_an_endorsement(self) -> None:
        """An add-only set is a decision, not an omission.

        Section 8.3 forbids `binding_state` and `supersedes_binding_ref` on the
        payload, so there is no wire form a retraction could take. A remover
        appearing on this family later would mean one arrived without the
        separate security command that section requires.
        """
        removers = [
            write
            for row in self.registry["event_kinds"]
            for write in row.get("result_writes") or []
            if write.get("result_family") == FAMILY
            and str(write["result_projection"]["kind"]).startswith("keyed_set_remove")
        ]
        self.assertEqual(removers, [])
        payload = self.payloads["$defs"]["direct_conversation_bound_payload"]
        self.assertNotIn("binding_state", payload["properties"])
        self.assertNotIn("supersedes_binding_ref", payload["properties"])

    def test_the_value_holds_at_least_one_endorsement(self) -> None:
        """`found` needs one accepted endorsement; an empty set is not a binding."""
        endorsements = self.results["$defs"][f"{FAMILY}_value"]["properties"]["endorsements"]
        self.assertEqual(endorsements["minItems"], 1)
        self.assertTrue(endorsements["uniqueItems"])

    # ---- the subject -----------------------------------------------------

    def test_the_subject_is_the_pair_key_alone(self) -> None:
        self.assertEqual(
            self.write["result_selector"],
            {"kind": "composite", "components": ["payload.pair_key"]},
        )

    def test_the_scope_is_not_repeated_in_the_selector(self) -> None:
        """The result already lives in the Direct Conversation's own Realm.

        `realm_id` and `main_strand_id` are wire fields that admission verifies
        against the Realm's settled coordinates. Adding either as a selector
        member would be a second copy of the scope -- exactly what
        `conformance/encoding.md` section 4 forbids -- and would silently split
        one conversation's endorsements across two subjects if the copies ever
        disagreed.
        """
        selector = self.results["$defs"][f"{FAMILY}_result"]["properties"]["selector"]
        self.assertEqual(sorted(selector["required"]), ["kind", "pair_key"])
        self.assertNotIn("realm_id", selector["properties"])
        self.assertNotIn("main_strand_id", selector["properties"])
        self.assertFalse(selector["additionalProperties"])

    def test_the_derived_digest_stays_off_the_stored_element(self) -> None:
        """`binding_digest` is receiver-derived and is not a wire field.

        Storing it on the element would create a second copy of a value every
        reader MUST recompute from the signed payload anyway, and the copy is
        what a reader would then trust.
        """
        payload = self.payloads["$defs"]["direct_conversation_bound_payload"]
        self.assertNotIn("binding_digest", payload["properties"])
        entry = self.results["$defs"][f"{FAMILY}_endorsement_entry"]
        self.assertEqual(sorted(entry["properties"]), ["tag_id", "value"])

    # ---- the withdrawn reading -------------------------------------------

    def test_neither_description_still_reads_as_write_once(self) -> None:
        """The exact sentence that produced the wrong shape.

        It is checked verbatim because the defect was never in the structure --
        the structure did not exist yet -- but in a description that a reader
        could only resolve one way.
        """
        stale = "Immutable after the first accepted write."
        self.assertNotIn(stale, self.payloads["$defs"]["direct_conversation_bound_payload"]["description"])
        self.assertNotIn(stale, self.row["payload"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
