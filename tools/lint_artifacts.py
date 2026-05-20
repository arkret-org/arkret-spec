#!/usr/bin/env python3
"""Lint Contrix artifact/registry consistency.

Canonical registries plus generated registry views under
``spec/v1/artifacts/registry`` define the machine-readable wire contract.
This script validates registry manifests, cross-artifact references, markdown
link integrity, selected JSON examples, and schema-declared fixtures.

The legacy ``zh/`` mirror integrity check has been removed: machine artifacts
are no longer copied into the prose tree. The site renders them directly.
"""

from __future__ import annotations

import json
import base64
import hashlib
import re
import sys
import warnings
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError:  # pragma: no cover - CI installs the dependency.
    yaml = None

try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from jsonschema import Draft202012Validator, RefResolver
except ImportError:  # pragma: no cover - CI installs the dependency.
    Draft202012Validator = None
    RefResolver = None


ROOT = Path(__file__).resolve().parents[1]
SPEC_ROOT = ROOT / "spec" / "v1"
ARTIFACTS = SPEC_ROOT / "artifacts"

EVENT_KIND_TOKEN_RE = re.compile(r"\bcx\.[a-z0-9_]+(?:\.[a-z0-9_]+)+\b")
OPERATION_ID_RE = re.compile(r"^cx\.[a-z0-9_]+(?:\.[a-z0-9_]+)+$")
SCHEMA_ID_RE = re.compile(r"^cx\.schema\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\.v[0-9]+$")
SCHEMA_ID_TOKEN_RE = re.compile(r"\bcx\.schema\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\.v[0-9]+\b")
PROFILE_ID_RE = re.compile(r"^cx\.profile\.[a-z0-9][a-z0-9_.-]*\.v[0-9]+$")
PROFILE_ID_TOKEN_RE = re.compile(r"\bcx\.profile\.[a-z0-9][a-z0-9_.-]*\.v[0-9]+\b")
VECTOR_ID_TOKEN_RE = re.compile(r"\bcx\.vector\.[a-z0-9_.-]+\.v[0-9]+\b")
TYPED_ID_TOKEN_RE = re.compile(r"\bcx:([a-z0-9_]+):([A-Za-z0-9._~=-]+(?::[A-Za-z0-9._~=-]+)*)")
UUID7_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
OPENAPI_OPERATION_ID_RE = re.compile(r"^\s*operationId:\s*([A-Za-z0-9_.-]+)\s*$", re.MULTILINE)
YAML_REF_RE = re.compile(r"\$ref:\s*['\"]?([^'\"\s#]+(?:#[^'\"\s]+)?)")
JSON_FENCE_RE = re.compile(r"```json(?P<meta>[^\n`]*)\n(?P<body>.*?)```", re.IGNORECASE | re.DOTALL)
JSON_FENCE_SCHEMA_ATTR_RE = re.compile(r"\bschema=(?:\"([^\"]+)\"|'([^']+)'|([^\s]+))")
TYPED_ID_PREFIX_TOKEN_RE = re.compile(r"\bcx:([a-z0-9_]+):")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+(?:#[^)]+)?)\)")
TEXT_ARTIFACT_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])("
    r"zh/[A-Za-z0-9_./-]+\.mdx?|"
    r"schemas/[A-Za-z0-9_./-]+\.json|"
    r"artifacts/[A-Za-z0-9_./-]+(?:\.json|\.yaml|\.yml|\.md)"
    r")"
)
STABLE_SECTION_PLACEHOLDER_RE = re.compile(r"(?:§\s*\d+\.x|§\s*x|^#{2,6}\s+\d+\.x\b)", re.IGNORECASE)
OPERATION_COUNT_RE = re.compile(r"(\d+)\s*条\s*operation(?:_id)?", re.IGNORECASE)
TRUST_DOMAIN_JSON_DID_RE = re.compile(r'"trust_domain"\s*:\s*"did:')
LEGACY_DID_METHOD_REGEX_RE = re.compile(r"\^did:\[a-z0-9:[.\-_\\]+")

SECURITY_CLOSURE_VECTOR_IDS = {
    "cx.vector.federation.idempotency_after_key_revoke.v1",
    "cx.vector.webrtc.media_plaintext_downgrade.v1",
    "cx.vector.identity_link.eager_invalidation.v1",
    "cx.vector.identity_link.policy_tightening_invalidation.v1",
    "cx.vector.late_key_recovery.removed_actor.v1",
    "cx.vector.invite.oob_code_entropy.v1",
    "cx.vector.invite.failure_indistinguishable.v1",
    "cx.vector.consent.scope_cascade.v1",
    "cx.vector.consent.cache_invalidation.v1",
    "cx.vector.sync.soft_fail_reconcile.v1",
    "cx.vector.lattice.lww_open_set.v1",
    "cx.vector.e2ee_relaxed.window_exceeds_ceiling.v1",
}

FULL_MARKDOWN_EXAMPLE_SCHEMAS = {
    "spec/v1/zh/models/realm-and-space.md": {
        1: "schemas/realm.schema.json",
        2: "schemas/space.schema.json",
    },
    "spec/v1/zh/models/flow-and-message.md": {
        1: "schemas/flow.schema.json",
        4: "schemas/message.schema.json",
    },
    "spec/v1/zh/models/morph.md": {
        1: "schemas/morph.schema.json",
    },
    "spec/v1/zh/models/relation.md": {
        1: "schemas/relation.schema.json",
    },
    "spec/v1/zh/models/event-and-patch.md": {
        1: "schemas/event-schema.json",
    },
    "spec/v1/zh/authz/capabilities.md": {
        1: "schemas/capability-grant.schema.json",
    },
}


class Lint:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            return str(path)

    def fail(self, path: Path, message: str) -> None:
        self.errors.append(f"{self.rel(path)}: {message}")


def load_json(lint: Lint, path: Path) -> Any:
    try:
        return parse_json_text(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - exact parser errors vary
        lint.fail(path, f"invalid JSON: {exc}")
        return None


def load_yaml(lint: Lint, path: Path) -> Any:
    if yaml is None:
        lint.fail(path, "PyYAML is required for OpenAPI lint; install pyyaml")
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - exact parser errors vary
        lint.fail(path, f"invalid YAML: {exc}")
        return None


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON numeric literal {value!r}")


def reject_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def parse_json_text(text: str) -> Any:
    data = json.loads(
        text,
        object_pairs_hook=reject_duplicate_object,
        parse_constant=reject_json_constant,
    )
    reject_lone_surrogates(data)
    return data


def reject_lone_surrogates(value: Any, json_path: str = "$") -> None:
    if isinstance(value, str):
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError(f"lone surrogate in string at {json_path}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_lone_surrogates(child, f"{json_path}[{index}]")
    elif isinstance(value, dict):
        for key, child in value.items():
            reject_lone_surrogates(key, f"{json_path}.<key>")
            reject_lone_surrogates(child, f"{json_path}.{key}")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def base64url_text(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).rstrip(b"=").decode("ascii")


def walk_json(value: Any, json_path: str = "$") -> Iterable[tuple[str, Any, str | None]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{json_path}.{key}"
            yield child_path, child, key
            yield from walk_json(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{json_path}[{index}]"
            yield child_path, child, None
            yield from walk_json(child, child_path)


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


def split_ref(ref: str) -> str:
    return ref.split("#", 1)[0]


def ensure_relative_file(lint: Lint, owner: Path, base: Path, ref: str, label: str) -> Path | None:
    if ref.startswith("#"):
        return None
    ref_path = split_ref(ref)
    if not ref_path:
        return None
    target = (base / ref_path).resolve()
    try:
        target.relative_to(ROOT.resolve())
    except ValueError:
        lint.fail(owner, f"{label} escapes repository: {ref}")
        return None
    if not target.exists():
        lint.fail(owner, f"{label} target does not exist: {ref}")
    return target


def json_string_tokens(data: Any, regex: re.Pattern[str]) -> set[str]:
    tokens: set[str] = set()
    if isinstance(data, str):
        tokens.update(regex.findall(data))
    elif isinstance(data, list):
        for item in data:
            tokens.update(json_string_tokens(item, regex))
    elif isinstance(data, dict):
        for key, value in data.items():
            tokens.update(regex.findall(key))
            tokens.update(json_string_tokens(value, regex))
    return tokens


def raw_artifact_files() -> list[Path]:
    files: list[Path] = []
    for pattern in ("**/*.json", "**/*.yaml", "**/*.yml", "README.md"):
        files.extend(ARTIFACTS.glob(pattern))
    return sorted({path for path in files if path.is_file()})


def all_json_files() -> list[Path]:
    return sorted(ARTIFACTS.glob("**/*.json"))


def markdown_files() -> list[Path]:
    roots = [ROOT / "README.md", ARTIFACTS / "README.md"]
    roots.extend(sorted((SPEC_ROOT / "zh").rglob("*.md")))
    return [path for path in roots if path.is_file()]


# Wire field names that were renamed during v1 schema evolution.
# Each entry maps the legacy field name to:
#   - replacement: human-readable description of the new shape
#   - context_tokens: substrings whose presence on the SAME line marks the
#     occurrence as legitimate migration commentary (not a regression).
# Adding a token here is preferred to wholesale whitelisting a file.
LEGACY_WIRE_FIELDS: dict[str, dict[str, Any]] = {
    "auth_refs": {
        "replacement": "refs[role=authorized_by]",
        "context_tokens": [
            # English migration tokens
            "dropped",
            "removed",
            "former",
            "replaces",
            "renamed",
            "deprecated",
            "legacy",
            # Chinese migration tokens
            "替代",
            "替换",
            "迁移",
            "早期",
            "草案",
            "曾",
            "旧 ",
            "旧`",
            "旧 `",
            "旧auth_refs",
            "已合并",
            "已收敛",
            "废弃",
            "字段名",
        ],
    },
}


def check_legacy_wire_fields(lint: Lint) -> None:
    """Reject lingering deprecated wire field names outside of migration notes.

    A bare ``auth_refs`` token in prose or JSON example will cause SDK / reducer
    implementations to either generate envelopes that the canonical schema
    rejects (since ``auth_refs`` is no longer a defined property) or split the
    authorization-dependency surface between two field names. Any legitimate
    discussion of the legacy field must explicitly call it out as such; this
    check uses a context-token allow-list (see ``LEGACY_WIRE_FIELDS``).
    """
    scan_paths: list[Path] = list(markdown_files())
    scan_paths.extend(p for p in all_json_files() if ARTIFACTS in p.parents)
    seen: set[tuple[Path, int]] = set()
    for path in scan_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for field, info in LEGACY_WIRE_FIELDS.items():
                if field not in line:
                    continue
                if any(tok in line for tok in info["context_tokens"]):
                    continue
                key = (path, line_no)
                if key in seen:
                    continue
                seen.add(key)
                lint.fail(
                    path,
                    f"line {line_no}: legacy wire field `{field}` appears without "
                    f"migration context — use `{info['replacement']}` instead, "
                    f"or add a migration-context token "
                    f"(e.g. 替代/迁移/dropped/replaces) on the same line.",
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
            elif not generated_from.startswith("registry/"):
                lint.fail(path, f"registries[{index}].generated_from must stay inside artifacts/registry: {generated_from}")
            elif not (ARTIFACTS / generated_from).exists():
                lint.fail(path, f"registries[{index}].generated_from does not exist: {generated_from}")
        if not isinstance(description, str) or not description.strip():
            lint.fail(path, f"registries[{index}].description must be a non-empty string")

    for file_ref, row in entries_by_file.items():
        if row.get("source_role") != "generated":
            continue
        generated_from = row.get("generated_from")
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

def check_markdown_links(lint: Lint) -> None:
    for path in markdown_files():
        text = path.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK_RE.findall(text):
            if not target or target.startswith("#"):
                continue
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            target_path = split_ref(target)
            if not target_path:
                continue
            resolved = (path.parent / target_path).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                lint.fail(path, f"markdown link escapes repository: {target}")
                continue
            if not resolved.exists():
                lint.fail(path, f"markdown link target does not exist: {target}")




def check_registries(lint: Lint) -> dict[str, set[str]]:
    event_path = ARTIFACTS / "registry" / "event-kind-registry.json"
    schema_path = ARTIFACTS / "registry" / "schema-registry.json"
    id_path = ARTIFACTS / "registry" / "id-kind-registry.json"
    operation_path = ARTIFACTS / "registry" / "operation-registry.json"
    profile_path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    constraint_schema_path = ARTIFACTS / "schemas" / "grant-constraint.schema.json"

    event_registry = load_json(lint, event_path) or {}
    schema_registry = load_json(lint, schema_path) or {}
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
    kind_pattern = re.compile(event_registry.get("kind_pattern", r"^cx\.[a-z0-9_]+(\.[a-z0-9_]+)*$"))
    wire_scopes = set((event_registry.get("wire_scope_definitions") or {}).keys())
    for row in event_by_kind.values():
        kind = row["event_kind"]
        if not kind_pattern.fullmatch(kind):
            lint.fail(event_path, f"event_kind does not match kind_pattern: {kind}")
        wire_scope = row.get("wire_scope")
        if wire_scope not in wire_scopes:
            lint.fail(event_path, f"{kind} has unknown wire_scope {wire_scope!r}")

    schema_rows = schema_registry.get("schemas", [])
    schema_ids = unique_values(lint, schema_path, schema_rows, "schema_id")
    for row in schema_rows if isinstance(schema_rows, list) else []:
        if not isinstance(row, dict):
            continue
        schema_id = row.get("schema_id")
        file_ref = row.get("file")
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
            load_json(lint, target)

    id_rows = id_registry.get("id_kinds", [])
    id_kinds = unique_values(lint, id_path, id_rows, "kind")
    for row in id_rows if isinstance(id_rows, list) else []:
        if not isinstance(row, dict):
            continue
        kind = row.get("kind")
        wire_form = row.get("wire_form")
        if isinstance(kind, str) and not re.fullmatch(r"[a-z0-9_]+", kind):
            lint.fail(id_path, f"id kind has invalid format: {kind}")
        if isinstance(kind, str) and isinstance(wire_form, str) and not wire_form.startswith(f"cx:{kind}:"):
            lint.fail(id_path, f"{kind} wire_form must start with cx:{kind}:")

    special_id_kinds = unique_values(lint, id_path, id_registry.get("special_forms", []), "kind")

    operation_rows = operation_registry.get("operations", [])
    operation_ids = unique_values(lint, operation_path, operation_rows, "operation_id")
    operation_http_map: dict[str, str] = {}
    operation_grpc_map: dict[str, str] = {}
    operation_mq_map: dict[str, str] = {}
    for operation_id in operation_ids:
        if not OPERATION_ID_RE.fullmatch(operation_id):
            lint.fail(operation_path, f"operation_id has invalid format: {operation_id}")
    for row in operation_rows if isinstance(operation_rows, list) else []:
        if not isinstance(row, dict):
            continue
        operation_id = row.get("operation_id")
        if not isinstance(operation_id, str) or operation_id not in operation_ids:
            continue
        http = row.get("http")
        grpc = row.get("grpc")
        mq = row.get("mq")
        if not isinstance(http, str) or not http:
            lint.fail(operation_path, f"{operation_id} missing http binding")
        else:
            operation_http_map[operation_id] = http
        if not isinstance(grpc, str) or not grpc:
            lint.fail(operation_path, f"{operation_id} missing grpc binding")
        else:
            operation_grpc_map[operation_id] = grpc
        if not isinstance(mq, str) or not mq:
            lint.fail(operation_path, f"{operation_id} missing mq binding")
        else:
            operation_mq_map[operation_id] = mq

    capability_tiers = operation_registry.get("capability_tiers")
    surface_groups = operation_registry.get("surface_groups")
    assigned_operations: dict[str, str] = {}
    if not isinstance(capability_tiers, dict) or not capability_tiers:
        lint.fail(operation_path, "operation registry missing capability_tiers")
    if not isinstance(surface_groups, list) or not surface_groups:
        lint.fail(operation_path, "operation registry missing surface_groups")
    else:
        for index, row in enumerate(surface_groups):
            if not isinstance(row, dict):
                lint.fail(operation_path, f"surface_groups[{index}] must be an object")
                continue
            surface = row.get("surface")
            tier = row.get("tier")
            surface_operations = row.get("operations")
            if not isinstance(surface, str) or not surface:
                lint.fail(operation_path, f"surface_groups[{index}].surface must be a non-empty string")
                continue
            if not isinstance(tier, str) or (
                isinstance(capability_tiers, dict) and tier not in capability_tiers
            ):
                lint.fail(operation_path, f"surface_groups[{index}] has unknown tier {tier!r}")
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
    for _, value, _ in walk_json(profile_registry):
        if isinstance(value, str) and value.startswith("cx.profile."):
            profiles.add(value)
            if not PROFILE_ID_RE.fullmatch(value):
                lint.fail(profile_path, f"profile id has invalid format: {value}")

    constraint_types: set[str] = set()
    constraint_type_schema = (
        constraint_schema.get("properties", {})
        if isinstance(constraint_schema, dict)
        else {}
    ).get("constraint_type", {})
    enum_values = constraint_type_schema.get("enum") if isinstance(constraint_type_schema, dict) else None
    if isinstance(enum_values, list):
        constraint_types = {item for item in enum_values if isinstance(item, str)}
    if not constraint_types:
        lint.fail(constraint_schema_path, "constraint_type enum must be non-empty")

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
        "schema_ids": schema_ids,
        "id_kinds": id_kinds,
        "special_id_kinds": special_id_kinds,
        "operation_ids": operation_ids,
        "operation_http_map": operation_http_map,
        "operation_grpc_map": operation_grpc_map,
        "operation_mq_map": operation_mq_map,
        "profiles": profiles,
        "constraint_types": constraint_types,
    }


def check_schema_refs(lint: Lint, known: dict[str, set[str]]) -> None:
    for path in all_json_files():
        data = load_json(lint, path)
        if data is None:
            continue
        if path.name != "event-envelope-negative-fixture.json":
            check_event_ref_invariants_in_value(lint, path, "$", data)
        for json_path, value, key in walk_json(data):
            if key == "$ref" and isinstance(value, str):
                ensure_relative_file(lint, path, path.parent, value, f"{json_path} $ref")
        for schema_id in json_string_tokens(data, SCHEMA_ID_TOKEN_RE):
            if schema_id not in known["schema_ids"]:
                lint.fail(path, f"unknown schema id reference: {schema_id}")
        for profile_id in json_string_tokens(data, PROFILE_ID_TOKEN_RE):
            if profile_id not in known["profiles"]:
                lint.fail(path, f"unknown profile reference: {profile_id}")

    for yaml_path in sorted((ARTIFACTS / "openapi").glob("*.yaml")) + sorted((ARTIFACTS / "bindings").glob("*.yaml")):
        text = yaml_path.read_text(encoding="utf-8")
        for ref in YAML_REF_RE.findall(text):
            ensure_relative_file(lint, yaml_path, yaml_path.parent, ref, "$ref")
        for schema_id in SCHEMA_ID_TOKEN_RE.findall(text):
            if schema_id not in known["schema_ids"]:
                lint.fail(yaml_path, f"unknown schema id reference: {schema_id}")
        for profile_id in PROFILE_ID_TOKEN_RE.findall(text):
            if profile_id not in known["profiles"]:
                lint.fail(yaml_path, f"unknown profile reference: {profile_id}")


def check_profile_requirements(lint: Lint, known: dict[str, set[str]]) -> None:
    path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    requirements = data.get("profile_requirements")
    if not isinstance(requirements, dict):
        lint.fail(path, "missing profile_requirements matrix")
        return

    declared_profiles: set[str] = set()
    for key in ("implementation_profiles", "deployment_profiles", "hardening_profiles", "vector_profiles"):
        values = data.get(key, [])
        if isinstance(values, list):
            declared_profiles.update(item for item in values if isinstance(item, str) and item.startswith("cx.profile."))

    for profile_id in sorted(declared_profiles - set(requirements.keys())):
        lint.fail(path, f"profile_requirements missing declared profile: {profile_id}")

    fixture_files = {fixture.name for fixture in (ARTIFACTS / "fixtures").glob("*.json")}
    required_keys = {
        "required_endpoints",
        "required_event_kinds",
        "rejected_event_kinds",
        "required_schemas",
        "required_fixtures",
        "optional_extensions",
        "feature_discovery",
    }

    for profile_id, requirement in requirements.items():
        if profile_id not in known["profiles"]:
            lint.fail(path, f"profile_requirements key is not a declared profile id: {profile_id}")
        if not isinstance(requirement, dict):
            lint.fail(path, f"{profile_id} requirement must be an object")
            continue
        for missing_key in sorted(required_keys - set(requirement.keys())):
            lint.fail(path, f"{profile_id} missing {missing_key}")

        for inherited in requirement.get("inherits", []):
            if inherited not in known["profiles"]:
                lint.fail(path, f"{profile_id} inherits unknown profile: {inherited}")

        for operation_id in requirement.get("required_endpoints", []):
            if operation_id not in known["operation_ids"]:
                lint.fail(path, f"{profile_id} requires unknown operation_id: {operation_id}")

        for event_kind in requirement.get("required_event_kinds", []):
            if isinstance(event_kind, str) and event_kind.startswith("wire_scope:"):
                continue
            if event_kind not in known["event_kinds"]:
                lint.fail(path, f"{profile_id} requires unknown Event.kind: {event_kind}")

        for event_kind in requirement.get("rejected_event_kinds", []):
            if isinstance(event_kind, str) and event_kind.startswith("wire_scope:"):
                scope = event_kind.split(":", 1)[1]
                if scope not in {"durable_event", "actor_private_event", "ephemeral_event"}:
                    lint.fail(path, f"{profile_id} rejects unknown wire_scope: {event_kind}")
                continue
            if event_kind not in known["event_kinds"]:
                lint.fail(path, f"{profile_id} rejects unknown Event.kind: {event_kind}")

        for schema_id in requirement.get("required_schemas", []):
            if schema_id not in known["schema_ids"]:
                lint.fail(path, f"{profile_id} requires unknown schema: {schema_id}")

        for constraint_type in requirement.get("required_constraint_types", []):
            if constraint_type not in known["constraint_types"]:
                lint.fail(path, f"{profile_id} requires invalid constraint_type: {constraint_type}")

        for fixture in requirement.get("required_fixtures", []):
            if fixture not in fixture_files:
                lint.fail(path, f"{profile_id} requires missing fixture: {fixture}")

        feature_discovery = requirement.get("feature_discovery")
        if not isinstance(feature_discovery, dict):
            lint.fail(path, f"{profile_id} feature_discovery must be an object")
        else:
            if not isinstance(feature_discovery.get("required"), list):
                lint.fail(path, f"{profile_id} feature_discovery.required must be a list")
            if not isinstance(feature_discovery.get("unsupported_optional"), str):
                lint.fail(path, f"{profile_id} feature_discovery.unsupported_optional must be a string")


def check_event_ref_invariants_in_value(lint: Lint, path: Path, json_path: str, value: Any) -> None:
    if isinstance(value, dict):
        event_id = value.get("event_id")
        if isinstance(event_id, str):
            for ref_key in ("prev_refs", "auth_refs"):
                refs = value.get(ref_key)
                if isinstance(refs, list) and event_id in refs:
                    lint.fail(path, f"{json_path}.{ref_key} contains its own event_id {event_id}")
        for key, child in value.items():
            check_event_ref_invariants_in_value(lint, path, f"{json_path}.{key}", child)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            check_event_ref_invariants_in_value(lint, path, f"{json_path}[{index}]", child)


def check_event_schema_coverage(lint: Lint, known: dict[str, set[str]]) -> None:
    path = ARTIFACTS / "schemas" / "event-schema.json"
    data = load_json(lint, path)
    if data is None:
        return

    event_schema_tokens: set[str] = set()
    for _, value, key in walk_json(data):
        if key == "const" and isinstance(value, str):
            event_schema_tokens.add(value)
        elif key == "enum" and isinstance(value, list):
            event_schema_tokens.update(item for item in value if isinstance(item, str))

    event_schema_kinds = {
        token
        for token in event_schema_tokens
        if token.startswith("cx.") and not SCHEMA_ID_RE.fullmatch(token) and not PROFILE_ID_RE.fullmatch(token)
    }
    for token in sorted(event_schema_kinds - known["event_kinds"]):
        lint.fail(path, f"event-schema enum references unregistered Event.kind: {token}")
    for token in sorted(known["active_durable_event_kinds"] - event_schema_kinds):
        lint.fail(path, f"active Event.kind missing from event-schema enum coverage: {token}")


def parse_openapi_operation_http_map(text: str) -> tuple[dict[str, str], list[str]]:
    mapping: dict[str, str] = {}
    errors: list[str] = []
    in_paths = False
    current_path: str | None = None
    current_method: str | None = None

    for line_no, line in enumerate(text.splitlines(), start=1):
        if not in_paths:
            if line.strip() == "paths:":
                in_paths = True
            continue
        if line and not line.startswith(" "):
            break

        path_match = re.match(r"^  (/[^:]+):\s*$", line)
        if path_match:
            current_path = path_match.group(1)
            current_method = None
            continue

        method_match = re.match(r"^    (get|post|put|patch|delete|head|options|trace):\s*$", line)
        if method_match and current_path is not None:
            current_method = method_match.group(1).upper()
            continue

        operation_match = re.match(r"^      operationId:\s*([A-Za-z0-9_.-]+)\s*$", line)
        if operation_match and current_path is not None and current_method is not None:
            operation_id = operation_match.group(1)
            http_binding = f"{current_method} {current_path}"
            previous = mapping.get(operation_id)
            if previous is not None and previous != http_binding:
                errors.append(
                    f"line {line_no}: operationId {operation_id} maps to multiple HTTP bindings: "
                    f"{previous} vs {http_binding}"
                )
            mapping[operation_id] = http_binding

    return mapping, errors


def check_openapi_contract_shape(lint: Lint, path: Path, text: str) -> None:
    for forbidden in ("structural skeleton", "placeholders", "placeholder", "_report.md"):
        if forbidden in text:
            lint.fail(path, f"OpenAPI must not reference unpublished or placeholder contract text: {forbidden}")

    in_paths = False
    current_path: str | None = None
    current_method: str | None = None
    current_operation_id: str | None = None
    has_request_body = False

    def finish_operation(line_no: int) -> None:
        if current_method in {"post", "put", "patch"} and not has_request_body:
            label = current_operation_id or f"{current_method.upper()} {current_path}"
            lint.fail(path, f"line {line_no}: write operation missing requestBody: {label}")

    for line_no, line in enumerate(text.splitlines(), start=1):
        if not in_paths:
            if line.strip() == "paths:":
                in_paths = True
            continue
        if line and not line.startswith(" "):
            finish_operation(line_no)
            break

        path_match = re.match(r"^  (/[^:]+):\s*$", line)
        if path_match:
            finish_operation(line_no)
            current_path = path_match.group(1)
            current_method = None
            current_operation_id = None
            has_request_body = False
            continue

        method_match = re.match(r"^    (get|post|put|patch|delete|head|options|trace):\s*$", line)
        if method_match and current_path is not None:
            finish_operation(line_no)
            current_method = method_match.group(1)
            current_operation_id = None
            has_request_body = False
            continue

        if current_method is None:
            continue
        operation_match = re.match(r"^      operationId:\s*([A-Za-z0-9_.-]+)\s*$", line)
        if operation_match:
            current_operation_id = operation_match.group(1)
        if re.match(r"^      requestBody:\s*$", line):
            has_request_body = True
        if re.match(r"^      headers:\s*$", line):
            label = current_operation_id or f"{current_method.upper()} {current_path}"
            lint.fail(path, f"line {line_no}: operation-level headers are invalid OpenAPI: {label}")

    if in_paths:
        finish_operation(line_no if "line_no" in locals() else 0)


def check_operation_surfaces(lint: Lint, known: dict[str, set[str]]) -> None:
    openapi_path = ARTIFACTS / "openapi" / "contrix-service-api.openapi.yaml"
    openapi_text = openapi_path.read_text(encoding="utf-8")
    check_openapi_contract_shape(lint, openapi_path, openapi_text)
    openapi_operation_ids = OPENAPI_OPERATION_ID_RE.findall(openapi_text)
    openapi_set = set(openapi_operation_ids)
    if len(openapi_operation_ids) != len(openapi_set):
        duplicates = sorted({item for item in openapi_operation_ids if openapi_operation_ids.count(item) > 1})
        lint.fail(openapi_path, f"duplicate operationId values: {', '.join(duplicates)}")
    for operation_id in sorted(openapi_set - known["operation_ids"]):
        lint.fail(openapi_path, f"operationId not registered: {operation_id}")
    for operation_id in sorted(known["operation_ids"] - openapi_set):
        lint.fail(openapi_path, f"registered operation_id missing from OpenAPI: {operation_id}")
    openapi_http_map, openapi_parse_errors = parse_openapi_operation_http_map(openapi_text)
    for error in openapi_parse_errors:
        lint.fail(openapi_path, error)
    for operation_id in sorted(known["operation_ids"]):
        expected_http = known["operation_http_map"].get(operation_id)
        actual_http = openapi_http_map.get(operation_id)
        if expected_http is None:
            continue
        if actual_http is None:
            lint.fail(openapi_path, f"operationId missing HTTP path/method mapping: {operation_id}")
        elif actual_http != expected_http:
            lint.fail(
                openapi_path,
                f"operationId HTTP binding mismatch for {operation_id}: "
                f"registry={expected_http!r}, openapi={actual_http!r}",
            )

    binding_path = ARTIFACTS / "bindings" / "non-http-bindings.yaml"
    binding_text = binding_path.read_text(encoding="utf-8")
    binding_operation_ids = set(EVENT_KIND_TOKEN_RE.findall(binding_text))
    for operation_id in sorted(binding_operation_ids - known["operation_ids"]):
        lint.fail(binding_path, f"non-HTTP binding references unregistered operation_id: {operation_id}")
    for operation_id in sorted(known["operation_ids"] - binding_operation_ids):
        lint.fail(binding_path, f"registered operation_id missing from non-HTTP bindings: {operation_id}")


def check_service_describe_alignment(lint: Lint) -> None:
    openapi_path = ARTIFACTS / "openapi" / "contrix-service-api.openapi.yaml"
    schema_path = ARTIFACTS / "schemas" / "service-describe.schema.json"
    openapi = load_yaml(lint, openapi_path)
    service_schema = load_json(lint, schema_path)
    if not isinstance(openapi, dict) or not isinstance(service_schema, dict):
        return

    component = (
        openapi.get("components", {})
        .get("schemas", {})
        .get("ServiceDescribe")
    )
    if not isinstance(component, dict):
        lint.fail(openapi_path, "components.schemas.ServiceDescribe missing")
        return

    openapi_required = set(component.get("required") or [])
    schema_required = set(service_schema.get("required") or [])
    for required_field in ("service_did", "trust_domain"):
        if required_field not in schema_required:
            lint.fail(schema_path, f"ServiceDescribe.required must include {required_field}")
        if required_field not in openapi_required:
            lint.fail(openapi_path, f"components.schemas.ServiceDescribe.required must include {required_field}")
    if "trust_domain" not in (service_schema.get("properties") or {}):
        lint.fail(schema_path, "ServiceDescribe.properties.trust_domain missing")
    if "trust_domain" not in (component.get("properties") or {}):
        lint.fail(openapi_path, "components.schemas.ServiceDescribe.properties.trust_domain missing")
    if openapi_required != schema_required:
        lint.fail(
            openapi_path,
            "ServiceDescribe.required differs from service-describe.schema.json: "
            f"openapi-only={sorted(openapi_required - schema_required)}, "
            f"schema-only={sorted(schema_required - openapi_required)}",
        )

    paths = openapi.get("paths")
    if not isinstance(paths, dict):
        return
    describe_paths = [
        "/server/describe",
        "/events/describe",
        "/identity/describe",
        "/sync/describe",
        "/directory/describe",
        "/applet/describe",
    ]
    for describe_path in describe_paths:
        response_schema = (
            paths.get(describe_path, {})
            .get("get", {})
            .get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema")
        )
        if response_schema != {"$ref": "#/components/schemas/ServiceDescribe"}:
            lint.fail(openapi_path, f"{describe_path} 200 response must reference ServiceDescribe")


def check_policy_check_alignment(lint: Lint) -> None:
    openapi_path = ARTIFACTS / "openapi" / "contrix-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return
    paths = openapi.get("paths")
    components = openapi.get("components", {}).get("schemas", {})
    if not isinstance(paths, dict) or not isinstance(components, dict):
        return
    if "/contrix/v1/check" in paths:
        lint.fail(openapi_path, "legacy /contrix/v1/check policy path must not be present; use /policy/check")

    policy_path = paths.get("/policy/check", {}).get("post", {})
    request_schema = (
        policy_path.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema")
    )
    response_schema = (
        policy_path.get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema")
    )
    if request_schema != {"$ref": "#/components/schemas/PolicyCheckRequest"}:
        lint.fail(openapi_path, "/policy/check requestBody must reference PolicyCheckRequest")
    if response_schema != {"$ref": "#/components/schemas/PolicyCheckResponse"}:
        lint.fail(openapi_path, "/policy/check 200 response must reference PolicyCheckResponse")

    request_component = components.get("PolicyCheckRequest")
    response_component = components.get("PolicyCheckResponse")
    if not isinstance(request_component, dict):
        lint.fail(openapi_path, "components.schemas.PolicyCheckRequest missing")
    elif "realm_id" not in set(request_component.get("required") or []):
        lint.fail(openapi_path, "PolicyCheckRequest.required must include realm_id")
    if not isinstance(response_component, dict):
        lint.fail(openapi_path, "components.schemas.PolicyCheckResponse missing")
    elif "bound_to" not in set(response_component.get("required") or []):
        lint.fail(openapi_path, "PolicyCheckResponse.required must include bound_to")


def check_text_reference_targets(lint: Lint) -> None:
    for path in raw_artifact_files():
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for match in TEXT_ARTIFACT_REF_RE.finditer(text):
            ref = match.group(1)
            if ref.startswith("zh/"):
                target = SPEC_ROOT / ref
            elif ref.startswith("schemas/"):
                target = ARTIFACTS / ref
            elif ref.startswith("artifacts/"):
                target = SPEC_ROOT / ref
            else:
                continue
            if not target.exists():
                lint.fail(path, f"text reference target does not exist: {ref}")


def check_cross_source_drift(lint: Lint, known: dict[str, set[str]]) -> None:
    scan_paths = markdown_files() + raw_artifact_files()
    active_event_kinds = sorted(known["active_event_kinds"], key=len, reverse=True)
    allowed_room_scoped = {
        (SPEC_ROOT / "zh" / "extensions" / "mimi-interop.md").resolve(),
    }
    operation_count = len(known["operation_ids"])

    for path in scan_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        resolved = path.resolve()
        for line_no, line in enumerate(text.splitlines(), start=1):
            if (
                re.search(r"\broom[- ]scoped\b", line, re.IGNORECASE)
                and resolved not in allowed_room_scoped
            ):
                lint.fail(path, f"line {line_no}: core docs/artifacts must not use room-scoped; use Realm-scoped")

            if STABLE_SECTION_PLACEHOLDER_RE.search(line):
                lint.fail(path, f"line {line_no}: placeholder section reference must be replaced with a stable heading or real section number")

            if "/contrix/v1/check" in line:
                lint.fail(path, f"line {line_no}: legacy policy path /contrix/v1/check must be replaced with /policy/check")

            if TRUST_DOMAIN_JSON_DID_RE.search(line):
                lint.fail(path, f"line {line_no}: trust_domain must use cx:trust_domain:<scope>, not a raw DID")

            if LEGACY_DID_METHOD_REGEX_RE.search(line):
                lint.fail(path, f"line {line_no}: DID regex must not allow ':'/'.'/'_' inside the method segment")

            for match in OPERATION_COUNT_RE.finditer(line):
                count = int(match.group(1))
                if count != operation_count:
                    lint.fail(path, f"line {line_no}: hard-coded operation count {count} differs from registry count {operation_count}")

            for event_kind in active_event_kinds:
                if re.search(rf"(?<![A-Za-z0-9_.-]){re.escape(event_kind)}\.v[0-9]+\b", line):
                    lint.fail(path, f"line {line_no}: active Event.kind {event_kind} must not be written with a .vN suffix")


def check_vector_reference_closure(lint: Lint) -> None:
    definition_paths = [
        SPEC_ROOT / "zh" / "conformance" / "conformance-vectors.md",
        *sorted((ARTIFACTS / "fixtures").glob("*.json")),
    ]
    known_vectors: set[str] = set()
    for path in definition_paths:
        if not path.is_file():
            continue
        try:
            known_vectors.update(VECTOR_ID_TOKEN_RE.findall(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    if not known_vectors:
        lint.fail(SPEC_ROOT / "zh" / "conformance" / "conformance-vectors.md", "no conformance vector ids found")
        return

    for path in markdown_files() + raw_artifact_files():
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for vector_id in sorted(set(VECTOR_ID_TOKEN_RE.findall(text))):
            if vector_id not in known_vectors:
                lint.fail(path, f"references undefined conformance vector id: {vector_id}")


def check_security_closure_vectors(lint: Lint) -> None:
    path = ARTIFACTS / "fixtures" / "security-closure-vectors.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    vectors = data.get("security_closure_vectors")
    if not isinstance(vectors, list) or not vectors:
        lint.fail(path, "security_closure_vectors must be a non-empty array")
        return

    conformance_path = SPEC_ROOT / "zh" / "conformance" / "conformance-vectors.md"
    try:
        defined_vectors = set(VECTOR_ID_TOKEN_RE.findall(conformance_path.read_text(encoding="utf-8")))
    except Exception as exc:
        lint.fail(conformance_path, f"could not read conformance vector definitions: {exc}")
        defined_vectors = set()

    seen: set[str] = set()
    for index, vector in enumerate(vectors):
        label = f"security_closure_vectors[{index}]"
        if not isinstance(vector, dict):
            lint.fail(path, f"{label} must be an object")
            continue

        vector_id = vector.get("vector_id")
        if not isinstance(vector_id, str) or not VECTOR_ID_TOKEN_RE.fullmatch(vector_id):
            lint.fail(path, f"{label}.vector_id must be a conformance vector id")
            continue
        if vector_id in seen:
            lint.fail(path, f"{label}.vector_id duplicates {vector_id}")
        seen.add(vector_id)
        if vector_id not in defined_vectors:
            lint.fail(path, f"{label}.vector_id is not defined in conformance-vectors.md: {vector_id}")
        if vector_id not in SECURITY_CLOSURE_VECTOR_IDS:
            lint.fail(path, f"{label}.vector_id is not part of the required security closure set: {vector_id}")

        steps = vector.get("steps")
        if not isinstance(steps, list) or not steps:
            lint.fail(path, f"{label}.steps must be a non-empty array")
            continue
        for step_index, step in enumerate(steps):
            step_label = f"{label}.steps[{step_index}]"
            if not isinstance(step, dict):
                lint.fail(path, f"{step_label} must be an object")
                continue
            if not isinstance(step.get("name"), str) or not step["name"]:
                lint.fail(path, f"{step_label}.name must be a non-empty string")
            if not isinstance(step.get("input"), dict):
                lint.fail(path, f"{step_label}.input must be an object")
            expected = step.get("expected")
            if not isinstance(expected, dict):
                lint.fail(path, f"{step_label}.expected must be an object")
                continue
            if not isinstance(expected.get("outcome"), str) or not expected["outcome"]:
                lint.fail(path, f"{step_label}.expected.outcome must be a non-empty string")
            if not any(key in expected for key in ("reason_code", "invariants", "response")):
                lint.fail(path, f"{step_label}.expected must include reason_code, invariants, or response")
            invariants = expected.get("invariants")
            if "invariants" in expected and (
                not isinstance(invariants, list)
                or not invariants
                or not all(isinstance(item, str) and item for item in invariants)
            ):
                lint.fail(path, f"{step_label}.expected.invariants must be a non-empty string array")
            runner = step.get("runner")
            if not isinstance(runner, dict):
                lint.fail(path, f"{step_label}.runner must be an object")
                continue
            required_runner_fields = {
                "given_state",
                "operation",
                "transcript",
                "expected_state_transition",
                "expected_external_response",
                "expected_audit_reason",
            }
            missing_runner_fields = sorted(required_runner_fields - set(runner))
            if missing_runner_fields:
                lint.fail(path, f"{step_label}.runner missing field(s): {', '.join(missing_runner_fields)}")
                continue
            for object_field in (
                "given_state",
                "transcript",
                "expected_state_transition",
                "expected_external_response",
            ):
                if not isinstance(runner.get(object_field), dict):
                    lint.fail(path, f"{step_label}.runner.{object_field} must be an object")
            for string_field in ("operation", "expected_audit_reason"):
                if not isinstance(runner.get(string_field), str) or not runner[string_field]:
                    lint.fail(path, f"{step_label}.runner.{string_field} must be a non-empty string")
            state_transition = runner.get("expected_state_transition")
            if isinstance(state_transition, dict) and state_transition.get("outcome") != expected.get("outcome"):
                lint.fail(
                    path,
                    f"{step_label}.runner.expected_state_transition.outcome must match expected.outcome",
                )
            external_response = runner.get("expected_external_response")
            reason_code = expected.get("reason_code")
            if isinstance(reason_code, str) and reason_code:
                external_reason = external_response.get("reason_code") if isinstance(external_response, dict) else None
                if external_reason != reason_code and runner.get("expected_audit_reason") != reason_code:
                    lint.fail(
                        path,
                        f"{step_label}.runner must carry expected.reason_code in external response or audit reason",
                    )

    missing = SECURITY_CLOSURE_VECTOR_IDS - seen
    for vector_id in sorted(missing):
        lint.fail(path, f"missing required security closure vector fixture: {vector_id}")


def check_typed_id_token(lint: Lint, path: Path, json_path: str, token_kind: str, rest: str, known: dict[str, set[str]]) -> None:
    if token_kind == "blob" and rest.startswith("sha256:"):
        if not SHA256_RE.fullmatch(rest):
            lint.fail(path, f"{json_path} has invalid cx:blob:sha256 reference")
        return
    if token_kind in known["id_kinds"]:
        candidate = rest[:36]
        if not UUID7_RE.fullmatch(candidate):
            lint.fail(path, f"{json_path} has invalid cx:{token_kind}: typed UUIDv7 reference")
        return
    if token_kind in known["special_id_kinds"]:
        if not rest:
            lint.fail(path, f"{json_path} has empty cx:{token_kind}: special reference")
        return
    lint.fail(path, f"{json_path} references unregistered typed ID kind: cx:{token_kind}:")


def check_fixtures(lint: Lint, known: dict[str, set[str]]) -> None:
    fixture_dir = ARTIFACTS / "fixtures"
    for path in sorted(fixture_dir.glob("*.json")):
        data = load_json(lint, path)
        if data is None:
            continue
        check_fixture_schema_validation_cases(lint, path, data)
        for json_path, value, key in walk_json(data):
            if key in {"auth_weight", "authority_class"}:
                lint.fail(path, f"{json_path} uses removed state-resolution authority field: {key}")

            if not isinstance(value, str):
                continue

            for schema_id in SCHEMA_ID_TOKEN_RE.findall(value):
                if schema_id not in known["schema_ids"]:
                    lint.fail(path, f"{json_path} references unknown schema id: {schema_id}")

            for profile_id in PROFILE_ID_TOKEN_RE.findall(value):
                if profile_id not in known["profiles"]:
                    lint.fail(path, f"{json_path} references unknown profile: {profile_id}")

            if (
                key in {"kind", "event_kind", "target_format"}
                and value.startswith("cx.")
                and not value.startswith("cx.content.")
            ):
                if value not in known["event_kinds"]:
                    lint.fail(path, f"{json_path} references unregistered Event.kind: {value}")

            if key in {"operation_id", "mapped_operation_id"} and value.startswith("cx."):
                if value not in known["operation_ids"]:
                    lint.fail(path, f"{json_path} references unregistered operation_id: {value}")
            if key == "call" and ".recovery.call" in json_path and value.startswith("cx."):
                if value not in known["operation_ids"]:
                    lint.fail(path, f"{json_path} references unregistered recovery operation_id: {value}")
            if key == "constraint_type" and value not in known["constraint_types"]:
                lint.fail(path, f"{json_path} uses invalid constraint_type: {value}")

            for match in TYPED_ID_TOKEN_RE.finditer(value):
                check_typed_id_token(lint, path, json_path, match.group(1), match.group(2), known)


def check_fixture_schema_validation_cases(lint: Lint, path: Path, data: Any) -> None:
    if not isinstance(data, dict):
        return
    cases = data.get("schema_validation_cases")
    if cases is None:
        return
    if not isinstance(cases, list) or not cases:
        lint.fail(path, "schema_validation_cases must be a non-empty array when present")
        return
    for index, case in enumerate(cases):
        label = f"schema_validation_cases[{index}]"
        if not isinstance(case, dict):
            lint.fail(path, f"{label} must be an object")
            continue
        schema_ref = case.get("schema_ref")
        instance = case.get("instance")
        expect_valid = case.get("expect_valid", True)
        if not isinstance(schema_ref, str) or not schema_ref:
            lint.fail(path, f"{label}.schema_ref must be a non-empty string")
            continue
        if "instance" not in case:
            lint.fail(path, f"{label}.instance is required")
            continue
        if not isinstance(expect_valid, bool):
            lint.fail(path, f"{label}.expect_valid must be boolean when present")
            continue
        case_name = case.get("name")
        if not isinstance(case_name, str) or not case_name:
            case_name = label
        check_json_instance_against_schema(lint, path, case_name, schema_ref, instance, expect_valid)


def check_crypto_signature_fixture(lint: Lint) -> None:
    path = ARTIFACTS / "fixtures" / "crypto-signature-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    vectors = data.get("vectors", [])
    if not isinstance(vectors, list):
        lint.fail(path, "vectors must be a list")
        return

    for index, vector in enumerate(vectors):
        if not isinstance(vector, dict):
            lint.fail(path, f"vectors[{index}] must be an object")
            continue

        event = vector.get("event_without_proofs")
        if isinstance(event, dict):
            signed_event = dict(event)
            signed_event.pop("unsigned", None)
            expected_canonical = canonical_json(signed_event)
            if vector.get("canonical_event_payload") != expected_canonical:
                lint.fail(path, f"vectors[{index}] canonical_event_payload does not match canonical JSON")
            expected_payload_hash = sha256_text(expected_canonical)
            if vector.get("payload_hash") != expected_payload_hash:
                lint.fail(path, f"vectors[{index}] payload_hash does not match canonical_event_payload")

            event_with_proof = vector.get("event_with_proof")
            if isinstance(event_with_proof, dict):
                unsigned = dict(event_with_proof)
                unsigned.pop("proofs", None)
                unsigned.pop("unsigned", None)
                if unsigned != signed_event:
                    lint.fail(path, f"vectors[{index}] event_with_proof without proofs differs from event_without_proofs")

        binding = vector.get("binding_object")
        if isinstance(binding, dict):
            expected_binding = canonical_json(binding)
            if vector.get("canonical_binding_payload") != expected_binding:
                lint.fail(path, f"vectors[{index}] canonical_binding_payload does not match canonical JSON")
            expected_binding_hash = sha256_text(expected_binding)
            if vector.get("binding_hash") != expected_binding_hash:
                lint.fail(path, f"vectors[{index}] binding_hash does not match canonical_binding_payload")
            if vector.get("detached_payload_b64u") != base64url_text(expected_binding):
                lint.fail(path, f"vectors[{index}] detached_payload_b64u does not match canonical_binding_payload")

        protected_header = vector.get("protected_header")
        if isinstance(protected_header, dict):
            expected_header = canonical_json(protected_header)
            if vector.get("protected_header_canonical") != expected_header:
                lint.fail(path, f"vectors[{index}] protected_header_canonical does not match canonical JSON")

        proof = vector.get("proof")
        if isinstance(proof, dict) and isinstance(vector.get("payload_hash"), str):
            if proof.get("payload_hash") != vector["payload_hash"]:
                lint.fail(path, f"vectors[{index}] proof payload_hash differs from vector payload_hash")


def is_placeholder_typed_id(rest: str) -> bool:
    return (
        "..." in rest
        or rest in {"id", "uuid", "example", "A", "B"}
        or rest.startswith("<")
        or rest.endswith(">")
    )


def check_markdown_json_value(lint: Lint, path: Path, json_path: str, value: Any, key: str | None, known: dict[str, set[str]]) -> None:
    if key in {"auth_weight", "authority_class"}:
        lint.fail(path, f"{json_path} markdown JSON uses removed state-resolution authority field: {key}")

    if isinstance(value, str):
        for schema_id in SCHEMA_ID_TOKEN_RE.findall(value):
            if schema_id not in known["schema_ids"]:
                lint.fail(path, f"{json_path} markdown JSON references unknown schema id: {schema_id}")
        for profile_id in PROFILE_ID_TOKEN_RE.findall(value):
            if profile_id not in known["profiles"]:
                lint.fail(path, f"{json_path} markdown JSON references unknown profile: {profile_id}")

        if (
            key in {"kind", "event_kind", "target_format"}
            and value.startswith("cx.")
            and not value.startswith("cx.content.")
        ):
            if value not in known["event_kinds"]:
                lint.fail(path, f"{json_path} markdown JSON references unregistered Event.kind: {value}")

        if key in {"operation_id", "mapped_operation_id", "operationId"} and value.startswith("cx."):
            if value not in known["operation_ids"]:
                lint.fail(path, f"{json_path} markdown JSON references unregistered operation_id: {value}")

        if key == "constraint_type" and value not in known["constraint_types"]:
            lint.fail(path, f"{json_path} markdown JSON uses invalid constraint_type: {value}")

        for match in TYPED_ID_TOKEN_RE.finditer(value):
            kind, rest = match.group(1), match.group(2)
            if is_placeholder_typed_id(rest):
                if kind not in known["id_kinds"] and kind not in known["special_id_kinds"]:
                    lint.fail(path, f"{json_path} markdown JSON references unregistered typed ID kind: cx:{kind}:")
                continue
            check_typed_id_token(lint, path, json_path, kind, rest, known)


def required_fields_from_schema(lint: Lint, schema_ref: str) -> list[str]:
    schema_path = ARTIFACTS / schema_ref
    schema = load_schema_document(lint, schema_path)
    if not isinstance(schema, dict):
        return []
    required = schema.get("required", [])
    if not isinstance(required, list):
        lint.fail(schema_path, "schema required must be an array")
        return []
    return [field for field in required if isinstance(field, str)]


def schema_ref_from_fence_meta(meta: str) -> str | None:
    match = JSON_FENCE_SCHEMA_ATTR_RE.search(meta)
    if not match:
        return None
    return next(group for group in match.groups() if group)


def resolve_artifact_schema_ref(lint: Lint, owner: Path, schema_ref: str) -> Path | None:
    schema_path_ref = split_ref(schema_ref)
    if Path(schema_path_ref).is_absolute() or ".." in Path(schema_path_ref).parts:
        lint.fail(owner, f"schema_ref escapes artifacts/: {schema_ref}")
        return None
    schema_path = (ARTIFACTS / schema_path_ref).resolve()
    try:
        schema_path.relative_to(ARTIFACTS.resolve())
    except ValueError:
        lint.fail(owner, f"schema_ref escapes artifacts/: {schema_ref}")
        return None
    if not schema_path.exists():
        lint.fail(owner, f"schema_ref target does not exist: {schema_ref}")
        return None
    return schema_path


def resolve_json_pointer(document: Any, fragment: str) -> Any:
    if fragment in {"", "#"}:
        return document
    if not fragment.startswith("#/"):
        raise ValueError(f"unsupported schema fragment {fragment!r}")
    current = document
    for raw_part in fragment[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise KeyError(part)
    return current


def load_json_schema_for_uri(uri: str) -> Any:
    prefix = "https://contrix.io/artifacts/"
    if not uri.startswith(prefix):
        raise ValueError(f"unsupported remote schema URI {uri}")
    path = ARTIFACTS / uri[len(prefix):]
    return parse_json_text(path.read_text(encoding="utf-8"))


def load_schema_document(lint: Lint, path: Path) -> Any:
    if path.suffix.lower() in {".yaml", ".yml"}:
        return load_yaml(lint, path)
    return load_json(lint, path)


def jsonschema_errors(lint: Lint, owner: Path, schema_ref: str, instance: Any) -> list[str]:
    if Draft202012Validator is None or RefResolver is None:
        lint.fail(owner, "jsonschema is required for declared schema validation; install jsonschema")
        return []
    schema_path = resolve_artifact_schema_ref(lint, owner, schema_ref)
    if schema_path is None:
        return []
    schema_document = load_schema_document(lint, schema_path)
    if not isinstance(schema_document, dict):
        return []
    fragment = "#" + schema_ref.split("#", 1)[1] if "#" in schema_ref else "#"
    try:
        schema = resolve_json_pointer(schema_document, fragment)
    except Exception as exc:
        lint.fail(owner, f"schema_ref fragment cannot be resolved: {schema_ref}: {exc}")
        return []
    if not isinstance(schema, dict):
        lint.fail(owner, f"schema_ref fragment is not an object schema: {schema_ref}")
        return []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        resolver = RefResolver(
            base_uri=schema_path.as_uri(),
            referrer=schema_document,
            handlers={
                "https": load_json_schema_for_uri,
            },
        )
        validator = Draft202012Validator(schema, resolver=resolver)
        errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    formatted: list[str] = []
    for error in errors:
        path_bits = ["$"]
        for bit in error.path:
            if isinstance(bit, int):
                path_bits[-1] = f"{path_bits[-1]}[{bit}]"
            else:
                path_bits.append(str(bit))
        formatted.append(".".join(path_bits) + ": " + error.message)
    return formatted


def check_json_instance_against_schema(
    lint: Lint,
    owner: Path,
    label: str,
    schema_ref: str,
    instance: Any,
    expect_valid: bool = True,
) -> None:
    errors = jsonschema_errors(lint, owner, schema_ref, instance)
    if expect_valid and errors:
        lint.fail(owner, f"{label} fails {schema_ref}: " + "; ".join(errors[:3]))
    if not expect_valid and not errors:
        lint.fail(owner, f"{label} expected to fail {schema_ref} but validated successfully")


def check_markdown_full_object_example(lint: Lint, path: Path, block_index: int, data: Any) -> None:
    if not isinstance(data, dict):
        return

    schema_ref = FULL_MARKDOWN_EXAMPLE_SCHEMAS.get(lint.rel(path), {}).get(block_index)
    if not schema_ref:
        return

    missing = [field for field in required_fields_from_schema(lint, schema_ref) if field not in data]
    if missing:
        lint.fail(
            path,
            f"json_block[{block_index}] full object example for {schema_ref} missing required field(s): "
            + ", ".join(missing),
        )

    if schema_ref not in {"schemas/event-schema.json", "schemas/capability-grant.schema.json"}:
        return

    proofs = data.get("proofs")
    if not isinstance(proofs, list) or not proofs:
        lint.fail(path, f"json_block[{block_index}] proof-bearing object must include non-empty proofs[]")
        return

    proof_required: list[str] = []
    event_schema = load_json(lint, ARTIFACTS / "schemas/event-schema.json")
    if isinstance(event_schema, dict):
        proof_schema = event_schema.get("$defs", {}).get("proof", {})
        required = proof_schema.get("required", []) if isinstance(proof_schema, dict) else []
        proof_required = [field for field in required if isinstance(field, str)]

    for proof_index, proof in enumerate(proofs):
        if not isinstance(proof, dict):
            lint.fail(path, f"json_block[{block_index}].proofs[{proof_index}] must be an object")
            continue
        missing_proof = [field for field in proof_required if field not in proof]
        if missing_proof:
            lint.fail(
                path,
                f"json_block[{block_index}].proofs[{proof_index}] missing required field(s): "
                + ", ".join(missing_proof),
            )


def check_markdown_examples(lint: Lint, known: dict[str, set[str]]) -> None:
    for path in markdown_files():
        text = path.read_text(encoding="utf-8")

        if "cx.moderation.policy_action" in text:
            lint.fail(path, "markdown references removed Event.kind cx.moderation.policy_action; use cx.policy.action")

        for schema_id in SCHEMA_ID_TOKEN_RE.findall(text):
            if schema_id not in known["schema_ids"]:
                lint.fail(path, f"markdown references unknown schema id: {schema_id}")
        for profile_id in PROFILE_ID_TOKEN_RE.findall(text):
            if profile_id not in known["profiles"]:
                lint.fail(path, f"markdown references unknown profile: {profile_id}")

        for prefix_match in TYPED_ID_PREFIX_TOKEN_RE.finditer(text):
            kind = prefix_match.group(1)
            if kind not in known["id_kinds"] and kind not in known["special_id_kinds"]:
                lint.fail(path, f"markdown references unregistered typed ID kind: cx:{kind}:")

        for match in TYPED_ID_TOKEN_RE.finditer(text):
            kind, rest = match.group(1), match.group(2)
            if is_placeholder_typed_id(rest):
                continue
            check_typed_id_token(lint, path, "markdown", kind, rest, known)

        for block_index, match in enumerate(JSON_FENCE_RE.finditer(text), start=1):
            block = match.group("body")
            schema_ref = schema_ref_from_fence_meta(match.group("meta"))
            try:
                data = parse_json_text(block)
            except Exception as exc:
                lint.fail(path, f"json_block[{block_index}] invalid canonical JSON: {exc}")
                continue
            if schema_ref:
                check_json_instance_against_schema(
                    lint,
                    path,
                    f"json_block[{block_index}] declared schema example",
                    schema_ref,
                    data,
                )
            check_markdown_full_object_example(lint, path, block_index, data)
            check_event_ref_invariants_in_value(lint, path, f"json_block[{block_index}]", data)
            for json_path, value, key in walk_json(data):
                check_markdown_json_value(lint, path, f"json_block[{block_index}]{json_path[1:]}", value, key, known)

def check_release_readiness_counts(lint: Lint, known: dict[str, set[str]]) -> None:
    """T4-2: schema↔doc count guard.

    Re-parses release-readiness.md's count table and verifies each number
    matches the canonical registry. Prevents the kind of drift that left
    counts at 146/81/66 while the registry was at 150/84/70.
    """
    path = SPEC_ROOT / "zh" / "overview" / "release-readiness.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")

    profile_data = load_json(lint, ARTIFACTS / "profiles" / "conformance-profiles.json") or {}
    profile_requirements_count = len(profile_data.get("profile_requirements", []))
    profile_tiers_count = len(profile_data.get("profile_tiers", []))

    expected: dict[str, int] = {
        "Event kind（active）": len(known["active_event_kinds"]),
        "Schema": len(known["schema_ids"]),
        "Typed ID kind": len(known["id_kinds"]),
        "Service operation": len(known["operation_ids"]),
        "Conformance profile（profile id）": len(known["profiles"]),
        "profile_requirements": profile_requirements_count,
        "profile_tiers": profile_tiers_count,
    }

    # Match table rows like "| Event kind（active） | 150 | `...` |"
    table_re = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|", re.MULTILINE)
    found: dict[str, int] = {}
    for match in table_re.finditer(text):
        label = match.group(1).strip()
        if label in expected:
            found[label] = int(match.group(2))

    for label, want in expected.items():
        if label in {"profile_requirements", "profile_tiers"}:
            # Look in inline prose: "...另含 N 个 `profile_requirements`..."
            for inline_match in re.finditer(
                rf"(\d+)\s*个\s*`{label}`",
                text,
            ):
                have = int(inline_match.group(1))
                if have != want:
                    lint.fail(
                        path,
                        f"prose mentions {have} `{label}` but registry has {want}",
                    )
            continue
        have = found.get(label)
        if have is None:
            lint.fail(path, f"missing count row for {label!r}")
        elif have != want:
            lint.fail(
                path,
                f"count drift for {label!r}: doc says {have}, registry has {want}",
            )


def check_error_code_closure(lint: Lint) -> None:
    """T4-3: error code closure.

    All `error_code` / `reason_code` literals used in spec markdown MUST be
    registered in `artifacts/registry/error-code-registry.json`. Prevents
    the drift where spec text invents a reason code that no implementation
    can resolve.
    """
    registry_path = ARTIFACTS / "registry" / "error-code-registry.json"
    data = load_json(lint, registry_path)
    if not isinstance(data, dict):
        return
    known_codes: set[str] = set()
    for entry in data.get("codes", []):
        if isinstance(entry, dict) and isinstance(entry.get("code"), str):
            known_codes.add(entry["code"])
    for entry in data.get("reason_codes", []):
        if isinstance(entry, dict) and isinstance(entry.get("code"), str):
            known_codes.add(entry["code"])

    if not known_codes:
        return

    # Look for the canonical normative usage forms only:
    #   reason_code="..." / reason="..." / reason=`...`
    #   reason == "..."
    #   `error_code=...`
    # We deliberately do NOT scan freeform prose (lots of false positives
    # for ordinary English words quoted in backticks).
    #
    # Patterns covered (single + double quotes + backticks):
    patterns = [
        re.compile(r'reason_code\s*[=:]\s*["`]([a-z_][a-z0-9_]+)["`]'),
        re.compile(r'reason\s*[=:]\s*["`]([a-z_][a-z0-9_]+)["`]'),
        re.compile(r'reason\s*==\s*["`]([a-z_][a-z0-9_]+)["`]'),
        re.compile(r'error_code\s*[=:]\s*["`]([a-z_][a-z0-9_]+)["`]'),
        re.compile(r'`reason\s*=\s*["\']?([a-z_][a-z0-9_]+)["\']?`'),
    ]

    for path in markdown_files():
        text = path.read_text(encoding="utf-8")
        unresolved: set[str] = set()
        for pat in patterns:
            for match in pat.finditer(text):
                code = match.group(1)
                if code in known_codes:
                    continue
                # Filter common false positives (English words used elsewhere)
                if code in {"true", "false", "null", "ok", "yes", "no", "n_a"}:
                    continue
                unresolved.add(code)
        for code in sorted(unresolved):
            lint.fail(path, f"reason_code referenced but not in error-code-registry.json: {code!r}")


def check_cross_doc_anchors(lint: Lint) -> None:
    """T4-4: cross-doc anchor check.

    Every markdown link `(./foo.md#anchor)` must resolve to a real header in
    foo.md, slugified the same way GitHub-flavored renderers do. Prevents
    silent rot when sections are renamed.
    """
    # Build slug index for every markdown file.
    slug_re = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)

    def slugify(heading: str) -> str:
        # Strip markdown decoration (bold, code, links), keep visible text.
        text = heading
        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"__([^_]+)__", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = text.strip().lower()
        # github-slugger style: drop punctuation (except hyphen/underscore),
        # replace each whitespace char with a hyphen (do NOT collapse runs).
        # This mirrors Astro Starlight's default renderer; collapsing breaks
        # anchors like "查询 / 回填" where " / " becomes "--".
        text = re.sub(r"[^\w一-鿿\s-]", "", text)
        text = re.sub(r"\s", "-", text)
        return text

    file_slugs: dict[Path, set[str]] = {}
    for path in markdown_files():
        text = path.read_text(encoding="utf-8")
        slugs: set[str] = set()
        for match in slug_re.finditer(text):
            slugs.add(slugify(match.group(2)))
        file_slugs[path.resolve()] = slugs

    link_re = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
    for path in markdown_files():
        text = path.read_text(encoding="utf-8")
        for match in link_re.finditer(text):
            href = match.group(1)
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            if "#" not in href:
                continue
            target_path, _, anchor = href.partition("#")
            if not anchor:
                continue
            if target_path == "":
                # Same-file anchor; check this file's own slugs.
                target_resolved = path.resolve()
            else:
                target_resolved = (path.parent / target_path).resolve()
            slugs = file_slugs.get(target_resolved)
            if slugs is None:
                # Target file not in spec tree (e.g. external schema JSON);
                # leave for check_markdown_links to validate file existence.
                continue
            if anchor not in slugs:
                # Try also without leading section number (e.g. "3.4-target"
                # vs "target"). Skip noisy false positives by only failing
                # when no slug fuzzy-matches.
                normalized = anchor.lower()
                if any(normalized in s or s in normalized for s in slugs):
                    continue
                lint.fail(path, f"broken anchor in cross-doc link: {href!r}")


def check_openapi_no_floating_number(lint: Lint) -> None:
    """T4-5: forbid `type: number` in OpenAPI.

    v1 wire mandates integer-only JSON numbers (see encoding.md §2). Any
    `type: number` in OpenAPI would generate float/double SDK fields and
    break canonical-bytes interop. The forbidden-fields list below carries
    explicit waivers for known non-canonical surfaces.
    """
    openapi_path = ARTIFACTS / "openapi" / "contrix-service-api.openapi.yaml"
    if not openapi_path.exists():
        return
    lines = openapi_path.read_text(encoding="utf-8").splitlines()

    # Walk line-by-line; a waiver comment makes the next few lines'
    # `type: number` legal. Window of 8 lines is generous enough for
    # any reasonable YAML block while keeping the scan O(n).
    waiver_re = re.compile(r"#\s*lint-waiver\(type:number\)\s*:")
    type_number_re = re.compile(r"^\s*-?\s*type:\s*number\s*(?:#.*)?$")

    waiver_window = 0
    for line_no, line in enumerate(lines, start=1):
        if waiver_re.search(line):
            # next ≤ 8 lines may carry the waivered `type: number`
            waiver_window = 8
            continue
        if type_number_re.match(line):
            if waiver_window > 0:
                waiver_window = 0  # consume the waiver
                continue
            lint.fail(
                openapi_path,
                f"line {line_no}: `type: number` is forbidden in v1 wire; "
                "use integer + scale, or add a `# lint-waiver(type:number): <reason>` "
                "comment within 8 lines for non-canonical surfaces",
            )
        elif waiver_window > 0:
            waiver_window -= 1


def check_canonical_digest_fixtures(lint: Lint) -> None:
    """T4-1: canonical-JSON recompute guard.

    Walk every fixture JSON and, when it contains both a canonical-input
    object and an expected digest field, recompute the digest from the
    input's canonical bytes and require an exact match.

    Recognized fixture shapes:
      { "input": <obj>, "expected_digest": "sha256:..." }
      { "input": <obj>, "digest": "sha256:..." }
      { "envelope": <obj>, "payload_hash": "sha256:..." }
      { "canonical_bytes": "<hex>", "digest": "sha256:..." }

    This is intentionally narrow: it does not try to canonicalize whole
    repositories of arbitrary fixtures. New fixtures opt in by naming
    their input + digest fields using one of the shapes above.
    """
    fixtures_dir = ARTIFACTS / "fixtures"
    if not fixtures_dir.exists():
        return

    shapes: list[tuple[str, str]] = [
        ("input", "expected_digest"),
        ("input", "digest"),
        ("envelope", "payload_hash"),
        ("canonical_input", "expected_digest"),
    ]

    for fixture_path in fixtures_dir.rglob("*.json"):
        data = load_json(lint, fixture_path)
        if data is None:
            continue
        candidates: list[Any] = []
        if isinstance(data, dict):
            candidates.append(data)
        elif isinstance(data, list):
            candidates.extend(d for d in data if isinstance(d, dict))

        for case in candidates:
            for input_key, digest_key in shapes:
                if input_key not in case or digest_key not in case:
                    continue
                expected = case.get(digest_key)
                if not isinstance(expected, str):
                    continue
                if not expected.startswith("sha256:"):
                    # Non-sha256 algorithms are out of scope for this guard.
                    continue
                try:
                    canonical = canonical_json(case[input_key])
                except (TypeError, ValueError) as exc:
                    lint.fail(
                        fixture_path,
                        f"could not canonicalize {input_key!r} for digest check: {exc}",
                    )
                    continue
                recomputed = "sha256:" + sha256_text(canonical)
                if recomputed != expected:
                    lint.fail(
                        fixture_path,
                        f"digest mismatch: {input_key!r} canonical bytes produce "
                        f"{recomputed} but {digest_key!r}={expected}",
                    )


def main() -> int:
    lint = Lint()
    check_registry_manifest(lint)
    known = check_registries(lint)
    check_schema_refs(lint, known)
    check_profile_requirements(lint, known)
    check_event_schema_coverage(lint, known)
    check_operation_surfaces(lint, known)
    check_service_describe_alignment(lint)
    check_policy_check_alignment(lint)
    check_text_reference_targets(lint)
    check_cross_source_drift(lint, known)
    check_vector_reference_closure(lint)
    check_security_closure_vectors(lint)
    check_fixtures(lint, known)
    check_crypto_signature_fixture(lint)
    check_markdown_links(lint)
    check_markdown_examples(lint, known)
    check_legacy_wire_fields(lint)
    check_release_readiness_counts(lint, known)
    check_error_code_closure(lint)
    check_cross_doc_anchors(lint)
    check_openapi_no_floating_number(lint)
    check_canonical_digest_fixtures(lint)

    if lint.errors:
        print("Artifact registry lint failed:", file=sys.stderr)
        for error in lint.errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "Artifact registry lint passed "
        f"({len(known['event_kinds'])} event kinds, "
        f"{len(known['schema_ids'])} schemas, "
        f"{len(known['id_kinds'])} typed ID kinds, "
        f"{len(known['operation_ids'])} operations, "
        f"{len(known['profiles'])} profiles)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
