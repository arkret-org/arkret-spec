"""Two-way closure gates for the two ak.schema.patch.v1 path-protection registries.

zh/models/event-and-patch.md section 4.2 owns both patch-path bans, and each
one used to live only in prose, so an implementation could not derive either
criterion from a machine-readable artifact:

* section 4.2.4, redactable content-carrier slots -- the paths an
  ``$op="unset"`` MUST NOT remove, projected by
  ``redactable-field-registry.json``;
* section 4.2.5, reducer-managed fields -- the paths a generic update surface
  MUST reject at all, projected per object kind by
  ``reducer-managed-path-registry.json``.

Both registries are now the canonical projections. This module keeps prose,
registry and shipped schema from drifting apart in either direction and
enforces the invariants that make each rule sound:

* the plaintext and encrypted forms of one slot always decide identically, so a
  body never becomes removable merely because a Realm is not end-to-end
  encrypted;
* every registered slot keeps a non-terminal clear path, so registering a slot
  can never turn a field into a write-once field;
* every object kind whose update payload embeds the generic patch document is
  classified exactly once, so a new patch surface cannot ship without deciding
  its forbidden set;
* a payload-level ``propertyNames`` guard and the registry agree in both
  directions, so a guard can neither forbid an unregistered path nor omit one
  the registry claims it enforces.
"""

from __future__ import annotations

import re

from .core import (
    ARTIFACTS,
    SPEC_ROOT,
    TOOLS_ROOT,
    Any,
    Lint,
    Path,
    load_json,
    read_text,
)


REGISTRY_PATH = ARTIFACTS / "registry" / "redactable-field-registry.json"

REDUCER_MANAGED_REGISTRY_PATH = ARTIFACTS / "registry" / "reducer-managed-path-registry.json"

EVENT_PAYLOAD_PATH = ARTIFACTS / "schemas" / "event-payload.schema.json"

PROSE_PATH = SPEC_ROOT / "zh" / "models" / "event-and-patch.md"

ERROR_CODE_PATH = ARTIFACTS / "registry" / "error-code-registry.json"

EVENT_KIND_PATH = ARTIFACTS / "registry" / "event-kind-registry.json"

CURRENT_RESULT_REGISTRY_PATH = ARTIFACTS / "registry" / "current-result-registry.json"

REDUCER_MANAGED_OWNER_BASELINE = TOOLS_ROOT / "reducer-managed-owner-baseline.json"

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
    check_reducer_managed_path_registry(lint)


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


# --- zh/models/event-and-patch.md section 4.2.5 ------------------------------

REDUCER_MANAGED_REASON_CODE = "patch_path_reducer_managed"

# The universal path list lives inside one prose bullet, between the phrase that
# introduces it and the parenthetical that explains it. Taking every backtick in
# the bullet would also pick up the reason code and the cross-references.
UNIVERSAL_PROSE_RE = re.compile(r"path MUST NOT 操作 reducer-managed 字段[:：](.*?)\(", re.DOTALL)

PATCH_PATH_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}(\.[a-z][a-z0-9_]{0,63}){0,15}$")

# A payload-level guard forbids a path prefix as `^<path>(?:\.|$)` so the path
# and every dotted descendant fall together, or names exact paths in an enum.
GUARD_PATTERN_RE = re.compile(r"^\^([a-z][a-z0-9_]*)\(\?:\\\.\|\$\)$")

GENERIC_PATCH_REF = "#/$defs/patch"

REDUCER_MANAGED_BASES = frozenset(
    {"create_locked", "reducer_derived", "dedicated_event_owned", "result_projection"}
)

OWNER_KINDS = frozenset({"reducer", "event_kind", "result_family"})

UNIVERSAL_ROW_FIELDS = ("path", "basis", "reason_code", "owner_kind", "owner", "description")

OBJECT_ROW_FIELDS = (
    "object_kind",
    "object_schema_ref",
    "update_payload_refs",
    "universal_exemptions",
    "forbidden_patch_paths",
)

# Optional, but not freely optional. The registry answered "which patch paths
# does the reducer own" without ever saying which typed current result family
# those paths belong to, so a consumer had to guess the target from a family
# name or a field spelling -- and the first one did not even try: it flattened
# every row into one set. `result_family` is absent only where no family is
# registered at all, which for five of the seven object kinds is the case, and
# is the subject the gap owner names.
OBJECT_ROW_OPTIONAL_FIELDS = (
    "result_family",
    "value_schema_ref",
    "value_member_maintenance",
    "value_schema_open_gap_owner",
)

FORBIDDEN_ROW_FIELDS = (
    "path",
    "basis",
    "reason_code",
    "owner_kind",
    "owner",
    "schema_enforced",
    "description",
)

EXEMPTION_ROW_FIELDS = ("path", "owner_kind", "owner", "justification")


def _check_row_value_coverage(
    lint: Lint, path: Path, label: str, row: dict, result_families: set[str]
) -> None:
    """A row declares its result family, and either its value schema or its gap owner.

    `value_member_maintenance` is what makes the member-source closure gate
    measure a family at all, so an undeclared row is an unmeasured family. That
    is defensible -- one report cannot close ten object kinds -- but only when
    the frontier is written down. An optional field with no rule would let the
    frontier grow back silently, one quiet row at a time.
    """
    family = row.get("result_family")
    has_family = isinstance(family, str) and bool(family)
    if has_family and result_families and family not in result_families:
        lint.fail(
            path,
            f"{label}.result_family {family!r} is not registered in current-result-registry.json",
        )
    has_value = isinstance(row.get("value_schema_ref"), str) and row["value_schema_ref"]
    if has_value and not has_family:
        lint.fail(
            path,
            f"{label} declares value_schema_ref without result_family, so nothing says which typed "
            "current result the value belongs to",
        )
    gap_owner = row.get("value_schema_open_gap_owner")
    has_gap = isinstance(gap_owner, str) and gap_owner
    if has_value == has_gap:
        lint.fail(
            path,
            f"{label} must declare exactly one of value_schema_ref (the family value whose members its "
            "ownership rules are solved against) or value_schema_open_gap_owner (the report that closes "
            "it); declaring both, or neither, leaves the coverage frontier unstated",
        )
    if not has_family and not has_gap:
        lint.fail(
            path,
            f"{label} registers reducer-managed paths for an object with no typed current result "
            "family and names no owner for that gap; the paths would then guard a value nothing "
            "writes",
        )
    if "value_member_maintenance" in row and not has_value:
        lint.fail(
            path,
            f"{label} declares value_member_maintenance without value_schema_ref, so there is no value "
            "whose members the maintenance rules could be checked against",
        )


def check_reducer_managed_path_registry(lint: Lint) -> None:
    """Close section 4.2.5 prose, the per-object registry and the shipped schema.

    The generic patch document cannot express a per-object forbidden set, so the
    only machine-readable statement of the rule is this registry plus whatever
    each update payload declares in its own ``propertyNames`` guard. Both halves
    are checked against each other and against the prose minimum set, so no
    implementation has to re-derive the criterion.
    """

    path = REDUCER_MANAGED_REGISTRY_PATH
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    if data.get("source_of_truth") is not True:
        lint.fail(path, "source_of_truth must be true")
    if not isinstance(data.get("description"), str) or not data["description"].strip():
        lint.fail(path, "description must be a non-empty string")
    rules = data.get("registry_rules")
    if not isinstance(rules, list) or not rules or any(
        not isinstance(rule, str) or not rule.strip() for rule in rules
    ):
        lint.fail(path, "registry_rules must be a non-empty string array")

    known_reason_codes = _known_reason_codes(lint)
    declared_reason_codes = data.get("reason_codes")
    if not isinstance(declared_reason_codes, list) or not declared_reason_codes:
        lint.fail(path, "reason_codes must be a non-empty array")
        declared_reason_codes = []
    for code in declared_reason_codes:
        if not isinstance(code, str) or (known_reason_codes and code not in known_reason_codes):
            lint.fail(path, f"reason_codes references unknown reason code: {code!r}")
    if REDUCER_MANAGED_REASON_CODE not in declared_reason_codes:
        lint.fail(path, f"reason_codes must include {REDUCER_MANAGED_REASON_CODE}")

    universal = _check_universal_paths(lint, data, set(declared_reason_codes))
    payload_document = load_json(lint, EVENT_PAYLOAD_PATH)
    patch_bearing = _patch_bearing_payload_defs(payload_document)

    objects = data.get("objects")
    if not isinstance(objects, list) or not objects:
        lint.fail(path, "objects must be a non-empty array")
        return

    seen_kinds: set[str] = set()
    claimed_payloads: dict[str, str] = {}
    active_event_kinds = _active_event_kinds(lint)
    result_families = _registered_result_families(lint)
    baselined_owners = _baselined_unregistered_owners(lint)
    if not result_families:
        # Fail closed. The previous reader returned the empty set on every run
        # and the owner guard short-circuited on it, so "no families" read
        # exactly like "every owner is fine".
        lint.fail(
            CURRENT_RESULT_REGISTRY_PATH,
            "result_kinds[] is empty or unreadable, so the reducer-managed owner guard has "
            "nothing to check owners against; its silence would mean nothing",
        )
    _check_result_family_owner_baseline(lint, data, result_families, baselined_owners)

    for index, row in enumerate(objects):
        label = f"objects[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue
        missing = [field for field in OBJECT_ROW_FIELDS if field not in row]
        if missing:
            lint.fail(path, f"{label} missing field(s): {', '.join(missing)}")
            continue
        unknown = sorted(set(row) - set(OBJECT_ROW_FIELDS) - set(OBJECT_ROW_OPTIONAL_FIELDS))
        if unknown:
            lint.fail(path, f"{label} declares unknown field(s): {', '.join(unknown)}")
        _check_row_value_coverage(lint, path, label, row, result_families)

        object_kind = row["object_kind"]
        if not isinstance(object_kind, str) or not PATCH_PATH_RE.fullmatch(object_kind):
            lint.fail(path, f"{label}.object_kind must be a snake_case object kind")
            continue
        if object_kind in seen_kinds:
            lint.fail(path, f"{label}.object_kind duplicates {object_kind}")
        seen_kinds.add(object_kind)
        label = f"objects[{object_kind}]"

        object_schema = _load_object_schema(lint, path, label, row.get("object_schema_ref"))
        declared_properties: set[str] = set()
        if isinstance(object_schema, dict) and isinstance(object_schema.get("properties"), dict):
            declared_properties = set(object_schema["properties"])

        guards = _collect_payload_guards(
            lint, path, label, row.get("update_payload_refs"), payload_document, claimed_payloads, object_kind
        )

        exemptions = _check_exemptions(
            lint,
            path,
            label,
            row,
            universal,
            declared_properties,
            active_event_kinds,
            result_families,
            baselined_owners,
        )

        extras = _check_object_paths(
            lint,
            path,
            label,
            row,
            universal,
            declared_properties,
            set(declared_reason_codes),
            active_event_kinds,
            result_families,
            baselined_owners,
        )

        effective = (universal.keys() & declared_properties) - exemptions | set(extras)

        for payload_ref, guarded in guards.items():
            for guarded_path in sorted(guarded):
                if guarded_path not in effective:
                    lint.fail(
                        path,
                        f"{label}: {payload_ref} forbids patch path {guarded_path!r} but the registry does not "
                        "register it for this object kind",
                    )
        for extra_path, extra_row in extras.items():
            enforced = [ref for ref, guarded in guards.items() if extra_path in guarded]
            if extra_row.get("schema_enforced") is True and len(enforced) != len(guards):
                lint.fail(
                    path,
                    f"{label}.forbidden_patch_paths[{extra_path}] claims schema_enforced but "
                    f"{sorted(set(guards) - set(enforced))} do not guard it",
                )
            if extra_row.get("schema_enforced") is False and enforced:
                lint.fail(
                    path,
                    f"{label}.forbidden_patch_paths[{extra_path}] declares schema_enforced=false but "
                    f"{enforced} already guard it",
                )

    for payload_ref in sorted(patch_bearing - set(claimed_payloads)):
        lint.fail(
            path,
            f"event-payload.schema.json {payload_ref} embeds the generic patch document but no object row "
            "classifies its reducer-managed path set",
        )

    _check_reducer_managed_error_code_description(lint)


def _check_universal_paths(lint: Lint, data: Any, reason_codes: set[str]) -> dict[str, dict[str, Any]]:
    path = REDUCER_MANAGED_REGISTRY_PATH
    rows = data.get("universal_forbidden_patch_paths")
    universal: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "universal_forbidden_patch_paths must be a non-empty array")
        return universal

    for index, row in enumerate(rows):
        label = f"universal_forbidden_patch_paths[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue
        missing = [field for field in UNIVERSAL_ROW_FIELDS if field not in row]
        if missing:
            lint.fail(path, f"{label} missing field(s): {', '.join(missing)}")
            continue
        unknown = sorted(set(row) - set(UNIVERSAL_ROW_FIELDS))
        if unknown:
            lint.fail(path, f"{label} declares unknown field(s): {', '.join(unknown)}")
        member = row["path"]
        if not isinstance(member, str) or not PATCH_PATH_RE.fullmatch(member):
            lint.fail(path, f"{label}.path must be a canonical patch path")
            continue
        if member in universal:
            lint.fail(path, f"{label}.path duplicates {member}")
        universal[member] = row
        if row["basis"] not in REDUCER_MANAGED_BASES:
            lint.fail(path, f"{label}.basis must be one of {sorted(REDUCER_MANAGED_BASES)}")
        if reason_codes and row["reason_code"] not in reason_codes:
            lint.fail(path, f"{label}.reason_code must be declared in reason_codes")
        if row["owner_kind"] not in OWNER_KINDS:
            lint.fail(path, f"{label}.owner_kind must be one of {sorted(OWNER_KINDS)}")
        for field in ("owner", "description"):
            if not isinstance(row[field], str) or not row[field].strip():
                lint.fail(path, f"{label}.{field} must be a non-empty string")

    prose = _universal_prose_paths(lint)
    if prose is not None:
        for member in sorted(prose - set(universal)):
            lint.fail(
                path,
                f"event-and-patch.md section 4.2.5 lists {member!r} in the general minimum set but the "
                "registry does not",
            )
        for member in sorted(set(universal) - prose):
            lint.fail(
                PROSE_PATH,
                f"reducer-managed-path-registry.json registers {member!r} as universal but section 4.2.5 "
                "does not list it",
            )
    return universal


def _universal_prose_paths(lint: Lint) -> set[str] | None:
    try:
        text = read_text(PROSE_PATH)
    except Exception as exc:  # pragma: no cover - unreadable prose is a hard stop
        lint.fail(PROSE_PATH, f"could not read reducer-managed field prose: {exc}")
        return None

    section = _section_body(text, "#### 4.2.5")
    if section is None:
        lint.fail(PROSE_PATH, "missing section 4.2.5 heading; reducer-managed prose cannot be located")
        return None
    match = UNIVERSAL_PROSE_RE.search(section)
    if match is None:
        lint.fail(PROSE_PATH, "section 4.2.5 no longer spells the reducer-managed general minimum set")
        return None
    members = {
        token
        for token in BACKTICK_TOKEN_RE.findall(match.group(1))
        if PATCH_PATH_RE.fullmatch(token)
    }
    if not members:
        lint.fail(PROSE_PATH, "section 4.2.5 general minimum set is empty")
        return None
    if "reducer-managed-path-registry.json" not in section:
        lint.fail(
            PROSE_PATH,
            "section 4.2.5 must point at registry/reducer-managed-path-registry.json so implementations "
            "read the path set from the registry instead of the prose",
        )
    return members


def _load_object_schema(lint: Lint, path: Path, label: str, schema_ref: Any) -> Any:
    if not isinstance(schema_ref, str) or not schema_ref.startswith("schemas/"):
        lint.fail(path, f"{label}.object_schema_ref must point inside artifacts/schemas")
        return None
    target = ARTIFACTS / schema_ref
    if not target.is_file():
        lint.fail(path, f"{label}.object_schema_ref does not exist: {schema_ref}")
        return None
    return load_json(lint, target)


def _patch_bearing_payload_defs(document: Any) -> set[str]:
    """Every event-payload def whose subtree embeds the generic patch document."""

    if not isinstance(document, dict) or not isinstance(document.get("$defs"), dict):
        return set()
    bearing: set[str] = set()
    for name, definition in document["$defs"].items():
        if name == "patch":
            continue
        if _references_generic_patch(definition):
            bearing.add(f"#/$defs/{name}")
    return bearing


def _references_generic_patch(node: Any) -> bool:
    if isinstance(node, dict):
        if node.get("$ref") == GENERIC_PATCH_REF:
            return True
        return any(_references_generic_patch(child) for child in node.values())
    if isinstance(node, list):
        return any(_references_generic_patch(child) for child in node)
    return False


def _collect_payload_guards(
    lint: Lint,
    path: Path,
    label: str,
    refs: Any,
    document: Any,
    claimed: dict[str, str],
    object_kind: str,
) -> dict[str, set[str]]:
    guards: dict[str, set[str]] = {}
    if not isinstance(refs, list) or not refs:
        lint.fail(path, f"{label}.update_payload_refs must be a non-empty array")
        return guards

    for ref in refs:
        if not isinstance(ref, str) or "#/$defs/" not in ref:
            lint.fail(path, f"{label}.update_payload_refs entry must be an event-payload JSON pointer: {ref!r}")
            continue
        file_part, fragment = ref.split("#", 1)
        pointer = f"#{fragment}"
        if file_part != "schemas/event-payload.schema.json":
            lint.fail(path, f"{label}.update_payload_refs entry must target event-payload.schema.json: {ref!r}")
            continue
        if pointer in claimed:
            lint.fail(
                path,
                f"{label}.update_payload_refs claims {pointer} already classified by object kind "
                f"{claimed[pointer]!r}",
            )
            continue
        claimed[pointer] = object_kind

        definition = _resolve_pointer(document, pointer)
        if definition is None:
            lint.fail(path, f"{label}.update_payload_refs target does not resolve: {ref}")
            continue
        if not _references_generic_patch(definition):
            lint.fail(
                path,
                f"{label}.update_payload_refs target {pointer} does not embed the generic patch document",
            )
            continue
        guarded = _guarded_paths(lint, path, f"{label} {pointer}", definition)
        if guarded is not None:
            guards[pointer] = guarded
    return guards


def _resolve_pointer(document: Any, pointer: str) -> Any:
    node = document
    for token in pointer.lstrip("#").strip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or token not in node:
            return None
        node = node[token]
    return node


def _guarded_paths(lint: Lint, path: Path, label: str, definition: Any) -> set[str] | None:
    """Read the forbidden path tokens out of a payload's patch propertyNames guard."""

    properties = definition.get("properties") if isinstance(definition, dict) else None
    patch_schema = properties.get("patch") if isinstance(properties, dict) else None
    if not isinstance(patch_schema, dict):
        lint.fail(path, f"{label}: payload does not declare a `patch` property")
        return None
    branches = patch_schema.get("allOf") if isinstance(patch_schema.get("allOf"), list) else [patch_schema]
    guarded: set[str] = set()
    for branch in branches:
        if not isinstance(branch, dict):
            continue
        property_names = branch.get("propertyNames")
        if not isinstance(property_names, dict):
            continue
        negated = property_names.get("not")
        if not isinstance(negated, dict):
            lint.fail(path, f"{label}: patch propertyNames guard must be a `not` subschema")
            continue
        unknown = sorted(set(negated) - {"pattern", "enum"})
        if unknown:
            lint.fail(
                path,
                f"{label}: patch propertyNames guard uses unsupported keyword(s) {unknown}; the registry "
                "can only close a `pattern` prefix ban or an exact `enum` ban",
            )
        pattern = negated.get("pattern")
        if isinstance(pattern, str):
            match = GUARD_PATTERN_RE.fullmatch(pattern)
            if match is None:
                lint.fail(
                    path,
                    f"{label}: patch propertyNames pattern {pattern!r} does not use the canonical "
                    "'^<path>(?:\\.|$)' prefix-ban form, so its path set is not machine-readable",
                )
            else:
                guarded.add(match.group(1))
        enum = negated.get("enum")
        if isinstance(enum, list):
            for member in enum:
                if not isinstance(member, str) or not PATCH_PATH_RE.fullmatch(member):
                    lint.fail(path, f"{label}: patch propertyNames enum member {member!r} is not a patch path")
                else:
                    guarded.add(member)
    return guarded


def _check_exemptions(
    lint: Lint,
    path: Path,
    label: str,
    row: dict[str, Any],
    universal: dict[str, dict[str, Any]],
    declared_properties: set[str],
    active_event_kinds: set[str],
    result_families: set[str],
    baselined_owners: dict[str, dict[str, Any]],
) -> set[str]:
    exemptions: set[str] = set()
    rows = row.get("universal_exemptions")
    if not isinstance(rows, list):
        lint.fail(path, f"{label}.universal_exemptions must be an array")
        return exemptions
    for index, exemption in enumerate(rows):
        entry_label = f"{label}.universal_exemptions[{index}]"
        if not isinstance(exemption, dict):
            lint.fail(path, f"{entry_label} must be an object")
            continue
        missing = [field for field in EXEMPTION_ROW_FIELDS if field not in exemption]
        if missing:
            lint.fail(path, f"{entry_label} missing field(s): {', '.join(missing)}")
            continue
        unknown = sorted(set(exemption) - set(EXEMPTION_ROW_FIELDS))
        if unknown:
            lint.fail(path, f"{entry_label} declares unknown field(s): {', '.join(unknown)}")
        member = exemption["path"]
        if member not in universal:
            lint.fail(path, f"{entry_label}.path {member!r} is not in the universal minimum set")
            continue
        if declared_properties and member not in declared_properties:
            lint.fail(
                path,
                f"{entry_label}.path {member!r} is not a declared property of this object schema, so there "
                "is nothing to exempt",
            )
        if not isinstance(exemption["justification"], str) or not exemption["justification"].strip():
            lint.fail(path, f"{entry_label}.justification must name the clause that authorises the carve-out")
        _check_owner(
            lint, path, entry_label, exemption, active_event_kinds, result_families, baselined_owners
        )
        exemptions.add(member)
    return exemptions


def _check_object_paths(
    lint: Lint,
    path: Path,
    label: str,
    row: dict[str, Any],
    universal: dict[str, dict[str, Any]],
    declared_properties: set[str],
    reason_codes: set[str],
    active_event_kinds: set[str],
    result_families: set[str],
    baselined_owners: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    extras: dict[str, dict[str, Any]] = {}
    rows = row.get("forbidden_patch_paths")
    if not isinstance(rows, list):
        lint.fail(path, f"{label}.forbidden_patch_paths must be an array")
        return extras
    for index, entry in enumerate(rows):
        entry_label = f"{label}.forbidden_patch_paths[{index}]"
        if not isinstance(entry, dict):
            lint.fail(path, f"{entry_label} must be an object")
            continue
        missing = [field for field in FORBIDDEN_ROW_FIELDS if field not in entry]
        if missing:
            lint.fail(path, f"{entry_label} missing field(s): {', '.join(missing)}")
            continue
        unknown = sorted(set(entry) - set(FORBIDDEN_ROW_FIELDS))
        if unknown:
            lint.fail(path, f"{entry_label} declares unknown field(s): {', '.join(unknown)}")
        member = entry["path"]
        if not isinstance(member, str) or not PATCH_PATH_RE.fullmatch(member):
            lint.fail(path, f"{entry_label}.path must be a canonical patch path")
            continue
        if member in universal:
            lint.fail(
                path,
                f"{entry_label}.path {member!r} is already in the universal minimum set; per-object rows "
                "MUST NOT restate it",
            )
            continue
        if member in extras:
            lint.fail(path, f"{entry_label}.path duplicates {member}")
        extras[member] = entry
        if declared_properties and member.split(".", 1)[0] not in declared_properties:
            lint.fail(
                path,
                f"{entry_label}.path {member!r} is not a declared property of this object schema",
            )
        if entry["basis"] not in REDUCER_MANAGED_BASES:
            lint.fail(path, f"{entry_label}.basis must be one of {sorted(REDUCER_MANAGED_BASES)}")
        if reason_codes and entry["reason_code"] not in reason_codes:
            lint.fail(path, f"{entry_label}.reason_code must be declared in reason_codes")
        if not isinstance(entry["schema_enforced"], bool):
            lint.fail(path, f"{entry_label}.schema_enforced must be a boolean")
        if not isinstance(entry["description"], str) or not entry["description"].strip():
            lint.fail(path, f"{entry_label}.description must be a non-empty string")
        _check_owner(
            lint, path, entry_label, entry, active_event_kinds, result_families, baselined_owners
        )
    return extras


def _check_owner(
    lint: Lint,
    path: Path,
    label: str,
    row: dict[str, Any],
    active_event_kinds: set[str],
    result_families: set[str],
    baselined_owners: dict[str, dict[str, Any]],
) -> None:
    owner_kind = row.get("owner_kind")
    owner = row.get("owner")
    if owner_kind not in OWNER_KINDS:
        lint.fail(path, f"{label}.owner_kind must be one of {sorted(OWNER_KINDS)}")
        return
    if not isinstance(owner, str) or not owner.strip():
        lint.fail(path, f"{label}.owner must be a non-empty string")
        return
    if owner_kind == "event_kind" and active_event_kinds and owner not in active_event_kinds:
        lint.fail(path, f"{label}.owner references unknown or inactive event kind: {owner!r}")
    if owner_kind == "result_family" and owner not in result_families:
        if owner in baselined_owners:
            return
        lint.fail(
            path,
            f"{label}.owner references a typed current result family that "
            f"current-result-registry.json does not register: {owner!r}",
        )


def _registered_result_families(lint: Lint) -> set[str]:
    """The closed set of typed current result families an owner may name.

    This used to walk `event_kinds[].cell_writes[].cell_family` and, since the
    authority-commit clean break renamed both, always returned the empty set.
    Its one consumer guards with `and cell_families`, so the guard short-circuited
    and every `owner_kind: result_family` owner went unchecked -- three of the
    four live owners turned out to be unregistered.

    `current-result-registry.json` is the right source in any case: it is the
    closed family registry, generated from `contract-registry.json`, and a
    forbidden path that cites a family as its write authority is citing that
    registry's rows, not whichever Event kind happens to write one today.
    """
    data = load_json(lint, CURRENT_RESULT_REGISTRY_PATH)
    if not isinstance(data, dict):
        return set()
    return {
        row["result_kind"]
        for row in data.get("result_kinds") or []
        if isinstance(row, dict) and isinstance(row.get("result_kind"), str)
    }


def _baselined_unregistered_owners(lint: Lint) -> dict[str, dict[str, Any]]:
    data = load_json(lint, REDUCER_MANAGED_OWNER_BASELINE)
    if not isinstance(data, dict):
        return {}
    return {
        row["owner"]: row
        for row in data.get("owners_without_registered_family") or []
        if isinstance(row, dict) and isinstance(row.get("owner"), str)
    }


def _check_result_family_owner_baseline(
    lint: Lint,
    data: Any,
    result_families: set[str],
    baselined: dict[str, dict[str, Any]],
) -> None:
    """The ledger only shrinks: a baselined owner that resolved must leave it."""
    cited: set[str] = set()
    for row in data.get("objects") or []:
        if not isinstance(row, dict):
            continue
        groups = (row.get("forbidden_patch_paths"), row.get("universal_exemptions"))
        for group in groups:
            for entry in group or []:
                if not isinstance(entry, dict):
                    continue
                if entry.get("owner_kind") == "result_family" and isinstance(
                    entry.get("owner"), str
                ):
                    cited.add(entry["owner"])
    for owner in sorted(baselined):
        if owner not in cited:
            lint.fail(
                REDUCER_MANAGED_OWNER_BASELINE,
                f"{owner} is no longer cited as a result_family owner by "
                "reducer-managed-path-registry.json; remove it from "
                "owners_without_registered_family (the ledger only shrinks)",
            )
        elif owner in result_families:
            lint.fail(
                REDUCER_MANAGED_OWNER_BASELINE,
                f"{owner} is now registered in current-result-registry.json; remove it "
                "from owners_without_registered_family (the ledger only shrinks)",
            )


def _known_reason_codes(lint: Lint) -> set[str]:
    data = load_json(lint, ERROR_CODE_PATH)
    if not isinstance(data, dict):
        return set()
    return {
        row.get("code")
        for row in data.get("reason_codes", [])
        if isinstance(row, dict) and isinstance(row.get("code"), str)
    }


def _check_reducer_managed_error_code_description(lint: Lint) -> None:
    """The reason code description must delegate, never restate, the path set."""

    data = load_json(lint, ERROR_CODE_PATH)
    if not isinstance(data, dict):
        return
    for row in data.get("reason_codes", []):
        if not isinstance(row, dict) or row.get("code") != REDUCER_MANAGED_REASON_CODE:
            continue
        description = row.get("description")
        if not isinstance(description, str):
            lint.fail(ERROR_CODE_PATH, f"{REDUCER_MANAGED_REASON_CODE}.description must be a string")
            return
        if "reducer-managed-path-registry.json" not in description:
            lint.fail(
                ERROR_CODE_PATH,
                f"{REDUCER_MANAGED_REASON_CODE}.description must point at "
                "registry/reducer-managed-path-registry.json instead of carrying an illustrative path list",
            )
        return
    lint.fail(ERROR_CODE_PATH, f"missing error code row: {REDUCER_MANAGED_REASON_CODE}")
