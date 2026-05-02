from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".json", ".md", ".yaml", ".yml"}
EXCLUDED = {
    Path("tools/check_no_legacy_contracts.py"),
    Path("artifacts/registry/legacy-compatibility-policy.json"),
    Path("zh/guides/legacy-subject-room-card-to-flow-migration.md"),
}
PATTERNS = {
    "legacy typed ID": re.compile(r"cx:(subject|room|card):"),
    "legacy event kind": re.compile(r"cx\.(subject|room|card)\."),
    "legacy schema ID": re.compile(r"cx\.schema\.(subject|room|card)\.v1"),
    "legacy schema file": re.compile(r"(subject|room|card)\.schema\.json"),
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


def main() -> int:
    findings: list[str] = []

    for path in iter_text_files():
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, pattern in PATTERNS.items():
                match = pattern.search(line)
                if not match:
                    continue
                snippet = line.strip()
                findings.append(f"{rel}:{lineno}: {label}: {snippet}")

    if findings:
        print("Removed legacy contracts were reintroduced:")
        for finding in findings:
            print(f"  {finding}")
        return 1

    print("No removed legacy subject/room/card contracts were found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
