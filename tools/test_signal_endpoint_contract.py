"""Signal endpoint KDF, AEAD, authority-input and lifecycle regression tests."""

import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jsonschema import ValidationError

from tools.artifact_lint.core import Lint
from tools.artifact_lint.signal_endpoint import check_signal_endpoint_contract, derive, verify_fixture
from tools.content_history import jcs
from tools.generate_signal_endpoint_fixture import build
from tools.signal_endpoint import (FIELDS, MAX_COUNTER, accept_nonce, nonce_scope, reserve_nonce,
                                   resume_nonce, sender_domain, verified_sender_domain)

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "spec/v1/artifacts"


class SignalEndpointContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((ART / "fixtures/arkret-private-kdf-fixture.json").read_text(encoding="utf-8"))
        cls.registry = json.loads((ART / "registry/exporter-label-registry.json").read_text(encoding="utf-8"))
        cls.kat = next(row for row in cls.fixture["cases"] if row["name"] == "signal_exporter_key_sha256_aes128gcm")
        cls.rows = {row["name"]: row for row in cls.fixture["signal_endpoint_contract"]["domains"]}

    def endpoint(self, name="human_phone"):
        return copy.deepcopy(self.rows[name]["verified_endpoint"])

    def test_frozen_kdf_and_aead_recomputed_with_independent_hkdf(self):
        verify_fixture(self.fixture)
        self.assertEqual(build(self.fixture), self.fixture)

    def test_same_actor_devices_keep_credential_identity_but_separate_signal_keys(self):
        phone, laptop = self.endpoint(), self.endpoint("human_laptop")
        self.assertEqual(jcs(phone["actor_id"]), jcs(laptop["actor_id"]))
        self.assertNotEqual(phone["endpoint"], laptop["endpoint"])
        self.assertNotEqual(self.rows["human_phone"]["signal_key_hex"], self.rows["human_laptop"]["signal_key_hex"])

    def test_each_endpoint_field_independently_separates_keys(self):
        cases = [("human_phone", "human_other_actor", "actor_id"),
                 ("human_phone", "human_other_station", "actor_id"),
                 ("human_phone", "human_reauthorized", "authorization_event_ref"),
                 ("human_phone", "human_new_leaf_key", "signature_key_base64url"),
                 ("agent_old", "agent_new_key", "signature_key_base64url"),
                 ("agent_old", "agent_new_method", "endpoint"),
                 ("agent_old", "agent_reauthorized", "authorization_event_ref")]
        for left, right, changed in cases:
            with self.subTest(case=right):
                a, b = self.endpoint(left), self.endpoint(right)
                self.assertEqual({key for key in FIELDS if a[key] != b[key]}, {changed})
                self.assertNotEqual(self.rows[left]["signal_key_hex"], self.rows[right]["signal_key_hex"])
        a, b = self.endpoint(), self.endpoint("human_other_station")
        self.assertEqual(a["actor_id"]["account_id"]["principal_id"], b["actor_id"]["account_id"]["principal_id"])

    def test_agent_endpoint_is_a_real_method_without_device(self):
        agent = self.endpoint("agent_old")
        self.assertEqual(set(agent["endpoint"]), {"kind", "verification_method"})
        self.assertEqual(verified_sender_domain(agent, agent), jcs(agent))
        agent["endpoint"]["device_id"] = self.endpoint()["endpoint"]["device_id"]
        with self.assertRaises(ValidationError):
            sender_domain(agent)

    def test_closed_schema_rejects_missing_extra_null_and_bad_key(self):
        for field in FIELDS:
            for value in ("missing", None):
                domain = self.endpoint()
                if value == "missing":
                    del domain[field]
                else:
                    domain[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    sender_domain(domain)
        for field in ("leaf_index", "payload_sequence", "authority_commit_id", "sender_device_id"):
            domain = self.endpoint()
            domain[field] = 0
            with self.subTest(field=field), self.assertRaises(ValidationError):
                sender_domain(domain)
        domain = self.endpoint()
        domain["signature_key_base64url"] = "A" * 42 + "B"
        with self.assertRaises(ValueError):
            sender_domain(domain)

    def test_legacy_actor_only_bare_device_and_wrapped_contexts_rejected(self):
        endpoint = self.endpoint()
        for candidate in (endpoint["actor_id"], endpoint["endpoint"]["device_id"],
                          jcs(endpoint).decode(), hashlib.sha256(jcs(endpoint)).hexdigest()):
            with self.subTest(candidate=candidate), self.assertRaises(ValidationError):
                sender_domain(candidate)

    def test_authority_mismatch_is_rejected_before_state_changes(self):
        for name in self.rows:
            if name == "human_phone":
                continue
            seen = set()
            with self.subTest(name=name), self.assertRaises(ValueError):
                domain = verified_sender_domain(self.endpoint(name), self.endpoint())
                accept_nonce(seen, ("group", 1, domain), 0)
            self.assertEqual(seen, set())
        for kwargs in ({"active": False}, {"matching_leaves": 0}, {"matching_leaves": 2}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                verified_sender_domain(self.endpoint(), self.endpoint(), **kwargs)

    def test_equal_nonce_devices_decrypt_independently_and_wrong_key_fails(self):
        kat = self.fixture["signal_endpoint_contract"]["same_actor_equal_nonce_aead"]
        first_key = bytes.fromhex(self.rows["human_phone"]["signal_key_hex"])
        second_key = bytes.fromhex(self.rows["human_laptop"]["signal_key_hex"])
        nonce = bytes.fromhex(kat["nonce_hex"])
        for prefix, key, wrong_key in (("first", first_key, second_key), ("second", second_key, first_key)):
            ciphertext, aad = bytes.fromhex(kat[prefix + "_ciphertext_hex"]), bytes.fromhex(kat[prefix + "_aad_hex"])
            self.assertEqual(AESGCM(key).decrypt(nonce, ciphertext, aad).hex(), kat[prefix + "_plaintext_hex"])
            with self.assertRaises(InvalidTag):
                AESGCM(wrong_key).decrypt(nonce, ciphertext, aad)

    def test_cross_device_counters_do_not_collide_in_replay_domain(self):
        seen = set()
        for name in ("human_phone", "human_laptop", "human_other_station", "agent_old", "agent_new_key"):
            accept_nonce(seen, nonce_scope("same-group", 7, self.endpoint(name)), 0)
        self.assertEqual(len(seen), 5)
        original = seen.copy()
        with self.assertRaises(ValueError):
            accept_nonce(seen, nonce_scope("same-group", 7, self.endpoint()), 0)
        self.assertEqual(seen, original)

    def test_leaf_index_is_not_an_identity_or_replay_namespace(self):
        endpoint = self.endpoint()
        first = {"leaf_index": 0, "endpoint": endpoint}
        moved = {"leaf_index": 99, "endpoint": endpoint}
        reused = {"leaf_index": 0, "endpoint": self.endpoint("human_laptop")}
        self.assertEqual(nonce_scope("g", 1, first["endpoint"]), nonce_scope("g", 1, moved["endpoint"]))
        self.assertNotEqual(nonce_scope("g", 1, first["endpoint"]), nonce_scope("g", 1, reused["endpoint"]))
        seen = set()
        accept_nonce(seen, nonce_scope("g", 1, first["endpoint"]), 0)
        with self.assertRaises(ValueError):
            accept_nonce(seen, nonce_scope("g", 1, moved["endpoint"]), 0)
        accept_nonce(seen, nonce_scope("g", 1, reused["endpoint"]), 0)

    def test_jcs_reordering_does_not_reset_domain(self):
        endpoint = self.endpoint()
        reordered = dict(reversed(list(endpoint.items())))
        self.assertEqual(sender_domain(endpoint), sender_domain(reordered))

    def test_scope_epoch_label_hashing_and_string_wrapping_separate_keys(self):
        given, expected = self.kat["input"], self.kat["expected"]
        secret, root = bytes.fromhex(given["exporter_secret_hex"]), bytes.fromhex(expected["signal_root_hex"])
        domain = sender_domain(self.endpoint())
        accepted = bytes.fromhex(expected["signal_key_hex"])
        for label, context in (("ak.content-v1", domain), ("ak.signal-v1", b""),
                               ("ak.signal-v1", hashlib.sha256(domain).digest()),
                               ("ak.signal-v1", jcs(domain.decode()))):
            self.assertNotEqual(derive(root, label, context, 16), accepted)
        for epoch_secret, scope in ((bytes([secret[0] ^ 1]) + secret[1:], given["realm_id_utf8"].encode()),
                                    (secret, (given["realm_id_utf8"] + "/different-scope").encode())):
            altered_root = derive(derive(epoch_secret, "ak.signal-root-v1", b"", 32), "exported", hashlib.sha256(scope).digest(), 32)
            self.assertNotEqual(derive(altered_root, "ak.signal-v1", domain, 16), accepted)
        self.assertNotEqual(nonce_scope("g", 1, self.endpoint()), nonce_scope("g", 2, self.endpoint()))

    def test_reservations_burn_gaps_and_restart_uses_durable_highwater(self):
        first, durable_next = reserve_nonce(0, 8)
        self.assertEqual((first, durable_next), (0, 8))
        restored = resume_nonce(1, durable_next)
        second, durable_next = reserve_nonce(restored, 8)
        self.assertEqual((second, durable_next), (8, 16))
        self.assertGreater(second, first + 1)

    def test_missing_rollback_and_overflow_fail_closed(self):
        for snapshot, durable in ((0, None), (8, 7), (-1, 7)):
            with self.subTest(snapshot=snapshot, durable=durable), self.assertRaises(ValueError):
                resume_nonce(snapshot, durable)
        for next_value, count in ((None, 1), (-1, 1), (MAX_COUNTER, 1), (MAX_COUNTER - 1, 2), (0, 0)):
            with self.subTest(next_value=next_value, count=count), self.assertRaises(ValueError):
                reserve_nonce(next_value, count)

    def test_two_writers_reserve_disjoint_blocks_from_the_same_atomic_state(self):
        # Sequential committed transitions model a serializable store/CAS;
        # this is not a test of a production database or multi-process runtime.
        state = 0
        a, state = reserve_nonce(state, 16)
        b, state = reserve_nonce(state, 16)
        self.assertTrue(set(range(a, a + 16)).isdisjoint(range(b, b + 16)))
        self.assertEqual(resume_nonce(0, state), 32)

    def test_reauthorization_separates_nonce_without_resetting_human_business_identity(self):
        old, new = self.endpoint(), self.endpoint("human_reauthorized")
        business_scope = lambda endpoint: (jcs(endpoint["actor_id"]), jcs(endpoint["endpoint"]), "scope")
        self.assertEqual(business_scope(old), business_scope(new))
        self.assertNotEqual(nonce_scope("g", 1, old), nonce_scope("g", 1, new))
        agent_old, agent_new = self.endpoint("agent_old"), self.endpoint("agent_reauthorized")
        self.assertEqual(agent_old["signature_key_base64url"], agent_new["signature_key_base64url"])
        self.assertNotEqual(sender_domain(agent_old), sender_domain(agent_new))

    def test_lint_accepts_current_contract_and_rejects_registry_and_kat_mutations(self):
        lint = Lint()
        check_signal_endpoint_contract(lint)
        self.assertEqual(lint.errors, [])
        for mutation in ("actor_only_registry", "wrong_encoding", "wrong_schema", "key", "context", "missing_case", "aead"):
            registry, fixture = copy.deepcopy(self.registry), copy.deepcopy(self.fixture)
            entry = next(row for row in registry["labels"] if row["label"] == "ak.signal-v1")
            if mutation == "actor_only_registry":
                entry["context_fields"] = ["sender_domain"]
            elif mutation == "wrong_encoding":
                entry["context_encoding"] = "exact active LeafNode BasicCredential identity bytes"
            elif mutation == "wrong_schema":
                entry["context_schema_ref"] = "schemas/common-ids.schema.json#/$defs/actor_id"
            elif mutation == "key":
                fixture["signal_endpoint_contract"]["domains"][0]["signal_key_hex"] = "00" * 16
            elif mutation == "context":
                fixture["signal_endpoint_contract"]["domains"][0]["sender_domain_utf8"] = "bare-device"
            elif mutation == "missing_case":
                fixture["signal_endpoint_contract"]["domains"].pop()
            else:
                fixture["signal_endpoint_contract"]["same_actor_equal_nonce_aead"]["first_ciphertext_hex"] = "00" * 48
            with self.subTest(mutation=mutation), patch("tools.artifact_lint.signal_endpoint.load_json", side_effect=lambda _lint, path: registry if path.name == "exporter-label-registry.json" else fixture):
                lint = Lint()
                check_signal_endpoint_contract(lint)
                self.assertTrue(lint.errors)


if __name__ == "__main__":
    unittest.main()
