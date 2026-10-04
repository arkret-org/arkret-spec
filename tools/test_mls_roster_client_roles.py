"""Single-boundary mutations for ordinary-client MLS verification responsibilities."""

import copy
import unittest
from unittest.mock import patch

from tools.artifact_lint import mls_roster_client_roles as gate
from tools.artifact_lint.core import Lint


class RosterClientRoleTests(unittest.TestCase):
    def run_gate(self, mutate=None):
        original = gate.load_json
        def load(lint, path):
            data = copy.deepcopy(original(lint, path))
            if mutate:
                mutate(path.name, data)
            return data
        with patch.object(gate, "load_json", load):
            lint = Lint()
            gate.check_mls_roster_client_roles(lint)
            return lint.errors

    def test_committed_contract_and_signature_kat(self):
        self.assertEqual(self.run_gate(), [])

    def test_ordinary_profile_cannot_require_history_or_network(self):
        for field in ("method_history_verifier", "live_did_discovery"):
            with self.subTest(field=field):
                def mutate(name, data):
                    if name == "contract-registry.json":
                        data["did_evidence_boundary_registry"]["mls_roster_verification_contract"]["roles"]["ordinary_client"][field] = True
                self.assertTrue(self.run_gate(mutate))

    def test_manifest_cannot_replace_recipient_signatures_or_leaf(self):
        for field in ("recipient_claim_receipt_signature", "recipient_add_attestation_signature", "rfc9420_credential_leaf_and_proposal_binding"):
            with self.subTest(field=field):
                def mutate(name, data):
                    if name == "contract-registry.json":
                        data["did_evidence_boundary_registry"]["mls_roster_verification_contract"]["roles"]["ordinary_client"]["checks"].remove(field)
                self.assertTrue(self.run_gate(mutate))

    def test_commit_signer_and_history_cannot_become_route_sources(self):
        for field in ("self_result_portable", "network_from_retained_commit_signer", "historical_closure_is_current_route"):
            with self.subTest(field=field):
                def mutate(name, data):
                    if name == "contract-registry.json":
                        data["did_evidence_boundary_registry"]["mls_roster_verification_contract"][field] = True
                self.assertTrue(self.run_gate(mutate))

    def test_self_cannot_use_unprojected_peer_result(self):
        def mutate(name, data):
            if name == "contract-registry.json":
                row = next(x for x in data["operation_registry"]["operations"] if x["operation_id"] == "ak.self.mls.read.roster_authority.v1")
                row["response_schema_ref"] = "schemas/mls-roster-authority.schema.json#/$defs/roster_read_outcome"
        self.assertTrue(self.run_gate(mutate))

    def test_member_selector_cannot_require_prejoin_genesis_or_open_shape(self):
        for field in ("genesis_event_ref", "additionalProperties"):
            def mutate(name, data):
                if name == "mls-roster-authority.schema.json":
                    row = data["$defs"]["member_roster_read_request"]
                    if field == "genesis_event_ref":
                        row["required"].append(field)
                        row["properties"][field] = {"type": "string"}
                    else:
                        row[field] = True
            self.assertTrue(self.run_gate(mutate))

    def test_self_cannot_use_peer_selector(self):
        def mutate(name, data):
            if name == "contract-registry.json":
                row = next(x for x in data["operation_registry"]["operations"] if x["operation_id"] == "ak.self.mls.read.roster_authority.v1")
                row["request_schema_ref"] = "schemas/mls-roster-authority.schema.json#/$defs/roster_read_request"
        self.assertTrue(self.run_gate(mutate))

    def test_signature_tampering_and_wrong_historical_key_rejected(self):
        for field in ("claim_receipt", "attestation"):
            with self.subTest(field=field):
                def mutate(name, data):
                    if name == "mls-roster-client-roles-fixture.json":
                        data["signature_binding_kat"][field]["signature"]["sig"] = "A" * 86
                self.assertTrue(self.run_gate(mutate))

    def test_key_binding_cannot_be_open_or_optional(self):
        for definition in ("self_roster_read_outcome", "roster_add_signing_keys", "roster_signing_key"):
            with self.subTest(definition=definition):
                def mutate(name, data):
                    if name == "mls-roster-authority.schema.json":
                        data["$defs"][definition]["additionalProperties"] = True
                self.assertTrue(self.run_gate(mutate))

    def test_native_and_role_cases_cannot_disappear(self):
        def mutate(name, data):
            if name == "mls-roster-client-roles-fixture.json":
                data["cases"] = [row for row in data["cases"] if row["name"] != "wrong_station_core"]
        self.assertTrue(self.run_gate(mutate))


if __name__ == "__main__":
    unittest.main()
