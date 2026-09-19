#!/usr/bin/env python3
"""Check spec fixture file digests against a reference manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "spec" / "v1" / "artifacts" / "fixtures"
DEFAULT_REFERENCE = ROOT / "spec" / "v1" / "artifacts" / "reports" / "fixture-digests.json"
DATED_VERSION_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:\.(\d+))?$")


def fixture_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        document = json.loads(data)
        version = document.get("version") if isinstance(document, dict) else None
        if not isinstance(version, (str, int)) or isinstance(version, bool):
            raise ValueError(f"{path}: fixture must carry a string or integer top-level version")
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "version": version,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return entries


def manifest() -> dict[str, Any]:
    return {
        "schema": "arkret.fixture-digests.v1",
        "source_of_truth": False,
        "generated_from": ["spec/v1/artifacts/fixtures/*.json"],
        "generated_by": "tools/check_fixture_digests.py --write-reference",
        "fixtures_root": "spec/v1/artifacts/fixtures",
        "hash": "sha256",
        "files": fixture_entries(),
    }


def load_reference(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def compare(current: dict[str, Any], reference: dict[str, Any]) -> list[str]:
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
        if (
            "version" in reference_files[path]
            and current_files[path].get("version") != reference_files[path].get("version")
        ):
            failures.append(
                f"version mismatch: {path} current={current_files[path].get('version')!r} "
                f"reference={reference_files[path].get('version')!r}"
            )
    return failures


def version_advanced(old: Any, new: Any) -> bool:
    if isinstance(old, int) and not isinstance(old, bool) and isinstance(new, int) and not isinstance(new, bool):
        return new > old
    if isinstance(old, str) and isinstance(new, str):
        old_match = DATED_VERSION_RE.fullmatch(old)
        new_match = DATED_VERSION_RE.fullmatch(new)
        if old_match and new_match:
            try:
                old_key = (date.fromisoformat(old_match.group(1)), int(old_match.group(2) or 0))
                new_key = (date.fromisoformat(new_match.group(1)), int(new_match.group(2) or 0))
            except ValueError:
                return False
            return new_key > old_key
        return new != old
    return False


def release_transition_errors(current: dict[str, Any], reference: dict[str, Any]) -> list[str]:
    """A fixture content edit and its version advance are one atomic release."""
    current_files = {entry["path"]: entry for entry in current.get("files", [])}
    reference_files = {entry["path"]: entry for entry in reference.get("files", [])}
    failures: list[str] = []
    for path in sorted(current_files.keys() & reference_files.keys()):
        old = reference_files[path]
        new = current_files[path]
        old_version = old.get("version")
        if old_version is None:
            # One-time migration from the v1 manifest that recorded only digests.
            continue
        changed = old.get("sha256") != new.get("sha256")
        version_changed = old_version != new.get("version")
        if changed and not version_advanced(old_version, new.get("version")):
            failures.append(f"fixture content changed without version advance: {path}")
        elif not changed and version_changed:
            failures.append(f"fixture version changed without content change: {path}")
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
        if args.reference.exists():
            failures = release_transition_errors(current, load_reference(args.reference))
            if failures:
                for failure in failures:
                    print(f"fixture-digest-check: {failure}")
                return 1
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
