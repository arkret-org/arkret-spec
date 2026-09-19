"""Mutation tests for Realm join locator carriers, bounds, and identity."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate
from tools.artifact_lint.core import Lint


SCHEMA_NAMES = {
    "intake": "realm-join-intake.schema.json",
    "invite_request": "invite-delivery-request.schema.json",
    "invite_delivery": "invite-delivery.schema.json",
    "directory": "directory-operations.schema.json",
}
FIXTURE = ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "realm-join-candidate-locator-fixture.json"


def _locator(service_id: str, *, source: str = "directory", endpoint: str | None = None) -> dict:
    value = {
        "service_kind": "station",
        "service_id": service_id,
        "source": source,
    }
    if endpoint is not None:
        value["endpoint_url"] = endpoint
    return value


class RealmJoinLocatorCarriersGateTest(unittest.TestCase):
    def setUp(self) -> None:
        schema_dir = ROOT / "spec" / "v1" / "artifacts" / "schemas"
        self.documents = {
            key: json.loads((schema_dir / name).read_text(encoding="utf-8"))
            for key, name in SCHEMA_NAMES.items()
        }
        self.documents["fixture"] = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def errors_after(self, mutate) -> list[str]:
        documents = copy.deepcopy(self.documents)
        mutate(documents)
        with tempfile.TemporaryDirectory() as directory:
            artifacts = Path(directory) / "artifacts"
            schemas = artifacts / "schemas"
            fixtures = artifacts / "fixtures"
            schemas.mkdir(parents=True)
            fixtures.mkdir(parents=True)
            paths = {
                key: schemas / name for key, name in SCHEMA_NAMES.items()
            }
            paths["fixture"] = fixtures / FIXTURE.name
            for name, path in paths.items():
                path.write_text(json.dumps(documents[name]), encoding="utf-8", newline="\n")
            lint = Lint()
            with (
                mock.patch.object(gate, "REALM_JOIN_INTAKE_SCHEMA", paths["intake"]),
                mock.patch.object(gate, "INVITE_DELIVERY_REQUEST_SCHEMA", paths["invite_request"]),
                mock.patch.object(gate, "INVITE_DELIVERY_SCHEMA", paths["invite_delivery"]),
                mock.patch.object(gate, "DIRECTORY_OPERATIONS_SCHEMA", paths["directory"]),
                mock.patch.object(gate, "REALM_JOIN_CANDIDATE_FIXTURE", paths["fixture"]),
            ):
                gate.check_realm_join_locator_carriers_and_bounds(lint)
            return lint.errors

    def assert_red(self, mutate, phrase: str) -> None:
        errors = self.errors_after(mutate)
        self.assertTrue(any(phrase in error for error in errors), errors)

    def test_shipped_contract_passes(self) -> None:
        self.assertEqual(self.errors_after(lambda _: None), [])

    def test_private_intake_hint_definition_cannot_return(self) -> None:
        self.assert_red(
            lambda d: d["intake"]["$defs"].__setitem__("authority_locator_hint", {}),
            "$defs.authority_locator_hint must not exist",
        )

    def test_every_surface_directly_refs_canonical_core(self) -> None:
        mutations = (
            lambda d: d["intake"]["$defs"]["join_target"]["properties"]["authority_locator_hints"]["items"].__setitem__("$ref", "#/$defs/authority_locator_hint"),
            lambda d: d["invite_request"]["properties"]["authority_locator_hints"]["items"].__setitem__("$ref", "./realm-join-intake.schema.json"),
            lambda d: d["invite_delivery"]["$defs"]["delivery_entry"]["properties"]["authority_locator_hints"]["items"].__setitem__("$ref", "./other.schema.json"),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.assert_red(mutate, "directly referencing")

    def test_directory_three_carriers_directly_ref_canonical_core(self) -> None:
        for definition in (
            "realm_preview",
            "directory_realm_resolution_outcome",
            "directory_target_resolution_outcome",
        ):
            with self.subTest(definition=definition):
                self.assert_red(
                    lambda d, definition=definition: d["directory"]["$defs"][definition]["properties"]["join_candidates"]["items"].__setitem__("$ref", "./other.schema.json"),
                    "directly referencing",
                )

    def test_directory_three_carriers_require_minimum_one(self) -> None:
        for definition in (
            "realm_preview",
            "directory_realm_resolution_outcome",
            "directory_target_resolution_outcome",
        ):
            with self.subTest(definition=definition):
                self.assert_red(
                    lambda d, definition=definition: d["directory"]["$defs"][definition]["properties"]["join_candidates"].pop("minItems"),
                    "must be a 1..8",
                )

    def test_directory_three_carriers_cap_at_eight(self) -> None:
        for definition in (
            "realm_preview",
            "directory_realm_resolution_outcome",
            "directory_target_resolution_outcome",
        ):
            with self.subTest(definition=definition):
                self.assert_red(
                    lambda d, definition=definition: d["directory"]["$defs"][definition]["properties"]["join_candidates"].__setitem__("maxItems", 9),
                    "must be a 1..8",
                )

    def test_all_arrays_keep_unique_items_schema_floor(self) -> None:
        self.assert_red(
            lambda d: d["invite_request"]["properties"]["authority_locator_hints"].pop("uniqueItems"),
            "must be a 1..8",
        )

    def test_directory_disclosure_field_stays_optional(self) -> None:
        self.assertEqual(self.errors_after(lambda _: None), [])
        self.assert_red(
            lambda d: d["directory"]["$defs"]["realm_preview"]["required"].append("join_candidates"),
            "optional for disclosure",
        )

    def test_invite_and_intake_carriers_stay_required(self) -> None:
        mutations = (
            lambda d: d["intake"]["$defs"]["join_target"]["required"].remove("authority_locator_hints"),
            lambda d: d["invite_request"]["required"].remove("authority_locator_hints"),
            lambda d: d["invite_delivery"]["$defs"]["delivery_entry"]["required"].remove("authority_locator_hints"),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.assert_red(mutate, "must remain required")

    def test_explicit_empty_array_fails_but_directory_omission_passes(self) -> None:
        self.assertEqual(gate.realm_join_locator_array_errors([]), ["locator array item count must be within 1..8"])
        self.assertNotIn(
            "join_candidates",
            self.documents["directory"]["$defs"]["realm_preview"]["required"],
        )

    def test_exact_duplicate_cannot_hide_behind_unique_items(self) -> None:
        candidate = _locator("ak:did_core:webvh:z1111111111111111111111111")
        errors = gate.realm_join_locator_array_errors([candidate, copy.deepcopy(candidate)])
        self.assertTrue(any("duplicates semantic service_id" in error for error in errors), errors)

    def test_same_service_different_source_is_rejected_as_a_group(self) -> None:
        service_id = "ak:did_core:webvh:z1111111111111111111111111"
        errors = gate.realm_join_locator_array_errors([
            _locator(service_id, source="invite"),
            _locator(service_id, source="cache"),
        ])
        self.assertTrue(any("duplicates semantic service_id" in error for error in errors), errors)

    def test_same_service_different_or_missing_endpoint_is_rejected(self) -> None:
        service_id = "ak:did_core:webvh:z1111111111111111111111111"
        for second in (
            _locator(service_id, endpoint="https://b.example"),
            _locator(service_id),
        ):
            with self.subTest(second=second):
                errors = gate.realm_join_locator_array_errors([
                    _locator(service_id, endpoint="https://a.example"),
                    second,
                ])
                self.assertTrue(any("duplicates semantic service_id" in error for error in errors), errors)

    def test_reverse_service_id_order_is_rejected(self) -> None:
        errors = gate.realm_join_locator_array_errors([
            _locator("ak:did_core:webvh:z2222222222222222222222222"),
            _locator("ak:did_core:webvh:z1111111111111111111111111"),
        ])
        self.assertTrue(any("UTF-8 bytes" in error for error in errors), errors)

    def test_locale_endpoint_and_source_order_cannot_replace_bytewise_id_order(self) -> None:
        cases = (
            [
                _locator("ak:did_core:webvh:zaaaaaaaaaaaaaaaaaaaaaaaaa", endpoint="https://a.example"),
                _locator("ak:did_core:webvh:zBBBBBBBBBBBBBBBBBBBBBBBBB", endpoint="https://z.example"),
            ],
            [
                _locator("ak:did_core:webvh:z2222222222222222222222222", source="cache", endpoint="https://a.example"),
                _locator("ak:did_core:webvh:z1111111111111111111111111", source="invite", endpoint="https://z.example"),
            ],
        )
        for value in cases:
            with self.subTest(value=value):
                self.assertTrue(gate.realm_join_locator_array_errors(value))

    def test_array_description_registers_non_schema_semantics(self) -> None:
        self.assert_red(
            lambda d: d["intake"]["$defs"]["join_target"]["properties"]["authority_locator_hints"].__setitem__("description", "Some locators."),
            "must register bytewise ordering",
        )

    def test_fixture_contract_cannot_move_freshness_into_locator(self) -> None:
        self.assert_red(
            lambda d: d["fixture"]["freshness_contract"].__setitem__("locator_specific_ttl_or_skew", True),
            "freshness_contract",
        )

    def test_weak_freshness_signals_cannot_become_authority(self) -> None:
        for name in (
            "directory_stale_false_only",
            "invite_unexpired_only",
            "endpoint_reachable_only",
        ):
            with self.subTest(name=name):
                self.assert_red(
                    lambda d, name=name: next(row for row in d["fixture"]["authority_assertion_cases"] if row["name"] == name).__setitem__("expected", "accept_current_authority"),
                    "authority_assertion_cases",
                )

    def test_missing_expired_or_nonce_mismatched_assertion_rejects_join(self) -> None:
        for name in (
            "current_assertion_missing",
            "current_assertion_expired",
            "current_assertion_nonce_mismatch",
        ):
            with self.subTest(name=name):
                self.assert_red(
                    lambda d, name=name: next(row for row in d["fixture"]["authority_assertion_cases"] if row["name"] == name).__setitem__("expected", "continue_join"),
                    "authority_assertion_cases",
                )

    def test_prose_cannot_restore_removed_candidate_time_members(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prose = Path(directory) / "discovery-directory.md"
            prose.write_text(
                "`observed_at` 与 `expires_at` 定义 locator 缓存窗口。\n",
                encoding="utf-8",
                newline="\n",
            )
            lint = Lint()
            with mock.patch.object(gate, "REALM_JOIN_LOCATOR_PROSE_FILES", (prose,)):
                gate.check_realm_join_locator_carriers_and_bounds(lint)
            self.assertTrue(
                any("restores removed per-locator" in error for error in lint.errors),
                lint.errors,
            )


if __name__ == "__main__":
    unittest.main()
