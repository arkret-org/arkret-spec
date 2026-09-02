"""Overlays on a closed base may only require what the base declares.

`additionalProperties: false` only sees the `properties` / `patternProperties`
of the schema object it sits in, and `unevaluatedProperties: false` only sees
what that object and its own subschemas evaluate. An overlay that reaches such
a base through `$ref` or `allOf` and then requires a member the base never
declares is dead: any instance carrying the member is rejected by the base and
any instance omitting it is rejected by the overlay. `check_schema_constructability`
already proves emptiness for whole intersections, but it accepts a `oneOf`
whenever one branch survives and it treats overlay-declared properties as
evaluated by a referenced base, so a dead branch or a dead `$ref` overlay slips
through. This gate is the structural complement: it compares the explicit
required set after `$ref` / `allOf` / branch folding with the declared set of
every closed base in the same intersection and reports each dead name.
"""

from __future__ import annotations

from .core import ARTIFACTS, Any, Lint, re, walk_json
from .schema_members import (
    explicit_properties,
    explicit_required,
    load_schema_documents,
    own_pattern_properties,
    resolve_ref,
)

SCHEMA_LIKE_KEYS = ("allOf", "oneOf", "anyOf", "then", "else", "$ref", "required")


def _looks_like_schema(node: dict[str, Any]) -> bool:
    if isinstance(node.get("$ref"), str) and len(node) > 1:
        return True
    for keyword in ("allOf", "oneOf", "anyOf", "required"):
        if isinstance(node.get(keyword), list):
            return True
    return any(isinstance(node.get(keyword), dict) for keyword in ("then", "else"))


def _pattern_allows(patterns: list[str], name: str) -> bool:
    for pattern in patterns:
        try:
            if re.search(pattern, name):
                return True
        except re.error:
            continue
    return False


def _closures(
    docs: dict[str, Any],
    file_name: str,
    node: dict[str, Any],
    json_path: str,
) -> list[tuple[str, bool, set[str], list[str]]]:
    """Closed bases of the intersection: (label, is_own_additional, declared names, patterns)."""
    found: list[tuple[str, bool, set[str], list[str]]] = []
    if node.get("additionalProperties") is False:
        found.append((json_path, True, set((node.get("properties") or {}).keys()), own_pattern_properties(node)))
    if node.get("unevaluatedProperties") is False:
        found.append((json_path, False, set(explicit_properties(docs, file_name, node)), own_pattern_properties(node)))
    candidates: list[tuple[str, Any]] = []
    if isinstance(node.get("$ref"), str):
        candidates.append(("$ref", {"$ref": node["$ref"]}))
    for index, branch in enumerate(node.get("allOf") or []):
        if isinstance(branch, dict):
            candidates.append((f"allOf[{index}]", branch))
    for origin, candidate in candidates:
        base_file, pointer, base = resolve_ref(docs, file_name, candidate)
        if not isinstance(base, dict) or base is node:
            continue
        label = f"{base_file}#{pointer}" if pointer is not None else f"{json_path}.{origin}"
        if base.get("additionalProperties") is False:
            found.append((label, False, set((base.get("properties") or {}).keys()), own_pattern_properties(base)))
        if base.get("unevaluatedProperties") is False:
            found.append((label, False, set(explicit_properties(docs, base_file, base)), own_pattern_properties(base)))
    return found


def check_schema_ref_overlay_closure(lint: Lint) -> None:
    docs = load_schema_documents(lint)
    for file_name in sorted(docs):
        document = docs[file_name]
        if not isinstance(document, dict):
            continue
        path = ARTIFACTS / "schemas" / file_name
        reported: set[tuple[str, str, str]] = set()
        for json_path, node, _key in walk_json(document):
            if not isinstance(node, dict) or not _looks_like_schema(node):
                continue
            closures = _closures(docs, file_name, node, json_path)
            if not closures:
                continue
            own_required = {name for name in node.get("required") or [] if isinstance(name, str)}
            required = explicit_required(docs, file_name, node)
            for label, is_own_additional, declared, patterns in closures:
                for name in sorted(required):
                    if name in declared or _pattern_allows(patterns, name):
                        continue
                    if is_own_additional and name in own_required:
                        # check_closed_object_required_declared already owns this shape.
                        continue
                    key = (json_path, name, label)
                    if key in reported:
                        continue
                    reported.add(key)
                    lint.fail(
                        path,
                        f"{json_path} requires {name!r} through an overlay, but closed base {label} "
                        "never declares it; the branch or overlay can match no instance",
                    )
