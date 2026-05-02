#!/usr/bin/env python3
"""Lint Contrix artifact/registry consistency.

The registries in artifacts/registry are the source of truth for standard
Event.kind values, cx.schema.* IDs, cx:<kind>: typed IDs, and service
operation IDs. This script keeps the machine-readable artifacts aligned with
those registries without requiring third-party Python packages.
"""

from __future__ import annotations

import json
import base64
import hashlib
import re
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"

EVENT_KIND_TOKEN_RE = re.compile(r"\bcx\.[a-z0-9_]+(?:\.[a-z0-9_]+)+\b")
OPERATION_ID_RE = re.compile(r"^cx\.[a-z0-9_]+(?:\.[a-z0-9_]+)+$")
SCHEMA_ID_RE = re.compile(r"^cx\.schema\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\.v[0-9]+$")
SCHEMA_ID_TOKEN_RE = re.compile(r"\bcx\.schema\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\.v[0-9]+\b")
PROFILE_ID_RE = re.compile(r"^cx\.profile\.[a-z0-9][a-z0-9_.-]*\.v[0-9]+$")
PROFILE_ID_TOKEN_RE = re.compile(r"\bcx\.profile\.[a-z0-9][a-z0-9_.-]*\.v[0-9]+\b")
TYPED_ID_TOKEN_RE = re.compile(r"\bcx:([a-z0-9_]+):([A-Za-z0-9._~=-]+(?::[A-Za-z0-9._~=-]+)*)")
ULID_RE = re.compile(r"^[0-9a-hjkmnp-z]{26}$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
OPENAPI_OPERATION_ID_RE = re.compile(r"^\s*operationId:\s*([A-Za-z0-9_.-]+)\s*$", re.MULTILINE)
YAML_REF_RE = re.compile(r"\$ref:\s*['\"]?([^'\"\s#]+(?:#[^'\"\s]+)?)")
JSON_FENCE_RE = re.compile(r"```json\s*(.*?)```", re.IGNORECASE | re.DOTALL)
TYPED_ID_PREFIX_TOKEN_RE = re.compile(r"\bcx:([a-z0-9_]+):")


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
    roots.extend(sorted((ROOT / "zh").rglob("*.md")))
    return [path for path in roots if path.is_file()]


def check_registries(lint: Lint) -> dict[str, set[str]]:
    event_path = ARTIFACTS / "registry" / "event-kind-registry.json"
    schema_path = ARTIFACTS / "registry" / "schema-registry.json"
    id_path = ARTIFACTS / "registry" / "id-kind-registry.json"
    operation_path = ARTIFACTS / "registry" / "operation-registry.json"
    profile_path = ARTIFACTS / "profiles" / "conformance-profiles.json"

    event_registry = load_json(lint, event_path) or {}
    schema_registry = load_json(lint, schema_path) or {}
    id_registry = load_json(lint, id_path) or {}
    operation_registry = load_json(lint, operation_path) or {}
    profile_registry = load_json(lint, profile_path) or {}

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
        if wire_scope == "deprecated_alias":
            if row.get("status") != "deprecated":
                lint.fail(event_path, f"{kind} is deprecated_alias but status is not deprecated")
            replaced_by = row.get("replaced_by")
            replacement = event_by_kind.get(replaced_by)
            if replacement is None:
                lint.fail(event_path, f"{kind} replaced_by target is not registered: {replaced_by!r}")
            elif replacement.get("status") != "active":
                lint.fail(event_path, f"{kind} replaced_by target is not active: {replaced_by}")
            if row.get("reducer_input") is not False:
                lint.fail(event_path, f"{kind} deprecated_alias must not be reducer_input")

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
    for operation_id in operation_ids:
        if not OPERATION_ID_RE.fullmatch(operation_id):
            lint.fail(operation_path, f"operation_id has invalid format: {operation_id}")

    profiles: set[str] = set()
    for _, value, _ in walk_json(profile_registry):
        if isinstance(value, str) and value.startswith("cx.profile."):
            profiles.add(value)
            if not PROFILE_ID_RE.fullmatch(value):
                lint.fail(profile_path, f"profile id has invalid format: {value}")

    return {
        "event_kinds": event_kinds,
        "active_event_kinds": {
            row["event_kind"]
            for row in event_by_kind.values()
            if row.get("status") == "active"
        },
        "deprecated_event_kinds": {
            row["event_kind"]
            for row in event_by_kind.values()
            if row.get("wire_scope") == "deprecated_alias"
        },
        "schema_ids": schema_ids,
        "id_kinds": id_kinds,
        "special_id_kinds": special_id_kinds,
        "operation_ids": operation_ids,
        "profiles": profiles,
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
                if scope not in {"durable_event", "actor_private_event", "ephemeral_event", "deprecated_alias"}:
                    lint.fail(path, f"{profile_id} rejects unknown wire_scope: {event_kind}")
                continue
            if event_kind not in known["event_kinds"]:
                lint.fail(path, f"{profile_id} rejects unknown Event.kind: {event_kind}")

        for schema_id in requirement.get("required_schemas", []):
            if schema_id not in known["schema_ids"]:
                lint.fail(path, f"{profile_id} requires unknown schema: {schema_id}")

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
    for token in sorted(known["active_event_kinds"] - event_schema_kinds):
        lint.fail(path, f"active Event.kind missing from event-schema enum coverage: {token}")
    for token in sorted(known["deprecated_event_kinds"] & event_schema_kinds):
        lint.fail(path, f"deprecated Event.kind alias appears in event-schema enum coverage: {token}")


def check_operation_surfaces(lint: Lint, known: dict[str, set[str]]) -> None:
    openapi_path = ARTIFACTS / "openapi" / "contrix-service-api.openapi.yaml"
    openapi_text = openapi_path.read_text(encoding="utf-8")
    openapi_operation_ids = OPENAPI_OPERATION_ID_RE.findall(openapi_text)
    openapi_set = set(openapi_operation_ids)
    if len(openapi_operation_ids) != len(openapi_set):
        duplicates = sorted({item for item in openapi_operation_ids if openapi_operation_ids.count(item) > 1})
        lint.fail(openapi_path, f"duplicate operationId values: {', '.join(duplicates)}")
    for operation_id in sorted(openapi_set - known["operation_ids"]):
        lint.fail(openapi_path, f"operationId not registered: {operation_id}")
    for operation_id in sorted(known["operation_ids"] - openapi_set):
        lint.fail(openapi_path, f"registered operation_id missing from OpenAPI: {operation_id}")

    binding_path = ARTIFACTS / "bindings" / "non-http-bindings.yaml"
    binding_text = binding_path.read_text(encoding="utf-8")
    binding_operation_ids = set(EVENT_KIND_TOKEN_RE.findall(binding_text))
    for operation_id in sorted(binding_operation_ids - known["operation_ids"]):
        lint.fail(binding_path, f"non-HTTP binding references unregistered operation_id: {operation_id}")
    for operation_id in sorted(known["operation_ids"] - binding_operation_ids):
        lint.fail(binding_path, f"registered operation_id missing from non-HTTP bindings: {operation_id}")


def check_typed_id_token(lint: Lint, path: Path, json_path: str, token_kind: str, rest: str, known: dict[str, set[str]]) -> None:
    if token_kind == "blob" and rest.startswith("sha256:"):
        if not SHA256_RE.fullmatch(rest):
            lint.fail(path, f"{json_path} has invalid cx:blob:sha256 reference")
        return
    if token_kind in known["id_kinds"]:
        candidate = rest[:26]
        if not ULID_RE.fullmatch(candidate):
            lint.fail(path, f"{json_path} has invalid cx:{token_kind}: typed ULID reference")
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
        for json_path, value, key in walk_json(data):
            if not isinstance(value, str):
                continue

            for schema_id in SCHEMA_ID_TOKEN_RE.findall(value):
                if schema_id not in known["schema_ids"]:
                    lint.fail(path, f"{json_path} references unknown schema id: {schema_id}")

            for profile_id in PROFILE_ID_TOKEN_RE.findall(value):
                if profile_id not in known["profiles"]:
                    lint.fail(path, f"{json_path} references unknown profile: {profile_id}")

            for deprecated_kind in known["deprecated_event_kinds"]:
                if deprecated_kind in value:
                    lint.fail(path, f"{json_path} uses deprecated Event.kind alias: {deprecated_kind}")

            if key in {"kind", "event_kind", "target_format"} and value.startswith("cx."):
                if value not in known["event_kinds"]:
                    lint.fail(path, f"{json_path} references unregistered Event.kind: {value}")
                elif value in known["deprecated_event_kinds"]:
                    lint.fail(path, f"{json_path} uses deprecated Event.kind alias: {value}")

            if key in {"operation_id", "mapped_operation_id"} and value.startswith("cx."):
                if value not in known["operation_ids"]:
                    lint.fail(path, f"{json_path} references unregistered operation_id: {value}")
            if key == "call" and ".recovery.call" in json_path and value.startswith("cx."):
                if value not in known["operation_ids"]:
                    lint.fail(path, f"{json_path} references unregistered recovery operation_id: {value}")

            for match in TYPED_ID_TOKEN_RE.finditer(value):
                check_typed_id_token(lint, path, json_path, match.group(1), match.group(2), known)


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
            expected_canonical = canonical_json(event)
            if vector.get("canonical_event_payload") != expected_canonical:
                lint.fail(path, f"vectors[{index}] canonical_event_payload does not match canonical JSON")
            expected_payload_hash = sha256_text(expected_canonical)
            if vector.get("payload_hash") != expected_payload_hash:
                lint.fail(path, f"vectors[{index}] payload_hash does not match canonical_event_payload")

            event_with_proof = vector.get("event_with_proof")
            if isinstance(event_with_proof, dict):
                unsigned = dict(event_with_proof)
                unsigned.pop("proofs", None)
                if unsigned != event:
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
        or rest in {"id", "ulid", "example", "A", "B"}
        or rest.startswith("<")
        or rest.endswith(">")
    )


def check_markdown_json_value(lint: Lint, path: Path, json_path: str, value: Any, key: str | None, known: dict[str, set[str]]) -> None:
    if isinstance(value, str):
        for schema_id in SCHEMA_ID_TOKEN_RE.findall(value):
            if schema_id not in known["schema_ids"]:
                lint.fail(path, f"{json_path} markdown JSON references unknown schema id: {schema_id}")
        for profile_id in PROFILE_ID_TOKEN_RE.findall(value):
            if profile_id not in known["profiles"]:
                lint.fail(path, f"{json_path} markdown JSON references unknown profile: {profile_id}")

        if key in {"kind", "event_kind", "target_format"} and value.startswith("cx."):
            if value not in known["event_kinds"]:
                lint.fail(path, f"{json_path} markdown JSON references unregistered Event.kind: {value}")
            elif value in known["deprecated_event_kinds"]:
                lint.fail(path, f"{json_path} markdown JSON uses deprecated Event.kind alias: {value}")

        if key in {"operation_id", "mapped_operation_id", "operationId"} and value.startswith("cx."):
            if value not in known["operation_ids"]:
                lint.fail(path, f"{json_path} markdown JSON references unregistered operation_id: {value}")

        for match in TYPED_ID_TOKEN_RE.finditer(value):
            kind, rest = match.group(1), match.group(2)
            if is_placeholder_typed_id(rest):
                if kind not in known["id_kinds"] and kind not in known["special_id_kinds"]:
                    lint.fail(path, f"{json_path} markdown JSON references unregistered typed ID kind: cx:{kind}:")
                continue
            check_typed_id_token(lint, path, json_path, kind, rest, known)


def check_markdown_examples(lint: Lint, known: dict[str, set[str]]) -> None:
    for path in markdown_files():
        text = path.read_text(encoding="utf-8")

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

        for deprecated_kind in known["deprecated_event_kinds"]:
            if deprecated_kind in text:
                lint.fail(path, f"deprecated Event.kind alias appears in Markdown example: {deprecated_kind}")

        for block_index, block in enumerate(JSON_FENCE_RE.findall(text), start=1):
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            try:
                data = parse_json_text(block)
            except Exception as exc:
                lint.fail(path, f"json_block[{block_index}] invalid canonical JSON: {exc}")
                continue
            check_event_ref_invariants_in_value(lint, path, f"json_block[{block_index}]", data)
            for json_path, value, key in walk_json(data):
                check_markdown_json_value(lint, path, f"json_block[{block_index}]{json_path[1:]}", value, key, known)


def check_deprecated_alias_leakage(lint: Lint, known: dict[str, set[str]]) -> None:
    aliases = known["deprecated_event_kinds"]
    if not aliases:
        return
    allowed = {
        (ARTIFACTS / "registry" / "event-kind-registry.json").resolve(),
        Path(__file__).resolve(),
    }
    for path in raw_artifact_files():
        if path.resolve() in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        for alias in aliases:
            if alias in text:
                lint.fail(path, f"deprecated Event.kind alias appears outside registry compatibility declaration: {alias}")


def compare_tree(lint: Lint, canonical: Path, mirror: Path, label: str) -> None:
    canonical_files = {path.relative_to(canonical).as_posix(): path for path in canonical.rglob("*") if path.is_file()}
    mirror_files = {path.relative_to(mirror).as_posix(): path for path in mirror.rglob("*") if path.is_file()}
    for name in sorted(canonical_files.keys() - mirror_files.keys()):
        lint.fail(mirror, f"{label} mirror missing {name}")
    for name in sorted(mirror_files.keys() - canonical_files.keys()):
        lint.fail(mirror / name, f"{label} mirror has extra file {name}")
    for name in sorted(canonical_files.keys() & mirror_files.keys()):
        if canonical_files[name].read_bytes() != mirror_files[name].read_bytes():
            lint.fail(mirror_files[name], f"{label} mirror differs from {lint.rel(canonical_files[name])}")


def check_zh_mirrors(lint: Lint) -> None:
    compare_tree(lint, ARTIFACTS / "schemas", ROOT / "zh" / "conformance" / "schemas", "schema")
    compare_tree(lint, ARTIFACTS / "fixtures", ROOT / "zh" / "conformance" / "fixtures", "fixture")

    mirror_pairs = [
        (
            ARTIFACTS / "openapi" / "contrix-service-api.openapi.yaml",
            ROOT / "zh" / "sync" / "contrix-service-api.openapi.yaml",
            "OpenAPI",
        ),
        (
            ARTIFACTS / "bindings" / "non-http-bindings.yaml",
            ROOT / "zh" / "sync" / "non-http-bindings.yaml",
            "non-HTTP binding",
        ),
    ]
    for canonical, mirror, label in mirror_pairs:
        if not mirror.exists():
            lint.fail(mirror, f"{label} mirror missing")
        elif canonical.read_bytes() != mirror.read_bytes():
            lint.fail(mirror, f"{label} mirror differs from {lint.rel(canonical)}")


def main() -> int:
    lint = Lint()
    known = check_registries(lint)
    check_schema_refs(lint, known)
    check_profile_requirements(lint, known)
    check_event_schema_coverage(lint, known)
    check_operation_surfaces(lint, known)
    check_fixtures(lint, known)
    check_crypto_signature_fixture(lint)
    check_markdown_examples(lint, known)
    check_deprecated_alias_leakage(lint, known)
    check_zh_mirrors(lint)

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
