"""Mutation tests for the naming gate.

These guard the three properties the naming gate exists to establish: the walker
reaches every declared property (including inside ``$defs``), exceptions and
debt are keyed by exact path rather than by bare name, and registered cases are
actually executed by the predicates they claim to cover.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.core import (
    ARTIFACTS,
    Lint,
    NAMING_DEBT_PATH,
    NAMING_RULES_PATH,
    parse_json_file,
    parse_yaml_file,
    read_text,
)
from tools.artifact_lint.naming import (
    DEFAULT_REJECTED_WRAPPER_WORDS,
    PREDICATES,
    enumerate_schema_properties,
    naive_property_occurrences,
    naive_property_population,
    stacked_wrapper_words,
    unregistered_wrapper_word,
)
from tools.artifact_lint.prose import check_naming_predicates

SCHEMA_DIR = ARTIFACTS / "schemas"


def schema_documents():
    for path in sorted(SCHEMA_DIR.glob("*.json")):
        yield path.name, json.loads(path.read_text(encoding="utf-8"))


def drop_reader_caches() -> None:
    """The lint memoises file reads for a single run; mutation tests need fresh ones."""

    read_text.cache_clear()
    parse_json_file.cache_clear()
    parse_yaml_file.cache_clear()


def run_gate() -> Lint:
    drop_reader_caches()
    lint = Lint()
    check_naming_predicates(lint)
    return lint


class MutationHarness(unittest.TestCase):
    def lint_with_file(self, path: Path, mutate) -> list[str]:
        """Apply a mutation, run the gate, always restore the original bytes."""

        original = path.read_bytes()
        document = json.loads(original.decode("utf-8"))
        mutate(document)
        try:
            path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            return run_gate().errors
        finally:
            path.write_bytes(original)
            drop_reader_caches()


class NamingGateBaselineTest(unittest.TestCase):
    def test_gate_is_green(self) -> None:
        lint = run_gate()
        self.assertEqual(lint.errors, [])
        self.assertEqual(lint.warnings, [])

    def test_every_rule_declares_enforcement(self) -> None:
        rules = json.loads(NAMING_RULES_PATH.read_text(encoding="utf-8"))
        for rule in rules["rules"]:
            self.assertIn(
                rule.get("enforcement"),
                {"predicate", "registry", "predicate+registry"},
                rule["rule_id"],
            )

    def test_exception_anchors_resolve(self) -> None:
        rules = json.loads(NAMING_RULES_PATH.read_text(encoding="utf-8"))
        for rule in rules["rules"]:
            for exception in rule.get("exceptions", []):
                self.assertTrue(
                    (ROOT / exception["anchor"]).exists(),
                    f"{rule['rule_id']} {exception['id']} anchors a missing path",
                )


class WalkerCoverageTest(unittest.TestCase):
    def test_walker_reaches_every_declared_property(self) -> None:
        for file_name, document in schema_documents():
            reached = {
                (occurrence.pointer, occurrence.name)
                for occurrence in enumerate_schema_properties(file_name, document)
            }
            self.assertEqual(
                naive_property_occurrences(document),
                reached,
                f"{file_name} lost or invented occurrence paths",
            )
            self.assertEqual(
                naive_property_population(document) - {name for _pointer, name in reached},
                set(),
                f"{file_name} lost coverage",
            )

    def test_occurrence_coverage_keeps_duplicate_names_distinct(self) -> None:
        document = {
            "allOf": [
                {"properties": {"state": {"type": "string"}}},
                {"properties": {"state": {"type": "integer"}}},
            ]
        }
        self.assertEqual(
            naive_property_occurrences(document),
            {
                ("/allOf/0/properties/state", "state"),
                ("/allOf/1/properties/state", "state"),
            },
        )

    def test_walker_descends_into_defs(self) -> None:
        document = {
            "$defs": {
                "wrapper": {
                    "properties": {
                        "nested_object": {
                            "properties": {"require_consent": {"type": "boolean"}}
                        }
                    }
                }
            }
        }
        pointers = {o.pointer for o in enumerate_schema_properties("t.json", document)}
        self.assertIn(
            "/$defs/wrapper/properties/nested_object/properties/require_consent", pointers
        )

    def test_walker_visits_each_property_once(self) -> None:
        for file_name, document in schema_documents():
            pointers = [o.pointer for o in enumerate_schema_properties(file_name, document)]
            self.assertEqual(len(pointers), len(set(pointers)), f"{file_name} duplicates")

    def test_walker_does_not_invent_paths_through_name_maps(self) -> None:
        document = {"properties": {"properties": {"type": "string"}}}
        pointers = {o.pointer for o in enumerate_schema_properties("t.json", document)}
        self.assertEqual(pointers, {"/properties/properties"})


class RegisteredCaseTest(MutationHarness):
    def test_registered_cases_agree_with_predicates(self) -> None:
        rules = json.loads(NAMING_RULES_PATH.read_text(encoding="utf-8"))
        for field in ("negative_cases", "positive_cases"):
            self.assertTrue(rules[field], f"{field} must not be empty")
            for case in rules[field]:
                predicate = PREDICATES[case["rule_id"]]
                self.assertIs(
                    predicate(case["candidate"]),
                    case["expected"] == "reject",
                    case,
                )

    def test_every_predicate_has_both_polarities(self) -> None:
        rules = json.loads(NAMING_RULES_PATH.read_text(encoding="utf-8"))
        for field in ("negative_cases", "positive_cases"):
            covered = {case["rule_id"] for case in rules[field]}
            self.assertEqual(covered, set(PREDICATES), field)

    def test_mutating_a_case_fails_the_gate(self) -> None:
        def mutate(document):
            document["negative_cases"].append(
                {"rule_id": "NC-BOOL-001", "candidate": "consent_required", "expected": "reject"}
            )

        errors = self.lint_with_file(NAMING_RULES_PATH, mutate)
        self.assertTrue(
            any("predicate disagrees with registered case" in error for error in errors), errors
        )

    def test_dropping_a_predicate_case_fails_the_gate(self) -> None:
        def mutate(document):
            document["negative_cases"] = [
                case for case in document["negative_cases"] if case["rule_id"] != "NC-HASH-001"
            ]
            document["positive_cases"] = [
                case for case in document["positive_cases"] if case["rule_id"] != "NC-HASH-001"
            ]

        errors = self.lint_with_file(NAMING_RULES_PATH, mutate)
        self.assertTrue(any("every predicate needs executed cases" in e for e in errors), errors)

    def test_rotten_exception_anchor_fails_the_gate(self) -> None:
        def mutate(document):
            document["rules"][0]["exceptions"][0]["anchor"] = "spec/v1/artifacts/schemas/gone.json"

        errors = self.lint_with_file(NAMING_RULES_PATH, mutate)
        self.assertTrue(any("no longer exists" in error for error in errors), errors)

    def test_ref_indirect_boolean_and_array_violations_fail_the_gate(self) -> None:
        def mutate(document):
            definitions = document.setdefault("$defs", {})
            definitions["review_boolean"] = {"type": "boolean"}
            definitions["review_array"] = {"type": "array", "items": {"type": "string"}}
            properties = document.setdefault("properties", {})
            properties["require_review"] = {"$ref": "#/$defs/review_boolean"}
            properties["blocked_reviews"] = {"$ref": "#/$defs/review_array"}
            properties["blocked_external_reviews"] = {
                "$ref": "./account-operations.schema.json#/$defs/device_summaries"
            }

        errors = self.lint_with_file(
            SCHEMA_DIR / "event-payload.schema.json",
            mutate,
        )
        self.assertTrue(any("require_review" in error and "NC-BOOL-001" in error for error in errors))
        self.assertTrue(any("blocked_reviews" in error and "NC-SET-001" in error for error in errors))
        self.assertTrue(
            any("blocked_external_reviews" in error and "NC-SET-001" in error for error in errors)
        )


class DebtBaselineTest(MutationHarness):
    def first_entry(self) -> dict:
        debt = json.loads(NAMING_DEBT_PATH.read_text(encoding="utf-8"))
        if not debt["entries"]:
            self.skipTest("debt baseline is empty; the ledger has reached closure")
        return debt["entries"][0]

    def test_debt_is_internal_and_owned(self) -> None:
        debt = json.loads(NAMING_DEBT_PATH.read_text(encoding="utf-8"))
        self.assertIs(debt["source_of_truth"], False)
        for entry in debt["entries"]:
            self.assertIn(entry["rule_id"], PREDICATES)
            self.assertTrue(entry["owner_batch"], entry)
            self.assertTrue(entry["reason"], entry)
            self.assertTrue(entry["pointer"].startswith("/"), entry)
            # Internal debt must never masquerade as an external-standard grant.
            self.assertNotIn("external_anchor", entry)
            self.assertNotEqual(entry.get("basis"), "external_literal")

    def test_unregistered_violation_fails_the_gate(self) -> None:
        # Data-driven: each batch drains the ledger, so pin to whatever row is
        # currently first rather than to a name that a later batch will delete.
        victim = self.first_entry()

        def mutate(document):
            document["entries"] = [
                entry
                for entry in document["entries"]
                if not (
                    entry["file"] == victim["file"] and entry["pointer"] == victim["pointer"]
                )
            ]

        errors = self.lint_with_file(NAMING_DEBT_PATH, mutate)
        self.assertTrue(any(victim["pointer"] in error for error in errors), errors)

    def test_stale_debt_fails_the_gate(self) -> None:
        def mutate(document):
            document["entries"].append(
                {
                    "rule_id": "NC-BOOL-001",
                    "file": "event-payload.schema.json",
                    "pointer": "/$defs/no_such_payload/properties/require_nothing",
                    "name": "require_nothing",
                    "reason": "deliberately stale",
                    "owner_batch": "batch-2-mechanical-renames",
                }
            )

        errors = self.lint_with_file(NAMING_DEBT_PATH, mutate)
        self.assertTrue(any("no longer match a violation" in error for error in errors), errors)

    def test_debt_does_not_leak_across_paths(self) -> None:
        """Relief is granted at the registered pointer only, never by name."""

        victim = self.first_entry()

        def mutate(document):
            for entry in document["entries"]:
                if entry["file"] == victim["file"] and entry["pointer"] == victim["pointer"]:
                    entry["pointer"] = "/$defs/moved_elsewhere/properties/" + entry["name"]

        errors = self.lint_with_file(NAMING_DEBT_PATH, mutate)
        self.assertTrue(
            any(victim["pointer"] in error and victim["name"] in error for error in errors),
            errors,
        )

    # Shape rules are validated while the debt index is built, before any
    # violation matching, so these inject a synthetic row instead of editing a
    # real one. That keeps them meaningful once the ledger reaches closure.
    SYNTHETIC = {
        "rule_id": "NC-BOOL-001",
        "file": "event-payload.schema.json",
        "pointer": "/$defs/synthetic_payload/properties/require_something",
        "name": "require_something",
        "reason": "synthetic row for the shape mutation tests",
        "owner_batch": "batch-test",
    }

    def test_debt_claiming_an_external_anchor_fails_the_gate(self) -> None:
        def mutate(document):
            document["entries"].append(dict(self.SYNTHETIC, external_anchor="RFC 9420"))

        errors = self.lint_with_file(NAMING_DEBT_PATH, mutate)
        self.assertTrue(any("must not claim an external anchor" in e for e in errors), errors)

    def test_debt_without_owner_fails_the_gate(self) -> None:
        def mutate(document):
            document["entries"].append(dict(self.SYNTHETIC, owner_batch=""))

        errors = self.lint_with_file(NAMING_DEBT_PATH, mutate)
        self.assertTrue(any("needs owner_batch and reason" in e for e in errors), errors)

    def test_empty_ledger_is_the_closure_state(self) -> None:
        """Batches 2 and 3 drained the ledger; closure means it stays empty."""

        debt = json.loads(NAMING_DEBT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(debt["entries"], [], "debt must be empty once all batches close")


class WrapperWordTest(unittest.TestCase):
    def test_stacked_wrapper_words_only_flags_repetition(self) -> None:
        self.assertEqual(stacked_wrapper_words("InviteDeliveryRequestBodyBody"), "BodyBody")
        self.assertEqual(stacked_wrapper_words("EventsSubmitOutcomeOutcome"), "OutcomeOutcome")
        # An operation verb followed by a wrapper word is legitimate.
        self.assertIsNone(stacked_wrapper_words("IdentityLogListOutcome"))
        self.assertIsNone(stacked_wrapper_words("InviteDeliveryRequestBody"))

    def test_rejected_wrapper_words_are_registry_driven(self) -> None:
        rules = json.loads(NAMING_RULES_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            tuple(rules["rejected_wrapper_words"]), DEFAULT_REJECTED_WRAPPER_WORDS
        )
        self.assertEqual(
            unregistered_wrapper_word("RelationConflictCandidate", DEFAULT_REJECTED_WRAPPER_WORDS),
            "Candidate",
        )
        self.assertIsNone(
            unregistered_wrapper_word("EventsSubmitOutcome", DEFAULT_REJECTED_WRAPPER_WORDS)
        )


if __name__ == "__main__":
    unittest.main()
