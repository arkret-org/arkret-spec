#!/usr/bin/env python3
"""Lint Arkret artifact/registry consistency.

Canonical registries plus generated registry views under
``spec/v1/artifacts/registry`` define the machine-readable wire contract.
This script validates registry manifests, cross-artifact references, markdown
link integrity, selected JSON examples, and schema-declared fixtures.

The legacy ``zh/`` mirror integrity check has been removed: machine artifacts
are no longer copied into the prose tree. The site renders them directly.
"""

from __future__ import annotations

import copy
import argparse
import binascii
import json
import base64
import hashlib
import re
import sys
import time
import unicodedata
import urllib.parse
import warnings
from collections import Counter
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError:  # pragma: no cover - CI installs the dependency.
    yaml = None

try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from jsonschema import Draft202012Validator, FormatChecker, RefResolver
        from referencing import Registry, Resource
except ImportError:  # pragma: no cover - CI installs the dependency.
    Draft202012Validator = None
    FormatChecker = None
    RefResolver = None
    Registry = None
    Resource = None


ROOT = Path(__file__).resolve().parents[1]
SPEC_ROOT = ROOT / "spec" / "v1"
ARTIFACTS = SPEC_ROOT / "artifacts"

EVENT_KIND_TOKEN_RE = re.compile(r"\bak\.[a-z0-9_]+(?:\.[a-z0-9_]+)+\b")
OPERATION_ID_RE = re.compile(r"^ak\.[a-z0-9_]+(?:\.[a-z0-9_]+)+$")
# zh/sync/api-conventions.md §2.4: ak.<surface>.<domain...>.<kind>.<action>.
OPERATION_KINDS = frozenset({"read", "query", "stream", "resource", "command", "upload", "exchange"})
# HTTP method names describe transport, not protocol effect; get/delete stay legal
# because they are the canonical resource-kind actions.
FORBIDDEN_OPERATION_ACTIONS = frozenset({"post", "put", "patch"})
SCHEMA_ID_RE = re.compile(r"^ak\.schema\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\.v[0-9]+$")
SCHEMA_ID_TOKEN_RE = re.compile(r"\bak\.schema\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\.v[0-9]+\b")
PROFILE_ID_RE = re.compile(r"^ak\.profile\.[a-z0-9][a-z0-9_.-]*\.v[0-9]+$")
PROFILE_ID_TOKEN_RE = re.compile(r"\bak\.profile\.[a-z0-9][a-z0-9_.-]*\.v[0-9]+\b")
VECTOR_ID_TOKEN_RE = re.compile(r"\bak\.vector\.[a-z0-9_.-]+\.v[0-9]+\b")
VECTOR_GROUP_ID_RE = re.compile(r"^ak\.vector_group\.[a-z0-9][a-z0-9_.-]*\.v[0-9]+$")
TYPED_ID_TOKEN_RE = re.compile(r"\bak:([a-z0-9_]+):([A-Za-z0-9._~=-]+(?::[A-Za-z0-9._~=-]+)*)")
UUID7_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
UUID8_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
OPENAPI_OPERATION_ID_RE = re.compile(r"^\s*operationId:\s*([A-Za-z0-9_.-]+)\s*$", re.MULTILINE)
YAML_REF_RE = re.compile(r"\$ref:\s*['\"]?([^'\"\s#]+(?:#[^'\"\s]+)?)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def markdown_heading_slug(heading: str) -> str:
    """Slugify a markdown heading the way GitHub-flavored renderers do.

    Strips markdown decoration (bold, code, links), keeps visible text, drops
    punctuation except hyphen/underscore, and replaces each whitespace char with
    a hyphen without collapsing runs. This mirrors Astro Starlight's default
    renderer; collapsing would break anchors like "查询 / 回填" where " / "
    becomes "--".
    """
    text = heading
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w一-鿿\s-]", "", text)
    text = re.sub(r"\s", "-", text)
    return text


def markdown_section_digest(text: str, anchor: str) -> str | None:
    """sha256 of the section owned by `anchor`, or None when it does not exist.

    The section runs from its heading line to the next heading of the same or
    higher level. Line endings are normalized so the digest is stable across
    checkouts.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    start: int | None = None
    level = 0
    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match and markdown_heading_slug(match.group(2)) == anchor:
            start, level = index, len(match.group(1))
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = re.match(r"^(#{1,6})\s+", lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    body = "\n".join(lines[start:end]).rstrip() + "\n"
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
JSON_FENCE_RE = re.compile(r"```json(?P<meta>[^\n`]*)\n(?P<body>.*?)```", re.IGNORECASE | re.DOTALL)
JSON_FENCE_SCHEMA_ATTR_RE = re.compile(r"\bschema=(?:\"([^\"]+)\"|'([^']+)'|([^\s]+))")
JSON_FENCE_EXPECT_ATTR_RE = re.compile(r"\bexpect=(valid|invalid)\b")
JSON_FENCE_FIRST_ERROR_ATTR_RE = re.compile(r"\bfirst_error=(?:\"([^\"]+)\"|'([^']+)'|([^\s]+))")
TYPED_ID_PREFIX_TOKEN_RE = re.compile(r"\bak:([a-z0-9_]+):")
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
DEVICE_ID_PATTERN = r"^ak:device:[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
DID_LEGACY_PREFIX_PATTERN = r"^did:"
DID_LEGACY_GREEDY_PATTERN = r"^did:[a-z0-9]+:[^\s]+$"
DID_BARE_PATTERN = r"^did:[a-z0-9]+:[^\s#?]+$"
DID_URL_PROFILE_PATTERN = r"^did:[a-z0-9]+:[^\s#?]+#[A-Za-z0-9._:-]+$"
GENERIC_OPERATION_REQUEST_REF = "#/components/schemas/OperationRequest"
GENERIC_OPERATION_RESULT_REF = "#/components/schemas/OperationResult"

SECURITY_CLOSURE_VECTOR_IDS = {
    "ak.vector.account.blocklist_projection.v1",
    "ak.vector.account_status.authority_publication.v1",
    "ak.vector.aad_visibility.policy_ceiling.v1",
    "ak.vector.federation.idempotency_after_key_revoke.v1",
    "ak.vector.webrtc.media_plaintext_downgrade.v1",
    "ak.vector.identity_link.eager_invalidation.v1",
    "ak.vector.identity_link.policy_tightening_invalidation.v1",
    "ak.vector.late_key_recovery.removed_actor.v1",
    "ak.vector.invite.oob_code_entropy.v1",
    "ak.vector.invite.failure_indistinguishable.v1",
    "ak.vector.invite.claim_reducer_state_machine.v1",
    "ak.vector.consent.scope_cascade.v1",
    "ak.vector.consent.cache_invalidation.v1",
    "ak.vector.sync.soft_fail_reconcile.v1",
    "ak.vector.lattice.lww_open_set.v1",
    "ak.vector.e2ee_relaxed.window_exceeds_ceiling.v1",
}

REGISTRY_LATTICES = {
    "or_set",
    "mv_register",
    "cas_register",
    "fsm",
    "counter",
    "ordered_log",
}
REGISTRY_BOTTOMS = {"reject", "expose", "inert"}
REGISTRY_PLANES = {"data", "control"}
CELL_FAMILY_RE = re.compile(r"^ak\.component\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\.v[0-9]+$")

FULL_MARKDOWN_EXAMPLE_SCHEMAS = {
    "spec/v1/zh/models/realm-and-space.md": {
        1: "schemas/realm.schema.json",
        2: "schemas/space.schema.json",
    },
    "spec/v1/zh/models/strand-and-message.md": {
        1: "schemas/strand.schema.json",
        5: "schemas/message.schema.json",
    },
    "spec/v1/zh/models/morph.md": {
        1: "schemas/morph.schema.json",
    },
    "spec/v1/zh/models/relation.md": {
        1: "schemas/relation.schema.json",
    },
    "spec/v1/zh/models/event-and-patch.md": {
        1: "schemas/event-envelope.schema.json",
    },
    "spec/v1/zh/authz/capabilities.md": {
        1: "schemas/capability-grant.schema.json",
    },
}


class Lint:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            return str(path)

    def fail(self, path: Path, message: str) -> None:
        self.errors.append(f"{self.rel(path)}: {message}")

    def warn(self, path: Path, message: str) -> None:
        self.warnings.append(f"{self.rel(path)}: {message}")


@lru_cache(maxsize=None)
def read_text(path: Path) -> str:
    """Read one repository file once per lint run."""
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def parse_json_file(path: Path) -> Any:
    return parse_json_text(read_text(path))


@lru_cache(maxsize=None)
def parse_yaml_file(path: Path) -> Any:
    if yaml is None:
        raise RuntimeError("PyYAML is required for OpenAPI lint; install pyyaml")
    return yaml.safe_load(read_text(path))


def load_json(lint: Lint, path: Path) -> Any:
    try:
        return parse_json_file(path.resolve())
    except Exception as exc:  # pragma: no cover - exact parser errors vary
        lint.fail(path, f"invalid JSON: {exc}")
        return None


def load_yaml(lint: Lint, path: Path) -> Any:
    try:
        return parse_yaml_file(path.resolve())
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


def resolve_json_pointer(document: Any, fragment: str) -> Any:
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


def load_artifact_schema_from_ref(lint: Lint, owner: Path, ref: str) -> Any:
    normalized = normalize_artifact_schema_ref(ref)
    if not isinstance(normalized, str) or not normalized.startswith("schemas/"):
        lint.fail(owner, f"schema ref must point to artifacts/schemas: {ref}")
        return None
    file_ref, _, fragment = normalized.partition("#")
    schema_path = ARTIFACTS / file_ref
    document = load_json(lint, schema_path)
    if document is None:
        return None
    try:
        return resolve_json_pointer(document, f"#{fragment}" if fragment else "#")
    except KeyError:
        lint.fail(owner, f"schema ref fragment not found: {ref}")
        return None


def resolve_openapi_component_schema(
    lint: Lint,
    openapi_path: Path,
    components: dict[str, Any],
    component_name: str,
) -> Any:
    schema = components.get(component_name)
    seen: set[str] = set()
    while isinstance(schema, dict):
        ref = schema.get("$ref")
        if not isinstance(ref, str):
            return schema
        if ref.startswith("#/components/schemas/"):
            next_name = ref.rsplit("/", 1)[-1]
            if next_name in seen:
                lint.fail(openapi_path, f"cyclic OpenAPI component ref: {component_name}")
                return None
            seen.add(next_name)
            schema = components.get(next_name)
            continue
        return load_artifact_schema_from_ref(lint, openapi_path, ref)
    return schema


def resolve_openapi_schema_node(
    lint: Lint,
    openapi_path: Path,
    components: dict[str, Any],
    schema: Any,
) -> Any:
    if not isinstance(schema, dict):
        return schema
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return schema
    if ref.startswith("#/components/schemas/"):
        return resolve_openapi_component_schema(lint, openapi_path, components, ref.rsplit("/", 1)[-1])
    return load_artifact_schema_from_ref(lint, openapi_path, ref)


def schema_ref_targets(ref_schema: Any, component_name: str) -> bool:
    if not isinstance(ref_schema, dict):
        return False
    ref = ref_schema.get("$ref")
    return ref in {
        f"#/components/schemas/{component_name}",
        f"#/$defs/{component_name}",
    }


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def base64url_text(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).rstrip(b"=").decode("ascii")


def sha256_base64url_text(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


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


EVENT_ENVELOPE_IDENTITY_FIELDS = frozenset({"event_id", "realm_id", "payload"})
FORBIDDEN_EVENT_ENVELOPE_FIELDS = frozenset(
    {"effects", "conflict_keys_digest", "effective_scope"}
)


def event_envelope_candidates(
    value: Any,
    json_path: str = "$",
    negative_context: bool = False,
) -> Iterable[tuple[str, dict[str, Any], bool]]:
    """Yield Event-like objects without treating unrelated ``kind`` fields as Event kinds."""
    if isinstance(value, dict):
        expected = value.get("expected")
        negative_context = negative_context or (
            isinstance(expected, dict)
            and expected.get("decision") in {"reject", "quarantine"}
        ) or value.get("expect_valid") is False
        if EVENT_ENVELOPE_IDENTITY_FIELDS.issubset(value) and "kind" in value:
            yield json_path, value, negative_context
        for key, child in value.items():
            child_path = f"{json_path}.{key}"
            yield from event_envelope_candidates(child, child_path, negative_context)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from event_envelope_candidates(
                child,
                f"{json_path}[{index}]",
                negative_context,
            )


def check_event_envelope_candidates(
    lint: Lint,
    owner: Path,
    value: Any,
    known_event_kinds: set[str],
    *,
    label: str = "",
    negative_context: bool = False,
) -> None:
    for json_path, event, is_negative in event_envelope_candidates(
        value,
        negative_context=negative_context,
    ):
        if is_negative:
            continue
        kind = event.get("kind")
        if isinstance(kind, str) and kind.startswith("ak.") and kind not in known_event_kinds:
            lint.fail(owner, f"{label}{json_path} references unregistered Event.kind: {kind}")
        forbidden = sorted(FORBIDDEN_EVENT_ENVELOPE_FIELDS.intersection(event))
        if forbidden:
            lint.fail(
                owner,
                f"{label}{json_path} Event envelope contains forbidden legacy field(s): {forbidden}",
            )
        auth_context = event.get("auth_context")
        if isinstance(auth_context, dict) and "capability_refs" in auth_context:
            lint.fail(
                owner,
                f"{label}{json_path}.auth_context contains forbidden legacy capability_refs",
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
    ensure_cross_file_pointer(lint, owner, target, ref, label)
    return target


def ensure_cross_file_pointer(
    lint: Lint, owner: Path, target: Path, ref: str, label: str
) -> None:
    """Resolve the ``#/...`` fragment of a cross-file ``$ref`` inside the target document.

    Checking only that the *file* exists lets a deleted ``$defs`` entry survive every gate and
    surface much later as a downstream schema-compile failure. Pruning a shared schema is exactly
    when that happens, so the pointer itself is verified here.
    """
    if "#" not in ref or target.suffix != ".json":
        return
    fragment = ref.split("#", 1)[1]
    if not fragment.startswith("/"):
        return
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    node: Any = document
    for raw in fragment.lstrip("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and token in node:
            node = node[token]
            continue
        if isinstance(node, list) and token.isdigit() and int(token) < len(node):
            node = node[int(token)]
            continue
        lint.fail(
            owner,
            f"{label} points at a missing location in {target.name}: {ref}",
        )
        return


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


def text_contract_files() -> list[Path]:
    files: set[Path] = set(markdown_files())
    files.update(raw_artifact_files())
    files.update(sorted((SPEC_ROOT / "en").rglob("*.md")))
    files.add(ROOT / "CHANGELOG.md")
    files.add(ROOT / "site" / "src" / "lib" / "site-meta.ts")
    return sorted(path for path in files if path.is_file())


WIRE_GUARD_FILES = {"forbidden-wire-fields.json"}

FORBIDDEN_NAMING_ALIAS_KEYS = {
    "valid_from": "not_before",
    "valid_until": "expires_at",
    "not_after": "expires_at",
    "cache_valid_until": "cache_expires_at",
    "signed_by": "verification_method",
    "sender": "sender_actor_id",
    "sender_display_name": "sender_actor_display_name",
    "source_capability": "parent_grant_id",
    "parent_space_refs": "membership_source_realm_refs",
    "parent_realm_id": "source_realm_id",
    "delivery_binding_hint": "member_delivery_binding",
    "frank": "franking_proof",
    "frank_id": "franking_proof_id",
    "requires_frank_verification": "franking_proof_verification_required",
    "retention_until": "retention_expires_at",
    "queue_item_id": "id",
    "actor_did": "actor_id",
    "principal_did": "principal_id",
    "subject_did": "subject_id",
    "series_sequence": "series_seq",
    "profileRef": "profile_ref",
    "featureRef": "feature_ref",
    "eventRef": "event_ref",
    "criticalExtension": "critical_extension",
    "parent_ref": "parent_space_id",
    "default_realm_ref": "default_realm_id",
    "metadata_encryption_profile": "metadata_encryption_floor",
    "retention_policy_ref": "retention_policy_id",
    "disclosure_policy_ref": "disclosure_policy_id",
    "rate_limit_policy_ref": "rate_limit_policy_id",
    "policy_ref": "policy_id for Policy objects, or policy_event_ref for policy-revision Event references",
    "allowed_view_refs": "allowed_view_ids",
    "allowed_strand_refs": "allowed_strand_ids",
    "allowed_circle_refs": "allowed_circle_ids",
    "denied_strand_refs": "denied_strand_ids",
    "allowed_space_refs": "allowed_space_ids",
    "denied_space_refs": "denied_space_ids",
    "realm_refs": "realm_ids",
    "approval_actor_refs": "approval_actor_ids",
    # Hash → digest vocabulary unification (common-fields.md §2):
    # algorithm selectors use _algorithm; hash output bytes use _digest; tree roots use _root.
    "hash_profile": "digest_algorithm",
    "previous_hash_profile": "previous_digest_algorithm",
    "payload_hash": "payload_digest",
    "state_hash": "state_digest",
    "auth_state_hash": "auth_state_digest",
    "expected_state_hash": "expected_state_digest",
    "did_document_hash": "did_document_digest",
    "old_did_document_hash": "old_did_document_digest",
    "new_did_document_hash": "new_did_document_digest",
    "old_did_document_canonical_hash": "old_did_document_canonical_digest",
    "head_event_hash": "head_event_digest",
    "prev_event_hash": "prev_event_digest",
    "audit_policy_version_hash": "audit_policy_version_digest",
    "code_hash": "code_digest",
    "sha256_hash": "sha256_digest",
    "material_hash": "material_digest",
    "leaf_hash": "leaf_digest",
    "query_hash": "query_digest",
    "event_hash": "event_digest",
    "frontier_hash": "frontier_digest",
    "membership_frontier_hash": "membership_frontier_digest",
    "policy_frontier_hash": "policy_frontier_digest",
    "discussion_metadata_hash": "discussion_metadata_digest",
    "group_info_hash": "group_info_digest",
    "ratchet_tree_hash": "ratchet_tree_digest",
    "commit_hash": "commit_digest",
    "proposal_hash": "proposal_digest",
    "keypackage_hash": "keypackage_digest",
    "device_list_hash": "device_list_digest",
    "audit_hash": "audit_digest",
    "policy_hash": "policy_digest",
    "diagnostic_hash": "diagnostic_digest",
    "external_transcript_hash": "external_transcript_digest",
    "full_transcript_hash": "full_transcript_digest",
    "request_canonical_hash": "request_canonical_digest",
    "source_ip_hash": "source_ip_digest",
    "retained_stub_hash": "retained_stub_digest",
    "artifact_hash": "artifact_digest",
    "original_envelope_hash": "original_envelope_digest",
    "event_ref_hash": "event_ref_digest",
    "causal_ref_hashes": "causal_ref_digests",
    "canonical_hash": "canonical_digest",
    "binding_hash": "binding_digest",
    "realm_policy_hash": "realm_policy_digest",
    "first_body_hash": "first_body_digest",
    "second_body_hash": "second_body_digest",
    "alpha_event_hash": "alpha_event_digest",
    "beta_event_hash": "beta_event_digest",
    "origin_key_state_hash": "origin_key_state_digest",
    "content_hash": "content_digest",
    "signed_payload_hash": "signed_payload_digest",
    "avatar_ref": "avatar_blob_ref",
    "icon_blob": "icon_blob_ref",
    "derived_hash_prefix": "derived_digest_prefix",
    "application_receipt_hash": "application_receipt_digest",
    "review_receipt_hash": "review_receipt_digest",
    "receipt_hash": "receipt_digest",
    "pattern_hash": "pattern_digest",
    "media_hash": "media_digest",
    "presentation_hash": "presentation_digest",
    "raw_document_hash": "raw_document_digest",
    "filter_hash": "filter_digest",
    "signature_over_content_hash": "signature_over_content_digest",
    "prev_frontier_hash": "prev_frontier_digest",
    "constraint_hash": "constraint_digest",
    "must_not_affect_state_hash": "must_not_affect_state_digest",
}

def is_wire_guard_file(path: Path) -> bool:
    return path.name in WIRE_GUARD_FILES


NAMING_RULES_PATH = Path(__file__).with_name("naming-convention-rules.json")
EVIDENCE_MATERIAL_AUDIT_PATH = Path(__file__).with_name("evidence-material-audit.json")
COMMON_OBJECT_FIELD_MATRIX_PATH = Path(__file__).with_name("common-object-field-matrix.json")
NAMING_RULE_MARKER_RE = re.compile(r"rule_id:\s*([A-Z0-9-]+)")
UNFOLDED_PASCAL_ACRONYM_RE = re.compile(
    r"(?:^[A-Z]{2,}(?=[A-Z][a-z])|[a-z0-9][A-Z]{2,}(?:$|[A-Z][a-z]))"
)
STAGE_VALUES = {
    "draft",
    "proposed",
    "planned",
    "in_progress",
    "blocked",
    "done",
    "cancelled",
    "superseded",
}


def check_naming_predicates(lint: Lint) -> None:
    """Apply naming predicates and retain exact aliases only as historical fallback.

    The drift registries and changelog intentionally mention legacy spellings;
    current schemas, fixtures, OpenAPI, and prose examples must not. This guard
    is driven by ``naming-convention-rules.json`` and enforces the mechanically
    decidable portion of common-fields.md §2.
    """

    rules_data = load_json(lint, NAMING_RULES_PATH)
    if not isinstance(rules_data, dict):
        return
    if rules_data.get("source_of_truth") is not False:
        lint.fail(NAMING_RULES_PATH, "naming rules are a derived predicate table, not a truth source")
    if rules_data.get("baseline") != []:
        lint.fail(NAMING_RULES_PATH, "naming convention baseline must be empty at closure")
    if rules_data.get("evidence_material_audit") != "tools/evidence-material-audit.json":
        lint.fail(NAMING_RULES_PATH, "NC-EVIDENCE-001 must point to the exact-path evidence audit")
    rules = rules_data.get("rules")
    if not isinstance(rules, list):
        lint.fail(NAMING_RULES_PATH, "rules must be an array")
        return
    rule_ids = [row.get("rule_id") for row in rules if isinstance(row, dict)]
    if len(rule_ids) != len(set(rule_ids)) or any(not isinstance(item, str) for item in rule_ids):
        lint.fail(NAMING_RULES_PATH, "rule_id values must be unique non-empty strings")
    prose_path = SPEC_ROOT / "zh" / "models" / "common-fields.md"
    prose_ids = NAMING_RULE_MARKER_RE.findall(prose_path.read_text(encoding="utf-8"))
    if len(prose_ids) != len(set(prose_ids)):
        lint.fail(prose_path, "naming rule markers must be unique")
    if set(prose_ids) != set(rule_ids):
        lint.fail(
            NAMING_RULES_PATH,
            f"narrative/predicate rule_id drift: prose-only={sorted(set(prose_ids) - set(rule_ids))}, "
            f"json-only={sorted(set(rule_ids) - set(prose_ids))}",
        )
    for row in rules:
        if not isinstance(row, dict):
            lint.fail(NAMING_RULES_PATH, "every naming rule must be an object")
            continue
        for exception in row.get("exceptions", []):
            if not isinstance(exception, dict) or not all(
                exception.get(field) for field in ("id", "basis", "reason", "anchor")
            ):
                lint.fail(NAMING_RULES_PATH, f"{row.get('rule_id')} has an incomplete exception")
                continue
            if exception.get("basis") == "external_literal" and not exception.get("external_anchor"):
                lint.fail(
                    NAMING_RULES_PATH,
                    f"{row.get('rule_id')} external_literal exception lacks external_anchor",
                )

    dto_schema_path = ARTIFACTS / "schemas" / "service-operation-dtos.schema.json"
    dto_schema = load_json(lint, dto_schema_path)
    if isinstance(dto_schema, dict):
        dto_defs = dto_schema.get("$defs")
        if isinstance(dto_defs, dict):
            for type_name in dto_defs:
                if UNFOLDED_PASCAL_ACRONYM_RE.search(type_name):
                    lint.fail(
                        dto_schema_path,
                        f"NC-TYPE-001 type name must fold acronym segments as ordinary "
                        f"PascalCase words: {type_name}",
                    )

    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    if isinstance(openapi, dict):
        components = openapi.get("components")
        schemas = components.get("schemas") if isinstance(components, dict) else None
        if isinstance(schemas, dict):
            for type_name in schemas:
                if UNFOLDED_PASCAL_ACRONYM_RE.search(type_name):
                    lint.fail(
                        openapi_path,
                        f"NC-TYPE-001 component name must fold acronym segments as ordinary "
                        f"PascalCase words: {type_name}",
                    )

    evidence_audit = load_json(lint, EVIDENCE_MATERIAL_AUDIT_PATH)
    if isinstance(evidence_audit, dict):
        if evidence_audit.get("source_of_truth") is not False:
            lint.fail(
                EVIDENCE_MATERIAL_AUDIT_PATH,
                "the evidence audit is derived from schemas and registries, not a truth source",
            )
        registrations = evidence_audit.get("registrations")
        expected_evidence_keys: dict[tuple[str, str], int] = {}
        if not isinstance(registrations, list):
            lint.fail(EVIDENCE_MATERIAL_AUDIT_PATH, "registrations must be an array")
            registrations = []
        allowed_dispositions = {
            "polymorphic_container",
            "derived_summary",
            "qualifier",
            "registry_contract",
        }
        material_family_names = {
            "proof",
            "attestation",
            "receipt",
            "commitment",
            "transcript",
        }
        for index, registration in enumerate(registrations):
            where = f"registrations[{index}]"
            if not isinstance(registration, dict):
                lint.fail(EVIDENCE_MATERIAL_AUDIT_PATH, f"{where} must be an object")
                continue
            file_name = registration.get("file")
            key = registration.get("key")
            occurrences = registration.get("occurrences")
            disposition = registration.get("disposition")
            reason = registration.get("reason")
            if not isinstance(file_name, str) or not isinstance(key, str) or "evidence" not in key:
                lint.fail(EVIDENCE_MATERIAL_AUDIT_PATH, f"{where} has an invalid file/key")
                continue
            pair = (file_name, key)
            if pair in expected_evidence_keys:
                lint.fail(EVIDENCE_MATERIAL_AUDIT_PATH, f"{where} duplicates {file_name}:{key}")
            if not isinstance(occurrences, int) or occurrences < 1:
                lint.fail(EVIDENCE_MATERIAL_AUDIT_PATH, f"{where}.occurrences must be positive")
                continue
            expected_evidence_keys[pair] = occurrences
            if disposition not in allowed_dispositions:
                lint.fail(EVIDENCE_MATERIAL_AUDIT_PATH, f"{where} has an unknown disposition")
            if not isinstance(reason, str) or not reason.strip():
                lint.fail(EVIDENCE_MATERIAL_AUDIT_PATH, f"{where} must explain the adjudication")
            families = registration.get("material_families", [])
            if disposition == "polymorphic_container":
                if (
                    not isinstance(families, list)
                    or len(set(families)) < 2
                    or any(family not in material_family_names for family in families)
                ):
                    lint.fail(
                        EVIDENCE_MATERIAL_AUDIT_PATH,
                        f"{where} must register at least two distinct material families",
                    )
            elif families:
                lint.fail(
                    EVIDENCE_MATERIAL_AUDIT_PATH,
                    f"{where} may declare material_families only for a polymorphic container",
                )

        actual_evidence_keys: dict[tuple[str, str], int] = {}

        def count_evidence_keys(file_name: str, node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if "evidence" in key:
                        pair = (file_name, key)
                        actual_evidence_keys[pair] = actual_evidence_keys.get(pair, 0) + 1
                    count_evidence_keys(file_name, value)
            elif isinstance(node, list):
                for value in node:
                    count_evidence_keys(file_name, value)

        evidence_scope = [
            *(ARTIFACTS / "schemas").glob("*.json"),
            *(ARTIFACTS / "registry").glob("*.json"),
        ]
        for evidence_path in sorted(evidence_scope):
            evidence_data = load_json(lint, evidence_path)
            if evidence_data is not None:
                count_evidence_keys(evidence_path.name, evidence_data)
        if actual_evidence_keys != expected_evidence_keys:
            missing = sorted(set(actual_evidence_keys) - set(expected_evidence_keys))
            stale = sorted(set(expected_evidence_keys) - set(actual_evidence_keys))
            count_drift = sorted(
                (pair, expected_evidence_keys[pair], actual_evidence_keys[pair])
                for pair in set(expected_evidence_keys) & set(actual_evidence_keys)
                if expected_evidence_keys[pair] != actual_evidence_keys[pair]
            )
            lint.fail(
                EVIDENCE_MATERIAL_AUDIT_PATH,
                f"evidence adjudication drift: unregistered={missing}, stale={stale}, "
                f"count_drift={count_drift}",
            )
        actual_occurrence_count = sum(actual_evidence_keys.values())
        if evidence_audit.get("audited_occurrence_count") != actual_occurrence_count:
            lint.fail(
                EVIDENCE_MATERIAL_AUDIT_PATH,
                "audited_occurrence_count does not match the registered schema/registry key count",
            )

    allowed_hash_fields = {
        "transcript_hash",
        "confirmed_transcript_hash",
        "nextKeyHashes",
        "current_key_hash",
        "current_key_hashes",
        "next_key_hash",
        "previous_next_key_hashes",
        "matches_previous_next_key_hashes",
        "hashes",
    }
    forbidden_boolean_prefixes = ("allow_", "require_", "requires_", "deny_", "force_")
    forbidden_set_prefixes = ("permitted_", "forbidden_", "blocked_", "banned_")
    forbidden_symbolic_literals = {
        "mls-rfc9420",
        "mls-exporter-aead-v1",
        "feldman-vss-sha256",
        "pedersen-vss-sha256",
        "share-hash-sha256",
        "share-hash-blake3",
        "arkret-native",
        "moq-relay",
    }

    def visit_schema(path: Path, node: Any, where: str = "$") -> None:
        if not isinstance(node, dict):
            if isinstance(node, list):
                for index, item in enumerate(node):
                    visit_schema(path, item, f"{where}[{index}]")
            return
        definitions = node.get("$defs")
        if isinstance(definitions, dict) and path.name != "service-operation-dtos.schema.json":
            for name in definitions:
                if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
                    lint.fail(path, f"{where}.$defs key `{name}` must be snake_case")
        properties = node.get("properties")
        if isinstance(properties, dict):
            for name, shape in properties.items():
                property_where = f"{where}.properties.{name}"
                is_boolean = isinstance(shape, dict) and shape.get("type") == "boolean"
                if is_boolean and name.startswith(forbidden_boolean_prefixes):
                    lint.fail(path, f"{property_where} violates NC-BOOL-001")
                if (
                    (name.endswith("_hash") or name.endswith("_hashes") or name in {"hash_profile", "hash_algorithm"})
                    and name not in allowed_hash_fields
                ):
                    lint.fail(path, f"{property_where} violates NC-HASH-001")
                if name.endswith(("_len", "_length", "_size")):
                    lint.fail(path, f"{property_where} violates NC-COUNT-001")
                if name in {"failure_code", "rejection_code"}:
                    lint.fail(path, f"{property_where} violates NC-CODE-001")
                if (
                    isinstance(shape, dict)
                    and shape.get("type") == "array"
                    and name.startswith(forbidden_set_prefixes)
                ):
                    lint.fail(path, f"{property_where} violates NC-SET-001")
                if name == "stage" and isinstance(shape, dict) and isinstance(shape.get("enum"), list):
                    if set(shape["enum"]) != STAGE_VALUES:
                        lint.fail(path, f"{property_where} reuses reserved stage outside the 8-value axis")
                visit_schema(path, shape, property_where)
        enum_values = node.get("enum")
        if isinstance(enum_values, list):
            for value in enum_values:
                if value in forbidden_symbolic_literals:
                    lint.fail(path, f"{where}.enum contains non-snake Arkret symbol `{value}`")
        for key, value in node.items():
            if key not in {"properties", "$defs", "enum"}:
                visit_schema(path, value, f"{where}.{key}")

    for schema_path in sorted((ARTIFACTS / "schemas").glob("*.json")):
        schema_data = load_json(lint, schema_path)
        if schema_data is not None:
            visit_schema(schema_path, schema_data)

    for artifact_path in raw_artifact_files():
        if "_" in artifact_path.name:
            lint.fail(artifact_path, "artifact filename violates NC-ARTIFACT-001 kebab-case rule")

    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi_text = openapi_path.read_text(encoding="utf-8")
    for match in re.finditer(r"^    ([A-Z][A-Za-z0-9]*Request):\s*$", openapi_text, re.MULTILINE):
        lint.fail(openapi_path, f"schema component `{match.group(1)}` must use RequestBody")

    negative_ids = {
        row.get("rule_id")
        for row in rules_data.get("negative_cases", [])
        if isinstance(row, dict) and row.get("expected") == "reject"
    }
    required_negative_ids = {f"NC-{axis}-001" for axis in (
        "BOOL", "COUNT", "ENUM", "TYPE", "CODE", "EVIDENCE", "ARTIFACT", "SET"
    )}
    if negative_ids != required_negative_ids:
        lint.fail(NAMING_RULES_PATH, "R1-R8 negative cases must cover every predicate exactly")

    def check_key(path: Path, where: str, key: str | None) -> None:
        if not key:
            return
        replacement = FORBIDDEN_NAMING_ALIAS_KEYS.get(key)
        if replacement:
            lint.fail(path, f"{where} uses forbidden legacy field `{key}`; use `{replacement}`")
            return
        if key != "principal_server_did" and (key == "service_did" or "_service_did" in key):
            lint.fail(
                path,
                f"{where} uses forbidden legacy service identity field `{key}`; "
                f"use `{key.replace('service_did', 'service_id')}`",
            )

    def check_json_value(path: Path, data: Any, where: str = "$") -> None:
        for json_path, _value, key in walk_json(data, where):
            check_key(path, json_path, key)

    json_paths = [p for p in all_json_files() if not is_wire_guard_file(p)]
    for path in json_paths:
        data = load_json(lint, path)
        if data is not None:
            check_json_value(path, data)

    # Prose may discuss historical spellings. Only machine objects and declared
    # JSON examples are naming-contract inputs; raw-word blacklists create false
    # positives when protocol rationale names a rejected spelling.
    for path in markdown_files():
        text = read_text(path)
        for match in JSON_FENCE_RE.finditer(text):
            try:
                data = parse_json_text(match.group("body"))
            except Exception:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            check_json_value(path, data, f"json block line {line_no}")


def check_profile_dependency_graph(lint: Lint) -> None:
    """Keep the generated profile graph aligned with its canonical requirements."""

    profiles_path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    graph_path = ARTIFACTS / "registry" / "profiles-dependency-graph.json"
    profiles = load_json(lint, profiles_path)
    graph = load_json(lint, graph_path)
    if not isinstance(profiles, dict) or not isinstance(graph, dict):
        return
    requirements = profiles.get("profile_requirements")
    if not isinstance(requirements, dict):
        lint.fail(profiles_path, "profile_requirements must be an object")
        return
    expected_nodes = set(requirements)
    expected_edges: set[tuple[str, str, str]] = set()
    for profile_id, requirement in requirements.items():
        if not isinstance(requirement, dict):
            continue
        for field, kind in (
            ("inherits", "inherits"),
            ("depends_on", "depends_on"),
            ("mutually_exclusive_with", "mutually_exclusive_with"),
        ):
            for target in requirement.get(field, []):
                if isinstance(target, str):
                    expected_edges.add((profile_id, target, kind))
    actual_nodes = set(graph.get("nodes", []))
    actual_edges = {
        (row.get("from"), row.get("to"), row.get("kind"))
        for row in graph.get("edges", [])
        if isinstance(row, dict)
    }
    if actual_nodes != expected_nodes:
        lint.fail(graph_path, "generated profile graph nodes drift from profile_requirements")
    if actual_edges != expected_edges:
        lint.fail(graph_path, "generated profile graph edges drift from profile_requirements")
    if graph.get("source_of_truth") is not False:
        lint.fail(graph_path, "generated profile graph must not claim source_of_truth")


def check_common_object_field_matrix(lint: Lint) -> None:
    """Check the derived §3.1 matrix and its conditional View lifecycle cells."""

    matrix = load_json(lint, COMMON_OBJECT_FIELD_MATRIX_PATH)
    prose_path = SPEC_ROOT / "zh" / "models" / "common-fields.md"
    if not isinstance(matrix, dict):
        return
    lines = prose_path.read_text(encoding="utf-8").splitlines()
    try:
        start = next(
            index
            for index, line in enumerate(lines)
            if line.startswith("| 字段 | 组 | Realm | Circle |")
        )
    except StopIteration:
        lint.fail(prose_path, "§3.1 matrix header is missing")
        return
    headers = [cell.strip() for cell in lines[start].strip("|").split("|")]
    prose_rows: list[dict[str, str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        values = [cell.strip() for cell in line.strip("|").split("|")]
        if len(values) != len(headers):
            lint.fail(prose_path, f"§3.1 matrix row has {len(values)} cells, expected {len(headers)}")
            continue
        prose_rows.append(dict(zip(headers, values)))
    if matrix.get("headers") != headers or matrix.get("rows") != prose_rows:
        lint.fail(COMMON_OBJECT_FIELD_MATRIX_PATH, "derived matrix drifts from common-fields.md §3.1")

    by_field = {row.get("字段"): row for row in prose_rows}
    view_schema_path = ARTIFACTS / "schemas" / "view.schema.json"
    view_schema = load_json(lint, view_schema_path)
    if not isinstance(view_schema, dict):
        return
    view_properties = view_schema.get("properties", {})
    view_required = view_schema.get("required", [])
    if "state" not in view_required:
        lint.fail(view_schema_path, "View.state must be explicitly required; missing state is not a valid wire shape")
    state_property = view_properties.get("state", {}) if isinstance(view_properties, dict) else {}
    if isinstance(state_property, dict) and "default" in state_property:
        lint.fail(view_schema_path, "View.state must not declare a default")
    for raw_field, row in by_field.items():
        if not isinstance(raw_field, str) or not isinstance(row, dict):
            continue
        field = raw_field.strip("`")
        cell = row.get("View", "")
        present = field in view_properties
        if cell.startswith("—") and present:
            lint.fail(view_schema_path, f"§3.1 View.{field} is not applicable but schema declares it")
        if not cell.startswith("—") and not present and "/" not in field:
            lint.fail(view_schema_path, f"§3.1 View.{field} is applicable but schema omits it")
    state_rule = next(
        (
            rule
            for rule in view_schema.get("allOf", [])
            if isinstance(rule, dict)
            and ((rule.get("if") or {}).get("properties") or {}).get("state")
            == {"const": "tombstoned"}
        ),
        None,
    )
    if not isinstance(state_rule, dict) or "state_changed_at" not in (
        (state_rule.get("then") or {}).get("required") or []
    ):
        lint.fail(view_schema_path, "View.state_changed_at must be conditionally required for tombstoned")


def check_keypackage_claim_proof_shape(lint: Lint) -> None:
    """Self-claim uses one canonical singular proof field and rejects plural aliases."""

    path = ARTIFACTS / "schemas" / "keypackage-operations.schema.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return
    claim = ((data.get("$defs") or {}).get("key_packages_claim_request_body") or {})
    if not isinstance(claim, dict):
        lint.fail(path, "$defs.key_packages_claim_request_body must exist")
        return
    required = claim.get("required") or []
    properties = claim.get("properties") or {}
    if "holder_acceptance_proof" not in required:
        lint.fail(path, "self KeyPackage claim must require holder_acceptance_proof")
    singular = properties.get("holder_acceptance_proof") if isinstance(properties, dict) else None
    if not isinstance(singular, dict) or singular.get("$ref") != "#/$defs/keypackage_claim_proof":
        lint.fail(path, "holder_acceptance_proof must directly reference keypackage_claim_proof")
    if isinstance(properties, dict) and "proofs" in properties:
        lint.fail(path, "self KeyPackage claim must not retain a plural proofs compatibility field")


def check_event_proof_digest_shape(lint: Lint) -> None:
    """Event proofs must use event_digest, not generic payload_hash."""

    path = ARTIFACTS / "schemas" / "event-envelope.schema.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    proofs = (((data.get("properties") or {}).get("proofs") or {}).get("items") or {})
    if proofs.get("$ref") != "#/$defs/event_proof":
        lint.fail(path, "Event.properties.proofs.items must reference $defs/event_proof")

    event_proof = ((data.get("$defs") or {}).get("event_proof") or {})
    if not isinstance(event_proof, dict):
        lint.fail(path, "$defs.event_proof must exist")
        return

    required = event_proof.get("required") or []
    properties = event_proof.get("properties") or {}
    if "event_digest" not in required or "event_digest" not in properties:
        lint.fail(path, "$defs.event_proof must require event_digest")
    if "payload_hash" in required or "payload_hash" in properties:
        lint.fail(path, "$defs.event_proof must not expose payload_hash; use event_digest")


LEGACY_ANNOUNCE_ID_RE = re.compile(r"\bann_(?:[0-9a-f]{16,64}|<hex>|\*)\b")


def check_legacy_announce_id_form(lint: Lint) -> None:
    """Reject the pre-registry Directory announce id spelling.

    ``ann_<hex>`` appeared in prose before Directory announce records were
    registered as typed IDs. The canonical v1 wire form is now
    ``ak:announce:<uuidv7>``; keeping this guard prevents examples or fixtures
    from reintroducing the unregistered local prefix.
    """
    scan_paths = sorted(SPEC_ROOT.rglob("*.md"))
    scan_paths.extend(raw_artifact_files())
    for path in scan_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if LEGACY_ANNOUNCE_ID_RE.search(line):
                lint.fail(
                    path,
                    f"line {line_no}: legacy Directory announce id form `ann_*` is forbidden; "
                    "use `ak:announce:<uuidv7>`.",
                )


def check_join_policy_gate_id_uniqueness(lint: Lint) -> None:
    """Enforce property-level gate_id uniqueness within join_policy gates[].

    JSON Schema 2020-12 has no native "unique by property" keyword: ``uniqueItems``
    only catches whole-object duplicates. The wire contract for
    ``ak.realm.join_policy`` (see zh/governance/join-policy.md §3.1) requires that
    ``gate_id`` be unique across siblings in ``gates[]`` so that audit refs in
    ``ak.member.state{gate_proofs[gate_id=…]}`` remain unambiguous; the canonical
    reject reason is ``schema_violation reason_code=join_policy_duplicate_gate_id``.

    This lint walks every JSON artifact and every Markdown ``json`` example,
    finds objects that look like a join_policy value (have a ``gates`` array
    whose items have ``gate_id``), and rejects any with duplicate ``gate_id``
    across siblings. Markdown blocks demonstrating the negative case MUST be
    annotated with ``expect=invalid first_error="join_policy_duplicate_gate_id"``
    in their fence header to be exempted (matching the existing negative-case
    convention used elsewhere in this linter).
    """

    def walk(value: Any, on_object: Any) -> None:
        if isinstance(value, dict):
            on_object(value)
            for child in value.values():
                walk(child, on_object)
        elif isinstance(value, list):
            for child in value:
                walk(child, on_object)

    def check_value(path: Path, value: Any, where: str) -> None:
        def on_object(obj: dict) -> None:
            gates = obj.get("gates")
            if not isinstance(gates, list) or not gates:
                return
            # heuristic: items must look like join_policy gates (have gate_id+kind)
            looks_like_join_policy = all(
                isinstance(g, dict) and "gate_id" in g and "kind" in g
                for g in gates
            )
            if not looks_like_join_policy:
                return
            seen: set[str] = set()
            for g in gates:
                gid = g.get("gate_id")
                if not isinstance(gid, str):
                    continue
                if gid in seen:
                    lint.fail(
                        path,
                        f"{where}: join_policy gates[] contains duplicate gate_id "
                        f"'{gid}' — see error-code-registry reason "
                        f"`join_policy_duplicate_gate_id` and join-policy.md §3.1.",
                    )
                    return
                seen.add(gid)

        walk(value, on_object)

    # JSON files under artifacts/
    for path in all_json_files():
        if ARTIFACTS not in path.parents:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        check_value(path, data, "value")

    # Markdown json fences
    fence_re = re.compile(r"```json([^\n]*)\n(.*?)```", re.DOTALL)
    for path in markdown_files():
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for match in fence_re.finditer(text):
            header = match.group(1) or ""
            body = match.group(2)
            # Skip explicit negative cases tagged in the fence header
            if "join_policy_duplicate_gate_id" in header and "expect=invalid" in header:
                continue
            try:
                data = json.loads(body)
            except Exception:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            check_value(path, data, f"json block at line {line_no}")


def check_content_composite_uses_parts(lint: Lint) -> None:
    """Reject legacy ``blocks`` spelling on ak.content.composite examples.

    The canonical composite child field is required as ``parts``. ``blocks`` is
    too tied to document layout semantics and is now listed in
    forbidden-wire-fields.json for the content_block_composite context. JSON
    Schema rejects it on real wire payloads; this lint keeps artifacts and prose
    JSON examples aligned.
    """

    def walk(value: Any, on_object: Any) -> None:
        if isinstance(value, dict):
            on_object(value)
            for child in value.values():
                walk(child, on_object)
        elif isinstance(value, list):
            for child in value:
                walk(child, on_object)

    def check_value(path: Path, value: Any, where: str) -> None:
        def on_object(obj: dict) -> None:
            if obj.get("kind") != "ak.content.composite":
                return
            if "blocks" in obj:
                lint.fail(
                    path,
                    f"{where}: ak.content.composite uses legacy `blocks`; "
                    "canonical wire field is `parts`.",
                )
            if "parts" not in obj:
                lint.fail(
                    path,
                    f"{where}: ak.content.composite is missing required `parts`.",
                )

        walk(value, on_object)

    for path in all_json_files():
        if ARTIFACTS not in path.parents:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        check_value(path, data, "value")

    fence_re = re.compile(r"```json([^\n]*)\n(.*?)```", re.DOTALL)
    for path in markdown_files():
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for match in fence_re.finditer(text):
            header = match.group(1) or ""
            if "content_block_legacy_blocks" in header and "expect=invalid" in header:
                continue
            try:
                data = json.loads(match.group(2))
            except Exception:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            check_value(path, data, f"json block at line {line_no}")


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


VALUE_PROJECTION_DIGEST_INPUTS = {
    "base64url_decoded_bytes",
    "canonical_json_bytes",
    "event_payload_canonical_bytes",
}

# Reducer derivations a cell write may add on top of the projected payload.
#
# The projected cell value is what a `state_root` leaf hashes, so a field the
# reducer computes rather than copies has to be named here or two conforming
# implementations could disagree on the root while both matching the schema.
# The set is closed: a derivation is a normative reducer rule, not an
# implementation's private cache. See zh/authz/capabilities.md section 10.
CELL_WRITE_DERIVATIONS = {
    "capability_authority_depth",
    "capability_authority_root_refs",
}


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

# encoding.md 9.5.1: a registered path is dot-separated *named* fields only.
# Array indices, wildcards and empty segments have no defined evaluation, so a
# registry carrying one would pass lint yet be underivable.
FIELD_PATH_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")


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


CONFLICT_RECOVERY_KIND = "ak.state.conflict_recovery"


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


# encoding.md §9.5.1 closes the set of Event Envelope fields a registered cell
# subject may read.
#
# `envelope.actor_id` is the accountable actor. `envelope.event_id` is
# Event-derived object identity: the created object's id is the create Event's
# own event_id retyped to the kind declared by `cell_subject.kind`
# (zh/models/common-fields.md), the payload MUST NOT carry the id, so the
# envelope is the only legal source and no second truth exists.
#
# One constant, three consumers: this per-occurrence lint, the prose sentence in
# §9.5.1, and the set the registry actually uses. `check_envelope_subject_source_whitelist`
# reconciles all three — §9.5.1 once forbade `envelope.event_id` outright while
# six registered create kinds were already using it, and both sides passed the
# release gate.
ENVELOPE_SUBJECT_SOURCES = ("envelope.actor_id", "envelope.event_id")

# Envelope fields §9.5.1 names as explicitly forbidden. Called out separately
# because "absent from the whitelist" and "named as a trap" are different
# statements, and the trap is what the prose spends words on.
ENVELOPE_SUBJECT_FORBIDDEN = ("envelope.realm_id", "envelope.executed_by")


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


def check_envelope_subject_source_whitelist(lint: Lint) -> None:
    """Reconcile the §9.5.1 prose whitelist with what the registry actually uses.

    Three statements of the same closed set have to agree: the sentence in
    `encoding.md` §9.5.1, [`ENVELOPE_SUBJECT_SOURCES`], and the envelope sources
    the registry really reads. Nothing compared them before, and they diverged:
    §9.5.1 forbade `envelope.event_id` as a cell subject in prose while six
    registered create kinds were already using it, and the release gate was green
    on both sides — the per-occurrence lint only ever checked each registry row
    against its own hard-coded copy of the list.

    An unused whitelist entry fails too. A permission the registry does not
    exercise is exactly the state that lets the prose and the registry drift
    apart unnoticed.
    """
    prose_path = SPEC_ROOT / "zh" / "conformance" / "encoding.md"
    if not prose_path.exists():
        lint.fail(prose_path, "encoding.md is missing")
        return
    text = read_text(prose_path)

    # The sentence that states the whitelist. Anchored on the phrase rather than a
    # section digest so rewording the surrounding paragraph stays free, while
    # deleting or renaming the whitelist sentence fails loudly.
    sentence = next(
        (line for line in text.splitlines() if "envelope 来源白名单" in line),
        None,
    )
    if sentence is None:
        lint.fail(
            prose_path,
            "§9.5.1 must keep a sentence naming the closed `envelope 来源白名单`; "
            "the machine check reads its members from there",
        )
        return
    prose_sources = set(re.findall(r"`(envelope\.[A-Za-z0-9_.]+)`", sentence))
    declared = set(ENVELOPE_SUBJECT_SOURCES)
    forbidden = set(ENVELOPE_SUBJECT_FORBIDDEN)
    if prose_sources != declared | forbidden:
        lint.fail(
            prose_path,
            "§9.5.1 whitelist sentence names "
            f"{sorted(prose_sources)} but the lint declares whitelist="
            f"{sorted(declared)} forbidden={sorted(forbidden)}",
        )

    # What the registry actually reads. Only `registry/`: a fixture negative case
    # legitimately names a forbidden source in order to assert its rejection.
    used: dict[str, list[str]] = {}

    def collect(node: Any, owner: Path, json_path: str) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                collect(child, owner, f"{json_path}.{key}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                collect(child, owner, f"{json_path}[{index}]")
        elif isinstance(node, str) and node.startswith("envelope."):
            used.setdefault(node, []).append(f"{owner.name}{json_path}")

    for registry_path in sorted((ARTIFACTS / "registry").glob("*.json")):
        registry = load_json(lint, registry_path)
        if registry is not None:
            collect(registry, registry_path, "$")

    for source, where in sorted(used.items()):
        if source in forbidden:
            lint.fail(
                ARTIFACTS / "registry",
                f"§9.5.1 forbids {source} as a subject source but the registry reads it at "
                f"{where[0]}",
            )
        elif source not in declared:
            lint.fail(
                ARTIFACTS / "registry",
                f"registry reads unregistered envelope source {source} at {where[0]}",
            )
    for source in sorted(declared - set(used)):
        lint.fail(
            prose_path,
            f"§9.5.1 whitelists {source} but no registered cell subject reads it; "
            "a permission nothing exercises is how the prose and the registry drifted apart",
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
        sources = [key for key in ("literal", "field", "select", "digest_of") if key in member]
        if len(sources) != 1:
            lint.fail(path, f"{member_ref} must declare exactly one of literal/field/select/digest_of")
            continue
        source = sources[0]
        if source == "field":
            lint_field_path(lint, path, f"{member_ref}.field", member["field"])
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


EFFECT_PROJECTION_ENVELOPE_FIELDS = {
    "event_id",
    "kind",
    "realm_id",
    "actor_id",
    "actor_seq",
    "created_at",
    "hlc",
    "executed_by",
    "authorization_ref",
}


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


def check_operation_durable_effect_contract(lint: Lint) -> None:
    path = ARTIFACTS / "registry" / "contract-registry.json"
    root = load_json(lint, path) or {}
    event_registry = root.get("event_kind_registry", {})
    operation_registry = root.get("operation_registry", {})
    rows = event_registry.get("event_kinds", []) if isinstance(event_registry, dict) else []
    operations = operation_registry.get("operations", []) if isinstance(operation_registry, dict) else []
    active = {
        row.get("event_kind")
        for row in rows
        if isinstance(row, dict) and row.get("status") != "retired"
    }
    actor_private = {
        row.get("event_kind")
        for row in rows
        if isinstance(row, dict)
        and row.get("status") != "retired"
        and row.get("wire_scope") == "actor_private_event"
    }
    if not isinstance(operations, list):
        lint.fail(path, "operation_registry.operations must be an array")
        return
    for operation in operations:
        if not isinstance(operation, dict) or "idempotency_mechanism" not in operation:
            continue
        operation_id = operation.get("operation_id", "<unknown>")
        effect = operation.get("durable_effect")
        if not isinstance(effect, dict):
            lint.fail(path, f"{operation_id} is a write operation without durable_effect")
            continue
        kind = effect.get("kind")
        if kind == "event_log":
            event_kinds = effect.get("event_kinds")
            source = effect.get("event_kind_source")
            sources = effect.get("event_kind_sources")
            mapping_forms = sum(value is not None for value in (event_kinds, source, sources))
            if mapping_forms != 1:
                lint.fail(path, f"{operation_id} event_log effect must declare exactly one mapping form")
            if event_kinds is not None:
                if not isinstance(event_kinds, list) or not event_kinds:
                    lint.fail(path, f"{operation_id}.durable_effect.event_kinds must be non-empty")
                else:
                    for event_kind in event_kinds:
                        if event_kind not in active or event_kind in actor_private:
                            lint.fail(path, f"{operation_id} maps to invalid shared Event {event_kind!r}")
            if source is not None and (
                not isinstance(source, str) or not source.startswith("$request.")
            ):
                lint.fail(path, f"{operation_id}.event_kind_source must be a $request JSON path")
            if sources is not None and (
                not isinstance(sources, list)
                or not sources
                or any(
                    not isinstance(item, str) or not item.startswith("$request.")
                    for item in sources
                )
                or len(sources) != len(set(sources))
            ):
                lint.fail(
                    path,
                    f"{operation_id}.event_kind_sources must be a non-empty unique array of $request JSON paths",
                )
        elif kind == "actor_private_event":
            if effect.get("event_kind") not in actor_private:
                lint.fail(path, f"{operation_id} must map actor_private_event to an active private kind")
        elif kind == "none":
            rationale = effect.get("rationale")
            if not isinstance(rationale, str) or not rationale:
                lint.fail(path, f"{operation_id} durable_effect none must state a rationale")
        else:
            lint.fail(path, f"{operation_id} has unknown durable_effect kind {kind!r}")


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
    event_derived_id_kinds = {
        row.get("kind")
        for row in (id_rows if isinstance(id_rows, list) else [])
        if isinstance(row, dict) and row.get("id_form") == "event_derived"
    }
    for row in id_rows if isinstance(id_rows, list) else []:
        if not isinstance(row, dict):
            continue
        kind = row.get("kind")
        wire_form = row.get("wire_form")
        if isinstance(kind, str) and not re.fullmatch(r"[a-z0-9_]+", kind):
            lint.fail(id_path, f"id kind has invalid format: {kind}")
        if isinstance(kind, str) and isinstance(wire_form, str) and not wire_form.startswith(f"ak:{kind}:"):
            lint.fail(id_path, f"{kind} wire_form must start with ak:{kind}:")

    special_id_kinds = unique_values(lint, id_path, id_registry.get("special_forms", []), "kind")

    operation_rows = operation_registry.get("operations", [])
    operation_ids = unique_values(lint, operation_path, operation_rows, "operation_id")
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
        compatibility_bindings = row.get("http_compatibility_bindings")
        if compatibility_bindings is not None:
            if not isinstance(http, str) or not http.startswith("QUERY "):
                lint.fail(operation_path, f"{operation_id} compatibility bindings require a canonical QUERY binding")
            if not isinstance(compatibility_bindings, list) or not compatibility_bindings:
                lint.fail(operation_path, f"{operation_id}.http_compatibility_bindings must be a non-empty array")
            else:
                seen_compatibility_http: set[str] = set()
                for binding in compatibility_bindings:
                    if not isinstance(binding, dict):
                        lint.fail(operation_path, f"{operation_id}.http_compatibility_bindings entries must be objects")
                        continue
                    compatibility_http = binding.get("http")
                    request_encoding = binding.get("request_encoding")
                    if not isinstance(compatibility_http, str) or not re.fullmatch(r"(?:GET|POST) /\S+", compatibility_http):
                        lint.fail(operation_path, f"{operation_id} has invalid compatibility HTTP binding {compatibility_http!r}")
                    elif compatibility_http in seen_compatibility_http:
                        lint.fail(operation_path, f"{operation_id} repeats compatibility HTTP binding {compatibility_http!r}")
                    else:
                        seen_compatibility_http.add(compatibility_http)
                    if request_encoding not in {"query_string", "json_body"}:
                        lint.fail(operation_path, f"{operation_id} has invalid compatibility request_encoding {request_encoding!r}")
                    if isinstance(compatibility_http, str) and compatibility_http.startswith("GET ") and request_encoding != "query_string":
                        lint.fail(operation_path, f"{operation_id} GET compatibility binding must use query_string")
                    if isinstance(compatibility_http, str) and compatibility_http.startswith("POST ") and request_encoding != "json_body":
                        lint.fail(operation_path, f"{operation_id} POST compatibility binding must use json_body")
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
                lint.fail(
                    operation_path,
                    f"{operation_id} may declare uncertain_outcome only when retry_safe=false",
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


def check_schema_refs(lint: Lint, known: dict[str, set[str]]) -> None:
    # The current-wire rejection guard intentionally names forbidden fields
    # that are absent from active registries.
    drift_tracking_files = {"forbidden-wire-fields.json"}
    for path in all_json_files():
        data = load_json(lint, path)
        if data is None:
            continue
        if path.name != "event-envelope-negative-fixture.json":
            check_event_ref_invariants_in_value(lint, path, "$", data)
        for json_path, value, key in walk_json(data):
            if key == "$ref" and isinstance(value, str):
                ensure_relative_file(lint, path, path.parent, value, f"{json_path} $ref")
        if path.name in drift_tracking_files:
            continue
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
    for key in (
        "implementation_profiles",
        "identity_extension_profiles",
        "deployment_profiles",
        "hardening_profiles",
    ):
        values = data.get(key, [])
        if isinstance(values, list):
            declared_profiles.update(item for item in values if isinstance(item, str) and item.startswith("ak.profile."))

    for profile_id in sorted(declared_profiles - set(requirements.keys())):
        lint.fail(path, f"profile_requirements missing declared profile: {profile_id}")

    action_registry = load_json(lint, ARTIFACTS / "registry" / "capability-action-registry.json") or {}
    capability_action_rows = {
        row["action"]: row
        for row in (action_registry.get("actions", []) if isinstance(action_registry, dict) else [])
        if isinstance(row, dict) and isinstance(row.get("action"), str)
    }

    fixture_files = {fixture.name for fixture in (ARTIFACTS / "fixtures").glob("*.json")}
    fixture_documents = {
        fixture.name: load_json(lint, fixture)
        for fixture in (ARTIFACTS / "fixtures").glob("*.json")
    }
    vector_registry = load_json(lint, ARTIFACTS / "registry" / "vector-registry.json")
    event_payload_schema_path = ARTIFACTS / "schemas" / "event-payload.schema.json"
    event_payload_schema = load_json(lint, event_payload_schema_path)
    applet_registration_payload = (
        event_payload_schema.get("$defs", {}).get("applet_registration_payload", {})
        if isinstance(event_payload_schema, dict)
        else {}
    )
    vector_ids = {
        row.get("vector_id")
        for row in (vector_registry or {}).get("vectors", [])
        if isinstance(row, dict) and isinstance(row.get("vector_id"), str)
    }
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
        if "summary" in requirement:
            lint.fail(path, f"{profile_id} uses summary for profile metadata; use description")
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
                if scope not in {"durable_event", "actor_private_event"}:
                    lint.fail(path, f"{profile_id} rejects unknown wire_scope: {event_kind}")
                continue
            if event_kind not in known["event_kinds"]:
                lint.fail(path, f"{profile_id} rejects unknown Event.kind: {event_kind}")

        for schema_id in requirement.get("required_schemas", []):
            if schema_id not in known["schema_ids"]:
                lint.fail(path, f"{profile_id} requires unknown schema: {schema_id}")

        for constraint_kind in requirement.get("required_constraint_kinds", []):
            if constraint_kind not in known["constraint_types"]:
                lint.fail(path, f"{profile_id} requires invalid constraint_kind: {constraint_kind}")

        if "owner_grant_authority_actions" in requirement:
            lint.fail(
                path,
                f"{profile_id}: owner_grant_authority_actions is retired; a profile action "
                "is owner-grantable exactly when the Realm declares the profile "
                "(capabilities.md section 3.2)",
            )

        authority_rule_keys = {
            "issuer_action",
            "issuer_owner_authority_allowed",
            "grantable_action",
            "required_registration_event_kind",
            "required_claimed_profile",
            "required_constraint_kind",
            "required_constraint_subkind",
            "subject_binding",
            "scope_binding",
            "epoch_binding",
            "requested_action_binding",
        }
        for index, rule in enumerate(requirement.get("non_event_grant_authority_rules", [])):
            label = f"{profile_id}.non_event_grant_authority_rules[{index}]"
            if not isinstance(rule, dict) or set(rule.keys()) != authority_rule_keys:
                lint.fail(path, f"{label} must use the closed non-event authority rule shape")
                continue
            if rule.get("issuer_action") not in known["capability_actions"]:
                lint.fail(path, f"{label} issuer_action is not registered")
            if not isinstance(rule.get("issuer_owner_authority_allowed"), bool):
                lint.fail(path, f"{label}.issuer_owner_authority_allowed must be a boolean")
            if rule.get("grantable_action") not in known["capability_actions"]:
                lint.fail(path, f"{label} grantable_action is not registered")
            if rule.get("required_registration_event_kind") not in known["event_kinds"]:
                lint.fail(path, f"{label} required_registration_event_kind is not registered")
            if rule.get("required_claimed_profile") not in known["profiles"]:
                lint.fail(path, f"{label} required_claimed_profile is not registered")
            if rule.get("required_constraint_kind") not in known["constraint_types"]:
                lint.fail(path, f"{label} required_constraint_kind is not registered")
            if rule.get("required_constraint_subkind") != "applet_authority":
                lint.fail(path, f"{label} uses an unsupported constraint subkind")
            expected_bindings = {
                "subject_binding": "registration.service_id",
                "scope_binding": "grant.resource_exact_registration_scope",
                "epoch_binding": "constraint.registration_epoch_exact_registration",
                "requested_action_binding": "grant.action_in_registration.requested_scopes",
            }
            for field, expected in expected_bindings.items():
                if rule.get(field) != expected:
                    lint.fail(path, f"{label}.{field} must equal {expected}")
            if rule.get("required_registration_event_kind") == "ak.applet.registration":
                registration_required = applet_registration_payload.get("required", [])
                registration_properties = applet_registration_payload.get("properties", {})
                if "claimed_profiles" not in registration_required:
                    lint.fail(
                        event_payload_schema_path,
                        f"{label} requires durable claimed_profiles but applet registration does not require it",
                    )
                if "claimed_profiles" not in registration_properties:
                    lint.fail(
                        event_payload_schema_path,
                        f"{label} requires durable claimed_profiles but applet registration does not define it",
                    )

        for fixture in requirement.get("required_fixtures", []):
            if fixture not in fixture_files:
                lint.fail(path, f"{profile_id} requires missing fixture: {fixture}")

        for vector_id in requirement.get("required_vectors", []):
            if vector_id not in vector_ids:
                lint.fail(path, f"{profile_id} requires unknown vector: {vector_id}")

        for runner_suite in requirement.get("required_runner_suites", []):
            if not isinstance(runner_suite, dict):
                lint.fail(path, f"{profile_id} required_runner_suites entry must be an object")
                continue
            suite = runner_suite.get("suite")
            fixture = runner_suite.get("artifact_fixture")
            entrypoint = runner_suite.get("entrypoint")
            if not isinstance(suite, str) or not suite:
                lint.fail(path, f"{profile_id} runner suite requires non-empty suite")
                continue
            if not isinstance(fixture, str) or fixture not in fixture_documents:
                lint.fail(path, f"{profile_id} runner suite references missing fixture: {fixture!r}")
                continue
            fixture_document = fixture_documents[fixture]
            if not isinstance(fixture_document, dict) or fixture_document.get("suite") != suite:
                lint.fail(path, f"{profile_id} runner suite {suite!r} does not match {fixture}")
                continue
            fixture_runner = fixture_document.get("runner")
            if not isinstance(fixture_runner, dict):
                lint.fail(path, f"{profile_id} runner suite fixture {fixture} has no runner")
                continue
            if entrypoint is not None and fixture_runner.get("entrypoint") != entrypoint:
                lint.fail(path, f"{profile_id} runner suite entrypoint does not match {fixture}")

        feature_discovery = requirement.get("feature_discovery")
        if not isinstance(feature_discovery, dict):
            lint.fail(path, f"{profile_id} feature_discovery must be an object")
        else:
            if not isinstance(feature_discovery.get("required"), list):
                lint.fail(path, f"{profile_id} feature_discovery.required must be a list")
            if not isinstance(feature_discovery.get("unsupported_optional"), str):
                lint.fail(path, f"{profile_id} feature_discovery.unsupported_optional must be a string")


def check_sdk_conformance_contract(lint: Lint) -> None:
    path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return
    contract = data.get("sdk_conformance_contract")
    if not isinstance(contract, dict):
        lint.fail(path, "missing sdk_conformance_contract")
        return
    if contract.get("contract_version") != "1":
        lint.fail(path, "sdk_conformance_contract.contract_version must be '1'")
    evidence_kinds = contract.get("evidence_kinds")
    if not isinstance(evidence_kinds, list) or not evidence_kinds:
        lint.fail(path, "sdk_conformance_contract.evidence_kinds must be non-empty")
        evidence_kinds = []
    clauses = contract.get("clauses")
    if not isinstance(clauses, list) or not clauses:
        lint.fail(path, "sdk_conformance_contract.clauses must be non-empty")
        return
    seen: set[str] = set()
    allowed_grades = {"V", "A", "U"}
    for index, clause in enumerate(clauses):
        label = f"sdk_conformance_contract.clauses[{index}]"
        if not isinstance(clause, dict):
            lint.fail(path, f"{label} must be an object")
            continue
        clause_id = clause.get("clause_id")
        if not isinstance(clause_id, str) or not re.fullmatch(r"AK-SDK-[0-9]{3}", clause_id):
            lint.fail(path, f"{label}.clause_id must be AK-SDK-NNN")
        elif clause_id in seen:
            lint.fail(path, f"{label}.clause_id duplicates {clause_id}")
        else:
            seen.add(clause_id)
        grades = clause.get("grades")
        if not isinstance(grades, list) or not grades or any(grade not in allowed_grades for grade in grades):
            lint.fail(path, f"{label}.grades must be a non-empty subset of V/A/U")
        required_evidence = clause.get("required_evidence")
        if not isinstance(required_evidence, list) or not required_evidence:
            lint.fail(path, f"{label}.required_evidence must be non-empty")
        elif any(kind not in evidence_kinds for kind in required_evidence):
            lint.fail(path, f"{label}.required_evidence contains an unknown evidence kind")
        source_anchor = clause.get("source_anchor")
        if not isinstance(source_anchor, str) or not source_anchor.startswith("spec/v1/zh/") or "#" not in source_anchor:
            lint.fail(path, f"{label}.source_anchor must reference a stable zh/ heading")
    expected_ids = {f"AK-SDK-{index:03d}" for index in range(1, 24)}
    if seen != expected_ids:
        lint.fail(path, "sdk_conformance_contract must define exactly AK-SDK-001 through AK-SDK-023")

    schema_path = ARTIFACTS / "schemas" / "sdk-conformance-claim.schema.json"
    fixture_path = ARTIFACTS / "fixtures" / "sdk-conformance-claim-fixture.json"
    if not schema_path.is_file():
        lint.fail(path, "sdk_conformance_contract requires schemas/sdk-conformance-claim.schema.json")
    if not fixture_path.is_file():
        lint.fail(path, "sdk_conformance_contract requires fixtures/sdk-conformance-claim-fixture.json")
    schema_registry = load_json(lint, ARTIFACTS / "registry" / "schema-registry.json")
    registered_schema_ids = {
        row.get("schema_id")
        for row in schema_registry.get("schemas", [])
        if isinstance(row, dict)
    } if isinstance(schema_registry, dict) else set()
    if "ak.schema.sdk_conformance_claim.v1" not in registered_schema_ids:
        lint.fail(path, "sdk conformance claim schema is not registered")


def check_fixture_runner_contract(lint: Lint) -> None:
    fixture_root = ARTIFACTS / "fixtures"
    runner_registry_path = ARTIFACTS / "registry" / "runner-kind-registry.json"
    runner_registry = load_json(lint, runner_registry_path)
    rows = runner_registry.get("runner_kinds", []) if isinstance(runner_registry, dict) else []
    allowed_kinds = {
        row.get("kind")
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("kind"), str)
    }
    if not allowed_kinds:
        lint.fail(runner_registry_path, "runner kind registry must declare a non-empty closed vocabulary")
        return
    if len(allowed_kinds) != len(rows):
        lint.fail(runner_registry_path, "runner kind registry contains duplicate or malformed kind entries")
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not isinstance(row.get("execution_contract"), str) or not row["execution_contract"].strip():
            lint.fail(runner_registry_path, f"runner kind {row.get('kind')!r} lacks execution_contract")
        if row.get("owner") not in {"protocol", "in_tree_lint", "cotest", "in_tree_lint_and_cotest"}:
            lint.fail(runner_registry_path, f"runner kind {row.get('kind')!r} has invalid owner")
        if row.get("execution_status") != "contract_published":
            lint.fail(runner_registry_path, f"runner kind {row.get('kind')!r} must publish its execution contract")
    executable_registry_assertions = {
        "error_code_registry_coverage_fixture": {
            "unique_top_level_codes",
            "unique_reason_codes",
            "operation_errors_registered",
            "reason_references_registered",
            "layering_is_explicit",
        },
        "operation_registry_coverage_fixture": {
            "catalog_registry_bijection",
            "registry_openapi_bijection",
            "registry_binding_coverage",
            "schema_refs_resolve",
            "write_retry_contract",
            "read_retry_contract",
            "write_durable_effect_contract",
        },
        "event_kind_lattice_dispatch_fixture": {
            "registered_dispatch_target",
            "or_set_bottom_never_rejects",
            "family_semantics_present",
            "unknown_dispatch_fails_closed",
            "fsm_family_contract_closure",
            "actor_private_contract_closure",
            "lifecycle_modality_scope",
        },
        "event_kind_payload_coverage_fixture": {
            "catalog_registry_bijection",
            "payload_schema_ref_resolves",
            "wire_scope_matches_envelope",
            "unknown_durable_kind_fails_closed",
        },
    }
    for path in sorted(fixture_root.glob("*.json")):
        data = load_json(lint, path)
        if not isinstance(data, dict):
            continue
        runner = data.get("runner")
        if not isinstance(runner, dict):
            lint.fail(path, "top-level runner must be an object with runner.kind")
            continue
        kind = runner.get("kind")
        if not isinstance(kind, str) or not kind:
            lint.fail(path, "top-level runner.kind must be a non-empty string")
            continue
        if kind not in allowed_kinds:
            lint.fail(path, f"runner.kind is not registered: {kind!r}")
            continue
        if kind == "named_suite":
            entrypoint = runner.get("entrypoint")
            if not isinstance(entrypoint, str) or not re.fullmatch(r"ak\.suite\.[a-z0-9_.-]+\.v1", entrypoint):
                lint.fail(path, "runner.kind=named_suite requires a tool-neutral ak.suite.*.v1 entrypoint")
        if kind == "registry_coverage":
            inputs = runner.get("inputs")
            if not isinstance(inputs, list) or not inputs:
                lint.fail(path, "runner.kind=registry_coverage requires non-empty inputs")
            else:
                for relative in inputs:
                    if not isinstance(relative, str) or not (ARTIFACTS / relative).is_file():
                        lint.fail(path, f"registry coverage input does not exist: {relative!r}")
            suite = data.get("suite")
            expected = executable_registry_assertions.get(suite)
            assertions = data.get("assertions")
            actual = {
                row.get("id") for row in assertions if isinstance(row, dict) and isinstance(row.get("id"), str)
            } if isinstance(assertions, list) else set()
            if expected is None or actual != expected:
                lint.fail(path, f"registry coverage assertions are not bound to the executable lint contract: {sorted(actual)}")

        if path.name == "morph-schema-migration-fixture.json":
            vectors = data.get("vectors")
            if not isinstance(vectors, list) or not vectors:
                lint.fail(path, "morph migration runner requires vectors")
                continue
            observed_rules: set[str] = set()
            for vector in vectors:
                if not isinstance(vector, dict):
                    lint.fail(path, "morph migration vector must be an object")
                    continue
                fields = dict(((vector.get("input") or {}).get("fields") or {}))
                rules = (((vector.get("input") or {}).get("payload") or {}).get("transformation_rules") or [])
                for rule in rules:
                    rule_id = rule.get("rule") if isinstance(rule, dict) else None
                    observed_rules.add(rule_id)
                    if rule_id == "ak.transform.identity.v1":
                        continue
                    if rule_id == "ak.transform.rename.v1":
                        source, target = rule.get("from"), rule.get("to")
                        if source not in fields or target in fields:
                            lint.fail(path, f"{vector.get('vector_id')} rename precondition failed")
                            continue
                        fields[target] = fields.pop(source)
                    elif rule_id == "ak.transform.type_widen.v1":
                        if (rule.get("from_kind"), rule.get("to_kind")) != ("integer", "number") or not isinstance(fields.get(rule.get("field")), int):
                            lint.fail(path, f"{vector.get('vector_id')} type widening precondition failed")
                    elif rule_id == "ak.transform.default_backfill.v1":
                        fields.setdefault(rule.get("to"), rule.get("value"))
                    else:
                        lint.fail(path, f"{vector.get('vector_id')} uses unknown transformation rule {rule_id!r}")
                if fields != vector.get("expected_output"):
                    lint.fail(path, f"{vector.get('vector_id')} executable transformation output mismatch")
                canonical = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                digest = "sha256:" + hashlib.sha256(canonical).hexdigest()
                if digest != vector.get("expected_output_digest"):
                    lint.fail(path, f"{vector.get('vector_id')} expected_output_digest mismatch")
            required_rules = {
                "ak.transform.identity.v1",
                "ak.transform.rename.v1",
                "ak.transform.type_widen.v1",
                "ak.transform.default_backfill.v1",
            }
            if observed_rules != required_rules:
                lint.fail(path, f"morph runner rule coverage mismatch: {sorted(observed_rules)}")


# --- event_log operations must carry the signature that makes the Event legal ---
#
# `durable_effect.kind = "event_log"` says the operation puts a signed Event into
# the log. The service MUST NOT produce that signature: `capabilities.md` §118 and
# §361, `conformance-profiles.md` §638, `applet-schema.md` §234 and
# `key-management.md` §411 all forbid a service co-signing or synthesizing an
# Event. So the signature can only come from the request, which means the request
# schema MUST reach a caller-signed Event.
#
# An operation that declares an event_log effect and takes no signed Event is
# declaring a durable effect it cannot legally produce. soland implements exactly
# these operations through `accept_local_operations`, which builds no wire Event at
# all — and five of them went on to mint the object id the missing Event would have
# derived.
#
# Two shapes count, both already in use: the `EventInitialSubmission` wrapper
# (agent lifecycle, `events.command.submit`) and a bare `event-envelope.schema.json`
# reference (`applet.command.install`'s `registration_event`).
SIGNED_EVENT_REQUEST_MARKERS = ("EventInitialSubmission", "event-envelope.schema.json")

# `actor_private_event` is in scope for the same reason `event_log` is.
# `event-and-patch.md` §342 is explicit: actor-private "只表示状态可见性与归属，不表示
# 可以省略持久化、CAS、签名 envelope 或重放校验". It is still a signed Event, so the
# service still cannot produce the signature.
#
# Scoping this check to `event_log` alone hid `ak.self.account_data.resource.delete`,
# whose sibling `resource.replace` writes the same `ak.account_data.set` kind — the same
# "adding is an Event, removing is not" asymmetry the circle and realm_link DELETEs have.
EVENT_AUTHORING_DURABLE_EFFECT_KINDS = ("event_log", "actor_private_event")

# The operations still in that state, each with what it would take to close it.
# This list may only shrink: an entry that starts carrying a signed Event fails as
# stale, and a new event_log operation cannot be added without one.
#
# Downgrading an operation's durable_effect out of event_log is NOT a way off this
# list. "The handler writes no Event" is true of every entry — accept_local_operations
# persists nothing unless persist_before_projection is set — so it proves nothing on
# its own. A downgrade additionally MUST show the state change reaches no replicated
# cell/lattice, i.e. it never enters state_root and no peer has to converge on it.
# See arkret-work/work/active/2026-08-06-event-log-operations-need-a-signed-request.md.
EVENT_LOG_OPERATIONS_WITHOUT_A_SIGNED_REQUEST: dict[str, str] = {
    # The one actor_private_event entry left. Its cell subject is
    # composite[envelope.actor_id, ...], so the subject *is* the actor and only the
    # holder can sign it. The account_data pair closed the same way; what that closure
    # had to fix in soland is recorded in
    # arkret-work/work/active/2026-08-06-event-log-operations-need-a-signed-request.md.
    "ak.self.read_cursor.command.advance": (
        "actor-private subject includes envelope.actor_id; needs the caller-signed "
        "ak.read_cursor.advance"
    ),
    "ak.self.circle.member.resource.delete": (
        "DELETE with no request body today; the shape decision is made (give it a body, as "
        "ak.self.keys.backups.resource.delete already does) but not yet landed"
    ),
    "ak.self.realm.moderation_policy.resource.replace": "payload-only request",
    "ak.self.account.command.update_profile": "needs the caller-signed profile Event",
    "ak.self.moderation.command.report": "needs the caller-signed report Event",
    "ak.self.applet.command.revoke": (
        "install already requires caller-signed `registration_event` + `capability_grant_events`; "
        "revoke takes none"
    ),
    "ak.self.agent.grant.resource.delete": (
        "DELETE with no request body today; soland already hard-refuses it outside development "
        "mode with agent_grant_fanout_unavailable, so the missing Event is admitted there too"
    ),
}


def _request_schema_reaches_signed_event(
    lint: Lint, ref: str, depth: int = 0, seen: set[str] | None = None
) -> bool:
    """Does a request schema reference reach a caller-signed Event?"""
    seen = set() if seen is None else seen
    if depth > 6 or not ref or ref in seen:
        return False
    seen.add(ref)
    file_part, _, fragment = ref.partition("#")
    relative = file_part.lstrip("./")
    if relative and not relative.startswith("schemas/"):
        relative = f"schemas/{relative}"
    if not relative:
        return False
    path = ARTIFACTS / relative
    if not path.is_file():
        return False
    document = load_json(lint, path)
    if document is None:
        return False
    node: Any = document
    if fragment:
        try:
            # `resolve_json_pointer` wants the `#/` form; `partition` dropped the `#`.
            node = resolve_json_pointer(document, f"#{fragment}")
        except (KeyError, IndexError, TypeError, ValueError):
            return False

    def walk(value: Any) -> bool:
        if isinstance(value, dict):
            nested = value.get("$ref")
            if isinstance(nested, str):
                if any(marker in nested for marker in SIGNED_EVENT_REQUEST_MARKERS):
                    return True
                next_ref = nested if ".schema.json" in nested else f"{relative}{nested}"
                if _request_schema_reaches_signed_event(lint, next_ref, depth + 1, seen):
                    return True
            return any(walk(child) for child in value.values())
        if isinstance(value, list):
            return any(walk(child) for child in value)
        return False

    return walk(node)


def check_event_log_operations_carry_a_signed_event(lint: Lint) -> None:
    """An operation that writes an Event MUST take that Event from its caller."""
    path = ARTIFACTS / "registry" / "operation-registry.json"
    registry = load_json(lint, path)
    if not isinstance(registry, dict):
        return
    operations = registry.get("operations")
    if not isinstance(operations, list):
        return

    unsigned: set[str] = set()
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        effect = operation.get("durable_effect")
        if (
            not isinstance(effect, dict)
            or effect.get("kind") not in EVENT_AUTHORING_DURABLE_EFFECT_KINDS
        ):
            continue
        operation_id = operation.get("operation_id")
        if not isinstance(operation_id, str):
            continue
        request_ref = operation.get("request_schema_ref")
        if isinstance(request_ref, str) and _request_schema_reaches_signed_event(lint, request_ref):
            continue
        unsigned.add(operation_id)
        if operation_id not in EVENT_LOG_OPERATIONS_WITHOUT_A_SIGNED_REQUEST:
            lint.fail(
                path,
                f"{operation_id} declares a durable event_log effect but its request carries no "
                "caller-signed Event, and a service MUST NOT sign one on the caller's behalf "
                "(capabilities.md sections 118/361, key-management.md section 411). Reference "
                "service-operation-dtos.schema.json#/$defs/EventInitialSubmission (or the Event "
                "envelope) from the request body, as the agent lifecycle operations and "
                "applet.command.install already do.",
            )
    for stale in sorted(set(EVENT_LOG_OPERATIONS_WITHOUT_A_SIGNED_REQUEST) - unsigned):
        lint.fail(
            path,
            f"{stale} now carries a caller-signed Event; drop it from "
            "EVENT_LOG_OPERATIONS_WITHOUT_A_SIGNED_REQUEST",
        )


def check_operation_clause_registry(lint: Lint) -> None:
    clause_path = ARTIFACTS / "registry" / "operation-clause-registry.json"
    operation_path = ARTIFACTS / "registry" / "operation-registry.json"
    clause_data = load_json(lint, clause_path)
    operation_data = load_json(lint, operation_path)
    if not isinstance(clause_data, dict) or not isinstance(operation_data, dict):
        return
    clauses = clause_data.get("clauses")
    operations = operation_data.get("operations")
    if not isinstance(clauses, list) or not clauses:
        lint.fail(clause_path, "operation clause registry must contain clauses")
        return
    if not isinstance(operations, list):
        return

    allowed_selectors = {
        "all_operations",
        "openapi_protected_operations",
        "write_operations",
        "http_operations",
        "stream_operations",
        "partial_outcome_operations",
        "privacy_sensitive_operations",
    }
    selectors_by_clause: dict[str, str] = {}
    seen: set[str] = set()
    for index, clause in enumerate(clauses):
        label = f"clauses[{index}]"
        if not isinstance(clause, dict):
            lint.fail(clause_path, f"{label} must be an object")
            continue
        clause_id = clause.get("clause_id")
        if not isinstance(clause_id, str) or not re.fullmatch(r"AK-OP-[0-9]{3}", clause_id):
            lint.fail(clause_path, f"{label}.clause_id must be AK-OP-NNN")
            continue
        if clause_id in seen:
            lint.fail(clause_path, f"duplicate operation clause {clause_id}")
        seen.add(clause_id)
        selector = clause.get("selector")
        selector_kind = selector.get("kind") if isinstance(selector, dict) else None
        if selector_kind not in allowed_selectors:
            lint.fail(clause_path, f"{clause_id} has unknown selector kind {selector_kind!r}")
            continue
        selectors_by_clause[clause_id] = selector_kind
        evidence = clause.get("required_evidence")
        if not isinstance(evidence, list) or not evidence or any(not isinstance(item, str) or not item for item in evidence):
            lint.fail(clause_path, f"{clause_id}.required_evidence must be a non-empty string list")
        refs = clause.get("source_refs")
        if not isinstance(refs, list) or not refs:
            lint.fail(clause_path, f"{clause_id}.source_refs must be non-empty")
        else:
            for ref in refs:
                if not isinstance(ref, str) or not ref.startswith("spec/v1/"):
                    lint.fail(clause_path, f"{clause_id} has invalid source ref {ref!r}")
                    continue
                relative = ref.split("#", 1)[0].removeprefix("spec/v1/")
                if not (SPEC_ROOT / relative).is_file():
                    lint.fail(clause_path, f"{clause_id} source ref does not exist: {ref}")

    required_clause_ids = {f"AK-OP-{index:03d}" for index in range(1, 9)}
    if seen != required_clause_ids:
        lint.fail(clause_path, "operation clause registry must define exactly AK-OP-001 through AK-OP-008")

    for row in operations:
        if not isinstance(row, dict):
            continue
        operation_id = row.get("operation_id")
        if not isinstance(operation_id, str):
            continue
        segments = operation_id.split(".")
        op_kind = segments[-2] if len(segments) >= 2 else ""
        op_action = segments[-1] if segments else ""
        is_write = op_kind in {"command", "upload", "exchange"} or (
            op_kind == "resource" and op_action in {"replace", "delete"}
        )
        required = {"AK-OP-001", "AK-OP-004", "AK-OP-005"}
        if is_write:
            required.add("AK-OP-003")
        if op_kind == "stream":
            required.add("AK-OP-006")
        missing = required - seen
        if missing:
            lint.fail(clause_path, f"{operation_id} lacks required clause coverage {sorted(missing)}")


def check_vector_group_requirements(lint: Lint, known: dict[str, set[str]]) -> None:
    # Conformance-vector groups are fixture/runner groupings, NOT ak.profile.*
    # capability-negotiation profiles. They live in their own ak.vector_group.*
    # namespace with a dedicated requirements matrix, kept out of profile_roles /
    # profile_requirements so the capability namespace stays pure.
    path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    groups = data.get("vector_groups")
    requirements = data.get("vector_group_requirements")
    if not isinstance(groups, list):
        lint.fail(path, "missing vector_groups list")
        return
    if not isinstance(requirements, dict):
        lint.fail(path, "missing vector_group_requirements matrix")
        return

    group_ids: set[str] = set()
    for gid in groups:
        if not isinstance(gid, str) or not VECTOR_GROUP_ID_RE.fullmatch(gid):
            lint.fail(path, f"vector_groups entry has invalid vector-group id: {gid}")
        else:
            group_ids.add(gid)

    for gid in sorted(group_ids - set(requirements.keys())):
        lint.fail(path, f"vector_group_requirements missing declared vector group: {gid}")

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

    for gid, requirement in requirements.items():
        if gid not in group_ids:
            lint.fail(path, f"vector_group_requirements key is not a declared vector group: {gid}")
        if not isinstance(requirement, dict):
            lint.fail(path, f"{gid} requirement must be an object")
            continue
        for missing_key in sorted(required_keys - set(requirement.keys())):
            lint.fail(path, f"{gid} missing {missing_key}")

        for operation_id in requirement.get("required_endpoints", []):
            if operation_id not in known["operation_ids"]:
                lint.fail(path, f"{gid} requires unknown operation_id: {operation_id}")

        for event_kind in requirement.get("required_event_kinds", []):
            if isinstance(event_kind, str) and event_kind.startswith("wire_scope:"):
                continue
            if event_kind not in known["event_kinds"]:
                lint.fail(path, f"{gid} requires unknown Event.kind: {event_kind}")

        for event_kind in requirement.get("rejected_event_kinds", []):
            if isinstance(event_kind, str) and event_kind.startswith("wire_scope:"):
                continue
            if event_kind not in known["event_kinds"]:
                lint.fail(path, f"{gid} rejects unknown Event.kind: {event_kind}")

        for schema_id in requirement.get("required_schemas", []):
            if schema_id not in known["schema_ids"]:
                lint.fail(path, f"{gid} requires unknown schema: {schema_id}")

        for fixture in requirement.get("required_fixtures", []):
            if fixture not in fixture_files:
                lint.fail(path, f"{gid} requires missing fixture: {fixture}")

        feature_discovery = requirement.get("feature_discovery")
        if not isinstance(feature_discovery, dict):
            lint.fail(path, f"{gid} feature_discovery must be an object")
        else:
            if not isinstance(feature_discovery.get("required"), list):
                lint.fail(path, f"{gid} feature_discovery.required must be a list")
            if not isinstance(feature_discovery.get("unsupported_optional"), str):
                lint.fail(path, f"{gid} feature_discovery.unsupported_optional must be a string")


def check_event_ref_invariants_in_value(lint: Lint, path: Path, json_path: str, value: Any) -> None:
    if isinstance(value, dict):
        event_id = value.get("event_id")
        if isinstance(event_id, str):
            for ref_key in ("prev_refs", "auth_refs"):
                refs = value.get(ref_key)
                if isinstance(refs, list) and event_id in refs:
                    lint.fail(path, f"{json_path}.{ref_key} contains its own event_id {event_id}")
        if value.get("role") == "authorized_by" and "id" in value:
            authorized_by_id = value.get("id")
            if not isinstance(authorized_by_id, str) or not authorized_by_id.startswith("ak:grant:"):
                lint.fail(
                    path,
                    f"{json_path}.id must be an ak:grant: id for role=authorized_by",
                )
        for key, child in value.items():
            check_event_ref_invariants_in_value(lint, path, f"{json_path}.{key}", child)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            check_event_ref_invariants_in_value(lint, path, f"{json_path}[{index}]", child)


def payload_schema_contains_ref(value: Any) -> bool:
    if isinstance(value, dict):
        if "$ref" in value:
            return True
        return any(payload_schema_contains_ref(child) for child in value.values())
    if isinstance(value, list):
        return any(payload_schema_contains_ref(child) for child in value)
    return False


def collect_kind_selector_tokens(value: Any) -> set[str]:
    if not isinstance(value, dict):
        return set()
    tokens: set[str] = set()
    const_value = value.get("const")
    if isinstance(const_value, str):
        tokens.add(const_value)
    enum_values = value.get("enum")
    if isinstance(enum_values, list):
        tokens.update(item for item in enum_values if isinstance(item, str))
    return tokens


def collect_payload_dispatch_kinds(value: Any) -> set[str]:
    dispatched: set[str] = set()
    if isinstance(value, dict):
        if_schema = value.get("if")
        then_schema = value.get("then")
        if isinstance(if_schema, dict) and isinstance(then_schema, dict):
            then_properties = then_schema.get("properties")
            payload_schema = (
                then_properties.get("payload")
                if isinstance(then_properties, dict)
                else None
            )
            if payload_schema_contains_ref(payload_schema):
                if_properties = if_schema.get("properties")
                kind_schema = (
                    if_properties.get("kind")
                    if isinstance(if_properties, dict)
                    else None
                )
                dispatched.update(collect_kind_selector_tokens(kind_schema))
        for child in value.values():
            dispatched.update(collect_payload_dispatch_kinds(child))
    elif isinstance(value, list):
        for child in value:
            dispatched.update(collect_payload_dispatch_kinds(child))
    return dispatched


# Matches dispatch refs of the form `[./]?<filename>.schema.json#/$defs/<class>`.
# Covers `event-payload.schema.json#/$defs/...` (canonical) and sibling-schema
# refs such as `moderation-appeal.schema.json#/$defs/submit_payload`.
# Refs without a $defs anchor (e.g. `./read-cursor.schema.json` whose entire
# file is the payload) have no class name to lint and are intentionally skipped.
PAYLOAD_DISPATCH_REF_RE = re.compile(
    r"[A-Za-z0-9_-]+\.schema\.json#/\$defs/([a-z][a-z0-9_]*)"
)


# Kind → payload-class pairs where the class name intentionally diverges from
# the kind's last dot-segment (one-to-one semantic renames).
KIND_PAYLOAD_RENAME_EXEMPTIONS: dict[str, str] = {
    "ak.member.state": "membership_payload",
    "ak.circle.update": "circle_patch_payload",
    "ak.space.update": "space_patch_payload",
    "ak.profile.space_override": "profile_realm_override_payload",
}


# Legitimate kind → payload-class pairs where multiple kinds intentionally
# share a "category" payload class (object_lifecycle, state, audit, view,
# invite, capability_grant, generic_standard, reaction, container_position,
# call, message_redact, space_state_transition, strand_patch,
# object_patch). Adding a new dispatch that doesn't match the last-segment
# rule MUST add the pair here, forcing reviewer awareness of the rename.
LEGACY_SHARED_PAYLOAD_DISPATCH: set[tuple[str, str]] = {
    ("ak.actor.discovery", "state_payload"),
    ("ak.applet.discovery", "state_payload"),
    ("ak.attestation.range_completeness", "audit_payload"),
    ("ak.audit.epoch_key_destruction", "audit_payload"),
    ("ak.audit.ryw_receipt", "audit_payload"),
    ("ak.call.recording.start", "call_payload"),
    ("ak.call.state", "call_payload"),
    ("ak.capability.derived", "capability_grant_payload"),
    ("ak.circle.archive", "object_lifecycle_payload"),
    ("ak.circle.restore", "object_lifecycle_payload"),
    ("ak.circle.tombstone", "object_lifecycle_payload"),
    ("ak.container.move_item", "container_position_payload"),
    ("ak.container.rebalance", "container_position_payload"),
    ("ak.did.proof", "state_payload"),
    ("ak.strand.archive", "object_lifecycle_payload"),
    ("ak.strand.restore", "object_lifecycle_payload"),
    ("ak.strand.tracks.update", "strand_patch_payload"),
    ("ak.strand.update", "strand_patch_payload"),
    ("ak.handle.discovery", "state_payload"),
    ("ak.identity.accountability_grant", "state_payload"),
    ("ak.identity.disclosure_policy", "state_payload"),
    ("ak.identity.disclosure_receipt", "state_payload"),
    ("ak.identity.presentation_request", "state_payload"),
    ("ak.identity.presentation_response", "state_payload"),
    ("ak.invite.accept", "invite_payload"),
    ("ak.invite.cancel", "invite_payload"),
    ("ak.invite.claim", "invite_payload"),
    ("ak.invite.create", "invite_payload"),
    ("ak.invite.revoke", "invite_payload"),
    ("ak.invite.third_party", "invite_payload"),
    ("ak.morph.archive", "object_lifecycle_payload"),
    ("ak.morph.restore", "object_lifecycle_payload"),
    ("ak.morph.update", "object_patch_payload"),
    ("ak.organization.discovery", "state_payload"),
    ("ak.organization.moderation_policy", "state_payload"),
    ("ak.policy.action", "state_payload"),
    ("ak.policy.set", "state_payload"),
    ("ak.profile.update", "object_patch_payload"),
    ("ak.reaction.add", "reaction_payload"),
    ("ak.reaction.remove", "reaction_payload"),
    ("ak.realm.asset_privacy_policy", "state_payload"),
    ("ak.realm.audit_policy_downgrade", "audit_payload"),
    ("ak.realm.delivery_binding_policy", "state_payload"),
    ("ak.realm.discovery", "state_payload"),
    ("ak.realm.join_rule", "state_payload"),
    ("ak.realm.media_service", "state_payload"),
    ("ak.realm.moderation_policy", "state_payload"),
    ("ak.realm.organization", "state_payload"),
    ("ak.realm.policy", "state_payload"),
    ("ak.realm.policy_bundle", "state_payload"),
    ("ak.realm.policy_server", "state_payload"),
    ("ak.realm.schema", "state_payload"),
    ("ak.realm.update", "object_patch_payload"),
    ("ak.redaction", "message_redact_payload"),
    ("ak.schema.define", "state_payload"),
    ("ak.schema.update", "state_payload"),
    ("ak.sovereign.did_policy", "state_payload"),
    ("ak.space.archive", "generic_standard_payload"),
    ("ak.space.archive", "space_state_transition_payload"),
    ("ak.space.create", "generic_standard_payload"),
    ("ak.space.parent", "generic_standard_payload"),
    ("ak.space.restore", "generic_standard_payload"),
    ("ak.space.restore", "space_state_transition_payload"),
    ("ak.space.tombstone", "generic_standard_payload"),
    ("ak.view.create", "view_payload"),
    ("ak.view.reconcile", "view_payload"),
    ("ak.view.update", "view_payload"),
}


def collect_payload_dispatch_refs(value: Any) -> list[tuple[str, str]]:
    """Return every `(Event kind, payload schema ref)` dispatch."""
    refs: list[tuple[str, str]] = []
    if isinstance(value, dict):
        if_schema = value.get("if")
        then_schema = value.get("then")
        if isinstance(if_schema, dict) and isinstance(then_schema, dict):
            then_properties = then_schema.get("properties")
            payload_schema = (
                then_properties.get("payload")
                if isinstance(then_properties, dict)
                else None
            )
            ref = payload_schema.get("$ref") if isinstance(payload_schema, dict) else None
            if isinstance(ref, str):
                if_properties = if_schema.get("properties")
                kind_schema = (
                    if_properties.get("kind")
                    if isinstance(if_properties, dict)
                    else None
                )
                for kind in collect_kind_selector_tokens(kind_schema):
                    if kind.startswith("ak."):
                        refs.append((kind, ref))
        for child in value.values():
            refs.extend(collect_payload_dispatch_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.extend(collect_payload_dispatch_refs(child))
    return refs


def collect_payload_dispatch_pairs(value: Any) -> list[tuple[str, str]]:
    """Return `(kind, payload class name)` views of the canonical dispatch scan."""
    pairs: list[tuple[str, str]] = []
    for kind, ref in collect_payload_dispatch_refs(value):
        match = PAYLOAD_DISPATCH_REF_RE.search(ref)
        if match:
            pairs.append((kind, match.group(1)))
    return pairs


def check_composite_subject_terminal_types(
    lint: Lint,
    event_schema_path: Path,
    event_schema: Any,
) -> None:
    """Reject cell-subject endpoints that are absent or not typed scalars.

    Single-field subjects and every composite/select endpoint must exist in the
    payload class selected for the Event kind. Coalesce descriptors may share
    one descriptor across payload classes, but at least one candidate must
    resolve. Every resolved ordinary endpoint must be scalar. A
    `string_set_digest` component is checked against its stricter closed
    string-or-array schema contract and is treated as a string only after
    transformation.
    """
    event_registry_path = ARTIFACTS / "registry" / "event-kind-registry.json"
    event_registry = load_json(lint, event_registry_path)
    if not isinstance(event_registry, dict):
        return

    schema_cache: dict[Path, Any] = {event_schema_path.resolve(): event_schema}

    def schema_document(path: Path) -> Any:
        resolved = path.resolve()
        if resolved not in schema_cache:
            schema_cache[resolved] = load_json(lint, resolved)
        return schema_cache[resolved]

    def dereference(
        schema_path: Path,
        document: Any,
        node: Any,
        seen: set[tuple[Path, str]] | None = None,
    ) -> tuple[Path, Any, Any]:
        seen = set() if seen is None else seen
        while isinstance(node, dict) and isinstance(node.get("$ref"), str):
            ref = node["$ref"]
            file_ref, separator, fragment = ref.partition("#")
            target_path = (
                (schema_path.parent / file_ref).resolve()
                if file_ref
                else schema_path.resolve()
            )
            key = (target_path, fragment)
            if key in seen:
                return schema_path, document, {}
            seen.add(key)
            target_document = schema_document(target_path)
            if target_document is None:
                return target_path, {}, {}
            try:
                target = resolve_json_pointer(
                    target_document,
                    f"#{fragment}" if separator else "#",
                )
            except KeyError:
                lint.fail(event_registry_path, f"cell subject schema ref not found: {ref}")
                return target_path, target_document, {}
            schema_path, document, node = target_path, target_document, target
        return schema_path, document, node

    def property_nodes(
        schema_path: Path,
        document: Any,
        node: Any,
        name: str,
        seen: set[int] | None = None,
    ) -> list[tuple[Path, Any, Any]]:
        schema_path, document, node = dereference(schema_path, document, node)
        if not isinstance(node, dict):
            return []
        seen = set() if seen is None else seen
        marker = id(node)
        if marker in seen:
            return []
        seen.add(marker)
        results: list[tuple[Path, Any, Any]] = []
        properties = node.get("properties")
        if isinstance(properties, dict) and name in properties:
            results.append((schema_path, document, properties[name]))
        for keyword in ("allOf", "oneOf", "anyOf"):
            branches = node.get(keyword)
            if isinstance(branches, list):
                for branch in branches:
                    results.extend(
                        property_nodes(schema_path, document, branch, name, seen.copy())
                    )
        return results

    def terminal_types(
        schema_path: Path,
        document: Any,
        node: Any,
        seen: set[int] | None = None,
    ) -> set[str]:
        schema_path, document, node = dereference(schema_path, document, node)
        if not isinstance(node, dict):
            return set()
        seen = set() if seen is None else seen
        marker = id(node)
        if marker in seen:
            return set()
        seen.add(marker)
        result: set[str] = set()
        declared = node.get("type")
        if isinstance(declared, str):
            result.add(declared)
        elif isinstance(declared, list):
            result.update(item for item in declared if isinstance(item, str))
        if "const" in node:
            value = node["const"]
            result.add(
                "null"
                if value is None
                else "boolean"
                if isinstance(value, bool)
                else "integer"
                if isinstance(value, int)
                else "number"
                if isinstance(value, float)
                else "string"
                if isinstance(value, str)
                else "array"
                if isinstance(value, list)
                else "object"
                if isinstance(value, dict)
                else "unknown"
            )
        enum = node.get("enum")
        if isinstance(enum, list):
            for value in enum:
                result.add(
                    "null"
                    if value is None
                    else "boolean"
                    if isinstance(value, bool)
                    else "integer"
                    if isinstance(value, int)
                    else "number"
                    if isinstance(value, float)
                    else "string"
                    if isinstance(value, str)
                    else "array"
                    if isinstance(value, list)
                    else "object"
                    if isinstance(value, dict)
                    else "unknown"
                )
        for keyword in ("allOf", "oneOf", "anyOf"):
            branches = node.get(keyword)
            if isinstance(branches, list):
                for branch in branches:
                    result.update(
                        terminal_types(schema_path, document, branch, seen.copy())
                    )
        return result

    def path_terminal_types(ref: str, payload_path: str) -> set[str] | None:
        file_ref, separator, fragment = ref.partition("#")
        schema_path = (
            (event_schema_path.parent / file_ref).resolve()
            if file_ref
            else event_schema_path.resolve()
        )
        document = schema_document(schema_path)
        if document is None:
            return None
        try:
            node = resolve_json_pointer(document, f"#{fragment}" if separator else "#")
        except KeyError:
            return None
        candidates = [(schema_path, document, node)]
        for segment in payload_path.removeprefix("payload.").split("."):
            next_candidates: list[tuple[Path, Any, Any]] = []
            for candidate_path, candidate_document, candidate in candidates:
                next_candidates.extend(
                    property_nodes(
                        candidate_path,
                        candidate_document,
                        candidate,
                        segment,
                    )
                )
            candidates = next_candidates
            if not candidates:
                return None
        result: set[str] = set()
        for candidate_path, candidate_document, candidate in candidates:
            result.update(
                terminal_types(candidate_path, candidate_document, candidate)
            )
        return result

    def path_terminal_nodes(
        ref: str, payload_path: str
    ) -> list[tuple[Path, Any, Any]] | None:
        file_ref, separator, fragment = ref.partition("#")
        schema_path = (
            (event_schema_path.parent / file_ref).resolve()
            if file_ref
            else event_schema_path.resolve()
        )
        document = schema_document(schema_path)
        if document is None:
            return None
        try:
            node = resolve_json_pointer(document, f"#{fragment}" if separator else "#")
        except KeyError:
            return None
        candidates = [(schema_path, document, node)]
        for segment in payload_path.removeprefix("payload.").split("."):
            next_candidates: list[tuple[Path, Any, Any]] = []
            for candidate_path, candidate_document, candidate in candidates:
                next_candidates.extend(
                    property_nodes(
                        candidate_path,
                        candidate_document,
                        candidate,
                        segment,
                    )
                )
            candidates = next_candidates
            if not candidates:
                return None
        return candidates

    def schema_variants(
        schema_path: Path,
        document: Any,
        node: Any,
        seen: set[int] | None = None,
    ) -> list[tuple[Path, Any, Any]]:
        schema_path, document, node = dereference(schema_path, document, node)
        if not isinstance(node, dict):
            return []
        seen = set() if seen is None else seen
        marker = id(node)
        if marker in seen:
            return []
        seen.add(marker)
        for keyword in ("oneOf", "anyOf"):
            branches = node.get(keyword)
            if isinstance(branches, list):
                result: list[tuple[Path, Any, Any]] = []
                for branch in branches:
                    result.extend(
                        schema_variants(
                            schema_path, document, branch, seen.copy()
                        )
                    )
                return result
        return [(schema_path, document, node)]

    def validate_string_set_schema(
        kind: str,
        source: str,
        component_ref: str,
    ) -> None:
        candidates: list[tuple[Path, Any, Any]] = []
        for ref in dispatch_refs.get(kind, []):
            nodes = path_terminal_nodes(ref, source)
            if nodes is not None:
                candidates.extend(nodes)
        variants: list[tuple[Path, Any, Any]] = []
        for candidate_path, candidate_document, candidate in candidates:
            variants.extend(
                schema_variants(candidate_path, candidate_document, candidate)
            )
        typed = [
            (
                terminal_types(variant_path, variant_document, variant),
                variant_path,
                variant_document,
                variant,
            )
            for variant_path, variant_document, variant in variants
        ]
        if not typed:
            lint.fail(
                event_registry_path,
                f"{component_ref} field {source!r} has no schema endpoint",
            )
            return
        if {next(iter(types)) for types, *_ in typed if len(types) == 1} != {
            "string",
            "array",
        } or any(len(types) != 1 for types, *_ in typed):
            lint.fail(
                event_registry_path,
                f"{component_ref} field {source!r} must be a closed string | array<string> union",
            )
            return
        string_shapes: list[Any] = []
        array_items: list[Any] = []
        for types, variant_path, variant_document, variant in typed:
            resolved_path, resolved_document, resolved = dereference(
                variant_path, variant_document, variant
            )
            if types == {"string"}:
                string_shapes.append(resolved)
                continue
            if not isinstance(resolved, dict):
                lint.fail(event_registry_path, f"{component_ref} array schema is malformed")
                continue
            if not isinstance(resolved.get("minItems"), int) or resolved["minItems"] < 1:
                lint.fail(
                    event_registry_path,
                    f"{component_ref} array schema must declare minItems >= 1",
                )
            if resolved.get("uniqueItems") is not True:
                lint.fail(
                    event_registry_path,
                    f"{component_ref} array schema must declare uniqueItems: true",
                )
            item = resolved.get("items")
            item_path, item_document, item = dereference(
                resolved_path, resolved_document, item
            )
            if terminal_types(item_path, item_document, item) != {"string"}:
                lint.fail(
                    event_registry_path,
                    f"{component_ref} array items must resolve only to string",
                )
            array_items.append(item)
        if len(string_shapes) != 1 or len(array_items) != 1:
            lint.fail(
                event_registry_path,
                f"{component_ref} must have exactly one string and one array variant",
            )
        elif canonical_json(string_shapes[0]) != canonical_json(array_items[0]):
            lint.fail(
                event_registry_path,
                f"{component_ref} string and array item variants must share one element schema",
            )

    dispatch_refs: dict[str, list[str]] = {}
    for kind, ref in collect_payload_dispatch_refs(event_schema):
        dispatch_refs.setdefault(kind, []).append(ref)

    def resolved_terminal_types(kind: str, source: str) -> tuple[bool, set[str]]:
        resolved_types: set[str] = set()
        resolved = False
        for ref in dispatch_refs.get(kind, []):
            types = path_terminal_types(ref, source)
            if types is not None:
                resolved = True
                resolved_types.update(types)
        return resolved, resolved_types

    def terminal_enum_values(
        schema_path: Path,
        document: Any,
        node: Any,
        seen: set[int] | None = None,
    ) -> set[Any]:
        schema_path, document, node = dereference(schema_path, document, node)
        if not isinstance(node, dict):
            return set()
        seen = set() if seen is None else seen
        marker = id(node)
        if marker in seen:
            return set()
        seen.add(marker)
        result: set[Any] = set()
        if "const" in node and isinstance(node["const"], (str, int, bool)):
            result.add(node["const"])
        enum = node.get("enum")
        if isinstance(enum, list):
            result.update(
                value for value in enum if isinstance(value, (str, int, bool))
            )
        for keyword in ("allOf", "oneOf", "anyOf"):
            branches = node.get(keyword)
            if isinstance(branches, list):
                for branch in branches:
                    result.update(
                        terminal_enum_values(
                            schema_path, document, branch, seen.copy()
                        )
                    )
        return result

    def reachable_selector_values(kind: str, selector: str) -> set[Any]:
        values: set[Any] = set()
        for ref in dispatch_refs.get(kind, []):
            nodes = path_terminal_nodes(ref, selector)
            for node_path, node_document, node in nodes or []:
                values.update(
                    terminal_enum_values(node_path, node_document, node)
                )
        return values

    def output_paths(kind: str, component: Any) -> list[str]:
        if isinstance(component, str):
            return [component]
        if not isinstance(component, dict):
            return []
        if isinstance(component.get("field"), str):
            return [component["field"]]
        branches = component.get("branches")
        if not isinstance(branches, dict):
            return []
        selector = component.get("selector")
        reachable = (
            reachable_selector_values(kind, selector)
            if isinstance(selector, str)
            else set()
        )
        return [
            branch["field"]
            for branch_name, branch in branches.items()
            if isinstance(branch, dict) and isinstance(branch.get("field"), str)
            and (not reachable or branch_name in reachable)
        ]

    allowed = {"string", "integer", "boolean", "null"}

    def validate_scalar_endpoint(
        kind: str,
        write_index: int,
        source: str,
        endpoint_ref: str,
        *,
        require_endpoint: bool = True,
    ) -> bool:
        if source == "envelope.actor_id":
            return True
        if not source.startswith("payload."):
            return False
        resolved, resolved_types = resolved_terminal_types(kind, source)
        if not resolved:
            if require_endpoint:
                lint.fail(
                    event_registry_path,
                    f"{endpoint_ref} endpoint {source!r} has no schema endpoint",
                )
            return False
        has_scalar_variant = bool(resolved_types & allowed)
        non_scalar_variants = resolved_types - allowed
        if not has_scalar_variant:
            lint.fail(
                event_registry_path,
                f"{endpoint_ref} endpoint {source!r} must be a schema-declared "
                f"JSON string/integer/boolean/null scalar, got "
                f"{sorted(resolved_types) or ['untyped']}",
            )
        elif non_scalar_variants:
            lint.fail(
                event_registry_path,
                f"{endpoint_ref} endpoint {source!r} has forbidden "
                f"non-scalar schema variants {sorted(non_scalar_variants)}",
            )
        return True

    rows = event_registry.get("event_kinds")
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not isinstance(row.get("event_kind"), str):
            continue
        kind = row["event_kind"]
        writes = row.get("cell_writes")
        for write_index, write in enumerate(writes if isinstance(writes, list) else []):
            subject = write.get("cell_subject") if isinstance(write, dict) else None
            if not isinstance(subject, dict):
                continue
            subject_kind = subject.get("kind")
            subject_ref = f"{kind} cell_writes[{write_index}].cell_subject"
            if subject_kind == "coalesce":
                fields = subject.get("fields")
                resolved_any = False
                for source in fields if isinstance(fields, list) else []:
                    if isinstance(source, str):
                        resolved_any = (
                            validate_scalar_endpoint(
                                kind,
                                write_index,
                                source,
                                subject_ref,
                                require_endpoint=False,
                            )
                            or resolved_any
                        )
                if not resolved_any:
                    lint.fail(
                        event_registry_path,
                        f"{subject_ref} coalesce fields have no schema endpoint",
                    )
                continue
            if subject_kind not in {"composite", "tuple"}:
                source = subject.get("field")
                if isinstance(source, str):
                    validate_scalar_endpoint(
                        kind, write_index, source, subject_ref
                    )
                continue
            components = subject.get("components")
            for component_index, component in enumerate(
                components if isinstance(components, list) else []
            ):
                component_ref = (
                    f"{kind} cell_writes[{write_index}].cell_subject.components"
                    f"[{component_index}]"
                )
                if (
                    isinstance(component, dict)
                    and component.get("kind") == "string_set_digest"
                ):
                    source = component.get("field")
                    if isinstance(source, str) and source.startswith("payload."):
                        validate_string_set_schema(kind, source, component_ref)
                    continue
                selector = (
                    component.get("selector")
                    if isinstance(component, dict)
                    else None
                )
                if isinstance(selector, str) and selector.startswith("payload."):
                    selector_resolved, selector_types = resolved_terminal_types(
                        kind, selector
                    )
                    if not selector_resolved:
                        lint.fail(
                            event_registry_path,
                            f"{component_ref} selector {selector!r} has no schema endpoint",
                        )
                    elif selector_types != {"string"}:
                        lint.fail(
                            event_registry_path,
                            f"{kind} cell_writes[{write_index}].cell_subject.components"
                            f"[{component_index}] selector {selector!r} must be a "
                            f"schema-declared JSON string, got "
                            f"{sorted(selector_types) or ['untyped']}",
                        )
                for source in output_paths(kind, component):
                    validate_scalar_endpoint(
                        kind, write_index, source, component_ref
                    )


def check_event_schema_coverage(lint: Lint, known: dict[str, set[str]]) -> None:
    path = ARTIFACTS / "schemas" / "event-envelope.schema.json"
    data = load_json(lint, path)
    if data is None:
        return

    event_schema_tokens: set[str] = set()

    def collect_admitted_kind_tokens(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                collect_admitted_kind_tokens(item)
            return
        if not isinstance(node, dict):
            return
        properties = node.get("properties")
        if isinstance(properties, dict):
            kind_schema = properties.get("kind")
            if isinstance(kind_schema, dict):
                value = kind_schema.get("const")
                if isinstance(value, str):
                    event_schema_tokens.add(value)
                values = kind_schema.get("enum")
                if isinstance(values, list):
                    event_schema_tokens.update(
                        item for item in values if isinstance(item, str)
                    )
        for key, value in node.items():
            # A negative rejection list proves that tokens are not Event kinds; it
            # is not admission coverage and must not be compared with the registry.
            if key != "not":
                collect_admitted_kind_tokens(value)

    collect_admitted_kind_tokens(data)

    event_schema_kinds = {
        token
        for token in event_schema_tokens
        if token.startswith("ak.") and not SCHEMA_ID_RE.fullmatch(token) and not PROFILE_ID_RE.fullmatch(token)
    }
    for token in sorted(event_schema_kinds - known["event_kinds"]):
        lint.fail(path, f"event-schema enum references unregistered Event.kind: {token}")
    for token in sorted(known["active_durable_event_kinds"] - event_schema_kinds):
        lint.fail(path, f"active Event.kind missing from event-schema enum coverage: {token}")

    active_event_wire_scopes = known.get("active_event_wire_scopes", {})
    active_envelope_event_kinds = {
        kind
        for kind, wire_scope in active_event_wire_scopes.items()
        if wire_scope in {"durable_event", "actor_private_event"}
    }
    payload_dispatch_kinds = {
        token
        for token in collect_payload_dispatch_kinds(data)
        if token.startswith("ak.") and not SCHEMA_ID_RE.fullmatch(token) and not PROFILE_ID_RE.fullmatch(token)
    }
    for token in sorted(active_envelope_event_kinds - payload_dispatch_kinds):
        lint.fail(path, f"active Event.kind missing payload schema dispatch: {token}")

    # An explicit registry payload_schema_ref is the canonical payload carrier.
    # The Event Envelope kind dispatch MUST select that exact schema location;
    # otherwise registry-driven SDKs and envelope-driven validators can accept
    # different payload languages for the same Event kind.
    event_registry_path = ARTIFACTS / "registry" / "event-kind-registry.json"
    event_registry = load_json(lint, event_registry_path)
    dispatch_refs: dict[str, set[str]] = {}
    for kind, ref in collect_payload_dispatch_refs(data):
        dispatch_refs.setdefault(kind, set()).add(ref)

    def normalize_payload_ref(ref: str, base: Path) -> str | None:
        file_ref, separator, fragment = ref.partition("#")
        target = (base / file_ref).resolve()
        try:
            relative = target.relative_to(ARTIFACTS.resolve()).as_posix()
        except ValueError:
            return None
        return relative + (f"#{fragment}" if separator else "")

    if isinstance(event_registry, dict):
        for row in event_registry.get("event_kinds", []):
            if not isinstance(row, dict):
                continue
            kind = row.get("event_kind")
            registered_ref = row.get("payload_schema_ref")
            if not isinstance(kind, str) or not isinstance(registered_ref, str):
                continue
            normalized_registered = normalize_payload_ref(registered_ref, ARTIFACTS)
            normalized_dispatches = {
                normalized
                for ref in dispatch_refs.get(kind, set())
                if (normalized := normalize_payload_ref(ref, path.parent)) is not None
            }
            if normalized_registered is None or normalized_registered not in normalized_dispatches:
                lint.fail(
                    path,
                    f"kind {kind} registry payload_schema_ref {registered_ref!r} is not selected "
                    f"by Event Envelope payload dispatch {sorted(normalized_dispatches)}",
                )

    check_composite_subject_terminal_types(lint, path, data)

    # Mis-routed dispatch detector: each (kind, payload_class) pair must either
    # appear in KIND_PAYLOAD_RENAME_EXEMPTIONS verbatim, or embed the kind's
    # last dot-segment as a case-insensitive substring of the class name.
    # Catches typo / copy-paste errors like `ak.self.agent.command.pause → agent_resume_payload`.
    seen_pairs: set[tuple[str, str]] = set()
    for kind, class_name in collect_payload_dispatch_pairs(data):
        if (kind, class_name) in seen_pairs:
            continue
        seen_pairs.add((kind, class_name))
        if SCHEMA_ID_RE.fullmatch(kind) or PROFILE_ID_RE.fullmatch(kind):
            continue
        exempt = KIND_PAYLOAD_RENAME_EXEMPTIONS.get(kind)
        if exempt is not None:
            if exempt != class_name:
                lint.fail(
                    path,
                    f"kind {kind} is exempt and MUST dispatch to {exempt!r}, "
                    f"but dispatches to {class_name!r}",
                )
            continue
        if (kind, class_name) in LEGACY_SHARED_PAYLOAD_DISPATCH:
            continue
        last_segment = kind.rsplit(".", 1)[-1].lower()
        if last_segment not in class_name.lower():
            lint.fail(
                path,
                f"kind {kind} dispatches to payload class {class_name!r} "
                f"whose name does not contain the kind's last segment "
                f"{last_segment!r}; likely a mis-routed $ref. If this rename "
                f"is intentional, add the (kind, class) pair to "
                f"LEGACY_SHARED_PAYLOAD_DISPATCH or KIND_PAYLOAD_RENAME_EXEMPTIONS "
                f"in tools/lint_artifacts.py.",
            )


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

        path_match = re.match(r"^  (/.*):\s*$", line)
        if path_match:
            current_path = path_match.group(1)
            current_method = None
            continue

        method_match = re.match(r"^    (get|post|put|patch|delete|head|options|trace|query):\s*$", line)
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
    in_paths = False
    current_path: str | None = None
    current_method: str | None = None
    current_operation_id: str | None = None
    has_request_body = False

    def finish_operation(line_no: int) -> None:
        if current_method in {"post", "put", "patch", "query"} and not has_request_body:
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

        path_match = re.match(r"^  (/.*):\s*$", line)
        if path_match:
            finish_operation(line_no)
            current_path = path_match.group(1)
            current_method = None
            current_operation_id = None
            has_request_body = False
            continue

        method_match = re.match(r"^    (get|post|put|patch|delete|head|options|trace|query):\s*$", line)
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


def check_openapi_schema_component_order(lint: Lint) -> None:
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return

    schemas = openapi.get("components", {}).get("schemas", {})
    if not isinstance(schemas, dict):
        lint.fail(openapi_path, "components.schemas missing")
        return

    names = list(schemas)
    expected = sorted(names, key=str.casefold)
    if names == expected:
        return

    index, actual, wanted = next(
        (index, actual, expected[index])
        for index, actual in enumerate(names)
        if actual != expected[index]
    )
    lint.fail(
        openapi_path,
        "components.schemas must be sorted alphabetically; "
        f"position {index + 1} has {actual}, expected {wanted}",
    )


def check_operation_surfaces(lint: Lint, known: dict[str, set[str]]) -> None:
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
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

    openapi = load_yaml(lint, openapi_path)
    operation_registry = load_json(lint, ARTIFACTS / "registry" / "operation-registry.json")
    if isinstance(openapi, dict) and isinstance(operation_registry, dict):
        if openapi.get("openapi") != "3.2.0":
            lint.fail(openapi_path, "Arkret OpenAPI must use 3.2.0 so RFC 10008 QUERY is represented by the standard query field")
        paths = openapi.get("paths")
        if isinstance(paths, dict):
            for row in operation_registry.get("operations", []):
                if not isinstance(row, dict):
                    continue
                operation_id = row.get("operation_id")
                compatibility_bindings = row.get("http_compatibility_bindings")
                if not isinstance(operation_id, str) or not isinstance(compatibility_bindings, list):
                    continue
                for binding in compatibility_bindings:
                    if not isinstance(binding, dict) or not isinstance(binding.get("http"), str):
                        continue
                    method, _, path_name = binding["http"].partition(" ")
                    path_item = paths.get(path_name)
                    operation = path_item.get(method.lower()) if isinstance(path_item, dict) else None
                    if not isinstance(operation, dict):
                        lint.fail(openapi_path, f"compatibility binding missing from OpenAPI: {binding['http']}")
                        continue
                    if operation.get("operationId") is not None:
                        lint.fail(openapi_path, f"compatibility binding must not declare operationId: {binding['http']}")
                    if operation.get("deprecated") is not True:
                        lint.fail(openapi_path, f"compatibility binding must declare deprecated=true: {binding['http']}")
                    if operation.get("x-arkret-compatibility-binding-of") != operation_id:
                        lint.fail(openapi_path, f"compatibility binding must point to {operation_id}: {binding['http']}")

    binding_path = ARTIFACTS / "bindings" / "non-http-bindings.yaml"
    binding = load_yaml(lint, binding_path)
    if not isinstance(binding, dict):
        return
    if binding.get("coverage") != "complete_except_http_only":
        lint.fail(binding_path, "non-HTTP binding coverage must be complete_except_http_only")
    binding_text = binding_path.read_text(encoding="utf-8")
    binding_operation_ids = set(EVENT_KIND_TOKEN_RE.findall(binding_text))
    http_only_operation_ids = known.get("http_only_operation_ids", set())
    for operation_id in sorted(binding_operation_ids - known["operation_ids"]):
        lint.fail(binding_path, f"non-HTTP binding references unregistered operation_id: {operation_id}")
    for operation_id in sorted(binding_operation_ids & http_only_operation_ids):
        lint.fail(binding_path, f"http-only operation_id must not appear in non-HTTP bindings: {operation_id}")
    for operation_id in sorted(known["operation_ids"] - binding_operation_ids - http_only_operation_ids):
        lint.fail(binding_path, f"registered operation_id missing from non-HTTP bindings: {operation_id}")


def check_service_describe_alignment(lint: Lint) -> None:
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
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
    for required_field in ("service_id", "trust_domain"):
        if required_field not in schema_required:
            lint.fail(schema_path, f"ServiceDescribe.required must include {required_field}")
        if required_field not in openapi_required:
            lint.fail(openapi_path, f"components.schemas.ServiceDescribe.required must include {required_field}")
    if "trust_domain" not in (service_schema.get("properties") or {}):
        lint.fail(schema_path, "ServiceDescribe.properties.trust_domain missing")
    if "trust_domain" not in (component.get("properties") or {}):
        lint.fail(openapi_path, "components.schemas.ServiceDescribe.properties.trust_domain missing")
    directory_fields = {
        "resource_kinds",
        "discovery_profiles",
        "restricted_query_proof",
        "ingest_modes",
        "accept_policy_kind",
        "accept_policy_ref",
        "default_ttl_seconds",
        "max_ttl_seconds",
        "revalidation_grace_seconds",
        "accepted_resource_kinds",
        "accepted_did_methods",
        "takedown_contact",
        "rate_limits",
    }
    schema_properties = service_schema.get("properties") or {}
    openapi_properties = component.get("properties") or {}
    for field in sorted(directory_fields):
        if field not in schema_properties:
            lint.fail(schema_path, f"ServiceDescribe.properties.{field} missing")
        if field not in openapi_properties:
            lint.fail(openapi_path, f"components.schemas.ServiceDescribe.properties.{field} missing")
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
        "/_arkret/describe",
        "/_arkret/self/events/describe",
        "/_arkret/root/identity/describe",
        "/_arkret/self/account/describe",
        "/_arkret/find/directory/describe",
        "/_arkret/edge/applet/describe",
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
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return
    paths = openapi.get("paths")
    components = openapi.get("components", {}).get("schemas", {})
    if not isinstance(paths, dict) or not isinstance(components, dict):
        return
    if "/arkret/v1/check" in paths:
        lint.fail(openapi_path, "legacy /arkret/v1/check policy path must not be present; use /_arkret/self/policy/check")

    policy_path = paths.get("/_arkret/self/policy/check", {}).get("post", {})
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
    if request_schema != {"$ref": "#/components/schemas/PolicyCheckRequestBody"}:
        lint.fail(openapi_path, "/_arkret/self/policy/check requestBody must reference PolicyCheckRequestBody")
    if response_schema != {"$ref": "#/components/schemas/PolicyCheckOutcome"}:
        lint.fail(openapi_path, "/_arkret/self/policy/check 200 response must reference PolicyCheckOutcome")

    request_component = resolve_openapi_component_schema(lint, openapi_path, components, "PolicyCheckRequestBody")
    response_component = resolve_openapi_component_schema(lint, openapi_path, components, "PolicyCheckOutcome")
    if not isinstance(request_component, dict):
        lint.fail(openapi_path, "components.schemas.PolicyCheckRequestBody missing")
    elif "realm_id" not in set(request_component.get("required") or []):
        lint.fail(openapi_path, "PolicyCheckRequestBody.required must include realm_id")
    if not isinstance(response_component, dict):
        lint.fail(openapi_path, "components.schemas.PolicyCheckOutcome missing")
    elif "bound_to" not in set(response_component.get("required") or []):
        lint.fail(openapi_path, "PolicyCheckOutcome.required must include bound_to")


def openapi_operations_by_id(openapi: dict[str, Any]) -> dict[str, dict[str, Any]]:
    paths = openapi.get("paths")
    if not isinstance(paths, dict):
        return {}
    operations: dict[str, dict[str, Any]] = {}
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete", "head", "query"):
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if isinstance(operation_id, str) and operation_id:
                operations[operation_id] = operation
    return operations


def openapi_parameter_schema(operation: dict[str, Any], name: str) -> Any:
    for parameter in operation.get("parameters", []) or []:
        if isinstance(parameter, dict) and parameter.get("name") == name:
            return parameter.get("schema")
    return None


def openapi_request_schema(operation: dict[str, Any]) -> Any:
    return (
        operation.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema")
    )


def openapi_response_schema(operation: dict[str, Any]) -> Any:
    return (
        operation.get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema")
    )


def check_openapi_dedicated_operation_schemas(lint: Lint) -> None:
    """Prevent security-sensitive operations from drifting back to generic schemas."""
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return

    paths = openapi.get("paths")
    components = openapi.get("components", {}).get("schemas", {})
    if not isinstance(paths, dict) or not isinstance(components, dict):
        return

    def find_operation(operation_id: str) -> dict[str, Any] | None:
        for path_item in paths.values():
            if not isinstance(path_item, dict):
                continue
            for method in ("get", "post", "put", "patch", "delete", "head", "query"):
                operation = path_item.get(method)
                if isinstance(operation, dict) and operation.get("operationId") == operation_id:
                    return operation
        return None

    def request_schema(operation: dict[str, Any]) -> Any:
        return (
            operation.get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema")
        )

    def response_schema(operation: dict[str, Any]) -> Any:
        return (
            operation.get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema")
        )

    expected = {
        "ak.root.identity.command.submit_did_operation": ("DidOperationSubmitRequestBody", "DidOperationSubmitOutcome"),
        "ak.gate.account.command.issue_session_grant": ("SessionGrantRequestBody", "SessionGrantOutcome"),
        "ak.gate.account.exchange.complete_oidc": ("AccountOidcCallbackRequestBody", "AccountOidcCallbackOutcome"),
        "ak.find.directory.command.announce": ("DirectoryAnnounceRequestBody", "DirectoryAnnounceOutcome"),
        "ak.find.directory.command.withdraw": ("DirectoryWithdrawRequestBody", "DirectoryWithdrawOutcome"),
    }
    expected_response_only = {}
    dedicated_schema_refs = {
        f"#/components/schemas/{name}"
        for pair in expected.values()
        for name in pair
    } | {f"#/components/schemas/{name}" for name in expected_response_only.values()}
    for operation_id, (request_name, response_name) in expected.items():
        operation = find_operation(operation_id)
        if operation is None:
            lint.fail(openapi_path, f"{operation_id} operation missing")
            continue
        if request_schema(operation) != {"$ref": f"#/components/schemas/{request_name}"}:
            lint.fail(openapi_path, f"{operation_id} requestBody must reference {request_name}")
        if response_schema(operation) != {"$ref": f"#/components/schemas/{response_name}"}:
            lint.fail(openapi_path, f"{operation_id} 200 response must reference {response_name}")

    for operation_id, response_name in expected_response_only.items():
        operation = find_operation(operation_id)
        if operation is None:
            lint.fail(openapi_path, f"{operation_id} operation missing")
            continue
        if request_schema(operation) is not None:
            lint.fail(openapi_path, f"{operation_id} must not define a JSON requestBody")
        if response_schema(operation) != {"$ref": f"#/components/schemas/{response_name}"}:
            lint.fail(openapi_path, f"{operation_id} 200 response must reference {response_name}")

    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete", "head", "query"):
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if operation_id in expected or operation_id in expected_response_only:
                continue
            for label, schema in (("requestBody", request_schema(operation)), ("200 response", response_schema(operation))):
                if isinstance(schema, dict) and schema.get("$ref") in dedicated_schema_refs:
                    lint.fail(
                        openapi_path,
                        f"{operation_id} {label} must not reference account/DID dedicated schema {schema.get('$ref')}",
                    )

    session_grant_proof_required = (
        (resolve_openapi_component_schema(lint, openapi_path, components, "SessionGrantRequestBody") or {})
        .get("properties", {})
        .get("proof", {})
        .get("required", [])
    )
    if "audience" not in session_grant_proof_required:
        lint.fail(openapi_path, "SessionGrantRequestBody.proof.required must include audience")

    projection_components = {
        "ak.self.space.query.list": "ProjectionSpaceList",
        "ak.self.strand.query.list": "ProjectionStrandList",
        "ak.self.morph.query.list": "ProjectionMorphList",
    }
    for operation_id, component_name in projection_components.items():
        operation = find_operation(operation_id)
        if operation is None:
            lint.fail(openapi_path, f"{operation_id} operation missing")
            continue
        parameter_names = {
            parameter.get("name")
            for parameter in operation.get("parameters", [])
            if isinstance(parameter, dict)
        }
        for required_parameter in ("cursor", "limit"):
            if required_parameter not in parameter_names:
                lint.fail(openapi_path, f"{operation_id} parameters must include {required_parameter}")
        component = resolve_openapi_component_schema(lint, openapi_path, components, component_name) or {}
        required = set(component.get("required") or [])
        properties = component.get("properties") or {}
        if "has_more" not in required:
            lint.fail(openapi_path, f"{component_name}.required must include has_more")
        if "next_cursor" not in properties:
            lint.fail(openapi_path, f"{component_name}.properties must include next_cursor")


def check_openapi_core_selector_constraints(lint: Lint) -> None:
    """Core event read operations must machine-declare selector and typed-id rules."""
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return
    operations = openapi_operations_by_id(openapi)

    def op(operation_id: str) -> dict[str, Any] | None:
        operation = operations.get(operation_id)
        if not isinstance(operation, dict):
            lint.fail(openapi_path, f"{operation_id} operation missing")
            return None
        return operation

    def expect_any_of(operation_id: str, expected: list[list[str]]) -> None:
        operation = op(operation_id)
        if operation is None:
            return
        actual = operation.get("x-arkret-required-any-of")
        if actual != expected:
            lint.fail(openapi_path, f"{operation_id} x-arkret-required-any-of must be {expected!r}")

    def expect_array_param(operation_id: str, name: str, ref: str) -> None:
        operation = op(operation_id)
        if operation is None:
            return
        schema = openapi_parameter_schema(operation, name)
        if not isinstance(schema, dict):
            lint.fail(openapi_path, f"{operation_id}.{name} parameter schema missing")
            return
        if schema.get("type") != "array":
            lint.fail(openapi_path, f"{operation_id}.{name} must be an array parameter")
        if schema.get("minItems") != 1:
            lint.fail(openapi_path, f"{operation_id}.{name} must require minItems=1")
        items = schema.get("items")
        if not isinstance(items, dict) or items.get("$ref") != ref:
            lint.fail(openapi_path, f"{operation_id}.{name}.items must reference {ref}")

    def expect_param_ref(operation_id: str, name: str, ref: str) -> None:
        operation = op(operation_id)
        if operation is None:
            return
        schema = openapi_parameter_schema(operation, name)
        if not isinstance(schema, dict) or schema.get("$ref") != ref:
            lint.fail(openapi_path, f"{operation_id}.{name} parameter must reference {ref}")

    expect_any_of("ak.self.events.stream.subscribe", [["realms"], ["actors"]])
    expect_array_param("ak.self.events.stream.subscribe", "realms", "#/components/schemas/RealmId")
    expect_array_param("ak.self.events.stream.subscribe", "actors", "#/components/schemas/ActorDid")
    expect_param_ref("ak.self.events.stream.subscribe", "after", "#/components/schemas/Cursor")
    expect_param_ref("ak.self.events.resource.get", "event_id", "#/components/schemas/EventId")
    expect_param_ref("ak.self.snapshot.query.manifest_head", "realm_id", "#/components/schemas/RealmId")

    query_body = op("ak.self.events.read.scan")
    if query_body is not None:
        schema = resolve_openapi_schema_node(lint, openapi_path, openapi.get("components", {}).get("schemas", {}), openapi_request_schema(query_body))
        if not isinstance(schema, dict):
            lint.fail(openapi_path, "ak.self.events.read.scan requestBody schema missing")
        else:
            expected_any_of = [{"required": ["realms"]}, {"required": ["actors"]}]
            if schema.get("anyOf") != expected_any_of:
                lint.fail(openapi_path, "ak.self.events.read.scan requestBody must require realms or actors")
            properties = schema.get("properties")
            if not isinstance(properties, dict):
                lint.fail(openapi_path, "ak.self.events.read.scan requestBody properties missing")
            else:
                for name, ref in (
                    ("realms", "#/components/schemas/RealmId"),
                    ("actors", "#/components/schemas/ActorDid"),
                ):
                    property_schema = properties.get(name)
                    if not isinstance(property_schema, dict):
                        lint.fail(openapi_path, f"ak.self.events.read.scan.{name} property missing")
                        continue
                    if property_schema.get("type") != "array" or property_schema.get("minItems") != 1:
                        lint.fail(openapi_path, f"ak.self.events.read.scan.{name} must be a non-empty array")
                    items = property_schema.get("items")
                    if not isinstance(items, dict) or not (
                        items.get("$ref") == ref or schema_ref_targets(items, ref.rsplit("/", 1)[-1])
                    ):
                        lint.fail(openapi_path, f"ak.self.events.read.scan.{name}.items must reference {ref}")
                for name in ("before", "after"):
                    property_schema = properties.get(name)
                    if not schema_ref_targets(property_schema, "Cursor"):
                        lint.fail(openapi_path, f"ak.self.events.read.scan.{name} must reference Cursor")


def check_openapi_auth_semantics(lint: Lint) -> None:
    """Distinguish public metadata, proof-in-body auth, user tokens, and admin tokens."""
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return
    operations = openapi_operations_by_id(openapi)
    public_metadata_operations = {
        "ak.server.query.describe",
        "ak.self.events.read.describe",
        "ak.peer.events.read.describe",
        "ak.open.mimi.query.provider_directory",
        "ak.root.identity.registry.query.describe",
        "ak.self.account.query.describe",
        "ak.find.directory.query.describe",
        "ak.edge.applet.query.describe",
        "ak.edge.applet.query.protocol_metadata",
    }
    proof_in_body_operations = {
        "ak.gate.account.command.register",
        "ak.gate.account.command.issue_session_grant",
        "ak.gate.account.exchange.complete_oidc",
        "ak.open.invite_locator.query.resolve",
        "ak.open.agent_pairing.query.resolve",
        "ak.open.agent_pairing.command.submit_runtime_key_request",
        "ak.open.agent_pairing.query.runtime_key_request_status",
        "ak.open.device_pairing.command.stage",
        "ak.open.device_pairing.query.resolve",
        "ak.open.device_pairing.query.status",
    }

    for operation_id, operation in operations.items():
        security = operation.get("security")
        if security == []:
            auth = operation.get("x-arkret-auth")
            proof_in_body = (
                operation_id in proof_in_body_operations
                and isinstance(auth, dict)
                and auth.get("public_metadata") is False
                and auth.get("proof_in_body") is True
            )
            if operation_id not in public_metadata_operations and not proof_in_body:
                lint.fail(
                    openapi_path,
                    f"{operation_id} has security: [] but is neither public metadata nor proof-in-body auth",
                )

    for operation_id in proof_in_body_operations:
        operation = operations.get(operation_id)
        if not isinstance(operation, dict):
            lint.fail(openapi_path, f"{operation_id} operation missing")
            continue
        auth = operation.get("x-arkret-auth")
        if not isinstance(auth, dict) or auth.get("public_metadata") is not False or auth.get("proof_in_body") is not True:
            lint.fail(openapi_path, f"{operation_id} must declare x-arkret-auth proof_in_body/public_metadata=false")

    def security_groups(operation: dict[str, Any]) -> list[dict[str, Any]]:
        groups = operation.get("security")
        return [group for group in groups if isinstance(group, dict)] if isinstance(groups, list) else []

    for operation_id, operation in operations.items():
        if not operation_id.startswith("ak.admin."):
            continue
        lint.fail(openapi_path, f"{operation_id} is product-local and must not be registered in Arkret OpenAPI")


def check_read_scope_schema_closure(lint: Lint) -> None:
    cursor_path = ARTIFACTS / "schemas" / "read-cursor.schema.json"
    receipt_path = ARTIFACTS / "schemas" / "read-receipt.schema.json"
    cursor = load_json(lint, cursor_path)
    receipt = load_json(lint, receipt_path)

    if isinstance(cursor, dict):
        if "device_id" not in set(cursor.get("required") or []):
            lint.fail(cursor_path, "read cursor required must include device_id")
        if cursor.get("additionalProperties") is not False:
            lint.fail(cursor_path, "read cursor root additionalProperties must be false")
        read_scope = (cursor.get("properties") or {}).get("read_scope")
        if not isinstance(read_scope, dict):
            lint.fail(cursor_path, "read_cursor.read_scope schema missing")
        else:
            local_ref = read_scope.get("$ref")
            if isinstance(local_ref, str) and local_ref.startswith("#/$defs/"):
                def_name = local_ref.removeprefix("#/$defs/")
                resolved = (cursor.get("$defs") or {}).get(def_name)
                if isinstance(resolved, dict):
                    read_scope = resolved
                else:
                    lint.fail(cursor_path, f"read_cursor.read_scope local $ref does not resolve: {local_ref}")
            properties = read_scope.get("properties") or {}
            if "track_name" not in properties:
                lint.fail(cursor_path, "read_cursor.read_scope must define track_name for strand-track cursors")
            if not isinstance(read_scope.get("allOf"), list) or not read_scope.get("allOf"):
                lint.fail(cursor_path, "read_cursor.read_scope must define conditional scope constraints")

    if isinstance(receipt, dict):
        if "read_scope" not in set(receipt.get("required") or []):
            lint.fail(receipt_path, "read receipt required must include read_scope")
        if receipt.get("additionalProperties") is not False:
            lint.fail(receipt_path, "read receipt root additionalProperties must be false")
        read_scope = (receipt.get("properties") or {}).get("read_scope")
        if not isinstance(read_scope, dict) or read_scope.get("type") != "object":
            lint.fail(receipt_path, "read_receipt.read_scope must be an object schema")
        properties = receipt.get("properties") or {}
        if "strand_id" in properties or "track" in properties:
            lint.fail(receipt_path, "read receipt must not reintroduce top-level strand_id/track aliases")


def check_signed_object_closure(lint: Lint) -> None:
    envelope_path = ARTIFACTS / "schemas" / "encrypted-envelope.schema.json"
    identity_path = ARTIFACTS / "schemas" / "identity-receipt.schema.json"
    batch_path = ARTIFACTS / "schemas" / "event-batch-receipt.schema.json"

    envelope = load_json(lint, envelope_path)
    if isinstance(envelope, dict):
        if envelope.get("additionalProperties") is not False:
            lint.fail(envelope_path, "encrypted envelope root additionalProperties must be false")
        aad = (envelope.get("properties") or {}).get("aad")
        if not isinstance(aad, dict) or aad.get("additionalProperties") is not False:
            lint.fail(envelope_path, "encrypted envelope aad additionalProperties must be false")

    identity = load_json(lint, identity_path)
    if isinstance(identity, dict) and identity.get("additionalProperties") is not False:
        lint.fail(identity_path, "identity receipt root additionalProperties must be false")

    batch = load_json(lint, batch_path)
    if isinstance(batch, dict):
        def is_closed_object_schema(schema: object) -> bool:
            if not isinstance(schema, dict):
                return False
            if schema.get("additionalProperties") is False:
                return True
            ref = schema.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                target: object = batch
                for token in ref[2:].split("/"):
                    if not isinstance(target, dict):
                        return False
                    target = target.get(token)
                return is_closed_object_schema(target)
            branches = schema.get("oneOf")
            return isinstance(branches, list) and bool(branches) and all(is_closed_object_schema(branch) for branch in branches)

        if batch.get("additionalProperties") is not False:
            lint.fail(batch_path, "event batch receipt root additionalProperties must be false")
        properties = batch.get("properties") or {}
        for name in ("scope", "frontier"):
            schema = properties.get(name)
            if not is_closed_object_schema(schema):
                lint.fail(batch_path, f"event batch receipt {name} additionalProperties must be false")


def check_directory_field_drift(lint: Lint) -> None:
    """Directory announce/withdraw prose must not regress to old field names."""
    banned = ("announcement_id", "withdraw_id")
    for path in markdown_files():
        if SPEC_ROOT / "zh" not in path.parents:
            continue
        text = path.read_text(encoding="utf-8")
        for token in banned:
            if token in text:
                lint.fail(path, f"legacy Directory field name present: {token}")


def check_typed_id_prose_consistency(lint: Lint) -> None:
    common_fields = SPEC_ROOT / "zh" / "models" / "common-fields.md"
    encoding = SPEC_ROOT / "zh" / "conformance" / "encoding.md"
    id_registry = ARTIFACTS / "registry" / "id-kind-registry.json"

    common_text = common_fields.read_text(encoding="utf-8")
    if "wire value SHOULD 使用" in common_text:
        lint.fail(common_fields, "typed identifier wire value must be MUST, not SHOULD")
    if "UUID 部分 SHOULD" in common_text:
        lint.fail(common_fields, "typed identifier UUIDv7 rule must be MUST, not SHOULD")

    encoding_text = encoding.read_text(encoding="utf-8")
    if "`txn`" in encoding_text:
        lint.fail(encoding, "typed ID kind prose must use `transaction`, not `txn`")
    if "principal_id`、`device_id` MUST 是完整 typed ID 或完整 DID URI" in encoding_text:
        lint.fail(encoding, "principal_id/device_id subject rule must distinguish DID from device typed ID")

    registry_text = id_registry.read_text(encoding="utf-8")
    if "any 16-byte token" in registry_text:
        lint.fail(id_registry, "rtc_participant must not permit non-UUIDv7 16-byte tokens")

    allowed_legacy_paths = {(ARTIFACTS / "registry" / "forbidden-wire-fields.json").resolve()}
    for path in [*markdown_files(), *all_json_files()]:
        if path.resolve() in allowed_legacy_paths:
            continue
        if "ak:txn:" in path.read_text(encoding="utf-8"):
            lint.fail(path, "legacy ak:txn: prefix present outside migration/forbidden registries")


def check_binding_variant_non_http(lint: Lint) -> None:
    operation_path = ARTIFACTS / "registry" / "operation-registry.json"
    binding_path = ARTIFACTS / "bindings" / "non-http-bindings.yaml"
    registry = load_json(lint, operation_path)
    if not isinstance(registry, dict):
        return
    binding_text = binding_path.read_text(encoding="utf-8")
    binding_operation_ids = set(EVENT_KIND_TOKEN_RE.findall(binding_text))

    for row in registry.get("operations", []) if isinstance(registry.get("operations"), list) else []:
        if not isinstance(row, dict):
            continue
        operation_id = row.get("operation_id")
        if not isinstance(operation_id, str):
            continue
        if not row.get("binding_variant_of"):
            continue
        if row.get("shares_non_http_binding") is True:
            if not isinstance(row.get("notes"), str) or "non-HTTP" not in row.get("notes", ""):
                lint.fail(operation_path, f"{operation_id} shares_non_http_binding must explain non-HTTP exposure in notes")
            continue
        if row.get("http_only_variant") is not True:
            lint.fail(operation_path, f"{operation_id} binding_variant_of must declare http_only_variant=true")
        if row.get("grpc") is not None or row.get("mq") is not None:
            lint.fail(operation_path, f"{operation_id} http-only binding variant must not declare grpc/mq")
        if operation_id in binding_operation_ids:
            lint.fail(binding_path, f"{operation_id} http-only binding variant must not appear in non-HTTP bindings")


def check_openapi_error_enum_alignment(lint: Lint) -> None:
    """ErrorEnvelope.error.code must be generated from the canonical error registry."""
    registry_path = ARTIFACTS / "registry" / "error-code-registry.json"
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    registry = load_json(lint, registry_path)
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(registry, dict) or not isinstance(openapi, dict):
        return

    expected = [
        row.get("code")
        for row in registry.get("codes", [])
        if isinstance(row, dict) and row.get("scope") in {"both", "endpoint"}
    ]
    enum = (
        openapi.get("components", {})
        .get("schemas", {})
        .get("ErrorEnvelope", {})
        .get("properties", {})
        .get("error", {})
        .get("properties", {})
        .get("code", {})
        .get("enum")
    )
    if not isinstance(enum, list):
        lint.fail(openapi_path, "ErrorEnvelope.error.code.enum missing")
        return

    if enum != expected:
        missing = sorted(set(expected) - set(enum))
        extra = sorted(set(enum) - set(expected))
        order_note = "" if missing or extra else "; same values but registry order differs"
        lint.fail(
            openapi_path,
            "ErrorEnvelope.error.code.enum must match error-code-registry codes with "
            f"scope endpoint/both: missing={missing}, extra={extra}{order_note}",
        )


PREIMAGE_SELF_REFERENCE_PHRASES = (
    "enclosing event",
    "carrying this",
    "this event's own",
    "same atomic unit",
    "same submit batch",
    "same ordered submit batch",
    "same batch",
    "sibling event",
)

# encoding.md 6.0.1 registers exactly one exemption, and it is an omission
# (ak.realm.create drops realm_id/scope_ref), not a property. Any future exemption
# belongs here AND in that section; an entry here alone is not a ruling.
PREIMAGE_EVENT_IDENTITY_EXEMPTIONS: set[tuple[str, str]] = set()


def check_preimage_event_identity_commitments(lint: Lint) -> None:
    """No payload field may commit to an Event identity that the preimage decides.

    encoding.md 6.0.1: `event_id` is a function of `event_digest`, whose preimage holds
    `payload` and `refs`. A field naming the enclosing Event, or a sibling of the same
    atomic unit that is not formed yet, therefore has no fixed point — the unit is
    unconstructible and fails at runtime as `event_id_digest_mismatch`. Commit to the
    counterpart's payload digest, or put the commitment outside the preimage (proofs,
    receipts).

    The signal is the declared meaning, so this reads descriptions: a field is only
    reachable by this rule if it says it names the enclosing Event or a same-unit sibling.
    """
    for path in sorted((ARTIFACTS / "schemas").glob("*.schema.json")):
        data = load_json(lint, path)
        if not isinstance(data, dict):
            continue
        for json_path, value, key in walk_json(data):
            if key != "properties" or not isinstance(value, dict):
                continue
            for name, field in value.items():
                if not isinstance(field, dict):
                    continue
                if not (
                    name.endswith("_event_id")
                    or name.endswith("_event_ref")
                    or name.endswith("_event_digest")
                    or name == "event_id"
                ):
                    continue
                if (path.name, name) in PREIMAGE_EVENT_IDENTITY_EXEMPTIONS:
                    continue
                description = str(field.get("description", "")).lower()
                hit = next(
                    (phrase for phrase in PREIMAGE_SELF_REFERENCE_PHRASES if phrase in description),
                    None,
                )
                if hit is None:
                    continue
                if "not the enclosing" in description or "outside the preimage" in description:
                    continue
                lint.fail(
                    path,
                    f"{json_path}.{name} declares an Event identity of the {hit!r} inside the "
                    "digest preimage; encoding.md 6.0.1 forbids it because event_id derives "
                    "from that preimage. Commit to the counterpart's payload digest, or move "
                    "the commitment into proofs/receipts.",
                )


def check_wire_schema_no_bare_scope(lint: Lint) -> None:
    """Wire schemas must use bare scope only for an object's own boundary field."""
    allowed = {
        ("erasure-receipt.schema.json", "$.properties"),
        ("erasure-receipt.schema.json", "$.$defs.verification_stub.properties"),
        ("erasure-verification-stub.schema.json", "$.properties"),
        ("event-batch-receipt.schema.json", "$.properties"),
        ("event-batch-receipt.schema.json", "$.allOf[0].if.properties"),
    }
    for path in sorted((ARTIFACTS / "schemas").glob("*.schema.json")):
        data = load_json(lint, path)
        if not isinstance(data, dict):
            continue
        for json_path, value, key in walk_json(data):
            if key == "properties" and isinstance(value, dict) and "scope" in value:
                if (path.name, json_path) in allowed:
                    continue
                lint.fail(path, f"{json_path}.scope uses bare wire field `scope`; use a domain-prefixed name")


def check_reducer_payload_closure(lint: Lint) -> None:
    """Standard reducer-input payloads must reject undeclared top-level fields."""
    event_envelope_path = ARTIFACTS / "schemas" / "event-envelope.schema.json"
    payload_path = ARTIFACTS / "schemas" / "event-payload.schema.json"
    event_envelope = load_json(lint, event_envelope_path)
    payload_schema = load_json(lint, payload_path)
    if not isinstance(event_envelope, dict) or not isinstance(payload_schema, dict):
        return

    referenced_defs: set[str] = set()
    for _json_path, value, key in walk_json(event_envelope):
        if key == "$ref" and isinstance(value, str) and value.startswith("./event-payload.schema.json#/$defs/"):
            referenced_defs.add(value.rsplit("/", 1)[-1])

    explicitly_open = {"generic_standard_payload"}
    defs = payload_schema.get("$defs", {})
    if not isinstance(defs, dict):
        lint.fail(payload_path, "event payload schema missing $defs")
        return

    for def_name in sorted(referenced_defs - explicitly_open):
        definition = defs.get(def_name)
        if not isinstance(definition, dict):
            lint.fail(payload_path, f"Event Envelope references missing payload $defs/{def_name}")
            continue
        if definition.get("type") == "object" and definition.get("additionalProperties") is not False:
            lint.fail(
                payload_path,
                f"$defs.{def_name} is a standard reducer-input payload and must set additionalProperties=false",
            )


def check_circle_membership_enum_single_source(lint: Lint) -> None:
    """Circle operation DTOs must reference the canonical membership enum directly."""
    path = ARTIFACTS / "schemas" / "circle-operations.schema.json"
    schema = load_json(lint, path)
    if not isinstance(schema, dict):
        return

    defs = schema.get("$defs", {})
    if not isinstance(defs, dict):
        lint.fail(path, "circle operation schema missing $defs")
        return

    if "circle_member_state" in defs:
        lint.fail(path, "$defs.circle_member_state is a forbidden alias; reference membership_state directly")

    canonical_ref = "./event-payload.schema.json#/$defs/membership_state"
    # Only the response DTOs still name a membership value. The request body carries
    # the caller-signed `ak.circle.member.state` Event and nothing else, so the
    # membership on the write path is `circle_member_state_payload.membership`, which
    # single-sources the same enum from inside event-payload.schema.json.
    fields = (
        ("circle_view", "viewer_membership"),
        ("circle_membership_outcome", "membership"),
    )
    for def_name, field_name in fields:
        definition = defs.get(def_name, {})
        properties = definition.get("properties", {}) if isinstance(definition, dict) else {}
        field = properties.get(field_name) if isinstance(properties, dict) else None
        if not isinstance(field, dict) or field.get("$ref") != canonical_ref:
            lint.fail(
                path,
                f"$defs.{def_name}.properties.{field_name} must reference {canonical_ref}",
            )


def check_null_cell_subject_wire_form(lint: Lint) -> None:
    """Pin the wire form of every cell family declared with `cell_subject: null`.

    encoding.md section 4 fixes that subject segment to the literal ASCII string
    `null`. The segment is both the state_root leaf preimage content and the leaf
    sort key, so any other spelling (realm id, Realm role classification, empty
    segment) forks state_root across implementations.
    """
    contract_registry = load_json(
        lint, ARTIFACTS / "registry" / "contract-registry.json"
    )
    if not isinstance(contract_registry, dict):
        return
    registry = contract_registry.get("event_kind_registry")
    if not isinstance(registry, dict):
        return

    null_families: set[str] = set()
    for contract in (registry.get("cell_contracts") or {}).values():
        if not isinstance(contract, dict):
            continue
        for write in contract.get("cell_writes", []) or []:
            if not isinstance(write, dict):
                continue
            family = write.get("cell_family")
            if isinstance(family, str) and family and write.get("cell_subject") is None:
                null_families.add(family)
    if not null_families:
        return

    scan_paths = sorted((ARTIFACTS / "fixtures").rglob("*.json"))
    scan_paths.extend(markdown_files())
    for path in scan_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for family in sorted(null_families):
            if family not in text:
                continue
            pattern = re.compile(
                r"ak:cell:" + re.escape(family) + r":([A-Za-z0-9._~=%-]*)"
            )
            for match in pattern.finditer(text):
                subject = match.group(1)
                if subject != "null":
                    lint.fail(
                        path,
                        f"ak:cell:{family} declares cell_subject: null; its wire subject "
                        f"segment MUST be the literal 'null', found {subject!r} "
                        "(encoding.md section 4)",
                    )


def check_classification_context_paths(lint: Lint) -> None:
    """Every closed-class context MUST resolve to a real node in a real artifact.

    A context that points at a field which does not exist silently governs nothing,
    so a registration slip reads as coverage it never had. `*` matches any element
    of a list or any value of an object.
    """
    path = ARTIFACTS / "registry" / "classification-field-registry.json"
    registry = load_json(lint, path)
    if not isinstance(registry, dict):
        return
    rows = registry.get("closed_class_fields")
    if not isinstance(rows, list):
        lint.fail(path, "closed_class_fields must be an array")
        return

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            lint.fail(path, f"closed_class_fields[{index}] must be an object")
            continue
        context = row.get("context")
        if not isinstance(context, str) or not context:
            lint.fail(path, f"closed_class_fields[{index}].context must be a non-empty string")
            continue
        artifact_ref, _, fragment = context.partition("#")
        artifact_path = ARTIFACTS / artifact_ref
        if not artifact_path.exists():
            lint.fail(path, f"{context} references missing artifact {artifact_ref}")
            continue
        document = load_json(lint, artifact_path)
        nodes: list[Any] = [document]
        for segment in [part for part in fragment.split("/") if part]:
            segment = segment.replace("~1", "/").replace("~0", "~")
            following: list[Any] = []
            for node in nodes:
                if segment == "*":
                    if isinstance(node, list):
                        following.extend(node)
                    elif isinstance(node, dict):
                        following.extend(node.values())
                elif isinstance(node, dict) and segment in node:
                    following.append(node[segment])
            if not following:
                lint.fail(path, f"{context} does not resolve: no node at {segment!r}")
                break
            nodes = following


def check_circle_lifecycle_basis_vector(lint: Lint) -> None:
    """Pin Circle lifecycle evaluation to the Event CBA basis and freshness rules."""
    path = ARTIFACTS / "fixtures" / "circle-scope-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    vector_id = "ak.vector.circle.lifecycle_basis_and_archive_freshness.v1"
    covers = data.get("covers_vectors", [])
    if not isinstance(covers, list) or vector_id not in covers:
        lint.fail(path, f"covers_vectors must include {vector_id}")

    rows = data.get("lifecycle_basis_cases")
    if not isinstance(rows, list):
        lint.fail(path, "lifecycle_basis_cases must be an array")
        return
    cases = {
        row.get("name"): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }
    required_names = {
        "data_event_basis_already_archived",
        "linear_archive_within_freshness_window",
        "linear_archive_beyond_freshness_window",
        "open_set_concurrent_archive",
        "tombstone_is_immediate",
        "restore_does_not_rehabilitate_pre_archive_basis",
        "control_move_basis_active",
        "control_move_basis_archived",
    }
    missing = sorted(required_names - cases.keys())
    if missing:
        lint.fail(path, f"missing Circle lifecycle basis case(s): {missing}")
        return

    archived = cases["data_event_basis_already_archived"]
    if archived.get("evaluation_basis") != "seal_ref" or archived.get("circle_state_at_basis") != "archived":
        lint.fail(path, "data_event_basis_already_archived must evaluate archived state at seal_ref")
    if archived.get("expected") != {"result": "failed_precondition", "reason": "circle_not_active"}:
        lint.fail(path, "an inactive Circle in the Event basis must reject with circle_not_active")

    within = cases["linear_archive_within_freshness_window"]
    within_expected = within.get("expected", {})
    if not isinstance(within_expected, dict) or within_expected.get("eligibility") != "stale_eligible":
        lint.fail(path, "linear archive within the freshness window must be stale_eligible")
    within_distance = within.get("distance_ms")
    within_window = within.get("revocation_freshness_window_ms")
    if not isinstance(within_distance, int) or not isinstance(within_window, int) or within_distance > within_window:
        lint.fail(path, "within-window Circle archive case exceeds its freshness window")
    if within_expected.get("accepted_query_grade") != "stale":
        lint.fail(path, "accepted within-window Circle archive must use stale query grade")
    if set(within_expected.get("allowed_results", [])) != {"accept_stale", "reject"}:
        lint.fail(path, "within-window Circle archive must allow only accept_stale or reject")
    if within_expected.get("must_not_reason") != "circle_not_active":
        lint.fail(path, "post-basis archive must not be reclassified as basis-time circle_not_active")

    beyond = cases["linear_archive_beyond_freshness_window"]
    beyond_distance = beyond.get("distance_ms")
    beyond_window = beyond.get("revocation_freshness_window_ms")
    if not isinstance(beyond_distance, int) or not isinstance(beyond_window, int) or beyond_distance <= beyond_window:
        lint.fail(path, "beyond-window Circle archive case must exceed its freshness window")
    if beyond.get("expected") != {"result": "reject_or_hide", "reason": "stale_seal_ref"}:
        lint.fail(path, "beyond-window Circle archive must reject or hide with stale_seal_ref")

    concurrent = cases["open_set_concurrent_archive"]
    concurrent_expected = concurrent.get("expected", {})
    if concurrent.get("notary_profile") != "open_set" or concurrent.get("evaluation_basis") != "joined_control_view":
        lint.fail(path, "concurrent Circle archive must evaluate the open_set joined control view")
    if not isinstance(concurrent_expected, dict) or concurrent_expected.get("reason") != "stale_seal_ref":
        lint.fail(path, "concurrent Circle archive must fail closed with stale_seal_ref")
    if concurrent_expected.get("freshness_window_applies") is not False:
        lint.fail(path, "concurrent Circle archive must not receive a freshness window")

    tombstone = cases["tombstone_is_immediate"]
    tombstone_expected = tombstone.get("expected", {})
    if tombstone.get("observed_lifecycle_move") != "ak.circle.tombstone":
        lint.fail(path, "tombstone_is_immediate must use ak.circle.tombstone")
    if (
        not isinstance(tombstone_expected, dict)
        or tombstone_expected.get("reason") != "stale_seal_ref"
        or tombstone_expected.get("freshness_window_applies") is not False
    ):
        lint.fail(path, "Circle tombstone must fail closed without a freshness window")

    restore = cases["restore_does_not_rehabilitate_pre_archive_basis"]
    restore_expected = restore.get("expected", {})
    if restore.get("seal_ref_position") != "before_archive":
        lint.fail(path, "restore barrier case must use a pre-archive seal_ref")
    if not isinstance(restore_expected, dict) or restore_expected.get("reason") != "stale_seal_ref":
        lint.fail(path, "restore must not rehabilitate a pre-archive seal_ref")
    if restore_expected.get("requires_new_basis_containing") != "ak.circle.restore":
        lint.fail(path, "post-restore writes must require a basis containing ak.circle.restore")

    control_active = cases["control_move_basis_active"]
    control_archived = cases["control_move_basis_archived"]
    control_active_expected = control_active.get("expected", {})
    if control_active.get("evaluation_basis") != "seal_basis_joined_view":
        lint.fail(path, "active Control Move case must evaluate seal_basis joined view")
    if (
        not isinstance(control_active_expected, dict)
        or control_active_expected.get("seal_revalidation_basis")
        != "frozen_predecessor_joined_governance_state"
    ):
        lint.fail(path, "Control Move must be revalidated at the Seal frozen predecessor state")
    if control_archived.get("expected") != {"result": "failed_precondition", "reason": "circle_not_active"}:
        lint.fail(path, "archived Circle in Control Move basis must reject with circle_not_active")


def check_did_and_device_constraints(lint: Lint) -> None:
    """Reject ambiguous DID/DID URL and device_id constraints in machine artifacts."""
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"

    schema_paths = sorted((ARTIFACTS / "schemas").glob("*.schema.json"))
    schema_docs: dict[str, Any] = {}
    for path in schema_paths:
        data = load_json(lint, path)
        if isinstance(data, dict):
            schema_docs[path.name] = data

    def resolve_terminal(owner_name: str, node: Any) -> Any:
        """Follow $ref chains (local and sibling-file) to the terminal constraint node."""
        seen: set[tuple[str, str]] = set()
        while isinstance(node, dict) and isinstance(node.get("$ref"), str):
            ref = node["$ref"]
            file_part, _, fragment = ref.partition("#")
            if file_part in ("", "."):
                target_name = owner_name
            else:
                target_name = file_part.removeprefix("./")
                if "/" in target_name:
                    return None
            key = (target_name, fragment)
            if key in seen:
                return None
            seen.add(key)
            target_doc = schema_docs.get(target_name)
            if target_doc is None:
                return None
            try:
                node = resolve_json_pointer(target_doc, f"#{fragment}" if fragment else "#")
            except KeyError:
                return None
            owner_name = target_name
        return node

    for path in schema_paths:
        data = schema_docs.get(path.name)
        if not isinstance(data, dict):
            continue
        defs = data.get("$defs", {})
        if isinstance(defs, dict):
            local_did_url = defs.get("did_url")
            if (
                isinstance(local_did_url, dict)
                and "pattern" in local_did_url
                and local_did_url["pattern"] != DID_URL_PROFILE_PATTERN
            ):
                lint.fail(
                    path,
                    "$defs.did_url must equal the Arkret verification-method DID URL profile "
                    "(common-ids.schema.json#/$defs/did_url)",
                )
            local_did = defs.get("did")
            if isinstance(local_did, dict) and "pattern" in local_did and local_did["pattern"] != DID_BARE_PATTERN:
                lint.fail(path, "$defs.did must equal the canonical bare DID pattern (common-ids.schema.json#/$defs/did)")
        for json_path, value, key in walk_json(data):
            if key == "pattern" and value == DID_LEGACY_GREEDY_PATTERN:
                lint.fail(path, f"{json_path} uses legacy greedy DID pattern; use bare DID or DID URL pattern")
            if key == "properties" and isinstance(value, dict):
                for vm_key in ("verification_method", "verificationMethod"):
                    vm_schema = value.get(vm_key)
                    if not isinstance(vm_schema, dict):
                        continue
                    terminal = resolve_terminal(path.name, vm_schema)
                    if not isinstance(terminal, dict):
                        continue
                    if terminal.get("type") == "array":
                        # DID Document verification-method object arrays are covered by
                        # their item schemas, not by the DID URL profile.
                        continue
                    if terminal.get("pattern") != DID_URL_PROFILE_PATTERN:
                        lint.fail(
                            path,
                            f"{json_path}.{vm_key} must resolve to the Arkret verification-method DID URL "
                            "profile (common-ids.schema.json#/$defs/did_url); see "
                            "identity/did-usage-and-verification.md section 2.2.1",
                        )

    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return

    for json_path, value, key in walk_json(openapi):
        if key == "pattern" and value in {DID_LEGACY_PREFIX_PATTERN, DID_LEGACY_GREEDY_PATTERN}:
            lint.fail(openapi_path, f"{json_path} uses legacy DID pattern {value!r}")

        if key == "properties" and isinstance(value, dict):
            device_schema = value.get("device_id")
            if isinstance(device_schema, dict) and not (
                device_schema.get("$ref") or device_schema.get("pattern") == DEVICE_ID_PATTERN
            ):
                lint.fail(openapi_path, f"{json_path}.device_id must use the canonical ak:device UUIDv7 pattern")

            vm_schema = value.get("verification_method")
            if isinstance(vm_schema, dict) and not (
                vm_schema.get("$ref") or "#" in str(vm_schema.get("pattern", ""))
            ):
                lint.fail(openapi_path, f"{json_path}.verification_method must use a DID URL pattern with a key fragment")

        if isinstance(value, dict) and value.get("name") == "device_id":
            schema = value.get("schema", {})
            if isinstance(schema, dict) and not (
                schema.get("$ref") or schema.get("pattern") == DEVICE_ID_PATTERN
            ):
                lint.fail(openapi_path, f"{json_path}.schema must use the canonical ak:device UUIDv7 pattern")


def infer_openapi_success_shape(method: str, content: Any) -> str:
    """Infer response shape from HTTP semantics instead of operation-name allowlists."""
    if method == "head":
        return "metadata_headers"
    if not isinstance(content, dict) or not content:
        return "empty_response"
    if "application/x-ndjson" in content:
        return "event_stream"
    if "application/octet-stream" in content:
        return "binary_stream"
    json_media = content.get("application/json")
    schema = json_media.get("schema") if isinstance(json_media, dict) else None
    if schema is None:
        return "empty_response"
    if isinstance(schema, dict):
        ref = schema.get("$ref")
        if ref == GENERIC_OPERATION_RESULT_REF:
            return "operation_result"
        if ref == "#/components/schemas/ServiceDescribe":
            return "service_describe"
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            return "typed_response"
        if isinstance(ref, str) and ref.startswith("../schemas/"):
            return "schema_resource"
        return "inline_response"
    return "empty_response"


def normalize_artifact_schema_ref(ref: str | None) -> str | None:
    if not isinstance(ref, str) or not ref:
        return None
    if ref.startswith("../schemas/"):
        return "schemas/" + ref.removeprefix("../schemas/")
    if ref.startswith("./schemas/"):
        return "schemas/" + ref.removeprefix("./schemas/")
    if ref.startswith("schemas/"):
        return ref
    return ref


def openapi_artifact_schema_ref(schema: Any, components: dict[str, Any]) -> str | None:
    if not isinstance(schema, dict):
        return None
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return None
    if ref.startswith("#/components/schemas/"):
        component_name = ref.rsplit("/", 1)[-1]
        component_schema = components.get(component_name)
        if isinstance(component_schema, dict):
            component_ref = component_schema.get("$ref")
            if isinstance(component_ref, str):
                return normalize_artifact_schema_ref(component_ref)
        return ref
    return normalize_artifact_schema_ref(ref)


def openapi_request_schema(operation: dict[str, Any]) -> Any:
    content = (
        operation.get("requestBody", {})
        .get("content", {})
    )
    if not isinstance(content, dict):
        return None
    for media_type in ("application/json", "multipart/form-data", "application/octet-stream"):
        schema = content.get(media_type, {}).get("schema") if isinstance(content.get(media_type), dict) else None
        if isinstance(schema, dict):
            return schema
    for media in content.values():
        schema = media.get("schema") if isinstance(media, dict) else None
        if isinstance(schema, dict):
            return schema
    return None


def check_artifact_schema_ref(lint: Lint, owner: Path, label: str, ref: Any) -> None:
    if not isinstance(ref, str) or not ref:
        lint.fail(owner, f"{label} must be a non-empty artifact schema ref")
        return
    file_ref, _, fragment = ref.partition("#")
    if not file_ref.startswith("schemas/"):
        lint.fail(owner, f"{label} must reference artifacts/schemas: {ref}")
        return
    target = ARTIFACTS / file_ref
    data = load_json(lint, target)
    if not isinstance(data, dict):
        return
    if fragment:
        current: Any = data
        for token in fragment.removeprefix("/").split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict) and token in current:
                current = current[token]
            else:
                lint.fail(owner, f"{label} fragment does not exist: {ref}")
                return


def collect_openapi_operation_facts(lint: Lint, openapi_path: Path) -> dict[str, dict[str, Any]]:
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return {}
    paths = openapi.get("paths")
    if not isinstance(paths, dict):
        lint.fail(openapi_path, "OpenAPI paths missing")
        return {}
    components = openapi.get("components", {}).get("schemas", {})
    if not isinstance(components, dict):
        components = {}

    facts: dict[str, dict[str, Any]] = {}
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete", "head", "query"):
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                continue
            request_schema = openapi_request_schema(operation)
            response_content = (
                operation.get("responses", {})
                .get("200", {})
                .get("content", {})
            )
            response_schema = (
                response_content.get("application/json", {}).get("schema")
                if isinstance(response_content, dict)
                and isinstance(response_content.get("application/json"), dict)
                else None
            )
            facts[operation_id] = {
                "generic_request": isinstance(request_schema, dict)
                and request_schema.get("$ref") == GENERIC_OPERATION_REQUEST_REF,
                "generic_response": isinstance(response_schema, dict)
                and response_schema.get("$ref") == GENERIC_OPERATION_RESULT_REF,
                "request_schema_ref": openapi_artifact_schema_ref(request_schema, components),
                "response_schema_ref": openapi_artifact_schema_ref(response_schema, components),
                "success_shape_kind": infer_openapi_success_shape(method, response_content),
            }
    return facts


def check_operation_binding_metadata(lint: Lint) -> None:
    """Operation registry must machine-declare success shape and governed generic bindings."""
    operation_path = ARTIFACTS / "registry" / "operation-registry.json"
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    operation_registry = load_json(lint, operation_path)
    if not isinstance(operation_registry, dict):
        return

    allowed_success_shapes = set((operation_registry.get("success_shape_kind_definitions") or {}).keys())
    if not allowed_success_shapes:
        lint.fail(operation_path, "operation registry missing success_shape_kind_definitions")

    surface_class_by_operation: dict[str, str] = {}
    for group in operation_registry.get("surface_groups", []) if isinstance(operation_registry.get("surface_groups"), list) else []:
        if not isinstance(group, dict):
            continue
        surface_class = group.get("surface_class")
        for operation_id in group.get("operations", []) or []:
            if isinstance(operation_id, str) and isinstance(surface_class, str):
                surface_class_by_operation[operation_id] = surface_class

    openapi_facts = collect_openapi_operation_facts(lint, openapi_path)
    for row in operation_registry.get("operations", []) if isinstance(operation_registry.get("operations"), list) else []:
        if not isinstance(row, dict):
            continue
        operation_id = row.get("operation_id")
        if not isinstance(operation_id, str):
            continue
        facts = openapi_facts.get(operation_id)
        if facts is None:
            lint.fail(operation_path, f"{operation_id} missing from OpenAPI facts")
            continue

        success_shape_kind = row.get("success_shape_kind")
        if success_shape_kind not in allowed_success_shapes:
            lint.fail(operation_path, f"{operation_id} has invalid success_shape_kind {success_shape_kind!r}")
        elif success_shape_kind != facts["success_shape_kind"]:
            lint.fail(
                operation_path,
                f"{operation_id} success_shape_kind={success_shape_kind!r} "
                f"but OpenAPI implies {facts['success_shape_kind']!r}",
            )

        uses_generic = facts["generic_request"] or facts["generic_response"]
        generic_binding = row.get("generic_binding")
        for schema_field, fact_field in (
            ("request_schema_ref", "request_schema_ref"),
            ("response_schema_ref", "response_schema_ref"),
        ):
            if schema_field in row:
                expected_ref = row.get(schema_field)
                check_artifact_schema_ref(lint, operation_path, f"{operation_id}.{schema_field}", expected_ref)
                if facts.get(fact_field) != expected_ref:
                    lint.fail(
                        operation_path,
                        f"{operation_id} {schema_field}={expected_ref!r} "
                        f"but OpenAPI references {facts.get(fact_field)!r}",
                    )
        if uses_generic:
            if surface_class_by_operation.get(operation_id) == "core":
                lint.fail(
                    operation_path,
                    f"{operation_id} has surface_class=core and must not use generic OpenAPI bindings",
                )
            if not isinstance(generic_binding, dict):
                lint.fail(operation_path, f"{operation_id} uses OperationRequest/OperationResult and must declare generic_binding")
                continue
            if generic_binding.get("request") is not facts["generic_request"]:
                lint.fail(operation_path, f"{operation_id} generic_binding.request does not match OpenAPI")
            if generic_binding.get("response") is not facts["generic_response"]:
                lint.fail(operation_path, f"{operation_id} generic_binding.response does not match OpenAPI")
            if generic_binding.get("profile_gate") is not True:
                lint.fail(operation_path, f"{operation_id} generic_binding.profile_gate must be true")
            for field in ("reason", "migration_plan", "surface"):
                if not isinstance(generic_binding.get(field), str) or not generic_binding.get(field):
                    lint.fail(operation_path, f"{operation_id} generic_binding.{field} must be a non-empty string")
        elif generic_binding is not None:
            lint.fail(operation_path, f"{operation_id} declares generic_binding but OpenAPI uses dedicated schemas")


def check_binding_completeness_index(lint: Lint) -> None:
    catalog_path = ARTIFACTS / "registry" / "contract-registry.json"
    binding_path = SPEC_ROOT / "zh" / "sync" / "service-http-binding.md"
    catalog = load_json(lint, catalog_path)
    if not isinstance(catalog, dict):
        return
    operation_registry = catalog.get("operation_registry")
    if not isinstance(operation_registry, dict):
        lint.fail(catalog_path, "operation_registry missing")
        return
    try:
        text = binding_path.read_text(encoding="utf-8")
    except Exception as exc:
        lint.fail(binding_path, f"unable to read binding completeness index: {exc}")
        return
    if "#### 2.4.1 Binding completeness index" not in text:
        lint.fail(binding_path, "missing §2.4.1 Binding completeness index")
        return
    section = text.split("#### 2.4.1 Binding completeness index", 1)[1].split("\n#### ", 1)[0]
    listed = {
        match.group(1)
        for match in re.finditer(r"^\|\s*`([^`]+)`\s*\|\s*`migration_required`\s*\|", section, re.MULTILINE)
    }
    expected_migration: set[str] = set()
    for row in operation_registry.get("operations", []) if isinstance(operation_registry.get("operations"), list) else []:
        if not isinstance(row, dict):
            continue
        generic_binding = row.get("generic_binding")
        if not isinstance(generic_binding, dict) or not generic_binding.get("migration_plan"):
            continue
        operation_id = row.get("operation_id")
        if not isinstance(operation_id, str):
            continue
        expected_migration.add(operation_id)
        expected = f"| `{operation_id}` | `migration_required` |"
        if expected not in text:
            lint.fail(
                binding_path,
                f"generic operation {operation_id} with migration_plan must be listed "
                "in Binding completeness index as migration_required",
            )
    stale = sorted(listed - expected_migration)
    if stale:
        lint.fail(
            binding_path,
            "Binding completeness index lists non-generic operation(s) as migration_required: "
            + ", ".join(stale),
        )


def schema_ref_mentioned_in_field_constraints(constraints: str, schema_ref: str) -> bool:
    if schema_ref in constraints:
        return True
    file_ref, _, fragment = schema_ref.partition("#")
    return bool(fragment and file_ref in constraints and f"#{fragment}" in constraints)


def collect_operation_field_table_constraints(text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("| `ak."):
            continue
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) != 5:
            continue
        operation_id = cells[0].strip("`")
        if operation_id.startswith("ak."):
            rows[operation_id] = cells[4]
    return rows


def check_operation_field_table_schema_refs(lint: Lint) -> None:
    """Operation field table rows must mention registry-declared schema refs."""
    catalog_path = ARTIFACTS / "registry" / "contract-registry.json"
    binding_path = SPEC_ROOT / "zh" / "sync" / "service-http-binding.md"
    catalog = load_json(lint, catalog_path)
    if not isinstance(catalog, dict):
        return
    operation_registry = catalog.get("operation_registry")
    if not isinstance(operation_registry, dict):
        lint.fail(catalog_path, "operation_registry missing")
        return
    try:
        text = binding_path.read_text(encoding="utf-8")
    except Exception as exc:
        lint.fail(binding_path, f"unable to read operation field table: {exc}")
        return
    field_rows = collect_operation_field_table_constraints(text)
    for row in operation_registry.get("operations", []) if isinstance(operation_registry.get("operations"), list) else []:
        if not isinstance(row, dict):
            continue
        operation_id = row.get("operation_id")
        if not isinstance(operation_id, str):
            continue
        refs = [
            ref
            for ref in (row.get("request_schema_ref"), row.get("response_schema_ref"))
            if isinstance(ref, str) and ref
        ]
        if not refs:
            continue
        constraints = field_rows.get(operation_id)
        if constraints is None:
            lint.fail(binding_path, f"{operation_id} declares schema refs but is missing from the operation field table")
            continue
        for schema_ref in refs:
            if not schema_ref_mentioned_in_field_constraints(constraints, schema_ref):
                lint.fail(
                    binding_path,
                    f"{operation_id} field table constraints must mention schema_ref {schema_ref}",
                )


def check_capability_action_event_mapping(lint: Lint) -> None:
    """Machine-check allowed action ↔ event-kind mapping deviations."""
    action_path = ARTIFACTS / "registry" / "capability-action-registry.json"
    action_registry = load_json(lint, action_path)
    if not isinstance(action_registry, dict):
        return

    allowed = set((action_registry.get("event_mapping_kind_definitions") or {}).keys())
    if not allowed:
        lint.fail(action_path, "capability action registry missing event_mapping_kind_definitions")
    for row in action_registry.get("actions", []) if isinstance(action_registry.get("actions"), list) else []:
        if not isinstance(row, dict):
            continue
        action = row.get("action")
        targets = row.get("target_event_kinds") or []
        mapping_kind = row.get("event_mapping_kind")
        if not isinstance(action, str):
            continue
        if mapping_kind not in allowed:
            lint.fail(action_path, f"{action} has invalid event_mapping_kind {mapping_kind!r}")
            continue
        if not targets and mapping_kind != "non_event_surface":
            lint.fail(action_path, f"{action} has no target_event_kinds and must use event_mapping_kind=non_event_surface")
        elif targets == [action] and mapping_kind != "same_name":
            lint.fail(action_path, f"{action} maps to the same event kind and must use event_mapping_kind=same_name")
        elif targets and targets != [action] and mapping_kind in {"same_name", "non_event_surface"}:
            lint.fail(action_path, f"{action} deviates from target_event_kinds and must declare an explicit deviation kind")


def check_event_admission_coverage(lint: Lint) -> None:
    """Every active durable reducer-input event MUST have a machine-readable admission source."""
    event_path = ARTIFACTS / "registry" / "event-kind-registry.json"
    action_path = ARTIFACTS / "registry" / "capability-action-registry.json"
    event_registry = load_json(lint, event_path)
    action_registry = load_json(lint, action_path)
    if not isinstance(event_registry, dict) or not isinstance(action_registry, dict):
        return
    allowed_classes = set((event_registry.get("admission_class_definitions") or {}).keys())
    if not allowed_classes:
        lint.fail(event_path, "event registry missing admission_class_definitions")
    predicate_contract = event_registry.get("admission_predicate_contract")
    if not isinstance(predicate_contract, dict) or predicate_contract.get("closed_world") is not True:
        lint.fail(event_path, "event registry missing closed-world admission_predicate_contract")
    actions = action_registry.get("actions", [])
    action_names = {a.get("action") for a in actions if isinstance(a, dict)}
    covered: set[str] = set()
    for a in actions:
        if isinstance(a, dict):
            for target in (a.get("target_event_kinds") or []):
                covered.add(target)
    for event in event_registry.get("event_kinds", []):
        if not isinstance(event, dict):
            continue
        if event.get("status") != "active" or event.get("wire_scope") != "durable_event" or not event.get("reducer_input"):
            continue
        kind = event.get("event_kind")
        admission = event.get("admission")
        if kind not in covered and not admission:
            lint.fail(event_path, f"{kind}: active durable reducer-input event has no admission source (no capability action coverage and no admission class)")
            continue
        if admission is not None:
            if admission not in allowed_classes:
                lint.fail(event_path, f"{kind}: invalid admission class {admission!r}")
            if admission == "conditional":
                variants = event.get("admission_variants")
                if not isinstance(variants, list) or len(variants) < 2:
                    lint.fail(event_path, f"{kind}: admission=conditional MUST list at least two admission_variants")
                else:
                    otherwise_count = 0
                    seen_predicates: set[str] = set()
                    for index, variant in enumerate(variants):
                        if not isinstance(variant, dict):
                            lint.fail(event_path, f"{kind}: admission_variants[{index}] MUST be an object")
                            continue
                        unknown_variant_keys = set(variant) - {"when", "admission"}
                        if unknown_variant_keys:
                            lint.fail(event_path, f"{kind}: admission_variants[{index}] has unknown keys {sorted(unknown_variant_keys)!r}")
                        when = variant.get("when")
                        variant_admission = variant.get("admission")
                        if not isinstance(when, dict):
                            lint.fail(event_path, f"{kind}: admission_variants[{index}].when MUST be an object")
                        elif when.get("otherwise") is True:
                            otherwise_count += 1
                            if index != len(variants) - 1 or len(when) != 1:
                                lint.fail(event_path, f"{kind}: conditional otherwise MUST be the final predicate and contain no other selectors")
                        else:
                            allowed_selectors = {"payload_path", "const", "not_const", "ref_role", "ref_critical", "ref_exact_count", "top_level_fields_present"}
                            unknown_selectors = set(when) - allowed_selectors
                            if unknown_selectors:
                                lint.fail(event_path, f"{kind}: admission_variants[{index}].when has unknown selectors {sorted(unknown_selectors)!r}")
                            if not when:
                                lint.fail(event_path, f"{kind}: admission_variants[{index}].when MUST contain a selector")
                            payload_path = when.get("payload_path")
                            if "payload_path" in when:
                                if not isinstance(payload_path, str) or re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*", payload_path) is None:
                                    lint.fail(event_path, f"{kind}: admission_variants[{index}].when.payload_path is invalid")
                                comparison_selectors = {selector for selector in ("const", "not_const") if selector in when}
                                if len(comparison_selectors) != 1:
                                    lint.fail(event_path, f"{kind}: admission_variants[{index}].when.payload_path requires exactly one of const/not_const")
                            elif "const" in when or "not_const" in when:
                                lint.fail(event_path, f"{kind}: admission_variants[{index}] const/not_const requires payload_path")
                            for selector in ("const", "not_const"):
                                if selector in when and not (when[selector] is None or isinstance(when[selector], (str, int, bool))):
                                    lint.fail(event_path, f"{kind}: admission_variants[{index}].when.{selector} MUST be a JSON scalar")
                            ref_role = when.get("ref_role")
                            if "ref_role" in when and (not isinstance(ref_role, str) or re.fullmatch(r"[a-z][a-z0-9_]*", ref_role) is None):
                                lint.fail(event_path, f"{kind}: admission_variants[{index}].when.ref_role is invalid")
                            for selector in ("ref_critical", "ref_exact_count"):
                                if selector in when and "ref_role" not in when:
                                    lint.fail(event_path, f"{kind}: admission_variants[{index}].when.{selector} requires ref_role")
                            if "ref_critical" in when and not isinstance(when["ref_critical"], bool):
                                lint.fail(event_path, f"{kind}: admission_variants[{index}].when.ref_critical MUST be boolean")
                            if "ref_exact_count" in when and (not isinstance(when["ref_exact_count"], int) or isinstance(when["ref_exact_count"], bool) or when["ref_exact_count"] < 0):
                                lint.fail(event_path, f"{kind}: admission_variants[{index}].when.ref_exact_count MUST be a non-negative integer")
                            if "top_level_fields_present" in when:
                                fields = when["top_level_fields_present"]
                                allowed_fields = {"executed_by", "authorization_ref"}
                                if not isinstance(fields, list) or not fields or len(fields) != len(set(fields)) or any(field not in allowed_fields for field in fields):
                                    lint.fail(event_path, f"{kind}: admission_variants[{index}].when.top_level_fields_present MUST be a non-empty unique subset of {sorted(allowed_fields)!r}")
                            predicate_key = json.dumps(when, sort_keys=True, separators=(",", ":"))
                            if predicate_key in seen_predicates:
                                lint.fail(event_path, f"{kind}: admission_variants[{index}].when duplicates an earlier predicate")
                            seen_predicates.add(predicate_key)
                        if variant_admission not in allowed_classes - {"conditional"}:
                            lint.fail(event_path, f"{kind}: admission_variants[{index}] has invalid admission {variant_admission!r}")
                        if variant_admission == "capability_gated" and kind not in covered:
                            lint.fail(
                                event_path,
                                f"{kind}: capability_gated admission variant but no action's "
                                "target_event_kinds lists this kind - admission has a single "
                                "direction of truth",
                            )
                    if otherwise_count != 1:
                        lint.fail(event_path, f"{kind}: admission=conditional MUST contain exactly one final otherwise variant")
            elif admission == "capability_gated":
                if kind not in covered:
                    lint.fail(
                        event_path,
                        f"{kind}: admission=capability_gated but no action's target_event_kinds "
                        "lists this kind - admission has a single direction of truth",
                    )
            if "admission_capabilities" in event or (
                isinstance(event.get("admission_variants"), list)
                and any(
                    isinstance(variant, dict) and "admission_capabilities" in variant
                    for variant in event["admission_variants"]
                )
            ):
                lint.fail(
                    event_path,
                    f"{kind}: admission_capabilities is retired; the authorizing actions are "
                    "exactly the ones whose target_event_kinds list the kind",
                )


def _resolve_dto_object(schema_ref: str) -> dict | None:
    """Resolve a 'schemas/X.schema.json#/$defs/Y' ref to its object, following pure $ref aliases."""
    file_ref, _, fragment = (schema_ref or "").partition("#")
    if not file_ref:
        return None
    path = ARTIFACTS / file_ref

    def load(p: Path):
        try:
            return parse_json_file(p.resolve())
        except Exception:
            return None

    def navigate(doc, frag):
        node = doc
        for token in [t for t in frag.split("/") if t]:
            token = token.replace("~1", "/").replace("~0", "~")
            if isinstance(node, dict) and token in node:
                node = node[token]
            else:
                return None
        return node

    document = load(path)
    if document is None:
        return None
    node = navigate(document, fragment.lstrip("#")) if fragment else document
    seen: set[str] = set()
    while isinstance(node, dict) and set(node.keys()) == {"$ref"}:
        ref = node["$ref"]
        if ref in seen:
            break
        seen.add(ref)
        ref_file, _, ref_fragment = ref.partition("#")
        if ref_file:
            path = (path.parent / ref_file).resolve()
            document = load(path)
            if document is None:
                return None
        node = navigate(document, ref_fragment.lstrip("#")) if ref_fragment else document
    return node if isinstance(node, dict) else None


def check_operation_dto_closure(lint: Lint) -> None:
    """Core operation DTOs (request/response object schemas) MUST be closed.

    Every operation request/response schema that resolves to a ``type: object``
    MUST declare ``additionalProperties: false`` unless the object is explicitly
    marked as an intentional extension surface via ``x_extension_surface: true``
    or a non-empty ``$comment`` (models/common-fields.md DTO-closure policy).
    Reads the generated operation-schema-index (already verified current).
    """
    index_path = ARTIFACTS / "reports" / "operation-schema-index.json"
    index = load_json(lint, index_path)
    if not isinstance(index, dict):
        return
    def summaries(dto: dict[str, Any]):
        yield dto
        for variant in dto.get("variants", []):
            if isinstance(variant, dict):
                yield from summaries(variant)

    for operation in index.get("operations", []):
        if not isinstance(operation, dict):
            continue
        operation_id = operation.get("operation_id")
        for role in ("request", "response"):
            dto = operation.get(role)
            if not isinstance(dto, dict):
                continue
            for summary in summaries(dto):
                if summary.get("schema_kind") != "object" or summary.get("closed") is True:
                    continue
                schema_ref = summary.get("schema_ref") or ""
                source = _resolve_dto_object(schema_ref)
                marked = isinstance(source, dict) and (
                    source.get("x_extension_surface") is True or bool(source.get("$comment"))
                )
                if not marked:
                    lint.fail(
                        index_path,
                        f"{operation_id} {role} DTO is not closed: {schema_ref} "
                        "MUST close every object/oneOf variant or be marked open (x_extension_surface / $comment)",
                    )


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
    versioned_event_kind_re = re.compile(
        r"(?<![A-Za-z0-9_.-])("
        + "|".join(re.escape(kind) for kind in active_event_kinds)
        + r")\.v[0-9]+\b"
    )

    for path in scan_paths:
        try:
            text = read_text(path.resolve())
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

            if "/arkret/v1/check" in line:
                lint.fail(path, f"line {line_no}: legacy policy path /arkret/v1/check must be replaced with /_arkret/self/policy/check")

            if TRUST_DOMAIN_JSON_DID_RE.search(line):
                lint.fail(path, f"line {line_no}: trust_domain must use ak:trust_domain:<scope>, not a raw DID")

            if LEGACY_DID_METHOD_REGEX_RE.search(line):
                lint.fail(path, f"line {line_no}: DID regex must not allow ':'/'.'/'_' inside the method segment")

            for match in OPERATION_COUNT_RE.finditer(line):
                count = int(match.group(1))
                if count != operation_count:
                    lint.fail(path, f"line {line_no}: hard-coded operation count {count} differs from registry count {operation_count}")

            for match in versioned_event_kind_re.finditer(line):
                lint.fail(
                    path,
                    f"line {line_no}: active Event.kind {match.group(1)} "
                    "must not be written with a .vN suffix",
                )


def check_normative_clause_registry(lint: Lint) -> None:
    """Reverse coverage: every registered normative clause must have live evidence.

    vector-registry.json proves each vector has a consumer. This registry proves
    the other direction for the high-risk obligation set: each registered clause
    points at an existing prose section, that section's text has not drifted
    since the clause was reviewed, and the clause names evidence that actually
    exists (an active vector, or an explicit non-vector test plan).
    """
    path = ARTIFACTS / "registry" / "normative-clause-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    if data.get("source_of_truth") is not True:
        lint.fail(path, "source_of_truth must be true")

    coverage_scope = data.get("coverage_scope")
    if not isinstance(coverage_scope, dict):
        lint.fail(path, "coverage_scope must be an object")
        return
    categories = coverage_scope.get("included_categories")
    if not isinstance(categories, list) or not categories:
        lint.fail(path, "coverage_scope.included_categories must be a non-empty array")
        return
    included_categories = set(categories)
    for field in ("rule", "extension_rule"):
        if not isinstance(coverage_scope.get(field), str) or not coverage_scope[field].strip():
            lint.fail(path, f"coverage_scope.{field} must be a non-empty string")

    vector_data = load_json(lint, ARTIFACTS / "registry" / "vector-registry.json")
    active_vectors = {
        row.get("vector_id")
        for row in (vector_data.get("vectors", []) if isinstance(vector_data, dict) else [])
        if isinstance(row, dict) and row.get("status") == "active"
    }

    rows = data.get("clauses")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "clauses must be a non-empty list")
        return

    clause_id_re = re.compile(r"^AK-NC-\d{3}$")
    allowed_status = {"active", "deprecated"}
    allowed_grades = {"vector", "api_shape", "audit"}
    seen: set[str] = set()
    covered_categories: set[str] = set()
    for index, row in enumerate(rows):
        label = f"clauses[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue

        clause_id = row.get("clause_id")
        if not isinstance(clause_id, str) or not clause_id_re.fullmatch(clause_id):
            lint.fail(path, f"{label}.clause_id must match AK-NC-###")
            continue
        if clause_id in seen:
            lint.fail(path, f"{label}.clause_id duplicates {clause_id}")
        seen.add(clause_id)

        status = row.get("status")
        if status not in allowed_status:
            lint.fail(path, f"{clause_id}.status must be one of {sorted(allowed_status)}")
        category = row.get("category")
        if category not in included_categories:
            lint.fail(path, f"{clause_id}.category {category!r} is outside coverage_scope.included_categories")
        elif status == "active":
            covered_categories.add(category)
        if not isinstance(row.get("requirement"), str) or not row["requirement"].strip():
            lint.fail(path, f"{clause_id}.requirement must be a non-empty string")

        source_anchor = row.get("source_anchor")
        if not isinstance(source_anchor, str) or "#" not in source_anchor:
            lint.fail(path, f"{clause_id}.source_anchor must be <repo-relative markdown path>#<heading slug>")
            continue
        rel, _, anchor = source_anchor.partition("#")
        source_path = Path(rel)
        if source_path.is_absolute() or ".." in source_path.parts:
            lint.fail(path, f"{clause_id}.source_anchor escapes repository: {source_anchor}")
            continue
        resolved = (ROOT / source_path).resolve()
        try:
            resolved.relative_to(ROOT.resolve())
        except ValueError:
            lint.fail(path, f"{clause_id}.source_anchor escapes repository: {source_anchor}")
            continue
        if not resolved.is_file():
            lint.fail(path, f"{clause_id}.source_anchor target does not exist: {rel}")
            continue
        digest = markdown_section_digest(read_text(resolved), anchor)
        if digest is None:
            lint.fail(path, f"{clause_id}.source_anchor heading does not exist: {source_anchor}")
            continue
        if row.get("section_digest") != digest:
            lint.fail(
                path,
                f"{clause_id}.section_digest is stale for {source_anchor}: the normative text changed, so the clause "
                f"and its evidence must be re-reviewed and the digest updated to {digest}",
            )

        grade = row.get("testability_grade")
        if grade not in allowed_grades:
            lint.fail(path, f"{clause_id}.testability_grade must be one of {sorted(allowed_grades)}")
            continue
        if grade == "vector":
            evidence = row.get("evidence_refs")
            if not isinstance(evidence, list) or not evidence:
                lint.fail(path, f"{clause_id}.evidence_refs must be a non-empty array for testability_grade=vector")
                continue
            if "test_plan" in row:
                lint.fail(path, f"{clause_id} must not declare both evidence_refs and test_plan")
            for vector_id in evidence:
                if vector_id not in active_vectors:
                    lint.fail(path, f"{clause_id}.evidence_refs references a non-active vector: {vector_id!r}")
        else:
            if "evidence_refs" in row:
                lint.fail(path, f"{clause_id} must declare test_plan instead of evidence_refs for grade {grade}")
            if not isinstance(row.get("test_plan"), str) or not row["test_plan"].strip():
                lint.fail(path, f"{clause_id}.test_plan must be a non-empty string for testability_grade={grade}")

    missing = included_categories - covered_categories
    if missing:
        lint.fail(path, f"coverage_scope.included_categories has no active clause: {sorted(missing)}")


def check_vector_registry(lint: Lint) -> None:
    path = ARTIFACTS / "registry" / "vector-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    if data.get("source_of_truth") is not True:
        lint.fail(path, "source_of_truth must be true")

    profiles_path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    profiles_data = load_json(lint, profiles_path)
    if not isinstance(profiles_data, dict):
        return
    known_profiles = set(PROFILE_ID_TOKEN_RE.findall(json.dumps(profiles_data, ensure_ascii=False)))
    known_vector_groups = set(profiles_data.get("vector_groups") or [])
    known_fixtures = {fixture.name for fixture in (ARTIFACTS / "fixtures").glob("*.json")}

    rows = data.get("vectors")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "vectors must be a non-empty list")
        return

    registered: dict[str, dict[str, Any]] = {}
    source_vector_ids: dict[Path, set[str]] = {}
    for index, row in enumerate(rows):
        label = f"vectors[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue

        vector_id = row.get("vector_id")
        if not isinstance(vector_id, str) or not VECTOR_ID_TOKEN_RE.fullmatch(vector_id):
            lint.fail(path, f"{label}.vector_id must be a ak.vector.*.vN identifier")
            continue
        if vector_id in registered:
            lint.fail(path, f"{label}.vector_id duplicates {vector_id}")
        registered[vector_id] = row

        if row.get("status") not in {"active", "reserved", "deprecated"}:
            lint.fail(path, f"{label}.status must be active, reserved, or deprecated")

        expected_domain = vector_id.removeprefix("ak.vector.").rsplit(".v", 1)[0].split(".", 1)[0]
        if row.get("domain") != expected_domain:
            lint.fail(path, f"{label}.domain must match vector id domain {expected_domain!r}")

        if "profile" in row:
            lint.fail(path, f"{label}.profile is ambiguous; use one explicit applicability selector")
        selector_keys = [
            key
            for key in ("scope", "applies_to_profiles", "applies_to_vector_groups", "applies_to_fixtures")
            if key in row
        ]
        if len(selector_keys) != 1:
            lint.fail(path, f"{label} must declare exactly one applicability selector")
        elif selector_keys[0] == "scope":
            if row.get("scope") != "universal":
                lint.fail(path, f"{label}.scope must be 'universal'")
        else:
            selector = selector_keys[0]
            values = row.get(selector)
            if not isinstance(values, list) or not values or any(not isinstance(value, str) for value in values):
                lint.fail(path, f"{label}.{selector} must be a non-empty string array")
            elif len(values) != len(set(values)):
                lint.fail(path, f"{label}.{selector} must not contain duplicates")
            elif selector == "applies_to_profiles":
                for profile_id in values:
                    if profile_id not in known_profiles:
                        lint.fail(path, f"{label}.{selector} references unknown profile: {profile_id}")
            elif selector == "applies_to_vector_groups":
                for group_id in values:
                    if group_id not in known_vector_groups:
                        lint.fail(path, f"{label}.{selector} references unknown vector group: {group_id}")
            elif selector == "applies_to_fixtures":
                for fixture in values:
                    if fixture not in known_fixtures:
                        lint.fail(path, f"{label}.{selector} references missing fixture: {fixture}")

        source_refs = row.get("source_refs")
        if not isinstance(source_refs, list) or not source_refs:
            lint.fail(path, f"{label}.source_refs must be a non-empty array")
            continue
        for source_index, source_ref in enumerate(source_refs):
            source_label = f"{label}.source_refs[{source_index}]"
            if not isinstance(source_ref, str) or not source_ref:
                lint.fail(path, f"{source_label} must be a non-empty string")
                continue
            source_path = Path(source_ref)
            if source_path.is_absolute() or ".." in source_path.parts:
                lint.fail(path, f"{source_label} escapes repository: {source_ref}")
                continue
            resolved = (ROOT / source_path).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                lint.fail(path, f"{source_label} escapes repository: {source_ref}")
                continue
            if not resolved.is_file():
                lint.fail(path, f"{source_label} target does not exist: {source_ref}")
                continue
            try:
                referenced_ids = source_vector_ids.get(resolved)
                if referenced_ids is None:
                    referenced_ids = set(VECTOR_ID_TOKEN_RE.findall(read_text(resolved)))
                    source_vector_ids[resolved] = referenced_ids
            except Exception as exc:
                lint.fail(path, f"{source_label} target cannot be read: {source_ref}: {exc}")
                continue
            if vector_id not in referenced_ids:
                lint.fail(path, f"{source_label} does not contain vector_id {vector_id}")

        for fixture in row.get("applies_to_fixtures", []):
            expected_ref = f"spec/v1/artifacts/fixtures/{fixture}"
            if expected_ref not in source_refs:
                lint.fail(path, f"{label}.applies_to_fixtures entry lacks matching source_ref: {fixture}")

    for scan_path in markdown_files() + raw_artifact_files():
        try:
            text = read_text(scan_path.resolve())
        except Exception:
            continue
        for vector_id in sorted(set(VECTOR_ID_TOKEN_RE.findall(text))):
            if vector_id not in registered:
                lint.fail(scan_path, f"references unregistered conformance vector id: {vector_id}")

    indexed_fixtures: set[str] = set()
    for row in registered.values():
        if row.get("status") != "active":
            continue
        indexed_fixtures.update(
            fixture
            for fixture in row.get("applies_to_fixtures", [])
            if isinstance(fixture, str)
        )
        for source_ref in row.get("source_refs", []):
            if not isinstance(source_ref, str):
                continue
            prefix = "spec/v1/artifacts/fixtures/"
            if source_ref.startswith(prefix) and source_ref.endswith(".json"):
                indexed_fixtures.add(source_ref.removeprefix(prefix))

    for fixture_path in sorted((ARTIFACTS / "fixtures").glob("*.json")):
        fixture = load_json(lint, fixture_path)
        if not isinstance(fixture, dict):
            continue
        runner = fixture.get("runner")
        if (
            isinstance(runner, dict)
            and runner.get("kind") == "named_suite"
            and fixture_path.name not in indexed_fixtures
        ):
            lint.fail(
                fixture_path,
                "runner.kind=named_suite fixture must be indexed by an active vector through "
                "applies_to_fixtures[] or source_refs[]",
            )


def check_cryptographic_suite_kat_bindings(lint: Lint) -> None:
    vector_path = ARTIFACTS / "registry" / "vector-registry.json"
    vector_registry = load_json(lint, vector_path)
    if not isinstance(vector_registry, dict):
        return
    active_vectors = {
        row.get("vector_id")
        for row in vector_registry.get("vectors", [])
        if isinstance(row, dict)
        and row.get("status") == "active"
        and isinstance(row.get("vector_id"), str)
    }
    registries = {
        "signature-alg-registry.json": "algorithms",
        "digest-suite-registry.json": "suites",
        "hpke-suite-registry.json": "suites",
        "mls-ciphersuite-registry.json": "ciphersuites",
    }
    for filename, rows_key in registries.items():
        path = ARTIFACTS / "registry" / filename
        data = load_json(lint, path)
        if not isinstance(data, dict):
            continue
        rows = data.get(rows_key)
        if not isinstance(rows, list):
            lint.fail(path, f"{rows_key} must be an array")
            continue
        for index, row in enumerate(rows):
            label = f"{rows_key}[{index}]"
            if not isinstance(row, dict):
                lint.fail(path, f"{label} must be an object")
                continue
            status = row.get("status")
            kat_vector_id = row.get("kat_vector_id")
            absence_reason = row.get("kat_absence_reason")
            if status == "active":
                if not isinstance(kat_vector_id, str) or not kat_vector_id:
                    lint.fail(path, f"{label} status=active requires kat_vector_id")
                elif kat_vector_id not in active_vectors:
                    lint.fail(path, f"{label}.kat_vector_id is not an active vector: {kat_vector_id!r}")
                if absence_reason is not None:
                    lint.fail(path, f"{label} status=active MUST NOT declare kat_absence_reason")
            elif status == "reserved":
                if kat_vector_id is not None:
                    lint.fail(path, f"{label} status=reserved MUST NOT declare kat_vector_id")
                if not isinstance(absence_reason, str) or not absence_reason.strip():
                    lint.fail(path, f"{label} status=reserved requires kat_absence_reason")


def check_account_data_key_registry(lint: Lint, known: dict[str, set[str]]) -> None:
    path = ARTIFACTS / "registry" / "account-data-key-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    if data.get("source_of_truth") is not True:
        lint.fail(path, "source_of_truth must be true")

    rows = data.get("account_data_key_patterns")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "account_data_key_patterns must be a non-empty list")
        return

    seen: set[str] = set()
    allowed_status = {"active", "reserved", "deprecated"}
    allowed_storage = {"encrypted_account_data", "local_only", "encrypted_account_data_or_local"}
    # zh/models/account-data.md §5: the convergence primitive is declared per row,
    # never defaulted, so an implementation can never guess "CAS/LWW".
    allowed_merge_strategies = {"cas_register"}
    allowed_deletion_modes = {"physical_delete", "value_tombstone"}
    for index, row in enumerate(rows):
        label = f"account_data_key_patterns[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue

        key_pattern = row.get("key_pattern")
        if not isinstance(key_pattern, str) or not key_pattern.startswith("ak."):
            lint.fail(path, f"{label}.key_pattern must be a ak.* key pattern")
            continue
        if key_pattern in seen:
            lint.fail(path, f"{label}.key_pattern duplicates {key_pattern}")
        seen.add(key_pattern)

        if row.get("status") not in allowed_status:
            lint.fail(path, f"{label}.status must be one of {sorted(allowed_status)}")
        if row.get("storage") not in allowed_storage:
            lint.fail(path, f"{label}.storage must be one of {sorted(allowed_storage)}")
        if row.get("merge_strategy") not in allowed_merge_strategies:
            lint.fail(path, f"{label}.merge_strategy must be one of {sorted(allowed_merge_strategies)}")
        if row.get("deletion_mode") not in allowed_deletion_modes:
            lint.fail(path, f"{label}.deletion_mode must be one of {sorted(allowed_deletion_modes)}")
        if not isinstance(row.get("scope"), str) or not row["scope"]:
            lint.fail(path, f"{label}.scope must be a non-empty string")
        if not isinstance(row.get("description"), str) or not row["description"].strip():
            lint.fail(path, f"{label}.description must be a non-empty string")

        write_event_kinds = row.get("write_event_kinds")
        if not isinstance(write_event_kinds, list) or not write_event_kinds:
            lint.fail(path, f"{label}.write_event_kinds must be a non-empty array")
        else:
            for event_kind in write_event_kinds:
                if not isinstance(event_kind, str) or event_kind not in known["event_kinds"]:
                    lint.fail(path, f"{label}.write_event_kinds contains unknown Event.kind: {event_kind!r}")

        source_refs = row.get("source_refs")
        if not isinstance(source_refs, list) or not source_refs:
            lint.fail(path, f"{label}.source_refs must be a non-empty array")
            continue

        mentions_key = False
        for source_index, source_ref in enumerate(source_refs):
            source_label = f"{label}.source_refs[{source_index}]"
            if not isinstance(source_ref, str) or not source_ref:
                lint.fail(path, f"{source_label} must be a non-empty string")
                continue
            source_path = Path(source_ref)
            if source_path.is_absolute() or ".." in source_path.parts:
                lint.fail(path, f"{source_label} escapes repository: {source_ref}")
                continue
            resolved = (ROOT / source_path).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                lint.fail(path, f"{source_label} escapes repository: {source_ref}")
                continue
            if not resolved.is_file():
                lint.fail(path, f"{source_label} target does not exist: {source_ref}")
                continue
            try:
                source_text = resolved.read_text(encoding="utf-8")
            except Exception as exc:
                lint.fail(path, f"{source_label} target cannot be read: {source_ref}: {exc}")
                continue
            if key_pattern in source_text:
                mentions_key = True
        if not mentions_key:
            lint.fail(path, f"{label}.source_refs must include at least one source that mentions {key_pattern}")


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


def check_security_closure_fixture(lint: Lint) -> None:
    path = ARTIFACTS / "fixtures" / "security-closure-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    vectors = data.get("security_closure_fixture")
    if not isinstance(vectors, list) or not vectors:
        lint.fail(path, "security_closure_fixture must be a non-empty array")
        return

    conformance_path = SPEC_ROOT / "zh" / "conformance" / "conformance-vectors.md"
    try:
        defined_vectors = set(VECTOR_ID_TOKEN_RE.findall(conformance_path.read_text(encoding="utf-8")))
    except Exception as exc:
        lint.fail(conformance_path, f"could not read conformance vector definitions: {exc}")
        defined_vectors = set()

    seen: set[str] = set()
    for index, vector in enumerate(vectors):
        label = f"security_closure_fixture[{index}]"
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
            lint.fail(path, f"{json_path} has invalid ak:blob:sha256 reference")
        return
    if token_kind in known["id_kinds"]:
        candidate = rest[:36]
        # zh/conformance/encoding.md section 4: the UUID construction is fixed per
        # kind by id-kind-registry id_form. event_derived kinds carry the UUIDv8
        # content-bound layout of section 4.0; everything else stays UUIDv7.
        if token_kind == "realm":
            # zh/models/realm-and-space.md section 2.5.0: `ak:realm:` is the one
            # kind with two content-bound forms — collaboration Realms are
            # event-derived (v8), Principal Control Realms are subject-derived
            # from the principal DID (v7 layout) so they stay computable from
            # the DID alone. Neither is producer-chosen.
            if not (UUID8_RE.fullmatch(candidate) or UUID7_RE.fullmatch(candidate)):
                lint.fail(
                    path,
                    f"{json_path} has invalid ak:realm: expected a content-bound typed uuid",
                )
        elif token_kind in known.get("event_derived_id_kinds", set()):
            if not UUID8_RE.fullmatch(candidate):
                lint.fail(
                    path,
                    f"{json_path} has invalid ak:{token_kind}: expected content-bound typed UUIDv8",
                )
        elif not UUID7_RE.fullmatch(candidate):
            lint.fail(path, f"{json_path} has invalid ak:{token_kind}: typed UUIDv7 reference")
        return
    if token_kind in known["special_id_kinds"]:
        if not rest:
            lint.fail(path, f"{json_path} has empty ak:{token_kind}: special reference")
        return
    lint.fail(path, f"{json_path} references unregistered typed ID kind: ak:{token_kind}:")


def check_fixtures(lint: Lint, known: dict[str, set[str]]) -> None:
    fixture_dir = ARTIFACTS / "fixtures"
    for path in sorted(fixture_dir.glob("*.json")):
        data = load_json(lint, path)
        if data is None:
            continue
        check_fixture_schema_validation_cases(lint, path, data)
        check_event_envelope_candidates(lint, path, data, known["event_kinds"])
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

            if key == "event_kind" and value.startswith("ak.") and value not in known["event_kinds"]:
                lint.fail(path, f"{json_path} references unregistered Event.kind: {value}")
            if key in {"operation_id", "mapped_operation_id"} and value.startswith("ak."):
                if value not in known["operation_ids"]:
                    lint.fail(path, f"{json_path} references unregistered operation_id: {value}")
            if key == "call" and ".recovery.call" in json_path and value.startswith("ak."):
                if value not in known["operation_ids"]:
                    lint.fail(path, f"{json_path} references unregistered recovery operation_id: {value}")
            if key == "constraint_kind" and value not in known["constraint_types"]:
                lint.fail(path, f"{json_path} uses invalid constraint_kind: {value}")

            for match in TYPED_ID_TOKEN_RE.finditer(value):
                check_typed_id_token(lint, path, json_path, match.group(1), match.group(2), known)


def check_snapshot_merkle_fixture(lint: Lint) -> None:
    """Execute the snapshot RFC 6962 root KAT, including actor subranges."""

    path = ARTIFACTS / "fixtures" / "sync-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return
    challenge = data.get("snapshot_inclusion_challenge")
    if not isinstance(challenge, dict):
        lint.fail(path, "snapshot_inclusion_challenge must be an object")
        return
    entries = challenge.get("event_set_entries")
    manifest = challenge.get("manifest")
    response = challenge.get("base_response")
    if not isinstance(entries, list) or not isinstance(manifest, dict) or not isinstance(response, dict):
        lint.fail(path, "snapshot Merkle KAT is missing entries, manifest, or response")
        return

    def leaf_data(entry: Any) -> bytes:
        return hashlib.sha256(canonical_json(entry).encode("utf-8")).digest()

    def merkle_root(raw_leaf_data: list[bytes]) -> str:
        if not raw_leaf_data:
            root = hashlib.sha256(b"").digest()
        else:
            level = [hashlib.sha256(b"\x00" + value).digest() for value in raw_leaf_data]
            while len(level) > 1:
                next_level: list[bytes] = []
                for offset in range(0, len(level), 2):
                    if offset + 1 == len(level):
                        next_level.append(level[offset])
                    else:
                        next_level.append(
                            hashlib.sha256(b"\x01" + level[offset] + level[offset + 1]).digest()
                        )
                level = next_level
            root = level[0]
        return "sha256:" + root.hex()

    try:
        ordered = sorted(
            entries,
            key=lambda row: (
                row["actor_id"].encode("utf-8"),
                row["actor_seq"],
                row["event_id"].encode("utf-8"),
            ),
        )
        computed = merkle_root([leaf_data(row) for row in ordered])
        commitment = manifest["event_set_commitment"]
        declared = commitment["root"]
    except (KeyError, TypeError) as exc:
        lint.fail(path, f"snapshot Merkle KAT has malformed input: {exc}")
        return

    if declared != computed:
        lint.fail(path, f"snapshot manifest RFC 6962 root {declared} != computed {computed}")
    if response.get("commitment_root") != computed:
        lint.fail(path, "snapshot inclusion response root does not match computed manifest root")

    ranges = commitment.get("actor_seq_ranges")
    if not isinstance(ranges, list):
        lint.fail(path, "snapshot Merkle KAT actor_seq_ranges must be an array")
        return
    for row in ranges:
        if not isinstance(row, dict):
            lint.fail(path, "snapshot Merkle actor_seq_range must be an object")
            continue
        try:
            selected = [
                entry
                for entry in ordered
                if entry["actor_id"] == row["actor_id"]
                and row["from_seq"] <= entry["actor_seq"] <= row["to_seq"]
            ]
            range_root = merkle_root([leaf_data(entry) for entry in selected])
        except (KeyError, TypeError) as exc:
            lint.fail(path, f"snapshot Merkle actor_seq_range is malformed: {exc}")
            continue
        if row.get("root") != range_root:
            lint.fail(
                path,
                f"snapshot actor range {row.get('actor_id')} root {row.get('root')} "
                f"!= computed {range_root}",
            )

    legacy_case = next(
        (
            row
            for row in challenge.get("cases", [])
            if isinstance(row, dict) and row.get("name") == "legacy_unprefixed_commitment_root"
        ),
        None,
    )
    if (
        not isinstance(legacy_case, dict)
        or legacy_case.get("replacement_root") == computed
        or legacy_case.get("expected", {}).get("decision") != "reject"
    ):
        lint.fail(path, "snapshot Merkle KAT must reject a distinct legacy unprefixed root")


def check_canonical_digest_alias(lint: Lint) -> None:
    """Keep one exact name for the Event digest preimage across prose and artifacts."""

    forbidden = "envelope_without_proofs_unsigned_reducer_stamps"
    for path in sorted({*markdown_files(), *raw_artifact_files()}):
        if forbidden in read_text(path):
            lint.fail(
                path,
                f"forbidden Event digest preimage alias `{forbidden}`; "
                "use `envelope_without_proofs_unsigned_actor_kind`",
            )


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
        first_expected_error = case.get("first_expected_error")
        if expect_valid:
            if first_expected_error is not None:
                lint.fail(path, f"{label}.first_expected_error is only valid when expect_valid=false")
                continue
        elif not isinstance(first_expected_error, str) or not first_expected_error:
            lint.fail(path, f"{label}.first_expected_error must be a non-empty string when expect_valid=false")
            continue
        case_name = case.get("name")
        if not isinstance(case_name, str) or not case_name:
            case_name = label
        check_json_instance_against_schema(
            lint,
            path,
            case_name,
            schema_ref,
            instance,
            expect_valid,
            first_expected_error,
        )


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
            # zh/conformance/encoding.md section 6: the digest preimage removes
            # proofs, unsigned, actor_kind and event_id. event_id is excluded
            # because section 4.0 derives it from this very digest.
            signed_event.pop("unsigned", None)
            signed_event.pop("actor_kind", None)
            signed_event.pop("event_id", None)
            expected_canonical = canonical_json(signed_event)
            if vector.get("canonical_event_payload") != expected_canonical:
                lint.fail(path, f"vectors[{index}] canonical_event_payload does not match canonical JSON")
            expected_event_digest = sha256_text(expected_canonical)
            if vector.get("event_digest") != expected_event_digest:
                lint.fail(path, f"vectors[{index}] event_digest does not match canonical_event_payload")

            event_with_proof = vector.get("event_with_proof")
            if isinstance(event_with_proof, dict):
                unsigned = dict(event_with_proof)
                unsigned.pop("proofs", None)
                unsigned.pop("unsigned", None)
                unsigned.pop("actor_kind", None)
                unsigned.pop("event_id", None)
                if unsigned != signed_event:
                    lint.fail(path, f"vectors[{index}] event_with_proof without proofs differs from event_without_proofs")

        binding = vector.get("binding_object")
        if isinstance(binding, dict):
            expected_binding = canonical_json(binding)
            if vector.get("canonical_binding_payload") != expected_binding:
                lint.fail(path, f"vectors[{index}] canonical_binding_payload does not match canonical JSON")
            expected_binding_digest = sha256_text(expected_binding)
            if vector.get("binding_digest") != expected_binding_digest:
                lint.fail(path, f"vectors[{index}] binding_digest does not match canonical_binding_payload")
            if vector.get("detached_payload_b64u") != base64url_text(expected_binding):
                lint.fail(path, f"vectors[{index}] detached_payload_b64u does not match canonical_binding_payload")

        protected_header = vector.get("protected_header")
        if isinstance(protected_header, dict):
            expected_header = canonical_json(protected_header)
            if vector.get("protected_header_canonical") != expected_header:
                lint.fail(path, f"vectors[{index}] protected_header_canonical does not match canonical JSON")

        proof = vector.get("proof")
        if isinstance(proof, dict) and isinstance(vector.get("event_digest"), str):
            if proof.get("event_digest") != vector["event_digest"]:
                lint.fail(path, f"vectors[{index}] proof event_digest differs from vector event_digest")

    negative_cases = data.get("negative_cases")
    if not isinstance(negative_cases, list) or not negative_cases:
        lint.fail(path, "negative_cases must be a non-empty list")
        return
    positive_names = {vector.get("name") for vector in vectors if isinstance(vector, dict)}
    negative_bases = {
        case.get("base_vector")
        for case in negative_cases
        if isinstance(case, dict) and isinstance(case.get("base_vector"), str)
    }
    missing_algorithm_negatives = positive_names - negative_bases
    if missing_algorithm_negatives:
        lint.fail(path, f"each active signature vector needs an algorithm-specific negative case: {sorted(missing_algorithm_negatives)}")


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

        if key == "event_kind" and value.startswith("ak.") and value not in known["event_kinds"]:
            lint.fail(path, f"{json_path} markdown JSON references unregistered Event.kind: {value}")

        if key in {"operation_id", "mapped_operation_id", "operationId"} and value.startswith("ak."):
            if value not in known["operation_ids"]:
                lint.fail(path, f"{json_path} markdown JSON references unregistered operation_id: {value}")

        if key == "constraint_kind" and value not in known["constraint_types"]:
            lint.fail(path, f"{json_path} markdown JSON uses invalid constraint_kind: {value}")

        for match in TYPED_ID_TOKEN_RE.finditer(value):
            kind, rest = match.group(1), match.group(2)
            if is_placeholder_typed_id(rest):
                if kind not in known["id_kinds"] and kind not in known["special_id_kinds"]:
                    lint.fail(path, f"{json_path} markdown JSON references unregistered typed ID kind: ak:{kind}:")
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


def expect_valid_from_fence_meta(meta: str) -> bool:
    match = JSON_FENCE_EXPECT_ATTR_RE.search(meta)
    return False if match and match.group(1) == "invalid" else True


def first_expected_error_from_fence_meta(meta: str) -> str | None:
    match = JSON_FENCE_FIRST_ERROR_ATTR_RE.search(meta)
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


@lru_cache(maxsize=None)
def load_json_schema_for_uri(uri: str) -> Any:
    # Canonical schema $id base: https://arkret.org/v1/schemas/<name>.schema.json
    # (the /v1/ segment pins the current spec generation so other generations get distinct
    # $ids). All schemas live on disk under ARTIFACTS/schemas/, so strip the
    # base and resolve the remaining filename there.
    prefix = "https://arkret.org/v1/schemas/"
    if not uri.startswith(prefix):
        raise ValueError(f"unsupported remote schema URI {uri}")
    path = ARTIFACTS / "schemas" / uri[len(prefix):]
    return parse_json_file(path.resolve())


def load_schema_document(lint: Lint, path: Path) -> Any:
    if path.suffix.lower() in {".yaml", ".yml"}:
        return load_yaml(lint, path)
    return load_json(lint, path)


@lru_cache(maxsize=1)
def schema_format_checker() -> Any:
    if FormatChecker is None:
        return None
    format_checker = FormatChecker()

    @format_checker.checks("date-time", raises=(TypeError, ValueError))
    def strict_rfc3339_date_time(value: object) -> bool:
        if not isinstance(value, str):
            return True
        if not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
            r"(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})",
            value,
        ):
            return False
        datetime.fromisoformat(value.removesuffix("Z") + ("+00:00" if value.endswith("Z") else ""))
        return True

    return format_checker


def schema_validator(schema_path: Path, fragment: str) -> Any:
    schema_document = (
        parse_yaml_file(schema_path)
        if schema_path.suffix.lower() in {".yaml", ".yml"}
        else parse_json_file(schema_path)
    )
    schema = resolve_json_pointer(schema_document, fragment)
    if not isinstance(schema, dict):
        raise TypeError("schema_ref fragment is not an object schema")
    root_id = schema_document.get("$id") if isinstance(schema_document, dict) else None
    if (
        schema_path.suffix.lower() == ".json"
        and isinstance(root_id, str)
        and Registry is not None
        and Resource is not None
    ):
        def retrieve_schema(uri: str) -> Any:
            return Resource.from_contents(load_json_schema_for_uri(uri))

        registry = Registry(retrieve=retrieve_schema).with_resource(
            root_id,
            Resource.from_contents(schema_document),
        )
        target = root_id + (fragment if fragment.startswith("#") else fragment)
        wrapper = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": target,
        }
        return Draft202012Validator(
            wrapper,
            registry=registry,
            format_checker=schema_format_checker(),
        )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        resolver = RefResolver(
            base_uri=schema_path.as_uri(),
            referrer=schema_document,
            handlers={"https": load_json_schema_for_uri},
        )
        return Draft202012Validator(
            schema,
            resolver=resolver,
            format_checker=schema_format_checker(),
        )


def jsonschema_errors(lint: Lint, owner: Path, schema_ref: str, instance: Any) -> list[str]:
    if Draft202012Validator is None or RefResolver is None:
        lint.fail(owner, "jsonschema is required for declared schema validation; install jsonschema")
        return []
    schema_path = resolve_artifact_schema_ref(lint, owner, schema_ref)
    if schema_path is None:
        return []
    fragment = "#" + schema_ref.split("#", 1)[1] if "#" in schema_ref else "#"
    try:
        validator = schema_validator(schema_path.resolve(), fragment)
    except Exception as exc:
        lint.fail(owner, f"schema_ref fragment cannot be resolved: {schema_ref}: {exc}")
        return []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        try:
            errors = sorted(
                validator.iter_errors(instance),
                key=lambda error: list(error.path),
            )
        except Exception as exc:
            lint.fail(owner, f"schema validation could not resolve {schema_ref}: {exc}")
            return []
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
    first_expected_error: str | None = None,
) -> None:
    errors = jsonschema_errors(lint, owner, schema_ref, instance)
    if expect_valid and errors:
        lint.fail(owner, f"{label} fails {schema_ref}: " + "; ".join(errors[:3]))
    if not expect_valid and not errors:
        lint.fail(owner, f"{label} expected to fail {schema_ref} but validated successfully")
    if not expect_valid and first_expected_error and errors:
        if first_expected_error.startswith("contains:"):
            expected_fragment = first_expected_error.removeprefix("contains:")
            matches = expected_fragment in errors[0]
        else:
            matches = errors[0] == first_expected_error
        if not matches:
            lint.fail(
                owner,
                f"{label} first schema error drift for {schema_ref}: got {errors[0]!r}, "
                f"expected {first_expected_error!r}",
            )


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

    if schema_ref != "schemas/event-envelope.schema.json":
        return

    proofs = data.get("proofs")
    if not isinstance(proofs, list) or not proofs:
        lint.fail(path, f"json_block[{block_index}] proof-bearing object must include non-empty proofs[]")
        return

    proof_required: list[str] = []
    event_schema = load_json(lint, ARTIFACTS / "schemas/event-envelope.schema.json")
    if isinstance(event_schema, dict):
        proof_def_name = "event_proof" if schema_ref == "schemas/event-envelope.schema.json" else "proof"
        proof_schema = event_schema.get("$defs", {}).get(proof_def_name, {})
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

        if "ak.moderation.policy_action" in text:
            lint.fail(path, "markdown references removed Event.kind ak.moderation.policy_action; use ak.policy.action")

        for schema_id in SCHEMA_ID_TOKEN_RE.findall(text):
            if schema_id not in known["schema_ids"]:
                lint.fail(path, f"markdown references unknown schema id: {schema_id}")
        for profile_id in PROFILE_ID_TOKEN_RE.findall(text):
            if profile_id not in known["profiles"]:
                lint.fail(path, f"markdown references unknown profile: {profile_id}")

        for prefix_match in TYPED_ID_PREFIX_TOKEN_RE.finditer(text):
            kind = prefix_match.group(1)
            if kind not in known["id_kinds"] and kind not in known["special_id_kinds"]:
                lint.fail(path, f"markdown references unregistered typed ID kind: ak:{kind}:")

        for match in TYPED_ID_TOKEN_RE.finditer(text):
            kind, rest = match.group(1), match.group(2)
            if is_placeholder_typed_id(rest):
                continue
            check_typed_id_token(lint, path, "markdown", kind, rest, known)

        for block_index, match in enumerate(JSON_FENCE_RE.finditer(text), start=1):
            block = match.group("body")
            meta = match.group("meta")
            schema_ref = schema_ref_from_fence_meta(meta)
            try:
                data = parse_json_text(block)
            except Exception as exc:
                lint.fail(path, f"json_block[{block_index}] invalid canonical JSON: {exc}")
                continue
            example_negative = False
            if schema_ref:
                expect_valid = expect_valid_from_fence_meta(meta)
                example_negative = not expect_valid
                first_expected_error = first_expected_error_from_fence_meta(meta)
                if expect_valid and first_expected_error is not None:
                    lint.fail(path, f"json_block[{block_index}] first_error is only valid with expect=invalid")
                if not expect_valid and not first_expected_error:
                    lint.fail(path, f"json_block[{block_index}] expect=invalid requires first_error metadata")
                check_json_instance_against_schema(
                    lint,
                    path,
                    f"json_block[{block_index}] declared schema example",
                    schema_ref,
                    data,
                    expect_valid,
                    first_expected_error,
                )
            check_markdown_full_object_example(lint, path, block_index, data)
            check_event_ref_invariants_in_value(lint, path, f"json_block[{block_index}]", data)
            check_event_envelope_candidates(
                lint,
                path,
                data,
                known["event_kinds"],
                label=f"json_block[{block_index}]",
                negative_context=example_negative,
            )
            for json_path, value, key in walk_json(data):
                check_markdown_json_value(lint, path, f"json_block[{block_index}]{json_path[1:]}", value, key, known)

def check_release_readiness_counts(lint: Lint, known: dict[str, set[str]]) -> None:
    """T4-2: schema↔doc count guard.

    Re-parses release-readiness.md's count table and verifies each number
    matches the canonical registry. Prevents the release baseline table from
    disagreeing with the machine-readable contract.
    """
    path = SPEC_ROOT / "zh" / "overview" / "release-readiness.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")

    profile_data = load_json(lint, ARTIFACTS / "profiles" / "conformance-profiles.json") or {}
    profile_requirements_count = len(profile_data.get("profile_requirements", []))
    profile_sets = profile_data.get("profile_sets", {})
    profile_tiers_count = (
        sum(1 for value in profile_sets.values() if isinstance(value, list))
        if isinstance(profile_sets, dict)
        else 0
    )

    expected: dict[str, int] = {
        "Event kind（active）": len(known["active_event_kinds"]),
        "Schema": len(known["schema_ids"]),
        "Typed ID kind": len(known["id_kinds"]),
        "Service operation": len(known["operation_ids"]),
        "Claimable conformance profile": len(known["claimable_profiles"]),
        "Profile id references": len(known["profiles"]),
        "profile_requirements": profile_requirements_count,
        "profile_sets": profile_tiers_count,
    }

    # Match table rows like "| Event kind（active） | 152 | `...` |"
    table_re = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|", re.MULTILINE)
    found: dict[str, int] = {}
    for match in table_re.finditer(text):
        label = match.group(1).strip()
        if label in expected:
            found[label] = int(match.group(2))

    for label, want in expected.items():
        if label in {"profile_requirements", "profile_sets"}:
            inline_patterns = [
                rf"(\d+)\s*(?:个|组|block|blocks)?\s*`{label}`",
                rf"`{label}`\s*(?:block|blocks|分组)?\s*[（(](\d+)[）)]",
            ]
            inline_counts: list[int] = []
            for pattern in inline_patterns:
                inline_counts.extend(int(match.group(1)) for match in re.finditer(pattern, text))
            if not inline_counts:
                lint.fail(path, f"missing prose count for `{label}`")
            for have in inline_counts:
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

    # Look for canonical normative usage forms:
    #   reason_code="..." / reason="..." / reason=`...`
    #   reason == "..."
    #   `error_code=...`
    #   返回 `...` / reject `...` / audit log records reason_code such as `...`
    # We still avoid scanning every freeform backtick token because prose also
    # quotes ordinary schema fields and enum values.
    #
    # Patterns covered (single + double quotes + backticks):
    patterns = [
        re.compile(r'reason_code\s*[=:]\s*["`]([a-z_][a-z0-9_]+)["`]'),
        re.compile(r'reason\s*[=:]\s*["`]([a-z_][a-z0-9_]+)["`]'),
        re.compile(r'reason\s*==\s*["`]([a-z_][a-z0-9_]+)["`]'),
        re.compile(r'error_code\s*[=:]\s*["`]([a-z_][a-z0-9_]+)["`]'),
        re.compile(r'`reason\s*=\s*["\']?([a-z_][a-z0-9_]+)["\']?`'),
        re.compile(r'reason_code[^`\n]*(?:如|such as)\s+`([a-z_][a-z0-9_]+)`', re.IGNORECASE),
    ]
    code_like_re = re.compile(
        r"(_invalid|_mismatch|_required|_forbidden|_denied|_expired|_stale|"
        r"_conflict|_unavailable|_missing|_not_allowed|_too_stale|"
        r"_rate_limited|_failed|_violation|_rejected|_redacted|"
        r"_unknown|_incomplete)$"
    )
    non_error_code_tokens = {
        "child_privacy_tightening_against_required",
        "on_conflict",
        # Sync stream frame.kind tokens, not reason codes. Their endpoint-layer
        # error codes are stream_dropped / stream_resync_required (client-sync.md
        # §5, service-http-binding.md §1015); the bare frame.kind ends in
        # _required and would otherwise trip the code-shape heuristic.
        "resync_required",
    }

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
        for line in text.splitlines():
            reason_examples = re.search(r"reason_code[^`\n]*(?:如|例如|such as)(?P<tail>.*)$", line, re.IGNORECASE)
            if reason_examples:
                candidate_text = reason_examples.group("tail")
                require_code_shape = False
            elif re.search(r"(返回|return|reject|拒绝)", line, re.IGNORECASE):
                candidate_text = line
                require_code_shape = True
            else:
                continue
            for code in re.findall(r"`([a-z_][a-z0-9_]+)`", candidate_text):
                if code in non_error_code_tokens:
                    continue
                if require_code_shape and not code_like_re.search(code):
                    continue
                if code in known_codes:
                    continue
                if code in {"true", "false", "null", "ok", "yes", "no", "n_a"}:
                    continue
                unresolved.add(code)
        for code in sorted(unresolved):
            lint.fail(path, f"reason_code referenced but not in error-code-registry.json: {code!r}")

    json_reason_keys = {"reason_code", "reject_reason", "expected_audit_reason"}
    for path in [ARTIFACTS / "profiles" / "conformance-profiles.json"]:
        data = load_json(lint, path)
        if data is None:
            continue
        unresolved: set[str] = set()
        for _, value, key in walk_json(data):
            if key in json_reason_keys and isinstance(value, str):
                if value not in known_codes:
                    unresolved.add(value)
        for code in sorted(unresolved):
            lint.fail(path, f"reason_code referenced but not in error-code-registry.json: {code!r}")


def check_error_code_registry_uniqueness(lint: Lint) -> None:
    """Reject duplicates and asymmetric explicit dual-registration metadata.

    Top-level ``codes`` and item-level ``reason_codes`` may intentionally reuse
    a string under the dual-registration model, but a duplicate inside the same
    section has no stable first/last-wins semantics for SDK generation or
    catalog UI. If either side explicitly labels a row dual-registered, the
    matching row and reciprocal label are required on the other side.
    """
    path = ARTIFACTS / "registry" / "error-code-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    rows_by_section: dict[str, dict[str, dict[str, Any]]] = {}
    for section in ("codes", "reason_codes"):
        rows = data.get(section, [])
        if not isinstance(rows, list):
            lint.fail(path, f"{section} must be a list")
            continue
        seen: dict[str, int] = {}
        rows_by_section[section] = {}
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                lint.fail(path, f"{section}[{index}] must be an object")
                continue
            code = row.get("code")
            if not isinstance(code, str) or not code:
                lint.fail(path, f"{section}[{index}] missing non-empty code")
                continue
            previous = seen.get(code)
            if previous is not None:
                lint.fail(
                    path,
                    f"duplicate error code {code!r} inside {section} at rows {previous} and {index}",
                )
            seen[code] = index
            rows_by_section[section][code] = row

    top_level_rows = rows_by_section.get("codes", {})
    reason_rows = rows_by_section.get("reason_codes", {})
    for code in sorted(set(top_level_rows) | set(reason_rows)):
        top_description = top_level_rows.get(code, {}).get("description", "")
        reason_description = reason_rows.get(code, {}).get("description", "")
        top_declares_dual = isinstance(top_description, str) and "dual-registered" in top_description.lower()
        reason_declares_dual = (
            isinstance(reason_description, str) and "dual-registered" in reason_description.lower()
        )
        if top_declares_dual != reason_declares_dual:
            missing_side = "reason_codes" if top_declares_dual else "codes"
            lint.fail(path, f"{code!r} dual-registration description missing reciprocal label in {missing_side}")


def check_operations_error_mapping_closure(lint: Lint) -> None:
    """Every operations-error-mapping code must be in the error registry."""
    registry_path = ARTIFACTS / "registry" / "error-code-registry.json"
    mapping_path = ARTIFACTS / "registry" / "operations-error-mapping.json"
    registry = load_json(lint, registry_path)
    mapping = load_json(lint, mapping_path)
    if not isinstance(registry, dict) or not isinstance(mapping, dict):
        return

    known_codes = {
        row.get("code")
        for section in ("codes", "reason_codes")
        for row in registry.get(section, [])
        if isinstance(row, dict) and isinstance(row.get("code"), str)
    }
    unresolved: set[str] = set()

    rules = mapping.get("rules")
    if isinstance(rules, dict):
        universal = rules.get("universal_codes")
        if isinstance(universal, str):
            match = re.search(r"any of:\s*(?P<codes>.*?)(?:\.|$)", universal)
            code_text = match.group("codes") if match else universal
            for raw_code in code_text.split(","):
                code = raw_code.strip().strip(".")
                if not re.fullmatch(r"[a-z][a-z0-9_]+", code):
                    continue
                if code not in known_codes:
                    unresolved.add(code)

    operations = mapping.get("operations")
    if isinstance(operations, list):
        for index, row in enumerate(operations):
            if not isinstance(row, dict):
                lint.fail(mapping_path, f"operations[{index}] must be an object")
                continue
            for code in row.get("operation_specific", []):
                if not isinstance(code, str):
                    lint.fail(mapping_path, f"operations[{index}].operation_specific contains non-string code")
                    continue
                if code not in known_codes:
                    unresolved.add(code)

    for code in sorted(unresolved):
        lint.fail(mapping_path, f"error code referenced but not in error-code-registry.json: {code!r}")

    # Coverage invariant (rules.operation_coverage): every operation_id in
    # operation-registry.json MUST appear in operations[] exactly once, and
    # operations[] MUST NOT reference an operation_id absent from the registry.
    op_registry_path = ARTIFACTS / "registry" / "operation-registry.json"
    op_registry = load_json(lint, op_registry_path)
    if isinstance(op_registry, dict) and isinstance(operations, list):
        registry_ids = {
            row.get("operation_id")
            for row in op_registry.get("operations", [])
            if isinstance(row, dict) and isinstance(row.get("operation_id"), str)
        }
        mapping_counts: dict[str, int] = {}
        for row in operations:
            if isinstance(row, dict) and isinstance(row.get("operation_id"), str):
                op_id = row["operation_id"]
                mapping_counts[op_id] = mapping_counts.get(op_id, 0) + 1
        for op_id in sorted(registry_ids):
            count = mapping_counts.get(op_id, 0)
            if count == 0:
                lint.fail(mapping_path, f"operation_id in operation-registry.json missing from operations[]: {op_id!r}")
            elif count > 1:
                lint.fail(mapping_path, f"operation_id appears {count} times in operations[] (must be exactly once): {op_id!r}")
        for op_id in sorted(mapping_counts):
            if op_id not in registry_ids:
                lint.fail(mapping_path, f"operations[] references operation_id absent from operation-registry.json: {op_id!r}")


FIXTURE_REJECT_DECISION_KEYS = ("decision", "result", "seal_result", "event_state")
_REJECT_REASON_CODE_RE = re.compile(r"^[a-z][a-z0-9_]+$")


def check_fixture_reject_reason_closure(lint: Lint) -> None:
    """Fixture reject `reason` codes must resolve in error-code-registry.json.

    Only enumerable reason_code-style values (snake_case identifiers) sitting in
    a reject / deny decision context (or a rollback object) are gated; free-text
    `reason` prose is ignored per the models/common-fields.md reason vs
    reason_code convention.
    """
    registry_path = ARTIFACTS / "registry" / "error-code-registry.json"
    registry = load_json(lint, registry_path)
    if not isinstance(registry, dict):
        return
    known_codes = {
        row.get("code")
        for section in ("codes", "reason_codes")
        for row in registry.get(section, [])
        if isinstance(row, dict) and isinstance(row.get("code"), str)
    }

    def is_reject(value: Any) -> bool:
        return isinstance(value, str) and ("reject" in value or value == "deny")

    def walk(node: Any, parent_key: str | None, json_path: str, path: Path) -> None:
        if isinstance(node, dict):
            reason = node.get("reason")
            if isinstance(reason, str) and _REJECT_REASON_CODE_RE.fullmatch(reason):
                reject_ctx = parent_key == "rollback" or any(
                    is_reject(node.get(key)) for key in FIXTURE_REJECT_DECISION_KEYS
                )
                if reject_ctx and reason not in known_codes:
                    lint.fail(
                        path,
                        f"{json_path}.reason reject code not in error-code-registry.json: {reason!r}",
                    )
            for key, value in node.items():
                walk(value, key, f"{json_path}/{key}", path)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, parent_key, f"{json_path}[{index}]", path)

    for path in sorted((ARTIFACTS / "fixtures").glob("**/*.json")):
        data = load_json(lint, path)
        if data is not None:
            walk(data, None, "$", path)


def check_cross_doc_anchors(lint: Lint) -> None:
    """T4-4: cross-doc anchor check.

    Every markdown link `(./foo.md#anchor)` must resolve to a real header in
    foo.md, slugified the same way GitHub-flavored renderers do. Prevents
    silent rot when sections are renamed.
    """
    # Build slug index for every markdown file.
    slug_re = HEADING_RE
    slugify = markdown_heading_slug

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
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
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
      { "envelope": <obj>, "event_digest": "sha256:..." }
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
        ("envelope", "event_digest"),
        ("envelope", "payload_hash"),
        ("canonical_input", "expected_digest"),
    ]

    def iter_dict_nodes(value: Any) -> Iterable[dict[str, Any]]:
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from iter_dict_nodes(child)
        elif isinstance(value, list):
            for child in value:
                yield from iter_dict_nodes(child)

    for fixture_path in fixtures_dir.rglob("*.json"):
        data = load_json(lint, fixture_path)
        if data is None:
            continue

        for case in iter_dict_nodes(data):
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
                expected_canonical = case.get("expected_canonical_bytes_utf8")
                if isinstance(expected_canonical, str) and expected_canonical != canonical:
                    lint.fail(
                        fixture_path,
                        f"canonical bytes mismatch: {input_key!r} produces {canonical!r} "
                        f"but expected_canonical_bytes_utf8={expected_canonical!r}",
                    )
                recomputed = sha256_text(canonical)
                if recomputed != expected:
                    lint.fail(
                        fixture_path,
                        f"digest mismatch: {input_key!r} canonical bytes produce "
                        f"{recomputed} but {digest_key!r}={expected}",
    )


# --- stated preimage <-> stated digest ---------------------------------------
#
# `(preimage key, digest key, how the preimage is encoded, how the digest is
# written, domain-separator prefix)`. One row per fixture family that spells out
# both halves of a hash beside each other.
#
# The prefix is part of the check on purpose: for the Applet registration epoch
# the digest is only reachable through `arkret-applet-registration-epoch-v1\n`,
# so pinning the pair pins the domain separator too.
STATED_PREIMAGE_DIGEST_PAIRS: tuple[tuple[str, str, str, str, str], ...] = (
    ("expected_canonical_bytes_utf8", "expected_subject", "utf8", "base64url", ""),
    ("expected_canonical_bytes_utf8", "expected_digest", "utf8", "sha256_hex", ""),
    ("tag_preimage_utf8", "batch_tag", "utf8", "base64url", ""),
    ("scope_preimage_utf8", "scope_set_component", "utf8", "base64url", ""),
    ("canonical_event_payload", "event_digest", "utf8", "sha256_hex", ""),
    ("digest_preimage_canonical_bytes_utf8", "event_digest", "utf8", "sha256_hex", ""),
    (
        "canonical_bytes_utf8",
        "expected_registration_epoch",
        "utf8",
        "sha256_hex",
        "arkret-applet-registration-epoch-v1\n",
    ),
    ("canonical_bytes_base64url", "digest", "base64url", "sha256_hex", ""),
)

# Keys that state canonical bytes but carry no digest the lint can check them
# against. Every one needs a reason, because "no digest beside it" is also what a
# silently deleted digest looks like.
UNPAIRED_STATED_PREIMAGE_KEYS: dict[str, str] = {
    "canonical_preimage": (
        "symbolic candidate label ('A', 'B') in the Seal tie-break vector, not bytes"
    ),
    "canonical_preimage_equal_to": (
        "names another candidate's label: an equality assertion between two vector rows"
    ),
    "forbidden_legacy_preimage": (
        "names the retired preimage form a v1 implementation MUST NOT use; hashing it "
        "is the failure, not the expectation"
    ),
    "effect_op_canonical_bytes": (
        "ordered-log op transcript bytes; the vector pins the op ordering, and no digest "
        "over these bytes is registered"
    ),
    "decoded_payload_canonical_bytes_utf8": (
        "cursor payload; the sibling `input_cursor` is its base64url encoding, not a digest"
    ),
    "expected_metadata_canonical_bytes_utf8": (
        "the digest beside it is composite (metadata bytes || ciphertext) and is checked "
        "by check_encrypted_envelope_digest_vector"
    ),
    "event_preimage_digest": "a digest field, not a stated preimage",
    "public_key_canonical_bytes": (
        "carries the assertion word 'stable' in the device-pairing edge case, not bytes"
    ),
}

# `schema-validation-fixture.json` asserts JSON-Schema admissibility and nothing
# else: every digest in it is a shaped placeholder (`sha256:5555…`), which is
# correct for its purpose and meaningless to hash-check. Digest relations inside
# those instances are enforced by implementations at runtime -- e.g. the SDK's
# `CanonicalPublicMaterial::validate_structural` -- not by this gate.
PLACEHOLDER_DIGEST_FIXTURES = {"schema-validation-fixture.json"}

# The naming convention for "this string is canonical preimage bytes". The pair
# table above MAY register key names outside the convention (`canonical_event_payload`);
# the convention is what the completeness guard enumerates.
STATED_PREIMAGE_KEY_RE = re.compile(r"preimage|canonical_bytes")


def _stated_preimage_bytes(source: str, decoding: str) -> bytes | None:
    if decoding == "utf8":
        return source.encode("utf-8")
    if decoding == "base64url":
        try:
            return base64.urlsafe_b64decode(source + "=" * (-len(source) % 4))
        except (ValueError, binascii.Error):
            return None
    raise AssertionError(f"unknown stated-preimage decoding: {decoding}")


def _stated_digest(data: bytes, encoding: str) -> str:
    digest = hashlib.sha256(data).digest()
    if encoding == "sha256_hex":
        return "sha256:" + digest.hex()
    if encoding == "base64url":
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    raise AssertionError(f"unknown stated-digest encoding: {encoding}")


def check_stated_preimage_matches_stated_digest(lint: Lint) -> None:
    """Every fixture that spells out a preimage MUST hash to the digest beside it.

    These pairs are the whole point of a KAT: an implementor reads the preimage,
    hashes it and compares. When an id inside the preimage changes and the digest
    beside it does not, the vector still *looks* authoritative while pinning a
    value nothing can produce — which is exactly how the v1 id-form change left
    stale `expected_subject` / `batch_tag` values behind.

    Checking the two pairs that were caught by hand only made *those two* pairs
    unreachable. The recurring failure is a fixture family nobody thought to add,
    so this check has two halves:

    * every registered `(preimage, digest)` pair must agree wherever both keys
      sit in one node — the same rule extended from 2 to 8 families, including
      the two Event-digest families (`canonical_event_payload`,
      `digest_preimage_canonical_bytes_utf8`) where a vector once hashed the
      envelope instead of the preimage; and
    * every key that *states* canonical preimage bytes must be registered,
      either as a pair source or as a documented unpaired key. A new fixture
      family cannot arrive with an unchecked preimage.
    """

    def walk(node: Any, fixture_path: Path, placeholder_digests: bool) -> None:
        if isinstance(node, dict):
            components = node.get("components_array")
            if isinstance(components, list) and isinstance(node.get("expected_subject"), str):
                recomputed = sha256_base64url_text(canonical_json(components))
                if recomputed != node["expected_subject"]:
                    lint.fail(
                        fixture_path,
                        f"'expected_subject'={node['expected_subject']} but "
                        f"'components_array' hashes to {recomputed}",
                    )
            for key, value in node.items():
                if not isinstance(value, str) or not STATED_PREIMAGE_KEY_RE.search(key):
                    continue
                registered = key in UNPAIRED_STATED_PREIMAGE_KEYS or any(
                    key == source for source, *_ in STATED_PREIMAGE_DIGEST_PAIRS
                )
                if not registered:
                    lint.fail(
                        fixture_path,
                        f"{key!r} states canonical preimage bytes but is not registered: add it to "
                        "STATED_PREIMAGE_DIGEST_PAIRS with the digest it must hash to, or to "
                        "UNPAIRED_STATED_PREIMAGE_KEYS with the reason no digest can check it",
                    )
            if not placeholder_digests:
                for source_key, digest_key, decoding, encoding, prefix in (
                    STATED_PREIMAGE_DIGEST_PAIRS
                ):
                    source = node.get(source_key)
                    digest = node.get(digest_key)
                    if not isinstance(source, str) or not isinstance(digest, str):
                        continue
                    data = _stated_preimage_bytes(source, decoding)
                    if data is None:
                        lint.fail(
                            fixture_path,
                            f"{source_key!r} is not decodable as {decoding}",
                        )
                        continue
                    recomputed = _stated_digest(prefix.encode("utf-8") + data, encoding)
                    if recomputed != digest:
                        domain = f" under {prefix!r}" if prefix else ""
                        lint.fail(
                            fixture_path,
                            f"{digest_key!r}={digest} but {source_key!r} hashes{domain} to "
                            f"{recomputed}: the stated preimage and the stated digest disagree",
                        )
            for value in node.values():
                walk(value, fixture_path, placeholder_digests)
        elif isinstance(node, list):
            for value in node:
                walk(value, fixture_path, placeholder_digests)

    for fixture_path in sorted((ARTIFACTS / "fixtures").glob("*.json")):
        fixture = load_json(lint, fixture_path)
        if fixture is not None:
            walk(fixture, fixture_path, fixture_path.name in PLACEHOLDER_DIGEST_FIXTURES)


def check_event_batch_receipt_normalization_vector(lint: Lint) -> None:
    fixture_path = ARTIFACTS / "fixtures" / "encoding-fixture.json"
    fixture = load_json(lint, fixture_path)
    if not isinstance(fixture, dict):
        return
    vector = next(
        (
            item
            for item in fixture.get("vectors", [])
            if isinstance(item, dict)
            and item.get("vector_id") == "ak.vector.encoding.event_batch_receipt_digest.v1"
        ),
        None,
    )
    if not isinstance(vector, dict):
        lint.fail(fixture_path, "missing Event Batch Receipt digest vector")
        return
    receipt = vector.get("input")
    expected_digest = vector.get("expected_digest")
    if not isinstance(receipt, dict) or not isinstance(expected_digest, str):
        lint.fail(fixture_path, "Event Batch Receipt vector must declare input and expected_digest")
        return

    def normalize_events(events: Any) -> list[Any] | None:
        if not isinstance(events, list) or not events:
            return None
        by_key: dict[bytes, Any] = {}
        for event in events:
            key = canonical_json(event).encode("utf-8")
            by_key[key] = event
        return [by_key[key] for key in sorted(by_key)]

    baseline_events = receipt.get("events")
    normalized_baseline = normalize_events(baseline_events)
    if normalized_baseline is None or baseline_events != normalized_baseline:
        lint.fail(fixture_path, "Event Batch Receipt vector events must already be canonical and unique")

    cases = vector.get("normalization_cases")
    if not isinstance(cases, list) or len(cases) < 3:
        lint.fail(fixture_path, "Event Batch Receipt vector must cover normalize, unsorted, and duplicate cases")
        return
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            lint.fail(fixture_path, f"normalization_cases[{index}] must be an object")
            continue
        if "input_events" in case:
            normalized = normalize_events(case.get("input_events"))
            if normalized != case.get("expected_events"):
                lint.fail(fixture_path, f"normalization_cases[{index}] expected_events mismatch")
                continue
            normalized_receipt = copy.deepcopy(receipt)
            normalized_receipt["events"] = normalized
            normalized_digest = sha256_text(canonical_json(normalized_receipt))
            if normalized_digest != case.get("expected_digest") or normalized_digest != expected_digest:
                lint.fail(fixture_path, f"normalization_cases[{index}] digest mismatch")
        if "wire_events" in case:
            wire_events = case.get("wire_events")
            if normalize_events(wire_events) == wire_events:
                lint.fail(fixture_path, f"normalization_cases[{index}] negative wire is canonical")
            if case.get("expected") != "schema_violation_before_digest_verification":
                lint.fail(fixture_path, f"normalization_cases[{index}] must reject before digest verification")

    schema_path = ARTIFACTS / "schemas" / "event-batch-receipt.schema.json"
    schema = load_json(lint, schema_path)
    events_schema = schema.get("properties", {}).get("events", {}) if isinstance(schema, dict) else {}
    if events_schema.get("uniqueItems") is not True:
        lint.fail(schema_path, "Event Batch Receipt events must set uniqueItems=true")


def check_encrypted_envelope_digest_vector(lint: Lint) -> None:
    fixture_path = ARTIFACTS / "fixtures" / "encoding-fixture.json"
    fixture = load_json(lint, fixture_path)
    if not isinstance(fixture, dict):
        return
    vector = next(
        (
            item
            for item in fixture.get("vectors", [])
            if isinstance(item, dict)
            and item.get("vector_id") == "ak.vector.encoding.encrypted_envelope_digest.v1"
        ),
        None,
    )
    if not isinstance(vector, dict):
        lint.fail(fixture_path, "missing Encrypted Envelope digest vector")
        return

    kat = vector.get("event_ref_digest_kat")
    metadata = vector.get("payload_metadata")
    if not isinstance(kat, dict) or not isinstance(metadata, dict):
        lint.fail(fixture_path, "Encrypted Envelope vector must declare payload_metadata and event_ref_digest_kat")
        return
    domain = kat.get("domain_separator_utf8")
    event_id = kat.get("event_id")
    realm_id = kat.get("realm_id")
    if not all(isinstance(value, str) for value in (domain, event_id, realm_id)):
        lint.fail(fixture_path, "event_ref_digest_kat inputs must be strings")
        return
    digest_input = domain.encode("utf-8") + b"\x00" + event_id.encode("utf-8") + b"\x00" + realm_id.encode("utf-8")
    expected_ref_digest = "sha256:" + hashlib.sha256(digest_input).hexdigest()
    if kat.get("digest_input_hex") != digest_input.hex():
        lint.fail(fixture_path, "event_ref_digest_kat digest_input_hex does not match canonical input")
    if kat.get("expected_digest") != expected_ref_digest:
        lint.fail(fixture_path, "event_ref_digest_kat expected_digest does not match canonical input")
    aad = metadata.get("aad")
    if not isinstance(aad, dict) or aad.get("realm_id") != realm_id or aad.get("event_ref_digest") != expected_ref_digest:
        lint.fail(fixture_path, "payload_metadata.aad is not bound to event_ref_digest_kat")

    mutations = kat.get("mutation_cases")
    expected_mutations = {
        "omit_nul_separators": domain.encode("utf-8") + event_id.encode("utf-8") + realm_id.encode("utf-8"),
        "swap_event_id_and_realm_id": (
            domain.encode("utf-8") + b"\x00" + realm_id.encode("utf-8") + b"\x00" + event_id.encode("utf-8")
        ),
        "append_trailing_nul": digest_input + b"\x00",
    }
    if not isinstance(mutations, list) or len(mutations) != len(expected_mutations):
        lint.fail(fixture_path, "event_ref_digest_kat must cover separator, field-order, and trailing-byte mutations")
    else:
        seen_mutation_names: set[str] = set()
        for index, mutation in enumerate(mutations):
            if not isinstance(mutation, dict):
                lint.fail(fixture_path, f"event_ref_digest_kat mutation_cases[{index}] must be an object")
                continue
            mutation_name = mutation.get("name")
            if (
                not isinstance(mutation_name, str)
                or mutation_name not in expected_mutations
                or mutation_name in seen_mutation_names
            ):
                lint.fail(fixture_path, f"event_ref_digest_kat mutation_cases[{index}] has unknown or duplicate name")
                continue
            seen_mutation_names.add(mutation_name)
            try:
                mutated_input = bytes.fromhex(mutation.get("digest_input_hex", ""))
            except (TypeError, ValueError):
                lint.fail(fixture_path, f"event_ref_digest_kat mutation_cases[{index}] has invalid hex")
                continue
            if mutated_input != expected_mutations[mutation_name]:
                lint.fail(fixture_path, f"event_ref_digest_kat mutation_cases[{index}] input does not match its name")
            mutated_digest = "sha256:" + hashlib.sha256(mutated_input).hexdigest()
            if mutation.get("expected_digest") != mutated_digest:
                lint.fail(fixture_path, f"event_ref_digest_kat mutation_cases[{index}] digest mismatch")
            if mutation.get("must_not_equal_valid") is not True or mutated_digest == expected_ref_digest:
                lint.fail(fixture_path, f"event_ref_digest_kat mutation_cases[{index}] is not a strict negative")

    canonical_metadata = canonical_json(metadata)
    if vector.get("expected_metadata_canonical_bytes_utf8") != canonical_metadata:
        lint.fail(fixture_path, "Encrypted Envelope canonical payload_metadata bytes mismatch")
    if isinstance(aad, dict) and vector.get("aad_digest") != sha256_text(canonical_json(aad)):
        lint.fail(fixture_path, "Encrypted Envelope aad_digest mismatch")
    ciphertext_base64url = vector.get("ciphertext_base64url")
    if not isinstance(ciphertext_base64url, str):
        lint.fail(fixture_path, "Encrypted Envelope ciphertext_base64url must be a string")
        return
    try:
        padded = ciphertext_base64url + "=" * (-len(ciphertext_base64url) % 4)
        ciphertext = base64.urlsafe_b64decode(padded)
    except (ValueError, base64.binascii.Error):
        lint.fail(fixture_path, "Encrypted Envelope ciphertext_base64url is invalid")
        return
    expected_digest = "sha256:" + hashlib.sha256(canonical_metadata.encode("utf-8") + ciphertext).hexdigest()
    if vector.get("expected_digest") != expected_digest:
        lint.fail(fixture_path, "Encrypted Envelope expected_digest mismatch")


ONE_OF_REFERENCE_RE = re.compile(
    r"^(?:https://arkret\.org/v1/schemas/|schemas/|\./|\.\./schemas/)?"
    r"([A-Za-z0-9._-]+\.json)(#.*)?$"
)


def check_one_of_branch_discriminability(lint: Lint) -> None:
    """Every object-union `oneOf` must have a decidable branch.

    ``oneOf`` means "exactly one branch matches". When the branches are objects
    that overlap, a single instance can satisfy two of them and the whole union
    fails, and a statically typed decoder has no principled way to choose. A
    union is decidable when one of these holds:

      * a discriminator: one required property carries a distinct single value
        (``const`` or a one-entry ``enum``) in every branch;
      * structural exclusivity: for every pair of branches, one side is closed
        and the other requires a property that side does not declare, the two
        pin a shared required property to different constants, or one side
        explicitly refuses a property the other requires.

    Two shapes are deliberately out of scope. A document-level ``oneOf`` is a
    catalog of DTOs whose consumers bind a fragment, not a runtime union. A
    constraint-style ``oneOf`` whose branches declare no ``required`` and no
    ``$ref`` expresses legal field combinations of one object, and its
    discriminator lives on the enclosing schema.
    """

    documents = {
        path.name: load_json(lint, path)
        for path in sorted((ARTIFACTS / "schemas").glob("*.json"))
    }

    def resolve_pointer(document: Any, pointer: str) -> Any:
        node = document
        for part in pointer.lstrip("#/").split("/"):
            if not part:
                continue
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(node, dict) and part in node:
                node = node[part]
            elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
                node = node[int(part)]
            else:
                return None
        return node

    def deref(node: Any, current: str, depth: int = 0) -> Any:
        if depth > 8 or not isinstance(node, dict) or "$ref" not in node:
            return node
        reference = node["$ref"]
        if reference.startswith("#"):
            return deref(resolve_pointer(documents[current], reference), current, depth + 1)
        match = ONE_OF_REFERENCE_RE.match(reference)
        if not match or match.group(1) not in documents:
            return None
        target = documents[match.group(1)]
        return deref(resolve_pointer(target, match.group(2) or "#"), match.group(1), depth + 1)

    def single_valued(node: Any) -> str | None:
        if not isinstance(node, dict):
            return None
        if "const" in node:
            return json.dumps(node["const"], sort_keys=True)
        enum = node.get("enum")
        if isinstance(enum, list) and len(enum) == 1:
            return json.dumps(enum[0], sort_keys=True)
        return None

    def discriminator(branches: list[dict[str, Any]], outer_required: set[str]) -> str | None:
        candidates: set[str] | None = None
        for branch in branches:
            required = set(branch.get("required", [])) | outer_required
            properties = branch.get("properties") or {}
            names = {name for name in required if single_valued(properties.get(name))}
            candidates = names if candidates is None else candidates & names
        for name in sorted(candidates or ()):
            values = [single_valued((branch.get("properties") or {})[name]) for branch in branches]
            if len(set(values)) == len(values):
                return name
        return None

    def closed(node: dict[str, Any]) -> bool:
        return node.get("additionalProperties") is False or node.get("unevaluatedProperties") is False

    def forbidden(node: dict[str, Any]) -> set[str]:
        names: set[str] = set()
        negated = node.get("not")
        if isinstance(negated, dict):
            names.update(name for name in negated.get("required", []) if isinstance(name, str))
            for branch in negated.get("anyOf", []) or []:
                if isinstance(branch, dict):
                    names.update(n for n in branch.get("required", []) if isinstance(n, str))
        return names

    def exclusive(left: dict[str, Any], right: dict[str, Any]) -> bool:
        left_required = set(left.get("required", []))
        right_required = set(right.get("required", []))
        if forbidden(left) & right_required or forbidden(right) & left_required:
            return True
        if closed(right) and left_required - set((right.get("properties") or {}).keys()):
            return True
        if closed(left) and right_required - set((left.get("properties") or {}).keys()):
            return True
        for name in left_required & right_required:
            left_value = single_valued((left.get("properties") or {}).get(name))
            right_value = single_valued((right.get("properties") or {}).get(name))
            if left_value and right_value and left_value != right_value:
                return True
        return False

    def sites(name: str, node: Any, pointer: str, out: list[tuple[str, list[Any], set[str]]]) -> None:
        if isinstance(node, dict):
            branches = node.get("oneOf")
            if isinstance(branches, list) and len(branches) > 1:
                out.append((pointer, branches, set(node.get("required", []))))
            for key, value in node.items():
                sites(name, value, f"{pointer}/{key}", out)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                sites(name, value, f"{pointer}/{index}", out)

    for document_name, document in documents.items():
        if not isinstance(document, dict):
            continue
        path = ARTIFACTS / "schemas" / document_name
        found: list[tuple[str, list[Any], set[str]]] = []
        sites(document_name, document, "", found)
        for pointer, branches, outer_required in found:
            if pointer == "":
                continue
            if all(
                isinstance(branch, dict) and not branch.get("required") and "$ref" not in branch
                for branch in branches
            ):
                continue
            resolved = [deref(branch, document_name) for branch in branches]
            if not all(isinstance(node, dict) for node in resolved):
                continue
            if not all(
                node.get("type") == "object" or "properties" in node for node in resolved
            ):
                continue
            if discriminator(resolved, outer_required):
                continue
            if all(
                exclusive(left, right)
                for index, left in enumerate(resolved)
                for right in resolved[index + 1 :]
            ):
                continue
            lint.fail(
                path,
                f"{pointer or '/'} oneOf object branches are not decidable: add a required "
                "single-valued discriminator, close a branch, or make the required sets exclusive",
            )


def check_string_profile_format_vectors(lint: Lint) -> None:
    """The custom string formats must keep one executable vector set.

    ``string-profiles.schema.json`` declares eight ``arkret-*`` formats whose
    normative semantics (PRECIS, UTS #46, NFC) cannot be expressed by the
    coarse JSON Schema pattern and length keywords. This check binds the
    fixture to the schema so every format keeps positive and negative vectors,
    and it proves the declared rejection layer of each negative value: a
    ``schema_pattern`` value must already fail the coarse shape, while a
    ``profile_validator`` value must pass it, which is exactly why a runtime
    that only validates JSON Schema is insufficient.
    """

    schema_path = ARTIFACTS / "schemas" / "string-profiles.schema.json"
    fixture_path = ARTIFACTS / "fixtures" / "string-profile-fixture.json"
    schema = load_json(lint, schema_path)
    fixture = load_json(lint, fixture_path)
    if not isinstance(schema, dict) or not isinstance(fixture, dict):
        return
    if Draft202012Validator is None:
        return

    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        lint.fail(schema_path, "string profiles schema must declare $defs")
        return
    declared_formats = {
        node["format"]: f"schemas/string-profiles.schema.json#/$defs/{name}"
        for name, node in defs.items()
        if isinstance(node, dict) and isinstance(node.get("format"), str)
    }

    vectors = fixture.get("vectors")
    if not isinstance(vectors, list) or not vectors:
        lint.fail(fixture_path, "string profile fixture must declare a non-empty vectors list")
        return

    covered: dict[str, str] = {}
    for index, vector in enumerate(vectors):
        label = f"vectors[{index}]"
        if not isinstance(vector, dict):
            lint.fail(fixture_path, f"{label} must be an object")
            continue
        format_name = vector.get("format")
        schema_ref = vector.get("schema_ref")
        if not isinstance(format_name, str) or format_name not in declared_formats:
            lint.fail(fixture_path, f"{label}.format is not declared by string-profiles.schema.json")
            continue
        if format_name in covered:
            lint.fail(fixture_path, f"{label}.format duplicates {format_name}")
            continue
        covered[format_name] = schema_ref if isinstance(schema_ref, str) else ""
        if schema_ref != declared_formats[format_name]:
            lint.fail(
                fixture_path,
                f"{label}.schema_ref must be {declared_formats[format_name]} for {format_name}",
            )
            continue

        definition = dict(defs[schema_ref.rsplit("/", 1)[-1]])
        definition.pop("format", None)
        definition["$defs"] = defs
        validator = Draft202012Validator(definition)

        accepted = vector.get("accepted")
        if not isinstance(accepted, list) or not accepted:
            lint.fail(fixture_path, f"{label}.accepted must be a non-empty list")
        else:
            for value in accepted:
                if not isinstance(value, str):
                    lint.fail(fixture_path, f"{label}.accepted values must be strings")
                elif not validator.is_valid(value):
                    lint.fail(
                        fixture_path,
                        f"{label}.accepted value fails the coarse {format_name} shape: {value!r}",
                    )
                elif unicodedata.normalize("NFC", value) != value:
                    lint.fail(
                        fixture_path,
                        f"{label}.accepted value is not NFC: {value!r}",
                    )

        rejected = vector.get("rejected")
        if not isinstance(rejected, list) or not rejected:
            lint.fail(fixture_path, f"{label}.rejected must be a non-empty list")
            continue
        profile_only = 0
        for position, case in enumerate(rejected):
            case_label = f"{label}.rejected[{position}]"
            if not isinstance(case, dict):
                lint.fail(fixture_path, f"{case_label} must be an object")
                continue
            value = case.get("value")
            layer = case.get("rejected_by")
            if not isinstance(value, str):
                lint.fail(fixture_path, f"{case_label}.value must be a string")
                continue
            if not isinstance(case.get("reason"), str) or not case.get("reason"):
                lint.fail(fixture_path, f"{case_label}.reason must be a non-empty string")
            if layer not in {"schema_pattern", "profile_validator"}:
                lint.fail(fixture_path, f"{case_label}.rejected_by must be schema_pattern or profile_validator")
                continue
            accepted_by_shape = validator.is_valid(value)
            if layer == "schema_pattern" and accepted_by_shape:
                lint.fail(
                    fixture_path,
                    f"{case_label} claims schema_pattern but the coarse shape accepts it: {value!r}",
                )
            if layer == "profile_validator":
                profile_only += 1
                if not accepted_by_shape:
                    lint.fail(
                        fixture_path,
                        f"{case_label} claims profile_validator but the coarse shape already rejects it: {value!r}",
                    )
        if profile_only == 0:
            lint.fail(
                fixture_path,
                f"{label} must carry at least one profile_validator-only negative for {format_name}",
            )

    for format_name in sorted(set(declared_formats) - set(covered)):
        lint.fail(fixture_path, f"custom format has no vector: {format_name}")


def check_declared_canonical_json_strings(lint: Lint) -> None:
    """A fixture field named `*_canonical_json` MUST actually be canonical.

    RFC 8785 canonical JSON sorts object keys. A fixture that stores an
    unsorted string under a `_canonical_json` name is self-contradictory: the
    vector stays internally consistent while disagreeing with every conforming
    implementation, and the mismatch only surfaces downstream. The
    `passphrase_kdf_kat` nonce transcript failed exactly this way, and every
    value derived from it had to be regenerated.
    """
    fixture_root = ARTIFACTS / "fixtures"
    for path in sorted(fixture_root.glob("*.json")):
        data = load_json(lint, path)
        if data is None:
            continue

        def walk(node: Any, pointer: str) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    child = f"{pointer}/{key}"
                    if key.endswith("_canonical_json") and isinstance(value, str):
                        try:
                            parsed = json.loads(value)
                        except json.JSONDecodeError:
                            lint.fail(path, f"{child} is not parseable JSON")
                            continue
                        if canonical_json(parsed) != value:
                            lint.fail(
                                path,
                                f"{child} is named canonical but is not RFC 8785 canonical "
                                "(object keys must be sorted, no insignificant whitespace)",
                            )
                    walk(value, child)
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    walk(value, f"{pointer}/{index}")

        walk(data, "")


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


def check_reducer_profile_registry(lint: Lint) -> None:
    registry_path = ARTIFACTS / "registry" / "reducer-profile-registry.json"
    registry = load_json(lint, registry_path)
    if not isinstance(registry, dict):
        return
    rows = registry.get("profiles")
    if not isinstance(rows, list) or not rows:
        lint.fail(registry_path, "profiles must be a non-empty array")
        return

    profile_pattern = re.compile(r"^ak\.reducer(?:\.[a-z0-9][a-z0-9_.-]*)?\.v[0-9]+$")
    ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            lint.fail(registry_path, f"profiles[{index}] must be an object")
            continue
        profile_id = row.get("profile_id")
        if not isinstance(profile_id, str) or not profile_pattern.fullmatch(profile_id):
            lint.fail(registry_path, f"profiles[{index}].profile_id must use ak.reducer.*.vN")
            continue
        if profile_id in ids:
            lint.fail(registry_path, f"duplicate reducer profile id: {profile_id}")
        ids.add(profile_id)
        if row.get("status") != "active":
            lint.fail(registry_path, f"{profile_id} status must be active")
        if not isinstance(row.get("governs"), list) or not row["governs"]:
            lint.fail(registry_path, f"{profile_id} must declare governs[]")
        if not isinstance(row.get("supported_lattices"), list) or not row["supported_lattices"]:
            lint.fail(registry_path, f"{profile_id} must declare supported_lattices[]")
        edges = row.get("upgrade_edges")
        if not isinstance(edges, list):
            lint.fail(registry_path, f"{profile_id}.upgrade_edges must be an array")

    for row in rows:
        if not isinstance(row, dict):
            continue
        for edge_index, edge in enumerate(row.get("upgrade_edges", [])):
            if not isinstance(edge, dict):
                lint.fail(registry_path, f"{row.get('profile_id')}.upgrade_edges[{edge_index}] must be an object")
                continue
            target = edge.get("target_profile")
            transition = edge.get("state_transition")
            if target not in ids:
                lint.fail(registry_path, f"upgrade edge target is not registered: {target}")
            if transition != "identity" and not isinstance(transition, dict):
                lint.fail(registry_path, "upgrade edge state_transition must be identity or a deterministic transition object")

    event_schema_path = ARTIFACTS / "schemas" / "event-envelope.schema.json"
    event_schema = load_json(lint, event_schema_path)
    requirement_properties = (
        event_schema.get("properties", {}).get("requirements", {}).get("properties", {})
        if isinstance(event_schema, dict)
        else {}
    )
    if "reducer" in requirement_properties:
        lint.fail(event_schema_path, "Event requirements must not declare reducer selection")

    realm_schema_path = ARTIFACTS / "schemas" / "realm.schema.json"
    realm_schema = load_json(lint, realm_schema_path)
    if isinstance(realm_schema, dict):
        if "reducer_profile" not in realm_schema.get("required", []):
            lint.fail(realm_schema_path, "Realm.reducer_profile must be required")
        reducer_property = realm_schema.get("properties", {}).get("reducer_profile")
        if not isinstance(reducer_property, dict) or reducer_property.get("pattern") != profile_pattern.pattern:
            lint.fail(realm_schema_path, "Realm.reducer_profile must use the canonical reducer profile pattern")

    event_registry_path = ARTIFACTS / "registry" / "event-kind-registry.json"
    event_registry = load_json(lint, event_registry_path)
    event_rows = event_registry.get("event_kinds", []) if isinstance(event_registry, dict) else []
    by_kind = {
        row.get("event_kind"): row
        for row in event_rows
        if isinstance(row, dict) and isinstance(row.get("event_kind"), str)
    }
    expected_family = "ak.component.realm.reducer_profile.v1"
    create_writes = by_kind.get("ak.realm.create", {}).get("cell_writes", [])
    upgrade_writes = by_kind.get("ak.realm.upgrade", {}).get("cell_writes", [])
    create_profile_writes = [write for write in create_writes if write.get("cell_family") == expected_family]
    upgrade_profile_writes = [write for write in upgrade_writes if write.get("cell_family") == expected_family]
    if len(create_profile_writes) != 1 or create_profile_writes[0].get("cell_subject") is not None:
        lint.fail(event_registry_path, "ak.realm.create must initialize exactly one reducer-profile singleton cell")
    if len(upgrade_profile_writes) != 1 or upgrade_profile_writes[0].get("cell_subject") is not None:
        lint.fail(event_registry_path, "ak.realm.upgrade must write exactly one reducer-profile singleton cell")

    dto_path = ARTIFACTS / "schemas" / "service-operation-dtos.schema.json"
    dto_schema = load_json(lint, dto_path)
    binding = dto_schema.get("$defs", {}).get("FederationServiceBindingRef", {}) if isinstance(dto_schema, dict) else {}
    binding_properties = binding.get("properties", {}) if isinstance(binding, dict) else {}
    if any(name in binding_properties for name in ("reducer_profile", "reducer_profile_digest")):
        lint.fail(dto_path, "FederationServiceBindingRef must not carry reducer identity")

    describe_path = ARTIFACTS / "schemas" / "service-describe.schema.json"
    describe = load_json(lint, describe_path)
    supported = describe.get("properties", {}).get("supported_reducer_profiles") if isinstance(describe, dict) else None
    if not isinstance(supported, dict):
        lint.fail(describe_path, "ServiceDescribe must declare supported_reducer_profiles")


FIELD_ORDER_RULES_PATH = Path(__file__).with_name("field-order-rules.json")


def _load_field_order_rules(lint: Lint) -> dict[str, Any]:
    """Load the declarative field-ordering rule config (C-BET-03).

    Falls back to the historical hard-coded rule set if the config is missing or
    malformed, so the gate never silently stops enforcing ordering.
    """
    default = {
        "hard_precedence": [
            {"earlier": "created_by", "later": "created_at"},
            {"earlier": "created_at", "later": "updated_at"},
            {"earlier": "updated_by", "later": "updated_at"},
        ],
        "hard_immediate_follow": [
            {"anchor": "state", "marker": "state_changed_at"},
            {"anchor": "stage", "marker": "stage_changed_at"},
        ],
        "ordered_groups": {},
        "role_after_subject": {},
    }
    if not FIELD_ORDER_RULES_PATH.exists():
        return default
    try:
        data = json.loads(FIELD_ORDER_RULES_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - config corruption
        lint.fail(FIELD_ORDER_RULES_PATH, f"invalid field-order rule config: {exc}")
        return default
    if not isinstance(data, dict):
        lint.fail(FIELD_ORDER_RULES_PATH, "field-order rule config must be a JSON object")
        return default
    return {**default, **data}


def check_field_order(lint: Lint) -> None:
    """Canonical field ordering gate (models/common-fields.md §3.2; C-BET-03).

    Rules are loaded from the declarative ``tools/field-order-rules.json`` config
    and applied recursively to every object's ``properties`` in all schema files
    (and to the relative order of ``required`` entries against ``properties``).

    Two enforcement tiers:

    * Hard rules (errors) — wire-stable leading-group, precedence and
      immediate-follow rules
      that already hold across every current schema:
        - created_by MUST precede created_at; created_at MUST precede updated_at;
          updated_by MUST precede updated_at.
        - state_changed_at MUST immediately follow state; stage_changed_at MUST
          immediately follow stage.

    * Ordered-group rules (errors) — coverage for validity / issuance /
      audit-tail member fields (issued_at, not_before, effective_at,
      expires_at, revoked_*, updated_*) and ``role`` placement. These rules are
      presence-conditional and currently hold across the registered schemas, so
      drift is a lint error rather than an advisory warning.

    All checks are presence-conditional, so intended exceptions (Read Cursor has
    no created_at, Capability Grant uses issued_at) never trigger.
    """

    rules = _load_field_order_rules(lint)
    leading_group = rules.get("leading_group") or []
    hard_precedence = rules.get("hard_precedence") or []
    hard_immediate = rules.get("hard_immediate_follow") or []
    ordered_groups = rules.get("ordered_groups") or {}
    cluster_precedence = rules.get("cluster_precedence") or []
    role_rule = rules.get("role_after_subject") or {}
    subject_anchors = set(role_rule.get("subject_anchors") or [])
    role_field = role_rule.get("role_field")

    def check_order_of_keys(
        path: Path,
        json_path: str,
        keys: list[str],
        where: str,
        enforce_leading_group: bool,
    ) -> None:
        index = {key: position for position, key in enumerate(keys)}

        # Present members of the canonical identity/schema/scope leading group
        # must occupy the first slots when the object declares that convention
        # by beginning `required` with one of those members. This preserves
        # non-canonical DTO/scope shapes that merely happen to carry realm_id.
        if enforce_leading_group:
            present_leaders = [member for member in leading_group if member in index]
            if keys[:len(present_leaders)] != present_leaders:
                lint.fail(
                    path,
                    f"{json_path}.{where}: leading group {present_leaders} MUST occupy "
                    "the first declared slots in that order",
                )

        # Hard precedence (errors).
        for rule in hard_precedence:
            earlier = rule.get("earlier")
            later = rule.get("later")
            if earlier in index and later in index and index[earlier] > index[later]:
                lint.fail(
                    path,
                    f"{json_path}.{where}: field order: '{earlier}' MUST precede '{later}'",
                )

        # Hard immediate-follow (errors). Only meaningful for properties ordering.
        if where == "properties":
            for rule in hard_immediate:
                anchor = rule.get("anchor")
                marker = rule.get("marker")
                if anchor in index and marker in index and index[marker] != index[anchor] + 1:
                    lint.fail(
                        path,
                        f"{json_path}.{where}: '{marker}' MUST immediately follow '{anchor}'",
                    )

        # Ordered-group relative ordering (errors).
        for group_name, members in ordered_groups.items():
            if group_name.startswith("$") or not isinstance(members, list):
                continue
            present = [m for m in members if m in index]
            for i in range(len(present)):
                for j in range(i + 1, len(present)):
                    earlier, later = present[i], present[j]
                    if index[earlier] > index[later]:
                        lint.fail(
                            path,
                            f"{json_path}.{where}: group '{group_name}' ordering: "
                            f"'{earlier}' MUST precede '{later}'",
                        )

        # Cluster precedence (errors): every present member of the earlier
        # cluster MUST precede every present member of the later cluster.
        for rule in cluster_precedence:
            if not isinstance(rule, dict):
                continue
            earlier_present = [m for m in (rule.get("earlier") or []) if m in index]
            later_present = [m for m in (rule.get("later") or []) if m in index]
            if earlier_present and later_present:
                latest_earlier = max(index[m] for m in earlier_present)
                earliest_later = min(index[m] for m in later_present)
                if latest_earlier > earliest_later:
                    offending_earlier = max(earlier_present, key=lambda m: index[m])
                    offending_later = min(later_present, key=lambda m: index[m])
                    lint.fail(
                        path,
                        f"{json_path}.{where}: validity cluster MUST precede creation/audit cluster: "
                        f"'{offending_earlier}' MUST precede '{offending_later}'",
                    )

        # role placement relative to subject/issuer anchor (error).
        if role_field and role_field in index:
            anchors_present = [a for a in subject_anchors if a in index]
            if anchors_present:
                earliest_anchor = min(index[a] for a in anchors_present)
                if index[role_field] < earliest_anchor:
                    lint.fail(
                        path,
                        f"{json_path}.{where}: '{role_field}' MUST follow its "
                        f"subject/issuer identity field",
                    )

    def check_node(path: Path, json_path: str, node: dict) -> None:
        props = node.get("properties")
        if isinstance(props, dict):
            required = node.get("required")
            present_leaders = [member for member in leading_group if member in props]
            enforce_leading_group = (
                isinstance(required, list)
                and "schema" in present_leaders
                and required[: len(present_leaders)] == present_leaders
            )
            check_order_of_keys(
                path,
                json_path,
                list(props.keys()),
                "properties",
                enforce_leading_group,
            )
            if isinstance(required, list):
                # Check required entries in the order they are declared. A field
                # listed in required but absent from properties is left to the
                # existing schema-shape checks; we only order known property keys.
                req_keys = [r for r in required if isinstance(r, str)]
                check_order_of_keys(
                    path,
                    json_path,
                    req_keys,
                    "required",
                    enforce_leading_group,
                )

    def recurse(path: Path, json_path: str, node: Any) -> None:
        if isinstance(node, dict):
            check_node(path, json_path, node)
            for key, child in node.items():
                recurse(path, f"{json_path}.{key}", child)
        elif isinstance(node, list):
            for position, child in enumerate(node):
                recurse(path, f"{json_path}[{position}]", child)

    for schema_path in sorted((ARTIFACTS / "schemas").glob("*.schema.json")):
        data = load_json(lint, schema_path)
        if data is not None:
            recurse(schema_path, "$", data)


def check_model_required_field_table_coverage(lint: Lint) -> None:
    """Ensure core model field tables list every schema-required top-level field."""

    model_tables = [
        (
            "spec/v1/zh/models/realm-and-space.md",
            "spec/v1/artifacts/schemas/realm.schema.json",
            "ak.schema.realm.v1",
        ),
        (
            "spec/v1/zh/models/realm-and-space.md",
            "spec/v1/artifacts/schemas/space.schema.json",
            "ak.schema.space.v1",
        ),
        (
            "spec/v1/zh/models/strand-and-message.md",
            "spec/v1/artifacts/schemas/strand.schema.json",
            "ak.schema.strand.v1",
        ),
        (
            "spec/v1/zh/models/strand-and-message.md",
            "spec/v1/artifacts/schemas/message.schema.json",
            "ak.schema.message.v1",
        ),
        (
            "spec/v1/zh/models/relation.md",
            "spec/v1/artifacts/schemas/relation.schema.json",
            "ak.schema.relation.v1",
        ),
        (
            "spec/v1/zh/models/circle.md",
            "spec/v1/artifacts/schemas/circle.schema.json",
            "ak.schema.circle.v1",
        ),
        (
            "spec/v1/zh/models/morph.md",
            "spec/v1/artifacts/schemas/morph.schema.json",
            "ak.schema.morph.v1",
        ),
        (
            "spec/v1/zh/models/views.md",
            "spec/v1/artifacts/schemas/view.schema.json",
            "ak.schema.view.v1",
        ),
        (
            "spec/v1/zh/models/actor.md",
            "spec/v1/artifacts/schemas/actor-profile.schema.json",
            "ak.schema.actor_profile.v1",
        ),
    ]

    row_field_re = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)
    next_heading_re = re.compile(r"^#{2,6}\s+", re.MULTILINE)

    for doc_rel, schema_rel, schema_id in model_tables:
        doc_path = ROOT / doc_rel
        schema_path = ROOT / schema_rel
        schema = load_json(lint, schema_path)
        if not isinstance(schema, dict):
            continue
        required = schema.get("required")
        if not isinstance(required, list):
            continue
        try:
            text = doc_path.read_text(encoding="utf-8")
        except Exception as exc:
            lint.fail(doc_path, f"cannot read model field table: {exc}")
            continue

        marker = f"Schema id: `{schema_id}`"
        marker_index = text.find(marker)
        if marker_index < 0:
            lint.fail(doc_path, f"missing model field table marker for {schema_id}")
            continue

        table_region = text[marker_index + len(marker) :]
        next_heading = next_heading_re.search(table_region)
        if next_heading:
            table_region = table_region[: next_heading.start()]
        table_fields = {match.group(1) for match in row_field_re.finditer(table_region)}
        missing = [field for field in required if isinstance(field, str) and field not in table_fields]
        if missing:
            lint.fail(
                doc_path,
                f"{schema_id} field table missing schema-required field(s): {', '.join(missing)}",
            )


def check_exporter_label_registry(lint: Lint) -> None:
    """Validate the media exporter-label registry (OPT-003 / TERM-006).

    Each label is a wire-breaking key-derivation domain separation parameter;
    the registry is the single source of truth for label string, Context field
    shape, output length, applicable profiles, and grandfathering.
    """
    path = ARTIFACTS / "registry" / "exporter-label-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        lint.fail(path, "exporter-label-registry.json must be a JSON object")
        return
    labels = data.get("labels")
    if not isinstance(labels, list) or not labels:
        lint.fail(path, "exporter-label-registry.json: labels MUST be a non-empty list")
        return
    required = {"label", "context_fields", "output_bytes", "applies_to_profiles", "grandfathered"}
    seen: set[str] = set()
    for index, entry in enumerate(labels):
        if not isinstance(entry, dict):
            lint.fail(path, f"labels[{index}] must be an object")
            continue
        for missing in sorted(required - set(entry.keys())):
            lint.fail(path, f"labels[{index}] missing required key: {missing}")
        label = entry.get("label")
        if isinstance(label, str):
            if label in seen:
                lint.fail(path, f"duplicate exporter label: {label}")
            seen.add(label)
        context_fields = entry.get("context_fields")
        if not isinstance(context_fields, list):
            lint.fail(path, f"labels[{index}] context_fields MUST be a list")
        elif not context_fields:
            if entry.get("primitive") != "ExpandWithLabel" or entry.get("empty_context_forbidden") is not False:
                lint.fail(
                    path,
                    f"labels[{index}] empty context_fields is allowed only for an explicitly empty-context ExpandWithLabel entry",
                )
            if not isinstance(entry.get("context_encoding"), str) or "empty" not in entry["context_encoding"]:
                lint.fail(path, f"labels[{index}] empty-context entry must define context_encoding")


def json_pointer_get(data: Any, pointer: str) -> Any:
    current = data
    for token in pointer.removeprefix("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
            continue
        return None
    return current


def check_alg_registry(lint: Lint) -> None:
    path = ARTIFACTS / "registry" / "signature-alg-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return
    algorithms = data.get("algorithms")
    if not isinstance(algorithms, list) or not algorithms:
        lint.fail(path, "algorithms must be a non-empty array")
        return

    algs_by_proof_kind: dict[str, set[str]] = {
        "detached_jws": set(),
        "raw_detached_signature": set(),
    }
    http_message_signature_algorithms: set[str] = set()
    canonical_ids: set[str] = set()
    for index, row in enumerate(algorithms):
        label = f"algorithms[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue
        canonical_id = row.get("canonical_id")
        jose_algorithm = row.get("jose_algorithm")
        raw_signature_algorithm = row.get("raw_signature_algorithm")
        http_message_signature_algorithm = row.get("http_message_signature_algorithm")
        proof_kinds = row.get("proof_kinds")
        status = row.get("status")
        if not isinstance(canonical_id, str) or not canonical_id:
            lint.fail(path, f"{label}.canonical_id must be a non-empty string")
            continue
        if canonical_id in canonical_ids:
            lint.fail(path, f"duplicate canonical_id: {canonical_id}")
        canonical_ids.add(canonical_id)
        if status == "active":
            if not isinstance(proof_kinds, list) or not proof_kinds:
                lint.fail(path, f"{label}.proof_kinds must be a non-empty array")
                continue
            for proof_kind in proof_kinds:
                if proof_kind not in algs_by_proof_kind:
                    lint.fail(path, f"{label}.proof_kinds contains unsupported kind {proof_kind!r}")
                    continue
                algorithm = (
                    jose_algorithm
                    if proof_kind == "detached_jws"
                    else raw_signature_algorithm
                )
                if not isinstance(algorithm, str) or not algorithm:
                    lint.fail(path, f"{label} lacks an algorithm mapping for {proof_kind}")
                    continue
                algs_by_proof_kind[proof_kind].add(algorithm)
            if isinstance(http_message_signature_algorithm, str) and http_message_signature_algorithm:
                http_message_signature_algorithms.add(http_message_signature_algorithm)

    expected_jws = sorted(algs_by_proof_kind["detached_jws"])
    expected_raw = sorted(algs_by_proof_kind["raw_detached_signature"])
    # `alg` belongs to standards-defined JOSE objects only. In v1 schemas the
    # only inline JOSE object is the WebSocket DPoP protected header; compact
    # detached JWS values elsewhere are opaque strings and MUST NOT duplicate
    # their protected algorithm in an Arkret wrapper field.
    allowed_alg_property = (
        "websocket-dpop-proof.schema.json",
        "/$defs/protected_header/properties/alg",
    )

    def algorithm_properties(value: Any, pointer: str = "") -> Iterable[tuple[str, str, Any]]:
        if isinstance(value, dict):
            properties = value.get("properties")
            if isinstance(properties, dict):
                for name, property_schema in properties.items():
                    yield name, f"{pointer}/properties/{name}", property_schema
            for key, child in value.items():
                yield from algorithm_properties(child, f"{pointer}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from algorithm_properties(child, f"{pointer}/{index}")

    for schema_path in sorted((ARTIFACTS / "schemas").glob("*.json")):
        schema = load_json(lint, schema_path)
        if not isinstance(schema, dict):
            continue
        for name, pointer, property_schema in algorithm_properties(schema):
            if name == "alg" and (schema_path.name, pointer) != allowed_alg_property:
                lint.fail(
                    schema_path,
                    f"{pointer} uses JOSE-only shorthand alg in an Arkret-owned object",
                )
            if name == "accepted_algs" or name.endswith("_alg"):
                lint.fail(schema_path, f"{pointer} uses forbidden abbreviated algorithm field {name}")
            if name != "signature_algorithm" or not isinstance(property_schema, dict):
                continue
            resolved = property_schema
            ref = resolved.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/"):
                resolved = json_pointer_get(schema, ref.removeprefix("#"))
            values: list[str] = []
            if isinstance(resolved, dict) and isinstance(resolved.get("const"), str):
                values = [resolved["const"]]
            elif isinstance(resolved, dict) and isinstance(resolved.get("enum"), list):
                values = [item for item in resolved["enum"] if isinstance(item, str)]
            if not values:
                lint.fail(
                    schema_path,
                    f"{pointer} must fail closed with an explicit const/enum from raw_signature_algorithm mappings",
                )
            elif not set(values).issubset(set(expected_raw)):
                lint.fail(
                    schema_path,
                    f"{pointer} contains values outside active raw_signature_algorithm mappings: {values!r}; allowed={expected_raw!r}",
                )

    def check_fixture_algorithm_names(value: Any, fixture_path: Path, pointer: str = "") -> None:
        if isinstance(value, dict):
            for short_name in (
                name for name in value if name == "accepted_algs" or name.endswith("_alg")
            ):
                lint.fail(
                    fixture_path,
                    f"{pointer}/{short_name} uses forbidden abbreviated algorithm field {short_name}",
                )
            if "alg" in value:
                path_tokens = {token for token in pointer.split("/") if token}
                is_protected_header = bool(path_tokens & {"protected_header", "protected"})
                is_jwk = value.get("kty") in {"OKP", "EC", "RSA", "AKP"} and (
                    "crv" in value or "x" in value or "n" in value or "pub" in value
                )
                if not is_protected_header and not is_jwk:
                    lint.fail(
                        fixture_path,
                        f"{pointer}/alg uses JOSE-only shorthand outside a protected header or JWK",
                    )
            for key, child in value.items():
                check_fixture_algorithm_names(child, fixture_path, f"{pointer}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                check_fixture_algorithm_names(child, fixture_path, f"{pointer}/{index}")

    for fixture_path in sorted((ARTIFACTS / "fixtures").glob("*.json")):
        fixture = load_json(lint, fixture_path)
        if fixture is not None:
            check_fixture_algorithm_names(fixture, fixture_path)

    dpop_alg = load_json(lint, ARTIFACTS / "schemas" / allowed_alg_property[0])
    dpop_value = json_pointer_get(dpop_alg, allowed_alg_property[1]) if isinstance(dpop_alg, dict) else None
    dpop_const = dpop_value.get("const") if isinstance(dpop_value, dict) else None
    if dpop_const not in expected_jws:
        lint.fail(
            ARTIFACTS / "schemas" / allowed_alg_property[0],
            f"{allowed_alg_property[1]} must use an active jose_algorithm; got {dpop_const!r}",
        )

    applet_path = ARTIFACTS / "schemas" / "applet-package.schema.json"
    applet_schema = load_json(lint, applet_path)
    accepted_http_algorithms = json_pointer_get(
        applet_schema,
        "/$defs/http_message_signature_algorithm/enum",
    ) if isinstance(applet_schema, dict) else None
    if set(accepted_http_algorithms or []) != http_message_signature_algorithms:
        lint.fail(
            applet_path,
            "webhook_auth.accepted_signature_algorithms must exactly match active "
            f"http_message_signature_algorithm mappings: {sorted(http_message_signature_algorithms)!r}",
        )


def check_service_kind_registry(lint: Lint) -> None:
    path = ARTIFACTS / "registry" / "service-kind-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return
    if data.get("source_of_truth") is not True:
        lint.fail(path, "source_of_truth must be true")

    contexts = data.get("contexts")
    rows = data.get("service_kinds")
    if not isinstance(contexts, list) or not contexts:
        lint.fail(path, "contexts must be a non-empty array")
        return
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "service_kinds must be a non-empty array")
        return

    historical_description_markers = (
        "before this registry",
        "was absent",
        "registered from",
        "unconstrained string",
        "inline enum",
        "prose list",
        "arkret-rust-sdk",
        "tools/lint_artifacts.py",
    )
    description_sources: list[tuple[Path, Any]] = [(path, data)]
    service_describe_path = ARTIFACTS / "schemas" / "service-describe.schema.json"
    service_describe = load_json(lint, service_describe_path)
    if isinstance(service_describe, dict):
        description_sources.append((service_describe_path, service_describe))
    for owner, source in description_sources:
        for json_path, value, key in walk_json(source):
            if key != "description" or not isinstance(value, str):
                continue
            lowered = value.lower()
            for marker in historical_description_markers:
                if marker in lowered:
                    lint.fail(
                        owner,
                        f"{json_path} contains implementation history marker {marker!r}",
                    )

    context_ids: set[str] = set()
    for index, context in enumerate(contexts):
        if not isinstance(context, dict):
            lint.fail(path, f"contexts[{index}] must be an object")
            continue
        context_id = context.get("id")
        if not isinstance(context_id, str) or not context_id:
            lint.fail(path, f"contexts[{index}].id must be a non-empty string")
            continue
        if context_id in context_ids:
            lint.fail(path, f"duplicate context id: {context_id}")
        context_ids.add(context_id)

    # Active canonical ids per context, derived from the rows.
    by_context: dict[str, set[str]] = {context_id: set() for context_id in context_ids}
    canonical_ids: set[str] = set()
    for index, row in enumerate(rows):
        label = f"service_kinds[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue
        canonical_id = row.get("canonical_id")
        status = row.get("status")
        valid_in = row.get("valid_in")
        if not isinstance(canonical_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", canonical_id or ""):
            lint.fail(path, f"{label}.canonical_id must be lowercase snake_case matching [a-z][a-z0-9_]*")
            continue
        if canonical_id in canonical_ids:
            lint.fail(path, f"duplicate canonical_id: {canonical_id}")
        canonical_ids.add(canonical_id)
        if status not in {"active", "reserved"}:
            lint.fail(path, f"{label}.status must be active or reserved")
            continue
        if not isinstance(valid_in, list) or not valid_in:
            lint.fail(path, f"{label}.valid_in must be a non-empty array")
            continue
        for context_id in valid_in:
            if context_id not in context_ids:
                lint.fail(path, f"{label}.valid_in references unknown context {context_id!r}")
                continue
            if status == "active":
                by_context[context_id].add(context_id and canonical_id)

    # Every declared consumer pointer must match the derived value set exactly.
    for context in contexts:
        if not isinstance(context, dict):
            continue
        context_id = context.get("id")
        if context_id not in by_context:
            continue
        expected = sorted(by_context[context_id])
        if not expected:
            lint.fail(path, f"context {context_id} has no active service_kinds")
            continue
        for consumer in context.get("consumers") or []:
            if not isinstance(consumer, dict):
                lint.fail(path, f"context {context_id} consumers[] entries must be objects")
                continue
            file_ref = consumer.get("file")
            pointer = consumer.get("pointer")
            if not isinstance(file_ref, str) or not isinstance(pointer, str):
                lint.fail(path, f"context {context_id} consumer must declare file and pointer")
                continue
            schema_path = ARTIFACTS / file_ref
            schema = load_schema_document(lint, schema_path)
            actual = json_pointer_get(schema, pointer) if isinstance(schema, dict) else None
            if pointer.endswith("/const"):
                # A const pins a single-value context; it must still be a registered id.
                if len(expected) != 1:
                    lint.fail(
                        schema_path,
                        f"{pointer} is a const but context {context_id} has {len(expected)} active service_kinds",
                    )
                elif actual != expected[0]:
                    lint.fail(
                        schema_path,
                        f"{pointer} must match service-kind-registry {context_id} value {expected[0]!r}",
                    )
                continue
            if sorted(actual or []) != expected:
                lint.fail(
                    schema_path,
                    f"{pointer} must match service-kind-registry {context_id} values {expected}",
                )


def check_mls_pq_suite_registration(lint: Lint) -> None:
    """Every reserved PQ-MLS row must track the current MLS WG suite mapping.

    MLS derives keys with the two-stage Extract/Expand pair, which
    draft-ietf-hpke-pq does not define for single-stage SHAKE KDFs. The MLS WG
    therefore pins HKDF-SHA256 (0x0001) / HKDF-SHA384 (0x0002) as the MLS KDF,
    never the HPKE PQ SHAKE256 KDF 0x0011.
    """
    path = ARTIFACTS / "registry" / "mls-ciphersuite-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return
    rows = data.get("ciphersuites")
    if not isinstance(rows, list):
        lint.fail(path, "ciphersuites must be an array")
        return
    mls_draft = "draft-ietf-mls-pq-ciphersuites-06"
    mls_reference_url = f"https://datatracker.ietf.org/doc/html/{mls_draft}"
    expected_rows = {
        "reserved_pqc_hybrid": {
            "canonical_id": "MLS_128_MLKEM768X25519_AES128GCM_SHA256_Ed25519",
            "rfc9420_id": None,
            "mls_draft": mls_draft,
            "mls_reference_url": mls_reference_url,
            "kem_draft": "draft-ietf-hpke-pq-05",
            "kem_hpke_id": "0x647A",
            "kem_reference_url": "https://datatracker.ietf.org/doc/html/draft-ietf-hpke-pq-05",
            "kdf_hpke_id": "0x0001",
            "aead_hpke_id": "0x0001",
            "transcript_hash": "SHA256",
            "signature_scheme": "ed25519",
            "ietf_recommended": True,
            "construction_draft": "draft-irtf-cfrg-concrete-hybrid-kems-04",
            "construction_reference_url": "https://datatracker.ietf.org/doc/html/draft-irtf-cfrg-concrete-hybrid-kems-04",
            "status": "reserved",
        },
        "reserved_pqc_hybrid_authentication": {
            "canonical_id": "MLS_128_MLKEM768X25519_CHACHA20POLY1305_SHA384_MLDSA44",
            "rfc9420_id": None,
            "mls_draft": mls_draft,
            "mls_reference_url": mls_reference_url,
            "kem_draft": "draft-ietf-hpke-pq-05",
            "kem_hpke_id": "0x647A",
            "kem_reference_url": "https://datatracker.ietf.org/doc/html/draft-ietf-hpke-pq-05",
            "kdf_hpke_id": "0x0002",
            "aead_hpke_id": "0x0003",
            "transcript_hash": "SHA384",
            "signature_scheme": "mldsa44",
            "signature_draft": "draft-ietf-tls-mldsa-05",
            "signature_reference_url": "https://datatracker.ietf.org/doc/html/draft-ietf-tls-mldsa-05",
            "ietf_recommended": True,
            "status": "reserved",
        },
    }
    for role, expected in expected_rows.items():
        matched = [item for item in rows if isinstance(item, dict) and item.get("role") == role]
        if len(matched) != 1:
            lint.fail(path, f"expected exactly one {role} row, found {len(matched)}")
            continue
        row = matched[0]
        for field, value in expected.items():
            if row.get(field) != value:
                lint.fail(path, f"{role} row {field} must be {value!r}, got {row.get(field)!r}")
        requirements = row.get("activation_requirements")
        requirements = requirements if isinstance(requirements, list) else []
        if not any(
            isinstance(entry, str)
            and mls_draft in entry
            and f"KDF {expected['kdf_hpke_id']}" in entry
            and "0x0011 MUST NOT be used as the MLS KDF" in entry
            for entry in requirements
        ):
            lint.fail(
                path,
                f"{role} activation_requirements must pin the {mls_draft} tuple and forbid the single-stage SHAKE KDF 0x0011",
            )
    if any(isinstance(item, dict) and item.get("canonical_id") == "MLS_128_XWING_AES128GCM_SHA256_Ed25519" for item in rows):
        lint.fail(path, "private MLS_128_XWING_AES128GCM_SHA256_Ed25519 alias is forbidden")


def check_mls_governance_proof_fixture(lint: Lint) -> None:
    path = ARTIFACTS / "fixtures" / "mls-governance-proof-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    verifier_vector = "ak.vector.mls.governance_proof.verifier.v1"
    materializer_vector = "ak.vector.mls.governance_proof.materializer.v1"
    bounds_vector = "ak.vector.scalability.mls_governance_proof_bounds.v1"
    profile_id = "ak.profile.mls_governance_binding.full.v1"
    expected_vectors = {verifier_vector, materializer_vector}

    if data.get("generated_by") != "tools/generate_mls_governance_proof_fixture.py":
        lint.fail(path, "MLS governance proof fixture must name its deterministic generator")
    if set(data.get("covers_vectors", [])) != expected_vectors:
        lint.fail(path, "MLS governance proof fixture must cover the verifier and materializer vectors exactly")
    if data.get("required_companion_vectors") != [bounds_vector]:
        lint.fail(path, "MLS governance proof fixture must require the bounds companion vector")

    expected_consumers = {
        "sdk_proof_verifier": "ak.suite.mls.governance_proof_bundle.verify.v1",
        "server_materializer": "ak.suite.mls.governance_proof_bundle.materialize.v1",
    }
    consumers = data.get("consumer_contracts")
    actual_consumers = {
        row.get("role"): row.get("entrypoint")
        for row in consumers
        if isinstance(row, dict)
    } if isinstance(consumers, list) else {}
    if actual_consumers != expected_consumers:
        lint.fail(path, f"MLS governance proof consumer ownership mismatch: {actual_consumers}")
    for row in consumers if isinstance(consumers, list) else []:
        outputs = set(row.get("required_output_fields", [])) if isinstance(row, dict) else set()
        if row.get("role") == "sdk_proof_verifier":
            required_outputs = {
                "case_name", "schema_result", "decision", "failure_stage", "reason_code",
                "verified_bundle_digest", "epoch_advanced",
            }
        else:
            required_outputs = {
                "case_name", "decision", "error_code", "response_count", "bundle_digest",
                "chunk_digests", "peak_buffer_bytes", "partial_manifest_emitted",
            }
        if outputs != required_outputs:
            lint.fail(path, f"{row.get('role')} required output contract drifted: {sorted(outputs)}")

    profile_path = ARTIFACTS / "profiles" / "conformance-profiles.json"
    profiles = load_json(lint, profile_path)
    requirement = (
        profiles.get("profile_requirements", {}).get(profile_id, {})
        if isinstance(profiles, dict)
        else {}
    )
    required_profile_refs = {
        "required_endpoints": "ak.self.events.read.mls_governance_proof",
        "required_schemas": "ak.schema.mls_governance_proof_bundle.v1",
        "required_fixtures": path.name,
    }
    for field, value in required_profile_refs.items():
        if value not in requirement.get(field, []):
            lint.fail(profile_path, f"{profile_id}.{field} must include {value}")

    vector_path = ARTIFACTS / "registry" / "vector-registry.json"
    vector_data = load_json(lint, vector_path)
    rows = {
        row.get("vector_id"): row
        for row in vector_data.get("vectors", [])
        if isinstance(row, dict)
    } if isinstance(vector_data, dict) else {}
    for vector_id in expected_vectors:
        row = rows.get(vector_id, {})
        if row.get("status") != "active" or row.get("applies_to_fixtures") != [path.name]:
            lint.fail(vector_path, f"{vector_id} must be active and owned by {path.name}")
    bounds_row = rows.get(bounds_vector, {})
    if bounds_row.get("status") != "active" or bounds_row.get("applies_to_profiles") != [profile_id]:
        lint.fail(vector_path, f"{bounds_vector} must apply directly to {profile_id}")

    def raw_sha256(value: bytes) -> bytes:
        return hashlib.sha256(value).digest()

    def wire_sha256(value: bytes) -> str:
        return "sha256:" + raw_sha256(value).hex()

    def raw_digest(value: Any, label: str) -> bytes:
        if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
            lint.fail(path, f"{label} must be a sha256 wire digest")
            return b""
        return bytes.fromhex(value.split(":", 1)[1])

    def merkle_root(leaf_data: list[bytes]) -> str:
        if not leaf_data:
            return "sha256:" + raw_sha256(b"").hex()
        level = [raw_sha256(b"\x00" + item) for item in leaf_data]
        while len(level) > 1:
            next_level: list[bytes] = []
            for index in range(0, len(level), 2):
                if index + 1 == len(level):
                    next_level.append(level[index])
                else:
                    next_level.append(raw_sha256(b"\x01" + level[index] + level[index + 1]))
            level = next_level
        return "sha256:" + level[0].hex()

    source = data.get("source_state", {})
    events = source.get("covered_events", []) if isinstance(source, dict) else []
    state = source.get("joined_control_state", []) if isinstance(source, dict) else []
    seals = source.get("accepted_seals", []) if isinstance(source, dict) else []
    known = data.get("known_answer", {})
    if len(events) != 2 or len(state) != 2 or len(seals) != 1:
        lint.fail(path, "base KAT must contain two Events, two state leaves and one Seal")
        return
    event_kats = known.get("event_steps", []) if isinstance(known, dict) else []
    event_digests: list[str] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            lint.fail(path, f"covered_events[{index}] must be an object")
            continue
        producer = {
            key: value
            for key, value in event.items()
            if key not in {"proofs", "unsigned", "effective_scope", "actor_kind", "event_id"}
        }
        # event_id is excluded because zh/conformance/encoding.md section 4.0
        # derives it from this digest; see section 6 for the two-class rationale.
        producer_bytes = canonical_json(producer).encode("utf-8")
        event_digest = wire_sha256(producer_bytes)
        event_digests.append(event_digest)
        proofs = event.get("proofs", [])
        proof = proofs[0] if isinstance(proofs, list) and len(proofs) == 1 and isinstance(proofs[0], dict) else {}
        if proof.get("event_digest") != event_digest:
            lint.fail(path, f"covered_events[{index}] proof.event_digest does not match producer bytes")
        binding = {
            "context": "ak.event-proof-v1",
            "event_digest": event_digest,
            "actor_id": event.get("actor_id"),
            "verification_method": proof.get("verification_method"),
            "created_at": proof.get("created_at"),
        }
        kat = event_kats[index] if index < len(event_kats) and isinstance(event_kats[index], dict) else {}
        expected_event_values = {
            "event_id": event.get("event_id"),
            "producer_event_canonical_bytes": len(producer_bytes),
            "producer_event_digest": event_digest,
            "proof_binding_canonical_bytes": len(canonical_json(binding).encode("utf-8")),
            "proof_binding_sha256": wire_sha256(canonical_json(binding).encode("utf-8")),
        }
        if kat != expected_event_values:
            lint.fail(path, f"covered_events[{index}] known-answer metadata drifted")

    sorted_digests = sorted(event_digests)
    if event_digests[0] == event_digests[1] or len(set(event_digests)) != 2:
        lint.fail(path, "base KAT Event digests must be distinct")
    control_root = merkle_root([raw_digest(value, "Event digest") for value in sorted_digests])
    if known.get("control_event_set_root") != control_root:
        lint.fail(path, "known_answer.control_event_set_root mismatch")
    cells = [row.get("cell") for row in state if isinstance(row, dict)]
    if cells != sorted(cells) or len(set(cells)) != len(cells):
        lint.fail(path, "base KAT control_state must be canonical sorted and duplicate-free")
    state_bytes = [canonical_json(row).encode("utf-8") for row in state]
    state_root = merkle_root(state_bytes)
    if known.get("state_root") != state_root:
        lint.fail(path, "known_answer.state_root mismatch")
    if known.get("state_leaf_canonical_bytes") != [len(value) for value in state_bytes]:
        lint.fail(path, "known_answer.state_leaf_canonical_bytes mismatch")

    completeness_leaf = {
        "actor_id": events[0].get("actor_id"),
        "from_seq": 0,
        "to_seq": 1,
        "event_digests": event_digests,
    }
    completeness_bytes = canonical_json(completeness_leaf).encode("utf-8")
    completeness_root = merkle_root([completeness_bytes])
    if known.get("completeness_root") != completeness_root or known.get("completeness_leaf_canonical_bytes") != len(completeness_bytes):
        lint.fail(path, "known-answer completeness commitment mismatch")

    seal = seals[0]
    seal_body = {key: value for key, value in seal.items() if key not in {"id", "notary_signature"}}
    seal_bytes = canonical_json(seal_body).encode("utf-8")
    seal_digest = wire_sha256(seal_bytes)
    signature = seal.get("notary_signature", {}) if isinstance(seal, dict) else {}
    if seal.get("id") != "ak:seal:" + seal_digest or signature.get("payload_digest") != seal_digest:
        lint.fail(path, "Seal id/signature payload digest does not match canonical Seal body")
    if seal.get("delta") != sorted_digests:
        lint.fail(path, "Seal delta must equal the canonical covered Event digest set")
    expected_seal_fields = {
        "control_event_set_root": control_root,
        "state_root": state_root,
        "completeness_root": completeness_root,
    }
    for field, expected in expected_seal_fields.items():
        if seal.get(field) != expected:
            lint.fail(path, f"Seal {field} mismatch")
    if known.get("seal_digest") != seal_digest or known.get("seal_canonical_bytes") != len(seal_bytes):
        lint.fail(path, "known-answer Seal commitment mismatch")

    commit_context = data.get("commit_context", {})
    leaf_entries = (
        commit_context.get("current_or_pending_mls_leaf_entries", [])
        if isinstance(commit_context, dict)
        else []
    )
    if not isinstance(leaf_entries, list) or leaf_entries != sorted(
        leaf_entries, key=lambda row: canonical_json(row).encode("utf-8")
    ):
        lint.fail(path, "commit_context MLS leaf entries must be canonical sorted")
        leaf_entries = []
    mls_leaf_set_digest = wire_sha256(canonical_json(leaf_entries).encode("utf-8"))
    if (
        not isinstance(commit_context, dict)
        or commit_context.get("mls_leaf_set_digest") != mls_leaf_set_digest
        or known.get("mls_leaf_set_digest") != mls_leaf_set_digest
    ):
        lint.fail(path, "MLS leaf-set digest commitment mismatch")

    cell_entries = known.get("security_frontier_cell_entries", [])
    if not isinstance(cell_entries, list):
        lint.fail(path, "known_answer.security_frontier_cell_entries must be an array")
        cell_entries = []
    expected_cell_entries = []
    for event in events:
        payload = event.get("payload", {}) if isinstance(event, dict) else {}
        if not isinstance(payload, dict):
            continue
        expected_cell_entries.append(
            {
                "cell_family": "ak.component.member.state.v1",
                "cell_subject": payload.get("actor_id"),
                "projected_value_digest": wire_sha256(
                    canonical_json(payload.get("membership")).encode("utf-8")
                ),
            }
        )
    expected_cell_entries.sort(
        key=lambda row: (
            row["cell_family"].encode("utf-8"),
            canonical_json(row["cell_subject"]).encode("utf-8"),
            row["projected_value_digest"],
        )
    )
    if cell_entries != expected_cell_entries:
        lint.fail(path, "known-answer security frontier cell projection mismatch")
    security_frontier_input = {
        "profile_id": "ak.security_frontier.v1",
        "effective_scope": data.get("commit_context", {}).get("expected_effective_scope"),
        "cell_entries": cell_entries,
        "mls_leaf_set_digest": mls_leaf_set_digest,
    }
    security_frontier_bytes = canonical_json(security_frontier_input).encode("utf-8")
    security_frontier_digest = wire_sha256(security_frontier_bytes)
    if known.get("security_frontier_digest") != security_frontier_digest or known.get("security_frontier_input_canonical_bytes") != len(security_frontier_bytes):
        lint.fail(path, "known-answer security frontier commitment mismatch")
    binding = commit_context.get("transcript_authenticated_governance_binding", {}) if isinstance(commit_context, dict) else {}
    if not isinstance(binding, dict) or binding.get("security_frontier_digest") != security_frontier_digest:
        lint.fail(path, "governance binding must contain the rederived security_frontier_digest")

    proof_identity = source.get("proof_identity", {})
    identity_bytes = canonical_json(proof_identity).encode("utf-8")
    request_digest = wire_sha256(b"arkret-mls-governance-proof-request-v1\n" + identity_bytes)
    if known.get("proof_request_digest") != request_digest or known.get("proof_identity_canonical_bytes") != len(identity_bytes):
        lint.fail(path, "known-answer proof request commitment mismatch")

    acquisition = data.get("expected_acquisition", {})
    responses = acquisition.get("responses", []) if isinstance(acquisition, dict) else []
    requests = data.get("requests", [])
    if len(responses) != 4 or len(requests) != 4:
        lint.fail(path, "base acquisition must contain exactly four requests and responses")
        return
    chunks = [row.get("chunk") for row in responses if isinstance(row, dict)]
    expected_collections = ["seal_path", "covered_event_digests", "control_state", "frontier_events"]
    if [chunk.get("collection") for chunk in chunks if isinstance(chunk, dict)] != expected_collections:
        lint.fail(path, "base chunks must use the canonical four-collection order")
    chunk_digests: list[str] = []
    chunk_bytes_lengths: list[int] = []
    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            continue
        digest_input = {
            "chunk_index": chunk.get("chunk_index"),
            "collection": chunk.get("collection"),
            "start_index": chunk.get("start_index"),
            "items": chunk.get("items"),
        }
        digest_bytes = canonical_json(digest_input).encode("utf-8")
        chunk_digest = wire_sha256(b"arkret-mls-governance-proof-chunk-v1\n" + digest_bytes)
        chunk_digests.append(chunk_digest)
        chunk_bytes_lengths.append(len(digest_bytes))
        if chunk.get("chunk_index") != index or chunk.get("start_index") != 0 or chunk.get("chunk_digest") != chunk_digest:
            lint.fail(path, f"chunk {index} index/start/digest commitment mismatch")
        response = responses[index]
        request = requests[index] if isinstance(requests[index], dict) else {}
        if response.get("proof_request_digest") != request_digest or request.get("chunk_index") != index:
            lint.fail(path, f"request/response {index} acquisition identity mismatch")
        if index == 0 and "expected_bundle_digest" in request:
            lint.fail(path, "chunk 0 request must not carry expected_bundle_digest")

    chunks_root = merkle_root([raw_digest(value, "chunk digest") for value in chunk_digests])
    manifests = [row.get("chunk_manifest") for row in responses if isinstance(row, dict)]
    if any(manifest != manifests[0] for manifest in manifests[1:]):
        lint.fail(path, "every response must repeat the same chunk_manifest")
    manifest = manifests[0] if manifests and isinstance(manifests[0], dict) else {}
    total_item_bytes = sum(
        len(canonical_json(item).encode("utf-8"))
        for chunk in chunks if isinstance(chunk, dict)
        for item in chunk.get("items", [])
    )
    totals = {
        chunk["collection"]: len(chunk.get("items", []))
        for chunk in chunks if isinstance(chunk, dict)
    }
    if manifest.get("chunks_root") != chunks_root or manifest.get("total_item_bytes") != total_item_bytes or manifest.get("collection_totals") != totals:
        lint.fail(path, "manifest root/item-byte/collection totals mismatch")
    if known.get("chunk_digests") != chunk_digests or known.get("chunk_canonical_bytes") != chunk_bytes_lengths:
        lint.fail(path, "known-answer chunk commitments mismatch")
    if known.get("chunks_root") != chunks_root or known.get("total_item_bytes") != total_item_bytes:
        lint.fail(path, "known-answer manifest commitment mismatch")

    base_header = {key: value for key, value in responses[0].items() if key not in {"bundle_digest", "chunk"}}
    header_bytes = canonical_json(base_header).encode("utf-8")
    bundle_digest = wire_sha256(b"arkret-mls-governance-proof-bundle-v1\n" + header_bytes)
    for index, response in enumerate(responses):
        response_header = {key: value for key, value in response.items() if key not in {"bundle_digest", "chunk"}}
        if response_header != base_header or response.get("bundle_digest") != bundle_digest:
            lint.fail(path, f"response {index} Bundle header/digest mismatch")
        request = requests[index]
        if index and request.get("expected_bundle_digest") != bundle_digest:
            lint.fail(path, f"request {index} must pin the base bundle_digest")
    if known.get("bundle_digest") != bundle_digest or known.get("bundle_header_canonical_bytes") != len(header_bytes):
        lint.fail(path, "known-answer Bundle commitment mismatch")

    expected_verifier_cases = {
        "valid_complete_bundle", "self_reported_anchor_is_not_trust", "broken_seal_path",
        "forked_seal_path", "wrong_notary_authority", "missing_covered_digest",
        "extra_covered_digest", "duplicate_covered_digest", "covered_digest_order",
        "missing_state_leaf", "extra_state_leaf", "duplicate_state_leaf", "state_leaf_order",
        "missing_frontier_event", "extra_frontier_event", "duplicate_frontier_event",
        "frontier_event_order", "frontier_cross_realm_scope", "frontier_event_proof_invalid",
        "chunks_root_mismatch", "missing_chunk", "duplicate_chunk", "chunk_order",
        "binding_realm_mismatch", "binding_group_mismatch", "binding_previous_epoch_mismatch",
        "binding_next_epoch_mismatch", "binding_profile_mismatch", "binding_reducer_mismatch",
        "security_frontier_digest_mismatch", "unrelated_capability_does_not_change_frontier",
        "active_leaf_revoke_missing_from_frontier",
    }
    verifier_cases = data.get("verifier_cases", [])
    actual_verifier_cases = {
        row.get("name") for row in verifier_cases if isinstance(row, dict)
    } if isinstance(verifier_cases, list) else set()
    if actual_verifier_cases != expected_verifier_cases:
        lint.fail(path, f"verifier mutation matrix drifted: {sorted(actual_verifier_cases)}")
    for row in verifier_cases if isinstance(verifier_cases, list) else []:
        expected = row.get("expected", {}) if isinstance(row, dict) else {}
        if row.get("name") != "valid_complete_bundle" and (
            expected.get("verified_bundle_persisted") is not False
            or expected.get("epoch_advanced") is not False
            or not expected.get("failure_stage")
            or not expected.get("reason_code")
        ):
            lint.fail(path, f"reject verifier case lacks fail-closed output: {row.get('name')}")

    expected_materializer_cases = {
        "valid_materialization", "unknown_anchor", "unreachable_anchor", "missing_seal_material",
        "forked_seal_source", "unauthorized_notary_source", "missing_covered_event_source",
        "bottom_control_cell_source", "scope_visibility_denied", "logical_bundle_over_bound",
    }
    materializer_cases = data.get("materializer_cases", [])
    actual_materializer_cases = {
        row.get("name") for row in materializer_cases if isinstance(row, dict)
    } if isinstance(materializer_cases, list) else set()
    if actual_materializer_cases != expected_materializer_cases:
        lint.fail(path, f"materializer mutation matrix drifted: {sorted(actual_materializer_cases)}")
    for row in materializer_cases if isinstance(materializer_cases, list) else []:
        expected = row.get("expected", {}) if isinstance(row, dict) else {}
        if row.get("name") != "valid_materialization" and (
            expected.get("response_count") != 0
            or expected.get("partial_manifest_emitted") is not False
            or not expected.get("error_code")
        ):
            lint.fail(path, f"reject materializer case may emit partial output: {row.get('name')}")


def check_mls_governance_proof_bounds(lint: Lint) -> None:
    """Bounded proof chunks and Service Describe limits must stay identical."""
    schema_path = ARTIFACTS / "schemas" / "mls-governance-proof-bundle.schema.json"
    schema = load_json(lint, schema_path)
    if not isinstance(schema, dict):
        return

    expected_schema_values = {
        "/$defs/proof_request/properties/chunk_index/maximum": 1023,
        "/$defs/chunk_manifest/properties/chunk_count/minimum": 2,
        "/$defs/chunk_manifest/properties/chunk_count/maximum": 1024,
        "/$defs/chunk_manifest/properties/total_item_bytes/maximum": 268435456,
        "/$defs/chunk_manifest/properties/max_response_bytes/const": 4194304,
        "/$defs/chunk_manifest/properties/max_total_item_bytes/const": 268435456,
        "/$defs/collection_totals/properties/seal_path/maximum": 4096,
        "/$defs/collection_totals/properties/covered_event_digests/maximum": 1048576,
        "/$defs/collection_totals/properties/control_state/maximum": 262144,
        "/$defs/collection_totals/properties/frontier_events/maximum": 128,
        "/$defs/seal_path_chunk/properties/items/maxItems": 128,
        "/$defs/covered_event_digests_chunk/properties/items/maxItems": 8192,
        "/$defs/control_state_chunk/properties/items/maxItems": 1024,
        "/$defs/frontier_events_chunk/properties/items/maxItems": 32,
        "/$defs/chunk_proof/maxItems": 10,
    }
    for pointer, expected in expected_schema_values.items():
        actual = json_pointer_get(schema, pointer)
        if actual != expected:
            lint.fail(schema_path, f"{pointer} must be {expected}, got {actual!r}")

    sha256_ref = "#/$defs/sha256_digest"
    digest_ref_pointers = (
        "/properties/proof_request_digest/$ref",
        "/properties/bundle_digest/$ref",
        "/$defs/proof_request/properties/expected_bundle_digest/$ref",
        "/$defs/chunk_manifest/properties/chunks_root/$ref",
        "/$defs/chunk_proof/items/$ref",
        "/$defs/seal_path_chunk/properties/chunk_digest/$ref",
        "/$defs/covered_event_digests_chunk/properties/chunk_digest/$ref",
        "/$defs/control_state_chunk/properties/chunk_digest/$ref",
        "/$defs/frontier_events_chunk/properties/chunk_digest/$ref",
    )
    for pointer in digest_ref_pointers:
        actual = json_pointer_get(schema, pointer)
        if actual != sha256_ref:
            lint.fail(schema_path, f"{pointer} must reference fixed {sha256_ref}, got {actual!r}")

    top_required = set(schema.get("required") or [])
    if not {"chunk_manifest", "chunk"} <= top_required:
        lint.fail(schema_path, "top-level response must require chunk_manifest and chunk")
    top_properties = schema.get("properties", {})
    for legacy_collection in ("seal_path", "covered_event_digests", "control_state", "frontier_events"):
        if isinstance(top_properties, dict) and legacy_collection in top_properties:
            lint.fail(schema_path, f"top-level unbounded {legacy_collection} collection is forbidden")
    proof_request = schema.get("$defs", {}).get("proof_request", {})
    request_required = set(proof_request.get("required") or []) if isinstance(proof_request, dict) else set()
    request_properties = proof_request.get("properties", {}) if isinstance(proof_request, dict) else {}
    if "chunk_index" not in request_required or "expected_bundle_digest" not in request_properties:
        lint.fail(schema_path, "proof_request must require chunk_index and define expected_bundle_digest")

    describe_path = ARTIFACTS / "schemas" / "service-describe.schema.json"
    describe = load_json(lint, describe_path)
    if not isinstance(describe, dict):
        return
    describe_expected = {
        "max_response_bytes": 4194304,
        "max_total_item_bytes": 268435456,
        "max_chunks": 1024,
        "max_seal_path_items": 4096,
        "max_covered_event_digests": 1048576,
        "max_control_state_items": 262144,
        "max_frontier_events": 128,
    }
    limit_schema = (
        describe.get("properties", {})
        .get("limits", {})
        .get("properties", {})
        .get("mls_governance_proof", {})
    )
    required_limits = set(limit_schema.get("required") or []) if isinstance(limit_schema, dict) else set()
    if required_limits != set(describe_expected):
        lint.fail(describe_path, f"MLS governance proof limit fields must be {sorted(describe_expected)}")
    limit_properties = limit_schema.get("properties", {}) if isinstance(limit_schema, dict) else {}
    for field, expected in describe_expected.items():
        actual = limit_properties.get(field, {}).get("const") if isinstance(limit_properties, dict) else None
        if actual != expected:
            lint.fail(describe_path, f"limits.mls_governance_proof.{field} must const {expected}, got {actual!r}")


# --- STR-002 / OPT-005: action prose-reference closure ------------------------
# (ak.profile.*.vN prose closure is already enforced for all markdown by
# check_markdown_examples; only the hand-maintained action list lacked a gate.)

# Action tokens that legitimately appear as a `- `ak.<...>`` bullet in
# capabilities.md §5 but are intentionally NOT capability-action-registry
# entries. Keep empty unless a real exception exists; every addition MUST carry
# a one-line reason.
ALLOWED_PROSE_ACTIONS: set[str] = set()

_ACTION_TOKEN_RE = re.compile(r"^ak\.[a-z0-9_]+(?:\.[a-z0-9_]+)*$")
_PROSE_ACTION_BULLET_RE = re.compile(r"^\s*-\s+`(ak\.[a-z0-9_.]+)`")
_PROSE_ACTION_TARGET_RE = re.compile(r"target=`([^`]+)`")


def check_action_reference_closure(lint: Lint) -> None:
    """STR-002 / OPT-005: every action declared in capabilities.md §5 (动作集合)
    bullet lists MUST resolve in capability-action-registry.json (the canonical
    action set generated from contract-registry.json). Scope is deliberately
    restricted to the §5 action-declaration bullets (`- `ak.<...>``) so that
    event kinds, grandfathered old names in the §5.0 deviation table, and prose
    `ak.*` tokens elsewhere cannot produce false positives — closing the
    hand-maintained-list drift (e.g. ak.object.read_history) at its root."""
    registry_path = ARTIFACTS / "registry" / "capability-action-registry.json"
    data = load_json(lint, registry_path)
    if not isinstance(data, dict):
        return
    known = {
        a.get("action")
        for a in data.get("actions", [])
        if isinstance(a, dict) and isinstance(a.get("action"), str)
    }
    rows_by_action = {
        a.get("action"): a
        for a in data.get("actions", [])
        if isinstance(a, dict) and isinstance(a.get("action"), str)
    }
    path = SPEC_ROOT / "zh" / "authz" / "capabilities.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        lint.fail(path, "capabilities.md not readable for action-reference closure")
        return
    in_section = False
    in_code = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if stripped.startswith("## "):
            # Enter the action catalogue on "## 5." and leave on the next H2.
            in_section = stripped.startswith("## 5.") or stripped.startswith("## 5 ")
            continue
        if not in_section:
            continue
        match = _PROSE_ACTION_BULLET_RE.match(line)
        if not match:
            continue
        action = match.group(1)
        if not _ACTION_TOKEN_RE.match(action):
            continue
        if action in known or action in ALLOWED_PROSE_ACTIONS:
            target_match = _PROSE_ACTION_TARGET_RE.search(line)
            if target_match and action in rows_by_action:
                raw_targets = target_match.group(1).strip().strip("{}")
                prose_targets = sorted(
                    target.strip() for target in raw_targets.split(",") if target.strip()
                )
                registry_targets = sorted(rows_by_action[action].get("target_event_kinds") or [])
                if prose_targets != registry_targets:
                    lint.fail(
                        path,
                        f"capabilities.md §5 action {action!r} declares target={prose_targets} "
                        f"but capability-action-registry.json declares {registry_targets}",
                    )
            continue
        lint.fail(
            path,
            f"capabilities.md §5 declares action {action!r} not present in "
            f"capability-action-registry.json (hand-list drift)",
        )


# --- C-BET-04: non-normative frontmatter sanity gate -------------------------

# Files that declare `normative: false` yet legitimately surface RFC 2119
# keywords (informative guides quoting requirements, the spec map, the OpenAPI
# view) are waived here. Each entry records why the exemption exists so the
# waiver list can shrink as the underlying arkret-work/review/spec-open findings are resolved.
NON_NORMATIVE_KEYWORD_WAIVERS: dict[str, str] = {
    # Informative migration/consumption/reference guides that quote the wire
    # contract's MUST/SHOULD requirements as reading aids, not as the
    # authoritative source (authority stays in the referenced normative docs).
    "spec/v1/zh/guides/artifact-consumption.md": "informative 指南，引用规范要求作为阅读辅助",
    "spec/v1/zh/guides/migrating-from-matrix.md": "informative 迁移指南，明确以正式规范小节的 MUST/SHOULD 为准",
    "spec/v1/zh/guides/reference-implementation-guide.md": "informative 参考实现指南，引用规范要求",
    # OpenAPI binding view; the mdx itself states authority is
    # service-http-binding.md / api-conventions.md.
    "spec/v1/zh/sync/service-api-schema.mdx": "OpenAPI binding 视图（informative），权威来源为 service-http-binding.md / api-conventions.md",
}

_NORMATIVE_KEYWORD_RE = re.compile(r"\b(MUST NOT|MUST|SHOULD NOT|SHOULD)\b")
_NORMATIVE_HEADING_RE = re.compile(r"^#{1,6}\s+.*normative", re.IGNORECASE)
_FRONTMATTER_BLOCK_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
C_BET_04_REQUIRED_FRONTMATTER = {"title", "status", "normative", "stability", "updated"}


def _parse_frontmatter_block(text: str) -> tuple[dict[str, Any] | None, str]:
    """Return (frontmatter dict or None, body-after-frontmatter)."""
    match = _FRONTMATTER_BLOCK_RE.match(text)
    if not match:
        return None, text
    body = text[match.end():]
    if yaml is None:
        return {}, body
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except Exception:
        return {}, body
    return (data if isinstance(data, dict) else {}), body


def _strip_code_for_keyword_scan(body: str) -> tuple[str, list[str]]:
    """Drop fenced code blocks and inline code; keep heading lines separately."""
    kept: list[str] = []
    heading_lines: list[str] = []
    in_code = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if _NORMATIVE_HEADING_RE.match(line):
            heading_lines.append(line.strip())
        kept.append(re.sub(r"`[^`]*`", "", line))
    return "\n".join(kept), heading_lines


def check_non_normative_frontmatter(lint: Lint) -> None:
    """C-BET-04: guard `normative: false` prose against undeclared requirements.

    Scans every ``spec/v1/zh/**/*.md`` and ``*.mdx`` file's frontmatter. A file
    that declares ``normative: false`` but contains RFC 2119 keywords
    (MUST / MUST NOT / SHOULD / SHOULD NOT, outside code spans) or a heading that
    declares a ``normative`` subsection MUST appear on the waiver list
    (``NON_NORMATIVE_KEYWORD_WAIVERS``) or it is an error. Files missing the
    required spec frontmatter metadata are also errors.

    The waiver mechanism keeps this gate green on the current tree (the known
    C-CON-01 finding on spec-map.md plus the informative guides and the OpenAPI
    view) while still catching *new* non-normative files that drift into carrying
    unscoped normative language.
    """
    zh_root = SPEC_ROOT / "zh"
    if not zh_root.exists():
        return
    files = sorted(set(zh_root.rglob("*.md")) | set(zh_root.rglob("*.mdx")))
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        rel = lint.rel(path)
        fm, body = _parse_frontmatter_block(text)

        if fm is None:
            lint.fail(path, "C-BET-04: missing frontmatter (spec metadata required)")
            continue

        missing = C_BET_04_REQUIRED_FRONTMATTER - set(fm.keys())
        for key in sorted(missing):
            lint.fail(path, f"C-BET-04: frontmatter missing required field '{key}'")

        # `normative` must be present and boolean-typed.
        normative_value = fm.get("normative")
        if "normative" in fm and not isinstance(normative_value, bool):
            lint.fail(
                path,
                f"C-BET-04: frontmatter 'normative' must be a boolean, got {normative_value!r}",
            )

        if normative_value is not False:
            continue

        scrubbed, heading_lines = _strip_code_for_keyword_scan(body)
        keywords = sorted(set(_NORMATIVE_KEYWORD_RE.findall(scrubbed)))
        if not keywords and not heading_lines:
            continue

        if rel in NON_NORMATIVE_KEYWORD_WAIVERS:
            continue

        detail_parts: list[str] = []
        if keywords:
            detail_parts.append(f"RFC 2119 keyword(s) {keywords}")
        if heading_lines:
            detail_parts.append(f"normative section heading(s) {heading_lines}")
        lint.fail(
            path,
            "C-BET-04: normative:false document contains "
            + " and ".join(detail_parts)
            + " -- scope the requirement to a normative doc or add an explicit "
            "waiver in NON_NORMATIVE_KEYWORD_WAIVERS.",
        )


def check_normative_prose_role_names(lint: Lint) -> None:
    """Keep normative prose bound to protocol roles rather than implementations."""
    zh_root = SPEC_ROOT / "zh"
    if not zh_root.exists():
        return
    forbidden = {
        "cotest::": "private runner module path",
        "cotest scanner": "implementation-specific scanner role",
        "teabay Directory": "implementation-specific Directory Service role",
    }
    files = sorted(set(zh_root.rglob("*.md")) | set(zh_root.rglob("*.mdx")))
    for path in files:
        text = path.read_text(encoding="utf-8")
        frontmatter, body = _parse_frontmatter_block(text)
        if not isinstance(frontmatter, dict) or frontmatter.get("normative") is not True:
            continue
        for token, label in forbidden.items():
            if token in body:
                lint.fail(path, f"normative prose contains {label}: {token!r}")


def check_device_messages_cursor_binding(lint: Lint) -> None:
    """Keep the to-device queue continuation parameter canonical across surfaces."""
    openapi_path = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    operation = (
        openapi.get("paths", {}).get("/_arkret/self/device_messages", {}).get("get", {})
        if isinstance(openapi, dict)
        else {}
    )
    parameters = operation.get("parameters", []) if isinstance(operation, dict) else []
    query_names = {
        row.get("name")
        for row in parameters
        if isinstance(row, dict) and row.get("in") == "query" and isinstance(row.get("name"), str)
    }
    for required in ("after", "limit"):
        if required not in query_names:
            lint.fail(openapi_path, f"device_messages GET missing canonical query parameter {required!r}")
    for forbidden in ("from", "start_at"):
        if forbidden in query_names:
            lint.fail(openapi_path, f"device_messages GET exposes forbidden cursor alias {forbidden!r}")

    legacy_patterns = (
        re.compile(r"self/device_messages\?from="),
        re.compile(r"device_messages(?:\.query\.list)?\?from="),
        re.compile(r"query\.from"),
        re.compile(r"device_messages from="),
    )
    for root in (SPEC_ROOT / "zh", ARTIFACTS):
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".yaml", ".yml"}:
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in legacy_patterns:
                if pattern.search(text):
                    lint.fail(path, f"device_messages uses forbidden cursor alias: {pattern.pattern}")


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


def websocket_canonical_wss_errors(value: object) -> list[str]:
    """Return profile-level canonicalization errors for a WebSocket base URL."""
    if not isinstance(value, str):
        return ["value is not a string"]
    errors: list[str] = []
    if len(value.encode("utf-8")) > 2048:
        errors.append("UTF-8 form exceeds 2048 bytes")
    if not value.isascii():
        errors.append("URI must use an ASCII DNS A-label host")
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError as exc:
        return [f"URI cannot be parsed: {exc}"]
    if parsed.scheme != "wss" or not value.startswith("wss://"):
        errors.append("scheme must be lowercase wss")
    if parsed.query or parsed.fragment:
        errors.append("query and fragment are forbidden")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        errors.append("userinfo is forbidden")
    authority = parsed.netloc.rsplit("@", 1)[-1]
    raw_host = authority.rsplit(":", 1)[0] if ":" in authority and not authority.startswith("[") else authority
    host = parsed.hostname
    if not host:
        errors.append("DNS host is required")
    else:
        if raw_host != raw_host.lower():
            errors.append("DNS host must be lowercase")
        if host.endswith("."):
            errors.append("DNS host trailing dot is forbidden")
        if ":" in host:
            errors.append("IP literals are not DNS A-label hosts")
        labels = host.split(".")
        if (
            any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)
            or len(host) > 253
        ):
            errors.append("host is not a valid lowercase DNS A-label name")
    try:
        port = parsed.port
    except ValueError as exc:
        errors.append(f"port is invalid: {exc}")
        port = None
    if ":" in authority and not authority.startswith("["):
        port_text = authority.rsplit(":", 1)[1]
        if not re.fullmatch(r"[1-9][0-9]{0,4}", port_text):
            errors.append("explicit port must be non-zero decimal without leading zeros")
        if port == 443:
            errors.append("default port 443 must be omitted")
    if port is not None and not 1 <= port <= 65535:
        errors.append("port is outside 1..65535")
    path_value = parsed.path
    if not path_value or not path_value.startswith("/"):
        errors.append("non-empty absolute path is required")
    if any(segment in {".", ".."} for segment in path_value.split("/")):
        errors.append("dot segments are forbidden")
    unreserved = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
    index = 0
    while index < len(path_value):
        if path_value[index] != "%":
            index += 1
            continue
        escape = path_value[index : index + 3]
        if not re.fullmatch(r"%[0-9A-F]{2}", escape):
            errors.append("percent escapes must be complete and use uppercase hexadecimal")
            index += 1
            continue
        if chr(int(escape[1:], 16)) in unreserved:
            errors.append("unreserved path characters must not be percent-encoded")
        index += 3
    return errors


def check_websocket_binding_fixture(lint: Lint) -> None:
    """Execute the in-tree, tool-neutral portion of the WebSocket binding suite."""
    path = ARTIFACTS / "fixtures" / "websocket-binding-fixture.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    discovery_cases = data.get("discovery_cases")
    if not isinstance(discovery_cases, list):
        lint.fail(path, "discovery_cases must be an array")
        return
    discovery_by_name = {
        case.get("name"): case
        for case in discovery_cases
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    required_discovery_names = {
        "closed_descriptor",
        "partial_operations_rejected",
        "noncanonical_or_credentialed_url_rejected",
        "missing_subprotocol_or_limit_rejected",
    }
    if set(discovery_by_name) != required_discovery_names:
        lint.fail(path, f"discovery_cases names drift: {sorted(set(discovery_by_name))}")
    descriptor_case = discovery_by_name.get("closed_descriptor") or {}
    descriptor = descriptor_case.get("instance")
    descriptor_schema_ref = descriptor_case.get("schema_ref")
    if not isinstance(descriptor, dict) or not isinstance(descriptor_schema_ref, str):
        lint.fail(path, "closed_descriptor requires instance and schema_ref")
    else:
        check_json_instance_against_schema(
            lint,
            path,
            "closed_descriptor",
            descriptor_schema_ref,
            descriptor,
        )
        canonical_errors = websocket_canonical_wss_errors(descriptor.get("base_url"))
        if canonical_errors:
            lint.fail(path, "closed_descriptor base_url is not canonical: " + "; ".join(canonical_errors))

        partial = copy.deepcopy(descriptor)
        partial["operations"] = [
            operation
            for operation in partial.get("operations", [])
            if operation != "ak.self.signal.stream.subscribe"
        ]
        check_json_instance_against_schema(
            lint,
            path,
            "partial_operations_rejected",
            descriptor_schema_ref,
            partial,
            expect_valid=False,
        )

        missing_case = discovery_by_name.get("missing_subprotocol_or_limit_rejected") or {}
        remove_each = missing_case.get("remove_each")
        if not isinstance(remove_each, list) or set(remove_each) != {
            "subprotocol",
            "authentication",
            "max_frame_bytes",
            "max_channels",
        }:
            lint.fail(path, "missing_subprotocol_or_limit_rejected remove_each drift")
        else:
            for field in remove_each:
                mutation = copy.deepcopy(descriptor)
                mutation.pop(field, None)
                check_json_instance_against_schema(
                    lint,
                    path,
                    f"missing descriptor field {field}",
                    descriptor_schema_ref,
                    mutation,
                    expect_valid=False,
                )

    url_case = discovery_by_name.get("noncanonical_or_credentialed_url_rejected") or {}
    rejected_urls = url_case.get("base_urls")
    if not isinstance(rejected_urls, list) or not rejected_urls:
        lint.fail(path, "noncanonical URL case requires base_urls")
    else:
        for value in rejected_urls:
            if not websocket_canonical_wss_errors(value):
                lint.fail(path, f"noncanonical base_url vector is canonical: {value!r}")
            if isinstance(descriptor, dict) and isinstance(descriptor_schema_ref, str):
                mutation = copy.deepcopy(descriptor)
                mutation["base_url"] = value
                check_json_instance_against_schema(
                    lint,
                    path,
                    f"noncanonical base_url {value!r}",
                    descriptor_schema_ref,
                    mutation,
                    expect_valid=False,
                )

    kat = data.get("dpop_kat")
    if not isinstance(kat, dict):
        lint.fail(path, "dpop_kat must be an object")
        return
    decoded = kat.get("decoded")
    check_json_instance_against_schema(
        lint,
        path,
        "dpop_kat.decoded",
        "schemas/websocket-dpop-proof.schema.json",
        decoded,
    )
    if not isinstance(decoded, dict):
        return
    protected = decoded.get("protected")
    claims = decoded.get("claims")
    if not isinstance(protected, dict) or not isinstance(claims, dict):
        lint.fail(path, "dpop_kat.decoded must contain protected and claims objects")
        return
    if protected.get("jwk") != kat.get("public_jwk"):
        lint.fail(path, "dpop_kat protected jwk must equal public_jwk")
    if claims.get("htu") != kat.get("base_url"):
        lint.fail(path, "dpop_kat htu must equal the advertised base_url verbatim")
    canonical_htu_errors = websocket_canonical_wss_errors(claims.get("htu"))
    if canonical_htu_errors:
        lint.fail(path, "dpop_kat htu is not canonical: " + "; ".join(canonical_htu_errors))
    if claims.get("nonce") != kat.get("nonce"):
        lint.fail(path, "dpop_kat nonce must equal the challenge nonce")

    def fixture_timestamp(value: object, label: str) -> datetime | None:
        if not isinstance(value, str):
            lint.fail(path, f"{label} must be an RFC 3339 timestamp")
            return None
        try:
            return datetime.fromisoformat(value.removesuffix("Z") + ("+00:00" if value.endswith("Z") else ""))
        except ValueError:
            lint.fail(path, f"{label} is not an RFC 3339 timestamp")
            return None

    issued_at = fixture_timestamp(kat.get("issued_at"), "dpop_kat.issued_at")
    expires_at = fixture_timestamp(kat.get("expires_at"), "dpop_kat.expires_at")
    if issued_at is not None and expires_at is not None:
        if not 0 < (expires_at - issued_at).total_seconds() <= 5:
            lint.fail(path, "dpop_kat challenge window must be greater than zero and at most 5 seconds")
        if claims.get("iat") != int(issued_at.timestamp()):
            lint.fail(path, "dpop_kat iat must equal issued_at NumericDate")

    challenge_state = kat.get("challenge_state")
    if not isinstance(challenge_state, dict):
        lint.fail(path, "dpop_kat challenge_state must be an object")
    else:
        expected_challenge_key = [kat.get("connection_id"), kat.get("nonce")]
        if challenge_state.get("key") != expected_challenge_key:
            lint.fail(path, "dpop_kat challenge_state key must be [connection_id, nonce]")
        for field in ("canonical_origin", "canonical_base_url", "issued_at", "expires_at"):
            expected_field = {
                "canonical_origin": kat.get("origin"),
                "canonical_base_url": kat.get("base_url"),
                "issued_at": kat.get("issued_at"),
                "expires_at": kat.get("expires_at"),
            }[field]
            if challenge_state.get(field) != expected_field:
                lint.fail(path, f"dpop_kat challenge_state {field} drift")
        if challenge_state.get("consumed") is not False:
            lint.fail(path, "dpop_kat initial challenge_state must be unconsumed")

    canonical_protected = json.dumps(
        protected,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    canonical_claims = json.dumps(
        claims,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if kat.get("protected_json_utf8") != canonical_protected:
        lint.fail(path, "dpop_kat protected_json_utf8 is not canonical JSON")
    if kat.get("claims_json_utf8") != canonical_claims:
        lint.fail(path, "dpop_kat claims_json_utf8 is not canonical JSON")

    def b64url(data_bytes: bytes) -> str:
        return base64.urlsafe_b64encode(data_bytes).rstrip(b"=").decode("ascii")

    protected_segment = b64url(canonical_protected.encode("utf-8"))
    claims_segment = b64url(canonical_claims.encode("utf-8"))
    signing_input = protected_segment + "." + claims_segment
    if kat.get("protected_base64url") != protected_segment:
        lint.fail(path, "dpop_kat protected_base64url drift")
    if kat.get("claims_base64url") != claims_segment:
        lint.fail(path, "dpop_kat claims_base64url drift")
    if kat.get("signing_input_ascii") != signing_input:
        lint.fail(path, "dpop_kat signing_input_ascii drift")
    signature = kat.get("signature_base64url")
    if not isinstance(signature, str) or len(signature) != 86:
        lint.fail(path, "dpop_kat signature must encode one 64-byte Ed25519 signature")
    elif kat.get("compact_jws") != signing_input + "." + signature:
        lint.fail(path, "dpop_kat compact_jws does not match its declared segments")
    else:
        try:
            signature_bytes = base64.urlsafe_b64decode(signature + "==")
        except (ValueError, TypeError):
            signature_bytes = b""
        if len(signature_bytes) != 64:
            lint.fail(path, "dpop_kat signature_base64url does not decode to 64 bytes")
    private_seed_hex = kat.get("private_seed_hex")
    if not isinstance(private_seed_hex, str) or not re.fullmatch(r"[0-9a-f]{64}", private_seed_hex):
        lint.fail(path, "dpop_kat private_seed_hex must encode one 32-byte public test seed")

    grant = kat.get("session_grant")
    if not isinstance(grant, str):
        lint.fail(path, "dpop_kat session_grant must be a string")
    else:
        expected_ath = b64url(hashlib.sha256(grant.encode("ascii")).digest())
        if claims.get("ath") != expected_ath:
            lint.fail(path, "dpop_kat ath does not bind the ASCII session grant")

    public_jwk = kat.get("public_jwk")
    if isinstance(public_jwk, dict):
        canonical_jwk = json.dumps(
            public_jwk,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        expected_jkt = b64url(hashlib.sha256(canonical_jwk.encode("utf-8")).digest())
        if kat.get("cnf_jkt") != expected_jkt:
            lint.fail(path, "dpop_kat cnf_jkt is not the RFC 7638 JWK thumbprint")
        expected_replay_key = [expected_jkt, claims.get("jti"), "ak.websocket-auth.v1"]
        if kat.get("expected_replay_ledger_key") != expected_replay_key:
            lint.fail(path, "dpop_kat replay ledger key drift")
    else:
        lint.fail(path, "dpop_kat public_jwk must be an object")

    dpop_negative_cases = data.get("dpop_negative_cases")
    if not isinstance(dpop_negative_cases, list):
        lint.fail(path, "dpop_negative_cases must be an array")
        dpop_negative_cases = []
    dpop_by_name = {
        case.get("name"): case
        for case in dpop_negative_cases
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    required_dpop_negative = {
        "http_validator_must_not_accept_application_context",
        "wrong_htu_scheme",
        "wrong_method_token",
        "wrong_ath",
        "wrong_nonce",
        "connection_id_mismatch",
        "origin_mismatch",
        "expired_challenge",
        "replayed_nonce_and_jti",
        "unknown_claim",
        "holder_thumbprint_mismatch",
    }
    if set(dpop_by_name) != required_dpop_negative:
        lint.fail(path, f"dpop_negative_cases names drift: {sorted(set(dpop_by_name))}")
    for name, case in dpop_by_name.items():
        if case.get("expected") != "rejected":
            lint.fail(path, f"dpop negative {name} must expect rejected")

    proof_schema_ref = kat.get("proof_schema_ref")
    if not isinstance(proof_schema_ref, str):
        lint.fail(path, "dpop_kat proof_schema_ref must be a string")
    else:
        if proof_schema_ref != "schemas/websocket-dpop-proof.schema.json":
            lint.fail(path, "dpop_kat proof_schema_ref drift")
        for value in (rejected_urls if isinstance(rejected_urls, list) else []):
            mutation = copy.deepcopy(decoded)
            mutation["claims"]["htu"] = value
            check_json_instance_against_schema(
                lint,
                path,
                f"dpop noncanonical htu {value!r}",
                proof_schema_ref,
                mutation,
                expect_valid=False,
            )
        for name in ("wrong_htu_scheme", "wrong_method_token", "unknown_claim"):
            case = dpop_by_name.get(name) or {}
            mutation = copy.deepcopy(decoded)
            if isinstance(case.get("replace_claim"), dict):
                mutation["claims"].update(case["replace_claim"])
            if isinstance(case.get("add_claim"), dict):
                mutation["claims"].update(case["add_claim"])
            check_json_instance_against_schema(
                lint,
                path,
                f"dpop negative {name}",
                proof_schema_ref,
                mutation,
                expect_valid=False,
            )

    if (dpop_by_name.get("http_validator_must_not_accept_application_context") or {}).get(
        "validator_context"
    ) != "http_request_dpop":
        lint.fail(path, "HTTP DPoP isolation negative must select http_request_dpop")
    wrong_ath = ((dpop_by_name.get("wrong_ath") or {}).get("replace_claim") or {}).get("ath")
    if not isinstance(wrong_ath, str) or wrong_ath == claims.get("ath"):
        lint.fail(path, "wrong_ath negative must replace ath with a distinct value")
    wrong_nonce = ((dpop_by_name.get("wrong_nonce") or {}).get("replace_claim") or {}).get("nonce")
    if not isinstance(wrong_nonce, str) or wrong_nonce == kat.get("nonce"):
        lint.fail(path, "wrong_nonce negative must replace nonce with a distinct value")
    if (dpop_by_name.get("connection_id_mismatch") or {}).get(
        "authenticate_connection_id"
    ) == kat.get("connection_id"):
        lint.fail(path, "connection_id_mismatch negative does not mismatch")
    if (dpop_by_name.get("origin_mismatch") or {}).get("socket_origin") == kat.get("origin"):
        lint.fail(path, "origin_mismatch negative does not mismatch")
    expired_verification = fixture_timestamp(
        (dpop_by_name.get("expired_challenge") or {}).get("verification_time"),
        "expired_challenge.verification_time",
    )
    if expires_at is not None and (
        expired_verification is None or expired_verification <= expires_at
    ):
        lint.fail(path, "expired_challenge verification_time must be after expires_at")
    replay_case = dpop_by_name.get("replayed_nonce_and_jti") or {}
    if replay_case.get("challenge_consumed") is not True or replay_case.get(
        "replay_ledger_key_present"
    ) is not True:
        lint.fail(path, "replay negative must exercise consumed challenge and present ledger key")
    if (dpop_by_name.get("holder_thumbprint_mismatch") or {}).get(
        "grant_cnf_jkt"
    ) == kat.get("cnf_jkt"):
        lint.fail(path, "holder_thumbprint_mismatch negative does not mismatch")

    parsed_frame_cases: dict[str, dict[str, Any]] = {}
    frame_cases = data.get("frame_schema_cases")
    if not isinstance(frame_cases, list) or not frame_cases:
        lint.fail(path, "frame_schema_cases must be a non-empty array")
    else:
        advertised_limit = ((data.get("limits") or {}).get("fixture_advertised_max_frame_bytes"))
        for index, case in enumerate(frame_cases):
            if not isinstance(case, dict):
                lint.fail(path, f"frame_schema_cases[{index}] must be an object")
                continue
            name = case.get("name")
            if not isinstance(name, str) or not name:
                lint.fail(path, f"frame_schema_cases[{index}] requires a name")
            elif name in parsed_frame_cases:
                lint.fail(path, f"duplicate frame_schema_cases name: {name}")
            else:
                parsed_frame_cases[name] = case
            wire = case.get("wire_utf8")
            schema_ref = case.get("direction_schema_ref")
            if not isinstance(wire, str) or not isinstance(schema_ref, str):
                lint.fail(path, f"frame_schema_cases[{index}] requires wire_utf8 and direction_schema_ref")
                continue
            if case.get("expect_valid") is not True:
                lint.fail(path, f"frame_schema_cases[{index}] must explicitly expect valid")
            if isinstance(advertised_limit, int) and len(wire.encode("utf-8")) > advertised_limit:
                lint.fail(path, f"frame_schema_cases[{index}] exceeds the advertised byte limit")
            try:
                duplicate_members: list[str] = []

                def collect_duplicate_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                    result: dict[str, Any] = {}
                    for key, value in pairs:
                        if key in result:
                            duplicate_members.append(key)
                        result[key] = value
                    return result

                instance = json.loads(wire, object_pairs_hook=collect_duplicate_members)
            except json.JSONDecodeError as exc:
                lint.fail(path, f"frame_schema_cases[{index}] wire_utf8 is invalid JSON: {exc}")
                continue
            if duplicate_members:
                lint.fail(path, f"frame_schema_cases[{index}] contains duplicate members")
            check_json_instance_against_schema(
                lint,
                path,
                f"frame_schema_cases[{index}]",
                schema_ref,
                instance,
                expect_valid=case.get("expect_valid") is True,
            )
            check_json_instance_against_schema(
                lint,
                path,
                f"frame_schema_cases[{index}] top-level union",
                "schemas/websocket-frame.schema.json",
                instance,
            )
            opposite_schema_ref = (
                "schemas/websocket-frame.schema.json#/$defs/client_frame"
                if schema_ref.endswith("/server_frame")
                else "schemas/websocket-frame.schema.json#/$defs/server_frame"
            )
            check_json_instance_against_schema(
                lint,
                path,
                f"frame_schema_cases[{index}] opposite direction",
                opposite_schema_ref,
                instance,
                expect_valid=False,
            )

        required_frame_cases = {
            "challenge",
            "authenticate",
            "welcome",
            "open_account",
            "open_events",
            "open_signal",
            "opened",
            "opened_events",
            "opened_signal",
            "account_data",
            "events_data",
            "signal_data",
            "channel_control",
            "signal_control",
            "channel_error",
            "connection_error",
            "client_close",
            "server_closed",
            "ping",
            "pong",
            "reauth_required",
            "connection_drain",
        }
        if set(parsed_frame_cases) != required_frame_cases:
            lint.fail(path, f"frame_schema_cases names drift: {sorted(set(parsed_frame_cases))}")
        authenticate_case = parsed_frame_cases.get("authenticate") or {}
        try:
            authenticate_instance = json.loads(authenticate_case.get("wire_utf8", "null"))
        except json.JSONDecodeError:
            authenticate_instance = None
        if not isinstance(authenticate_instance, dict) or authenticate_instance.get(
            "dpop_proof"
        ) != kat.get("compact_jws"):
            lint.fail(path, "authenticate frame must carry the exact DPoP KAT compact_jws")
        welcome_case = parsed_frame_cases.get("welcome") or {}
        try:
            welcome_instance = json.loads(welcome_case.get("wire_utf8", "null"))
        except json.JSONDecodeError:
            welcome_instance = None
        if not isinstance(welcome_instance, dict) or welcome_instance.get(
            "max_frame_bytes"
        ) != advertised_limit:
            lint.fail(path, "welcome max_frame_bytes must equal the fixture advertised limit")
        error_registry = load_json(lint, ARTIFACTS / "registry" / "error-code-registry.json")
        registered_error_codes = {
            row.get("code")
            for row in (error_registry or {}).get("codes", [])
            if isinstance(row, dict) and isinstance(row.get("code"), str)
        }
        for error_case_name in ("channel_error", "connection_error"):
            try:
                error_instance = json.loads(
                    (parsed_frame_cases.get(error_case_name) or {}).get("wire_utf8", "null")
                )
            except json.JSONDecodeError:
                error_instance = None
            error_code = (
                ((error_instance or {}).get("error") or {}).get("code")
                if isinstance(error_instance, dict)
                else None
            )
            if error_code not in registered_error_codes:
                lint.fail(path, f"{error_case_name} uses an unregistered error code: {error_code!r}")

    negative_cases = data.get("wire_negative_cases")
    if not isinstance(negative_cases, list) or not negative_cases:
        lint.fail(path, "wire_negative_cases must be a non-empty array")
        return
    by_name = {
        case.get("name"): case
        for case in negative_cases
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    required_negative = {
        "duplicate_member",
        "unknown_field",
        "non_ascii_session_grant",
        "wrong_direction",
        "binary_message",
        "oversize_before_json_parse",
        "data_on_unopened_channel",
        "payload_does_not_match_channel_operation",
    }
    if set(by_name) != required_negative:
        lint.fail(path, f"wire_negative_cases names drift: {sorted(set(by_name))}")

    duplicate_wire = (by_name.get("duplicate_member") or {}).get("wire_utf8")
    duplicate_seen = False
    if isinstance(duplicate_wire, str):
        def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            nonlocal duplicate_seen
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    duplicate_seen = True
                result[key] = value
            return result
        json.loads(duplicate_wire, object_pairs_hook=reject_duplicates)
    if not duplicate_seen:
        lint.fail(path, "duplicate_member vector does not contain a duplicate JSON member")

    for name in ("unknown_field", "non_ascii_session_grant", "wrong_direction"):
        case = by_name.get(name) or {}
        wire = case.get("wire_utf8")
        schema_ref = case.get("direction_schema_ref") or "schemas/websocket-frame.schema.json#/$defs/client_frame"
        if isinstance(wire, str):
            check_json_instance_against_schema(
                lint,
                path,
                name,
                schema_ref,
                json.loads(wire),
                expect_valid=False,
            )

    oversize = by_name.get("oversize_before_json_parse") or {}
    generator = oversize.get("generator")
    limit = oversize.get("advertised_max_frame_bytes")
    if not isinstance(generator, dict) or not isinstance(limit, int):
        lint.fail(path, "oversize vector requires generator and advertised_max_frame_bytes")
    else:
        total = generator.get("total_message_bytes")
        prefix = generator.get("prefix_utf8")
        repeated = generator.get("repeat_utf8")
        suffix = generator.get("suffix_utf8")
        if (
            not isinstance(total, int)
            or not isinstance(prefix, str)
            or not isinstance(repeated, str)
            or len(repeated.encode("utf-8")) != 1
            or not isinstance(suffix, str)
            or total != limit + 1
            or len(prefix.encode("utf-8")) + len(suffix.encode("utf-8")) >= total
        ):
            lint.fail(path, "oversize generator must materialize exactly limit + 1 UTF-8 bytes")

    expected_wire_close_codes = {
        "duplicate_member": 1002,
        "unknown_field": 1002,
        "non_ascii_session_grant": 1002,
        "wrong_direction": 1002,
        "binary_message": 1002,
        "oversize_before_json_parse": 1009,
        "data_on_unopened_channel": 1002,
    }
    for name, expected_close_code in expected_wire_close_codes.items():
        if (by_name.get(name) or {}).get("expected_close_code") != expected_close_code:
            lint.fail(path, f"{name} close code must be {expected_close_code}")
    binary_case = by_name.get("binary_message") or {}
    if binary_case.get("opcode") != "binary" or not re.fullmatch(
        r"(?:[0-9a-f]{2})+",
        binary_case.get("wire_hex", ""),
    ):
        lint.fail(path, "binary_message must contain lowercase even-length wire_hex and binary opcode")
    state_case = by_name.get("data_on_unopened_channel") or {}
    if state_case.get("rejection_stage") != "connection_state":
        lint.fail(path, "data_on_unopened_channel must fail at connection_state")
    operation_case = by_name.get("payload_does_not_match_channel_operation") or {}
    if (
        operation_case.get("channel_operation") != "ak.self.signal.stream.subscribe"
        or operation_case.get("rejection_stage") != "channel_operation_schema"
        or operation_case.get("connection_remains_open") is not True
    ):
        lint.fail(path, "payload mismatch negative must isolate the Signal channel")

    multiplex_trace = data.get("multiplex_trace")
    if not isinstance(multiplex_trace, dict):
        lint.fail(path, "multiplex_trace must be an object")
    else:
        sequence = multiplex_trace.get("frame_case_sequence")
        required_sequence = [
            "challenge",
            "authenticate",
            "welcome",
            "open_account",
            "opened",
            "open_events",
            "opened_events",
            "open_signal",
            "opened_signal",
            "account_data",
            "events_data",
            "channel_control",
            "signal_control",
            "channel_error",
            "server_closed",
        ]
        if sequence != required_sequence:
            lint.fail(path, "multiplex_trace frame_case_sequence drift")
        elif any(name not in parsed_frame_cases for name in sequence):
            lint.fail(path, "multiplex_trace references an unknown exact frame case")
        expected_state = multiplex_trace.get("expected")
        if not isinstance(expected_state, dict):
            lint.fail(path, "multiplex_trace expected state must be an object")
        else:
            try:
                account_data = json.loads(parsed_frame_cases["account_data"]["wire_utf8"])
                events_data = json.loads(parsed_frame_cases["events_data"]["wire_utf8"])
            except (KeyError, json.JSONDecodeError):
                account_data = {}
                events_data = {}
            if expected_state.get("account_cursor") != (
                (account_data.get("payload") or {}).get("cursor")
            ):
                lint.fail(path, "multiplex_trace account cursor does not come from account_data")
            if expected_state.get("events_cursor") != (
                (events_data.get("payload") or {}).get("cursor")
            ):
                lint.fail(path, "multiplex_trace events cursor does not come from events_data")
            if (
                expected_state.get("signal_cursor") is not None
                or expected_state.get("signal_catchup") is not False
                or expected_state.get("open_channels_after_events_close")
                != ["account-1", "signal-1"]
                or expected_state.get("channel_id_reuse") != "conflict"
                or expected_state.get("physical_connection_open") is not True
            ):
                lint.fail(path, "multiplex_trace isolation state drift")

    reauth_trace = data.get("reauth_trace")
    reauth_by_name = {
        case.get("name"): case
        for case in reauth_trace or []
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    if set(reauth_by_name) != {"fresh_reauth_succeeds", "old_proof_reuse_fails"}:
        lint.fail(path, f"reauth_trace names drift: {sorted(set(reauth_by_name))}")
    fresh_reauth = reauth_by_name.get("fresh_reauth_succeeds") or {}
    if (
        any(fresh_reauth.get(field) is not True for field in (
            "new_nonce",
            "new_jti",
            "new_session_grant",
            "new_ath",
        ))
        or not isinstance(fresh_reauth.get("authenticate_within_ms"), int)
        or fresh_reauth.get("authenticate_within_ms", 5001) > 5000
        or fresh_reauth.get("expected") != "channels_continue"
    ):
        lint.fail(path, "fresh_reauth_succeeds must refresh every proof input within 5 seconds")
    stale_reauth = reauth_by_name.get("old_proof_reuse_fails") or {}
    if (
        stale_reauth.get("reuse_old_nonce") is not True
        or stale_reauth.get("reuse_old_jti") is not True
        or stale_reauth.get("expected_close_code") != 1008
        or stale_reauth.get("old_authorization_continues") is not False
    ):
        lint.fail(path, "old_proof_reuse_fails semantics drift")

    close_traces = data.get("drain_and_close_traces")
    close_by_name = {
        case.get("name"): case
        for case in close_traces or []
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    expected_close_names = {
        "channel_error_isolated",
        "graceful_service_drain",
        "protocol_error",
        "policy_error_retry_once",
        "message_too_big",
        "restart_retry_budget",
    }
    if set(close_by_name) != expected_close_names:
        lint.fail(path, f"drain_and_close_traces names drift: {sorted(set(close_by_name))}")
    required_trace_codes = {
        "graceful_service_drain": 1001,
        "protocol_error": 1002,
        "message_too_big": 1009,
    }
    for name, code in required_trace_codes.items():
        if (close_by_name.get(name) or {}).get("expected_close_code") != code:
            lint.fail(path, f"{name} close code must be {code}")
    if (close_by_name.get("restart_retry_budget") or {}).get("attempts") != 3:
        lint.fail(path, "restart_retry_budget must fall back after three pre-welcome failures")

    fallback_cases = data.get("fallback_cases")
    fallback_by_name = {
        case.get("name"): case
        for case in fallback_cases or []
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    }
    if set(fallback_by_name) != {"upgrade_or_proxy_failure", "single_owner_transport_switch"}:
        lint.fail(path, f"fallback_cases names drift: {sorted(set(fallback_by_name))}")
    for name, case in fallback_by_name.items():
        if case.get("expected_transport") != "http_json":
            lint.fail(path, f"fallback case {name} must end on http_json")
    owner_switch = fallback_by_name.get("single_owner_transport_switch") or {}
    if (
        owner_switch.get("old_websocket_owner_closed") is not True
        or owner_switch.get("http_owner_started_after_old_owner_stopped") is not True
        or owner_switch.get("duplicate_consumers") is not False
        or owner_switch.get("signal_catchup_attempted") is not False
    ):
        lint.fail(path, "single_owner_transport_switch ordering drift")

    frame_schema = load_json(lint, ARTIFACTS / "schemas" / "websocket-frame.schema.json")
    definitions = set(((frame_schema or {}).get("$defs") or {}).keys())
    required_frame_definitions = {
        "challenge",
        "authenticate",
        "welcome",
        "open",
        "opened",
        "data",
        "control",
        "error",
        "close",
        "closed",
        "ping",
        "pong",
        "reauth_required",
        "server_frame",
        "client_frame",
    }
    missing = sorted(required_frame_definitions - definitions)
    if missing:
        lint.fail(path, f"websocket frame schema misses required definitions: {missing}")


def run_lint_phase(
    index: int,
    total: int,
    label: str,
    checks: list[tuple[str, Any]],
    *,
    quiet: bool,
    timing: bool,
) -> dict[str, Any]:
    if not quiet:
        print(f"[lint {index}/{total}] {label} ...", file=sys.stderr, flush=True)
    phase_started = time.perf_counter()
    results: dict[str, Any] = {}
    for name, check in checks:
        started = time.perf_counter()
        results[name] = check()
        if timing:
            print(
                f"  {name}: {time.perf_counter() - started:.3f}s",
                file=sys.stderr,
                flush=True,
            )
    if not quiet:
        print(
            f"[lint {index}/{total}] {label} done "
            f"({time.perf_counter() - phase_started:.2f}s)",
            file=sys.stderr,
            flush=True,
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="suppress phase progress")
    parser.add_argument(
        "--timing",
        action="store_true",
        help="print individual check timings in addition to phase progress",
    )
    args = parser.parse_args(argv)
    lint = Lint()
    started = time.perf_counter()

    for cached in (
        read_text,
        parse_json_file,
        parse_yaml_file,
        load_json_schema_for_uri,
        schema_format_checker,
    ):
        cached.cache_clear()

    phase_count = 6
    foundation = run_lint_phase(
        1,
        phase_count,
        "基础文件与规范注册表",
        [
            ("text_encoding", lambda: check_text_files_utf8_no_nul(lint)),
            ("registry_manifest", lambda: check_registry_manifest(lint)),
            ("timestamp_profile", lambda: check_timestamp_profile_single_source(lint)),
            ("proof_contexts", lambda: check_proof_context_registry(lint)),
            ("registries", lambda: check_registries(lint)),
            ("state_contract_closure", lambda: check_state_contract_closure(lint)),
            ("protocol_layers", lambda: check_protocol_layer_registry(lint)),
        ],
        quiet=args.quiet,
        timing=args.timing,
    )
    known = foundation["registries"]

    run_lint_phase(
        2,
        phase_count,
        "Schema、profile 与授权闭包",
        [
            ("schema_refs", lambda: check_schema_refs(lint, known)),
            ("profile_requirements", lambda: check_profile_requirements(lint, known)),
            ("sdk_conformance", lambda: check_sdk_conformance_contract(lint)),
            ("operation_clauses", lambda: check_operation_clause_registry(lint)),
            ("vector_groups", lambda: check_vector_group_requirements(lint, known)),
            ("event_schema_coverage", lambda: check_event_schema_coverage(lint, known)),
            ("wire_scope", lambda: check_wire_schema_no_bare_scope(lint)),
            (
                "preimage_event_identity",
                lambda: check_preimage_event_identity_commitments(lint),
            ),
            ("read_scope", lambda: check_read_scope_schema_closure(lint)),
            ("signed_objects", lambda: check_signed_object_closure(lint)),
            ("reducer_payloads", lambda: check_reducer_payload_closure(lint)),
            ("circle_membership", lambda: check_circle_membership_enum_single_source(lint)),
            ("null_cell_subject", lambda: check_null_cell_subject_wire_form(lint)),
            (
                "classification_contexts",
                lambda: check_classification_context_paths(lint),
            ),
            ("circle_lifecycle", lambda: check_circle_lifecycle_basis_vector(lint)),
            ("did_device", lambda: check_did_and_device_constraints(lint)),
        ],
        quiet=args.quiet,
        timing=args.timing,
    )

    run_lint_phase(
        3,
        phase_count,
        "OpenAPI 与 operation 绑定",
        [
            ("openapi_component_order", lambda: check_openapi_schema_component_order(lint)),
            ("operation_surfaces", lambda: check_operation_surfaces(lint, known)),
            (
                "operation_durable_effect",
                lambda: check_operation_durable_effect_contract(lint),
            ),
            ("service_describe", lambda: check_service_describe_alignment(lint)),
            ("policy_check", lambda: check_policy_check_alignment(lint)),
            ("dedicated_schemas", lambda: check_openapi_dedicated_operation_schemas(lint)),
            ("core_selectors", lambda: check_openapi_core_selector_constraints(lint)),
            ("openapi_auth", lambda: check_openapi_auth_semantics(lint)),
            ("openapi_errors", lambda: check_openapi_error_enum_alignment(lint)),
            ("binding_metadata", lambda: check_operation_binding_metadata(lint)),
            ("binding_index", lambda: check_binding_completeness_index(lint)),
            ("field_table_refs", lambda: check_operation_field_table_schema_refs(lint)),
            ("non_http_variants", lambda: check_binding_variant_non_http(lint)),
            ("capability_mapping", lambda: check_capability_action_event_mapping(lint)),
            ("event_admission", lambda: check_event_admission_coverage(lint)),
            ("dto_closure", lambda: check_operation_dto_closure(lint)),
        ],
        quiet=args.quiet,
        timing=args.timing,
    )

    run_lint_phase(
        4,
        phase_count,
        "Fixtures、样例与向量",
        [
            ("account_data_keys", lambda: check_account_data_key_registry(lint, known)),
            ("vector_registry", lambda: check_vector_registry(lint)),
            ("crypto_suite_kats", lambda: check_cryptographic_suite_kat_bindings(lint)),
            ("normative_clauses", lambda: check_normative_clause_registry(lint)),
            ("vector_refs", lambda: check_vector_reference_closure(lint)),
            ("security_fixture", lambda: check_security_closure_fixture(lint)),
            ("fixtures", lambda: check_fixtures(lint, known)),
            ("snapshot_merkle", lambda: check_snapshot_merkle_fixture(lint)),
            ("fixture_runner", lambda: check_fixture_runner_contract(lint)),
            ("websocket_binding", lambda: check_websocket_binding_fixture(lint)),
            ("crypto_signatures", lambda: check_crypto_signature_fixture(lint)),
            ("canonical_digests", lambda: check_canonical_digest_fixtures(lint)),
            ("batch_receipt", lambda: check_event_batch_receipt_normalization_vector(lint)),
            (
                "stated_preimage_digest",
                lambda: check_stated_preimage_matches_stated_digest(lint),
            ),
            ("encrypted_digest", lambda: check_encrypted_envelope_digest_vector(lint)),
            ("string_profiles", lambda: check_string_profile_format_vectors(lint)),
            ("one_of_branches", lambda: check_one_of_branch_discriminability(lint)),
            ("canonical_strings", lambda: check_declared_canonical_json_strings(lint)),
            ("reducer_profiles", lambda: check_reducer_profile_registry(lint)),
            ("mls_proof", lambda: check_mls_governance_proof_fixture(lint)),
        ],
        quiet=args.quiet,
        timing=args.timing,
    )

    run_lint_phase(
        5,
        phase_count,
        "正文引用与结构化命名",
        [
            ("text_targets", lambda: check_text_reference_targets(lint)),
            ("cross_source", lambda: check_cross_source_drift(lint, known)),
            ("markdown_links", lambda: check_markdown_links(lint)),
            ("markdown_examples", lambda: check_markdown_examples(lint, known)),
            ("naming_predicates", lambda: check_naming_predicates(lint)),
            ("profile_graph", lambda: check_profile_dependency_graph(lint)),
            ("field_matrix", lambda: check_common_object_field_matrix(lint)),
            ("keypackage_claim_proof_shape", lambda: check_keypackage_claim_proof_shape(lint)),
            ("event_proof_digest", lambda: check_event_proof_digest_shape(lint)),
            ("digest_alias", lambda: check_canonical_digest_alias(lint)),
            ("announce_ids", lambda: check_legacy_announce_id_form(lint)),
            ("directory_fields", lambda: check_directory_field_drift(lint)),
            ("typed_id_prose", lambda: check_typed_id_prose_consistency(lint)),
            (
                "event_log_signed_request",
                lambda: check_event_log_operations_carry_a_signed_event(lint),
            ),
            (
                "envelope_subject_sources",
                lambda: check_envelope_subject_source_whitelist(lint),
            ),
            ("join_policy_ids", lambda: check_join_policy_gate_id_uniqueness(lint)),
            ("composite_parts", lambda: check_content_composite_uses_parts(lint)),
            ("release_counts", lambda: check_release_readiness_counts(lint, known)),
            ("cross_doc_anchors", lambda: check_cross_doc_anchors(lint)),
            ("non_normative_frontmatter", lambda: check_non_normative_frontmatter(lint)),
            ("normative_roles", lambda: check_normative_prose_role_names(lint)),
            ("account_notification", lambda: check_account_notification_prose_schema_alignment(lint)),
        ],
        quiet=args.quiet,
        timing=args.timing,
    )

    run_lint_phase(
        6,
        phase_count,
        "错误、字段顺序与安全边界",
        [
            ("error_uniqueness", lambda: check_error_code_registry_uniqueness(lint)),
            ("error_mapping", lambda: check_operations_error_mapping_closure(lint)),
            ("fixture_reasons", lambda: check_fixture_reject_reason_closure(lint)),
            ("error_closure", lambda: check_error_code_closure(lint)),
            ("openapi_numbers", lambda: check_openapi_no_floating_number(lint)),
            ("field_order", lambda: check_field_order(lint)),
            ("required_field_tables", lambda: check_model_required_field_table_coverage(lint)),
            ("exporter_labels", lambda: check_exporter_label_registry(lint)),
            ("algs", lambda: check_alg_registry(lint)),
            ("mls_bounds", lambda: check_mls_governance_proof_bounds(lint)),
            ("mls_pq", lambda: check_mls_pq_suite_registration(lint)),
            ("service_kinds", lambda: check_service_kind_registry(lint)),
            ("action_refs", lambda: check_action_reference_closure(lint)),
            ("device_cursor", lambda: check_device_messages_cursor_binding(lint)),
        ],
        quiet=args.quiet,
        timing=args.timing,
    )

    if lint.warnings:
        print("Artifact registry lint warnings:", file=sys.stderr)
        for warning in lint.warnings:
            print(f"- {warning}", file=sys.stderr)

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
        f"{len(known['claimable_profiles'])} claimable profiles, "
        f"{len(known['profiles'])} profile id references, "
        f"{time.perf_counter() - started:.2f}s)."
    )
    return 0


def check_account_notification_prose_schema_alignment(lint: Lint) -> None:
    prose_path = SPEC_ROOT / "zh" / "sync" / "client-sync.md"
    schema_path = ARTIFACTS / "schemas" / "account-subscribe-frame.schema.json"
    prose = prose_path.read_text(encoding="utf-8")
    schema = load_json(lint, schema_path)
    if not isinstance(schema, dict):
        return
    notification_delta = schema.get("$defs", {}).get("notification_delta", {})
    required = notification_delta.get("required", [])
    properties = notification_delta.get("properties", {})
    canonical_field = "notification_kind"
    if canonical_field not in required or canonical_field not in properties:
        lint.fail(
            schema_path,
            "notification_delta must require the canonical notification_kind field",
        )
    canonical_shape = "{id, notification_kind, action, data?}"
    canonical_literal = '`notification_kind="agent"`'
    if canonical_shape not in prose or canonical_literal not in prose:
        lint.fail(
            prose_path,
            "account notification normative prose must match notification_delta.notification_kind",
        )
    if "{id, type, action, data?}" in prose or '`type="agent"`' in prose:
        lint.fail(
            prose_path,
            "legacy NotificationDelta.type is forbidden; use notification_kind",
        )


if __name__ == "__main__":
    raise SystemExit(main())
