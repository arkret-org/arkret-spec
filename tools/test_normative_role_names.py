"""Mutation tests for protocol role names in normative prose."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import prose as lint_prose

NORMATIVE_FRONTMATTER = "---\nnormative: true\n---\n\n"


class NormativeRoleNamesTest(unittest.TestCase):
    def _role_name_errors(self, files: dict[str, str]) -> list[str]:
        """Run one gate over a temporary tree standing in for the spec roots."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "zh").mkdir()
            for relative, content in files.items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content.encode("utf-8"))
            original_spec_root = lint_prose.SPEC_ROOT
            lint_prose.SPEC_ROOT = root
            try:
                lint = lint_prose.Lint()
                lint_prose.check_normative_prose_role_names(lint)
                return lint.errors
            finally:
                lint_prose.SPEC_ROOT = original_spec_root

    def test_unmutated_repository_passes(self) -> None:
        lint = lint_prose.Lint()
        lint_prose.check_normative_prose_role_names(lint)
        self.assertEqual(lint.errors, [])

    def test_reports_a_line_wrapped_occurrence(self) -> None:
        errors = self._role_name_errors(
            {
                "zh/conformance.md": NORMATIVE_FRONTMATTER
                + "验收由 cotest\nscanner 执行，Directory 由 flagon\nDirectory 提供。\n"
            }
        )
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(any("cotest scanner" in error for error in errors), errors)
        self.assertTrue(any("flagon Directory" in error for error in errors), errors)

    def test_still_reports_a_single_line_occurrence(self) -> None:
        errors = self._role_name_errors(
            {"zh/conformance.md": NORMATIVE_FRONTMATTER + "路径 cotest::runner 不是协议面。\n"}
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("private runner module path", errors[0])

    def test_line_numbers_count_the_frontmatter(self) -> None:
        """The gate matches inside the body but reports against the file, so the
        line number has to be the one the author would open."""

        errors = self._role_name_errors(
            {"zh/conformance.md": NORMATIVE_FRONTMATTER + "第一行。\n第二行由 cotest scanner 执行。\n"}
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("line 6", errors[0])

    def test_ignores_non_normative_documents(self) -> None:
        errors = self._role_name_errors(
            {"zh/notes.md": "---\nnormative: false\n---\n\n由 cotest\nscanner 执行。\n"}
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
