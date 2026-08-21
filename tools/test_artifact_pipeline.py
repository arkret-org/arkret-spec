from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import artifact_pipeline


class CapabilityActionSnapshotArchiveTests(unittest.TestCase):
    def test_accepts_snapshot_named_by_complete_jcs_digest(self) -> None:
        snapshot = {
            "version": "2026-08-21.5",
            "generated_at": "2026-08-21T23:55:00+08:00",
            "actions": [{"action": "ak.example.read", "risk_tier": "low"}],
        }
        digest = artifact_pipeline.capability_action_registry_digest(snapshot)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / f"sha256-{digest}.json").write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            errors, archived = (
                artifact_pipeline.check_capability_action_snapshot_archive_files(root)
            )
        self.assertEqual(errors, [])
        self.assertEqual(archived, {digest})

    def test_rejects_filename_that_does_not_match_complete_object(self) -> None:
        snapshot = {
            "version": "2026-08-21.5",
            "generated_at": "2026-08-21T23:55:00+08:00",
            "actions": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / f"sha256-{'0' * 64}.json").write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            errors, archived = (
                artifact_pipeline.check_capability_action_snapshot_archive_files(root)
            )
        self.assertEqual(len(errors), 1)
        self.assertIn("digest mismatch", errors[0])
        self.assertEqual(archived, set())

    def test_registry_change_requires_exact_predecessor_snapshot(self) -> None:
        digest = "1" * 64
        with (
            mock.patch.object(
                artifact_pipeline,
                "check_capability_action_snapshot_archive_files",
                return_value=([], set()),
            ),
            mock.patch.object(
                artifact_pipeline,
                "capability_action_archive_baseline_names",
                return_value=None,
            ),
            mock.patch.object(
                artifact_pipeline,
                "capability_action_predecessor",
                return_value=(digest, {"version": "old"}),
            ),
        ):
            errors = artifact_pipeline.check_capability_action_snapshot_archive()

        self.assertEqual(len(errors), 1)
        self.assertIn(f"sha256-{digest}.json", errors[0])


if __name__ == "__main__":
    unittest.main()
