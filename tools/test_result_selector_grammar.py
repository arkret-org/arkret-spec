"""Mutation tests for the closed `result_selector` subject grammar.

`zh/conformance/encoding.md` section 9.5.1 states the whole rule: a subject's
registry field source MUST be named explicitly, a bare field name or a
payload-then-envelope fallback is undefined and MUST be rejected, and
`envelope.actor_id` is the only registered envelope source.

Until this closure the gate checked only that `kind` was in the closed table,
plus a shallow non-empty/no-duplicate pass over `composite.components`. A
subject could therefore name no source at all, read an unregistered envelope
field, or carry members nobody reads. Two normative sentences -- the
`payload.grant_id` revoke selector of `authz/capabilities.md` and the
`payload.mimi_room_uri` subject of `extensions/mimi-interop.md` -- could not be
spelled at all, because a non-composite subject had nowhere to name its field.

Each test states one proposition about the closure. `typed_pair` has its own
file; this one covers everything else.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate

REGISTRY = ROOT / "spec/v1/artifacts/registry/contract-registry.json"


def errors_for(selector, id_source=None) -> list[str]:
    lint = gate.Lint()
    gate._check_result_selector(lint, "probe.result_selector", selector, id_source)
    return lint.errors


class ResultSelectorGrammarTest(unittest.TestCase):
    def test_every_live_selector_is_accepted(self) -> None:
        """The live registry is the first assertion: the closure must describe
        what is already registered, not a grammar nobody uses."""
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        lint = gate.Lint()
        seen = 0
        for row in registry["event_kind_registry"]["event_kinds"]:
            for index, write in enumerate(row.get("result_writes") or ()):
                seen += 1
                gate._check_result_selector(
                    lint,
                    f"{row['event_kind']}.result_writes[{index}].result_selector",
                    write["result_selector"],
                    row.get("id_source"),
                )
        self.assertGreater(seen, 40)
        self.assertEqual(lint.errors, [])

    def test_a_singleton_is_json_null(self) -> None:
        self.assertEqual(errors_for(None), [])

    # ---- the source a subject reads -------------------------------------

    def test_a_non_composite_subject_without_a_field_is_reported(self) -> None:
        """This is the gap that made two normative sentences unspellable."""
        for kind in ("uri", "did", "string", "typed_id", "id:grant"):
            with self.subTest(kind=kind):
                reported = errors_for({"kind": kind})
                self.assertEqual(len(reported), 1, reported)
                self.assertIn("field is required", reported[0])

    def test_a_non_composite_subject_naming_its_field_is_accepted(self) -> None:
        for kind in ("uri", "did", "string", "typed_id", "id:grant"):
            with self.subTest(kind=kind):
                self.assertEqual(errors_for({"kind": kind, "field": "payload.grant_id"}), [])

    def test_a_fieldless_id_subject_is_accepted_only_on_an_event_derived_kind(self) -> None:
        self.assertEqual(errors_for({"kind": "id:strand"}, "event_derived"), [])
        for id_source in ("reference", "not_an_object_id", None):
            with self.subTest(id_source=id_source):
                reported = errors_for({"kind": "id:strand"}, id_source)
                self.assertEqual(len(reported), 1, reported)
                self.assertIn("field is required", reported[0])

    def test_naming_a_field_on_an_event_derived_id_subject_is_reported(self) -> None:
        """The fieldless form already means this Event's own id retyped, so a
        field says the opposite of what the row says."""
        reported = errors_for({"kind": "id:strand", "field": "payload.strand_id"}, "event_derived")
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("contradicts the row", reported[0])

    def test_an_unregistered_envelope_source_is_reported(self) -> None:
        for field in ("envelope.realm_id", "envelope.executed_by", "envelope.event_id"):
            with self.subTest(field=field):
                reported = errors_for({"kind": "uri", "field": field})
                self.assertEqual(len(reported), 1, reported)
                self.assertIn("unregistered envelope source", reported[0])

    def test_a_bare_field_name_is_reported(self) -> None:
        reported = errors_for({"kind": "uri", "field": "grant_id"})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("explicit payload.*", reported[0])

    # ---- component descriptors ------------------------------------------

    def test_a_component_descriptor_is_not_a_top_level_subject_kind(self) -> None:
        """Both describe how one component is reduced to bytes, so neither has a
        row in the closed embedding table and neither has a wire id on its own.
        `CELL_SUBJECT_KINDS` is what excludes them; this asserts it stays that
        way, because adding one there would give it an undefined encoding."""
        for kind in ("canonical_json", "string_set_digest"):
            with self.subTest(kind=kind):
                reported = errors_for({"kind": kind, "field": "payload.member_id"})
                self.assertEqual(len(reported), 1, reported)
                self.assertIn("closed subject table", reported[0])

    def test_a_composite_component_with_an_unregistered_source_is_reported(self) -> None:
        reported = errors_for(
            {"kind": "composite", "components": ["payload.call_id", "envelope.realm_id"]}
        )
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("unregistered envelope source", reported[0])

    def test_a_composite_component_descriptor_of_an_unknown_kind_is_reported(self) -> None:
        reported = errors_for(
            {
                "kind": "composite",
                "components": [{"kind": "id:space", "field": "payload.board_space_id"}],
            }
        )
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("only registered component descriptors", reported[0])

    def test_a_composite_component_descriptor_without_a_field_is_reported(self) -> None:
        reported = errors_for({"kind": "composite", "components": [{"kind": "canonical_json"}]})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("field is required", reported[0])

    def test_a_composite_component_with_unknown_members_is_reported(self) -> None:
        reported = errors_for(
            {
                "kind": "composite",
                "components": [
                    {"kind": "canonical_json", "field": "payload.member_id", "name": "member"}
                ],
            }
        )
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("unknown member(s) ['name']", reported[0])

    def test_an_empty_or_repeating_component_list_is_reported(self) -> None:
        reported = errors_for({"kind": "composite", "components": []})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("non-empty array", reported[0])
        reported = errors_for(
            {"kind": "composite", "components": ["payload.call_id", "payload.call_id"]}
        )
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("must not repeat a component", reported[0])

    def test_tuple_is_validated_like_composite(self) -> None:
        """`tuple` sat in the closed table with no validation at all, which is
        how a subject kind becomes three different things."""
        self.assertEqual(errors_for({"kind": "tuple", "components": ["payload.call_id"]}), [])
        reported = errors_for({"kind": "tuple", "components": ["call_id"]})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("explicit payload.*", reported[0])

    # ---- coalesce --------------------------------------------------------

    def test_coalesce_fields_are_validated(self) -> None:
        self.assertEqual(
            errors_for(
                {"kind": "coalesce", "fields": ["payload.circle_id", "payload.target_ref"]}
            ),
            [],
        )
        for selector, expected in (
            ({"kind": "coalesce", "fields": []}, "non-empty array"),
            (
                {"kind": "coalesce", "fields": ["payload.circle_id", "payload.circle_id"]},
                "must not repeat a field",
            ),
            ({"kind": "coalesce", "fields": ["circle_id"]}, "explicit payload.*"),
        ):
            with self.subTest(selector=selector):
                reported = errors_for(selector)
                self.assertEqual(len(reported), 1, reported)
                self.assertIn(expected, reported[0])

    def test_coalesce_spelled_with_components_is_reported(self) -> None:
        """`zh/models/circle.md` spells this subject with `"type"` rather than
        `"kind"`; a member nobody reads is how that drift survives."""
        reported = errors_for({"kind": "coalesce", "components": ["payload.circle_id"]})
        self.assertEqual(len(reported), 2, reported)
        self.assertIn("unknown member(s) ['components']", reported[0])
        self.assertIn("fields must be a non-empty array", reported[1])

    # ---- the enclosing shape --------------------------------------------

    def test_an_unregistered_subject_kind_is_reported(self) -> None:
        reported = errors_for({"kind": "sha256_of_everything", "field": "payload.x"})
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("closed subject table", reported[0])

    def test_a_non_object_selector_is_reported(self) -> None:
        reported = errors_for("payload.grant_id")
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("must be JSON null or an object", reported[0])


if __name__ == "__main__":
    unittest.main()
