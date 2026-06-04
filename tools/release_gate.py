#!/usr/bin/env python3
"""Unified release gate (spec-review STR-005).

Runs every artifact / spec / cross-reference / fixture check as a single
authoritative gate. Exits non-zero if ANY check fails, so a release MUST NOT
proceed while the spec tree has registry drift, unknown profiles, broken
anchors, lint warnings-as-errors, crossref breaks, or fixture digest drift.

Usage:
    python tools/release_gate.py            # fail on any error
    python tools/release_gate.py --strict   # also fail on lint_spec warnings
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (label, argv, fail_on_warning_substring_optional)
CHECKS: list[tuple[str, list[str]]] = [
    ("artifact pipeline", [sys.executable, "tools/artifact_pipeline.py", "check"]),
    ("artifact lint", [sys.executable, "tools/lint_artifacts.py"]),
    ("spec lint", [sys.executable, "tools/lint_spec.py"]),
    ("crossref", ["node", "site/scripts/crossref-check.mjs"]),
    ("fixture digests", [sys.executable, "tools/check_fixture_digests.py"]),
]


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    failures: list[str] = []
    for label, cmd in CHECKS:
        print(f"=== release-gate: {label} ===", flush=True)
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        out = (result.stdout or "") + (result.stderr or "")
        sys.stdout.write(out)
        if not out.endswith("\n"):
            sys.stdout.write("\n")
        failed = result.returncode != 0
        if strict and label == "spec lint" and "0 warning" not in out:
            failed = True
        if failed:
            failures.append(label)

    print("\n=== release-gate summary ===", flush=True)
    if failures:
        print(f"BLOCKED: {len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print(f"PASS: all {len(CHECKS)} checks green; release gate open.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
