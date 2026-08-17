"""Two-way closure gate for the redactable content-carrier slot registry.

zh/models/event-and-patch.md section 4.2.4 used to be the only place the set of
protected paths existed, so an implementation could not derive the criterion
from any machine-readable artifact. The registry is now the canonical
projection; this module keeps prose and registry from drifting apart in either
direction and enforces the two invariants that make the rule sound:

* the plaintext and encrypted forms of one slot always decide identically, so a
  body never becomes removable merely because a Realm is not end-to-end
  encrypted;
* every registered slot keeps a non-terminal clear path, so registering a slot
  can never turn a field into a write-once field.
"""

from __future__ import annotations

import re

from .core import (
    ARTIFACTS,
    SPEC_ROOT,
    Any,
    Lint,
    Path,
    load_json,
    read_text,
)


REGISTRY_PATH = ARTIFACTS / "registry" / "redactable-field-registry.json"

PROSE_PATH = SPEC_ROOT / "zh" / "models" / "event-and-patch.md"

ERROR_CODE_PATH = ARTIFACTS / "registry" / "error-code-registry.json"

EVENT_KIND_PATH = ARTIFACTS / "registry" / "event-kind-registry.json"

REASON_CODE = "patch_unset_redactable_field"

# The prose bullet list is `- <ObjectName>: `path`、`path``; the trailing bullet
# delegates Realm-defined fields to the Realm schema and carries no path.
PROSE_BULLET_RE = re.compile(r"^- (Message|Strand|Morph): (.+)$", re.MULTILINE)

BACKTICK_TOKEN_RE = re.compile(r"`([^`]+)`")

PROSE_OBJECT_KINDS = {"Message": "message", "Strand": "strand", "Morph": "morph"}

# zh/models/event-and-patch.md section 4.2.5: unset is the removal op, so it can
# never be a row's declared clear path.
NON_TERMINAL_CLEAR_OPS = frozenset({"set", "add", "remove"})

# The 2026-08-17 adjudication: metadata is not a content carrier. Registering a
# metadata path would recreate the write-once deadlock the ban must not create.
FORBIDDEN_PATH_PREFIXES = ("metadata", "encrypted_metadata")

REQUIRED_ROW_FIELDS = (
    "object_kind",
    "schema_ref",
    "path",
    "paired_path",
    "non_terminal_clear_op",
    "non_terminal_clear_contract",
    "terminal_clear_event_kinds",
    "description",
)


def _schema_property_exists(schema: Any, document: Any, path: str) -> bool:
    """Resolve a dotted patch path against a JSON Schema object document."""

    node = _resolve_local_ref(schema, document)
    for segment in path.split("."):
        if not isinstance(node, dict):
            return False
        properties = node.get("properties")
        if not isinstance(properties, dict) or segment not in properties:
            return False
        node = _resolve_local_ref(properties[segment], document)
    return node is not None


def _resolve_local_ref(node: Any, document: Any) -> Any:
    seen = 0
    while isinstance(node, dict) and isinstance(node.get("$ref"), str) and seen < 8:
        ref = node["$ref"]
        if not ref.startswith("#/"):
            return node
        target: Any = document
        for token in ref[2:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, dict) or token not in target:
                return None
            target = target[token]
        node = target
        seen += 1
    return node


def _prose_paths(lint: Lint) -> set[tuple[str, str]] | None:
    try:
        text = read_text(PROSE_PATH)
    except Exception as exc:  # pragma: no cover - unreadable prose is a hard stop
        lint.fail(PROSE_PATH, f"could not read redactable slot prose: {exc}")
        return None

    section = _section_body(text, "#### 4.2.4")
    if section is None:
        lint.fail(PROSE_PATH, "missing section 4.2.4 heading; redactable slot prose cannot be located")
        return None

    pairs: set[tuple[str, str]] = set()
    for match in PROSE_BULLET_RE.finditer(section):
        object_kind = PROSE_OBJECT_KINDS[match.group(1)]
        for token in BACKTICK_TOKEN_RE.findall(match.group(2)):
            pairs.add((object_kind, token))
    if not pairs:
        lint.fail(PROSE_PATH, "section 4.2.4 declares no per-object redactable slot paths")
        return None
    return pairs


def _section_body(text: str, heading_prefix: str) -> str | None:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith(heading_prefix):
            start = index + 1
            break
    if start is None:
        return None
    body: list[str] = []
    for line in lines[start:]:
        if line.startswith("#### ") or line.startswith("### ") or line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


def check_redactable_field_registry(lint: Lint) -> None:
    data = load_json(lint, REGISTRY_PATH)
    if not isinstance(data, dict):
        return

    if data.get("source_of_truth") is not True:
        lint.fail(REGISTRY_PATH, "source_of_truth must be true")
    if not isinstance(data.get("description"), str) or not data["description"].strip():
        lint.fail(REGISTRY_PATH, "description must be a non-empty string")
    rules = data.get("registry_rules")
    if not isinstance(rules, list) or not rules or any(
        not isinstance(rule, str) or not rule.strip() for rule in rules
    ):
        lint.fail(REGISTRY_PATH, "registry_rules must be a non-empty string array")

    rows = data.get("redactable_fields")
    if not isinstance(rows, list) or not rows:
        lint.fail(REGISTRY_PATH, "redactable_fields must be a non-empty array")
        return

    active_event_kinds = _active_event_kinds(lint)
    registered: dict[tuple[str, str], dict[str, Any]] = {}
    schema_cache: dict[str, Any] = {}

    for index, row in enumerate(rows):
        label = f"redactable_fields[{index}]"
        if not isinstance(row, dict):
            lint.fail(REGISTRY_PATH, f"{label} must be an object")
            continue

        missing = [field for field in REQUIRED_ROW_FIELDS if field not in row]
        if missing:
            lint.fail(REGISTRY_PATH, f"{label} missing field(s): {', '.join(missing)}")
            continue
        unknown = sorted(set(row) - set(REQUIRED_ROW_FIELDS))
        if unknown:
            lint.fail(REGISTRY_PATH, f"{label} declares unknown field(s): {', '.join(unknown)}")

        object_kind = row["object_kind"]
        path = row["path"]
        if object_kind not in set(PROSE_OBJECT_KINDS.values()):
            lint.fail(REGISTRY_PATH, f"{label}.object_kind must be one of message, strand, morph")
            continue
        if not isinstance(path, str) or not path:
            lint.fail(REGISTRY_PATH, f"{label}.path must be a non-empty string")
            continue
        key = (object_kind, path)
        if key in registered:
            lint.fail(REGISTRY_PATH, f"{label} duplicates ({object_kind}, {path})")
        registered[key] = row

        first_segment = path.split(".", 1)[0]
        if first_segment in FORBIDDEN_PATH_PREFIXES:
            lint.fail(
                REGISTRY_PATH,
                f"{label}.path {path!r} is metadata, not a content-carrier slot; registering it would "
                "make an optional field write-once (see event-and-patch.md section 4.2.4)",
            )

        schema_ref = row["schema_ref"]
        if not isinstance(schema_ref, str) or not schema_ref.startswith("schemas/"):
            lint.fail(REGISTRY_PATH, f"{label}.schema_ref must point inside artifacts/schemas")
        else:
            schema_path = ARTIFACTS / schema_ref
            if not schema_path.is_file():
                lint.fail(REGISTRY_PATH, f"{label}.schema_ref does not exist: {schema_ref}")
            else:
                document = schema_cache.get(schema_ref)
                if document is None:
                    document = load_json(lint, schema_path)
                    schema_cache[schema_ref] = document
                if isinstance(document, dict) and not _schema_property_exists(document, document, path):
                    lint.fail(
                        REGISTRY_PATH,
                        f"{label}.path {path!r} is not a declared property of {schema_ref}",
                    )

        clear_op = row["non_terminal_clear_op"]
        if clear_op not in NON_TERMINAL_CLEAR_OPS:
            lint.fail(
                REGISTRY_PATH,
                f"{label}.non_terminal_clear_op must be one of {sorted(NON_TERMINAL_CLEAR_OPS)}; "
                "a registered slot MUST keep a non-terminal clear path",
            )
        if not isinstance(row["non_terminal_clear_contract"], str) or not row["non_terminal_clear_contract"].strip():
            lint.fail(REGISTRY_PATH, f"{label}.non_terminal_clear_contract must be a non-empty string")
        if not isinstance(row["description"], str) or not row["description"].strip():
            lint.fail(REGISTRY_PATH, f"{label}.description must be a non-empty string")

        terminal_kinds = row["terminal_clear_event_kinds"]
        if not isinstance(terminal_kinds, list) or not terminal_kinds:
            lint.fail(REGISTRY_PATH, f"{label}.terminal_clear_event_kinds must be a non-empty array")
        else:
            for kind in terminal_kinds:
                if not isinstance(kind, str) or kind not in active_event_kinds:
                    lint.fail(
                        REGISTRY_PATH,
                        f"{label}.terminal_clear_event_kinds references unknown or inactive event kind: {kind!r}",
                    )

    # Slot pairing must be symmetric: the plaintext and encrypted forms of one
    # slot are the same slot, so a decision can never apply to only one of them.
    for (object_kind, path), row in registered.items():
        paired_path = row.get("paired_path")
        if not isinstance(paired_path, str) or not paired_path:
            lint.fail(REGISTRY_PATH, f"({object_kind}, {path}).paired_path must be a non-empty string")
            continue
        if paired_path == path:
            lint.fail(REGISTRY_PATH, f"({object_kind}, {path}).paired_path must name the other slot form")
            continue
        partner = registered.get((object_kind, paired_path))
        if partner is None:
            lint.fail(
                REGISTRY_PATH,
                f"({object_kind}, {path}).paired_path {paired_path!r} is not registered for the same object kind",
            )
            continue
        if partner.get("paired_path") != path:
            lint.fail(
                REGISTRY_PATH,
                f"({object_kind}, {path}) and ({object_kind}, {paired_path}) are not mutually paired",
            )

    prose_pairs = _prose_paths(lint)
    if prose_pairs is not None:
        for missing_pair in sorted(prose_pairs - set(registered)):
            lint.fail(
                REGISTRY_PATH,
                f"event-and-patch.md section 4.2.4 lists {missing_pair[0]}.{missing_pair[1]} but the registry does not",
            )
        for extra_pair in sorted(set(registered) - prose_pairs):
            lint.fail(
                PROSE_PATH,
                f"redactable-field-registry.json registers {extra_pair[0]}.{extra_pair[1]} but section 4.2.4 does not list it",
            )

    _check_error_code_description(lint)


def _active_event_kinds(lint: Lint) -> set[str]:
    data = load_json(lint, EVENT_KIND_PATH)
    if not isinstance(data, dict):
        return set()
    return {
        row.get("event_kind")
        for row in data.get("event_kinds", [])
        if isinstance(row, dict)
        and row.get("status") == "active"
        and isinstance(row.get("event_kind"), str)
    }


def _check_error_code_description(lint: Lint) -> None:
    """The reason code description must delegate, never restate, the path set."""

    data = load_json(lint, ERROR_CODE_PATH)
    if not isinstance(data, dict):
        return
    for row in data.get("reason_codes", []):
        if not isinstance(row, dict) or row.get("code") != REASON_CODE:
            continue
        description = row.get("description")
        if not isinstance(description, str):
            lint.fail(ERROR_CODE_PATH, f"{REASON_CODE}.description must be a string")
            return
        if "redactable-field-registry.json" not in description:
            lint.fail(
                ERROR_CODE_PATH,
                f"{REASON_CODE}.description must point at registry/redactable-field-registry.json "
                "instead of carrying an illustrative path list",
            )
        for forbidden in ("metadata.summary", "encrypted_metadata"):
            if f"strand.{forbidden}" in description or f"morph.{forbidden}" in description:
                lint.fail(
                    ERROR_CODE_PATH,
                    f"{REASON_CODE}.description still names {forbidden} as a protected path",
                )
        return
    lint.fail(ERROR_CODE_PATH, f"missing error code row: {REASON_CODE}")
