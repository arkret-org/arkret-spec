"""Single-boundary mutations for ordinary-client MLS verification responsibilities."""

import copy
import base64
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

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

    def test_valid_parent_signature_cannot_replace_original_claim_receipt(self):
        def mutate(name, data):
            if name == "mls-roster-client-roles-fixture.json":
                kat = data["signature_binding_kat"]
                parent = kat["attestation"]
                parent["claim_receipt"]["signature"]["signature"] = base64.urlsafe_b64encode(bytes(64)).decode().rstrip("=")
                signed = Ed25519PrivateKey.from_private_bytes(bytes(range(32, 64))).sign(
                    gate.signing_bytes(parent, "ak.mls_add_authority_attestation.v1\n"))
                parent["signature"]["signature"] = base64.urlsafe_b64encode(signed).decode().rstrip("=")
                self.assertTrue(gate.verify_signature(parent, kat["attestation_signing_key"], "ak.mls_add_authority_attestation.v1\n"))
        errors = self.run_gate(mutate)
        self.assertTrue(any("byte-identical original signed claim receipt" in error for error in errors), errors)

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

    def test_recovery_origin_and_original_endpoint_checks_cannot_disappear(self):
        for role, check in (("ordinary_client", "recovery_original_endpoint_signature_origin_binding_and_rfc_path_leaf"), ("account_station", "recovery_origin_station_exact_native_history_and_original_source_signature"), ("governance_station", "recovery_origin_station_exact_native_history_and_original_source_signature"), ("independent_auditor", "recovery_origin_station_exact_native_history_and_original_source_signature")):
            def mutate(name, data):
                if name == "contract-registry.json":
                    data["did_evidence_boundary_registry"]["mls_roster_verification_contract"]["roles"][role]["checks"].remove(check)
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
                row["response_schema_ref"] = "schemas/mls-roster-authority.schema.json#/$defs/roster_read_response_body"
        self.assertTrue(self.run_gate(mutate))

    def test_member_selector_cannot_require_prejoin_genesis_or_open_shape(self):
        for field in ("genesis_event_ref", "additionalProperties"):
            def mutate(name, data):
                if name == "mls-roster-authority.schema.json":
                    row = data["$defs"]["mls_member_roster_authority_read_request_body"]
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
                row["request_schema_ref"] = "schemas/mls-roster-authority.schema.json#/$defs/mls_roster_authority_read_request_body"
        self.assertTrue(self.run_gate(mutate))

    def test_signature_tampering_and_wrong_historical_key_rejected(self):
        for field in ("claim_receipt", "attestation"):
            with self.subTest(field=field):
                def mutate(name, data):
                    if name == "mls-roster-client-roles-fixture.json":
                        data["signature_binding_kat"][field]["signature"]["signature"] = "A" * 86
                self.assertTrue(self.run_gate(mutate))

    def test_key_binding_cannot_be_open_or_optional(self):
        for definition in ("self_roster_read_response_body", "roster_add_signing_keys", "roster_signing_key"):
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

    def test_recovery_cannot_drop_original_event_or_authorization_binding(self):
        for field in ("original_event", "binding", "record_branch"):
            def mutate(name, data):
                if name != "mls-roster-authority.schema.json":
                    return
                definitions = data["$defs"]
                if field == "record_branch":
                    definitions["roster_record"]["oneOf"] = [row for row in definitions["roster_record"]["oneOf"] if row.get("$ref") != "#/$defs/roster_recovery_record"]
                elif field == "binding":
                    definitions["roster_recovery_record"]["properties"]["commit_event"]["allOf"][1]["properties"]["payload"]["required"] = []
                else:
                    definitions["roster_recovery_record"]["properties"]["commit_event"]["allOf"] = []
            self.assertTrue(self.run_gate(mutate))

    def test_agent_recovery_fact_cannot_become_a_boolean_or_open_claim(self):
        for field in ("event_ref", "authorization_event_ref", "verification_method"):
            def mutate(name, data):
                if name == "authority-commit-operations.schema.json":
                    data["$defs"]["agent_runtime_historical_signer_fact"]["required"].remove(field)
            self.assertTrue(self.run_gate(mutate))


if __name__ == "__main__":
    unittest.main()
