"""Pure transcript/shape regressions; no native role/DB/RFC acceptance credit."""
import copy
import json
import unittest
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.content_history import b64
from tools.mls_native_scope_source import basis_digest, signing_bytes, verify_source_bytes, covered_authorization, installed_fence_projection
from tools.regenerate_mls_native_scope_source_fixture import build_fixture, OUTPUT


class NativeScopeSourceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = build_fixture()
        self.case = self.fixture["case"]

    def verify(self, q=None, r=None, expected=None, deadline=None, key=None):
        q = self.case["request"] if q is None else q
        return verify_source_bytes(q, self.case["response"] if r is None else r,
            self.case["owning_method"] if key is None else key, self.case["evaluated_at"],
            self.case["request"] if expected is None else expected,
            self.case["peer_deadline"] if deadline is None else deadline)

    def resign(self, q, r):
        r["signature"]["signature"] = b64(Ed25519PrivateKey.from_private_bytes(bytes([213]) * 32).sign(signing_bytes(q, r["qualification"])))
        return r

    def test_committed_fixture_and_real_signature(self):
        self.assertEqual(json.loads(OUTPUT.read_text(encoding="utf-8")), self.fixture)
        self.verify()

    def test_original_nonce_scope_and_tenure_are_signed_once(self):
        for field, value in [("query_nonce_base64url", b64(bytes([2]) * 32)), ("original_request_digest", "sha256:" + "ab" * 32), ("governance_authority_ref", self.case["qualified_endpoint_context_not_H_leaf_attestation"]["authorization_event_ref"])]:
            q = copy.deepcopy(self.case["request"]); q[field] = value
            with self.subTest(field=field), self.assertRaises((ValueError, InvalidSignature)):
                self.verify(q=q, expected=q)

    def test_source_and_native_producer_keys_are_independent(self):
        key = copy.deepcopy(self.case["owning_method"])
        key["public_key_base64url"] = self.case["wrong_method_public_key_base64url"]
        with self.assertRaises(InvalidSignature): self.verify(key=key)

    def test_fresh_source_keeps_existing_business_identity(self):
        q = copy.deepcopy(self.case["request"]); q["query_nonce_base64url"] = b64(bytes([3]) * 32)
        r = self.resign(q, copy.deepcopy(self.case["response"]))
        self.assertEqual(q["original_request_digest"], self.case["request"]["original_request_digest"])
        self.verify(q=q, r=r, expected=q)

    def test_first_installed_empty_fence_changes_basis_but_fp_only_does_not(self):
        values = self.fixture["basis_cases"]
        self.assertNotEqual(values["before_digest"], values["installed_empty_fence_digest"])
        self.assertEqual(values["before_digest"], values["fp_reservation_not_a_fence_digest"])
        self.assertNotEqual(values["before_digest"], values["controller_rejoin_digest"])
        expected = copy.deepcopy(self.case["request"]); expected["g_basis_digest"] = values["installed_empty_fence_digest"]
        with self.assertRaises(ValueError): self.verify(expected=expected)

    def test_complete_negative_candidates_cannot_be_omitted_under_opaque_token(self):
        q = copy.deepcopy(self.case["request"]); q["sidecar_membership_basis"]["candidate_joins"].pop()
        r = self.resign(q, copy.deepcopy(self.case["response"]))
        with self.assertRaises(ValueError): self.verify(q=q, r=r)

    def test_same_key_authorization_ABA_cannot_replace_retained_instance(self):
        q = copy.deepcopy(self.case["request"]); r = copy.deepcopy(self.case["response"])
        q["endpoint_sources"][0]["authorization_event_ref"] = q["genesis_event_ref"]
        r = self.resign(q, r)
        with self.assertRaises(ValueError): self.verify(q=q, r=r)

    def test_result_order_length_and_selected_package_binding_are_required(self):
        for change in ["empty", "extra", "mirrored_endpoint"]:
            q = copy.deepcopy(self.case["request"]); r = copy.deepcopy(self.case["response"])
            results = r["qualification"]["endpoint_qualifications"]
            if change == "empty": results.clear()
            elif change == "extra": results.append(copy.deepcopy(results[0]))
            else: results[0]["endpoint"] = self.case["qualified_endpoint_context_not_H_leaf_attestation"]
            self.resign(q, r)
            with self.subTest(change=change), self.assertRaises(ValueError): self.verify(q=q, r=r)

    def test_sidecar_create_token_mismatch_rejects_even_after_valid_H_resigning(self):
        q = copy.deepcopy(self.case["request"])
        q["sidecar_membership_basis"]["sidecar_create_event_ref"] = q["genesis_event_ref"]
        r = self.resign(q, copy.deepcopy(self.case["response"]))
        with self.assertRaises(ValueError): self.verify(q=q, r=r, expected=q)
        wrong = copy.deepcopy(self.fixture["basis_cases"]["before"])
        wrong["sidecar_membership_basis"]["sidecar_create_event_ref"] = q["genesis_event_ref"]
        with self.assertRaises(ValueError): basis_digest(wrong)

    def test_first_add_requires_real_selected_package_result_shape(self):
        q = copy.deepcopy(self.case["request"])
        original_endpoint = self.case["qualified_endpoint_context_not_H_leaf_attestation"]
        q["endpoint_sources"] = [{"claim_id": "ak:keypackage_claim:019a0000-0000-7000-8000-000000000001"}]
        r = copy.deepcopy(self.case["response"])
        r["qualification"]["endpoint_qualifications"] = [{"state": "qualified", "endpoint": original_endpoint, "keypackage_ref": "sha256:" + "ad" * 32}]
        self.resign(q, r); self.verify(q=q, r=r, expected=q)
        r["qualification"]["endpoint_qualifications"][0].pop("keypackage_ref")
        self.resign(q, r)
        with self.assertRaises(ValueError): self.verify(q=q, r=r, expected=q)

    def test_desired_boolean_projection_is_exact_and_never_a_partial_roster(self):
        q = copy.deepcopy(self.case["request"])
        for values in [[True], [True, False, True], [True, 0], [True, 1], [True, "unknown"]]:
            r = copy.deepcopy(self.case["response"]); r["qualification"]["desired_qualifications"] = values
            self.resign(q, r)
            with self.subTest(values=values), self.assertRaises(ValueError): self.verify(q=q, r=r)
        reordered = copy.deepcopy(self.case["response"])
        reordered["qualification"]["desired_qualifications"].reverse()
        with self.assertRaises(InvalidSignature): self.verify(r=reordered)
        true_ids = [e["agent_actor_id"]["account_id"]["principal_id"] for e, value in zip(q["sidecar_membership_basis"]["candidate_joins"], self.case["response"]["qualification"]["desired_qualifications"]) if value]
        self.assertEqual(true_ids, [q["sidecar_membership_basis"]["candidate_joins"][0]["agent_actor_id"]["account_id"]["principal_id"]])

    def test_response_never_mirrors_request_common_fields(self):
        for field in ["source_id", "destination_id", "effective_scope", "governance_authority_ref", "query_nonce_base64url", "original_request_digest", "g_basis_digest", "sidecar_membership_basis"]:
            r = copy.deepcopy(self.case["response"]); r[field] = self.case["request"][field]
            with self.subTest(field=field), self.assertRaises(ValueError): self.verify(r=r)

    def test_source_expiry_and_original_peer_deadline_still_apply(self):
        q = self.case["request"]; r = copy.deepcopy(self.case["response"])
        r["qualification"]["expires_at"] = self.case["evaluated_at"]; self.resign(q, r)
        with self.assertRaises(ValueError): self.verify(r=r)
        with self.assertRaises(ValueError): self.verify(deadline="2026-11-17T00:00:10.000Z")

    def test_fence_identity_excludes_key_but_preserves_authorization(self):
        source = self.fixture["basis_cases"]["first_source_intent_only_not_native_proof"]
        first = copy.deepcopy(source["attestation"]["replacement"])
        second = copy.deepcopy(first); second["signature_key_base64url"] = b64(bytes([4]) * 32)
        self.assertEqual(covered_authorization(first), covered_authorization(second))
        self.assertEqual(len(installed_fence_projection(source, [first, second])["covered_authorizations"]), 1)
        second["authorization_event_ref"] = self.case["request"]["genesis_event_ref"]
        self.assertNotEqual(covered_authorization(first), covered_authorization(second))

    def test_noncanonical_nonce_and_wrong_scope_projection_are_rejected(self):
        q = copy.deepcopy(self.case["request"]); q["query_nonce_base64url"] += "="
        r = self.resign(q, copy.deepcopy(self.case["response"]))
        with self.assertRaises(ValueError): self.verify(q=q, r=r, expected=q)
        q = copy.deepcopy(self.case["request"])
        q["effective_scope"] = {"kind": "realm", "realm_id": q["realm_id"]}
        q["purpose"] = "mls_admission"; q.pop("sidecar_membership_basis")
        r = self.resign(q, copy.deepcopy(self.case["response"]))
        with self.assertRaises(ValueError): self.verify(q=q, r=r, expected=q)

    def test_signature_projection_has_one_exact_request_and_qualification(self):
        raw = signing_bytes(self.case["request"], self.case["response"]["qualification"])
        self.assertEqual(raw.hex(), self.case["signing_bytes_hex"])
        q = copy.deepcopy(self.case["request"]); q["purpose"] = "payload_delivery"
        with self.assertRaises(InvalidSignature): self.verify(q=q, expected=q)


if __name__ == "__main__": unittest.main()
