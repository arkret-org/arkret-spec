#!/usr/bin/env python3
"""Unified artifact maintenance pipeline for Contrix spec."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
REGISTRY = ARTIFACTS / "registry"
CONTRACT_CATALOG_PATH = REGISTRY / "contract-catalog.json"
MIRROR_MANIFEST_PATH = REGISTRY / "mirror-manifest.json"
LEGACY_POLICY_PATH = REGISTRY / "legacy-compatibility-policy.json"
LINT_SCRIPT = ARTIFACTS / "lint_artifacts.py"
ALLOWED_LEGACY_PATHS = {
    LEGACY_POLICY_PATH.resolve(),
    (ROOT / "zh" / "guides" / "legacy-subject-room-card-to-flow-migration.md").resolve(),
}
TEXT_SUFFIXES = {".json", ".yaml", ".yml", ".md", ".py", ".toml", ".txt"}
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "
"


def load_contract_catalog() -> dict[str, Any]:
    data = load_json(CONTRACT_CATALOG_PATH)
    if not isinstance(data, dict):
        raise SystemExit(f"invalid contract catalog: {CONTRACT_CATALOG_PATH}")
    return data


def generated_registry_payloads(catalog: dict[str, Any]) -> dict[Path, dict[str, Any]]:
    version = catalog.get("version")
    generated = catalog.get("generated_registries")
    if not isinstance(version, str) or not version:
        raise SystemExit("contract catalog missing version")
    if not isinstance(generated, list) or not generated:
        raise SystemExit("contract catalog missing generated_registries")

    payloads: dict[Path, dict[str, Any]] = {}
    for row in generated:
        if not isinstance(row, dict):
            raise SystemExit("generated_registries rows must be objects")
        file_ref = row.get("file")
        section = row.get("section")
        if not isinstance(file_ref, str) or not file_ref:
            raise SystemExit("generated registry missing file")
        if not isinstance(section, str) or not section:
            raise SystemExit(f"generated registry {file_ref} missing section")
        section_payload = catalog.get(section)
        if not isinstance(section_payload, dict):
            raise SystemExit(f"contract catalog missing section {section}")
        payloads[ARTIFACTS / file_ref] = {
            "version": version,
            "source_of_truth": False,
            "generated_from": "registry/contract-catalog.json",
            "generated_by": "tools/artifact_pipeline.py",
            **section_payload,
        }
    return payloads


def write_generated_registries() -> None:
    for path, payload in generated_registry_payloads(load_contract_catalog()).items():
        path.write_text(dump_json(payload), encoding="utf-8")
        print(f"updated {path.relative_to(ROOT).as_posix()}")


def check_generated_registries() -> list[str]:
    errors: list[str] = []
    for path, payload in generated_registry_payloads(load_contract_catalog()).items():
        expected = dump_json(payload)
        if not path.exists():
            errors.append(f"missing generated registry {path.relative_to(ROOT).as_posix()}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            errors.append(
                f"generated registry drift: {path.relative_to(ROOT).as_posix()} (run python tools/artifact_pipeline.py generate)"
            )
    return errors


def load_mirror_manifest() -> list[dict[str, str]]:
    data = load_json(MIRROR_MANIFEST_PATH)
    mirrors = data.get("mirrors")
    if not isinstance(mirrors, list) or not mirrors:
        raise SystemExit("mirror-manifest.json missing mirrors")
    return mirrors


def sync_file(canonical: Path, mirror: Path) -> None:
    mirror.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(canonical, mirror)


def sync_tree(canonical: Path, mirror: Path) -> None:
    if mirror.exists():
        for candidate in sorted(mirror.rglob("*"), reverse=True):
            if candidate.is_file():
                candidate.unlink()
            elif candidate.is_dir():
                try:
                    candidate.rmdir()
                except OSError:
                    pass
    mirror.mkdir(parents=True, exist_ok=True)
    for source in sorted(canonical.rglob("*")):
        rel = source.relative_to(canonical)
        dest = mirror / rel
        if source.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)


def sync_mirrors() -> None:
    for row in load_mirror_manifest():
        canonical = ROOT / row["canonical"]
        mirror = ROOT / row["mirror"]
        mode = row["mode"]
        if mode == "tree":
            sync_tree(canonical, mirror)
        else:
            sync_file(canonical, mirror)
        print(f"synced {mirror.relative_to(ROOT).as_posix()}")


def compare_tree(canonical: Path, mirror: Path, label: str) -> list[str]:
    errors: list[str] = []
    canonical_files = {
        path.relative_to(canonical).as_posix(): path
        for path in canonical.rglob("*")
        if path.is_file()
    }
    mirror_files = {
        path.relative_to(mirror).as_posix(): path
        for path in mirror.rglob("*")
        if path.is_file()
    }
    for name in sorted(canonical_files.keys() - mirror_files.keys()):
        errors.append(f"{label} mirror missing {name}")
    for name in sorted(mirror_files.keys() - canonical_files.keys()):
        errors.append(f"{label} mirror has extra file {name}")
    for name in sorted(canonical_files.keys() & mirror_files.keys()):
        if canonical_files[name].read_bytes() != mirror_files[name].read_bytes():
            errors.append(f"{label} mirror differs for {name}")
    return errors


def check_mirrors() -> list[str]:
    errors: list[str] = []
    for row in load_mirror_manifest():
        canonical = ROOT / row["canonical"]
        mirror = ROOT / row["mirror"]
        label = row["label"]
        mode = row["mode"]
        if not mirror.exists():
            errors.append(f"{label} mirror missing: {row['mirror']}")
            continue
        if mode == "tree":
            errors.extend(compare_tree(canonical, mirror, label))
        elif canonical.read_bytes() != mirror.read_bytes():
            errors.append(f"{label} mirror differs: {row['mirror']}")
    return errors


def load_legacy_policy() -> dict[str, Any]:
    data = load_json(LEGACY_POLICY_PATH)
    if not isinstance(data, dict):
        raise SystemExit("invalid legacy compatibility policy")
    return data


def collect_legacy_guard_inputs(policy: dict[str, Any]) -> tuple[list[str], list[str]]:
    patterns: list[str] = []
    removed_files: list[str] = []
    families = policy.get("contract_families")
    if not isinstance(families, list):
        raise SystemExit("legacy compatibility policy missing contract_families")
    for family in families:
        if not isinstance(family, dict):
            continue
        if family.get("current_phase") == "active":
            continue
        patterns.extend(pattern for pattern in family.get("forbidden_patterns", []) if isinstance(pattern, str) and pattern)
        removed_files.extend(path for path in family.get("removed_contract_files", []) if isinstance(path, str) and path)
    return sorted(set(patterns)), sorted(set(removed_files))


def iter_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != "README.md":
            continue
        yield path


def check_legacy_contracts() -> list[str]:
    policy = load_legacy_policy()
    patterns, removed_files = collect_legacy_guard_inputs(policy)
    errors: list[str] = []
    for rel in removed_files:
        if (ROOT / rel).exists():
            errors.append(f"removed legacy contract file reintroduced: {rel}")
    for path in iter_text_files():
        if path.resolve() in ALLOWED_LEGACY_PATHS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in patterns:
            if pattern in text:
                errors.append(
                    f"forbidden legacy pattern {pattern!r} in {path.relative_to(ROOT).as_posix()}"
                )
                break
    return errors


def run_lint() -> int:
    result = subprocess.run([sys.executable, str(LINT_SCRIPT)], cwd=ROOT)
    return result.returncode


def cmd_generate(_: argparse.Namespace) -> int:
    write_generated_registries()
    return 0


def cmd_sync(_: argparse.Namespace) -> int:
    sync_mirrors()
    return 0


def cmd_check(_: argparse.Namespace) -> int:
    errors: list[str] = []
    errors.extend(check_generated_registries())
    errors.extend(check_legacy_contracts())
    errors.extend(check_mirrors())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return run_lint()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="regenerate derived registries from contract-catalog.json")
    generate_parser.set_defaults(func=cmd_generate)

    sync_parser = subparsers.add_parser("sync", help="sync canonical artifacts into zh/ mirrors")
    sync_parser.set_defaults(func=cmd_sync)

    check_parser = subparsers.add_parser("check", help="check generated registries, legacy guards, mirrors, and artifact lint")
    check_parser.set_defaults(func=cmd_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
