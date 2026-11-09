"""Positive/negative crypto, closed-schema and canonical source mutation tests."""
import copy
import json
import unittest
import hashlib
from pathlib import Path

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tools.content_history import SCHEME, STRATEGY, aad, content_key, content_root, jcs, key_commitment, unb64, root_ref
from tools.content_history import b64, hpke_context, hpke_seal, hpke_open, grant_header, mnemonic_backup_key, verify_root_index, coverage_pages, inventory_digest, cleanup_digest, ordered_roster, verify_roster_keys, verify_recovery_source, recovery_path_leaf, authorize_history_read, roster_pages
from tools.generate_content_history_fixture import build
from tools.content_history import verify_external_recovery_binding
from tools.content_history import qualify_history_request, qualify_history_grant
from tools.content_history import verify_preparation_resource

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "spec/v1/artifacts"


class ContentHistoryContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        docs = [json.loads(path.read_text(encoding="utf-8")) for path in (ART / "schemas").glob("*.schema.json")]
        cls.resources = Registry().with_resources((d["$id"], Resource.from_contents(d)) for d in docs)
        cls.fixture = json.loads((ART / "fixtures/content-history-fixture.json").read_text(encoding="utf-8"))

    def validate(self, schema, value):
        Draft202012Validator({"$ref": "https://arkret.org/v1/schemas/" + schema}, registry=self.resources).validate(value)

    def invalid(self, schema, value):
        with self.assertRaises(Exception) as caught:
            self.validate(schema, value)
        self.assertIn("ValidationError", type(caught.exception).__name__)

    def test_pcr_private_profile_has_a_typed_whole_envelope_slot(self):
        envelope = self.fixture["kat"]["envelope"]
        profile = {"principal_id": self.fixture["kat"]["outer_event"]["actor_id"]["account_id"]["principal_id"],
                   "actor_kind": "user", "display_name": "Public name", "encrypted_private_fields": envelope}
        schema = "actor-profile.schema.json#/$defs/actor_profile_definition"
        self.validate(schema, profile)
        self.invalid(schema, {**profile, "encrypted_private_fields": None})
        self.invalid(schema, {**profile, "encrypted_private_fields": {"profile_fields": {"biography": "private"}}})
        realm_profile = {"actor_kind": "bot", "display_name": "Bot", "actor_id": {"kind": "realm", "realm_actor_id": {
            "realm_id": self.fixture["kat"]["outer_event"]["realm_id"], "principal_id": profile["principal_id"]}}}
        self.validate(schema, realm_profile)
        self.invalid(schema, {**realm_profile, "encrypted_private_fields": envelope})
        target = "ak:actor_profile:" + self.fixture["kat"]["outer_event"]["realm_id"].split(":", 2)[2]
        update = "event-payload.schema.json#/$defs/actor_profile_update_payload"
        for slot in (envelope, {"$op": "set", "value": envelope}):
            self.validate(update, {"target_ref": target, "patch": {"encrypted_private_fields": slot}})
        for slot in (None, {"$op": "unset"}, {"$op": "remove", "value": envelope}, {"op": "set", "value": envelope}):
            self.invalid(update, {"target_ref": target, "patch": {"encrypted_private_fields": slot}})
        self.invalid(update, {"target_ref": target, "patch": {"encrypted_private_fields.ciphertext": "changed"}})
        self.invalid("event-payload.schema.json#/$defs/profile_realm_override_payload", {
            "target_ref": target, "target_realm_id": self.fixture["kat"]["outer_event"]["realm_id"],
            "patch": {"encrypted_private_fields": envelope}})

    def test_private_profile_plaintext_is_closed_and_uses_registered_fresh_content_domain(self):
        plain = {"profile_fields": {"biography": "private profile", "locale": "zh-CN"}}
        self.validate("actor-profile.schema.json#/$defs/private_profile_fields", plain)
        self.invalid("actor-profile.schema.json#/$defs/private_profile_fields", {**plain, "device_authorization": {}})
        self.invalid("actor-profile.schema.json#/$defs/private_profile_fields", {"profile_fields": {"biography": "x" * 257}})
        k = self.fixture["kat"]
        context = copy.deepcopy(k["content_context"])
        context["content_key_salt"] = b64(bytes([213]) * 32)
        self.validate("content-encryption.schema.json#/$defs/content_context", context)
        root = bytes.fromhex(k["root_hex"])
        key = content_key(root, context)
        self.assertNotEqual(key.hex(), k["key_hex"])
        outer = {**k["outer_event"], "kind": "ak.profile.create"}
        envelope = copy.deepcopy(k["envelope"])
        envelope["encryption_context"]["content_key_salt"] = context["content_key_salt"]
        envelope["encryption_context"]["key_commitment"] = key_commitment(key, context)
        associated = aad(outer, envelope, context)
        encrypted = AESGCM(key).encrypt(bytes(12), jcs(plain), associated)
        self.assertEqual(json.loads(AESGCM(key).decrypt(bytes(12), encrypted, associated)), plain)
        with self.assertRaises(InvalidTag):
            AESGCM(bytes.fromhex(k["key_hex"])).decrypt(bytes(12), encrypted, associated)
        with self.assertRaises(InvalidTag):
            AESGCM(key).decrypt(bytes(12), encrypted, aad(k["outer_event"], envelope, context))

    def test_frozen_kat_and_original_ciphertext(self):
        self.assertEqual(self.fixture, build())
        k = self.fixture["kat"]
        root = content_root(bytes.fromhex(k["exporter_secret_hex"]), k["root_context"])
        self.assertEqual(root.hex(), k["root_hex"])
        key = content_key(root, k["content_context"])
        self.assertEqual(key.hex(), k["key_hex"])
        associated = aad(k["outer_event"], k["envelope"], k["content_context"])
        self.assertEqual(associated.hex(), k["aad_hex"])
        self.assertEqual(AESGCM(key).decrypt(bytes(12), unb64(k["envelope"]["ciphertext"]), associated).hex(), k["plaintext_hex"])
        signer = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(k["signing_seed_hex"]))
        signer.public_key().verify(unb64(k["signature_base64url"]), bytes.fromhex(k["primitive_original_transcript_hex"]))
        with self.assertRaises(InvalidSignature):
            signer.public_key().verify(unb64(k["signature_base64url"]), bytes.fromhex(k["primitive_original_transcript_hex"]) + b" ")

    def test_external_recovery_uses_existing_cbor_binding_in_rfc_authenticated_data(self):
        for case in self.fixture["external_recovery_binding"]["cases"]:
            binding = case["binding"]
            encoded = bytes.fromhex(case["encoded_map_hex"])
            inherited = b"exact accepted base extensions"
            verify_external_recovery_binding(binding, encoded, inherited, inherited)
            for altered in (b"", jcs(binding), b"prefix" + encoded, encoded + b" "):
                with self.assertRaises(ValueError):
                    verify_external_recovery_binding(binding, altered, inherited, inherited)
            changed = copy.deepcopy(binding); changed["next_epoch"] = "43"
            with self.assertRaises(ValueError):
                verify_external_recovery_binding(changed, encoded, inherited, inherited)
            with self.assertRaises(ValueError):
                verify_external_recovery_binding(binding, encoded, inherited + b"changed policy", inherited)

    def test_scheme_is_mandatory_distinct_and_closed(self):
        envelope = self.fixture["kat"]["envelope"]
        self.validate("encrypted-envelope.schema.json", envelope)
        for value in (None, "application/json", STRATEGY, "ak.encryption.future.v1", "ak.encryption.mls_private_message.v1"):
            altered = copy.deepcopy(envelope)
            if value is None:
                del altered["encryption_scheme"]
            else:
                altered["encryption_scheme"] = value
            self.invalid("encrypted-envelope.schema.json", altered)
        for field in ("content_key_salt", "root_ref", "key_commitment"):
            altered = copy.deepcopy(envelope)
            del altered["encryption_context"][field]
            self.invalid("encrypted-envelope.schema.json", altered)

    def test_scope_epoch_strategy_and_endpoint_separation(self):
        k = self.fixture["kat"]
        root = bytes.fromhex(k["root_hex"])
        expected = bytes.fromhex(k["key_hex"])
        for field, value in (("epoch", "13"), ("backup_strategy_ref", "ak:event:" + "A" * 44), ("encryption_backup_strategy", "ak.encryption_backup.future.v1")):
            coordinate = copy.deepcopy(k["root_context"])
            coordinate[field] = value
            self.assertNotEqual(content_root(bytes.fromhex(k["exporter_secret_hex"]), coordinate), root)
        changed = copy.deepcopy(k["content_context"])
        changed["producer"]["endpoint"]["device_id"] = "ak:device:019a0000-0000-7000-8000-000000000002"
        self.assertNotEqual(content_key(root, changed), expected)
        for field, value in (("purpose", "blob_content"), ("content_key_salt", "A" * 43)):
            changed = copy.deepcopy(k["content_context"])
            changed[field] = value
            wrong = content_key(root, changed)
            self.assertNotEqual(wrong, expected)
            self.assertNotEqual(key_commitment(wrong, changed), k["envelope"]["encryption_context"]["key_commitment"])
            with self.assertRaises(InvalidTag):
                AESGCM(wrong).decrypt(bytes(12), unb64(k["envelope"]["ciphertext"]), bytes.fromhex(k["aad_hex"]))

    def test_original_metadata_and_ciphertext_are_authenticated(self):
        k = self.fixture["kat"]
        changed = copy.deepcopy(k["envelope"])
        changed["content_type"] = "application/octet-stream"
        with self.assertRaises(InvalidTag):
            AESGCM(bytes.fromhex(k["key_hex"])).decrypt(bytes(12), unb64(k["envelope"]["ciphertext"]), aad(k["outer_event"], changed, k["content_context"]))
        ct = bytearray(unb64(k["envelope"]["ciphertext"]))
        ct[0] ^= 1
        with self.assertRaises(InvalidTag):
            AESGCM(bytes.fromhex(k["key_hex"])).decrypt(bytes(12), bytes(ct), bytes.fromhex(k["aad_hex"]))

    def test_registry_and_kdf_canonical_binding(self):
        catalog = json.loads((ART / "registry/contract-registry.json").read_text(encoding="utf-8"))
        contract = catalog["content_encryption_contract"]
        self.assertEqual(contract["scheme"], SCHEME)
        self.assertEqual(contract["strategy"], STRATEGY)
        self.assertEqual(contract["unknown_selector"], "reject_without_fallback")
        registry = json.loads((ART / "registry/content-encryption-registry.json").read_text(encoding="utf-8"))
        self.assertEqual([r["scheme_id"] for r in registry["schemes"] if r["status"] == "active"], [SCHEME])
        labels = json.loads((ART / "registry/exporter-label-registry.json").read_text(encoding="utf-8"))["labels"]
        self.assertEqual(next(r for r in labels if r["label"] == "ak.content-v1")["parent_secret"], "ak.epoch-content-root-v1")
        self.assertFalse(contract["external_commit"]["membership_creation"])
        self.assertFalse(contract["external_commit"]["intermediate_business_writes"])
        self.assertEqual(contract["external_commit"]["cleanup_authorization"], "current_recovery_replacement_exact_same_actor_inventory_only_without_admin_escalation")
        schema = json.loads((ART / "schemas/realm-genesis.schema.json").read_text(encoding="utf-8"))
        self.assertIn("initial_encryption_backup_strategy", schema["required"])
        schema = json.loads((ART / "schemas/realm.schema.json").read_text(encoding="utf-8"))
        self.assertIn("encryption_backup_strategy", schema["required"])

    def test_ready_requires_crypto_cleanup_and_closed_carriers(self):
        cut = {"event_id": self.fixture["kat"]["root_context"]["genesis_event_ref"], "commit_id": "ak:realm_commit:" + "A" * 44,
               "stream_ref": {"kind": "realm", "realm_id": self.fixture["kat"]["root_context"]["effective_scope"]["realm_id"]}, "stream_position": 0}
        value = {"state": "ready", "pcr_cut": cut, "coverage_head_digest": "sha256:" + "1" * 64,
                 "restored_event_count": "12", "cleanup_inventory_digest": "sha256:" + "2" * 64, "cleanup_completed": True,
                 "replacement": self.fixture["kat"]["content_context"]["producer"],
                 "inventory_blob_ref": "ak:blob:sha256:" + "3" * 64, "cleanup_blob_ref": "ak:blob:sha256:" + "4" * 64}
        self.validate("content-encryption.schema.json#/$defs/history_recovery", value)
        value["cleanup_completed"] = False
        self.invalid("content-encryption.schema.json#/$defs/history_recovery", value)

    def test_history_grant_identifies_the_exact_body_or_attachment(self):
        k = self.fixture["kat"]
        source = k["root_context"]["group_state_ref"]
        cut = {"event_id": source, "commit_id": "ak:realm_commit:" + "A" * 44,
               "stream_ref": {"kind": "realm", "realm_id": k["root_context"]["effective_scope"]["realm_id"]}, "stream_position": 0}
        grant = copy.deepcopy(self.fixture["hpke_grant"]["grant"])
        self.validate("content-encryption.schema.json#/$defs/history_grant", grant)
        missing = copy.deepcopy(grant)
        del missing["entries"][0]["selector"]["content_path"]
        self.invalid("content-encryption.schema.json#/$defs/history_grant", missing)
        extra = copy.deepcopy(grant)
        extra["plaintext"] = "replacement archive"
        self.invalid("content-encryption.schema.json#/$defs/history_grant", extra)

    def test_root_backup_forbids_live_state_and_dependency_omission(self):
        k = self.fixture["kat"]
        item = {"item_kind": "content_epoch_root", "secret_id": "root_12", "root_context": k["root_context"],
                "root_ref": k["content_context"]["root_ref"], "root_base64url": "A" * 43}
        self.validate("content-encryption.schema.json#/$defs/content_epoch_root", item)
        item["exporter_secret"] = "A" * 43
        self.invalid("content-encryption.schema.json#/$defs/content_epoch_root", item)
        for key in ("root_refs", "backup_refs"):
            value = copy.deepcopy(k["envelope"])
            value["encryption_context"]["protection"][key] = []
            self.invalid("encrypted-envelope.schema.json", value)

    def test_recovery_roster_requires_key_projection_only_on_recovery_pages(self):
        definitions = json.loads((ART / "schemas/mls-roster-authority.schema.json").read_text(encoding="utf-8"))["$defs"]
        conditional = definitions["self_roster_read_response_body"]["allOf"][0]
        validator = Draft202012Validator(conditional)
        for kind, keys, valid in (("recovery", False, False), ("recovery", True, True), ("add", True, False), ("add", False, True)):
            value = {"roster": {"records": [{"kind": kind}]}}
            if keys:
                value["recovery_signing_keys"] = [{"record_digest": "sha256:" + "1" * 64, "public_key_base64url": "A" * 43}]
            self.assertEqual(validator.is_valid(value), valid)
        recovery = definitions["roster_recovery_record"]
        self.assertEqual(recovery["required"], ["kind", "commit_event", "covering_commit", "producer_signer_fact", "recovery_source", "base_group_info_ref", "base_ratchet_tree_ref"])
        restriction = recovery["properties"]["commit_event"]["allOf"][1]
        self.assertEqual(restriction["properties"]["payload"]["required"], ["recovery_binding"])
        for field in ("semantic_refs", "external_ref"):
            self.assertFalse(Draft202012Validator(restriction).is_valid({"payload": {"recovery_binding": {}}, field: []}))

    def test_agent_recovery_signer_fact_is_closed_and_not_a_current_key_lookup(self):
        k = self.fixture["kat"]
        source = k["root_context"]["group_state_ref"]
        value = {"kind": "agent_runtime", "event_ref": source, "actor_id": k["content_context"]["producer"]["actor_id"],
                 "verification_method": "did:key:z6MknativeAgent#runtime", "public_key_base64url": "A" * 43,
                 "authorization_event_ref": source, "accepted_at": "2026-11-08T01:00:00.000Z"}
        schema = "authority-commit-operations.schema.json#/$defs/agent_runtime_historical_signer_fact"
        self.validate(schema, value)
        for field in ("event_ref", "authorization_event_ref", "verification_method"):
            altered = copy.deepcopy(value)
            del altered[field]
            self.invalid(schema, altered)
        value["verified"] = True
        self.invalid(schema, value)

    def test_recovery_binding_is_exact_and_cannot_grant_membership(self):
        k = self.fixture["kat"]
        value = {"replacement": k["content_context"]["producer"],
                 "authorization_event_ref": k["root_context"]["group_state_ref"],
                 "base_group_state_ref": k["root_context"]["group_state_ref"],
                 "expected_epoch": "12", "inventory_digest": "sha256:" + "1" * 64}
        schema = "content-encryption.schema.json#/$defs/recovery_binding"
        self.validate(schema, value)
        for field in value:
            altered = copy.deepcopy(value)
            del altered[field]
            self.invalid(schema, altered)
        value["create_membership"] = True
        self.invalid(schema, value)

    def test_pcr_grants_have_only_exact_current_agent_custody_self_disclosure(self):
        profiles = json.loads((ART / "profiles/conformance-profiles.json").read_text(encoding="utf-8"))
        def find(value):
            if isinstance(value, dict):
                policy = value.get("realm_event_kind_policy", {})
                allowed = policy.get("allowed_event_kinds", [])
                if "ak.agent.key.authorize" in allowed:
                    return allowed
                for child in value.values():
                    result = find(child)
                    if result:
                        return result
            elif isinstance(value, list):
                for child in value:
                    result = find(child)
                    if result:
                        return result
            return None
        self.assertIn("ak.mls.history_grant", find(profiles))
        exposure = json.loads((ART / "registry/pcr-exposure-registry.json").read_text(encoding="utf-8"))
        rows = [row for value in exposure.values() if isinstance(value, list) for row in value if isinstance(row, dict) and row.get("event_kind") == "ak.mls.history_grant"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["exposures"]), 2)
        for carrier in rows[0]["exposures"]:
            self.assertEqual(carrier["authorization_policy_id"], "ak.pcr_exposure_policy.current_agent_history_custodian.v1")
            self.assertTrue(carrier["operation_id"].startswith("ak.self.committed_event."))
            self.assertEqual(carrier["direction"], "response")
            self.assertEqual(carrier["anti_enumeration_policy_id"], "ak.pcr_anti_enumeration.indistinguishable_not_found.v1")

    def test_hpke_reference_matches_independent_pinned_rfc_vector(self):
        v = json.loads((ART / "fixtures/hpke-suite-fixture.json").read_text(encoding="utf-8"))["vectors"][0]
        h = lambda name: bytes.fromhex(v[name])
        dh = X25519PrivateKey.from_private_bytes(h("skEm_hex")).exchange(X25519PublicKey.from_public_bytes(h("pkRm_hex")))
        key, nonce = hpke_context(dh, h("enc_hex"), h("pkRm_hex"), h("info_hex"))
        self.assertEqual(key, h("key_hex")); self.assertEqual(nonce, h("base_nonce_hex"))
        e = v["encryptions"][0]
        self.assertEqual(hpke_open(h("skRm_hex"), h("enc_hex") + bytes.fromhex(e["ct_hex"]), h("info_hex"), bytes.fromhex(e["aad_hex"])), bytes.fromhex(e["pt_hex"]))

    def test_hpke_grant_roundtrip_uses_exact_request_and_header(self):
        f = self.fixture["hpke_grant"]; g = f["grant"]
        self.validate("content-encryption.schema.json#/$defs/history_grant", g)
        for entry, kat in zip(g["entries"], f["entries"]):
            header = grant_header(g, entry["selector"])
            self.assertEqual(header.hex(), kat["info_hex"])
            self.assertEqual(hpke_open(bytes.fromhex(f["recipient_private_hex"]), unb64(entry["sealed_key_base64url"]), header).hex(), kat["plaintext_hex"])
            changed = copy.deepcopy(g); changed["recipient_key_event_ref"] = self.fixture["kat"]["root_context"]["group_state_ref"]
            with self.assertRaises(InvalidTag):
                hpke_open(bytes.fromhex(f["recipient_private_hex"]), unb64(entry["sealed_key_base64url"]), grant_header(changed, entry["selector"]))

    def _history_request(self):
        request = copy.deepcopy(self.fixture["hpke_grant"]["grant"])
        request.pop("entries"); request.pop("recipient_key_event_ref")
        return request

    def test_history_authorization_has_one_endpoint_reference_and_no_opaque_scope_grant(self):
        grant = self.fixture["hpke_grant"]["grant"]
        request = self._history_request()
        self.assertNotIn("authorization_event_ref", grant)
        self.assertNotIn("authorization_event_ref", request)
        for name, value in (("history_request", request), ("history_grant", grant)):
            self.validate("content-encryption.schema.json#/$defs/" + name, value)
            stale = copy.deepcopy(value)
            stale["authorization_event_ref"] = value["recipient"]["authorization_event_ref"]
            self.invalid("content-encryption.schema.json#/$defs/" + name, stale)
            missing = copy.deepcopy(value); del missing["recipient"]["authorization_event_ref"]
            self.invalid("content-encryption.schema.json#/$defs/" + name, missing)

    def test_nested_endpoint_authorization_is_authenticated_by_hpke(self):
        case = self.fixture["hpke_grant"]; grant = case["grant"]; entry = grant["entries"][0]
        mutations = {
            "authorization_event_ref": grant["recipient_key_event_ref"],
            "signature_key_base64url": b64(bytes([99]) * 32),
            "endpoint": {"kind": "device", "device_id": "ak:device:019a0000-0000-7000-8000-000000000099"},
        }
        for field, value in mutations.items():
            changed = copy.deepcopy(grant); changed["recipient"][field] = value
            with self.assertRaises(InvalidTag):
                hpke_open(bytes.fromhex(case["recipient_private_hex"]),
                          unb64(entry["sealed_key_base64url"]), grant_header(changed, entry["selector"]))

    def test_readonly_request_uses_native_leaf_binding_with_independent_event_key(self):
        request = self._history_request(); endpoint = request["recipient"]
        event_key = Ed25519PrivateKey.from_private_bytes(bytes([81]) * 32)
        event_public = b64(event_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
        self.assertNotEqual(event_public, endpoint["signature_key_base64url"])
        args = (endpoint["actor_id"], endpoint["endpoint"], endpoint["authorization_event_ref"],
                endpoint, True, "2026-11-08T00:00:00.000Z", "2026-11-08T00:01:00.000Z")
        self.assertEqual(qualify_history_request(request, *args), endpoint)
        altered = list(args); altered[4] = False
        with self.assertRaises(ValueError): qualify_history_request(request, *altered)
        for index, value in ((0, {"kind": "service", "service_id": "ak:did_core:web:other.example"}),
                             (1, {"kind": "device", "device_id": "ak:device:019a0000-0000-7000-8000-000000000099"}),
                             (2, self.fixture["hpke_grant"]["grant"]["recipient_key_event_ref"])):
            altered = list(args); altered[index] = value
            with self.assertRaises(ValueError): qualify_history_request(request, *altered)
        low_order = copy.deepcopy(request); low_order["recipient_hpke_key_base64url"] = b64(bytes(32))
        with self.assertRaises(ValueError): qualify_history_request(low_order, *args)
        # Native current qualification is independent of the older history cut.
        later = copy.deepcopy(request); later["recipient"]["authorization_event_ref"] = self.fixture["hpke_grant"]["grant"]["recipient_key_event_ref"]
        args = (later["recipient"]["actor_id"], later["recipient"]["endpoint"],
                later["recipient"]["authorization_event_ref"], later["recipient"], True,
                "2026-11-08T00:00:30.000Z", "2026-11-08T00:01:00.000Z")
        self.assertEqual(qualify_history_request(later, *args), later["recipient"])

    def test_new_grant_rechecks_disclosure_read_selection_and_original_request(self):
        grant = self.fixture["hpke_grant"]["grant"]; request = self._history_request(); endpoint = request["recipient"]
        args = [grant["recipient_key_event_ref"], request, endpoint["actor_id"], endpoint["endpoint"],
                endpoint["authorization_event_ref"], endpoint, True, True, True,
                "2026-11-08T00:00:00.000Z", "2026-11-08T00:01:00.000Z"]
        self.assertEqual(qualify_history_grant(grant, *args), endpoint)
        for index in (6, 7, 8):
            denied = args.copy(); denied[index] = False
            with self.assertRaises(ValueError): qualify_history_grant(grant, *denied)
        expired = args.copy(); expired[-1] = grant["expires_at"]
        with self.assertRaises(ValueError): qualify_history_grant(grant, *expired)
        for field, value in (("recipient_key_event_ref", endpoint["authorization_event_ref"]),
                             ("recipient_hpke_key_base64url", b64(bytes([99]) * 32)),
                             ("expires_at", "2026-11-08T00:14:00.000Z")):
            altered = copy.deepcopy(grant); altered[field] = value
            with self.assertRaises(ValueError): qualify_history_grant(altered, *args)

    def test_hpke_rejects_old_short_encoding_wrong_recipient_and_truncation(self):
        f = self.fixture["hpke_grant"]; g = f["grant"]; entry = g["entries"][0]; encoded = entry["sealed_key_base64url"]
        for value in ("AQID", encoded[:-1], encoded + "=", b64(unb64(encoded)[32:])):
            altered = copy.deepcopy(g); altered["entries"][0]["sealed_key_base64url"] = value
            self.invalid("content-encryption.schema.json#/$defs/history_grant", altered)
        with self.assertRaises(InvalidTag): hpke_open(bytes([7]) * 32, unb64(encoded), grant_header(g, entry["selector"]))
        for index in (0, 33, len(unb64(encoded)) - 1):
            changed = bytearray(unb64(encoded)); changed[index] ^= 1
            with self.assertRaises((InvalidTag, ValueError)): hpke_open(bytes.fromhex(f["recipient_private_hex"]), bytes(changed), grant_header(g, entry["selector"]))
        with self.assertRaises(ValueError): hpke_seal(bytes([3]) * 32, bytes(32), b"header", bytes(16))

    def test_mnemonic_derivation_matches_existing_kdf_and_reopens_root_backup(self):
        v = json.loads((ART / "fixtures/identity-recovery-kdf-fixture.json").read_text(encoding="utf-8"))["cases"][0]
        private, public = mnemonic_backup_key(v["input"]["mnemonic_utf8"], v["input"]["passphrase_utf8"])
        self.assertEqual(private.hex(), v["expected"]["backup_hpke_serialized_private_key_hex"])
        self.assertEqual(public.hex(), v["expected"]["backup_hpke_public_key_hex"])
        f = self.fixture["root_backup"]
        private, _ = mnemonic_backup_key(self.fixture["hpke_grant"]["mnemonic"])
        sealed = unb64(f["envelope"]["encryption"]["aead"]["enc"]) + unb64(f["envelope"]["ciphertext"])
        opened = json.loads(hpke_open(private, sealed, bytes.fromhex(f["info_hex"]), bytes.fromhex(f["aad_hex"])))
        self.assertEqual(opened, f["plaintext"])
        verify_root_index(f["envelope"], opened)
        self.validate("key-backup.schema.json", f["envelope"])
        self.validate("key-backup-plaintext.schema.json", opened)
        signer = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.fixture["kat"]["signing_seed_hex"]))
        signer.public_key().verify(unb64(f["envelope"]["signature_proof"]["signature"]), bytes.fromhex(f["signing_hex"]))

    def test_root_index_complete_envelope_rejects_mismatch_and_daily_recipient(self):
        f = self.fixture["root_backup"]
        for field in ("root_ref", "root_context"):
            altered = copy.deepcopy(f["envelope"]); del altered["contents"][0][field]
            self.invalid("key-backup.schema.json", altered)
        for field, value in (("root_ref", "sha256:" + "0" * 64), ("secret_id", "different")):
            altered = copy.deepcopy(f["envelope"]); altered["contents"][0][field] = value
            with self.assertRaises(ValueError): verify_root_index(altered, f["plaintext"])
        altered = copy.deepcopy(f["envelope"]); altered["encryption"]["recipient_method"] = "secret_storage_key"
        self.invalid("key-backup.schema.json", altered)
        altered = copy.deepcopy(f["plaintext"]); altered["items"] *= 2
        with self.assertRaises(ValueError): verify_root_index(f["envelope"], altered)

    def test_fresh_backup_context_excludes_old_block_key_and_daily_material(self):
        f = self.fixture["root_backup"]; g = self.fixture["hpke_grant"]; public = X25519PrivateKey.from_private_bytes(bytes.fromhex(g["recipient_private_hex"])).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        info, associated = bytes.fromhex(f["info_hex"]), bytes.fromhex(f["aad_hex"])
        coordinate = copy.deepcopy(self.fixture["kat"]["root_context"])
        coordinate["epoch"] = "13"; coordinate["group_state_ref"] = g["grant"]["recipient_key_event_ref"]
        future_root = content_root(bytes([233]) * 32, coordinate)
        future_bag = copy.deepcopy(f["plaintext"])
        future_bag["items"][0].update({"root_context": coordinate, "root_ref": root_ref(future_root, coordinate), "root_base64url": b64(future_root)})
        new = hpke_seal(bytes([144]) * 32, public, info, jcs(future_bag), associated)
        self.assertEqual(json.loads(hpke_open(bytes.fromhex(g["recipient_private_hex"]), new, info, associated)), future_bag)
        for old in (bytes.fromhex(self.fixture["kat"]["root_hex"]), bytes(range(32)), bytes([9]) * 32):
            with self.assertRaises(InvalidTag): hpke_open(old, new, info, associated)
        def context(secret):
            e = X25519PrivateKey.from_private_bytes(secret); enc = e.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
            return hpke_context(e.exchange(X25519PublicKey.from_public_bytes(public)), enc, public, info)
        old_key, _ = context(bytes([133]) * 32); new_key, nonce = context(bytes([144]) * 32)
        self.assertNotEqual(old_key, new_key)
        with self.assertRaises(InvalidTag): ChaCha20Poly1305(old_key).decrypt(nonce, new[32:], associated)
        item_context = copy.deepcopy(self.fixture["kat"]["content_context"])
        item_context.update({"root_context": coordinate, "root_ref": root_ref(future_root, coordinate), "content_key_salt": b64(bytes([199]) * 32)})
        associated_content = jcs(item_context)
        future_message = AESGCM(content_key(future_root, item_context)).encrypt(bytes(12), b"future content", associated_content)
        with self.assertRaises(InvalidTag): AESGCM(content_key(bytes.fromhex(self.fixture["kat"]["root_hex"]), item_context)).decrypt(bytes(12), future_message, associated_content)

    def _history_intent(self):
        f = self.fixture["root_backup"]; actor = f["envelope"]["actor_id"]; signer = Ed25519PrivateKey.from_private_bytes(bytes([211]) * 32)
        current = {"actor_id": actor, "device_id": "ak:device:019a0000-0000-7000-8000-000000000002", "generation": 2, "authorized_generation": 2,
                   "verification_method": "did:key:z6Mknew#device", "public_key_base64url": b64(signer.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)), "lifecycle": "active", "now": "2026-11-08T00:01:00.000Z"}
        source = {"subject_actor_id": actor, "reference": self.fixture["hpke_grant"]["grant"]["history_cut"], "protection": self.fixture["kat"]["envelope"]["encryption_context"]["protection"]}
        proof = {"schema": "ak.schema.key_backup_unlock_proof.v1", "kind": "current_device", "account_id": actor["account_id"], "requesting_device_id": current["device_id"],
                 **{k: f["envelope"][k] for k in ("backup_id", "backup_kind", "series_id", "ciphertext_digest")}, "challenge_id": "A" * 22, "challenge": "A" * 43, "nonce": "B" * 43,
                 "audience": "https://example.test", "service_id": actor["account_id"]["station_id"], "issued_at": "2026-11-08T00:00:00.000Z", "expires_at": "2026-11-08T00:04:00.000Z",
                 "content_history": {"source": source["reference"], "root_refs": source["protection"]["root_refs"]}, "signature_proof": {"verification_method": current["verification_method"], "signature_algorithm": "Ed25519"}}
        proof["signature_proof"]["signature"] = b64(signer.sign(jcs(proof)))
        challenge = {k: v for k, v in proof.items() if k not in ("schema", "kind", "signature_proof")}
        return proof, challenge, current, source

    def test_generation_fence_and_completed_session_do_not_block_current_history_intent(self):
        proof, challenge, current, source = self._history_intent()
        self.validate("key-backup-unlock-proof.schema.json", proof)
        envelope = self.fixture["root_backup"]["envelope"]
        self.assertEqual(envelope["source_commit_ref"]["device_generation_ref"], 1)
        for _ in range(3):
            self.assertEqual(authorize_history_read(*json.loads(json.dumps([proof, challenge, current, source, envelope]))), set(proof["content_history"]["root_refs"]))
        old = copy.deepcopy(current); old["authorized_generation"] = 1
        with self.assertRaises(ValueError): authorize_history_read(proof, challenge, old, source, envelope)
        old = copy.deepcopy(current); old["lifecycle"] = "revoked"
        with self.assertRaises(ValueError): authorize_history_read(proof, challenge, old, source, envelope)

    def test_history_intent_rejects_replay_wrong_source_and_expiry(self):
        proof, challenge, current, source = self._history_intent(); envelope = self.fixture["root_backup"]["envelope"]
        for field, value in (("nonce", "C" * 43), ("ciphertext_digest", "sha256:" + "0" * 64), ("requesting_device_id", self.fixture["kat"]["content_context"]["producer"]["endpoint"]["device_id"])):
            altered = copy.deepcopy(proof); altered[field] = value
            with self.assertRaises(ValueError): authorize_history_read(altered, challenge, current, source, envelope)
        altered = copy.deepcopy(source); altered["protection"]["root_refs"] = []
        with self.assertRaises(ValueError): authorize_history_read(proof, challenge, current, altered, envelope)
        expired = copy.deepcopy(current); expired["now"] = "2026-11-08T00:05:00.000Z"
        with self.assertRaises(ValueError): authorize_history_read(proof, challenge, expired, source, envelope)
        altered = copy.deepcopy(proof); altered["recovery_session_id"] = "ak:recovery_session:019a0000-0000-7000-8000-000000000001"
        self.invalid("key-backup-unlock-proof.schema.json", altered)

    def test_agent_custody_is_on_provision_before_any_runtime(self):
        data = json.loads((ART / "fixtures/content-bound-event-id-fixture.json").read_text(encoding="utf-8"))
        case = next(x for x in data["cases"] if x["name"] == "agent_provision_declares_the_frozen_genesis_realm_id")
        value = json.loads(case["digest_preimage_canonical_bytes_utf8"])["payload"]
        value["history_custody"] = {"custodian_actor_id": self.fixture["kat"]["content_context"]["producer"]["actor_id"],
                                    "recovery_policy_ref": self.fixture["root_backup"]["envelope"]["recovery_policy_ref"], "recipient_key_ref": "did:key:z6Mkfixture#backup"}
        self.validate("agent-provision.schema.json", value)
        missing = copy.deepcopy(value); del missing["history_custody"]
        self.invalid("agent-provision.schema.json", missing)
        schema = json.loads((ART / "schemas/event-payload.schema.json").read_text(encoding="utf-8"))
        self.assertNotIn("history_custody", schema["$defs"]["agent_key_authorize_payload"]["properties"])

    def test_agent_runtime_backup_signer_does_not_fabricate_device_generation(self):
        value = copy.deepcopy(self.fixture["root_backup"]["envelope"])
        controller = value["actor_id"]
        value["actor_id"] = {"kind": "account", "account_id": {**controller["account_id"], "principal_id": "ak:did_core:webvh:z6mkagent"}}
        value["custodian_actor_id"] = controller
        value["custody_authorization_ref"] = self.fixture["kat"]["root_context"]["genesis_event_ref"]
        value.pop("source_commit_ref")
        proof = value["signature_proof"]; proof.pop("device_id"); proof.pop("device_authorize_event_id")
        proof["agent_authorization_event_ref"] = self.fixture["hpke_grant"]["grant"]["recipient_key_event_ref"]
        self.validate("key-backup.schema.json", value)
        for field, item in (("source_commit_ref", self.fixture["root_backup"]["envelope"]["source_commit_ref"]), ("device_id", self.fixture["kat"]["content_context"]["producer"]["endpoint"]["device_id"])):
            bad = copy.deepcopy(value); bad[field] = item
            self.invalid("key-backup.schema.json", bad)
        bad = copy.deepcopy(value); bad["signature_proof"]["device_id"] = self.fixture["kat"]["content_context"]["producer"]["endpoint"]["device_id"]
        self.invalid("key-backup.schema.json", bad)

    def test_controller_subject_intent_is_explicit_and_wrong_controller_denied(self):
        proof, challenge, current, source = self._history_intent()
        envelope = copy.deepcopy(self.fixture["root_backup"]["envelope"])
        subject = {"kind": "account", "account_id": {**envelope["actor_id"]["account_id"], "principal_id": "ak:did_core:webvh:z6mkagent"}}
        custody = self.fixture["hpke_grant"]["grant"]["recipient_key_event_ref"]
        envelope.update({"actor_id": subject, "custodian_actor_id": current["actor_id"], "custody_authorization_ref": custody})
        source["subject_actor_id"] = subject; current["custody_authorization_ref"] = custody; current["custody_subject_actor_id"] = subject
        for value in (proof, challenge): value.update({"subject_actor_id": subject, "custody_authorization_ref": custody})
        proof["signature_proof"].pop("signature")
        proof["signature_proof"]["signature"] = b64(Ed25519PrivateKey.from_private_bytes(bytes([211]) * 32).sign(jcs(proof)))
        self.validate("key-backup-unlock-proof.schema.json", proof)
        self.assertEqual(authorize_history_read(proof, challenge, current, source, envelope), set(proof["content_history"]["root_refs"]))
        wrong = copy.deepcopy(current); wrong["custody_authorization_ref"] = "ak:event:" + "A" * 44
        with self.assertRaises(ValueError): authorize_history_read(proof, challenge, wrong, source, envelope)
        wrong = copy.deepcopy(envelope); wrong["custody_authorization_ref"] = "ak:event:" + "A" * 44
        with self.assertRaises(ValueError): authorize_history_read(proof, challenge, current, source, wrong)
        bad = copy.deepcopy(proof); del bad["custody_authorization_ref"]
        self.invalid("key-backup-unlock-proof.schema.json", bad)
        bad = copy.deepcopy(proof); bad["kind"] = "recovery_session"; bad["recovery_session_id"] = "ak:recovery_session:019a0000-0000-7000-8000-000000000001"; bad.pop("challenge_id"); bad.pop("nonce")
        self.invalid("key-backup-unlock-proof.schema.json", bad)

    def test_coverage_has_one_partition_and_detects_omission_or_duplicate_original(self):
        scope = self.fixture["kat"]["root_context"]["effective_scope"]
        entries, backups = [], {}
        for i in range(257):
            event = "ak:event:" + b64(b"\x01" + i.to_bytes(32, "big"))
            source = {"event_id": event, "commit_id": "ak:realm_commit:" + "A" * 44, "stream_ref": scope, "stream_position": i}
            entries.append({"source": source, "root_refs": [], "blob_refs": []}); backups[event] = []
        pages = coverage_pages(scope, entries[0]["source"]["event_id"], entries[-1]["source"], entries, backups)
        self.assertEqual([len(x["entries"]) for x in pages], [256, 1])
        self.assertEqual(pages[1]["previous_page_digest"], pages[0]["page_digest"])
        for page in pages: self.validate("content-encryption.schema.json#/$defs/coverage", page)
        for altered in (entries[:-1], entries[:100] + entries[101:], [*entries[:1], entries[0], *entries[2:]]):
            with self.assertRaises(ValueError): coverage_pages(scope, entries[0]["source"]["event_id"], entries[-1]["source"], altered, backups)
        self.assertEqual(coverage_pages(scope, entries[0]["source"]["event_id"], entries[-1]["source"], json.loads(json.dumps(entries)), backups), pages)

    def _inventory(self):
        k = self.fixture["kat"]; endpoint = k["content_context"]["producer"]
        entries = []
        for i in range(2):
            entries.append({"effective_scope": k["root_context"]["effective_scope"], "genesis_event_ref": "ak:event:" + b64(b"\x01" + bytes([i + 65]) * 32),
                            "base_group_state_ref": k["root_context"]["group_state_ref"], "epoch": "12",
                            "old_leaves": [] if i == 0 else [{"leaf_index": 1, "endpoint": endpoint}]})
        entries.sort(key=lambda row: jcs({k: row[k] for k in ("effective_scope", "genesis_event_ref")}))
        replacement = copy.deepcopy(endpoint)
        replacement["endpoint"]["device_id"] = "ak:device:019a0000-0000-7000-8000-000000000002"
        replacement["signature_key_base64url"] = b64(Ed25519PrivateKey.from_private_bytes(bytes([211]) * 32).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
        inventory = {"actor_id": endpoint["actor_id"], "replacement": replacement, "authorization_event_ref": replacement["authorization_event_ref"],
                     "pcr_cut": self.fixture["hpke_grant"]["grant"]["history_cut"], "entries": entries}
        return inventory

    def test_inventory_includes_empty_scopes_and_exact_ordered_cleanup(self):
        inventory = self._inventory(); self.validate("content-encryption.schema.json#/$defs/recovery_inventory", inventory)
        self.assertTrue(any(not x["old_leaves"] for x in inventory["entries"]))
        original = inventory_digest(inventory)
        omitted = copy.deepcopy(inventory); omitted["entries"] = [x for x in omitted["entries"] if x["old_leaves"]]
        self.assertNotEqual(original, inventory_digest(omitted))
        bad = copy.deepcopy(inventory); bad["entries"].reverse()
        with self.assertRaises(ValueError): inventory_digest(bad)
        reused = copy.deepcopy(inventory); reused["replacement"]["signature_key_base64url"] = self.fixture["kat"]["content_context"]["producer"]["signature_key_base64url"]
        with self.assertRaises(ValueError): inventory_digest(reused)
        results = [{"state": "rekeyed", "effective_scope": x["effective_scope"], "genesis_event_ref": x["genesis_event_ref"], "winning_commit": inventory["pcr_cut"],
                    "remaining_old_leaf_count": 0, "root_refs": [self.fixture["kat"]["content_context"]["root_ref"]],
                    "backup_refs": self.fixture["kat"]["envelope"]["encryption_context"]["protection"]["backup_refs"]} for x in inventory["entries"]]
        value = {"inventory_digest": original, "scope_cleanups": results}; self.validate("content-encryption.schema.json#/$defs/cleanup_inventory", value)
        self.assertTrue(cleanup_digest(inventory, results).startswith("sha256:"))
        for rows in (results[:-1], list(reversed(results)), [results[0], results[0]]):
            with self.assertRaises(ValueError): cleanup_digest(inventory, rows)
        bad = copy.deepcopy(results); bad[1]["remaining_old_leaf_count"] = 1
        with self.assertRaises(ValueError): cleanup_digest(inventory, bad)

    def test_first_preparation_is_discovered_from_original_authorization_without_checkpoint(self):
        inventory = self._inventory()
        source = inventory["replacement"]
        authorization = source["authorization_event_ref"]
        pending = {"state": "pending", "replacement": source, "pcr_cut": inventory["pcr_cut"]}
        schema = "content-encryption.schema.json#/$defs/recovery_preparation"
        self.validate(schema, pending)
        verify_preparation_resource(pending, authorization, source, inventory["pcr_cut"])
        prepared = {**pending, "state": "prepared", "inventory_blob_ref": "ak:blob:sha256:" + hashlib.sha256(jcs(inventory)).hexdigest()}
        self.validate(schema, prepared)
        verify_preparation_resource(prepared, authorization, source, inventory["pcr_cut"], pending)
        verify_preparation_resource(prepared, authorization, source, inventory["pcr_cut"], prepared)
        for changed in ({**pending, "inventory_blob_ref": prepared["inventory_blob_ref"]},
                        {**pending, "state": "ready"}, {**prepared, "inventory_blob_ref": None},
                        {**prepared, "cleanup_completed": True}):
            self.invalid(schema, changed)
        missing = copy.deepcopy(prepared); missing.pop("inventory_blob_ref")
        self.invalid(schema, missing)
        realm = copy.deepcopy(prepared)
        realm["replacement"]["actor_id"] = {"kind": "realm", "realm_actor_id": {
            "realm_id": inventory["entries"][0]["effective_scope"]["realm_id"],
            "principal_id": source["actor_id"]["account_id"]["principal_id"]}}
        self.invalid(schema, realm)
        wrong_token = bytearray(unb64(authorization.rsplit(":", 1)[1])); wrong_token[-1] ^= 1
        with self.assertRaises(ValueError):
            verify_preparation_resource(prepared, "ak:event:" + b64(bytes(wrong_token)), source, inventory["pcr_cut"])
        changed = copy.deepcopy(prepared); changed["pcr_cut"]["stream_position"] = str(int(changed["pcr_cut"]["stream_position"]) + 1)
        with self.assertRaises(ValueError): verify_preparation_resource(changed, authorization, source, inventory["pcr_cut"])
        with self.assertRaises(ValueError): verify_preparation_resource(pending, authorization, source, inventory["pcr_cut"], prepared)
        changed = {**prepared, "inventory_blob_ref": "ak:blob:sha256:" + "f" * 64}
        with self.assertRaises(ValueError): verify_preparation_resource(changed, authorization, source, inventory["pcr_cut"], prepared)
        changed = copy.deepcopy(prepared); changed["replacement"]["signature_key_base64url"] = b64(bytes([19]) * 32)
        with self.assertRaises(ValueError): verify_preparation_resource(changed, authorization, source, inventory["pcr_cut"])

    def test_no_activated_group_has_an_empty_census_without_fabricating_genesis(self):
        inventory = self._inventory(); inventory["entries"] = []
        self.validate("content-encryption.schema.json#/$defs/recovery_inventory", inventory)
        cleanup = {"inventory_digest": inventory_digest(inventory), "scope_cleanups": []}
        self.validate("content-encryption.schema.json#/$defs/cleanup_inventory", cleanup)
        self.assertEqual(cleanup_digest(inventory, []), "sha256:" + hashlib.sha256(b"ak.content.cleanup_inventory.v1\n" + jcs(cleanup)).hexdigest())
        activated = self._inventory(); activated["entries"] = [activated["entries"][0]]
        activated["entries"][0]["old_leaves"] = []
        self.assertNotEqual(inventory_digest(inventory), inventory_digest(activated))
        with self.assertRaises(ValueError): cleanup_digest(activated, [])

    def test_preparation_registry_exposes_only_a_private_existing_authorization_lookup(self):
        registry = json.loads((ART / "registry/contract-registry.json").read_text(encoding="utf-8"))["operation_registry"]
        operation = next(row for row in registry["operations"] if row["operation_id"] == "ak.self.mls.content_recovery.resource.get.v1")
        self.assertEqual(operation["http"], "GET /_arkret/self/mls/content-recoveries/{authorization_event_ref}")
        self.assertNotIn("request_schema_ref", operation)
        self.assertEqual(operation["response_schema_ref"], "schemas/content-encryption.schema.json#/$defs/recovery_preparation")
        self.assertFalse(any("content_recovery.command.prepare" in row["operation_id"] for row in registry["operations"]))
        receipt = json.loads((ART / "schemas/recovery-receipt.schema.json").read_text(encoding="utf-8"))
        self.assertNotIn("content_recovery", receipt["properties"])

    def test_preparation_wire_and_private_inventory_have_frozen_canonical_bytes(self):
        value = self.fixture["recovery_preparation_encoding"]
        pending, prepared = value["pending"], value["prepared"]
        self.assertEqual(jcs(pending).hex(), value["pending_jcs_hex"])
        self.assertEqual(jcs(prepared).hex(), value["prepared_jcs_hex"])
        raw = bytes.fromhex(value["inventory_jcs_hex"])
        self.assertEqual(raw, jcs(value["empty_inventory"]))
        self.assertEqual(prepared["inventory_blob_ref"], "ak:blob:sha256:" + hashlib.sha256(raw).hexdigest())
        self.validate("content-encryption.schema.json#/$defs/recovery_preparation", pending)
        self.validate("content-encryption.schema.json#/$defs/recovery_preparation", prepared)
        verify_preparation_resource(prepared, value["authorization_event_ref"], pending["replacement"], pending["pcr_cut"], pending)

    def test_mixed_roster_orders_recovery_and_retains_original_key_binding(self):
        native = self.fixture["public_recovery_wire"]; key = native["native_output_bindings"]["signature_key_base64url"]
        genesis = {"kind": "genesis", "source": "original genesis"}
        add = {"kind": "add", "covering_commit": {"stream_position": 2}, "consumed_proposal_ordinal": 1}
        recovery = {"kind": "recovery", "covering_commit": {"stream_position": 3}, "producer_signer_fact": {"public_key_base64url": key},
                    "commit_event": {"actor_id": native["native_output_bindings"]["actor_id"], "scope_ref": native["native_scope"],
                                     "payload": {"commit_base64url": b64(bytes.fromhex(native["public_message_hex"])), "recovery_binding": {"replacement": {"actor_id": native["native_output_bindings"]["actor_id"], "signature_key_base64url": key}}}}}
        later = {"kind": "add", "covering_commit": {"stream_position": 4}, "consumed_proposal_ordinal": 0}
        records = ordered_roster([later, genesis, recovery, add]); self.assertEqual(records, [genesis, add, recovery, later])
        add_rows = [{"record_digest": "sha256:" + hashlib.sha256(jcs(x)).hexdigest()} for x in (add, later)]
        recovery_rows = [{"record_digest": "sha256:" + hashlib.sha256(jcs(recovery)).hexdigest(), "public_key_base64url": key}]
        verify_roster_keys(records, add_rows, recovery_rows)
        for rows in ([], [recovery_rows[0], recovery_rows[0]], [{**recovery_rows[0], "public_key_base64url": "A" * 43}]):
            with self.assertRaises(ValueError): verify_roster_keys(records, add_rows, rows)
        with self.assertRaises(ValueError): verify_roster_keys([genesis, recovery, add, later], add_rows, recovery_rows)
        wrong = copy.deepcopy(recovery); wrong["producer_signer_fact"]["public_key_base64url"] = "A" * 43
        wrong["commit_event"]["payload"]["recovery_binding"]["replacement"]["signature_key_base64url"] = "A" * 43
        wrong_row = {"record_digest": "sha256:" + hashlib.sha256(jcs(wrong)).hexdigest(), "public_key_base64url": "A" * 43}
        with self.assertRaises(ValueError): verify_roster_keys([genesis, add, wrong, later], add_rows, [wrong_row])

    def test_real_public_external_commit_path_matches_frozen_native_output(self):
        value = self.fixture["public_recovery_wire"]; wire = bytes.fromhex(value["public_message_hex"])
        self.assertEqual(hashlib.sha256(wire).hexdigest(), value["wire_sha256"])
        self.assertEqual(recovery_path_leaf(wire), value["expected_path_leaf"])
        for key, expected in value["native_output_bindings"].items():
            self.assertEqual(recovery_path_leaf(wire)[key], expected)
        self.assertEqual(value["expected_path_leaf"]["actor_id"]["kind"], "account")
        for bad in (wire[:-1], wire + b"\x00", b"\x00\x01\x00\x02" + wire[4:]):
            with self.assertRaises(ValueError): recovery_path_leaf(bad)

    def test_dynamic_recovery_state_does_not_modify_presigned_identity_receipt(self):
        schema = json.loads((ART / "schemas/recovery-receipt.schema.json").read_text(encoding="utf-8"))
        self.assertNotIn("content_recovery", schema["properties"])
        request = copy.deepcopy(self.fixture["hpke_grant"]["grant"])
        request.pop("entries"); request.pop("recipient_key_event_ref")
        self.validate("content-encryption.schema.json#/$defs/history_request", request)

    def test_roster_longest_prefix_paging_includes_self_projection_and_final_manifest(self):
        records = [{"kind": "add", "ordinal": i, "original_evidence": "a" * 250000} for i in range(15)]
        def wrap(selected, index, count):
            peer = {"manifest": {"page_count": count, "signature": "A" * 86}, "page_index": index, "records": selected}
            own = {"roster": peer, "signing_keys_and_provenance_budget": "b" * 100000}
            return peer, own
        pages = roster_pages(records, wrap)
        self.assertEqual([len(peer["records"]) for peer, _ in pages], [7, 7, 1])
        self.assertEqual([peer["manifest"]["page_count"] for peer, _ in pages], [3, 3, 3])
        self.assertEqual([row for peer, _ in pages for row in peer["records"]], records)
        for peer, own in pages: self.assertLessEqual(max(len(jcs(peer)), len(jcs(own))), 2 * 1024 * 1024)
        with self.assertRaises(ValueError): roster_pages([{"original_evidence": "a" * (2 * 1024 * 1024)}], wrap)

    def test_pending_checkpoint_forbids_partial_cleanup_claim(self):
        inventory = self._inventory()
        value = {"state": "pending", "pcr_cut": inventory["pcr_cut"], "coverage_head_digest": "sha256:" + "1" * 64,
                 "restored_event_count": "0", "cleanup_completed": False, "replacement": inventory["replacement"],
                 "inventory_blob_ref": "ak:blob:sha256:" + "2" * 64}
        self.validate("content-encryption.schema.json#/$defs/history_recovery", value)
        value["cleanup_blob_ref"] = "ak:blob:sha256:" + "3" * 64
        self.invalid("content-encryption.schema.json#/$defs/history_recovery", value)
        value.pop("cleanup_blob_ref"); value["cleanup_completed"] = True
        self.invalid("content-encryption.schema.json#/$defs/history_recovery", value)

    def test_frozen_recovery_checkpoint_ready_requires_both_private_cleanup_proofs(self):
        value = copy.deepcopy(self.fixture["recovery_checkpoint"])
        self.validate("content-encryption.schema.json#/$defs/history_recovery", value)
        for field in ("cleanup_inventory_digest", "cleanup_blob_ref", "inventory_blob_ref"):
            changed = copy.deepcopy(value); changed.pop(field)
            self.invalid("content-encryption.schema.json#/$defs/history_recovery", changed)

    def test_original_recovery_source_signature_cannot_be_rebound_or_replaced_by_manifest(self):
        native = self.fixture["public_recovery_wire"]; actor = native["native_output_bindings"]["actor_id"]
        ref = self.fixture["kat"]["root_context"]["group_state_ref"]
        replacement = {"actor_id": actor, "signature_key_base64url": native["native_output_bindings"]["signature_key_base64url"],
                       "authorization_event_ref": ref, "endpoint": {"kind": "device", "device_id": "ak:device:019a0000-0000-7000-8000-000000000002"}}
        binding = {"replacement": replacement, "base_group_state_ref": ref, "expected_epoch": native["expected_path_leaf"]["epoch"], "authorization_event_ref": ref, "inventory_digest": "sha256:" + "1" * 64}
        event = {"event_id": ref, "actor_id": actor, "scope_ref": native["native_scope"], "payload": {"recovery_binding": binding, "base_group_state_ref": ref, "previous_epoch": binding["expected_epoch"]}}
        auth = copy.deepcopy(self.fixture["hpke_grant"]["grant"]["history_cut"]); auth["event_id"] = ref
        fact = {"event_id": ref, "actor": actor, "device_id": replacement["endpoint"]["device_id"], "verification_method": "did:web:agent.example#runtime", "key": {"public_key_base64url": replacement["signature_key_base64url"], "authorization_ref": auth, "revision": {"commit_id": auth["commit_id"], "stream_position": auth["stream_position"]}, "governance_generation": "0"}, "accepted_at": "2026-11-08T00:01:00.000Z"}
        digest = "sha256:" + hashlib.sha256(jcs(fact)).hexdigest()
        source = {"event_ref": ref, "replacement": replacement, "effective_scope": native["native_scope"], "base_group_state_ref": ref,
                  "previous_epoch": binding["expected_epoch"], "inventory_digest": binding["inventory_digest"], "verification_method": fact["verification_method"],
                  "attested_at": "2026-11-08T00:00:00.000Z", "expires_at": "2026-11-08T00:04:00.000Z"}
        signer = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
        method = "did:web:recovery-station.example#origin-key"
        source["signature"] = {"kid": method, "signature_algorithm": "Ed25519", "signature": b64(signer.sign(b"ak.mls.recovery_source.v1\n" + jcs(source)))}
        self.validate("content-encryption.schema.json#/$defs/recovery_source_attestation", source)
        key = {"station_id": actor["account_id"]["station_id"], "verification_method": method, "public_key_base64url": b64(signer.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))}
        record = {"commit_event": event, "covering_commit": {"producer_signer_fact_digest": digest, "committed_at": "2026-11-08T00:01:00.000Z"}, "producer_signer_fact": fact, "recovery_source": {"attestation": source}}
        verify_recovery_source(record, key)
        human = copy.deepcopy(record)
        auth = copy.deepcopy(self.fixture["hpke_grant"]["grant"]["history_cut"]); auth["event_id"] = ref
        human["producer_signer_fact"] = {"event_id": ref, "actor": actor, "device_id": replacement["endpoint"]["device_id"], "verification_method": fact["verification_method"], "key": {"public_key_base64url": replacement["signature_key_base64url"], "authorization_ref": auth, "revision": {"commit_id": auth["commit_id"], "stream_position": auth["stream_position"]}, "governance_generation": "0"}, "accepted_at": fact["accepted_at"]}
        self.validate("authority-commit-operations.schema.json#/$defs/account_device_historical_signer_fact", human["producer_signer_fact"])
        human["covering_commit"]["producer_signer_fact_digest"] = "sha256:" + hashlib.sha256(jcs(human["producer_signer_fact"])).hexdigest()
        verify_recovery_source(human, key)
        # Source crypto binds the actual Human producer, independently of the
        # resource Actor. This minimal transcript does not prove native control
        # delegation or admit a new Event into an Agent PCR.
        controlled = copy.deepcopy(human)
        controlled["commit_event"]["actor_id"] = {"kind": "account", "account_id": {
            **actor["account_id"], "principal_id": "ak:did_core:web:controlled-agent.example"}}
        controlled["commit_event"]["executed_by"] = actor
        verify_recovery_source(controlled, key)
        changed_controller = copy.deepcopy(controlled)
        changed_controller["commit_event"]["executed_by"] = controlled["commit_event"]["actor_id"]
        with self.assertRaises(ValueError):
            verify_recovery_source(changed_controller, key)
        agent = copy.deepcopy(record)
        agent_actor = copy.deepcopy(actor); agent_actor["account_id"]["principal_id"] = "ak:did_core:web:agent.example"
        agent["commit_event"]["actor_id"] = agent_actor
        agent_endpoint = {"kind": "agent_runtime", "verification_method": fact["verification_method"]}
        for target in (agent["commit_event"]["payload"]["recovery_binding"]["replacement"], agent["recovery_source"]["attestation"]["replacement"]):
            target["actor_id"] = agent_actor; target["endpoint"] = agent_endpoint
        agent["producer_signer_fact"] = {"kind": "agent_runtime", "event_ref": ref, "actor_id": agent_actor, "verification_method": fact["verification_method"], "public_key_base64url": replacement["signature_key_base64url"], "authorization_event_ref": ref, "accepted_at": fact["accepted_at"]}
        self.validate("authority-commit-operations.schema.json#/$defs/agent_runtime_historical_signer_fact", agent["producer_signer_fact"])
        agent["covering_commit"]["producer_signer_fact_digest"] = "sha256:" + hashlib.sha256(jcs(agent["producer_signer_fact"])).hexdigest()
        attestation = agent["recovery_source"]["attestation"]; attestation["signature"]["signature"] = b64(signer.sign(b"ak.mls.recovery_source.v1\n" + jcs({k: v for k, v in attestation.items() if k != "signature"})))
        verify_recovery_source(agent, key)
        changed_agent = copy.deepcopy(agent)
        for target in (changed_agent["commit_event"]["payload"]["recovery_binding"]["replacement"], changed_agent["recovery_source"]["attestation"]["replacement"]): target["endpoint"] = replacement["endpoint"]
        attestation = changed_agent["recovery_source"]["attestation"]; attestation["signature"]["signature"] = b64(signer.sign(b"ak.mls.recovery_source.v1\n" + jcs({k: v for k, v in attestation.items() if k != "signature"})))
        with self.assertRaises(ValueError): verify_recovery_source(changed_agent, key)
        human["producer_signer_fact"]["device_id"] = "ak:device:019a0000-0000-7000-8000-000000000099"
        human["covering_commit"]["producer_signer_fact_digest"] = "sha256:" + hashlib.sha256(jcs(human["producer_signer_fact"])).hexdigest()
        with self.assertRaises(ValueError): verify_recovery_source(human, key)
        changed = copy.deepcopy(record); changed["commit_event"]["payload"]["base_group_state_ref"] = self.fixture["hpke_grant"]["grant"]["recipient_key_event_ref"]
        with self.assertRaises(ValueError): verify_recovery_source(changed, key)
        changed = copy.deepcopy(record); changed["producer_signer_fact"]["key"]["public_key_base64url"] = "A" * 43
        with self.assertRaises(ValueError): verify_recovery_source(changed, key)
        changed["covering_commit"]["producer_signer_fact_digest"] = "sha256:" + hashlib.sha256(jcs(changed["producer_signer_fact"])).hexdigest()
        with self.assertRaises(ValueError): verify_recovery_source(changed, key)
        changed_key = copy.deepcopy(key); changed_key["station_id"] = "ak:did_core:web:other.example"
        with self.assertRaises(ValueError): verify_recovery_source(record, changed_key)
        changed = copy.deepcopy(record); changed["recovery_source"]["attestation"]["signature"]["signature"] = "A" * 86
        with self.assertRaises(InvalidSignature): verify_recovery_source(changed, key)
        changed = copy.deepcopy(record); changed["covering_commit"]["committed_at"] = source["expires_at"]
        with self.assertRaises(ValueError): verify_recovery_source(changed, key)
        changed = copy.deepcopy(record); changed["commit_event"]["payload"]["recovery_binding"]["authorization_event_ref"] = "ak:event:" + "B" * 44
        with self.assertRaises(ValueError): verify_recovery_source(changed, key)


class ScopeRetirementContractTest(unittest.TestCase):
    """Crypto and explicit native-model assumptions, without production claims."""

    setUpClass = classmethod(ContentHistoryContractTest.setUpClass.__func__)
    validate = ContentHistoryContractTest.validate
    invalid = ContentHistoryContractTest.invalid

    def setUp(self):
        self.kat = copy.deepcopy(self.fixture['scope_retirement'])
        self.inventory = self.kat['inventory']
        self.entry = self.inventory['entries'][0]
        self.authorization = self.kat['authorization']
        self.reader = self.kat['reader_authority']
        self.historical = self.kat['historical_completion_basis']
        self.route = self.kat['current_delivery']

    def verify(self, result=None, historical=None, authorization=None):
        from tools.recovery_scope_cleanup import verify_retirement
        return verify_retirement(result or self.kat['results']['removed'], authorization or self.authorization,
                                 self.inventory, self.entry, historical or self.historical)

    def consume(self, scenario=None, reader=None, route=None, now=None, response=None):
        from tools.recovery_scope_cleanup import verify_self_retirement
        scenario = scenario or self.kat
        return verify_self_retirement(response or scenario['self_deliveries']['removed'], scenario['authorization'],
            self.inventory, self.entry, reader or self.reader, self.historical,
            route or scenario['current_delivery'], now or ('2026-11-09T00:06:02.000Z' if scenario is self.kat['handoff'] else '2026-11-09T00:00:03.000Z'))

    def test_retired_branches_are_signed_closed_and_do_not_deliver_roots(self):
        from tools.recovery_scope_cleanup import qualify_source, signing_bytes
        qualify_source(self.authorization, self.inventory, self.entry, self.reader, self.route, '2026-11-09T00:00:03.000Z')
        self.validate('content-encryption.schema.json#/$defs/recovery_scope_cleanup_authorization', self.authorization)
        self.assertEqual(signing_bytes(self.authorization, source=True).hex(), self.kat['authorization_signing_hex'])
        for state, cleanup in self.kat['results'].items():
            self.validate('content-encryption.schema.json#/$defs/scope_cleanup', cleanup)
            self.validate('content-encryption.schema.json#/$defs/recovery_scope_cleanup_response_body', self.kat['deliveries'][state])
            self.validate('content-encryption.schema.json#/$defs/recovery_scope_cleanup_self_response_body', self.kat['self_deliveries'][state])
            self.verify(cleanup)
            self.assertEqual(signing_bytes(cleanup['retirement_proof']).hex(), self.kat[state + '_signing_hex'])
            for field, value in [('root_refs', ['sha256:' + '0' * 64]), ('backup_refs', ['unrelated']),
                                  ('winning_commit', self.inventory['pcr_cut'])]:
                self.invalid('content-encryption.schema.json#/$defs/scope_cleanup', {**cleanup, field: value})

    def test_retirement_requires_native_absence_and_no_inflight_admission(self):
        for field, value in [('old_endpoint_count', 1), ('pending_admission_count', 1),
                             ('episode_fenced', False), ('native_source_complete', False), ('eligible_at_completion', True)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.verify(historical={**self.historical, field: value})

    def test_old_index_empty_does_not_prove_current_absence(self):
        self.assertEqual(self.entry['old_leaves'], [])
        with self.assertRaises(ValueError):
            self.verify(historical={**self.historical, 'old_endpoint_count': 2})

    def test_retirement_rejects_wrong_governance_cut_and_handoff_generation(self):
        for field, value in [('governance_station_id', 'ak:did_core:web:wrong.example'), ('governance_generation', 1),
                             ('epoch', '13'), ('group_state_ref', self.fixture['hpke_grant']['grant']['recipient_key_event_ref']),
                             ('scope_cut', {**self.historical['scope_cut'], 'stream_position': 999})]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.verify(historical={**self.historical, field: value})

    def test_modified_nonce_inventory_scope_or_endpoint_breaks_signature(self):
        for field, value in [('nonce_base64url', b64(bytes([1]) * 32)), ('inventory_digest', 'sha256:' + '0' * 64),
                             ('inventory_entry_digest', 'sha256:' + '1' * 64), ('state', 'terminated'),
                             ('replacement', self.fixture['kat']['content_context']['producer'])]:
            result = copy.deepcopy(self.kat['results']['removed'])
            result['retirement_proof'][field] = value
            with self.subTest(field=field), self.assertRaises((InvalidSignature, ValueError)):
                self.verify(result)

    def test_resigning_cannot_change_native_scope_or_episode(self):
        from tools.recovery_scope_cleanup import sign
        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.kat['governor_signing_seed_hex']))
        for field, value in [('inventory_digest', 'sha256:' + '0' * 64), ('nonce_base64url', b64(bytes([8]) * 32)),
                             ('request_digest', 'sha256:' + '2' * 64),
                             ('genesis_event_ref', self.fixture['hpke_grant']['grant']['recipient_key_event_ref'])]:
            result = copy.deepcopy(self.kat['results']['removed'])
            result['retirement_proof'] = sign({**result['retirement_proof'], field: value}, key)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.verify(result)

    def test_terminated_requires_registered_irreversible_all_writes_gate(self):
        result = self.kat['results']['terminated']
        self.verify(result, {**self.historical, 'old_endpoint_count': 3})
        for field, value in [('terminal_irreversible', False), ('terminal_all_writes_blocked', False),
                             ('terminal_source_digest', 'sha256:' + '0' * 64)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.verify(result, {**self.historical, field: value})
        for state, field, value in [('terminated', 'remaining_old_leaf_count', 0),
                                    ('removed', 'terminal_source_digest', 'sha256:' + '0' * 64)]:
            altered = copy.deepcopy(self.kat['results'][state])
            altered['retirement_proof'][field] = value
            self.invalid('content-encryption.schema.json#/$defs/scope_cleanup', altered)

    def test_current_origin_episode_and_source_ttl_are_not_signature_shortcuts(self):
        from tools.recovery_scope_cleanup import qualify_source
        for field, value in [('origin_service_id', 'ak:did_core:web:other.example'),
                             ('origin_native_qualified', False), ('governance_active', False)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                qualify_source(self.authorization, self.inventory, self.entry, self.reader,
                               {**self.route, field: value}, '2026-11-09T00:00:03.000Z')
        with self.assertRaises(ValueError):
            qualify_source(self.authorization, self.inventory, self.entry, self.reader, self.route, self.authorization['expires_at'])

    def test_fresh_source_renewal_preserves_intent_but_nonce_rebinding_does_not(self):
        from tools.recovery_scope_cleanup import request_digest, digest, qualify_source
        after = self.kat['handoff']
        self.assertEqual(request_digest(after['authorization']), request_digest(self.authorization))
        self.assertNotEqual(digest(after['authorization']), digest(self.authorization))
        qualify_source(after['authorization'], self.inventory, self.entry, self.reader, after['current_delivery'], '2026-11-09T00:06:02.000Z')
        self.assertNotEqual(request_digest({**self.authorization, 'nonce_base64url': b64(bytes([6]) * 32)}), request_digest(self.authorization))

    def test_pending_is_closed_and_has_no_key_or_partial_proof(self):
        schema = 'content-encryption.schema.json#/$defs/recovery_scope_cleanup_response_body'
        self.validate(schema, {'state': 'pending'})
        self.invalid(schema, {'state': 'pending', 'remaining_old_leaf_count': 0})
        self.invalid(schema, self.kat['results']['removed'])
        schema = 'content-encryption.schema.json#/$defs/recovery_scope_cleanup_self_response_body'
        self.validate(schema, {'delivery': {'state': 'pending'}})
        self.invalid(schema, {'delivery': {'state': 'pending'}, 'attestor_signing_key': self.kat['self_deliveries']['removed']['attestor_signing_key']})
        self.invalid(schema, {'delivery': self.kat['deliveries']['removed']})

    def test_retired_entries_remain_in_cleanup_without_fake_roots(self):
        result = self.kat['results']['removed']
        self.validate('content-encryption.schema.json#/$defs/cleanup_inventory', {
            'inventory_digest': inventory_digest(self.inventory), 'scope_cleanups': [result]})
        self.assertTrue(cleanup_digest(self.inventory, [result]).startswith('sha256:'))
        for results in [[], [{**result, 'state': 'rekeyed'}]]:
            with self.assertRaises(ValueError):
                cleanup_digest(self.inventory, results)
        self.assertNotIn('delivery_attestation', jcs(result).decode())

    def test_registered_commands_are_private_and_do_not_expand_chat_archive_guarantee(self):
        catalog = json.loads((ART / 'registry/contract-registry.json').read_text(encoding='utf-8'))
        ops = {op['operation_id']: op for op in catalog['operation_registry']['operations']}
        for prefix in ['self', 'peer']:
            op = ops[f'ak.{prefix}.mls.command.reconcile_recovery_scope.v1']
            self.assertEqual(op['canonical_hash_input'], 'full_body')
            self.assertEqual(op['idempotency_mechanism'], 'canonical_hash')
            self.assertTrue(op['retry_safe'])
        self.assertFalse(catalog['content_encryption_contract']['group_chat_full_archive_guarantee'])
        identity = catalog['content_encryption_contract']['retirement_idempotency']
        self.assertEqual(identity['intent_fields'], ['replacement', 'inventory_digest', 'inventory_entry', 'nonce_base64url'])
        self.assertFalse(identity['route_is_intent'])
        self.assertFalse(identity['delivery_challenge_is_intent'])
        self.assertTrue(identity['observation_binds_authorization_digest'])
        self.assertTrue(identity['derived_peer_request_durable_before_send'])
        barrier = catalog['content_encryption_contract']['recovery_send_barrier']
        self.assertEqual(barrier['pending'], 'block_all_business_senders')
        self.assertEqual(barrier['removed'], 'release_only_completed_episode_blocker')
        self.assertEqual(barrier['terminated'], 'permanent_lifecycle_gate')
        self.assertFalse(barrier['advance_key_access_revision'])

    def test_service_method_and_first_finalization_window_are_bound(self):
        from tools.recovery_scope_cleanup import sign
        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.kat['governor_signing_seed_hex']))
        for field, value in [('verification_method', 'did:web:governor.example#wrong'),
                             ('attested_at', self.authorization['expires_at']), ('attested_at', '2026-11-08T00:00:00.000Z')]:
            result = copy.deepcopy(self.kat['results']['removed'])
            result['retirement_proof'] = sign({**result['retirement_proof'], field: value}, key)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.verify(result)

    def test_cleanup_bindings_keep_authenticated_origin_and_current_holder_roles(self):
        import yaml
        api = yaml.safe_load((ART / 'openapi/arkret-service-api.openapi.yaml').read_text(encoding='utf-8'))
        for prefix, schemes in [('peer', {'httpMessageSignature', 'sourceServiceId', 'destinationServiceId',
                                          'sourceTrustDomain', 'destinationTrustDomain', 'contentDigest'}),
                                ('self', {'sessionGrantAuth', 'dpopProof'})]:
            operation = api['paths'][f'/_arkret/{prefix}/mls/recovery-scope-cleanup']['post']
            self.assertEqual(len(operation['security']), 1)
            self.assertEqual(set(operation['security'][0]), schemes)
            self.assertIn('fresh', operation['description'])
            self.assertIn('intent', operation['description'])

    def test_self_key_projection_cannot_be_swapped_or_rebound(self):
        self.consume()
        for projection, field, value in [
            ('attestor_signing_key', 'proof_digest', 'sha256:' + '0' * 64),
            ('attestor_signing_key', 'public_key_base64url', b64(bytes([8]) * 32)),
            ('delivery_signing_key', 'delivery_digest', 'sha256:' + '1' * 64),
            ('delivery_signing_key', 'verification_method', 'did:web:wrong.example#key')]:
            response = copy.deepcopy(self.kat['self_deliveries']['removed'])
            response[projection][field] = value
            with self.subTest(projection=projection, field=field), self.assertRaises(ValueError):
                self.consume(response=response)

    def test_terminal_source_commitment_hides_upstream_coordinates_and_binds_nonce(self):
        from tools.recovery_scope_cleanup import terminal_source_digest, sign
        source = {**self.inventory['pcr_cut'], 'event_id': 'ak:event:' + b64(b'\x01' + bytes([17]) * 32), 'stream_position': 991}
        nonce = self.authorization['nonce_base64url']
        committed = terminal_source_digest(self.entry, source, nonce)
        self.assertNotEqual(committed, terminal_source_digest(self.entry, source, b64(bytes([18]) * 32)))
        result = copy.deepcopy(self.kat['results']['terminated'])
        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.kat['governor_signing_seed_hex']))
        result['retirement_proof'] = sign({**result['retirement_proof'], 'terminal_source_digest': committed}, key)
        self.verify(result, {**self.historical, 'terminal_source_digest': committed})
        self.assertNotIn(source['event_id'], jcs(result).decode())

    def test_completed_rejoin_uses_terminal_before_first_eligibility_gate(self):
        from tools.recovery_scope_cleanup import settle_intent
        ledger = {}
        expected = self.kat['results']['removed']
        self.assertEqual(settle_intent(ledger, self.authorization, False, expected), expected)
        self.assertEqual(settle_intent(ledger, self.authorization, True, None), expected)
        with self.assertRaisesRegex(ValueError, 'failed_precondition'):
            settle_intent({}, self.authorization, True, expected)
        self.consume()

    def test_rejoin_then_handoff_preserves_original_proof_and_uses_current_delivery(self):
        from tools.recovery_scope_cleanup import signing_bytes, settle_intent
        after = self.kat['handoff']
        self.validate('content-encryption.schema.json#/$defs/recovery_scope_cleanup_authorization', after['authorization'])
        self.validate('content-encryption.schema.json#/$defs/recovery_scope_cleanup_response_body', after['deliveries']['removed'])
        self.validate('content-encryption.schema.json#/$defs/recovery_scope_cleanup_self_response_body', after['self_deliveries']['removed'])
        original = jcs(self.kat['results']['removed']['retirement_proof'])
        ledger = {}
        settle_intent(ledger, self.authorization, False, self.kat['results']['removed'])
        imported = copy.deepcopy(ledger)
        current = settle_intent(imported, after['authorization'], True, None)
        self.assertEqual(jcs(current['retirement_proof']), original)
        self.assertEqual(self.consume(after), current['retirement_proof'])
        self.assertEqual(signing_bytes(after['deliveries']['removed']['delivery_attestation'], delivery=True).hex(), self.kat['handoff_delivery_signing_hex'])
        self.assertEqual(after['deliveries']['removed']['cleanup']['retirement_proof']['governance_generation'], 0)
        self.assertEqual(after['deliveries']['removed']['delivery_attestation']['governance_generation'], 1)

    def test_missing_import_or_fence_never_authorizes_delivery(self):
        after = self.kat['handoff']
        for field, value in [('proof_and_fence_retained', False), ('retained_proof_digests', []), ('governance_active', False)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.consume(after, route={**after['current_delivery'], field: value})

    def test_current_reader_revocation_episode_and_custody_are_independent(self):
        for field, value in [('current_authorized', False), ('episode_current', False), ('inventory_prepared', False),
                             ('authorization_event_ref', self.fixture['kat']['root_context']['genesis_event_ref'])]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.consume(reader={**self.reader, field: value})
        self.consume(reader={**self.reader, 'role': 'agent_custodian', 'custody_current': True})
        with self.assertRaises(ValueError):
            self.consume(reader={**self.reader, 'role': 'agent_custodian', 'custody_current': False})

    def test_full_body_outer_retry_and_inner_intent_settle_once_across_refresh(self):
        from tools.recovery_scope_cleanup import transport_replay, settle_intent
        outer, inner, calls = {}, {}, []
        def first():
            calls.append('first')
            return settle_intent(inner, self.authorization, False, self.kat['results']['removed'])
        a = transport_replay(outer, 'origin', 'peer', self.authorization, True, first)
        b = transport_replay(outer, 'origin', 'peer', self.authorization, True, lambda: self.fail('outer retry reexecuted'))
        refreshed = self.kat['handoff']['authorization']
        c = transport_replay(outer, 'origin', 'peer', refreshed, True,
            lambda: settle_intent(inner, refreshed, True, None))
        self.assertEqual(a, b)
        self.assertEqual(a, c)
        self.assertEqual(calls, ['first'])
        self.assertEqual(len(outer), 2)
        self.assertEqual(len(inner), 1)
        with self.assertRaisesRegex(ValueError, 'not_found'):
            transport_replay(outer, 'origin', 'peer', self.authorization, False, first)

    def test_inner_nonce_rebinding_conflicts_even_with_another_outer_body(self):
        from tools.recovery_scope_cleanup import settle_intent, request_digest
        from unittest.mock import patch
        ledger = {}
        settle_intent(ledger, self.authorization, False, self.kat['results']['removed'])
        for field, value in [('inventory_digest', 'sha256:' + '0' * 64),
                             ('inventory_entry', {**self.entry, 'epoch': '99'}),
                             ('replacement', {**self.authorization['replacement'],
                                              'signature_key_base64url': b64(bytes([10]) * 32)})]:
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'duplicate_conflict'):
                settle_intent(ledger, {**self.authorization, field: value}, False, None)
        with patch('tools.recovery_scope_cleanup.request_digest', return_value=request_digest(self.authorization)):
            with self.assertRaisesRegex(ValueError, 'duplicate_conflict'):
                settle_intent(ledger, {**self.authorization, 'inventory_digest': 'sha256:' + '0' * 64}, False, None)

    def test_pending_outer_observation_is_not_rewritten_when_inner_finishes(self):
        from tools.recovery_scope_cleanup import transport_replay, settle_intent, observe_delivery
        outer, inner, observations = {}, {}, {}
        pending = transport_replay(outer, 'origin', 'peer', self.authorization, True,
            lambda: observe_delivery(observations, self.authorization,
                lambda: settle_intent(inner, self.authorization, False, None)))
        self.assertEqual(pending, {'state': 'pending'})
        # Native completion occurs within the original live source window.
        settle_intent(inner, self.authorization, False, self.kat['results']['removed'])
        self.assertEqual(observe_delivery(observations, self.authorization,
            lambda: self.fail('old observation executed native settlement')), pending)
        later = self.kat['handoff']['authorization']
        complete = transport_replay(outer, 'origin', 'peer', later, True,
            lambda: observe_delivery(observations, later, lambda: settle_intent(inner, later, True, None)))
        replayed = transport_replay(outer, 'origin', 'peer', self.authorization, True, lambda: self.fail('old body changed'))
        self.assertEqual(replayed, pending)
        self.assertEqual(complete, self.kat['results']['removed'])

    def test_observation_challenge_cannot_rebind_source_even_with_same_intent(self):
        from tools.recovery_scope_cleanup import observe_delivery, request_digest, sign
        ledger = {}
        observe_delivery(ledger, self.authorization, lambda: {'state': 'pending'})
        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.kat['origin_signing_seed_hex']))
        changed = sign({**self.authorization, 'expires_at': '2026-11-09T00:04:00.000Z'}, key, source=True)
        self.assertEqual(request_digest(changed), request_digest(self.authorization))
        with self.assertRaisesRegex(ValueError, 'duplicate_conflict'):
            observe_delivery(ledger, changed, lambda: self.fail('challenge conflict executed native effects'))

    def test_current_governor_key_rotation_preserves_original_proof_key(self):
        from tools.recovery_scope_cleanup import sign, digest
        key = Ed25519PrivateKey.from_private_bytes(bytes([237]) * 32)
        public = b64(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
        method = self.route['governor_verification_method'] + '-rotated'
        route = {**self.route, 'governor_public_key': public, 'governor_verification_method': method}
        response = copy.deepcopy(self.kat['self_deliveries']['removed'])
        source = {**self.authorization, 'delivery_challenge_base64url': b64(bytes([96]) * 32)}
        origin = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.kat['origin_signing_seed_hex']))
        source = sign(source, origin, source=True)
        delivery = sign({**response['delivery']['delivery_attestation'], 'verification_method': method,
                         'delivery_challenge_base64url': source['delivery_challenge_base64url'],
                         'authorization_digest': digest(source)}, key, delivery=True)
        response['delivery']['delivery_attestation'] = delivery
        response['delivery_signing_key'] = {'delivery_digest': digest(delivery), 'verification_method': method,
                                            'public_key_base64url': public}
        from tools.recovery_scope_cleanup import verify_self_retirement
        verified = verify_self_retirement(response, source, self.inventory, self.entry, self.reader,
                                          self.historical, route, '2026-11-09T00:00:03.000Z')
        self.assertEqual(verified, self.kat['results']['removed']['retirement_proof'])
        self.assertNotEqual(response['attestor_signing_key']['public_key_base64url'], public)

    def test_current_origin_key_rotation_does_not_rewrite_original_source(self):
        from tools.recovery_scope_cleanup import sign, digest, verify_self_retirement
        key = Ed25519PrivateKey.from_private_bytes(bytes([238]) * 32)
        public = b64(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
        method = self.route['origin_verification_method'] + '-rotated'
        route = {**self.route, 'origin_public_key': public, 'origin_verification_method': method}
        source = sign({**self.authorization, 'verification_method': method,
                       'delivery_challenge_base64url': b64(bytes([97]) * 32)}, key, source=True)
        response = copy.deepcopy(self.kat['self_deliveries']['removed'])
        governor = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.kat['governor_signing_seed_hex']))
        delivery = sign({**response['delivery']['delivery_attestation'], 'authorization_digest': digest(source),
                         'delivery_challenge_base64url': source['delivery_challenge_base64url']}, governor, delivery=True)
        response['delivery']['delivery_attestation'] = delivery
        response['delivery_signing_key']['delivery_digest'] = digest(delivery)
        self.assertEqual(verify_self_retirement(response, source, self.inventory, self.entry, self.reader,
            self.historical, route, '2026-11-09T00:00:03.000Z'), self.kat['results']['removed']['retirement_proof'])
        self.assertNotEqual(self.historical['authorization']['verification_method'], method)

    def test_nonce_and_challenge_require_canonical_32_byte_encoding(self):
        from tools.recovery_scope_cleanup import canonical_nonce
        for field in ('nonce_base64url', 'delivery_challenge_base64url'):
            value = self.authorization[field]
            for wrong in (value + '=', value[:-1], value[:-1] + 'B'):
                with self.subTest(field=field, wrong=wrong), self.assertRaises(ValueError):
                    canonical_nonce(wrong)
                self.invalid('content-encryption.schema.json#/$defs/recovery_scope_cleanup_authorization',
                             {**self.authorization, field: wrong})

    def test_delivery_time_bounds_do_not_extend_current_source_window(self):
        from tools.recovery_scope_cleanup import sign, digest
        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.kat['governor_signing_seed_hex']))
        for field, value in [('expires_at', '2026-11-09T00:05:01.000Z'),
                             ('attested_at', '2026-11-08T23:59:59.000Z'),
                             ('attested_at', '2026-11-09T00:00:04.000Z')]:
            response = copy.deepcopy(self.kat['self_deliveries']['removed'])
            delivery = sign({**response['delivery']['delivery_attestation'], field: value}, key, delivery=True)
            response['delivery']['delivery_attestation'] = delivery
            response['delivery_signing_key']['delivery_digest'] = digest(delivery)
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.consume(response=response)

    def test_delivery_binds_fresh_challenge_audience_authorization_and_original_proof(self):
        from tools.recovery_scope_cleanup import sign, digest
        for field, value in [('delivery_challenge_base64url', b64(bytes([1]) * 32)),
                             ('recipient_service_id', 'ak:did_core:web:wrong.example'),
                             ('authorization_digest', 'sha256:' + '0' * 64), ('proof_digest', 'sha256:' + '1' * 64),
                             ('request_digest', 'sha256:' + '2' * 64), ('governance_generation', 99)]:
            response = copy.deepcopy(self.kat['self_deliveries']['removed'])
            attestation = response['delivery']['delivery_attestation']
            key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.kat['governor_signing_seed_hex']))
            attestation = sign({**attestation, field: value}, key, delivery=True)
            response['delivery']['delivery_attestation'] = attestation
            response['delivery_signing_key']['delivery_digest'] = digest(attestation)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.consume(response=response)

    def test_expired_delivery_rejected_but_historical_proof_has_no_completion_lease(self):
        with self.assertRaises(ValueError):
            self.consume(now='2026-11-09T00:05:00.000Z')
        self.verify(authorization=self.kat['handoff']['authorization'])
        self.consume(self.kat['handoff'])

    def test_wrong_current_governor_cannot_reuse_valid_old_delivery(self):
        after = self.kat['handoff']
        with self.assertRaises((ValueError, InvalidSignature)):
            self.consume(after, response=self.kat['self_deliveries']['removed'])
        from tools.recovery_scope_cleanup import qualify_source
        with self.assertRaises(ValueError):
            qualify_source(self.authorization, self.inventory, self.entry, self.reader,
                           after['current_delivery'], '2026-11-09T00:00:03.000Z')

    def test_parallel_episode_blockers_release_independently_and_terminal_never_reopens(self):
        from tools.recovery_scope_cleanup import business_send_allowed
        blockers = {'episode-A', 'episode-B'}
        self.assertFalse(business_send_allowed(blockers, True))
        blockers.remove('episode-A')
        self.assertFalse(business_send_allowed(blockers, True))
        blockers.remove('episode-B')
        self.assertTrue(business_send_allowed(blockers, True))
        self.assertFalse(business_send_allowed(blockers, False))
        self.assertFalse(business_send_allowed(blockers, True, terminal=True))

    def test_delivery_signatures_have_separate_domains_and_cannot_replace_original(self):
        from tools.recovery_scope_cleanup import verify_signature, signing_bytes
        attestation = self.kat['deliveries']['removed']['delivery_attestation']
        self.assertEqual(signing_bytes(attestation, delivery=True).hex(), self.kat['delivery_signing_hex'])
        with self.assertRaises(InvalidSignature):
            verify_signature(attestation, self.route['governor_public_key'])
        with self.assertRaises(ValueError):
            signing_bytes(attestation, source=True, delivery=True)



if __name__ == "__main__":
    unittest.main()
