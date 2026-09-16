"""Focused locks for the accepted required-constant family cleanup."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "spec" / "v1" / "artifacts" / "schemas"
REGISTRY = ROOT / "spec" / "v1" / "artifacts" / "registry" / "contract-registry.json"


def load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


class RequiredConstantFamilySchemaTest(unittest.TestCase):
    def assert_members_absent(self, schema: dict, *members: str) -> None:
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        for member in members:
            self.assertNotIn(member, required)
            self.assertNotIn(member, properties)

    def test_success_only_members_are_not_carried(self) -> None:
        cases = [
            ("account-operations.schema.json", "identity_abandonment_outcome", ("status",)),
            ("account-operations.schema.json", "account_request_erasure_outcome", ("status",)),
            ("directory-operations.schema.json", "directory_agent_selector_resolution_outcome", ("verified",)),
            ("holder-quarantine.schema.json", "quarantine_entry", ("status",)),
            ("mimi-operations.schema.json", "mimi_request_consent_outcome", ("status",)),
            ("mimi-operations.schema.json", "mimi_update_consent_outcome", ("status",)),
            ("mimi-operations.schema.json", "mimi_report_abuse_outcome", ("status",)),
            ("principal-locator.schema.json", "invite_locator_revoke_outcome", ("status",)),
            ("recovery-session.schema.json", "recovery_session_proof_submit_outcome", ("state", "verification")),
            ("service-operation-dtos.schema.json", "ModerationReportOutcome", ("status",)),
            ("service-operation-dtos.schema.json", "ReferenceLockedEventStub", ("status",)),
        ]
        for file_name, definition, members in cases:
            with self.subTest(file_name=file_name, definition=definition):
                self.assert_members_absent(load(file_name)["$defs"][definition], *members)

    def test_failure_and_position_discriminators_are_retained(self) -> None:
        definitions = load("service-operation-dtos.schema.json")["$defs"]
        retained = [
            ("SessionGrantReplayExpiredProblem", "state", "expired"),
            ("DeviceMessageDeliveredResult", "status", "delivered"),
            ("DeviceMessageUnknownResult", "status", "unknown"),
        ]
        for definition, member, expected in retained:
            with self.subTest(definition=definition, member=member):
                self.assertEqual(
                    definitions[definition]["properties"][member]["const"],
                    expected,
                )

    def test_empty_success_operations_have_no_response_schema(self) -> None:
        keys = load("keys-operations.schema.json")
        signal = load("signal-relay.schema.json")
        principal = load("principal-operations.schema.json")
        self.assertNotIn("keys_backups_delete_outcome", keys["$defs"])
        self.assertNotIn("signal_relay_outcome", signal.get("$defs", {}))
        self.assertNotIn("keypackage_terminal_command", principal["$defs"])

        entries = {
            item["operation_id"]: item
            for item in json.loads(REGISTRY.read_text(encoding="utf-8"))["operation_registry"]["operations"]
            if isinstance(item, dict) and "operation_id" in item
        }
        for operation_id in (
            "ak.self.keys.backups.resource.delete.v1",
            "ak.peer.signal.command.relay.v1",
        ):
            with self.subTest(operation_id=operation_id):
                entry = entries[operation_id]
                self.assertEqual(entry["success_shape_kind"], "empty_response")
                self.assertNotIn("response_schema_ref", entry)

    def test_profile_fixed_members_are_injected_by_identity(self) -> None:
        cases = [
            ("agent-sidecar-exchange-projection.schema.json", None, ("origin", "completion_policy")),
            ("agent-sidecar-event-exchange-binding.schema.json", "request_context", ("completion_policy",)),
            ("agent-sidecar.schema.json", None, ("encryption_profile",)),
            ("call-recording-artifact.schema.json", None, ("artifact_kind",)),
            ("identity-link.schema.json", None, ("response_signing_algorithm",)),
            ("message.schema.json", None, ("track_name",)),
            ("signal-typing.schema.json", None, ("track_name",)),
            ("recovery-session.schema.json", "publication_authority_context", ("identity_model",)),
            (
                "service-describe.schema.json",
                "transport_binding_websocket",
                ("extension_profile_required", "subprotocol", "authentication"),
            ),
        ]
        for file_name, definition, members in cases:
            with self.subTest(file_name=file_name, definition=definition):
                document = load(file_name)
                schema = document if definition is None else document["$defs"][definition]
                self.assert_members_absent(schema, *members)

        stream = load("signal-message-stream.schema.json")["$defs"]
        for definition in ("common_properties", "keyframe", "delta", "abort"):
            with self.subTest(definition=definition):
                text = json.dumps(stream[definition], sort_keys=True)
                self.assertNotIn('"track_name"', text)

    def test_signed_profile_constants_are_retained(self) -> None:
        self.assertEqual(
            load("agent-provision.schema.json")["properties"]["accountability_scope"]["const"],
            "agent_operator",
        )
        self.assertEqual(
            load("recovery-receipt.schema.json")["properties"]["identity_model"]["const"],
            "pcr_policy",
        )
        self.assertEqual(
            load("security-transaction.schema.json")["$defs"]
            ["pcr_policy_recovery_binding"]["properties"]["identity_model"]["const"],
            "pcr_policy",
        )

    def test_pcd_profile_fixed_parameters_are_not_echoed(self) -> None:
        describe = load("service-describe.schema.json")["properties"]["private_contact_discovery"]
        self.assert_members_absent(
            describe,
            "oprf_mode",
            "ciphersuite",
            "derived_prefix_bytes",
            "proof_shape",
            "response_size_buckets_bytes",
        )
        self.assert_members_absent(describe["properties"]["anti_enumeration_delay"], "distribution")

        directory = load("directory-operations.schema.json")["$defs"]
        for definition in (
            "psi_blind_request_body",
            "psi_blind_outcome",
            "psi_match_request_body",
            "psi_match_outcome",
        ):
            schema = directory[definition]
            self.assert_members_absent(schema, "ciphersuite", "derived_prefix_bytes")
            self.assertIn("profile", schema["required"])


if __name__ == "__main__":
    unittest.main()
