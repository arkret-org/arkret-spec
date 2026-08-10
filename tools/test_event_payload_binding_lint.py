"""Mutation tests for the explicit Event kind to payload schema binding lint."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import core, schemas

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
CONTRACT_REGISTRY = ARTIFACTS / "registry" / "contract-registry.json"
EVENT_ENVELOPE = ARTIFACTS / "schemas" / "event-envelope.schema.json"
EVENT_PAYLOAD = ARTIFACTS / "schemas" / "event-payload.schema.json"


class EventPayloadBindingLintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_registry = core.parse_json_text(
            CONTRACT_REGISTRY.read_text(encoding="utf-8")
        )
        cls.event_envelope = core.parse_json_text(
            EVENT_ENVELOPE.read_text(encoding="utf-8")
        )
        cls.event_payload = core.parse_json_text(
            EVENT_PAYLOAD.read_text(encoding="utf-8")
        )
        rows = cls.contract_registry["event_kind_registry"]["event_kinds"]
        cls.known = {
            "event_kinds": {row["event_kind"] for row in rows},
            "active_durable_event_kinds": {
                row["event_kind"]
                for row in rows
                if row.get("status") == "active"
                and row.get("wire_scope") == "durable_event"
            },
            "active_event_wire_scopes": {
                row["event_kind"]: row["wire_scope"]
                for row in rows
                if row.get("status") == "active"
            },
        }

    def _lint(
        self,
        *,
        registry_mutation=None,
        envelope_mutation=None,
        payload_mutation=None,
    ) -> list[str]:
        registry = copy.deepcopy(self.contract_registry)
        envelope = copy.deepcopy(self.event_envelope)
        payload = copy.deepcopy(self.event_payload)
        if registry_mutation is not None:
            registry_mutation(registry)
        if envelope_mutation is not None:
            envelope_mutation(envelope)
        if payload_mutation is not None:
            payload_mutation(payload)

        original_load_json = schemas.load_json

        def load_json_with_mutation(lint, path):
            resolved = path.resolve()
            if resolved == CONTRACT_REGISTRY.resolve():
                return registry
            if resolved == EVENT_ENVELOPE.resolve():
                return envelope
            if resolved == EVENT_PAYLOAD.resolve():
                return payload
            return original_load_json(lint, path)

        schemas.load_json = load_json_with_mutation
        try:
            lint = schemas.Lint()
            schemas.check_event_schema_coverage(lint, self.known)
            return lint.errors
        finally:
            schemas.load_json = original_load_json

    @staticmethod
    def _row(registry, kind: str):
        return next(
            row
            for row in registry["event_kind_registry"]["event_kinds"]
            if row["event_kind"] == kind
        )

    def test_current_binding_is_closed(self) -> None:
        self.assertEqual(self._lint(), [])

    def test_missing_active_binding_fails(self) -> None:
        def mutate(registry) -> None:
            self._row(registry, "ak.message.create").pop("payload_schema_ref")

        errors = self._lint(registry_mutation=mutate)
        self.assertTrue(
            any("must declare payload_schema_ref" in error for error in errors),
            errors,
        )

    def test_dangling_binding_fails(self) -> None:
        def mutate(registry) -> None:
            self._row(registry, "ak.message.create")["payload_schema_ref"] = (
                "schemas/event-payload.schema.json#/$defs/missing_payload"
            )

        errors = self._lint(registry_mutation=mutate)
        self.assertTrue(any("does not resolve" in error for error in errors), errors)

    def test_divergent_binding_fails(self) -> None:
        def mutate(registry) -> None:
            self._row(registry, "ak.message.create")["payload_schema_ref"] = (
                "schemas/event-payload.schema.json#/$defs/relation_update_payload"
            )

        errors = self._lint(registry_mutation=mutate)
        self.assertTrue(
            any("unique Event Envelope payload dispatch" in error for error in errors),
            errors,
        )

    def test_duplicate_dispatch_fails(self) -> None:
        def mutate(envelope) -> None:
            branch = next(
                branch
                for branch in envelope["allOf"]
                if branch.get("if", {})
                .get("properties", {})
                .get("kind", {})
                .get("const")
                == "ak.message.create"
            )
            envelope["allOf"].append(copy.deepcopy(branch))

        errors = self._lint(envelope_mutation=mutate)
        self.assertTrue(any("exactly one" in error for error in errors), errors)

    def test_orphan_payload_definition_fails(self) -> None:
        def mutate(payload) -> None:
            payload["$defs"]["orphan_probe_payload"] = {
                "type": "object",
                "additionalProperties": False,
            }

        errors = self._lint(payload_mutation=mutate)
        self.assertTrue(
            any("orphan Event payload definition" in error for error in errors),
            errors,
        )

    def test_stale_shared_dispatch_allowlist_fails(self) -> None:
        probe = ("ak.message.create", "stale_probe_payload")
        schemas.LEGACY_SHARED_PAYLOAD_DISPATCH.add(probe)
        try:
            errors = self._lint()
        finally:
            schemas.LEGACY_SHARED_PAYLOAD_DISPATCH.remove(probe)
        self.assertTrue(
            any("stale LEGACY_SHARED_PAYLOAD_DISPATCH" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
