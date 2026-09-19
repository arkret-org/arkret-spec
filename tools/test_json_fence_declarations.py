from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.artifact_lint import prose
from tools.artifact_lint.core import Lint


class JsonFenceDeclarationMutationTest(unittest.TestCase):
    def run_meta(self, meta: str) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.md"
            path.write_text(f"```json{meta}\n{{\"x\": 1}}\n```\n", encoding="utf-8", newline="\n")
            lint = Lint()
            with mock.patch.object(prose, "markdown_files", return_value=[path]):
                prose.check_json_fence_declarations(lint)
            return lint.errors

    def test_schema_fragment_and_illustrative_each_pass_alone(self) -> None:
        for meta in (" schema=schemas/probe.json", " fragment", " illustrative"):
            with self.subTest(meta=meta):
                self.assertEqual(self.run_meta(meta), [])

    def test_p1_missing_declaration_fails(self) -> None:
        self.assertTrue(self.run_meta(""))

    def test_p2_schema_plus_fragment_fails(self) -> None:
        self.assertTrue(self.run_meta(" schema=schemas/probe.json fragment"))

    def test_p3_schema_plus_illustrative_fails(self) -> None:
        self.assertTrue(self.run_meta(" schema=schemas/probe.json illustrative"))

    def test_p4_fragment_plus_illustrative_fails(self) -> None:
        self.assertTrue(self.run_meta(" fragment illustrative"))

    def test_p5_all_three_declarations_fail(self) -> None:
        self.assertTrue(self.run_meta(" schema=schemas/probe.json fragment illustrative"))

    def test_p6_fragment_cannot_carry_expectation(self) -> None:
        self.assertTrue(self.run_meta(" fragment expect=invalid"))

    def test_p7_illustrative_cannot_carry_first_error(self) -> None:
        self.assertTrue(self.run_meta(' illustrative first_error="wrong"'))

    def test_live_tree_is_fully_declared_and_runner_is_wired(self) -> None:
        lint = Lint()
        prose.check_json_fence_declarations(lint)
        self.assertEqual(lint.errors, [])
        source = (Path(__file__).parent / "artifact_lint" / "runner.py").read_text(encoding="utf-8")
        self.assertIn("check_json_fence_declarations(lint)", source)

    def test_every_schema_declared_fence_validates_as_declared(self) -> None:
        lint = Lint()
        validated = 0
        for path in prose.markdown_files():
            text = path.read_text(encoding="utf-8")
            for block_index, match in enumerate(prose.JSON_FENCE_RE.finditer(text), start=1):
                meta = match.group("meta")
                schema_ref = prose.schema_ref_from_fence_meta(meta)
                if schema_ref is None:
                    continue
                validated += 1
                data = prose.parse_json_text(match.group("body"))
                prose.check_json_instance_against_schema(
                    lint,
                    path,
                    f"json_block[{block_index}] declared schema example",
                    schema_ref,
                    data,
                    prose.expect_valid_from_fence_meta(meta),
                    prose.first_expected_error_from_fence_meta(meta),
                )
        self.assertGreater(validated, 0)
        self.assertEqual(lint.errors, [])


if __name__ == "__main__":
    unittest.main()
