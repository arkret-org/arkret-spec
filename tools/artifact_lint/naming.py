"""Artifact lint: executable naming predicates, full-coverage walker and debt baseline.

This module owns the mechanically decidable portion of common-fields.md 2.0.1
(R1-R8). Three properties are enforced here and must not regress:

1. Traversal completeness. ``enumerate_schema_properties`` is the single walker
   used both by the checks and by the coverage assertion, and it descends into
   ``$defs`` as well as every combinator branch. A separate, deliberately naive
   enumerator recomputes the same population so a walker regression fails the
   lint instead of silently shrinking the checked surface.
2. Exact-path exceptions. Every exception and every temporary debt entry is
   keyed by ``(schema file, RFC 6901 pointer, name)``. Name-only allowlists are
   rejected because they leak an exception granted for one external anchor into
   unrelated Arkret-owned schemas.
3. Executable predicates. The predicate table below is the same code path the
   registered positive/negative cases run against, so a rule cannot be
   "registered" without also being executed.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterator, NamedTuple

FORBIDDEN_BOOLEAN_PREFIXES = ("allow_", "require_", "requires_", "deny_", "force_")
FORBIDDEN_SET_PREFIXES = ("permitted_", "forbidden_", "blocked_", "banned_")
FORBIDDEN_REASON_CODE_NAMES = frozenset({"failure_code", "rejection_code"})
FORBIDDEN_SYMBOLIC_LITERALS = frozenset(
    {
        "mls-rfc9420",
        "mls-exporter-aead-v1",
        "feldman-vss-sha256",
        "pedersen-vss-sha256",
        "share-hash-sha256",
        "share-hash-blake3",
        "arkret-native",
        "moq-relay",
    }
)

# NC-TYPE-001 closed wrapper table. A component may end in at most one of these;
# a name ending in two stacked wrapper words (RequestBodyBody) is a rename
# artifact, not a domain noun.
STRUCTURAL_WRAPPER_WORDS = (
    "RequestBody",
    "Outcome",
    "View",
    "Row",
    "List",
    "Envelope",
    "Ref",
    "Problem",
)

SNAKE_CASE_RE = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*\Z")
PASCAL_CASE_RE = re.compile(r"[A-Z][A-Za-z0-9]*\Z")

SchemaRefResolver = Callable[[str, str], tuple[str, Any] | None]

# Nodes whose keys are user-authored names rather than JSON Schema keywords.
# Descending into them as if they were subschemas would invent property paths.
_NAME_MAP_KEYWORDS = frozenset({"properties", "$defs", "patternProperties", "definitions"})


class PropertyOccurrence(NamedTuple):
    """One declared property, addressed by RFC 6901 pointer within its schema."""

    file_name: str
    pointer: str
    name: str
    shape: Any


class EnumOccurrence(NamedTuple):
    file_name: str
    pointer: str
    values: list[Any]


class TypeNameOccurrence(NamedTuple):
    file_name: str
    pointer: str
    name: str


def _escape(token: str) -> str:
    """RFC 6901 escaping."""

    return token.replace("~", "~0").replace("/", "~1")


def enumerate_schema_nodes(
    file_name: str, node: Any, pointer: str = ""
) -> Iterator[tuple[str, Any]]:
    """Yield every node in a schema document with its RFC 6901 pointer.

    Name-map keywords are traversed through their values but their keys are not
    treated as schema keywords, so ``$defs`` content is reached exactly once.
    """

    yield pointer, node
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{pointer}/{_escape(key)}"
            if key in _NAME_MAP_KEYWORDS and isinstance(value, dict):
                # The map itself is not a schema node. Yielding it would make a
                # property literally named `properties` look like the keyword and
                # invent a phantom path one level deeper.
                for name, shape in value.items():
                    yield from enumerate_schema_nodes(
                        file_name, shape, f"{child}/{_escape(name)}"
                    )
            else:
                yield from enumerate_schema_nodes(file_name, value, child)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from enumerate_schema_nodes(file_name, item, f"{pointer}/{index}")


def enumerate_schema_properties(file_name: str, document: Any) -> Iterator[PropertyOccurrence]:
    """Yield every declared property occurrence, including inside ``$defs``."""

    for pointer, node in enumerate_schema_nodes(file_name, document):
        if not isinstance(node, dict):
            continue
        properties = node.get("properties")
        if not isinstance(properties, dict):
            continue
        for name, shape in properties.items():
            yield PropertyOccurrence(
                file_name,
                f"{pointer}/properties/{_escape(name)}",
                name,
                shape,
            )


def enumerate_schema_enums(file_name: str, document: Any) -> Iterator[EnumOccurrence]:
    for pointer, node in enumerate_schema_nodes(file_name, document):
        if isinstance(node, dict) and isinstance(node.get("enum"), list):
            yield EnumOccurrence(file_name, f"{pointer}/enum", node["enum"])


def enumerate_schema_type_names(file_name: str, document: Any) -> Iterator[TypeNameOccurrence]:
    for pointer, node in enumerate_schema_nodes(file_name, document):
        if not isinstance(node, dict):
            continue
        definitions = node.get("$defs")
        if not isinstance(definitions, dict):
            continue
        for name in definitions:
            yield TypeNameOccurrence(file_name, f"{pointer}/$defs/{_escape(name)}", name)


def naive_property_occurrences(document: Any) -> set[tuple[str, str]]:
    """Independently enumerate every declared property pointer and name.

    Deliberately structure-blind: it recurses through every container and
    collects every key of every ``properties`` object it meets. This must retain
    occurrence identity: comparing names alone would miss a skipped path when
    the same property name is declared elsewhere in the schema.
    """

    found: set[tuple[str, str]] = set()

    def walk(node: Any, pointer: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                child = f"{pointer}/{_escape(key)}"
                if key == "properties" and isinstance(value, dict):
                    for name, shape in value.items():
                        property_pointer = f"{child}/{_escape(name)}"
                        found.add((property_pointer, name))
                        walk(shape, property_pointer)
                else:
                    walk(value, child)
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{pointer}/{index}")

    walk(document, "")
    return found


def naive_property_population(document: Any) -> set[str]:
    """Return distinct property names from the independent occurrence walk."""

    return {name for _pointer, name in naive_property_occurrences(document)}


def schema_shape_has_type(
    file_name: str,
    shape: Any,
    expected_type: str,
    resolve_ref: SchemaRefResolver,
) -> bool:
    """Return whether a property shape admits ``expected_type`` through refs/combinators.

    Applicability cannot rely on an inline ``type`` keyword: Arkret schemas
    routinely project reusable shapes through local and cross-file ``$ref``.
    Reference cycles are cut by their resolved ``(file, ref)`` edge.
    """

    seen_refs: set[tuple[str, str]] = set()

    def visit(current_file: str, node: Any) -> bool:
        if not isinstance(node, dict):
            return False

        declared_type = node.get("type")
        if declared_type == expected_type or (
            isinstance(declared_type, list) and expected_type in declared_type
        ):
            return True
        if expected_type == "boolean":
            if isinstance(node.get("const"), bool):
                return True
            enum_values = node.get("enum")
            if isinstance(enum_values, list) and any(isinstance(value, bool) for value in enum_values):
                return True
        if expected_type == "array" and isinstance(node.get("const"), list):
            return True

        ref = node.get("$ref")
        if isinstance(ref, str):
            edge = (current_file, ref)
            if edge not in seen_refs:
                seen_refs.add(edge)
                resolved = resolve_ref(current_file, ref)
                if resolved is not None and visit(*resolved):
                    return True

        for keyword in ("allOf", "anyOf", "oneOf"):
            branches = node.get(keyword)
            if isinstance(branches, list) and any(visit(current_file, branch) for branch in branches):
                return True
        return False

    return visit(file_name, shape)


# --------------------------------------------------------------------------
# Predicates. Each returns True when the candidate VIOLATES the rule.
# Applicability (is it a boolean? is it an array? is the enum Arkret-owned?) is
# decided by the caller; these functions only judge the name or literal.
# --------------------------------------------------------------------------


def nc_bool_001(candidate: str) -> bool:
    """R1: permission booleans end _allowed, obligation booleans end _required."""

    if candidate.startswith(FORBIDDEN_BOOLEAN_PREFIXES):
        return True
    return bool(re.match(r"(?:no|disallow)_", candidate))


def nc_count_001(candidate: str) -> bool:
    """R2: counts use _count, bytes use _bytes; _len/_length/_size are rejected."""

    return candidate.endswith(("_len", "_length", "_size"))


def nc_enum_001(candidate: str) -> bool:
    """R3: Arkret-owned symbolic enum literals use snake_case."""

    return not bool(SNAKE_CASE_RE.fullmatch(candidate))


DEFAULT_REJECTED_WRAPPER_WORDS = (
    "Candidate",
    "Item",
    "ResponseBody",
    "Response",
    "Request",
    "Wrapper",
    "Info",
    "Details",
)


def nc_type_001(candidate: str) -> bool:
    """R4: fold acronyms, never stack a wrapper word, never invent a wrapper role."""

    if re.search(r"[A-Z]{2,}", candidate):
        return True
    if stacked_wrapper_words(candidate) is not None:
        return True
    return unregistered_wrapper_word(candidate, DEFAULT_REJECTED_WRAPPER_WORDS) is not None


def nc_code_001(candidate: str) -> bool:
    """R5: machine reasons use reason_code / <domain>_reason_code."""

    if candidate in FORBIDDEN_REASON_CODE_NAMES:
        return True
    return bool(re.fullmatch(r"(?:[a-z0-9]+_)*(?:failure|rejection|fault|err)_code", candidate))


def nc_evidence_001(candidate: str) -> bool:
    """R6: `evidence` names a polymorphic container over >= 2 material families.

    Singular-material names such as ``single_signature_evidence`` are rejected
    here; the per-occurrence adjudication itself lives in
    ``evidence-material-audit.json`` because it needs the material inventory,
    not just the token.
    """

    if not candidate.endswith(("_evidence", "evidence")):
        return False
    return bool(
        re.match(
            r"(?:[a-z0-9]+_)*(?:single|sole|lone|one)_[a-z0-9_]*evidence\Z",
            candidate,
        )
    )


def nc_artifact_001(candidate: str) -> bool:
    """R7: artifact filenames are kebab-case."""

    return "_" in candidate


def nc_set_001(candidate: str) -> bool:
    """R8: allowlist/denylist arrays use allowed_ / denied_."""

    return candidate.startswith(FORBIDDEN_SET_PREFIXES)


def nc_hash_001(candidate: str) -> bool:
    """Existing hash-vocabulary rule: no _hash/_hashes, no hash_profile/algorithm."""

    if candidate in {"hash_profile", "hash_algorithm", "hash", "hashes"}:
        return True
    return candidate.endswith(("_hash", "_hashes"))


def nc_classification_001(candidate: str) -> bool:
    """Four-axis suffix rule; per-field adjudication is registry-owned."""

    return bool(re.search(r"_(?:kind|type|class|tier)_(?:kind|type|class|tier)\Z", candidate))


PREDICATES: dict[str, Callable[[str], bool]] = {
    "NC-BOOL-001": nc_bool_001,
    "NC-COUNT-001": nc_count_001,
    "NC-ENUM-001": nc_enum_001,
    "NC-TYPE-001": nc_type_001,
    "NC-CODE-001": nc_code_001,
    "NC-EVIDENCE-001": nc_evidence_001,
    "NC-ARTIFACT-001": nc_artifact_001,
    "NC-SET-001": nc_set_001,
    "NC-HASH-001": nc_hash_001,
    "NC-CLASSIFICATION-001": nc_classification_001,
}


def stacked_wrapper_words(name: str) -> str | None:
    """Return the doubled suffix when a name repeats one wrapper word consecutively.

    Only *consecutive repetition of the same* wrapper role is a defect:
    ``InviteDeliveryRequestBodyBody`` is ``RequestBody`` with a second ``Body``
    welded on by a mechanical rename. Two *different* wrapper words in sequence
    are legitimate, because the inner one is usually an operation verb rather
    than a wrapper: ``IdentityLogListOutcome`` is the outcome of a list
    operation, not a list of outcomes.
    """

    for word in STRUCTURAL_WRAPPER_WORDS:
        if name.endswith(word * 2):
            return word * 2
    # `RequestBody` carries the bare noun `Body` as its own tail, so the doubled
    # form appears as `...RequestBodyBody` rather than `...RequestBodyRequestBody`.
    if name.endswith("BodyBody"):
        return "BodyBody"
    return None


def unregistered_wrapper_word(name: str, rejected_words: tuple[str, ...]) -> str | None:
    """Return the trailing word when a name uses a wrapper role outside the closed table.

    R4 leaves domain subjects unconstrained, so this cannot be "anything not in
    the table". It is driven by an explicit list of words that read as structural
    roles (``Candidate``, ``Item``, ``ResponseBody``) and therefore must be
    expressed with the registered equivalent instead.
    """

    for word in rejected_words:
        if name.endswith(word) and name != word:
            return word
    return None
