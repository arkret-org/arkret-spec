from __future__ import annotations

import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "artifacts" / "registry" / "legacy-compatibility-policy.json"
TEXT_SUFFIXES = {".json", ".md", ".yaml", ".yml"}
EXCLUDED = {
    Path("tools/check_no_legacy_contracts.py"),
    Path("artifacts/registry/legacy-compatibility-policy.json"),
    Path("zh/guides/legacy-subject-room-card-to-flow-migration.md"),
}


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if rel in EXCLUDED:
            continue
        if any(part.startswith(".git") for part in rel.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        files.append(path)
    return files


def load_policy() -> dict[str, object]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def main() -> int:
    policy = load_policy()
    families = policy.get("contract_families", [])
    forbidden_patterns: list[str] = []
    removed_contract_files: list[str] = []
    if isinstance(families, list):
        for family in families:
            if not isinstance(family, dict):
                continue
            if family.get("current_phase") == "active":
                continue
            patterns = family.get("forbidden_patterns", [])
            files = family.get("removed_contract_files", [])
            if isinstance(patterns, list):
                forbidden_patterns.extend(pattern for pattern in patterns if isinstance(pattern, str) and pattern)
            if isinstance(files, list):
                removed_contract_files.extend(file_ref for file_ref in files if isinstance(file_ref, str) and file_ref)

    patterns = [
        (pattern, re.compile(re.escape(pattern)))
        for pattern in dict.fromkeys(forbidden_patterns)
    ]
    findings: list[str] = []

    for file_ref in dict.fromkeys(removed_contract_files):
        path = ROOT / file_ref
        if path.exists():
            findings.append(f"{file_ref}: removed contract file exists")

    for path in iter_text_files():
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern_text, pattern in patterns:
                match = pattern.search(line)
                if not match:
                    continue
                snippet = line.strip()
                findings.append(f"{rel}:{lineno}: forbidden pattern {pattern_text!r}: {snippet}")

    if findings:
        print("Removed legacy contracts were reintroduced:")
        for finding in findings:
            print(f"  {finding}")
        return 1

    print("No removed legacy contracts were found in non-active contract families.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
