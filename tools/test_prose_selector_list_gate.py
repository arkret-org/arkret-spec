"""Mutation tests for the registered-family / normative-list gate.

`zh/sync/current-results.md` section 2 says "v1 登记的 selector kind 为" and then
enumerates them. That is a closure claim an implementer acts on: an unlisted
selector is one it MUST reject. So the list is not documentation of the
registry, it is a second copy of it -- and the copy rotted the first time a
batch added families without touching prose, because nothing connected them.

Each test states one proposition about that connection. The first is the live
assertion; the rest are mutations that must be reported.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate


def errors_for(prose: str | None = None, families: list[str] | None = None) -> list[str]:
    """Run the gate against substituted prose and/or a substituted registry."""
    lint = gate.Lint()
    original_read = Path.read_text
    original_is_file = Path.is_file
    original_families = gate._registered_result_families

    if prose is not None:
        def read_text(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if self == gate.CURRENT_RESULTS_PROSE:
                return prose
            return original_read(self, *args, **kwargs)

        def is_file(self):  # type: ignore[no-untyped-def]
            if self == gate.CURRENT_RESULTS_PROSE:
                return True
            return original_is_file(self)

        Path.read_text = read_text  # type: ignore[method-assign]
        Path.is_file = is_file  # type: ignore[method-assign]
    if families is not None:
        gate._registered_result_families = lambda _lint: set(families)  # type: ignore[assignment]
    try:
        gate.check_registered_families_are_listed_in_prose(lint)
    finally:
        Path.read_text = original_read  # type: ignore[method-assign]
        Path.is_file = original_is_file  # type: ignore[method-assign]
        gate._registered_result_families = original_families  # type: ignore[assignment]
    return lint.errors


class ProseSelectorListTest(unittest.TestCase):
    def test_the_live_prose_lists_every_registered_family(self) -> None:
        self.assertEqual(errors_for(), [])

    def test_the_live_prose_and_registry_agree_on_the_count(self) -> None:
        """A count check, so a family added to only one side is visible as a number."""
        registry = json.loads(
            (ROOT / "spec/v1/artifacts/registry/contract-registry.json").read_text(
                encoding="utf-8"
            )
        )
        registered = {
            row["result_kind"]
            for row in registry["current_result_registry"]["result_kinds"]
        }
        text = gate.CURRENT_RESULTS_PROSE.read_text(encoding="utf-8")
        section = text.split(gate.CURRENT_RESULTS_PROSE_HEADING)[1].split("\n## ")[0]
        listed = set(gate._PROSE_FAMILY_TOKEN_RE.findall(section))
        self.assertEqual(sorted(registered - listed), [])

    def test_a_registered_family_missing_from_the_list_is_reported(self) -> None:
        """This is the exact regression the gate exists for: the registry grew,
        the list did not."""
        reported = errors_for(families=["realm_profile", "a_family_prose_never_names"])
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("a_family_prose_never_names", reported[0])

    def test_several_omissions_are_reported_together(self) -> None:
        reported = errors_for(families=["first_missing_family", "second_missing_family"])
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("first_missing_family", reported[0])
        self.assertIn("second_missing_family", reported[0])

    def test_a_name_listed_outside_the_section_does_not_count(self) -> None:
        """Section 2 is the closure claim; a mention elsewhere in the file is not
        the list an implementer reads as closed."""
        prose = (
            "# current results\n\n`lonely_family` appears here.\n\n"
            + gate.CURRENT_RESULTS_PROSE_HEADING
            + "\n\n- nothing registered is named here;\n\n## 3. 其它\n\n`lonely_family` again.\n"
        )
        reported = errors_for(prose=prose, families=["lonely_family"])
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("lonely_family", reported[0])

    def test_a_name_inside_the_section_counts(self) -> None:
        prose = (
            gate.CURRENT_RESULTS_PROSE_HEADING
            + "\n\n- `listed_family`：something;\n\n## 3. 其它\n"
        )
        self.assertEqual(errors_for(prose=prose, families=["listed_family"]), [])

    def test_renaming_the_anchor_heading_is_reported(self) -> None:
        """Without this the gate would go quiet instead of red, which is the
        failure mode it was written against."""
        prose = "## 2. 别的标题\n\n- `listed_family`：something;\n"
        reported = errors_for(prose=prose, families=["listed_family"])
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("heading to anchor", reported[0])

    def test_a_duplicated_anchor_heading_is_reported(self) -> None:
        prose = (
            gate.CURRENT_RESULTS_PROSE_HEADING
            + "\n\n- `listed_family`：a;\n\n"
            + gate.CURRENT_RESULTS_PROSE_HEADING
            + "\n\n- `listed_family`：b;\n"
        )
        reported = errors_for(prose=prose, families=["listed_family"])
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("heading to anchor", reported[0])

    def test_an_unbackticked_family_name_does_not_count_as_listed(self) -> None:
        """The list is machine-readable only because every family is code-spanned;
        a plain-text mention is not a registered spelling."""
        prose = (
            gate.CURRENT_RESULTS_PROSE_HEADING
            + "\n\n- listed_family：mentioned without backticks;\n"
        )
        reported = errors_for(prose=prose, families=["listed_family"])
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("listed_family", reported[0])


if __name__ == "__main__":
    unittest.main()
