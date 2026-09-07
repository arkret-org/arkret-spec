"""Mutation tests for the CBS canonical Seal body gate."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as lint_artifacts

FIXTURE = ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "cbs-lattice-fixture.json"


class CbsSealCanonicalFixtureLintTest(unittest.TestCase):
    @staticmethod
    def _vector(fixture):
        return next(
            vector
            for vector in fixture["vectors"]
            if vector["name"] == "seal_canonical_no_self_reference"
        )

    def _lint_mutation(self, mutate) -> list[str]:
        original_load_json = lint_artifacts.load_json
        fixture = original_load_json(lint_artifacts.Lint(), FIXTURE)
        mutated = copy.deepcopy(fixture)
        mutate(self._vector(mutated))

        def load_json_with_mutation(lint, path):
            if path.resolve() == FIXTURE.resolve():
                return mutated
            return original_load_json(lint, path)

        lint_artifacts.load_json = load_json_with_mutation
        try:
            lint = lint_artifacts.Lint()
            lint_artifacts.check_cbs_seal_canonical_fixture(lint)
            return lint.errors
        finally:
            lint_artifacts.load_json = original_load_json

    def _lint_fixture_mutation(self, mutate) -> list[str]:
        original_load_json = lint_artifacts.load_json
        fixture = original_load_json(lint_artifacts.Lint(), FIXTURE)
        mutated = copy.deepcopy(fixture)
        mutate(mutated)

        def load_json_with_mutation(lint, path):
            if path.resolve() == FIXTURE.resolve():
                return mutated
            return original_load_json(lint, path)

        lint_artifacts.load_json = load_json_with_mutation
        try:
            lint = lint_artifacts.Lint()
            lint_artifacts.check_vector_registry(lint)
            return lint.errors
        finally:
            lint_artifacts.load_json = original_load_json

    def test_unmodified_fixture_passes(self) -> None:
        lint = lint_artifacts.Lint()
        lint_artifacts.check_cbs_seal_canonical_fixture(lint)
        self.assertEqual(lint.errors, [])

    def test_missing_required_signed_body_field_fails(self) -> None:
        errors = self._lint_mutation(
            lambda vector: vector["seal_body"].pop("availability_receipt_digests")
        )
        self.assertTrue(
            any("availability_receipt_digests" in error and "required" in error for error in errors),
            errors,
        )

    def test_stale_content_derived_identity_fails(self) -> None:
        errors = self._lint_mutation(
            lambda vector: vector["expected"].__setitem__(
                "id", "ak:seal:sha256:" + "0" * 64
            )
        )
        self.assertTrue(any("vector id must be" in error for error in errors), errors)

    def test_id_must_not_enter_signed_body(self) -> None:
        errors = self._lint_mutation(
            lambda vector: vector["seal_body"].__setitem__("id", vector["expected"]["id"])
        )
        self.assertTrue(any("self-referential member" in error for error in errors), errors)

    def test_duplicate_top_level_vector_id_fails(self) -> None:
        errors = self._lint_fixture_mutation(
            lambda fixture: fixture["vectors"].append(copy.deepcopy(fixture["vectors"][0]))
        )
        self.assertTrue(
            any("vector_id duplicates" in error and "within the fixture" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
