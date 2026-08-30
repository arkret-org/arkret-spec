"""Regression checks for the complete Actor frontier digest fixture closure."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.core import Lint
from tools.artifact_lint.fixtures import check_actor_frontier_digest_fixture
from tools.regenerate_fixture_digests import update_actor_frontier_vectors

FIXTURE = ROOT / "spec/v1/artifacts/fixtures/sync-fixture.json"


class SyncFrontierDigestFixtureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def errors(self) -> list[str]:
        lint = Lint()
        check_actor_frontier_digest_fixture(lint, FIXTURE, self.data)
        return lint.errors

    def test_committed_vectors_are_closed_and_generation_is_idempotent(self) -> None:
        self.assertEqual(self.errors(), [])
        self.assertEqual(update_actor_frontier_vectors(copy.deepcopy(self.data)), 0)

    def test_same_principal_at_another_station_changes_the_digest(self) -> None:
        vector = self.data["actor_frontier_digest"]
        body = json.loads(vector["canonical_json"])
        body["actor_id"]["account_id"]["station_id"] = "ak:did_core:web:other.example"
        vector["canonical_json"] = json.dumps(body, separators=(",", ":"), sort_keys=True)
        self.assertTrue(any("KAT digest mismatch" in error for error in self.errors()))
        self.assertGreater(update_actor_frontier_vectors(self.data), 0)
        self.assertEqual(self.errors(), [])

    def test_bare_principal_is_not_a_complete_actor(self) -> None:
        vector = self.data["actor_frontier_digest"]
        body = json.loads(vector["canonical_json"])
        body["actor_id"] = body["actor_id"]["account_id"]["principal_id"]
        vector["canonical_json"] = json.dumps(body, separators=(",", ":"), sort_keys=True)
        update_actor_frontier_vectors(self.data)
        self.assertTrue(any("complete ActorId" in error for error in self.errors()))

    def test_domain_separator_is_pinned(self) -> None:
        self.data["actor_frontier_digest"]["transcript_label_utf8_nul"] = ""
        self.assertTrue(any("label mismatch" in error for error in self.errors()))

    def test_schema_negative_keeps_an_independently_valid_digest(self) -> None:
        case = next(
            row for row in self.data["schema_validation_cases"]
            if row["name"] == "realm_actor_frontier_nonempty_sequence_requires_heads"
        )
        case["instance"]["frontier_digest"] = "sha256:" + "0" * 64
        self.assertTrue(any("schema case" in error for error in self.errors()))
        self.assertEqual(update_actor_frontier_vectors(self.data), 1)
        self.assertFalse(case["expect_valid"])
        self.assertEqual(self.errors(), [])


if __name__ == "__main__":
    unittest.main()
