"""Pin the MLS proof advertisement requirement to registered bundle members."""

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ARTIFACTS = Path(__file__).resolve().parents[1] / "spec/v1/artifacts"


class MlsProofDescribeLimitTest(unittest.TestCase):
    def test_bundle_trigger_matches_registry_and_rejects_missing_limit(self):
        schema = json.loads((ARTIFACTS / "schemas/service-describe.schema.json").read_text(encoding="utf-8"))
        registry = json.loads((ARTIFACTS / "registry/contract-registry.json").read_text(encoding="utf-8"))
        bundles = {
            bundle["operation_bundle_id"]
            for bundle in registry["operation_registry"]["operation_bundles"]
            if any(member["operation_id"] == "ak.self.seals.read.mls_governance_proof.v1" for member in bundle["members"])
        }
        rules = [rule for rule in schema["allOf"]
                 if "mls_governance_proof" in rule.get("then", {}).get("properties", {}).get("limits", {}).get("required", [])]
        self.assertEqual(len(rules), 1)
        self.assertEqual(bundles, {rules[0]["if"]["properties"]["supported_operation_bundles"]["contains"]["const"]})
        validator = Draft202012Validator({"properties": {"limits": schema["properties"]["limits"]}, "allOf": rules})
        base = {"supported_operation_bundles": sorted(bundles)}
        self.assertFalse(validator.is_valid(base))
        self.assertFalse(validator.is_valid({**base, "limits": {}}))
        for limit in [1048575, 1048576, 1048577]:
            value = {**base, "limits": {"mls_governance_proof": {"max_exact_response_bytes": limit}, "storage": "memory"}}
            self.assertEqual(validator.is_valid(value), limit == 1048576)
        self.assertFalse(validator.is_valid({**base, "limits": {"mls_governance_proof": {"max_exact_response_bytes": 1048576, "cursor": "old"}}}))
        self.assertTrue(validator.is_valid({"supported_operation_bundles": ["ak.operation_bundle.station.describe.v1"], "limits": {}}))


if __name__ == "__main__":
    unittest.main()
