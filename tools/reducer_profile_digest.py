#!/usr/bin/env python3
"""Build content-addressed reducer-profile digest inputs."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SPEC_ROOT = ROOT / "spec" / "v1"
ARTIFACTS = SPEC_ROOT / "artifacts"
PROFILE_REGISTRY_PATH = ARTIFACTS / "registry" / "reducer-profile-registry.json"
EVENT_KIND_REGISTRY_PATH = ARTIFACTS / "registry" / "event-kind-registry.json"
SCHEMA_REGISTRY_PATH = ARTIFACTS / "registry" / "schema-registry.json"
CONFORMANCE_PROFILE_PATH = ARTIFACTS / "profiles" / "conformance-profiles.json"
REDUCER_DIGEST_VECTOR_ID = "ak.vector.federation.reducer_profile_digest.v1"
SHA256_LITERAL_RE = re.compile(r"sha256:[0-9a-f]{64}")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def content_digest(value: Any) -> str:
    if not isinstance(value, str):
        value = canonical_json(value)
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_json_pointer(document: Any, fragment: str) -> Any:
    if not fragment or fragment == "#":
        return document
    if not fragment.startswith("#/"):
        raise ValueError(f"unsupported JSON pointer: {fragment}")
    current = document
    for token in fragment[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise ValueError(f"unresolved JSON pointer: {fragment}")
        current = current[token]
    return current


def fixture_semantic_projection(value: Any) -> Any:
    """Remove reducer-digest outputs so required fixtures can be hashed without a cycle."""
    if isinstance(value, dict):
        if value.get("vector_id") == REDUCER_DIGEST_VECTOR_ID:
            return None
        projected: dict[str, Any] = {}
        for key, child in value.items():
            if "reducer_profile_digest" in key:
                continue
            projected_child = fixture_semantic_projection(child)
            if projected_child is not None:
                projected[key] = projected_child
        return projected
    if isinstance(value, list):
        projected_items = [fixture_semantic_projection(item) for item in value]
        return [item for item in projected_items if item is not None]
    return value


def referenced_content_digest(ref: str) -> str:
    file_ref, separator, fragment = ref.partition("#")
    path = SPEC_ROOT / file_ref
    if not path.is_file():
        raise ValueError(f"missing reducer contract reference: {ref}")
    if path.suffix == ".json":
        document = load_json(path)
        selected = resolve_json_pointer(document, f"#{fragment}" if separator else "#")
        return content_digest(selected)
    if separator:
        raise ValueError(f"fragments are only supported for JSON reducer contracts: {ref}")
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    # Published reducer-profile digest examples are outputs of this algorithm, not
    # reducer semantics. Other SHA-256 literals remain bound by the contract digest.
    text = "\n".join(
        SHA256_LITERAL_RE.sub("sha256:<digest>", line)
        if "reducer_profile_digest" in line
        else line
        for line in text.split("\n")
    )
    return content_digest(text)


def profile_chain(
    profile_id: str,
    profiles: dict[str, dict[str, Any]],
    visiting: set[str] | None = None,
) -> set[str]:
    if profile_id not in profiles:
        raise ValueError(f"unknown reducer profile: {profile_id}")
    visiting = set() if visiting is None else visiting
    if profile_id in visiting:
        raise ValueError(f"reducer profile inheritance cycle at {profile_id}")
    visiting.add(profile_id)
    result = {profile_id}
    declaration = profiles[profile_id].get("digest_input")
    if not isinstance(declaration, dict):
        raise ValueError(f"{profile_id} missing digest_input declaration")
    inherits = declaration.get("inherits", [])
    if not isinstance(inherits, list) or not all(isinstance(item, str) for item in inherits):
        raise ValueError(f"{profile_id}.digest_input.inherits must be a string array")
    for inherited in inherits:
        result.update(profile_chain(inherited, profiles, visiting))
    visiting.remove(profile_id)
    return result


def build_resolved_digest_input(registry: dict[str, Any], profile_id: str) -> dict[str, Any]:
    rows = registry.get("profiles")
    if not isinstance(rows, list):
        raise ValueError("reducer profile registry missing profiles")
    profiles = {
        row.get("profile_id"): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("profile_id"), str)
    }
    conformance_profiles = load_json(CONFORMANCE_PROFILE_PATH)
    requirements = conformance_profiles.get("profile_requirements", {})
    if isinstance(requirements, dict):
        for external_id, requirement in requirements.items():
            if (
                external_id not in profiles
                and isinstance(external_id, str)
                and isinstance(requirement, dict)
            ):
                profiles[external_id] = {
                    "profile_id": external_id,
                    "digest_input": {"profile_id": external_id, **copy.deepcopy(requirement)},
                }
    chain_ids = sorted(profile_chain(profile_id, profiles))
    declarations = [copy.deepcopy(profiles[item]["digest_input"]) for item in chain_ids]

    event_registry = load_json(EVENT_KIND_REGISTRY_PATH)
    event_rows = {
        row.get("event_kind"): row
        for row in event_registry.get("event_kinds", [])
        if isinstance(row, dict) and isinstance(row.get("event_kind"), str)
    }
    required_event_kinds = sorted(
        {
            item
            for declaration in declarations
            for item in declaration.get("required_event_kinds", [])
            if isinstance(item, str)
        }
    )
    missing_event_kinds = sorted(set(required_event_kinds) - set(event_rows))
    if missing_event_kinds:
        raise ValueError("unknown required event kinds: " + ", ".join(missing_event_kinds))
    event_kind_contracts = [
        {
            "event_kind": event_kind,
            "content_digest": content_digest(event_rows[event_kind]),
        }
        for event_kind in required_event_kinds
    ]

    schema_registry = load_json(SCHEMA_REGISTRY_PATH)
    schema_rows = {
        row.get("schema_id"): row
        for row in schema_registry.get("schemas", [])
        if isinstance(row, dict) and isinstance(row.get("schema_id"), str)
    }
    required_schemas = sorted(
        {
            item
            for declaration in declarations
            for item in declaration.get("required_schemas", [])
            if isinstance(item, str)
        }
    )
    schema_contracts: list[dict[str, str]] = []
    for schema_id in required_schemas:
        row = schema_rows.get(schema_id)
        if row is None:
            raise ValueError(f"unknown required schema: {schema_id}")
        file_ref = row.get("file")
        if not isinstance(file_ref, str):
            raise ValueError(f"schema registry row {schema_id} missing file")
        schema_path = ARTIFACTS / file_ref
        if not schema_path.is_file():
            raise ValueError(f"schema file does not resolve for {schema_id}: {file_ref}")
        schema_contracts.append(
            {
                "schema_id": schema_id,
                "registry_row_digest": content_digest(row),
                "document_digest": content_digest(load_json(schema_path)),
            }
        )

    fixture_names = sorted(
        {
            item
            for declaration in declarations
            for item in declaration.get("required_fixtures", [])
            if isinstance(item, str)
        }
    )
    fixture_contracts: list[dict[str, str]] = []
    for fixture_name in fixture_names:
        fixture_path = ARTIFACTS / "fixtures" / fixture_name
        if not fixture_path.is_file():
            raise ValueError(f"missing required fixture: {fixture_name}")
        fixture_contracts.append(
            {
                "fixture": fixture_name,
                "semantic_projection_digest": content_digest(
                    fixture_semantic_projection(load_json(fixture_path))
                ),
            }
        )

    contract_refs = sorted(
        {
            item
            for declaration in declarations
            for item in declaration.get("reducer_contract_refs", [])
            if isinstance(item, str)
        }
    )
    reducer_contracts: list[dict[str, str]] = []
    for ref in contract_refs:
        if ref == "artifacts/registry/event-kind-registry.json":
            continue
        reducer_contracts.append({"ref": ref, "content_digest": referenced_content_digest(ref)})

    return {
        "profile_id": profile_id,
        "profile_declarations": declarations,
        "event_kind_contracts": event_kind_contracts,
        "schema_contracts": schema_contracts,
        "fixture_contracts": fixture_contracts,
        "reducer_contracts": reducer_contracts,
    }


def materialize_registry(registry: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(registry)
    result["description"] = (
        "Canonical reducer profile declarations and generated content-addressed semantic "
        "closures used for federation service_binding_ref.reducer_profile_digest."
    )
    result["digest_input_rule"] = (
        "Resolve the selected profile and its transitive inherits closure; independently "
        "rebuild resolved_digest_input from the declared event kinds, schemas, fixtures, "
        "and reducer contract references using tools/reducer_profile_digest.py semantics; "
        "canonicalize that resolved object with Arkret canonical JSON; hash its UTF-8 bytes "
        "with SHA-256; encode as sha256:<lowercase_hex>."
    )
    result["generated_fields"] = ["profiles[].resolved_digest_input", "profiles[].reducer_profile_digest"]
    rows = result.get("profiles")
    if not isinstance(rows, list):
        raise ValueError("reducer profile registry missing profiles")
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("profile_id"), str):
            raise ValueError("invalid reducer profile row")
        resolved = build_resolved_digest_input(result, row["profile_id"])
        row["resolved_digest_input"] = resolved
        row["reducer_profile_digest"] = content_digest(resolved)
    return result
