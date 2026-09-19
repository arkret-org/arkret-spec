#!/usr/bin/env python3
"""Detect artifact content drift without a corresponding metadata advance."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
REFERENCE = ARTIFACTS / "reports" / "artifact-version-digests.json"
GOVERNANCE_MANIFEST = ROOT / "tools" / "artifact-version-governance.json"
DATE_VERSION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATED_VERSION_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:\.(\d+))?$")


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def semantic_content_digest(data: dict[str, Any]) -> str:
    content = {
        key: value for key, value in data.items() if key not in {"version", "generated_at"}
    }
    return "sha256:" + hashlib.sha256(canonical_json(content)).hexdigest()


def artifact_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    paths = [
        *(ARTIFACTS / "registry").glob("*.json"),
        *(ARTIFACTS / "profiles").glob("*.json"),
    ]
    governance = json.loads(GOVERNANCE_MANIFEST.read_text(encoding="utf-8"))
    governed = governance.get("governed_tool_artifacts")
    scripts = governance.get("governing_scripts")
    if not isinstance(governed, list) or not all(isinstance(value, str) for value in governed):
        raise ValueError(f"{GOVERNANCE_MANIFEST}: governed_tool_artifacts must be a string array")
    if governed != sorted(set(governed)):
        raise ValueError(f"{GOVERNANCE_MANIFEST}: governed_tool_artifacts must be sorted and unique")
    if not isinstance(scripts, list) or not all(isinstance(value, str) for value in scripts):
        raise ValueError(f"{GOVERNANCE_MANIFEST}: governing_scripts must be a string array")
    if scripts != sorted(set(scripts)):
        raise ValueError(f"{GOVERNANCE_MANIFEST}: governing_scripts must be sorted and unique")
    for relative in scripts:
        if not (ROOT / relative).is_file():
            raise ValueError(f"{GOVERNANCE_MANIFEST}: governing script does not exist: {relative}")
    paths.extend(ROOT / relative for relative in governed)

    discovered_tool_ledgers: set[str] = set()
    for path in (ROOT / "tools").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if (
            isinstance(data, dict)
            and isinstance(data.get("version"), (str, int))
            and not isinstance(data.get("version"), bool)
        ):
            discovered_tool_ledgers.add(path.relative_to(ROOT).as_posix())
    if set(governed) != discovered_tool_ledgers:
        missing = sorted(discovered_tool_ledgers - set(governed))
        stale = sorted(set(governed) - discovered_tool_ledgers)
        raise ValueError(
            f"{GOVERNANCE_MANIFEST}: explicit tool ledger inventory drift; "
            f"missing={missing}, stale={stale}"
        )
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
        if isinstance(version, str) and DATED_VERSION_RE.fullmatch(version) and generated_at:
            try:
                parsed = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"{path}: generated_at must be RFC3339") from exc
            if parsed.tzinfo is None:
                raise ValueError(f"{path}: generated_at must carry an RFC3339 offset")
            version_day = DATED_VERSION_RE.fullmatch(version).group(1)
            if parsed.date().isoformat() != version_day:
                raise ValueError(
                    f"{path}: generated_at civil date must match version date {version_day}"
                )
        rows.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "version": version,
                "generated_at": generated_at,
                "content_digest": semantic_content_digest(data),
            }
        )
    return rows


def version_advanced(old: Any, new: Any) -> bool:
    if isinstance(old, int) and isinstance(new, int):
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


def version_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    match = DATED_VERSION_RE.fullmatch(value)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def instant(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return parsed if parsed.tzinfo is not None else None


def latest_civil_date(now: datetime) -> date:
    """The largest calendar date that has already started anywhere on Earth.

    A date-shaped version carries no offset, so the only offset-independent
    statement about it is whether the date has begun in the earliest time zone
    there is. UTC+14 is that zone, and using it keeps the guard from calling a
    legitimate same-evening release in +08:00 a future stamp.
    """

    return now.astimezone(timezone(timedelta(hours=14))).date()


def walks_back_a_future_version(old: Any, new: Any, now: datetime) -> bool:
    old_date = version_date(old)
    new_date = version_date(new)
    if old_date is None or new_date is None:
        return False
    today = latest_civil_date(now)
    return old_date > today >= new_date


def walks_back_a_future_instant(old: Any, new: Any, now: datetime) -> bool:
    old_dt = instant(old)
    new_dt = instant(new)
    if old_dt is None or new_dt is None:
        return False
    return old_dt > now >= new_dt


def date_repair_waivers(old: dict[str, Any], new: dict[str, Any], now: datetime) -> set[str]:
    """Transition errors that a future-to-real date correction is allowed to clear.

    The ratchet only ever lets metadata move forward, so a stamp that was written
    ahead of real time can never be walked back by an ordinary edit: with the
    content unchanged any metadata edit is "changed without semantic content
    change", and with the content changed the smaller value is "without advance".
    A correction is therefore only recognised when the recorded value is in the
    future and the replacement is not, which is a shape an ordinary release can
    never have.
    """

    path = new["path"]
    waived: set[str] = set()
    if walks_back_a_future_version(old.get("version"), new.get("version"), now):
        waived.add(f"{path}: version changed without semantic content change")
        waived.add(f"{path}: content changed without version advance")
    if walks_back_a_future_instant(old.get("generated_at"), new.get("generated_at"), now):
        waived.add(f"{path}: generated_at changed without semantic content change")
        waived.add(f"{path}: content changed without generated_at advance")
    return waived


def future_metadata_errors(rows: list[dict[str, Any]], now: datetime) -> list[str]:
    """Refuse to record a stamp that has not happened yet.

    Nothing else in the toolchain anchors these two fields to real time, so
    without this a single stamp written ahead of the clock becomes the baseline
    every later release has to beat, and the whole registry set drifts into the
    future one commit at a time.
    """

    errors: list[str] = []
    today = latest_civil_date(now)
    for row in rows:
        version_at = version_date(row.get("version"))
        if version_at is not None and version_at > today:
            errors.append(f"{row['path']}: version {row['version']} is dated after today")
        generated_at = instant(row.get("generated_at"))
        if generated_at is not None and generated_at > now:
            errors.append(f"{row['path']}: generated_at {row['generated_at']} has not happened yet")
    return errors


def transition_errors(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    path = new["path"]
    content_changed = old.get("content_digest") != new.get("content_digest")
    version_changed = old.get("version") != new.get("version")
    generated_at_changed = old.get("generated_at") != new.get("generated_at")
    errors: list[str] = []
    if not content_changed:
        if version_changed:
            errors.append(f"{path}: version changed without semantic content change")
        if generated_at_changed:
            errors.append(f"{path}: generated_at changed without semantic content change")
        return errors
    if not version_advanced(old.get("version"), new["version"]):
        errors.append(f"{path}: content changed without version advance")
    if not generated_at_advanced(old.get("generated_at"), new.get("generated_at")):
        errors.append(f"{path}: content changed without generated_at advance")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-reference",
        action="store_true",
        help="write the current metadata/content reference after validating advances",
    )
    parser.add_argument(
        "--repair-future-date",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "with --write-reference, walk one named artifact's future version and/or "
            "generated_at back to a real instant; repeat the flag per artifact"
        ),
    )
    args = parser.parse_args(argv)
    if args.repair_future_date and not args.write_reference:
        parser.error("--repair-future-date requires --write-reference")

    now = datetime.now(timezone.utc)
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
            repairing = set(args.repair_future_date)
            unknown = sorted(repairing - {row["path"] for row in rows})
            for path in unknown:
                errors.append(f"--repair-future-date names no artifact: {path}")
            idle = set(repairing)
            for row in rows:
                old = old_by_path.get(row["path"])
                if not old:
                    continue
                row_errors = transition_errors(old, row)
                if row["path"] in repairing:
                    waived = date_repair_waivers(old, row, now)
                    if waived:
                        idle.discard(row["path"])
                    cleared = [error for error in row_errors if error in waived]
                    row_errors = [error for error in row_errors if error not in waived]
                    for error in cleared:
                        print(f"repaired future date: {error}")
                errors.extend(row_errors)
            for path in sorted(idle - set(unknown)):
                errors.append(
                    f"--repair-future-date {path}: neither version nor generated_at "
                    "walks a future value back to a real one"
                )
            if errors:
                for error in errors:
                    print(error, file=sys.stderr)
                return 1
        errors = future_metadata_errors(rows, now)
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
