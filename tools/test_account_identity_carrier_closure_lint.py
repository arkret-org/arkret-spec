"""Mutation tests for exact account/actor carriers and re-anchor authority."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import bindings, core, schemas


class AccountIdentityCarrierClosureTest(unittest.TestCase):
    def check(self, filename=None, mutate=None, reanchor=False):
        original = schemas.load_json

        def load(lint, path):
            value = original(lint, path)
            if path.name == filename:
                value = copy.deepcopy(value)
                mutate(value)
            return value

        lint = core.Lint()
        with patch.object(schemas, "load_json", load):
            if reanchor:
                schemas.check_account_identity_carrier_closure(lint)
            else:
                schemas.check_account_identity_carrier_closure(lint)
        return lint.errors

    def test_current_carriers_pass(self):
        self.assertEqual(self.check(), [])
        self.assertEqual(self.check(reanchor=True), [])

    def test_actor_filter_cannot_fall_back_to_core(self):
        def mutate(value):
            value["$defs"]["events_open_parameters"]["properties"]["actor_ids"]["items"]["$ref"] = "./common-ids.schema.json#/$defs/did_core_id"

        self.assertTrue(self.check("websocket-frame.schema.json", mutate))

    def test_key_map_cannot_return(self):
        def mutate(value):
            value["$defs"]["query_account_device_entries"] = {"type": "object"}

        self.assertTrue(self.check("keys-operations.schema.json", mutate))

    def test_profile_identity_must_be_required(self):
        def mutate(value):
            value["$defs"]["state_at_window_start"]["properties"]["actor_profiles"]["items"]["required"] = []

        self.assertTrue(self.check("account-subscribe-frame.schema.json", mutate))

    def test_via_ids_cannot_return(self):
        def mutate(value):
            value["$defs"]["membership_payload"]["properties"]["via_ids"] = {"type": "array"}

        self.assertTrue(self.check("event-payload.schema.json", mutate))

    def test_reanchor_cannot_restore_split_pair(self):
        def mutate(value):
            value["$defs"]["device_reanchor_payload"]["properties"]["station_id"] = {"type": "string"}

        self.assertTrue(self.check("event-payload.schema.json", mutate, reanchor=True))

    def test_reanchor_cannot_omit_exact_account(self):
        def mutate(value):
            value["$defs"]["device_reanchor_payload"]["required"].remove("account_id")

        self.assertTrue(self.check("event-payload.schema.json", mutate, reanchor=True))

    def test_get_subscription_uses_encoded_actor_objects(self):
        lint = core.Lint()
        bindings.check_openapi_core_selector_constraints(lint)
        self.assertEqual(lint.errors, [])

    def test_get_subscription_cannot_restore_bare_did_items(self):
        original = bindings.load_yaml
        def load(lint, path):
            value = copy.deepcopy(original(lint, path))
            operation = bindings.openapi_operations_by_id(value)["ak.self.committed_event.stream.subscribe.v1"]
            parameter = next(p for p in operation["parameters"] if p.get("name") == "actor_ids")
            parameter["schema"]["items"] = {"$ref": "../schemas/common-ids.schema.json#/$defs/did_core_id"}
            return value
        lint = core.Lint()
        with patch.object(bindings, "load_yaml", load):
            bindings.check_openapi_core_selector_constraints(lint)
        self.assertTrue(any("JCS ActorId" in error for error in lint.errors), lint.errors)



if __name__ == "__main__":
    unittest.main()
