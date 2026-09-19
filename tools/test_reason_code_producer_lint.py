"""Tests for the reason-code producer-path ratchet adopted by ruling `2026-09-04-1752`.

The gate exists because `invalid_task_fsm_transition` sat in error-code-registry.json for
months describing a profile-declared state machine that no event kind, cell family or fsm
contract could produce. These tests pin the four rules: unreferenced codes must be baselined
or fail, the baseline only shrinks, stale baseline rows fail, and removed codes never return.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.core import ARTIFACTS, Lint
from tools.artifact_lint.reason_code_producers import (
    REASON_CODE_PRODUCER_BASELINE_PATH,
    baseline_document,
    check_reason_code_producer_paths,
    unreferenced_reason_codes,
)

REMOVED_ROW = {
    "code": "gone_code",
    "ruling": "2026-09-04-1752 workflow profile stage transition",
    "registry_version": "2026-09-04.2",
    "why": "no producer path could ever exist",
}


def active(code: str) -> dict:
    return {"code": code, "status": "active"}


def reserved(code: str) -> dict:
    return {
        "code": code,
        "status": "reserved",
        "applies_to": ["test_surface"],
        "activation_condition": "Add a canonical machine producer in the same release.",
    }


def registry_with(*rows: dict) -> dict:
    return {"version": "2026-09-04.2", "codes": [], "reason_codes": list(rows)}


def run(
    registry: dict,
    baseline: dict,
    artifacts: dict[str, str] | None = None,
    prose: dict[str, str] | None = None,
) -> list[str]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        art = root / "artifacts"
        (art / "registry").mkdir(parents=True)
        (art / "registry" / "error-code-registry.json").write_text(
            json.dumps(registry), encoding="utf-8"
        )
        for name, text in (artifacts or {}).items():
            path = art / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        zh = root / "zh"
        zh.mkdir()
        for name, text in (prose or {}).items():
            (zh / name).write_text(text, encoding="utf-8")
        baseline_path = root / "baseline.json"
        baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
        lint = Lint()
        check_reason_code_producer_paths(
            lint, artifacts_root=art, baseline_path=baseline_path, prose_roots=(zh,)
        )
        return [str(error) for error in lint.errors]


REFERENCING_SCHEMA = {
    "schemas/example.schema.json": json.dumps(
        {"description": "reducer rejects with reason_code=bound_code when the cell is bottom"}
    )
}


class ReasonCodeProducerLintTest(unittest.TestCase):
    def test_runner_registers_the_shared_error_code_producer_gate(self) -> None:
        source = (ROOT / "tools/artifact_lint/runner.py").read_text(encoding="utf-8")
        self.assertIn("check_reason_code_producer_paths(lint)", source)

    def test_referenced_code_passes(self) -> None:
        errors = run(registry_with(active("bound_code")), baseline_document([], []), REFERENCING_SCHEMA)
        self.assertEqual(errors, [])

    def test_active_unreferenced_code_fails(self) -> None:
        errors = run(
            registry_with(active("bound_code"), active("orphan_code")),
            baseline_document([], []),
            REFERENCING_SCHEMA,
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("orphan_code) is active but has no machine producer path", errors[0])

    def test_reserved_unreferenced_code_passes(self) -> None:
        errors = run(
            registry_with(active("bound_code"), reserved("orphan_code")),
            baseline_document([], []),
            REFERENCING_SCHEMA,
        )
        self.assertEqual(errors, [])

    def test_reserved_code_must_not_be_emitted(self) -> None:
        errors = run(
            registry_with(reserved("bound_code")), baseline_document([], []), REFERENCING_SCHEMA
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("reserved but a machine artifact emits/references it", errors[0])

    def test_reserved_code_requires_applies_to_and_activation_condition(self) -> None:
        errors = run(
            registry_with({"code": "orphan_code", "status": "reserved"}),
            baseline_document([], []),
        )
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(any("requires a non-empty unique applies_to" in error for error in errors))
        self.assertTrue(any("requires activation_condition" in error for error in errors))

    def test_unknown_status_is_rejected(self) -> None:
        errors = run(
            registry_with({"code": "orphan_code", "status": "planned"}),
            baseline_document([], []),
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("status must be one of", errors[0])

    def test_substring_match_is_not_a_reference(self) -> None:
        artifacts = {
            "schemas/example.schema.json": json.dumps({"description": "see orphan_code_v2 and xorphan_code"})
        }
        errors = run(registry_with(active("orphan_code")), baseline_document([], []), artifacts)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("orphan_code) is active but has no machine producer path", errors[0])

    def test_generated_report_does_not_count_as_producer(self) -> None:
        artifacts = {"reports/some-report.json": json.dumps({"codes": ["orphan_code"]})}
        errors = run(registry_with(active("orphan_code")), baseline_document([], []), artifacts)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("orphan_code) is active but has no machine producer path", errors[0])

    def test_unreferenced_baseline_is_now_forbidden(self) -> None:
        errors = run(registry_with(active("bound_code")), baseline_document(["bound_code"], []), REFERENCING_SCHEMA)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("unreferenced_reason_codes must be empty", errors[0])

    def test_unsorted_baseline_is_rejected(self) -> None:
        baseline = baseline_document([], [])
        baseline["unreferenced_reason_codes"] = ["b_code", "a_code"]
        errors = run(registry_with(reserved("a_code"), reserved("b_code")), baseline)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("must be sorted and unique", errors[0])

    def test_removed_code_re_registered_fails(self) -> None:
        errors = run(
            registry_with(active("bound_code"), active("gone_code")),
            baseline_document([], [REMOVED_ROW]),
            {**REFERENCING_SCHEMA, "schemas/other.json": json.dumps({"x": "gone_code"})},
        )
        self.assertTrue(any("MUST NOT be re-registered" in e for e in errors), errors)

    def test_removed_code_residue_in_artifact_fails(self) -> None:
        artifacts = {
            **REFERENCING_SCHEMA,
            "reports/stale-view.json": json.dumps({"codes": ["gone_code"]}),
        }
        errors = run(registry_with(active("bound_code")), baseline_document([], [REMOVED_ROW]), artifacts)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("removed reason code gone_code still appears", errors[0])
        self.assertIn("stale-view.json", errors[0])

    def test_removed_code_residue_in_prose_fails(self) -> None:
        errors = run(
            registry_with(active("bound_code")),
            baseline_document([], [REMOVED_ROW]),
            REFERENCING_SCHEMA,
            {"doc.md": "reducer MUST reject with `gone_code`"},
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("removed reason code gone_code still appears", errors[0])

    def test_removed_row_naming_a_repository_path_is_rejected(self) -> None:
        row = {**REMOVED_ROW, "ruling": "arkret-work/tasks/spec-open/2026-09-04-1752.md"}
        errors = run(registry_with(active("bound_code")), baseline_document([], [row]), REFERENCING_SCHEMA)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("never a repository path", errors[0])

    def test_code_cannot_be_both_removed_and_baselined(self) -> None:
        errors = run(
            registry_with(active("bound_code")),
            baseline_document(["gone_code"], [REMOVED_ROW]),
            REFERENCING_SCHEMA,
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("cannot be both removed and baselined", errors[0])

    def test_removed_reason_carrier_must_be_active_and_referenced(self) -> None:
        removed = {**REMOVED_ROW, "carried_by_code": "carrier_code"}
        registry = {
            "version": "2026-09-04.2",
            "codes": [reserved("carrier_code")],
            "reason_codes": [active("bound_code")],
        }
        errors = run(registry, baseline_document([], [removed]), REFERENCING_SCHEMA)
        self.assertTrue(any("carried_by_code carrier_code must be active" in error for error in errors), errors)

    def test_live_baseline_matches_live_tree(self) -> None:
        """The committed baseline is exactly the current unreferenced set: nothing hidden,
        nothing stale, and the removed code is gone everywhere."""
        lint = Lint()
        live = unreferenced_reason_codes(lint, ARTIFACTS)
        self.assertEqual(lint.errors, [])
        committed = json.loads(REASON_CODE_PRODUCER_BASELINE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(committed["unreferenced_reason_codes"], [])
        lint = Lint()
        check_reason_code_producer_paths(lint)
        self.assertEqual(lint.errors, [])


if __name__ == "__main__":
    unittest.main()
