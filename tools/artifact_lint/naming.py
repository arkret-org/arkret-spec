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
import string
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


# NC-FIELDCASE-001. The only object whose property names escape the Arkret
# snake_case lexicon is one that mirrors an external specification verbatim, and
# it says so on its own schema node rather than in a lint-side name list. The
# annotation is therefore exact by construction: it governs the properties the
# node declares directly and nothing reached through `$ref`, a shared type name
# or a same-named field elsewhere.
EXTERNAL_LITERAL_OBJECT_KEYWORD = "x-arkret-external-literal-object"
EXTERNAL_LITERAL_OBJECT_FIELDS = ("specification", "anchor")
EXTERNAL_ANCHOR_URL_RE = re.compile(r"https://[^\s#]+#\S+\Z")

# Reserved grammar directive keys carry a `$` sigil precisely so they cannot
# collide with the snake_case data-field namespace; the remainder still has to be
# snake_case, so this is a lexical rule and not an escape hatch.
RESERVED_DIRECTIVE_SIGIL = "$"

# The typed-ID namespace token that non-typed identifier value categories must
# stay disjoint from (common-fields.md 2.1).
TYPED_ID_NAMESPACE_PREFIX = "ak:"


class PropertyOccurrence(NamedTuple):
    """One declared property, addressed by RFC 6901 pointer within its schema."""

    file_name: str
    pointer: str
    name: str
    shape: Any


class PropertyOwner(NamedTuple):
    """One object node that declares ``properties``, with its declared names."""

    file_name: str
    pointer: str
    node: Any
    names: tuple[str, ...]


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


def enumerate_property_owners(file_name: str, document: Any) -> Iterator[PropertyOwner]:
    """Yield every object node that declares ``properties``, with its own names.

    ``enumerate_schema_properties`` flattens the same population into individual
    occurrences. NC-FIELDCASE-001 needs the owning node itself, because the
    external-literal annotation lives on the node and MUST NOT reach any property
    the node does not declare directly.
    """

    for pointer, node in enumerate_schema_nodes(file_name, document):
        if not isinstance(node, dict):
            continue
        properties = node.get("properties")
        if not isinstance(properties, dict):
            continue
        yield PropertyOwner(file_name, pointer, node, tuple(properties))


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
    "Wrapper",
    "Info",
    "Details",
    # `Result` reads as a structural answer role, and the closed table already
    # registers `Outcome` for exactly that. The typed current result envelopes
    # are the single exemption: their names are not invented at the call site
    # but derived from `current-result-registry.json`, and
    # `check_typed_current_result_naming` proves that bijection separately.
    "Result",
)

# `_result` survives only inside the schema whose every `$defs` key is pinned to
# a registered `result_kind`.
TYPED_CURRENT_RESULT_SCHEMA = "typed-current-result.schema.json"


def nc_type_001(candidate: str) -> bool:
    """R4: fold acronyms, never stack a wrapper word, never invent a wrapper role."""

    if re.search(r"[A-Z]{2,}", candidate):
        return True
    if stacked_wrapper_words(candidate) is not None:
        return True
    return unregistered_wrapper_word(candidate, DEFAULT_REJECTED_WRAPPER_WORDS) is not None


def request_wrapper_violation(candidate: str, *, domain_object: bool = False) -> bool:
    """Apply R4 to a real operation input, preserving an explicitly signed domain object."""
    return candidate.endswith("Request") and not domain_object


DEFAULT_FORBIDDEN_LEXEMES = frozenset(
    {
        "org",
        "arkret_organization_membership_credential",
    }
)
def forbidden_lexeme_pattern(alias: str) -> re.Pattern[str]:
    snake_clause = rf"(?:^|[_.:/-]){re.escape(alias)}(?=$|[_.:/-])"
    pascal = "".join(word.title() for word in alias.split("_"))
    return re.compile(
        rf"{snake_clause}|(?:^|[a-z0-9]){re.escape(pascal)}(?=$|[A-Z0-9])"
    )


FORBIDDEN_LEXEME_PATTERNS = tuple(
    forbidden_lexeme_pattern(alias) for alias in DEFAULT_FORBIDDEN_LEXEMES
)


def nc_lexeme_001(candidate: str) -> bool:
    """Reject registered shortened aliases on Arkret-owned naming surfaces.

    The registry decides which ordinary words have canonical full spellings;
    this predicate only performs the casing-independent word-boundary check.
    It therefore catches the same alias in ``org_membership``,
    ``OrgMembershipClaim`` and ``ak.profile.org_identity.v1`` without treating
    the letters inside ``organization`` as a match.
    """

    return any(pattern.search(candidate) for pattern in FORBIDDEN_LEXEME_PATTERNS)


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


def split_name_words(name: str) -> list[str]:
    """Split snake_case, camelCase and PascalCase into lowercase words.

    The hash vocabulary is a *word* rule, not a substring or suffix rule. A
    suffix test on the raw string only sees ``_hash``/``_hashes`` and therefore
    lets a camelCase spelling such as ``nextKeyHashes`` through, which turns an
    accidental lexical blind spot into the only thing keeping a field legal.
    Splitting first makes the same judgement in every casing style, while
    keeping words that merely *contain* the letters (``hashtag``) intact.
    """

    words: list[str] = []
    for chunk in name.split("_"):
        if chunk:
            words.extend(re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+", chunk))
    return [word.lower() for word in words]


HASH_WORDS = frozenset({"hash", "hashes"})


def nc_hash_001(candidate: str) -> bool:
    """Hash-vocabulary rule, decided on word boundaries in any casing style.

    A name is rejected when its final word is ``hash``/``hashes`` (the digest
    output spelling, which must be ``<noun>_digest``) or when its head word is
    ``hash`` with a qualifier after it (``hash_profile``, ``hash_algorithm``,
    ``hashAlgorithm``), which is the selector spelling that must be
    ``<noun>_algorithm``.
    """

    words = split_name_words(candidate)
    if not words:
        return False
    if words[-1] in HASH_WORDS:
        return True
    return words[0] == "hash"


def nc_classification_001(candidate: str) -> bool:
    """Four-axis suffix rule; per-field adjudication is registry-owned."""

    return bool(re.search(r"_(?:kind|type|class|tier)_(?:kind|type|class|tier)\Z", candidate))


def nc_fieldcase_001(candidate: str) -> bool:
    """Wire object field names are snake_case (common-fields.md 2, `object`).

    A leading ``$`` marks a reserved grammar directive key rather than a data
    field -- ``ak.schema.patch.v1`` uses ``$op`` exactly so the directive cannot
    collide with a patched field name -- and the remainder is still judged, so
    ``$Op`` is rejected while ``$op`` is not. Whether an *object* is exempt is a
    separate question decided by the schema-level external-literal annotation,
    never by the name.
    """

    name = candidate[1:] if candidate.startswith(RESERVED_DIRECTIVE_SIGIL) else candidate
    return not bool(SNAKE_CASE_RE.fullmatch(name))


def nc_idrole_001(candidate: str) -> bool:
    """Identifier-role legality cannot be decided from a name alone.

    This table entry keeps the narrative rule registered on the same executable
    surface as the other naming rules. The authoritative judgement is
    ``check_identifier_role_suffix_contracts``, which combines the candidate
    with its resolved terminal category, lexical owner, and exact-path registry
    exception. The lexical predicate catches only the canonical bare-role probes
    used by this registry. It is deliberately not the schema gate: a future role
    such as ``signer`` is still rejected by the resolved-terminal walker even
    though the name alone cannot reveal its representation category.
    """

    return candidate in {"issuer", "subject", "audience", "inviter", "invitee"}


def nc_collection_001(candidate: str) -> bool:
    """Lexical probes for the independent collection naming contract.

    The resolved-terminal and exact-path judgement lives in
    ``check_collection_field_contracts``. This predicate only keeps mutation
    probes for unmistakably singular collection candidates on the shared
    naming-rule surface.
    """

    return candidate in {"entry", "item", "member", "status", "class"}


PREDICATES: dict[str, Callable[[str], bool]] = {
    "NC-BOOL-001": nc_bool_001,
    "NC-COUNT-001": nc_count_001,
    "NC-ENUM-001": nc_enum_001,
    "NC-TYPE-001": nc_type_001,
    "NC-LEXEME-001": nc_lexeme_001,
    "NC-CODE-001": nc_code_001,
    "NC-EVIDENCE-001": nc_evidence_001,
    "NC-ARTIFACT-001": nc_artifact_001,
    "NC-SET-001": nc_set_001,
    "NC-HASH-001": nc_hash_001,
    "NC-CLASSIFICATION-001": nc_classification_001,
    "NC-IDROLE-001": nc_idrole_001,
    "NC-COLLECTION-001": nc_collection_001,
    "NC-FIELDCASE-001": nc_fieldcase_001,
}


# --------------------------------------------------------------------------
# Lexical disjointness against the typed-ID namespace (common-fields.md 2.1).
#
# The value-category table calls itself finite and mutually exclusive, which is
# only true if the categories that do not own `ak:` cannot produce a value in it.
# Deciding that from a regex has to be *sound*: every judgement below is a
# sufficient condition, so an unanalysable pattern is reported as undecided and
# never as safe. Two sufficient conditions cover the shapes Arkret schemas use:
#
# 1. the regex cannot emit one of the characters the forbidden prefix needs, so
#    the prefix is unreachable regardless of structure;
# 2. the anchored head provably differs from the forbidden prefix -- a negative
#    lookahead that forbids it, a leading literal that diverges from it, a
#    leading character class that excludes its first character, or a leading
#    group whose every alternative does one of those.
# --------------------------------------------------------------------------

_REGEX_QUANTIFIER_START = "?*"
_REGEX_METACHARACTERS = "^$.|()[]{}*+?\\"
_UNBOUNDED_CLASS_ESCAPES = frozenset({"S", "D", "W"})


def _regex_class_end(pattern: str, start: int) -> int:
    """Return the index of the ``]`` closing the character class opened at ``start``."""

    index = start + 1
    if index < len(pattern) and pattern[index] == "^":
        index += 1
    if index < len(pattern) and pattern[index] == "]":
        index += 1
    while index < len(pattern):
        if pattern[index] == "\\":
            index += 2
            continue
        if pattern[index] == "]":
            return index
        index += 1
    return len(pattern)


def _regex_group_end(pattern: str, start: int) -> int:
    """Return the index of the ``)`` closing the group opened at ``start``."""

    depth = 0
    index = start
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            index += 2
            continue
        if char == "[":
            index = _regex_class_end(pattern, index) + 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return len(pattern)


def _regex_class_members(body: str) -> frozenset[str] | None:
    """Expand a character-class body into its member set, or ``None`` when unbounded."""

    members: set[str] = set()
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\":
            escape = body[index + 1: index + 2]
            if escape in _UNBOUNDED_CLASS_ESCAPES:
                return None
            if escape == "d":
                members |= set(string.digits)
            elif escape == "w":
                members |= set(string.ascii_letters + string.digits + "_")
            elif escape == "s":
                members |= set(" \t\n\r\f\v")
            else:
                members.add(escape)
            index += 2
            continue
        if index + 2 < len(body) and body[index + 1] == "-":
            start_char = char
            end_char = body[index + 2]
            if end_char != "\\" and ord(start_char) <= ord(end_char):
                members |= {chr(code) for code in range(ord(start_char), ord(end_char) + 1)}
                index += 3
                continue
        members.add(char)
        index += 1
    return frozenset(members)


def _regex_class_admits(body: str, char: str) -> bool:
    """Return whether a character class can match ``char``. Unknown means yes."""

    negated = body.startswith("^")
    members = _regex_class_members(body[1:] if negated else body)
    if members is None:
        return True
    return (char not in members) if negated else (char in members)


def _regex_can_emit(pattern: str, char: str) -> bool:
    """Return whether any string the regex matches can contain ``char``."""

    index = 0
    while index < len(pattern):
        current = pattern[index]
        if current == "\\":
            escape = pattern[index + 1: index + 2]
            if escape in _UNBOUNDED_CLASS_ESCAPES or escape == char:
                return True
            index += 2
            continue
        if current == "[":
            end = _regex_class_end(pattern, index)
            if _regex_class_admits(pattern[index + 1:end], char):
                return True
            index = end + 1
            continue
        if current == "." or current == char:
            return True
        index += 1
    return False


def _regex_split_alternatives(pattern: str) -> list[str]:
    """Split one regex body on its top-level ``|``."""

    alternatives: list[str] = []
    depth = 0
    start = 0
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            index += 2
            continue
        if char == "[":
            index = _regex_class_end(pattern, index) + 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "|" and depth == 0:
            alternatives.append(pattern[start:index])
            start = index + 1
        index += 1
    alternatives.append(pattern[start:])
    return alternatives


def _regex_atom_is_optional(pattern: str, index: int) -> bool:
    """Return whether the quantifier at ``index`` lets the preceding atom vanish."""

    if index >= len(pattern):
        return False
    if pattern[index] in _REGEX_QUANTIFIER_START:
        return True
    if pattern[index] == "{":
        end = pattern.find("}", index)
        if end < 0:
            return True
        return pattern[index + 1:end].lstrip().startswith("0")
    return False


def _regex_head_excludes(body: str, forbidden: str) -> bool:
    """Return whether the head of an anchored regex body cannot be ``forbidden``."""

    if not forbidden:
        return False
    if not body:
        # The pattern ends before the forbidden prefix is consumed, so no matching
        # value is long enough to carry it.
        return True
    if body.startswith("(?!"):
        end = _regex_group_end(body, 0)
        inner = body[3:end]
        if inner and forbidden.startswith(inner):
            return True
        return _regex_head_excludes(body[end + 1:], forbidden)
    if body.startswith("("):
        end = _regex_group_end(body, 0)
        if _regex_atom_is_optional(body, end + 1):
            return False
        inner = body[1:end]
        if inner.startswith("?:"):
            inner = inner[2:]
        elif inner.startswith("?"):
            return False
        alternatives = _regex_split_alternatives(inner)
        return all(
            _regex_head_excludes(alternative + body[end + 1:], forbidden)
            for alternative in alternatives
        )
    if body.startswith("["):
        end = _regex_class_end(body, 0)
        if _regex_atom_is_optional(body, end + 1):
            return False
        return not _regex_class_admits(body[1:end], forbidden[0])
    if body.startswith("\\"):
        literal = body[1:2]
        if not literal or literal in "dwsSDWbB":
            return False
        if _regex_atom_is_optional(body, 2):
            return False
        if literal != forbidden[0]:
            return True
        return _regex_head_excludes(body[2:], forbidden[1:])
    if body[0] in _REGEX_METACHARACTERS:
        return False
    if _regex_atom_is_optional(body, 1):
        return False
    if body[0] != forbidden[0]:
        return True
    return _regex_head_excludes(body[1:], forbidden[1:])


def pattern_excludes_prefix(pattern: str, forbidden: str) -> bool:
    """Return whether an anchored ``pattern`` provably rejects every ``forbidden`` prefix."""

    if not pattern.startswith("^"):
        return False
    if any(not _regex_can_emit(pattern, char) for char in set(forbidden)):
        return True
    return _regex_head_excludes(pattern[1:], forbidden)


def terminal_excludes_typed_id_namespace(kind: str, value: str) -> bool | None:
    """Judge one resolved terminal constraint against the ``ak:`` namespace.

    ``True`` means the constraint provably cannot produce an ``ak:`` value,
    ``False`` means it can, and ``None`` means the constraint carries no lexical
    information at all (a bare ``type`` or ``format``) so nothing can be decided
    from it.
    """

    if kind == "pattern":
        return pattern_excludes_prefix(value, TYPED_ID_NAMESPACE_PREFIX)
    if kind == "const":
        return not value.startswith(TYPED_ID_NAMESPACE_PREFIX)
    if kind == "enum":
        return not any(
            member.startswith(TYPED_ID_NAMESPACE_PREFIX) for member in value.split("|")
        )
    return None


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


def _snake_of(word: str) -> str:
    """Render a PascalCase wrapper word as the snake_case tail a `$defs` key uses."""

    return re.sub(r"(?<!^)(?=[A-Z])", "_", word).lower()


def unregistered_snake_wrapper_word(name: str, rejected_words: tuple[str, ...]) -> str | None:
    """`unregistered_wrapper_word` for a snake_case `$defs` key.

    R4 governs one naming axis expressed in two casings: an OpenAPI component
    spells the wrapper role ``Item`` and the `$defs` key spelling the same role
    writes ``_item``. Checking only the PascalCase mirror left 1791 `$defs` keys
    with no wrapper-role gate at all, which is how a whole `_result` family grew
    a fourth meaning without any check failing.
    """

    for word in rejected_words:
        tail = _snake_of(word)
        if name == tail or name.endswith(f"_{tail}"):
            return tail
    return None
