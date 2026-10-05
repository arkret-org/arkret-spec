"""Grammar tests for the `typed_pair` typed current result subject.

`zh/models/realm-and-space.md` section 3.6 is the only paragraph that pins a
family to this subject kind, and it pins two properties that a free-form
component list cannot carry: the wire form
`strand_position:<board_space_id>:<strand_id>` MUST stay invertible, and a
reader MUST validate BOTH typed-ID components instead of slicing the tail. Two
ordered components, each naming its own registered id kind, is exactly what
makes that true, so the shape is closed rather than inherited from `composite`.

Each test states one proposition about that closure. The first one is the live
assertion -- if `strand_position` ever stops being spelled the way the section
spells it, this file says so before the pipeline has to.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate

LIVE = {
    "kind": "typed_pair",
    "components": [
        {"kind": "id:space", "field": "payload.board_space_id"},
        {"kind": "id:strand", "field": "payload.strand_id"},
    ],
}


def errors_for(selector) -> list[str]:
    lint = gate.Lint()
    gate._check_result_selector(lint, "probe.result_selector", selector)
    return lint.errors


class TypedPairSubjectTest(unittest.TestCase):
    def test_the_registered_strand_position_subject_is_accepted(self) -> None:
        self.assertEqual(errors_for(LIVE), [])

    def test_every_registry_use_of_typed_pair_is_the_strand_position_subject(self) -> None:
        """The grammar is pinned by one section, so one shape may use it.

        A second, differently shaped `typed_pair` would mean some other family
        had adopted the kind without a paragraph fixing its components, which is
        how a subject kind becomes a name three parties spell differently.
        """
        registry = gate.load_json(gate.Lint(), gate.EVENT_KIND_REGISTRY)
        observed = [
            (row["event_kind"], write["result_family"], write["result_selector"])
            for row in registry["event_kinds"]
            for write in row.get("result_writes") or ()
            if isinstance(write.get("result_selector"), dict)
            and write["result_selector"].get("kind") == "typed_pair"
        ]
        self.assertEqual(
            sorted(kind for kind, _, _ in observed),
            ["ak.strand.move", "ak.strand.move", "ak.strand.reorder"],
        )
        for kind, family, selector in observed:
            self.assertEqual(family, "strand_position", kind)
            self.assertEqual(selector, LIVE, kind)

    def test_an_arity_other_than_two_is_reported(self) -> None:
        for components in ([LIVE["components"][0]], LIVE["components"] + [LIVE["components"][0]], []):
            with self.subTest(arity=len(components)):
                reported = errors_for({"kind": "typed_pair", "components": components})
                self.assertEqual(len(reported), 1, reported)
                self.assertIn("exactly two ordered components", reported[0])

    def test_a_component_that_is_not_exactly_kind_and_field_is_reported(self) -> None:
        for component in (
            {"kind": "id:space"},
            {"field": "payload.board_space_id"},
            {"kind": "id:space", "field": "payload.board_space_id", "name": "board"},
            "payload.board_space_id",
        ):
            with self.subTest(component=component):
                reported = errors_for(
                    {"kind": "typed_pair", "components": [component, LIVE["components"][1]]}
                )
                self.assertEqual(len(reported), 1, reported)
                self.assertIn("must be exactly {kind, field}", reported[0])

    def test_an_untyped_component_kind_is_reported(self) -> None:
        """`canonical_json` is a legal `composite` component descriptor and an
        illegal `typed_pair` one: hashing or stringifying a component is what
        makes the pair non-invertible."""
        reported = errors_for(
            {
                "kind": "typed_pair",
                "components": [
                    {"kind": "canonical_json", "field": "payload.board_space_id"},
                    LIVE["components"][1],
                ],
            }
        )
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("must be an `id:<object kind>` typed-ID kind", reported[0])

    def test_an_unregistered_id_kind_is_reported(self) -> None:
        reported = errors_for(
            {
                "kind": "typed_pair",
                "components": [
                    {"kind": "id:board", "field": "payload.board_space_id"},
                    LIVE["components"][1],
                ],
            }
        )
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("is not a registered id_kinds[] row", reported[0])

    def test_repeating_one_field_is_reported(self) -> None:
        reported = errors_for(
            {
                "kind": "typed_pair",
                "components": [
                    {"kind": "id:strand", "field": "payload.strand_id"},
                    {"kind": "id:strand", "field": "payload.strand_id"},
                ],
            }
        )
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("must not read the same field twice", reported[0])

    def test_an_unknown_selector_member_is_reported(self) -> None:
        reported = errors_for(dict(LIVE, digest_subject=True))
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("unknown member(s) ['digest_subject']", reported[0])

    def test_a_malformed_field_path_is_reported(self) -> None:
        reported = errors_for(
            {
                "kind": "typed_pair",
                "components": [
                    {"kind": "id:space", "field": "payload.spaces[0]"},
                    LIVE["components"][1],
                ],
            }
        )
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("dot-separated named fields", reported[0])


if __name__ == "__main__":
    unittest.main()
