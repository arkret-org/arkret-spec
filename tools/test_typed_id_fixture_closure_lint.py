"""Mutation tests for the fixture -> id-kind-registry typed-ID value closure.

The prefix, id_form and payload-form closures all read
``typed_id_validation_documents``, which sweeps ``artifacts/schemas`` and
``artifacts/openapi``. A conformance fixture validates nothing, so it sat
outside every one of them, and a shipped positive vector carried
``ak:seal:<uuidv7>`` -- a wire form the registry never declared and the repo's
own schemas reject -- with two ``batch_tag`` digests computed over exactly those
bytes. Implementations align to a vector byte for byte, so an unregistered form
in a KAT is worse than a loose regex: it freezes the wrong value into a
published expectation.

Each case below reproduces one shape that failure can take and asserts the value
closure rejects it, asserts the legitimate shapes stay accepted, and holds the
negative-vector exemption path to an exact path plus an exact value so no future
value can opt out by renaming its field.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import inspect
import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import foundation as lint_artifacts
from tools.artifact_lint import runner

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
FIXTURES = ARTIFACTS / "fixtures"
ENCODING_FIXTURE = FIXTURES / "encoding-fixture.json"
EXEMPTIONS = lint_artifacts.FIXTURE_TYPED_ID_EXEMPTION_PATH
SYNTHETIC = FIXTURES / "synthetic-fixture.json"

EVENT_TOKEN = "AZwvW3iEuBDjklBhqPTd1nmetaHgvhyZPMRSw1O0Lo09"
REGISTERED_SEAL = "ak:seal:sha256:" + "a" * 64
UNREGISTERED_SEAL = "ak:seal:01964185-0400-7000-8000-00000000000a"
OR_SET_DOT = f"ak:event:{EVENT_TOKEN}:0"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class TypedIdFixtureClosureLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.real_documents = lint_artifacts.typed_id_value_documents
        self.real_load_json = lint_artifacts.load_json
        self.shipped = self.real_documents(lint_artifacts.Lint())

    def tearDown(self) -> None:
        lint_artifacts.typed_id_value_documents = self.real_documents
        lint_artifacts.load_json = self.real_load_json

    # --- helpers --------------------------------------------------------

    def _run(
        self,
        probe: Any = None,
        *,
        exemptions: dict[str, Any] | None = None,
    ) -> list[str]:
        documents = list(self.shipped)
        if probe is not None:
            documents.append((SYNTHETIC, probe))
        lint_artifacts.typed_id_value_documents = lambda lint: documents
        if exemptions is not None:

            def fake_load_json(lint: Any, path: Path) -> Any:
                if path == EXEMPTIONS:
                    return exemptions
                return self.real_load_json(lint, path)

            lint_artifacts.load_json = fake_load_json
        lint = lint_artifacts.Lint()
        lint_artifacts.check_typed_id_fixture_value_closure(lint)
        return list(lint.errors)

    def _assert_rejected(self, failures: list[str], fragment: str) -> None:
        self.assertTrue(any(fragment in failure for failure in failures), failures)

    def _shipped_exemptions(self) -> dict[str, Any]:
        return copy.deepcopy(_load(EXEMPTIONS))

    def _or_set_vector(self) -> dict[str, Any]:
        for vector in _load(ENCODING_FIXTURE)["vectors"]:
            if vector.get("vector_id") == "ak.vector.encoding.or_set_dot_and_batch_tag.v1":
                return vector
        raise AssertionError("or_set_dot_and_batch_tag vector is missing")

    # --- committed tree -------------------------------------------------

    def test_committed_fixtures_pass(self) -> None:
        self.assertEqual(self._run(), [])

    def test_gate_runs_from_the_artifact_lint_entry_point(self) -> None:
        self.assertIs(
            runner.check_typed_id_fixture_value_closure,
            lint_artifacts.check_typed_id_fixture_value_closure,
        )
        self.assertIn(
            "check_typed_id_fixture_value_closure(lint)",
            inspect.getsource(runner.main),
        )

    # --- the regression this closure exists for --------------------------

    def test_uuid_shaped_seal_value_is_rejected(self) -> None:
        self._assert_rejected(
            self._run({"cases": [{"value": UNREGISTERED_SEAL}]}),
            f"ships ak:seal value {UNREGISTERED_SEAL!r}",
        )

    def test_or_set_batch_tags_are_digests_of_the_registered_values(self) -> None:
        # The vector's own definition: batch_tag =
        # base64url_nopad(sha256(tag_context || 0x0A || dot || 0x0A ||
        # canonical_json(value))). Recomputing it here binds the published digest
        # to the published value, so correcting one without the other fails.
        vector = self._or_set_vector()
        batch_add = vector["batch_add"]
        values = [case["value"] for case in batch_add["cases"]]
        self.assertEqual(values, batch_add["sorted_values"])
        self.assertEqual(values, sorted(values))
        for case in batch_add["cases"]:
            canonical = json.dumps(case["value"], ensure_ascii=False, separators=(",", ":"))
            preimage = f"{batch_add['tag_context']}\n{batch_add['dot']}\n{canonical}"
            self.assertEqual(case["tag_preimage_utf8"], preimage)
            self.assertEqual(
                case["batch_tag"],
                base64.urlsafe_b64encode(
                    hashlib.sha256(preimage.encode("utf-8")).digest()
                ).decode("ascii").rstrip("="),
            )

    # --- carrier positions ----------------------------------------------

    def test_object_key_is_inside_the_closure(self) -> None:
        failures = self._run({UNREGISTERED_SEAL: {"covered": True}})
        self._assert_rejected(failures, f"ships ak:seal value {UNREGISTERED_SEAL!r}")

    def test_embedded_canonical_json_string_is_inside_the_closure(self) -> None:
        # This is the digest preimage shape: an unregistered value can hide
        # inside a preimage even after every standalone copy is corrected.
        preimage = f'ak.covered-seal-tag-v1\n{OR_SET_DOT}\n"{UNREGISTERED_SEAL}"'
        self._assert_rejected(
            self._run({"tag_preimage_utf8": preimage}),
            f"ships ak:seal value {UNREGISTERED_SEAL!r}",
        )

    def test_unquoted_prose_mention_is_not_a_value(self) -> None:
        self.assertEqual(
            self._run(
                {
                    "note": (
                        "Cell ids follow ak:cell:ak.component.<facet-path>.v<n>:<subject>; "
                        "request a proof for ak:cell:ak.component.member.state.v1"
                    )
                }
            ),
            [],
        )

    def test_bare_prefix_without_a_payload_is_not_a_value(self) -> None:
        # A prefix with nothing after it names a prefix, not an identifier:
        # forbidden_identity_surfaces lists ak:signal: precisely to keep it
        # unminted, and a preimage description spells "ak:event:" as a
        # concatenation operand.
        self.assertEqual(
            self._run(
                {
                    "forbidden_identity_surfaces": ["ak:signal:"],
                    "description": 'dot = "ak:event:" + event_id + ":" + write_index',
                }
            ),
            [],
        )

    def test_regex_carried_inside_a_fixture_is_not_a_value(self) -> None:
        self.assertEqual(
            self._run({"schema": {"pattern": "^ak:realm:[A-Za-z0-9_-]{44}$"}}), []
        )

    # --- registered forms stay accepted -----------------------------------

    def test_registered_seal_digest_form_is_accepted(self) -> None:
        self.assertEqual(self._run({"value": REGISTERED_SEAL}), [])

    def test_canonical_or_set_dot_is_accepted(self) -> None:
        # The dot is a registered composite carrier; the value closure reads the
        # same swept schema branches the payload-form closure holds to the
        # registry, so it needs no restated wire form of its own.
        self.assertEqual(self._run({"tag": OR_SET_DOT}), [])

    def test_both_registered_blob_forms_are_accepted(self) -> None:
        self.assertEqual(
            self._run(
                {
                    "metadata_row": "ak:blob:0110c853-1d09-7044-b214-c74240110c85",
                    "content_addressed": "ak:blob:sha256:" + "c" * 64,
                }
            ),
            [],
        )

    def test_typed_id_used_as_a_map_key_is_accepted(self) -> None:
        self.assertEqual(
            self._run({"realms": {f"ak:realm:{EVENT_TOKEN}": {"epoch": 1}}}), []
        )

    # --- prefix direction --------------------------------------------------

    def test_unregistered_prefix_carrying_a_payload_is_rejected(self) -> None:
        self._assert_rejected(
            self._run({"id": "ak:not_a_registered_kind:abc"}),
            "ships unregistered typed ID prefix 'ak:not_a_registered_kind:'",
        )

    # --- the exemption registry is the only opt-out ------------------------

    def test_field_name_alone_does_not_exempt_a_negative_value(self) -> None:
        self._assert_rejected(
            self._run(
                {
                    "negative_cases": [{"invalid_seal_id": UNREGISTERED_SEAL}],
                    "reject_cases": [{"value": UNREGISTERED_SEAL}],
                }
            ),
            f"ships ak:seal value {UNREGISTERED_SEAL!r}",
        )

    def test_exemption_is_pinned_to_the_exact_value(self) -> None:
        exemptions = self._shipped_exemptions()
        for entry in exemptions["entries"]:
            if entry["pointer"].startswith("cursor-negative-fixture.json#"):
                entry["value"] = "ak:cursor:some-other-token"
        failures = self._run(exemptions=exemptions)
        self._assert_rejected(failures, "ships ak:cursor value 'ak:cursor:!!!not-base64url!!!'")
        self._assert_rejected(failures, "stale fixture typed ID exemption")

    def test_exemption_is_pinned_to_the_exact_path(self) -> None:
        exemptions = self._shipped_exemptions()
        for entry in exemptions["entries"]:
            if entry["pointer"].startswith("cursor-negative-fixture.json#"):
                entry["pointer"] = "cursor-negative-fixture.json#/vectors/0/cases/0/input_cursor"
        failures = self._run(exemptions=exemptions)
        self._assert_rejected(failures, "ships ak:cursor value 'ak:cursor:!!!not-base64url!!!'")

    def test_exemption_with_an_unknown_category_is_rejected(self) -> None:
        exemptions = self._shipped_exemptions()
        exemptions["entries"][0]["category"] = "looks_fine_to_me"
        self._assert_rejected(
            self._run(exemptions=exemptions), "unknown category 'looks_fine_to_me'"
        )

    def test_exemption_without_a_reason_is_rejected(self) -> None:
        exemptions = self._shipped_exemptions()
        exemptions["entries"][0]["reason"] = "   "
        self._assert_rejected(
            self._run(exemptions=exemptions), "reason must be a non-empty string"
        )

    def test_exemption_naming_a_file_that_is_not_a_fixture_is_rejected(self) -> None:
        exemptions = self._shipped_exemptions()
        exemptions["entries"][0]["pointer"] = "not-a-fixture.json#/cases/0/value"
        self._assert_rejected(
            self._run(exemptions=exemptions), "names a file that is not a shipped fixture"
        )

    def test_exemption_with_an_unknown_position_is_rejected(self) -> None:
        exemptions = self._shipped_exemptions()
        exemptions["entries"][0]["position"] = "somewhere"
        self._assert_rejected(self._run(exemptions=exemptions), "position must be one of")

    def test_duplicate_exemption_is_rejected(self) -> None:
        exemptions = self._shipped_exemptions()
        exemptions["entries"].append(copy.deepcopy(exemptions["entries"][0]))
        self._assert_rejected(self._run(exemptions=exemptions), "duplicate exemption for")

    def test_stale_exemption_is_rejected(self) -> None:
        exemptions = self._shipped_exemptions()
        exemptions["entries"].append(
            {
                "pointer": "encoding-fixture.json#/vectors/0/nothing_here",
                "position": "value",
                "value": UNREGISTERED_SEAL,
                "category": "deliberate_negative_vector",
                "reason": "n/a",
            }
        )
        self._assert_rejected(self._run(exemptions=exemptions), "stale fixture typed ID exemption")

    def test_every_shipped_exemption_is_still_needed(self) -> None:
        # A registered exemption that no longer matches a failing occurrence is
        # reported as stale by the committed-tree run, so the shipped registry
        # carries no dead rows.
        registry = _load(EXEMPTIONS)
        self.assertTrue(registry["entries"])
        self.assertEqual(self._run(), [])

    # --- occurrence extraction --------------------------------------------

    def test_value_occurrence_rows(self) -> None:
        rows = lint_artifacts.typed_id_fixture_value_rows(
            {
                "a": UNREGISTERED_SEAL,
                "b": [f'ctx\n{OR_SET_DOT}\n"{REGISTERED_SEAL}"'],
                UNREGISTERED_SEAL: 1,
                "c": "ak:seal:",
            }
        )
        self.assertEqual(
            [(pointer, position, segment) for pointer, position, segment, _p, _v in rows],
            [
                ("/a", "value", "seal"),
                ("/b/0", "embedded_json_string", "seal"),
                (f"/{UNREGISTERED_SEAL}", "object_key", "seal"),
            ],
        )

    def test_registered_value_forms_read_the_registry_and_the_carrier_sweep(self) -> None:
        lint = lint_artifacts.Lint()
        path = ARTIFACTS / "registry" / "id-kind-registry.json"
        registry = lint_artifacts.load_json(lint, path)
        forms = lint_artifacts.registered_typed_id_value_forms(lint, registry, path)
        self.assertEqual(list(lint.errors), [])
        self.assertIn(lint_artifacts.EVENT_TOKEN_PAYLOAD_REGEX, forms["event"])
        self.assertIn("(?:sha256|blake3):[0-9a-f]{64}", forms["seal"])
        self.assertIn(lint_artifacts.PRODUCER_UUID_PAYLOAD_REGEX, forms["blob"])
        self.assertIn("(?:sha256|blake3):[0-9a-f]{64}", forms["blob"])
        self.assertTrue(
            lint_artifacts.payload_matches_registered_form(
                f"{EVENT_TOKEN}:0", forms["event"]
            )
        )
        self.assertFalse(
            lint_artifacts.payload_matches_registered_form(
                "01964185-0400-7000-8000-00000000000a", forms["seal"]
            )
        )


if __name__ == "__main__":
    unittest.main()
