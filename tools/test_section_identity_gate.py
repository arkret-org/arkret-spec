"""Mutation tests for the section-identity gate.

Report 0140 found three pages whose numbered sections were cited as normative
sources while the numbers themselves were ambiguous, and fragment links that
pointed at headings which did not exist. The gate that now forbids both is only
worth its runtime if each rule can actually be made to fail: a gate nobody can
make fail is indistinguishable from no gate.

So every check here is exercised twice — once against a tree that satisfies it,
and once against a single-mutation tree that violates exactly one rule. The
committed spec is asserted green too, so a rule that silently stops matching
real prose shows up as a failure here rather than as quiet permission.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from artifact_lint import core
from artifact_lint import section_identity as gate
from artifact_lint.core import Lint

NEWLINE = chr(10)

OWNER = "arkret-work/tasks/spec-open/probe.md"

GREEN_PAGE = """# 探针页

## 1. 第一节

正文一。见 [§2 第二节](#2-第二节)。

## 2. 第二节

正文二。见 [另一页 §1](./other.md#1-另一节)。

### 2.1 指向节

> **引用别名（normative pointer）**：本节不独立新增义务，其全部规范内容见
> [§1 第一节](#1-第一节)。
"""

OTHER_PAGE = """# 另一页

## 1. 另一节

正文。
"""

LEDGER = {
    "version": "probe",
    "sections": [
        {
            "page": "probe.md",
            "section": "2.1",
            "meaning": "指向节的旧身份。",
            "disposition": "pointer",
            "target": "probe.md#21-指向节",
        }
    ],
}

RATCHET: dict = {"version": "probe", "anchors": []}

ARTIFACT = {
    "version": "probe",
    "rows": [{"source_anchor": "spec/v1/zh/probe.md#1-第一节"}],
}


class SectionIdentityGateTest(unittest.TestCase):
    """Each test mutates one thing and asserts the gate notices."""

    def run_gates(
        self,
        *,
        pages: dict[str, str] | None = None,
        artifacts: dict[str, dict] | None = None,
        ledger: dict | None = None,
        ratchet: dict | None = None,
        which: str = "all",
    ) -> list[str]:
        pages = {"probe.md": GREEN_PAGE, "other.md": OTHER_PAGE} if pages is None else pages
        artifacts = {"registry/probe.json": ARTIFACT} if artifacts is None else artifacts
        ledger = LEDGER if ledger is None else ledger
        ratchet = RATCHET if ratchet is None else ratchet

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            zh = root / "spec" / "v1" / "zh"
            zh.mkdir(parents=True)
            page_paths = []
            for name, text in pages.items():
                path = zh / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8", newline="\n")
                page_paths.append(path)
            artifacts_root = root / "spec" / "v1" / "artifacts"
            artifacts_root.mkdir(parents=True)
            for name, document in artifacts.items():
                path = artifacts_root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
            tools = root / "tools"
            tools.mkdir()
            ledger_path = tools / "prose-section-identity-ledger.json"
            ratchet_path = tools / "artifact-anchor-fragment-exemptions.json"
            if ledger is not False:
                ledger_path.write_text(
                    json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
            if ratchet is not False:
                ratchet_path.write_text(
                    json.dumps(ratchet, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )

            lint = Lint()
            with mock.patch.object(gate, "ROOT", root), mock.patch.object(
                gate, "SPEC_ROOT", root / "spec" / "v1"
            ), mock.patch.object(gate, "ARTIFACTS", artifacts_root), mock.patch.object(
                gate, "LEDGER_PATH", ledger_path
            ), mock.patch.object(
                gate, "ARTIFACT_ANCHOR_RATCHET_PATH", ratchet_path
            ), mock.patch.object(
                gate, "markdown_files", lambda: page_paths
            ), mock.patch.object(
                core, "ROOT", root
            ):
                if which in ("all", "numbers"):
                    gate.check_numbered_heading_identity(lint)
                if which in ("all", "links"):
                    gate.check_markdown_fragment_targets(lint)
                if which in ("all", "linked_sections"):
                    gate.check_linked_page_section_refs(lint)
                if which in ("all", "artifacts"):
                    gate.check_artifact_fragment_targets(lint)
                if which in ("all", "pointers"):
                    gate.check_normative_pointer_aliases(lint)
                if which in ("all", "ledger"):
                    gate.check_prose_section_identity_ledger(lint)
            return lint.errors

    # ---- baselines -------------------------------------------------------

    def test_the_probe_tree_is_green(self) -> None:
        """Without a mutation nothing fires, so every red below is the mutation."""
        self.assertEqual([], self.run_gates())

    def test_the_committed_spec_is_green(self) -> None:
        """The real tree passes, so no rule has quietly stopped matching prose."""
        lint = Lint()
        gate.check_numbered_heading_identity(lint)
        gate.check_markdown_fragment_targets(lint)
        gate.check_linked_page_section_refs(lint)
        gate.check_artifact_fragment_targets(lint)
        gate.check_normative_pointer_aliases(lint)
        gate.check_prose_section_identity_ledger(lint)
        self.assertEqual([], lint.errors)

    # ---- linked page section refs ---------------------------------------

    def test_a_linked_page_citation_of_a_missing_section_turns_the_gate_red(self) -> None:
        """The plain-text gate strips the link, taking the page name with it."""
        page = GREEN_PAGE + "\n见 [`other.md`](./other.md) §9.7 的规则。\n"
        errors = self.run_gates(
            pages={"probe.md": page, "other.md": OTHER_PAGE}, which="linked_sections"
        )
        self.assertTrue(
            any("does not have" in error for error in errors), errors
        )

    def test_a_linked_page_citation_of_a_real_section_stays_green(self) -> None:
        page = GREEN_PAGE + "\n见 [`other.md`](./other.md) §1 的规则。\n"
        self.assertEqual(
            [],
            self.run_gates(
                pages={"probe.md": page, "other.md": OTHER_PAGE},
                which="linked_sections",
            ),
        )

    def test_a_section_number_inside_the_link_label_is_resolved(self) -> None:
        """``[`other.md` §9.7](./other.md)`` is the shape 842 citations use."""
        page = GREEN_PAGE + NEWLINE + "见 [`other.md` §9.7](./other.md) 的规则。" + NEWLINE
        errors = self.run_gates(
            pages={"probe.md": page, "other.md": OTHER_PAGE}, which="linked_sections"
        )
        self.assertTrue(any("does not have" in error for error in errors), errors)

    def test_a_real_section_inside_the_link_label_stays_green(self) -> None:
        page = GREEN_PAGE + NEWLINE + "见 [`other.md` §1](./other.md) 的规则。" + NEWLINE
        self.assertEqual(
            [],
            self.run_gates(
                pages={"probe.md": page, "other.md": OTHER_PAGE},
                which="linked_sections",
            ),
        )

    # ---- numbered heading identity --------------------------------------

    def test_a_number_naming_two_sections_turns_the_gate_red(self) -> None:
        page = GREEN_PAGE + "\n## 2. 冒名顶替的第二节\n\n正文。\n"
        errors = self.run_gates(
            pages={"probe.md": page, "other.md": OTHER_PAGE}, which="numbers"
        )
        self.assertTrue(
            any("names two sections" in error for error in errors), errors
        )

    def test_two_headings_producing_one_slug_turn_the_gate_red(self) -> None:
        """Renderers resolve the first, so the second is unaddressable."""
        page = GREEN_PAGE + "\n### 2.1 指向节\n\n正文。\n"
        errors = self.run_gates(
            pages={"probe.md": page, "other.md": OTHER_PAGE}, which="numbers"
        )
        self.assertTrue(
            any("is produced by two headings" in error for error in errors), errors
        )

    def test_a_duplicate_number_inside_a_code_fence_is_not_a_heading(self) -> None:
        """A sample document in a fence is an example, not a section of this page."""
        page = GREEN_PAGE + "\n```markdown\n## 2. 示例里的第二节\n```\n"
        self.assertEqual(
            [],
            self.run_gates(
                pages={"probe.md": page, "other.md": OTHER_PAGE}, which="numbers"
            ),
        )

    # ---- markdown fragments ---------------------------------------------

    def test_a_link_to_a_heading_that_does_not_exist_turns_the_gate_red(self) -> None:
        page = GREEN_PAGE.replace("#1-第一节", "#1-不存在的节")
        errors = self.run_gates(
            pages={"probe.md": page, "other.md": OTHER_PAGE}, which="links"
        )
        self.assertTrue(
            any("has no such heading" in error for error in errors), errors
        )

    def test_a_cross_page_link_resolves_against_the_other_page(self) -> None:
        page = GREEN_PAGE.replace("./other.md#1-另一节", "./other.md#1-并不在另一页")
        errors = self.run_gates(
            pages={"probe.md": page, "other.md": OTHER_PAGE}, which="links"
        )
        self.assertTrue(
            any("other.md" in error and "has no such heading" in error for error in errors),
            errors,
        )

    def test_an_external_url_fragment_is_not_a_section_reference(self) -> None:
        page = GREEN_PAGE + "\n见 [RFC 9530 §2](https://example.test/rfc#section-2)。\n"
        self.assertEqual(
            [],
            self.run_gates(
                pages={"probe.md": page, "other.md": OTHER_PAGE}, which="links"
            ),
        )

    # ---- artifact anchors ------------------------------------------------

    def test_an_artifact_anchor_with_no_such_heading_turns_the_gate_red(self) -> None:
        artifact = {"rows": [{"source_anchor": "spec/v1/zh/probe.md#1-并不存在"}]}
        errors = self.run_gates(
            artifacts={"registry/probe.json": artifact}, which="artifacts"
        )
        self.assertTrue(
            any("artifact anchor" in error for error in errors), errors
        )

    def test_a_bare_number_anchor_turns_the_gate_red(self) -> None:
        """`...md#2.1` names a section number, which no renderer resolves."""
        artifact = {"rows": [{"normative": "zh/probe.md#2.1"}]}
        errors = self.run_gates(
            artifacts={"registry/probe.json": artifact}, which="artifacts"
        )
        self.assertTrue(
            any("retired section-number form" in error for error in errors), errors
        )

    def test_a_bare_number_anchor_is_red_even_when_the_number_exists(self) -> None:
        """The number resolving is not the point: the fragment still cannot be clicked."""
        artifact = {"rows": [{"normative": "zh/probe.md#1"}]}
        errors = self.run_gates(
            artifacts={"registry/probe.json": artifact}, which="artifacts"
        )
        self.assertTrue(
            any("retired section-number form" in error for error in errors), errors
        )

    def test_an_explicit_html_anchor_resolves(self) -> None:
        """A table row cannot be an ATX heading, so it carries `<a id>` instead."""
        page = GREEN_PAGE + NEWLINE + '| <a id="probe-001"></a>1 | 条款 |' + NEWLINE
        artifact = {"rows": [{"source_anchor": "spec/v1/zh/probe.md#probe-001"}]}
        self.assertEqual(
            [],
            self.run_gates(
                pages={"probe.md": page},
                artifacts={"registry/probe.json": artifact},
                which="artifacts",
            ),
        )

    def test_an_html_anchor_inside_a_code_fence_does_not_resolve(self) -> None:
        """A sample in a fence is not a target, exactly as a fenced heading is not."""
        page = (
            GREEN_PAGE
            + NEWLINE
            + "```html"
            + NEWLINE
            + '<a id="probe-002"></a>'
            + NEWLINE
            + "```"
            + NEWLINE
        )
        artifact = {"rows": [{"source_anchor": "spec/v1/zh/probe.md#probe-002"}]}
        errors = self.run_gates(
            pages={"probe.md": page},
            artifacts={"registry/probe.json": artifact},
            which="artifacts",
        )
        self.assertTrue(any("artifact anchor" in error for error in errors), errors)

    def test_a_ratchet_row_suppresses_a_known_broken_anchor(self) -> None:
        artifact = {"rows": [{"source_anchor": "spec/v1/zh/probe.md#1-并不存在"}]}
        ratchet = {
            "anchors": [
                {
                    "artifact": "spec/v1/artifacts/registry/probe.json",
                    "anchor": "zh/probe.md#1-并不存在",
                    "owner_report": OWNER,
                }
            ]
        }
        self.assertEqual(
            [],
            self.run_gates(
                artifacts={"registry/probe.json": artifact},
                ratchet=ratchet,
                which="artifacts",
            ),
        )

    def test_a_ratchet_row_for_an_anchor_that_now_resolves_turns_the_gate_red(self) -> None:
        """A repaired anchor must leave the list, not sit there licensing the next break."""
        ratchet = {
            "anchors": [
                {
                    "artifact": "spec/v1/artifacts/registry/probe.json",
                    "anchor": "zh/probe.md#1-第一节",
                    "owner_report": OWNER,
                }
            ]
        }
        errors = self.run_gates(ratchet=ratchet, which="artifacts")
        self.assertTrue(
            any("resolves now" in error for error in errors), errors
        )

    def test_a_ratchet_row_no_artifact_carries_turns_the_gate_red(self) -> None:
        ratchet = {
            "anchors": [
                {
                    "artifact": "spec/v1/artifacts/registry/probe.json",
                    "anchor": "zh/probe.md#9-早就删掉的节",
                    "owner_report": OWNER,
                }
            ]
        }
        errors = self.run_gates(ratchet=ratchet, which="artifacts")
        self.assertTrue(
            any("no artifact carries this anchor" in error for error in errors), errors
        )

    def test_a_ratchet_row_without_an_owner_report_turns_the_gate_red(self) -> None:
        """An unowned exemption is a permanent hole, not a tracked gap."""
        artifact = {"rows": [{"source_anchor": "spec/v1/zh/probe.md#1-并不存在"}]}
        ratchet = {
            "anchors": [
                {
                    "artifact": "spec/v1/artifacts/registry/probe.json",
                    "anchor": "zh/probe.md#1-并不存在",
                }
            ]
        }
        errors = self.run_gates(
            artifacts={"registry/probe.json": artifact},
            ratchet=ratchet,
            which="artifacts",
        )
        self.assertTrue(any("no owner_report" in error for error in errors), errors)

    def test_a_missing_ratchet_file_turns_the_gate_red(self) -> None:
        errors = self.run_gates(ratchet=False, which="artifacts")
        self.assertTrue(any("ratchet is missing" in error for error in errors), errors)

    # ---- normative pointers ---------------------------------------------

    def test_a_pointer_that_also_carries_prose_turns_the_gate_red(self) -> None:
        """Half the obligation here and half there means neither copy is authoritative."""
        page = GREEN_PAGE + "\n带 body 的请求 MUST 绑定 Content-Digest。\n"
        errors = self.run_gates(
            pages={"probe.md": page, "other.md": OTHER_PAGE}, which="pointers"
        )
        self.assertTrue(
            any("outside the pointer block" in error for error in errors), errors
        )

    def test_a_pointer_with_two_targets_turns_the_gate_red(self) -> None:
        page = GREEN_PAGE.replace(
            "> [§1 第一节](#1-第一节)。",
            "> [§1 第一节](#1-第一节) 与 [§2 第二节](#2-第二节)。",
        )
        errors = self.run_gates(
            pages={"probe.md": page, "other.md": OTHER_PAGE}, which="pointers"
        )
        self.assertTrue(
            any("with 2 link targets" in error for error in errors), errors
        )

    def test_a_pointer_with_no_target_turns_the_gate_red(self) -> None:
        page = GREEN_PAGE.replace("> [§1 第一节](#1-第一节)。", "> 见本页上文。")
        errors = self.run_gates(
            pages={"probe.md": page, "other.md": OTHER_PAGE}, which="pointers"
        )
        self.assertTrue(
            any("with 0 link targets" in error for error in errors), errors
        )

    def test_a_pointer_without_a_fragment_turns_the_gate_red(self) -> None:
        """Naming a page is not naming the section that carries the obligation."""
        page = GREEN_PAGE.replace("(#1-第一节)", "(./other.md)")
        errors = self.run_gates(
            pages={"probe.md": page, "other.md": OTHER_PAGE}, which="pointers"
        )
        self.assertTrue(
            any("without a section fragment" in error for error in errors), errors
        )

    def test_a_pointer_at_a_missing_section_turns_the_gate_red(self) -> None:
        page = GREEN_PAGE.replace("(#1-第一节)", "(#1-并不存在)")
        errors = self.run_gates(
            pages={"probe.md": page, "other.md": OTHER_PAGE}, which="pointers"
        )
        self.assertTrue(
            any("has no such heading" in error for error in errors), errors
        )

    def test_a_pointer_chain_turns_the_gate_red(self) -> None:
        """A pointer that points at a pointer has no authoritative end."""
        page = GREEN_PAGE.replace(
            "## 1. 第一节\n\n正文一。见 [§2 第二节](#2-第二节)。",
            "## 1. 第一节\n\n> **引用别名（normative pointer）**：其全部规范内容见\n"
            "> [另一页 §1](./other.md#1-另一节)。",
        ).replace("(#1-第一节)", "(#1-第一节)")
        errors = self.run_gates(
            pages={"probe.md": page, "other.md": OTHER_PAGE}, which="pointers"
        )
        self.assertTrue(
            any("itself a pointer" in error for error in errors), errors
        )

    def test_the_parent_of_a_pointer_section_is_not_itself_a_pointer(self) -> None:
        """A pointer block belongs to the section declaring it, not to its ancestors."""
        self.assertEqual([], self.run_gates(which="pointers"))

    # ---- identity ledger -------------------------------------------------

    def test_a_missing_ledger_turns_the_gate_red(self) -> None:
        errors = self.run_gates(ledger=False, which="ledger")
        self.assertTrue(any("ledger is missing" in error for error in errors), errors)

    def test_an_empty_ledger_turns_the_gate_red(self) -> None:
        errors = self.run_gates(ledger={"sections": []}, which="ledger")
        self.assertTrue(any("carries no sections" in error for error in errors), errors)

    def test_a_ledger_target_that_does_not_resolve_turns_the_gate_red(self) -> None:
        """A registered anchor whose recorded home vanished is a lost obligation."""
        ledger = json.loads(json.dumps(LEDGER))
        ledger["sections"][0]["target"] = "probe.md#21-搬走之后没人要的节"
        errors = self.run_gates(ledger=ledger, which="ledger")
        self.assertTrue(
            any("has no such heading" in error for error in errors), errors
        )

    def test_a_ledger_target_without_a_fragment_turns_the_gate_red(self) -> None:
        ledger = json.loads(json.dumps(LEDGER))
        ledger["sections"][0]["target"] = "probe.md"
        errors = self.run_gates(ledger=ledger, which="ledger")
        self.assertTrue(
            any("must name a page and a fragment" in error for error in errors), errors
        )

    def test_an_unknown_disposition_turns_the_gate_red(self) -> None:
        ledger = json.loads(json.dumps(LEDGER))
        ledger["sections"][0]["disposition"] = "deleted"
        errors = self.run_gates(ledger=ledger, which="ledger")
        self.assertTrue(
            any("is not one of" in error for error in errors), errors
        )

    def test_a_ledger_row_without_a_meaning_turns_the_gate_red(self) -> None:
        """The number alone does not say what the section used to oblige."""
        ledger = json.loads(json.dumps(LEDGER))
        ledger["sections"][0]["meaning"] = "  "
        errors = self.run_gates(ledger=ledger, which="ledger")
        self.assertTrue(
            any("no recorded meaning" in error for error in errors), errors
        )

    def test_a_duplicated_ledger_row_turns_the_gate_red(self) -> None:
        ledger = json.loads(json.dumps(LEDGER))
        ledger["sections"].append(json.loads(json.dumps(ledger["sections"][0])))
        errors = self.run_gates(ledger=ledger, which="ledger")
        self.assertTrue(
            any("duplicate ledger row" in error for error in errors), errors
        )


if __name__ == "__main__":
    unittest.main()
