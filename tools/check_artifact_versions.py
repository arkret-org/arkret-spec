#!/usr/bin/env python3
"""Detect artifact content drift without a corresponding metadata advance."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
REFERENCE = ARTIFACTS / "reports" / "artifact-version-digests.json"
DATE_VERSION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def artifact_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    paths = [
        *(ARTIFACTS / "registry").glob("*.json"),
        *(ARTIFACTS / "profiles").glob("*.json"),
    ]
    for path in sorted(paths):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "version" not in data:
            continue
        version = data.get("version")
        generated_at = data.get("generated_at")
        if not isinstance(version, (str, int)) or isinstance(version, bool):
            raise ValueError(f"{path}: top-level version must be a string or integer")
        if generated_at is not None and not isinstance(generated_at, str):
            raise ValueError(f"{path}: top-level generated_at must be a string")
        if isinstance(version, str) and DATE_VERSION_RE.fullmatch(version) and generated_at:
            try:
                parsed = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"{path}: generated_at must be RFC3339") from exc
            if parsed.date().isoformat() != version:
                raise ValueError(f"{path}: generated_at date must match date version")
        content = {key: value for key, value in data.items() if key not in {"version", "generated_at"}}
        rows.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "version": version,
                "generated_at": generated_at,
                "content_digest": "sha256:" + hashlib.sha256(canonical_json(content)).hexdigest(),
            }
        )
    return rows


def version_advanced(old: Any, new: Any) -> bool:
    if isinstance(old, int) and isinstance(new, int):
        return new > old
    if isinstance(old, str) and isinstance(new, str):
        if DATE_VERSION_RE.fullmatch(old) and DATE_VERSION_RE.fullmatch(new):
            return new > old
        return new != old
    return False


def generated_at_advanced(old: str | None, new: str | None) -> bool:
    if old is None and new is None:
        return True
    if old is None and isinstance(new, str):
        return True
    if not isinstance(old, str) or not isinstance(new, str):
        return False
    try:
        old_dt = datetime.fromisoformat(old.replace("Z", "+00:00"))
        new_dt = datetime.fromisoformat(new.replace("Z", "+00:00"))
    except ValueError:
        return False
    return new_dt > old_dt


def load_reference() -> dict[str, Any] | None:
    if not REFERENCE.exists():
        return None
    data = json.loads(REFERENCE.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format_version") != 1:
        raise ValueError(f"{REFERENCE}: unsupported reference format")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-reference",
        action="store_true",
        help="write the current metadata/content reference after validating advances",
    )
    args = parser.parse_args(argv)

    try:
        rows = artifact_rows()
        current = {"format_version": 1, "artifacts": rows}
        previous = load_reference()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"artifact version check failed: {exc}", file=sys.stderr)
        return 1

    if args.write_reference:
        if previous is not None:
            old_by_path = {
                row["path"]: row
                for row in previous.get("artifacts", [])
                if isinstance(row, dict) and isinstance(row.get("path"), str)
            }
            errors: list[str] = []
            for row in rows:
                old = old_by_path.get(row["path"])
                if not old or old.get("content_digest") == row["content_digest"]:
                    continue
                if not version_advanced(old.get("version"), row["version"]):
                    errors.append(f"{row['path']}: content changed without version advance")
                if not generated_at_advanced(old.get("generated_at"), row.get("generated_at")):
                    errors.append(f"{row['path']}: content changed without generated_at advance")
            if errors:
                for error in errors:
                    print(error, file=sys.stderr)
                return 1
        REFERENCE.parent.mkdir(parents=True, exist_ok=True)
        REFERENCE.write_text(
            json.dumps(current, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"updated {REFERENCE.relative_to(ROOT).as_posix()} ({len(rows)} artifacts)")
        return 0

    if previous is None:
        print(
            f"artifact version check failed: missing {REFERENCE.relative_to(ROOT).as_posix()} "
            "(run with --write-reference)",
            file=sys.stderr,
        )
        return 1
    if previous != current:
        old_by_path = {
            row.get("path"): row
            for row in previous.get("artifacts", [])
            if isinstance(row, dict)
        }
        new_by_path = {row["path"]: row for row in rows}
        changed = sorted(
            path
            for path in set(old_by_path) | set(new_by_path)
            if old_by_path.get(path) != new_by_path.get(path)
        )
        print(
            "artifact version check failed: metadata/content reference drift in "
            + ", ".join(changed),
            file=sys.stderr,
        )
        return 1

    print(f"Artifact version metadata passed ({len(rows)} artifacts).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
