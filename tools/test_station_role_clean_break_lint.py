"""Mutation tests for the Station clean-break and normative-role-name gates.

The clean-break gate promises that no retired Station role name is left
anywhere under ``spec/v1/zh`` or ``spec/v1/artifacts``, and it reported zero
errors while six real occurrences sat in the tree: three in normative prose
(one of them the subject of a MUST NOT) and three in the published OpenAPI
artifact. Every one of them was split by a line break, and both of the gate's
criteria were whitespace-intolerant -- the stem regex separator class was
``[ _-]`` and the guard table was tested with ``token in text`` -- so a wrap
between the two words made the occurrence structurally invisible. Parsing the
document first would not have helped: a YAML single-quoted scalar folds a blank
line into a real newline, so the retired name was split inside the parsed value
as well.

Each case below is either one of the shapes that actually survived in the tree
or the cheapest way to hide a retired name from the repaired gate. The cases
run against temporary trees because the gate reads files from disk; the guard
tables themselves stay in ``tools/artifact_lint/prose.py``, outside both
scanned roots, which is why the gate does not report its own table.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import prose as lint_prose

PROSE_MODULE = ROOT / "tools" / "artifact_lint" / "prose.py"

NORMATIVE_FRONTMATTER = "---\nnormative: true\n---\n\n"


class StationRoleCleanBreakGateTest(unittest.TestCase):
    def _errors(self, files: dict[str, str], check) -> list[str]:
        """Run one gate over a temporary tree standing in for the spec roots."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "zh").mkdir()
            (root / "artifacts").mkdir()
            for relative, content in files.items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content.encode("utf-8"))
            original_spec_root = lint_prose.SPEC_ROOT
            original_artifacts = lint_prose.ARTIFACTS
            lint_prose.SPEC_ROOT = root
            lint_prose.ARTIFACTS = root / "artifacts"
            try:
                lint = lint_prose.Lint()
                check(lint)
                return lint.errors
            finally:
                lint_prose.SPEC_ROOT = original_spec_root
                lint_prose.ARTIFACTS = original_artifacts

    def _station_errors(self, files: dict[str, str]) -> list[str]:
        return self._errors(files, lint_prose.check_station_role_clean_break)

    def _role_name_errors(self, files: dict[str, str]) -> list[str]:
        return self._errors(files, lint_prose.check_normative_prose_role_names)

    # --- the real tree -------------------------------------------------------

    def test_unmutated_repository_passes(self) -> None:
        lint = lint_prose.Lint()
        lint_prose.check_station_role_clean_break(lint)
        self.assertEqual(lint.errors, [])
        lint = lint_prose.Lint()
        lint_prose.check_normative_prose_role_names(lint)
        self.assertEqual(lint.errors, [])

    def test_the_guard_table_is_outside_both_scanned_roots(self) -> None:
        """The only place that legitimately spells the retired names out is the
        gate's own table. It is exempt because ``tools/`` is not a scanned root,
        not because anything filters it, so the table must never be deleted to
        keep the gate quiet."""

        table = PROSE_MODULE.read_text(encoding="utf-8")
        self.assertIn('"Principal Server": "retired Station prose name"', table)
        for root in (ROOT / "spec" / "v1" / "zh", ROOT / "spec" / "v1" / "artifacts"):
            self.assertNotIn(root, PROSE_MODULE.parents)

    def test_the_guard_table_inside_a_scanned_root_is_reported(self) -> None:
        """Copying the table into a scanned root does make it a violation, which
        is what an attempt to widen ``roots`` to the repository would produce:
        such a change needs an explicit waiver for the table, not a smaller
        table."""

        errors = self._station_errors({"zh/copied-guard-table.py": PROSE_MODULE.read_text(encoding="utf-8")})
        self.assertTrue(errors)

    # --- the criteria the gate used to have ----------------------------------

    def test_single_line_occurrence_is_reported(self) -> None:
        errors = self._station_errors(
            {"zh/roles.md": "Principal Server MUST NOT judge freshness locally.\n"}
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("retired Station prose name", errors[0])
        self.assertIn("line 1", errors[0])

    def test_line_wrapped_occurrence_is_reported(self) -> None:
        """The regression: hard-wrapped zh prose split the retired name between
        two lines and the gate saw nothing."""

        errors = self._station_errors(
            {
                "zh/account-lifecycle.md": (
                    "认证新鲜度由 Account Authority 本地判定。Principal\n"
                    "Server MUST NOT 依据 session grant introspection 自行判定。\n"
                )
            }
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("'Principal\\nServer'", errors[0])
        self.assertIn("line 1", errors[0])

    def test_yaml_folded_occurrence_is_reported(self) -> None:
        """The artifact shape: a blank line inside a single-quoted scalar folds
        into a real newline, so the retired name is split in the parsed value
        too and no amount of YAML parsing would expose it."""

        errors = self._station_errors(
            {
                "artifacts/openapi/service.openapi.yaml": (
                    "paths:\n"
                    "  /pcr:\n"
                    "    post:\n"
                    "      description: 'Account Authority relays the unit. The Principal\n"
                    "\n"
                    "        Server independently verifies the transcript.'\n"
                )
            }
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("Principal\\n\\n        Server", errors[0])
        self.assertIn("line 4", errors[0])

    def test_other_whitespace_between_the_words_is_reported(self) -> None:
        """Tabs, runs of spaces and a CRLF wrap are all wrapping artefacts, not
        different terms."""

        for label, separator in (
            ("tab", "\t"),
            ("double space", "  "),
            ("crlf", "\r\n"),
            ("newline and indent", "\n    "),
        ):
            with self.subTest(separator=label):
                errors = self._station_errors(
                    {"zh/roles.md": f"The Principal{separator}Server accepts the unit.\n"}
                )
                self.assertEqual(len(errors), 1, errors)

    def test_word_internal_break_is_reported(self) -> None:
        """A wrap can land inside a word as well as between two words."""

        errors = self._station_errors({"zh/roles.md": "The Princi\npal Server accepts the unit.\n"})
        self.assertEqual(len(errors), 1, errors)

    def test_stem_only_spelling_is_still_reported(self) -> None:
        """Widening the separator class must not cost the stem criterion the
        spellings it already caught."""

        for spelling in ("principal_server", "principal-server", "PrincipalServer", "principalserver"):
            with self.subTest(spelling=spelling):
                errors = self._station_errors({"zh/roles.md": f"See {spelling} for details.\n"})
                self.assertTrue(errors, spelling)

    # --- every occurrence, not just the first --------------------------------

    def test_every_occurrence_in_one_file_is_reported(self) -> None:
        """The gate used to ``search`` and stop, so an author fixed the first
        retired name and had to rerun to learn there were more."""

        errors = self._station_errors(
            {
                "zh/roles.md": (
                    "The Principal Server accepts the unit.\n"
                    "The inviter-side Principal\n"
                    "Server delivers the invite.\n"
                    "The issuer-side principal_server delivers the fact.\n"
                )
            }
        )
        self.assertEqual(len(errors), 3, errors)
        self.assertTrue(any("line 1" in error for error in errors), errors)
        self.assertTrue(any("line 2" in error for error in errors), errors)
        self.assertTrue(any("line 4" in error for error in errors), errors)

    def test_one_occurrence_is_reported_once(self) -> None:
        """``Principal\\nServer`` satisfies the prose name, the type stem and
        the stem regex at the same offset; the reader needs one finding per
        occurrence, not one per matching table row."""

        errors = self._station_errors({"zh/roles.md": "The Principal\nServer accepts.\n"})
        self.assertEqual(len(errors), 1, errors)

    def test_other_retired_tokens_are_reported_when_wrapped(self) -> None:
        for token in (
            "auth_server",
            "ServiceAccountId",
            "Realtime Media Server",
            "ak.profile.auth_server.v1",
        ):
            with self.subTest(token=token):
                wrapped = token[: len(token) // 2] + "\n" + token[len(token) // 2 :]
                errors = self._station_errors({"zh/roles.md": f"See {wrapped} here.\n"})
                self.assertTrue(errors, token)

    # --- no false positives --------------------------------------------------

    def test_current_terms_and_unrelated_principal_uses_stay_green(self) -> None:
        """``Principal Control Realm``, ``principal_did`` and a Station sentence
        must not become violations when the separators are widened -- the whole
        point of the repair is that it costs nothing to adopt."""

        errors = self._station_errors(
            {
                "zh/roles.md": (
                    "PCR 的作用域是「某个 DID 在**当前 Station** 上的账号」。\n"
                    "它的唯一 durable lifecycle 权威是 issuer 的 ledger；Principal\n"
                    "Control Realm 不保存 grant genesis。\n"
                    "`realm_id` MUST NOT 只由 principal DID 决定。\n"
                    "accountable_principal_id 与 principal_id 都不是角色名。\n"
                ),
                "artifacts/registry/service-kinds.json": (
                    '{\n  "service_kind": "station",\n  "server": "station"\n}\n'
                ),
            }
        )
        self.assertEqual(errors, [])

    def test_proposals_stay_exempt(self) -> None:
        errors = self._station_errors(
            {"zh/proposals/old-roles.md": "The Principal\nServer used to accept the unit.\n"}
        )
        self.assertEqual(errors, [])

    # --- the sister gate -----------------------------------------------------

    def test_sister_gate_reports_a_line_wrapped_occurrence(self) -> None:
        """``check_normative_prose_role_names`` had the identical blind spot and
        happened to have nothing hidden behind it; this holds the repair."""

        errors = self._role_name_errors(
            {
                "zh/conformance.md": NORMATIVE_FRONTMATTER
                + "验收由 cotest\nscanner 执行，Directory 由 teabay\nDirectory 提供。\n"
            }
        )
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(any("cotest scanner" in error for error in errors), errors)
        self.assertTrue(any("teabay Directory" in error for error in errors), errors)

    def test_sister_gate_still_reports_a_single_line_occurrence(self) -> None:
        errors = self._role_name_errors(
            {"zh/conformance.md": NORMATIVE_FRONTMATTER + "路径 cotest::runner 不是协议面。\n"}
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("private runner module path", errors[0])

    def test_sister_gate_line_numbers_count_the_frontmatter(self) -> None:
        """The gate matches inside the body but reports against the file, so the
        line number has to be the one the author would open."""

        errors = self._role_name_errors(
            {"zh/conformance.md": NORMATIVE_FRONTMATTER + "第一行。\n第二行由 cotest scanner 执行。\n"}
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("line 6", errors[0])

    def test_sister_gate_ignores_non_normative_documents(self) -> None:
        errors = self._role_name_errors(
            {"zh/notes.md": "---\nnormative: false\n---\n\n由 cotest\nscanner 执行。\n"}
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
