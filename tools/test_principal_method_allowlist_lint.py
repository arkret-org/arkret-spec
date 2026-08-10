"""Regression tests for the closed v1 principal DID-method allowlist."""

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


class PrincipalMethodAllowlistLintTest(unittest.TestCase):
    def _run(self, mutate) -> list[str]:
        original_load_json = lint_artifacts.load_json
        profiles = copy.deepcopy(
            original_load_json(lint_artifacts.Lint(), PROFILES_PATH)
        )
        mutate(profiles)

        def load_json_with_mutation(lint, path):
            if path.resolve() == PROFILES_PATH:
                return profiles
            return original_load_json(lint, path)

        lint_artifacts.load_json = load_json_with_mutation
        try:
            lint = lint_artifacts.Lint()
            lint_artifacts.check_did_and_device_constraints(lint)
            return lint.errors
        finally:
            lint_artifacts.load_json = original_load_json

    def test_personal_node_cannot_reintroduce_did_web_principal(self) -> None:
        def mutate(profiles):
            profiles["profile_requirements"]["ak.profile.personal_node.v1"][
                "identity"
            ]["allowed_principal_methods"] = ["did:webvh", "did:web"]

        errors = self._run(mutate)
        self.assertTrue(
            any(
                "ak.profile.personal_node.v1" in error
                and "['did:webvh']" in error
                for error in errors
            ),
            errors,
        )

    def test_ephemeral_profile_cannot_admit_an_open_method_set(self) -> None:
        def mutate(profiles):
            profiles["profile_requirements"][
                "ak.profile.ephemeral_pairwise_principal.v1"
            ]["identity"]["allowed_principal_methods"] = ["did:key", "did:web"]

        errors = self._run(mutate)
        self.assertTrue(
            any("ephemeral pairwise profile must admit exactly did:key" in error for error in errors),
            errors,
        )

    def test_ephemeral_profile_cannot_enable_pcr_or_device_directory(self) -> None:
        def mutate(profiles):
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
