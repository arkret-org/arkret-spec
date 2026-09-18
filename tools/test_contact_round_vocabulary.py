"""The Contact lineage key is named `contact_round_id`, and only that.

An earlier revision called it the "basis". The rename to `contact_round`
reached the wire schemas and `identity/contact-and-direct-conversation.md`, but
left nine sites behind in descriptions and in one registered conformance
vector, two of which named a field -- `basis_id` -- that no schema in the
repository defines. `ak.vector.contact.next_prepare_input.v1` and
`conformance/conformance-vectors.md` section on it both told an implementer to
copy `basis_id` verbatim into the prepare phase, where the closed
`contact_next_prepare_input` has no such member and `additionalProperties` is
false: following the vector produced a request the schema rejects.

Nothing mechanical caught it. A description is prose to every gate, and the
vector registry carries no field names a schema can be diffed against. These
propositions are the check that does not exist otherwise.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SPEC = ROOT / "spec" / "v1"
ARTIFACTS = SPEC / "artifacts"

CONTACT_KINDS = (
    "ak.contact.requested",
    "ak.contact.accepted",
    "ak.contact.rejected",
    "ak.contact.scope.update",
    "ak.contact.tombstone",
)

LINEAGE_CURSOR_MEMBERS = ["contact_round_id", "predecessor_event_ref", "version"]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ContactRoundVocabularyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = _load(ARTIFACTS / "registry" / "contract-registry.json")
        cls.vectors = _load(ARTIFACTS / "registry" / "vector-registry.json")
        cls.contact_ops = _load(ARTIFACTS / "schemas" / "contact-operations.schema.json")
        cls.payloads = _load(ARTIFACTS / "schemas" / "event-payload.schema.json")
        cls.rows = {
            row["event_kind"]: row
            for row in cls.registry["event_kind_registry"]["event_kinds"]
            if row["event_kind"] in CONTACT_KINDS
        }

    # ---- the retired name ------------------------------------------------

    def test_no_artifact_names_a_basis_id_field(self) -> None:
        """`basis_id` is not a member of any schema, so no text may promise it."""
        offenders = [
            path.relative_to(ROOT).as_posix()
            for path in sorted(SPEC.rglob("*"))
            if path.is_file()
            and path.suffix in {".json", ".md", ".yaml"}
            and "basis_id" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])

    def test_the_contact_surface_does_not_say_basis(self) -> None:
        """The five kinds and the cursor describe the same thing one way."""
        texts = [row["payload"] for row in self.rows.values()]
        texts.append(self.contact_ops["$defs"]["contact_next_prepare_input"]["description"])
        for name in (
            "contact_requested_payload",
            "contact_accepted_payload",
            "contact_rejected_payload",
            "contact_tombstoned_payload",
        ):
            texts.append(self.payloads["$defs"][name].get("description", ""))
        self.assertEqual([text for text in texts if "basis" in text], [])

    # ---- the live name ---------------------------------------------------

    def test_the_cursor_carries_exactly_the_three_live_names(self) -> None:
        cursor = self.contact_ops["$defs"]["contact_next_prepare_input"]
        self.assertEqual(sorted(cursor["required"]), LINEAGE_CURSOR_MEMBERS)
        self.assertEqual(sorted(cursor["properties"]), LINEAGE_CURSOR_MEMBERS)
        self.assertFalse(cursor["additionalProperties"])

    def test_the_vector_names_the_members_the_schema_defines(self) -> None:
        """The vector tells an implementer to copy these verbatim.

        Verbatim is the whole content of the rule, so a name the vector prints
        that the closed object does not define is not a wording slip: it is an
        instruction to build a rejected request.
        """
        vector = next(
            row
            for row in self.vectors["vectors"]
            if row["vector_id"] == "ak.vector.contact.next_prepare_input.v1"
        )
        description = vector["description"]
        for member in LINEAGE_CURSOR_MEMBERS:
            self.assertIn(member, description, member)

    def test_the_lineage_key_reaches_the_three_successor_payloads(self) -> None:
        """accepted / scope.update / tombstone carry the key; request does not.

        The asymmetry is load-bearing -- a request precedes the round that is
        derived from it -- and it is the reason the cursor is absent from a
        pending row rather than carrying a placeholder.
        """
        for name in (
            "contact_accepted_payload",
            "contact_scope_update_payload",
            "contact_tombstoned_payload",
        ):
            node = self.payloads["$defs"][name]
            target = self.contact_ops["$defs"][name] if "$ref" in node else node
            self.assertIn("contact_round_id", target["required"], name)
        self.assertNotIn(
            "contact_round_id",
            self.payloads["$defs"]["contact_requested_payload"]["properties"],
        )

    # ---- the vocabularies that were deliberately left alone --------------

    def test_the_unrelated_basis_vocabularies_survive(self) -> None:
        """`basis` is a live word elsewhere; this was a rename, not a purge."""
        self.assertIn(
            "direct_conversation_authorization_basis", self.payloads["$defs"]
        )
        self.assertIn("root_basis", self.contact_ops["$defs"]["bilateral_continuity_checkpoint_core"]["properties"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
