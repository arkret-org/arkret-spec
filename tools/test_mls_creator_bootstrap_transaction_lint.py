"""Mutation tests for the creator MLS Genesis bootstrap transaction gate.

The ruling behind encryption-and-audit.md section 5.1.2 exists because two
clients that both obeyed the older prose could still choose different cut
points: one persisted only the final signed Genesis, the other re-read the
pre-Genesis selector from a projection. The machine contract only removes that
freedom if every registered arrow is proven crash-recoverable from both sides,
so each case below removes one piece of that proof and expects the gate to
fail.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as lint_fixtures

REGISTRY_PATH = lint_fixtures.MLS_CREATOR_BOOTSTRAP_REGISTRY_PATH.resolve()
FIXTURE_PATH = lint_fixtures.MLS_CREATOR_BOOTSTRAP_FIXTURE_PATH.resolve()


class MlsCreatorBootstrapTransactionLintTest(unittest.TestCase):
    def _run(self, *, mutate_registry=None, mutate_fixture=None) -> list[str]:
        original_load_json = lint_fixtures.load_json
        overrides: dict[Path, object] = {}

        def snapshot(path: Path, mutate) -> None:
            document = copy.deepcopy(original_load_json(lint_fixtures.Lint(), path))
            mutate(document)
            overrides[path] = document

        if mutate_registry is not None:
            snapshot(REGISTRY_PATH, mutate_registry)
        if mutate_fixture is not None:
            snapshot(FIXTURE_PATH, mutate_fixture)

        def load_json_with_overrides(lint, path):
            resolved = path.resolve()
            if resolved in overrides:
                return overrides[resolved]
            return original_load_json(lint, path)

        lint_fixtures.load_json = load_json_with_overrides
        try:
            lint = lint_fixtures.Lint()
            lint_fixtures.check_mls_creator_bootstrap_transaction(lint)
            return lint.errors
        finally:
            lint_fixtures.load_json = original_load_json

    def test_committed_tree_passes(self) -> None:
        self.assertEqual(self._run(), [])

    def test_arrow_without_a_pre_commit_crash_case_fails(self) -> None:
        def mutate(fixture):
            fixture["crash_cases"] = [
                case
                for case in fixture["crash_cases"]
                if not (
                    case["transition"] == "epoch0_state_persisted_to_genesis_queued"
                    and case["injection"] == "pre_commit"
                )
            ]

        errors = self._run(mutate_fixture=mutate)
        self.assertTrue(
            any("epoch0_state_persisted_to_genesis_queued" in error and "pre_commit" in error for error in errors),
            errors,
        )

    def test_arrow_without_a_post_commit_crash_case_fails(self) -> None:
        def mutate(fixture):
            fixture["crash_cases"] = [
                case
                for case in fixture["crash_cases"]
                if not (
                    case["transition"] == "artifacts_converged_to_ready"
                    and case["injection"] == "post_commit"
                )
            ]

        errors = self._run(mutate_fixture=mutate)
        self.assertTrue(
            any("artifacts_converged_to_ready" in error and "post_commit" in error for error in errors),
            errors,
        )

    def test_new_arrow_without_crash_cases_fails(self) -> None:
        def mutate(registry):
            registry["states"][1]["allowed_exits"].append("ready")
            registry["transitions"].append(
                {
                    "transition_id": "realm_accepted_to_ready",
                    "from_state": "realm_accepted",
                    "to_state": "ready",
                    "commit_boundary": "shortcut",
                    "crash_before_commit": "shortcut",
                    "crash_after_commit": "shortcut",
                }
            )

        errors = self._run(mutate_registry=mutate)
        self.assertTrue(
            any("realm_accepted_to_ready" in error for error in errors),
            errors,
        )

    def test_reordering_the_ruled_chain_fails(self) -> None:
        # The ruling rejected RealmAccepted -> GenesisIntentPersisted because it
        # still allows an accepted Realm create with no durable selector.
        def mutate(registry):
            for row in registry["transitions"]:
                if row["transition_id"] == "genesis_intent_persisted_to_realm_accepted":
                    row["transition_id"] = "realm_accepted_to_genesis_intent_persisted"
                    row["from_state"] = "realm_accepted"
                    row["to_state"] = "genesis_intent_persisted"

        errors = self._run(mutate_registry=mutate)
        self.assertTrue(errors, "an inverted first arrow must fail")

    def test_state_losing_its_required_durable_fields_fails(self) -> None:
        def mutate(registry):
            for row in registry["states"]:
                if row["state_id"] == "genesis_queued":
                    row["required_durable_fields"] = []

        errors = self._run(mutate_registry=mutate)
        self.assertTrue(
            any("required_durable_fields" in error for error in errors),
            errors,
        )

    def test_unregistered_exit_target_fails(self) -> None:
        def mutate(registry):
            for row in registry["states"]:
                if row["state_id"] == "genesis_accepted":
                    row["allowed_exits"] = ["write_ready"]

        errors = self._run(mutate_registry=mutate)
        self.assertTrue(
            any("write_ready" in error for error in errors),
            errors,
        )

    def test_missing_failure_scenario_fails(self) -> None:
        def mutate(fixture):
            fixture["scenario_cases"] = [
                case for case in fixture["scenario_cases"] if case["name"] != "another_genesis_wins"
            ]

        errors = self._run(mutate_fixture=mutate)
        self.assertTrue(
            any("another_genesis_wins" in error for error in errors),
            errors,
        )

    def test_amendment_allowed_after_realm_accepted_fails(self) -> None:
        # The ruling confines in-place amendment to genesis_intent_persisted: from
        # realm_accepted on, the pinned governance outcome and the
        # selector-dependent random material already depend on the selector.
        def mutate(registry):
            for row in registry["states"]:
                if row["state_id"] == "realm_accepted":
                    row["amendment_rule"] = "closed_intent_atomic_replacement"

        errors = self._run(mutate_registry=mutate)
        self.assertTrue(
            any("realm_accepted" in error and "amend" in error for error in errors),
            errors,
        )

    def test_late_state_amendment_without_a_self_arrow_still_fails(self) -> None:
        # Marking a late state amendable without registering its arrow must not
        # slip through the arrow-coverage check by having no arrow at all.
        def mutate(registry):
            for row in registry["states"]:
                if row["state_id"] == "genesis_queued":
                    row["amendment_rule"] = "closed_intent_atomic_replacement"

        errors = self._run(mutate_registry=mutate)
        self.assertTrue(
            any("genesis_queued" in error for error in errors),
            errors,
        )

    def test_amendment_arrow_without_crash_cases_fails(self) -> None:
        def mutate(fixture):
            fixture["crash_cases"] = [
                case
                for case in fixture["crash_cases"]
                if case["transition"] != "genesis_intent_persisted_to_genesis_intent_persisted"
            ]

        errors = self._run(mutate_fixture=mutate)
        self.assertTrue(
            any(
                "genesis_intent_persisted_to_genesis_intent_persisted" in error
                for error in errors
            ),
            errors,
        )

    def test_amendable_record_identity_field_fails(self) -> None:
        def mutate(registry):
            registry["selector_amendment"]["amendable_fields"].append("effective_scope")

        errors = self._run(mutate_registry=mutate)
        self.assertTrue(
            any("effective_scope" in error for error in errors),
            errors,
        )

    def test_sidecar_scope_not_excluded_fails(self) -> None:
        def mutate(registry):
            registry["scope_kind_applicability"]["applicable_scope_kinds"] = [
                "realm",
                "circle",
                "sidecar",
            ]
            registry["scope_kind_applicability"]["excluded_scope_kinds"] = []

        errors = self._run(mutate_registry=mutate)
        self.assertTrue(
            any("sidecar" in error for error in errors),
            errors,
        )

    def test_silent_scope_kind_fails(self) -> None:
        def mutate(registry):
            registry["scope_kind_applicability"]["excluded_scope_kinds"] = ["sidecar"]
            registry["scope_kind_applicability"]["applicable_scope_kinds"] = ["realm"]

        errors = self._run(mutate_registry=mutate)
        self.assertTrue(
            any("every registered effective_scope kind" in error for error in errors),
            errors,
        )

    def test_terminal_failure_state_with_an_exit_fails(self) -> None:
        def mutate(registry):
            for row in registry["states"]:
                if row["state_id"] == "quarantined":
                    row["allowed_exits"] = ["genesis_intent_persisted"]

        errors = self._run(mutate_registry=mutate)
        self.assertTrue(
            any("quarantined" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
