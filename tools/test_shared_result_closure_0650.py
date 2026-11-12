"""Mutation coverage for the shared typed-current closure owned by report 0650."""

from __future__ import annotations

import copy
import json
import sys
import unittest

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as writes_gate
from tools.artifact_lint import effect_ownership as owner_gate
from tools.artifact_lint.core import schema_validator
from tools.event_admission_contract import selected_branches, schema_definitions


TARGETS = {
    "ak.agent.action_approve": ("agent_action_approval",),
    "ak.agent.sidecar.exchange.control": ("agent_sidecar_exchange_controls",),
    "ak.applet.discovery": ("applet_discovery",),
    "ak.applet.registration": ("applet_registration",),
    "ak.call.create": ("call_state",),
    "ak.key_backup.active_series": ("key_backup_active_series", "realm_actor_key_backup_active_series"),
    "ak.member.identity.update": ("member_identity_updates",),
    "ak.message.create": ("message_revision",),
    "ak.message.revise": ("message_revision",),
    "ak.profile.realm_override": ("actor_profile_realm_override",),
    "ak.realm.organization": ("realm_organization",),
}


def row_of(document: dict, kind: str) -> dict:
    rows = document.get("event_kinds") or document["event_kind_registry"]["event_kinds"]
    return next(row for row in rows if row["event_kind"] == kind)


class SharedResultClosure0650Test(unittest.TestCase):
    def _owner_errors(self, mutate=None) -> list[str]:
        original = owner_gate.load_json
        document = copy.deepcopy(original(owner_gate.Lint(), owner_gate.CONTRACT_REGISTRY))
        if mutate:
            mutate(document)

        def load_json(lint, path):  # type: ignore[no-untyped-def]
            if Path(path).resolve() == owner_gate.CONTRACT_REGISTRY.resolve():
                return document
            return original(lint, path)

        owner_gate.load_json = load_json
        try:
            lint = owner_gate.Lint()
            owner_gate.check_effect_ownership(lint)
            return lint.errors
        finally:
            owner_gate.load_json = original

    def _write_errors(self, mutate=None) -> list[str]:
        original = writes_gate.load_json
        contract = copy.deepcopy(
            original(writes_gate.Lint(), owner_gate.CONTRACT_REGISTRY)
        )
        document = contract["event_kind_registry"]
        if mutate:
            mutate(document)

        def load_json(lint, path):  # type: ignore[no-untyped-def]
            if Path(path).resolve() == writes_gate.EVENT_KIND_REGISTRY.resolve():
                return document
            if Path(path).resolve() == writes_gate.CURRENT_RESULT_REGISTRY.resolve():
                return contract["current_state_registry"]
            return original(lint, path)

        writes_gate.load_json = load_json
        try:
            lint = writes_gate.Lint()
            writes_gate.check_result_write_contracts(lint)
            return lint.errors
        finally:
            writes_gate.load_json = original

    def test_all_target_kinds_have_the_exact_owned_families(self) -> None:
        contract = owner_gate.load_json(owner_gate.Lint(), owner_gate.CONTRACT_REGISTRY)
        for kind, families in TARGETS.items():
            with self.subTest(kind=kind):
                row = row_of(contract, kind)
                self.assertEqual(row["effect_ownership"], {"kind": "typed_state_writer"})
                self.assertEqual([write["state_family"] for write in row["state_writes"]], list(families))

    def test_each_target_loses_ownership_if_its_declared_writes_are_removed(self) -> None:
        baseline = set(self._owner_errors())
        for kind in TARGETS:
            with self.subTest(kind=kind):
                errors = self._owner_errors(lambda d, k=kind: row_of(d, k).pop("state_writes"))
                new = set(errors) - baseline
                self.assertTrue(any("non-empty state_writes" in error for error in new), new)

    def test_backup_family_conditions_and_native_projection_are_disjoint(self) -> None:
        contract = owner_gate.load_json(owner_gate.Lint(), owner_gate.CONTRACT_REGISTRY)
        row = row_of(contract, "ak.key_backup.active_series")
        account, native = row["state_writes"]
        for write, kind in ((account, "account"), (native, "realm")):
            self.assertEqual(write["condition"], {
                "kind": "field_equals", "field": "payload.actor_id.kind", "const": kind})
        self.assertEqual(native["state_selector"]["components"], [
            {"kind": "canonical_json", "field": "payload.actor_id.realm_actor_id"},
            {"kind": "canonical_json", "field": "payload.effective_scope"}, "payload.backup_kind"])
        self.assertEqual(native["value_schema_ref"],
            "schemas/current-state.schema.json#/$defs/realm_actor_key_backup_active_series_value")
        self.assertEqual(native["state_projection"]["value_projection"]["members"], [
            {"name": field, "field": "payload." + field}
            for field in ("active_series_id", "series_pointer_version", "manager_ref", "recovery_ref", "recipient_ref")])
        schema = writes_gate.load_json(writes_gate.Lint(), ROOT / "spec/v1/artifacts/schemas/current-state.schema.json")
        value = schema["$defs"]["realm_actor_key_backup_active_series_value"]
        self.assertFalse(value["additionalProperties"])
        self.assertEqual(list(value["properties"]), [
            "active_series_id", "series_pointer_version", "manager_ref", "recovery_ref", "recipient_ref"])

    def test_backup_admission_roles_do_not_cross_native_and_account_families(self) -> None:
        contract = owner_gate.load_json(owner_gate.Lint(), owner_gate.CONTRACT_REGISTRY)
        registry = contract["event_kind_registry"]
        row = row_of(registry, "ak.key_backup.active_series")
        artifacts = ROOT / "spec/v1/artifacts"
        event_path = artifacts / "schemas/event-envelope.schema.json"
        event_schema = json.loads(event_path.read_text(encoding="utf-8"))
        base = schema_validator(event_path, "#")
        # Inline generated guards retain the actual Event resource's base URI.
        base = base.evolve(_resolver=base._resolver.lookup(event_schema["$id"]).resolver)
        branches = [(name, base.evolve(schema=guard)) for name, guard in selected_branches(row)]
        gate = base.evolve(schema=schema_definitions(registry)["registered_admission_shape"])
        fixture = json.loads((artifacts / "fixtures/managed-governance-fixture.json").read_text(encoding="utf-8"))
        identities = fixture["identities"]
        scopes = json.loads((artifacts / "fixtures/applet-device-scope-fixture.json").read_text(encoding="utf-8"))
        circle = next(case["scope"] for case in scopes["cases"]
                      if case.get("valid") and case.get("scope", {}).get("kind") == "circle")
        actors = schema_validator(artifacts / "schemas/common-ids.schema.json", "#/$defs/actor_id")
        for role in ("service", "bot", "alice"):
            self.assertTrue(actors.is_valid(identities[role]), role)
        candidate = {"kind": "ak.key_backup.active_series", "actor_id": copy.deepcopy(identities["service"]),
            "scope_ref": {"kind": "realm_control", "realm_id": identities["realm_id"]},
            "applet_id": identities["applet_id"], "payload": {"actor_id": copy.deepcopy(identities["bot"])}}
        self.assertEqual([name for name, guard in branches if guard.is_valid(candidate)], ["realm_actor_backup"])
        self.assertTrue(gate.is_valid(candidate))
        for field, value in (("actor_id", identities["alice"]), ("actor_id", identities["bot"]),
                             ("scope_ref", {"kind": "realm", "realm_id": identities["realm_id"]}),
                             ("scope_ref", circle), ("authorization_ref", fixture["lineage"]["parent_id"]),
                             ("executed_by", identities["service"])):
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(candidate)
                changed[field] = value
                self.assertFalse(gate.is_valid(changed))
        changed = copy.deepcopy(candidate)
        del changed["applet_id"]
        self.assertFalse(gate.is_valid(changed))
        account = {"kind": "ak.key_backup.active_series", "actor_id": copy.deepcopy(identities["alice"]),
                   "payload": {"actor_id": copy.deepcopy(identities["alice"])}}
        self.assertEqual([name for name, guard in branches if guard.is_valid(account)], ["self_authored_proof"])
        account.update({"executed_by": copy.deepcopy(identities["alice"]),
                        "authorization_ref": fixture["lineage"]["parent_id"]})
        self.assertEqual([name for name, guard in branches if guard.is_valid(account)], ["capability_gated"])
        account["payload"]["actor_id"] = copy.deepcopy(identities["bot"])
        self.assertEqual([name for name, guard in branches if guard.is_valid(account)], ["deny"])

    def test_sidecar_selector_never_exposes_plaintext_exchange_identity(self) -> None:
        contract = owner_gate.load_json(owner_gate.Lint(), owner_gate.CONTRACT_REGISTRY)
        write = row_of(contract, "ak.agent.sidecar.exchange.control")["state_writes"][0]
        serialized = repr(write["state_selector"])
        self.assertNotIn("exchange_id", serialized)
        self.assertNotIn("encrypted_payload", serialized)
        self.assertEqual(write["state_projection"]["kind"], "keyed_set_add")

    def test_all_new_families_resolve_to_closed_result_defs(self) -> None:
        contract = owner_gate.load_json(owner_gate.Lint(), owner_gate.CONTRACT_REGISTRY)
        registered = {
            row["state_kind"]: row["schema_ref"]
            for row in contract["current_state_registry"]["state_kinds"]
        }
        schema = writes_gate.load_json(
            writes_gate.Lint(), ROOT / "spec/v1/artifacts/schemas/current-state.schema.json"
        )
        for family in sorted({family for families in TARGETS.values() for family in families} - {"call_state"}):
            with self.subTest(family=family):
                self.assertIn(family, registered)
                definition = registered[family].rsplit("/", 1)[-1]
                self.assertIn(definition, schema["$defs"])


if __name__ == "__main__":
    unittest.main()
