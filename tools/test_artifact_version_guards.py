from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from artifact_pipeline import preserve_artifact_metadata_when_semantics_match
from check_artifact_versions import ARTIFACTS, semantic_content_digest, transition_errors


class ArtifactVersionGuardTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
