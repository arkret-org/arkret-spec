"""`keyed_set_remove_observed.match` has exactly two spellings, and only two.

The sub-grammar sat in the lint with no registered user and no prose definition
until `ak.agent.key.revoke` landed. It now has both, and it carries a security
obligation that a one-character edit would silently invert:
`identity/key-management.md` section 3.6.1 removes every *active authorize* dot
and keeps every revocation boundary marker, and the only thing standing between
those two sets is `present: true` on `verification_method`.

So the propositions under test are the ones a future edit could break:

* the equality spelling `{element_field, source}` still validates;
* the existence spelling `{element_field, present: true}` validates;
* `present: false` -- the complement, which would delete the markers -- is
  refused;
* a truthy non-boolean in `present` is refused, so no language's truthiness
  rules can smuggle the complement back in;
* the two spellings are exclusive, and naming neither is refused.

Every mutation reads as a delta against the live baseline, so each test keeps
testing its own proposition as coverage grows.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate

REGISTRY = gate.EVENT_KIND_REGISTRY
REVOKE = "ak.agent.key.revoke"


def row_of(registry: dict, kind: str) -> dict:
    for row in registry["event_kinds"]:
        if row["event_kind"] == kind:
            return row
    raise AssertionError(f"{kind} is not a registered Event kind")


def remove_write(registry: dict) -> dict:
    """The one registered `keyed_set_remove_observed` write."""
    for write in row_of(registry, REVOKE)["result_writes"]:
        if write["result_projection"]["kind"] == "keyed_set_remove_observed":
            return write
    raise AssertionError("ak.agent.key.revoke no longer removes observed elements")


class KeyedSetMatchPredicateTest(unittest.TestCase):
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
            gate.check_result_write_contracts(lint)
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

    def test_the_registered_predicate_is_the_existence_form(self) -> None:
        registry = gate.load_json(gate.Lint(), REGISTRY)
        self.assertEqual(
            remove_write(registry)["result_projection"]["match"],
            {"element_field": "verification_method", "present": True},
        )

    # ---- both spellings are accepted ------------------------------------

    def test_the_equality_spelling_validates(self) -> None:
        def mutate(registry: dict) -> None:
            remove_write(registry)["result_projection"]["match"] = {
                "element_field": "key_id",
                "source": "payload.key_id",
            }

        self.assertEqual(self._newly_reported(mutate), [])

    # ---- the complement stays out ---------------------------------------

    def test_present_false_is_refused(self) -> None:
        def mutate(registry: dict) -> None:
            remove_write(registry)["result_projection"]["match"]["present"] = False

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("present may only be true", reported[0])

    def test_a_truthy_non_boolean_is_refused(self) -> None:
        """`if not match["present"]` would let 1, "true" or a non-empty list
        through; identity against True is what keeps the complement out."""
        for value in (1, "true", ["yes"], {"x": 1}):
            with self.subTest(value=value):

                def mutate(registry: dict, value=value) -> None:
                    remove_write(registry)["result_projection"]["match"]["present"] = value

                reported = self._newly_reported(mutate)
                self.assertTrue(
                    any("present may only be true" in message for message in reported), reported
                )

    # ---- the two spellings are exclusive --------------------------------

    def test_both_sources_at_once_are_refused(self) -> None:
        def mutate(registry: dict) -> None:
            remove_write(registry)["result_projection"]["match"]["source"] = "payload.key_id"

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("exactly one of source/present", reported[0])

    def test_naming_neither_source_is_refused(self) -> None:
        def mutate(registry: dict) -> None:
            remove_write(registry)["result_projection"]["match"] = {
                "element_field": "verification_method"
            }

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("exactly one of source/present", reported[0])

    def test_an_unknown_match_member_is_refused(self) -> None:
        def mutate(registry: dict) -> None:
            remove_write(registry)["result_projection"]["match"]["absent"] = True

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("{element_field, source}", reported[0])

    def test_the_element_field_must_be_a_named_path(self) -> None:
        def mutate(registry: dict) -> None:
            remove_write(registry)["result_projection"]["match"]["element_field"] = "items[0]"

        reported = self._newly_reported(mutate)
        self.assertTrue(
            any("element_field" in message for message in reported), reported
        )


if __name__ == "__main__":
    unittest.main()
