"""Mutation tests for the delegated-write admission / Event Envelope lock lint.

The Agent lifecycle Control Moves (ak.self.agent.pause / resume / deactivate) derive
the Agent principal from envelope.actor_id and the controller from envelope.executed_by.
The lint pins that the event-kind registry denies every branch without the executor
pair and that event-envelope.schema.json mirrors that requirement as a schema lock.
All mutations run on in-memory copies; no real artifact is rewritten.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import bindings, core

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
EVENT_KIND_REGISTRY = ARTIFACTS / "registry" / "event-kind-registry.json"
EVENT_ENVELOPE = ARTIFACTS / "schemas" / "event-envelope.schema.json"


class DelegatedWriteAdmissionLockLintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.event_registry = core.parse_json_text(
            EVENT_KIND_REGISTRY.read_text(encoding="utf-8")
        )
        cls.event_envelope = core.parse_json_text(EVENT_ENVELOPE.read_text(encoding="utf-8"))

    def _lint(self, *, registry_mutation=None, envelope_mutation=None) -> list[str]:
        registry = copy.deepcopy(self.event_registry)
        envelope = copy.deepcopy(self.event_envelope)
        if registry_mutation is not None:
            registry_mutation(registry)
        if envelope_mutation is not None:
            envelope_mutation(envelope)

        original_load_json = bindings.load_json

        def load_json_with_mutation(lint, path):
            resolved = path.resolve()
            if resolved == EVENT_KIND_REGISTRY.resolve():
                return registry
            if resolved == EVENT_ENVELOPE.resolve():
                return envelope
            return original_load_json(lint, path)

        bindings.load_json = load_json_with_mutation
        try:
            lint = bindings.Lint()
            bindings.check_delegated_write_admission_envelope_lock(lint)
            return lint.errors
        finally:
            bindings.load_json = original_load_json

    @staticmethod
    def _row(registry, kind: str):
        return next(row for row in registry["event_kinds"] if row["event_kind"] == kind)

    @staticmethod
    def _lifecycle_lock(envelope):
        for block in envelope["$defs"]["registered_admission_shape"]["allOf"]:
            if block["if"]["properties"]["kind"].get("const") == "ak.self.agent.pause":
                return block
        raise AssertionError("agent lifecycle envelope lock is missing")

    def test_current_artifacts_are_locked(self) -> None:
        self.assertEqual(self._lint(), [])

    def test_every_lifecycle_kind_is_mandatory(self) -> None:
        mandatory = bindings._admission_mandatory_top_level_fields(self.event_registry)
        for kind in bindings.DELEGATED_WRITE_ADMISSION_KINDS:
            self.assertEqual(mandatory.get(kind), {"executed_by", "authorization_ref"}, kind)
        self.assertNotIn("ak.realm.create", mandatory)

    def test_dropping_conditional_admission_fails(self) -> None:
        def mutate(registry) -> None:
            row = self._row(registry, "ak.self.agent.pause")
            row.pop("admission")
            row.pop("admission_variants")

        errors = self._lint(registry_mutation=mutate)
        self.assertTrue(
            any("ak.self.agent.pause: delegated controller write MUST declare" in e for e in errors),
            errors,
        )

    def test_otherwise_branch_must_deny(self) -> None:
        def mutate(registry) -> None:
            row = self._row(registry, "ak.self.agent.resume")
            row["admission_variants"][-1]["admission"] = "capability_gated"

        errors = self._lint(registry_mutation=mutate)
        self.assertTrue(any("ak.self.agent.resume" in e for e in errors), errors)

    def test_branch_without_authorization_ref_fails(self) -> None:
        def mutate(registry) -> None:
            row = self._row(registry, "ak.self.agent.deactivate")
            row["admission_variants"][0]["when"]["top_level_fields_present"] = ["executed_by"]

        errors = self._lint(registry_mutation=mutate)
        self.assertTrue(any("ak.self.agent.deactivate" in e for e in errors), errors)

    def test_missing_envelope_lock_fails(self) -> None:
        def mutate(envelope) -> None:
            envelope["allOf"].remove({"$ref": "#/$defs/registered_admission_shape"})
        self.assertTrue(any("projection reference" in e for e in self._lint(envelope_mutation=mutate)))

    def test_envelope_lock_missing_one_field_fails(self) -> None:
        def mutate(envelope) -> None:
            self._lifecycle_lock(envelope)["then"] = {"required": ["executed_by"]}
        self.assertTrue(any("projection drift" in e for e in self._lint(envelope_mutation=mutate)))

    def test_envelope_lock_with_extra_selector_does_not_count(self) -> None:
        def mutate(envelope) -> None:
            self._lifecycle_lock(envelope)["if"]["required"].append("refs")
        self.assertTrue(any("projection drift" in e for e in self._lint(envelope_mutation=mutate)))

    def test_agent_genesis_refs_dependent_selector_fails(self) -> None:
        def mutate(envelope) -> None:
            guard = next(g for g in envelope["$defs"]["registered_admission_shape"]["allOf"]
                         if g["if"]["properties"]["kind"].get("const") == "ak.realm.create")
            guard["if"]["required"].append("refs")
        self.assertTrue(any("projection drift" in e for e in self._lint(envelope_mutation=mutate)))


if __name__ == "__main__":
    unittest.main()
