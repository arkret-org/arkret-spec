"""Mutation tests for the FULL_MARKDOWN_EXAMPLE_SCHEMAS index gate.

The map is an index into prose: it keys a schema by the ordinal of a ```json fence
inside a normative file. Nothing in prose points back at it, so a row whose example
is deleted, renumbered or turned into a non-``json`` fence stops guarding silently —
the lookup in ``check_markdown_full_object_example`` simply misses and that example's
required fields are never checked again. `spec/v1/zh/models/event-and-patch.md` sat in
the map that way: the file carries no ```json fence at all.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import prose as lint_artifacts


EXAMPLE = '```json\n{\n  "kind": "example"\n}\n```\n'


class FullMarkdownExampleIndexLintTest(unittest.TestCase):
    def _lint(self, mapping, root: Path | None = None) -> list[str]:
        lint = lint_artifacts.Lint()
        with patch.object(lint_artifacts, "FULL_MARKDOWN_EXAMPLE_SCHEMAS", mapping):
            if root is None:
                lint_artifacts.check_full_markdown_example_index_resolves(lint)
            else:
                with patch.object(lint_artifacts, "ROOT", root):
                    lint_artifacts.check_full_markdown_example_index_resolves(lint)
        return lint.errors

    def _prose(self, root: Path, body: str) -> str:
        rel = "spec/v1/zh/models/synthetic.md"
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8", newline="\n")
        return rel

    def test_every_committed_row_still_guards_an_object_example(self) -> None:
        self.assertEqual(
            self._lint(lint_artifacts.FULL_MARKDOWN_EXAMPLE_SCHEMAS), []
        )

    def test_a_row_naming_a_prose_file_that_does_not_exist_fails(self) -> None:
        errors = self._lint(
            {"spec/v1/zh/models/no-such-file.md": {1: "schemas/realm.schema.json"}}
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("does not exist", errors[0])

    def test_a_row_indexing_past_the_last_json_block_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rel = self._prose(root, f"# synthetic\n\n{EXAMPLE}")
            errors = self._lint({rel: {2: "schemas/realm.schema.json"}}, root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("carries 1 json block(s)", errors[0])

    def test_an_example_demoted_to_a_text_fence_stops_being_a_json_block(self) -> None:
        # This is the shape event-and-patch.md was in: an ABNF ```text fence where the
        # map expected json_block[1]. Only ```json fences are numbered.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rel = self._prose(root, '# synthetic\n\n```text\n{ "kind": "example" }\n```\n')
            errors = self._lint({rel: {1: "schemas/realm.schema.json"}}, root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("guards nothing", errors[0])

    def test_a_row_pointing_at_a_non_object_example_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rel = self._prose(root, '# synthetic\n\n```json\n["example"]\n```\n')
            errors = self._lint({rel: {1: "schemas/realm.schema.json"}}, root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("is not an object", errors[0])

    def test_a_row_naming_a_missing_schema_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rel = self._prose(root, f"# synthetic\n\n{EXAMPLE}")
            errors = self._lint({rel: {1: "schemas/no-such.schema.json"}}, root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("names a missing schema", errors[0])


if __name__ == "__main__":
    unittest.main()
