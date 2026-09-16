from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from artifact_pipeline import preserve_artifact_metadata_when_semantics_match
from check_artifact_versions import ARTIFACTS, main, repairs_future_generated_at, semantic_content_digest, transition_errors


class ArtifactVersionGuardTest(unittest.TestCase):
    def test_future_timestamp_repair_is_explicit_and_still_requires_version_advance(self) -> None:
        old = {"path": "registry/example.json", "version": 1,
               "generated_at": "2099-01-01T00:00:00Z", "content_digest": "sha256:old"}
        new = {**old, "generated_at": "2001-01-01T00:00:00Z", "content_digest": "sha256:new"}
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / "reference.json"
            with patch("check_artifact_versions.artifact_rows", return_value=[new]), \
                 patch("check_artifact_versions.load_reference", return_value={"artifacts": [old]}), \
                 patch("check_artifact_versions.REFERENCE", reference), \
                 patch("check_artifact_versions.ROOT", Path(directory)):
                self.assertEqual(main(["--write-reference", "--repair-future-generated-at"]), 1)
                self.assertFalse(reference.exists())
                new["version"] = 2
                self.assertEqual(main(["--write-reference"]), 1)
                self.assertFalse(reference.exists())
                self.assertEqual(main(["--write-reference", "--repair-future-generated-at"]), 0)
                self.assertEqual(json.loads(reference.read_text())["artifacts"], [new])

    def test_future_timestamp_repair_cannot_backdate_an_ordinary_transition(self) -> None:
        now = datetime(2026, 9, 7, 10, tzinfo=timezone.utc)
        self.assertTrue(repairs_future_generated_at(
            "2026-09-07T20:20:00+08:00", "2026-09-07T18:00:00+08:00", now
        ))
        for old, new in [
            ("2026-09-07T09:00:00Z", "2026-09-07T08:00:00Z"),
            ("2026-09-07T12:00:00Z", "2026-09-07T11:00:00Z"),
            ("invalid", "2026-09-07T10:00:00Z"),
            ("2026-09-07T12:00:00Z", "2026-09-07T10:00:00"),
        ]:
            with self.subTest(old=old, new=new):
                self.assertFalse(repairs_future_generated_at(old, new, now))

    def test_every_versioned_artifact_excludes_release_metadata_from_semantics(self) -> None:
        paths = sorted(
            [
                *(ARTIFACTS / "registry").glob("*.json"),
                *(ARTIFACTS / "profiles").glob("*.json"),
            ]
        )
        checked = 0
        for path in paths:
            original = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(original, dict) or "version" not in original:
                continue
            mutated = dict(original)
            mutated["version"] = "metadata-only-mutation"
            mutated["generated_at"] = "2099-01-01T00:00:00Z"
            self.assertEqual(
                semantic_content_digest(original),
                semantic_content_digest(mutated),
                path.as_posix(),
            )
            checked += 1
        self.assertGreaterEqual(checked, 50)

    def test_metadata_only_advance_is_rejected(self) -> None:
        old = {
            "path": "registry/example.json",
            "version": "2026-08-26.1",
            "generated_at": "2026-08-26T10:00:00+08:00",
            "content_digest": "sha256:old",
        }
        new = {
            **old,
            "version": "2026-08-26.2",
            "generated_at": "2026-08-26T11:00:00+08:00",
        }
        self.assertEqual(
            transition_errors(old, new),
            [
                "registry/example.json: version changed without semantic content change",
                "registry/example.json: generated_at changed without semantic content change",
            ],
        )

    def test_semantic_change_requires_both_metadata_fields_to_advance(self) -> None:
        old = {
            "path": "registry/example.json",
            "version": "2026-08-26.1",
            "generated_at": "2026-08-26T10:00:00+08:00",
            "content_digest": "sha256:old",
        }
        new = {**old, "content_digest": "sha256:new"}
        self.assertEqual(
            transition_errors(old, new),
            [
                "registry/example.json: content changed without version advance",
                "registry/example.json: content changed without generated_at advance",
            ],
        )

    def test_semantic_change_with_metadata_advance_is_accepted(self) -> None:
        old = {
            "path": "registry/example.json",
            "version": "2026-08-26.1",
            "generated_at": "2026-08-26T10:00:00+08:00",
            "content_digest": "sha256:old",
        }
        new = {
            **old,
            "version": "2026-08-26.2",
            "generated_at": "2026-08-26T11:00:00+08:00",
            "content_digest": "sha256:new",
        }
        self.assertEqual(transition_errors(old, new), [])

    def test_derived_view_preserves_artifact_local_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "derived.json"
            path.write_text(
                json.dumps(
                    {
                        "version": "2026-08-26.1",
                        "generated_at": "2026-08-26T10:00:00+08:00",
                        "rows": ["stable"],
                    }
                ),
                encoding="utf-8",
            )
            candidate = {
                "version": "2026-08-26.2",
                "generated_at": "2026-08-26T11:00:00+08:00",
                "rows": ["stable"],
            }
            actual = preserve_artifact_metadata_when_semantics_match(path, candidate)
            self.assertEqual(actual["version"], "2026-08-26.1")
            self.assertEqual(actual["generated_at"], "2026-08-26T10:00:00+08:00")

    def test_derived_view_uses_new_metadata_for_semantic_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "derived.json"
            path.write_text(
                json.dumps(
                    {
                        "version": "2026-08-26.1",
                        "generated_at": "2026-08-26T10:00:00+08:00",
                        "rows": ["old"],
                    }
                ),
                encoding="utf-8",
            )
            candidate = {
                "version": "2026-08-26.2",
                "generated_at": "2026-08-26T11:00:00+08:00",
                "rows": ["new"],
            }
            self.assertEqual(
                preserve_artifact_metadata_when_semantics_match(path, candidate), candidate
            )

    def test_repeated_generation_does_not_pin_unvalidated_old_metadata(self) -> None:
        import artifact_pipeline

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "derived.json"
            existing = {
                "version": "2026-08-26.1",
                "generated_at": "2026-08-26T10:00:00+08:00",
                "rows": ["new"],
            }
            path.write_text(json.dumps(existing), encoding="utf-8")
            baseline = {
                "path": "derived.json",
                "version": existing["version"],
                "generated_at": existing["generated_at"],
                "content_digest": semantic_content_digest({**existing, "rows": ["old"]}),
            }
            candidate = {
                **existing,
                "version": "2026-08-26.2",
                "generated_at": "2026-08-26T11:00:00+08:00",
            }
            with patch.object(artifact_pipeline, "ROOT", root), patch.object(
                artifact_pipeline, "artifact_metadata_references", return_value={"derived.json": baseline}
            ):
                self.assertEqual(preserve_artifact_metadata_when_semantics_match(path, candidate), candidate)


if __name__ == "__main__":
    unittest.main()
