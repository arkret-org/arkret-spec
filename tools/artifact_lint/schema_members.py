"""Explicit member sets of schema objects after `$ref`, `allOf` and branch overlays.

Several gates need the same question answered: which property names does a
schema object declare once its `$ref` chain, `allOf` mixins and `oneOf` /
`anyOf` / `then` / `else` branches are folded in, and which names does it
require through the same overlays. `if` and `not` never contribute: a
`required` inside `if` is a condition, a `required` inside `not` is a
prohibition. The helpers here are deliberately structural; they do not decide
satisfiability and they do not read prose.
"""

from __future__ import annotations

from .core import ARTIFACTS, Any, Lint, load_json

SCHEMAS = ARTIFACTS / "schemas"

BRANCH_KEYWORDS = ("allOf", "oneOf", "anyOf")

CONDITIONAL_KEYWORDS = ("then", "else")

MAX_DEPTH = 12


def load_schema_documents(lint: Lint) -> dict[str, Any]:
    return {
        path.name: load_json(lint, path)
        for path in sorted(SCHEMAS.glob("*.schema.json"))
    }


def pointer_segments(fragment: str) -> list[str]:
    return [
        segment.replace("~1", "/").replace("~0", "~")
        for segment in fragment.lstrip("#").split("/")
        if segment
    ]


def walk_pointer(document: Any, fragment: str) -> Any:
    """Resolve a JSON Pointer (with or without a leading #); None when it misses."""
    node = document
    for segment in pointer_segments(fragment):
        if isinstance(node, dict) and segment in node:
            node = node[segment]
        elif isinstance(node, list) and segment.isdigit() and int(segment) < len(node):
            node = node[int(segment)]
        else:
            return None
    return node


def locate(docs: dict[str, Any], schema_ref: str) -> tuple[str, str, Any]:
    """Resolve `schemas/<file>#<pointer>` or `<file>#<pointer>` to (file, pointer, node-or-None)."""
    file_part, _, fragment = schema_ref.partition("#")
    file_name = file_part.split("/")[-1]
    document = docs.get(file_name)
    if document is None:
        return file_name, fragment, None
    return file_name, fragment, walk_pointer(document, fragment)


def resolve_ref(docs: dict[str, Any], file_name: str, node: Any) -> tuple[str, str | None, Any]:
    """Follow a `$ref` chain to its terminal node: (file, pointer-or-None, node)."""
    pointer: str | None = None
    depth = 0
    while isinstance(node, dict) and isinstance(node.get("$ref"), str) and depth < MAX_DEPTH:
        file_part, _, fragment = node["$ref"].partition("#")
        target_file = file_part.removeprefix("./").split("/")[-1] or file_name
        document = docs.get(target_file)
        if document is None:
            return file_name, pointer, node
        target = walk_pointer(document, fragment)
        if target is None:
            return file_name, pointer, node
        file_name, pointer, node, depth = target_file, fragment, target, depth + 1
    return file_name, pointer, node


def explicit_properties(
    docs: dict[str, Any],
    file_name: str,
    node: Any,
    depth: int = 0,
) -> dict[str, tuple[str, Any]]:
    """Every property name the object declares through `$ref`, `allOf` and branches.

    The first declaration wins so the returned subschema is the nearest one.
    """
    found: dict[str, tuple[str, Any]] = {}
    if depth > MAX_DEPTH or not isinstance(node, dict):
        return found
    properties = node.get("properties")
    if isinstance(properties, dict):
        for name, subschema in properties.items():
            found.setdefault(name, (file_name, subschema))
    if isinstance(node.get("$ref"), str):
        target_file, _, target = _ref_target(docs, file_name, node["$ref"])
        if target is not None:
            for name, located in explicit_properties(docs, target_file, target, depth + 1).items():
                found.setdefault(name, located)
    for keyword in BRANCH_KEYWORDS:
        for branch in node.get(keyword) or []:
            for name, located in explicit_properties(docs, file_name, branch, depth + 1).items():
                found.setdefault(name, located)
    for keyword in CONDITIONAL_KEYWORDS:
        branch = node.get(keyword)
        if isinstance(branch, dict):
            for name, located in explicit_properties(docs, file_name, branch, depth + 1).items():
                found.setdefault(name, located)
    return found


def explicit_required(docs: dict[str, Any], file_name: str, node: Any, depth: int = 0) -> set[str]:
    """Every name the object requires through `$ref`, `allOf` and branches (never `if` / `not`)."""
    found: set[str] = set()
    if depth > MAX_DEPTH or not isinstance(node, dict):
        return found
    required = node.get("required")
    if isinstance(required, list):
        found.update(name for name in required if isinstance(name, str))
    if isinstance(node.get("$ref"), str):
        target_file, _, target = _ref_target(docs, file_name, node["$ref"])
        if target is not None:
            found |= explicit_required(docs, target_file, target, depth + 1)
    for keyword in BRANCH_KEYWORDS:
        for branch in node.get(keyword) or []:
            found |= explicit_required(docs, file_name, branch, depth + 1)
    for keyword in CONDITIONAL_KEYWORDS:
        branch = node.get(keyword)
        if isinstance(branch, dict):
            found |= explicit_required(docs, file_name, branch, depth + 1)
    return found


def own_pattern_properties(node: Any) -> list[str]:
    patterns = node.get("patternProperties") if isinstance(node, dict) else None
    return [pattern for pattern in (patterns or {}) if isinstance(pattern, str)]


def _ref_target(docs: dict[str, Any], file_name: str, reference: str) -> tuple[str, str, Any]:
    file_part, _, fragment = reference.partition("#")
    target_file = file_part.removeprefix("./").split("/")[-1] or file_name
    document = docs.get(target_file)
    if document is None:
        return target_file, fragment, None
    return target_file, fragment, walk_pointer(document, fragment)
