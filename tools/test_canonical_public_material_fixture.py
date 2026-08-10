from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as lint_artifacts

class CanonicalPublicMaterialFixtureTests(unittest.TestCase):
    def _lint(self, mutate=None) -> list[str]:
        target = (
            lint_artifacts.ARTIFACTS
            / "fixtures"
            / "schema-validation-fixture.json"
        ).resolve()
        original = lint_artifacts.load_json

        def load_json_with_mutation(lint, path: Path):
            loaded = original(lint, path)
            if path.resolve() != target or mutate is None:
                return loaded
            loaded = copy.deepcopy(loaded)
            mutate(loaded)
            return loaded

        lint_artifacts.load_json = load_json_with_mutation
        try:
            lint = lint_artifacts.Lint()
            lint_artifacts.check_schema_fixture_canonical_public_material(lint)
            return lint.errors
        finally:
            lint_artifacts.load_json = original

    def test_current_fixture_is_reproducible(self) -> None:
        self.assertEqual(self._lint(), [])

    def test_value_bytes_drift_is_rejected(self) -> None:
        def mutate(fixture):
            case = next(
                case
                for case in fixture["schema_validation_cases"]
                if case["name"]
                == "root_anchored_recovery_public_did_entry_valid"
            )
            material = case["instance"]
            material["value"]["versionId"] = "3-drifted"

        errors = self._lint(mutate)
        self.assertTrue(any("canonical_bytes_base64url" in error for error in errors), errors)
        self.assertTrue(any(".digest=" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
