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
from check_artifact_versions import (
    ARTIFACTS,
    date_repair_waivers,
    future_metadata_errors,
    main,
    semantic_content_digest,
    transition_errors,
    walks_back_a_future_instant,
    walks_back_a_future_version,
)


class ArtifactVersionGuardTest(unittest.TestCase):
    def repair(self, old, new, argv):
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / "reference.json"
            with (
                patch("check_artifact_versions.artifact_rows", return_value=[new]),
                patch("check_artifact_versions.load_reference", return_value={"artifacts": [old]}),
                patch("check_artifact_versions.REFERENCE", reference),
                patch("check_artifact_versions.ROOT", Path(directory)),
            ):
                code = main(argv)
            return code, reference.exists()

    def test_future_date_repair_must_name_the_artifact_it_repairs(self) -> None:
        old = {"path": "registry/example.json", "version": "2099-01-01.1",
               "generated_at": "2099-01-01T00:00:00Z", "content_digest": "sha256:old"}
        new = {**old, "version": "2001-01-01.1", "generated_at": "2001-01-01T00:00:00Z"}
        # Without the flag the walk-back is an ordinary metadata-only edit and is refused.
        self.assertEqual(self.repair(old, new, ["--write-reference"]), (1, False))
        # Naming some other artifact does not license this one either.
        self.assertEqual(
            self.repair(old, new, ["--write-reference", "--repair-future-date", "registry/other.json"]),
            (1, False),
        )
        self.assertEqual(
            self.repair(old, new, ["--write-reference", "--repair-future-date", "registry/example.json"]),
            (0, True),
        )

    def test_naming_an_artifact_that_needs_no_repair_is_an_error(self) -> None:
        old = {"path": "registry/example.json", "version": "2001-01-01.1",
               "generated_at": "2001-01-01T00:00:00Z", "content_digest": "sha256:old"}
        new = {**old, "version": "2001-01-02.1", "generated_at": "2001-01-02T00:00:00Z",
               "content_digest": "sha256:new"}
        # An ordinary advance is accepted on its own, so the flag has nothing to clear
        # and must say so rather than silently widening what the run is allowed to write.
        self.assertEqual(self.repair(old, new, ["--write-reference"]), (0, True))
        self.assertEqual(
            self.repair(old, new, ["--write-reference", "--repair-future-date", "registry/example.json"]),
            (1, False),
        )

    def test_future_metadata_can_never_become_the_recorded_baseline(self) -> None:
        old = {"path": "registry/example.json", "version": "2001-01-01.1",
               "generated_at": "2001-01-01T00:00:00Z", "content_digest": "sha256:old"}
        new = {**old, "version": "2099-01-01.1", "generated_at": "2099-01-01T00:00:00Z",
               "content_digest": "sha256:new"}
        # Both fields advance, so the transition itself is legal; it is refused only
        # because a stamp that has not happened yet would become the next baseline.
        self.assertEqual(transition_errors(old, new), [])
        self.assertEqual(self.repair(old, new, ["--write-reference"]), (1, False))
        self.assertEqual(
            future_metadata_errors([new], datetime(2026, 9, 19, 3, 31, tzinfo=timezone.utc)),
            [
                "registry/example.json: version 2099-01-01.1 is dated after today",
                "registry/example.json: generated_at 2099-01-01T00:00:00Z has not happened yet",
            ],
        )

    def test_a_date_repair_waives_only_the_field_it_walks_back(self) -> None:
        now = datetime(2026, 9, 19, 3, 31, tzinfo=timezone.utc)
        old = {"path": "registry/example.json", "version": "2026-09-22.1",
               "generated_at": "2026-09-22T09:30:00+08:00", "content_digest": "sha256:old"}
        version_only = {**old, "version": "2026-09-19.1"}
        self.assertEqual(
            date_repair_waivers(old, version_only, now),
            {
                "registry/example.json: version changed without semantic content change",
                "registry/example.json: content changed without version advance",
            },
        )
        instant_only = {**old, "generated_at": "2026-09-19T11:00:00+08:00"}
        self.assertEqual(
            date_repair_waivers(old, instant_only, now),
            {
                "registry/example.json: generated_at changed without semantic content change",
                "registry/example.json: content changed without generated_at advance",
            },
        )

    def test_future_date_repair_cannot_backdate_an_ordinary_transition(self) -> None:
        now = datetime(2026, 9, 7, 10, tzinfo=timezone.utc)
        self.assertTrue(walks_back_a_future_instant(
            "2026-09-07T20:20:00+08:00", "2026-09-07T18:00:00+08:00", now
        ))
        for old, new in [
            ("2026-09-07T09:00:00Z", "2026-09-07T08:00:00Z"),
            ("2026-09-07T12:00:00Z", "2026-09-07T11:00:00Z"),
            ("invalid", "2026-09-07T10:00:00Z"),
            ("2026-09-07T12:00:00Z", "2026-09-07T10:00:00"),
        ]:
            with self.subTest(old=old, new=new):
                self.assertFalse(walks_back_a_future_instant(old, new, now))

    def test_a_version_still_inside_the_last_time_zone_is_not_a_future_stamp(self) -> None:
        # 2026-09-19T23:00+08:00 is already 2026-09-20 in UTC+14, so a release cut
        # that evening may legitimately carry either date; the day after may not.
        now = datetime(2026, 9, 19, 15, tzinfo=timezone.utc)
        self.assertEqual(future_metadata_errors([{"path": "p", "version": "2026-09-20.1"}], now), [])
        self.assertEqual(
            future_metadata_errors([{"path": "p", "version": "2026-09-21.1"}], now),
            ["p: version 2026-09-21.1 is dated after today"],
        )
        self.assertFalse(walks_back_a_future_version("2026-09-20.1", "2026-09-19.1", now))
        self.assertTrue(walks_back_a_future_version("2026-09-21.1", "2026-09-19.1", now))

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
