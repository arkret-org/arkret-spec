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


def fixture_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        document = json.loads(data)
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return entries


def manifest() -> dict[str, Any]:
    return {
        "generated_from": ["spec/v1/artifacts/fixtures/*.json"],
        "generated_by": "tools/check_fixture_digests.py --write-reference",
        "files": fixture_entries(),
    }


def load_reference(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def compare(current: dict[str, Any], reference: dict[str, Any]) -> list[str]:
    for label, document in (("current", current), ("reference", reference)):
        rows = document.get("files", [])
        if any(set(row) != {"path", "sha256"} for row in rows):
            return [f"{label} fixture entries must contain only path and sha256"]
        if len({row["path"] for row in rows}) != len(rows):
            return [f"{label} repeats a fixture path"]
    current_files = {entry["path"]: entry for entry in current.get("files", [])}
    reference_files = {entry["path"]: entry for entry in reference.get("files", [])}

    failures: list[str] = []
    for path in sorted(reference_files.keys() - current_files.keys()):
        failures.append(f"missing fixture: {path}")
    for path in sorted(current_files.keys() - reference_files.keys()):
        failures.append(f"new fixture not in reference: {path}")
    for path in sorted(current_files.keys() & reference_files.keys()):
        if current_files[path].get("sha256") != reference_files[path].get("sha256"):
            failures.append(
                f"digest mismatch: {path} current={current_files[path].get('sha256')} "
                f"reference={reference_files[path].get('sha256')}"
            )
    return failures






def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--write-reference", action="store_true")
    args = parser.parse_args()

    try:
        current = manifest()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"fixture-digest-check: {exc}")
        return 1
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
