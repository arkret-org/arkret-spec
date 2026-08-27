#!/usr/bin/env python3
"""Freeze operation contract and operation-bundle membership closures.

``generate`` is intentionally append-only: it creates the initial lock or adds
new versioned identities, but refuses to rewrite an existing identity whose
closure changed.  Therefore the command cannot be used to bless an in-place
contract change accidentally.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec/v1/artifacts"
REGISTRY = ARTIFACTS / "registry"
CONTRACT = REGISTRY / "contract-registry.json"
ERROR_MAPPING = REGISTRY / "operations-error-mapping.json"
ERROR_CODES = REGISTRY / "error-code-registry.json"
OPERATION_LOCK = REGISTRY / "operation-contract-closure-lock.json"
BUNDLE_LOCK = REGISTRY / "operation-bundle-closure-lock.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


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
    return {
        "version": "2026-08-27.1",
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


def verify_or_append(path: Path, expected: dict[str, Any], generate: bool) -> list[str]:
    if not path.exists():
        if generate:
            path.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return []
        return [f"missing closure lock: {path.relative_to(ROOT).as_posix()}"]
    actual = load(path)
    key = expected["identity_key"]
    existing = {row[key]: row["sha256"] for row in actual.get("closures", [])}
    current = {row[key]: row["sha256"] for row in expected["closures"]}
    errors = [
        f"{path.name}: closure changed without version upgrade: {identity}"
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
        path.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif additions:
        errors.append(f"{path.name}: new identities are not locked: {additions}")
    return errors


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
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("generate", "check"))
    args = parser.parse_args()
    catalog = load(CONTRACT)
    errors = self_test(catalog)
    errors.extend(verify_or_append(
        OPERATION_LOCK, payload("operation_contract", operation_closures(catalog)), args.mode == "generate"
    ))
    errors.extend(verify_or_append(
        BUNDLE_LOCK, payload("operation_bundle_members", bundle_closures(catalog)), args.mode == "generate"
    ))
    if errors:
        for error in errors:
            print(error)
        return 1
    print("operation closure locks: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
