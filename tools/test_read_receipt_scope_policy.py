"""Mutation regressions for the scope-local receipt policy release gate."""

import copy
import json
import unittest
from unittest.mock import patch

from tools.artifact_lint import read_receipt_scope_policy as contract
from tools.artifact_lint.core import ARTIFACTS, Lint


class ScopeReadReceiptPolicyTest(unittest.TestCase):
    def setUp(self):
        self.documents = {
            path: json.loads(path.read_text(encoding="utf-8"))
            for path in [contract.FIXTURE, ARTIFACTS / "registry/contract-registry.json",
                         ARTIFACTS / "schemas/event-envelope.schema.json"]
        }

    def run_gate(self):
        lint = Lint()
        with patch.object(contract, "load_json", side_effect=lambda _, path: self.documents[path]):
            contract.check_read_receipt_scope_policy(lint)
        return lint.errors

    def writer(self):
        return next(row for row in self.documents[ARTIFACTS / "registry/contract-registry.json"]
                    ["event_kind_registry"]["event_kinds"] if row["event_kind"] == contract.KIND)

    def test_canonical_vectors_execute(self):
        self.assertEqual(self.run_gate(), [])

    def test_missing_scope_subject_is_rejected(self):
        self.writer()["result_writes"][0]["result_selector"] = None
        self.assertTrue(self.run_gate())

    def test_payload_merge_is_rejected(self):
        self.writer()["result_writes"][0]["result_projection"]["kind"] = "merge"
        self.assertTrue(self.run_gate())

    def test_second_writer_is_rejected(self):
        catalog = self.documents[ARTIFACTS / "registry/contract-registry.json"]
        duplicate = copy.deepcopy(self.writer())
        duplicate["event_kind"] = "ak.circle.read_receipt_policy"
        catalog["event_kind_registry"]["event_kinds"].append(duplicate)
        self.assertTrue(self.run_gate())

    def test_parent_fallback_expectation_is_rejected(self):
        fixture = self.documents[contract.FIXTURE]
        row = next(row for row in fixture["decision_cases"]
                   if row["name"] == "realm_disabled_does_not_disable_circle")
        row["expected"] = {"send": False, "display": False}
        self.assertTrue(self.run_gate())

    def test_missing_current_cannot_be_reclassified_as_absence(self):
        fixture = self.documents[contract.FIXTURE]
        row = next(row for row in fixture["decision_cases"] if row["name"] == "missing_current")
        row["expected"] = {"send": True, "display": True}
        self.assertTrue(self.run_gate())

    def test_broader_event_scope_union_is_rejected(self):
        envelope = self.documents[ARTIFACTS / "schemas/event-envelope.schema.json"]
        branch = next(row for row in envelope["allOf"]
                      if row.get("if", {}).get("properties", {}).get("kind", {}).get("const") == contract.KIND)
        branch["then"]["properties"]["scope_ref"] = {"$ref": "#/$defs/scope_ref"}
        self.assertTrue(self.run_gate())


if __name__ == "__main__":
    unittest.main()
