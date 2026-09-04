"""Mutation tests for the pre_state_requirements grammar.

zh/models/event-and-patch.md section 2.4.2 closes three things about a
``pre_state_requirements[]`` entry: its member set, its optional ``condition``
(the same closed payload-condition grammar a conditional cell write uses), and
its stored-field predicate. Nothing exercised any of the three until the invite
live-target slot needed ``stored_field_matches_payload`` and a per-target_state
``condition``, so this file pins all three by mutation: the unmutated registry
must be clean, and each malformed shape must fail closed.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import core, foundation

CONTRACT_PATH = ROOT / "spec" / "v1" / "artifacts" / "registry" / "contract-registry.json"
SUBJECT_KIND = "ak.invite.revoke"


class PreStateRequirementGrammarTest(unittest.TestCase):
    def _lint_mutated_contract(self, mutate) -> list[str]:
        root = core.parse_json_text(CONTRACT_PATH.read_text(encoding="utf-8"))
        mutated = copy.deepcopy(root)
        if mutate is not None:
            requirements = mutated["event_kind_registry"]["cell_contracts"][SUBJECT_KIND][
                "pre_state_requirements"
            ]
            mutate(requirements)

        original_load_json = foundation.load_json

        def load_json_with_mutation(lint, path):
            if Path(path).resolve() == CONTRACT_PATH.resolve():
                return mutated
            return original_load_json(lint, path)

        foundation.load_json = load_json_with_mutation
        try:
            lint = foundation.Lint()
            foundation.check_state_contract_closure(lint)
            return lint.errors
        finally:
            foundation.load_json = original_load_json

    def _requirement_errors(self, mutate) -> list[str]:
        return [
            error
            for error in self._lint_mutated_contract(mutate)
            if "pre_state_requirements" in error
        ]

    def test_registered_contract_is_clean(self) -> None:
        self.assertEqual(self._lint_mutated_contract(None), [])

    def test_registered_revoke_requirements_are_condition_gated(self) -> None:
        root = core.parse_json_text(CONTRACT_PATH.read_text(encoding="utf-8"))
        requirements = root["event_kind_registry"]["cell_contracts"][SUBJECT_KIND][
            "pre_state_requirements"
        ]
        # send_failed keeps the live-target slot claimed, so it is the one
        # target_state that must not carry a requirement here.
        gated = {
            requirement["condition"]["const"]
            for requirement in requirements
            if isinstance(requirement.get("condition"), dict)
        }
        self.assertNotIn("send_failed", gated)
        self.assertEqual(
            gated,
            {
                "revoked",
                "expired",
                "revoked_by_capability_loss",
                "revoked_by_inviter_left",
                "invalidated_by_rate_limit",
            },
        )
        for requirement in requirements:
            self.assertEqual(
                requirement["predicate"]["kind"], "stored_field_matches_payload"
            )

    def test_unknown_requirement_member_fails_closed(self) -> None:
        def mutate(requirements):
            requirements[0]["note"] = "an unregistered member"

        self.assertTrue(self._requirement_errors(mutate))

    def test_unknown_condition_kind_fails_closed(self) -> None:
        def mutate(requirements):
            requirements[0]["condition"] = {
                "kind": "field_not_equals",
                "field": "payload.target_state",
                "const": "send_failed",
            }

        self.assertTrue(self._requirement_errors(mutate))

    def test_condition_without_field_path_fails_closed(self) -> None:
        def mutate(requirements):
            requirements[0]["condition"] = {"kind": "field_present", "field": "target_state"}

        self.assertTrue(self._requirement_errors(mutate))

    def test_unknown_predicate_kind_fails_closed(self) -> None:
        def mutate(requirements):
            requirements[0]["predicate"]["kind"] = "stored_field_absent"

        self.assertTrue(self._requirement_errors(mutate))

    def test_matches_payload_predicate_requires_payload_field(self) -> None:
        def mutate(requirements):
            del requirements[0]["predicate"]["payload_field"]

        self.assertTrue(self._requirement_errors(mutate))

    def test_matches_payload_predicate_requires_payload_prefix(self) -> None:
        def mutate(requirements):
            requirements[0]["predicate"]["payload_field"] = "invitee_account_id"

        self.assertTrue(self._requirement_errors(mutate))

    def test_unknown_cell_family_fails_closed(self) -> None:
        def mutate(requirements):
            requirements[0]["cell_family"] = "ak.component.invite.not_a_family.v1"

        self.assertTrue(self._requirement_errors(mutate))

    def test_failure_must_declare_code_and_reason_code(self) -> None:
        def mutate(requirements):
            del requirements[0]["failure"]["reason_code"]

        self.assertTrue(self._requirement_errors(mutate))


if __name__ == "__main__":
    unittest.main()
