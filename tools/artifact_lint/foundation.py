"""Artifact lint phase 1: foundation."""

from __future__ import annotations

from .core import (
    ARTIFACTS,
    Any,
    CELL_FAMILY_RE,
    CELL_WRITE_DERIVATIONS,
    CONFLICT_RECOVERY_KIND,
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
    REGISTRY_BOTTOMS,
    REGISTRY_LATTICES,
    REGISTRY_PLANES,
    ROOT,
    SCHEMA_ID_RE,
    SPEC_ROOT,
    VALUE_PROJECTION_DIGEST_INPUTS,
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
    files.add(ROOT / "site" / "src" / "lib" / "site-meta.ts")
    return sorted(path for path in files if path.is_file())



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
    unknown_keys = set(component) - {"kind", "selector", "branches"}
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
        and context != "ak.accountability-scope-set-v1"
    ):
        lint.fail(
            path,
            f"{ref}.context must be 'ak.accountability-scope-set-v1' for {event_kind}",
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
    """The single registered exception to literal cell addressing.

    Enforces both directions: only `ak.state.conflict_recovery` may declare
    `cell_ref` or a `reset` projection, and it MUST declare exactly that pair
    with no lattice, bottom, family, subject or condition -- a reset is not a
    join, and a conditional reset would make the recovery path itself depend on
    payload shape.
    """
    if kind != CONFLICT_RECOVERY_KIND:
        lint.fail(
            event_path,
            f"{write_ref} declares cell_ref or a reset projection; that form is reserved "
            f"to {CONFLICT_RECOVERY_KIND} (event-auth-state-resolution.md section 9.5)",
        )
        return
    cell_ref = write.get("cell_ref")
    if not isinstance(cell_ref, dict) or cell_ref.get("kind") != "cell_ref":
        lint.fail(event_path, f"{write_ref}.cell_ref must be an object with kind='cell_ref'")
    elif cell_ref.get("field") != "payload.target_cell":
        lint.fail(
            event_path,
            f"{write_ref}.cell_ref.field must be payload.target_cell, got "
            f"{cell_ref.get('field')!r}",
        )
    projection = write.get("effect_projection")
    if not isinstance(projection, dict) or projection.get("kind") != "reset":
        lint.fail(event_path, f"{write_ref}.effect_projection must be kind='reset'")
    elif projection.get("value") != {"field": "payload.resolved_value"}:
        lint.fail(
            event_path,
            f"{write_ref}.effect_projection.value must be "
            "{'field': 'payload.resolved_value'}",
        )
    for forbidden in ("cell_family", "cell_subject", "lattice", "bottom", "condition"):
        if forbidden in write:
            lint.fail(
                event_path,
                f"{write_ref} MUST NOT declare {forbidden}: the target family, its lattice "
                "and its bottom belong to the cell being recovered, not to this kind",
            )



def lint_subject_field_path(lint: Lint, path: Path, ref: str, value: object) -> None:
    """Validate an explicitly sourced cell-subject field path."""
    lint_field_path(lint, path, ref, value)
    if not isinstance(value, str) or FIELD_PATH_RE.fullmatch(value) is None:
        return
    if value.startswith("payload.") or value in ENVELOPE_SUBJECT_SOURCES:
        return
    if value.startswith("envelope."):
        lint.fail(path, f"{ref} uses an unregistered envelope source: {value!r}")
        return
    lint.fail(
        path,
        f"{ref} must use an explicit payload.* or "
        f"{' / '.join(ENVELOPE_SUBJECT_SOURCES)} source: {value!r}",
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
    a literal, a field path, a `select` component, or a digest over a field.
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
            for key in ("literal", "field", "envelope_field", "select", "digest_of")
            if key in member
        ]
        if len(sources) != 1:
            lint.fail(
                path,
                f"{member_ref} must declare exactly one of "
                "literal/field/envelope_field/select/digest_of",
            )
            continue
        source = sources[0]
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
        unknown_keys = set(member) - {"name", "optional", source}
        if unknown_keys:
            lint.fail(path, f"{member_ref} has unknown member(s) {sorted(unknown_keys)}")
        if "optional" in member and not isinstance(member["optional"], bool):
            lint.fail(path, f"{member_ref}.optional must be a boolean")



def lint_effect_source(
    lint: Lint, path: Path, ref: str, source: object, *, allow_dot: bool = False
) -> None:
    """Validate one closed source used to derive a lattice op member.

    `dot` resolves to the write's canonical OR-Set dot
    (`ak:event:<event_id>:<write_index>`, event-and-patch.md section 2.4.2) and is
    only legal in an or_set tag position, so callers must opt in.
    """
    if not isinstance(source, dict):
        lint.fail(path, f"{ref} must be an object")
        return
    allowed = ("field", "envelope_field", "const", "projected_value")
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

    The only provable form in the closed condition grammar is field_present /
    field_absent over the identical path. Treating any other pair as exclusive
    would be a guess, and a wrong guess means two writes racing on one cell.
    """
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    kinds = {left.get("kind"), right.get("kind")}
    if kinds != {"field_present", "field_absent"}:
        return False
    return (
        isinstance(left.get("field"), str)
        and left.get("field") == right.get("field")
    )



def lint_effect_projection(
    lint: Lint,
    path: Path,
    ref: str,
    projection: object,
    lattice: object,
) -> None:
    """Validate the closed payload-to-lattice-op projection grammar."""
    if not isinstance(projection, dict):
        lint.fail(path, f"{ref} must be an object")
        return
    projection_kind = projection.get("kind")
    expected_kinds = {
        "fsm": {"transition", "transition_to"},
        "mv_register": {"set", "apply_patch"},
        "cas_register": {"set", "apply_patch"},
        "ordered_log": {"append"},
        "or_set": {
            "or_set_delta",
            "or_set_add",
            "or_set_batch_add",
            "or_set_remove_observed",
            "or_set_remove_dots",
        },
    }.get(lattice)
    if expected_kinds is None:
        lint.fail(path, f"{ref} is not defined for lattice {lattice!r}")
        return
    if projection_kind not in expected_kinds:
        lint.fail(
            path,
            f"{ref}.kind must be one of {sorted(expected_kinds)!r} for lattice {lattice!r}",
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
        unknown = set(projection) - {"kind", "patch", "expected_prestate"}
        if unknown:
            lint.fail(path, f"{ref} has unknown member(s) {sorted(unknown)}")
        if "patch" not in projection:
            lint.fail(path, f"{ref}.patch is required")
        else:
            lint_effect_source(lint, path, f"{ref}.patch", projection["patch"])
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
        issuer_seq = projection.get("issuer_seq")
        if (
            isinstance(issuer_seq, dict)
            and "const" in issuer_seq
            and (
                not isinstance(issuer_seq["const"], int)
                or isinstance(issuer_seq["const"], bool)
                or issuer_seq["const"] < 0
            )
        ):
            lint.fail(path, f"{ref}.issuer_seq.const must be an unsigned integer")
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
    ref = f"event_kind_registry.fsm_contracts[{family!r}]"
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
    templates = registry.get("fsm_templates")
    fsm_contracts = registry.get("fsm_contracts")
    private = registry.get("actor_private_contracts")
    if not isinstance(rows, list) or not isinstance(contracts, dict):
        lint.fail(path, "event_kind_registry must contain event_kinds and cell_contracts")
        return
    if not isinstance(templates, dict) or not isinstance(fsm_contracts, dict):
        lint.fail(path, "event_kind_registry must contain fsm_templates and fsm_contracts")
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
    for family, contract in fsm_contracts.items():
        if not isinstance(family, str) or CELL_FAMILY_RE.fullmatch(family) is None:
            lint.fail(path, f"fsm_contracts key must be a canonical cell family: {family!r}")
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
            lint.fail(path, f"fsm_contracts[{family!r}].states must be a non-empty unique string array")
            continue
        state_set = set(states)
        if (
            not isinstance(initial_values, list)
            or not initial_values
            or not set(initial_values) <= state_set
        ):
            lint.fail(path, f"fsm_contracts[{family!r}] must declare valid initial_state(s)")
        if not isinstance(terminal, list) or not set(terminal) <= state_set:
            lint.fail(path, f"fsm_contracts[{family!r}].terminal_states must be a states subset")
        if not isinstance(transitions, list):
            lint.fail(path, f"fsm_contracts[{family!r}].allowed_transitions must be an array")
            continue
        seen_edges: set[tuple[str, str]] = set()
        for index, edge in enumerate(transitions):
            if (
                not isinstance(edge, list)
                or len(edge) != 2
                or not all(isinstance(value, str) for value in edge)
                or not set(edge) <= state_set
            ):
                lint.fail(path, f"fsm_contracts[{family!r}].allowed_transitions[{index}] is invalid")
                continue
            pair = (edge[0], edge[1])
            if pair in seen_edges:
                lint.fail(path, f"fsm_contracts[{family!r}] repeats transition {pair}")
            seen_edges.add(pair)
        resolved_contracts[family] = resolved

    shared_fsm_families: set[str] = set()
    for kind, contract in contracts.items():
        if not isinstance(contract, dict):
            continue
        for write in contract.get("cell_writes", []):
            if not isinstance(write, dict) or write.get("lattice") != "fsm":
                continue
            family = write.get("cell_family")
            if isinstance(family, str):
                shared_fsm_families.add(family)
                if family not in resolved_contracts:
                    lint.fail(path, f"{kind} writes FSM family {family} without one fsm_contract")
                elif resolved_contracts[family].get("axis") == "object_lifecycle":
                    modality = event_rows.get(kind, {}).get("lifecycle_modality")
                    if modality not in {"reversible", "terminal"}:
                        lint.fail(
                            path,
                            f"{kind} writes object_lifecycle FSM {family} but has no valid lifecycle_modality",
                        )
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
            predicate = requirement.get("predicate")
            predicate_valid = isinstance(predicate, dict) and isinstance(
                predicate.get("field"), str
            )
            if predicate_valid and predicate.get("kind") == "stored_field_present":
                predicate_valid = set(predicate) == {"kind", "field"}
            elif predicate_valid and predicate.get("kind") == "stored_field_equals_payload":
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
        lint.fail(path, f"unreferenced fsm_contracts: {sorted(extra_contracts)}")
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
            "lattice", "bottom", "initial_value",
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
                # zh/authz/event-auth-state-resolution.md section 9.5: a
                # conflict recovery addresses one cell of an arbitrary family,
                # so its target cannot be a literal ak.component.*.v<n> URI and
                # its write is a reset rather than a join. That form is closed
                # to this one kind, and this kind MUST use it -- otherwise
                # `cell_ref` becomes a general escape from static cell
                # addressing, which is what the literal family exists to
                # prevent.
                has_cell_ref = "cell_ref" in write
                projection_kind = None
                if isinstance(write.get("effect_projection"), dict):
                    projection_kind = write["effect_projection"].get("kind")
                if kind == CONFLICT_RECOVERY_KIND or has_cell_ref or projection_kind == "reset":
                    lint_conflict_recovery_write(lint, event_path, write_ref, kind, write)
                    continue
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
                        write.get("lattice"),
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
                write_lattice = write.get("lattice")
                if write_lattice not in REGISTRY_LATTICES:
                    lint.fail(event_path, f"{write_ref} has unknown lattice {write_lattice!r}")
                write_bottom = write.get("bottom")
                if write_bottom not in REGISTRY_BOTTOMS:
                    lint.fail(event_path, f"{write_ref} has unknown bottom {write_bottom!r}")
                elif write_lattice == "or_set" and write_bottom == "reject":
                    # zh/authz/event-auth-state-resolution.md section 9.1.1: the
                    # or_set join never produces bottom, so an or_set bottom can
                    # never be an authorization rejection. inert is the default;
                    # expose is legal only where the owning domain document
                    # defines the exposed multi-head handling.
                    lint.fail(
                        event_path,
                        f"{write_ref} declares bottom=reject on an or_set; an or_set bottom "
                        "MUST be inert or expose and MUST NOT fail authorization closed",
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
                        write_lattice == "or_set"
                        and {previous_kind, projection_kind}
                        <= (add_kinds | remove_kinds)
                        and bool({previous_kind, projection_kind} & add_kinds)
                        and bool({previous_kind, projection_kind} & remove_kinds)
                    )
                    # The other legal repeat is a provably complementary pair:
                    # field_present / field_absent on the same path, so the
                    # reducer derives exactly one of them for any payload.
                    # Anything weaker would let two writes race on one cell.
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
                lint.fail(event_path, f"{kind} cell_writes row must declare plane=data|control")
            if not isinstance(sealed, bool):
                lint.fail(event_path, f"{kind} cell_writes row must declare sealed boolean")
            elif (plane == "control") != sealed:
                lint.fail(event_path, f"{kind} sealed must be true iff plane=control")
            concurrency_class = row.get("concurrency_class")
            if plane == "control":
                if concurrency_class not in {
                    "merge_safe",
                    "exclusive",
                    "security_barrier",
                }:
                    lint.fail(
                        event_path,
                        f"{kind} control contract must declare a valid concurrency_class",
                    )
            elif concurrency_class is not None:
                lint.fail(
                    event_path,
                    f"{kind} data contract must omit control concurrency_class",
                )
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
            if id_kind != "session_grant":
                lint.fail(
                    id_path,
                    f"{id_kind} has no registered suite_tagged_full_digest authority contract",
                )
            if authority != "issuer_record":
                lint.fail(
                    id_path,
                    "session_grant suite-tagged row must declare identity_authority=issuer_record",
                )
            if genesis_kinds is not None:
                lint.fail(id_path, "session_grant issuer-record row must omit genesis_event_kinds")
            if row.get("derivation_contract_ref") != "#/id_kind_registry/issuer_record_identity_contract":
                lint.fail(id_path, "session_grant must reference issuer_record_identity_contract")
            if row.get("storage_identity_key") != ["issuer_did", "typed_id"]:
                lint.fail(id_path, "session_grant storage identity key must bind issuer_did and typed_id")
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
        if len(segments) < 4:
            lint.fail(
                operation_path,
                f"operation_id must be ak.<surface>.<domain...>.<kind>.<action>: {operation_id}",
            )
            continue
        if segments[-2] not in OPERATION_KINDS:
            lint.fail(
                operation_path,
                f"operation_id kind segment {segments[-2]!r} is not one of {sorted(OPERATION_KINDS)}: {operation_id}",
            )
        if segments[-1] in FORBIDDEN_OPERATION_ACTIONS:
            lint.fail(
                operation_path,
                f"operation_id action segment {segments[-1]!r} is an HTTP method name, not a protocol effect: {operation_id}",
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
        op_kind = segments[-2] if len(segments) >= 2 else ""
        op_action = segments[-1] if segments else ""
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



def check_id_form_wire_schema_alignment(lint: Lint) -> None:
    """Join ID classification, derived wire forms, schema regexes, and storage rules."""
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

    pattern_rows: list[tuple[Path, str]] = []
    for schema_path in sorted((ARTIFACTS / "schemas").glob("*.schema.json")):
        schema = load_json(lint, schema_path)
        if not isinstance(schema, dict):
            continue
        for _json_path, value, key in walk_json(schema):
            if key == "pattern" and isinstance(value, str):
                pattern_rows.append((schema_path, value))

    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = row.get("kind")
        id_form = row.get("id_form")
        wire_form = row.get("wire_form")
        if not isinstance(kind, str):
            continue
        if id_form == "event_derived":
            expected_wire = f"ak:{kind}:<44-char-event-token>"
            if wire_form != expected_wire:
                lint.fail(registry_path, f"{kind} event-derived wire_form must equal {expected_wire!r}")
            matching = [
                (path, pattern)
                for path, pattern in pattern_rows
                if pattern.startswith(f"^ak:{kind}:")
            ]
            if not matching:
                lint.fail(registry_path, f"{kind} event-derived ID has no schema regex")
            if matching and not any("{44}" in pattern for _, pattern in matching):
                lint.fail(registry_path, f"event-derived {kind} schemas never require a 44-character token")
            for schema_path, pattern in matching:
                if "{44}" not in pattern and "-7[0-9a-f]{3}-" in pattern:
                    lint.fail(schema_path, f"event-derived {kind} schema retains a UUID-only pattern")
        elif id_form == "suite_tagged_full_digest":
            expected_wire = f"ak:{kind}:<44-char-suite-tagged-full-digest-token>"
            if wire_form != expected_wire:
                lint.fail(registry_path, f"{kind} suite-tagged wire_form must equal {expected_wire!r}")
            matching = [
                (path, pattern)
                for path, pattern in pattern_rows
                if pattern.startswith(f"^ak:{kind}:")
            ]
            if not matching:
                lint.fail(registry_path, f"{kind} suite-tagged ID has no schema regex")
            if matching and not any("{44}" in pattern for _, pattern in matching):
                lint.fail(registry_path, f"suite-tagged {kind} schemas never require a 44-character token")
        elif id_form == "producer_allocated":
            expected_wire = f"ak:{kind}:<uuidv7>"
            if wire_form != expected_wire:
                lint.fail(registry_path, f"{kind} producer wire_form must equal {expected_wire!r}")
            matching = [
                (path, pattern)
                for path, pattern in pattern_rows
                if pattern.startswith(f"^ak:{kind}:")
            ]
            if matching and not any("-7[0-9a-f]{3}-" in pattern for _, pattern in matching):
                lint.fail(registry_path, f"producer-allocated {kind} schemas never require UUIDv7")



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



def check_proof_context_registry(lint: Lint) -> None:
    path = ARTIFACTS / "registry" / "proof-context-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict) or data.get("source_of_truth") is not True:
        lint.fail(path, "proof context registry must be a source_of_truth object")
        return
    rows = data.get("contexts")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "proof context registry must contain non-empty contexts[]")
        return
    contexts: set[str] = set()
    families: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            lint.fail(path, f"contexts[{index}] must be an object")
            continue
        context = row.get("context")
        family = row.get("object_family")
        fields = row.get("binding_fields")
        schema_ref = row.get("schema_ref")
        if not isinstance(context, str) or not re.fullmatch(r"ak\.[a-z0-9-]+-proof-v1", context):
            lint.fail(path, f"contexts[{index}].context is not a canonical proof context")
        elif context in contexts:
            lint.fail(path, f"duplicate proof context {context}")
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
        if not isinstance(schema_ref, str) or not schema_ref.startswith("schemas/"):
            lint.fail(path, f"contexts[{index}].schema_ref must point into artifacts/schemas")
        else:
            schema_path = ARTIFACTS / schema_ref.split("#", 1)[0]
            if not schema_path.is_file():
                lint.fail(path, f"contexts[{index}].schema_ref does not resolve: {schema_ref}")

    token_re = re.compile(r"ak\.[a-z0-9-]+-proof-v1")
    used: set[str] = set()
    for scan_path in SPEC_ROOT.rglob("*"):
        if scan_path.is_file() and scan_path.suffix.lower() in {".json", ".md", ".yaml", ".yml"}:
            used.update(token_re.findall(scan_path.read_text(encoding="utf-8")))
    for token in sorted(used - contexts):
        lint.fail(path, f"proof context literal is not registered: {token}")



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

