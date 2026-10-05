"""Mutation tests for the stated-preimage / stated-digest gate.

Every case below is a state the fixtures were once actually in, or could reach
without any other gate noticing: a KAT whose input moved while its output did
not. The gate is worth nothing unless it fails on each of them.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as lint_artifacts

FIXTURES = ROOT / "spec" / "v1" / "artifacts" / "fixtures"


class StatedPreimageLintTest(unittest.TestCase):
    def _lint_mutated_fixture(self, fixture_name: str, mutate) -> list[str]:
        """Run the gate with one fixture replaced by a mutated copy."""
        target = (FIXTURES / fixture_name).resolve()
        original_load_json = lint_artifacts.load_json
        loaded = original_load_json(lint_artifacts.Lint(), target)
        mutated = copy.deepcopy(loaded)
        mutate(mutated)

        def load_json_with_mutation(lint, path):
            if path.resolve() == target:
                return mutated
            return original_load_json(lint, path)

        lint_artifacts.load_json = load_json_with_mutation
        try:
            lint = lint_artifacts.Lint()
            lint_artifacts.check_stated_preimage_matches_stated_digest(lint)
            return lint.errors
        finally:
            lint_artifacts.load_json = original_load_json

    @staticmethod
    def _first_node_with(node, key):
        """Depth-first search for the first dict carrying `key`."""
        if isinstance(node, dict):
            if key in node:
                return node
            for value in node.values():
                found = StatedPreimageLintTest._first_node_with(value, key)
                if found is not None:
                    return found
        elif isinstance(node, list):
            for value in node:
                found = StatedPreimageLintTest._first_node_with(value, key)
                if found is not None:
                    return found
        return None

    def test_unmutated_fixtures_pass(self) -> None:
        lint = lint_artifacts.Lint()
        lint_artifacts.check_stated_preimage_matches_stated_digest(lint)
        self.assertEqual(lint.errors, [])

    def test_stale_expected_digest_fails(self) -> None:
        # `expected_canonical_bytes_utf8` / `expected_digest` was outside the
        # original two-pair table: eight vectors were unchecked.
        def mutate(fixture):
            node = self._first_node_with(fixture, "expected_canonical_bytes_utf8")
            assert node is not None and "expected_digest" in node, node
            node["expected_canonical_bytes_utf8"] += " "

        errors = self._lint_mutated_fixture("encoding-fixture.json", mutate)
        self.assertTrue(
            any("stated preimage and the stated digest disagree" in error for error in errors),
            errors,
        )

    def test_content_bound_event_id_preimage_is_checked(self) -> None:
        def mutate(fixture):
            node = self._first_node_with(fixture, "digest_preimage_canonical_bytes_utf8")
            assert node is not None and "event_digest" in node, node
            node["event_digest"] = "sha256:" + "1" * 64

        errors = self._lint_mutated_fixture("content-bound-event-id-fixture.json", mutate)
        self.assertTrue(
            any("digest_preimage_canonical_bytes_utf8" in error for error in errors),
            errors,
        )

    def test_dropping_the_domain_separator_fails(self) -> None:
        # The registration epoch is only reachable through
        # `arkret-applet-registration-epoch-v1\n`. A digest computed over the
        # bare canonical bytes is the classic domain-separation regression.
        import hashlib

        def mutate(fixture):
            node = self._first_node_with(fixture, "canonical_bytes_utf8")
            assert node is not None and "expected_registration_epoch" in node, node
            undomained = hashlib.sha256(node["canonical_bytes_utf8"].encode("utf-8")).hexdigest()
            node["expected_registration_epoch"] = f"sha256:{undomained}"

        errors = self._lint_mutated_fixture("applet-registration-epoch-fixture.json", mutate)
        self.assertTrue(
            any("arkret-applet-registration-epoch-v1" in error for error in errors),
            errors,
        )

    def test_unregistered_stated_preimage_key_fails(self) -> None:
        # The recurring failure is a fixture family nobody thought to add. A new
        # key that states canonical bytes must be registered before it can ship.
        def mutate(fixture):
            node = self._first_node_with(fixture, "expected_canonical_bytes_utf8")
            assert node is not None, node
            node["new_family_preimage_utf8"] = "{}"

        errors = self._lint_mutated_fixture("encoding-fixture.json", mutate)
        self.assertTrue(
            any(
                "new_family_preimage_utf8" in error and "not registered" in error
                for error in errors
            ),
            errors,
        )

    def test_schema_validation_placeholders_stay_exempt(self) -> None:
        # Inject a registered shape-only pair; existing cases no longer state bytes.
        # No accepted outcome or cryptographic truth is asserted by this probe.
        def mutate(fixture):
            fixture["shape_only_registered_pair_probe"] = {
                "canonical_bytes_base64url": "e30",
                "digest": "sha256:" + "e" * 64,
            }
        errors = self._lint_mutated_fixture("schema-validation-fixture.json", mutate)
        self.assertEqual(errors, [])



if __name__ == "__main__":
    unittest.main()
