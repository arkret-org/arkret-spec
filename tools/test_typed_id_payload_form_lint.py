"""Mutation tests for the typed-ID payload-form closure.

The first two typed-ID closures bind the wire prefix and the id_form direction.
Neither one looked at how tight the payload actually is, so a carrier that was
neither canonical nor inverted still shipped: a bare prefix anchor, a character
class missing the canonical alphabet, a class wide enough to admit unregistered
text, or a length the registry never declared. Each case below reproduces one of
those shapes and asserts the gate rejects it, plus asserts the gate really runs
from the artifact-lint entry point.

The special-form half of the closure is held to the same standard. Every
``special_forms`` row registers ``payload_pattern``, the value space of
everything after its ``ak:<kind>:`` prefix, so an opaque payload can no longer
pick its own alphabet: a carrier may be narrower than the registered space for
one field, but a carrier that admits an octet the registry rejects fails here.
"""

from __future__ import annotations

import copy
import inspect
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import foundation as lint_artifacts
from tools.artifact_lint import runner

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
REGISTRY = ARTIFACTS / "registry" / "id-kind-registry.json"
PROBE = ARTIFACTS / "schemas" / "payload-form-probe.schema.json"

EVENT_TOKEN = lint_artifacts.EVENT_TOKEN_PAYLOAD_REGEX
PRODUCER_UUIDV7 = lint_artifacts.PRODUCER_UUID_PAYLOAD_REGEX


class TypedIdPayloadFormLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.real_documents = lint_artifacts.typed_id_validation_documents
        self.shipped = self.real_documents(lint_artifacts.Lint())

    def tearDown(self) -> None:
        lint_artifacts.typed_id_validation_documents = self.real_documents

    # --- helpers --------------------------------------------------------

    def _run(self, probe: dict[str, Any] | None = None) -> list[str]:
        documents = list(self.shipped)
        if probe is not None:
            documents.append((PROBE, probe))
        lint_artifacts.typed_id_validation_documents = lambda lint: documents
        lint = lint_artifacts.Lint()
        lint_artifacts.check_typed_id_payload_form_closure(lint)
        return list(lint.errors)

    def _pattern(self, pattern: str) -> list[str]:
        return self._run({"type": "string", "pattern": pattern})

    def _assert_rejected(self, failures: list[str], fragment: str) -> None:
        self.assertTrue(
            any(fragment in failure for failure in failures), failures
        )

    def _shipped_registry(self) -> dict[str, Any]:
        lint = lint_artifacts.Lint()
        registry = lint_artifacts.load_json(lint, REGISTRY)
        self.assertEqual(list(lint.errors), [])
        return copy.deepcopy(registry)

    def _special_row(self, registry: dict[str, Any], kind: str) -> dict[str, Any]:
        for row in registry["special_forms"]:
            if row.get("kind") == kind:
                return row
        raise AssertionError(f"{kind} is not a registered special form")

    def _contract_failures(self, registry: dict[str, Any]) -> list[str]:
        lint = lint_artifacts.Lint()
        lint_artifacts.registry_special_form_payload_contracts(lint, registry, REGISTRY)
        return list(lint.errors)

    # --- committed tree -------------------------------------------------

    def test_committed_artifacts_pass(self) -> None:
        self.assertEqual(self._run(), [])

    def test_gate_runs_from_the_artifact_lint_entry_point(self) -> None:
        self.assertIs(
            runner.check_typed_id_payload_form_closure,
            lint_artifacts.check_typed_id_payload_form_closure,
        )
        source = inspect.getsource(runner.main)
        self.assertIn("check_typed_id_payload_form_closure(lint)", source)

    # --- bare prefix anchors --------------------------------------------

    def test_bare_prefix_anchor_on_an_id_kind_is_rejected(self) -> None:
        self._assert_rejected(
            self._pattern("^ak:event:"),
            "validates ak:event with an unterminated payload",
        )

    def test_bare_prefix_anchor_on_a_special_form_is_rejected(self) -> None:
        self._assert_rejected(
            self._pattern("^ak:cursor:"),
            "validates ak:cursor with an unterminated payload",
        )

    def test_unterminated_special_form_branch_is_rejected(self) -> None:
        # The digest suite is pinned but the digest segment is not terminated,
        # so every trailing byte is still accepted.
        self._assert_rejected(
            self._pattern(r"^ak:blob:sha256:"),
            "validates ak:blob with an unterminated payload",
        )

    # --- character class defects ----------------------------------------

    def test_payload_missing_the_canonical_alphabet_is_rejected(self) -> None:
        # Lowercase hex plus hyphen cannot spell a canonical Event token, so the
        # carrier rejects 100% of valid values instead of merely widening them.
        self._assert_rejected(
            self._pattern("^ak:event:[0-9a-f-]+:[0-9]+$"),
            "wider than or disjoint from the registered wire form",
        )

    def test_payload_wider_than_the_producer_uuid_is_rejected(self) -> None:
        self._assert_rejected(
            self._pattern("^ak:applet:[0-9a-f-]+$"),
            "validates ak:applet with payload",
        )

    def test_special_form_payload_losing_a_registered_segment_is_rejected(self) -> None:
        # ak:blob: is registered as the two-segment digest form, so a single
        # flat character class collapses the suite and digest segments.
        self._assert_rejected(
            self._pattern("^ak:blob:[A-Za-z0-9._:-]+$"),
            "validates ak:blob with payload",
        )

    def test_content_addressed_kind_written_as_a_uuid_is_rejected(self) -> None:
        self._assert_rejected(
            self._pattern(f"^ak:signer_evidence:{PRODUCER_UUIDV7}$"),
            "validates ak:signer_evidence with payload",
        )

    # --- length defects --------------------------------------------------

    def test_payload_length_the_registry_never_declared_is_rejected(self) -> None:
        self._assert_rejected(
            self._pattern("^ak:request:[0-9a-f-]{36}$"),
            "validates ak:request with payload",
        )

    def test_truncated_event_token_length_is_rejected(self) -> None:
        self._assert_rejected(
            self._pattern("^ak:realm:[A-Za-z0-9_-]{43}$"),
            "validates ak:realm with payload",
        )

    # --- carrier positions ----------------------------------------------

    def test_pattern_properties_key_is_inside_the_closure(self) -> None:
        failures = self._run(
            {
                "type": "object",
                "patternProperties": {"^ak:realm:[0-9a-f-]+$": {"type": "object"}},
            }
        )
        self._assert_rejected(failures, "validates ak:realm with payload")
        self._assert_rejected(failures, "patternProperties[^ak:realm:[0-9a-f-]+$]")

    def test_pattern_properties_key_is_inside_the_prefix_closure(self) -> None:
        # The prefix closure reads the same carrier sweep, so an unregistered
        # prefix cannot hide in an object key either.
        documents = list(self.shipped) + [
            (
                PROBE,
                {
                    "type": "object",
                    "patternProperties": {
                        f"^ak:evt:{EVENT_TOKEN}$": {"type": "object"}
                    },
                },
            )
        ]
        lint_artifacts.typed_id_validation_documents = lambda lint: documents
        lint = lint_artifacts.Lint()
        lint_artifacts.check_typed_id_prefix_registry_closure(lint)
        self._assert_rejected(
            list(lint.errors), "accepts unregistered typed ID prefix 'ak:evt:'"
        )

    def test_one_polluted_union_branch_is_rejected_alone(self) -> None:
        failures = self._pattern(
            f"^(ak:(realm|space):{EVENT_TOKEN}|ak:view:[0-9a-f-]+)$"
        )
        self._assert_rejected(failures, "validates ak:view with payload")
        self.assertFalse(
            any("ak:realm with payload" in failure for failure in failures), failures
        )
        self.assertFalse(
            any("ak:space with payload" in failure for failure in failures), failures
        )

    # --- canonical carriers stay accepted --------------------------------

    def test_canonical_composite_event_position_is_accepted(self) -> None:
        self.assertEqual(self._pattern(f"^ak:event:{EVENT_TOKEN}:[0-9]+$"), [])

    def test_canonical_blob_forms_are_accepted(self) -> None:
        self.assertEqual(
            self._pattern(
                f"^ak:blob:(?:{PRODUCER_UUIDV7}|(?:sha256|blake3):[0-9a-f]{{64}})$"
            ),
            [],
        )

    # --- registry is the single source ------------------------------------

    def test_canonical_payload_regexes_are_read_from_the_registry(self) -> None:
        lint = lint_artifacts.Lint()
        path = ARTIFACTS / "registry" / "id-kind-registry.json"
        registry = lint_artifacts.load_json(lint, path)
        self.assertEqual(
            lint_artifacts.registry_canonical_payload_regex(lint, registry, path),
            {
                "event_derived": EVENT_TOKEN,
                "suite_tagged_full_digest": EVENT_TOKEN,
                "producer_allocated": PRODUCER_UUIDV7,
            },
        )
        self.assertEqual(list(lint.errors), [])

    def test_registry_payload_regex_drift_is_rejected(self) -> None:
        lint = lint_artifacts.Lint()
        path = ARTIFACTS / "registry" / "id-kind-registry.json"
        registry = dict(lint_artifacts.load_json(lint, path))
        registry["event_token_pattern"] = "^[0-9a-f-]{44}$"
        lint_artifacts.registry_canonical_payload_regex(lint, registry, path)
        self._assert_rejected(list(lint.errors), "MUST stay one value")

    # --- payload segment counting ----------------------------------------

    def test_segment_count_ignores_colons_that_cannot_separate(self) -> None:
        self.assertEqual(lint_artifacts.regex_payload_segments("[A-Za-z0-9._:-]+"), 1)
        self.assertEqual(
            lint_artifacts.regex_payload_segments("(?:sha256|blake3):[0-9a-f]{64}"), 2
        )
        self.assertEqual(
            lint_artifacts.regex_payload_segments(r"[a-z0-9]+:[^\s/?#]+"), 2
        )

    # --- registered special-form alphabets -------------------------------

    def test_special_form_payload_wider_than_the_registered_alphabet_is_rejected(
        self,
    ) -> None:
        # '.' admits spaces, control bytes, ':' and every Unicode code point the
        # registered base64url cursor token never had.
        self._assert_rejected(
            self._pattern("^ak:cursor:.+$"), "validates ak:cursor with payload"
        )

    def test_special_form_payload_admitting_one_extra_character_is_rejected(
        self,
    ) -> None:
        self._assert_rejected(
            self._pattern("^ak:cursor:[A-Za-z0-9_:-]+$"),
            "validates ak:cursor with payload",
        )

    def test_special_form_payload_disjoint_from_the_registered_alphabet_is_rejected(
        self,
    ) -> None:
        # A percent-encoded token is not a base64url token; '%' is registered for
        # no cursor value at all.
        self._assert_rejected(
            self._pattern("^ak:cursor:(?:%[0-9A-Fa-f]{2})+$"),
            "validates ak:cursor with payload",
        )

    def test_correct_segment_count_with_the_wrong_alphabet_is_rejected(self) -> None:
        # Two ':' segments is exactly what ak:mls: declares, so the segment rule
        # alone accepted this; only the registered alphabet rejects it.
        payload = "[a-z0-9_]+:.+"
        self.assertEqual(
            lint_artifacts.regex_payload_segments(payload),
            lint_artifacts.wire_form_payload_segments("<profile>:<profile_id>"),
        )
        self._assert_rejected(
            self._pattern(f"^ak:mls:{payload}$"), "validates ak:mls with payload"
        )

    def test_special_form_payload_narrower_than_the_registry_is_accepted(self) -> None:
        # A frame may bound a cursor and a DTO may pin one digest suite; neither
        # admits anything the registry rejects.
        self.assertEqual(self._pattern("^ak:cursor:[A-Za-z0-9_-]{1,2028}$"), [])
        self.assertEqual(self._pattern("^ak:blob:sha256:[0-9a-f]{64}$"), [])
        self.assertEqual(self._pattern("^ak:mls:[a-z0-9_]+:[A-Za-z0-9._:-]+$"), [])

    # --- registry declares the alphabet -----------------------------------

    def test_every_special_form_registers_a_payload_pattern(self) -> None:
        registry = self._shipped_registry()
        lint = lint_artifacts.Lint()
        contracts = lint_artifacts.registry_special_form_payload_contracts(
            lint, registry, REGISTRY
        )
        self.assertEqual(list(lint.errors), [])
        self.assertEqual(
            sorted(contracts),
            sorted(row["kind"] for row in registry["special_forms"]),
        )

    def test_special_form_without_a_payload_pattern_is_rejected(self) -> None:
        registry = self._shipped_registry()
        del self._special_row(registry, "cursor")["payload_pattern"]
        self._assert_rejected(
            self._contract_failures(registry),
            "special_forms[cursor] must declare payload_pattern",
        )

    def test_payload_pattern_losing_a_wire_form_segment_is_rejected(self) -> None:
        registry = self._shipped_registry()
        self._special_row(registry, "blob")["payload_pattern"] = "[0-9a-f]{64}"
        self._assert_rejected(
            self._contract_failures(registry),
            "carries fewer ':' segments than wire_form",
        )

    def test_digest_suite_payload_pattern_drift_is_rejected(self) -> None:
        # Pinning one suite in the registry is exactly the drift that would make
        # the blob wire form contradict digest-suite-registry.json.
        registry = self._shipped_registry()
        self._special_row(registry, "blob")["payload_pattern"] = "sha256:[0-9a-f]{64}"
        self._assert_rejected(
            self._contract_failures(registry),
            "MUST spell the active suites registered in digest-suite-registry.json",
        )

    def test_blob_uses_the_active_digest_suite_value_space(self) -> None:
        registry = self._shipped_registry()
        lint = lint_artifacts.Lint()
        expected = lint_artifacts.active_digest_suite_payload_regex(lint)
        self.assertEqual(list(lint.errors), [])
        self.assertEqual(expected, "(?:sha256|blake3):[0-9a-f]{64}")
        row = self._special_row(registry, "blob")
        self.assertEqual(row["wire_form"], "ak:blob:<digest-suite>:<digest>")
        self.assertEqual(row["payload_pattern"], expected)

    # --- payload alphabet reading ------------------------------------------

    def test_payload_charset_containment(self) -> None:
        charset = lint_artifacts.regex_payload_charset
        contains = lint_artifacts.payload_charset_contains
        base64url = charset("[A-Za-z0-9_-]+")
        self.assertTrue(contains(base64url, charset("[A-Za-z0-9_-]{1,2028}")))
        self.assertFalse(contains(base64url, charset(".+")))
        self.assertFalse(contains(base64url, charset("[A-Za-z0-9_:-]+")))
        # Group syntax, alternation bars, quantifiers and anchors are structure,
        # not content, so they contribute no characters.
        self.assertTrue(
            contains(
                charset("(?:sha256|blake3):[0-9a-f]{64}"),
                charset("sha256:[0-9a-f]{64}"),
            )
        )
        # A negated class stays exact instead of collapsing to "anything".
        self.assertTrue(contains(charset(r"[^\s/?#]+"), charset("[a-z0-9]+")))
        self.assertFalse(contains(charset("[a-z0-9]+"), charset(r"[^\s/?#]+")))

    def test_wire_form_segment_count_ignores_placeholder_text(self) -> None:
        self.assertEqual(
            lint_artifacts.wire_form_payload_segments("<digest-suite>:<digest>"), 2
        )
        self.assertEqual(
            lint_artifacts.wire_form_payload_segments("<profile>:<profile_id>"),
            2,
        )
        self.assertEqual(lint_artifacts.wire_form_payload_segments("<base64url>"), 1)


if __name__ == "__main__":
    unittest.main()
