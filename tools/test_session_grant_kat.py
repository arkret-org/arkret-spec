"""Focused regression tests for the dedicated SessionGrant KAT checker."""

from __future__ import annotations

import copy
import unittest

from tools import check_session_grant_kat, lint_artifacts


class SessionGrantKatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = check_session_grant_kat.load_json(check_session_grant_kat.FIXTURE_PATH)
        cls.contract = check_session_grant_kat.load_json(check_session_grant_kat.CONTRACT_PATH)
        cls.digest_registry = check_session_grant_kat.load_json(
            check_session_grant_kat.DIGEST_SUITE_PATH
        )
        cls.claims_schema = check_session_grant_kat.load_json(
            check_session_grant_kat.CLAIMS_SCHEMA_PATH
        )

    def _check(self, *, fixture=None, contract=None, digest_registry=None, claims_schema=None):
        return check_session_grant_kat.check_documents(
            copy.deepcopy(self.fixture if fixture is None else fixture),
            copy.deepcopy(self.contract if contract is None else contract),
            copy.deepcopy(self.digest_registry if digest_registry is None else digest_registry),
            copy.deepcopy(self.claims_schema if claims_schema is None else claims_schema),
        )

    def _claims_by_vector(self) -> dict[str, dict]:
        issuer_contract = self.contract["id_kind_registry"]["issuer_record_identity_contract"]
        required, optional = check_session_grant_kat._contract_field_sets(issuer_contract)
        resolved, errors = check_session_grant_kat._resolve_vectors(
            self.fixture["accepted_vectors"], required | optional
        )
        self.assertEqual(errors, [])
        vectors = {row["name"]: row for row in self.fixture["accepted_vectors"]}
        return {
            name: {
                **{key: copy.deepcopy(value) for key, value in preimage.items() if key != "schema"},
                "kind": "ak.session.grant",
                "jti": vectors[name]["jwt_jti"],
            }
            for name, preimage in resolved.items()
        }

    def test_repository_fixture_is_reproducible(self) -> None:
        self.assertEqual(self._check(), [])

    def test_inherited_override_is_recomputed(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        vector = next(
            row
            for row in fixture["accepted_vectors"]
            if row["name"] == "issuer_b_domain_separation"
        )
        vector["override"]["issuer"] = "did:webvh:z6mkfixture:drift.example"
        errors = self._check(fixture=fixture)
        self.assertTrue(any("issuer_b_domain_separation: canonical_preimage_utf8 mismatch" in error for error in errors), errors)
        self.assertTrue(any("issuer_b_domain_separation: sha256_digest_hex mismatch" in error for error in errors), errors)
        self.assertTrue(any("issuer_b_domain_separation: grant_id mismatch" in error for error in errors), errors)

    def test_explicit_canonical_bytes_drift_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["accepted_vectors"][0]["canonical_preimage_utf8"] += " "
        errors = self._check(fixture=fixture)
        self.assertTrue(any("canonical_preimage_utf8 mismatch" in error for error in errors), errors)

    def test_suite_code_must_come_from_registry(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["accepted_vectors"][0]["suite_wire_code"] = 2
        errors = self._check(fixture=fixture)
        self.assertTrue(any("does not come from digest-suite registry" in error for error in errors), errors)

    def test_v1_suite_code_high_nibble_must_be_zero(self) -> None:
        contract = copy.deepcopy(self.contract)
        digest_registry = copy.deepcopy(self.digest_registry)
        issuer_contract = contract["id_kind_registry"]["issuer_record_identity_contract"]
        issuer_contract["digest_suite_wire_code"] = 0x11
        suite = next(
            row for row in digest_registry["suites"] if row["canonical_id"] == "sha256"
        )
        suite["wire_code"] = 0x11
        errors = self._check(contract=contract, digest_registry=digest_registry)
        self.assertTrue(any("must have a zero high nibble" in error for error in errors), errors)

    def test_existing_registry_codes_01_02_03_are_unchanged_and_v1_safe(self) -> None:
        codes = {
            row["canonical_id"]: row["wire_code"]
            for row in self.digest_registry["suites"]
            if row["canonical_id"] in {"sha256", "blake3", "cbor.sha256"}
        }
        self.assertEqual(codes, {"sha256": 0x01, "blake3": 0x02, "cbor.sha256": 0x03})
        self.assertTrue(all(code & 0xF0 == 0 for code in codes.values()))

    def test_realm_nibble_tagged_id_form_is_rejected_for_session_grant(self) -> None:
        contract = copy.deepcopy(self.contract)
        row = next(
            row
            for row in contract["id_kind_registry"]["id_kinds"]
            if row["kind"] == "session_grant"
        )
        row["id_form"] = "derivation_tagged_full_digest"
        errors = self._check(contract=contract)
        self.assertTrue(any("not the Realm nibble-tagged form" in error for error in errors), errors)

    def test_grant_token_must_be_suite_code_plus_full_digest(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        vector = fixture["accepted_vectors"][0]
        vector["grant_id"] = vector["grant_id"][:-1] + "A"
        vector["jwt_jti"] = vector["grant_id"]
        errors = self._check(fixture=fixture)
        self.assertTrue(any("grant_id mismatch" in error for error in errors), errors)
        self.assertTrue(any("not suite-code || digest" in error for error in errors), errors)

    def test_nonce_with_nonzero_padding_bits_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        nonce = fixture["accepted_vectors"][0]["issuance_preimage"]["issuance_nonce"]
        self.assertTrue(nonce.endswith("8"))
        fixture["accepted_vectors"][0]["issuance_preimage"]["issuance_nonce"] = nonce[:-1] + "9"
        errors = self._check(fixture=fixture)
        self.assertTrue(any("issuance_nonce is not canonical unpadded Base64URL" in error for error in errors), errors)

    def test_equivalent_jwk_input_must_normalize_to_same_public_key(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["equivalent_non_canonical_jwk_inputs"][0] = (
            '{"crv":"Ed25519","kty":"OKP","x":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}'
        )
        errors = self._check(fixture=fixture)
        self.assertTrue(any("does not normalize to canonical_public_jwk" in error for error in errors), errors)

    def test_private_jwk_material_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["canonical_public_jwk"] = (
            '{"crv":"Ed25519","d":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",'
            '"kty":"OKP","x":"11qYAYdk9Jc1iP4Z9Qv7XKpM6Jw8LmN0RsTuVwXyZaB"}'
        )
        errors = self._check(fixture=fixture)
        self.assertTrue(any("private/symmetric JWK member" in error for error in errors), errors)

    def test_claim_property_drift_breaks_closed_preimage_projection(self) -> None:
        schema = copy.deepcopy(self.claims_schema)
        schema["$defs"]["SignedSessionGrantClaims"]["properties"]["device_id"] = {
            "type": "string"
        }
        errors = self._check(claims_schema=schema)
        self.assertTrue(any("preimage/claims closure drift" in error for error in errors), errors)

    def test_credential_class_binding_xor_is_enforced(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["accepted_vectors"][0]["issuance_preimage"]["bootstrap_binding"] = {
            "credential_kind": "device_bootstrap"
        }
        errors = self._check(fixture=fixture)
        self.assertTrue(any("requires exactly holder_binding" in error for error in errors), errors)

    def test_credential_binding_xor_is_enforced_by_json_schema(self) -> None:
        validator = lint_artifacts.schema_validator(
            check_session_grant_kat.CLAIMS_SCHEMA_PATH.resolve(),
            "#/$defs/SignedSessionGrantClaims",
        )
        claims = self._claims_by_vector()
        for name, document in claims.items():
            self.assertEqual(
                list(validator.iter_errors(document)),
                [],
                f"accepted vector {name} must validate as SignedSessionGrantClaims",
            )

        recovery_binding = copy.deepcopy(
            claims["recovery_binding_is_identity_material"]["recovery_binding"]
        )
        invalid_standard = copy.deepcopy(claims["issuer_a_closed_preimage"])
        invalid_standard["recovery_binding"] = recovery_binding
        invalid_bootstrap = copy.deepcopy(claims["device_bootstrap_binding_is_identity_material"])
        invalid_bootstrap["recovery_binding"] = recovery_binding

        self.assertTrue(
            list(validator.iter_errors(invalid_standard)),
            "standard claims carrying recovery_binding must fail the actual JSON Schema",
        )
        self.assertTrue(
            list(validator.iter_errors(invalid_bootstrap)),
            "device_bootstrap claims carrying recovery_binding must fail the actual JSON Schema",
        )

    def test_introspection_grant_requires_cnf_jkt_but_inactive_may_omit_grant(self) -> None:
        validator = lint_artifacts.schema_validator(
            check_session_grant_kat.CLAIMS_SCHEMA_PATH.resolve(),
            "#/$defs/SessionGrantIntrospectOutcome",
        )
        claims = self._claims_by_vector()["issuer_a_closed_preimage"]
        active_outcome = {
            "active": True,
            "status": "active",
            "proof_required": False,
            "one_time_use_consumed": False,
            "grant": {
                "id": claims["jti"],
                "issuer": claims["issuer"],
                "subject": claims["subject"],
                "service_account_id": "service-account-fixture",
                "audience": claims["audience"],
                "scopes": claims["scopes"],
                "expires_at": claims["expires_at"],
                "revocation_ref": "issuer-ledger-fixture",
                "session_public_key": claims["session_public_key"],
                "cnf_jkt": "fixture-rfc7638-thumbprint",
                "credential_class": claims["credential_class"],
                "holder_binding": claims["holder_binding"],
            },
        }
        self.assertEqual(list(validator.iter_errors(active_outcome)), [])

        missing_cnf = copy.deepcopy(active_outcome)
        del missing_cnf["grant"]["cnf_jkt"]
        self.assertTrue(
            list(validator.iter_errors(missing_cnf)),
            "an active introspected grant without cnf_jkt must fail the actual JSON Schema",
        )

        inactive_outcome = {
            "active": False,
            "status": "not_found",
            "proof_required": False,
            "one_time_use_consumed": False,
        }
        self.assertEqual(
            list(validator.iter_errors(inactive_outcome)),
            [],
            "an inactive outcome may omit the entire grant object",
        )

    def test_tamper_cases_must_be_structurally_complete(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["tamper_cases"][0].pop("expected")
        errors = self._check(fixture=fixture)
        self.assertTrue(any("tamper_cases[0].expected must be a non-empty string" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
