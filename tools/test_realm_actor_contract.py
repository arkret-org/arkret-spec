"""Realm actor wire, signature and acceptance-model regression tests; no SUT claim."""
import base64
import copy
import json
import unittest

from tools.artifact_lint import core
from tools.test_realm_actor_mls_contract import RealmActorMlsTests
from tools.realm_actor_contract import ART, CONTEXTS, FAMILIES, ControlModel, actor, canonical, committed, digest, signature_fixture, token, verify, native_recovery_fixture, verify_native_recovery, native_verify


class RealmActorContractTests(unittest.TestCase):
    def test_applet_execution_bundles_follow_key_custody_roles(self):
        catalog = json.loads((ART / "registry/contract-registry.json").read_text(encoding="utf-8"))
        bundles = {row["operation_bundle_id"]: row
                   for row in catalog["operation_registry"]["operation_bundles"]}
        station = bundles["ak.operation_bundle.station.applet.v1"]
        applet = bundles["ak.operation_bundle.applet_service.applet.v1"]
        self.assertEqual("station", station["service_kind"])
        self.assertEqual("applet_service", applet["service_kind"])
        members = lambda row: {(entry["operation_id"], entry["binding_kind"])
                               for entry in row["members"]}
        exclusive = {
            ("ak.edge.applet.managed_actor.command.author.v1", "http_json"),
            ("ak.edge.applet.configuration.command.execute.v1", "http_json"),
        }
        self.assertTrue(exclusive.isdisjoint(members(station)))
        self.assertEqual(members(station) | exclusive, members(applet))
        self.assertIn(("ak.edge.applet.command.transaction.v1", "http_json"), members(station))
        self.assertIn(("ak.self.applet.configuration.command.submit.v1", "http_json"),
                      members(bundles["ak.operation_bundle.station.applet_install.v1"]))
        self.assertEqual({("ak.server.read.describe.v1", "http_json")},
                         members(bundles["ak.operation_bundle.applet_service.describe.v1"]))

    def test_realm_mentions_use_native_content_without_account_notification_identity(self):
        registry = json.loads((ART / "registry/applet-managed-authority-registry.json").read_text(encoding="utf-8"))
        contract = registry["realm_mentions"]
        self.assertEqual("subject_actor_id", contract["target_field"])
        self.assertEqual("authorized_native_device_content_stream", contract["delivery"])
        for key in ["verify_original_before_processing",
                    "verify_mls_before_processing_encrypted_content",
                    "current_delivery_gates_required"]:
            self.assertTrue(contract[key], key)
        for key in ["ordinary_notification_projection", "account_subscribe",
                    "grants_execution_authority", "unknown_execution_may_restart"]:
            self.assertFalse(contract[key], key)
        self.assertEqual(["recipient_actor_id", "source_event_id", "processing_purpose"],
                         contract["durable_local_deduplication_key"])
        preimage = {
            "recipient_account_id": {
                "principal_id": "ak:did_core:webvh:zPerson",
                "station_id": "ak:did_core:web:account.example"
            },
            "realm_id": token("realm"), "source_event_id": token("event"),
            "notification_kind": "mention"
        }
        validator = self.validator("notification", "#/$defs/projection_preimage")
        validator.validate(preimage)
        self.assertFalse(validator.is_valid({**preimage, "recipient_account_id": actor()}))
        self.assertFalse(validator.is_valid({**preimage, "recipient_actor_id": actor()}))
        self.validator("event-payload", "#/$defs/mention_node").validate(
            {"kind": "mention", "subject_actor_id": actor()})

    def test_device_revoke_terminal_material_is_closed(self):
        validator = self.validator("realm-actor-material", "#/$defs/outcome_record")
        for state in ["pending", "accepted", "rejected"]:
            outcome = {"status": "device_revoke", "proposal_ref": committed(4, 2),
                       "device_id": "ak:device:00000000-0000-7000-8000-000000000001", "authorization_ref": committed(),
                       "authorized_generation_ref": 1, "state": state,
                       "decided_at": None if state == "pending" else "2026-10-20T00:00:00.000Z"}
            value = {"target_request_digest": "sha256:" + "1" * 64, "outcome": outcome}
            validator.validate(value)
            for field in outcome:
                bad = copy.deepcopy(value)
                del bad["outcome"][field]
                self.assertFalse(validator.is_valid(bad), field)
            for field, invalid in [("decided_at", "2026-10-20T00:00:00.000Z" if state == "pending" else None),
                                   ("authorized_generation_ref", 0), ("state", "committed"),
                                   ("device_id", token("event")), ("extra", True)]:
                bad = copy.deepcopy(value)
                bad["outcome"][field] = invalid
                self.assertFalse(validator.is_valid(bad), field)

    def test_account_peer_material_closed_carrier_and_signed_audience(self):
        schema = self.validator("realm-actor-material", "#/$defs/peer_request")
        request = {"actor_id": actor(), "purpose": "current", "request_nonce": "N" * 22,
                   "selectors": [{"kind": "realm_actor_control", "actor_id": actor()}]}
        account = {"principal_id": "ak:did_core:webvh:zPerson", "station_id": "ak:did_core:webvh:zAccountStation"}
        peer = {"requester_account_id": account, "request": request}
        schema.validate(peer)
        for field in ["bearer", "session_grant", "dpop", "allowed"]:
            self.assertFalse(schema.is_valid({**peer, field: "untrusted"}))
        self.assertFalse(schema.is_valid({"request": request}))
        self.assertFalse(schema.is_valid({**peer, "requester_account_id": account["principal_id"]}))
        catalog = json.loads((ART / "registry/contract-registry.json").read_text(encoding="utf-8"))
        operation = next(row for row in catalog["operation_registry"]["operations"] if row["operation_id"] == "ak.peer.realm_actor.read.material.v1")
        self.assertEqual("schemas/realm-actor-material.schema.json#/$defs/peer_request", operation["request_schema_ref"])
        self.assertEqual("schemas/realm-actor-material.schema.json#/$defs/outcome", operation["response_schema_ref"])
        self.assertEqual(4194304, operation["max_canonical_body_bytes"])
        self.assertEqual({"service_signature"}, set(operation["auth_requirements"]))

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
        self.assertFalse(model.transfer(actor(), (0, 1, 1), controller=True, governance=True, acceptance=True))
        self.assertTrue(model.transfer(actor(), (0, 1, 1), controller=True, governance=True, acceptance=True, native_transfer=True))
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

    def test_recovery_service_fact_is_closed_and_has_no_business_grant(self):
        fields = "kind event_id actor_id target_actor_id verification_method public_key_b64u accepted_at applet_id registration_epoch registration_ref manager_ref recovery_ref".split()
        path = ART / "schemas/authority-commit-operations.schema.json"
        definition = json.loads(path.read_text(encoding="utf-8"))["$defs"]["realm_recovery_service_historical_signer_fact"]
        self.assertEqual(list(definition["properties"]), fields)
        self.assertEqual(definition["required"], fields)
        fact = {"kind":"realm_recovery_service", "event_id":token("event"),
                "actor_id":{"kind":"service","service_id":"ak:did_core:webvh:zApplet"},
                "target_actor_id":actor(), "verification_method":"did:webvh:zApplet:applet.example#signer",
                "public_key_b64u":base64.urlsafe_b64encode(bytes([1])*32).rstrip(b"=").decode(),
                "accepted_at":"2026-10-20T00:00:00.000Z", "applet_id":"ak:applet:01904100-0000-7000-8000-bbbbbbbbbbbb",
                "registration_epoch":"sha256:"+"1"*64, "registration_ref":committed(),
                "manager_ref":committed(), "recovery_ref":committed(4,1)}
        v = self.validator("authority-commit-operations", "#/$defs/historical_producer_signer_fact")
        v.validate(fact)
        for field in fields:
            bad = copy.deepcopy(fact); del bad[field]
            self.assertFalse(v.is_valid(bad), field)
        for field in ["authorization_ref", "effective_scope", "private_key", "method_history_evidence"]:
            self.assertFalse(v.is_valid({**fact,field:committed()}), field)
        bad=copy.deepcopy(fact); bad["actor_id"]=actor()
        self.assertFalse(v.is_valid(bad))
        bad=copy.deepcopy(fact); bad["target_actor_id"]=fact["actor_id"]
        self.assertFalse(v.is_valid(bad))

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

    def test_kr_native_scid_chain_prerotation_signatures_and_witness(self):
        vector = native_recovery_fixture()
        result = verify_native_recovery(vector, vector["log_entries"][:1])
        self.assertEqual(result["did"], vector["did"])
        self.assertEqual(result["version_id"], vector["log_entries"][-1]["versionId"])
        mutations = [
            lambda v: v.update(scid="wrong"),
            lambda v: v["log_entries"][1]["parameters"].update(updateKeys=v["log_entries"][0]["parameters"]["updateKeys"]),
            lambda v: v["log_entries"][1]["proof"][0].update(proofPurpose="authentication"),
            lambda v: v["log_entries"][1]["proof"][0].update(proofValue=v["log_entries"][0]["proof"][0]["proofValue"]),
            lambda v: v["log_entries"][1]["state"]["verificationMethod"][0].update(controller="did:web:attacker.example"),
            lambda v: v["witness_records"].pop(),
            lambda v: v["witness_records"][1]["proof"][0].update(proofValue=v["witness_records"][0]["proof"][0]["proofValue"]),
        ]
        for mutate in mutations:
            bad = copy.deepcopy(vector); mutate(bad)
            with self.assertRaises(Exception): verify_native_recovery(bad)
        changed_prefix = copy.deepcopy(vector["log_entries"][:1]); changed_prefix[0]["versionTime"] = "different"
        with self.assertRaises(ValueError): verify_native_recovery(vector, changed_prefix)

    def test_kr_native_proof_signs_final_entry_not_predecessor_hash_input(self):
        vector = native_recovery_fixture(); entry = vector["log_entries"][1]
        unsigned = {k:v for k,v in entry.items() if k != "proof"}
        native_verify(unsigned, entry["proof"][0], entry["parameters"]["updateKeys"][0])
        unsigned["versionId"] = vector["log_entries"][0]["versionId"]
        with self.assertRaises(Exception): native_verify(unsigned, entry["proof"][0], entry["parameters"]["updateKeys"][0])

    def test_kr_recovery_wire_and_real_service_producer(self):
        case = signature_fixture()["cases"][4]
        payload = {**case["unsigned_projection"]["payload_without_control_signature"], "control_signature":case["signature"]}
        self.validator("realm-actor", "#/$defs/recovery_begin_payload").validate(payload)
        candidate=signature_fixture()["cases"][0]["candidate"]
        event={"event_id":token("event"),"kind":"ak.realm.actor.recovery.begin","scope_ref":{"kind":"realm_control","realm_id":token("realm")},"actor_id":{"kind":"service","service_id":candidate["service_id"]},"created_at":"2026-10-19T00:00:00.000Z","payload":payload,"applet_id":candidate["applet_id"],"producer_proof":{"kind":"detached_jws","verification_method":candidate["control_method_kid"],"event_digest":"sha256:"+"1"*64,"created_at":"2026-10-19T00:00:00.000Z","jws":"YQ..Yg"}}
        v=self.validator("event-envelope","#/$defs/shared_event_envelope");v.validate(event)
        for change in [{"actor_id":actor()},{"authorization_ref":token("grant")},{"executed_by":actor()},{"scope_ref":{"kind":"realm","realm_id":token("realm")}}]:
            self.assertFalse(v.is_valid({**event,**change}))
        for field in payload:
            bad=copy.deepcopy(payload);bad.pop(field)
            self.assertFalse(self.validator("realm-actor","#/$defs/recovery_begin_payload").is_valid(bad))

    def test_kr_recovery_pop_every_nested_binding(self):
        case=signature_fixture()["cases"][4];unsigned=case["unsigned_projection"]
        public=base64.urlsafe_b64decode(case["public_key_b64u"]+"=")
        for field in unsigned["payload_without_control_signature"]:
            bad=copy.deepcopy(unsigned);bad["payload_without_control_signature"].pop(field)
            self.assertFalse(verify(case["context"],bad,case["signature"],public))

    def test_kr_prepare_rejects_missing_authority_and_partial_effects(self):
        for invalid in [{"authenticated":False},{"manager":"foreign-service"},{"native_plan":False},{"pop":False},{"expired":True},{"crash":True}]:
            m=self.created();before=m.export();options={"manager":"old-service",**invalid}
            self.assertNotIsInstance(m.recovery_begin(actor(),"r",(0,0,1),**options),tuple)
            self.assertEqual(m.export(),before)
        m=self.created();before=m.export()
        self.assertEqual(m.recovery_begin(actor(2),"r",(0,0,1),manager="old-service"),"denied")
        self.assertEqual(m.export(),before)

    def test_kr_same_identity_fence_and_no_implicit_business_or_mls(self):
        m=self.created();r=m.rows[canonical(actor())];r["devices"]["old"]=1
        identity=canonical(actor());accepted=m.recovery_begin(actor(),"r",(0,0,1),manager="old-service")
        self.assertEqual(accepted,("accepted",1));self.assertEqual(r["generation"],2)
        self.assertFalse(m.business(actor(),"old"));self.assertEqual(r["control"],"old")
        self.assertFalse(m.rotate(actor(),0,"other",old_proof=True,new_pop=True,native_continuity=True))
        self.assertTrue(m.recovery_finish(actor(),1,manager="old-service"))
        self.assertIn(identity,m.rows);self.assertEqual(r["generation"],2);self.assertEqual(r["owner"],"paused")
        r["owner"]="active";r["devices"]["new"]=2
        self.assertFalse(m.business(actor(),"new"))
        r["cleanup"].clear();self.assertTrue(m.business(actor(),"new"));self.assertFalse(m.business(actor(),"old"))

    def test_kr_finish_publication_witness_crash_and_cas(self):
        for invalid in [{"authenticated":False},{"manager":"other"},{"published":False},{"matches":False},{"witness":False},{"crash":True}]:
            m=self.created();m.recovery_begin(actor(),"r",(0,0,1),manager="old-service");before=m.export()
            self.assertFalse(m.recovery_finish(actor(),1,**{"manager":"old-service",**invalid}))
            self.assertEqual(m.export(),before)
        m=self.created();m.recovery_begin(actor(),"r",(0,0,1),manager="old-service")
        self.assertFalse(m.recovery_finish(actor(),99,manager="old-service"))

    def test_kr_disable_cancel_retire_and_finish_races(self):
        m=self.created();m.recovery_begin(actor(),"r",(0,0,1),manager="old-service")
        self.assertTrue(m.recovery_policy(actor(),False,expected=1))
        self.assertFalse(m.recovery_finish(actor(),1,manager="old-service"))
        self.assertEqual(next(iter(m.private_inventory["outcomes"].values()))["state"],"cancelled")
        self.assertTrue(m.recovery_policy(actor(),True,expected=2))
        self.assertFalse(m.recovery_finish(actor(),1,manager="old-service"))
        m=self.created();m.recovery_begin(actor(),"r",(0,0,1),manager="old-service")
        self.assertTrue(m.recovery_finish(actor(),1,manager="old-service"))
        self.assertTrue(m.recovery_policy(actor(),False,expected=2))
        self.assertEqual(next(iter(m.private_inventory["outcomes"].values()))["state"],"completed")
        m=self.created();self.assertTrue(m.recovery_policy(actor(),True,expected=0,retire=True))
        self.assertEqual(m.recovery_begin(actor(),"r",(1,0,1),manager="old-service"),"denied")

    def test_kr_supersede_exact_replay_authenticated_and_expiry(self):
        m=self.created();first=m.recovery_begin(actor(),"r",(0,0,1),manager="old-service")
        self.assertEqual(m.recovery_begin(actor(),"r",(0,0,1),manager="old-service",expired=True),first)
        self.assertEqual(m.recovery_begin(actor(),"r",(0,0,1),manager="old-service",authenticated=False),"denied")
        self.assertEqual(m.recovery_begin(actor(),"r",(0,0,1),manager="old-service",intent_digest="changed"),"conflict")
        self.assertEqual(m.recovery_begin(actor(),"next",(1,0,2),manager="old-service"),"conflict")
        self.assertEqual(m.recovery_begin(actor(),"next",(1,0,2),manager="old-service",replaces=1),("accepted",2))
        self.assertFalse(m.recovery_finish(actor(),1,manager="old-service"));self.assertTrue(m.recovery_finish(actor(),2,manager="old-service"))

    def test_kr_governance_handoff_pending_and_pause_survive(self):
        m=self.created();m.rows[canonical(actor())]["governance"]="paused"
        m.recovery_begin(actor(),"r",(0,0,1),manager="old-service");export=m.export()
        successor=ControlModel.handoff(export,export,True)
        self.assertTrue(successor.recovery_finish(actor(),1,manager="old-service"))
        self.assertEqual(successor.rows[canonical(actor())]["governance"],"paused")
        for field in ["pending","recovery_enabled","cleanup"]:
            incomplete=copy.deepcopy(export);incomplete["rows"][canonical(actor())].pop(field)
            with self.assertRaises(ValueError):ControlModel.handoff(export,incomplete,True)

    def test_kr_private_recovery_current_and_terminal_carrier(self):
        value={"selector":{"kind":"realm_actor_recovery","actor_id":actor()},"source_stream_ref":committed()["stream_ref"],"revision":{ "commit_id":token("realm_commit"),"stream_position":0},"value":{"kind":"manager_native","enabled":True,"pending":None}}
        self.validator("typed-current-result","#/$defs/realm_actor_recovery_result").validate(value)
        self.validator("realm-actor-material","#/$defs/current_entry").validate({"status":"present","row":value})
        self.assertFalse(self.validator("realm-actor-material","#/$defs/current_entry").is_valid({"status":"never_written","selector":value["selector"]}))

    def test_kr_plan_is_not_published_evidence(self):
        plan = signature_fixture()["cases"][4]["unsigned_projection"]["payload_without_control_signature"]["method_history_evidence"]
        validator = self.validator("realm-actor", "#/$defs/webvh_recovery_plan")
        validator.validate(plan)
        published = self.validator("identity-resolution", "#/$defs/webvh_method_history_evidence")
        self.assertFalse(published.is_valid(plan))
        self.assertFalse(validator.is_valid({**plan, "evidence": {}}))
        vector = native_recovery_fixture()
        vector["witness_records"] = []
        verify_native_recovery(vector, require_witness=False)
        with self.assertRaises(ValueError):
            verify_native_recovery(vector)

    def test_kr_lifecycle_terminal_reference_is_mandatory(self):
        validator = self.validator("realm-actor-material", "#/$defs/outcome_record")
        for state in ["pending", "completed", "cancelled", "superseded"]:
            outcome = {"status": "recovery", "begin_ref": committed(), "state": state,
                       "terminal_ref": None if state == "pending" else committed(4, 2)}
            value = {"target_request_digest": "sha256:" + "1" * 64, "outcome": outcome}
            validator.validate(value)
            outcome["terminal_ref"] = committed(4, 2) if state == "pending" else None
            self.assertFalse(validator.is_valid(value))

    def created(self):
        model = ControlModel(token("realm")); model.create(actor(), "request", "digest", verified=True, allowed=True)
        return model


if __name__ == "__main__":
    unittest.main()
