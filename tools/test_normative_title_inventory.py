"""Mutation tests for the closed normative-title inventory."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from artifact_lint import section_identity as gate
from artifact_lint.core import Lint


PAGE = """# 探针

## 1. 必须保持的标题（normative）

正文。
"""


class NormativeTitleInventoryTest(unittest.TestCase):
    def run_gate(
        self,
        *,
        page: str = PAGE,
        rows: list[dict[str, str]] | None = None,
        write_inventory: bool = True,
    ) -> list[str]:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            zh = root / "spec" / "v1" / "zh"
            zh.mkdir(parents=True)
            prose = zh / "probe.md"
            prose.write_text(page, encoding="utf-8", newline="\n")
            inventory_path = root / "tools" / "normative-title-inventory.json"
            inventory_path.parent.mkdir()
            if rows is None:
                rows = [
                    {
                        "page": "probe.md",
                        "heading": "1. 必须保持的标题（normative）",
                        "fragment": "1-必须保持的标题normative",
                    }
                ]
            if write_inventory:
                inventory_path.write_text(
                    json.dumps({"titles": rows}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
            lint = Lint()
            with mock.patch.object(gate, "SPEC_ROOT", root / "spec" / "v1"), mock.patch.object(
                gate, "NORMATIVE_TITLE_INVENTORY_PATH", inventory_path
            ), mock.patch.object(gate, "markdown_files", lambda: [prose]):
                gate.check_normative_title_inventory(lint)
            return lint.errors

    def test_matching_inventory_is_green(self) -> None:
        self.assertEqual([], self.run_gate())

    def test_registered_title_disappearance_is_red(self) -> None:
        errors = self.run_gate(page="# 探针\n\n正文。\n")
        self.assertTrue(any("disappeared" in error for error in errors), errors)

    def test_unregistered_title_appearance_is_red(self) -> None:
        errors = self.run_gate(
            page=PAGE + "\n## 2. 新标题（normative）\n\n正文。\n"
        )
        self.assertTrue(any("appeared" in error for error in errors), errors)

    def test_fragment_drift_is_red(self) -> None:
        rows = [
            {
                "page": "probe.md",
                "heading": "1. 必须保持的标题（normative）",
                "fragment": "wrong",
            }
        ]
        errors = self.run_gate(rows=rows)
        self.assertTrue(any("fragment" in error for error in errors), errors)

    def test_duplicate_row_is_red(self) -> None:
        row = {
            "page": "probe.md",
            "heading": "1. 必须保持的标题（normative）",
            "fragment": "1-必须保持的标题normative",
        }
        errors = self.run_gate(rows=[row, row])
        self.assertTrue(any("duplicate" in error for error in errors), errors)

    def test_missing_inventory_is_red(self) -> None:
        errors = self.run_gate(write_inventory=False)
        self.assertTrue(any("missing" in error for error in errors), errors)

    def test_runner_wires_the_gate(self) -> None:
        source = (Path(__file__).parent / "artifact_lint" / "runner.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("check_normative_title_inventory(lint)", source)


if __name__ == "__main__":
    unittest.main()
