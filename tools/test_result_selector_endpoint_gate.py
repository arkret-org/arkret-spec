"""A typed current result key must exist in the payload it is derived from.

`check_composite_subject_terminal_types` reads every `result_selector` in the
Event kind registry and resolves each endpoint against the payload class the
Envelope dispatch selects for that kind. Until 2026-09-18 it read
`cell_writes[].cell_subject`. The authority-commit clean break had renamed the
array to `result_writes[]` and the member to `result_selector`, so the row loop
iterated an absent key on every row, the gate returned with nothing to say, and
`check` recorded that as a pass.

What it was passing over: the four `ak.call.state` capture rows keyed themselves
on `payload.recording_id`, a field `call_state_payload` does not have.
`crypto-media/call-state.md` section 4.2 says the segment key comes from
`recording_transition.recording_id` / `transcript_transition.recording_id` and
MUST equal the segment's start Event value byte for byte. A selector is the key
a reducer writes under, so an unresolvable component is not cosmetic: the row
cannot be implemented at all.

The port carries a fail-closed empty-sweep guard, because the failure above was
not a wrong answer -- it was no answer at all, and nothing distinguished it from
a clean run.

Every mutation reads as a delta against the live baseline, so each test keeps
testing its own proposition as the registry grows.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import schemas as gate

EVENT_KIND_REGISTRY = gate.ARTIFACTS / "registry" / "event-kind-registry.json"
ENVELOPE_SCHEMA = gate.ARTIFACTS / "schemas" / "event-envelope.schema.json"

CAPTURE_ROWS = {
    "call_recording_state": "payload.recording_transition.recording_id",
    "call_recording_artifact": "payload.recording_transition.recording_id",
    "call_transcript_state": "payload.transcript_transition.recording_id",
    "call_transcript_artifact": "payload.transcript_transition.recording_id",
}


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


class ResultSelectorEndpointGateTest(unittest.TestCase):
    def _run(self, mutate=None) -> list[str]:
        original_load_json = gate.load_json
        documents = {}
        if mutate is not None:
            document = copy.deepcopy(
                original_load_json(gate.Lint(), EVENT_KIND_REGISTRY)
            )
            mutate(document)
            documents[EVENT_KIND_REGISTRY.resolve()] = document

        def load_json_with_mutation(lint, path):
            return documents.get(path.resolve(), original_load_json(lint, path))

        gate.load_json = load_json_with_mutation
        try:
            lint = gate.Lint()
            envelope = load_json_with_mutation(lint, ENVELOPE_SCHEMA)
            gate.check_composite_subject_terminal_types(lint, ENVELOPE_SCHEMA, envelope)
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

    def test_the_capture_rows_key_on_the_per_transition_segment_id(self) -> None:
        """The defect the port caught. `call_state_payload` has no top-level
        `recording_id`; each transition object carries its own."""
        registry = gate.load_json(gate.Lint(), EVENT_KIND_REGISTRY)
        for family, expected in CAPTURE_ROWS.items():
            write = write_of(registry, "ak.call.state", family)
            self.assertEqual(
                write["result_selector"]["components"],
                ["payload.call_id", expected],
                family,
            )

    def test_the_start_rows_still_key_on_the_top_level_segment_id(self) -> None:
        """`ak.call.recording.start` is the counterpart: its payload declares
        `recording_id` at the top level, and section 4.2 requires both sides to
        derive the same key."""
        registry = gate.load_json(gate.Lint(), EVENT_KIND_REGISTRY)
        for family in ("call_recording_state", "call_transcript_state"):
            write = write_of(registry, "ak.call.recording.start", family)
            self.assertEqual(
                write["result_selector"]["components"],
                ["payload.call_id", "payload.recording_id"],
                family,
            )

    # ---- the gate cannot be silenced by renaming its input ---------------

    def test_an_empty_sweep_is_a_failure_not_a_pass(self) -> None:
        """Exactly what the clean break did: the writes were still there, under
        a name this gate no longer read."""

        def mutate(registry: dict) -> None:
            for row in registry["event_kinds"]:
                if "result_writes" in row:
                    row["cell_writes"] = row.pop("result_writes")

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("inspected no result_writes[] entry", reported[0])

    def test_the_historical_defect_is_reported_if_it_returns(self) -> None:
        def mutate(registry: dict) -> None:
            write = write_of(registry, "ak.call.state", "call_recording_state")
            write["result_selector"]["components"] = [
                "payload.call_id",
                "payload.recording_id",
            ]

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("'payload.recording_id' has no schema endpoint", reported[0])

    # ---- the endpoint rules ---------------------------------------------

    def test_a_component_that_resolves_to_an_object_is_reported(self) -> None:
        """A selector component is embedded as a scalar; an object endpoint
        would make the key depend on member order."""

        def mutate(registry: dict) -> None:
            write = write_of(registry, "ak.call.state", "call_recording_state")
            write["result_selector"]["components"] = [
                "payload.call_id",
                "payload.recording_transition",
            ]

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn(
            "must be a schema-declared JSON string/integer/boolean/null scalar",
            reported[0],
        )

    def test_a_single_field_selector_endpoint_is_resolved_too(self) -> None:
        """Not only composites: an `id:<kind>` selector names its source field
        and that field must exist."""

        def mutate(registry: dict) -> None:
            write = write_of(registry, "ak.capability.revoke", "capability_grant")
            assert write["result_selector"]["kind"].startswith("id:")
            write["result_selector"]["field"] = "payload.not_a_field"

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("'payload.not_a_field' has no schema endpoint", reported[0])

    # ---- the canonical_json component rules ------------------------------

    def test_canonical_json_as_a_top_level_selector_kind_is_reported(self) -> None:
        """Ruling 2026-09-05-1200: `canonical_json` has no row in the
        `encoding.md` section 4.1 embedding table, so a top-level use has no
        defined wire id. It is spelled as a one-component composite."""

        def mutate(registry: dict) -> None:
            write = write_of(registry, "ak.member.state", "member_state")
            write["result_selector"] = {
                "kind": "canonical_json",
                "field": "payload.member_id",
            }

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("uses canonical_json as a top-level subject kind", reported[0])

    def test_a_canonical_json_component_over_a_scalar_is_reported(self) -> None:
        """`canonical_json` exists to embed a composite identifier. Over a plain
        string it is a slower spelling of the string itself, and it hides that
        the key is really a single field."""

        def mutate(registry: dict) -> None:
            write = write_of(registry, "ak.member.state", "member_state")
            write["result_selector"]["components"] = [
                {"kind": "canonical_json", "field": "payload.realm_id"}
            ]

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("must be a closed object", reported[0])

    def test_a_canonical_json_component_outside_the_payload_is_reported(self) -> None:
        """`envelope.actor_id` is the one envelope source a selector may embed;
        every other envelope member is assigned at submission and would key the
        result on transport metadata."""

        def mutate(registry: dict) -> None:
            write = write_of(registry, "ak.member.state", "member_state")
            write["result_selector"]["components"] = [
                {"kind": "canonical_json", "field": "envelope.event_id"}
            ]

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn(
            "canonical_json component must name one payload field or envelope.actor_id",
            reported[0],
        )

    # ---- the coalesce and string_set_digest rules -------------------------

    def test_a_coalesce_selector_needs_one_resolvable_candidate(self) -> None:
        """A coalesce descriptor may be shared across payload classes, so a
        candidate that is absent here is legal -- but all of them absent means
        the key is underivable for this kind."""

        def mutate(registry: dict) -> None:
            write = write_of(registry, "ak.member.state", "member_state")
            write["result_selector"] = {
                "kind": "coalesce",
                "fields": ["payload.not_here", "payload.nor_here"],
            }

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("coalesce fields have no schema endpoint", reported[0])

    def test_a_coalesce_selector_passes_on_one_resolvable_candidate(self) -> None:
        def mutate(registry: dict) -> None:
            write = write_of(registry, "ak.member.state", "member_state")
            write["result_selector"] = {
                "kind": "coalesce",
                "fields": ["payload.not_here", "payload.realm_id"],
            }

        self.assertEqual(self._newly_reported(mutate), [])

    def test_a_string_set_digest_component_keeps_its_closed_schema_contract(self) -> None:
        """No live row uses one today. The contract is still enforced, so the
        first row that does gets the check rather than discovering it later.

        An array-only endpoint is the interesting case: the digest normalizes a
        bare string as the one-element set, so `string` alone stays legal, but
        `array` alone means one writer can never produce the singleton form the
        other side may send."""

        def mutate(registry: dict) -> None:
            write = write_of(registry, "ak.member.state", "member_state")
            write["result_selector"]["components"] = [
                {"kind": "string_set_digest", "field": "payload.gate_proofs"}
            ]

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("must be a closed string | array<string> union", reported[0])

    def test_a_typed_pair_component_endpoint_is_resolved(self) -> None:
        """Both halves of a reversible typed-ID pair are validated; slicing the
        tail of the wire form is exactly what `typed_pair` exists to prevent."""

        def mutate(registry: dict) -> None:
            for row in registry["event_kinds"]:
                for write in row.get("result_writes") or ():
                    selector = write.get("result_selector")
                    if isinstance(selector, dict) and selector.get("kind") == "typed_pair":
                        selector["components"][0]["field"] = "payload.not_a_field"
                        return
            raise AssertionError("no typed_pair selector in the registry")

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("'payload.not_a_field' has no schema endpoint", reported[0])


if __name__ == "__main__":
    unittest.main()
