"""Mutation tests for the two human Principal Control Realm admission branches.

A human ``ak.realm.create`` used to be routed by a ``did_inception`` reference
whose closed union made the reference name an immutable Event, while the only
DID inception material is method-native and is never an Arkret Event. The branch
was therefore unsatisfiable, and its sibling delegated branch was distinguished
by that same reference count. The branches are now split on the presence of the
executor pair, so these tests read the canonical selector out of
contract-registry.json and prove the split over every pair combination instead of
restating the admission rules a second time.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.event_admission_contract import predicate_schema, selected_branches

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
EXECUTOR_PAIR = ("executed_by", "authorization_ref")

# The executor pair members are typed: executed_by is the composite actor_id and
# authorization_ref is one of the closed authority references. The selector only
# looks at presence, so it accepted placeholder strings here for as long as these
# tests existed -- including a bare "ak:actor:..." spelling that no schema in the
# repository defines. Presence tests that use values the wire would reject cannot
# tell a routing bug from a shape bug, so both members are the same values the
# fixture admits, and the identity is asserted below rather than assumed.
CONSTRUCTIVE_FIXTURE = "fixtures/content-bound-event-id-fixture.json"
DELEGATED_CASE = "organization_governed_pcr_genesis_derives_a_distinct_realm"
SELF_CASE = (
    "principal_control_realm_id_is_event_derived_and_nonzero_nibble_rejected"
)
MATRIX_CASE = (
    "human_pcr_admission_selection_is_exclusive_over_the_executor_pair"
)


def load(relative: str) -> dict:
    return json.loads((ARTIFACTS / relative).read_text(encoding="utf-8"))


def schema_registry() -> Registry:
    resources = []
    for path in sorted((ARTIFACTS / "schemas").glob("*.schema.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        schema_id = document.get("$id")
        if isinstance(schema_id, str):
            resources.append((schema_id, Resource.from_contents(document)))
    return Registry().with_resources(resources)


class HumanPcrAdmissionSelectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load("registry/contract-registry.json")["event_kind_registry"]
        cls.envelope = load("schemas/event-envelope.schema.json")
        row = next(
            event
            for event in cls.registry["event_kinds"]
            if event["event_kind"] == "ak.realm.create"
        )
        cls.branches = [
            (admission, Draft202012Validator(guard))
            for admission, guard in selected_branches(row)
        ]

    def select(self, instance: dict) -> str:
        matched = [
            admission
            for admission, validator in self.branches
            if validator.is_valid(instance)
        ]
        self.assertEqual(len(matched), 1, f"{instance!r} selected {matched!r}")
        return matched[0]

    @classmethod
    def case(cls, name: str) -> dict:
        fixture = load(CONSTRUCTIVE_FIXTURE)
        return next(case for case in fixture["cases"] if case.get("name") == name)

    def human_create(self, **members: object) -> dict:
        instance = {"kind": "ak.realm.create", "payload": {"object": {"purpose": "principal_control"}}}
        instance.update(members)
        return instance

    def executor_pair(self) -> dict:
        delegated = self.case(DELEGATED_CASE)["complete_wire_event"]
        return {member: delegated[member] for member in EXECUTOR_PAIR}

    def test_executor_pair_absence_selects_the_self_principal_branch(self) -> None:
        self.assertEqual(self.select(self.human_create()), "registration_anchor")

    def test_executor_pair_presence_selects_the_delegated_branch(self) -> None:
        instance = self.human_create(**self.executor_pair())
        self.assertEqual(self.select(instance), "delegated_pcr_genesis")

    def test_the_pair_members_are_the_shapes_the_envelope_schema_accepts(self) -> None:
        # A presence selector cannot notice a malformed member, so the values used
        # here have to be checked against the closed envelope somewhere or the test
        # suite silently documents a wire form that does not exist.
        envelope = Draft202012Validator(
            self.envelope, registry=schema_registry()
        )
        for name in (SELF_CASE, DELEGATED_CASE):
            with self.subTest(case=name):
                event = self.case(name)["complete_wire_event"]
                self.assertEqual(
                    [error.message for error in envelope.iter_errors(event)], []
                )

    def test_each_complete_event_selects_exactly_its_declared_branch(self) -> None:
        for name in (SELF_CASE, DELEGATED_CASE):
            with self.subTest(case=name):
                case = self.case(name)
                self.assertEqual(self.select(case["complete_wire_event"]), case["admission"])

    def test_a_partial_executor_pair_is_denied_with_no_fallback(self) -> None:
        pair = self.executor_pair()
        for member in EXECUTOR_PAIR:
            with self.subTest(member=member):
                self.assertEqual(
                    self.select(self.human_create(**{member: pair[member]})), "deny"
                )

    def test_a_null_executor_member_counts_as_present(self) -> None:
        for member in EXECUTOR_PAIR:
            with self.subTest(member=member):
                self.assertEqual(self.select(self.human_create(**{member: None})), "deny")
        both_null = self.human_create(executed_by=None, authorization_ref=None)
        self.assertEqual(self.select(both_null), "delegated_pcr_genesis")

    def test_the_two_human_branches_never_overlap(self) -> None:
        # selected_branches() builds every guard as predicate_i AND NOT(any other
        # predicate), so two guards can never both accept one instance and
        # intersecting them is a tautology that passes even if two variants are
        # written to match the same Event. Overlap is only observable on the
        # unguarded `when` predicates.
        row = next(
            event
            for event in self.registry["event_kinds"]
            if event["event_kind"] == "ak.realm.create"
        )
        guards = {admission for admission, _ in self.branches}
        self.assertIn("registration_anchor", guards)
        self.assertIn("delegated_pcr_genesis", guards)
        predicates = [
            (variant["admission"], Draft202012Validator(predicate_schema(variant["when"])))
            for variant in row["admission_variants"][:-1]
        ]
        pair = self.executor_pair()
        for present in ([], ["executed_by"], ["authorization_ref"], list(EXECUTOR_PAIR)):
            instance = self.human_create(**{member: pair[member] for member in present})
            accepting = [
                admission for admission, validator in predicates if validator.is_valid(instance)
            ]
            with self.subTest(present=present):
                self.assertLessEqual(
                    len(accepting),
                    1,
                    f"unguarded admission predicates {accepting} all accept {instance!r}",
                )

    def test_the_guard_subtraction_is_what_makes_guards_disjoint(self) -> None:
        # Pins the reason the test above cannot use the guards. If selected_branches()
        # ever stops subtracting the sibling predicates, this fails and the overlap
        # test above becomes the only thing standing between two variants and a
        # silent double match.
        row = next(
            event
            for event in self.registry["event_kinds"]
            if event["event_kind"] == "ak.realm.create"
        )
        guard = dict(selected_branches(row))["registration_anchor"]
        self.assertIn("not", json.dumps(guard))

    def test_the_retired_inception_role_no_longer_routes_or_validates(self) -> None:
        union = self.envelope["$defs"]["semantic_ref"]["anyOf"]
        roles = union[1]["properties"]["role"]["enum"]
        self.assertNotIn("did_inception", roles)
        self.assertNotIn("did_inception", json.dumps(self.registry["admission_class_definitions"]))
        ref_validator = Draft202012Validator(
            {"$ref": "https://arkret.org/v1/schemas/event-envelope.schema.json#/$defs/semantic_ref"},
            registry=schema_registry(),
        )
        for critical in (True, False):
            reference = {
                "id": "ak:event:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "role": "did_inception",
                "critical": critical,
            }
            with self.subTest(critical=critical):
                self.assertFalse(ref_validator.is_valid(reference))
                self.assertEqual(self.select(self.human_create(refs=[reference])), "registration_anchor")

    def test_the_registry_declares_exactly_the_selectors_the_projection_supports(self) -> None:
        declared = set(self.registry["admission_predicate_contract"]["non_otherwise_selectors"])
        self.assertIn("top_level_fields_absent", declared)
        for selector in declared:
            with self.subTest(selector=selector):
                try:
                    predicate_schema({selector: self.sample_value(selector)})
                except ValueError as error:
                    self.assertNotIn("unknown admission selector", str(error))
        with self.assertRaises(ValueError):
            predicate_schema({"top_level_fields_absent_extra": ["executed_by"]})

    def test_presence_and_absence_selectors_cannot_be_combined(self) -> None:
        with self.assertRaises(ValueError):
            predicate_schema(
                {
                    "payload_path": "object.purpose",
                    "const": "principal_control",
                    "top_level_fields_present": ["executed_by"],
                    "top_level_fields_absent": ["authorization_ref"],
                }
            )

    def test_absence_is_evaluated_member_by_member(self) -> None:
        guard = predicate_schema({"top_level_fields_absent": list(EXECUTOR_PAIR)})
        self.assertEqual(
            guard,
            {"allOf": [{"not": {"required": ["executed_by"]}}, {"not": {"required": ["authorization_ref"]}}]},
        )

    def lint_errors_with_registry_mutation(self, mutate) -> list[str]:
        from tools.artifact_lint import bindings, core

        event_path = ARTIFACTS / "registry" / "event-kind-registry.json"
        original_load_json = bindings.load_json

        def load_json_with_mutation(lint, path):
            document = original_load_json(lint, path)
            if Path(path).resolve() == event_path.resolve():
                document = json.loads(json.dumps(document))
                mutate(document)
            return document

        bindings.load_json = load_json_with_mutation
        try:
            lint = core.Lint()
            bindings.check_event_admission_coverage(lint)
            return lint.errors
        finally:
            bindings.load_json = original_load_json

    def test_a_selector_declared_but_not_validated_fails_the_gate(self) -> None:
        def mutate(registry: dict) -> None:
            registry["admission_predicate_contract"]["non_otherwise_selectors"]["ref_absent"] = {
                "value_shape": "string"
            }

        errors = self.lint_errors_with_registry_mutation(mutate)
        self.assertTrue(
            any("non_otherwise_selectors MUST be exactly the selector" in error for error in errors),
            errors,
        )

    def test_dropping_the_absence_selector_from_the_registry_fails_the_gate(self) -> None:
        def mutate(registry: dict) -> None:
            del registry["admission_predicate_contract"]["non_otherwise_selectors"]["top_level_fields_absent"]

        errors = self.lint_errors_with_registry_mutation(mutate)
        self.assertTrue(
            any("non_otherwise_selectors MUST be exactly the selector" in error for error in errors),
            errors,
        )

    def test_combining_both_field_selectors_in_one_variant_fails_the_gate(self) -> None:
        def mutate(registry: dict) -> None:
            row = next(event for event in registry["event_kinds"] if event["event_kind"] == "ak.realm.create")
            variant = next(v for v in row["admission_variants"] if v["admission"] == "registration_anchor")
            variant["when"]["top_level_fields_present"] = ["executed_by"]

        errors = self.lint_errors_with_registry_mutation(mutate)
        self.assertTrue(
            any("MUST NOT combine top_level_fields_present" in error for error in errors),
            errors,
        )

    def test_an_out_of_vocabulary_field_member_fails_the_gate(self) -> None:
        def mutate(registry: dict) -> None:
            row = next(event for event in registry["event_kinds"] if event["event_kind"] == "ak.realm.create")
            variant = next(v for v in row["admission_variants"] if v["admission"] == "registration_anchor")
            variant["when"]["top_level_fields_absent"] = ["executed_by", "applet_id"]

        errors = self.lint_errors_with_registry_mutation(mutate)
        self.assertTrue(
            any("top_level_fields_absent MUST be a non-empty unique subset" in error for error in errors),
            errors,
        )

    @staticmethod
    def sample_value(selector: str) -> object:
        return {
            "payload_path": "object.purpose",
            "const": "principal_control",
            "not_const": "agent_control",
            "ref_role": "attestation",
            "ref_critical": True,
            "ref_exact_count": 1,
            "top_level_fields_present": ["executed_by"],
            "top_level_fields_absent": ["executed_by"],
        }[selector]


if __name__ == "__main__":
    unittest.main()
