"""Mutation tests for the fixture -> id-kind-registry typed-ID value closure.

The prefix, id_form and payload-form closures all read
``typed_id_validation_documents``, which sweeps ``artifacts/schemas`` and
``artifacts/openapi``. A conformance fixture validates nothing, so it sat
outside every one of them, and a shipped positive vector carried a
content-addressed identifier written as ``<uuidv7>`` -- a wire form the registry
never declared and the repo's own schemas reject. Implementations align to a
vector byte for byte, so an unregistered form in a KAT is worse than a loose
regex: it freezes the wrong value into a published expectation.

Each case below reproduces one shape that failure can take and asserts the value
closure rejects it, asserts the legitimate shapes stay accepted, and holds the
negative-vector exemption path to an exact path plus an exact value so no future
value can opt out by renaming its field.
"""

from __future__ import annotations

import copy
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
EXEMPTIONS = lint_artifacts.FIXTURE_TYPED_ID_EXEMPTION_PATH
SYNTHETIC = FIXTURES / "synthetic-fixture.json"

EVENT_TOKEN = "AZwvW3iEuBDjklBhqPTd1nmetaHgvhyZPMRSw1O0Lo09"
COMMIT_TOKEN = "ARNRmzDi2r78zveOLmoHOb6AephFMwVuGE1fwXmCoeo4"
ZERO_SUITE_COMMIT = "ak:realm_commit:" + "A" * 44
BLAKE3_SUITE_COMMIT = "ak:realm_commit:AhNRmzDi2r78zveOLmoHOb6AephFMwVuGE1fwXmCoeo4"
BLAKE3_SUITE_SNAPSHOT = "ak:realm_snapshot:AhNRmzDi2r78zveOLmoHOb6AephFMwVuGE1fwXmCoeo4"
REGISTERED_COMMIT = f"ak:realm_commit:{COMMIT_TOKEN}"
UNREGISTERED_COMMIT = "ak:realm_commit:01964185-0400-7000-8000-00000000000a"


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

    def test_uuid_shaped_content_addressed_value_is_rejected(self) -> None:
        self._assert_rejected(
            self._run({"cases": [{"value": UNREGISTERED_COMMIT}]}),
            f"ships ak:realm_commit value {UNREGISTERED_COMMIT!r}",
        )

    # --- carrier positions ----------------------------------------------

    def test_object_key_is_inside_the_closure(self) -> None:
        failures = self._run({UNREGISTERED_COMMIT: {"covered": True}})
        self._assert_rejected(
            failures, f"ships ak:realm_commit value {UNREGISTERED_COMMIT!r}"
        )

    def test_embedded_canonical_json_string_is_inside_the_closure(self) -> None:
        # This is the digest preimage shape: an unregistered value can hide
        # inside a preimage even after every standalone copy is corrected.
        preimage = f'ak.commit-tag-v1\nak:event:{EVENT_TOKEN}\n"{UNREGISTERED_COMMIT}"'
        self._assert_rejected(
            self._run({"tag_preimage_utf8": preimage}),
            f"ships ak:realm_commit value {UNREGISTERED_COMMIT!r}",
        )

    def test_unquoted_prose_mention_is_not_a_value(self) -> None:
        self.assertEqual(
            self._run(
                {
                    "note": (
                        "Commit ids follow ak:realm_commit:<44-char-base64url>; "
                        "request a proof for ak:realm_commit:<commit>"
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

    def test_registered_commit_digest_form_is_accepted(self) -> None:
        self.assertEqual(self._run({"value": REGISTERED_COMMIT}), [])

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
                    "negative_cases": [{"invalid_commit_id": UNREGISTERED_COMMIT}],
                    "reject_cases": [{"value": UNREGISTERED_COMMIT}],
                }
            ),
            f"ships ak:realm_commit value {UNREGISTERED_COMMIT!r}",
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
                "value": UNREGISTERED_COMMIT,
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
                "a": UNREGISTERED_COMMIT,
                "b": [f'ctx\nak:event:{EVENT_TOKEN}\n"{REGISTERED_COMMIT}"'],
                UNREGISTERED_COMMIT: 1,
                "c": "ak:realm_commit:",
            }
        )
        self.assertEqual(
            [(pointer, position, segment) for pointer, position, segment, _p, _v in rows],
            [
                ("/a", "value", "realm_commit"),
                ("/b/0", "embedded_json_string", "realm_commit"),
                (f"/{UNREGISTERED_COMMIT}", "object_key", "realm_commit"),
            ],
        )

    def test_registered_value_forms_read_the_registry_and_the_carrier_sweep(self) -> None:
        lint = lint_artifacts.Lint()
        path = ARTIFACTS / "registry" / "id-kind-registry.json"
        registry = lint_artifacts.load_json(lint, path)
        forms = lint_artifacts.registered_typed_id_value_forms(lint, registry, path)
        self.assertEqual(list(lint.errors), [])
        self.assertIn(lint_artifacts.EVENT_TOKEN_PAYLOAD_REGEX, forms["event"])
        self.assertIn(lint_artifacts.PRODUCER_UUID_PAYLOAD_REGEX, forms["blob"])
        self.assertIn("(?:sha256|blake3):[0-9a-f]{64}", forms["blob"])
        self.assertTrue(
            lint_artifacts.payload_matches_registered_form(EVENT_TOKEN, forms["event"])
        )
        self.assertFalse(
            lint_artifacts.payload_matches_registered_form(
                "01964185-0400-7000-8000-00000000000a", forms["realm_commit"]
            )
        )

    # --- positive content addresses carry a registered suite byte ---------

    def test_positive_zero_suite_realm_commit_is_rejected(self) -> None:
        self._assert_rejected(
            self._run(
                {"schema_validation_cases": [{"expect_valid": True, "instance": {"realm_commit_ref": ZERO_SUITE_COMMIT}}]}
            ),
            "digest-suite code 0x00 is not an active row",
        )

    def test_negative_case_zero_suite_realm_commit_stays_out_of_scope(self) -> None:
        for marker in ({"expect_valid": False}, {"semantic_outcome": "reject"}, {"expected_result": "reject_signature_invalid"}):
            with self.subTest(marker=marker):
                self.assertEqual(
                    self._run({"cases": [{**marker, "instance": {"realm_commit_ref": ZERO_SUITE_COMMIT}}]}),
                    [],
                )

    def test_realm_commit_is_pinned_to_the_fixed_v1_suite(self) -> None:
        self._assert_rejected(
            self._run({"value": BLAKE3_SUITE_COMMIT}),
            "this identity is fixed to suite 0x01",
        )

    def test_other_content_address_accepts_any_active_suite(self) -> None:
        self.assertEqual(self._run({"value": BLAKE3_SUITE_SNAPSHOT}), [])


if __name__ == "__main__":
    unittest.main()
