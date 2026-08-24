#!/usr/bin/env python3
"""Replace semantically identical cross-schema $defs with canonical $refs."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def rewrite_local_refs(value: Any, file: Path, classes: dict[tuple[Path, str], str]) -> Any:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            name = ref.removeprefix("#/$defs/")
            target_class = classes.get((file, name))
            if target_class is not None:
                replaced = dict(value)
                replaced["$ref"] = f"semantic-def:{target_class}"
                return replaced
        return {key: rewrite_local_refs(item, file, classes) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_local_refs(item, file, classes) for item in value]
    return value


def semantic_classes(documents: dict[Path, dict[str, Any]]) -> dict[tuple[Path, str], str]:
    nodes = {
        (file, name): definition
        for file, document in documents.items()
        for name, definition in document.get("$defs", {}).items()
        if not (isinstance(definition, dict) and set(definition) == {"$ref"})
    }
    # Partition refinement, rather than recursive cryptographic hashing, is
    # deliberate: schemas may contain self-references or mutually recursive
    # definitions.  Including the previous class makes each round monotonic.
    classes = {node: "0" for node in nodes}
    for _ in range(len(nodes) + 1):
        signatures = {
            node: canonical(
                [classes[node], rewrite_local_refs(definition, node[0], classes)]
            )
            for node, definition in nodes.items()
        }
        identifiers = {
            signature: str(index)
            for index, signature in enumerate(sorted(set(signatures.values())))
        }
        updated = {node: identifiers[signature] for node, signature in signatures.items()}
        same_partition = all(
            (classes[left] == classes[right]) == (updated[left] == updated[right])
            for left in nodes
            for right in nodes
        )
        if same_partition:
            return updated
        classes = updated
    raise RuntimeError("schema definition semantic classes did not converge")


def duplicate_groups(
    documents: dict[Path, dict[str, Any]], classes: dict[tuple[Path, str], str]
) -> list[list[tuple[Path, str]]]:
    groups: dict[str, list[tuple[Path, str]]] = {}
    for node, semantic_class in classes.items():
        groups.setdefault(semantic_class, []).append(node)
    return [
        sorted(nodes, key=lambda node: (node[0].name, node[1]))
        for nodes in groups.values()
        if len({file for file, _ in nodes}) > 1
    ]


def rebase_registry_definition_pointers(
    documents: dict[Path, dict[str, Any]], registry: dict[str, Any]
) -> int:
    """Follow definition aliases for registry pointers that address child fields."""
    schema_dir = next(iter(documents)).parent
    changed = 0
    for entry in registry.get("external_type_fields", []):
        schema_ref = entry.get("schema_ref")
        pointer = entry.get("json_pointer")
        if not isinstance(schema_ref, str) or not isinstance(pointer, str):
            continue
        parts = pointer.split("/")
        if len(parts) < 4 or parts[1] != "$defs":
            continue
        file = schema_dir / Path(schema_ref).name
        name = parts[2]
        seen: set[tuple[Path, str]] = set()
        while (file, name) not in seen:
            seen.add((file, name))
            definition = documents.get(file, {}).get("$defs", {}).get(name)
            if not (isinstance(definition, dict) and set(definition) == {"$ref"}):
                break
            reference = definition["$ref"]
            if not isinstance(reference, str) or "#/$defs/" not in reference:
                break
            path_part, name = reference.split("#/$defs/", 1)
            if path_part:
                file = (file.parent / path_part).resolve()
            entry["schema_ref"] = f"schemas/{file.name}"
            entry["json_pointer"] = f"/$defs/{name}/" + "/".join(parts[3:])
            changed += 1
            parts = entry["json_pointer"].split("/")

    unique: list[dict[str, Any]] = []
    fingerprints: set[bytes] = set()
    for entry in registry.get("external_type_fields", []):
        fingerprint = canonical(entry)
        if fingerprint in fingerprints:
            changed += 1
            continue
        fingerprints.add(fingerprint)
        unique.append(entry)
    registry["external_type_fields"] = unique
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    schema_dir = Path(__file__).resolve().parents[1] / "spec" / "v1" / "artifacts" / "schemas"
    documents = {
        path: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(schema_dir.glob("*.json"))
    }
    registry_path = schema_dir.parent / "registry" / "classification-field-registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    normalized_registry = copy.deepcopy(registry)
    registry_changes = rebase_registry_definition_pointers(documents, normalized_registry)
    groups = duplicate_groups(documents, semantic_classes(documents))
    if not args.write:
        if registry_changes:
            print(
                "classification-field-registry contains definition-child pointers "
                "that must be rebased or deduplicated"
            )
        if groups:
            for group in groups:
                print(", ".join(f"{file.name}#/$defs/{name}" for file, name in group))
        return int(bool(groups or registry_changes))

    changed: set[Path] = set()
    for group in groups:
        host_file, host_name = group[0]
        for file, name in group[1:]:
            if file == host_file:
                reference = f"#/$defs/{host_name}"
            else:
                reference = f"./{host_file.name}#/$defs/{host_name}"
            documents[file]["$defs"][name] = {"$ref": reference}
            changed.add(file)
    for path in sorted(changed):
        path.write_text(
            json.dumps(documents[path], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if registry_changes:
        registry_path.write_text(
            json.dumps(normalized_registry, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"deduplicated {len(groups)} semantic groups across {len(changed)} schema files")
    if registry_changes:
        print(f"rebased/deduplicated {registry_changes} registry definition pointers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
