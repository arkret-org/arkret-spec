"""Realm actor wire, signature and acceptance-model regression tests; no SUT claim."""
import base64
import copy
import json
import unittest

from tools.artifact_lint import core
from tools.realm_actor_contract import ART, CONTEXTS, FAMILIES, ControlModel, actor, canonical, committed, digest, signature_fixture, token, verify


class RealmActorContractTests(unittest.TestCase):
    def validator(self, name, fragment=""):
        return core.schema_validator(ART / "schemas" / (name + ".schema.json"), fragment)

    def test_ra_id_complete_identity_and_station_independence(self):
        v = self.validator("common-ids", "#/$defs/actor_id")
        v.validate(actor())
        self.assertNotEqual(canonical(actor()), canonical(actor(2)))
        bad = actor(); bad["realm_actor_id"]["station_id"] = "ak:did_core:webvh:station"
        self.assertFalse(v.is_valid(bad))
        self.assertFalse(v.is_valid({"kind": "realm", "account_id": {"principal_id": "ak:did_core:webvh:x", "station_id": "ak:did_core:webvh:y"}}))

    def test_ra_stream_initialization_terminal_identity_and_independent_order(self):
        model = ControlModel(token("realm"))
        self.assertIsNone(model.head)
        self.assertEqual(model.create(actor(), "request", "digest", verified=True, allowed=True), ("accepted", 0))
        other = actor(); other["realm_actor_id"]["principal_id"] += "Other"
        self.assertEqual(model.create(other, "request2", "digest2", verified=True, allowed=True), ("accepted", 1))
        model.rows[canonical(actor())]["owner"] = "retired"
        self.assertEqual(model.create(actor(), "new-intent", "digest3", verified=True, allowed=True), "rejected")
        self.assertEqual(model.head, 1)
        scope = {"kind": "realm_control", "realm_id": token("realm")}
        self.validator("realm-commit", "#/$defs/stream_ref").validate(scope)
        self.assertFalse(self.validator("applet-install-plan", "#/$defs/effective_scope").is_valid(scope))

    def test_ra_create_exact_replay_expiry_permissions_and_cross_realm(self):
        model = ControlModel(token("realm"))
        for options in [dict(verified=False, allowed=True), dict(verified=True, allowed=False), dict(verified=True, allowed=True, expired=True)]:
            self.assertEqual(model.create(actor(), "request", "digest", **options), "rejected")
            self.assertIsNone(model.head)
        self.assertEqual(model.create(actor(2), "request", "digest", verified=True, allowed=True), "rejected")
        accepted = model.create(actor(), "request", "digest", verified=True, allowed=True)
        self.assertEqual(model.create(actor(), "request", "digest", verified=True, allowed=True, expired=True), accepted)
        self.assertEqual(model.create(actor(), "request", "changed", verified=True, allowed=True), "conflict")

    def test_ra_control_old_and_new_proofs_revision_continuity_and_pause(self):
        model = self.created()
        for key in ["old_proof", "new_pop", "native_continuity"]:
            kwargs = dict(old_proof=True, new_pop=True, native_continuity=True); kwargs[key] = False
            self.assertFalse(model.rotate(actor(), 0, "new", **kwargs))
        self.assertFalse(model.rotate(actor(), 99, "new", old_proof=True, new_pop=True, native_continuity=True))
        model.rows[canonical(actor())]["owner"] = "paused"
        self.assertTrue(model.rotate(actor(), 0, "new", old_proof=True, new_pop=True, native_continuity=True))
        model.rows[canonical(actor())]["governance"] = "retired"
        self.assertFalse(model.rotate(actor(), 1, "next", old_proof=True, new_pop=True, native_continuity=True))

    def test_ra_device_transcript_complete_fields_and_no_account_fallback(self):
        schema = json.loads((ART / "schemas/event-payload.schema.json").read_text(encoding="utf-8"))["$defs"]
        transcript = schema["device_authorize_realm_actor_possession_transcript"]
        expected = "actor_id device_id device_public_key_did hpke_key algorithms device_key_algorithm authorized_by authorization_binding_kind authorized_generation_ref not_before expires_at scopes applet_id expected_control_revision expected_device_revision".split()
        self.assertEqual(list(transcript["properties"]), expected)
        self.assertEqual(transcript["required"], expected)
        self.assertFalse(transcript["additionalProperties"])
        self.assertEqual(transcript["properties"]["authorization_binding_kind"], {"const": "realm_managed_delegation"})
        self.assertNotIn("device_authorize_applet_managed_possession_transcript", schema)

    def test_ra_current_crypto_kats_all_fields_domains_and_wrong_key(self):
        fixture = signature_fixture()
        actual = json.loads((ART / "fixtures/realm-actor-signature-kat-fixture.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, fixture)
        for case in fixture["cases"]:
            context, signature = case["context"], case["signature"]
            unsigned = case.get("unsigned_projection") or {k:v for k,v in case["candidate"].items() if k != "control_signature"}
            key = base64.urlsafe_b64decode(case["public_key_b64u"] + "=")
            self.assertTrue(verify(context, unsigned, signature, key))
            for field in unsigned:
                changed = copy.deepcopy(unsigned); changed.pop(field)
                self.assertFalse(verify(context, changed, signature, key), (context, field))
            for domain in CONTEXTS:
                if domain != context: self.assertFalse(verify(domain, unsigned, signature, key))
            self.assertFalse(verify(context, unsigned, signature, bytes(reversed(key))))
            file, fragment = case["unsigned_schema_ref"].split("#")
            core.schema_validator(ART / file, "#" + fragment).validate(unsigned)

    def test_ra_gate_owner_cannot_clear_governance_or_installation(self):
        model = self.created(); row = model.rows[canonical(actor())]; row["devices"]["device"] = 1
        self.assertTrue(model.business(actor(), "device"))
        row["governance"] = "paused"; row["owner"] = "active"
        self.assertFalse(model.business(actor(), "device"))
        row["governance"] = "active"
        self.assertFalse(model.business(actor(), "device", installed=False))
        self.assertFalse(model.business(actor(), "device", grant=False))
        row["revoked"].add("device")
        self.assertFalse(model.business(actor(), "device"))

    def test_ra_manager_rotation_three_authorities_and_old_device_fence(self):
        model = self.created(); row = model.rows[canonical(actor())]; row["devices"]["old-device"] = 1
        row["owner"] = "paused"
        self.assertFalse(model.transfer(actor(), (0, 0, 1), controller=True, governance=True, acceptance=True))
        self.assertTrue(model.rotate(actor(), 0, "new", old_proof=True, new_pop=True, native_continuity=True))
        for missing in ["controller", "governance", "acceptance"]:
            kwargs = dict(controller=True, governance=True, acceptance=True); kwargs[missing] = False
            self.assertFalse(model.transfer(actor(), (0, 1, 1), **kwargs))
        self.assertTrue(model.transfer(actor(), (0, 1, 1), controller=True, governance=True, acceptance=True))
        row["owner"] = "active"
        self.assertFalse(model.business(actor(), "old-device"))

    def test_ra_handoff_actual_import_and_replay_retained(self):
        model = self.created(); exported = model.export()
        for key in exported:
            incomplete = copy.deepcopy(exported); incomplete.pop(key)
            with self.assertRaises(ValueError): ControlModel.handoff(exported, incomplete, True)
        with self.assertRaises(ValueError): ControlModel.handoff(exported, exported, False)
        successor = ControlModel.handoff(exported, exported, True)
        self.assertEqual(successor.create(actor(), "request", "digest", verified=True, allowed=True), ("accepted", 0))
        self.assertEqual(successor.rows, model.rows)
        self.assertEqual(successor.tenure, 1)

    def test_ra_privacy_minimal_fact_and_exact_current_selector(self):
        defs = json.loads((ART / "schemas/authority-commit-operations.schema.json").read_text(encoding="utf-8"))["$defs"]
        public = defs["realm_device_historical_signer_fact"]["properties"]
        self.assertEqual(set(public), {"kind", "event_id", "actor_id", "verification_method", "public_key_b64u", "accepted_at", "device_id", "authorization_event_id", "authorized_generation_ref"})
        for field in ["control_event_ref", "stream_position", "method_history_evidence", "commit_id"]: self.assertNotIn(field, public)
        request = {"actor_id": actor(), "purpose": "current", "request_nonce": "N" * 22, "selectors": [{"kind": "realm_actor_identity", "actor_id": actor()}]}
        v = self.validator("realm-actor-material", "#/$defs/request"); v.validate(request)
        request["selectors"].append(request["selectors"][0]); self.assertFalse(v.is_valid(request))

    def test_device_raw_possession_signature_covers_every_field(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        f = signature_fixture()["device_possession"]
        self.validator("event-payload", "#/$defs/device_authorize_realm_actor_possession_transcript").validate(f["transcript"])
        key = Ed25519PublicKey.from_public_bytes(base64.urlsafe_b64decode(f["public_key_b64u"] + "="))
        signature = base64.urlsafe_b64decode(f["signature_b64u"] + "==")
        message = (f["context"] + "\n").encode() + canonical(f["transcript"])
        self.assertEqual(message.hex(), f["signature_input_hex"])
        key.verify(signature, message)
        for field in f["transcript"]:
            changed = copy.deepcopy(f["transcript"]); changed.pop(field)
            with self.assertRaises(InvalidSignature):
                key.verify(signature, (f["context"] + "\n").encode() + canonical(changed))
        with self.assertRaises(InvalidSignature):
            key.verify(signature, b"ak.device_authorize_possession_proof.v1\n" + canonical(f["transcript"]))

    def test_realm_mentions_and_revocation_reject_account_splicing(self):
        mention = self.validator("event-payload", "#/$defs/mention_node")
        value = {"kind":"mention", "subject_actor_id":actor()}; mention.validate(value)
        account = {"principal_id":"ak:did_core:webvh:zExample", "station_id":"ak:did_core:webvh:zStation"}
        for field, content in [("subject_account_id",account),("handle_at_time","alice:example.com")]:
            self.assertFalse(mention.is_valid({**value,field:content}))
        ordinary = {"kind":"mention", "subject_account_id":account}; mention.validate(ordinary)
        value["subject_actor_id"]={"kind":"account","account_id":account}
        self.assertFalse(mention.is_valid(value))
        record = {"schema":"ak.schema.device_revocation_state.v1", "actor_id":actor(), "device_id":"ak:device:0195be74-0000-7000-8000-000000000001", "target_device_authorize_event_id":token("event"), "target_device_generation_ref":1,"proposal_event_id":token("event",2),"accepted_at":"2026-10-19T00:00:00.000Z","acceptance_seq":1}
        validator = self.validator("device-revocation-state", "#/$defs/common_record")
        validator.validate(record)
        self.assertFalse(validator.is_valid({**record,"account_id":account}))

    def test_exact_replay_requires_authentication_and_applet_namespace(self):
        model = self.created()
        self.assertEqual(model.create(actor(), "request", "digest", verified=False, allowed=True), "rejected")
        other = actor(); other["realm_actor_id"]["principal_id"] += "Other"
        self.assertEqual(model.create(other, "request", "other", verified=True, allowed=True, applet_id="another-applet"),("accepted",1))
        exported = model.export()
        for section in exported["private_inventory"]:
            incomplete = copy.deepcopy(exported); incomplete["private_inventory"].pop(section)
            with self.assertRaises(ValueError): ControlModel.handoff(exported,incomplete,True)

    def test_private_create_envelope_and_controller_branch(self):
        candidate = signature_fixture()["cases"][0]["candidate"]
        event = {"event_id":token("event"), "kind":"ak.realm.actor.create", "scope_ref":{"kind":"realm_control","realm_id":token("realm")}, "actor_id":{"kind":"service","service_id":candidate["service_id"]}, "created_at":"2026-10-19T00:00:00.000Z", "payload":candidate, "applet_id":candidate["applet_id"], "authorization_ref":candidate["creation_authorization_ref"], "producer_proof":{"kind":"detached_jws","verification_method":candidate["control_method_kid"],"event_digest":"sha256:"+"1"*64,"created_at":"2026-10-19T00:00:00.000Z","jws":"YQ..Yg"}}
        validator = self.validator("event-envelope", "#/$defs/shared_event_envelope")
        validator.validate(event)
        for change in [{"scope_ref":{"kind":"realm","realm_id":token("realm")}}, {"actor_id":actor()}, {"executed_by":actor()}]:
            self.assertFalse(validator.is_valid({**event,**change}))
        event.update(kind="ak.realm.actor.devices.reset",actor_id=actor(),payload={"expected_revision":{"commit_id":token("realm_commit"),"stream_position":0},"expected_generation":1,"new_generation":2})
        event.pop("authorization_ref")
        validator.validate(event)
        self.assertFalse(validator.is_valid({**event,"authorization_ref":token("grant")}))

    def test_ghost_lookup_requires_full_realm_namespace(self):
        query = {"applet_id":"ak:applet:0195be74-0000-7000-8000-000000000001","realm_id":token("realm"),"protocol":"example","instance_id":"network","external_id":"user"}
        validator = self.validator("applet-edge-operations","#/$defs/third_party_user_query")
        validator.validate(query)
        for field in query:
            missing = dict(query);missing.pop(field);self.assertFalse(validator.is_valid(missing))
        response = self.validator("applet-edge-operations","#/$defs/applet_third_party_user_list")
        response.validate({"exists":False})
        self.assertFalse(response.is_valid({"exists":False,"actor_id":actor()}))
        self.assertFalse(response.is_valid({"exists":True}))

    def created(self):
        model = ControlModel(token("realm")); model.create(actor(), "request", "digest", verified=True, allowed=True)
        return model


if __name__ == "__main__":
    unittest.main()
