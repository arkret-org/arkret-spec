#!/usr/bin/env python3
"""Guard operation contract and operation-bundle membership closures.

``generate`` is intentionally append-only: it creates the initial lock or adds
new versioned identities, but refuses to rewrite an existing identity whose
closure changed.  Therefore the command cannot be used to bless an in-place
contract change accidentally.  Before stable promotion, ``refresh-candidate``
is the explicit clean-break path for replacing the current candidate locks.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from .release_metadata import current_release_tag, is_candidate_release_tag
except ImportError:  # Direct script execution: python tools/check_operation_closure_locks.py
    from release_metadata import current_release_tag, is_candidate_release_tag


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec/v1/artifacts"
REGISTRY = ARTIFACTS / "registry"
CONTRACT = REGISTRY / "contract-registry.json"
ERROR_MAPPING = REGISTRY / "operations-error-mapping.json"
ERROR_CODES = REGISTRY / "error-code-registry.json"
OPERATION_LOCK = REGISTRY / "operation-contract-closure-lock.json"
BUNDLE_LOCK = REGISTRY / "operation-bundle-closure-lock.json"
LOCK_VERSION_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.(\d+)$")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def require_candidate_release() -> str:
    tag = current_release_tag()
    if not is_candidate_release_tag(tag):
        raise ValueError(
            "refresh-candidate is forbidden after stable promotion; "
            f"current specReleaseTag is {tag!r}"
        )
    return tag


def pointer(document: Any, fragment: str) -> Any:
    if fragment in {"", "#"}:
        return document
    if not fragment.startswith("#/"):
        raise ValueError(f"unsupported schema fragment: {fragment}")
    node = document
    for token in fragment[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


@lru_cache(maxsize=None)
def schema_closure(schema_ref: str) -> dict[str, Any]:
    closure: dict[str, Any] = {}
    visiting: set[str] = set()

    def visit(file_path: Path, fragment: str) -> None:
        file_path = file_path.resolve()
        key = f"{file_path.relative_to(ARTIFACTS.resolve()).as_posix()}{fragment}"
        if key in closure or key in visiting:
            return
        visiting.add(key)
        node = schema_node(file_path, fragment)
        closure[key] = digest(node)
        for target_file, target_fragment in schema_refs(file_path, fragment):
            visit(Path(target_file), target_fragment)
        visiting.remove(key)

    file_ref, separator, fragment = schema_ref.partition("#")
    visit(ARTIFACTS / file_ref, f"#{fragment}" if separator else "")
    return dict(sorted(closure.items()))


@lru_cache(maxsize=None)
def schema_document(file_path: Path) -> Any:
    return load(file_path)


@lru_cache(maxsize=None)
def schema_node(file_path: Path, fragment: str) -> Any:
    return pointer(schema_document(file_path.resolve()), fragment)


@lru_cache(maxsize=None)
def schema_refs(file_path: Path, fragment: str) -> tuple[tuple[str, str], ...]:
    refs_found: set[tuple[str, str]] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            ref = value.get("$ref")
            if isinstance(ref, str) and not ref.startswith(("http://", "https://")):
                target, separator, target_fragment = ref.partition("#")
                target_file = file_path if not target else (file_path.parent / target).resolve()
                refs_found.add((str(target_file.resolve()), f"#{target_fragment}" if separator else ""))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(schema_node(file_path.resolve(), fragment))
    return tuple(sorted(refs_found))


def operation_closures(catalog: dict[str, Any]) -> list[dict[str, str]]:
    mapping = load(ERROR_MAPPING)
    error_registry = load(ERROR_CODES)
    error_rows = {
        row.get("code"): row
        for section in ("codes", "reason_codes")
        for row in error_registry.get(section, [])
        if isinstance(row, dict) and isinstance(row.get("code"), str)
    }
    mapping_rows = {
        row.get("operation_id"): row
        for row in mapping.get("operations", [])
        if isinstance(row, dict) and isinstance(row.get("operation_id"), str)
    }
    result: list[dict[str, str]] = []
    for operation in catalog["operation_registry"]["operations"]:
        operation_id = operation["operation_id"]
        schemas: dict[str, Any] = {}
        for key in ("request_schema_ref", "response_schema_ref", "error_schema_ref"):
            ref = operation.get(key)
            if isinstance(ref, str):
                schemas.update(schema_closure(ref))
        error_mapping = mapping_rows.get(operation_id, {})
        operation_specific = error_mapping.get("operation_specific", [])
        closure = {
            "operation": operation,
            "schema_recursive_closure": dict(sorted(schemas.items())),
            "error_mapping": error_mapping,
            "universal_error_rules": mapping.get("rules", {}).get("universal_codes"),
            "registered_operation_specific_errors": {
                code: error_rows.get(code) for code in sorted(operation_specific)
            },
        }
        result.append({"operation_id": operation_id, "sha256": digest(closure)})
    return sorted(result, key=lambda row: row["operation_id"])


def bundle_closures(catalog: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for bundle in catalog["operation_registry"]["operation_bundles"]:
        identity = bundle["operation_bundle_id"]
        frozen = {
            "operation_bundle_id": identity,
            "service_kind": bundle["service_kind"],
            "members": bundle["members"],
        }
        rows.append({"operation_bundle_id": identity, "sha256": digest(frozen)})
    return sorted(rows, key=lambda row: row["operation_bundle_id"])


def payload(kind: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    id_key = "operation_id" if kind == "operation_contract" else "operation_bundle_id"
    catalog = load(CONTRACT)
    return {
        "version": "2026-08-27.1",
        "generated_at": catalog["generated_at"],
        "source_of_truth": False,
        "generated_from": [
            "registry/contract-registry.json",
            *(["registry/operations-error-mapping.json", "registry/error-code-registry.json"]
              if kind == "operation_contract" else []),
        ],
        "algorithm": "sha256 over canonical sorted-key JSON closure",
        "lock_kind": kind,
        "identity_key": id_key,
        "closures": rows,
    }


def next_lock_version(path: Path, actual: dict[str, Any]) -> str:
    version = actual.get("version")
    match = LOCK_VERSION_RE.fullmatch(version) if isinstance(version, str) else None
    if not match:
        raise ValueError(
            f"{path.name}: cannot advance unsupported lock version {version!r}"
        )
    return f"{match.group(1)}.{int(match.group(2)) + 1}"


def parse_generated_at(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def next_generated_at(previous: Any, candidate: Any) -> Any:
    """Return a ``generated_at`` that is strictly later than ``previous``.

    The candidate is copied from the source catalog, which is regenerated on
    its own schedule and is routinely older than the lock being replaced. A
    refresh that took it verbatim wrote the timestamp backwards, and then
    ``check_artifact_versions.py --write-reference`` refused the result with
    ``content changed without generated_at advance`` — leaving the timestamp to
    be repaired by hand after every refresh. Falling back to one second past
    the previous value keeps the advance without reaching for a wall clock, so
    the refresh stays reproducible from its inputs.
    """
    previous_dt = parse_generated_at(previous)
    if previous_dt is None:
        return candidate
    candidate_dt = parse_generated_at(candidate)
    if candidate_dt is not None and candidate_dt > previous_dt:
        return candidate
    return (previous_dt + timedelta(seconds=1)).isoformat()


def verify_or_append(path: Path, expected: dict[str, Any], generate: bool) -> list[str]:
    if not path.exists():
        if generate:
            path.write_text(
                json.dumps(expected, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            return []
        return [f"missing closure lock: {path.relative_to(ROOT).as_posix()}"]
    actual = load(path)
    key = expected["identity_key"]
    existing = {row[key]: row["sha256"] for row in actual.get("closures", [])}
    current = {row[key]: row["sha256"] for row in expected["closures"]}
    errors = [
        f"{path.name}: closure changed: {identity}; use refresh-candidate before "
        "stable promotion, or add a versioned successor after promotion"
        for identity in sorted(existing.keys() & current.keys())
        if existing[identity] != current[identity]
    ]
    removed = sorted(existing.keys() - current.keys())
    if removed:
        errors.append(f"{path.name}: locked identities were removed: {removed}")
    if errors:
        return errors
    additions = sorted(current.keys() - existing.keys())
    if additions and generate:
        expected_rows = {row[key]: row for row in expected["closures"]}
        actual["closures"] = sorted(
            [*actual.get("closures", []), *(expected_rows[item] for item in additions)],
            key=lambda row: row[key],
        )
        actual["version"] = next_lock_version(path, actual)
        actual["generated_at"] = next_generated_at(
            actual.get("generated_at"), expected.get("generated_at")
        )
        path.write_text(
            json.dumps(actual, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    elif additions:
        errors.append(f"{path.name}: new identities are not locked: {additions}")
    return errors


def refresh_candidate_lock(
    path: Path, expected: dict[str, Any]
) -> dict[str, list[str]]:
    key = expected["identity_key"]
    actual = load(path) if path.exists() else {"closures": []}
    existing = {row[key]: row["sha256"] for row in actual.get("closures", [])}
    current = {row[key]: row["sha256"] for row in expected["closures"]}
    summary = {
        "changed": sorted(
            identity
            for identity in existing.keys() & current.keys()
            if existing[identity] != current[identity]
        ),
        "added": sorted(current.keys() - existing.keys()),
        "removed": sorted(existing.keys() - current.keys()),
    }
    changed = any(summary.values())
    if not path.exists() or changed:
        refreshed = copy.deepcopy(expected)
        if path.exists():
            refreshed["version"] = next_lock_version(path, actual)
            refreshed["generated_at"] = next_generated_at(
                actual.get("generated_at"), refreshed.get("generated_at")
            )
        path.write_text(
            json.dumps(refreshed, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return summary


def print_refresh_summary(path: Path, summary: dict[str, list[str]]) -> None:
    print(f"{path.name}: candidate closure lock refreshed")
    for category in ("changed", "added", "removed"):
        identities = summary[category]
        print(f"  {category}: {len(identities)}")
        for identity in identities:
            print(f"    {identity}")


def self_test(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    base_operation = operation_closures(catalog)[0]["sha256"]
    mutated = copy.deepcopy(catalog)
    mutated["operation_registry"]["operations"][0]["success_shape_kind"] = "mutation_probe"
    if operation_closures(mutated)[0]["sha256"] == base_operation:
        errors.append("operation closure mutation probe did not change digest")
    base_bundle = bundle_closures(catalog)[0]["sha256"]
    mutated = copy.deepcopy(catalog)
    mutated["operation_registry"]["operation_bundles"][0]["members"] = []
    if bundle_closures(mutated)[0]["sha256"] == base_bundle:
        errors.append("bundle membership mutation probe did not change digest")
    if not is_candidate_release_tag("v9.8.7-candidate.probe"):
        errors.append("candidate release tag probe was rejected")
    if is_candidate_release_tag("v9.8.7"):
        errors.append("stable release tag probe was accepted as candidate")
    if next_lock_version(Path("probe.json"), {"version": "2026-08-27.1"}) != "2026-08-27.2":
        errors.append("lock version advance probe failed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("generate", "check", "refresh-candidate"))
    args = parser.parse_args()
    catalog = load(CONTRACT)
    errors = self_test(catalog)
    if errors:
        for error in errors:
            print(error)
        return 1

    operation_payload = payload("operation_contract", operation_closures(catalog))
    bundle_payload = payload("operation_bundle_members", bundle_closures(catalog))
    if args.mode == "refresh-candidate":
        try:
            release_tag = require_candidate_release()
        except (OSError, ValueError) as exc:
            print(exc)
            return 1
        try:
            operation_summary = refresh_candidate_lock(OPERATION_LOCK, operation_payload)
            bundle_summary = refresh_candidate_lock(BUNDLE_LOCK, bundle_payload)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(exc)
            return 1
        print(f"release state: {release_tag}")
        print_refresh_summary(OPERATION_LOCK, operation_summary)
        print_refresh_summary(BUNDLE_LOCK, bundle_summary)
        return 0

    errors.extend(verify_or_append(
        OPERATION_LOCK, operation_payload, args.mode == "generate"
    ))
    errors.extend(verify_or_append(
        BUNDLE_LOCK, bundle_payload, args.mode == "generate"
    ))
    if errors:
        for error in errors:
            print(error)
        return 1
    print("operation closure locks: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
