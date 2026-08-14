"""Report how much of the schema naming surface the lint predicates actually reach.

Two figures are reported because they answer different questions and only the
second one is honest about exception granularity:

* ``name``  - distinct property names. Tells you how much of the vocabulary is
  checked at all.
* ``path``  - property occurrences addressed by ``(file, RFC 6901 pointer)``.
  This is the unit exceptions and debt entries are keyed by, so it is the figure
  that governs whether a per-path exception can be written at all.

Usage::

    python tools/naming_coverage.py             # human-readable summary
    python tools/naming_coverage.py --json      # machine-readable
    python tools/naming_coverage.py --require-full   # exit 1 unless both are 100%
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.artifact_lint.naming import (  # noqa: E402
    enumerate_schema_properties,
    naive_property_occurrences,
    naive_property_population,
)

SCHEMA_DIR = ROOT / "spec" / "v1" / "artifacts" / "schemas"


def measure() -> dict:
    reached_names: set[str] = set()
    expected_names: set[str] = set()
    reached_paths: set[tuple[str, str]] = set()
    expected_paths: set[tuple[str, str]] = set()
    per_file: list[dict] = []

    schema_paths = sorted(SCHEMA_DIR.glob("*.json"))
    for path in schema_paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        occurrences = list(enumerate_schema_properties(path.name, document))
        names = {occurrence.name for occurrence in occurrences}
        expected = naive_property_population(document)
        expected_occurrences = naive_property_occurrences(document)
        reached_names |= names
        expected_names |= expected
        reached_paths |= {(path.name, occurrence.pointer) for occurrence in occurrences}
        expected_paths |= {(path.name, pointer) for pointer, _name in expected_occurrences}
        missing = sorted(expected - names)
        reached_occurrences = {(occurrence.pointer, occurrence.name) for occurrence in occurrences}
        missing_occurrences = sorted(expected_occurrences - reached_occurrences)
        unexpected_occurrences = sorted(reached_occurrences - expected_occurrences)
        if missing or missing_occurrences or unexpected_occurrences:
            per_file.append(
                {
                    "file": path.name,
                    "missing_names": missing,
                    "missing_occurrences": missing_occurrences,
                    "unexpected_occurrences": unexpected_occurrences,
                }
            )

    return {
        "schemas": len(schema_paths),
        "name": {
            "expected": len(expected_names),
            "reached": len(reached_names),
            "missing": sorted(expected_names - reached_names),
        },
        "path": {
            "expected": len(expected_paths),
            "reached": len(expected_paths & reached_paths),
            "observed": len(reached_paths),
            "missing": sorted(expected_paths - reached_paths),
            "unexpected": sorted(reached_paths - expected_paths),
        },
        "files_with_gaps": per_file,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--require-full",
        action="store_true",
        help="exit non-zero unless the walker reaches every declared property",
    )
    args = parser.parse_args(argv)

    report = measure()
    name_pct = 100.0 * report["name"]["reached"] / max(report["name"]["expected"], 1)
    path_pct = 100.0 * report["path"]["reached"] / max(report["path"]["expected"], 1)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"schemas scanned            : {report['schemas']}")
        print(
            f"distinct property names    : {report['name']['reached']}"
            f" / {report['name']['expected']}  ({name_pct:.1f}%)"
        )
        print(
            f"property occurrence paths  : {report['path']['reached']}"
            f" / {report['path']['expected']}  ({path_pct:.1f}%)"
        )
        if report["files_with_gaps"]:
            print("\nfiles with unreached names:")
            for row in report["files_with_gaps"]:
                print(
                    f"  {row['file']}: names={row['missing_names']}, "
                    f"missing_paths={row['missing_occurrences'][:5]}, "
                    f"unexpected_paths={row['unexpected_occurrences'][:5]}"
                )
        else:
            print("\nno unreached declared property names")

    if args.require_full and (
        report["name"]["missing"]
        or report["path"]["missing"]
        or report["path"]["unexpected"]
    ):
        print(
            f"\nFAIL: {len(report['name']['missing'])} declared names, "
            f"{len(report['path']['missing'])} paths unreached, and "
            f"{len(report['path']['unexpected'])} unexpected paths",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
