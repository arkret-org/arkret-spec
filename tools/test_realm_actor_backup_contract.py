"""Real primitive and reference-state regressions for native backup custody."""
import copy
import json
import unittest

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from tools.realm_actor_backup_contract import *


class RealmActorBackupContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = fixture()
        cls.frozen = json.loads((ART / "fixtures/realm-actor-content-backup-fixture.json").read_text(encoding="utf-8"))

    def inputs(self):
        return copy.deepcopy((self.f["native_packet"], self.f["current_reference_cut"], self.f["active_series"]))

    def public(self):
        return unb64(self.f["test_material"]["device_public_base64url"])

    def private(self):
        return bytes.fromhex(self.f["test_material"]["archive_private_hex"])

    def sign_packet(self, packet):
        return sign_envelope(packet, bytes.fromhex(self.f["test_material"]["device_seed_hex"]))

    def sign_pointer(self, pointer, seed=None):
        seed = seed or bytes.fromhex(self.f["test_material"]["manager_seed_hex"])
        pointer["signature_proof"]["signature"] = b64(Ed25519PrivateKey.from_private_bytes(seed).sign(series_bytes(pointer)))
        return pointer

    def test_frozen_fixture_is_exactly_reproducible(self):
        self.assertEqual(self.frozen, self.f)

    def test_rfc9180_seal_open_and_original_ed_transcripts(self):
        packet = self.f["native_packet"]
        self.assertEqual(open_backup(packet,self.private(),self.public()),self.f["plaintext"])
        for name, actual in [("aad_hex",backup_aad(packet)),("info_hex",backup_info(packet)),
                ("signature_input_hex",envelope_bytes(packet)),("plaintext_hex",canonical(self.f["plaintext"]))]:
            self.assertEqual(actual.hex(),self.f["kat"][name])
        self.assertEqual(seal(unsigned_envelope(packet),self.f["plaintext"],
            unb64(self.f["recipient"]["public_key_base64url"]),
            bytes.fromhex(self.f["test_material"]["ephemeral_private_hex"]),
            bytes.fromhex(self.f["test_material"]["device_seed_hex"])),packet)

    def test_account_and_agent_aad_info_stay_byte_identical(self):
        old=json.loads((ART/"fixtures/content-history-fixture.json").read_text(encoding="utf-8"))["root_backup"]
        self.assertEqual(backup_aad(old["envelope"]).hex(),old["aad_hex"])
        self.assertEqual(backup_info(old["envelope"]).hex(),old["info_hex"])
        self.assertEqual(self.f["kat"]["account_aad_hex"],old["aad_hex"])
        golden=json.loads((ART/"fixtures/content-history-fixture.json").read_text(encoding="utf-8"))
        self.assertEqual(envelope_bytes(old["envelope"]).hex(),old["signing_hex"])
        legacy_plain=hpke_open(bytes.fromhex(golden["hpke_grant"]["recipient_private_hex"]),
            unb64(old["envelope"]["encryption"]["aead"]["enc"])+unb64(old["envelope"]["ciphertext"]),
            backup_info(old["envelope"]),backup_aad(old["envelope"]))
        self.assertEqual(json.loads(legacy_plain),old["plaintext"])
        legacy_public=Ed25519PrivateKey.from_private_bytes(bytes.fromhex(golden["kat"]["signing_seed_hex"])).public_key()
        legacy_public.verify(unb64(old["envelope"]["signature_proof"]["signature"]),bytes.fromhex(old["signing_hex"]))
        agent=copy.deepcopy(old["envelope"])
        agent["custodian_actor_id"]=old["envelope"]["actor_id"]
        agent["custody_authorization_ref"]=token("event",99)
        self.assertEqual(backup_aad(agent),backup_aad(old["envelope"]))
        self.assertNotIn("auth_binding",json.loads(backup_aad(agent)))

    def test_archive_key_is_exact_original_native_key_agreement(self):
        public=check_recipient(self.f["recipient"],self.f["native_history"],0)
        self.assertEqual(public,unb64(self.f["recipient"]["public_key_base64url"]))
        with self.assertRaises(ValueError):
            check_recipient(self.f["recipient"],self.f["native_history"],2)
        check_recipient(self.f["next_recipient"],self.f["native_history"],2)

    def test_key_agreement_substitution_low_order_and_native_history_forgery_fail(self):
        for change in ["key","method","zero","ed_method","padding","history"]:
            descriptor=copy.deepcopy(self.f["recipient"]);history=copy.deepcopy(self.f["native_history"])
            if change=="key": descriptor["public_key_base64url"]=self.f["next_recipient"]["public_key_base64url"]
            if change=="method": descriptor["key_agreement_ref"]+="-wrong"
            if change=="zero": descriptor["public_key_base64url"]=b64(bytes(32))
            if change=="ed_method": descriptor["key_agreement_ref"]=history["did"]+"#control-0"
            if change=="padding": descriptor["public_key_base64url"]+="="
            if change=="history": history["log_entries"][0]["state"]["keyAgreement"]=[history["did"]+"#control-0"]
            with self.subTest(change=change),self.assertRaises((ValueError,InvalidSignature)):
                check_recipient(descriptor,history,0)

    def test_auth_binding_enters_signature_and_aead_without_normalization(self):
        packet=copy.deepcopy(self.f["native_packet"])
        packet["auth_binding"]["device_generation"]+=1
        with self.assertRaises(InvalidSignature):open_backup(packet,self.private(),self.public())
        self.sign_packet(packet)
        with self.assertRaises(InvalidTag):open_backup(packet,self.private(),self.public())

    def test_ciphertext_recipient_and_public_index_tampering_fail(self):
        for change in ["ciphertext","recipient","index","plaintext"]:
            packet=copy.deepcopy(self.f["native_packet"])
            if change=="ciphertext":packet["ciphertext"]=b64(bytes(len(unb64(packet["ciphertext"]))))
            if change=="recipient":packet["encryption"]["recipient_key_ref"]+="-wrong"
            if change=="index":packet["contents"][0]["root_context"]["epoch"]="13"
            if change=="plaintext":packet["contents"][0]["root_ref"]="sha256:"+"0"*64
            self.sign_packet(packet)
            with self.subTest(change=change),self.assertRaises((ValueError,InvalidTag)):
                open_backup(packet,self.private(),self.public())
        with self.assertRaises(InvalidTag):
            open_backup(self.f["native_packet"],bytes.fromhex(self.f["test_material"]["next_archive_private_hex"]),self.public())

    def test_native_and_account_pcr_agent_branches_cannot_mix(self):
        packet=copy.deepcopy(self.f["native_packet"])
        for name,value in [("source_commit_ref",{"realm_commit_id":committed()["commit_id"],"device_generation_ref":1}),
                ("recovery_policy_ref",{"policy_id":"ak:policy:019a0000-0000-7000-8000-000000000011","policy_version":1}),
                ("custodian_actor_id",packet["actor_id"]),("custody_authorization_ref",token("event",21)),("kdf",{})]:
            mixed=copy.deepcopy(packet);mixed[name]=value
            with self.subTest(name=name),self.assertRaises(ValueError):validate_native_shape(mixed)
        for change in ["account","method","agent_proof","extra_auth","alias","null","boolean_generation","nonce","two_roots","other_item"]:
            mixed=copy.deepcopy(packet)
            if change=="account":mixed["actor_id"]={"kind":"account","account_id":{"principal_id":"ak:did_core:web:alice.example","station_id":"ak:did_core:web:station.example"}}
            if change=="method":mixed["encryption"]["recipient_method"]="recovery_public_key"
            if change=="agent_proof":mixed["signature_proof"]["agent_authorization_event_ref"]=token("event",22)
            if change=="extra_auth":mixed["auth_binding"]["x_extra"]=1
            if change=="alias":mixed["auth_binding"]["device_generation_ref"]=mixed["auth_binding"].pop("device_generation")
            if change=="null":mixed["auth_binding"]["recipient_ref"]=None
            if change=="boolean_generation":mixed["auth_binding"]["device_generation"]=True
            if change=="nonce":mixed["encryption"]["aead"]["nonce"]="AA"
            if change=="two_roots":mixed["contents"]*=2
            if change=="other_item":mixed["contents"][0]["item_kind"]="secret_storage"
            with self.subTest(change=change),self.assertRaises((ValueError,TypeError)):
                validate_native_shape(mixed)

    def test_signed_native_packet_rejects_caller_expiry_including_null(self):
        from tools.artifact_lint.core import schema_validator
        validator=schema_validator(ART/"schemas/key-backup.schema.json","")
        for expiry in ["2026-11-09T00:00:00.000Z",None]:
            packet,current,pointer=self.inputs()
            packet["expires_at"]=expiry
            self.sign_packet(packet)
            Ed25519PublicKey.from_public_bytes(self.public()).verify(
                unb64(packet["signature_proof"]["signature"]),envelope_bytes(packet))
            with self.subTest(expiry=expiry):
                self.assertFalse(validator.is_valid(packet))
                with self.assertRaises(ValueError):validate_native_shape(packet)
                with self.assertRaises(ValueError):open_backup(packet,self.private(),self.public())
                with self.assertRaises(ValueError):admit_packet(packet,current,pointer,self.public())

    def test_device_native_metadata_and_unlock_cannot_carry_caller_expiry(self):
        from tools.artifact_lint.core import schema_validator
        head=schema_validator(ART/"schemas/keys-operations.schema.json","#/$defs/realm_actor_backup_series_head_response_body")
        unlock=schema_validator(ART/"schemas/keys-operations.schema.json","#/$defs/realm_actor_backup_unlock_response_body")
        head.validate(self.f["device_head_response"])
        unlock.validate(self.f["device_unlock_response"])
        for expiry in ["2026-11-09T00:00:00.000Z",None]:
            page=copy.deepcopy(self.f["device_head_response"])
            page["items"][0]["metadata"]["expires_at"]=expiry
            response=copy.deepcopy(self.f["device_unlock_response"])
            response["backup"]["expires_at"]=expiry
            with self.subTest(expiry=expiry):
                self.assertFalse(head.is_valid(page))
                self.assertFalse(unlock.is_valid(response))

    def test_legacy_account_and_agent_signed_hpke_packets_keep_optional_expiry(self):
        from tools.artifact_lint.core import schema_validator
        golden=json.loads((ART/"fixtures/content-history-fixture.json").read_text(encoding="utf-8"))
        original=golden["root_backup"]["envelope"]
        validator=schema_validator(ART/"schemas/key-backup.schema.json","")
        signer=bytes.fromhex(golden["kat"]["signing_seed_hex"])
        public=Ed25519PrivateKey.from_private_bytes(signer).public_key()
        recipient_private=bytes.fromhex(golden["hpke_grant"]["recipient_private_hex"])
        recipient_public=X25519PrivateKey.from_private_bytes(recipient_private).public_key().public_bytes_raw()
        for author in ["account","agent"]:
            template=copy.deepcopy(original)
            if author=="agent":
                template.pop("source_commit_ref")
                template["custodian_actor_id"]=copy.deepcopy(original["actor_id"])
                template["custody_authorization_ref"]=token("event",89)
                template["actor_id"]["account_id"]["principal_id"]="ak:did_core:web:agent.example"
                template["signature_proof"].pop("device_id")
                template["signature_proof"].pop("device_authorize_event_id")
                template["signature_proof"]["agent_authorization_event_ref"]=token("event",90)
            for expiry in ["2026-11-09T00:00:00.000Z",None]:
                packet=copy.deepcopy(template)
                packet["expires_at"]=expiry
                packet=seal(packet,golden["root_backup"]["plaintext"],recipient_public,bytes([177])*32,signer)
                with self.subTest(author=author,expiry=expiry):
                    validator.validate(packet)
                    self.assertEqual(packet["expires_at"],expiry)
                    public.verify(unb64(packet["signature_proof"]["signature"]),envelope_bytes(packet))
                    plain=hpke_open(recipient_private,unb64(packet["encryption"]["aead"]["enc"])+unb64(packet["ciphertext"]),backup_info(packet),backup_aad(packet))
                    self.assertEqual(json.loads(plain),golden["root_backup"]["plaintext"])
                    self.assertEqual(backup_aad(packet),backup_aad(template))
                    self.assertEqual(backup_info(packet),backup_info(template))

    def test_disabled_identity_recovery_does_not_disable_real_device_publication(self):
        packet,current,pointer=self.inputs();current["recovery_enabled"]=False
        self.assertFalse(current["recovery_enabled"])
        result=admit_packet(packet,current,pointer,self.public())
        self.assertEqual(result["ciphertext_digest"],packet["ciphertext_digest"])
        select_series(pointer,None,current,unb64(self.f["test_material"]["manager_public_base64url"]))

    def test_recovery_source_advance_keeps_original_series_and_uses_current_packet_binding(self):
        packet,current,pointer=self.inputs()
        original_pointer=copy.deepcopy(pointer)
        original_recipient=copy.deepcopy(current["recipient"])
        manager_public=unb64(self.f["test_material"]["manager_public_base64url"])
        current["recovery_enabled"]=False
        current["recovery_ref"]={**committed(86,5),"stream_ref":copy.deepcopy(pointer["recovery_ref"]["stream_ref"])}
        self.assertNotEqual(current["recovery_ref"],pointer["recovery_ref"])
        store=ArchiveReference();before=copy.deepcopy(store.__dict__)
        with self.assertRaises(ValueError):store.put(packet,current,pointer,self.public())
        self.assertEqual(store.__dict__,before)
        unsigned=unsigned_envelope(packet)
        unsigned["auth_binding"]["recovery_ref"]=copy.deepcopy(current["recovery_ref"])
        packet=seal(unsigned,self.f["plaintext"],unb64(current["recipient"]["public_key_base64url"]),
            bytes.fromhex(self.f["test_material"]["ephemeral_private_hex"]),
            bytes.fromhex(self.f["test_material"]["device_seed_hex"]))
        self.assertEqual(open_backup(packet,self.private(),self.public()),self.f["plaintext"])
        result=store.put(packet,current,pointer,self.public())
        self.assertEqual(result["backup_id"],packet["backup_id"])
        Ed25519PublicKey.from_public_bytes(manager_public).verify(
            unb64(pointer["signature_proof"]["signature"]),series_bytes(pointer))
        self.assertEqual(pointer,original_pointer)
        self.assertEqual(current["recipient"],original_recipient)
        # Historical validity is not permission to select a new record with stale refs.
        with self.assertRaises(ValueError):select_series(pointer,None,current,manager_public)
        fresh=copy.deepcopy(pointer);fresh["recovery_ref"]=copy.deepcopy(current["recovery_ref"])
        self.sign_pointer(fresh)
        select_series(fresh,None,current,manager_public)

    def test_historical_series_recovery_ref_does_not_relax_other_current_gates(self):
        for field,value in [("manager_ref",committed(88,7)),("recipient_ref",committed(87,6)),
                ("pending",{"begin_ref":committed(90,9)}),("device_generation",2),
                ("owner_status","paused"),("governance_status","retired"),("actions",[])]:
            packet,current,pointer=self.inputs()
            current["recovery_ref"]={**committed(86,5),"stream_ref":copy.deepcopy(pointer["recovery_ref"]["stream_ref"])}
            unsigned=unsigned_envelope(packet)
            unsigned["auth_binding"]["recovery_ref"]=copy.deepcopy(current["recovery_ref"])
            if field in {"manager_ref","recipient_ref"}:
                value={**value,"stream_ref":copy.deepcopy(current[field]["stream_ref"])}
            current[field]=value
            if field in {"manager_ref","recipient_ref"}:
                unsigned["auth_binding"][field]=copy.deepcopy(value)
            packet=seal(unsigned,self.f["plaintext"],unb64(current["recipient"]["public_key_base64url"]),
                bytes.fromhex(self.f["test_material"]["ephemeral_private_hex"]),
                bytes.fromhex(self.f["test_material"]["device_seed_hex"]))
            store=ArchiveReference();before=copy.deepcopy(store.__dict__)
            with self.subTest(field=field),self.assertRaises(ValueError):
                store.put(packet,current,pointer,self.public())
            self.assertEqual(store.__dict__,before)

    def test_pending_retired_wrong_scope_old_manager_and_wrong_epoch_are_zero_effects(self):
        for field,value in [("pending",{"begin_ref":committed(90,9)}),("owner_status","paused"),
                ("governance_status","retired"),("device_generation",2),("device_id","different-device"),
                ("actions",[]),("manager_ref",committed(88,7)),("recipient_ref",committed(87,6)),
                ("recovery_ref",committed(86,5))]:
            packet,current,pointer=self.inputs();current[field]=value
            store=ArchiveReference();before=copy.deepcopy(store.__dict__)
            with self.subTest(field=field),self.assertRaises(ValueError):store.put(packet,current,pointer,self.public())
            self.assertEqual(store.__dict__,before)
        for field,value in [("epoch","13"),("group_state_ref",token("event",94)),("backup_strategy_ref",token("event",95))]:
            packet,current,pointer=self.inputs();current["root_context"][field]=value
            with self.assertRaises(ValueError):admit_packet(packet,current,pointer,self.public())

    def test_real_body_and_native_http_header_signature_refuses_each_mutation(self):
        case=self.f["http"]
        original=http_base(case["method"],case["uri"],case["headers"],case["signature_parameters"])
        self.assertEqual(original.hex(),case["signature_input_hex"])
        public=Ed25519PublicKey.from_public_bytes(self.public())
        public.verify(unb64(case["signature_base64url"]),original)
        for name in case["headers"]:
            headers=copy.deepcopy(case["headers"]);headers[name]+="changed"
            with self.subTest(header=name),self.assertRaises(InvalidSignature):
                public.verify(unb64(case["signature_base64url"]),http_base(case["method"],case["uri"],headers,case["signature_parameters"]))
        for method,uri,parameters in [("GET",case["uri"],case["signature_parameters"]),
                ("PUT",case["uri"]+"-other",case["signature_parameters"]),
                ("PUT",case["uri"],case["signature_parameters"].replace("1794096300","1794096301"))]:
            with self.assertRaises(InvalidSignature):public.verify(unb64(case["signature_base64url"]),http_base(method,uri,case["headers"],parameters))

    def test_unknown_put_result_cannot_create_publication_or_delete_custody(self):
        packet,current,pointer=self.inputs();store=ArchiveReference()
        result=store.put(packet,current,pointer,self.public())
        self.assertEqual(len(store.packets),1)
        issuer=unb64(self.f["admission_case"]["public_key_base64url"])
        with self.assertRaises(ValueError):store.acknowledge(packet,None,issuer)
        root=packet["contents"][0]
        with self.assertRaises(ValueError):store.dependencies(root["root_context"],root["root_ref"])
        self.assertEqual(len(store.packets),1)
        retry=store.put(packet,current,pointer,self.public());self.assertEqual(retry,result)
        store.acknowledge(packet,self.f["native_put_response"],issuer)
        self.assertEqual(store.dependencies(root["root_context"],root["root_ref"]),[packet["backup_id"]])

    def test_publication_acknowledgement_must_match_actual_packet(self):
        packet,current,pointer=self.inputs();store=ArchiveReference();store.put(packet,current,pointer,self.public())
        result=self.f["native_put_response"];issuer=unb64(self.f["admission_case"]["public_key_base64url"])
        for name in ["backup_id","ciphertext_digest"]:
            wrong=copy.deepcopy(result);wrong[name]+="wrong"
            with self.assertRaises(ValueError):store.acknowledge(packet,wrong,issuer)
        cold=ArchiveReference();cold.packets=copy.deepcopy(store.packets)
        cold.acknowledge(packet,result,issuer)
        self.assertEqual(cold.publications,{packet["backup_id"]:result})

    def test_immutable_retry_and_series_predecessor_cas(self):
        packet,current,pointer=self.inputs();store=ArchiveReference();store.put(packet,current,pointer,self.public())
        fork=copy.deepcopy(packet);fork["backup_version"]="different";self.sign_packet(fork)
        before=copy.deepcopy(store.__dict__)
        with self.assertRaises(ValueError):store.put(fork,current,pointer,self.public())
        self.assertEqual(store.__dict__,before)
        successor=copy.deepcopy(packet);successor.update(backup_id="ak:backup:019a0000-0000-7000-8000-000000000012",
            series_sequence=1,supersedes_id=packet["backup_id"],supersedes_digest=digest(unsigned_envelope(packet)));self.sign_packet(successor)
        self.assertEqual(store.put(successor,current,pointer,self.public())["backup_id"],successor["backup_id"])
        bad=copy.deepcopy(successor);bad["backup_id"]="ak:backup:019a0000-0000-7000-8000-000000000013";self.sign_packet(bad)
        with self.assertRaises(ValueError):store.put(bad,current,pointer,self.public())

    def test_private_circle_scope_series_counter_does_not_cross_scope(self):
        packet,current,pointer=self.inputs()
        first={"kind":"circle","realm_id":current["effective_scope"]["realm_id"],"circle_id":token("circle",71)}
        second={**first,"circle_id":token("circle",72)}
        pointer["effective_scope"]=first;self.sign_pointer(pointer)
        current["effective_scope"]=first
        select_series(pointer,None,current,unb64(self.f["test_material"]["manager_public_base64url"]))
        independent=copy.deepcopy(pointer);independent["effective_scope"]=second;self.sign_pointer(independent)
        current["effective_scope"]=second
        select_series(independent,None,current,unb64(self.f["test_material"]["manager_public_base64url"]))
        with self.assertRaises(ValueError):select_series(independent,pointer,current,unb64(self.f["test_material"]["manager_public_base64url"]))
        self.assertNotEqual(series_key(packet["actor_id"],first),series_key(packet["actor_id"],second))
        store=ArchiveReference();store.packets[packet["backup_id"]]=packet
        self.assertEqual(store.list_exact_scope(packet["actor_id"],second),[])

    def test_manager_series_signature_and_counter_cas_are_real(self):
        _,current,pointer=self.inputs();public=unb64(self.f["test_material"]["manager_public_base64url"])
        for field,value in [("series_pointer_version",2),("manager_ref",committed(91,11)),("recipient_ref",committed(92,12))]:
            changed=copy.deepcopy(pointer);changed[field]=value
            with self.assertRaises(InvalidSignature):select_series(changed,None,current,public)
            self.sign_pointer(changed)
            with self.assertRaises(ValueError):select_series(changed,None,current,public)
        changed=copy.deepcopy(pointer);changed["signature_proof"]["device_authorize_event_id"]=token("event",1)
        with self.assertRaises(ValueError):select_series(changed,None,current,public)

    def test_manager_handover_really_opens_all_old_root_packets(self):
        case=self.f["private_handover"];transfer=self.f["manager_handover"]
        new_public=unb64(transfer["new_manager_public_base64url"])
        actual=open_handover(case["sealed"],bytes.fromhex(self.f["test_material"]["next_archive_private_hex"]),
            new_public,self.f["inventory_cut"],"2026-11-08T00:00:02.000Z")
        self.assertEqual(actual,case["plaintext"])
        self.assertEqual(digest(actual),transfer["acceptance_input"]["content_backup_handover_digest"])
        self.assertEqual(digest(actual["inventory_manifest"]),transfer["acceptance_input"]["content_backup_inventory_digest"])
        self.assertTrue(verify("ak.realm_actor_manager_acceptance_signature.v1",transfer["acceptance_input"],
            transfer["acceptance"],new_public))

    def test_old_recipient_opens_history_but_cannot_authorize_current_put(self):
        packet,current,pointer=self.inputs()
        self.assertEqual(open_backup(packet,self.private(),self.public()),self.f["plaintext"])
        current["recipient"]=self.f["next_recipient"]
        current["recipient_ref"]=committed(93,13)
        current["manager_ref"]=committed(94,14)
        current["manager_method"]="did:web:new-manager.example#signing-1"
        with self.assertRaises(ValueError):admit_packet(packet,current,pointer,self.public())
        with self.assertRaises(ValueError):select_series(pointer,None,current,unb64(self.f["test_material"]["manager_public_base64url"]))

    def test_native_current_key_is_closed_actor_scope_domain_and_preserves_old_key(self):
        actor=self.f["native_packet"]["actor_id"]["realm_actor_id"]
        scope=self.f["current_reference_cut"]["effective_scope"]
        preimage,key=derive_native_series_current_key(actor,scope,"secret_storage")
        self.assertEqual(preimage,b"ak.current_key.realm_actor_key_backup_active_series.v1\n"+canonical([actor,scope,"secret_storage"]))
        other_actor={**actor,"principal_id":"ak:did_core:webvh:zDifferentActor"}
        circle={"kind":"circle","realm_id":scope["realm_id"],"circle_id":token("circle",21)}
        sibling={**circle,"circle_id":token("circle",22)}
        outputs=[derive_native_series_current_key(a,b,"secret_storage")[1] for a,b in [(actor,scope),(other_actor,scope),(actor,circle),(actor,sibling)]]
        self.assertEqual(len(set(outputs)),4)
        old_domain=b"ak.current_key.key_backup_active_series.v1\n"
        self.assertNotEqual(b64(hashlib.sha256(old_domain+canonical([actor,"secret_storage"])).digest()),key)
        for wrong_actor,wrong_scope,kind in [(self.f["native_packet"]["actor_id"],scope,"secret_storage"),
                (actor,{**scope,"realm_id":token("realm",22)},"secret_storage"),
                (actor,{"kind":"realm_control","realm_id":scope["realm_id"]},"secret_storage"),
                (actor,scope,"mls_state")]:
            with self.assertRaises(ValueError):derive_native_series_current_key(wrong_actor,wrong_scope,kind)

    def test_native_admission_generator_cannot_accept_fake_account_or_device_series(self):
        from tools.event_admission_contract import schema_definitions
        from tools.artifact_lint.core import load_json_schema_for_uri
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
        registry={"authority_commit_admission_contract":{"native_admission_classes":["realm_actor_backup"]},
            "admission_class_definitions":{"realm_actor_backup":{}},"event_kinds":[{
                "event_kind":"ak.key_backup.active_series","status":"active","wire_scope":"durable_event",
                "admission":"realm_actor_backup"}]}
        guard=schema_definitions(registry)["registered_admission_shape"]
        guard={"$id":"https://arkret.org/v1/schemas/event-envelope.schema.json",**guard}
        validator=Draft202012Validator(guard,registry=Registry(retrieve=lambda uri:Resource.from_contents(load_json_schema_for_uri(uri))))
        event={"kind":"ak.key_backup.active_series","actor_id":{"kind":"service","service_id":"ak:did_core:web:manager.example"},
            "scope_ref":{"kind":"realm_control","realm_id":token("realm",41)},
            "applet_id":"ak:applet:019a0000-0000-7000-8000-000000000011"}
        self.assertFalse(list(validator.iter_errors(event)))
        for failure in ["actor","scope","applet","executor","authorization"]:
            changed=copy.deepcopy(event)
            if failure=="actor":changed["actor_id"]=self.f["native_packet"]["actor_id"]
            if failure=="scope":changed["scope_ref"]["kind"]="realm"
            if failure=="applet":changed.pop("applet_id")
            if failure=="executor":changed["executed_by"]=None
            if failure=="authorization":changed["authorization_ref"]=None
            with self.subTest(failure=failure):self.assertTrue(list(validator.iter_errors(changed)))

    def test_all_registered_detached_context_kats_recompute_and_refuse_dropped_fields(self):
        for name in ["admission_case","handover_offer_case","handover_confirmation_case"]:
            case=self.f[name];public=unb64(case["public_key_base64url"])
            self.assertEqual(canonical(case["unsigned_projection"]).hex(),case["canonical_hex"])
            self.assertTrue(verify(case["context"],case["unsigned_projection"],case["signature"],public))
            envelope={key:value for key,value in case["signature"].items() if key!="signature"}
            self.assertEqual((case["context"].encode()+b"\n"+canonical(envelope)).hex(),case["signature_input_hex"])
            for key in case["unsigned_projection"]:
                wrong=copy.deepcopy(case["unsigned_projection"]);wrong.pop(key)
                with self.subTest(case=name,key=key):self.assertFalse(verify(case["context"],wrong,case["signature"],public))
            self.assertFalse(verify("ak.realm_actor_material_signature.v1",case["unsigned_projection"],case["signature"],public))

    def test_native_receipt_verifies_real_authorization_genesis_commit_fact_and_webvh(self):
        packet=self.f["native_packet"];source=self.f["native_source"]
        self.assertEqual(verify_native_receipt(packet,source),source["admission"])
        self.assertEqual(source["admission"]["envelope_digest"],digest(packet))
        self.assertNotIn("event_id",source["admission"])
        self.assertNotIn("commit_id",source["admission"])
        self.assertNotIn("current_assertion",canonical(source["governance_history"]).decode())
        self.assertNotIn("request_nonce",canonical(source["governance_history"]).decode())
        self.assertNotEqual(source["admission"]["device_public_key_base64url"],source["device_authorization"]["producer_signer_fact"]["public_key_base64url"])

    def test_real_source_authorization_and_historical_governance_mutations_fail(self):
        for failure in ["event","commit","fact","genesis","issuer","scope","generation","original_key","authorization_ref"]:
            source=copy.deepcopy(self.f["native_source"]);packet=self.f["native_packet"]
            if failure=="event":source["device_authorization"]["event"]["payload"]["authorized_generation_ref"]=2
            if failure=="commit":source["device_authorization"]["commit"]["stream_position"]=999
            if failure=="fact":source["device_authorization"]["producer_signer_fact"]["public_key_base64url"]=b64(bytes([42])*32)
            if failure=="genesis":source["governance_history"]["genesis"]["event"]["payload"]["object"]["governance_station_id"]="ak:did_core:web:attacker.example"
            if failure=="issuer":source["origin_resolution"]["normalized_did_document"]["services"][0]["endpoint"]="https://attacker.example/"
            if failure in ["scope","generation","original_key","authorization_ref"]:
                admission=source["admission"]
                if failure=="scope":admission["effective_scope"]={"kind":"circle","realm_id":packet["actor_id"]["realm_actor_id"]["realm_id"],"circle_id":token("circle",88)}
                if failure=="generation":admission["governance_generation"]="1"
                if failure=="original_key":admission["device_public_key_base64url"]=b64(bytes([42])*32)
                if failure=="authorization_ref":admission["device_authorize_ref"]["stream_position"]=3
                unsigned={name:value for name,value in admission.items() if name!="signature"}
                admission["signature"],_,_=sign("ak.realm_actor_content_backup_admission_signature.v1",unsigned,
                    bytes.fromhex(self.f["original_authority_reference"]["governor_seed_hex"]),admission["signature"]["verification_method"],admission["accepted_at"])
            with self.subTest(failure=failure),self.assertRaises((ValueError,InvalidSignature,KeyError)):
                verify_native_receipt(packet,source)

    def test_native_bound_put_refuses_old_reply_missing_original_receipt(self):
        response=copy.deepcopy(self.f["native_put_response"]);issuer=unb64(self.f["admission_case"]["public_key_base64url"])
        self.assertEqual(verify_device_put_response(self.f["native_packet"],response,issuer),response["admission"])
        response.pop("admission")
        from tools.artifact_lint.core import schema_validator
        schema_validator(ART/"schemas/keys-operations.schema.json","#/$defs/keys_backups_replace_response_body").validate(response)
        with self.assertRaises(ValueError):verify_device_put_response(self.f["native_packet"],response,issuer)

    def test_actual_schema_cases_and_native_private_crypto_hosts(self):
        from tools.artifact_lint.core import schema_validator, jsonschema_errors, Lint
        for case in self.f["schema_validation_cases"]:
            file,_,pointer=case["schema_ref"].partition("#")
            valid=schema_validator(ART/file,"#"+pointer if pointer else "").is_valid(case["instance"])
            self.assertEqual(valid,case["expect_valid"],case["name"])
            if not case["expect_valid"]:
                lint=Lint()
                errors=jsonschema_errors(lint,ART/"fixtures/realm-actor-content-backup-fixture.json",case["schema_ref"],case["instance"])
                self.assertEqual(lint.errors,[])
                self.assertTrue(errors,case["name"])
                self.assertEqual(case["first_expected_error"],errors[0],case["name"])
        cases=[("realm_actor_content_backup_source",self.f["native_source"]),
            ("realm_actor_archive_inventory_manifest",self.f["archive_inventory"]),
            ("realm_actor_content_backup_handover_offer",self.f["private_handover"]["sealed"]["offer"]),
            ("realm_actor_content_backup_handover_plaintext",self.f["private_handover"]["plaintext"]),
            ("realm_actor_content_backup_sealed_handover",self.f["private_handover"]["sealed"]),
            ("realm_actor_content_backup_handover_confirmation",self.f["private_handover"]["confirmation"])]
        for name,value in cases:
            errors=list(schema_validator(ART/"schemas/keys-operations.schema.json","#/$defs/"+name).iter_errors(value))
            self.assertEqual([error.message[:250] for error in errors],[],name)

    def test_device_replies_never_disclose_sibling_circle_authorization(self):
        from tools.artifact_lint.core import schema_validator
        sibling=self.f["native_source"]["device_authorization"]["event"]["payload"]["scopes"][1]["effective_scope"]["circle_id"]
        self.assertIn(sibling,canonical(self.f["native_source"]).decode())
        for name,definition in [("native_put_response","keys_backups_replace_response_body"),
                ("device_head_response","realm_actor_backup_series_head_response_body"),("device_unlock_response","realm_actor_backup_unlock_response_body")]:
            value=self.f[name];validator=schema_validator(ART/"schemas/keys-operations.schema.json","#/$defs/"+definition)
            validator.validate(value)
            self.assertNotIn(sibling,canonical(value).decode())
            bad=copy.deepcopy(value);bad["native_source"]=self.f["native_source"]
            self.assertFalse(validator.is_valid(bad),name)
        schema_validator(ART/"schemas/keys-operations.schema.json","#/$defs/realm_actor_archive_unlock_response_body").validate(self.f["manager_unlock_response"])

    def test_full_packet_receipt_and_unsigned_predecessor_are_distinct_digest_axes(self):
        packet=copy.deepcopy(self.f["native_packet"])
        changed=copy.deepcopy(packet);changed["signature_proof"]["signature"]=b64(bytes(64))
        self.assertNotEqual(digest(packet),digest(changed))
        self.assertEqual(digest(unsigned_envelope(packet)),digest(unsigned_envelope(changed)))
        self.assertEqual(self.f["native_source"]["admission"]["envelope_digest"],digest(packet))
        current=copy.deepcopy(self.f["current_reference_cut"]);pointer=self.f["active_series"]
        with self.assertRaises(ValueError):admit_packet(changed,current,pointer,self.public(),packet)

    def test_exact_retry_preserves_original_before_changed_business_epoch_or_series(self):
        packet,current,pointer=self.inputs()
        current["root_context"]["epoch"]="13";current["owner_status"]="paused";current["actions"]=[]
        pointer["active_series_id"]="ak:backup_series:019a0000-0000-7000-8000-000000000099"
        self.assertEqual(admit_packet(packet,current,pointer,self.public(),packet),"exact_retry")
        for name,value in [("device_generation",2),("device_id","retired-endpoint"),("governance_status","retired")]:
            stale=copy.deepcopy(current);stale[name]=value
            with self.assertRaises(ValueError):admit_packet(packet,stale,pointer,self.public(),packet)

    def test_frozen_inventory_includes_first_put_with_no_event_and_no_ack(self):
        manifest=self.f["archive_inventory"];packets,_=verify_inventory(manifest,self.f["inventory_cut"])
        self.assertEqual(set(packets),{self.f["native_packet"]["backup_id"]})
        self.assertNotIn("published_event",canonical(manifest).decode())
        self.assertNotIn("local_ack",canonical(manifest).decode())
        for failure in ["omit_first_put","duplicate","reorder","wrong_revision","rewritten_source"]:
            changed=copy.deepcopy(manifest)
            if failure=="omit_first_put":changed["entries"]=[row for row in changed["entries"] if row["kind"]!="backup"]
            if failure=="duplicate":changed["entries"].append(copy.deepcopy(changed["entries"][0]))
            if failure=="reorder":changed["entries"].reverse()
            if failure=="wrong_revision":changed["archive_revision"]+=1
            if failure=="rewritten_source":changed["entries"][0]["native_source"]["admission"]["accepted_at"]="2026-11-08T00:00:01.000Z"
            with self.subTest(failure=failure),self.assertRaises(ValueError):verify_inventory(changed,self.f["inventory_cut"])

    def test_handover_actual_hpke_secret_challenge_and_post_import_confirmation(self):
        case=self.f["private_handover"];cut=self.f["inventory_cut"]
        importer=ImportedArchiveReference();self.assertEqual(importer.imports,{})
        result=importer.import_and_confirm(case["sealed"],bytes.fromhex(self.f["test_material"]["next_archive_private_hex"]),bytes([152])*32,cut,"2026-11-08T00:00:02.000Z")
        self.assertEqual(result,case["confirmation"])
        self.assertEqual(importer.imports[digest(case["sealed"]["offer"])],case["plaintext"])
        self.assertEqual(verify_confirmation(result,case["sealed"]["offer"],case["plaintext"],
            unb64(self.f["manager_handover"]["new_manager_public_base64url"])),digest(case["plaintext"]))
        self.assertNotIn("challenge_base64url",canonical(result).decode())
        self.assertEqual(hpke_open(bytes.fromhex(self.f["test_material"]["next_archive_private_hex"]),
            unb64(case["sealed"]["enc"])+unb64(case["sealed"]["ciphertext_base64url"]),bytes.fromhex(case["info_hex"]),bytes.fromhex(case["aad_hex"])),canonical(case["plaintext"]))

    def test_handover_wrong_key_offer_context_ciphertext_and_replay_fail_before_import(self):
        case=self.f["private_handover"];cut=self.f["inventory_cut"];private=bytes.fromhex(self.f["test_material"]["next_archive_private_hex"])
        for failure in ["key","offer","ciphertext","wrong_cut","expired","offer_domain"]:
            sealed=copy.deepcopy(case["sealed"]);expected=copy.deepcopy(cut);secret=private;now="2026-11-08T00:00:02.000Z"
            if failure=="key":secret=bytes([99])*32
            if failure=="offer":sealed["offer"]["nonce"]=b64(bytes([9])*32)
            if failure=="ciphertext":sealed["ciphertext_base64url"]=b64(bytes(len(unb64(sealed["ciphertext_base64url"]))))
            if failure=="wrong_cut":expected["archive_revision"]+=1
            if failure=="expired":now="2026-11-08T00:05:00.000Z"
            if failure=="offer_domain":sealed["offer"]["signature"]["context"]="ak.realm_actor_content_backup_confirmation_signature.v1"
            importer=ImportedArchiveReference()
            with self.subTest(failure=failure),self.assertRaises((ValueError,InvalidTag)):importer.import_and_confirm(sealed,secret,bytes([152])*32,expected,now)
            self.assertEqual(importer.imports,{})

    def test_handover_resealed_but_missing_private_key_or_first_put_still_fails(self):
        case=self.f["private_handover"];new_private=bytes.fromhex(self.f["test_material"]["next_archive_private_hex"])
        public=X25519PrivateKey.from_private_bytes(new_private).public_key().public_bytes_raw()
        for failure in ["missing_key","wrong_private","duplicate_key","missing_first_put","wrong_root"]:
            plain=copy.deepcopy(case["plaintext"])
            if failure=="missing_key":plain["recipient_keys"]=[]
            if failure=="wrong_private":plain["recipient_keys"][0]["private_key_base64url"]=b64(bytes([19])*32)
            if failure=="duplicate_key":plain["recipient_keys"]*=2
            if failure=="missing_first_put":plain["inventory_manifest"]["entries"]=[entry for entry in plain["inventory_manifest"]["entries"] if entry["kind"]!="backup"]
            if failure=="wrong_root":plain["inventory_manifest"]["entries"][0]["backup"]["contents"][0]["root_ref"]="sha256:"+"0"*64
            sealed=copy.deepcopy(case["sealed"])
            blob=hpke_seal(bytes([188])*32,public,handover_info(sealed["offer"]),canonical(plain),canonical(sealed["offer"]))
            sealed["enc"]=b64(blob[:32]);sealed["ciphertext_base64url"]=b64(blob[32:])
            importer=ImportedArchiveReference()
            with self.subTest(failure=failure),self.assertRaises((ValueError,InvalidTag)):importer.import_and_confirm(sealed,new_private,bytes([152])*32,self.f["inventory_cut"],"2026-11-08T00:00:02.000Z")
            self.assertEqual(importer.imports,{})

    def test_valid_new_service_signature_cannot_replace_decrypted_challenge_answer(self):
        case=self.f["private_handover"];public=unb64(self.f["manager_handover"]["new_manager_public_base64url"])
        for field,value in [("offer_digest","sha256:"+"0"*64),("handover_digest","sha256:"+"1"*64),
                ("inventory_digest","sha256:"+"2"*64),("challenge_response_base64url",b64(bytes(32)))]:
            changed=copy.deepcopy(case["confirmation"]);changed[field]=value
            unsigned={name:item for name,item in changed.items() if name!="signature"}
            changed["signature"],_,_=sign("ak.realm_actor_content_backup_confirmation_signature.v1",unsigned,bytes([152])*32,
                changed["signature"]["verification_method"],changed["signature"]["created_at"])
            with self.subTest(field=field),self.assertRaises(ValueError):verify_confirmation(changed,case["sealed"]["offer"],case["plaintext"],public)

    def test_gate_cannot_green_on_changed_plaintext_receipt_or_import_confirmation(self):
        from tools.artifact_lint.realm_actor_backup import validate_fixture
        for failure in ["plaintext","source","confirmation","transcript","missing_namespace"]:
            changed=copy.deepcopy(self.f)
            if failure=="plaintext":changed["plaintext"]["items"][0]["root_base64url"]=b64(bytes(32))
            if failure=="source":changed["native_source"]["admission"]["envelope_digest"]="sha256:"+"0"*64
            if failure=="confirmation":changed["private_handover"]["confirmation"]["challenge_response_base64url"]=b64(bytes(32))
            if failure=="transcript":changed["kat"]["aad_hex"]="00"
            if failure=="missing_namespace":changed["archive_inventory"]["entries"]=[]
            with self.subTest(failure=failure),self.assertRaises(Exception):validate_fixture(changed)

    def test_complete_native_series_event_has_no_ordinary_or_account_bypass(self):
        from tools.artifact_lint.core import schema_validator
        event=next(entry["source"]["event"] for entry in self.f["archive_inventory"]["entries"] if entry["kind"]=="series")
        validator=schema_validator(ART/"schemas/event-envelope.schema.json","")
        validator.validate(event)
        for failure in ["account_actor","realm_actor","ordinary_scope","account_payload","missing_applet","executor","authorization"]:
            changed=copy.deepcopy(event)
            if failure=="account_actor":changed["actor_id"]={"kind":"account","account_id":{"principal_id":"ak:did_core:web:alice.example","station_id":"ak:did_core:web:station.example"}}
            if failure=="realm_actor":changed["actor_id"]=self.f["native_packet"]["actor_id"]
            if failure=="ordinary_scope":changed["scope_ref"]["kind"]="realm"
            if failure=="account_payload":changed["payload"]["actor_id"]={"kind":"account","account_id":{"principal_id":"ak:did_core:web:alice.example","station_id":"ak:did_core:web:station.example"}}
            if failure=="missing_applet":changed.pop("applet_id")
            if failure=="executor":changed["executed_by"]=None
            if failure=="authorization":changed["authorization_ref"]=None
            with self.subTest(failure=failure):self.assertFalse(validator.is_valid(changed))

    def test_positive_full_crypto_gate_uses_current_canonical_sources(self):
        from tools.artifact_lint.realm_actor_backup import validate_fixture
        validate_fixture(self.f)

    def test_first_expected_errors_are_checked_instead_of_accepting_any_rejection(self):
        from tools.artifact_lint.realm_actor_backup import validate_fixture
        for failure in ["missing","changed"]:
            changed=copy.deepcopy(self.f)
            case=next(case for case in changed["schema_validation_cases"] if not case["expect_valid"])
            if failure=="missing":case.pop("first_expected_error")
            else:case["first_expected_error"]="invented unrelated schema error"
            with self.subTest(failure=failure),self.assertRaises(ValueError):validate_fixture(changed)

    def test_decision_cases_recompute_crypto_and_reference_acknowledgement(self):
        self.assertEqual(self.f["decision_cases"],execute_decision_cases(self.f))
        self.assertEqual(len(self.f["decision_cases"]),2)
        from tools.artifact_lint.realm_actor_backup import validate_fixture
        for failure in ["removed_case","invented_result","wrong_key","missing_admission"]:
            changed=copy.deepcopy(self.f)
            if failure=="removed_case":changed["decision_cases"].pop()
            if failure=="invented_result":changed["decision_cases"][1]["expected"]["local_freeze_without_ack_refused"]=False
            if failure=="wrong_key":changed["test_material"]["archive_private_hex"]=(bytes([183])*32).hex()
            if failure=="missing_admission":changed["native_put_response"].pop("admission")
            with self.subTest(failure=failure),self.assertRaises(Exception):validate_fixture(changed)

    def test_each_native_backup_operation_requires_its_own_original_exact_scope_action(self):
        packet=self.f["native_packet"];current=self.f["current_reference_cut"]
        for operation in NATIVE_BACKUP_OPERATIONS:
            for actions,valid in [([operation],True),([],False),([value for value in NATIVE_BACKUP_OPERATIONS if value!=operation],False)]:
                source=admission_fixture(packet,current,self.f["recipient"],self.f["native_history"],
                    bytes.fromhex(self.f["test_material"]["device_seed_hex"]),authorized_actions=actions)
                authorization=source["device_authorization"]
                verify_reference_original(authorization,source["origin_resolution"])
                args=(authorization,source["origin_resolution"],packet["actor_id"],packet["device_id"],1,
                    current["effective_scope"],operation,self.f["native_source"]["admission"]["accepted_at"])
                with self.subTest(operation=operation,actions=actions):
                    if valid:self.assertEqual(verify_native_device_operation(*args)[0],source["device_authorize_ref"])
                    else:
                        with self.assertRaises(ValueError):verify_native_device_operation(*args)

    def test_unsigned_schema_inputs_exclude_the_signature_and_preserve_full_host_fields(self):
        from tools.artifact_lint.core import schema_validator
        for name in ["admission_case","handover_offer_case","handover_confirmation_case"]:
            case=self.f[name];file,_,pointer=case["unsigned_schema_ref"].partition("#")
            validator=schema_validator(ART/file,"#"+pointer)
            validator.validate(case["unsigned_projection"])
            self.assertFalse(validator.is_valid({**case["unsigned_projection"],"signature":case["signature"]}))

    def test_native_current_and_material_projection_are_minimal_and_reachable(self):
        from tools.artifact_lint.core import schema_validator
        current=self.f["native_current"]
        validator=schema_validator(ART/"schemas/current-state.schema.json","#/$defs/current_realm_actor_key_backup_active_series")
        validator.validate(current)
        schema_validator(ART/"schemas/realm-actor-material.schema.json","#/$defs/current_entry").validate(self.f["native_current_entry"])
        self.assertEqual(set(current["value"]),{"active_series_id","series_pointer_version","manager_ref","recovery_ref","recipient_ref"})
        expanded=copy.deepcopy(current);expanded["value"]=self.f["active_series"]
        self.assertFalse(validator.is_valid(expanded))
        for field in ["previous_series_ids","signature_proof","schema","actor_id","effective_scope"]:
            changed=copy.deepcopy(current);changed["value"][field]=self.f["active_series"][field]
            with self.subTest(field=field):self.assertFalse(validator.is_valid(changed))


if __name__=="__main__":unittest.main()
