#!/usr/bin/env python3
"""Require two current-source artifact generations to be byte-identical."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATCH_ROOTS = (
    ROOT / "spec" / "v1" / "artifacts",
    ROOT / "site" / "public" / "v1",
)


def snapshot() -> dict[str, str]:
    result: dict[str, str] = {}
    for root in WATCH_ROOTS:
        if not root.exists():
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            result[path.relative_to(ROOT).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return result


def generate() -> None:
    subprocess.run(
        [sys.executable, "tools/artifact_pipeline.py", "generate"],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    generate()
    first = snapshot()
    generate()
    second = snapshot()
    if first == second:
        print(f"Artifact generation is deterministic ({len(second)} files).")
        return 0

    changed = sorted(
        path for path in set(first) | set(second) if first.get(path) != second.get(path)
    )
    print(
        "artifact determinism check failed: second generation changed "
        + ", ".join(changed),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
