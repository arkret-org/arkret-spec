"""Mutation tests for the Event-preimage validity gate.

Hashing bytes and comparing the result is only half a known-answer vector. The
other half — that the hashed bytes are an Event any implementation could have
produced — went unchecked, and every preimage in the content-bound Event-ID
family drifted through the hole at once. Each mutation below is a state the
fixture was actually in before 0450, or the shape that let the two-step class C
exemption claim a match it did not have.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as lint_artifacts

FIXTURES = ROOT / "spec" / "v1" / "artifacts" / "fixtures"
CONTENT_BOUND = "content-bound-event-id-fixture.json"


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class EventPreimageValidityGateTest(unittest.TestCase):
    def _lint_mutated_fixture(self, mutate, check) -> list[str]:
        target = (FIXTURES / CONTENT_BOUND).resolve()
        original_load_json = lint_artifacts.load_json
        mutated = copy.deepcopy(original_load_json(lint_artifacts.Lint(), target))
        mutate(mutated)

        def load_json_with_mutation(lint, path):
            if path.resolve() == target:
                return mutated
            return original_load_json(lint, path)

        lint_artifacts.load_json = load_json_with_mutation
        try:
            lint = lint_artifacts.Lint()
            check(lint)
            return lint.errors
        finally:
            lint_artifacts.load_json = original_load_json

    @staticmethod
    def _case(fixture, name):
        for case in fixture["cases"]:
            if case.get("name") == name:
                return case
        raise AssertionError(f"missing case {name}")

    @classmethod
    def _patch_preimage(cls, fixture, name, patch):
        case = cls._case(fixture, name)
        envelope = json.loads(case["digest_preimage_canonical_bytes_utf8"])
        patch(envelope)
        case["digest_preimage_canonical_bytes_utf8"] = canonical_json(envelope)

    def _validity_errors(self, mutate) -> list[str]:
        return self._lint_mutated_fixture(
            mutate, lint_artifacts.check_stated_event_preimage_is_a_valid_event
        )

    def _fixture_errors(self, mutate) -> list[str]:
        return self._lint_mutated_fixture(
            mutate, lint_artifacts.check_content_bound_event_id_fixture
        )

    def test_unmutated_fixtures_pass(self) -> None:
        lint = lint_artifacts.Lint()
        lint_artifacts.check_stated_event_preimage_is_a_valid_event(lint)
        self.assertEqual(lint.errors, [])
        lint = lint_artifacts.Lint()
        lint_artifacts.check_content_bound_event_id_fixture(lint)
        self.assertEqual(lint.errors, [])

    def test_bare_principal_id_as_actor_id_fails(self) -> None:
        # Every preimage in this family carried `"actor_id": "ak:did_core:..."`
        # where the envelope requires the composite actor_id.
        def mutate(fixture):
            self._patch_preimage(
                fixture,
                "strand_object_id_is_retyped_event_id",
                lambda envelope: envelope.__setitem__(
                    "actor_id", "ak:did_core:webvh:z6mkfixture"
                ),
            )

        errors = self._validity_errors(mutate)
        self.assertTrue(
            any("$.actor_id" in error and "envelope rejects" in error for error in errors),
            errors,
        )

    def test_empty_refs_array_fails(self) -> None:
        # `"refs": []` violates the envelope minItems. The absent-vs-empty
        # distinction is exactly what encoding.md 6.0.2(a)(2) forbids collapsing.
        def mutate(fixture):
            self._patch_preimage(
                fixture,
                "strand_object_id_is_retyped_event_id",
                lambda envelope: envelope.__setitem__("refs", []),
            )

        errors = self._validity_errors(mutate)
        self.assertTrue(
            any("$.refs" in error for error in errors),
            errors,
        )

    def test_realm_genesis_carrying_schema_refs_fails(self) -> None:
        # The original 0450 finding: a closed realm-genesis object carrying a
        # `schema_refs` member the schema has no room for, holding a profile id.
        def mutate(fixture):
            self._patch_preimage(
                fixture,
                "agent_provision_forward_declaration_is_constructible",
                lambda envelope: envelope["payload"]["object"].__setitem__(
                    "schema_refs", ["ak.profile.principal_control_realm.v1"]
                ),
            )

        errors = self._validity_errors(mutate)
        self.assertTrue(
            any("schema_refs" in error for error in errors),
            errors,
        )

    def test_materialized_object_in_place_of_a_genesis_fails(self) -> None:
        # The collaboration vector hashed an `ak.schema.realm.v1` object, which
        # the create payload can never carry.
        def mutate(fixture):
            self._patch_preimage(
                fixture,
                "realm_genesis_id_is_derived_and_self_certifying",
                lambda envelope: envelope["payload"].__setitem__(
                    "object",
                    {
                        "schema": "ak.schema.realm.v1",
                        "title": "Vector Realm",
                        "trust_domain": "ak:trust_domain:did.webvh.alice.example",
                    },
                ),
            )

        errors = self._validity_errors(mutate)
        self.assertTrue(
            any("ak.realm.create" in error or "envelope rejects" in error for error in errors),
            errors,
        )

    def test_payload_id_in_did_form_fails(self) -> None:
        # `agent_id` is a did_core_id; the provision preimage carried the DID.
        def mutate(fixture):
            self._patch_preimage(
                fixture,
                "agent_provision_declares_the_frozen_genesis_realm_id",
                lambda envelope: envelope["payload"].__setitem__(
                    "agent_id", "did:webvh:z6mkagent:agent.example"
                ),
            )

        errors = self._validity_errors(mutate)
        self.assertTrue(
            any("agent_id" in error for error in errors),
            errors,
        )

    def test_preimage_for_an_unregistered_kind_fails(self) -> None:
        def mutate(fixture):
            self._patch_preimage(
                fixture,
                "strand_object_id_is_retyped_event_id",
                lambda envelope: envelope.__setitem__("kind", "ak.not.a.registered.kind"),
            )

        errors = self._validity_errors(mutate)
        self.assertTrue(
            any("no payload_schema_ref" in error for error in errors),
            errors,
        )

    def test_declaration_naming_a_different_realm_fails(self) -> None:
        # 914279c0 recomputed step 1 and left step 2 declaring the previous
        # realm id; both halves stayed internally consistent, so every digest
        # check kept passing while the pair proved nothing.
        def mutate(fixture):
            case = self._case(
                fixture, "agent_provision_declares_the_frozen_genesis_realm_id"
            )
            case["declared_principal_control_realm_id"] = "ak:realm:" + "A" * 44

        errors = self._fixture_errors(mutate)
        self.assertTrue(
            any("but step 1 derives" in error for error in errors),
            errors,
        )

    def test_hashed_declaration_diverging_from_the_declared_one_fails(self) -> None:
        def mutate(fixture):
            self._patch_preimage(
                fixture,
                "agent_provision_declares_the_frozen_genesis_realm_id",
                lambda envelope: envelope["payload"].__setitem__(
                    "principal_control_realm_id", "ak:realm:" + "B" * 44
                ),
            )

        errors = self._fixture_errors(mutate)
        self.assertTrue(
            any("declared value and the hashed value" in error for error in errors),
            errors,
        )

    def test_dropping_the_cross_step_assertion_fails(self) -> None:
        def mutate(fixture):
            case = self._case(
                fixture, "agent_provision_declares_the_frozen_genesis_realm_id"
            )
            case["expected"].pop("declaration_equals_step_1_derived_realm_id")

        errors = self._fixture_errors(mutate)
        self.assertTrue(
            any("the exemption has no vector" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
