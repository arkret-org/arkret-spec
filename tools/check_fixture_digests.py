#!/usr/bin/env python3
"""Check spec fixture file digests against a reference manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "spec" / "v1" / "artifacts" / "fixtures"
DEFAULT_REFERENCE = ROOT / "spec" / "v1" / "artifacts" / "reports" / "fixture-digests.json"


def fixture_entries() -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        data = path.read_bytes()
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return entries


def manifest() -> dict[str, Any]:
    return {
        "schema": "arkret.fixture-digests.v1",
        "fixtures_root": "spec/v1/artifacts/fixtures",
        "hash": "sha256",
        "files": fixture_entries(),
    }


def load_reference(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def compare(current: dict[str, Any], reference: dict[str, Any]) -> list[str]:
    current_files = {entry["path"]: entry["sha256"] for entry in current.get("files", [])}
    reference_files = {entry["path"]: entry["sha256"] for entry in reference.get("files", [])}

    failures: list[str] = []
    for path in sorted(reference_files.keys() - current_files.keys()):
        failures.append(f"missing fixture: {path}")
    for path in sorted(current_files.keys() - reference_files.keys()):
        failures.append(f"new fixture not in reference: {path}")
    for path in sorted(current_files.keys() & reference_files.keys()):
        if current_files[path] != reference_files[path]:
            failures.append(
                f"digest mismatch: {path} current={current_files[path]} reference={reference_files[path]}"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--write-reference", action="store_true")
    args = parser.parse_args()

    current = manifest()
    if args.write_reference:
        args.reference.parent.mkdir(parents=True, exist_ok=True)
        with args.reference.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(f"wrote fixture digest reference: {args.reference}")
        return 0

    reference = load_reference(args.reference)
    failures = compare(current, reference)
    if failures:
        for failure in failures:
            print(f"fixture-digest-check: {failure}")
        return 1

    print(f"fixture-digest-check: {len(current['files'])} fixtures match {args.reference}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
