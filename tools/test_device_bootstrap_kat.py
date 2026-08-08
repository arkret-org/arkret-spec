"""Focused regression tests for the first-device bootstrap KAT checker."""

from __future__ import annotations

import copy
import unittest

from tools import check_device_bootstrap_kat as checker


class DeviceBootstrapKatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = checker.load_json(checker.FIXTURE_PATH)
        cls.session = checker.load_json(checker.SESSION_FIXTURE_PATH)
        cls.principal = checker.load_json(checker.PRINCIPAL_SCHEMA_PATH)
        cls.agent = checker.load_json(checker.AGENT_SCHEMA_PATH)
        cls.event = checker.load_json(checker.EVENT_SCHEMA_PATH)
        cls.service = checker.load_json(checker.SERVICE_SCHEMA_PATH)

    def check(self, fixture=None, session=None, principal=None, agent=None, event=None, service=None):
        return checker.check_documents(
            copy.deepcopy(self.fixture if fixture is None else fixture),
            copy.deepcopy(self.session if session is None else session),
            copy.deepcopy(self.principal if principal is None else principal),
            copy.deepcopy(self.agent if agent is None else agent),
            copy.deepcopy(self.event if event is None else event),
            copy.deepcopy(self.service if service is None else service),
        )

    def test_repository_fixture_is_reproducible(self) -> None:
        self.assertEqual(self.check(), [])

    def test_founding_order_tamper_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["founding_batch"]["event_ids"].reverse()
        self.assertTrue(any("founding" in error or "predecessor" in error for error in self.check(fixture=fixture)))

    def test_raw_key_text_hash_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        text = fixture["device_key"]["public_key_multibase"].encode()
        fixture["device_key"]["expected_digest"] = checker.sha256_typed(text)
        self.assertTrue(any("device_key_digest" in error or "raw-key" in error for error in self.check(fixture=fixture)))

    def test_request_tamper_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["enroll_request"]["authorize_event_preimage"]["payload"]["hpke_key"] += "x"
        self.assertTrue(any("request" in error or "Event" in error for error in self.check(fixture=fixture)))

    def test_authority_proof_in_preimage_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["enroll_request"]["authorize_event_preimage"]["proofs"] = []
        self.assertTrue(any("preimage shape" in error for error in self.check(fixture=fixture)))

    def test_closed_request_unknown_member_vector_is_executable(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        row = fixture["canonical_request"]["negative_vectors"][1]
        row["json_pointer"] = "/device_id"
        self.assertTrue(any("adds no unknown" in error for error in self.check(fixture=fixture)))

    def test_holder_jkt_mismatch_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["holder"]["credential_cnf_jkt"] = "A" * 43
        self.assertTrue(any("holder_jkt" in error for error in self.check(fixture=fixture)))

    def test_fifth_transaction_state_is_rejected(self) -> None:
        principal = copy.deepcopy(self.principal)
        principal["$defs"]["device_bootstrap_transaction_state"]["enum"].append("failed")
        self.assertTrue(any("state" in error for error in self.check(principal=principal)))

    def test_session_fixture_binding_drift_is_rejected(self) -> None:
        session = copy.deepcopy(self.session)
        row = next(row for row in session["accepted_vectors"] if row["name"] == "device_bootstrap_binding_is_identity_material")
        row["override"]["bootstrap_binding"]["founding_batch_digest"] = "sha256:" + "0" * 64
        self.assertTrue(any("SessionGrant" in error for error in self.check(session=session)))

    def test_issue_request_admitting_issuer_derived_field_is_rejected(self) -> None:
        service = copy.deepcopy(self.service)
        bootstrap = service["$defs"]["SessionGrantDeviceBootstrapRequest"]
        bootstrap["properties"]["transaction_id"] = {"type": "string"}
        self.assertTrue(any("issuer-derived" in error or "closed field" in error for error in self.check(service=service)))

    def test_issue_request_losing_handoff_xor_is_rejected(self) -> None:
        service = copy.deepcopy(self.service)
        service["$defs"]["SessionGrantRequestBody"]["allOf"] = []
        self.assertTrue(any("XOR" in error for error in self.check(service=service)))

    def test_refresh_contract_losing_accepted_gate_is_rejected(self) -> None:
        service = copy.deepcopy(self.service)
        service["$defs"]["SessionGrantRefreshRequestBody"]["description"] = "ordinary refresh"
        self.assertTrue(any("accepted" in error for error in self.check(service=service)))


if __name__ == "__main__":
    unittest.main()
