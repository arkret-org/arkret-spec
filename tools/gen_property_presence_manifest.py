#!/usr/bin/env python3
"""Generate property-presence-manifest.json.

Every schema property has a wire presence contract that a strongly typed SDK
must reproduce exactly. ``required``, ``nullable`` and ``default`` are three
independent axes, and their combination decides whether a receiver can tell
"absent", "explicit null" and "concrete value" apart:

  required              the property must be present; absent is a violation.
  required_nullable     the property must be present but may carry null;
                        absent and null are different wire facts.
  tristate              optional and nullable with no default, so absent,
                        explicit null and a value are three accepted wire
                        spellings. Their business semantics come from the
                        presence disposition below, not from JSON Schema alone.
  optional_defaulted    optional with a schema default; omission means the
                        default, so absent and the default value agree.
  optional              optional and never null; absent is the only extra
                        state.

The manifest is a derived artifact: the schema documents stay canonical. The
drift check turns any change of a property's presence class into a reviewed
change, which is what stops a tristate field from being silently degraded on
either the schema side or the SDK side.

Usage:
  python tools/gen_property_presence_manifest.py [generate|check]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
SCHEMA_DIR = ARTIFACTS / "schemas"
SCHEMA_REGISTRY = ARTIFACTS / "registry" / "schema-registry.json"
MANIFEST = ARTIFACTS / "reports" / "property-presence-manifest.json"

REFERENCE_RE = re.compile(
    r"^(?:https://arkret\.org/v1/schemas/|\./|\.\./schemas/)?([A-Za-z0-9._-]+\.json)(#.*)?$"
)
MAX_REFERENCE_DEPTH = 8


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def load_documents() -> dict[str, Any]:
    return {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(SCHEMA_DIR.glob("*.json"))
    }


def load_schema_ids() -> dict[tuple[str, str], list[str]]:
    """Map (document, fragment) to the logical schema IDs bound to it."""

    registry = json.loads(SCHEMA_REGISTRY.read_text(encoding="utf-8"))
    bindings: dict[tuple[str, str], list[str]] = {}
    for row in registry.get("schemas", []):
        schema_id = row.get("schema_id")
        file_ref = row.get("file")
        if not isinstance(schema_id, str) or not isinstance(file_ref, str):
            continue
        document, separator, inline_fragment = file_ref.partition("#")
        fragment = row.get("fragment")
        if not isinstance(fragment, str):
            fragment = f"#{inline_fragment}" if separator else "#"
        key = (Path(document).name, fragment)
        bindings.setdefault(key, []).append(schema_id)
    return {key: sorted(value) for key, value in bindings.items()}


def resolve_pointer(document: Any, pointer: str) -> Any:
    node = document
    for part in pointer.lstrip("#/").split("/"):
        if not part:
            continue
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return None
    return node


def resolve_reference(
    documents: dict[str, Any], reference: str, current: str
) -> tuple[Any, str]:
    if reference.startswith("#"):
        return resolve_pointer(documents[current], reference), current
    match = REFERENCE_RE.match(reference)
    if not match:
        return None, current
    target = match.group(1)
    if target not in documents:
        return None, current
    return resolve_pointer(documents[target], match.group(2) or "#"), target


def is_nullable(documents: dict[str, Any], node: Any, current: str, depth: int = 0) -> bool:
    """Evaluate whether JSON null satisfies the applicable schema assertions."""

    if node is True:
        return True
    if node is False or depth > MAX_REFERENCE_DEPTH or not isinstance(node, dict):
        return False
    declared = node.get("type")
    if declared is not None and declared != "null" and not (
        isinstance(declared, list) and "null" in declared
    ):
        return False
    if "const" in node and node["const"] is not None:
        return False
    if isinstance(node.get("enum"), list) and None not in node["enum"]:
        return False

    reference = node.get("$ref")
    if isinstance(reference, str):
        target, target_document = resolve_reference(documents, reference, current)
        if target is None or not is_nullable(
            documents, target, target_document, depth + 1
        ):
            return False

    if any(
        not is_nullable(documents, branch, current, depth + 1)
        for branch in node.get("allOf", []) or []
    ):
        return False
    any_of = node.get("anyOf", []) or []
    if any_of and not any(
        is_nullable(documents, branch, current, depth + 1) for branch in any_of
    ):
        return False
    one_of = node.get("oneOf", []) or []
    if one_of and sum(
        is_nullable(documents, branch, current, depth + 1) for branch in one_of
    ) != 1:
        return False
    if isinstance(node.get("not"), (dict, bool)) and is_nullable(
        documents, node["not"], current, depth + 1
    ):
        return False

    condition = node.get("if")
    if isinstance(condition, (dict, bool)):
        selected = "then" if is_nullable(documents, condition, current, depth + 1) else "else"
        branch = node.get(selected)
        if isinstance(branch, (dict, bool)) and not is_nullable(
            documents, branch, current, depth + 1
        ):
            return False
    return True


def required_axes(
    documents: dict[str, Any], node: Any, current: str, depth: int = 0
) -> tuple[set[str], set[str]]:
    """Return property names required always and only on some schema paths.

    ``if`` is intentionally not traversed as an assertion: in Draft 2020-12 it
    only selects ``then`` or ``else``. ``allOf`` applies every branch, while a
    name is unconditionally required by ``anyOf`` / ``oneOf`` only when every
    branch requires it.
    """

    if depth > MAX_REFERENCE_DEPTH or not isinstance(node, dict):
        return set(), set()
    always = {
        name for name in node.get("required", []) if isinstance(name, str)
    }
    conditional: set[str] = set()

    reference = node.get("$ref")
    if isinstance(reference, str):
        target, target_document = resolve_reference(documents, reference, current)
        target_always, target_conditional = required_axes(
            documents, target, target_document, depth + 1
        )
        always |= target_always
        conditional |= target_conditional

    for branch in node.get("allOf", []) or []:
        branch_always, branch_conditional = required_axes(
            documents, branch, current, depth + 1
        )
        always |= branch_always
        conditional |= branch_conditional

    for keyword in ("anyOf", "oneOf"):
        branch_axes = [
            required_axes(documents, branch, current, depth + 1)
            for branch in node.get(keyword, []) or []
        ]
        if branch_axes:
            shared = set.intersection(*(branch_always for branch_always, _ in branch_axes))
            possible = set.union(
                *(branch_always | branch_conditional for branch_always, branch_conditional in branch_axes)
            )
            always |= shared
            conditional |= possible - shared

    then_axes = required_axes(documents, node.get("then"), current, depth + 1)
    else_axes = required_axes(documents, node.get("else"), current, depth + 1)
    if then_axes != (set(), set()) or else_axes != (set(), set()):
        shared = then_axes[0] & else_axes[0]
        possible = then_axes[0] | then_axes[1] | else_axes[0] | else_axes[1]
        always |= shared
        conditional |= possible - shared

    return always, conditional - always


def presence_class(required: bool, nullable: bool, has_default: bool) -> str:
    if required and nullable:
        return "required_nullable"
    if required:
        return "required"
    if nullable and not has_default:
        return "tristate"
    if has_default:
        return "optional_defaulted"
    return "optional"


def collect_rows(documents: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def walk(
        document_name: str,
        node: Any,
        pointer: str,
        shape: str,
        instance_path: str,
    ) -> None:
        if not isinstance(node, dict):
            return
        properties = node.get("properties")
        if isinstance(properties, dict):
            required, conditional = required_axes(documents, node, document_name)
            for name, child in properties.items():
                child_pointer = f"{pointer}/properties/{name}"
                nullable = is_nullable(documents, child, document_name)
                has_default = isinstance(child, dict) and "default" in child
                is_required = name in required
                rows.append(
                    {
                        "schema_file": document_name,
                        "pointer": child_pointer,
                        "shape": shape,
                        "instance_path": f"{instance_path}/{name}",
                        "conditionally_required": name in conditional,
                        "presence_class": presence_class(is_required, nullable, has_default),
                        "declared_presence_semantics": (
                            child.get("x-arkret-presence-semantics")
                            if isinstance(child, dict)
                            else None
                        ),
                    }
                )
                walk(
                    document_name,
                    child,
                    child_pointer,
                    shape,
                    f"{instance_path}/{name}",
                )
        for keyword in ("oneOf", "anyOf", "allOf", "prefixItems"):
            for index, branch in enumerate(node.get(keyword, []) or []):
                walk(
                    document_name,
                    branch,
                    f"{pointer}/{keyword}/{index}",
                    shape,
                    instance_path,
                )
        for keyword in ("if", "then", "else", "items", "contains", "not"):
            branch = node.get(keyword)
            if isinstance(branch, dict):
                nested_instance = (
                    f"{instance_path}/*" if keyword in {"items", "contains"} else instance_path
                )
                walk(
                    document_name,
                    branch,
                    f"{pointer}/{keyword}",
                    shape,
                    nested_instance,
                )
        for container in ("$defs", "patternProperties", "additionalProperties"):
            branch = node.get(container)
            if container == "additionalProperties":
                if isinstance(branch, dict):
                    walk(
                        document_name,
                        branch,
                        f"{pointer}/{container}",
                        shape,
                        f"{instance_path}/*",
                    )
                continue
            if isinstance(branch, dict):
                for name, child in branch.items():
                    child_pointer = f"{pointer}/{container}/{name}"
                    if container == "$defs":
                        walk(document_name, child, child_pointer, child_pointer, "")
                    else:
                        walk(
                            document_name,
                            child,
                            child_pointer,
                            shape,
                            f"{instance_path}/{{{name}}}",
                        )

    for document_name, document in documents.items():
        walk(document_name, document, "", "#", "")
    rows.sort(key=lambda row: (row["schema_file"], row["pointer"]))
    return rows


def build_manifest() -> dict[str, Any]:
    documents = load_documents()
    schema_ids = load_schema_ids()
    rows = collect_rows(documents)

    class_counts: dict[str, int] = {}
    for row in rows:
        class_counts[row["presence_class"]] = class_counts.get(row["presence_class"], 0) + 1

    tristate = [
        f"{row['schema_file']}{row['pointer']}"
        for row in rows
        if row["presence_class"] == "tristate"
    ]
    tristate_targets: dict[tuple[str, str, str], list[str]] = {}
    for row in rows:
        if row["presence_class"] != "tristate":
            continue
        key = (row["schema_file"], row["shape"], row["instance_path"])
        tristate_targets.setdefault(key, []).append(row["pointer"])
    tristate_audit_targets = []
    disposition_counts: dict[str, int] = {}
    for (schema_file, shape, instance_path), occurrences in sorted(
        tristate_targets.items()
    ):
        matching_rows = [
            row
            for row in rows
            if row["schema_file"] == schema_file
            and row["shape"] == shape
            and row["instance_path"] == instance_path
            and row["presence_class"] == "tristate"
        ]
        declared = {
            row["declared_presence_semantics"]
            for row in matching_rows
            if row["declared_presence_semantics"] is not None
        }
        unknown = declared - {"distinct"}
        if unknown:
            raise SystemExit(
                f"{schema_file} {shape} {instance_path} has unknown "
                f"x-arkret-presence-semantics values {sorted(unknown)}"
            )
        if "distinct" in declared:
            disposition = "distinct"
            rationale = (
                "The schema explicitly declares x-arkret-presence-semantics=distinct; "
                "the SDK must preserve Missing / Null / Value."
            )
        elif any(row["conditionally_required"] for row in matching_rows):
            disposition = "condition_guarded"
            rationale = (
                "A conditional branch requires this property. Draft 2020-12 validation "
                "rejects missing in that branch; explicit null remains the branch's empty value."
            )
        else:
            disposition = "absent_null_equivalent"
            rationale = (
                "encoding.md §2.1.1 applies the v1 default: absent and explicit null "
                "are the same empty value, and canonical producers omit the property."
            )
        disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1
        tristate_audit_targets.append(
            {
            "schema_file": schema_file,
            "shape": shape,
            "instance_path": instance_path,
            "occurrences": sorted(occurrences),
            "sdk_disposition": disposition,
            "rationale": rationale,
        }
        )

    by_document: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = by_document.setdefault(
            row["schema_file"], {"schema_ids": [], "properties": {}}
        )
        entry["properties"][row["pointer"]] = row["presence_class"]
        if row["conditionally_required"]:
            entry.setdefault("conditionally_required", []).append(row["pointer"])
    for (document_name, fragment), ids in sorted(schema_ids.items()):
        entry = by_document.get(document_name)
        if entry is None:
            continue
        for schema_id in ids:
            binding = schema_id if fragment == "#" else f"{schema_id} -> {fragment}"
            entry["schema_ids"].append(binding)

    return {
        "schema": "arkret.property-presence-manifest.v1",
        "source_of_truth": False,
        "generated_by": "tools/gen_property_presence_manifest.py",
        "generated_from": ["spec/v1/artifacts/schemas/*.json", "spec/v1/artifacts/registry/schema-registry.json"],
        "description": (
            "Per-property wire presence contract derived from the schema documents. "
            "required, nullable and default are independent axes; presence_class is "
            "their normative combination. An SDK MUST reproduce the class exactly: a "
            "tristate property needs an explicit SDK disposition: the protocol-wide default "
            "normalizes absent/null, conditional requiredness is enforced by the Draft runtime, "
            "and only x-arkret-presence-semantics=distinct requires Missing / Null / Value. Repeated conditional "
            "schema occurrences are also grouped into semantic audit targets by shape and "
            "instance path so SDK audits do not count the same DTO field multiple times."
        ),
        "presence_class_definitions": {
            "required": "must be present and never null.",
            "required_nullable": "must be present and may be null; absent and null are different wire facts.",
            "tristate": "optional, nullable, no default; absent, explicit null and a value are three accepted wire spellings whose semantics require a disposition.",
            "optional_defaulted": "optional with a schema default; omission means the default.",
            "optional": "optional and never null.",
        },
        "summary": {
            "total_properties": len(rows),
            "total_schema_documents": len(documents),
            "by_presence_class": dict(sorted(class_counts.items())),
            "tristate_occurrences": len(tristate),
            "tristate_audit_targets": len(tristate_audit_targets),
            "tristate_sdk_dispositions": dict(sorted(disposition_counts.items())),
        },
        "sdk_disposition_definitions": {
            "distinct": "business semantics distinguish Missing / Null / Value; SDK must preserve all three.",
            "condition_guarded": "missing is invalid in an applicable conditional branch and is enforced before typed decoding.",
            "absent_null_equivalent": "v1 default normalization; SDK uses an optional value and canonical output omits None.",
        },
        "tristate_properties": tristate,
        "tristate_audit_targets": tristate_audit_targets,
        "documents": by_document,
    }


def write_manifest() -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(dump_json(build_manifest()), encoding="utf-8", newline="\n")
    print(f"updated {MANIFEST.relative_to(ROOT).as_posix()}")


def check_manifest() -> int:
    expected = dump_json(build_manifest())
    if not MANIFEST.exists():
        print(
            f"missing {MANIFEST.relative_to(ROOT).as_posix()} "
            "(run python tools/gen_property_presence_manifest.py)",
            file=sys.stderr,
        )
        return 1
    if MANIFEST.read_text(encoding="utf-8") != expected:
        print(
            f"property presence manifest drift: {MANIFEST.relative_to(ROOT).as_posix()} "
            "(run python tools/gen_property_presence_manifest.py)",
            file=sys.stderr,
        )
        return 1
    print("property presence manifest: clean")
    return 0


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "generate"
    if mode == "check":
        return check_manifest()
    write_manifest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
