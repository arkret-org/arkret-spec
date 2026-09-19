"""Regression checks for reports 1355, 1517 and 1600 R2."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

from artifact_lint.bindings import check_non_http_binding_exactness
from artifact_lint.core import Lint


ROOT = Path(__file__).resolve().parents[1]
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
            "#/components/schemas/EventDeliveryStatusOutcome",
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
            "| Service operation | 222 | `artifacts/registry/operation-registry.json` |",
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
        outcome = defs["EventDeliveryStatusOutcome"]
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


if __name__ == "__main__":
    unittest.main()
