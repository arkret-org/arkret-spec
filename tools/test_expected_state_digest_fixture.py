"""Published current-state known answers must match their exact JSON values."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.artifact_lint import primitive_fixtures
from tools.artifact_lint.core import Lint
from tools.regenerate_named_primitive_fixtures import build, canonical, sha


FIXTURE = Path(__file__).resolve().parents[1] / "spec/v1/artifacts/fixtures/expected-state-digest-kat-fixture.json"


class ExpectedStateDigestFixtureTest(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def lint_fixture(self, data):
        original = primitive_fixtures.load_json

        def load(lint, path):
            return data if path == FIXTURE else original(lint, path)

        with patch.object(primitive_fixtures, "load_json", side_effect=load):
            lint = Lint()
            primitive_fixtures.check_named_primitive_fixtures(lint)
        return [str(error) for error in lint.errors]

    def test_all_five_shipped_known_answers_pass_the_integrated_gate(self):
        self.assertEqual(len(self.fixture["cases"]), 5)
        self.assertEqual(self.lint_fixture(self.fixture), [])
        self.assertEqual(build(FIXTURE.name, self.fixture), self.fixture)
        first = self.fixture["cases"][0]
        self.assertEqual(first["inputs"]["frozen_value"], first["digest_input_value"])
        self.assertEqual(first["digest_input_value"]["authority_generation"], "0")
        self.assertEqual(first["expected_digest"], "sha256:bf339e4a62487a260f19d4f727052e8f7b9f5b19ad713d24635a7a7a8d36c934")

    def test_decimal_migration_cannot_retain_integer_known_answer(self):
        stale = copy.deepcopy(self.fixture)
        legacy_value = copy.deepcopy(stale["cases"][0]["digest_input_value"])
        legacy_value["authority_generation"] = 0
        stale["cases"][0]["canonical_utf8"] = canonical(legacy_value)
        stale["cases"][0]["expected_digest"] = sha(canonical(legacy_value))
        self.assertTrue(any("expected-state-digest-kat-fixture.json" in error for error in self.lint_fixture(stale)))
        self.assertEqual(build(FIXTURE.name, stale), self.fixture)

    def test_changed_value_without_refreshed_known_answer_is_rejected(self):
        changed = copy.deepcopy(self.fixture)
        changed["cases"][0]["inputs"]["frozen_value"]["authority_generation"] = "1"
        changed["cases"][0]["digest_input_value"]["authority_generation"] = "1"
        self.assertTrue(self.lint_fixture(changed))
        regenerated = build(FIXTURE.name, changed)
        self.assertEqual(regenerated["cases"][0]["inputs"], changed["cases"][0]["inputs"])
        self.assertEqual(regenerated["cases"][1:], self.fixture["cases"][1:])
        self.assertEqual(self.lint_fixture(regenerated), [])

    def test_digest_only_corruption_is_rejected(self):
        changed = copy.deepcopy(self.fixture)
        changed["cases"][0]["expected_digest"] = "sha256:" + "f" * 64
        self.assertTrue(self.lint_fixture(changed))
        self.assertEqual(build(FIXTURE.name, changed), self.fixture)


if __name__ == "__main__":
    unittest.main()
