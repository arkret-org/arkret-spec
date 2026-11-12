"""Classification examples must resolve to the exact observed identifier role."""
from __future__ import annotations

import json

from tools.artifact_lint.naming_contracts import (
    IDENTIFIER_CLASSIFICATION_PATH,
    check_identifier_value_categories,
)
from tools.test_naming_gate_lint import MutationHarness, run_check


class IdentifierClassificationExampleTests(MutationHarness):
    def check_registry(self, mutate):
        return self.lint_with_file(
            IDENTIFIER_CLASSIFICATION_PATH, mutate,
            check=check_identifier_value_categories,
        )

    def test_current_examples_match_observed_fields(self):
        self.assertEqual(run_check(check_identifier_value_categories).errors, [])

    def test_removed_schema_owner_is_not_an_example(self):
        def mutate(document):
            document["classifications"][0]["example_path"] = "event-payload.schema.json#/$defs/removed_payload/properties/action_id"
        errors = self.check_registry(mutate)
        self.assertTrue(any("example_path must name an actual observed occurrence" in e for e in errors), errors)

    def test_an_existing_different_field_cannot_supply_the_example(self):
        def mutate(document):
            first = document["classifications"][0]
            other = next(row for row in document["classifications"] if row["name"] != first["name"])
            first["example_path"] = other["example_path"]
        errors = self.check_registry(mutate)
        self.assertTrue(any("same property name and terminal signature" in e for e in errors), errors)

    def test_missing_example_cannot_claim_inventory_closure(self):
        def mutate(document):
            document["classifications"][0].pop("example_path")
        errors = self.check_registry(mutate)
        self.assertTrue(any("example_path must name an actual observed occurrence" in e for e in errors), errors)
