"""Positive/negative crypto, closed-schema and canonical source mutation tests."""
import copy
import json
import unittest
from pathlib import Path

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tools.content_history import SCHEME, STRATEGY, aad, content_key, content_root, jcs, key_commitment, unb64
from tools.generate_content_history_fixture import build

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
                 "restored_event_count": "12", "cleanup_inventory_digest": "sha256:" + "2" * 64, "cleanup_completed": True}
        self.validate("content-encryption.schema.json#/$defs/history_recovery", value)
        value["cleanup_completed"] = False
        self.invalid("content-encryption.schema.json#/$defs/history_recovery", value)

    def test_history_grant_identifies_the_exact_body_or_attachment(self):
        k = self.fixture["kat"]
        source = k["root_context"]["group_state_ref"]
        cut = {"event_id": source, "commit_id": "ak:realm_commit:" + "A" * 44,
               "stream_ref": {"kind": "realm", "realm_id": k["root_context"]["effective_scope"]["realm_id"]}, "stream_position": 0}
        grant = {"recipient": k["content_context"]["producer"], "recipient_hpke_key_base64url": "A" * 43,
                 "history_cut": cut, "authorization_event_ref": source, "expires_at": "2026-11-08T01:00:00.000Z",
                 "entries": [{"selector": {"kind": "content_key", "source_event_ref": source, "content_path": "/payload"}, "sealed_key_base64url": "AQID"}]}
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
        self.assertEqual(recovery["required"], ["kind", "commit_event", "covering_commit", "producer_signer_fact"])
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
        schema = "mls-roster-authority.schema.json#/$defs/roster_agent_signer_fact"
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

    def test_pcr_grants_are_admitted_but_have_no_outward_disclosure(self):
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
        self.assertEqual(rows[0]["exposures"], [])


if __name__ == "__main__":
    unittest.main()
