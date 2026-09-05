"""Guards for how the artifact tooling reports failure and writes files.

Three merge-time traps live here, all of them about signal rather than
content:

1. ``artifact_pipeline.py check`` streams each step's output, and the steps
   that happen to run last end on reassuring lines. A run that already failed
   still finished with ``0 error(s), 0 warning(s)`` and ``registry diff:
   clean``, so reading the tail reported green on a non-zero exit.
2. ``refresh-operation-closure-locks`` advanced ``version`` but copied
   ``generated_at`` from the source catalog, which is routinely older than the
   lock being replaced. The timestamp went backwards and
   ``check_artifact_versions.py --write-reference`` then refused the result.
3. Writers that omit ``newline`` inherit the platform line ending, so the same
   generator produced CRLF on Windows and LF elsewhere against a repository
   pinned to ``eol=lf``.
"""

from __future__ import annotations

import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

import artifact_pipeline
import check_operation_closure_locks
from check_operation_closure_locks import next_generated_at, refresh_candidate_lock


TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"


def call_arguments(source: str, opener: str) -> list[str]:
    """Return the argument text of every ``opener`` call in ``source``."""

    calls: list[str] = []
    for match in re.finditer(re.escape(opener), source):
        index = match.end()
        depth = 1
        while index < len(source) and depth:
            if source[index] == "(":
                depth += 1
            elif source[index] == ")":
                depth -= 1
            index += 1
        calls.append(source[match.end() : index])
    return calls


class CheckVerdictTest(unittest.TestCase):
    def test_verdict_is_the_last_line_and_names_the_failing_steps(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            status = artifact_pipeline.verdict("check", ["artifact lint", "prose lint"])
        self.assertEqual(status, 1)
        last = stream.getvalue().splitlines()[-1]
        self.assertTrue(last.startswith("FAILED: check:"), last)
        self.assertIn("artifact lint", last)
        self.assertIn("prose lint", last)

    def test_passing_verdict_is_explicit(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            status = artifact_pipeline.verdict("check", [])
        self.assertEqual(status, 0)
        self.assertEqual(stream.getvalue().splitlines()[-1], "PASSED: check: all steps clean")

    def test_failing_step_still_ends_on_a_failure_marker(self) -> None:
        """The regression: a failing step followed by reassuring tail output."""

        def reassuring_prose_lint() -> int:
            print("0 error(s), 0 warning(s)")
            print("registry diff: clean")
            return 0

        clean_checks = {
            name: Mock(return_value=[])
            for name in (
                "check_capability_action_derivations",
                "check_id_wire_form_derivations",
                "check_openapi_policy_projection",
                "check_derived_registry_views",
                "check_operation_schema_index",
                "check_public_registry_snapshot",
                "check_classification_discipline",
            )
        }
        clean_steps = {
            name: Mock(return_value=0)
            for name in (
                "run_openapi_operation_selector",
                "run_operation_closure_locks",
                "run_operation_completeness_report",
                "run_event_reference_inventory",
                "run_payload_validator_profile_check",
                "run_event_kind_vector_gap_check",
                "run_property_presence_manifest",
                "run_schema_consumer_coverage",
                "run_operation_string_classification",
                "run_operation_string_classification_test",
                "run_long_text_schema_test",
                "run_schema_constructability_test",
                "run_session_grant_kat_check",
                "run_contact_round_kat_check",
                "run_handle_claim_kat_check",
                "run_artifact_version_check",
                "run_lint",
            )
        }
        stream = io.StringIO()
        with (
            patch.multiple(
                artifact_pipeline,
                **clean_checks,
                **clean_steps,
                print_contract_status=Mock(),
                # The step that actually fails runs early, exactly as it did in
                # the merge that motivated this guard.
                run_fixture_digest_check=Mock(return_value=1),
                run_prose_lint=Mock(side_effect=reassuring_prose_lint),
            ),
            redirect_stdout(stream),
        ):
            status = artifact_pipeline.cmd_check(None)

        lines = stream.getvalue().splitlines()
        self.assertEqual(status, 1)
        self.assertIn("registry diff: clean", lines)
        self.assertTrue(lines[-1].startswith("FAILED: check:"), lines[-1])
        self.assertIn("fixture digests", lines[-1])

    def test_pre_lint_errors_also_end_on_a_failure_marker(self) -> None:
        clean = {
            name: Mock(return_value=[])
            for name in (
                "check_id_wire_form_derivations",
                "check_openapi_policy_projection",
                "check_derived_registry_views",
                "check_operation_schema_index",
                "check_public_registry_snapshot",
                "check_classification_discipline",
            )
        }
        stream = io.StringIO()
        with (
            patch.multiple(
                artifact_pipeline,
                **clean,
                check_capability_action_derivations=Mock(return_value=["derivation drift"]),
                profile_summary_text=Mock(return_value="profiles: n/a"),
            ),
            redirect_stdout(stream),
        ):
            status = artifact_pipeline.cmd_check(None)
        self.assertEqual(status, 1)
        self.assertTrue(stream.getvalue().splitlines()[-1].startswith("FAILED: check:"))


class ClosureLockGeneratedAtTest(unittest.TestCase):
    def test_stale_candidate_timestamp_is_advanced(self) -> None:
        self.assertEqual(
            next_generated_at("2026-09-05T12:00:00+08:00", "2026-09-05T10:21:00+08:00"),
            "2026-09-05T12:00:01+08:00",
        )

    def test_equal_timestamp_still_advances(self) -> None:
        self.assertEqual(
            next_generated_at("2026-09-05T12:00:00+08:00", "2026-09-05T12:00:00+08:00"),
            "2026-09-05T12:00:01+08:00",
        )

    def test_fresher_candidate_is_kept_verbatim(self) -> None:
        self.assertEqual(
            next_generated_at("2026-09-05T10:21:00+08:00", "2026-09-05T12:00:00+08:00"),
            "2026-09-05T12:00:00+08:00",
        )

    def test_refresh_advances_both_version_and_generated_at(self) -> None:
        existing = {
            "version": "2026-09-05.1",
            "generated_at": "2026-09-05T12:00:00+08:00",
            "identity_key": "operation",
            "closures": [{"operation": "ak.realm.create", "sha256": "old"}],
        }
        # The catalog the payload copies its timestamp from is older than the
        # lock being replaced, which is what wrote the timestamp backwards.
        expected = {
            "version": "2026-08-27.1",
            "generated_at": "2026-09-05T10:21:00+08:00",
            "identity_key": "operation",
            "closures": [{"operation": "ak.realm.create", "sha256": "new"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "operation-contract-closure-lock.json"
            path.write_text(json.dumps(existing), encoding="utf-8", newline="\n")
            summary = refresh_candidate_lock(path, expected)
            written = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(summary["changed"], ["ak.realm.create"])
        self.assertEqual(written["version"], "2026-09-05.2")
        self.assertGreater(written["generated_at"], existing["generated_at"])


class GeneratedFileNewlineTest(unittest.TestCase):
    def test_every_tool_writer_pins_lf(self) -> None:
        offenders: list[str] = []
        for path in sorted(TOOLS.rglob("*.py")):
            if path.name.startswith("test_"):
                continue
            source = path.read_text(encoding="utf-8")
            for call in call_arguments(source, ".write_text("):
                if "newline=" not in call:
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}: write_text")
            for call in call_arguments(source, "open("):
                if re.search(r"""["'][wa]\+?["']""", call) and "newline=" not in call:
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}: open")
        self.assertEqual(offenders, [])

    def test_no_tracked_artifact_carries_crlf(self) -> None:
        offenders = [
            path.relative_to(ROOT).as_posix()
            for path in sorted(ARTIFACTS.rglob("*"))
            if path.is_file()
            and path.suffix in {".json", ".yaml", ".yml", ".md"}
            and b"\r\n" in path.read_bytes()
        ]
        self.assertEqual(offenders, [])


class ModuleImportTest(unittest.TestCase):
    def test_closure_lock_helpers_are_exported(self) -> None:
        self.assertTrue(hasattr(check_operation_closure_locks, "next_generated_at"))
        self.assertTrue(hasattr(check_operation_closure_locks, "parse_generated_at"))


if __name__ == "__main__":
    unittest.main()
