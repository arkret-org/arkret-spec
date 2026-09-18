"""The artifact-to-prose section-reference gate, and the prose it made possible.

`patch.schema.json` declared itself the "canonical machine projection of
zh/models/event-and-patch.md §4.2.1" while that section, and the whole §4.2
patch-path block, had been deleted. The markdown link check only reads markdown
links, so a section number written into a canonical artifact's `description` was
never checked at all. These tests pin both halves: the restored grammar section,
and the gate that keeps the citation honest.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from artifact_lint.core import Lint
from artifact_lint.prose import (
    ARTIFACT_PROSE_SECTION_REF_EXEMPTIONS_PATH,
    _artifact_prose_section_citations,
    check_artifact_prose_section_refs,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec" / "v1"
ARTIFACTS = SPEC / "artifacts"
EVENT_AND_PATCH = SPEC / "zh" / "models" / "event-and-patch.md"
PATCH_SCHEMA = ARTIFACTS / "schemas" / "patch.schema.json"
ERROR_CODES = ARTIFACTS / "registry" / "error-code-registry.json"

HEADING_RE = re.compile(r"^#{1,6}\s+(\d+(?:\.\d+)*)(?:[.．]\s+|\s+|$)")


def numbered_sections(path: Path) -> set[str]:
    return {
        match.group(1)
        for match in map(HEADING_RE.match, path.read_text(encoding="utf-8").splitlines())
        if match
    }


def run_gate() -> list[str]:
    lint = Lint()
    check_artifact_prose_section_refs(lint)
    return lint.errors


class MutateFile:
    """Apply one substring replacement to a file, then restore it verbatim."""

    def __init__(self, path: Path, old: str, new: str) -> None:
        self.path = path
        self.old = old
        self.new = new

    def __enter__(self) -> "MutateFile":
        self.original = self.path.read_text(encoding="utf-8")
        assert self.old in self.original, f"mutation anchor missing in {self.path.name}"
        self.path.write_text(
            self.original.replace(self.old, self.new, 1), encoding="utf-8", newline="\n"
        )
        return self

    def __exit__(self, *exc: object) -> None:
        self.path.write_text(self.original, encoding="utf-8", newline="\n")


class ArtifactProseSectionRefGateTest(unittest.TestCase):
    def test_no_artifact_cites_a_section_that_does_not_exist(self) -> None:
        self.assertEqual([], run_gate())

    def test_a_stale_section_number_turns_the_gate_red(self) -> None:
        with MutateFile(
            ERROR_CODES,
            "See zh/models/event-and-patch.md §4.3.1.",
            "See zh/models/event-and-patch.md §4.9.1.",
        ):
            errors = run_gate()
        self.assertEqual(1, len(errors), errors)
        self.assertIn("§4.9.1", errors[0])
        self.assertIn("event-and-patch.md", errors[0])

    def test_a_bare_section_ref_inherits_the_last_named_file(self) -> None:
        # "models/common-fields.md section 2 ... section 9.8.3" was exactly the
        # shape that hid a reference to a different page's section.
        citations = list(
            _artifact_prose_section_citations(
                "the keyed-set union of models/common-fields.md section 2, "
                "and section 9.8.3 requires the audit view"
            )
        )
        self.assertEqual(
            [("models/common-fields.md", "2"), ("models/common-fields.md", "9.8.3")],
            citations,
        )

    def test_a_string_that_names_no_file_yields_no_citation(self) -> None:
        self.assertEqual(
            [], list(_artifact_prose_section_citations("see section 4.2.1 above"))
        )

    def test_generated_views_are_not_counted_as_separate_findings(self) -> None:
        # contract-registry.json is the source of truth; event-kind-registry.json
        # and schema-registry.json copy its notes. One stale citation must be one
        # finding, not three.
        generated = ARTIFACTS / "registry" / "event-kind-registry.json"
        document = json.loads(generated.read_text(encoding="utf-8"))
        self.assertIs(False, document.get("source_of_truth"))
        with MutateFile(
            ARTIFACTS / "registry" / "contract-registry.json",
            "crypto-media/media-and-blob.md section 6",
            "crypto-media/media-and-blob.md section 61",
        ):
            errors = run_gate()
        self.assertEqual(1, len(errors), errors)
        self.assertIn("contract-registry.json", errors[0])


class ExemptionLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = json.loads(
            ARTIFACT_PROSE_SECTION_REF_EXEMPTIONS_PATH.read_text(encoding="utf-8")
        )

    def test_every_entry_names_a_reason_and_an_owning_report(self) -> None:
        self.assertTrue(self.ledger["exemptions"])
        for entry in self.ledger["exemptions"]:
            for key in ("artifact", "target", "section", "reason", "owner_report"):
                self.assertTrue(entry.get(key), (key, entry))
            self.assertGreater(len(entry["reason"]), 80, entry["artifact"])

    def test_every_exempted_citation_is_really_broken(self) -> None:
        """An exemption may only cover a citation the gate would otherwise fail.

        Otherwise the ledger silently accumulates rows that no longer describe
        anything, and the shrink-only ratchet stops meaning what it says.
        """
        for entry in self.ledger["exemptions"]:
            target = SPEC / entry["target"]
            self.assertTrue(target.is_file(), entry["target"])
            self.assertNotIn(
                str(entry["section"]),
                numbered_sections(target),
                f"{entry['target']} now has §{entry['section']}; "
                "remove the exemption instead of keeping it",
            )

    def test_dropping_an_exemption_turns_the_gate_red(self) -> None:
        with MutateFile(
            ARTIFACT_PROSE_SECTION_REF_EXEMPTIONS_PATH,
            '"exemptions": [',
            '"exemptions": [] , "retired_exemptions": [',
        ):
            errors = run_gate()
        self.assertEqual(len(self.ledger["exemptions"]), len(errors), errors)


class RestoredPatchPathGrammarTest(unittest.TestCase):
    def setUp(self) -> None:
        self.prose = EVENT_AND_PATCH.read_text(encoding="utf-8")
        self.sections = numbered_sections(EVENT_AND_PATCH)
        self.schema = json.loads(PATCH_SCHEMA.read_text(encoding="utf-8"))

    def test_the_grammar_section_the_schema_projects_exists_again(self) -> None:
        for section in ("4.2", "4.2.1", "4.2.2", "4.2.3"):
            self.assertIn(section, self.sections)
        self.assertIn("ABNF", self.prose)

    def test_the_schema_pattern_and_the_prose_state_the_same_bounds(self) -> None:
        property_names = self.schema["propertyNames"]
        self.assertEqual(
            "^[a-z][a-z0-9_]{0,63}(\\.[a-z][a-z0-9_]{0,63}){0,15}$",
            property_names["pattern"],
        )
        self.assertEqual(1024, property_names["maxLength"])
        self.assertIn("`^[a-z][a-z0-9_]{0,63}$`", self.prose)
        self.assertIn("path 最多 16 段，UTF-8 编码后最多 1024 bytes", self.prose)

    def test_the_prose_keeps_the_three_rules_no_regex_can_express(self) -> None:
        self.assertIn("reason_code=patch_path_invalid", self.prose)
        self.assertIn("MUST NOT 走 fallback 路径", self.prose)
        self.assertIn("无 stable-key 列表元素", self.prose)

    def test_the_prose_and_the_schema_point_at_each_other(self) -> None:
        self.assertIn("patch.schema.json", self.prose)
        self.assertIn(
            "zh/models/event-and-patch.md §4.2.1",
            self.schema["propertyNames"]["$comment"],
        )

    def test_atomicity_is_claimed_by_exactly_one_section(self) -> None:
        """§4.3.1 already owned patch atomicity; §4.4 must not be re-added."""
        self.assertIn("4.3.1", self.sections)
        self.assertNotIn("4.4", self.sections)
        self.assertEqual(
            1, self.prose.count("单次原子写入"), "patch atomicity has two prose homes"
        )


if __name__ == "__main__":
    unittest.main()
