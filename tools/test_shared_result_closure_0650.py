"""Mutation coverage for the shared typed-current closure owned by report 0650."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as writes_gate
from tools.artifact_lint import result_effect_ownership as owner_gate


TARGETS = {
    "ak.agent.action_approve": "agent_action_approval",
    "ak.agent.sidecar.exchange.control": "agent_sidecar_exchange_controls",
    "ak.applet.discovery": "applet_discovery",
    "ak.applet.registration": "applet_registration",
    "ak.call.create": "call_state",
    "ak.key_backup.active_series": "key_backup_active_series",
    "ak.member.identity.update": "member_identity_updates",
    "ak.message.create": "message_revision",
    "ak.message.revise": "message_revision",
    "ak.profile.realm_override": "actor_profile_realm_override",
    "ak.realm.organization": "realm_organization",
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
            owner_gate.check_result_effect_ownership(lint)
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
                return contract["current_result_registry"]
            return original(lint, path)

        writes_gate.load_json = load_json
        try:
            lint = writes_gate.Lint()
            writes_gate.check_result_write_contracts(lint)
            return lint.errors
        finally:
            writes_gate.load_json = original

    def test_all_fifteen_kinds_have_the_exact_owned_family(self) -> None:
        contract = owner_gate.load_json(owner_gate.Lint(), owner_gate.CONTRACT_REGISTRY)
        for kind, family in TARGETS.items():
            with self.subTest(kind=kind):
                row = row_of(contract, kind)
                self.assertEqual(row["result_effect_ownership"], {"kind": "typed_result_writer"})
                self.assertEqual([write["result_family"] for write in row["result_writes"]], [family])

    def test_each_target_loses_ownership_if_its_single_write_is_removed(self) -> None:
        baseline = set(self._owner_errors())
        for kind in TARGETS:
            with self.subTest(kind=kind):
                errors = self._owner_errors(lambda d, k=kind: row_of(d, k).pop("result_writes"))
                new = set(errors) - baseline
                self.assertTrue(any("non-empty result_writes" in error for error in new), new)

    def test_sidecar_selector_never_exposes_plaintext_exchange_identity(self) -> None:
        contract = owner_gate.load_json(owner_gate.Lint(), owner_gate.CONTRACT_REGISTRY)
        write = row_of(contract, "ak.agent.sidecar.exchange.control")["result_writes"][0]
        serialized = repr(write["result_selector"])
        self.assertNotIn("exchange_id", serialized)
        self.assertNotIn("encrypted_payload", serialized)
        self.assertEqual(write["result_projection"]["kind"], "keyed_set_add")

    def test_all_new_families_resolve_to_closed_result_defs(self) -> None:
        contract = owner_gate.load_json(owner_gate.Lint(), owner_gate.CONTRACT_REGISTRY)
        registered = {
            row["result_kind"]: row["schema_ref"]
            for row in contract["current_result_registry"]["result_kinds"]
        }
        schema = writes_gate.load_json(
            writes_gate.Lint(), ROOT / "spec/v1/artifacts/schemas/typed-current-result.schema.json"
        )
        for family in sorted(set(TARGETS.values()) - {"call_state"}):
            with self.subTest(family=family):
                self.assertIn(family, registered)
                definition = registered[family].rsplit("/", 1)[-1]
                self.assertIn(definition, schema["$defs"])


if __name__ == "__main__":
    unittest.main()
