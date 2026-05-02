from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIRROR_MANIFEST_PATH = ROOT / "artifacts" / "registry" / "mirror-manifest.json"
LEGACY_POLICY_PATH = ROOT / "artifacts" / "registry" / "legacy-compatibility-policy.json"
LINT_SCRIPT_PATH = ROOT / "artifacts" / "lint_artifacts.py"
TEXT_SUFFIXES = {".json", ".md", ".yaml", ".yml"}
LEGACY_SCAN_EXCLUDED = {
    Path("tools/artifact_pipeline.py"),
    Path("artifacts/registry/legacy-compatibility-policy.json"),
    Path("zh/guides/legacy-subject-room-card-to-flow-migration.md"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unified maintenance pipeline for Contrix machine artifacts.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("sync", help="Sync derived zh/ machine-artifact mirrors from canonical artifacts/.")
    subparsers.add_parser("check", help="Run mirror checks, legacy guards, and artifact lint in one pipeline.")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_tree_files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file()
    }


def load_mirror_manifest() -> list[dict[str, Path | str]]:
    data = load_json(MIRROR_MANIFEST_PATH)
    rows = data.get("mirrors")
    if not isinstance(rows, list):
        raise ValueError("mirror manifest must contain a mirrors list")

    manifest: list[dict[str, Path | str]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("mirror manifest entries must be objects")
        label = row.get("label")
        mode = row.get("mode")
        canonical = row.get("canonical")
        mirror = row.get("mirror")
        if not all(isinstance(value, str) and value for value in (label, mode, canonical, mirror)):
            raise ValueError("mirror manifest entries require non-empty label/mode/canonical/mirror strings")
        manifest.append(
            {
                "label": label,
                "mode": mode,
                "canonical": ROOT / canonical,
                "mirror": ROOT / mirror,
            }
        )
    return manifest


def sync_file(label: str, canonical: Path, mirror: Path, check: bool, changes: list[str]) -> None:
    if not canonical.exists():
        raise FileNotFoundError(f"canonical {label} file is missing: {canonical}")
    if not mirror.exists() or canonical.read_bytes() != mirror.read_bytes():
        changes.append(f"{label}: {mirror.relative_to(ROOT).as_posix()}")
        if not check:
            mirror.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(canonical, mirror)


def sync_tree(label: str, canonical: Path, mirror: Path, check: bool, changes: list[str]) -> None:
    if not canonical.exists():
        raise FileNotFoundError(f"canonical {label} tree is missing: {canonical}")

    canonical_files = iter_tree_files(canonical)
    mirror_files = iter_tree_files(mirror) if mirror.exists() else {}

    for rel_path in sorted(canonical_files.keys() - mirror_files.keys()):
        changes.append(f"{label}: add {mirror.relative_to(ROOT).as_posix()}/{rel_path}")
        if not check:
            target = mirror / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(canonical_files[rel_path], target)

    for rel_path in sorted(mirror_files.keys() - canonical_files.keys()):
        changes.append(f"{label}: remove {mirror.relative_to(ROOT).as_posix()}/{rel_path}")
        if not check:
            (mirror / rel_path).unlink()

    for rel_path in sorted(canonical_files.keys() & mirror_files.keys()):
        if canonical_files[rel_path].read_bytes() == mirror_files[rel_path].read_bytes():
            continue
        changes.append(f"{label}: update {mirror.relative_to(ROOT).as_posix()}/{rel_path}")
        if not check:
            target = mirror / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(canonical_files[rel_path], target)

    if not check and mirror.exists():
        for path in sorted(mirror.rglob("*"), reverse=True):
            if path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass


def run_mirror_sync(check: bool) -> int:
    changes: list[str] = []
    for row in load_mirror_manifest():
        label = str(row["label"])
        mode = str(row["mode"])
        canonical = Path(row["canonical"])
        mirror = Path(row["mirror"])
        if mode == "file":
            sync_file(label, canonical, mirror, check, changes)
        elif mode == "tree":
            sync_tree(label, canonical, mirror, check, changes)
        else:
            raise ValueError(f"unsupported mirror mode {mode!r}")

    if check:
        if changes:
            print("zh mirror drift detected:")
            for change in changes:
                print(f"  {change}")
            return 1
        print("zh mirrors are in sync with canonical artifacts.")
        return 0

    if changes:
        print("Synced zh mirrors from canonical artifacts:")
        for change in changes:
            print(f"  {change}")
    else:
        print("zh mirrors were already in sync with canonical artifacts.")
    return 0


def iter_legacy_scan_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if rel in LEGACY_SCAN_EXCLUDED:
            continue
        if any(part.startswith(".git") for part in rel.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        files.append(path)
    return files


def run_legacy_guard() -> int:
    policy = load_json(LEGACY_POLICY_PATH)
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

    regexes = [(pattern, re.compile(re.escape(pattern))) for pattern in dict.fromkeys(forbidden_patterns)]
    findings: list[str] = []

    for file_ref in dict.fromkeys(removed_contract_files):
        path = ROOT / file_ref
        if path.exists():
            findings.append(f"{file_ref}: removed contract file exists")

    for path in iter_legacy_scan_files():
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern_text, regex in regexes:
                if not regex.search(line):
                    continue
                findings.append(f"{rel}:{lineno}: forbidden pattern {pattern_text!r}: {line.strip()}")

    if findings:
        print("Removed legacy contracts were reintroduced:")
        for finding in findings:
            print(f"  {finding}")
        return 1

    print("No removed legacy contracts were found in non-active contract families.")
    return 0


def run_artifact_lint() -> int:
    result = subprocess.run([sys.executable, str(LINT_SCRIPT_PATH)], cwd=ROOT)
    return result.returncode


def command_sync() -> int:
    return run_mirror_sync(check=False)


def command_check() -> int:
    steps = [
        ("mirror sync check", lambda: run_mirror_sync(check=True)),
        ("legacy contract guard", run_legacy_guard),
        ("artifact lint", run_artifact_lint),
    ]
    for label, runner in steps:
        exit_code = runner()
        if exit_code != 0:
            print(f"artifact pipeline failed during {label}.")
            return exit_code
    print("artifact pipeline check passed.")
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "sync":
        return command_sync()
    if args.command == "check":
        return command_check()
    raise ValueError(f"unsupported command {args.command!r}")


if __name__ == "__main__":
    sys.exit(main())
