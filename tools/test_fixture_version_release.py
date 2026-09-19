from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.check_fixture_digests import fixture_entries, release_transition_errors


def manifest(version: str, digest: str) -> dict:
    return {
        "files": [
            {
                "path": "spec/v1/artifacts/fixtures/example.json",
                "version": version,
                "sha256": digest,
            }
        ]
    }


class FixtureVersionReleaseTest(unittest.TestCase):
    def test_content_change_requires_strict_version_advance(self) -> None:
        old = manifest("2026-09-19.4", "old")
        self.assertEqual(
            release_transition_errors(manifest("2026-09-18.99", "new"), old),
            [
                "fixture content changed without version advance: "
                "spec/v1/artifacts/fixtures/example.json"
            ],
        )
        self.assertEqual(
            release_transition_errors(manifest("2026-09-19.5", "new"), old), []
        )

    def test_metadata_only_version_change_is_rejected(self) -> None:
        self.assertEqual(
            release_transition_errors(
                manifest("2026-09-19.5", "same"),
                manifest("2026-09-19.4", "same"),
            ),
            [
                "fixture version changed without content change: "
                "spec/v1/artifacts/fixtures/example.json"
            ],
        )

    def test_every_live_fixture_has_a_version(self) -> None:
        entries = fixture_entries()
        self.assertTrue(entries)
        self.assertTrue(all("version" in entry for entry in entries))


if __name__ == "__main__":
    unittest.main()
