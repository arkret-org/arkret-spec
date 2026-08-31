#!/usr/bin/env python3
"""Unified artifact maintenance pipeline for Arkret spec.

Layout (post-restructure):

  spec/v1/zh/                          normative Chinese prose
  spec/v1/en/                          English informative entry (non-normative; no English specification is promised)
  spec/v1/artifacts/registry/          canonical + generated registry views
  spec/v1/artifacts/profiles/          conformance profiles
  spec/v1/artifacts/schemas/           JSON Schemas
  spec/v1/artifacts/openapi/           OpenAPI document(s)
  spec/v1/artifacts/bindings/          non-HTTP bindings
  spec/v1/artifacts/fixtures/          conformance fixtures

This pipeline owns three responsibilities:

  generate   regenerate derived registry views from contract-registry.json
             and the single version-pinned public registry snapshot
  check      verify generated/public drift, fixture digests, artifact versions,
             then run lints

The legacy "sync canonical files into zh/ mirrors" and "rewrite generated
markdown tables inside zh/sync/service-api-schema.{md,mdx}" responsibilities
are gone. The site renders machine artifacts directly via MDX components
(<EventKindTable/>, <OperationTable/>, <SchemaViewer/>, ...), so duplicating
them inside Markdown or under zh/ is no longer needed.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from .release_metadata import current_release_tag as read_current_release_tag
    from .check_artifact_versions import semantic_content_digest, transition_errors
except ImportError:  # Direct script execution: python tools/artifact_pipeline.py
    from release_metadata import current_release_tag as read_current_release_tag
    from check_artifact_versions import semantic_content_digest, transition_errors

ROOT = Path(__file__).resolve().parents[1]
SPEC_ROOT = ROOT / "spec" / "v1"
ARTIFACTS = SPEC_ROOT / "artifacts"
REGISTRY = ARTIFACTS / "registry"
CONTRACT_REGISTRY_PATH = REGISTRY / "contract-registry.json"
PROFILE_REGISTRY_PATH = ARTIFACTS / "profiles" / "conformance-profiles.json"
LINT_MODULE = "tools.artifact_lint"
PROSE_LINT_SCRIPT = Path(__file__).with_name("lint_spec.py")
FIXTURE_DIGEST_SCRIPT = Path(__file__).with_name("check_fixture_digests.py")
SESSION_GRANT_KAT_SCRIPT = Path(__file__).with_name("check_session_grant_kat.py")
CONTACT_ROUND_KAT_SCRIPT = Path(__file__).with_name("check_contact_round_kat.py")
ARTIFACT_VERSION_SCRIPT = Path(__file__).with_name("check_artifact_versions.py")
COMPLETENESS_REPORT_SCRIPT = Path(__file__).with_name("gen_operation_completeness_report.py")
EVENT_REFERENCE_INVENTORY_SCRIPT = Path(__file__).with_name(
    "gen_event_reference_inventory.py"
)
PAYLOAD_VALIDATOR_PROFILE_SCRIPT = Path(__file__).with_name(
    "check_payload_validator_profiles.py"
)
EVENT_KIND_VECTOR_GAP_SCRIPT = Path(__file__).with_name(
    "check_event_kind_vector_gaps.py"
)
PRESENCE_MANIFEST_SCRIPT = Path(__file__).with_name("gen_property_presence_manifest.py")
SCHEMA_COVERAGE_SCRIPT = Path(__file__).with_name("gen_schema_consumer_coverage.py")
OPERATION_STRING_CLASSIFICATION_SCRIPT = Path(__file__).with_name(
    "gen_operation_string_field_classification.py"
)
OPERATION_STRING_CLASSIFICATION_TEST = Path(__file__).with_name(
    "test_operation_string_field_classification.py"
)
OPENAPI_OPERATION_SELECTOR_SCRIPT = Path(__file__).with_name(
    "check_openapi_operation_selectors.py"
)
OPERATION_CLOSURE_LOCK_SCRIPT = Path(__file__).with_name(
    "check_operation_closure_locks.py"
)
PUBLIC_V1 = ROOT / "site" / "public" / "v1"
OPERATION_SCHEMA_INDEX_PATH = ARTIFACTS / "reports" / "operation-schema-index.json"
CLASSIFICATION_FIELD_REGISTRY_PATH = REGISTRY / "classification-field-registry.json"
OPENAPI_PATH = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
OPENAPI_HIGH_SECURITY_POLICY_KEY = "x-arkret-high-security-session-authentication-policy"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


@lru_cache(maxsize=1)
def artifact_metadata_references() -> dict[str, dict[str, Any]]:
    """Read the last validated metadata baseline, not another semantic source."""
    path = ARTIFACTS / "reports" / "artifact-version-digests.json"
    if not path.exists():
        return {}
    return {row["path"]: row for row in load_json(path).get("artifacts", [])}


def preserve_artifact_metadata_when_semantics_match(
    path: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    """Keep artifact-local release metadata stable across unrelated source changes."""
    if not path.exists():
        return payload
    existing = load_json(path)
    if not isinstance(existing, dict):
        return payload
    semantic_keys = {"version", "generated_at"}
    existing_semantics = {
        key: value for key, value in existing.items() if key not in semantic_keys
    }
    payload_semantics = {
        key: value for key, value in payload.items() if key not in semantic_keys
    }
    if existing_semantics != payload_semantics:
        return payload
    if path.is_relative_to(ROOT):
        reference = artifact_metadata_references().get(path.relative_to(ROOT).as_posix())
        if reference is not None:
            current = {
                "path": reference["path"],
                "version": existing.get("version"),
                "generated_at": existing.get("generated_at"),
                "content_digest": semantic_content_digest(existing),
            }
            if transition_errors(reference, current):
                # A prior generation may have written new content before the
                # author advanced its canonical metadata. Do not pin that
                # intermediate state merely because the next run is byte-stable.
                return payload
    version = existing.get("version")
    generated_at = existing.get("generated_at")
    if not isinstance(version, (str, int)) or isinstance(version, bool):
        return payload
    if not isinstance(generated_at, str) or not generated_at:
        return payload
    stable = copy.deepcopy(payload)
    stable["version"] = version
    stable["generated_at"] = generated_at
    return stable


@lru_cache(maxsize=1)
def load_contract_registry() -> dict[str, Any]:
    data = load_json(CONTRACT_REGISTRY_PATH)
    if not isinstance(data, dict):
        raise SystemExit(f"invalid contract registry: {CONTRACT_REGISTRY_PATH}")
    return data


def registry_generation_metadata(catalog: dict[str, Any]) -> tuple[str, str]:
    version = catalog.get("version")
    generated_at = catalog.get("generated_at")
    if not isinstance(version, str) or not version:
        raise SystemExit("contract registry missing version")
    if not isinstance(generated_at, str) or not generated_at:
        raise SystemExit("contract registry missing generated_at")
    try:
        datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SystemExit(f"contract registry generated_at must be RFC3339: {generated_at}") from exc
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", version) and not generated_at.startswith(version):
        raise SystemExit("contract registry generated_at date must match version")
    return version, generated_at


def current_release_tag() -> str:
    try:
        return read_current_release_tag()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"invalid spec/v1/release-metadata.json: {exc}") from exc


def current_public_registry_path() -> Path:
    version = current_release_tag()[1:]
    return PUBLIC_V1 / f"contract-registry-{version}.json"


def public_registry_paths() -> list[Path]:
    return [current_public_registry_path()]


# Capability action rows may declare a machine-evaluated derivation instead of a
# hand-maintained list. The rule is the source of truth; the materialized list is
# a cached projection that `check` recomputes, so hand-editing either the
# contract registry row or the generated view is a drift failure.
CAPABILITY_ACTION_DERIVATION_RULES = {
    "coverage_rule": "target_event_kinds",
    "grant_authority_rule": "grant_authority_actions",
}
CAPABILITY_ACTION_DERIVATION_FLAGS = ("root_control_only", "subject_only", "reducer_only")
CAPABILITY_ACTION_RULE_KEYS = {
    "exclude_self",
    "require_profile_null",
    "include_actions",
    "exclude_event_mapping_kinds",
    "exclude_flags",
    "exclude_categories",
    "exclude_action_prefixes",
    "exclude_actions",
}


def capability_action_rows(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    section = catalog.get("capability_action_registry")
    if not isinstance(section, dict):
        raise SystemExit("contract registry missing capability_action_registry")
    rows = section.get("actions")
    if not isinstance(rows, list):
        raise SystemExit("capability_action_registry.actions must be an array")
    return [row for row in rows if isinstance(row, dict)]


def capability_action_flag(row: dict[str, Any], flag: str) -> bool:
    value = row.get(flag)
    if value is None:
        return False
    if not isinstance(value, bool):
        raise SystemExit(
            f"capability action {row.get('action')!r} {flag} must be a boolean"
        )
    return value


def rule_string_list(rule: dict[str, Any], key: str, rule_ref: str) -> list[str]:
    value = rule.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise SystemExit(f"{rule_ref}.{key} must be an array of non-empty strings")
    return value


def capability_action_rule_selection(
    rule: object, rows: list[dict[str, Any]], owner_action: str, rule_ref: str
) -> list[dict[str, Any]]:
    """Evaluate one closed action-predicate rule over the registry rows."""
    if not isinstance(rule, dict):
        raise SystemExit(f"{rule_ref} must be an object")
    unknown = sorted(set(rule) - CAPABILITY_ACTION_RULE_KEYS)
    if unknown:
        raise SystemExit(f"{rule_ref} has unknown member(s) {unknown}")
    exclude_self = rule.get("exclude_self", False)
    require_profile_null = rule.get("require_profile_null", False)
    for key, value in (
        ("exclude_self", exclude_self),
        ("require_profile_null", require_profile_null),
    ):
        if not isinstance(value, bool):
            raise SystemExit(f"{rule_ref}.{key} must be a boolean")
    exclude_mapping_kinds = set(rule_string_list(rule, "exclude_event_mapping_kinds", rule_ref))
    include_actions = set(rule_string_list(rule, "include_actions", rule_ref))
    exclude_flags = rule_string_list(rule, "exclude_flags", rule_ref)
    unknown_flags = sorted(set(exclude_flags) - set(CAPABILITY_ACTION_DERIVATION_FLAGS))
    if unknown_flags:
        raise SystemExit(f"{rule_ref}.exclude_flags has unknown flag(s) {unknown_flags}")
    exclude_categories = set(rule_string_list(rule, "exclude_categories", rule_ref))
    exclude_prefixes = tuple(rule_string_list(rule, "exclude_action_prefixes", rule_ref))
    exclude_actions = set(rule_string_list(rule, "exclude_actions", rule_ref))
    known_actions = {row.get("action") for row in rows}
    unknown_includes = sorted(action for action in include_actions if action not in known_actions)
    if unknown_includes:
        raise SystemExit(f"{rule_ref}.include_actions names unregistered action(s) {unknown_includes}")
    unknown_actions = sorted(action for action in exclude_actions if action not in known_actions)
    if unknown_actions:
        raise SystemExit(f"{rule_ref}.exclude_actions names unregistered action(s) {unknown_actions}")

    selected: list[dict[str, Any]] = []
    for row in rows:
        action = row.get("action")
        if not isinstance(action, str):
            continue
        if exclude_self and action == owner_action:
            continue
        if action in exclude_actions:
            continue
        if require_profile_null and row.get("profile") is not None and action not in include_actions:
            continue
        if row.get("event_mapping_kind") in exclude_mapping_kinds:
            continue
        if row.get("category") in exclude_categories:
            continue
        if exclude_prefixes and action.startswith(exclude_prefixes):
            continue
        if any(capability_action_flag(row, flag) for flag in exclude_flags):
            continue
        selected.append(row)
    return selected


def capability_action_derivations(catalog: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    """Materialized value for every rule-derived capability action field."""
    rows = capability_action_rows(catalog)
    derived: dict[str, dict[str, list[str]]] = {}
    for row in rows:
        action = row.get("action")
        if not isinstance(action, str):
            continue
        for rule_key, field in CAPABILITY_ACTION_DERIVATION_RULES.items():
            if rule_key not in row:
                continue
            rule_ref = f"capability_action_registry.actions[{action}].{rule_key}"
            selected = capability_action_rule_selection(row[rule_key], rows, action, rule_ref)
            if field == "target_event_kinds":
                values: set[str] = set()
                for selected_row in selected:
                    targets = selected_row.get("target_event_kinds")
                    if not isinstance(targets, list):
                        raise SystemExit(
                            f"{rule_ref} selected {selected_row.get('action')!r} without target_event_kinds"
                        )
                    values.update(target for target in targets if isinstance(target, str))
            else:
                values = {
                    selected_row["action"]
                    for selected_row in selected
                    if isinstance(selected_row.get("action"), str)
                }
            if not values:
                raise SystemExit(f"{rule_ref} selected nothing; a derived authority set MUST NOT be empty")
            derived.setdefault(action, {})[field] = sorted(values)
    return derived


def apply_capability_action_derivations(catalog: dict[str, Any]) -> list[str]:
    """Write derived fields back into the catalog; return the changed action ids."""
    derived = capability_action_derivations(catalog)
    changed: list[str] = []
    for row in capability_action_rows(catalog):
        action = row.get("action")
        if action not in derived:
            continue
        for field, values in derived[action].items():
            if row.get(field) != values:
                row[field] = values
                if action not in changed:
                    changed.append(action)
    return changed


def write_capability_action_derivations() -> None:
    catalog = load_contract_registry()
    changed = apply_capability_action_derivations(catalog)
    if not changed:
        return
    CONTRACT_REGISTRY_PATH.write_text(dump_json(catalog), encoding="utf-8", newline="\n")
    print(
        f"updated {CONTRACT_REGISTRY_PATH.relative_to(ROOT).as_posix()} "
        f"(derived capability action fields: {', '.join(changed)})"
    )


def check_capability_action_derivations() -> list[str]:
    catalog = load_contract_registry()
    derived = capability_action_derivations(catalog)
    errors: list[str] = []
    for row in capability_action_rows(catalog):
        action = row.get("action")
        if action not in derived:
            continue
        for field, values in derived[action].items():
            if row.get(field) != values:
                errors.append(
                    f"derived capability action drift: {action}.{field} does not match its rule "
                    "(run python tools/artifact_pipeline.py generate)"
                )
    return errors


def derived_id_wire_form(row: dict[str, Any], templates: dict[str, Any]) -> str | None:
    kind = row.get("kind")
    id_form = row.get("id_form")
    if not isinstance(kind, str) or not kind:
        return None
    template = templates.get(id_form)
    if not isinstance(template, str):
        return None
    return template.replace("<kind>", kind)


def write_id_wire_form_derivations() -> None:
    catalog = load_contract_registry()
    section = catalog.get("id_kind_registry")
    rows = section.get("id_kinds") if isinstance(section, dict) else None
    templates = section.get("wire_form_generation") if isinstance(section, dict) else None
    if not isinstance(rows, list) or not isinstance(templates, dict):
        raise SystemExit("contract registry missing id_kind_registry wire-form inputs")
    changed: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        expected = derived_id_wire_form(row, templates)
        if expected is not None and row.get("wire_form") != expected:
            row["wire_form"] = expected
            changed.append(str(row.get("kind")))
    if not changed:
        return
    CONTRACT_REGISTRY_PATH.write_text(dump_json(catalog), encoding="utf-8", newline="\n")
    print(
        f"updated {CONTRACT_REGISTRY_PATH.relative_to(ROOT).as_posix()} "
        f"(derived ID wire forms: {', '.join(changed)})"
    )


def check_id_wire_form_derivations() -> list[str]:
    catalog = load_contract_registry()
    section = catalog.get("id_kind_registry")
    rows = section.get("id_kinds") if isinstance(section, dict) else None
    templates = section.get("wire_form_generation") if isinstance(section, dict) else None
    if not isinstance(rows, list) or not isinstance(templates, dict):
        return ["contract registry missing id_kind_registry wire-form inputs"]
    errors: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        expected = derived_id_wire_form(row, templates)
        if expected is not None and row.get("wire_form") != expected:
            errors.append(
                f"derived ID wire-form drift: {row.get('kind')}.wire_form must equal {expected!r} "
                "(run python tools/artifact_pipeline.py generate)"
            )
    return errors


def generated_registry_payloads(catalog: dict[str, Any]) -> dict[Path, dict[str, Any]]:
    version, generated_at = registry_generation_metadata(catalog)
    generated = catalog.get("derived_registry_views")
    if not isinstance(generated, list) or not generated:
        raise SystemExit("contract registry missing derived_registry_views")

    payloads: dict[Path, dict[str, Any]] = {}
    for row in generated:
        if not isinstance(row, dict):
            raise SystemExit("derived_registry_views rows must be objects")
        file_ref = row.get("file")
        section = row.get("section")
        if not isinstance(file_ref, str) or not file_ref:
            raise SystemExit("generated registry missing file")
        if not isinstance(section, str) or not section:
            raise SystemExit(f"generated registry {file_ref} missing section")
        section_payload = catalog.get(section)
        if not isinstance(section_payload, dict):
            raise SystemExit(f"contract registry missing section {section}")
        section_payload = copy.deepcopy(section_payload)
        if section == "event_kind_registry":
            cell_contracts = section_payload.pop("cell_contracts", None)
            if not isinstance(cell_contracts, dict):
                raise SystemExit("event_kind_registry missing cell_contracts object")
            event_rows = section_payload.get("event_kinds")
            if not isinstance(event_rows, list):
                raise SystemExit("event_kind_registry.event_kinds must be an array")
            known_kinds = {
                event_row.get("event_kind")
                for event_row in event_rows
                if isinstance(event_row, dict)
            }
            unknown_contracts = sorted(set(cell_contracts) - known_kinds)
            if unknown_contracts:
                raise SystemExit(
                    "cell_contracts references unknown event kinds: "
                    + ", ".join(unknown_contracts)
                )
            for event_row in event_rows:
                if not isinstance(event_row, dict):
                    continue
                event_kind = event_row.get("event_kind")
                contract = cell_contracts.get(event_kind)
                if contract is None:
                    continue
                if not isinstance(contract, dict):
                    raise SystemExit(f"cell contract for {event_kind} must be an object")
                overlapping = sorted(set(event_row) & set(contract))
                if overlapping:
                    raise SystemExit(
                        f"cell contract for {event_kind} overlaps inline fields: "
                        + ", ".join(overlapping)
                    )
                event_row.update(copy.deepcopy(contract))
        elif section == "id_kind_registry":
            templates = section_payload.get("wire_form_generation")
            id_rows = section_payload.get("id_kinds")
            if not isinstance(templates, dict) or not isinstance(id_rows, list):
                raise SystemExit("id_kind_registry requires wire_form_generation and id_kinds")
            for id_row in id_rows:
                if not isinstance(id_row, dict):
                    continue
                kind = id_row.get("kind")
                id_form = id_row.get("id_form")
                template = templates.get(id_form)
                if not isinstance(kind, str) or not isinstance(template, str):
                    raise SystemExit(f"cannot generate wire_form for id row {id_row!r}")
                id_row["wire_form"] = template.replace("<kind>", kind)
        path = ARTIFACTS / file_ref
        payload = {
            "version": version,
            "source_of_truth": False,
            "generated_at": generated_at,
            "generated_from": "registry/contract-registry.json",
            "generated_by": "tools/artifact_pipeline.py",
            **section_payload,
        }
        payloads[path] = preserve_artifact_metadata_when_semantics_match(path, payload)
    return payloads


def openapi_high_security_policy_block(catalog: dict[str, Any]) -> str:
    operation_registry = catalog.get("operation_registry")
    if not isinstance(operation_registry, dict):
        raise SystemExit("contract registry missing operation_registry")
    policy = operation_registry.get("high_security_session_authentication_policy")
    if not isinstance(policy, dict):
        raise SystemExit(
            "contract registry missing operation_registry.high_security_session_authentication_policy"
        )
    prefix = policy.get("applies_to_operation_id_prefix")
    protected_default = policy.get("protected_operation_default")
    public_operations = policy.get("unauthenticated_public_projection_operations")
    new_operation_rule = policy.get("new_operation_rule")
    if not isinstance(prefix, str) or not prefix:
        raise SystemExit("high-security policy prefix must be a non-empty string")
    if not isinstance(protected_default, str) or not protected_default:
        raise SystemExit("high-security policy protected default must be a non-empty string")
    if not isinstance(public_operations, list) or any(
        not isinstance(operation, str) or not operation for operation in public_operations
    ):
        raise SystemExit("high-security policy public operations must be non-empty strings")
    if not isinstance(new_operation_rule, str) or not new_operation_rule:
        raise SystemExit("high-security policy new-operation rule must be a non-empty string")
    lines = [
        f"{OPENAPI_HIGH_SECURITY_POLICY_KEY}:",
        f"  appliesToOperationIdPrefix: {prefix}",
        f"  protectedOperationDefault: {protected_default}",
        "  unauthenticatedPublicProjectionOperations:",
        *(f"  - {operation}" for operation in public_operations),
        "  newOperationsFailClosed: true",
    ]
    return "\n".join(lines) + "\n"


def projected_openapi_text(catalog: dict[str, Any]) -> str:
    text = OPENAPI_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"(?ms)^{re.escape(OPENAPI_HIGH_SECURITY_POLICY_KEY)}:\n.*?(?=^info:)"
    )
    replacement = openapi_high_security_policy_block(catalog)
    projected, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise SystemExit(
            f"{OPENAPI_PATH.relative_to(ROOT).as_posix()} must contain exactly one "
            f"{OPENAPI_HIGH_SECURITY_POLICY_KEY} block before info"
        )
    return projected


def write_openapi_policy_projection() -> None:
    projected = projected_openapi_text(load_contract_registry())
    OPENAPI_PATH.write_text(projected, encoding="utf-8", newline="\n")
    print(f"updated {OPENAPI_PATH.relative_to(ROOT).as_posix()} high-security policy projection")


def check_openapi_policy_projection() -> list[str]:
    actual = OPENAPI_PATH.read_text(encoding="utf-8")
    expected = projected_openapi_text(load_contract_registry())
    if actual == expected:
        return []
    return [
        "OpenAPI high-security session authentication policy drift: "
        f"{OPENAPI_PATH.relative_to(ROOT).as_posix()} "
        "(run python tools/artifact_pipeline.py generate)"
    ]


def resolve_schema_pointer(document: Any, fragment: str) -> Any:
    if not fragment or fragment == "#":
        return document
    if not fragment.startswith("#/"):
        raise KeyError(fragment)
    current = document
    for token in fragment[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        else:
            raise KeyError(fragment)
    return current


def resolve_json_pointer(document: Any, pointer: str) -> Any:
    """Resolve an RFC 6901 pointer used by classification-field-registry."""
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise KeyError(pointer)
    current = document
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise KeyError(pointer)
    return current


def classification_axis(field: str) -> tuple[str, str] | None:
    """Return (semantic stem, axis) for classification-bearing field names."""
    for suffix, axis in (
        ("_kinds", "kind"),
        ("_kind", "kind"),
        ("_types", "type"),
        ("_type", "type"),
        ("_classes", "class"),
        ("_class", "class"),
        ("_tiers", "tier"),
        ("_tier", "tier"),
    ):
        if field.endswith(suffix):
            return field[: -len(suffix)], axis
    if field in {"kind", "type", "class", "tier"}:
        return "", field
    return None


def closed_schema_values(
    schema_path: Path,
    document: Any,
    schema: Any,
    seen: set[tuple[str, str]] | None = None,
) -> set[Any] | None:
    """Resolve a finite enum/const set through local or artifact-schema refs."""
    if not isinstance(schema, dict):
        return None
    if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
        return set(schema["enum"])
    if "const" in schema:
        return {schema["const"]}
    if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
        return closed_schema_values(schema_path, document, schema["items"], seen)
    ref = schema.get("$ref")
    if isinstance(ref, str):
        ref_file, _, fragment = ref.partition("#")
        target_path = (schema_path.parent / ref_file).resolve() if ref_file else schema_path.resolve()
        key = (target_path.as_posix(), fragment)
        seen = seen or set()
        if key in seen or not target_path.exists():
            return None
        next_seen = seen | {key}
        target_document = load_json(target_path)
        try:
            target_schema = resolve_schema_pointer(
                target_document, f"#{fragment}" if fragment else "#"
            )
        except KeyError:
            return None
        return closed_schema_values(target_path, target_document, target_schema, next_seen)
    for combinator in ("oneOf", "anyOf"):
        branches = schema.get(combinator)
        if isinstance(branches, list) and branches:
            values: set[Any] = set()
            for branch in branches:
                branch_values = closed_schema_values(
                    schema_path, document, branch, set(seen or ())
                )
                if branch_values is None:
                    return None
                values.update(branch_values)
            return values
    return None


def _walk_schema_properties(
    node: Any, pointer: tuple[str, ...] = ()
) -> list[tuple[str, str, Any, dict[str, Any]]]:
    rows: list[tuple[str, str, Any, dict[str, Any]]] = []
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict):
            axes: dict[str, set[str]] = {}
            for field, field_schema in properties.items():
                field_pointer = "/" + "/".join(
                    part.replace("~", "~0").replace("/", "~1")
                    for part in pointer + ("properties", field)
                )
                axis = classification_axis(field)
                if axis is not None:
                    stem, axis_name = axis
                    axes.setdefault(stem, set()).add(axis_name)
                    rows.append((field_pointer, field, field_schema, properties))
            for stem, axis_names in axes.items():
                if len(axis_names) > 1:
                    rows.append(
                        (
                            "/" + "/".join(pointer + ("properties",)),
                            f"@mixed_axis:{stem}",
                            sorted(axis_names),
                            properties,
                        )
                    )
        for key, value in node.items():
            rows.extend(_walk_schema_properties(value, pointer + (key,)))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            rows.extend(_walk_schema_properties(value, pointer + (str(index),)))
    return rows


def classification_discipline_errors(
    schema_documents: dict[str, Any],
    executable_registries: dict[str, Any],
    registry: dict[str, Any],
) -> list[str]:
    """Apply the four naming-axis hard criteria to parsed artifact contexts."""
    errors: list[str] = []
    external_rows = registry.get("external_type_fields")
    class_rows = registry.get("closed_class_fields")
    tier_rows = registry.get("ordered_tier_fields")
    if not isinstance(external_rows, list):
        return ["classification-field-registry.external_type_fields must be an array"]
    if not isinstance(class_rows, list):
        errors.append("classification-field-registry.closed_class_fields must be an array")
        class_rows = []
    if not isinstance(tier_rows, list):
        errors.append("classification-field-registry.ordered_tier_fields must be an array")
        tier_rows = []

    external_schema_contexts: set[tuple[str, str]] = set()
    for index, row in enumerate(external_rows):
        ref = f"external_type_fields[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{ref} must be an object")
            continue
        for required in (
            "external_standard",
            "external_field_path",
            "round_trip_requirement",
        ):
            if not isinstance(row.get(required), str) or not row[required]:
                errors.append(f"{ref}.{required} must be a non-empty string")
        if row.get("dispatch_authority") != "external_standard":
            errors.append(f"{ref}.dispatch_authority must be external_standard")
        if row.get("arkret_extensions_allowed") is not False:
            errors.append(f"{ref}.arkret_extensions_allowed must be false")
        schema_ref = row.get("schema_ref")
        pointer = row.get("json_pointer")
        doc_ref = row.get("doc_ref")
        if isinstance(schema_ref, str):
            if not isinstance(pointer, str):
                errors.append(f"{ref}.json_pointer is required for schema_ref")
                continue
            document = schema_documents.get(schema_ref)
            if document is None:
                errors.append(f"{ref}.schema_ref does not resolve: {schema_ref}")
                continue
            try:
                resolve_json_pointer(document, pointer)
            except KeyError:
                errors.append(f"{ref}.json_pointer does not resolve: {schema_ref}#{pointer}")
            external_schema_contexts.add((schema_ref, pointer))
        elif isinstance(doc_ref, str):
            for required in ("heading_anchor", "block_anchor", "json_pointer"):
                if not isinstance(row.get(required), str) or not row[required]:
                    errors.append(f"{ref}.{required} is required for doc_ref")
        else:
            errors.append(f"{ref} must declare schema_ref or doc_ref")

    ordered_tiers: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(tier_rows):
        if not isinstance(row, dict) or not isinstance(row.get("field"), str):
            errors.append(f"ordered_tier_fields[{index}] must declare field")
            continue
        allowed = row.get("allowed_values")
        order = row.get("strict_order")
        if (
            not isinstance(allowed, list)
            or not allowed
            or not isinstance(order, list)
            or order != allowed
            or len(set(order)) != len(order)
            or not isinstance(row.get("comparison_semantics"), str)
            or not row["comparison_semantics"]
        ):
            errors.append(
                f"ordered_tier_fields[{index}] must declare one duplicate-free strict total order "
                "and comparison_semantics"
            )
        ordered_tiers[row["field"]] = row

    for schema_ref, document in schema_documents.items():
        schema_path = ARTIFACTS / schema_ref
        for pointer, field, field_schema, _ in _walk_schema_properties(document):
            if field.startswith("@mixed_axis:"):
                errors.append(
                    f"{schema_ref}#{pointer} mixes classification axes for stem "
                    f"{field.split(':', 1)[1]!r}: {field_schema}"
                )
                continue
            axis = classification_axis(field)
            if axis is None:
                continue
            _, axis_name = axis
            if axis_name == "type" and (schema_ref, pointer) not in external_schema_contexts:
                errors.append(
                    f"{schema_ref}#{pointer} uses type axis without an exact external-standard entry"
                )
            elif axis_name == "class":
                if closed_schema_values(schema_path, document, field_schema) is None:
                    errors.append(
                        f"{schema_ref}#{pointer} uses class axis without a finite closed value set"
                    )
            elif axis_name == "tier":
                tier = ordered_tiers.get(field)
                if tier is None:
                    errors.append(
                        f"{schema_ref}#{pointer} uses tier axis without strict-order metadata"
                    )
                else:
                    values = closed_schema_values(schema_path, document, field_schema)
                    if values is not None and values != set(tier["allowed_values"]):
                        errors.append(
                            f"{schema_ref}#{pointer} tier values do not match strict-order metadata"
                        )

    def walk_executable(value: Any, ref: str) -> None:
        if isinstance(value, dict):
            if value.get("kind") == "select":
                selector = value.get("selector")
                tail = selector.rsplit(".", 1)[-1] if isinstance(selector, str) else ""
                if tail != "kind" and not tail.endswith(("_kind", "_kinds")):
                    errors.append(
                        f"{ref}.selector must end in kind/_kind/_kinds, got {selector!r}"
                    )
            if "type" in value:
                errors.append(
                    f"{ref}.type is an Arkret executable mini-schema/DSL field; use kind or value_shape"
                )
            for key, child in value.items():
                walk_executable(child, f"{ref}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk_executable(child, f"{ref}/{index}")

    for registry_ref, document in executable_registries.items():
        walk_executable(document, registry_ref)
    return errors


def check_classification_discipline() -> list[str]:
    registry = load_json(CLASSIFICATION_FIELD_REGISTRY_PATH)
    schema_documents = {
        f"schemas/{path.name}": load_json(path)
        for path in sorted((ARTIFACTS / "schemas").glob("*.json"))
    }
    catalog = load_contract_registry()
    executable = {
        "registry/contract-registry.json#event_kind_registry": catalog.get(
            "event_kind_registry", {}
        )
    }
    errors = classification_discipline_errors(schema_documents, executable, registry)

    # Four fail-closed negative probes keep each criterion executable rather
    # than relying only on the current positive corpus.
    probes = [
        (
            {"schemas/probe.schema.json": {"properties": {}}},
            {"probe": {"kind": "select", "selector": "payload.share_class"}},
            registry,
            "selector must end",
        ),
        (
            {
                "schemas/probe.schema.json": {
                    "properties": {"output_class": {"type": "string"}}
                }
            },
            {},
            registry,
            "finite closed value set",
        ),
        (
            {
                "schemas/probe.schema.json": {
                    "properties": {"policy_type": {"enum": ["a", "b"]}}
                }
            },
            {},
            registry,
            "exact external-standard entry",
        ),
        (
            {
                "schemas/probe.schema.json": {
                    "properties": {"priority_tier": {"enum": ["low", "high"]}}
                }
            },
            {},
            registry,
            "strict-order metadata",
        ),
    ]
    for probe_schemas, probe_executable, probe_registry, expected in probes:
        probe_errors = classification_discipline_errors(
            probe_schemas, probe_executable, probe_registry
        )
        if not any(expected in error for error in probe_errors):
            errors.append(f"classification scanner negative probe did not reject {expected!r}")
    return errors


def _absolute_artifact_schema_ref(schema_path: Path, ref: str) -> tuple[Path, str, str]:
    ref_file, _, ref_fragment = ref.partition("#")
    target_path = (schema_path.parent / ref_file).resolve() if ref_file else schema_path.resolve()
    target_ref = target_path.relative_to(ARTIFACTS.resolve()).as_posix()
    if ref_fragment:
        target_ref += f"#{ref_fragment}"
    return target_path, ref_fragment, target_ref


def _schema_summary_node(
    schema_path: Path,
    document: Any,
    schema: Any,
    display_ref: str,
    seen: set[tuple[str, str]],
) -> dict[str, Any]:
    if not isinstance(schema, dict):
        schema = {}
    if isinstance(schema.get("$ref"), str) and set(schema.keys()) == {"$ref"}:
        ref = schema["$ref"]
        target_path, ref_fragment, target_ref = _absolute_artifact_schema_ref(schema_path, ref)
        key = (target_path.as_posix(), ref_fragment)
        if key not in seen:
            target_document = document if target_path == schema_path.resolve() else load_json(target_path)
            target_schema = resolve_schema_pointer(
                target_document,
                f"#{ref_fragment}" if ref_fragment else "#",
            )
            return _schema_summary_node(
                target_path,
                target_document,
                target_schema,
                target_ref,
                seen | {key},
            )

    one_of = schema.get("oneOf")
    if isinstance(one_of, list) and one_of:
        variants = [
            _schema_summary_node(schema_path, document, variant, display_ref, seen)
            for variant in one_of
        ]
        property_names: list[str] = []
        for variant in variants:
            for field in variant.get("properties", []):
                if field not in property_names:
                    property_names.append(field)
        required_sets = [set(variant.get("required", [])) for variant in variants]
        common_required = [
            field
            for field in property_names
            if required_sets and all(field in required for required in required_sets)
        ]
        return {
            "schema_ref": display_ref,
            "schema_kind": "oneOf",
            "required": common_required,
            "properties": property_names,
            "closed": all(variant.get("closed") is True for variant in variants),
            "variants": variants,
        }

    properties = schema.get("properties")
    required = schema.get("required")
    additional_properties = schema.get("additionalProperties")
    return {
        "schema_ref": display_ref,
        "schema_kind": schema.get("type") if isinstance(schema.get("type"), str) else None,
        "required": [field for field in required if isinstance(field, str)] if isinstance(required, list) else [],
        "properties": list(properties.keys()) if isinstance(properties, dict) else [],
        "closed": additional_properties is False,
    }


def schema_summary(schema_ref: str) -> dict[str, Any]:
    file_ref, _, fragment = schema_ref.partition("#")
    schema_path = (ARTIFACTS / file_ref).resolve()
    document = load_json(schema_path)
    schema = resolve_schema_pointer(document, f"#{fragment}" if fragment else "#")
    return _schema_summary_node(schema_path, document, schema, schema_ref, set())


def operation_schema_index_payload(catalog: dict[str, Any]) -> dict[str, Any]:
    version, generated_at = registry_generation_metadata(catalog)
    operation_registry = catalog.get("operation_registry")
    if not isinstance(operation_registry, dict):
        raise SystemExit("contract registry missing operation_registry")

    operations: list[dict[str, Any]] = []
    for row in operation_registry.get("operations", []):
        if not isinstance(row, dict):
            continue
        operation_id = row.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id:
            continue
        entry: dict[str, Any] = {
            "operation_id": operation_id,
            "success_shape_kind": row.get("success_shape_kind"),
        }
        request_schema_ref = row.get("request_schema_ref")
        if isinstance(request_schema_ref, str) and request_schema_ref:
            entry["request"] = schema_summary(request_schema_ref)
        response_schema_ref = row.get("response_schema_ref")
        if isinstance(response_schema_ref, str) and response_schema_ref:
            entry["response"] = schema_summary(response_schema_ref)
        if "request" in entry or "response" in entry:
            operations.append(entry)

    return {
        "version": version,
        "source_of_truth": False,
        "generated_at": generated_at,
        "generated_from": [
            "registry/contract-registry.json",
            "schemas/*.schema.json"
        ],
        "generated_by": "tools/artifact_pipeline.py",
        "description": "Generated DTO index for registered operations with request_schema_ref/response_schema_ref. JSON Schema files remain the canonical source; this report is a machine-readable summary for SDK/conformance tooling and prose drift review.",
        "operations": operations,
    }


def profile_summary_text() -> str:
    data = load_json(PROFILE_REGISTRY_PATH)
    if not isinstance(data, dict):
        raise SystemExit("invalid conformance profile registry")
    implementation_profiles = data.get("implementation_profiles", [])
    deployment_profiles = data.get("deployment_profiles", [])
    vector_groups = data.get("vector_groups", [])
    hardening_profiles = data.get("hardening_profiles", [])
    profile_requirements = data.get("profile_requirements", {})
    return (
        "profile summary: "
        f"{len(implementation_profiles)} implementation, "
        f"{len(deployment_profiles)} deployment, "
        f"{len(vector_groups)} vector-group, "
        f"{len(hardening_profiles)} hardening, "
        f"{len(profile_requirements)} requirement blocks"
    )


def registry_diff_summary_text() -> str:
    drifts = check_derived_registry_views()
    if not drifts:
        return "registry diff: clean"
    return f"registry diff: {len(drifts)} generated artifact drift(s)"


def print_contract_status() -> None:
    print("contract policy: active-contract checks only")
    print(profile_summary_text())
    print(registry_diff_summary_text())


def write_derived_registry_views() -> None:
    for path, payload in generated_registry_payloads(load_contract_registry()).items():
        path.write_text(dump_json(payload), encoding="utf-8", newline="\n")
        print(f"updated {path.relative_to(ROOT).as_posix()}")


def write_operation_schema_index() -> None:
    OPERATION_SCHEMA_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPERATION_SCHEMA_INDEX_PATH.write_text(
        dump_json(operation_schema_index_payload(load_contract_registry())),
        encoding="utf-8",
        newline="\n",
    )
    print(f"updated {OPERATION_SCHEMA_INDEX_PATH.relative_to(ROOT).as_posix()}")


def write_public_registry_snapshot() -> None:
    canonical_bytes = CONTRACT_REGISTRY_PATH.read_bytes()
    PUBLIC_V1.mkdir(parents=True, exist_ok=True)
    expected = set(public_registry_paths())
    for obsolete in sorted(PUBLIC_V1.glob("contract-registry-*.json")):
        if obsolete not in expected:
            obsolete.unlink()
            print(f"removed obsolete {obsolete.relative_to(ROOT).as_posix()}")
    for target in public_registry_paths():
        target.write_bytes(canonical_bytes)
        print(f"updated {target.relative_to(ROOT).as_posix()}")


def check_public_registry_snapshot() -> list[str]:
    expected_path = current_public_registry_path()
    present = sorted(PUBLIC_V1.glob("contract-registry-*.json"))
    errors: list[str] = []
    unexpected = [path for path in present if path != expected_path]
    for path in unexpected:
        errors.append(
            f"obsolete public registry snapshot: {path.relative_to(ROOT).as_posix()} "
            f"(current release tag requires {expected_path.name})"
        )
    if not expected_path.exists():
        errors.append(
            f"missing public registry snapshot {expected_path.relative_to(ROOT).as_posix()} "
            "(run python tools/artifact_pipeline.py generate)"
        )
        return errors
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", expected_path.relative_to(ROOT).as_posix()],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if tracked.returncode != 0:
        errors.append(
            f"public registry snapshot is not tracked by Git: "
            f"{expected_path.relative_to(ROOT).as_posix()}"
        )
    if expected_path.read_bytes() != CONTRACT_REGISTRY_PATH.read_bytes():
        errors.append(
            f"public registry snapshot drift: {expected_path.relative_to(ROOT).as_posix()} "
            "(run python tools/artifact_pipeline.py generate)"
        )
    return errors


def check_derived_registry_views() -> list[str]:
    errors: list[str] = []
    for path, payload in generated_registry_payloads(load_contract_registry()).items():
        expected = dump_json(payload)
        if not path.exists():
            errors.append(f"missing generated registry {path.relative_to(ROOT).as_posix()}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            errors.append(
                f"generated registry drift: {path.relative_to(ROOT).as_posix()} (run python tools/artifact_pipeline.py generate)"
            )
    return errors


def check_operation_schema_index() -> list[str]:
    errors: list[str] = []
    expected = dump_json(operation_schema_index_payload(load_contract_registry()))
    if not OPERATION_SCHEMA_INDEX_PATH.exists():
        errors.append(
            f"missing operation schema index {OPERATION_SCHEMA_INDEX_PATH.relative_to(ROOT).as_posix()} "
            "(run python tools/artifact_pipeline.py generate)"
        )
        return errors
    actual = OPERATION_SCHEMA_INDEX_PATH.read_text(encoding="utf-8")
    if actual != expected:
        errors.append(
            f"operation schema index drift: {OPERATION_SCHEMA_INDEX_PATH.relative_to(ROOT).as_posix()} "
            "(run python tools/artifact_pipeline.py generate)"
        )
    return errors


def run_lint() -> int:
    result = subprocess.run([sys.executable, "-m", LINT_MODULE], cwd=ROOT)
    return result.returncode


def run_prose_lint() -> int:
    result = subprocess.run([sys.executable, str(PROSE_LINT_SCRIPT)], cwd=ROOT)
    return result.returncode


def run_fixture_digest_check() -> int:
    result = subprocess.run([sys.executable, str(FIXTURE_DIGEST_SCRIPT)], cwd=ROOT)
    return result.returncode


def run_session_grant_kat_check() -> int:
    result = subprocess.run([sys.executable, str(SESSION_GRANT_KAT_SCRIPT)], cwd=ROOT)
    return result.returncode


def run_contact_round_kat_check() -> int:
    result = subprocess.run([sys.executable, str(CONTACT_ROUND_KAT_SCRIPT)], cwd=ROOT)
    return result.returncode


def run_artifact_version_check() -> int:
    result = subprocess.run([sys.executable, str(ARTIFACT_VERSION_SCRIPT)], cwd=ROOT)
    return result.returncode


def run_operation_completeness_report(mode: str) -> int:
    result = subprocess.run(
        [sys.executable, str(COMPLETENESS_REPORT_SCRIPT), mode], cwd=ROOT
    )
    return result.returncode


def run_event_reference_inventory(mode: str) -> int:
    result = subprocess.run(
        [sys.executable, str(EVENT_REFERENCE_INVENTORY_SCRIPT), mode], cwd=ROOT
    )
    return result.returncode


def run_payload_validator_profile_check() -> int:
    result = subprocess.run(
        [sys.executable, str(PAYLOAD_VALIDATOR_PROFILE_SCRIPT)], cwd=ROOT
    )
    return result.returncode


def run_event_kind_vector_gap_check() -> int:
    result = subprocess.run([sys.executable, str(EVENT_KIND_VECTOR_GAP_SCRIPT)], cwd=ROOT)
    return result.returncode


def run_property_presence_manifest(mode: str) -> int:
    result = subprocess.run(
        [sys.executable, str(PRESENCE_MANIFEST_SCRIPT), mode], cwd=ROOT
    )
    return result.returncode


def run_schema_consumer_coverage(mode: str) -> int:
    result = subprocess.run(
        [sys.executable, str(SCHEMA_COVERAGE_SCRIPT), mode], cwd=ROOT
    )
    return result.returncode


def run_operation_string_classification(mode: str) -> int:
    result = subprocess.run(
        [sys.executable, str(OPERATION_STRING_CLASSIFICATION_SCRIPT), mode], cwd=ROOT
    )
    return result.returncode


def run_operation_string_classification_test() -> int:
    result = subprocess.run(
        [sys.executable, str(OPERATION_STRING_CLASSIFICATION_TEST)], cwd=ROOT
    )
    return result.returncode


def run_long_text_schema_test() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "tools.test_long_text_schema"], cwd=ROOT
    )
    return result.returncode


def run_openapi_operation_selector(mode: str) -> int:
    result = subprocess.run(
        [sys.executable, str(OPENAPI_OPERATION_SELECTOR_SCRIPT), mode], cwd=ROOT
    )
    return result.returncode


def run_operation_closure_locks(mode: str) -> int:
    result = subprocess.run(
        [sys.executable, str(OPERATION_CLOSURE_LOCK_SCRIPT), mode], cwd=ROOT
    )
    return result.returncode


def cmd_generate(_: argparse.Namespace) -> int:
    write_capability_action_derivations()
    write_id_wire_form_derivations()
    write_openapi_policy_projection()
    selector_status = run_openapi_operation_selector("generate")
    closure_status = run_operation_closure_locks("generate")
    write_derived_registry_views()
    write_operation_schema_index()
    write_public_registry_snapshot()
    completeness_status = run_operation_completeness_report("generate")
    event_reference_status = run_event_reference_inventory("generate")
    presence_status = run_property_presence_manifest("generate")
    coverage_status = run_schema_consumer_coverage("generate")
    string_classification_status = run_operation_string_classification("generate")
    print_contract_status()
    return (
        selector_status
        or closure_status
        or completeness_status
        or event_reference_status
        or presence_status
        or coverage_status
        or string_classification_status
    )


def cmd_check(_: argparse.Namespace) -> int:
    errors = check_capability_action_derivations()
    errors.extend(check_id_wire_form_derivations())
    errors.extend(check_openapi_policy_projection())
    errors.extend(check_derived_registry_views())
    errors.extend(check_operation_schema_index())
    errors.extend(check_public_registry_snapshot())
    errors.extend(check_classification_discipline())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print("contract policy: active-contract checks only")
        print(profile_summary_text())
        print(f"registry diff: {len(errors)} pre-lint pipeline error(s)")
        return 1
    print_contract_status()
    checks = (
        lambda: run_openapi_operation_selector("check"),
        lambda: run_operation_closure_locks("check"),
        lambda: run_operation_completeness_report("check"),
        lambda: run_event_reference_inventory("check"),
        run_payload_validator_profile_check,
        run_event_kind_vector_gap_check,
        lambda: run_property_presence_manifest("check"),
        lambda: run_schema_consumer_coverage("check"),
        lambda: run_operation_string_classification("check"),
        run_operation_string_classification_test,
        run_long_text_schema_test,
        run_fixture_digest_check,
        run_session_grant_kat_check,
        run_contact_round_kat_check,
        run_artifact_version_check,
        run_lint,
        run_prose_lint,
    )
    statuses = tuple(check() for check in checks)
    return int(any(statuses))


def cmd_snapshot(_: argparse.Namespace) -> int:
    write_public_registry_snapshot()
    return 0


def cmd_refresh_operation_closure_locks(_: argparse.Namespace) -> int:
    return run_operation_closure_locks("refresh-candidate")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser(
        "generate",
        help="regenerate derived registry views from contract-registry.json",
    )
    generate_parser.set_defaults(func=cmd_generate)

    check_parser = subparsers.add_parser(
        "check",
        help="check generated registries and run artifact lint",
    )
    check_parser.set_defaults(func=cmd_check)

    snapshot_parser = subparsers.add_parser(
        "snapshot",
        help="write the committed version-pinned public registry snapshot under site/public/v1",
    )
    snapshot_parser.set_defaults(func=cmd_snapshot)

    refresh_closure_parser = subparsers.add_parser(
        "refresh-operation-closure-locks",
        help=(
            "explicitly replace operation closure locks while the canonical "
            "spec release tag is candidate"
        ),
    )
    refresh_closure_parser.set_defaults(func=cmd_refresh_operation_closure_locks)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
