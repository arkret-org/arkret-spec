from __future__ import annotations

import base64
import copy
import hashlib
import json
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import check_session_grant_kat as checker
from tools.check_opaque_session_grant import REQUIRED_CASES, validator
from tools.session_grant_reference import (
    GrantError, IssuerLedger, ath, canonical_public_jwk, credential_digest, grant_ref,
    jcs_text, jwk_thumbprint, secret_from_random, sign_dpop, strict_base64url,
    validate_id, validate_metadata, validate_ref, validate_secret, verify_dpop,
)


class SessionGrantKatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = checker.load_json(checker.FIXTURE_PATH)
        cls.contract = checker.load_json(checker.CONTRACT_PATH)
        cls.schema = checker.load_json(checker.CLAIMS_SCHEMA_PATH)
        cls.common = checker.load_json(checker.COMMON_IDS_PATH)
        cls.vectors = {row["name"]: row for row in cls.fixture["accepted_vectors"]}
        cls.now = "2026-08-08T12:00:00.000Z"

    def _check(self, fixture=None, contract=None, schema=None, common=None):
        return checker.check_documents(
            copy.deepcopy(self.fixture if fixture is None else fixture),
            copy.deepcopy(self.contract if contract is None else contract),
            copy.deepcopy(self.schema if schema is None else schema),
            copy.deepcopy(self.common if common is None else common),
        )

    def _issue(self, ledger=None, name="issuer_a_standard", request_id="request-1"):
        ledger = ledger or IssuerLedger()
        row = self.vectors[name]
        outcome = ledger.issue(copy.deepcopy(row["metadata"]), request_id,
                               {"request_id": request_id, "audience_id": row["metadata"]["audience_id"]},
                               self.now, holder_current=True,
                               random_source=lambda size: bytes.fromhex(row["random_bytes_hex"]))
        return ledger, outcome

    def _refresh(self, ledger, intent=None, successor=None, current=True):
        predecessor = self.vectors["issuer_a_standard"]
        next_row = self.vectors["refresh_successor"]
        return ledger.refresh(predecessor["metadata"]["issuer_id"], predecessor["session_grant"],
                              copy.deepcopy(next_row["metadata"] if successor is None else successor),
                              {"purpose": "refresh"} if intent is None else intent, self.now,
                              holder_current=current,
                              random_source=lambda size: bytes.fromhex(next_row["random_bytes_hex"]))

    def _dpop(self, **changes):
        row = self.fixture["dpop_kat"]
        args = {
            "seed": bytes.fromhex(row["public_test_seed_hex"]), "secret": row["session_grant"],
            "method": row["method"], "uri": row["uri"], "issued": row["iat"],
            "jti": row["jti"], "nonce": row["nonce"],
        }
        args.update(changes)
        return sign_dpop(**args)

    def _verify_dpop(self, proof=None, **changes):
        row = self.fixture["dpop_kat"]
        args = {"proof": row["proof_jwt"] if proof is None else proof,
                "secret": row["session_grant"], "metadata": copy.deepcopy(self.vectors["issuer_a_standard"]["metadata"]),
                "method": row["method"], "uri": row["uri"], "now": row["iat"], "seen": set(), "nonce": row["nonce"]}
        args.update(changes)
        verify_dpop(**args)

    def test_repository_fixture_and_actual_contract_are_reproducible(self):
        self.assertEqual(self._check(), [])
        self.assertEqual(checker.check_agent_initial_proof(), [])

    def test_issuer_contract_requires_allocated_identity_and_exact_secret(self):
        changed = copy.deepcopy(self.contract)
        changed["id_kind_registry"]["issuer_record_identity_contract"]["secret_bytes"] = 16
        self.assertTrue(any("secret_bytes" in error for error in self._check(contract=changed)))

    def test_content_addressed_identity_contract_is_rejected(self):
        changed = copy.deepcopy(self.contract)
        row = next(row for row in changed["id_kind_registry"]["id_kinds"] if row["kind"] == "session_grant")
        row["id_form"] = "suite_tagged_full_digest"
        self.assertTrue(any("issuer-allocated" in error for error in self._check(contract=changed)))

    def test_secret_is_exact_32_octets_without_a_header(self):
        row = self.vectors["issuer_a_standard"]
        self.assertEqual(secret_from_random(bytes.fromhex(row["random_bytes_hex"])), row["session_grant"])
        self.assertEqual(len(row["session_grant"]), 43)
        self.assertEqual(len(strict_base64url(row["session_grant"], 32)), 32)
        for size in (0, 16, 31, 33):
            with self.subTest(size=size), self.assertRaises(GrantError):
                secret_from_random(bytes(size))

    def test_secret_padding_and_nonzero_pad_bits_are_rejected(self):
        secret = self.vectors["issuer_a_standard"]["session_grant"]
        self.assertTrue(secret.endswith("8"))
        for invalid in (secret + "=", secret[:-1] + "9", secret[:-1], " " + secret, "jwt.header.signature"):
            with self.subTest(invalid=invalid), self.assertRaises(GrantError):
                validate_secret(invalid)

    def test_explicit_entropy_output_drift_is_detected(self):
        changed = copy.deepcopy(self.fixture)
        changed["accepted_vectors"][0]["random_bytes_hex"] = "ff" * 32
        errors = self._check(fixture=changed)
        self.assertTrue(any("session_grant mismatch" in error for error in errors))
        self.assertTrue(any("credential_digest mismatch" in error for error in errors))
        self.assertTrue(any("dpop_ath mismatch" in error for error in errors))

    def test_metadata_is_not_an_id_derivation_input(self):
        left = self.vectors["issuer_a_standard"]
        right = self.vectors["issuer_b_same_record_id"]
        self.assertEqual(left["metadata"]["id"], right["metadata"]["id"])
        self.assertNotEqual(left["session_grant_ref"], right["session_grant_ref"])
        self.assertNotEqual(left["session_grant"], right["session_grant"])
        validate_id(left["metadata"]["id"])

    def test_uuidv7_and_full_portable_ref_are_required(self):
        good = self.vectors["issuer_a_standard"]["session_grant_ref"]
        self.assertEqual(validate_ref(good), (good["issuer_id"], good["id"]))
        for invalid in (good["id"], {"id": good["id"]}, {**good, "session_grant": "secret"}):
            with self.subTest(invalid=invalid), self.assertRaises(GrantError):
                validate_ref(invalid)
        with self.assertRaises(GrantError):
            validate_id("ak:session_grant:" + "A" * 44)
        with self.assertRaises(GrantError):
            validate_id(good["id"].replace("-7000-", "-4000-"))

    def test_canonical_metadata_bytes_drift_is_detected(self):
        changed = copy.deepcopy(self.fixture)
        changed["accepted_vectors"][0]["canonical_metadata_utf8"] += " "
        self.assertTrue(any("canonical_metadata_utf8 mismatch" in error for error in self._check(fixture=changed)))

    def test_ascii_credential_hash_is_not_decoded_random_hash(self):
        secret = self.vectors["issuer_a_standard"]["session_grant"]
        self.assertEqual(credential_digest(secret), "sha256:" + hashlib.sha256(secret.encode("ascii")).hexdigest())
        wrong = base64.urlsafe_b64encode(hashlib.sha256(strict_base64url(secret, 32)).digest()).rstrip(b"=").decode()
        self.assertNotEqual(ath(secret), wrong)

    def test_public_jwk_inputs_normalize_to_one_key(self):
        expected = self.fixture["canonical_public_jwk"]
        for value in self.fixture["equivalent_non_canonical_jwk_inputs"]:
            _, canonical = canonical_public_jwk(value)
            self.assertEqual(canonical, expected)
            self.assertEqual(jwk_thumbprint(value), jwk_thumbprint(expected))

    def test_private_or_symmetric_jwk_and_changed_key_are_rejected(self):
        changed = json.loads(self.fixture["canonical_public_jwk"])
        changed["d"] = "A" * 43
        with self.assertRaisesRegex(GrantError, "private_or_symmetric"):
            canonical_public_jwk(jcs_text(changed))
        metadata = copy.deepcopy(self.vectors["issuer_a_standard"]["metadata"])
        metadata["cnf_jkt"] = "A" * 43
        with self.assertRaisesRegex(GrantError, "holder_thumbprint"):
            validate_metadata(metadata)

    def test_metadata_schema_is_closed_and_all_classes_have_positive_vectors(self):
        check = validator("schemas/service-operation-dtos.schema.json#/$defs/SessionGrantMetadata", self.schema, self.common)
        for row in self.fixture["accepted_vectors"]:
            with self.subTest(name=row["name"]):
                self.assertEqual(list(check.iter_errors(row["metadata"])), [])
        for field in ("holder_binding", "cnf_jkt", "account_id", "not_before", "session_id"):
            changed = copy.deepcopy(self.vectors["issuer_a_standard"]["metadata"])
            changed.pop(field)
            self.assertFalse(check.is_valid(changed), field)
        changed = copy.deepcopy(self.vectors["issuer_a_standard"]["metadata"])
        changed["unregistered"] = True
        self.assertFalse(check.is_valid(changed))

    def test_class_and_holder_xor_are_enforced_by_real_schema(self):
        check = validator("schemas/service-operation-dtos.schema.json#/$defs/SessionGrantMetadata", self.schema, self.common)
        for case in self.fixture["credential_binding_negative_cases"]:
            with self.subTest(case=case["name"]):
                changed = copy.deepcopy(self.vectors[case["base_vector"]]["metadata"])
                for field in case.get("omit", []):
                    changed.pop(field, None)
                changed.update(case.get("set", {}))
                self.assertFalse(check.is_valid(changed))

    def test_agent_resource_ceiling_remains_complete_and_closed(self):
        check = validator("schemas/service-operation-dtos.schema.json#/$defs/SessionGrantMetadata", self.schema, self.common)
        agent = self.vectors["agent_runtime"]["metadata"]
        for field in agent["scope_details"]:
            for replacement in ("missing", None):
                with self.subTest(field=field, replacement=replacement):
                    changed = copy.deepcopy(agent)
                    if replacement == "missing":
                        changed["scope_details"].pop(field)
                    else:
                        changed["scope_details"][field] = replacement
                    self.assertFalse(check.is_valid(changed))
        for field in ("resources", "constraints"):
            changed = copy.deepcopy(agent)
            changed["scope_details"][field]["unregistered"] = []
            self.assertFalse(check.is_valid(changed))

    def test_active_introspection_requires_complete_metadata(self):
        check = validator("schemas/service-operation-dtos.schema.json#/$defs/SessionGrantIntrospectResponseBody", self.schema, self.common)
        inactive = {"active": False, "status": "not_found", "proof_required": False, "one_time_use_consumed": False}
        self.assertTrue(check.is_valid(inactive))
        for name in ("issuer_a_standard", "recovery_candidate", "agent_runtime"):
            active = {"active": True, "status": "active", "proof_required": False, "one_time_use_consumed": False,
                      "grant": {**copy.deepcopy(self.vectors[name]["metadata"]), "revocation_ref": "issuer-ledger-kat"}}
            self.assertEqual(list(check.iter_errors(active)), [], name)
            del active["grant"]["cnf_jkt"]
            self.assertFalse(check.is_valid(active))

    def test_ledger_fixture_executes_all_replay_and_refresh_cases(self):
        self.assertEqual(checker.run_ledger_cases(self.fixture), [])
        self.assertTrue(REQUIRED_CASES <= {case["name"] for case in self.fixture["ledger_cases"]})

    def test_removing_required_executable_case_fails_coverage(self):
        changed = copy.deepcopy(self.fixture)
        changed["ledger_cases"] = changed["ledger_cases"][1:]
        self.assertTrue(any("every required" in error for error in checker.run_ledger_cases(changed)))

    def test_random_token_shape_does_not_grant_authority(self):
        ledger, _ = self._issue()
        row = self.vectors["issuer_a_standard"]
        unknown = secret_from_random(bytes([255]) * 32)
        with self.assertRaisesRegex(GrantError, "not_found"):
            ledger.introspect(row["metadata"]["issuer_id"], unknown, row["metadata"]["audience_id"], self.now)

    def test_id_only_status_cannot_be_used_as_exact_credential(self):
        ledger, outcome = self._issue()
        self.assertEqual(ledger.management_status(outcome["session_grant_ref"], self.now), "active")
        with self.assertRaisesRegex(GrantError, "invalid_session_grant_secret"):
            ledger.introspect(outcome["metadata"]["issuer_id"], outcome["metadata"]["id"], outcome["metadata"]["audience_id"], self.now)

    def test_metadata_copy_cannot_mutate_frozen_issuer_record(self):
        ledger, outcome = self._issue()
        row = self.vectors["issuer_a_standard"]
        outcome["metadata"]["scopes"].append("ak.forbidden")
        actual = ledger.introspect(row["metadata"]["issuer_id"], row["session_grant"], row["metadata"]["audience_id"], self.now)
        self.assertEqual(actual, row["metadata"])

    def test_concurrent_issue_allocates_once_and_returns_one_exact_outcome(self):
        ledger = IssuerLedger()
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(lambda _: self._issue(ledger)[1], range(16)))
        self.assertTrue(all(outcome == outcomes[0] for outcome in outcomes))
        self.assertEqual(len(ledger.records), 1)
        self.assertEqual(ledger.draws, 1)

    def test_concurrent_refresh_has_one_successor(self):
        ledger, _ = self._issue()
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(lambda _: self._refresh(ledger), range(16)))
        self.assertTrue(all(outcome == outcomes[0] for outcome in outcomes))
        self.assertEqual(len(ledger.records), 2)
        self.assertEqual(ledger.draws, 2)

    def test_changed_refresh_intent_cannot_fork_after_first_commit(self):
        ledger, _ = self._issue()
        self._refresh(ledger)
        with self.assertRaisesRegex(GrantError, "predecessor_terminal"):
            self._refresh(ledger, {"purpose": "different"})
        self.assertEqual(len(ledger.records), 2)

    def test_refresh_cannot_widen_or_change_endpoint(self):
        for field, value in (("scopes", ["ak.forbidden"]), ("session_id", "another-chain"),
                             ("account_id", {"principal_id": "ak:did_core:webvh:other", "station_id": "ak:did_core:webvh:otherstation"})):
            with self.subTest(field=field):
                ledger, _ = self._issue()
                successor = copy.deepcopy(self.vectors["refresh_successor"]["metadata"])
                successor[field] = value
                with self.assertRaisesRegex(GrantError, "refresh_ceiling_changed"):
                    self._refresh(ledger, successor=successor)
                self.assertEqual(len(ledger.records), 1)

    def test_failed_current_holder_does_not_allocate(self):
        ledger = IssuerLedger()
        row = self.vectors["issuer_a_standard"]
        with self.assertRaisesRegex(GrantError, "unauthenticated"):
            ledger.issue(row["metadata"], "new", {}, self.now, holder_current=False)
        self.assertEqual(len(ledger.records), 0)
        self.assertEqual(ledger.draws, 0)

    def test_revoke_is_idempotent_and_does_not_mutate_metadata(self):
        ledger, outcome = self._issue()
        ledger.revoke(outcome["session_grant_ref"], caller_current=True)
        snapshot = ledger.export()
        ledger.revoke(outcome["session_grant_ref"], caller_current=True)
        self.assertEqual(ledger.export(), snapshot)

    def test_restore_retains_byte_exact_secret_and_outcome(self):
        ledger, outcome = self._issue()
        restored = IssuerLedger.restore(json.loads(json.dumps(ledger.export())))
        _, replay = self._issue(restored)
        self.assertEqual(replay, outcome)
        self.assertEqual(restored.draws, 1)

    def test_dpop_golden_signature_verifies_without_credential_jwt(self):
        self.assertEqual(self._dpop(), self.fixture["dpop_kat"]["proof_jwt"])
        self._verify_dpop()

    def test_dpop_wrong_secret_method_uri_nonce_and_key_fail(self):
        for kwargs, reason in (({"secret": secret_from_random(bytes([99]) * 32)}, "ath"),
                               ({"method": "POST"}, "target"), ({"uri": "https://other.example/_arkret/self/account"}, "target"),
                               ({"nonce": "other"}, "nonce")):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(GrantError, reason):
                self._verify_dpop(**kwargs)
        with self.assertRaisesRegex(GrantError, "thumbprint"):
            self._verify_dpop(proof=self._dpop(seed=bytes([9]) * 32))

    def test_dpop_freshness_boundaries_and_replay_are_independent(self):
        row = self.fixture["dpop_kat"]
        for offset in (-30, 30):
            self._verify_dpop(now=row["iat"] + offset)
        for offset in (-31, 31):
            with self.assertRaisesRegex(GrantError, "freshness"):
                self._verify_dpop(now=row["iat"] + offset)
        seen = set()
        self._verify_dpop(seen=seen)
        with self.assertRaisesRegex(GrantError, "dpop_replay"):
            self._verify_dpop(seen=seen)

    def test_accepted_device_signature_binds_intent_and_new_holder(self):
        row = self.fixture["accepted_device_possession"]
        unsigned = copy.deepcopy(row["proof"])
        signature = strict_base64url(unsigned.pop("signature"), 64)
        key = Ed25519PublicKey.from_public_bytes(strict_base64url(row["public_key_b64u"], 32))
        for field, value in (("holder_jkt", "A" * 43), ("purpose", "recovery_completion_grant_issue"),
                             ("session_intent_digest", "sha256:" + "0" * 64), ("account_handoff_grant_digest", "sha256:" + "0" * 64)):
            changed = dict(unsigned, **{field: value})
            with self.subTest(field=field), self.assertRaises(InvalidSignature):
                key.verify(signature, (changed["context"] + "\n" + jcs_text(changed)).encode())

    def test_jcs_retains_utf16_order_and_rejects_unsupported_numbers(self):
        self.assertEqual(jcs_text({"\ue000": 1, "\U00010000": 2}), '{"\U00010000":2,"\ue000":1}')
        for value in (1.0, 9_007_199_254_740_992):
            with self.assertRaises(ValueError):
                jcs_text(value)


if __name__ == "__main__":
    unittest.main()
