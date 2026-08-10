"""Regression tests for registry-derived DID-method role eligibility."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import schemas as lint_artifacts

PROFILES_PATH = (
    ROOT / "spec" / "v1" / "artifacts" / "profiles" / "conformance-profiles.json"
).resolve()
ADAPTERS_PATH = (
    ROOT / "spec" / "v1" / "artifacts" / "registry" / "did-method-adapter-registry.json"
).resolve()


class PrincipalMethodAllowlistLintTest(unittest.TestCase):
    def _run(self, mutate) -> list[str]:
        original_load_json = lint_artifacts.load_json
        profiles = copy.deepcopy(
            original_load_json(lint_artifacts.Lint(), PROFILES_PATH)
        )
        adapters = copy.deepcopy(
            original_load_json(lint_artifacts.Lint(), ADAPTERS_PATH)
        )
        mutate(profiles, adapters)

        def load_json_with_mutation(lint, path):
            if path.resolve() == PROFILES_PATH:
                return profiles
            if path.resolve() == ADAPTERS_PATH:
                return adapters
            return original_load_json(lint, path)

        lint_artifacts.load_json = load_json_with_mutation
        try:
            lint = lint_artifacts.Lint()
            lint_artifacts.check_did_and_device_constraints(lint)
            return lint.errors
        finally:
            lint_artifacts.load_json = original_load_json

    def test_personal_node_cannot_remove_registered_human_anchor(self) -> None:
        def mutate(profiles, _adapters):
            profiles["profile_requirements"]["ak.profile.personal_node.v1"][
                "identity"
            ]["allowed_principal_methods"] = ["did:webvh", "did:web"]

        errors = self._run(mutate)
        self.assertTrue(
            any(
                "ak.profile.personal_node.v1" in error
                and "registry-derived human principal anchor allowlist ['did:webvh', 'did:web', 'did:key']" in error
                for error in errors
            ),
            errors,
        )

    def test_ephemeral_profile_cannot_admit_an_open_actor_method_set(self) -> None:
        def mutate(profiles, _adapters):
            profiles["profile_requirements"][
                "ak.profile.ephemeral_pairwise_principal.v1"
            ]["identity"]["allowed_actor_methods"] = ["did:key", "did:web"]

        errors = self._run(mutate)
        self.assertTrue(
            any("registry-derived Realm-local ephemeral actor allowlist ['did:key']" in error for error in errors),
            errors,
        )

    def test_service_profile_cannot_admit_did_key(self) -> None:
        def mutate(profiles, _adapters):
            profiles["profile_requirements"]["ak.profile.personal_node.v1"][
                "identity"
            ]["allowed_service_methods"] = ["did:webvh", "did:web", "did:key"]

        errors = self._run(mutate)
        self.assertTrue(
            any(
                "ak.profile.personal_node.v1" in error
                and "registry-derived service allowlist ['did:webvh', 'did:web']" in error
                for error in errors
            ),
            errors,
        )

    def test_principal_allowlist_is_derived_from_adapter_properties(self) -> None:
        def mutate(_profiles, adapters):
            did_key = next(
                adapter for adapter in adapters["adapters"] if adapter["method"] == "did:key"
            )
            did_key["human_principal_anchor"] = False

        errors = self._run(mutate)
        self.assertTrue(
            any(
                "registry-derived human principal anchor allowlist ['did:webvh', 'did:web']" in error
                for error in errors
            ),
            errors,
        )

    def test_ephemeral_profile_cannot_enable_pcr_or_device_directory(self) -> None:
        def mutate(profiles, _adapters):
            identity = profiles["profile_requirements"][
                "ak.profile.ephemeral_pairwise_principal.v1"
            ]["identity"]
            identity["principal_control_realm_allowed"] = True
            identity["device_directory_allowed"] = True

        errors = self._run(mutate)
        self.assertTrue(
            any("principal_control_realm_allowed" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("device_directory_allowed" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
