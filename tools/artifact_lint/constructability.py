"""Detect structurally empty JSON Schema languages across the schema graph.

This is deliberately a satisfiability gate, not an instance fixture generator.  It
follows references and schema intersections, then proves emptiness only for the
closed structural fragment used by Arkret artifacts.  Unsupported assertions stay
conservative: they cannot make a schema pass by exception, but they also do not
produce speculative failures.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote, urlparse

import re

from .core import ARTIFACTS, Lint, load_json


SCHEMAS = ARTIFACTS / "schemas"
JSON_TYPES = frozenset({"null", "boolean", "object", "array", "number", "integer", "string"})
ANNOTATIONS = frozenset({"$id", "$schema", "$defs", "$comment", "title", "description", "default", "examples", "deprecated", "readOnly", "writeOnly"})
SINGLE_SCHEMA_KEYWORDS = frozenset(
    {
        "additionalProperties",
        "contains",
        "contentSchema",
        "else",
        "if",
        "items",
        "not",
        "propertyNames",
        "then",
        "unevaluatedItems",
        "unevaluatedProperties",
    }
)
ARRAY_SCHEMA_KEYWORDS = frozenset({"allOf", "anyOf", "oneOf", "prefixItems"})
MAP_SCHEMA_KEYWORDS = frozenset(
    {"$defs", "definitions", "dependentSchemas", "patternProperties", "properties"}
)


@dataclass(frozen=True)
class LocatedSchema:
    document: str
    pointer: str
    schema: Any

    @property
    def label(self) -> str:
        return f"{self.document}#{self.pointer.removeprefix('$')}"


@dataclass(frozen=True)
class Conflict:
    location: LocatedSchema
    reason: str

    def render(self, use: LocatedSchema) -> str:
        return f"{use.pointer} is unconstructible: {self.reason} (constraint: {self.location.label})"


def _child_pointer(pointer: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{pointer}[{key}]"
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
        return f"{pointer}.{key}"
    escaped = key.replace("\\", "\\\\").replace("'", "\\'")
    return f"{pointer}['{escaped}']"


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


def _json_key(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _schema_children(node: LocatedSchema) -> list[LocatedSchema]:
    """Return only actual subschemas, never annotation or literal JSON data."""
    if not isinstance(node.schema, dict):
        return []
    children: list[LocatedSchema] = []
    for key, value in node.schema.items():
        key_pointer = _child_pointer(node.pointer, key)
        if key in SINGLE_SCHEMA_KEYWORDS and isinstance(value, dict):
            children.append(LocatedSchema(node.document, key_pointer, value))
        elif key in ARRAY_SCHEMA_KEYWORDS and isinstance(value, list):
            children.extend(
                LocatedSchema(node.document, _child_pointer(key_pointer, index), child)
                for index, child in enumerate(value)
                if isinstance(child, dict)
            )
        elif key in MAP_SCHEMA_KEYWORDS and isinstance(value, dict):
            children.extend(
                LocatedSchema(node.document, _child_pointer(key_pointer, name), child)
                for name, child in value.items()
                if isinstance(child, dict)
            )
    return children


class SchemaGraph:
    def __init__(self, documents: dict[str, Any]) -> None:
        self.documents = documents

    def resolve(self, owner: LocatedSchema, reference: str) -> LocatedSchema | None:
        parsed = urlparse(reference)
        file_part = parsed.path
        fragment = unquote(parsed.fragment)
        if parsed.scheme and parsed.scheme not in {"http", "https"}:
            return None
        if file_part:
            name = PurePosixPath(file_part).name
        else:
            name = owner.document
        document = self.documents.get(name)
        if document is None:
            return None
        value = document
        pointer = "$"
        if fragment:
            if not fragment.startswith("/"):
                return None
            try:
                for raw in fragment[1:].split("/"):
                    token = raw.replace("~1", "/").replace("~0", "~")
                    if isinstance(value, list):
                        value = value[int(token)]
                        pointer = _child_pointer(pointer, int(token))
                    else:
                        value = value[token]
                        pointer = _child_pointer(pointer, token)
            except (KeyError, IndexError, TypeError, ValueError):
                return None
        return LocatedSchema(name, pointer, value)


class ConstructabilityAnalyzer:
    def __init__(self, documents: dict[str, Any]) -> None:
        self.graph = SchemaGraph(documents)

    def analyze(self, use: LocatedSchema) -> Conflict | None:
        return self._conjunction([use], frozenset())

    def _expand_all_of(
        self,
        nodes: list[LocatedSchema],
        resolving: frozenset[tuple[str, str]],
    ) -> tuple[list[LocatedSchema], Conflict | None]:
        expanded: list[LocatedSchema] = []
        pending = list(nodes)
        seen_refs = set(resolving)
        while pending:
            node = pending.pop()
            schema = node.schema
            if schema is False:
                return [], Conflict(node, "contains the boolean false schema")
            if schema is True:
                continue
            if not isinstance(schema, dict):
                continue

            reference = schema.get("$ref")
            if isinstance(reference, str):
                target = self.graph.resolve(node, reference)
                if target is not None:
                    key = (target.document, target.pointer)
                    if key not in seen_refs:
                        seen_refs.add(key)
                        pending.append(target)

            branches = schema.get("allOf")
            if isinstance(branches, list):
                for index, branch in enumerate(branches):
                    pending.append(
                        LocatedSchema(node.document, _child_pointer(_child_pointer(node.pointer, "allOf"), index), branch)
                    )

            remainder = {key: value for key, value in schema.items() if key not in {"$ref", "allOf"}}
            if any(key not in ANNOTATIONS for key in remainder):
                expanded.append(LocatedSchema(node.document, node.pointer, remainder))
        return expanded, None

    def _conjunction(
        self,
        nodes: list[LocatedSchema],
        ancestors: frozenset[tuple[tuple[str, str], ...]],
    ) -> Conflict | None:
        atoms, conflict = self._expand_all_of(nodes, frozenset())
        if conflict is not None:
            return conflict
        fingerprint = tuple(sorted((node.document, node.pointer) for node in atoms))
        if fingerprint in ancestors:
            return Conflict(nodes[0], "requires an infinitely recursive finite JSON value")
        next_ancestors = ancestors | {fingerprint}

        # A union is satisfiable when at least one branch remains satisfiable in
        # the complete surrounding conjunction.  This is what makes nested
        # overlays work instead of testing their branches in isolation.
        for index, atom in enumerate(atoms):
            schema = atom.schema
            if not isinstance(schema, dict):
                continue
            for keyword in ("anyOf", "oneOf"):
                branches = schema.get(keyword)
                if not isinstance(branches, list):
                    continue
                base = {key: value for key, value in schema.items() if key != keyword}
                rest = atoms[:index] + atoms[index + 1 :]
                if any(
                    self._conjunction(
                        rest
                        + [
                            LocatedSchema(atom.document, atom.pointer, base),
                            LocatedSchema(
                                atom.document,
                                _child_pointer(_child_pointer(atom.pointer, keyword), branch_index),
                                branch,
                            ),
                        ],
                        next_ancestors,
                    )
                    is None
                    for branch_index, branch in enumerate(branches)
                ):
                    return None
                return Conflict(atom, f"{keyword} has no constructible branch in the surrounding intersection")

        allowed_types = set(JSON_TYPES)
        candidates: dict[str, Any] | None = None
        for atom in atoms:
            schema = atom.schema
            if not isinstance(schema, dict):
                continue
            declared = schema.get("type")
            if isinstance(declared, str):
                declared_types = {declared}
            elif isinstance(declared, list):
                declared_types = {item for item in declared if isinstance(item, str)}
            else:
                declared_types = set(JSON_TYPES)
            if "number" in declared_types:
                declared_types.add("integer")
            allowed_types &= declared_types

            values: list[Any] | None = None
            if "const" in schema:
                values = [schema["const"]]
            elif isinstance(schema.get("enum"), list):
                values = schema["enum"]
            if values is not None:
                keyed = {_json_key(value): value for value in values}
                candidates = keyed if candidates is None else {
                    key: value for key, value in candidates.items() if key in keyed
                }

            if schema.get("not") == {} or schema.get("not") is True:
                return Conflict(atom, "not rejects every JSON value")

        if not allowed_types:
            return Conflict(atoms[-1] if atoms else nodes[0], "intersected type constraints have no common JSON type")

        if candidates is not None:
            viable = [
                value
                for value in candidates.values()
                if _json_type(value) in allowed_types
                or (_json_type(value) == "integer" and "number" in allowed_types)
            ]
            if not viable:
                return Conflict(atoms[-1] if atoms else nodes[0], "const/enum and type intersections have no common value")
            # Exact object and array candidates need full keyword evaluation to
            # prove emptiness.  Structural object analysis below is still useful
            # when the candidate itself is not the sole source of feasibility.

        type_conflicts: list[Conflict] = []
        for json_type in sorted(allowed_types):
            if json_type == "object":
                candidate_conflict = self._object(atoms, next_ancestors)
            elif json_type == "array":
                candidate_conflict = self._array(atoms, next_ancestors)
            elif json_type == "string":
                candidate_conflict = self._string(atoms)
            elif json_type in {"number", "integer"}:
                candidate_conflict = self._number(atoms, json_type)
            else:
                candidate_conflict = None
            if candidate_conflict is None:
                return None
            type_conflicts.append(candidate_conflict)
        return type_conflicts[0]

    def _object(
        self,
        atoms: list[LocatedSchema],
        ancestors: frozenset[tuple[tuple[str, str], ...]],
    ) -> Conflict | None:
        required_sources: dict[str, LocatedSchema] = {}
        declared_names: set[str] = set()
        local_closures: list[LocatedSchema] = []
        evaluated_closures: list[LocatedSchema] = []
        min_properties = 0
        max_properties: int | None = None
        for atom in atoms:
            schema = atom.schema
            if not isinstance(schema, dict):
                continue
            required = schema.get("required")
            if isinstance(required, list):
                for name in required:
                    if isinstance(name, str):
                        required_sources.setdefault(name, atom)
            dependent = schema.get("dependentRequired")
            if isinstance(dependent, dict):
                # A dependency is only unconditional when its trigger is already
                # required.  Close this finite implication set below.
                pass
            properties = schema.get("properties")
            if isinstance(properties, dict):
                declared_names.update(name for name in properties if isinstance(name, str))
            if schema.get("additionalProperties") is False:
                local_closures.append(atom)
            if schema.get("unevaluatedProperties") is False:
                evaluated_closures.append(atom)
            if isinstance(schema.get("minProperties"), int):
                min_properties = max(min_properties, schema["minProperties"])
            if isinstance(schema.get("maxProperties"), int):
                value = schema["maxProperties"]
                max_properties = value if max_properties is None else min(max_properties, value)

        changed = True
        while changed:
            changed = False
            for atom in atoms:
                schema = atom.schema
                dependent = schema.get("dependentRequired") if isinstance(schema, dict) else None
                if not isinstance(dependent, dict):
                    continue
                for trigger, dependencies in dependent.items():
                    if trigger not in required_sources or not isinstance(dependencies, list):
                        continue
                    for name in dependencies:
                        if isinstance(name, str) and name not in required_sources:
                            required_sources[name] = atom
                            changed = True

        if max_properties is not None and len(required_sources) > max_properties:
            source = next(iter(required_sources.values()), atoms[0])
            return Conflict(source, f"requires {len(required_sources)} properties but maxProperties is {max_properties}")

        for name, source in sorted(required_sources.items()):
            property_nodes: list[LocatedSchema] = []
            for atom in atoms:
                schema = atom.schema
                if not isinstance(schema, dict):
                    continue
                matched = False
                properties = schema.get("properties")
                if isinstance(properties, dict) and name in properties:
                    property_nodes.append(
                        LocatedSchema(atom.document, _child_pointer(_child_pointer(atom.pointer, "properties"), name), properties[name])
                    )
                    matched = True
                patterns = schema.get("patternProperties")
                if isinstance(patterns, dict):
                    for pattern, property_schema in patterns.items():
                        try:
                            matches = re.search(pattern, name) is not None
                        except re.error:
                            matches = False
                        if matches:
                            property_nodes.append(
                                LocatedSchema(atom.document, _child_pointer(_child_pointer(atom.pointer, "patternProperties"), pattern), property_schema)
                            )
                            matched = True
                if not matched and isinstance(schema.get("additionalProperties"), dict):
                    property_nodes.append(
                        LocatedSchema(atom.document, _child_pointer(atom.pointer, "additionalProperties"), schema["additionalProperties"])
                    )

                property_names = schema.get("propertyNames")
                if isinstance(property_names, (dict, bool)):
                    name_conflict = self._conjunction(
                        [
                            LocatedSchema(atom.document, _child_pointer(atom.pointer, "propertyNames"), property_names),
                            LocatedSchema(atom.document, atom.pointer, {"const": name}),
                        ],
                        ancestors,
                    )
                    if name_conflict is not None:
                        return Conflict(source, f"required property {name!r} is rejected by propertyNames at {atom.label}")

            for closure in local_closures:
                if not self._locally_allows(closure, name):
                    return Conflict(
                        source,
                        f"required property {name!r} is forbidden by additionalProperties:false at {closure.label}",
                    )
            if evaluated_closures and name not in declared_names and not any(
                self._matches_pattern(atom, name) for atom in atoms
            ):
                return Conflict(
                    source,
                    f"required property {name!r} is not evaluated before unevaluatedProperties:false at {evaluated_closures[0].label}",
                )
            if property_nodes:
                nested = self._conjunction(property_nodes, ancestors)
                if nested is not None:
                    return Conflict(source, f"required property {name!r} has an empty value language: {nested.reason}")

        if min_properties > len(required_sources):
            finite_names: set[str] | None = None
            for closure in local_closures:
                schema = closure.schema
                patterns = schema.get("patternProperties") if isinstance(schema, dict) else None
                if isinstance(patterns, dict) and patterns:
                    finite_names = None
                    break
                properties = schema.get("properties") if isinstance(schema, dict) else None
                names = set(properties) if isinstance(properties, dict) else set()
                finite_names = names if finite_names is None else finite_names & names
            if finite_names is not None and len(finite_names) < min_properties:
                return Conflict(
                    local_closures[0],
                    f"minProperties is {min_properties}, but intersected closed objects allow at most {len(finite_names)} names",
                )
        return None

    @staticmethod
    def _matches_pattern(atom: LocatedSchema, name: str) -> bool:
        schema = atom.schema
        patterns = schema.get("patternProperties") if isinstance(schema, dict) else None
        if not isinstance(patterns, dict):
            return False
        for pattern in patterns:
            try:
                if re.search(pattern, name):
                    return True
            except re.error:
                continue
        return False

    def _locally_allows(self, atom: LocatedSchema, name: str) -> bool:
        schema = atom.schema
        if not isinstance(schema, dict):
            return True
        properties = schema.get("properties")
        return (isinstance(properties, dict) and name in properties) or self._matches_pattern(atom, name)

    def _array(
        self,
        atoms: list[LocatedSchema],
        ancestors: frozenset[tuple[tuple[str, str], ...]],
    ) -> Conflict | None:
        minimum = 0
        maximum: int | None = None
        item_nodes: list[LocatedSchema] = []
        prefix_nodes: list[list[LocatedSchema]] = []
        for atom in atoms:
            schema = atom.schema
            if not isinstance(schema, dict):
                continue
            if isinstance(schema.get("minItems"), int):
                minimum = max(minimum, schema["minItems"])
            if isinstance(schema.get("maxItems"), int):
                value = schema["maxItems"]
                maximum = value if maximum is None else min(maximum, value)
            if "items" in schema:
                item_nodes.append(LocatedSchema(atom.document, _child_pointer(atom.pointer, "items"), schema["items"]))
            prefix_items = schema.get("prefixItems")
            if isinstance(prefix_items, list):
                while len(prefix_nodes) < len(prefix_items):
                    prefix_nodes.append([])
                for index, item in enumerate(prefix_items):
                    prefix_nodes[index].append(
                        LocatedSchema(
                            atom.document,
                            _child_pointer(_child_pointer(atom.pointer, "prefixItems"), index),
                            item,
                        )
                    )
        if maximum is not None and minimum > maximum:
            return Conflict(atoms[0], f"minItems {minimum} exceeds maxItems {maximum}")
        for index in range(minimum):
            position_nodes = prefix_nodes[index] if index < len(prefix_nodes) else item_nodes
            if not position_nodes:
                continue
            nested = self._conjunction(position_nodes, ancestors)
            if nested is not None:
                return Conflict(
                    position_nodes[0],
                    f"minItems requires item {index}, but that item language is empty: {nested.reason}",
                )
        return None

    @staticmethod
    def _string(atoms: list[LocatedSchema]) -> Conflict | None:
        minimum = 0
        maximum: int | None = None
        source = atoms[0]
        for atom in atoms:
            schema = atom.schema
            if not isinstance(schema, dict):
                continue
            if isinstance(schema.get("minLength"), int):
                minimum = max(minimum, schema["minLength"])
                source = atom
            if isinstance(schema.get("maxLength"), int):
                value = schema["maxLength"]
                maximum = value if maximum is None else min(maximum, value)
        if maximum is not None and minimum > maximum:
            return Conflict(source, f"minLength {minimum} exceeds maxLength {maximum}")
        return None

    @staticmethod
    def _number(atoms: list[LocatedSchema], json_type: str) -> Conflict | None:
        lower: float | int | None = None
        lower_exclusive = False
        upper: float | int | None = None
        upper_exclusive = False
        source = atoms[0]
        for atom in atoms:
            schema = atom.schema
            if not isinstance(schema, dict):
                continue
            candidate_lower = schema.get("exclusiveMinimum")
            candidate_exclusive = isinstance(candidate_lower, (int, float)) and not isinstance(candidate_lower, bool)
            if not candidate_exclusive:
                candidate_lower = schema.get("minimum")
            if isinstance(candidate_lower, (int, float)) and not isinstance(candidate_lower, bool):
                if lower is None or candidate_lower > lower or (candidate_lower == lower and candidate_exclusive):
                    lower, lower_exclusive, source = candidate_lower, candidate_exclusive, atom
            candidate_upper = schema.get("exclusiveMaximum")
            candidate_exclusive = isinstance(candidate_upper, (int, float)) and not isinstance(candidate_upper, bool)
            if not candidate_exclusive:
                candidate_upper = schema.get("maximum")
            if isinstance(candidate_upper, (int, float)) and not isinstance(candidate_upper, bool):
                if upper is None or candidate_upper < upper or (candidate_upper == upper and candidate_exclusive):
                    upper, upper_exclusive = candidate_upper, candidate_exclusive
        if lower is not None and upper is not None:
            if lower > upper or (lower == upper and (lower_exclusive or upper_exclusive)):
                return Conflict(source, f"numeric lower bound {lower} exceeds upper bound {upper}")
            if json_type == "integer":
                import math

                first = math.floor(lower) + 1 if lower_exclusive else math.ceil(lower)
                last = math.ceil(upper) - 1 if upper_exclusive else math.floor(upper)
                if first > last:
                    return Conflict(source, f"numeric interval {lower}..{upper} contains no integer")
        return None


def constructability_errors(documents: dict[str, Any]) -> list[tuple[str, str]]:
    """Return ``(schema file, diagnostic)`` for every provably empty node."""
    analyzer = ConstructabilityAnalyzer(documents)
    errors: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for document_name, document in sorted(documents.items()):
        pending = [LocatedSchema(document_name, "$", document)]
        while pending:
            node = pending.pop()
            if isinstance(node.schema, dict):
                conflict = analyzer.analyze(node)
                if conflict is not None:
                    rendered = conflict.render(node)
                    key = (document_name, rendered)
                    if key not in seen:
                        seen.add(key)
                        errors.append(key)
                pending.extend(_schema_children(node))
    return errors


def check_schema_constructability(lint: Lint) -> None:
    documents = {
        path.name: load_json(lint, path)
        for path in sorted(SCHEMAS.glob("*.schema.json"))
    }
    documents = {name: document for name, document in documents.items() if isinstance(document, dict)}
    for document_name, error in constructability_errors(documents):
        lint.fail(SCHEMAS / document_name, error)
