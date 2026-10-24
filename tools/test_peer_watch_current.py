"""Mutation tests for the normative cross-Station Watch read gate."""

import copy
import json
import unittest

from tools.artifact_lint.core import ARTIFACTS, Lint
from tools.artifact_lint.peer_watch_current import (
    CONTRACT, FIXTURE, PEER, case_input, check_peer_watch_current, contract_errors, evaluate_read,
)


class PeerWatchCurrentTest(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_canonical_contract_and_all_schema_vectors(self):
        lint = Lint()
        check_peer_watch_current(lint)
        self.assertEqual([], lint.errors)

    def test_missing_operation_rejected(self):
        self.catalog["operation_registry"]["operations"] = [row for row in self.catalog["operation_registry"]["operations"] if row["operation_id"] != PEER]
        self.assertTrue(contract_errors(self.catalog, self.fixture))

    def test_signature_removal_rejected(self):
        peer = next(row for row in self.catalog["operation_registry"]["operations"] if row["operation_id"] == PEER)
        peer.pop("auth_requirements")
        self.assertTrue(contract_errors(self.catalog, self.fixture))

    def test_shared_dto_and_budget_mutations_rejected(self):
        for field, value in [("request_schema_ref", "schemas/exact-current-state-read.schema.json"), ("response_schema_ref", "schemas/realm-state-snapshot.schema.json"), ("max_canonical_body_bytes", 32768)]:
            catalog = copy.deepcopy(self.catalog)
            peer = next(row for row in catalog["operation_registry"]["operations"] if row["operation_id"] == PEER)
            peer[field] = value
            self.assertTrue(contract_errors(catalog, self.fixture), field)

    def test_missing_required_evidence_case_rejected(self):
        self.fixture["cross_station_cases"] = [case for case in self.fixture["cross_station_cases"] if case["name"] != "handoff_omitted_clear_row_fails_closed"]
        self.assertTrue(contract_errors(self.catalog, self.fixture))

    def test_wrong_negative_verdict_cannot_be_blessed(self):
        for name in ["snapshot_omission_does_not_prove_never_written", "others_author_write_prevents_never_written", "handoff_late_response_is_discarded", "same_principal_other_station_is_private_cell"]:
            fixture = copy.deepcopy(self.fixture)
            next(case for case in fixture["cross_station_cases"] if case["name"] == name)["expected"] = "never_written"
            self.assertTrue(contract_errors(self.catalog, fixture), name)

    def test_known_response_faults_have_concrete_wrong_bindings(self):
        for name in ["realm", "selector", "generation", "stream", "revision"]:
            case = next(case for case in self.fixture["cross_station_cases"] if case["name"] == "wrong_response_" + name + "_rejected")
            value = case_input(self.fixture, case)
            self.assertEqual("revision_unavailable", evaluate_read(value), name)
            clean = copy.deepcopy(value["confirmed_response"])
            value["response"] = clean
            self.assertIn(evaluate_read(value), {"current", "never_written"}, name)

    def test_cas_mutation_rejected(self):
        next(case for case in self.fixture["submit_cas_cases"] if case["name"] == "written_clear_omission_rejected")["expected"] = "accepted"
        self.assertTrue(contract_errors(self.catalog, self.fixture))


if __name__ == "__main__":
    unittest.main()
