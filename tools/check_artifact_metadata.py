#!/usr/bin/env python3
"""Reject redundant static artifact metadata without inspecting protocol members."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec/v1/artifacts"
REDUNDANT = frozenset({
    "version", "revision", "content_revision", "artifact_version", "format_version",
    "generated_at", "source_of_truth", "metadata_authority", "schema_version", "generator_version",
    "coverage_summary", "type_derived_summary",
    "baseline_date", "x-floria-schema-version", "fixture_version", "lock_kind", "generated_views",
})


def metadata_errors(document: object, *, fixture: bool = False, catalog: bool = False) -> list[str]:
    if not isinstance(document, dict):
        return []
    errors = [f"redundant root metadata: {key}" for key in sorted(REDUNDANT & document.keys())]
    if isinstance(document.get("schema"), str) and document["schema"].startswith(("arkret.", "cotest.", "inkson.")):
        errors.append("self-declared schema label has no formal schema contract")
    if fixture:
        errors += [f"duplicate fixture label: {key}" for key in ("suite", "fixture_id", "fixture_kind", "schema") if key in document]
    if catalog:
        for name, section in document.items():
            if isinstance(section, dict) and name.endswith(("_registry", "_contract")):
                errors += [f"{name}: {message}" for message in metadata_errors(section, catalog=True)]
    return errors


def check(root: Path = ROOT) -> list[str]:
    artifacts = root / "spec/v1/artifacts"
    manifest_path = artifacts / "registry/registry-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    generated = set()
    for row in manifest["registries"]:
        if "source_of_truth" in row:
            errors.append(f"{manifest_path}: duplicate source_of_truth for {row.get('file')}")
        if row.get("source_role") == "generated":
            generated.add(row["file"])
    paths = sorted(artifacts.rglob("*.json")) + sorted((root / "tools").glob("*.json"))
    paths += sorted((root / "site/public/v1").glob("contract-registry-*.json"))
    for path in paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        relative = path.relative_to(root).as_posix()
        messages = metadata_errors(value, fixture=path.parent == artifacts / "fixtures",
                                   catalog=path.parent == artifacts / "registry" or path.name.startswith("contract-registry"))
        if (isinstance(value, dict) and path.parent == root / "tools"
                and value.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
                and not path.name.endswith(".schema.json")
                and not set(value) & {"$defs", "$ref", "properties", "type", "oneOf", "allOf", "anyOf", "const", "enum", "if", "not", "additionalProperties"}):
            messages.append("a data ledger cannot declare itself to be a JSON Schema")
        if path.parent == artifacts / "registry":
            messages += [f"duplicate registry metadata: {key}" for key in ("$schema", "kind", "source_role") if key in value]
        if path.parent == root / "tools" and isinstance(value, dict) and "kind" in value:
            messages.append("a fixed-path ledger does not need a duplicate root kind label")
        if path.is_relative_to(artifacts) and path.relative_to(artifacts).as_posix() in generated:
            messages += [f"duplicate generated lineage: {key}" for key in ("generated_from", "generated_by") if key in value]
        errors += [f"{relative}: {message}" for message in messages]
    return errors


def main() -> int:
    errors = check()
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print("static artifact metadata: no redundant revisions or ownership labels")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
