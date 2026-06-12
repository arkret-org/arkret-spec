#!/usr/bin/env python3
"""Unified release gate (spec-review STR-005).

Runs the artifact pipeline and the spec-site cross-reference check as the
authoritative release gate. The artifact pipeline already verifies generated
registry drift, operation completeness, fixture digests, artifact lint, and
prose lint; this wrapper intentionally avoids re-running those checks.

Usage:
    python tools/release_gate.py            # fail on any error
    python tools/release_gate.py --strict   # also fail on lint_spec warnings
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECKS: list[tuple[str, list[str]]] = [
    ("artifact pipeline", [sys.executable, "tools/artifact_pipeline.py", "check"]),
    ("crossref", ["node", "site/scripts/crossref-check.mjs"]),
]


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    checks = CHECKS.copy()
    if strict:
        checks.append(("strict spec lint", [sys.executable, "tools/lint_spec.py", "--strict"]))

    failures: list[str] = []
    for label, cmd in checks:
        print(f"=== release-gate: {label} ===", flush=True)
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        out = (result.stdout or "") + (result.stderr or "")
        sys.stdout.write(out)
        if not out.endswith("\n"):
            sys.stdout.write("\n")
        if result.returncode != 0:
            failures.append(label)

    print("\n=== release-gate summary ===", flush=True)
    if failures:
        print(f"BLOCKED: {len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print(f"PASS: all {len(checks)} checks green; release gate open.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
