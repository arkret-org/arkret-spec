import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


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
        cls.schema_store = {}
        for path in (ARTIFACTS / "schemas").glob("*.json"):
            schema = json.loads(path.read_text(encoding="utf-8"))
            cls.schema_store[path.as_uri()] = schema
            if "$id" in schema:
                cls.schema_store[schema["$id"]] = schema
        cls.resource_registry = Registry().with_resources((key, Resource.from_contents(value)) for key, value in cls.schema_store.items())
        cls.validator = Draft202012Validator(
            cls.schema,
            registry=cls.resource_registry,
        )

    def validate_fragment(self, fragment, value):
        definition = {"$ref": self.schema["$id"] + "#/$defs/" + fragment}
        validator = Draft202012Validator(
            definition,
            registry=self.resource_registry,
        )
        self.assertEqual([], list(validator.iter_errors(value)))

    def test_request_and_outcomes_match_closed_schema(self):
        self.validate_fragment("exact_current_results_read_request", self.fixture["request"])
        for case in self.fixture["valid_outcomes"]:
            self.validate_fragment("exact_current_results_read_outcome", case["value"])

    def test_selector_union_rejects_unknown_kind_and_extra_fields(self):
        request = json.loads(json.dumps(self.fixture["request"]))
        request["selector"]["kind"] = "strand"
        definition = {"$ref": self.schema["$id"] + "#/$defs/exact_current_results_read_request"}
        validator = Draft202012Validator(
            definition,
            registry=self.resource_registry,
        )
        self.assertTrue(list(validator.iter_errors(request)))

        request = json.loads(json.dumps(self.fixture["request"]))
        request["expected_revision"] = None
        self.assertTrue(list(validator.iter_errors(request)))

    def test_moderation_never_written_is_not_a_schema_outcome(self):
        definition = {"$ref": self.schema["$id"] + "#/$defs/exact_current_results_read_outcome"}
        validator = Draft202012Validator(
            definition,
            registry=self.resource_registry,
        )
        negative = next(case for case in self.fixture["schema_validation_cases"] if case["name"] == "moderation_never_written_is_not_a_schema_outcome")
        self.assertTrue(list(validator.iter_errors(negative["instance"])))

    def test_all_schema_vectors_respect_their_declared_fragment(self):
        for case in self.fixture["schema_validation_cases"]:
            fragment = case["schema_ref"].split("#/$defs/")[1]
            validator = Draft202012Validator({"$ref": self.schema["$id"] + "#/$defs/" + fragment}, registry=self.resource_registry)
            self.assertEqual(case["expect_valid"], not list(validator.iter_errors(case["instance"])), case["name"])

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

    def test_relation_is_a_closed_snapshot_current_carrier(self):
        path = ARTIFACTS / "schemas" / "realm-state-snapshot.schema.json"
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(
            {"$ref": snapshot["$id"] + "#/properties/current_state_entries"},
            registry=self.resource_registry,
        )
        entry = next(
            case["value"]["entry"] for case in self.fixture["valid_outcomes"]
            if case["name"] == "authorized_relation_present_snapshot_carrier"
        )
        self.assertEqual([], list(validator.iter_errors([entry])))
        mutations = [
            lambda row: row["selector"].update(kind="unknown"),
            lambda row: row["selector"]["primary_conflict_domain"].update(scope_circle_id=None),
            lambda row: row["selector"].pop("primary_conflict_domain"),
            lambda row: row["value"].update(to_ref="ak:did_core:web:alice.example"),
            lambda row: row.pop("source_stream_ref"),
        ]
        for mutate in mutations:
            invalid = json.loads(json.dumps(entry))
            mutate(invalid)
            self.assertTrue(list(validator.iter_errors([invalid])))


if __name__ == "__main__":
    unittest.main()
