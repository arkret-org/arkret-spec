import copy
import json
import unittest
from pathlib import Path

from tools.artifact_lint.core import Lint
from tools.artifact_lint.frontier_reduction import check_frontier_reduction_fixture

FIXTURE = Path(__file__).resolve().parents[1] / "spec/v1/artifacts/fixtures/sync-fixture.json"


class FrontierReductionTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def errors(self):
        lint = Lint()
        check_frontier_reduction_fixture(lint, FIXTURE, self.data)
        return lint.errors

    def test_committed_vectors(self):
        self.assertEqual(self.errors(), [])

    def test_lookup_before_validation_cannot_quarantine_local_event(self):
        self.data["frontier_event_evidence"]["forged_carried_id"]["expected"] = {"reason": "witness_disagreement", "quarantine": True}
        self.assertTrue(self.errors())

    def test_collision_requires_valid_proof_and_independent_recomputation(self):
        vector = self.data["frontier_event_evidence"]["injected_full_hash_collision"]
        del vector["injected_digest_hex"]
        self.assertTrue(self.errors())

    def test_benign_scope_cannot_increment_failures_or_claim_completeness(self):
        baseline = copy.deepcopy(self.data)
        for case in self.data["frontier_reduction_cases"]:
            if case["name"] == "permanent_scope_difference":
                case["expected"]["failures"] = 1
        self.assertTrue(self.errors())
        self.data = baseline
        self.data["frontier_reduction_cases"][0]["expected"]["complete"] = True
        self.assertTrue(self.errors())

    def test_http_success_does_not_complete_an_event_intent(self):
        case = next(case for case in self.data["delivery_outcome_cases"] if case["name"] == "http_2xx_without_item_outcome")
        case["expected"]["delivered"] = True
        case["expected"]["retry"] = False
        self.assertTrue(self.errors())

    def test_historical_outcome_does_not_complete_an_event_intent(self):
        case = next(case for case in self.data["delivery_outcome_cases"] if case["name"] == "historical_only_original_outcome_does_not_complete_intent")
        case["top_level_accepted"] = case["original_outcome_accepted"]
        self.assertTrue(self.errors())

    def test_root_mismatch_does_not_require_routine_scan(self):
        case = next(case for case in self.data["frontier_diagnostic_cases"] if case["name"] == "aggregate_root_mismatch_unknown_scope")
        case["expected"] = "routine_full_history_scan"
        self.assertTrue(self.errors())


if __name__ == "__main__":
    unittest.main()
