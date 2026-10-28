"""The exact WebSocket Signal bytes must retain a matching unsigned digest."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.artifact_lint import fixtures
from tools.artifact_lint.core import Lint
from tools.regenerate_named_primitive_fixtures import build


FIXTURE = Path(__file__).resolve().parents[1] / "spec/v1/artifacts/fixtures/websocket-binding-fixture.json"


def signal_case(data):
    return next(row for row in data["frame_schema_cases"] if row["name"] == "signal_data")


class WebSocketSignalFixtureDigestTest(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def lint_fixture(self, data):
        original = fixtures.load_json

        def load(lint, path):
            return data if path == FIXTURE else original(lint, path)

        with patch.object(fixtures, "load_json", side_effect=load):
            lint = Lint()
            fixtures.check_websocket_binding_fixture(lint)
        return [str(error) for error in lint.errors]

    def test_shipped_vector_passes_the_integrated_gate(self):
        self.assertEqual(self.lint_fixture(self.fixture), [])

    def test_integer_migration_cannot_retain_the_old_digest(self):
        stale = copy.deepcopy(self.fixture)
        frame = json.loads(signal_case(stale)["wire_utf8"])
        envelope = frame["payload"]["envelope"]
        self.assertEqual(envelope["encrypted_payload"]["epoch"], "7")
        envelope["proof"]["envelope_digest"] = (
            "sha256:27fa7559bd09fb59725f88e4f4b2b05070b82ea8d89d4279f9d1a50e022ea639"
        )
        signal_case(stale)["wire_utf8"] = json.dumps(frame, sort_keys=True, separators=(",", ":"))
        self.assertTrue(any("proof.envelope_digest" in error for error in self.lint_fixture(stale)))
        regenerated = build(FIXTURE.name, stale)
        self.assertEqual(regenerated, self.fixture, "regeneration must change only the stale commitment")
        self.assertEqual(len(regenerated["frame_schema_cases"]), 22)

    def test_ciphertext_change_without_a_new_commitment_is_rejected(self):
        frame = json.loads(signal_case(self.fixture)["wire_utf8"])
        frame["payload"]["envelope"]["encrypted_payload"]["ciphertext"] = "AQAAAAAAAAAAAAAAAAAAAA"
        self.assertIn("proof.envelope_digest", fixtures.websocket_signal_fixture_digest_error(frame))


if __name__ == "__main__":
    unittest.main()
