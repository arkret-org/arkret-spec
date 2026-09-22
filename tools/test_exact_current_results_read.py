import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
SCHEMA = ARTIFACTS / "schemas" / "exact-current-results-read.schema.json"
FIXTURE = ARTIFACTS / "fixtures" / "exact-current-results-read-fixture.json"
REGISTRY = ARTIFACTS / "registry" / "contract-registry.json"


class ExactCurrentResultsReadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(
            cls.schema,
            resolver=RefResolver(base_uri=SCHEMA.as_uri(), referrer=cls.schema),
        )

    def validate_fragment(self, fragment, value):
        definition = self.schema["$defs"][fragment]
        validator = Draft202012Validator(
            definition,
            resolver=RefResolver(base_uri=SCHEMA.as_uri(), referrer=self.schema),
        )
        self.assertEqual([], list(validator.iter_errors(value)))

    def test_request_and_outcomes_match_closed_schema(self):
        self.validate_fragment("exact_current_results_read_request", self.fixture["request"])
        for case in self.fixture["valid_outcomes"]:
            self.validate_fragment("exact_current_results_read_outcome", case["value"])

    def test_selector_union_rejects_unknown_kind_and_extra_fields(self):
        request = json.loads(json.dumps(self.fixture["request"]))
        request["selector"]["kind"] = "strand"
        definition = self.schema["$defs"]["exact_current_results_read_request"]
        validator = Draft202012Validator(
            definition,
            resolver=RefResolver(base_uri=SCHEMA.as_uri(), referrer=self.schema),
        )
        self.assertTrue(list(validator.iter_errors(request)))

        request = json.loads(json.dumps(self.fixture["request"]))
        request["expected_revision"] = None
        self.assertTrue(list(validator.iter_errors(request)))

    def test_moderation_never_written_is_not_a_schema_outcome(self):
        definition = self.schema["$defs"]["exact_current_results_read_outcome"]
        validator = Draft202012Validator(
            definition,
            resolver=RefResolver(base_uri=SCHEMA.as_uri(), referrer=self.schema),
        )
        for case in self.fixture["schema_validation_cases"]:
            self.assertTrue(
                list(validator.iter_errors(case["instance"])),
                msg=f'{case["name"]} unexpectedly matched the outcome schema',
            )

    def test_operation_is_closed_and_read_only(self):
        operation = next(
            row
            for row in self.registry["operation_registry"]["operations"]
            if row["operation_id"] == "ak.self.current_results.read.exact.v1"
        )
        self.assertEqual(
            "schemas/exact-current-results-read.schema.json#/$defs/exact_current_results_read_request",
            operation["request_schema_ref"],
        )
        self.assertEqual(
            "schemas/exact-current-results-read.schema.json#/$defs/exact_current_results_read_outcome",
            operation["response_schema_ref"],
        )
        self.assertEqual("none", operation["durable_effect"]["kind"])


if __name__ == "__main__":
    unittest.main()
