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

import json
import re
import subprocess
import sys
from pathlib import Path

try:
    from .release_metadata import current_release_tag
except ImportError:  # Direct script execution: python tools/release_gate.py
    from release_metadata import current_release_tag

ROOT = Path(__file__).resolve().parents[1]

CHECKS: list[tuple[str, list[str]]] = [
    ("artifact pipeline", [sys.executable, "tools/artifact_pipeline.py", "check"]),
    ("crossref", ["node", "site/scripts/crossref-check.mjs"]),
]


def check_stable_promotion_evidence() -> str | None:
    try:
        release_tag = current_release_tag()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return f"release metadata is unreadable: {exc}"
    if release_tag != "v1.0.0":
        return None
    vector_gap_path = (
        ROOT
        / "spec"
        / "v1"
        / "artifacts"
        / "registry"
        / "event-kind-vector-gap-registry.json"
    )
    try:
        vector_gaps = json.loads(vector_gap_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"stable vector-gap registry is unreadable: {exc}"
    blocking_gaps = [
        row
        for row in vector_gaps.get("uncovered_event_kinds", [])
        if isinstance(row, dict) and row.get("priority") in {"critical", "high"}
    ]
    if blocking_gaps:
        counts = {
            priority: sum(row.get("priority") == priority for row in blocking_gaps)
            for priority in ("critical", "high")
        }
        return (
            "stable promotion requires zero critical/high Event vector gaps "
            f"(critical={counts['critical']}, high={counts['high']})"
        )
    evidence_path = ROOT / "spec" / "v1" / "artifacts" / "reports" / "core-interop-evidence.json"
    if not evidence_path.is_file():
        return "stable tag requires artifacts/reports/core-interop-evidence.json"
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"stable interop evidence is unreadable: {exc}"
    implementations = evidence.get("implementations")
    if not isinstance(implementations, list) or len(implementations) < 2:
        return "stable promotion requires at least two independent implementations"
    digests = {
        row.get("artifact_digest")
        for row in implementations
        if isinstance(row, dict) and row.get("runner_result") == "pass"
    }
    if len(digests) < 2 or any(not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value) for value in digests):
        return "stable promotion requires two distinct passing implementation artifact digests"
    required = {"core_event_store", "sync", "state", "capability", "security_negative"}
    for row in implementations:
        if not isinstance(row, dict) or not required.issubset(set(row.get("passed_suites") or [])):
            return "each stable implementation must pass all core behavioral suites"
    return None


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    checks = CHECKS.copy()
    if strict:
        checks.append(("strict spec lint", [sys.executable, "tools/lint_spec.py", "--strict"]))

    failures: list[str] = []
    stable_error = check_stable_promotion_evidence()
    if stable_error is not None:
        print(f"BLOCKED: {stable_error}")
        failures.append("stable promotion evidence")
    for label, cmd in checks:
        print(f"=== release-gate: {label} ===", flush=True)
        try:
            # `text=True` alone decodes with the locale encoding, so a child that
            # prints any non-ASCII byte (the artifact lint's progress lines are
            # Chinese) crashes the reader thread and the gate loses that output
            # entirely. The artifacts and tools are UTF-8; say so.
            result = subprocess.run(
                cmd,
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            print(f"unable to start {cmd[0]!r} for {label}: {exc}")
            failures.append(label)
            continue
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
