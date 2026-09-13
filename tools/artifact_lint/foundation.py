"""Artifact lint phase 1: foundation."""

from __future__ import annotations

import base64
import hashlib

from .core import (
    ARTIFACTS,
    Any,
    CELL_FAMILY_RE,
    CELL_SUBJECT_COMPONENT_ONLY_KINDS,
    CELL_SUBJECT_KINDS,
    CELL_WRITE_DERIVATIONS,
    CONFLICT_RECOVERY_KIND,
    TOOLS_ROOT,
    NOTARY_CELL_FAMILY,
    Counter,
    EFFECT_PROJECTION_ENVELOPE_FIELDS,
    ENVELOPE_SUBJECT_SOURCES,
    FIELD_PATH_RE,
    FORBIDDEN_OPERATION_ACTIONS,
    Lint,
    OPERATION_ID_RE,
    OPERATION_KINDS,
    PROFILE_ID_RE,
    Path,
    REGISTRY_STATE_MODELS,
    REGISTRY_PLANES,
    ROOT,
    SCHEMA_ID_RE,
    SPEC_ROOT,
    VALUE_PROJECTION_DIGEST_INPUTS,
    NORMALIZED_STRING_SET_CONTEXTS,
    VALUE_PROJECTION_DERIVATIONS,
    VALUE_PROJECTION_IDENTITY_SUBJECTS,
    json,
    load_json,
    load_yaml,
    markdown_files,
    raw_artifact_files,
    re,
    read_text,
    resolve_json_pointer,
    walk_json,
)


# encoding.md 4.1 closed subject dispatch table (ruling 2026-09-05-1200). A
# top-level cell_subject.kind MUST be one of these or the `id:<object kind>`
# form; canonical_json and string_set_digest are components[] descriptors only.
CELL_SUBJECT_KINDS = frozenset(
    {"did", "typed_id", "string", "uri", "coalesce", "composite", "tuple"}
)
CELL_SUBJECT_ID_KIND_RE = re.compile(r"^id:[a-z][a-z0-9_]*$")


def is_registered_cell_subject_kind(kind: str) -> bool:
    return kind in CELL_SUBJECT_KINDS or CELL_SUBJECT_ID_KIND_RE.fullmatch(kind) is not None


def unique_values(lint: Lint, path: Path, rows: Any, key: str) -> set[str]:
    values: set[str] = set()
    seen: dict[str, int] = {}
    if not isinstance(rows, list):
        lint.fail(path, f"expected list for {key} rows")
        return values

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            lint.fail(path, f"row {index} is not an object")
            continue
        value = row.get(key)
        if not isinstance(value, str) or not value:
            lint.fail(path, f"row {index} has missing or non-string {key}")
            continue
        if value in seen:
            lint.fail(path, f"duplicate {key} {value!r} at rows {seen[value]} and {index}")
        seen[value] = index
        values.add(value)
    return values



def text_contract_files() -> list[Path]:
    files: set[Path] = set(markdown_files())
    files.update(raw_artifact_files())
    files.update(sorted((SPEC_ROOT / "en").rglob("*.md")))
    files.add(ROOT / "CHANGELOG.md")
    files.add(SPEC_ROOT / "release-metadata.json")
    files.add(ROOT / "site" / "src" / "lib" / "site-meta.ts")
    return sorted(path for path in files if path.is_file())


HISTORY_RESPONSE_MACHINE_FORBIDDEN_RE = re.compile(
    r"history[ _-]mailbox|reply[_-]mailbox|history[_-]reply|reply[_-]history"
    r"|arkret-mailbox|closed[_-]mailbox[_-]delivery"
    r"|(?:history[-_ ]?key|history response|history recovery).{0,100}\b(?:mailbox|inbox)\b",
    re.IGNORECASE,
)
HISTORY_RESPONSE_PROSE_FORBIDDEN_RE = re.compile(r"\b(?:mailbox|inbox|reply)\b", re.IGNORECASE)


def history_response_naming_violations(text: str, *, strict_prose: bool = False) -> list[tuple[int, str]]:
    """Return forbidden retired history-response terms with one-based line numbers."""
    pattern = (
        HISTORY_RESPONSE_PROSE_FORBIDDEN_RE
        if strict_prose
        else HISTORY_RESPONSE_MACHINE_FORBIDDEN_RE
    )
    return [
        (line_number, match.group(0))
        for line_number, line in enumerate(text.splitlines(), 1)
        for match in pattern.finditer(line)
    ]


def check_history_response_naming(lint: Lint) -> None:
    """Prevent reintroduction of the retired second history stream identity."""
    for directory in ("schemas", "registry", "openapi", "bindings", "profiles"):
        root = ARTIFACTS / directory
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
            for line_number, token in history_response_naming_violations(read_text(path)):
                lint.fail(
                    path,
                    f"retired history response machine term {token!r} at line {line_number}",
                )

    prose_path = SPEC_ROOT / "zh" / "governance" / "history-visibility.md"
    for line_number, token in history_response_naming_violations(
        read_text(prose_path), strict_prose=True
    ):
        lint.fail(
            prose_path,
            f"retired history response prose term {token!r} at line {line_number}",
        )



def check_registry_manifest(lint: Lint) -> None:
    path = ARTIFACTS / "registry" / "registry-manifest.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    if data.get("source_of_truth") is not True:
        lint.fail(path, "source_of_truth must be true")

    rows = data.get("registries")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "registries must be a non-empty list")
        return

    seen_names: set[str] = set()
    seen_files: set[str] = set()
    listed_files: set[str] = set()
    entries_by_file: dict[str, dict[str, Any]] = {}
    actual_files = {
        f"registry/{candidate.name}"
        for candidate in sorted((ARTIFACTS / "registry").glob("*.json"))
    }

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            lint.fail(path, f"registries[{index}] must be an object")
            continue
        name = row.get("name")
        file_ref = row.get("file")
        kind = row.get("kind")
        source_role = row.get("source_role")
        source_of_truth = row.get("source_of_truth")
        generated_from = row.get("generated_from")
        description = row.get("description")

        if not isinstance(name, str) or not name:
            lint.fail(path, f"registries[{index}].name must be a non-empty string")
            continue
        if name in seen_names:
            lint.fail(path, f"duplicate registry name {name!r}")
        seen_names.add(name)

        if not isinstance(file_ref, str) or not file_ref:
            lint.fail(path, f"registries[{index}].file must be a non-empty string")
            continue
        if file_ref in seen_files:
            lint.fail(path, f"duplicate registry file {file_ref!r}")
        seen_files.add(file_ref)
        listed_files.add(file_ref)
        entries_by_file[file_ref] = row
        if Path(file_ref).is_absolute() or ".." in Path(file_ref).parts:
            lint.fail(path, f"registries[{index}].file escapes artifacts/: {file_ref}")
            continue
        if not file_ref.startswith("registry/"):
            lint.fail(path, f"registries[{index}].file must stay inside artifacts/registry: {file_ref}")
            continue
        target = ARTIFACTS / file_ref
        if not target.exists():
            lint.fail(path, f"registries[{index}].file does not exist: {file_ref}")

        if not isinstance(kind, str) or not kind:
            lint.fail(path, f"registries[{index}].kind must be a non-empty string")
        if source_role not in {"canonical", "generated"}:
            lint.fail(path, f"registries[{index}].source_role must be canonical or generated")
        if source_role == "canonical":
            if source_of_truth is not True:
                lint.fail(path, f"registries[{index}].source_of_truth must be true for canonical entries")
            if generated_from not in {None, ""}:
                lint.fail(path, f"registries[{index}] canonical entry must not declare generated_from")
        elif source_role == "generated":
            if source_of_truth is not False:
                lint.fail(path, f"registries[{index}].source_of_truth must be false for generated entries")
            if not isinstance(generated_from, str) or not generated_from:
                lint.fail(path, f"registries[{index}].generated_from must be a non-empty string")
            elif Path(generated_from).is_absolute() or ".." in Path(generated_from).parts:
                lint.fail(path, f"registries[{index}].generated_from escapes artifacts/: {generated_from}")
            elif not (ARTIFACTS / generated_from.split("#", 1)[0]).exists():
                lint.fail(path, f"registries[{index}].generated_from does not exist: {generated_from}")
        if not isinstance(description, str) or not description.strip():
            lint.fail(path, f"registries[{index}].description must be a non-empty string")

    for file_ref, row in entries_by_file.items():
        if row.get("source_role") != "generated":
            continue
        generated_from = row.get("generated_from")
        source_file = generated_from.split("#", 1)[0] if isinstance(generated_from, str) else ""
        if generated_from not in entries_by_file and source_file.startswith("profiles/"):
            continue
        if generated_from not in entries_by_file:
            lint.fail(path, f"generated registry {file_ref} references unlisted source {generated_from!r}")
            continue
        source_row = entries_by_file[generated_from]
        if source_row.get("source_role") != "canonical":
            lint.fail(path, f"generated registry {file_ref} must reference a canonical source entry")

    for file_ref in sorted(actual_files - listed_files):
        lint.fail(path, f"registry manifest missing file {file_ref}")
    for file_ref in sorted(listed_files - actual_files):
        lint.fail(path, f"registry manifest lists unknown file {file_ref}")



def lint_select_component(
    lint: Lint,
    path: Path,
    ref: str,
    component: object,
    *,
    subject_source: bool = False,
) -> None:
    """Validate a discriminated `select` cell-subject component (encoding.md 9.5.1).

    A select component picks one scalar field path from a closed branch map keyed by
    the literal value of a discriminator field. Unknown component kinds, missing
    selectors and empty or malformed branch maps are fail-closed lint errors so a
    registry can never leave a subject partially derivable.
    """
    # A malformed registry must produce a lint failure, never an exception:
    # the release gate has to report the problem, not abort on it.
    if not isinstance(component, dict):
        lint.fail(path, f"{ref} must be a select component object")
        return
    component_kind = component.get("kind")
    if component_kind != "select":
        lint.fail(path, f"{ref}.kind must be 'select'; unknown component kinds are rejected")
        return
    lint_path = lint_subject_field_path if subject_source else lint_field_path
    lint_path(lint, path, f"{ref}.selector", component.get("selector"))
    branches = component.get("branches")
    if not isinstance(branches, dict) or not branches:
        lint.fail(path, f"{ref}.branches must be a non-empty object")
        return
    for branch_key, branch in branches.items():
        branch_ref = f"{ref}.branches[{branch_key}]"
        if not isinstance(branch_key, str) or not branch_key:
            lint.fail(path, f"{branch_ref} key must be a non-empty discriminator value")
        if not isinstance(branch, dict):
            lint.fail(path, f"{branch_ref} must be an object")
            continue
        lint_path(lint, path, f"{branch_ref}.field", branch.get("field"))
        # Exclusivity is declared per branch, never inferred from "some other
        # branch's field is present": branches may legitimately share a field.
        if "forbidden_fields" in branch:
            forbidden = branch.get("forbidden_fields")
            if not isinstance(forbidden, list) or not forbidden:
                lint.fail(path, f"{branch_ref}.forbidden_fields must be a non-empty array")
            else:
                for forbidden_index, item in enumerate(forbidden):
                    lint_path(
                        lint, path, f"{branch_ref}.forbidden_fields[{forbidden_index}]", item
                    )
            if isinstance(forbidden, list) and branch.get("field") in forbidden:
                lint.fail(path, f"{branch_ref}.forbidden_fields must not contain its own field")
        unknown_branch_keys = set(branch) - {"field", "forbidden_fields"}
        if unknown_branch_keys:
            lint.fail(path, f"{branch_ref} has unknown member(s) {sorted(unknown_branch_keys)}")
    if "transform" in component and component["transform"] != "base64url_utf8":
        lint.fail(path, f"{ref}.transform must be base64url_utf8")
    unknown_keys = set(component) - {"kind", "selector", "branches", "transform"}
    if unknown_keys:
        lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown_keys)}")



def lint_string_set_digest_component(
    lint: Lint,
    path: Path,
    ref: str,
    component: object,
    *,
    event_kind: str,
) -> None:
    """Validate the closed `string_set_digest` descriptor surface."""
    if not isinstance(component, dict):
        lint.fail(path, f"{ref} must be a string_set_digest component object")
        return
    unknown_keys = set(component) - {"kind", "field", "context"}
    if unknown_keys:
        lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown_keys)}")
    if component.get("kind") != "string_set_digest":
        lint.fail(path, f"{ref}.kind must be 'string_set_digest'")
    lint_subject_field_path(lint, path, f"{ref}.field", component.get("field"))
    context = component.get("context")
    if (
        not isinstance(context, str)
        or not context
        or not context.isascii()
        or any(ord(character) < 0x20 or ord(character) > 0x7E for character in context)
    ):
        lint.fail(path, f"{ref}.context must be non-empty printable ASCII")
    if (
        event_kind == "ak.identity.accountability_grant"
        and context != "ak.accountability_scope_set.v1"
    ):
        lint.fail(
            path,
            f"{ref}.context must be 'ak.accountability_scope_set.v1' for {event_kind}",
        )



def lint_derived_members(lint: Lint, path: Path, ref: str, members: object) -> None:
    """Validate a cell write's registered reducer derivations."""
    if not isinstance(members, list) or not members:
        lint.fail(path, f"{ref} must be a non-empty array")
        return
    seen_names: set[str] = set()
    for index, member in enumerate(members):
        member_ref = f"{ref}[{index}]"
        if not isinstance(member, dict):
            lint.fail(path, f"{member_ref} must be an object")
            continue
        unknown = set(member) - {"name", "derivation"}
        if unknown:
            lint.fail(path, f"{member_ref} has unknown member(s) {sorted(unknown)}")
        name = member.get("name")
        if not isinstance(name, str) or not name:
            lint.fail(path, f"{member_ref}.name must be a non-empty string")
        elif name in seen_names:
            lint.fail(path, f"{member_ref}.name duplicates another member")
        else:
            seen_names.add(name)
        derivation = member.get("derivation")
        if derivation not in CELL_WRITE_DERIVATIONS:
            lint.fail(
                path,
                f"{member_ref}.derivation must be one of {sorted(CELL_WRITE_DERIVATIONS)}",
            )



def lint_field_path(lint: Lint, path: Path, ref: str, value: object) -> None:
    """Validate one registered dot-separated named-field path."""
    if not isinstance(value, str) or not value:
        lint.fail(path, f"{ref} must be a non-empty field path")
        return
    if FIELD_PATH_RE.fullmatch(value) is None:
        lint.fail(
            path,
            f"{ref} must be dot-separated named fields "
            f"(no array index, wildcard or empty segment): {value!r}",
        )



def lint_conflict_recovery_write(lint, event_path, write_ref, kind, write):
    """Reject every arbitrary target/reset escape from registered Cell effects."""
    lint.fail(event_path, f"{write_ref}: dynamic cell_ref/reset writes are forbidden; use registered authorized effects")


def lint_subject_field_path(lint: Lint, path: Path, ref: str, value: object) -> None:
    """Validate an explicitly sourced cell-subject field path."""
    lint_field_path(lint, path, ref, value)
    if not isinstance(value, str) or FIELD_PATH_RE.fullmatch(value) is None:
        return
    if value.startswith("payload.") or value in ENVELOPE_SUBJECT_SOURCES or (value == "item.key_id" and "ak.agent.key.authorize cell_writes[0]" in ref):
        return
    if value.startswith("envelope."):
        lint.fail(path, f"{ref} uses an unregistered envelope source: {value!r}")
        return
    lint.fail(
        path,
        f"{ref} must use an explicit payload.* or "
        f"{' / '.join(ENVELOPE_SUBJECT_SOURCES)} source: {value!r}",
    )



def _lint_cell_subject_kind(lint: Lint, path: Path, ref: str, subject: object) -> None:
    """Pin `cell_subject.kind` to the closed set of encoding.md 4.1.

    That table names itself the complete list of legal `cell_subject` shapes and
    forbids two rows applying to one field. `canonical_json` and
    `string_set_digest` are `components[]` descriptors with no row of their own,
    so a structured single-field subject MUST be a one-component composite; the
    top-level spelling would have no defined embedding at all.
    """
    if subject is None:
        # A JSON `null` subject is the registered per-Realm singleton form.
        return
    if not isinstance(subject, dict):
        lint.fail(path, f"{ref}.cell_subject must be an object or JSON null")
        return
    subject_kind = subject.get("kind")
    if subject_kind in CELL_SUBJECT_COMPONENT_ONLY_KINDS:
        field = subject.get("field")
        spelled = (
            f'{{"kind":"composite","components":[{{"kind":{subject_kind!r},"field":{field!r}}}]}}'
        )
        lint.fail(
            path,
            f"{ref}.cell_subject.kind {subject_kind!r} is a components[] descriptor, "
            f"not a top-level subject kind; spell it as {spelled}",
        )
        return
    if isinstance(subject_kind, str) and subject_kind.startswith("id:"):
        return
    if subject_kind not in CELL_SUBJECT_KINDS:
        lint.fail(
            path,
            f"{ref}.cell_subject.kind must be one of "
            f"{sorted(CELL_SUBJECT_KINDS)} or id:<object kind>: {subject_kind!r}",
        )


def lint_cell_write_condition(lint: Lint, path: Path, ref: str, condition: object) -> None:
    """Validate the closed `condition` grammar of a conditional cell write.

    See zh/models/event-and-patch.md section 2.4.2: a conditional target
    participates only when the condition holds, and the grammar is closed so the
    predicate stays a pure function of the schema-validated signed Event.
    """
    if not isinstance(condition, dict):
        lint.fail(path, f"{ref} must be an object")
        return
    allowed_kinds = {
        "field_present",
        "field_absent",
        "field_equals",
        "any_field_present",
        "critical_ref_role_exact_count",
    }
    condition_kind = condition.get("kind")
    if condition_kind not in allowed_kinds:
        lint.fail(path, f"{ref}.kind must be one of {sorted(allowed_kinds)}")
        return
    # zh/conformance/encoding.md 9.5.1: a registry field source is explicitly
    # sourced. A bare name would reintroduce the "try payload, then envelope"
    # fallback that section makes undefined, and a condition decides whether a
    # cell write happens at all, so an undefined source there is worse than in a
    # subject. Every registered condition already carries the prefix, so this is
    # a zero-baseline rule rather than a ratchet.
    for member in ("field", "fields"):
        value = condition.get(member)
        candidates = value if isinstance(value, list) else [value]
        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, str) or candidate.startswith("payload."):
                continue
            where = f"{ref}.{member}" if member == "field" else f"{ref}.{member}[{index}]"
            lint.fail(
                path,
                f"{where} must be an explicitly sourced payload path: {candidate!r}",
            )
    if condition_kind == "any_field_present":
        unknown = set(condition) - {"kind", "fields"}
        if unknown:
            lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown)}")
        fields = condition.get("fields")
        if not isinstance(fields, list) or len(fields) < 2:
            lint.fail(path, f"{ref}.fields must be an array of at least two field paths")
            return
        for index, field in enumerate(fields):
            lint_field_path(lint, path, f"{ref}.fields[{index}]", field)
        if len(fields) != len({repr(field) for field in fields}):
            lint.fail(path, f"{ref}.fields must not repeat a path")
        return
    if condition_kind == "critical_ref_role_exact_count":
        unknown = set(condition) - {"kind", "role", "count"}
        if unknown:
            lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown)}")
        role = condition.get("role")
        if not isinstance(role, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", role) is None:
            lint.fail(path, f"{ref}.role must be a canonical semantic-ref role")
        count = condition.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            lint.fail(path, f"{ref}.count must be a non-negative integer")
        return
    allowed_keys = {"kind", "field"} | ({"const"} if condition_kind == "field_equals" else set())
    unknown = set(condition) - allowed_keys
    if unknown:
        lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown)}")
    lint_field_path(lint, path, f"{ref}.field", condition.get("field"))
    if condition_kind == "field_equals":
        if "const" not in condition:
            lint.fail(path, f"{ref}.const is required for field_equals")
        elif not isinstance(condition["const"], (str, int, float, bool)):
            lint.fail(path, f"{ref}.const must be a scalar")



def lint_value_projection(lint: Lint, path: Path, ref: str, projection: object) -> None:
    """Validate a declared ordered_log append `op.value` projection.

    The projection is the pure function a receiver re-runs to rebuild `op.value`
    from the signed payload, so every member must name exactly one closed source:
    a literal, a field path, a `select` component, a registered derivation, or
    a digest over a field.
    """
    if not isinstance(projection, dict):
        lint.fail(path, f"{ref} must be an object")
        return
    unknown_projection_keys = set(projection) - {"kind", "members"}
    if unknown_projection_keys:
        lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown_projection_keys)}")
    if projection.get("kind") != "object":
        lint.fail(path, f"{ref}.kind must be 'object'")
    members = projection.get("members")
    if not isinstance(members, list) or not members:
        lint.fail(path, f"{ref}.members must be a non-empty array")
        return
    seen_names: set[str] = set()
    for index, member in enumerate(members):
        member_ref = f"{ref}.members[{index}]"
        if not isinstance(member, dict):
            lint.fail(path, f"{member_ref} must be an object")
            continue
        name = member.get("name")
        if not isinstance(name, str) or not name:
            lint.fail(path, f"{member_ref}.name must be a non-empty string")
        elif name in seen_names:
            lint.fail(path, f"{member_ref}.name duplicates another member")
        else:
            seen_names.add(name)
        sources = [
            key
            for key in (
                "literal",
                "field",
                "envelope_field",
                "select",
                "derivation",
                "digest_of",
                "normalized_string_set",
            )
            if key in member
        ]
        if len(sources) != 1:
            lint.fail(
                path,
                f"{member_ref} must declare exactly one of "
                "literal/field/envelope_field/select/derivation/digest_of/normalized_string_set",
            )
            continue
        source = sources[0]
        if source == "normalized_string_set":
            # Same normalization as the string_set_digest cell-subject
            # component: a bare string is the one-element set, an array is
            # deduplicated and sorted. Registering it here rather than hiding it
            # behind a plain `field` keeps the reshaping visible and closed.
            descriptor = member["normalized_string_set"]
            if not isinstance(descriptor, dict):
                lint.fail(path, f"{member_ref}.normalized_string_set must be an object")
                continue
            unknown = set(descriptor) - {"field", "context"}
            if unknown:
                lint.fail(
                    path,
                    f"{member_ref}.normalized_string_set has unknown member(s) {sorted(unknown)}",
                )
            lint_field_path(
                lint, path, f"{member_ref}.normalized_string_set.field", descriptor.get("field")
            )
            if descriptor.get("context") not in NORMALIZED_STRING_SET_CONTEXTS:
                lint.fail(
                    path,
                    f"{member_ref}.normalized_string_set.context must be one of "
                    f"{sorted(NORMALIZED_STRING_SET_CONTEXTS)}",
                )
            continue
        if source == "field":
            lint_field_path(lint, path, f"{member_ref}.field", member["field"])
        elif source == "envelope_field":
            if member["envelope_field"] not in {
                "actor_id",
                "created_at",
                "event_id",
                "realm_id",
            }:
                lint.fail(
                    path,
                    f"{member_ref}.envelope_field must be actor_id, created_at, event_id, or realm_id",
                )
        elif source == "select":
            lint_select_component(lint, path, f"{member_ref}.select", member["select"])
        elif source == "derivation":
            if member["derivation"] not in VALUE_PROJECTION_DERIVATIONS:
                lint.fail(
                    path,
                    f"{member_ref}.derivation must be one of "
                    f"{sorted(VALUE_PROJECTION_DERIVATIONS)}",
                )
        elif source == "digest_of":
            digest = member["digest_of"]
            if not isinstance(digest, dict):
                lint.fail(path, f"{member_ref}.digest_of must be an object")
            else:
                digest_input = digest.get("input")
                if digest_input == "event_payload_canonical_bytes":
                    if "field" in digest:
                        lint.fail(
                            path,
                            f"{member_ref}.digest_of.field must be omitted when digesting "
                            "the whole event payload",
                        )
                elif "field" in digest:
                    lint_field_path(lint, path, f"{member_ref}.digest_of.field", digest["field"])
                else:
                    lint.fail(
                        path,
                        f"{member_ref}.digest_of must declare a field unless it digests the "
                        "whole event payload",
                    )
                if digest_input not in VALUE_PROJECTION_DIGEST_INPUTS:
                    lint.fail(
                        path,
                        f"{member_ref}.digest_of.input must be one of {sorted(VALUE_PROJECTION_DIGEST_INPUTS)}",
                    )
                unknown = set(digest) - {"field", "input"}
                if unknown:
                    lint.fail(path, f"{member_ref}.digest_of has unknown member(s) {sorted(unknown)}")
        identity_metadata_keys = {"terminal_category", "subject_class"}
        present_identity_metadata = identity_metadata_keys & set(member)
        if present_identity_metadata and present_identity_metadata != identity_metadata_keys:
            lint.fail(
                path,
                f"{member_ref}.terminal_category and .subject_class must be declared together",
            )
        elif present_identity_metadata:
            terminal_category = member["terminal_category"]
            subject_class = member["subject_class"]
            if (
                not isinstance(terminal_category, str)
                or terminal_category not in VALUE_PROJECTION_IDENTITY_SUBJECTS
            ):
                lint.fail(
                    path,
                    f"{member_ref}.terminal_category must be one of "
                    f"{sorted(VALUE_PROJECTION_IDENTITY_SUBJECTS)}",
                )
            else:
                allowed_subjects = VALUE_PROJECTION_IDENTITY_SUBJECTS[terminal_category]
                if not isinstance(subject_class, str) or subject_class not in allowed_subjects:
                    lint.fail(
                        path,
                        f"{member_ref}.subject_class must be one of {sorted(allowed_subjects)} "
                        f"for terminal_category={terminal_category!r}",
                    )
        unknown_keys = set(member) - {"name", "optional", source} - identity_metadata_keys
        if unknown_keys:
            lint.fail(path, f"{member_ref} has unknown member(s) {sorted(unknown_keys)}")
        if "optional" in member and not isinstance(member["optional"], bool):
            lint.fail(path, f"{member_ref}.optional must be a boolean")



def lint_effect_source(
    lint: Lint, path: Path, ref: str, source: object, *, allow_dot: bool = False
) -> None:
    """Validate one closed source used to derive a state operation member.

    `dot` resolves to the write's canonical OR-Set dot
    (`ak:event:<event_id>:<write_index>`, event-and-patch.md section 2.4.2) and is
    only legal in an or_set tag position, so callers must opt in.
    """
    if not isinstance(source, dict):
        lint.fail(path, f"{ref} must be an object")
        return
    if "agent_authorization_dot" in source:
        expected = {"agent_authorization_dot": {"field": "item.authorized_event_ref"}}
        if source != expected or "ak.agent.key.authorize cell_writes[0]" not in ref or not ref.endswith(".dots"):
            lint.fail(path, f"{ref} permits agent_authorization_dot only in the exact Agent supersedes remove")
        return
    allowed = ("field", "envelope_field", "const", "projected_value", "object_without_fields")
    if allow_dot:
        allowed += ("dot",)
    source_keys = [key for key in allowed if key in source]
    if len(source_keys) != 1 or len(source) != 1:
        lint.fail(
            path,
            f"{ref} must declare exactly one of {'/'.join(allowed)}",
        )
        return
    source_key = source_keys[0]
    if source_key == "field":
        lint_field_path(lint, path, f"{ref}.field", source["field"])
    elif source_key == "object_without_fields":
        value = source[source_key]
        if not isinstance(value, dict) or set(value) != {"field", "exclude"}:
            lint.fail(path, f"{ref}.object_without_fields requires field and exclude")
            return
        lint_field_path(lint, path, f"{ref}.field", value["field"])
        excluded = value["exclude"]
        if not isinstance(excluded, list) or not excluded or any(not isinstance(v, str) or not v or "." in v for v in excluded) or len(excluded) != len(set(excluded)):
            lint.fail(path, f"{ref}.exclude must be a non-empty unique top-level field list")
    elif source_key == "envelope_field":
        value = source["envelope_field"]
        if value not in EFFECT_PROJECTION_ENVELOPE_FIELDS:
            lint.fail(
                path,
                f"{ref}.envelope_field must be one of "
                f"{sorted(EFFECT_PROJECTION_ENVELOPE_FIELDS)}",
            )
    elif source_key == "projected_value" and source["projected_value"] is not True:
        lint.fail(path, f"{ref}.projected_value must be true")
    elif source_key == "dot" and source["dot"] is not True:
        lint.fail(path, f"{ref}.dot must be true")



def complementary_conditions(left: object, right: object) -> bool:
    """True when two cell writes can never both participate in one Event.

    The provable forms in the closed condition grammar are field_present /
    field_absent over the identical path and field_equals over the identical
    path with unequal canonical constants. Treating any other pair as
    exclusive would be a guess, and a wrong guess means two writes racing on
    one cell.
    """
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    if not isinstance(left.get("field"), str) or left.get("field") != right.get("field"):
        return False
    kinds = {left.get("kind"), right.get("kind")}
    if kinds == {"field_present", "field_absent"}:
        return True
    return (
        left.get("kind") == "field_equals"
        and right.get("kind") == "field_equals"
        and "const" in left
        and "const" in right
        and left["const"] != right["const"]
    )



def lint_effect_projection(
    lint: Lint,
    path: Path,
    ref: str,
    projection: object,
    state_model: object,
) -> None:
    """Validate the closed payload-to-state-operation projection grammar."""
    if not isinstance(projection, dict):
        lint.fail(path, f"{ref} must be an object")
        return
    projection_kind = projection.get("kind")
    expected_kinds = {
        "causal_register": {"set", "apply_patch", "transition", "transition_to"},
        "sequenced_state": {"set", "apply_patch", "transition", "transition_to", "append", "or_set_delta", "or_set_add", "or_set_batch_add", "or_set_remove_observed", "or_set_remove_dots"},
        "ordered_log": {"append"},
        "or_set": {
            "or_set_delta",
            "or_set_add",
            "or_set_batch_add",
            "or_set_remove_observed",
            "or_set_remove_dots",
        },
    }.get(state_model)
    if expected_kinds is None:
        lint.fail(path, f"{ref} is not defined for state model {state_model!r}")
        return
    if projection_kind not in expected_kinds:
        lint.fail(
            path,
            f"{ref}.kind must be one of {sorted(expected_kinds)!r} for state model {state_model!r}",
        )
        return
    if projection_kind == "transition_to":
        unknown = set(projection) - {"kind", "to"}
        if unknown:
            lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown)}")
        if "to" not in projection:
            lint.fail(path, f"{ref}.to is required")
        else:
            lint_effect_source(lint, path, f"{ref}.to", projection["to"])
        return
    if projection_kind == "transition":
        unknown = set(projection) - {"kind", "from", "to"}
        if unknown:
            lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown)}")
        for member in ("from", "to"):
            if member not in projection:
                lint.fail(path, f"{ref}.{member} is required")
            else:
                lint_effect_source(lint, path, f"{ref}.{member}", projection[member])
        return
    if projection_kind == "set":
        unknown = set(projection) - {"kind", "value"}
        if unknown:
            lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown)}")
        if "value" not in projection:
            lint.fail(path, f"{ref}.value is required")
        else:
            lint_effect_source(lint, path, f"{ref}.value", projection["value"])
        return
    if projection_kind == "apply_patch":
        unknown = set(projection) - {
            "kind", "patch", "increment_members", "expected_prestate"
        }
        if unknown:
            lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown)}")
        increment_members = projection.get("increment_members")
        if "patch" not in projection and increment_members is None:
            lint.fail(path, f"{ref} requires patch and/or increment_members")
        elif "patch" in projection:
            lint_effect_source(lint, path, f"{ref}.patch", projection["patch"])
        # Patches bind a specific causal head; sequential commands use their confirmed predecessor.
        if state_model == "causal_register" and "expected_prestate" not in projection:
            lint.fail(
                path,
                f"{ref} on a causal_register requires expected_prestate; without it the exact "
                f"current source/value this patch applies to is undefined",
            )
        if increment_members is not None:
            if state_model != "sequenced_state":
                lint.fail(path, f"{ref}.increment_members requires sequenced_state")
            if "expected_prestate" not in projection:
                lint.fail(path, f"{ref}.increment_members requires expected_prestate")
            if (
                not isinstance(increment_members, list)
                or not increment_members
                or not all(
                    isinstance(member, str)
                    and "." not in member
                    and FIELD_PATH_RE.fullmatch(member)
                    for member in increment_members
                )
            ):
                lint.fail(
                    path,
                    f"{ref}.increment_members must be a non-empty array of member names",
                )
            elif increment_members != sorted(set(increment_members), key=lambda value: value.encode("utf-8")):
                lint.fail(
                    path,
                    f"{ref}.increment_members must be unique and sorted by UTF-8 bytes",
                )
        # The optional prestate guard has to name a payload path, because it is
        # a producer-signed claim about the frozen pre-state. envelope_field,
        # const, dot and projected_value would either be unsigned by the
        # producer or unable to vary per write, which defeats the guard.
        expected = projection.get("expected_prestate")
        if expected is not None:
            lint_effect_source(lint, path, f"{ref}.expected_prestate", expected)
            if not (isinstance(expected, dict)
                    and isinstance(expected.get("field"), str)
                    and expected["field"].startswith("payload.")):
                lint.fail(
                    path,
                    f"{ref}.expected_prestate MUST be a payload.* field source",
                )
        return
    if projection_kind == "append":
        unknown = set(projection) - {"kind", "value", "issuer_seq"}
        if unknown:
            lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown)}")
        for member in ("value", "issuer_seq"):
            if member not in projection:
                lint.fail(path, f"{ref}.{member} is required")
            else:
                lint_effect_source(lint, path, f"{ref}.{member}", projection[member])
        if projection.get("issuer_seq") != {"envelope_field": "actor_seq"}:
            lint.fail(
                path,
                f"{ref}.issuer_seq must be exactly "
                '{"envelope_field":"actor_seq"}; ordered_log uses the sparse '
                "Realm actor-chain coordinate and has no cell-local counter",
            )
        return

    if projection_kind == "or_set_add":
        unknown = set(projection) - {"kind", "tag", "value"}
        if unknown:
            lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown)}")
        for member in ("tag", "value"):
            if member not in projection:
                lint.fail(path, f"{ref}.{member} is required")
            else:
                lint_effect_source(
                    lint,
                    path,
                    f"{ref}.{member}",
                    projection[member],
                    allow_dot=member == "tag",
                )
        if isinstance(projection.get("tag"), dict) and projection["tag"].get(
            "envelope_field"
        ) == "event_id":
            lint.fail(
                path,
                f"{ref}.tag must use {{\"dot\": true}}; a bare event_id is not unique "
                "across multiple or_set writes on the same cell",
            )
        return
    if projection_kind == "or_set_batch_add":
        unknown = set(projection) - {"kind", "values", "tag_context"}
        if unknown:
            lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown)}")
        if "values" not in projection:
            lint.fail(path, f"{ref}.values is required")
        else:
            lint_effect_source(lint, path, f"{ref}.values", projection["values"])
        if not isinstance(projection.get("tag_context"), str) or not projection["tag_context"]:
            lint.fail(path, f"{ref}.tag_context must be a non-empty string")
        return

    if projection_kind == "or_set_remove_dots":
        # Partial revoke: the removal set is the payload-enumerated dot array,
        # byte-for-byte. It is the remove-side counterpart of or_set_batch_add
        # and MUST NOT be substituted for or_set_remove_observed, whose set
        # comes from the frozen pre-state instead.
        unknown = set(projection) - {"kind", "dots"}
        if unknown:
            lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown)}")
        if "dots" not in projection:
            lint.fail(path, f"{ref}.dots is required")
        else:
            lint_effect_source(lint, path, f"{ref}.dots", projection["dots"])
        return

    if projection_kind == "or_set_remove_observed":
        unknown = set(projection) - {"kind", "match"}
        if unknown:
            lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown)}")
        match = projection.get("match")
        if match is None:
            return
        if not isinstance(match, dict):
            lint.fail(path, f"{ref}.match must be an object")
            return
        unknown_match = set(match) - {"element_field", "source"}
        if unknown_match:
            lint.fail(path, f"{ref}.match has unknown member(s) {sorted(unknown_match)}")
        element_field = match.get("element_field")
        if not isinstance(element_field, str) or not FIELD_PATH_RE.fullmatch(element_field):
            lint.fail(
                path,
                f"{ref}.match.element_field must be a dotted named path on the element value",
            )
        if "source" not in match:
            lint.fail(path, f"{ref}.match.source is required")
        else:
            lint_effect_source(lint, path, f"{ref}.match.source", match["source"])
        return

    unknown = set(projection) - {"kind", "selector", "branches"}
    if unknown:
        lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown)}")
    lint_field_path(lint, path, f"{ref}.selector", projection.get("selector"))
    branches = projection.get("branches")
    if not isinstance(branches, dict) or not branches:
        lint.fail(path, f"{ref}.branches must be a non-empty object")
        return
    for branch_name, branch in branches.items():
        branch_ref = f"{ref}.branches[{branch_name}]"
        if not isinstance(branch_name, str) or not branch_name:
            lint.fail(path, f"{branch_ref} key must be a non-empty discriminator value")
        if not isinstance(branch, dict):
            lint.fail(path, f"{branch_ref} must be an object")
            continue
        op = branch.get("op")
        if op not in {"add", "remove"}:
            lint.fail(path, f"{branch_ref}.op must be add or remove")
            continue
        allowed = {"op", "tag", "value"} if op == "add" else {"op", "tag"}
        unknown_branch = set(branch) - allowed
        if unknown_branch:
            lint.fail(path, f"{branch_ref} has unknown member(s) {sorted(unknown_branch)}")
        if "tag" not in branch:
            lint.fail(path, f"{branch_ref}.tag is required")
        else:
            lint_effect_source(
                lint, path, f"{branch_ref}.tag", branch["tag"], allow_dot=True
            )
            if (
                isinstance(branch["tag"], dict)
                and branch["tag"].get("envelope_field") == "event_id"
            ):
                lint.fail(
                    path,
                    f"{branch_ref}.tag must use {{\"dot\": true}}; a bare event_id is "
                    "not unique across multiple or_set writes on the same cell",
                )
        if op == "add":
            if "value" not in branch:
                lint.fail(path, f"{branch_ref}.value is required for add")
            else:
                lint_effect_source(lint, path, f"{branch_ref}.value", branch["value"])



def _resolved_fsm_contract(
    lint: Lint,
    path: Path,
    family: str,
    contract: object,
    templates: dict[str, object],
) -> dict[str, object] | None:
    ref = f"event_kind_registry.transition_contracts[{family!r}]"
    if not isinstance(contract, dict):
        lint.fail(path, f"{ref} must be an object")
        return None
    template_name = contract.get("template")
    if template_name is None:
        return contract
    if not isinstance(template_name, str) or not isinstance(templates.get(template_name), dict):
        lint.fail(path, f"{ref}.template must name a registered FSM template")
        return None
    template = templates[template_name]
    assert isinstance(template, dict)
    parameter_schema = template.get("parameter_schema", {})
    required = [
        name
        for name, schema in parameter_schema.items()
        if isinstance(name, str) and isinstance(schema, dict) and schema.get("required") is True
    ] if isinstance(parameter_schema, dict) else []
    parameters = contract.get("instance_parameters")
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        lint.fail(path, f"fsm template {template_name!r} has invalid required_instance_parameters")
        return None
    if not isinstance(parameters, dict) or set(parameters) != set(required):
        lint.fail(
            path,
            f"{ref}.instance_parameters must provide exactly {sorted(required)}",
        )
        return None
    resolved: dict[str, object] = {
        key: value
        for key, value in template.items()
        if key not in {"required_instance_parameters", "conditional_transitions"}
    }
    transitions = list(resolved.get("allowed_transitions", []))
    conditional = template.get("conditional_transitions", [])
    if not isinstance(conditional, list):
        lint.fail(path, f"fsm template {template_name!r}.conditional_transitions must be an array")
        return None
    for index, item in enumerate(conditional):
        item_ref = f"fsm template {template_name!r}.conditional_transitions[{index}]"
        if not isinstance(item, dict):
            lint.fail(path, f"{item_ref} must be an object")
            continue
        when = item.get("when")
        transition = item.get("transition")
        if (
            not isinstance(when, dict)
            or not isinstance(when.get("parameter"), str)
            or "const" not in when
            or not isinstance(transition, list)
            or len(transition) != 2
        ):
            lint.fail(path, f"{item_ref} must declare when.parameter, when.const, and a pair transition")
            continue
        if parameters.get(when["parameter"]) == when["const"]:
            transitions.append(transition)
    resolved["allowed_transitions"] = transitions
    for key, value in contract.items():
        if key not in {"template", "instance_parameters"}:
            resolved[key] = value
    resolved["instance_parameters"] = parameters
    return resolved



def check_state_contract_closure(lint: Lint) -> None:
    """Close FSM and actor-private state semantics over the canonical contract."""

    path = ARTIFACTS / "registry" / "contract-registry.json"
    root = load_json(lint, path) or {}
    registry = root.get("event_kind_registry")
    if not isinstance(registry, dict):
        lint.fail(path, "event_kind_registry must be an object")
        return
    rows = registry.get("event_kinds")
    contracts = registry.get("cell_contracts")
    templates = registry.get("transition_templates")
    transition_contracts = registry.get("transition_contracts")
    private = registry.get("actor_private_contracts")
    if not isinstance(rows, list) or not isinstance(contracts, dict):
        lint.fail(path, "event_kind_registry must contain event_kinds and cell_contracts")
        return
    if not isinstance(templates, dict) or not isinstance(transition_contracts, dict):
        lint.fail(path, "event_kind_registry must contain transition_templates and transition_contracts")
        return
    if not isinstance(private, dict):
        lint.fail(path, "event_kind_registry.actor_private_contracts must be an object")
        return

    event_rows = {
        row.get("event_kind"): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("event_kind"), str)
    }
    resolved_contracts: dict[str, dict[str, object]] = {}
    for family, contract in transition_contracts.items():
        if not isinstance(family, str) or CELL_FAMILY_RE.fullmatch(family) is None:
            lint.fail(path, f"transition_contracts key must be a canonical cell family: {family!r}")
            continue
        resolved = _resolved_fsm_contract(lint, path, family, contract, templates)
        if resolved is None:
            continue
        states = resolved.get("states")
        transitions = resolved.get("allowed_transitions")
        initial_values = (
            [resolved.get("initial_state")]
            if "initial_state" in resolved
            else resolved.get("initial_states")
        )
        terminal = resolved.get("terminal_states", [])
        if (
            not isinstance(states, list)
            or not states
            or not all(isinstance(value, str) and value for value in states)
            or len(states) != len(set(states))
        ):
            lint.fail(path, f"transition_contracts[{family!r}].states must be a non-empty unique string array")
            continue
        state_set = set(states)
        transition_state_set = state_set | {None}
        if (
            not isinstance(initial_values, list)
            or not initial_values
            or not set(initial_values) <= transition_state_set
        ):
            lint.fail(path, f"transition_contracts[{family!r}] must declare valid initial_state(s)")
        if not isinstance(terminal, list) or not set(terminal) <= state_set:
            lint.fail(path, f"transition_contracts[{family!r}].terminal_states must be a states subset")
        if not isinstance(transitions, list):
            lint.fail(path, f"transition_contracts[{family!r}].allowed_transitions must be an array")
            continue
        seen_edges: set[tuple[object, object]] = set()
        for index, edge in enumerate(transitions):
            if (
                not isinstance(edge, list)
                or len(edge) != 2
                or not all(value is None or isinstance(value, str) for value in edge)
                or not set(edge) <= transition_state_set
            ):
                lint.fail(path, f"transition_contracts[{family!r}].allowed_transitions[{index}] is invalid")
                continue
            pair = (edge[0], edge[1])
            if pair in seen_edges:
                lint.fail(path, f"transition_contracts[{family!r}] repeats transition {pair}")
            seen_edges.add(pair)
        resolved_contracts[family] = resolved

    shared_fsm_families: set[str] = set()
    for kind, contract in contracts.items():
        if not isinstance(contract, dict):
            continue
        for write_index, write in enumerate(contract.get("cell_writes", [])):
            if isinstance(write, dict):
                _lint_cell_subject_kind(
                    lint, path, f"{kind} cell_writes[{write_index}]", write.get("cell_subject")
                )
            if not isinstance(write, dict) or "transition_contract" not in write:
                continue
            family = write.get("cell_family")
            if isinstance(family, str):
                shared_fsm_families.add(family)
                if family not in resolved_contracts:
                    lint.fail(path, f"{kind} writes FSM family {family} without one fsm_contract")
            projection = write.get("effect_projection")
            if (
                isinstance(projection, dict)
                and projection.get("kind") == "apply_patch"
                and isinstance(projection.get("max_cell_writes"), int)
                and projection["max_cell_writes"] > 128
            ):
                lint.fail(path, f"{kind} apply_patch max_cell_writes exceeds Event limit 128")
        requirements = contract.get("pre_state_requirements", [])
        if not isinstance(requirements, list):
            lint.fail(path, f"{kind}.pre_state_requirements must be an array")
        for index, requirement in enumerate(requirements):
            if not isinstance(requirement, dict):
                lint.fail(path, f"{kind}.pre_state_requirements[{index}] must be an object")
                continue
            unknown_members = set(requirement) - {
                "cell_family",
                "subject",
                "condition",
                "predicate",
                "failure",
            }
            if unknown_members:
                lint.fail(
                    path,
                    f"{kind}.pre_state_requirements[{index}] has unknown member(s) "
                    f"{sorted(unknown_members)}",
                )
            # event-and-patch.md 2.4.2: a requirement MAY be gated by the same
            # closed payload-condition grammar a conditional cell write uses, so
            # one kind can carry a per-branch pre-state rule without a second
            # predicate vocabulary. An ungated requirement is always evaluated.
            if "condition" in requirement:
                lint_cell_write_condition(
                    lint,
                    path,
                    f"{kind}.pre_state_requirements[{index}].condition",
                    requirement["condition"],
                )
            predicate = requirement.get("predicate")
            predicate_valid = isinstance(predicate, dict) and isinstance(
                predicate.get("field"), str
            )
            if predicate_valid and predicate.get("kind") == "stored_field_present":
                predicate_valid = set(predicate) == {"kind", "field"}
            elif predicate_valid and predicate.get("kind") in {
                "stored_field_equals_payload",
                "stored_field_matches_payload",
            }:
                predicate_valid = (
                    set(predicate) == {"kind", "field", "payload_field"}
                    and isinstance(predicate.get("payload_field"), str)
                    and predicate["payload_field"].startswith("payload.")
                )
            else:
                predicate_valid = False
            if (
                requirement.get("cell_family") not in resolved_contracts
                or not predicate_valid
                or not isinstance(requirement.get("failure"), dict)
                or not isinstance(requirement["failure"].get("code"), str)
                or not isinstance(requirement["failure"].get("reason_code"), str)
            ):
                lint.fail(path, f"{kind}.pre_state_requirements[{index}] is not a closed stored-field predicate")

    extra_contracts = set(resolved_contracts) - shared_fsm_families
    if extra_contracts:
        lint.fail(path, f"unreferenced transition_contracts: {sorted(extra_contracts)}")
    for kind, row in event_rows.items():
        parameters = row.get("parameters")
        if isinstance(parameters, dict) and ({"states", "allowed_transitions"} & set(parameters)):
            lint.fail(path, f"{kind} duplicates family FSM state semantics in event parameters")

    merge_definitions = private.get("merge_definitions")
    private_families = private.get("cell_families")
    private_writes = private.get("event_writes")
    if (
        not isinstance(merge_definitions, dict)
        or not isinstance(private_families, dict)
        or not isinstance(private_writes, dict)
    ):
        lint.fail(path, "actor_private_contracts must declare merge_definitions, cell_families, event_writes")
        return
    for family, family_contract in private_families.items():
        if (
            not isinstance(family, str)
            or not family.startswith("ak.private.")
            or not isinstance(family_contract, dict)
            or family_contract.get("merge") not in merge_definitions
        ):
            lint.fail(path, f"invalid actor-private cell family contract {family!r}")
    actor_private = {
        kind for kind, row in event_rows.items() if row.get("wire_scope") == "actor_private_event"
    }
    if set(private_writes) != actor_private:
        lint.fail(
            path,
            "actor_private_contracts.event_writes must cover active actor-private kinds exactly; "
            f"missing={sorted(actor_private - set(private_writes))}, "
            f"extra={sorted(set(private_writes) - actor_private)}",
        )
    for kind in actor_private:
        row = event_rows[kind]
        if kind in contracts or "plane" in row or "sealed" in row or row.get("reducer_input") is not False:
            lint.fail(path, f"{kind} must not reuse shared plane/seal/reducer cell semantics")
        write = private_writes.get(kind)
        if not isinstance(write, dict) or write.get("cell_family") not in private_families:
            lint.fail(path, f"{kind} must resolve to one registered actor-private cell family")



def _cell_subject_sources(subject: object) -> set[str]:
    """Every payload/envelope field path a cell subject is derived from."""
    sources: set[str] = set()
    if isinstance(subject, dict):
        field = subject.get("field")
        if isinstance(field, str):
            sources.add(field)
        for key in ("components", "options"):
            for part in subject.get(key) or []:
                sources |= _cell_subject_sources(part)
    return sources


def check_apply_patch_base_producers(lint: Lint, event_registry: dict, event_path: Path) -> None:
    """An apply_patch needs a base value, and only a registered write can supply it.

    zh/authz/event-auth-state-resolution.md section 9.3.1.2 closes the other door:
    a family may not declare an initial_value, so the base has to come from a
    registered create or genesis write. A family whose only writer is the patch
    itself therefore has no defined pre-state, and the first patch silently
    becomes the object's definition. The four families that are in that state
    today are frozen in tools/patch-base-producer-baseline.json; the list only
    shrinks.
    """
    def subject_shape(write: dict) -> str:
        subject = write.get("cell_subject")
        if subject is None:
            return "null"
        if isinstance(subject, dict):
            return str(subject.get("kind"))
        return str(subject)

    producers: dict[str, set[str]] = {}
    producer_shapes: dict[str, set[str]] = {}
    non_set_producers: dict[str, set[str]] = {}
    patchers: dict[str, set[str]] = {}
    patcher_shapes: dict[str, set[str]] = {}
    for row in event_registry.get("event_kinds") or []:
        if not isinstance(row, dict):
            continue
        kind = row.get("event_kind")
        for write in row.get("cell_writes") or []:
            if not isinstance(write, dict):
                continue
            family = write.get("cell_family")
            if not isinstance(family, str):
                continue
            projection_kind = (write.get("effect_projection") or {}).get("kind")
            if projection_kind == "apply_patch":
                patchers.setdefault(family, set()).add(kind)
                patcher_shapes.setdefault(family, set()).add(subject_shape(write))
            elif projection_kind == "set":
                producers.setdefault(family, set()).add(kind)
                producer_shapes.setdefault(family, set()).add(subject_shape(write))
            elif projection_kind in ("append", "transition"):
                non_set_producers.setdefault(family, set()).add(kind)
    unproduced = {family for family in patchers if not producers.get(family)}

    # decisions/0029 section 3.2: a producer has to be usable as this patch's
    # base, not merely present. An append or a transition writes no whole value,
    # and a producer that addresses a different subject shape names a different
    # object, so neither supplies a base the patch can apply to.
    for family in sorted(set(patchers) - unproduced):
        if not patcher_shapes[family] <= producer_shapes[family]:
            lint.fail(
                event_path,
                f"{family} is patched on subject shape(s) {sorted(patcher_shapes[family])} but its "
                f"set producer(s) address {sorted(producer_shapes[family])}; a base value has to be "
                "written to the same object the patch addresses",
            )
    for family in sorted(unproduced & set(non_set_producers)):
        lint.fail(
            event_path,
            f"{family} has only append/transition writer(s) {sorted(non_set_producers[family])}; "
            "neither writes a whole value, so neither can be the base an apply_patch resolves "
            "against",
        )

    baseline_path = TOOLS_ROOT / "patch-base-producer-baseline.json"
    baseline = load_json(lint, baseline_path) or {}
    known = {
        entry.get("cell_family")
        for entry in baseline.get("families_without_base_producer") or []
        if isinstance(entry, dict)
    }
    for family in sorted(unproduced - known):
        lint.fail(
            event_path,
            f"{family} is the target of apply_patch write(s) {sorted(patchers[family])} but no "
            "registered write produces a base value for it; a patch has no pre-state and section "
            "9.3.1.2 forbids closing the gap with a registered initial_value",
        )
    for family in sorted(known - unproduced):
        detail = (
            "now has a registered base-value producer"
            if family in patchers
            else "is no longer the target of any apply_patch write"
        )
        lint.fail(
            baseline_path,
            f"{family} {detail}; remove it from families_without_base_producer "
            "(the baseline only shrinks)",
        )


def check_concurrency_class_closure(lint: Lint, event_registry: dict, event_path: Path) -> None:
    """Every writer of a registered family must use one execution/model contract."""
    families = {}
    for row in event_registry.get("event_kinds", []):
        if "concurrency_class" in row:
            lint.fail(event_path, "retired concurrency_class must not override registered write execution")
        for write in row.get("cell_writes", []):
            family = write.get("cell_family")
            execution = write.get("execution")
            model = write.get("state_model")
            if (execution == "security") != (model == "sequenced_state"):
                lint.fail(event_path, f"{family} execution and state_model disagree")
            contract = (execution, model, write.get("value_shape"))
            if family in families and families[family] != contract:
                lint.fail(event_path, f"{family} has conflicting execution/model contracts")
            families[family] = contract


def check_registries(lint: Lint) -> dict[str, set[str]]:
    event_path = ARTIFACTS / "registry" / "event-kind-registry.json"
    schema_path = ARTIFACTS / "registry" / "schema-registry.json"
    track_path = ARTIFACTS / "registry" / "track-name-registry.json"
    id_path = ARTIFACTS / "registry" / "id-kind-registry.json"
    operation_path = ARTIFACTS / "registry" / "operation-registry.json"
    profile_path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    constraint_schema_path = ARTIFACTS / "schemas" / "grant-constraint.schema.json"

    event_registry = load_json(lint, event_path) or {}
    schema_registry = load_json(lint, schema_path) or {}
    track_registry = load_json(lint, track_path) or {}
    id_registry = load_json(lint, id_path) or {}
    operation_registry = load_json(lint, operation_path) or {}
    profile_registry = load_json(lint, profile_path) or {}
    constraint_schema = load_json(lint, constraint_schema_path) or {}

    check_concurrency_class_closure(lint, event_registry, event_path)
    check_apply_patch_base_producers(lint, event_registry, event_path)

    event_rows = event_registry.get("event_kinds", [])
    event_kinds = unique_values(lint, event_path, event_rows, "event_kind")
    event_by_kind = {
        row.get("event_kind"): row
        for row in event_rows
        if isinstance(row, dict) and isinstance(row.get("event_kind"), str)
    }
    kind_pattern = re.compile(event_registry.get("kind_pattern", r"^ak\.[a-z0-9_]+(\.[a-z0-9_]+)*$"))
    wire_scopes = set((event_registry.get("wire_scope_definitions") or {}).keys())
    for row in event_by_kind.values():
        kind = row["event_kind"]
        if not kind_pattern.fullmatch(kind):
            lint.fail(event_path, f"event_kind does not match kind_pattern: {kind}")
        wire_scope = row.get("wire_scope")
        if wire_scope not in wire_scopes:
            lint.fail(event_path, f"{kind} has unknown wire_scope {wire_scope!r}")
        removed_single_target_fields = {
            "cell_family", "cell_subject", "value_projection", "effect_projection",
            "state_model", "bottom", "initial_value",
        }
        present_removed_fields = sorted(removed_single_target_fields.intersection(row))
        if present_removed_fields:
            lint.fail(
                event_path,
                f"{kind} uses removed single-target fields {present_removed_fields}; cell_writes[] is the only reducer contract",
            )
        cell_writes = row.get("cell_writes")
        if cell_writes is not None:
            if not isinstance(cell_writes, list) or not cell_writes:
                lint.fail(event_path, f"{kind} cell_writes must be a non-empty array")
                cell_writes = []
            seen_writes: dict[str, tuple[str | None, object]] = {}
            for index, write in enumerate(cell_writes):
                write_ref = f"{kind} cell_writes[{index}]"
                if not isinstance(write, dict):
                    lint.fail(event_path, f"{write_ref} must be an object")
                    continue
                # Every effect has one registered static family and derived subject.
                has_cell_ref = "cell_ref" in write
                projection_kind = None
                if isinstance(write.get("effect_projection"), dict):
                    projection_kind = write["effect_projection"].get("kind")
                if kind == CONFLICT_RECOVERY_KIND or has_cell_ref or projection_kind == "reset":
                    lint_conflict_recovery_write(lint, event_path, write_ref, kind, write)
                    continue
                if "for_each" in write:
                    expected = {"field": "payload.supersedes", "max_items": 256}
                    if kind != "ak.agent.key.authorize" or index != 0 or write["for_each"] != expected:
                        lint.fail(event_path, f"{write_ref}.for_each is restricted to the Agent supersedes remove")
                    if write.get("cell_subject") != {"kind": "composite", "components": ["payload.agent_id", "item.key_id"]} or write.get("effect_projection") != {"kind": "or_set_remove_dots", "dots": {"agent_authorization_dot": {"field": "item.authorized_event_ref"}}}:
                        lint.fail(event_path, f"{write_ref} must remove only the exact observed authorization dot from its old key cell")
                elif kind == "ak.agent.key.authorize" and index == 0:
                    lint.fail(event_path, f"{write_ref} must enumerate the bounded exact supersedes set")
                write_family = write.get("cell_family")
                if not isinstance(write_family, str) or CELL_FAMILY_RE.fullmatch(write_family) is None:
                    lint.fail(
                        event_path,
                        f"{write_ref}.cell_family must use canonical ak.component.<facet-path>.v<n> form",
                    )
                if "cell_subject" not in write:
                    lint.fail(event_path, f"{write_ref} must declare cell_subject (null is allowed)")
                else:
                    subject = write.get("cell_subject")
                    if subject is not None and not isinstance(subject, (str, dict)):
                        lint.fail(event_path, f"{write_ref}.cell_subject must be null, string, or object")
                    elif isinstance(subject, dict):
                        subject_kind = subject.get("kind")
                        if not isinstance(subject_kind, str) or not subject_kind:
                            lint.fail(event_path, f"{write_ref}.cell_subject.kind must be a non-empty string")
                        elif not is_registered_cell_subject_kind(subject_kind):
                            # encoding.md 4.1 is a closed dispatch table; a kind outside it
                            # has no embedding rule, so the cell wire id is undefined.
                            # canonical_json in particular is a components[] descriptor
                            # only (ruling 2026-09-05-1200): a structured single-field
                            # subject is spelled as a single-component composite.
                            lint.fail(
                                event_path,
                                f"{write_ref}.cell_subject.kind {subject_kind!r} is not in the "
                                "encoding.md 4.1 closed subject table "
                                f"({', '.join(sorted(CELL_SUBJECT_KINDS))}, id:<object kind>); "
                                "canonical_json is a composite component descriptor, not a "
                                "top-level subject kind",
                            )
                        if subject_kind == "composite":
                            parts = subject.get("components")
                            if not isinstance(parts, list) or not parts:
                                lint.fail(
                                    event_path,
                                    f"{write_ref}.cell_subject.components must be a non-empty array",
                                )
                            else:
                                for part_index, part in enumerate(parts):
                                    part_ref = f"{write_ref}.cell_subject.components[{part_index}]"
                                    if isinstance(part, str):
                                        lint_subject_field_path(lint, event_path, part_ref, part)
                                    elif isinstance(part, dict):
                                        if part.get("kind") == "string_set_digest":
                                            lint_string_set_digest_component(
                                                lint,
                                                event_path,
                                                part_ref,
                                                part,
                                                event_kind=kind,
                                            )
                                        elif part.get("kind") == "canonical_json":
                                            lint_subject_field_path(
                                                lint,
                                                event_path,
                                                f"{part_ref}.field",
                                                part.get("field"),
                                            )
                                        else:
                                            lint_select_component(
                                                lint,
                                                event_path,
                                                part_ref,
                                                part,
                                                subject_source=True,
                                            )
                                    else:
                                        lint.fail(
                                            event_path,
                                            f"{part_ref} must be a field path string or a registered component object",
                                        )
                        elif subject_kind == "coalesce":
                            parts = subject.get("fields")
                            if not isinstance(parts, list) or not parts:
                                lint.fail(
                                    event_path,
                                    f"{write_ref}.cell_subject.fields must be a non-empty string array",
                                )
                            else:
                                for part_index, part in enumerate(parts):
                                    lint_subject_field_path(
                                        lint,
                                        event_path,
                                        f"{write_ref}.cell_subject.fields[{part_index}]",
                                        part,
                                    )
                        elif subject_kind == "tuple":
                            parts = subject.get("components")
                            if not isinstance(parts, list) or not parts:
                                lint.fail(event_path, f"{write_ref}.cell_subject.components must be non-empty")
                            else:
                                for part_index, part in enumerate(parts):
                                    part_ref = (
                                        f"{write_ref}.cell_subject.components[{part_index}].field"
                                    )
                                    if not isinstance(part, dict):
                                        lint.fail(
                                            event_path,
                                            f"{write_ref} tuple components must declare field",
                                        )
                                    else:
                                        lint_subject_field_path(
                                            lint, event_path, part_ref, part.get("field")
                                        )
                        else:
                            lint_subject_field_path(
                                lint,
                                event_path,
                                f"{write_ref}.cell_subject.field",
                                subject.get("field"),
                            )
                if "value_projection" in write:
                    lint_value_projection(
                        lint, event_path, f"{write_ref}.value_projection", write["value_projection"]
                    )
                if "derived_members" in write:
                    lint_derived_members(
                        lint, event_path, f"{write_ref}.derived_members", write["derived_members"]
                    )
                if "effect_projection" in write:
                    lint_effect_projection(
                        lint,
                        event_path,
                        f"{write_ref}.effect_projection",
                        write["effect_projection"],
                        write.get("state_model"),
                    )
                    projection = write.get("effect_projection")
                    if (
                        isinstance(projection, dict)
                        and projection.get("kind") == "append"
                        and isinstance(projection.get("value"), dict)
                        and projection["value"].get("projected_value") is True
                        and "value_projection" not in write
                    ):
                        lint.fail(
                            event_path,
                            f"{write_ref}.effect_projection uses projected_value "
                            "without value_projection",
                        )
                else:
                    lint.fail(
                        event_path,
                        f"{write_ref}.effect_projection is required; reducers must derive "
                        "every write from signed kind+payload",
                    )
                if "condition" in write:
                    lint_cell_write_condition(
                        lint, event_path, f"{write_ref}.condition", write["condition"]
                    )
                    # event-and-patch.md 2.4.2: when an `any_field_present`
                    # condition selects the same alternative paths a `coalesce`
                    # subject derives from, the two lists MUST agree item-for-item
                    # and in order. A mismatch means the target can be required on
                    # a payload shape whose subject cannot be derived, or derived
                    # on a shape where the target must not appear. The other
                    # legitimate use of `any_field_present` -- one cell carrying
                    # several distinct fields, addressed by an unconditional
                    # subject field -- is not constrained here.
                    condition = write["condition"]
                    subject = write.get("cell_subject")
                    if (
                        isinstance(condition, dict)
                        and condition.get("kind") == "any_field_present"
                        and isinstance(condition.get("fields"), list)
                        and isinstance(subject, dict)
                        and subject.get("kind") == "coalesce"
                        and subject.get("fields") != condition["fields"]
                    ):
                        lint.fail(
                            event_path,
                            f"{write_ref}.condition.fields must equal the cell_subject "
                            "coalesce fields item-for-item and in order",
                        )
                write_model = write.get("state_model")
                if write_model not in REGISTRY_STATE_MODELS:
                    lint.fail(event_path, f"{write_ref} has unknown state model {write_model!r}")
                if write.get("execution") not in {"data", "security"}:
                    lint.fail(event_path, f"{write_ref} must declare data or security execution")
                if (write.get("execution") == "security") != (write_model == "sequenced_state"):
                    lint.fail(event_path, f"{write_ref} execution and state_model disagree")
                if write.get("value_shape") not in {"register", "set", "log", "counter"}:
                    lint.fail(event_path, f"{write_ref} requires a registered value_shape")
                if "bottom" in write:
                    lint.fail(
                        event_path,
                        f"{write_ref} declares removed bottom policy; causal_register uses the fixed deterministic winner",
                    )
                write_key = json.dumps(
                    [write_family, write.get("cell_subject")],
                    sort_keys=True,
                    ensure_ascii=False,
                )
                # zh/models/event-and-patch.md section 2.4.2 allows one Event to
                # carry several ops of the same family when the kind's closed
                # contract registers them explicitly. The one shape that needs
                # it is an or_set atomic remove-then-add on a single cell
                # (zh/identity/key-management.md section 3.6.1 requires exactly
                # that for agent key re-authorization). Any other repeat of a
                # cell is still a duplicate target: the two ops would be
                # indistinguishable to a receiver.
                projection_kind = None
                if isinstance(write.get("effect_projection"), dict):
                    projection_kind = write["effect_projection"].get("kind")
                add_kinds = {"or_set_add", "or_set_batch_add"}
                remove_kinds = {"or_set_remove_observed", "or_set_remove_dots"}
                previous = seen_writes.get(write_key)
                if previous is not None:
                    previous_kind, previous_condition = previous
                    paired = (
                        write.get("value_shape") == "set"
                        and {previous_kind, projection_kind}
                        <= (add_kinds | remove_kinds)
                        and bool({previous_kind, projection_kind} & add_kinds)
                        and bool({previous_kind, projection_kind} & remove_kinds)
                    )
                    # The other legal repeat is a provably disjoint condition
                    # pair: complementary presence tests, or unequal exact
                    # constants on the same field. Anything weaker would let
                    # two writes race on one cell.
                    complementary = complementary_conditions(
                        previous_condition, write.get("condition")
                    )
                    if not paired and not complementary:
                        lint.fail(
                            event_path,
                            f"{write_ref} duplicates another cell target",
                        )
                seen_writes[write_key] = (projection_kind, write.get("condition"))
            plane = row.get("plane")
            sealed = row.get("sealed")
            if plane not in REGISTRY_PLANES:
                lint.fail(event_path, f"{kind} must declare a registered plane")
            if plane == "conditional":
                if "sealed" in row:
                    lint.fail(event_path, f"{kind} conditional execution cannot declare static sealed")
                if not any(w.get("execution") == "security" and w.get("condition") for w in cell_writes):
                    lint.fail(event_path, f"{kind} conditional execution requires a conditional security write")
            elif not isinstance(sealed, bool) or sealed != (plane == "control"):
                lint.fail(event_path, f"{kind} static sealed must agree with execution")
        if row.get("status") == "active" and row.get("reducer_input") is True:
            if cell_writes is None:
                lint.fail(
                    event_path,
                    f"{kind} active reducer-input kind must declare cell_writes",
                )
    schema_rows = schema_registry.get("schemas", [])
    schema_ids = unique_values(lint, schema_path, schema_rows, "schema_id")
    schema_refs_by_file: dict[str, set[str]] = {}
    declared_wire_binding_kinds = {
        "account_data_plaintext",
        "account_data_storage",
        "dynamic_schema_ref",
        "mls_encrypted_payload",
        "signal_plaintext_dispatch",
        "standalone_schema_alias",
    }
    for row in schema_rows if isinstance(schema_rows, list) else []:
        if not isinstance(row, dict):
            continue
        schema_id = row.get("schema_id")
        schema_status = row.get("status", "active")
        if schema_status != "active":
            lint.fail(schema_path, f"{schema_id!r} schema status must be active; historical compatibility rows are forbidden")
        file_ref = row.get("file")
        fragment = row.get("fragment")
        consumer_binding = row.get("consumer_binding")
        if isinstance(schema_id, str) and not SCHEMA_ID_RE.fullmatch(schema_id):
            lint.fail(schema_path, f"schema_id has invalid format: {schema_id}")
        if not isinstance(file_ref, str) or not file_ref:
            lint.fail(schema_path, f"{schema_id!r} has missing file")
            continue
        if Path(file_ref).is_absolute() or ".." in Path(file_ref).parts:
            lint.fail(schema_path, f"{schema_id} file must stay inside artifacts/: {file_ref}")
            continue
        target = ARTIFACTS / file_ref
        if not target.exists():
            lint.fail(schema_path, f"{schema_id} file does not exist: {file_ref}")
        elif target.suffix == ".json":
            document = load_json(lint, target)
            if fragment is not None:
                if not isinstance(fragment, str) or not fragment.startswith("#/"):
                    lint.fail(schema_path, f"{schema_id} fragment must start with '#/': {fragment!r}")
                elif document is not None:
                    try:
                        resolved = resolve_json_pointer(document, fragment)
                    except (KeyError, TypeError, ValueError):
                        lint.fail(schema_path, f"{schema_id} fragment does not resolve in {file_ref}: {fragment}")
                    else:
                        if not isinstance(resolved, (dict, bool)):
                            lint.fail(schema_path, f"{schema_id} fragment must resolve to an object or boolean schema")
        if isinstance(fragment, str) or fragment is None:
            effective_fragment = fragment or ""
            seen_fragments = schema_refs_by_file.setdefault(file_ref, set())
            if effective_fragment in seen_fragments:
                lint.fail(
                    schema_path,
                    f"{schema_id} duplicates effective schema reference {file_ref}{effective_fragment}",
                )
            seen_fragments.add(effective_fragment)
        if consumer_binding is not None:
            if not isinstance(consumer_binding, dict):
                lint.fail(schema_path, f"{schema_id} consumer_binding must be an object")
            else:
                binding_kind = consumer_binding.get("kind")
                if binding_kind == "prose_only":
                    if not isinstance(consumer_binding.get("rationale"), str) or not consumer_binding[
                        "rationale"
                    ]:
                        lint.fail(
                            schema_path,
                            f"{schema_id} prose_only consumer_binding must state a rationale",
                        )
                elif binding_kind in declared_wire_binding_kinds:
                    for field in ("selector", "normative_ref"):
                        if not isinstance(consumer_binding.get(field), str) or not consumer_binding[field]:
                            lint.fail(
                                schema_path,
                                f"{schema_id} {binding_kind} consumer_binding must declare {field}",
                            )
                else:
                    lint.fail(
                        schema_path,
                        f"{schema_id} has unknown consumer_binding kind {binding_kind!r}",
                    )

    # Reverse closure (ruling 2026-09-05-0245): every schema file under
    # artifacts/schemas is the `file` of at least one schema-registry row. The
    # forward check above only proves rows point at files; a renamed or newly
    # added file that no row names has a $id and a $ref audience but no
    # schema_id, so consumers that walk the registry never see it.
    registered_files = {
        row.get("file")
        for row in schema_rows
        if isinstance(row, dict) and isinstance(row.get("file"), str)
    }
    for schema_file in sorted((ARTIFACTS / "schemas").glob("*.schema.json")):
        file_ref = f"schemas/{schema_file.name}"
        if file_ref not in registered_files:
            lint.fail(
                schema_path,
                f"{file_ref} exists but no schema-registry row names it; "
                "register a schema_id for it or delete the file",
            )

    id_rows = id_registry.get("id_kinds", [])
    id_kinds = unique_values(lint, id_path, id_rows, "kind")
    producer_contract = id_registry.get("producer_allocated_identity_contract")
    expected_producer_contract = {
        "identity_key": ["mint_authority", "typed_id"],
        "mint_authority_source": "accepted_genesis_proof_signer_did",
        "bare_typed_id_resolution": "forbidden",
        "same_authority_exact_replay": "idempotent",
        "same_authority_conflicting_binding": "reject_and_quarantine",
        "cross_authority_same_uuid": "distinct_identity",
        "atomic_reservation_required": True,
        "signature_binding_required": True,
    }
    if not isinstance(producer_contract, dict):
        lint.fail(id_path, "producer_allocated_identity_contract must be an object")
    else:
        for field, expected in expected_producer_contract.items():
            if producer_contract.get(field) != expected:
                lint.fail(
                    id_path,
                    f"producer_allocated_identity_contract.{field} must equal {expected!r}",
                )
        if not isinstance(producer_contract.get("security_rationale"), str) or not producer_contract[
            "security_rationale"
        ]:
            lint.fail(id_path, "producer_allocated_identity_contract.security_rationale is required")
        expected_suite = {
            "vector_id": "ak.vector.object_identity.producer_allocated_collision.v1",
            "fixture": "producer-allocated-identity-collision-fixture.json",
            "parameter_source": "id_kind_registry.id_kinds[id_form=producer_allocated]",
        }
        if producer_contract.get("conformance_suite") != expected_suite:
            lint.fail(
                id_path,
                "producer_allocated_identity_contract.conformance_suite must use the registry-parameterized suite",
            )
    event_derived_id_kinds = {
        row.get("kind")
        for row in (id_rows if isinstance(id_rows, list) else [])
        if isinstance(row, dict) and row.get("id_form") == "event_derived"
    }
    id_by_kind = {
        row.get("kind"): row
        for row in (id_rows if isinstance(id_rows, list) else [])
        if isinstance(row, dict) and isinstance(row.get("kind"), str)
    }
    expected_wire_form_generation = {
        "producer_allocated": "ak:<kind>:<uuidv7>",
        "event_derived": "ak:<kind>:<44-char-event-token>",
        "suite_tagged_full_digest": "ak:<kind>:<44-char-suite-tagged-full-digest-token>",
    }
    if id_registry.get("wire_form_generation") != expected_wire_form_generation:
        lint.fail(
            id_path,
            "id_kind_registry.wire_form_generation must declare the canonical v1 forms",
        )
    for row in id_rows if isinstance(id_rows, list) else []:
        if not isinstance(row, dict):
            continue
        kind = row.get("kind")
        wire_form = row.get("wire_form")
        if isinstance(kind, str) and not re.fullmatch(r"[a-z0-9_]+", kind):
            lint.fail(id_path, f"id kind has invalid format: {kind}")
        if isinstance(kind, str) and isinstance(wire_form, str) and not wire_form.startswith(f"ak:{kind}:"):
            lint.fail(id_path, f"{kind} wire_form must start with ak:{kind}:")
        id_form = row.get("id_form")
        template = expected_wire_form_generation.get(id_form)
        if isinstance(kind, str) and isinstance(template, str):
            expected_wire_form = template.replace("<kind>", kind)
            if wire_form != expected_wire_form:
                lint.fail(
                    id_path,
                    f"{kind} wire_form must be generated from id_form={id_form}: {expected_wire_form}",
                )

    # Bidirectional registry/schema guard: every token-derived kind must have
    # an exact 44-character schema carrier somewhere, and no schema may retain
    # an exact UUID carrier for that same typed kind. This closes the gap where
    # registry generation was correct but an independently hand-written schema
    # still accepted the retired physical form.
    schema_patterns: set[str] = set()

    def collect_schema_patterns(value: object) -> None:
        if isinstance(value, dict):
            pattern = value.get("pattern")
            if isinstance(pattern, str):
                schema_patterns.add(pattern)
            for child in value.values():
                collect_schema_patterns(child)
        elif isinstance(value, list):
            for child in value:
                collect_schema_patterns(child)

    for schema_file in sorted((ARTIFACTS / "schemas").glob("*.json")):
        schema_document = load_json(lint, schema_file)
        if schema_document is not None:
            collect_schema_patterns(schema_document)
    for kind, row in id_by_kind.items():
        if row.get("id_form") not in {
            "event_derived",
            "suite_tagged_full_digest",
        }:
            continue
        escaped_kind = re.escape(kind)
        token_pattern = rf"^ak:{escaped_kind}:[A-Za-z0-9_-]{{44}}$"
        uuid_pattern = (
            rf"^ak:{escaped_kind}:[0-9a-f]{{8}}-[0-9a-f]{{4}}-7[0-9a-f]{{3}}-"
            rf"[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}$"
        )
        if token_pattern not in schema_patterns:
            lint.fail(id_path, f"{kind} has no exact 44-character schema carrier")
        if uuid_pattern in schema_patterns:
            lint.fail(id_path, f"{kind} schema still carries the retired UUIDv7 form")

    # zh/models/common-fields.md section 6.0: an event-derived Event may
    # retype its event_id into more than one *different* typed ID kind.  The
    # full `ak:<kind>:<44-char-event-token>` is the identity key, so this is collision-free;
    # however the target set must be closed and one-per-kind.  Single-output
    # rows retain `id_kind`; multi-output rows use `id_kinds[]`.
    for event_kind, row in event_by_kind.items():
        single_target = row.get("id_kind")
        multiple_targets = row.get("id_kinds")
        if row.get("id_source") != "event_derived":
            # Conditional event/subject-derived rows (currently Realm) retain
            # a single shared id_kind and validate their branch table
            # separately.  Multi-output is defined only for event_derived.
            if multiple_targets is not None:
                lint.fail(event_path, f"{event_kind} id_kinds requires id_source=event_derived")
            continue
        if (single_target is None) == (multiple_targets is None):
            lint.fail(
                event_path,
                f"{event_kind} event_derived row must declare exactly one of id_kind or id_kinds",
            )
            continue
        if single_target is not None:
            targets = [single_target]
            if not isinstance(single_target, str) or not single_target:
                lint.fail(event_path, f"{event_kind} id_kind must be a non-empty string")
                continue
        else:
            if (
                not isinstance(multiple_targets, list)
                or not multiple_targets
                or not all(isinstance(target, str) and target for target in multiple_targets)
            ):
                lint.fail(event_path, f"{event_kind} id_kinds must be a non-empty string array")
                continue
            targets = multiple_targets
            if len(set(targets)) != len(targets):
                lint.fail(event_path, f"{event_kind} id_kinds must not repeat a typed ID kind")
        for target in targets:
            if target not in id_kinds:
                lint.fail(event_path, f"{event_kind} derives unregistered id kind {target!r}")
            elif target not in event_derived_id_kinds:
                lint.fail(
                    event_path,
                    f"{event_kind} derives {target!r}, whose id-kind row is not event_derived",
                )
            elif event_kind not in (id_by_kind[target].get("genesis_event_kinds") or []):
                lint.fail(
                    event_path,
                    f"{event_kind} -> {target!r} is missing from that id kind's genesis_event_kinds",
                )

    # The ID registry is the object-side join table.  Every Event-derived
    # object names all of its genesis Event kinds, and every such Event must
    # point back through id_kind/id_kinds.  This makes the mapping queryable in
    # either direction without prose search or two drifting hand-maintained
    # tables.  `event` is the sole self-content-derived kind rather than an
    # object created by a particular Event kind.
    for id_kind, row in id_by_kind.items():
        id_form = row.get("id_form")
        authority = row.get("identity_authority")
        genesis_kinds = row.get("genesis_event_kinds")
        if id_form == "event_derived" and id_kind == "event":
            if authority != "canonical_event_content" or genesis_kinds is not None:
                lint.fail(id_path, "event must use canonical_event_content and omit genesis_event_kinds")
            continue
        if id_form == "event_derived":
            if authority != "event":
                lint.fail(id_path, f"{id_kind} event_derived row must declare identity_authority=event")
            if (
                not isinstance(genesis_kinds, list)
                or not genesis_kinds
                or not all(isinstance(value, str) and value for value in genesis_kinds)
                or len(set(genesis_kinds)) != len(genesis_kinds)
            ):
                lint.fail(id_path, f"{id_kind} must declare unique non-empty genesis_event_kinds")
                continue
            for genesis_kind in genesis_kinds:
                genesis_row = event_by_kind.get(genesis_kind)
                if genesis_row is None:
                    lint.fail(id_path, f"{id_kind} names unknown genesis Event {genesis_kind}")
                    continue
                declared_targets = []
                if isinstance(genesis_row.get("id_kind"), str):
                    declared_targets.append(genesis_row["id_kind"])
                if isinstance(genesis_row.get("id_kinds"), list):
                    declared_targets.extend(genesis_row["id_kinds"])
                if genesis_row.get("id_source") != "event_derived" or id_kind not in declared_targets:
                    lint.fail(
                        id_path,
                        f"{id_kind} genesis Event {genesis_kind} does not point back to this id kind",
                    )
        elif id_form == "suite_tagged_full_digest":
            expected_authority = (
                "source_evidence" if id_kind == "notification_projection" else "issuer_record"
            )
            if authority != expected_authority:
                lint.fail(
                    id_path,
                    f"{id_kind} suite-tagged row must declare identity_authority={expected_authority}",
                )
            if genesis_kinds is not None:
                lint.fail(
                    id_path,
                    f"{id_kind} issuer-record row must omit genesis_event_kinds",
                )
            contract_ref = row.get("derivation_contract_ref")
            prefix = "#/id_kind_registry/"
            contract_name = (
                contract_ref[len(prefix) :]
                if isinstance(contract_ref, str) and contract_ref.startswith(prefix)
                else None
            )
            contract = id_registry.get(contract_name) if contract_name else None
            if not isinstance(contract, dict):
                lint.fail(
                    id_path,
                    f"{id_kind} has no registered suite_tagged_full_digest authority contract",
                )
                continue
            applies_to = contract.get("applies_to_id_kinds")
            if not isinstance(applies_to, list) or id_kind not in applies_to:
                lint.fail(
                    id_path,
                    f"{id_kind} derivation contract does not declare this id kind",
                )
            expected_storage_key = contract.get("storage_identity_key", contract.get("identity_key"))
            if row.get("storage_identity_key") != expected_storage_key:
                lint.fail(
                    id_path,
                    f"{id_kind} storage identity key does not match its derivation contract",
                )
            if id_kind == "notification_projection":
                if (contract.get("domain_separator") != "ak.notification-projection.v1\n"
                    or contract.get("digest_suite_wire_code") != 1
                    or contract.get("canonicalization") != "json_jcs"):
                    lint.fail(id_path, "notification projection derivation parameters are invalid")
                answer = contract.get("known_answer", {})
                preimage = answer.get("preimage", {})
                # The frozen vector contains ASCII string leaves only, so
                # sorted compact JSON is byte-identical to RFC 8785 JCS.
                if set(preimage) != {"recipient_account_id", "realm_id", "source_event_id", "notification_kind"}:
                    lint.fail(id_path, "notification projection KAT has an invalid preimage")
                else:
                    encoded = json.dumps(preimage, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                    digest = hashlib.sha256(b"ak.notification-projection.v1\n" + encoded).digest()
                    expected = "ak:notification_projection:" + base64.urlsafe_b64encode(b"\x01" + digest).decode("ascii")
                    if answer.get("notification_id") != expected:
                        lint.fail(id_path, "notification projection KAT digest does not match")
        elif id_form == "producer_allocated":
            if authority != "producer_signature":
                lint.fail(
                    id_path,
                    f"{id_kind} producer_allocated row must declare identity_authority=producer_signature",
                )
            if genesis_kinds is not None:
                lint.fail(id_path, f"{id_kind} producer_allocated row must omit genesis_event_kinds")
        elif authority is not None or genesis_kinds is not None:
            lint.fail(
                id_path,
                f"{id_kind} non-derived row must not declare derived identity authority/genesis fields",
            )

    special_id_kinds = unique_values(lint, id_path, id_registry.get("special_forms", []), "kind")

    operation_rows = operation_registry.get("operations", [])
    operation_ids = unique_values(lint, operation_path, operation_rows, "operation_id")
    high_security_policy = operation_registry.get("high_security_session_authentication_policy")
    if not isinstance(high_security_policy, dict):
        lint.fail(operation_path, "operation_registry.high_security_session_authentication_policy must be an object")
    else:
        if high_security_policy.get("applies_to_operation_id_prefix") != "ak.self.":
            lint.fail(operation_path, "high-security session policy must classify the ak.self. surface")
        if high_security_policy.get("protected_operation_default") != "rfc9421_session_public_key_required":
            lint.fail(operation_path, "high-security session policy must fail closed to RFC 9421 PoP")
        public_operations = high_security_policy.get("unauthenticated_public_projection_operations")
        if not isinstance(public_operations, list) or not public_operations:
            lint.fail(operation_path, "high-security session policy must declare its public projection exceptions")
        else:
            for public_operation in public_operations:
                if public_operation not in operation_ids:
                    lint.fail(operation_path, f"high-security public projection operation is not registered: {public_operation!r}")
                elif not isinstance(public_operation, str) or not public_operation.startswith("ak.self.") or ".read." not in public_operation:
                    lint.fail(operation_path, f"invalid high-security public projection operation: {public_operation!r}")
    operation_http_map: dict[str, str] = {}
    operation_grpc_map: dict[str, str] = {}
    operation_mq_map: dict[str, str] = {}
    for operation_id in operation_ids:
        if not OPERATION_ID_RE.fullmatch(operation_id):
            lint.fail(operation_path, f"operation_id has invalid format: {operation_id}")
            continue
        segments = operation_id.split(".")
        if len(segments) < 5 or segments[-1] != "v1":
            lint.fail(
                operation_path,
                f"operation_id must be ak.<surface>.<domain...>.<kind>.<action>.v1: {operation_id}",
            )
            continue
        if segments[-3] not in OPERATION_KINDS:
            lint.fail(
                operation_path,
                f"operation_id kind segment {segments[-3]!r} is not one of {sorted(OPERATION_KINDS)}: {operation_id}",
            )
        if segments[-2] in FORBIDDEN_OPERATION_ACTIONS:
            lint.fail(
                operation_path,
                f"operation_id action segment {segments[-2]!r} is an HTTP method name, not a protocol effect: {operation_id}",
            )
    for row in operation_rows if isinstance(operation_rows, list) else []:
        if not isinstance(row, dict):
            continue
        operation_id = row.get("operation_id")
        if not isinstance(operation_id, str) or operation_id not in operation_ids:
            continue
        http = row.get("http")
        grpc = row.get("grpc")
        mq = row.get("mq")
        http_only_variant = row.get("http_only_variant") is True
        if not isinstance(http, str) or not http:
            lint.fail(operation_path, f"{operation_id} missing http binding")
        else:
            operation_http_map[operation_id] = http
        if "http_compatibility_bindings" in row:
            lint.fail(operation_path, f"{operation_id} must not declare removed http_compatibility_bindings")
        if http_only_variant:
            if grpc is not None:
                lint.fail(operation_path, f"{operation_id} is http_only_variant and must not declare grpc binding")
            if mq is not None:
                lint.fail(operation_path, f"{operation_id} is http_only_variant and must not declare mq binding")
        else:
            if not isinstance(grpc, str) or not grpc:
                lint.fail(operation_path, f"{operation_id} missing grpc binding")
            else:
                operation_grpc_map[operation_id] = grpc
            if not isinstance(mq, str) or not mq:
                lint.fail(operation_path, f"{operation_id} missing mq binding")
            else:
                operation_mq_map[operation_id] = mq
        # Idempotency contract fields: every write operation (command / upload /
        # exchange kinds, plus resource.replace / resource.delete) MUST declare
        # idempotency_mechanism + retry_safe; read-only operations MUST NOT.
        segments = operation_id.split(".")
        op_kind = segments[-3] if len(segments) >= 3 else ""
        op_action = segments[-2] if len(segments) >= 2 else ""
        is_write_operation = op_kind in {"command", "upload", "exchange"} or (
            op_kind == "resource" and op_action in {"replace", "delete"}
        )
        idempotency_mechanism = row.get("idempotency_mechanism")
        retry_safe = row.get("retry_safe")
        allowed_mechanisms = {
            "idempotency_key",
            "object_id",
            "request_id",
            "canonical_hash",
            "protocol_sequence",
            "none",
        }
        if is_write_operation:
            if idempotency_mechanism not in allowed_mechanisms:
                lint.fail(
                    operation_path,
                    f"{operation_id} is a write operation and must declare idempotency_mechanism "
                    f"as one of {sorted(allowed_mechanisms)} (got {idempotency_mechanism!r})",
                )
            if not isinstance(retry_safe, bool):
                lint.fail(
                    operation_path,
                    f"{operation_id} is a write operation and must declare retry_safe as a boolean",
                )
            canonical_hash_input = row.get("canonical_hash_input")
            if idempotency_mechanism == "canonical_hash":
                if not isinstance(canonical_hash_input, str) or not canonical_hash_input:
                    lint.fail(
                        operation_path,
                        f"{operation_id} uses canonical_hash and must declare canonical_hash_input",
                    )
                elif canonical_hash_input != "full_body" and not canonical_hash_input.startswith("/"):
                    lint.fail(
                        operation_path,
                        f"{operation_id} canonical_hash_input must be full_body or an RFC 6901 JSON Pointer",
                    )
            elif canonical_hash_input is not None:
                lint.fail(
                    operation_path,
                    f"{operation_id} may declare canonical_hash_input only with idempotency_mechanism=canonical_hash",
                )
            uncertain_outcome = row.get("uncertain_outcome")
            if retry_safe is False:
                if not isinstance(uncertain_outcome, dict):
                    lint.fail(
                        operation_path,
                        f"{operation_id} has retry_safe=false and must declare uncertain_outcome",
                    )
                else:
                    strategy = uncertain_outcome.get("strategy")
                    allowed_strategies = {
                        "query_operation",
                        "reissue_material",
                        "revoke_then_reissue",
                        "manual_confirmation",
                        "drop_unconfirmed",
                    }
                    if strategy not in allowed_strategies:
                        lint.fail(
                            operation_path,
                            f"{operation_id} uncertain_outcome.strategy must be one of {sorted(allowed_strategies)}",
                        )
                    recovery_operation = uncertain_outcome.get("operation_id")
                    if strategy in {"query_operation", "reissue_material"}:
                        if recovery_operation not in operation_ids:
                            lint.fail(
                                operation_path,
                                f"{operation_id} uncertain_outcome references unknown operation {recovery_operation!r}",
                            )
                    elif "operation_id" in uncertain_outcome:
                        lint.fail(
                            operation_path,
                            f"{operation_id} uncertain_outcome strategy {strategy!r} must not declare operation_id",
                        )
                    if strategy == "revoke_then_reissue":
                        revoke_operation = uncertain_outcome.get("revoke_operation_id")
                        reissue_operation = uncertain_outcome.get("reissue_operation_id")
                        if revoke_operation not in operation_ids or reissue_operation not in operation_ids:
                            lint.fail(
                                operation_path,
                                f"{operation_id} revoke_then_reissue must reference known revoke and reissue operations",
                            )
                        if revoke_operation == reissue_operation:
                            lint.fail(
                                operation_path,
                                f"{operation_id} revoke_then_reissue must use distinct revoke and reissue operations",
                            )
                    elif "revoke_operation_id" in uncertain_outcome or "reissue_operation_id" in uncertain_outcome:
                        lint.fail(
                            operation_path,
                            f"{operation_id} uncertain_outcome strategy {strategy!r} must not declare revoke/reissue operation ids",
                        )
                    if strategy in {"reissue_material", "revoke_then_reissue"} and uncertain_outcome.get("requires_fresh_request_identity") is not True:
                        lint.fail(
                            operation_path,
                            f"{operation_id} {strategy} must require a fresh request identity",
                        )
            elif uncertain_outcome is not None:
                if not (
                    isinstance(uncertain_outcome, dict)
                    and uncertain_outcome.get("strategy") == "replay_same_operation"
                    and uncertain_outcome.get("operation_id") == operation_id
                    and uncertain_outcome.get("requires_same_request_identity_and_canonical_intent") is True
                ):
                    lint.fail(
                        operation_path,
                        f"{operation_id} retry-safe uncertain_outcome must use replay_same_operation with the same stable request identity and canonical intent",
                    )
        else:
            if "idempotency_mechanism" in row or "retry_safe" in row:
                lint.fail(
                    operation_path,
                    f"{operation_id} is read-only and must not declare idempotency_mechanism / retry_safe",
                )

    surface_classes = operation_registry.get("surface_classes")
    surface_groups = operation_registry.get("surface_groups")
    assigned_operations: dict[str, str] = {}
    if not isinstance(surface_classes, dict) or not surface_classes:
        lint.fail(operation_path, "operation registry missing surface_classes")
    if not isinstance(surface_groups, list) or not surface_groups:
        lint.fail(operation_path, "operation registry missing surface_groups")
    else:
        for index, row in enumerate(surface_groups):
            if not isinstance(row, dict):
                lint.fail(operation_path, f"surface_groups[{index}] must be an object")
                continue
            surface = row.get("surface")
            surface_class = row.get("surface_class")
            surface_operations = row.get("operations")
            if not isinstance(surface, str) or not surface:
                lint.fail(operation_path, f"surface_groups[{index}].surface must be a non-empty string")
                continue
            if not isinstance(surface_class, str) or (
                isinstance(surface_classes, dict) and surface_class not in surface_classes
            ):
                lint.fail(
                    operation_path,
                    f"surface_groups[{index}] has unknown surface_class {surface_class!r}",
                )
            if not isinstance(surface_operations, list) or not surface_operations:
                lint.fail(operation_path, f"surface_groups[{index}].operations must be a non-empty list")
                continue
            for operation_id in surface_operations:
                if not isinstance(operation_id, str) or not operation_id:
                    lint.fail(operation_path, f"surface_groups[{index}] contains invalid operation_id")
                    continue
                if operation_id not in operation_ids:
                    lint.fail(operation_path, f"surface_groups[{index}] references unknown operation_id {operation_id}")
                    continue
                prior = assigned_operations.get(operation_id)
                if prior is not None:
                    lint.fail(
                        operation_path,
                        f"operation_id {operation_id} assigned to multiple surface_groups: {prior}, {surface}",
                    )
                    continue
                assigned_operations[operation_id] = surface
        for operation_id in sorted(operation_ids - set(assigned_operations)):
            lint.fail(operation_path, f"operation_id missing from surface_groups: {operation_id}")

    profiles: set[str] = set()
    claimable_profiles: set[str] = set()
    if isinstance(profile_registry, dict):
        for key in ("implementation_profiles", "deployment_profiles", "hardening_profiles"):
            values = profile_registry.get(key)
            if isinstance(values, list):
                claimable_profiles.update(
                    item for item in values if isinstance(item, str) and item.startswith("ak.profile.")
                )
    for _, value, _ in walk_json(profile_registry):
        if isinstance(value, str) and value.startswith("ak.profile."):
            if value in event_kinds:
                continue
            profiles.add(value)
            if not PROFILE_ID_RE.fullmatch(value):
                lint.fail(profile_path, f"profile id has invalid format: {value}")

    track_rows = track_registry.get("track_names", [])
    track_names = unique_values(lint, track_path, track_rows, "track_name")
    active_track_names: set[str] = set()
    name_pattern = track_registry.get("name_pattern")
    try:
        compiled_track_name = re.compile(name_pattern) if isinstance(name_pattern, str) else None
    except re.error as exc:
        lint.fail(track_path, f"name_pattern is invalid: {exc}")
        compiled_track_name = None
    if compiled_track_name is None and not isinstance(name_pattern, str):
        lint.fail(track_path, "name_pattern must be a regex string")

    registered_schema_refs = {
        f"{file_ref}{fragment}"
        for file_ref, fragments in schema_refs_by_file.items()
        for fragment in fragments
    }
    for index, row in enumerate(track_rows if isinstance(track_rows, list) else []):
        if not isinstance(row, dict):
            continue
        track_name = row.get("track_name")
        status = row.get("status")
        if isinstance(track_name, str) and compiled_track_name is not None:
            if compiled_track_name.fullmatch(track_name) is None:
                lint.fail(track_path, f"track_names[{index}] has invalid track_name {track_name!r}")
        if status not in {"active", "deprecated"}:
            lint.fail(track_path, f"track_names[{index}].status must be active or deprecated")
        elif status == "active" and isinstance(track_name, str):
            active_track_names.add(track_name)

        owner = row.get("owner")
        if not isinstance(owner, dict):
            lint.fail(track_path, f"track_names[{index}].owner must be an object")
            continue
        owner_kind = owner.get("kind")
        if owner_kind == "schema":
            if set(owner) != {"kind", "schema_ref"}:
                lint.fail(
                    track_path,
                    f"track_names[{index}].owner kind=schema must contain only kind and schema_ref",
                )
            schema_ref = owner.get("schema_ref")
            if not isinstance(schema_ref, str) or schema_ref not in registered_schema_refs:
                lint.fail(
                    track_path,
                    f"track_names[{index}].owner.schema_ref does not resolve through schema-registry: {schema_ref!r}",
                )
        elif owner_kind == "profile":
            if set(owner) != {"kind", "profile_id"}:
                lint.fail(
                    track_path,
                    f"track_names[{index}].owner kind=profile must contain only kind and profile_id",
                )
            profile_id = owner.get("profile_id")
            if not isinstance(profile_id, str) or profile_id not in profiles:
                lint.fail(
                    track_path,
                    f"track_names[{index}].owner.profile_id does not resolve through conformance-profiles: {profile_id!r}",
                )
        else:
            lint.fail(
                track_path,
                f"track_names[{index}].owner.kind must be schema or profile",
            )

    strand_schema_path = ARTIFACTS / "schemas" / "strand.schema.json"
    strand_schema = load_json(lint, strand_schema_path) or {}
    track_name_schema = (
        strand_schema.get("$defs", {}).get("track_name", {})
        if isinstance(strand_schema, dict)
        else {}
    )
    schema_track_names = (
        track_name_schema.get("enum", [])
        if isinstance(track_name_schema, dict)
        else []
    )
    if (
        not isinstance(schema_track_names, list)
        or any(not isinstance(value, str) for value in schema_track_names)
        or len(schema_track_names) != len(set(schema_track_names))
    ):
        lint.fail(
            strand_schema_path,
            "$defs.track_name.enum must be a duplicate-free string array",
        )
    elif set(schema_track_names) != active_track_names:
        lint.fail(
            strand_schema_path,
            "$defs.track_name.enum must exactly equal active track-name-registry names: "
            f"schema={sorted(schema_track_names)!r}, registry={sorted(active_track_names)!r}",
        )
    tracks_property_names = (
        strand_schema.get("properties", {}).get("tracks", {}).get("propertyNames")
        if isinstance(strand_schema, dict)
        else None
    )
    if tracks_property_names != {"$ref": "#/$defs/track_name"}:
        lint.fail(
            strand_schema_path,
            "Strand.tracks.propertyNames must reference #/$defs/track_name",
        )

    track_vector_path = ARTIFACTS / "fixtures" / "state-reducer-hardening-fixture.json"
    track_vector_fixture = load_json(lint, track_vector_path) or {}
    vector_rows = (
        track_vector_fixture.get("cases", [])
        if isinstance(track_vector_fixture, dict)
        else []
    )
    track_vector = next(
        (
            row
            for row in vector_rows
            if isinstance(row, dict)
            and row.get("vector_id") == "ak.vector.strand_tracks_update.atomic.v1"
        ),
        None,
    )
    if not isinstance(track_vector, dict):
        lint.fail(track_vector_path, "missing strand_tracks_update atomic vector")
    else:
        vector_input = track_vector.get("input")
        cases = vector_input.get("cases") if isinstance(vector_input, dict) else None
        if not isinstance(cases, list):
            lint.fail(track_vector_path, "strand_tracks_update vector cases must be a list")
        else:
            has_unknown_rejection = False
            for case_index, case in enumerate(cases):
                if not isinstance(case, dict):
                    continue
                expected = case.get("expected")
                decision = expected.get("decision") if isinstance(expected, dict) else None
                reason = expected.get("reason") if isinstance(expected, dict) else None
                patch = case.get("patch")
                if not isinstance(patch, list):
                    continue
                for patch_index, operation in enumerate(patch):
                    path_value = operation.get("path") if isinstance(operation, dict) else None
                    match = (
                        re.fullmatch(r"tracks\.([a-z][a-z0-9_]{0,63})\.[a-z][a-z0-9_]*", path_value)
                        if isinstance(path_value, str)
                        else None
                    )
                    if match is None:
                        continue
                    vector_track_name = match.group(1)
                    if decision == "accept" and vector_track_name not in active_track_names:
                        lint.fail(
                            track_vector_path,
                            f"cases[{case_index}].patch[{patch_index}] accepts unregistered TrackName {vector_track_name!r}",
                        )
                    if (
                        decision == "reject"
                        and reason == "schema_violation"
                        and vector_track_name not in active_track_names
                    ):
                        has_unknown_rejection = True
            if not has_unknown_rejection:
                lint.fail(
                    track_vector_path,
                    "strand_tracks_update vector must reject an unregistered TrackName with schema_violation",
                )

    constraint_types: set[str] = set()
    constraint_type_schema = (
        constraint_schema.get("properties", {})
        if isinstance(constraint_schema, dict)
        else {}
    ).get("constraint_kind", {})
    enum_values = constraint_type_schema.get("enum") if isinstance(constraint_type_schema, dict) else None
    if isinstance(enum_values, list):
        constraint_types = {item for item in enum_values if isinstance(item, str)}
    if not constraint_types:
        lint.fail(constraint_schema_path, "constraint_kind enum must be non-empty")

    constraint_fields = set(
        constraint_schema.get("properties", {}).keys()
        if isinstance(constraint_schema, dict) and isinstance(constraint_schema.get("properties"), dict)
        else []
    )
    action_path = ARTIFACTS / "registry" / "capability-action-registry.json"
    action_registry = load_json(lint, action_path) or {}
    action_rows = action_registry.get("actions", []) if isinstance(action_registry, dict) else []
    capability_actions = {
        row.get("action")
        for row in action_rows
        if isinstance(row, dict) and isinstance(row.get("action"), str)
    }
    for row in action_rows:
        if not isinstance(row, dict):
            continue
        action = row.get("action", "<unknown>")
        for constraint_name in row.get("required_constraints", []) or []:
            if isinstance(constraint_name, str) and constraint_name not in constraint_fields:
                lint.fail(
                    action_path,
                    f"{action} required_constraints references unknown grant constraint field: {constraint_name}",
                )

    check_operation_bundles_and_features(lint)

    return {
        "event_kinds": event_kinds,
        "active_event_kinds": {
            row["event_kind"]
            for row in event_by_kind.values()
            if row.get("status") == "active"
        },
        "active_durable_event_kinds": {
            row["event_kind"]
            for row in event_by_kind.values()
            if row.get("status") == "active" and row.get("wire_scope") == "durable_event"
        },
        "active_event_wire_scopes": {
            row["event_kind"]: row.get("wire_scope")
            for row in event_by_kind.values()
            if row.get("status") == "active"
        },
        "schema_ids": schema_ids,
        "track_names": track_names,
        "active_track_names": active_track_names,
        "id_kinds": id_kinds,
        # Exact `<fixture file>#<json pointer>|<value>` triples the closed
        # exemption registry pins as deliberate negative vectors or wire-form
        # templates. A gate that rejects every unregistered spelling still has
        # to let a fixture publish the input it exists to reject, and the
        # registry is the only place that can say so per exact value.
        "fixture_typed_id_exemption_keys": {
            f"{pointer}|{value}"
            for (pointer, position, value) in fixture_typed_id_exemptions(lint)
            if position == "value"
        },
        # An Event token leads with the digest-suite wire code. Only the codes
        # the registry marks active are legal; `0x0` is permanently disabled, so
        # a placeholder token of zero bytes must not pass as an Event id.
        "active_digest_suite_wire_codes": {
            row.get("wire_code")
            for row in (
                load_json(lint, ARTIFACTS / "registry" / "digest-suite-registry.json") or {}
            ).get("suites", [])
            if isinstance(row, dict) and row.get("status") == "active"
        },
        "event_derived_id_kinds": event_derived_id_kinds,
        "digest_token_id_kinds": {
            row.get("kind")
            for row in (id_rows if isinstance(id_rows, list) else [])
            if isinstance(row, dict)
            and row.get("id_form") == "suite_tagged_full_digest"
        },
        "special_id_kinds": special_id_kinds,
        "operation_ids": operation_ids,
        "http_only_operation_ids": {
            row["operation_id"]
            for row in operation_rows
            if isinstance(row, dict)
            and isinstance(row.get("operation_id"), str)
            and row.get("http_only_variant") is True
        },
        "operation_http_map": operation_http_map,
        "operation_grpc_map": operation_grpc_map,
        "operation_mq_map": operation_mq_map,
        "profiles": profiles,
        "claimable_profiles": claimable_profiles,
        "constraint_types": constraint_types,
        "capability_actions": capability_actions,
    }


def check_operation_bundles_and_features(lint: Lint) -> None:
    """Validate the clean-break ServiceDescribe deployment catalogs."""
    operation_path = ARTIFACTS / "registry" / "operation-registry.json"
    binding_path = ARTIFACTS / "registry" / "binding-kind-registry.json"
    service_path = ARTIFACTS / "registry" / "service-kind-registry.json"
    feature_path = ARTIFACTS / "registry" / "feature-registry.json"
    profile_path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    operation_registry = load_json(lint, operation_path) or {}
    binding_registry = load_json(lint, binding_path) or {}
    service_registry = load_json(lint, service_path) or {}
    feature_registry = load_json(lint, feature_path) or {}
    profile_registry = load_json(lint, profile_path) or {}

    operations = {
        row.get("operation_id")
        for row in operation_registry.get("operations", [])
        if isinstance(row, dict) and isinstance(row.get("operation_id"), str)
    }
    bindings = {
        row.get("kind")
        for row in binding_registry.get("entries", [])
        if isinstance(row, dict) and row.get("status") in {"active", "candidate"}
    }
    service_kinds = {
        row.get("canonical_id")
        for row in service_registry.get("service_kinds", [])
        if isinstance(row, dict)
        and row.get("status") == "active"
        and "service_describe" in (row.get("valid_in") or [])
    }
    prototypes = {
        row.get("prototype_id")
        for row in operation_registry.get("deployment_prototypes", [])
        if isinstance(row, dict) and isinstance(row.get("prototype_id"), str)
    }
    bundle_pattern = re.compile(r"^ak\.operation_bundle(?:\.[a-z0-9_]+)+\.v1$")
    pair_owners: dict[tuple[str, str, str], str] = {}
    bundle_ids: set[str] = set()
    bundle_pairs: set[tuple[str, str]] = set()
    expected_bundle_keys = {
        "operation_bundle_id", "service_kind", "deployment_evidence", "members"
    }
    for index, bundle in enumerate(operation_registry.get("operation_bundles", [])):
        spot = f"operation_bundles[{index}]"
        if not isinstance(bundle, dict):
            lint.fail(operation_path, f"{spot} must be an object")
            continue
        if set(bundle) != expected_bundle_keys:
            lint.fail(operation_path, f"{spot} must use the closed bundle row shape")
        bundle_id = bundle.get("operation_bundle_id")
        service_kind = bundle.get("service_kind")
        if not isinstance(bundle_id, str) or not bundle_pattern.fullmatch(bundle_id):
            lint.fail(operation_path, f"{spot}.operation_bundle_id must be a registered current-v1 id")
            continue
        if bundle_id in bundle_ids:
            lint.fail(operation_path, f"duplicate operation bundle id: {bundle_id}")
        bundle_ids.add(bundle_id)
        if service_kind not in service_kinds:
            lint.fail(operation_path, f"{bundle_id} references unavailable service_kind {service_kind!r}")
        evidence = bundle.get("deployment_evidence")
        if not isinstance(evidence, list) or not evidence or len(evidence) != len(set(evidence)):
            lint.fail(operation_path, f"{bundle_id}.deployment_evidence must be non-empty and unique")
        else:
            for prototype_id in evidence:
                if isinstance(prototype_id, str) and prototype_id.split("#", 1)[0] in prototypes:
                    continue
                if isinstance(prototype_id, str) and prototype_id.startswith("normative:"):
                    file_ref = prototype_id.removeprefix("normative:").split("#", 1)[0]
                    if (SPEC_ROOT / file_ref).is_file():
                        continue
                lint.fail(operation_path, f"{bundle_id} references unknown deployment evidence {prototype_id!r}")
        members = bundle.get("members")
        if not isinstance(members, list) or not members:
            lint.fail(operation_path, f"{bundle_id}.members must be non-empty")
            continue
        canonical_members: list[tuple[str, str]] = []
        for member_index, member in enumerate(members):
            member_spot = f"{bundle_id}.members[{member_index}]"
            if not isinstance(member, dict) or set(member) != {"operation_id", "binding_kind"}:
                lint.fail(operation_path, f"{member_spot} must be a closed operation/binding pair")
                continue
            operation_id = member.get("operation_id")
            binding_kind = member.get("binding_kind")
            pair = (operation_id, binding_kind)
            canonical_members.append(pair)
            if operation_id not in operations:
                lint.fail(operation_path, f"{member_spot} references unknown operation {operation_id!r}")
            if binding_kind not in bindings:
                lint.fail(operation_path, f"{member_spot} references unknown binding {binding_kind!r}")
            owner_key = (str(service_kind), str(operation_id), str(binding_kind))
            previous = pair_owners.get(owner_key)
            if previous is not None:
                lint.fail(operation_path, f"{bundle_id} overlaps {previous} on pair {pair!r}")
            pair_owners[owner_key] = bundle_id
            bundle_pairs.add((str(operation_id), str(binding_kind)))
        if canonical_members != sorted(set(canonical_members)):
            lint.fail(operation_path, f"{bundle_id}.members must be unique and canonical-sorted")

    if len(bundle_ids) != 37:
        lint.fail(operation_path, f"operation_bundles must contain the 37 evidenced v1 bundles, got {len(bundle_ids)}")
    describe_pair = ("ak.server.read.describe.v1", "http_json")
    for service_kind in sorted(service_kinds):
        describe_bundle_id = f"ak.operation_bundle.{service_kind}.describe.v1"
        matching = [
            row
            for row in operation_registry.get("operation_bundles", [])
            if isinstance(row, dict) and row.get("operation_bundle_id") == describe_bundle_id
        ]
        if len(matching) != 1:
            lint.fail(
                operation_path,
                f"{service_kind} must have exactly one role-local {describe_bundle_id}",
            )
            continue
        member_pairs = [
            (member.get("operation_id"), member.get("binding_kind"))
            for member in matching[0].get("members", [])
            if isinstance(member, dict)
        ]
        if matching[0].get("service_kind") != service_kind or member_pairs != [describe_pair]:
            lint.fail(
                operation_path,
                f"{describe_bundle_id} must belong to {service_kind} and contain only {describe_pair!r}",
            )

    bundles_by_id = {
        row.get("operation_bundle_id"): row
        for row in operation_registry.get("operation_bundles", [])
        if isinstance(row, dict) and isinstance(row.get("operation_bundle_id"), str)
    }
    surface_operations = {
        row.get("surface"): {
            operation_id
            for operation_id in row.get("operations", [])
            if isinstance(operation_id, str)
        }
        for row in operation_registry.get("surface_groups", [])
        if isinstance(row, dict) and isinstance(row.get("surface"), str)
    }

    def exact_http_members(bundle_id: str) -> set[str]:
        bundle = bundles_by_id.get(bundle_id)
        if not isinstance(bundle, dict):
            lint.fail(operation_path, f"required evidenced bundle is missing: {bundle_id}")
            return set()
        members = bundle.get("members")
        if not isinstance(members, list):
            return set()
        if any(
            not isinstance(member, dict) or member.get("binding_kind") != "http_json"
            for member in members
        ):
            lint.fail(operation_path, f"{bundle_id} must be an HTTP/JSON-only evidenced bundle")
        return {
            member.get("operation_id")
            for member in members
            if isinstance(member, dict) and isinstance(member.get("operation_id"), str)
        }

    identity_surface = surface_operations.get("identity_registry", set())
    identity_core = exact_http_members("ak.operation_bundle.identity_registry.http_core.v1")
    if identity_core != identity_surface:
        lint.fail(
            operation_path,
            "identity_registry.http_core must exactly project Soland's mounted identity_registry surface",
        )

    directory_surface = surface_operations.get("directory_discovery", set())
    directory_optional = {
        "ak.find.directory.read.private_contact_discovery.v1",
        "ak.find.directory.read.resolve_agent_selector.v1",
    }
    directory_core = exact_http_members("ak.operation_bundle.directory_service.http_core.v1")
    if directory_core != directory_surface - directory_optional:
        lint.fail(
            operation_path,
            "directory_service.http_core must be the exact Soland/Teabay common support vector",
        )
    for bundle_id, operation_id in (
        (
            "ak.operation_bundle.directory_service.private_contact_discovery.v1",
            "ak.find.directory.read.private_contact_discovery.v1",
        ),
        (
            "ak.operation_bundle.directory_service.resolve_agent_selector.v1",
            "ak.find.directory.read.resolve_agent_selector.v1",
        ),
    ):
        if exact_http_members(bundle_id) != {operation_id}:
            lint.fail(operation_path, f"{bundle_id} must contain only {operation_id}")

    auth_account_authority = exact_http_members(
        "ak.operation_bundle.station.account_authority.v1"
    )
    expected_auth_account_authority = {
        "ak.gate.account.command.abandon_identity_creation.v1",
        "ak.gate.account.command.issue_controller_gate_attestation.v1",
        "ak.gate.account.command.issue_did_binding_challenge.v1",
        "ak.gate.account.command.request_erasure.v1",
        "ak.gate.account.read.onboarding.v1",
    }
    if auth_account_authority != expected_auth_account_authority:
        lint.fail(
            operation_path,
            "station.account_authority must exactly project Coauth's deployment-private Account Authority routes",
        )

    principal_core = exact_http_members("ak.operation_bundle.station.http_core.v1")
    leaked_role_operations = sorted(principal_core & (identity_surface | directory_surface))
    if leaked_role_operations:
        lint.fail(
            operation_path,
            "station.http_core leaks identity/directory role operations: "
            f"{leaked_role_operations}",
        )

    history_key_recovery = exact_http_members(
        "ak.operation_bundle.station.history_key_recovery.v1"
    )
    if history_key_recovery != surface_operations.get("history_key_recovery", set()):
        lint.fail(
            operation_path,
            "station.history_key_recovery must exactly project the complete history_key_recovery surface",
        )

    device_pairing_handoff = exact_http_members(
        "ak.operation_bundle.station.device_pairing_handoff.v1"
    )
    if device_pairing_handoff != surface_operations.get("device_pairing_handoff", set()):
        lint.fail(
            operation_path,
            "station.device_pairing_handoff must exactly project the complete device_pairing_handoff surface",
        )

    migration_path = ROOT / "tools" / "operation-id-v1-migration.json"
    migration = load_json(lint, migration_path) or {}
    if migration.get("runtime_aliases") is not False:
        lint.fail(migration_path, "operation migration map must explicitly forbid runtime aliases")
    mappings = migration.get("mappings")
    mapped_new: set[str] = set()
    mapped_old: set[str] = set()
    if not isinstance(mappings, list):
        lint.fail(migration_path, "mappings must be an array")
    else:
        for index, row in enumerate(mappings):
            if not isinstance(row, dict) or set(row) != {"old", "new"}:
                lint.fail(migration_path, f"mappings[{index}] must contain exactly old and new")
                continue
            old = row.get("old")
            new = row.get("new")
            if not isinstance(old, str) or not isinstance(new, str) or new != old + ".v1":
                lint.fail(migration_path, f"mappings[{index}] must be a mechanical old -> old.v1 rename")
                continue
            mapped_old.add(old)
            mapped_new.add(new)
        if len(mapped_old) != len(mappings) or len(mapped_new) != len(mappings):
            lint.fail(migration_path, "migration mappings must be one-to-one")
        if mapped_new != operations:
            lint.fail(
                migration_path,
                "migration new-id set must exactly equal the canonical operation registry",
            )

    profiles = {
        row.get("profile")
        for row in profile_registry.get("profile_requirements", [])
        if isinstance(row, dict) and isinstance(row.get("profile"), str)
    }
    feature_pattern = re.compile(r"^ak\.feature(?:\.[a-z0-9_]+)+\.v1$")
    feature_ids: set[str] = set()
    expected_feature_keys = {
        "feature_id", "status", "defined_in", "service_kinds",
        "required_operation_pairs", "required_profiles", "required_limits",
        "semantic_guarantees", "conflicts",
    }
    for index, feature in enumerate(feature_registry.get("features", [])):
        spot = f"features[{index}]"
        if not isinstance(feature, dict):
            lint.fail(feature_path, f"{spot} must be an object")
            continue
        if set(feature) != expected_feature_keys:
            lint.fail(feature_path, f"{spot} must use the closed feature row shape")
        feature_id = feature.get("feature_id")
        if not isinstance(feature_id, str) or not feature_pattern.fullmatch(feature_id):
            lint.fail(feature_path, f"{spot}.feature_id must be an exact current-v1 id")
            continue
        if feature_id in feature_ids:
            lint.fail(feature_path, f"duplicate feature id: {feature_id}")
        feature_ids.add(feature_id)
        if feature.get("status") not in {"active", "test_only"}:
            lint.fail(feature_path, f"{feature_id}.status must be active or test_only")
        defined_in = feature.get("defined_in")
        if not isinstance(defined_in, str) or not (SPEC_ROOT / defined_in.split("#", 1)[0]).is_file():
            lint.fail(feature_path, f"{feature_id}.defined_in does not resolve: {defined_in!r}")
        for service_kind in feature.get("service_kinds", []) or []:
            if service_kind not in service_kinds:
                lint.fail(feature_path, f"{feature_id} references unknown service_kind {service_kind!r}")
        for pair in feature.get("required_operation_pairs", []) or []:
            if not isinstance(pair, dict) or set(pair) != {"operation_id", "binding_kind"}:
                lint.fail(feature_path, f"{feature_id} has a malformed required operation pair")
                continue
            exact_pair = (pair.get("operation_id"), pair.get("binding_kind"))
            if exact_pair not in bundle_pairs:
                lint.fail(feature_path, f"{feature_id} requires a pair absent from every bundle: {exact_pair!r}")
        for profile in feature.get("required_profiles", []) or []:
            if profile not in profiles:
                lint.fail(feature_path, f"{feature_id} references unknown profile {profile!r}")
        guarantees = feature.get("semantic_guarantees")
        if feature.get("status") == "active" and not feature.get("required_operation_pairs") and not guarantees:
            lint.fail(feature_path, f"{feature_id} is redundant: no operation prerequisite or semantic guarantee")
        conflicts = feature.get("conflicts")
        if not isinstance(conflicts, list) or len(conflicts) != len(set(conflicts)):
            lint.fail(feature_path, f"{feature_id}.conflicts must be a unique array")

    feature_token = re.compile(r"ak\.feature(?:\.[a-z0-9_]+)+\.v1")
    referenced: set[str] = set()
    for path in text_contract_files():
        referenced.update(feature_token.findall(read_text(path)))
    for feature_id in sorted(referenced - feature_ids):
        lint.fail(feature_path, f"unregistered exact feature token referenced by spec: {feature_id}")



def check_event_id_suite_registry(lint: Lint) -> None:
    path = ARTIFACTS / "registry" / "digest-suite-registry.json"
    data = load_json(lint, path)
    rows = data.get("suites", []) if isinstance(data, dict) else []
    expected_codes = {"sha256": 0x01, "blake3": 0x02, "cbor.sha256": 0x03}
    seen: dict[int, str] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        suite_id = row.get("canonical_id")
        code = row.get("wire_code")
        if not isinstance(code, int) or not 0 < code <= 0x0F:
            lint.fail(path, f"{suite_id!r} must declare assigned uint4 wire_code 0x01..0x0F")
            continue
        if code in seen:
            lint.fail(path, f"wire_code 0x{code:02x} reused by {seen[code]!r} and {suite_id!r}")
        seen[code] = str(suite_id)
        if row.get("digest_length_bytes") != 32:
            lint.fail(path, f"{suite_id!r} cannot use v1 Event-ID format with non-32-byte digest")
        if suite_id in expected_codes and code != expected_codes[suite_id]:
            lint.fail(path, f"{suite_id} wire_code must remain 0x{expected_codes[suite_id]:02x}")
    for suite_id, code in expected_codes.items():
        if seen.get(code) != suite_id:
            lint.fail(path, f"wire_code 0x{code:02x} must be assigned to {suite_id}")



def check_retired_event_id_contract(lint: Lint) -> None:
    retired = re.compile(r"UUIDv8|uuidv8|34[- ]bit|88[- ]bit|11[- ]octet|248[- ]bit|31[- ]octet prefix|公元 2514|时间戳段")
    owners = [
        *sorted((SPEC_ROOT / "zh").rglob("*.md")),
        *sorted((ARTIFACTS / "schemas").glob("*.json")),
        ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml",
        ARTIFACTS / "registry/digest-suite-registry.json",
        ARTIFACTS / "registry/id-kind-registry.json",
        ARTIFACTS / "registry/vector-registry.json",
    ]
    for path in owners:
        match = retired.search(read_text(path))
        if match:
            lint.fail(path, f"retired Event-ID contract term remains: {match.group(0)!r}")
    old_pattern = "^ak:event:[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
    id_registry_path = ARTIFACTS / "registry" / "id-kind-registry.json"
    id_registry = load_json(lint, id_registry_path)
    id_rows = id_registry.get("id_kinds", []) if isinstance(id_registry, dict) else []
    retired_event_derived_kinds = {
        row.get("kind")
        for row in id_rows
        if isinstance(row, dict)
        and row.get("id_form") == "event_derived"
        and isinstance(row.get("kind"), str)
    }
    for path in sorted((ARTIFACTS / "schemas").glob("*.json")):
        schema_text = read_text(path)
        if old_pattern in schema_text:
            lint.fail(path, "schema retains retired UUIDv8 Event-ID pattern")
        for kind in retired_event_derived_kinds:
            derived_old_pattern = f"^ak:{kind}:[0-9a-f]{{8}}-[0-9a-f]{{4}}-8[0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}"
            if derived_old_pattern in schema_text:
                lint.fail(path, f"schema retains retired UUIDv8 pattern for event-derived ak:{kind} ID")



def check_protocol_layer_registry(lint: Lint) -> None:
    """Require an exhaustive, single-owner layer classification for active Event kinds."""
    path = ARTIFACTS / "registry" / "protocol-layer-registry.json"
    data = load_json(lint, path)
    event_registry_path = ARTIFACTS / "registry" / "event-kind-registry.json"
    event_registry = load_json(lint, event_registry_path)
    if not isinstance(data, dict) or not isinstance(event_registry, dict):
        return

    layers = data.get("event_kinds")
    expected_layer_names = {"kernel", "collaboration_base", "extension"}
    if not isinstance(layers, dict) or set(layers) != expected_layer_names:
        lint.fail(
            path,
            "event_kinds must contain exactly kernel, collaboration_base, and extension",
        )
        return

    classified: list[str] = []
    for layer_name in ("kernel", "collaboration_base", "extension"):
        values = layers.get(layer_name)
        if not isinstance(values, list) or not values:
            lint.fail(path, f"event_kinds.{layer_name} must be a non-empty array")
            continue
        if values != sorted(values):
            lint.fail(path, f"event_kinds.{layer_name} must be sorted")
        if any(not isinstance(value, str) for value in values):
            lint.fail(path, f"event_kinds.{layer_name} entries must be strings")
            continue
        classified.extend(values)

    duplicates = sorted(
        value for value, count in Counter(classified).items() if count > 1
    )
    if duplicates:
        lint.fail(path, f"Event kinds assigned to multiple layers: {duplicates}")

    active = {
        row.get("event_kind")
        for row in event_registry.get("event_kinds", [])
        if isinstance(row, dict) and row.get("status") == "active"
    }
    actual = set(classified)
    missing = sorted(active - actual)
    extra = sorted(actual - active)
    if missing:
        lint.fail(path, f"active Event kinds missing a protocol layer: {missing}")
    if extra:
        lint.fail(path, f"unknown or inactive Event kinds have a protocol layer: {extra}")

    envelope_path = ARTIFACTS / "schemas" / "event-envelope.schema.json"
    envelope = load_json(lint, envelope_path)
    protocol_prose_path = SPEC_ROOT / "zh" / "overview" / "protocol-layers.md"
    protocol_prose = read_text(protocol_prose_path)
    if isinstance(envelope, dict):
        branches = envelope.get("$defs", {}).get("scope_ref", {}).get("oneOf", [])
        scope_kinds = {
            branch.get("properties", {}).get("kind", {}).get("const")
            for branch in branches
            if isinstance(branch, dict)
        }
        expected_scope_kinds = {"realm", "circle", "sidecar", "realm_genesis"}
        if scope_kinds != expected_scope_kinds:
            lint.fail(
                envelope_path,
                f"scope_ref closed union must be exactly {sorted(expected_scope_kinds)}",
            )
        for scope_kind in expected_scope_kinds:
            if f'"kind":"{scope_kind}"' not in protocol_prose:
                lint.fail(
                    protocol_prose_path,
                    f"Security Scope prose omits schema scope_ref kind {scope_kind}",
                )



def check_id_form_wire_schema_alignment(lint: Lint) -> None:
    """Join ID classification, derived wire forms, wire schema regexes, and storage rules.

    The regex side is collected from every shipped validation carrier, JSON
    Schema and OpenAPI alike, and each carrier is expanded into its concrete
    alternation branches. A union such as ``^ak:(realm|space):<payload>$``
    therefore constrains ``realm`` and ``space`` individually instead of
    escaping a ``startswith`` probe that only ever saw single-kind regexes.
    """
    registry_path = ARTIFACTS / "registry" / "id-kind-registry.json"
    registry = load_json(lint, registry_path)
    if not isinstance(registry, dict):
        return
    rows = registry.get("id_kinds")
    if not isinstance(rows, list):
        return
    storage_rules = registry.get("storage_rules")
    if not isinstance(storage_rules, list) or not all(isinstance(rule, str) for rule in storage_rules):
        lint.fail(registry_path, "storage_rules must be a string array")
        return
    storage_text = "\n".join(storage_rules).lower()
    for forbidden in ("uuidv8", "version 8"):
        if forbidden in storage_text:
            lint.fail(registry_path, f"storage_rules retain forbidden Event-derived UUID wording {forbidden!r}")
    if "raw 33-byte token" not in storage_text or "must not use a native uuid column" not in storage_text:
        lint.fail(registry_path, "storage_rules must require 33-byte digest tokens outside native UUID columns")

    branches_by_kind = typed_id_payload_branches_by_kind(lint)

    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = row.get("kind")
        id_form = row.get("id_form")
        wire_form = row.get("wire_form")
        if not isinstance(kind, str):
            continue
        matching = branches_by_kind.get(kind, [])
        if id_form == "event_derived":
            expected_wire = f"ak:{kind}:<44-char-event-token>"
            if wire_form != expected_wire:
                lint.fail(registry_path, f"{kind} event-derived wire_form must equal {expected_wire!r}")
            if not matching:
                lint.fail(registry_path, f"{kind} event-derived ID has no schema regex")
            if matching and not any(
                payload.startswith(EVENT_TOKEN_PAYLOAD_REGEX) for *_, payload in matching
            ):
                lint.fail(registry_path, f"event-derived {kind} schemas never require a 44-character token")
            report_inverted_id_form_payloads(lint, kind, "event-derived", matching)
        elif id_form == "suite_tagged_full_digest":
            expected_wire = f"ak:{kind}:<44-char-suite-tagged-full-digest-token>"
            if wire_form != expected_wire:
                lint.fail(registry_path, f"{kind} suite-tagged wire_form must equal {expected_wire!r}")
            if not matching:
                lint.fail(registry_path, f"{kind} suite-tagged ID has no schema regex")
            if matching and not any(
                payload.startswith(EVENT_TOKEN_PAYLOAD_REGEX) for *_, payload in matching
            ):
                lint.fail(registry_path, f"suite-tagged {kind} schemas never require a 44-character token")
            report_inverted_id_form_payloads(lint, kind, "suite-tagged", matching)
        elif id_form == "producer_allocated":
            expected_wire = f"ak:{kind}:<uuidv7>"
            if wire_form != expected_wire:
                lint.fail(registry_path, f"{kind} producer wire_form must equal {expected_wire!r}")
            if matching and not any(
                payload.startswith(PRODUCER_UUID_PAYLOAD_REGEX) for *_, payload in matching
            ):
                lint.fail(registry_path, f"producer-allocated {kind} schemas never require UUIDv7")
            for path, json_path, pattern, payload in matching:
                if not payload.startswith(EVENT_TOKEN_PAYLOAD_REGEX):
                    continue
                lint.fail(
                    path,
                    f"{json_path} validates producer-allocated ak:{kind} with a 44-character "
                    f"token payload {payload!r} (carrier {pattern!r}); the canonical wire form is "
                    f"ak:{kind}:{PRODUCER_UUID_PAYLOAD_REGEX}",
                )


TYPED_ID_WIRE_PREFIX_RE = re.compile(r"^ak:([A-Za-z0-9_-]+):")
TYPED_ID_BRANCH_PREFIX_RE = re.compile(r"^\^?ak:([A-Za-z0-9_-]+):")
REGEX_QUANTIFIER_RE = re.compile(r"[*+?]|\{\d+(?:,\d*)?\}")
REGEX_LITERAL_BRANCH_LIMIT = 512
REGEX_LITERAL_TEXT_LIMIT = 256
EVENT_TOKEN_PAYLOAD_REGEX = "[A-Za-z0-9_-]{44}"
PRODUCER_UUID_PAYLOAD_REGEX = (
    "[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
UUID_PAYLOAD_PREFIX_RE = re.compile(r"^\[0-9a-f\]\{8\}-\[0-9a-f\]\{4\}-")


def report_inverted_id_form_payloads(
    lint: Lint,
    kind: str,
    label: str,
    matching: list[tuple[Path, str, str, str]],
) -> None:
    """Fail on a digest-token kind whose carrier validates a UUID payload instead.

    This is the inverted contract the OpenAPI mirror shipped: the canonical
    44-character token was rejected while a UUID shape the protocol declares
    permanently invalid was accepted. Any UUID payload is rejected, not only the
    retired version-8 layout, because no digest-token kind has a UUID form at all.
    """
    for path, json_path, pattern, payload in matching:
        if not UUID_PAYLOAD_PREFIX_RE.match(payload):
            continue
        lint.fail(
            path,
            f"{json_path} validates {label} ak:{kind} with a UUID payload {payload!r} "
            f"(carrier {pattern!r}); the canonical wire form is "
            f"ak:{kind}:{EVENT_TOKEN_PAYLOAD_REGEX}",
        )


def typed_id_wire_prefix(wire_form: object) -> str | None:
    """Parse the canonical ``ak:<segment>:`` prefix out of a registry wire_form.

    Both ``id_kinds`` and ``special_forms`` declare their prefix inside
    ``wire_form``, so the gate never needs a hand-written allowlist that cannot
    be validated back against the registry.
    """
    if not isinstance(wire_form, str):
        return None
    match = TYPED_ID_WIRE_PREFIX_RE.match(wire_form)
    if match is None:
        return None
    return f"ak:{match.group(1)}:"


def registered_typed_id_wire_prefixes(
    registry: object,
) -> tuple[dict[str, str], list[str]]:
    """Return {canonical wire prefix: kind} plus registry-side defects."""
    prefixes: dict[str, str] = {}
    errors: list[str] = []
    if not isinstance(registry, dict):
        return prefixes, ["id kind registry is not an object"]
    for section in ("id_kinds", "special_forms"):
        rows = registry.get(section)
        if not isinstance(rows, list):
            errors.append(f"{section} must be an array")
            continue
        for row in rows:
            if not isinstance(row, dict):
                errors.append(f"{section} rows must be objects")
                continue
            kind = row.get("kind")
            wire_form = row.get("wire_form")
            if not isinstance(kind, str) or not kind:
                errors.append(f"{section} row has a missing or non-string kind")
                continue
            prefix = typed_id_wire_prefix(wire_form)
            if prefix is None:
                errors.append(
                    f"{section} row {kind} wire_form {wire_form!r} does not start with a "
                    "parsable ak:<segment>: prefix"
                )
                continue
            segment = prefix[3:-1]
            # The wire segment MUST be the snake_case kind verbatim. A per-row
            # rationale used to buy an exception here, but a gate can force a
            # rationale to exist and cannot force it to be true: the single
            # registered exception turned out to rest on nothing but its own
            # prior existence, so the exception slot is gone.
            if segment != kind:
                errors.append(
                    f"{section} row {kind} declares wire segment {segment!r}; a wire segment "
                    "MUST equal its snake_case kind verbatim"
                )
            if row.get("wire_segment_rationale") is not None:
                errors.append(
                    f"{section} row {kind} carries wire_segment_rationale; wire segments no "
                    "longer admit spelling exceptions, so the field MUST be absent"
                )
            owner = prefixes.get(prefix)
            if owner is not None and owner != kind:
                errors.append(
                    f"wire prefix {prefix!r} is claimed by both {owner!r} and {kind!r}; "
                    "a prefix MUST resolve to exactly one registered kind"
                )
            prefixes[prefix] = kind
    return prefixes, errors


def _regex_close(states: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    return [(text, False) for text, _ in states]


def _regex_append(states: list[tuple[str, bool]], text: str) -> list[tuple[str, bool]]:
    grown: list[tuple[str, bool]] = []
    for current, open_ in states:
        if not open_ or len(current) >= REGEX_LITERAL_TEXT_LIMIT:
            grown.append((current, False))
        else:
            grown.append((current + text, True))
    return grown


def _regex_dedupe(states: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    seen: dict[tuple[str, bool], None] = {}
    for state in states:
        seen.setdefault(state, None)
    trimmed = list(seen)
    if len(trimmed) > REGEX_LITERAL_BRANCH_LIMIT:
        return _regex_close(trimmed[:REGEX_LITERAL_BRANCH_LIMIT])
    return trimmed


def _regex_skip_class(pattern: str, index: int) -> int:
    index += 1
    if index < len(pattern) and pattern[index] == "^":
        index += 1
    if index < len(pattern) and pattern[index] == "]":
        index += 1
    while index < len(pattern) and pattern[index] != "]":
        index += 2 if pattern[index] == "\\" else 1
    return min(index + 1, len(pattern))


def _regex_skip_group(pattern: str, index: int) -> int:
    depth = 1
    while index < len(pattern) and depth:
        char = pattern[index]
        if char == "\\":
            index += 1
        elif char == "[":
            index = _regex_skip_class(pattern, index) - 1
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        index += 1
    return index


def _regex_read_quantifier(pattern: str, index: int) -> tuple[bool, int]:
    match = REGEX_QUANTIFIER_RE.match(pattern, index)
    if match is None:
        return False, index
    index = match.end()
    if index < len(pattern) and pattern[index] in "?+":
        index += 1
    return True, index


def _regex_parse_sequence(
    pattern: str, index: int
) -> tuple[list[tuple[str, bool]], int]:
    states: list[tuple[str, bool]] = [("", True)]
    while index < len(pattern) and pattern[index] not in "|)":
        char = pattern[index]
        if char in "^$":
            index += 1
            continue
        if char == "(":
            index += 1
            if pattern.startswith("?:", index):
                index += 2
            elif pattern.startswith("?", index):
                index = _regex_skip_group(pattern, index)
                _, index = _regex_read_quantifier(pattern, index)
                states = _regex_close(states)
                continue
            inner, index = _regex_parse_alternation(pattern, index)
            if index >= len(pattern) or pattern[index] != ")":
                return _regex_close(states), len(pattern)
            index += 1
            quantified, index = _regex_read_quantifier(pattern, index)
            if quantified:
                states = _regex_close(states)
                continue
            merged: list[tuple[str, bool]] = []
            for text, open_ in states:
                if not open_:
                    merged.append((text, False))
                    continue
                for inner_text, inner_open in inner:
                    merged.append((text + inner_text, inner_open))
            states = _regex_dedupe(merged)
            continue
        if char == "[":
            index = _regex_skip_class(pattern, index)
            _, index = _regex_read_quantifier(pattern, index)
            states = _regex_close(states)
            continue
        if char == ".":
            index += 1
            _, index = _regex_read_quantifier(pattern, index)
            states = _regex_close(states)
            continue
        if char == "\\":
            if index + 1 >= len(pattern):
                return _regex_close(states), len(pattern)
            escaped = pattern[index + 1]
            index += 2
            quantified, index = _regex_read_quantifier(pattern, index)
            if quantified or escaped.isalnum():
                states = _regex_close(states)
            else:
                states = _regex_append(states, escaped)
            continue
        index += 1
        quantified, index = _regex_read_quantifier(pattern, index)
        if quantified:
            states = _regex_close(states)
        else:
            states = _regex_append(states, char)
    return states, index


def _regex_parse_alternation(
    pattern: str, index: int
) -> tuple[list[tuple[str, bool]], int]:
    branches, index = _regex_parse_sequence(pattern, index)
    while index < len(pattern) and pattern[index] == "|":
        more, index = _regex_parse_sequence(pattern, index + 1)
        branches = _regex_dedupe(branches + more)
    return branches, index


def regex_literal_branches(pattern: str) -> list[tuple[str, bool]]:
    """Expand a JSON Schema regex into ``(literal text, is_complete)`` branches.

    ``is_complete`` is False when the branch stopped at a character class,
    wildcard, quantifier or lookaround, meaning the literal text only covers a
    prefix of what that branch can accept. Grouped and union patterns are
    expanded, so ``^ak:(a|b):x$`` yields both concrete branches instead of one
    opaque string.
    """
    branches, _ = _regex_parse_alternation(pattern, 0)
    return branches


def _regex_source_quantifier(pattern: str, index: int) -> tuple[str, int]:
    match = REGEX_QUANTIFIER_RE.match(pattern, index)
    if match is None:
        return "", index
    end = match.end()
    if end < len(pattern) and pattern[end] in "?+":
        end += 1
    return pattern[index:end], end


def _regex_expansion_dedupe(branches: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for branch in branches:
        seen.setdefault(branch, None)
    return list(seen)[:REGEX_LITERAL_BRANCH_LIMIT]


def _regex_expand_sequence(pattern: str, index: int) -> tuple[list[str], int]:
    branches = [""]
    while index < len(pattern) and pattern[index] not in "|)":
        char = pattern[index]
        if char == "(":
            start = index
            index += 1
            if pattern.startswith("?:", index):
                index += 2
            elif pattern.startswith("?", index):
                end = _regex_skip_group(pattern, index)
                _, end = _regex_source_quantifier(pattern, end)
                branches = [text + pattern[start:end] for text in branches]
                index = end
                continue
            inner, index = _regex_expand_alternation(pattern, index)
            if index >= len(pattern) or pattern[index] != ")":
                return [text + pattern[start:] for text in branches], len(pattern)
            index += 1
            quantifier, index = _regex_source_quantifier(pattern, index)
            if quantifier:
                branches = [text + pattern[start:index] for text in branches]
                continue
            branches = _regex_expansion_dedupe(
                [text + option for text in branches for option in inner]
            )
            continue
        if char == "[":
            end = _regex_skip_class(pattern, index)
            _, end = _regex_source_quantifier(pattern, end)
            branches = [text + pattern[index:end] for text in branches]
            index = end
            continue
        if char == "\\":
            end = min(index + 2, len(pattern))
            _, end = _regex_source_quantifier(pattern, end)
            branches = [text + pattern[index:end] for text in branches]
            index = end
            continue
        end = index + 1
        _, end = _regex_source_quantifier(pattern, end)
        branches = [text + pattern[index:end] for text in branches]
        index = end
    return branches, index


def _regex_expand_alternation(pattern: str, index: int) -> tuple[list[str], int]:
    branches, index = _regex_expand_sequence(pattern, index)
    while index < len(pattern) and pattern[index] == "|":
        more, index = _regex_expand_sequence(pattern, index + 1)
        branches = _regex_expansion_dedupe(branches + more)
    return branches, index


def regex_alternation_expansions(pattern: str) -> list[str]:
    """Expand one regex into a concrete regex per alternation branch.

    ``regex_literal_branches`` keeps only the literal head of a branch, which is
    enough to read a typed-ID prefix but says nothing about the payload that
    follows it. This expander preserves regex source instead, so
    ``^ak:(realm|space):[A-Za-z0-9_-]{44}$`` becomes two self-contained regexes
    whose payload can be compared against the id_form the registry declares.
    Character classes, escapes and quantified groups are copied verbatim: they
    are opaque to the caller, not silently dropped.
    """
    branches, _ = _regex_expand_alternation(pattern, 0)
    return branches


def typed_id_payload_branches(pattern: str) -> list[tuple[str, str]]:
    """Return ``(kind segment, payload regex)`` per typed-ID branch of one regex.

    A branch whose kind segment is itself a character class declares no literal
    kind, so it yields nothing; there is no registry row to hold it to.
    """
    return [
        (segment, payload)
        for segment, payload, _anchored in typed_id_anchored_payload_branches(pattern)
    ]


def typed_id_anchored_payload_branches(pattern: str) -> list[tuple[str, str, bool]]:
    """Return ``(kind segment, payload regex, end anchored)`` per typed-ID branch.

    Whether the branch terminates matters as much as what it spells: a carrier
    that stops at ``^ak:cell:<component>:`` constrains nothing after the anchor,
    so an unterminated branch accepts every trailing byte the registry never
    declared. The anchor flag is kept beside the payload so one closure can hold
    both facts instead of re-parsing the regex.
    """
    branches: list[tuple[str, str, bool]] = []
    for branch in regex_alternation_expansions(pattern):
        match = TYPED_ID_BRANCH_PREFIX_RE.match(branch)
        if match is None:
            continue
        payload = branch[match.end():]
        anchored = payload.endswith("$")
        if anchored:
            payload = payload[:-1]
        branches.append((match.group(1), payload, anchored))
    return branches


def regex_carriers_in_document(document: Any) -> list[tuple[str, str]]:
    """Return every regex that validates wire text in one document.

    ``pattern`` constrains a value, ``patternProperties`` keys constrain object
    keys, and both are shipped validation. Sweeping only ``pattern`` left typed
    IDs used as object keys outside every closure.
    """
    carriers: list[tuple[str, str]] = []
    if not isinstance(document, dict):
        return carriers
    for json_path, value, key in walk_json(document):
        if key == "pattern" and isinstance(value, str):
            carriers.append((json_path, value))
        elif key == "patternProperties" and isinstance(value, dict):
            for member in value:
                if isinstance(member, str):
                    carriers.append((f"{json_path}[{member}]", member))
    return carriers


def literal_typed_id_prefixes(value: str) -> set[str]:
    """Return the literal ``ak:<segment>:`` prefix carried by one literal string.

    A branch whose kind segment never terminates in literal text (``^ak:[a-z_]+:``
    and friends) resolves to nothing: it declares no literal prefix, so there is
    nothing for the registry to close over.
    """
    if not value.startswith("ak:"):
        return set()
    remainder = value[3:]
    boundary = remainder.find(":")
    if boundary <= 0:
        return set()
    return {f"ak:{remainder[:boundary]}:"}


def typed_id_prefix_carriers_in_document(
    path: Path, document: Any
) -> list[tuple[Path, str, str, set[str]]]:
    """Collect every validation carrier in one document that accepts a literal typed ID.

    ``pattern``, ``patternProperties`` keys, ``const`` and ``enum`` are all
    validation carriers; restricting the sweep to ``pattern`` values starting
    with ``^ak:`` would miss grouped and union regexes, typed IDs used as object
    keys, plus constant IDs entirely. The whole document is walked, so a shape
    reused through a local ``$ref`` is inspected at its definition site.
    """
    carriers: list[tuple[Path, str, str, set[str]]] = []
    if not isinstance(document, dict):
        return carriers
    for json_path, regex in regex_carriers_in_document(document):
        found: set[str] = set()
        for text, _complete in regex_literal_branches(regex):
            found |= literal_typed_id_prefixes(text)
        if found:
            carriers.append((path, json_path, regex, found))
    for json_path, value, key in walk_json(document):
        if key == "const" and isinstance(value, str):
            found = literal_typed_id_prefixes(value)
            if found:
                carriers.append((path, json_path, value, found))
        elif key == "enum" and isinstance(value, list):
            found = set()
            for member in value:
                if isinstance(member, str):
                    found |= literal_typed_id_prefixes(member)
            if found:
                carriers.append((path, json_path, repr(value), found))
    return carriers


def typed_id_validation_documents(lint: Lint) -> list[tuple[Path, Any]]:
    """Return every shipped document that can validate a typed ID on the wire.

    Both closure directions read this one list, so ``registry -> artifact`` and
    ``artifact -> registry`` can never disagree about which files are inside the
    typed-ID contract. The OpenAPI mirror is a published external contract, not
    documentation, so it is swept exactly like a JSON Schema.
    """
    documents: list[tuple[Path, Any]] = []
    for schema_path in sorted((ARTIFACTS / "schemas").glob("*.schema.json")):
        documents.append((schema_path, load_json(lint, schema_path)))
    for openapi_path in sorted((ARTIFACTS / "openapi").glob("*.yaml")):
        documents.append((openapi_path, load_yaml(lint, openapi_path)))
    return documents


def schema_typed_id_prefix_carriers(
    lint: Lint,
) -> list[tuple[Path, str, str, set[str]]]:
    """Sweep every shipped schema plus the OpenAPI mirror for typed ID carriers."""
    carriers: list[tuple[Path, str, str, set[str]]] = []
    for path, document in typed_id_validation_documents(lint):
        carriers.extend(typed_id_prefix_carriers_in_document(path, document))
    return carriers


def typed_id_payload_branches_by_kind(
    lint: Lint,
) -> dict[str, list[tuple[Path, str, str, str]]]:
    """Group every swept ``pattern`` branch by the typed-ID kind it validates.

    Each row is ``(document, json path, carrier regex, payload regex)``. An
    OpenAPI field reached through ``$ref`` or ``allOf`` is inspected at the
    definition site the reference resolves to, which the whole-document walk
    always visits, so no carrier hides behind an indirection.
    """
    grouped: dict[str, list[tuple[Path, str, str, str]]] = {}
    for path, json_path, carrier, segment, payload, _anchored in typed_id_payload_branch_rows(lint):
        grouped.setdefault(segment, []).append((path, json_path, carrier, payload))
    return grouped


def typed_id_payload_branch_rows(
    lint: Lint,
) -> list[tuple[Path, str, str, str, str, bool]]:
    """Return every swept typed-ID payload branch as one flat row.

    Each row is ``(document, json path, carrier regex, wire segment, payload
    regex, end anchored)``. ``patternProperties`` keys are swept exactly like
    ``pattern`` values, so a typed ID used as an object key is inside the same
    closure as a typed ID used as a value.
    """
    rows: list[tuple[Path, str, str, str, str, bool]] = []
    for path, document in typed_id_validation_documents(lint):
        for json_path, carrier in regex_carriers_in_document(document):
            for segment, payload, anchored in typed_id_anchored_payload_branches(carrier):
                rows.append((path, json_path, carrier, segment, payload, anchored))
    return rows


WIRE_FORM_PLACEHOLDER_RE = re.compile(r"<[^>]*>")
REGEX_GROUP_FLAG_RE = re.compile(r"\(\?[:=!]|\(\?<[=!]")


def wire_form_payload_template(wire_form: object) -> str | None:
    """Return the payload template a registry ``wire_form`` declares after its prefix."""
    if not isinstance(wire_form, str):
        return None
    match = TYPED_ID_WIRE_PREFIX_RE.match(wire_form)
    if match is None:
        return None
    return wire_form[match.end():]


def wire_form_payload_segments(template: str) -> int:
    """Count the ``:``-separated payload segments a registry wire form declares."""
    return WIRE_FORM_PLACEHOLDER_RE.sub("", template).count(":") + 1


def regex_payload_segments(payload: str) -> int:
    """Count the ``:``-separated segments one payload regex can ever produce.

    A colon inside a character class, an escape, a bounded quantifier or a group
    flag such as ``(?:`` belongs to the surrounding segment, so it is skipped.
    Quantified and alternated groups are copied verbatim by the branch expander,
    so a colon inside one is counted even when a concrete value could omit it.
    The count is therefore permissive by construction: it can only let a payload
    through, never fail a canonical one that really carries the declared
    separators.
    """
    segments = 1
    index = 0
    while index < len(payload):
        flag = REGEX_GROUP_FLAG_RE.match(payload, index)
        if flag is not None:
            index = flag.end()
            continue
        char = payload[index]
        if char == "\\":
            index += 2
            continue
        if char == "[":
            index = _regex_skip_class(payload, index)
            continue
        if char == "{":
            end = payload.find("}", index)
            index = len(payload) if end < 0 else end + 1
            continue
        if char == ":":
            segments += 1
        index += 1
    return segments


PayloadCharset = tuple[bool, frozenset[str]]

UNIVERSAL_PAYLOAD_CHARSET: PayloadCharset = (True, frozenset())
EMPTY_PAYLOAD_CHARSET: PayloadCharset = (False, frozenset())
REGEX_DIGIT_CHARS = frozenset("0123456789")
REGEX_WORD_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"
)
REGEX_WHITESPACE_CHARS = frozenset(" \t\n\r\f\v")
REGEX_CLASS_RANGE_LIMIT = 256
DIGEST_SUITE_WIRE_PLACEHOLDER = "<digest-suite>:"


def payload_charset_union(left: PayloadCharset, right: PayloadCharset) -> PayloadCharset:
    """Return the characters either side can produce.

    A charset is ``(True, excluded)`` for a negated class and ``(False, members)``
    otherwise, so a negated class stays exact instead of collapsing to "anything".
    """
    left_negated, left_members = left
    right_negated, right_members = right
    if left_negated and right_negated:
        return (True, left_members & right_members)
    if left_negated:
        return (True, left_members - right_members)
    if right_negated:
        return (True, right_members - left_members)
    return (False, left_members | right_members)


def payload_charset_contains(outer: PayloadCharset, inner: PayloadCharset) -> bool:
    """Return True when every character ``inner`` admits is inside ``outer``."""
    outer_negated, outer_members = outer
    inner_negated, inner_members = inner
    if outer_negated and inner_negated:
        return outer_members <= inner_members
    if outer_negated:
        return not (inner_members & outer_members)
    if inner_negated:
        return False
    return inner_members <= outer_members


def _regex_escape_charset(escaped: str) -> PayloadCharset:
    if escaped == "d":
        return (False, REGEX_DIGIT_CHARS)
    if escaped == "D":
        return (True, REGEX_DIGIT_CHARS)
    if escaped == "w":
        return (False, REGEX_WORD_CHARS)
    if escaped == "W":
        return (True, REGEX_WORD_CHARS)
    if escaped == "s":
        return (False, REGEX_WHITESPACE_CHARS)
    if escaped == "S":
        return (True, REGEX_WHITESPACE_CHARS)
    if escaped == "n":
        return (False, frozenset("\n"))
    if escaped == "r":
        return (False, frozenset("\r"))
    if escaped == "t":
        return (False, frozenset("\t"))
    if escaped.isalnum():
        # An unrecognised alphanumeric escape is a class this reader cannot
        # bound, so it widens to everything rather than silently narrowing.
        return UNIVERSAL_PAYLOAD_CHARSET
    return (False, frozenset(escaped))


def _regex_class_member(body: str, index: int) -> tuple[PayloadCharset, str | None, int]:
    """Read one character-class member as ``(charset, literal char, next index)``."""
    if body[index] == "\\" and index + 1 < len(body):
        escaped = body[index + 1]
        charset = _regex_escape_charset(escaped)
        literal = escaped if charset == (False, frozenset(escaped)) else None
        return charset, literal, index + 2
    return (False, frozenset(body[index])), body[index], index + 1


def _regex_class_charset(pattern: str, index: int) -> tuple[PayloadCharset, int]:
    end = _regex_skip_class(pattern, index)
    body = pattern[index + 1 : max(end - 1, index + 1)]
    negated = body.startswith("^")
    if negated:
        body = body[1:]
    charset = EMPTY_PAYLOAD_CHARSET
    cursor = 0
    while cursor < len(body):
        low, low_char, after_low = _regex_class_member(body, cursor)
        if low_char is not None and after_low < len(body) - 1 and body[after_low] == "-":
            high, high_char, after_high = _regex_class_member(body, after_low + 1)
            if high_char is not None:
                span = ord(high_char) - ord(low_char)
                if 0 <= span <= REGEX_CLASS_RANGE_LIMIT:
                    charset = payload_charset_union(
                        charset,
                        (
                            False,
                            frozenset(
                                chr(code)
                                for code in range(ord(low_char), ord(high_char) + 1)
                            ),
                        ),
                    )
                else:
                    charset = payload_charset_union(charset, UNIVERSAL_PAYLOAD_CHARSET)
                cursor = after_high
                continue
            charset = payload_charset_union(charset, high)
        charset = payload_charset_union(charset, low)
        cursor = after_low
    if negated:
        member_negated, members = charset
        charset = UNIVERSAL_PAYLOAD_CHARSET if member_negated else (True, members)
    return charset, end


def regex_payload_charset(payload: str) -> PayloadCharset:
    """Return every character one payload regex can place on the wire.

    Group syntax, alternation bars, quantifiers and anchors describe structure,
    not content, so only classes, escapes, wildcards and literal characters
    contribute. The reader over-approximates on anything it cannot bound, which
    can only make a carrier look wider than it is — never narrower.
    """
    charset = EMPTY_PAYLOAD_CHARSET
    index = 0
    while index < len(payload):
        flag = REGEX_GROUP_FLAG_RE.match(payload, index)
        if flag is not None:
            index = flag.end()
            continue
        char = payload[index]
        if char == "\\":
            if index + 1 >= len(payload):
                return UNIVERSAL_PAYLOAD_CHARSET
            charset = payload_charset_union(
                charset, _regex_escape_charset(payload[index + 1])
            )
            index += 2
            continue
        if char == "[":
            member, index = _regex_class_charset(payload, index)
            charset = payload_charset_union(charset, member)
            continue
        if char == "{":
            end = payload.find("}", index)
            index = len(payload) if end < 0 else end + 1
            continue
        if char == ".":
            charset = payload_charset_union(charset, UNIVERSAL_PAYLOAD_CHARSET)
            index += 1
            continue
        if char in "()|*+?^$":
            index += 1
            continue
        charset = payload_charset_union(charset, (False, frozenset(char)))
        index += 1
    return charset


def active_digest_suite_payload_regex(lint: Lint) -> str | None:
    """Return the payload regex the active digest suites spell, or None on error.

    A ``<digest-suite>`` wire form is only as closed as the suite vocabulary it
    points at, so the regex is derived from ``digest-suite-registry.json`` rather
    than restated. Activating or retiring a suite then moves the typed-ID gate
    with it instead of leaving the two registries to drift.
    """
    path = ARTIFACTS / "registry" / "digest-suite-registry.json"
    registry = load_json(lint, path)
    if not isinstance(registry, dict):
        return None
    suites = registry.get("suites")
    if not isinstance(suites, list):
        lint.fail(path, "suites must be an array of registered digest suites")
        return None
    canonical_ids: list[str] = []
    digest_lengths: set[int] = set()
    for row in suites:
        if not isinstance(row, dict) or row.get("status") != "active":
            continue
        canonical_id = row.get("canonical_id")
        digest_length = row.get("digest_length_bytes")
        if not isinstance(canonical_id, str) or not isinstance(digest_length, int):
            lint.fail(
                path,
                "an active suite row MUST declare canonical_id and digest_length_bytes",
            )
            return None
        canonical_ids.append(canonical_id)
        digest_lengths.add(digest_length)
    if not canonical_ids or len(digest_lengths) != 1:
        lint.fail(
            path,
            "active digest suites MUST exist and MUST share one digest_length_bytes "
            "so a <digest-suite> typed ID has a single payload length",
        )
        return None
    return f"(?:{'|'.join(canonical_ids)}):[0-9a-f]{{{2 * digest_lengths.pop()}}}"


def registry_special_form_payload_contracts(
    lint: Lint, registry: dict[str, Any], path: Path
) -> dict[str, tuple[str, int]]:
    """Return ``kind -> (payload regex, minimum payload segments)`` per special form.

    ``wire_form`` is a human-readable template whose placeholders declare no value
    space at all, which is why a special-form carrier could ship any alphabet it
    liked. ``payload_pattern`` is that value space, and this reader also holds the
    registry to its own two statements: the regex MUST carry at least the
    separators ``wire_form`` declares, and a ``<digest-suite>`` template MUST
    spell exactly the active suites of ``digest-suite-registry.json``.
    """
    contracts: dict[str, tuple[str, int]] = {}
    digest_suite_payload = active_digest_suite_payload_regex(lint)
    for row in registry.get("special_forms") or []:
        if not isinstance(row, dict) or not isinstance(row.get("kind"), str):
            continue
        kind = row["kind"]
        template = wire_form_payload_template(row.get("wire_form"))
        if template is None:
            lint.fail(path, f"special_forms[{kind}].wire_form must carry an ak:<kind>: prefix")
            continue
        payload_pattern = row.get("payload_pattern")
        if not isinstance(payload_pattern, str) or not payload_pattern:
            lint.fail(
                path,
                f"special_forms[{kind}] must declare payload_pattern, the "
                f"machine-readable value space of everything after ak:{kind}:",
            )
            continue
        required_segments = wire_form_payload_segments(template)
        if regex_payload_segments(payload_pattern) < required_segments:
            lint.fail(
                path,
                f"special_forms[{kind}].payload_pattern {payload_pattern!r} carries "
                f"fewer ':' segments than wire_form {row.get('wire_form')!r}; the two "
                "MUST declare one value space",
            )
            continue
        if (
            template.startswith(DIGEST_SUITE_WIRE_PLACEHOLDER)
            and digest_suite_payload is not None
            and payload_pattern != digest_suite_payload
        ):
            lint.fail(
                path,
                f"special_forms[{kind}].payload_pattern is {payload_pattern!r}; a "
                "<digest-suite> wire form MUST spell the active suites registered in "
                f"digest-suite-registry.json, {digest_suite_payload!r}",
            )
            continue
        contracts[kind] = (payload_pattern, required_segments)
    return contracts


def registry_canonical_payload_regex(lint: Lint, registry: dict[str, Any], path: Path) -> dict[str, str]:
    """Return the canonical payload regex per ``id_form``, read from the registry.

    The regexes are the registry's own ``event_token_pattern`` and
    ``uuid_pattern_producer_allocated``. Reading them here instead of restating
    them keeps the gate from drifting away from the artifact it enforces; the
    module constants are held to the same registry text.
    """
    canonical: dict[str, str] = {}
    declared = {
        "event_derived": ("event_token_pattern", EVENT_TOKEN_PAYLOAD_REGEX),
        "suite_tagged_full_digest": ("event_token_pattern", EVENT_TOKEN_PAYLOAD_REGEX),
        "producer_allocated": (
            "uuid_pattern_producer_allocated",
            PRODUCER_UUID_PAYLOAD_REGEX,
        ),
    }
    for id_form, (field, constant) in declared.items():
        pattern = registry.get(field)
        if not isinstance(pattern, str):
            lint.fail(path, f"{field} must be a string payload regex")
            continue
        if pattern != f"^{constant}$":
            lint.fail(
                path,
                f"{field} is {pattern!r}; the typed-ID closure enforces "
                f"{f'^{constant}$'!r} and the two MUST stay one value",
            )
            continue
        canonical[id_form] = constant
    return canonical


def check_typed_id_payload_form_closure(lint: Lint) -> None:
    """Close every typed-ID payload branch against the registered wire form.

    ``check_id_form_wire_schema_alignment`` proves only that some branch spells
    the canonical payload and that no branch inverts the id_form. A payload that
    is neither canonical nor inverted — a bare prefix anchor, a character class
    missing the canonical alphabet's uppercase or ``_``, a class wide enough to
    admit unregistered text, or a length the registry never declared — escaped
    both directions and still shipped. Every branch is held to the registry here:

    * a registered ``id_kinds`` payload MUST start with that ``id_form``'s
      canonical payload regex, so a composite carrier such as an OR-Set dot keeps
      its suffix while its leading token stays canonical;
    * a registered ``special_forms`` payload MUST carry at least the separator
      segments its ``wire_form`` declares AND MUST stay inside the alphabet its
      ``payload_pattern`` registers, so a carrier may be narrower than the
      registered value space for one field but can never admit an octet the
      registry rejects;
    * every branch MUST terminate, because an unanchored branch leaves the whole
      tail of the value unconstrained.
    """
    registry_path = ARTIFACTS / "registry" / "id-kind-registry.json"
    registry = load_json(lint, registry_path)
    if not isinstance(registry, dict):
        return
    prefixes, registry_errors = registered_typed_id_wire_prefixes(registry)
    for message in registry_errors:
        lint.fail(registry_path, message)
    canonical = registry_canonical_payload_regex(lint, registry, registry_path)
    id_forms: dict[str, str] = {}
    for row in registry.get("id_kinds") or []:
        if isinstance(row, dict) and isinstance(row.get("kind"), str):
            id_form = row.get("id_form")
            if isinstance(id_form, str):
                id_forms[row["kind"]] = id_form
    contracts = registry_special_form_payload_contracts(lint, registry, registry_path)
    special_charsets = {
        kind: regex_payload_charset(payload_pattern)
        for kind, (payload_pattern, _segments) in contracts.items()
    }

    for path, json_path, carrier, segment, payload, anchored in typed_id_payload_branch_rows(lint):
        kind = prefixes.get(f"ak:{segment}:")
        if kind is None:
            # check_typed_id_prefix_registry_closure owns unregistered prefixes.
            continue
        accepted: list[str] = []
        canonical_payload = canonical.get(id_forms.get(kind, ""))
        if canonical_payload is not None:
            accepted.append(f"ak:{kind}:{canonical_payload}")
        contract = contracts.get(kind)
        if contract is not None:
            accepted.append(f"ak:{kind}:{contract[0]}")
        if not accepted:
            continue
        if not anchored:
            lint.fail(
                path,
                f"{json_path} validates ak:{segment} with an unterminated payload "
                f"{payload!r} (carrier {carrier!r}); a typed-ID branch MUST end-anchor "
                f"so the registered wire form {' or '.join(accepted)} is the whole value",
            )
            continue
        if canonical_payload is not None and payload.startswith(canonical_payload):
            continue
        if (
            contract is not None
            and payload
            and regex_payload_segments(payload) >= contract[1]
            and payload_charset_contains(
                special_charsets[kind], regex_payload_charset(payload)
            )
        ):
            continue
        lint.fail(
            path,
            f"{json_path} validates ak:{segment} with payload {payload!r} "
            f"(carrier {carrier!r}); it is wider than or disjoint from the registered "
            f"wire form {' or '.join(accepted)}",
        )


def check_typed_id_carrier_sweep_closure(lint: Lint) -> None:
    """Require every cross-document ``$ref`` to land inside the swept carrier set.

    The typed-ID gates only bind what they read. A reference to a document
    outside ``artifacts/schemas`` and ``artifacts/openapi`` would move wire
    validation out of both closures without any gate noticing, which is exactly
    how the OpenAPI mirror drifted before it was swept.
    """
    documents = typed_id_validation_documents(lint)
    swept = {path.resolve() for path, _ in documents}
    for path, document in documents:
        if not isinstance(document, dict):
            continue
        for json_path, value, key in walk_json(document):
            if key != "$ref" or not isinstance(value, str):
                continue
            target = value.split("#", 1)[0]
            if not target:
                continue
            if (path.parent / target).resolve() in swept:
                continue
            lint.fail(
                path,
                f"{json_path} references {value!r}, a document outside the typed ID "
                "carrier sweep; typed ID validation must stay inside "
                "artifacts/schemas and artifacts/openapi",
            )


def check_typed_id_prefix_registry_closure(lint: Lint) -> None:
    """Close schema -> registry: every literal ak:<segment>: MUST be registered.

    ``check_id_form_wire_schema_alignment`` walks registry -> schema and only
    proves that a registered kind has some matching regex. Nothing stopped a
    schema from minting an unregistered prefix, which is exactly the failure the
    fail-closed parser rule in encoding.md forbids on the wire.
    """
    registry_path = ARTIFACTS / "registry" / "id-kind-registry.json"
    registry = load_json(lint, registry_path)
    prefixes, registry_errors = registered_typed_id_wire_prefixes(registry)
    for message in registry_errors:
        lint.fail(registry_path, message)
    if not prefixes:
        lint.fail(registry_path, "no canonical typed ID wire prefixes could be parsed")
        return
    for path, json_path, carrier, found in schema_typed_id_prefix_carriers(lint):
        for prefix in sorted(found):
            if prefix in prefixes:
                continue
            lint.fail(
                path,
                f"{json_path} accepts unregistered typed ID prefix {prefix!r} "
                f"(carrier {carrier!r}); register it in "
                "contract-registry.json#/id_kind_registry or drop the ak: prefix",
            )


FIXTURE_TYPED_ID_EXEMPTION_PATH = ROOT / "tools" / "fixture-typed-id-exemption-registry.json"
FIXTURE_TYPED_ID_POSITIONS = ("value", "object_key", "embedded_json_string")
TYPED_ID_VALUE_RE = re.compile(r"ak:([A-Za-z0-9_-]+):")
EMBEDDED_JSON_STRING_RE = re.compile(r'"(ak:[A-Za-z0-9_-]+:[^"\\]*)"')


def json_pointer_token(token: str) -> str:
    """Escape one object member name into an RFC 6901 pointer token."""
    return token.replace("~", "~0").replace("/", "~1")


def typed_id_value_occurrences(
    text: str, pointer: str, position: str
) -> list[tuple[str, str, str, str, str]]:
    """Return every concrete typed ID one fixture string ships.

    A schema carries regexes, so the schema-side closures compare value spaces.
    A fixture carries the bytes themselves, so the comparison has to run per
    value. Three positions carry a value and nothing else does:

    * the whole string is the identifier;
    * an object member name is the identifier, which is how cell and Realm maps
      are keyed;
    * a JSON string literal embedded in a longer string. That is canonical JSON
      inside a digest preimage -- ``or_set_batch_add`` hashes
      ``tag_context || 0x0A || dot || 0x0A || canonical_json(value)`` -- so the
      quoted run is a shipped value exactly like a standalone one.

    Prose that merely names a prefix is not a value and never enters this list:
    a prefix with an empty payload (``"ak:event:"`` as a concatenation operand,
    or ``ak:signal:`` listed as a surface that MUST stay unminted) declares no
    identifier, and an unquoted mention inside a sentence or a regex is
    structure rather than content.

    Each row is ``(pointer, position, wire segment, payload, value)``.
    """
    rows: list[tuple[str, str, str, str, str]] = []
    match = TYPED_ID_VALUE_RE.match(text)
    if match is not None:
        payload = text[match.end():]
        if payload:
            rows.append((pointer, position, match.group(1), payload, text))
        return rows
    for embedded in EMBEDDED_JSON_STRING_RE.finditer(text):
        literal = embedded.group(1)
        inner = TYPED_ID_VALUE_RE.match(literal)
        if inner is None:
            continue
        payload = literal[inner.end():]
        if payload:
            rows.append(
                (pointer, "embedded_json_string", inner.group(1), payload, literal)
            )
    return rows


def typed_id_fixture_value_rows(document: Any) -> list[tuple[str, str, str, str, str]]:
    """Walk one fixture document for every concrete typed-ID value it ships."""
    rows: list[tuple[str, str, str, str, str]] = []

    def visit(node: Any, pointer: str) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                child_pointer = f"{pointer}/{json_pointer_token(key)}"
                rows.extend(typed_id_value_occurrences(key, child_pointer, "object_key"))
                visit(child, child_pointer)
        elif isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, f"{pointer}/{index}")
        elif isinstance(node, str):
            rows.extend(typed_id_value_occurrences(node, pointer, "value"))

    visit(document, "")
    return rows


def typed_id_value_documents(lint: Lint) -> list[tuple[Path, Any]]:
    """Return every shipped conformance fixture that can carry a typed-ID value.

    ``typed_id_validation_documents`` is the schema-side member list of the same
    contract. Fixtures were outside it because they validate nothing; they
    publish values instead, which is why they need their own document list and
    their own per-value comparison.
    """
    documents: list[tuple[Path, Any]] = []
    for fixture_path in sorted((ARTIFACTS / "fixtures").glob("*.json")):
        documents.append((fixture_path, load_json(lint, fixture_path)))
    return documents


def registered_typed_id_value_forms(
    lint: Lint, registry: dict[str, Any], registry_path: Path
) -> dict[str, list[str]]:
    """Return ``wire segment -> accepted payload regexes`` for concrete values.

    The accepted space is assembled from the same two sources the payload-form
    closure reads, so a fixture can never be held to a different contract than a
    schema:

    * the registry's own ``event_token_pattern`` /
      ``uuid_pattern_producer_allocated`` per ``id_kinds`` row, and
      ``special_forms[].payload_pattern`` per special form;
    * every end-anchored typed-ID branch already swept out of
      ``artifacts/schemas`` and ``artifacts/openapi``.

    The second source is what admits a registered composite such as the OR-Set
    dot ``ak:event:<event_id>:<write_index>``: that shape is a shipped carrier
    which ``check_typed_id_payload_form_closure`` already proves stays inside the
    registered value space, so reading it here adds no acceptance the registry
    has not already closed over, and it keeps the gate from restating a wire form
    the artifacts own.
    """
    forms: dict[str, list[str]] = {}
    canonical = registry_canonical_payload_regex(lint, registry, registry_path)
    contracts = registry_special_form_payload_contracts(lint, registry, registry_path)
    for row in registry.get("id_kinds") or []:
        if not isinstance(row, dict):
            continue
        prefix = typed_id_wire_prefix(row.get("wire_form"))
        payload = canonical.get(row.get("id_form"))
        if prefix is not None and payload:
            forms.setdefault(prefix[3:-1], []).append(payload)
    for row in registry.get("special_forms") or []:
        if not isinstance(row, dict):
            continue
        prefix = typed_id_wire_prefix(row.get("wire_form"))
        contract = contracts.get(row.get("kind"))
        if prefix is not None and contract is not None:
            forms.setdefault(prefix[3:-1], []).append(contract[0])
    for _path, _json_path, _carrier, segment, payload, anchored in typed_id_payload_branch_rows(lint):
        if anchored and payload:
            forms.setdefault(segment, []).append(payload)
    return {segment: list(dict.fromkeys(patterns)) for segment, patterns in forms.items()}


def payload_matches_registered_form(payload: str, patterns: list[str]) -> bool:
    """True when one concrete payload is spelled by a registered value space."""
    for pattern in patterns:
        try:
            if re.fullmatch(pattern, payload) is not None:
                return True
        except re.error:
            continue
    return False


def fixture_typed_id_exemptions(lint: Lint) -> dict[tuple[str, str, str], str]:
    """Load the closed exact-path exemption registry for fixture typed-ID values.

    A conformance fixture legitimately ships a few strings that carry a typed-ID
    prefix and MUST NOT be a registered wire form: a negative vector whose whole
    point is that the value is rejected, and a documented wire-form template.
    Neither can be recognised from a field name -- ``negative_cases``,
    ``reject_*`` and ``invalid_*`` are authoring conventions, not a contract, and
    a gate that trusted them would let any future value opt out by renaming its
    key. So the exemption is declared here instead, pinned to the exact JSON
    pointer, the exact carrier position and the exact value, with the reason
    recorded. Changing the value ends the exemption, and an entry that no longer
    matches a failing occurrence is reported as stale.
    """
    registry = load_json(lint, FIXTURE_TYPED_ID_EXEMPTION_PATH)
    exemptions: dict[tuple[str, str, str], str] = {}
    if not isinstance(registry, dict):
        return exemptions
    categories = registry.get("categories")
    if not isinstance(categories, dict) or not categories:
        lint.fail(FIXTURE_TYPED_ID_EXEMPTION_PATH, "categories must be a non-empty object")
        return exemptions
    rows = registry.get("entries")
    if not isinstance(rows, list):
        lint.fail(FIXTURE_TYPED_ID_EXEMPTION_PATH, "entries must be an array")
        return exemptions
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            lint.fail(FIXTURE_TYPED_ID_EXEMPTION_PATH, f"entries[{index}] must be an object")
            continue
        unknown = set(row) - {"pointer", "position", "value", "category", "reason"}
        if unknown:
            lint.fail(
                FIXTURE_TYPED_ID_EXEMPTION_PATH,
                f"entries[{index}] has unknown member(s) {sorted(unknown)}",
            )
        pointer = row.get("pointer")
        position = row.get("position")
        value = row.get("value")
        category = row.get("category")
        reason = row.get("reason")
        if not isinstance(pointer, str) or "#" not in pointer:
            lint.fail(
                FIXTURE_TYPED_ID_EXEMPTION_PATH,
                f"entries[{index}].pointer must be <fixture file>#<json pointer>",
            )
            continue
        fixture_name = pointer.split("#", 1)[0]
        if not (ARTIFACTS / "fixtures" / fixture_name).is_file():
            lint.fail(
                FIXTURE_TYPED_ID_EXEMPTION_PATH,
                f"{pointer}: names a file that is not a shipped fixture",
            )
            continue
        if position not in FIXTURE_TYPED_ID_POSITIONS:
            lint.fail(
                FIXTURE_TYPED_ID_EXEMPTION_PATH,
                f"{pointer}: position must be one of {sorted(FIXTURE_TYPED_ID_POSITIONS)}",
            )
            continue
        if not isinstance(value, str) or not value:
            lint.fail(
                FIXTURE_TYPED_ID_EXEMPTION_PATH,
                f"{pointer}: value must pin the exact exempted string",
            )
            continue
        if category not in categories:
            lint.fail(FIXTURE_TYPED_ID_EXEMPTION_PATH, f"{pointer}: unknown category {category!r}")
        if not isinstance(reason, str) or not reason.strip():
            lint.fail(FIXTURE_TYPED_ID_EXEMPTION_PATH, f"{pointer}: reason must be a non-empty string")
        key = (pointer, position, value)
        if key in exemptions:
            lint.fail(FIXTURE_TYPED_ID_EXEMPTION_PATH, f"duplicate exemption for {pointer}")
        exemptions[key] = pointer
    return exemptions


def check_typed_id_fixture_value_closure(lint: Lint) -> None:
    """Close conformance fixtures over the registered typed-ID wire forms.

    All three earlier typed-ID closures read ``typed_id_validation_documents``,
    which sweeps ``artifacts/schemas`` and ``artifacts/openapi`` only. A fixture
    validates nothing, so it was inside no closure at all -- and a shipped
    positive KAT is exactly where an unregistered wire form does the most damage:
    implementations align to the vector byte for byte, and any digest computed
    over the value freezes the wrong bytes into a published expectation.

    A fixture carries values rather than regexes, so this gate compares per
    value instead of per value space. Every concrete typed ID a fixture ships
    MUST carry a registered prefix and MUST be spelled by a registered form for
    that prefix, unless the exact path is registered in
    ``tools/fixture-typed-id-exemption-registry.json``.
    """
    registry_path = ARTIFACTS / "registry" / "id-kind-registry.json"
    registry = load_json(lint, registry_path)
    if not isinstance(registry, dict):
        return
    prefixes, registry_errors = registered_typed_id_wire_prefixes(registry)
    for message in registry_errors:
        lint.fail(registry_path, message)
    if not prefixes:
        lint.fail(registry_path, "no canonical typed ID wire prefixes could be parsed")
        return
    forms = registered_typed_id_value_forms(lint, registry, registry_path)
    exemptions = fixture_typed_id_exemptions(lint)
    used: set[tuple[str, str, str]] = set()

    for path, document in typed_id_value_documents(lint):
        if document is None:
            continue
        for pointer, position, segment, payload, value in typed_id_fixture_value_rows(document):
            absolute = f"{path.name}#{pointer}"
            key = (absolute, position, value)
            # An entry stays live while the fixture still ships that exact value
            # at that exact pointer, whichever gate the value is exempted from:
            # the same registry now also pins deliberate negative vectors for
            # the digest-suite wire-code gate, which fires in the fixture pass.
            if key in exemptions:
                used.add(key)
            if f"ak:{segment}:" not in prefixes:
                if key in exemptions:
                    used.add(key)
                    continue
                lint.fail(
                    path,
                    f"{pointer} ships unregistered typed ID prefix 'ak:{segment}:' "
                    f"(value {value!r}); register it in "
                    "contract-registry.json#/id_kind_registry or drop the ak: prefix",
                )
                continue
            if payload_matches_registered_form(payload, forms.get(segment, [])):
                continue
            if key in exemptions:
                used.add(key)
                continue
            lint.fail(
                path,
                f"{pointer} ships ak:{segment} value {value!r}; it is not any wire form "
                "registered for that prefix, and a conformance vector MUST NOT publish a "
                "typed ID the registry never declared. Correct the value, or register the "
                "exact path in tools/fixture-typed-id-exemption-registry.json",
            )

    for key in sorted(set(exemptions) - used):
        lint.fail(
            FIXTURE_TYPED_ID_EXEMPTION_PATH,
            f"stale fixture typed ID exemption: {key[0]} ({key[1]}) no longer carries "
            f"{key[2]!r} or no longer needs an exemption",
        )


EVENT_KIND_VERB_FORMS = ("base", "past_participle", "not_applicable")
VERB_FORM_PROSE_ANCHOR = "verb_form"
VERB_FORM_PROSE_PATH = SPEC_ROOT / "zh" / "models" / "common-fields.md"


def prose_past_participle_event_kinds(text: str) -> tuple[set[str], list[str]]:
    """Parse the readable past-participle exception table into a per-kind set."""
    errors: list[str] = []
    kinds: set[str] = set()
    lines = text.splitlines()
    anchor = None
    for index, line in enumerate(lines):
        if VERB_FORM_PROSE_ANCHOR in line and "past_participle" in line:
            anchor = index
            break
    if anchor is None:
        return kinds, ["no verb_form registration paragraph found"]
    started = False
    for line in lines[anchor + 1:]:
        stripped = line.strip()
        if not stripped:
            if started:
                break
            continue
        if not stripped.startswith("|"):
            if started:
                break
            continue
        started = True
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        if first in {"kind", ""} or set(first) <= {"-", ":", " "}:
            continue
        if not (first.startswith("`") and first.endswith("`")):
            errors.append(f"past-participle table row {first!r} must name one kind in backticks")
            continue
        kind = first.strip("`")
        if "/" in kind or " " in kind:
            errors.append(
                f"past-participle table row {kind!r} merges several kinds; use one kind per row"
            )
            continue
        if kind in kinds:
            errors.append(f"past-participle table lists {kind!r} twice")
        kinds.add(kind)
    if not started:
        errors.append("verb_form registration paragraph is not followed by a table")
    return kinds, errors


def event_kind_verb_form_errors(rows: object) -> list[str]:
    """Validate the terminal-segment classification carried by event_kind rows."""
    errors: list[str] = []
    if not isinstance(rows, list):
        return ["event_kinds must be an array"]
    for row in rows:
        if not isinstance(row, dict):
            errors.append("event_kinds rows must be objects")
            continue
        event_kind = row.get("event_kind")
        if not isinstance(event_kind, str) or not event_kind:
            errors.append("event_kinds row has a missing or non-string event_kind")
            continue
        if row.get("status") != "active":
            continue
        verb_form = row.get("verb_form")
        rationale = row.get("verb_form_rationale")
        if verb_form not in EVENT_KIND_VERB_FORMS:
            errors.append(
                f"{event_kind} must declare verb_form as one of "
                f"{list(EVENT_KIND_VERB_FORMS)}, found {verb_form!r}"
            )
            continue
        if verb_form == "past_participle":
            if not isinstance(rationale, str) or not rationale.strip():
                errors.append(
                    f"{event_kind} declares verb_form=past_participle without a non-empty "
                    "verb_form_rationale"
                )
        elif rationale is not None:
            errors.append(
                f"{event_kind} declares verb_form={verb_form} and MUST NOT carry a "
                "verb_form_rationale"
            )
    return errors


def check_event_kind_verb_form_registration(lint: Lint) -> None:
    """Close the terminal-segment classification across truth source, view and prose.

    An English suffix scan cannot decide this: ``bound`` and ``withheld`` are
    irregular past participles, so the registration is the only complete record
    and the readable table MUST close against it in both directions.
    """
    contract_path = ARTIFACTS / "registry" / "contract-registry.json"
    generated_path = ARTIFACTS / "registry" / "event-kind-registry.json"
    contract = load_json(lint, contract_path)
    generated = load_json(lint, generated_path)
    section = contract.get("event_kind_registry") if isinstance(contract, dict) else None
    source_rows = section.get("event_kinds") if isinstance(section, dict) else None
    for message in event_kind_verb_form_errors(source_rows):
        lint.fail(contract_path, message)
    if not isinstance(source_rows, list):
        return

    generated_rows = generated.get("event_kinds") if isinstance(generated, dict) else None
    if not isinstance(generated_rows, list):
        lint.fail(generated_path, "event_kinds must be an array")
        return
    source_map = {
        row.get("event_kind"): (row.get("verb_form"), row.get("verb_form_rationale"))
        for row in source_rows
        if isinstance(row, dict)
    }
    generated_map = {
        row.get("event_kind"): (row.get("verb_form"), row.get("verb_form_rationale"))
        for row in generated_rows
        if isinstance(row, dict)
    }
    if source_map != generated_map:
        for event_kind in sorted(set(source_map) | set(generated_map), key=str):
            if source_map.get(event_kind) != generated_map.get(event_kind):
                lint.fail(
                    generated_path,
                    f"generated verb_form registration for {event_kind!r} drifted from "
                    "contract-registry.json (run python tools/artifact_pipeline.py generate)",
                )

    registered = {
        row.get("event_kind")
        for row in source_rows
        if isinstance(row, dict)
        and row.get("status") == "active"
        and row.get("verb_form") == "past_participle"
    }
    prose_kinds, prose_errors = prose_past_participle_event_kinds(
        read_text(VERB_FORM_PROSE_PATH)
    )
    for message in prose_errors:
        lint.fail(VERB_FORM_PROSE_PATH, message)
    for event_kind in sorted(registered - prose_kinds, key=str):
        lint.fail(
            VERB_FORM_PROSE_PATH,
            f"{event_kind} is registered as past_participle but missing from the readable table",
        )
    for event_kind in sorted(prose_kinds - registered, key=str):
        lint.fail(
            VERB_FORM_PROSE_PATH,
            f"{event_kind} is listed as a past-participle exception but is not registered "
            "with verb_form=past_participle",
        )



def check_text_files_utf8_no_nul(lint: Lint) -> None:
    """Reject binary-corrupted text contract files.

    NUL bytes in Markdown or machine artifacts are usually editor or merge
    corruption. They can render invisible in review but break site builds,
    artifact consumption, and generated SDK input.
    """
    for path in text_contract_files():
        raw = path.read_bytes()
        if b"\x00" in raw:
            lint.fail(path, "text contract file contains NUL byte(s)")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            lint.fail(path, f"text contract file is not valid UTF-8: {exc}")



SHARED_PROOF_LEAF = ("event-envelope.schema.json", "/$defs/proof")
PROOF_CONTEXT_ANNOTATION = "x-arkret-proof-context"
PROOF_CONTEXT_SET_ANNOTATION = "x-arkret-proof-contexts"
SIGNATURE_DOMAIN_ANNOTATION = "x-arkret-signature-domain"
SECURITY_DOMAIN_LABEL_PATTERN = r"ak\.[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*\.v1"
LEGACY_PROOF_CONTEXT_PATTERN = r"ak\.[a-z0-9-]+-proof-v1"
REPLAY_CACHE_NAMESPACE_PRIMITIVE = "replay_cache_namespace"
DOMAIN_SEPARATION_PRIMITIVES = frozenset(
    {
        "canonical_json_sha256",
        "merkle_leaf_sha256",
        "merkle_node_sha256",
        "merkle_root_sha256",
        "detached_signature",
        "http_message_signature",
        "hpke_info",
        REPLAY_CACHE_NAMESPACE_PRIMITIVE,
    }
)


def _proof_pointer_escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _proof_schema_documents(lint: Lint) -> dict[str, Any]:
    documents: dict[str, Any] = {}
    for schema_path in sorted((ARTIFACTS / "schemas").glob("*.json")):
        document = load_json(lint, schema_path)
        if isinstance(document, (dict, list)):
            documents[schema_path.name] = document
    return documents


def _proof_ref_edges(documents: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Every ``$ref`` edge between schema nodes as (file, node_pointer, target_file, target_pointer)."""
    edges: list[tuple[str, str, str, str]] = []

    def walk(file_name: str, node: Any, pointer: str) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                target, _, fragment = ref.partition("#")
                target_file = file_name if not target else target.split("/")[-1]
                if target_file in documents:
                    edges.append((file_name, pointer, target_file, fragment))
            for key, child in node.items():
                walk(file_name, child, f"{pointer}/{_proof_pointer_escape(key)}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(file_name, child, f"{pointer}/{index}")

    for file_name, document in documents.items():
        walk(file_name, document, "")
    return edges


def _shared_proof_use_points(documents: dict[str, Any]) -> list[tuple[str, str]]:
    """Terminal use points of the shared detached-proof leaf.

    A node is proof-carrying when its ``$ref`` chain terminates at
    ``event-envelope.schema.json#/$defs/proof``. Intermediate aliases such as
    ``high-risk-authority-proof.schema.json#/$defs/detached_proof`` are consumed by
    the nodes that reference them, so only unreferenced proof-carrying nodes are
    reported: those are the places where a detached proof actually lands in a wire
    object family and therefore need a registered context.
    """
    edges = _proof_ref_edges(documents)
    proof_nodes = {(file, pointer) for file, pointer, tf, tp in edges if (tf, tp) == SHARED_PROOF_LEAF}
    changed = True
    while changed:
        changed = False
        for file, pointer, target_file, target_pointer in edges:
            if (target_file, target_pointer) in proof_nodes and (file, pointer) not in proof_nodes:
                proof_nodes.add((file, pointer))
                changed = True
    referenced = {(target_file, target_pointer) for _, _, target_file, target_pointer in edges}
    return sorted(node for node in proof_nodes if node not in referenced)


def _resolve_proof_schema_ref(documents: dict[str, Any], schema_ref: str) -> tuple[str, str, Any]:
    """Resolve ``schemas/<file>.json#/<pointer>`` to (file, pointer, node-or-None)."""
    file_part, _, fragment = schema_ref.partition("#")
    file_name = file_part.split("/")[-1]
    document = documents.get(file_name)
    if document is None:
        return file_name, fragment, None
    if not fragment:
        return file_name, "", document
    try:
        node = resolve_json_pointer(document, "#" + fragment)
    except (KeyError, IndexError, ValueError):
        return file_name, fragment, None
    return file_name, fragment, node


def _proof_anchor_covers(anchor: tuple[str, str], file_name: str, pointer: str) -> bool:
    anchor_file, anchor_pointer = anchor
    if anchor_file != file_name:
        return False
    return anchor_pointer == "" or pointer == anchor_pointer or pointer.startswith(anchor_pointer + "/")


def _proof_annotation_at(documents: dict[str, Any], file_name: str, pointer: str) -> tuple[str, Any] | None:
    """Nearest proof-context annotation at the node or one of its ancestors."""
    parts = [part for part in pointer.split("/") if part != ""]
    while True:
        node_pointer = "".join(f"/{part}" for part in parts)
        _, _, node = _resolve_proof_schema_ref(documents, f"{file_name}#{node_pointer}")
        if isinstance(node, dict):
            if PROOF_CONTEXT_SET_ANNOTATION in node:
                return PROOF_CONTEXT_SET_ANNOTATION, node[PROOF_CONTEXT_SET_ANNOTATION]
            if PROOF_CONTEXT_ANNOTATION in node:
                return PROOF_CONTEXT_ANNOTATION, node[PROOF_CONTEXT_ANNOTATION]
        if not parts:
            return None
        parts.pop()


def _proof_annotated_nodes(document: Any) -> list[tuple[str, dict[str, Any]]]:
    """Every node carrying a proof-context annotation, keyed by JSON Pointer."""
    found: list[tuple[str, dict[str, Any]]] = []

    def walk(node: Any, pointer: str) -> None:
        if isinstance(node, dict):
            if PROOF_CONTEXT_ANNOTATION in node or PROOF_CONTEXT_SET_ANNOTATION in node:
                found.append((pointer, node))
            for key, child in node.items():
                walk(child, f"{pointer}/{_proof_pointer_escape(key)}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{pointer}/{index}")

    walk(document, "")
    return found


def _proof_transcript_property_names(
    documents: dict[str, Any], file_name: str, node: Any, depth: int = 0
) -> set[str]:
    """Collect explicitly declared transcript members through schema overlays.

    This is deliberately narrower than instance validation: it only answers whether
    a registered binding member has a declared schema source. Conditional branches
    contribute their properties, while ``if``/``not`` predicates do not.
    """
    if depth > 12 or not isinstance(node, dict):
        return set()
    names = set((node.get("properties") or {}).keys()) if isinstance(node.get("properties"), dict) else set()
    reference = node.get("$ref")
    if isinstance(reference, str):
        target, _, fragment = reference.partition("#")
        target_file = file_name if not target else target.split("/")[-1]
        target_document = documents.get(target_file)
        if target_document is not None:
            try:
                target_node = resolve_json_pointer(target_document, "#" + fragment) if fragment else target_document
            except (KeyError, IndexError, ValueError):
                target_node = None
            names.update(_proof_transcript_property_names(documents, target_file, target_node, depth + 1))
    for keyword in ("allOf", "oneOf", "anyOf"):
        for branch in node.get(keyword) or []:
            names.update(_proof_transcript_property_names(documents, file_name, branch, depth + 1))
    for keyword in ("then", "else"):
        names.update(_proof_transcript_property_names(documents, file_name, node.get(keyword), depth + 1))
    return names


def _check_domain_binding_schema_closure(
    lint: Lint,
    path: Path,
    documents: dict[str, Any],
    index: int,
    row: dict[str, Any],
) -> None:
    """Require every domain binding member to have a schema or explicit injected source."""
    refs: list[str] = []
    schema_ref = row.get("schema_ref")
    if isinstance(schema_ref, str):
        refs.append(schema_ref)
    transcript_refs = row.get("transcript_schema_refs")
    if transcript_refs is not None:
        if not isinstance(transcript_refs, list) or not transcript_refs or not all(
            isinstance(item, str) and item.startswith("schemas/") for item in transcript_refs
        ):
            lint.fail(path, f"domain_separations[{index}].transcript_schema_refs must be a non-empty schemas/* string array")
            return
        refs.extend(transcript_refs)
    if not refs:
        if "injected_fields" in row:
            lint.fail(path, f"domain_separations[{index}].injected_fields requires schema_ref or transcript_schema_refs")
        return

    schema_fields: set[str] = set()
    for ref in refs:
        file_name, _, node = _resolve_proof_schema_ref(documents, ref)
        if not isinstance(node, dict):
            lint.fail(path, f"domain_separations[{index}] transcript schema does not resolve: {ref}")
            return
        schema_fields.update(_proof_transcript_property_names(documents, file_name, node))

    fields = row.get("binding_fields")
    if not isinstance(fields, list) or not all(isinstance(item, str) for item in fields):
        return
    binding_fields = {item.removesuffix("?") for item in fields}
    injected = row.get("injected_fields", [])
    if not isinstance(injected, list):
        lint.fail(path, f"domain_separations[{index}].injected_fields must be an array of field/source objects")
        return
    injected_names: set[str] = set()
    for injection_index, entry in enumerate(injected):
        if (
            not isinstance(entry, dict)
            or set(entry) != {"field", "source"}
            or not isinstance(entry.get("field"), str)
            or not entry["field"]
            or not isinstance(entry.get("source"), str)
            or not entry["source"].strip()
        ):
            lint.fail(
                path,
                f"domain_separations[{index}].injected_fields[{injection_index}] must be exactly a non-empty field/source object",
            )
            continue
        if entry["field"] in injected_names:
            lint.fail(path, f"domain_separations[{index}].injected_fields duplicates {entry['field']!r}")
        injected_names.add(entry["field"])
    missing = binding_fields - schema_fields
    if injected_names != missing:
        undeclared = sorted(missing - injected_names)
        stale = sorted(injected_names - missing)
        if undeclared:
            lint.fail(
                path,
                f"domain_separations[{index}].binding_fields names {undeclared} outside its registered transcript schemas; declare injected_fields sources",
            )
        if stale:
            lint.fail(
                path,
                f"domain_separations[{index}].injected_fields names {stale} that are already schema fields or not binding fields",
            )


def _proof_top_def(pointer: str) -> str:
    """The ``/$defs/<name>`` entry a pointer lives under, or "" for a root-level node."""
    parts = [part for part in pointer.split("/") if part != ""]
    if len(parts) >= 2 and parts[0] == "$defs":
        return f"/$defs/{parts[1]}"
    return ""


def _proof_packed_leaf_holders(documents: dict[str, Any]) -> dict[tuple[str, str], list[str]]:
    """Top-level ``$defs`` entries that reach another entry's subtree only through ``$ref``.

    A DTO container can pass the closure while still packing dozens of object families
    behind one proof node: every family ``$ref``s the same ``#/$defs/proofs`` alias, so
    there is a single terminal use point and one fragmentless row covers it. The wire
    graph then cannot tell the families apart, which is exactly what domain separation
    is supposed to do. Counting the distinct holders of a use point's own ``$defs``
    entry makes that shape mechanically visible.
    """
    holders: dict[tuple[str, str], set[str]] = {}
    for source_file, source_pointer, target_file, target_pointer in _proof_ref_edges(documents):
        if source_file != target_file:
            continue
        owner = _proof_top_def(target_pointer)
        holder = _proof_top_def(source_pointer)
        if not owner or not holder or holder == owner:
            continue
        holders.setdefault((target_file, owner), set()).add(holder)
    return {key: sorted(value) for key, value in holders.items()}


def _proof_named_field_values(document: Any, key: str) -> list[tuple[str, Any]]:
    """Every value carried by a field with this exact name, keyed by JSON Pointer."""
    found: list[tuple[str, Any]] = []

    def walk(node: Any, pointer: str) -> None:
        if isinstance(node, dict):
            for name, child in node.items():
                child_pointer = f"{pointer}/{_proof_pointer_escape(name)}"
                if name == key:
                    found.append((child_pointer, child))
                walk(child, child_pointer)
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{pointer}/{index}")

    walk(document, "")
    return found


def check_proof_context_registry(lint: Lint) -> None:
    """Close the shared detached-proof surface in both directions.

    Forward: every terminal use point of ``event-envelope.schema.json#/$defs/proof``
    must resolve to exactly one most-specific registry row. Reverse: every row must
    resolve to a real schema node, and a row whose subtree only contains use points
    owned by deeper rows is over-broad and must be tightened to the inner object
    family it claims. A canonical token regex is a spelling check, never the closure.
    """
    path = ARTIFACTS / "registry" / "proof-context-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict) or data.get("source_of_truth") is not True:
        lint.fail(path, "proof context registry must be a source_of_truth object")
        return
    rows = data.get("contexts")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "proof context registry must contain non-empty contexts[]")
        return

    documents = _proof_schema_documents(lint)
    operation_registry = load_json(lint, ARTIFACTS / "registry" / "operation-registry.json")
    known_operations = {
        row.get("operation_id")
        for row in (operation_registry or {}).get("operations", [])
        if isinstance(row, dict)
    }

    contexts: set[str] = set()
    families: set[str] = set()
    anchors: dict[str, tuple[str, str]] = {}
    consumer_operations: dict[str, str] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            lint.fail(path, f"contexts[{index}] must be an object")
            continue
        context = row.get("context")
        family = row.get("object_family")
        fields = row.get("binding_fields")
        schema_ref = row.get("schema_ref")
        consumer_operation = row.get("consumer_operation")
        if not isinstance(context, str) or not re.fullmatch(SECURITY_DOMAIN_LABEL_PATTERN, context):
            lint.fail(path, f"contexts[{index}].context is not a canonical proof context")
            context = None
        elif context in contexts:
            lint.fail(path, f"duplicate proof context {context}")
            context = None
        else:
            contexts.add(context)
        if not isinstance(family, str) or not family:
            lint.fail(path, f"contexts[{index}].object_family must be a non-empty string")
        elif family in families:
            lint.fail(path, f"duplicate proof object_family {family}")
        else:
            families.add(family)
        if not isinstance(fields, list) or not fields or not all(isinstance(item, str) and item for item in fields):
            lint.fail(path, f"contexts[{index}].binding_fields must be a non-empty string array")
        if consumer_operation is not None:
            if not isinstance(consumer_operation, str) or consumer_operation not in known_operations:
                lint.fail(
                    path,
                    f"contexts[{index}].consumer_operation is not a registered operation: {consumer_operation!r}",
                )
            elif context is not None:
                consumer_operations[context] = consumer_operation
        if not isinstance(schema_ref, str) or not schema_ref.startswith("schemas/"):
            lint.fail(path, f"contexts[{index}].schema_ref must point into artifacts/schemas")
            continue
        file_name, fragment, node = _resolve_proof_schema_ref(documents, schema_ref)
        if file_name not in documents:
            lint.fail(path, f"contexts[{index}].schema_ref does not resolve: {schema_ref}")
            continue
        if node is None:
            lint.fail(
                path,
                f"contexts[{index}].schema_ref fragment does not resolve to a schema node: {schema_ref}",
            )
            continue
        if not isinstance(node, dict):
            lint.fail(path, f"contexts[{index}].schema_ref must resolve to a schema object: {schema_ref}")
            continue
        if SIGNATURE_DOMAIN_ANNOTATION in node:
            lint.fail(
                path,
                f"contexts[{index}].schema_ref resolves an explicitly local signature domain; "
                "local proof leaves belong in domain_separations[]",
            )
        if context is not None:
            anchors[context] = (file_name, fragment)

    use_points = _shared_proof_use_points(documents)
    packed_holders = _proof_packed_leaf_holders(documents)
    owned: dict[str, list[tuple[str, str]]] = {context: [] for context in anchors}
    for file_name, pointer in use_points:
        covering = [context for context, anchor in anchors.items() if _proof_anchor_covers(anchor, file_name, pointer)]
        if not covering:
            lint.fail(
                path,
                "shared detached-proof use point has no registered context: "
                f"schemas/{file_name}#{pointer}",
            )
            continue
        depth = max(len(anchors[context][1]) for context in covering)
        resolved = sorted(context for context in covering if len(anchors[context][1]) == depth)
        for context in resolved:
            owned[context].append((file_name, pointer))
        annotation = _proof_annotation_at(documents, file_name, pointer)
        if len(resolved) > 1:
            # One shared wire leaf with several consumer contexts: the schema node must
            # enumerate them and every row must name the consuming operation it belongs to.
            if annotation is None or annotation[0] != PROOF_CONTEXT_SET_ANNOTATION:
                lint.fail(
                    path,
                    f"schemas/{file_name}#{pointer} is claimed by {len(resolved)} contexts "
                    f"({', '.join(resolved)}) but the schema node carries no "
                    f"{PROOF_CONTEXT_SET_ANNOTATION} enumerating them",
                )
            elif not isinstance(annotation[1], list) or sorted(annotation[1]) != resolved:
                lint.fail(
                    path,
                    f"{PROOF_CONTEXT_SET_ANNOTATION} at schemas/{file_name}#{pointer} must list "
                    f"exactly {resolved}",
                )
            missing = [context for context in resolved if context not in consumer_operations]
            if missing:
                lint.fail(
                    path,
                    "contexts sharing one schema anchor must each declare consumer_operation; "
                    f"missing for {', '.join(missing)}",
                )
            declared = [consumer_operations[context] for context in resolved if context in consumer_operations]
            if len(set(declared)) != len(declared):
                lint.fail(
                    path,
                    f"contexts sharing schemas/{file_name}#{pointer} declare a duplicate consumer_operation",
                )
            continue
        context = resolved[0]
        owner = _proof_top_def(pointer)
        holders = packed_holders.get((file_name, owner), []) if owner else []
        anchor_fragment = anchors[context][1]
        if len(holders) > 1 and not (
            anchor_fragment == owner or anchor_fragment.startswith(owner + "/")
        ):
            lint.fail(
                path,
                f"schemas/{file_name}#{pointer} is a packed shared-proof leaf: {owner} is reached from "
                f"{len(holders)} object families ({', '.join(holders)}) while only {context} covers it; "
                "give every family its own proof node and row, or register one row per consumer_operation",
            )
        if annotation is not None:
            if annotation[0] == PROOF_CONTEXT_ANNOTATION:
                if annotation[1] != context:
                    lint.fail(
                        path,
                        f"{PROOF_CONTEXT_ANNOTATION} at schemas/{file_name}#{pointer} is {annotation[1]!r} "
                        f"but the registry binds {context!r}",
                    )
            elif not isinstance(annotation[1], list) or sorted(annotation[1]) != [context]:
                lint.fail(
                    path,
                    f"{PROOF_CONTEXT_SET_ANNOTATION} at schemas/{file_name}#{pointer} must list "
                    f"exactly ['{context}']",
                )

    for context, anchor in sorted(anchors.items()):
        inside = [point for point in use_points if _proof_anchor_covers(anchor, *point)]
        if inside and not owned[context]:
            lint.fail(
                path,
                f"{context} claims schemas/{anchor[0]}#{anchor[1]} but every shared-proof use point "
                "inside it belongs to a deeper context; tighten schema_ref to the object family it describes",
            )
        if context in consumer_operations:
            _, _, node = _resolve_proof_schema_ref(documents, f"{anchor[0]}#{anchor[1]}")
            listed = node.get(PROOF_CONTEXT_SET_ANNOTATION) if isinstance(node, dict) else None
            if not isinstance(listed, list) or context not in listed:
                lint.fail(
                    path,
                    f"{context} declares consumer_operation, so schemas/{anchor[0]}#{anchor[1]} must list it "
                    f"in {PROOF_CONTEXT_SET_ANNOTATION}",
                )

    for file_name, document in sorted(documents.items()):
        for pointer, node in _proof_annotated_nodes(document):
            for key in (PROOF_CONTEXT_ANNOTATION, PROOF_CONTEXT_SET_ANNOTATION):
                value = node.get(key)
                if value is None:
                    continue
                declared = [value] if key == PROOF_CONTEXT_ANNOTATION else value
                if key == PROOF_CONTEXT_ANNOTATION and not isinstance(value, str):
                    lint.fail(ARTIFACTS / "schemas" / file_name, f"{key} at {pointer} must be a string")
                    continue
                if key == PROOF_CONTEXT_SET_ANNOTATION and (
                    not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value)
                ):
                    lint.fail(ARTIFACTS / "schemas" / file_name, f"{key} at {pointer} must be a non-empty string array")
                    continue
                for item in declared:
                    if item not in anchors:
                        lint.fail(
                            ARTIFACTS / "schemas" / file_name,
                            f"{key} at {pointer} names an unregistered proof context: {item}",
                        )
                    elif not _proof_anchor_covers(anchors[item], file_name, pointer):
                        lint.fail(
                            ARTIFACTS / "schemas" / file_name,
                            f"{key} at {pointer} names {item}, whose registry schema_ref anchors elsewhere",
                        )

    legacy_token_re = re.compile(LEGACY_PROOF_CONTEXT_PATTERN)
    legacy_used: set[str] = set()
    for scan_path in SPEC_ROOT.rglob("*"):
        if scan_path.is_file() and scan_path.suffix.lower() in {".json", ".md", ".yaml", ".yml"}:
            legacy_used.update(legacy_token_re.findall(scan_path.read_text(encoding="utf-8")))
    for token in sorted(legacy_used):
        lint.fail(path, f"legacy proof context spelling is forbidden: {token}")

    # Domain separations are the second half of this file: separators that are not
    # signing contexts but still decide security outcomes. A replay-cache namespace
    # partitions a replay ledger, so an unregistered or reused literal silently merges
    # two surfaces' replay windows, and spelling one as a proof context (or carrying it
    # in a field named proof_context) makes two different primitives look like one.
    separations = data.get("domain_separations")
    if not isinstance(separations, list) or not separations:
        lint.fail(path, "proof context registry must contain non-empty domain_separations[]")
        separations = []
    domains: set[str] = set()
    separation_families: set[str] = set()
    replay_namespaces: set[str] = set()
    for index, row in enumerate(separations):
        if not isinstance(row, dict):
            lint.fail(path, f"domain_separations[{index}] must be an object")
            continue
        domain = row.get("domain")
        family = row.get("object_family")
        primitive = row.get("primitive")
        fields = row.get("binding_fields")
        if not isinstance(domain, str) or not re.fullmatch(SECURITY_DOMAIN_LABEL_PATTERN, domain):
            lint.fail(
                path,
                f"domain_separations[{index}].domain must be a canonical dot-separated snake_case v1 label",
            )
            domain = None
        elif domain in contexts:
            lint.fail(path, f"security domain label is registered as both context and domain separation: {domain}")
            domain = None
        elif domain in domains:
            lint.fail(path, f"duplicate domain separation {domain}")
            domain = None
        else:
            domains.add(domain)
        if not isinstance(family, str) or not family:
            lint.fail(path, f"domain_separations[{index}].object_family must be a non-empty string")
        elif family in families:
            lint.fail(
                path,
                f"domain separation object_family {family} is already a proof context object family",
            )
        elif family in separation_families:
            lint.fail(path, f"duplicate domain separation object_family {family}")
        else:
            separation_families.add(family)
        if primitive not in DOMAIN_SEPARATION_PRIMITIVES:
            lint.fail(
                path,
                f"domain_separations[{index}].primitive is not a registered primitive: {primitive!r}",
            )
        if not isinstance(fields, list) or not fields or not all(isinstance(item, str) and item for item in fields):
            lint.fail(path, f"domain_separations[{index}].binding_fields must be a non-empty string array")
        schema_ref = row.get("schema_ref")
        if schema_ref is not None:
            if not isinstance(schema_ref, str) or not schema_ref.startswith("schemas/"):
                lint.fail(
                    path,
                    f"domain_separations[{index}].schema_ref must point into artifacts/schemas",
                )
            else:
                file_name, fragment, node = _resolve_proof_schema_ref(documents, schema_ref)
                if not isinstance(node, dict):
                    lint.fail(path, f"domain_separations[{index}].schema_ref does not resolve: {schema_ref}")
                elif primitive == "detached_signature" and node.get(SIGNATURE_DOMAIN_ANNOTATION) != domain:
                    lint.fail(
                        ARTIFACTS / "schemas" / file_name,
                        f"{fragment or '/'} must declare {SIGNATURE_DOMAIN_ANNOTATION}={domain!r}",
                    )
        _check_domain_binding_schema_closure(lint, path, documents, index, row)
        if primitive != REPLAY_CACHE_NAMESPACE_PRIMITIVE:
            continue
        defined_in = row.get("defined_in")
        if not isinstance(defined_in, str) or not defined_in:
            lint.fail(
                path,
                f"domain_separations[{index}] with primitive {REPLAY_CACHE_NAMESPACE_PRIMITIVE} "
                "must declare defined_in",
            )
            continue
        source = SPEC_ROOT / defined_in.split("#", 1)[0]
        if not source.is_file():
            lint.fail(path, f"domain_separations[{index}].defined_in does not resolve: {defined_in}")
        elif domain is not None and domain not in source.read_text(encoding="utf-8"):
            lint.fail(path, f"{domain} is not defined in its declared source {defined_in}")
        if domain is not None:
            replay_namespaces.add(domain)

    for fixture_path in sorted((ARTIFACTS / "fixtures").glob("*.json")):
        fixture = load_json(lint, fixture_path)
        if fixture is None:
            continue
        for pointer, value in _proof_named_field_values(fixture, "proof_context"):
            if not isinstance(value, str) or value not in contexts:
                lint.fail(
                    fixture_path,
                    f"proof_context at {pointer} is not a registered proof context: {value!r}",
                )
        for pointer, value in _proof_named_field_values(fixture, REPLAY_CACHE_NAMESPACE_PRIMITIVE):
            if not isinstance(value, str) or value not in replay_namespaces:
                lint.fail(
                    fixture_path,
                    f"{REPLAY_CACHE_NAMESPACE_PRIMITIVE} at {pointer} is not a registered "
                    f"replay-cache namespace: {value!r}",
                )



def check_timestamp_profile_single_source(lint: Lint) -> None:
    """Keep Arkret-owned absolute instants on the shared fixed-millisecond profile."""
    schema_root = ARTIFACTS / "schemas"
    time_path = schema_root / "time.schema.json"
    time_schema = load_json(lint, time_path)
    timestamp = ((time_schema or {}).get("$defs") or {}).get("timestamp")
    expected_pattern = (
        r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
        r"T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]\.[0-9]{3}Z$"
    )
    if not isinstance(timestamp, dict) or timestamp.get("type") != "string":
        lint.fail(time_path, "$defs.timestamp must be a string schema")
    elif timestamp.get("format") != "date-time" or timestamp.get("pattern") != expected_pattern:
        lint.fail(time_path, "$defs.timestamp must define the fixed YYYY-MM-DDTHH:MM:SS.sssZ profile")

    external_allowlist = {
        ("service-operation-dtos.schema.json", "/$defs/ServiceWebvhInceptionOperation/properties/versionTime"),
    }

    def walk(path: Path, value: Any, pointer: str = "") -> None:
        if isinstance(value, dict):
            if value.get("format") == "date-time":
                key = (path.name, pointer)
                if path == time_path and pointer == "/$defs/timestamp":
                    pass
                elif key in external_allowlist:
                    if value.get("type") != "string":
                        lint.fail(path, f"external date-time allowlist entry must remain a string at {pointer}")
                else:
                    lint.fail(
                        path,
                        f"date-time at {pointer} must reference ./time.schema.json#/$defs/timestamp "
                        "(or be explicitly classified in the external/local allowlist)",
                    )
            for name, child in value.items():
                escaped = name.replace("~", "~0").replace("/", "~1")
                walk(path, child, f"{pointer}/{escaped}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(path, child, f"{pointer}/{index}")

    for path in sorted(schema_root.glob("*.json")):
        data = load_json(lint, path)
        if data is not None:
            walk(path, data)

    for path in sorted((ARTIFACTS / "openapi").glob("*.y*ml")):
        data = load_yaml(lint, path)
        if data is not None:
            walk(path, data)


def check_pcr_exposure_registry(lint: Lint) -> None:
    """Close the read direction of the Principal Control Realm.

    realm_event_kind_policy.allowed_event_kinds says what may be written into a
    PCR. Nothing said what may leave it, so every outward path was decided once,
    in prose, in whichever document happened to need it. This gate makes the
    outward decision a registered artifact and fails when the two directions
    disagree.
    """
    path = ARTIFACTS / "registry" / "pcr-exposure-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict) or data.get("source_of_truth") is not True:
        lint.fail(path, "pcr exposure registry must be a source_of_truth object")
        return

    disclosure_path = ARTIFACTS / "registry" / "outward-disclosure-policy-registry.json"
    disclosure = load_json(lint, disclosure_path)
    if not isinstance(disclosure, dict) or disclosure.get("source_of_truth") is not True:
        lint.fail(disclosure_path, "outward disclosure policy registry must be a source_of_truth object")
        return
    disclosure_rows = disclosure.get("policies")
    if not isinstance(disclosure_rows, list) or not disclosure_rows:
        lint.fail(disclosure_path, "policies must be a non-empty list")
        return
    disclosure_ids: set[str] = set()
    error_registry = load_json(lint, ARTIFACTS / "registry" / "error-code-registry.json") or {}
    error_status = {
        row.get("code"): row.get("http_status")
        for row in error_registry.get("codes", [])
        if isinstance(row, dict)
    }
    body_classes = disclosure.get("body_shape_classes") or {}
    header_classes = disclosure.get("header_classes") or {}
    timing_classes = disclosure.get("timing_classes") or {}
    for index, policy in enumerate(disclosure_rows):
        where = f"policies[{index}]"
        if not isinstance(policy, dict):
            lint.fail(disclosure_path, f"{where} must be an object")
            continue
        policy_id = policy.get("policy_id")
        if not isinstance(policy_id, str) or not policy_id:
            lint.fail(disclosure_path, f"{where}.policy_id must be a non-empty string")
            continue
        if policy_id in disclosure_ids:
            lint.fail(disclosure_path, f"duplicate policy_id {policy_id}")
        disclosure_ids.add(policy_id)
        gates = policy.get("gate_order")
        target_read_gate = policy.get("target_read_gate")
        if (
            not isinstance(gates, list)
            or not gates
            or any(not isinstance(gate, str) or not gate for gate in gates)
            or len(gates) != len(set(gates))
        ):
            lint.fail(disclosure_path, f"{where}.gate_order must be a non-empty unique string list")
        elif target_read_gate not in gates:
            lint.fail(disclosure_path, f"{where}.target_read_gate must name a gate_order entry")
        buckets = policy.get("outward_buckets")
        if not isinstance(buckets, list):
            lint.fail(disclosure_path, f"{where}.outward_buckets must be a list")
            continue
        bucket_ids: set[str] = set()
        for position, bucket in enumerate(buckets):
            spot = f"{where}.outward_buckets[{position}]"
            if not isinstance(bucket, dict):
                lint.fail(disclosure_path, f"{spot} must be an object")
                continue
            bucket_id = bucket.get("bucket_id")
            if not isinstance(bucket_id, str) or not bucket_id or bucket_id in bucket_ids:
                lint.fail(disclosure_path, f"{spot}.bucket_id must be unique and non-empty")
            bucket_ids.add(bucket_id)
            code = bucket.get("code")
            if code not in error_status or bucket.get("http_status") != error_status.get(code):
                lint.fail(disclosure_path, f"{spot} code/http_status must match error-code-registry")
            if bucket.get("body_shape_class") not in body_classes:
                lint.fail(disclosure_path, f"{spot}.body_shape_class is not registered")
            if bucket.get("header_class") not in header_classes:
                lint.fail(disclosure_path, f"{spot}.header_class is not registered")
            if bucket.get("timing_class") not in timing_classes:
                lint.fail(disclosure_path, f"{spot}.timing_class is not registered")
            reasons = bucket.get("internal_reason_families")
            if not isinstance(reasons, list) or not reasons or len(reasons) != len(set(reasons)):
                lint.fail(disclosure_path, f"{spot}.internal_reason_families must be non-empty and unique")

    contract = load_json(lint, ARTIFACTS / "registry" / "contract-registry.json") or {}
    operation_rows = (contract.get("operation_registry") or {}).get("operations", [])
    operation_policy: dict[str, str] = {}
    for operation in operation_rows if isinstance(operation_rows, list) else []:
        if not isinstance(operation, dict):
            continue
        policy_id = operation.get("outward_disclosure_policy_id")
        if policy_id is not None:
            if policy_id not in disclosure_ids:
                lint.fail(disclosure_path, f"{operation.get('operation_id')} references unknown outward disclosure policy {policy_id}")
            operation_policy[operation.get("operation_id")] = policy_id
    keypackage_refs = {
        operation.get("operation_id")
        for operation in operation_rows
        if isinstance(operation, dict)
        and "keypackage-operations.schema.json" in str(operation.get("request_schema_ref", ""))
    }
    missing_keypackage_policy = sorted(keypackage_refs - set(operation_policy))
    if missing_keypackage_policy:
        lint.fail(disclosure_path, f"KeyPackage operations without outward disclosure policy: {missing_keypackage_policy}")
    mappings = load_json(lint, ARTIFACTS / "registry" / "operations-error-mapping.json") or {}
    mapped_codes = {
        row.get("operation_id"): set(row.get("operation_specific", []))
        for row in mappings.get("operations", [])
        if isinstance(row, dict) and isinstance(row.get("operation_specific"), list)
    }
    mimi_signature_codes = {
        "http_signature_required",
        "http_signature_invalid",
        "signature_window_invalid",
    }
    expected_mimi_signature_operations = {
        "ak.open.mimi.command.notify.v1",
        "ak.open.mimi.command.proxy_download.v1",
        "ak.open.mimi.command.report_abuse.v1",
        "ak.open.mimi.command.request_consent.v1",
        "ak.open.mimi.command.submit_message.v1",
        "ak.open.mimi.command.update_consent.v1",
        "ak.open.mimi.command.update_room.v1",
        "ak.open.mimi.exchange.request_key_material.v1",
        "ak.open.mimi.read.identifiers.v1",
    }
    actual_mimi_signature_operations = {
        operation_id
        for operation_id, codes in mapped_codes.items()
        if isinstance(operation_id, str)
        and operation_id.startswith("ak.open.mimi.")
        and mimi_signature_codes.issubset(codes)
    }
    if actual_mimi_signature_operations != expected_mimi_signature_operations:
        lint.fail(
            ARTIFACTS / "registry" / "operations-error-mapping.json",
            "MIMI RFC 9421 operation closure mismatch: "
            f"missing={sorted(expected_mimi_signature_operations - actual_mimi_signature_operations)!r}, "
            f"stale={sorted(actual_mimi_signature_operations - expected_mimi_signature_operations)!r}",
        )
    for unsigned_read in ("ak.open.mimi.read.provider_directory.v1",):
        if mapped_codes.get(unsigned_read, set()) & mimi_signature_codes:
            lint.fail(
                ARTIFACTS / "registry" / "operations-error-mapping.json",
                f"{unsigned_read} must remain outside the per-request source-signature profile",
            )
    mimi_fixture_path = ARTIFACTS / "fixtures" / "mimi-interop-fixture.json"
    mimi_fixture = load_json(lint, mimi_fixture_path) or {}
    mimi_cases = mimi_fixture.get("cases", []) if isinstance(mimi_fixture, dict) else []
    signature_vector = next(
        (
            row for row in mimi_cases
            if isinstance(row, dict)
            and row.get("vector_id") == "ak.vector.mimi.identifier_query_source_signature.v1"
        ),
        None,
    )
    if not isinstance(signature_vector, dict):
        lint.fail(mimi_fixture_path, "missing identifier-query source-signature negative vector")
    else:
        negative_codes = {
            case.get("expected_error_code")
            for case in signature_vector.get("cases", [])
            if isinstance(case, dict) and case.get("psi_evaluated") is False
        }
        if not {"http_signature_required", "http_signature_invalid"}.issubset(negative_codes):
            lint.fail(
                mimi_fixture_path,
                "identifier-query vector must reject missing and invalid signatures before PSI evaluation",
            )
    forbidden_claim_details = {
        "one_time_keys_exhausted",
        "principal_unknown",
        "keypackage_unknown",
        "keypackage_already_consumed",
    }
    for operation_id, policy_id in operation_policy.items():
        if policy_id != "ak.outward_disclosure.target_private_claim.v1":
            continue
        codes = mapped_codes.get(operation_id, set())
        if "claim_failed" not in codes or codes & forbidden_claim_details:
            lint.fail(disclosure_path, f"{operation_id} target-private claim mapping must expose claim_failed and no target-private detail codes")

    carrier_kinds = data.get("carrier_kinds")
    surface_kinds = data.get("surface_kinds")
    if not isinstance(carrier_kinds, dict) or not carrier_kinds:
        lint.fail(path, "carrier_kinds must be a non-empty object")
        return
    if not isinstance(surface_kinds, dict) or not surface_kinds:
        lint.fail(path, "surface_kinds must be a non-empty object")
        return

    def policy_ids(key: str) -> set[str]:
        rows = data.get(key)
        if not isinstance(rows, list) or not rows:
            lint.fail(path, f"{key} must be a non-empty list")
            return set()
        out: set[str] = set()
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                lint.fail(path, f"{key}[{index}] must be an object")
                continue
            policy_id = row.get("policy_id")
            description = row.get("description")
            if not isinstance(policy_id, str) or not policy_id:
                lint.fail(path, f"{key}[{index}].policy_id must be a non-empty string")
                continue
            if policy_id in out:
                lint.fail(path, f"duplicate policy {policy_id}")
            if not isinstance(description, str) or not description.strip():
                lint.fail(path, f"{key}[{index}] must explain the policy")
            out.add(policy_id)
        return out

    authorization_policies = policy_ids("authorization_policies")
    anti_enumeration_policies = policy_ids("anti_enumeration_policies")

    profiles = load_json(lint, ARTIFACTS / "profiles" / "conformance-profiles.json")
    allowlist = (
        ((profiles or {}).get("profile_requirements") or {})
        .get("ak.profile.principal_control_realm.v1", {})
        .get("realm_event_kind_policy", {})
        .get("allowed_event_kinds")
    )
    if not isinstance(allowlist, list) or not allowlist:
        lint.fail(path, "PCR allowlist is unavailable; the exposure registry cannot be closed")
        return

    operations = load_json(lint, ARTIFACTS / "registry" / "operation-registry.json")
    operation_ids = {
        row.get("operation_id")
        for row in ((operations or {}).get("operations") or [])
        if isinstance(row, dict)
    }

    rows = data.get("event_kinds")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "event_kinds must be a non-empty list")
        return

    declared: list[str] = []
    outward_fragments: list[tuple[str, Any]] = []
    registered_schema_kind_pairs: set[tuple[str, str]] = set()
    private_kinds: set[str] = set()

    def resolve_pointer(document: Any, pointer: str) -> Any:
        cursor = document
        for raw_token in pointer.split("/")[1:]:
            token = raw_token.replace("~1", "/").replace("~0", "~")
            if isinstance(cursor, list):
                cursor = cursor[int(token)]
            else:
                cursor = cursor[token]
        return cursor

    for index, row in enumerate(rows):
        where = f"event_kinds[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{where} must be an object")
            continue
        event_kind = row.get("event_kind")
        exposures = row.get("exposures")
        if not isinstance(event_kind, str) or not event_kind:
            lint.fail(path, f"{where}.event_kind must be a non-empty string")
            continue
        declared.append(event_kind)
        if not isinstance(exposures, list):
            lint.fail(path, f"{where}.exposures must be a list")
            continue
        if not exposures:
            private_kinds.add(event_kind)
            continue
        for position, exposure in enumerate(exposures):
            spot = f"{where}.exposures[{position}]"
            if not isinstance(exposure, dict):
                lint.fail(path, f"{spot} must be an object")
                continue
            carrier = exposure.get("carrier")
            surface = exposure.get("surface")
            schema_ref = exposure.get("schema_ref")
            pointers = exposure.get("json_pointers")
            authorization = exposure.get("authorization_policy_id")
            anti_enumeration = exposure.get("anti_enumeration_policy_id")
            disclosure_policy = exposure.get("outward_disclosure_policy_id")
            if carrier not in carrier_kinds:
                lint.fail(path, f"{spot}.carrier is not a registered carrier kind")
            if surface not in surface_kinds:
                lint.fail(path, f"{spot}.surface is not a registered surface kind")
            if authorization not in authorization_policies:
                lint.fail(path, f"{spot}.authorization_policy_id is not registered")
            if anti_enumeration is not None and anti_enumeration not in anti_enumeration_policies:
                lint.fail(path, f"{spot}.anti_enumeration_policy_id is not registered")
            mapping = data.get("outward_disclosure_policy_mapping") or {}
            anti_mapping = mapping.get("anti_enumeration_policy_ids") or {}
            resolved_disclosure = disclosure_policy
            if resolved_disclosure is None:
                if authorization == mapping.get("public_authorization_policy_id"):
                    resolved_disclosure = mapping.get("public_policy_id")
                elif anti_enumeration is not None:
                    resolved_disclosure = anti_mapping.get(anti_enumeration)
                else:
                    resolved_disclosure = mapping.get("authenticated_default_policy_id")
            if resolved_disclosure not in disclosure_ids:
                lint.fail(path, f"{spot} does not resolve a registered outward disclosure policy")
            if surface == "operation":
                if exposure.get("operation_id") not in operation_ids:
                    lint.fail(path, f"{spot}.operation_id is not a registered operation")
                if exposure.get("direction") not in {"request", "response"}:
                    lint.fail(path, f"{spot}.direction must be request or response")
            elif "operation_id" in exposure:
                lint.fail(path, f"{spot} declares operation_id on a non-operation surface")
            if not isinstance(schema_ref, str) or not schema_ref:
                lint.fail(path, f"{spot}.schema_ref must be a non-empty string")
                continue
            file_ref, _, fragment = schema_ref.partition("#")
            schema_path = ARTIFACTS / file_ref
            if not schema_path.is_file():
                lint.fail(path, f"{spot}.schema_ref does not resolve: {schema_ref}")
                continue
            document = load_json(lint, schema_path)
            if document is None:
                continue
            if fragment:
                try:
                    fragment_node = resolve_pointer(document, fragment)
                    outward_fragments.append((event_kind, fragment_node))
                except (KeyError, IndexError, ValueError):
                    lint.fail(path, f"{spot}.schema_ref fragment does not resolve: {schema_ref}")
                    continue
            else:
                fragment_node = document
                outward_fragments.append((event_kind, document))
            registered_schema_kind_pairs.add((schema_ref, event_kind))
            annotation = fragment_node.get("x-arkret-pcr-outward-event-kinds") if isinstance(fragment_node, dict) else None
            if not isinstance(annotation, list) or event_kind not in annotation:
                lint.fail(path, f"{spot}.schema_ref target lacks x-arkret-pcr-outward-event-kinds annotation for {event_kind}")
            if not isinstance(pointers, list):
                lint.fail(path, f"{spot}.json_pointers must be a list")
                continue
            for pointer in pointers:
                if not isinstance(pointer, str) or not pointer.startswith("/"):
                    lint.fail(path, f"{spot}.json_pointers entries must be JSON pointers")
                    continue
                try:
                    resolve_pointer(document, pointer)
                except (KeyError, IndexError, ValueError):
                    lint.fail(
                        path,
                        f"{spot}.json_pointers does not resolve in {file_ref}: {pointer}",
                    )

    missing = sorted(set(allowlist) - set(declared))
    extra = sorted(set(declared) - set(allowlist))
    if missing:
        lint.fail(path, f"PCR allowlist kinds without an exposure decision: {missing}")
    if extra:
        lint.fail(path, f"exposure decisions for kinds outside the PCR allowlist: {extra}")
    duplicates = sorted({kind for kind in declared if declared.count(kind) > 1})
    if duplicates:
        lint.fail(path, f"duplicate event_kind rows: {duplicates}")

    # Reverse direction: a schema cannot mark a PCR kind as outward without an
    # exact registry exposure that names the same annotated schema fragment.
    for schema_path in sorted((ARTIFACTS / "schemas").glob("*.json")):
        document = load_json(lint, schema_path)
        if not isinstance(document, dict):
            continue

        def walk_annotations(node: Any, tokens: list[str]) -> None:
            if isinstance(node, dict):
                annotation = node.get("x-arkret-pcr-outward-event-kinds")
                if annotation is not None:
                    if not isinstance(annotation, list) or not annotation:
                        lint.fail(schema_path, "x-arkret-pcr-outward-event-kinds must be a non-empty list")
                    else:
                        fragment = "/".join(token.replace("~", "~0").replace("/", "~1") for token in tokens)
                        schema_ref = f"schemas/{schema_path.name}" + (f"#/{fragment}" if fragment else "")
                        for kind in annotation:
                            if (schema_ref, kind) not in registered_schema_kind_pairs:
                                lint.fail(schema_path, f"unregistered PCR outward annotation {kind} at {schema_ref}")
                for key, value in node.items():
                    if key != "x-arkret-pcr-outward-event-kinds":
                        walk_annotations(value, [*tokens, key])
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    walk_annotations(value, [*tokens, str(index)])

        walk_annotations(document, [])

    # A kind declared PCR-private must not be reachable through a fragment some
    # other kind already opened. This is the check that catches a carrier quietly
    # widened to a second kind.
    for private in sorted(private_kinds):
        for owner, fragment in outward_fragments:
            if private in json.dumps(fragment, ensure_ascii=False):
                lint.fail(
                    path,
                    f"PCR-private kind {private} is reachable inside the outward carrier "
                    f"registered for {owner}",
                )
                break
