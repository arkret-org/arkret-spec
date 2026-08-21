"""Report naming coverage in three separate columns that answer three questions.

The three sections are deliberately not summed into one number, because they are
not the same claim and only the first one was ever total:

* **walker reachability** - can the schema-property walker reach every declared
  property? This proves the enforced surface has not silently shrunk. It proves
  nothing about whether any rule applies once a property has been reached.
* **registered predicate applicability** - for each executed predicate, how many
  of the reached occurrences its applicability gate actually admits. A predicate
  restricted to boolean-typed properties judges a small slice of the surface,
  and reporting it as part of a 100% figure would be false.
* **rule-contract coverage** - how many of the normative naming clauses in
  ``tools/naming-rule-coverage-matrix.json`` have mechanical enforcement at all.
  This is the figure that says whether the naming contract is closed, and it is
  the only one that counts ``prose_only`` and ``uncovered`` clauses. The two are
  not the same state: ``uncovered`` is an open protocol issue nobody accepted,
  while ``prose_only`` is an accepted end state whose residual-risk justification
  the artifact lint itself enforces (``check_naming_rule_coverage_matrix``
  requires every such row to carry a substantive ``manual_review_reason`` and
  forbids it to claim full coverage). ``--require-full`` therefore fails on
  ``uncovered`` clauses and reports ``prose_only`` clauses without failing on
  them; gating on an accepted state would make the gate unfixable by
  construction.

Usage::

    python tools/naming_coverage.py             # human-readable summary
    python tools/naming_coverage.py --json      # machine-readable
    python tools/naming_coverage.py --require-full   # exit 1 unless the walker is
                                                     # total and nothing is uncovered
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
    PREDICATES,
    enumerate_schema_properties,
    naive_property_occurrences,
    naive_property_population,
    schema_shape_has_type,
)

SCHEMA_DIR = ROOT / "spec" / "v1" / "artifacts" / "schemas"
COVERAGE_MATRIX_PATH = ROOT / "tools" / "naming-rule-coverage-matrix.json"

# Applicability gate of every predicate over the schema-property surface. A rule
# whose gate is not a property-shape test does not judge this surface at all and
# says so instead of borrowing the walker's totals.
PROPERTY_APPLICABILITY = {
    "NC-BOOL-001": "boolean",
    "NC-COUNT-001": None,
    "NC-CODE-001": None,
    "NC-EVIDENCE-001": None,
    "NC-FIELDCASE-001": None,
    "NC-HASH-001": None,
    "NC-SET-001": "array",
}
OFF_SURFACE_PREDICATES = {
    "NC-ENUM-001": "symbolic enum values, not property names",
    "NC-TYPE-001": "$defs keys and OpenAPI components, not property names",
    "NC-ARTIFACT-001": "artifact filenames, not property names",
    "NC-CLASSIFICATION-001": "classification-field-registry rows, not property names",
}


def _resolver(documents: dict[str, object]):
    def resolve(current_file: str, ref: str):
        target, separator, fragment = ref.partition("#")
        target_file = current_file if not target else Path(target).name
        document = documents.get(target_file)
        if document is None:
            return None
        node = document
        if separator:
            for token in fragment.split("/"):
                if not token:
                    continue
                token = token.replace("~1", "/").replace("~0", "~")
                if isinstance(node, dict):
                    if token not in node:
                        return None
                    node = node[token]
                elif isinstance(node, list):
                    try:
                        node = node[int(token)]
                    except (IndexError, ValueError):
                        return None
                else:
                    return None
        return target_file, node

    return resolve


def measure_walker() -> dict:
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


def measure_predicate_applicability() -> dict:
    documents = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(SCHEMA_DIR.glob("*.json"))
    }
    resolve = _resolver(documents)
    total = 0
    admitted = {rule_id: 0 for rule_id in PROPERTY_APPLICABILITY}
    for file_name, document in documents.items():
        for occurrence in enumerate_schema_properties(file_name, document):
            total += 1
            for rule_id, required_type in PROPERTY_APPLICABILITY.items():
                if required_type is None or schema_shape_has_type(
                    file_name, occurrence.shape, required_type, resolve
                ):
                    admitted[rule_id] += 1
    return {
        "property_occurrences": total,
        "registered_predicates": len(PREDICATES),
        "admitted": admitted,
        "off_surface": OFF_SURFACE_PREDICATES,
    }


def measure_rule_contract() -> dict:
    if not COVERAGE_MATRIX_PATH.exists():
        return {"available": False}
    matrix = json.loads(COVERAGE_MATRIX_PATH.read_text(encoding="utf-8"))
    rows = matrix.get("rules", [])
    mechanical = {"predicate", "registry_closure", "schema_type"}
    by_kind: dict[str, int] = {}
    full = 0
    unenforced: list[str] = []
    uncovered: list[str] = []
    prose_only: list[str] = []
    for row in rows:
        kind = row.get("enforcement_kind")
        by_kind[kind] = by_kind.get(kind, 0) + 1
        if row.get("coverage_level") == "full":
            full += 1
        if kind not in mechanical:
            unenforced.append(f"{row.get('rule_id')}({kind})")
            if kind == "uncovered":
                uncovered.append(row.get("rule_id"))
            elif kind == "prose_only":
                prose_only.append(row.get("rule_id"))
    return {
        "available": True,
        "rules": len(rows),
        "by_enforcement_kind": by_kind,
        "mechanically_enforced": sum(by_kind.get(kind, 0) for kind in mechanical),
        "full_coverage": full,
        "unenforced": sorted(unenforced),
        "uncovered": sorted(uncovered),
        "prose_only": sorted(prose_only),
    }


def measure() -> dict:
    return {
        "walker_reachability": measure_walker(),
        "predicate_applicability": measure_predicate_applicability(),
        "rule_contract_coverage": measure_rule_contract(),
    }


def _percent(reached: int, expected: int) -> float:
    return 100.0 * reached / max(expected, 1)


def _print_report(report: dict) -> None:
    walker = report["walker_reachability"]
    name_pct = _percent(walker["name"]["reached"], walker["name"]["expected"])
    path_pct = _percent(walker["path"]["reached"], walker["path"]["expected"])

    print("[1] walker reachability  (can every declared property be reached?)")
    print(f"  schemas scanned            : {walker['schemas']}")
    print(
        f"  distinct property names    : {walker['name']['reached']}"
        f" / {walker['name']['expected']}  ({name_pct:.1f}%)"
    )
    print(
        f"  property occurrence paths  : {walker['path']['reached']}"
        f" / {walker['path']['expected']}  ({path_pct:.1f}%)"
    )
    if walker["files_with_gaps"]:
        print("  files with unreached names:")
        for row in walker["files_with_gaps"]:
            print(
                f"    {row['file']}: names={row['missing_names']}, "
                f"missing_paths={row['missing_occurrences'][:5]}, "
                f"unexpected_paths={row['unexpected_occurrences'][:5]}"
            )
    else:
        print("  no unreached declared property names")

    applicability = report["predicate_applicability"]
    total = applicability["property_occurrences"]
    print()
    print("[2] registered predicate applicability  (how much does each predicate judge?)")
    print(f"  registered predicates      : {applicability['registered_predicates']}")
    for rule_id, count in sorted(applicability["admitted"].items()):
        print(
            f"  {rule_id:24s} : {count} / {total} property occurrences admitted"
            f"  ({_percent(count, total):.1f}%)"
        )
    for rule_id, note in sorted(applicability["off_surface"].items()):
        print(f"  {rule_id:24s} : off this surface -- {note}")

    contract = report["rule_contract_coverage"]
    print()
    print("[3] rule-contract coverage  (is the naming contract itself closed?)")
    if not contract.get("available"):
        print("  no coverage matrix; rule-contract coverage is UNKNOWN, not 100%")
        return
    rules = contract["rules"]
    mechanical = contract["mechanically_enforced"]
    print(f"  registered naming clauses  : {rules}")
    print(
        f"  mechanically enforced      : {mechanical} / {rules}"
        f"  ({_percent(mechanical, rules):.1f}%)"
    )
    print(f"  full coverage              : {contract['full_coverage']} / {rules}")
    for kind, count in sorted(contract["by_enforcement_kind"].items()):
        print(f"  {kind:24s} : {count}")
    if contract["unenforced"]:
        print(f"  clauses without mechanical enforcement: {contract['unenforced']}")
    if contract["uncovered"]:
        print(
            f"  uncovered clauses (open protocol issues; --require-full fails on these): "
            f"{contract['uncovered']}"
        )
    if contract["prose_only"]:
        print(
            f"  prose_only clauses (accepted human-review debt with a lint-enforced "
            f"manual_review_reason; reported, not gated): {contract['prose_only']}"
        )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--require-full",
        action="store_true",
        help="exit non-zero unless the walker is total AND no naming clause is uncovered "
        "(prose_only clauses are accepted review debt: reported, not gated)",
    )
    args = parser.parse_args(argv)

    report = measure()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report)

    if not args.require_full:
        return 0

    walker = report["walker_reachability"]
    contract = report["rule_contract_coverage"]
    failures: list[str] = []
    if walker["name"]["missing"] or walker["path"]["missing"] or walker["path"]["unexpected"]:
        failures.append(
            f"{len(walker['name']['missing'])} declared names, "
            f"{len(walker['path']['missing'])} paths unreached, "
            f"{len(walker['path']['unexpected'])} unexpected paths"
        )
    if not contract.get("available"):
        failures.append("no rule-contract coverage matrix")
    elif contract["uncovered"]:
        failures.append(
            f"{len(contract['uncovered'])} naming clauses are uncovered open issues: "
            f"{contract['uncovered']}"
        )
    if failures:
        print("\nFAIL: " + "; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
