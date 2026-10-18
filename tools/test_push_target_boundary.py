"""Mutation checks for push context binding and retired Describe fields."""

import copy
import json
import unittest
from unittest.mock import patch

from tools.artifact_lint import push_target_boundary as gate


class PushTargetBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(gate.FIXTURE.read_text(encoding="utf-8"))
        self.describe = json.loads(gate.DESCRIBE.read_text(encoding="utf-8"))

    def run_gate(self, fixture=None, describe=None):
        original = gate.load_json

        def load(lint, path):
            if path == gate.FIXTURE:
                return self.fixture if fixture is None else fixture
            if path == gate.DESCRIBE:
                return self.describe if describe is None else describe
            return original(lint, path)

        lint = gate.Lint()
        with patch.object(gate, "load_json", side_effect=load):
            gate.check_push_target_boundary(lint)
        return lint.errors

    def test_committed_material(self):
        self.assertEqual(self.run_gate(), [])

    def test_context_and_full_hmac_mutations_fail(self):
        for mutation in ("omit_station", "bare_principal", "omit_route", "add_realm", "short_tag", "wrong_secret", "wrong_canonical", "copy_target", "omit_case"):
            with self.subTest(mutation=mutation):
                data = copy.deepcopy(self.fixture)
                row = data["derivations"][0]
                if mutation == "omit_station":
                    del row["context"]["account_id"]["station_id"]
                elif mutation == "bare_principal":
                    row["context"]["account_id"] = row["context"]["account_id"]["principal_id"]
                elif mutation == "omit_route":
                    del row["context"]["push_route_id"]
                elif mutation == "add_realm":
                    row["context"]["realm_id"] = "realm"
                elif mutation == "short_tag":
                    row["expected_push_target_id"] = row["expected_push_target_id"][:-1]
                elif mutation == "wrong_secret":
                    row["test_secret_hex"] = "00" * 32
                elif mutation == "wrong_canonical":
                    row["expected_canonical_input"] += " "
                elif mutation == "copy_target":
                    data["derivations"][2]["expected_push_target_id"] = row["expected_push_target_id"]
                else:
                    data["derivations"].pop()
                self.assertTrue(self.run_gate(fixture=data))

    def test_describe_cannot_restore_claims(self):
        for mutation in ("property", "gateway_required", "open"):
            with self.subTest(mutation=mutation):
                describe = copy.deepcopy(self.describe)
                if mutation == "property":
                    describe["properties"]["privacy_derivation"] = {}
                elif mutation == "gateway_required":
                    describe["allOf"].append({"then": {"required": ["privacy_derivation"]}})
                else:
                    describe["additionalProperties"] = True
                self.assertTrue(self.run_gate(describe=describe))

    def test_legacy_claims_are_rejected_for_both_roles(self):
        for row in self.fixture["schema_validation_cases"]:
            with self.subTest(name=row["name"]):
                validator = gate.schema_validator(gate.DESCRIBE, "#")
                errors = list(validator.iter_errors(row["instance"]))
                self.assertEqual(not errors, row["expect_valid"])
                if not row["expect_valid"]:
                    self.assertTrue(any(error.validator == "additionalProperties" and "privacy_derivation" in error.message for error in errors))


if __name__ == "__main__":
    unittest.main()
