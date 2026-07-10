#!/usr/bin/env python3
"""Lint Arkret prose specification (`spec/v1/zh/**/*.md`).

P0/P1 checks aligned with `_improve.md`:

- Frontmatter must declare title / status / normative / stability / updated.
- Normative documents should reference `conformance/normative-language.md`
  for RFC 2119 keywords (warning, not error).
- Second-person pronouns ("你 / 你的 / 我们") flagged as style violations.
- Casual section titles ("一句话理解 / 速查 / 读图要点 / 先读路径") flagged.
- Internal link style: `[file.md §N.M](path)` preferred; bare relative paths
  in body text flagged as warnings.
- Mixed half-width punctuation in Chinese-language paragraphs (`,` `;`
  surrounded by CJK chars) reported.

Usage:

    python tools/lint_spec.py              # lint default spec tree, summary
    python tools/lint_spec.py --strict     # exit non-zero on warnings
    python tools/lint_spec.py path/to.md   # lint a single file

The intent is incremental adoption — most rules emit warnings, frontmatter
gaps and unknown status values are errors.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import yaml
except ImportError:  # pragma: no cover - CI installs the dependency.
    yaml = None


ROOT = Path(__file__).resolve().parents[1]
SPEC_ZH = ROOT / "spec" / "v1" / "zh"
PROPOSALS = ROOT / "spec" / "v1" / "proposals"
OPENAPI = ROOT / "spec" / "v1" / "artifacts" / "openapi" / "arkret-service-api.openapi.yaml"

REQUIRED_FRONTMATTER = {"title", "status", "normative", "stability", "updated"}
ALLOWED_STATUS = {"draft", "candidate", "stable", "deprecated"}
ALLOWED_PROPOSAL_STATUS = {"draft", "review"}

SECOND_PERSON_RE = re.compile(r"[你您]的?|我们")

CASUAL_HEADING_PATTERNS = [
    r"一句话理解",
    r"一句话总结",
    r"不做什么",
    r"先读路径",
    r"读图要点",
    r"速查",
    r"一分钟实施",
]
CASUAL_HEADING_RE = re.compile(r"^#{1,6}\s.*(" + "|".join(CASUAL_HEADING_PATTERNS) + r")")

# Half-width comma / semicolon between two CJK characters: a punctuation
# mix-up rather than a code identifier.
MIXED_PUNCT_RE = re.compile(r"[一-鿿][,;][一-鿿]")
ARKRET_PATH_RE = re.compile(r"/_arkret/[A-Za-z0-9_./{}:*-]+")

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
PROPOSAL_FILE_RE = re.compile(r"^(?P<num>[0-9]{4})-[A-Za-z0-9_.-]+\.md$")
OLD_CHINESE_NORMATIVE_DISCLAIMER_RE = re.compile(r"中文.*(?:不构成规范要求|只供阅读理解)")
REQUIRED_CHINESE_NORMATIVE_ROWS = {
    "必须 / 要求": "`MUST` / `REQUIRED`",
    "只能 / 仅限": "`MUST`",
    "不得 / 禁止 / 不允许 / 不可": "`MUST NOT`",
    "不能": "`MUST NOT`",
    "应当 / 建议 / 推荐": "`SHOULD` / `RECOMMENDED`",
    "不应 / 不建议 / 不推荐": "`SHOULD NOT` / `NOT RECOMMENDED`",
    "可以 / 可选": "`MAY` / `OPTIONAL`",
}
NORMATIVE_KEYWORD_PATTERNS = {
    "MUST NOT": [
        re.compile(r"\bMUST NOT\b"),
        re.compile(r"不得|禁止|不允许|不可|不能"),
    ],
    "MUST": [
        re.compile(r"\bMUST\b(?!\s+NOT)|\bREQUIRED\b|\bSHALL\b(?!\s+NOT)"),
        re.compile(r"必须|要求|只能|仅限"),
    ],
    "SHOULD NOT": [
        re.compile(r"\b(?:SHOULD NOT|NOT RECOMMENDED)\b"),
        re.compile(r"不应|不建议|不推荐"),
    ],
    "SHOULD": [
        re.compile(r"\bSHOULD\b(?!\s+NOT)|(?<!NOT\s)\bRECOMMENDED\b"),
        re.compile(r"应当|(?<!不)建议|(?<!不)推荐"),
    ],
    "MAY": [
        re.compile(r"\b(?:MAY|OPTIONAL)\b"),
        re.compile(r"可以|可选"),
    ],
}
NORMATIVE_KEYWORD_ORDER = ["MUST NOT", "MUST", "SHOULD NOT", "SHOULD", "MAY"]


@dataclass
class Finding:
    path: Path
    line: int
    code: str
    message: str
    level: str  # "error" | "warn"

    def format(self, root: Path) -> str:
        resolved = self.path.resolve()
        try:
            rel = resolved.relative_to(root)
            rel_str = rel.as_posix()
        except ValueError:
            rel_str = resolved.as_posix()
        return f"{rel_str}:{self.line}: [{self.level}] {self.code} {self.message}"


def parse_frontmatter(text: str) -> tuple[dict | None, int]:
    """Return (frontmatter dict, line offset to body)."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, 0
    if yaml is None:
        return {}, match.group(0).count("\n")
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        data = {}
    return data, match.group(0).count("\n")


def load_registered_arkret_paths() -> set[str]:
    if yaml is None or not OPENAPI.exists():
        return set()
    try:
        data = yaml.safe_load(OPENAPI.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return set()
    paths = data.get("paths")
    if not isinstance(paths, dict):
        return set()
    return {str(path) for path in paths}


REGISTERED_ARKRET_PATHS = load_registered_arkret_paths()


def normalize_arkret_path_token(token: str) -> str:
    return token.rstrip(".,;:，。；：）)]】>")


def is_local_see_also_target(value: str) -> bool:
    return not (
        value.startswith("#")
        or value.startswith("http://")
        or value.startswith("https://")
        or value.startswith("mailto:")
    )


def see_also_target_path(path: Path, value: str) -> Path:
    target = value.split("#", 1)[0].split("?", 1)[0]
    return (path.parent / target).resolve()


def is_registered_arkret_path_or_namespace(token: str) -> bool:
    if token == "/_arkret/_conformance/*" or token.startswith("/_arkret/_conformance/"):
        return True
    if token in REGISTERED_ARKRET_PATHS:
        return True
    without_trailing_slash = token.rstrip("/")
    if without_trailing_slash in REGISTERED_ARKRET_PATHS:
        return True
    if token.endswith("*"):
        return any(path.startswith(token[:-1]) for path in REGISTERED_ARKRET_PATHS)
    if token.endswith("/"):
        return any(path.startswith(token) for path in REGISTERED_ARKRET_PATHS)
    return False


def lint_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    text = path.read_text(encoding="utf-8")
    fm, body_offset = parse_frontmatter(text)

    if fm is None:
        findings.append(Finding(path, 1, "FM001", "missing frontmatter", "error"))
        fm = {}

    missing = REQUIRED_FRONTMATTER - set(fm.keys())
    for key in sorted(missing):
        findings.append(
            Finding(path, 1, "FM002", f"frontmatter missing field '{key}'", "error")
        )

    status = fm.get("status")
    if status is not None and status not in ALLOWED_STATUS:
        findings.append(
            Finding(
                path,
                1,
                "FM003",
                f"frontmatter status '{status}' not in {sorted(ALLOWED_STATUS)}",
                "error",
            )
        )

    is_normative = bool(fm.get("normative"))
    see_also = fm.get("see_also")
    if see_also is not None:
        if not isinstance(see_also, list) or any(not isinstance(item, str) for item in see_also):
            findings.append(
                Finding(path, 1, "FM004", "frontmatter see_also must be a list of strings", "error")
            )
        else:
            for item in see_also:
                if not is_local_see_also_target(item):
                    continue
                target_path = see_also_target_path(path, item)
                try:
                    target_path.relative_to(ROOT)
                except ValueError:
                    findings.append(
                        Finding(path, 1, "FM005", f"see_also target escapes repository: {item}", "error")
                    )
                    continue
                if not target_path.exists():
                    findings.append(
                        Finding(path, 1, "FM006", f"see_also target does not exist relative to document: {item}", "error")
                    )

    is_self_normative_language = path.name == "normative-language.md"
    if is_normative and not is_self_normative_language and "normative-language.md" not in text:
        findings.append(
            Finding(
                path,
                1,
                "NL001",
                "normative doc should reference conformance/normative-language.md",
                "warn",
            )
        )
    if OLD_CHINESE_NORMATIVE_DISCLAIMER_RE.search(text):
        findings.append(
            Finding(
                path,
                1,
                "NL002",
                "old Chinese normative-keyword disclaimer found; Chinese normative keywords are registered in normative-language.md",
                "error",
            )
        )
    if is_self_normative_language:
        for chinese_terms, rfc_terms in REQUIRED_CHINESE_NORMATIVE_ROWS.items():
            if chinese_terms not in text or rfc_terms not in text:
                findings.append(
                    Finding(
                        path,
                        1,
                        "NL003",
                        f"normative-language.md must register {chinese_terms} as {rfc_terms}",
                        "error",
                    )
                )

    for idx, raw in enumerate(text.splitlines(), start=1):
        # Skip lines inside fenced code blocks heuristically: tracked below.
        pass

    in_code = False
    pending_ignore: set[str] = set()
    for idx, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        # Skip frontmatter range.
        if idx <= body_offset:
            continue

        # "<!-- lint-ignore: CODE,CODE -->" on its own line applies to the next
        # non-blank, non-comment content line. Same-line comments apply to
        # that line.
        ignore_match = re.search(r"<!--\s*lint-ignore:\s*([A-Z0-9, ]+?)(?:\s*[—–-]\s.*?)?\s*-->", raw)
        same_line_codes: set[str] = set()
        if ignore_match:
            codes = {c.strip() for c in ignore_match.group(1).split(",")}
            stripped_no_comment = re.sub(r"<!--.*?-->", "", raw).strip()
            if stripped_no_comment:
                same_line_codes = codes
            else:
                pending_ignore |= codes
                continue

        ignored = same_line_codes | pending_ignore
        if stripped:
            pending_ignore = set()

        if CASUAL_HEADING_RE.match(raw):
            findings.append(
                Finding(
                    path,
                    idx,
                    "ST001",
                    f"casual heading: '{raw.strip()}' — use a normative noun phrase",
                    "warn",
                )
            )

        # Strip inline code spans before second-person / punctuation checks.
        scrubbed = re.sub(r"`[^`]*`", "", raw)

        if "ST002" not in ignored and SECOND_PERSON_RE.search(scrubbed):
            findings.append(
                Finding(
                    path,
                    idx,
                    "ST002",
                    "second-person pronoun in prose (use third-person / passive)",
                    "warn",
                )
            )

        if "PU001" not in ignored and MIXED_PUNCT_RE.search(scrubbed):
            findings.append(
                Finding(
                    path,
                    idx,
                    "PU001",
                    "half-width ',' or ';' between CJK characters",
                    "warn",
                )
            )

        if "CW001" not in ignored:
            path_scan_text = re.sub(r"<!--.*?-->", "", raw)
            for match in ARKRET_PATH_RE.finditer(path_scan_text):
                token = normalize_arkret_path_token(match.group(0))
                if not is_registered_arkret_path_or_namespace(token):
                    findings.append(
                        Finding(
                            path,
                            idx,
                            "CW001",
                            f"unregistered /_arkret path '{token}' in current-v1 prose",
                            "error",
                        )
                    )

    return findings


def count_normative_keywords(path: Path) -> Counter[str]:
    text = path.read_text(encoding="utf-8")
    _, body_offset = parse_frontmatter(text)
    counts: Counter[str] = Counter()
    in_code = False

    for idx, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or idx <= body_offset:
            continue
        scrubbed = re.sub(r"`[^`]*`", "", raw)
        for keyword, patterns in NORMATIVE_KEYWORD_PATTERNS.items():
            for pattern in patterns:
                counts[keyword] += len(pattern.findall(scrubbed))

    return counts


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def is_proposal_file(path: Path) -> bool:
    return is_relative_to(path, PROPOSALS) and PROPOSAL_FILE_RE.match(path.name) is not None


def lint_proposal_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    text = path.read_text(encoding="utf-8")
    fm, _body_offset = parse_frontmatter(text)

    if fm is None:
        findings.append(Finding(path, 1, "AKP004", "proposal missing frontmatter", "error"))
        fm = {}

    status = fm.get("status")
    if status is not None and status not in ALLOWED_PROPOSAL_STATUS:
        findings.append(
            Finding(
                path,
                1,
                "AKP005",
                f"proposal status '{status}' not in {sorted(ALLOWED_PROPOSAL_STATUS)}",
                "error",
            )
        )

    match = PROPOSAL_FILE_RE.match(path.name)
    expected_akp = f"AKP-{match.group('num')}" if match else None
    actual_akp = fm.get("akp")
    if expected_akp is not None and actual_akp != expected_akp:
        findings.append(
            Finding(
                path,
                1,
                "AKP003",
                f"proposal akp '{actual_akp}' does not match filename '{expected_akp}'",
                "error",
            )
        )

    if status == "review" and not fm.get("discussion"):
        findings.append(
            Finding(
                path,
                1,
                "AKP001",
                "review status MUST carry a discussion: frontmatter link",
                "warn",
            )
        )

    return findings


def iter_targets(paths: Iterable[Path]) -> Iterable[Path]:
    for entry in paths:
        if entry.is_dir():
            yield from sorted(entry.rglob("*.md"))
        elif entry.suffix == ".md":
            yield entry


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Lint Arkret prose spec.")
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[SPEC_ZH, PROPOSALS],
        help="Files or directories to lint (default: spec/v1/zh and spec/v1/proposals).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on warnings as well as errors.",
    )
    parser.add_argument(
        "--keyword-stats",
        action="store_true",
        help="Print RFC 2119 keyword counts with Chinese normative aliases normalized.",
    )
    args = parser.parse_args(argv)

    all_findings: list[Finding] = []
    targets = list(iter_targets(args.paths))
    for target in targets:
        if is_proposal_file(target):
            all_findings.extend(lint_proposal_file(target))
        elif is_relative_to(target, PROPOSALS):
            continue
        else:
            all_findings.extend(lint_file(target))

    for finding in all_findings:
        print(finding.format(ROOT))

    if args.keyword_stats:
        counts: Counter[str] = Counter()
        for target in targets:
            if is_relative_to(target, PROPOSALS):
                continue
            counts.update(count_normative_keywords(target))
        print("\nNormative keyword counts (English + Chinese aliases normalized):")
        for keyword in NORMATIVE_KEYWORD_ORDER:
            print(f"{keyword}: {counts[keyword]}")

    errors = sum(1 for f in all_findings if f.level == "error")
    warnings = sum(1 for f in all_findings if f.level == "warn")
    print(f"\n{errors} error(s), {warnings} warning(s)")

    if errors:
        return 1
    if args.strict and warnings:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
