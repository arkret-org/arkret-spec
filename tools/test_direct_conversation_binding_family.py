"""Mutation regressions for the one immutable confirmation and peer contract."""

import json
import unittest
from pathlib import Path

from tools.artifact_lint.protocol_simplification import contract_errors

A = Path(__file__).resolve().parents[1] / "spec/v1/artifacts"


def load(path):
    return json.loads((A / path).read_text(encoding="utf-8"))


class DirectConversationBindingFamilyTest(unittest.TestCase):
    def setUp(self):
        self.c = load("registry/contract-registry.json")
        self.o = load("schemas/consent-operations.schema.json")
        self.t = load("schemas/typed-current-result.schema.json")
        self.bound = next(row for row in self.c["event_kind_registry"]["event_kinds"]
                          if row["event_kind"] == "ak.direct_conversation.bound")

    def errors(self):
        return contract_errors(self.c, self.o, self.t)

    def test_contract(self):
        self.assertEqual(self.errors(), [])

    def test_tagged_set_rejected(self):
        self.bound["result_writes"][0]["result_projection"] = {
            "kind": "keyed_set_add", "tag": {"dot": True}, "value": {"field": "payload"}}
        self.assertTrue(self.errors())

    def test_changing_source_ref_rejected(self):
        self.bound["result_writes"][0]["result_projection"]["value_projection"]["members"][0] = {
            "name": "binding_event_ref", "field": "payload.initial_exact_pair_group_state_ref"}
        self.assertTrue(self.errors())

    def test_endorsement_array_rejected(self):
        self.t["$defs"]["direct_conversation_binding_value"]["required"] = ["endorsements"]
        self.assertTrue(self.errors())

    def test_replacement_guard_cannot_be_weakened(self):
        self.c["event_kind_registry"]["direct_conversation_binding_contract"]["replacement_allowed"] = True
        self.assertTrue(self.errors())

    def test_pair_selector_and_closed_payload(self):
        self.assertEqual(self.bound["result_writes"][0]["result_selector"],
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


if __name__ == "__main__":
    unittest.main()
