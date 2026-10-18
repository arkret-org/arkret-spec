"""Mutation guards for the retained core scope and unknown refusal semantics."""

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.artifact_lint import constraint_evaluation as gate


class ConstraintEvaluationTest(unittest.TestCase):
    def check(self, name=None, mutate=None):
        original = gate.load_json

        def load(lint, path):
            data = copy.deepcopy(original(lint, path))
            if path.name == name:
                mutate(data)
            return data

        with patch.object(gate, "load_json", load):
            lint = gate.Lint()
            gate.check_constraint_evaluation(lint)
            return lint.errors

    def test_current_contract_and_all_schema_cases(self):
        self.assertEqual(self.check(), [])

    def test_unknown_cannot_disappear_from_refusal_fold(self):
        self.assertTrue(self.check("contract-registry.json", lambda value: value[
            "capability_action_registry"]["constraint_evaluation_contract"].update(refusal_applies_on=["match"])))

    def test_parser_only_support_cannot_replace_positive_consumer(self):
        self.assertTrue(self.check("contract-registry.json", lambda value: value[
            "capability_action_registry"]["constraint_evaluation_contract"].update(support_evidence=["decoder"])))

    def test_session_cannot_be_removed_from_the_core_floor(self):
        self.assertTrue(self.check("conformance-profiles.json", lambda value: value[
            "profile_requirements"]["ak.profile.core_event_store.v1"].update(required_constraint_subkinds=["window", "rate"])))

    def test_an_unknown_deny_cannot_expect_allowed(self):
        self.assertTrue(self.check("constraint-evaluation-fixture.json", lambda value: value[
            "schema_validation_cases"][1].update(expected_with_unrestricted_grant="Allowed")))

    def test_missing_matrix_case_is_not_coverage(self):
        self.assertTrue(self.check("constraint-evaluation-fixture.json", lambda value: value[
            "schema_validation_cases"].pop()))


if __name__ == "__main__":
    unittest.main()
