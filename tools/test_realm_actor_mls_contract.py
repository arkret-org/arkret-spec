"""Schema, real signature and explicit ledger-model checks; not production evidence."""
import copy
import json
import unittest

from tools.artifact_lint import core
from tools.artifact_lint.mls_roster_client_roles import verify_signature
from tools.realm_actor_mls_contract import ART, ADD_DOMAIN, CLAIM_DOMAIN, ClaimContinuationModel, handoff_fixture

class RealmActorMlsTests(unittest.TestCase):
    def validator(self, schema, definition):
        return core.schema_validator(ART / "schemas" / f"{schema}.schema.json", f"#/$defs/{definition}")

    def request(self, target=True, requester=False):
        fixture = json.loads((ART / "fixtures/keypackage-lifecycle-fixture.json").read_text(encoding="utf-8"))
        req = copy.deepcopy(fixture["schema_validation_cases"][0]["instance"])
        actor = {"kind": "realm", "realm_actor_id": {"realm_id": req["intended_realm_id"], "principal_id": req["target_account_id"]["principal_id"]}}
        if target:
            del req["target_account_id"]
            req["target_actor_id"] = actor
        if requester:
            del req["requester_account_id"]
            req["requester_actor_id"] = actor
            req["requester_authorization"]["kind"] = "realm_device"
        return req

    def test_claim_full_and_unsigned_positive_branches(self):
        for target, requester in ((False, False), (True, False), (False, True), (True, True)):
            req = self.request(target, requester)
            self.validator("keypackage-operations", "keypackages_claim_request_body").validate(req)
            unsigned = {k: v for k, v in req.items() if k not in ("service_binding", "requester_authorization")}
            self.validator("keypackage-operations", "peer_keypackages_claim_unsigned_request").validate(unsigned)

    def test_claim_mixed_missing_or_fake_account_rejected(self):
        valid = self.request(True, True)
        validator = self.validator("keypackage-operations", "keypackages_claim_request_body")
        for field in ("target_actor_id", "requester_actor_id"):
            bad = copy.deepcopy(valid); del bad[field]
            self.assertFalse(validator.is_valid(bad), field)
        for field in ("target_account_id", "requester_account_id"):
            bad = copy.deepcopy(valid); bad[field] = self.request(False, False)[field]
            self.assertFalse(validator.is_valid(bad), field)
        bad = copy.deepcopy(valid); bad["requester_authorization"]["kind"] = "device"
        self.assertFalse(validator.is_valid(bad))
        bad = copy.deepcopy(valid); bad["target_actor_id"]["realm_actor_id"]["station_id"] = "ak:did_core:web:fake.example"
        self.assertFalse(validator.is_valid(bad))

    def test_realm_claim_cannot_enter_direct_conversation(self):
        req = self.request(); req["claim_purpose"] = "direct_conversation"
        self.assertFalse(self.validator("keypackage-operations", "keypackages_claim_request_body").is_valid(req))

    def test_claim_and_add_authority_fields_are_required_for_realm(self):
        f = handoff_fixture()
        for field, definition, schema in (("claim_receipt", "peer_keypackage_claim_receipt", "keypackage-operations"), ("attestation", "mls_add_authority_attestation", "mls-roster-authority")):
            value = copy.deepcopy(f[field]); validator = self.validator(schema, definition)
            validator.validate(value)
            del value["claim_authority_ref"]
            self.assertFalse(validator.is_valid(value))

    def test_ordinary_claim_and_add_forbid_realm_authority_fields(self):
        f = json.loads((ART / "fixtures/mls-roster-client-roles-fixture.json").read_text(encoding="utf-8"))["signature_binding_kat"]
        for field, definition, schema in (("claim_receipt", "peer_keypackage_claim_receipt", "keypackage-operations"), ("attestation", "mls_add_authority_attestation", "mls-roster-authority")):
            value = copy.deepcopy(f[field]); validator = self.validator(schema, definition)
            validator.validate(value)
            value["claim_authority_ref"] = f["attestation"]["genesis_event_ref"]
            self.assertFalse(validator.is_valid(value))

    def test_two_real_signatures_bind_each_issuer_and_every_field(self):
        f = handoff_fixture()
        self.assertNotEqual(f["claim_receipt"]["destination_id"], f["attestation"]["attestor_station_id"])
        for name, key, other, domain in (("claim_receipt", "claim_receipt_signing_key", "attestation_signing_key", CLAIM_DOMAIN), ("attestation", "attestation_signing_key", "claim_receipt_signing_key", ADD_DOMAIN)):
            self.assertTrue(verify_signature(f[name], f[key], domain))
            self.assertFalse(verify_signature(f[name], f[other], domain))
            for field in f[name]:
                if field == "signature": continue
                bad = copy.deepcopy(f[name]); del bad[field]
                self.assertFalse(verify_signature(bad, f[key], domain), field)

    def test_nested_original_receipt_is_covered_by_add(self):
        f = handoff_fixture(); bad = copy.deepcopy(f["attestation"])
        bad["claim_receipt"]["destination_id"] = bad["attestor_station_id"]
        self.assertFalse(verify_signature(bad, f["attestation_signing_key"], ADD_DOMAIN))

    def model(self):
        f = handoff_fixture(); c = f["claim_receipt"]
        return ClaimContinuationModel(f["attestation"]["actor_id"], c["destination_id"], c["claim_authority_ref"], 100)

    def consume(self, model, **changes):
        args = dict(destination=model.governor, actor=model.actor, generation=1, historical_recipient=model.issuer, now=50, request=b"original request", receipt=b"original receipt")
        args.update(changes)
        return model.consume(**args)

    def test_model_multiple_transfers_preserve_historical_issuer_and_outcome(self):
        m = self.model(); m.inventory["welcome"] = "original Welcome"
        original = copy.deepcopy(m.inventory)
        for next_governor in ("new", "third"):
            m.frozen = True
            self.assertTrue(m.transfer(next_governor, m.governor, copy.deepcopy(m.inventory)))
        self.assertEqual(m.inventory, original)
        self.assertFalse(self.consume(m, historical_recipient=m.governor))
        self.assertEqual(self.consume(m), b"original receipt")
        self.assertEqual(self.consume(m, now=101, receipt=b"must not replace"), b"original receipt")

    def test_model_exact_replay_after_transfer_and_authentication(self):
        m = self.model(); m.inventory["welcome"] = "Welcome"
        self.assertTrue(self.consume(m))
        m.frozen = True
        self.assertTrue(m.transfer("new", m.governor, copy.deepcopy(m.inventory)))
        self.assertEqual(self.consume(m, now=101), b"original receipt")
        self.assertFalse(self.consume(m, authenticated=False))
        self.assertFalse(self.consume(m, request=b"different request"))

    def test_model_fences_and_failed_imports_leave_zero_effects(self):
        for field in ("claim", "method_history", "welcome", "outcome"):
            m = self.model(); m.frozen = True; original = copy.deepcopy(m.__dict__)
            imported = copy.deepcopy(m.inventory); del imported[field]
            self.assertFalse(m.transfer("new", m.governor, imported))
            self.assertEqual(m.__dict__, original)
        for changes in ({"destination": "wrong"}, {"generation": 2}, {"actor": {}}, {"now": 101}, {"authorized": False}):
            m = self.model(); m.inventory["welcome"] = "Welcome"; original = copy.deepcopy(m.__dict__)
            self.assertFalse(self.consume(m, **changes)); self.assertEqual(m.__dict__, original)
        m = self.model(); m.frozen = True
        self.assertFalse(self.consume(m))

    def test_registry_pins_scope_and_non_disclosure(self):
        d = json.loads((ART / "registry/contract-registry.json").read_text(encoding="utf-8"))
        rules = d["realm_actor_contract"]["mls_claim_handoff_contract"]
        for key in ("original_receipt_rewrite", "authority_ref_alone_suffices", "ordinary_account_agent_rules_changed", "claim_private_inventory_public"):
            self.assertIs(rules[key], False)
        self.assertEqual(rules["scenarios"], handoff_fixture()["required_scenarios"])

if __name__ == "__main__":
    unittest.main()
