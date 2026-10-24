"""Mutation regressions for the one immutable confirmation and peer contract."""

import json
import unittest
from pathlib import Path

from tools.artifact_lint.protocol_simplification import contract_errors, direct_governance_errors

A = Path(__file__).resolve().parents[1] / "spec/v1/artifacts"


def load(path):
    return json.loads((A / path).read_text(encoding="utf-8"))


class DirectConversationBindingFamilyTest(unittest.TestCase):
    def setUp(self):
        self.c = load("registry/contract-registry.json")
        self.o = load("schemas/consent-operations.schema.json")
        self.t = load("schemas/current-state.schema.json")
        self.bound = next(row for row in self.c["event_kind_registry"]["event_kinds"]
                          if row["event_kind"] == "ak.direct_conversation.bound")

    def errors(self):
        return contract_errors(self.c, self.o, self.t)

    def test_contract(self):
        self.assertEqual(self.errors(), [])

    def test_tagged_set_rejected(self):
        self.bound["state_writes"][0]["state_projection"] = {
            "kind": "keyed_set_add", "tag": {"dot": True}, "value": {"field": "payload"}}
        self.assertTrue(self.errors())

    def test_changing_source_ref_rejected(self):
        self.bound["state_writes"][0]["state_projection"]["value_projection"]["members"][0] = {
            "name": "binding_event_ref", "field": "payload.initial_exact_pair_group_state_ref"}
        self.assertTrue(self.errors())

    def test_endorsement_array_rejected(self):
        self.t["$defs"]["direct_conversation_binding_value"]["required"] = ["endorsements"]
        self.assertTrue(self.errors())

    def test_replacement_guard_cannot_be_weakened(self):
        self.c["event_kind_registry"]["direct_conversation_binding_contract"]["replacement_allowed"] = True
        self.assertTrue(self.errors())

    def test_pair_selector_and_closed_payload(self):
        self.assertEqual(self.bound["state_writes"][0]["state_selector"],
                         {"kind": "composite", "components": ["payload.pair_key"]})
        self.assertNotIn("direct_conversation_binding_endorsement_entry", self.t["$defs"])
        props = load("schemas/event-payload.schema.json")["$defs"]["direct_conversation_bound_payload"]["properties"]
        for name in ["binding_digest", "binding_state", "supersedes_binding_ref"]:
            self.assertNotIn(name, props)

    def test_scope_filtered_edit_rejected(self):
        self.o["$defs"]["consent_current_read_request_body"]["properties"]["consent_scope"] = {}
        self.assertTrue(self.errors())

    def test_guessed_supply_operation_rejected(self):
        self.c["message_authoring_contract"]["input_supply"][0]["source_operations"] = ["ak.self.messages.read.context.v1"]
        self.assertTrue(self.errors())

    def test_missing_sidecar_branch_rejected(self):
        self.c["message_authoring_contract"]["branches"] = [
            row for row in self.c["message_authoring_contract"]["branches"] if row["kind"] != "sidecar"]
        self.assertTrue(self.errors())

    def test_governance_policy_is_not_optional_or_mutable(self):
        policy = self.c["event_kind_registry"]["direct_conversation_binding_contract"]["governance_station_policy"]
        for field, replacement in [("mutable", True), ("governance_generation", 1),
                                   ("binding_source", "current_profile"),
                                   ("rejected_stages", ["change_admission"]),
                                   ("public_generation_zero_authority_bundle", "not_found"),
                                   ("per_message_online_probe_required", True)]:
            original = policy[field]
            policy[field] = replacement
            self.assertTrue(self.errors(), field)
            policy[field] = original

    def test_governance_schema_and_profile_fences(self):
        bundle = load("schemas/realm-authority-bundle.schema.json")
        handoff = load("schemas/authority-commit-operations.schema.json")
        profiles = load("profiles/conformance-profiles.json")
        check = lambda: direct_governance_errors(bundle, handoff, profiles)
        self.assertEqual(check(), [])
        original = bundle["allOf"]
        bundle["allOf"] = []
        self.assertTrue(check())
        bundle["allOf"] = original
        original = handoff["$defs"]["realm_authority_handoff_request_body"]["allOf"]
        handoff["$defs"]["realm_authority_handoff_request_body"]["allOf"] = original[:-1]
        self.assertTrue(check())
        handoff["$defs"]["realm_authority_handoff_request_body"]["allOf"] = original
        profile = profiles["profile_requirements"]["ak.profile.direct_conversation_realm.v1"]
        profile["rejected_event_kinds"].remove("ak.realm.governance_station.change")
        self.assertTrue(check())
        profile["rejected_event_kinds"].append("ak.realm.governance_station.change")
        profile["root_owner_mask"]["stable_phase"]["allowed_root_control_actions"].append("ak.realm.governance_station.change")
        self.assertTrue(check())

    def test_governance_qualification_cannot_run_after_profile(self):
        gate = self.c["operation_registry"]["direct_conversation_admission_mappings"]["governance_station_qualification"]
        gate["stage"] = "after_profile_admission"
        self.assertTrue(self.errors())
        del self.c["operation_registry"]["direct_conversation_admission_mappings"]["governance_station_qualification"]
        self.assertTrue(self.errors())

    def test_direct_governance_cases_are_restrictions_not_live_credit(self):
        rows = load("fixtures/protocol-simplification-fixture.json")["direct_governance_cases"]
        self.assertEqual(len(rows), 10)
        for row in rows:
            allowed = row["genesis_purpose"] != "direct_conversation" or (
                row["current_station"] == row["genesis_station"]
                and int(row["current_generation"]) == 0 and row["transitions"] == 0
                and row["operation"] in {"current", "deployment_update", "historical_read"})
            self.assertEqual(allowed, row["expected"], row["name"])


if __name__ == "__main__":
    unittest.main()
