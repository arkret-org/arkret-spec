"""Regression checks for reports 1355, 1517 and 1600 R2."""

from __future__ import annotations

import sys
import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.bindings import check_non_http_binding_exactness
from tools.artifact_lint.core import Lint
from tools.artifact_lint.foundation import operation_bundle_inclusion_errors


ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
SPEC_ZH = ROOT / "spec" / "v1" / "zh"


def load(relative: str) -> dict:
    return json.loads((ARTIFACTS / relative).read_text(encoding="utf-8"))


class OperationResidualClosureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load("registry/contract-registry.json")
        self.operations = {
            row["operation_id"]: row
            for row in self.contract["operation_registry"]["operations"]
        }

    def test_delivery_status_is_a_complete_registered_operation(self) -> None:
        operation_id = "ak.self.events.read.delivery_status.v1"
        row = self.operations[operation_id]
        self.assertEqual("QUERY /_arkret/self/events/delivery-status", row["http"])
        self.assertEqual("SelfEvents/DeliveryStatus", row["grpc"])
        self.assertEqual("self.events.read.delivery_status", row["mq"])
        events_surface = next(
            row
            for row in self.contract["operation_registry"]["surface_groups"]
            if row["surface"] == "events_sync"
        )
        self.assertIn(operation_id, events_surface["operations"])

    def test_delivery_status_is_closed_across_migration_openapi_and_prose(self) -> None:
        operation_id = "ak.self.events.read.delivery_status.v1"
        migration = json.loads(
            (ROOT / "tools" / "operation-id-v1-migration.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn(
            {
                "old": "ak.self.events.read.delivery_status",
                "new": operation_id,
            },
            migration["mappings"],
        )

        openapi = yaml.safe_load(
            (ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml").read_text(
                encoding="utf-8"
            )
        )
        endpoint = openapi["paths"]["/_arkret/self/events/delivery-status"]["query"]
        self.assertEqual("ak.self.events.read.delivery_status", endpoint["operationId"])
        selector = next(
            row for row in endpoint["parameters"] if row.get("name") == "Arkret-Operation"
        )
        self.assertEqual(operation_id, selector["schema"]["const"])
        self.assertEqual(
            "#/components/schemas/EventDeliveryStatusRequestBody",
            endpoint["requestBody"]["content"]["application/json"]["schema"]["$ref"],
        )
        self.assertEqual(
            "#/components/schemas/EventDeliveryStatusResponseBody",
            endpoint["responses"]["200"]["content"]["application/json"]["schema"]["$ref"],
        )

        binding = (SPEC_ZH / "sync" / "service-http-binding.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "| `ak.self.events.read.delivery_status.v1` | `QUERY "
            "/_arkret/self/events/delivery-status` |",
            binding,
        )

    def test_actor_private_effects_and_operation_count_are_in_prose_indexes(self) -> None:
        spec_map = (SPEC_ZH / "spec-map.md").read_text(encoding="utf-8")
        self.assertIn("`models/actor-private-effects.md`", spec_map)
        readiness = (SPEC_ZH / "overview" / "release-readiness.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            f"| Service operation | {len(json.loads((ROOT / 'spec/v1/artifacts/registry/operation-registry.json').read_text())['operations'])} | `artifacts/registry/operation-registry.json` |",
            readiness,
        )

    def test_delivery_target_id_is_classified_as_an_opaque_correlation(self) -> None:
        registry = json.loads(
            (ROOT / "tools" / "identifier-classification-registry.json").read_text(
                encoding="utf-8"
            )
        )
        rows = [
            row
            for row in registry["classifications"]
            if row["name"] == "target_id"
            and "A-Za-z0-9_-]{15,127}" in row["terminal_signature"]
        ]
        self.assertEqual(1, len(rows))
        self.assertEqual("opaque_correlation", rows[0]["category"])
        self.assertEqual(1, rows[0]["occurrences"])

    def test_delivery_status_dtos_are_closed(self) -> None:
        defs = load("schemas/service-operation-dtos.schema.json")["$defs"]
        request = defs["EventDeliveryStatusRequestBody"]
        outcome = defs["EventDeliveryStatusResponseBody"]
        target = defs["EventDeliveryTargetStatus"]
        self.assertFalse(request["additionalProperties"])
        self.assertEqual(["event_id", "targets"], outcome["required"])
        self.assertFalse(outcome["additionalProperties"])
        self.assertFalse(target["additionalProperties"])
        self.assertEqual(
            [
                "pending_route",
                "pending_delivery",
                "delivered",
                "cancelled_authority_lost",
            ],
            defs["EventDeliveryTargetState"]["enum"],
        )

    def test_delivery_fixture_uses_the_read_surface_not_a_stale_submit_field(self) -> None:
        text = (ARTIFACTS / "fixtures" / "fanout-route-miss-fixture.json").read_text(
            encoding="utf-8"
        )
        self.assertIn("QUERY ak.self.events.read.delivery_status.v1", text)
        self.assertNotIn("pending_delivery_count", text)

    def test_abandonment_has_no_preceding_challenge_contract(self) -> None:
        forbidden = "issue_identity_abandonment_challenge"
        self.assertNotIn(forbidden, json.dumps(self.contract))
        fixture = load("fixtures/pcr-genesis-fixture.json")[
            "provisional_identity_abandonment"
        ]
        self.assertNotIn("challenge_operation", fixture)
        self.assertNotIn("challenge", fixture)
        self.assertEqual(
            [
                "record_orphan_anchor_tombstone_audit_reservation",
                "suppress_reserved_identity_creation_on_every_holder_readable_surface",
                "release_identity_creation_lease",
            ],
            fixture["atomic_writes"],
        )
        error_rows = {
            row["operation_id"]: row
            for row in load("registry/operations-error-mapping.json")["operations"]
        }
        abandonment = error_rows["ak.gate.account.command.abandon_identity_creation.v1"]
        self.assertNotIn("identity_creation_challenge_expired", abandonment["operation_specific"])
        self.assertNotIn(
            "identity_creation_challenge_already_consumed",
            abandonment["operation_specific"],
        )

    def test_live_non_http_projection_exactly_matches_canonical_maps(self) -> None:
        rows = self.contract["operation_registry"]["operations"]
        known = {
            "operation_grpc_map": {
                row["operation_id"]: row["grpc"] for row in rows if row.get("grpc")
            },
            "operation_mq_map": {
                row["operation_id"]: row["mq"] for row in rows if row.get("mq")
            },
        }
        path = ARTIFACTS / "bindings" / "non-http-bindings.yaml"
        lint = Lint()
        check_non_http_binding_exactness(
            lint, path, yaml.safe_load(path.read_text(encoding="utf-8")), known
        )
        self.assertEqual([], lint.errors)


class OperationBundleInclusionTest(unittest.TestCase):
    def bundle(self, name, operations, included=None, role="station"):
        row = {
            "operation_bundle_id": f"ak.operation_bundle.{role}.{name}.v1",
            "service_kind": role,
            "members": [{"operation_id": operation, "binding_kind": "http_json"} for operation in operations],
        }
        if included is not None:
            row["included_operation_bundle_ids"] = included
        return row

    def test_declared_strict_inclusion_accepts_only_shared_exact_pairs(self):
        child = self.bundle("issuer", ["issue"])
        parent = self.bundle("lifecycle", ["issue", "activate"], [child["operation_bundle_id"]])
        self.assertEqual([], operation_bundle_inclusion_errors([child, parent]))

    def test_undeclared_overlap_stays_rejected(self):
        self.assertTrue(operation_bundle_inclusion_errors([
            self.bundle("issuer", ["issue"]), self.bundle("lifecycle", ["issue", "activate"])
        ]))

    def test_missing_or_non_v1_inclusion_is_rejected(self):
        for target in ["ak.operation_bundle.station.missing.v1", "ak.operation_bundle.station.issuer.v2"]:
            with self.subTest(target=target):
                self.assertTrue(operation_bundle_inclusion_errors([self.bundle("lifecycle", ["issue", "activate"], [target])]))

    def test_cross_role_inclusion_is_rejected_without_banning_cross_role_pairs(self):
        child = self.bundle("issuer", ["issue"], role="identity_registry")
        parent = self.bundle("lifecycle", ["issue", "activate"])
        self.assertEqual([], operation_bundle_inclusion_errors([child, parent]))
        parent["included_operation_bundle_ids"] = [child["operation_bundle_id"]]
        self.assertTrue(operation_bundle_inclusion_errors([child, parent]))

    def test_empty_equal_and_partial_member_sets_are_rejected(self):
        for operations in [[], ["issue", "activate"], ["issue", "other"]]:
            with self.subTest(operations=operations):
                child = self.bundle("issuer", operations)
                parent = self.bundle("lifecycle", ["issue", "activate"], [child["operation_bundle_id"]])
                self.assertTrue(operation_bundle_inclusion_errors([child, parent]))

    def test_binding_mismatch_is_not_containment(self):
        child = self.bundle("issuer", ["issue"])
        child["members"][0]["binding_kind"] = "websocket"
        parent = self.bundle("lifecycle", ["issue", "activate"], [child["operation_bundle_id"]])
        self.assertTrue(operation_bundle_inclusion_errors([child, parent]))

    def test_cycle_and_self_inclusion_are_rejected(self):
        child = self.bundle("issuer", ["issue"])
        parent = self.bundle("lifecycle", ["issue", "activate"], [child["operation_bundle_id"]])
        child["included_operation_bundle_ids"] = [parent["operation_bundle_id"]]
        self.assertTrue(any("cycle" in error for error in operation_bundle_inclusion_errors([child, parent])))
        child["included_operation_bundle_ids"] = [child["operation_bundle_id"]]
        self.assertTrue(any("cycle" in error for error in operation_bundle_inclusion_errors([child])))

    def test_inclusion_list_is_closed_unique_and_sorted(self):
        child = self.bundle("issuer", ["issue"])
        for invalid in [[], "not-an-array", [None], [child["operation_bundle_id"]] * 2]:
            with self.subTest(invalid=invalid):
                parent = self.bundle("lifecycle", ["issue", "activate"], invalid)
                self.assertTrue(operation_bundle_inclusion_errors([child, parent]))
        other = self.bundle("another_issuer", ["activate"])
        parent = self.bundle("lifecycle", ["issue", "activate"], [child["operation_bundle_id"], other["operation_bundle_id"]])
        self.assertTrue(any("canonical-sorted" in error for error in operation_bundle_inclusion_errors([child, other, parent])))

    def test_transitive_inclusion_is_valid_but_shared_siblings_are_rejected(self):
        child = self.bundle("issuer", ["issue"])
        parent = self.bundle("lifecycle", ["issue", "activate"], [child["operation_bundle_id"]])
        root = self.bundle("complete", ["issue", "activate", "present"], [parent["operation_bundle_id"]])
        self.assertEqual([], operation_bundle_inclusion_errors([child, parent, root]))
        sibling = self.bundle("other", ["issue", "status"], [child["operation_bundle_id"]])
        self.assertTrue(operation_bundle_inclusion_errors([child, parent, sibling]))

    def test_inclusion_is_part_of_frozen_bundle_closure(self):
        from tools.check_operation_closure_locks import bundle_closures

        child = self.bundle("issuer", ["issue"])
        parent = self.bundle("lifecycle", ["issue", "activate"])
        before = bundle_closures({"operation_registry": {"operation_bundles": [child, parent]}})
        parent["included_operation_bundle_ids"] = [child["operation_bundle_id"]]
        after = bundle_closures({"operation_registry": {"operation_bundles": [child, parent]}})
        self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
