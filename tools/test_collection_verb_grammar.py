"""Operation verbs in object arrays require their exact registered owner."""
from tools.artifact_lint.naming_contracts import (
    COLLECTION_NAMING_REGISTRY_PATH,
    check_collection_field_contracts,
)
from tools.test_naming_gate_lint import MutationHarness, run_check


class CollectionVerbGrammarTests(MutationHarness):
    def test_registered_operation_grammar_is_closed(self):
        self.assertEqual(run_check(check_collection_field_contracts).errors, [])

    def test_each_operation_verb_needs_its_exact_exception(self):
        for member in ("supersedes", "replaces"):
            def mutate(document):
                document["exact_exceptions"] = [
                    row for row in document["exact_exceptions"]
                    if not row["pointer"].endswith("/properties/" + member)
                ]
            errors = self.lint_with_file(
                COLLECTION_NAMING_REGISTRY_PATH, mutate,
                check=check_collection_field_contracts,
            )
            self.assertTrue(any("NC-COLLECTION-001" in error and member in error for error in errors), errors)
