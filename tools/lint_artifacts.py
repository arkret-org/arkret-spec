#!/usr/bin/env python3
"""Lint Cokret artifact/registry consistency.

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

EVENT_KIND_TOKEN_RE = re.compile(r"\bck\.[a-z0-9_]+(?:\.[a-z0-9_]+)+\b")
OPERATION_ID_RE = re.compile(r"^ck\.[a-z0-9_]+(?:\.[a-z0-9_]+)+$")
SCHEMA_ID_RE = re.compile(r"^ck\.schema\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\.v[0-9]+$")
SCHEMA_ID_TOKEN_RE = re.compile(r"\bck\.schema\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\.v[0-9]+\b")
PROFILE_ID_RE = re.compile(r"^ck\.profile\.[a-z0-9][a-z0-9_.-]*\.v[0-9]+$")
PROFILE_ID_TOKEN_RE = re.compile(r"\bck\.profile\.[a-z0-9][a-z0-9_.-]*\.v[0-9]+\b")
VECTOR_ID_TOKEN_RE = re.compile(r"\bck\.vector\.[a-z0-9_.-]+\.v[0-9]+\b")
TYPED_ID_TOKEN_RE = re.compile(r"\bck:([a-z0-9_]+):([A-Za-z0-9._~=-]+(?::[A-Za-z0-9._~=-]+)*)")
UUID7_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
OPENAPI_OPERATION_ID_RE = re.compile(r"^\s*operationId:\s*([A-Za-z0-9_.-]+)\s*$", re.MULTILINE)
YAML_REF_RE = re.compile(r"\$ref:\s*['\"]?([^'\"\s#]+(?:#[^'\"\s]+)?)")
JSON_FENCE_RE = re.compile(r"```json(?P<meta>[^\n`]*)\n(?P<body>.*?)```", re.IGNORECASE | re.DOTALL)
JSON_FENCE_SCHEMA_ATTR_RE = re.compile(r"\bschema=(?:\"([^\"]+)\"|'([^']+)'|([^\s]+))")
JSON_FENCE_EXPECT_ATTR_RE = re.compile(r"\bexpect=(valid|invalid)\b")
JSON_FENCE_FIRST_ERROR_ATTR_RE = re.compile(r"\bfirst_error=(?:\"([^\"]+)\"|'([^']+)'|([^\s]+))")
TYPED_ID_PREFIX_TOKEN_RE = re.compile(r"\bck:([a-z0-9_]+):")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+(?:#[^)]+)?)\)")
RULE_MARKER_EMOJI_RE = re.compile(r"[✅❌]")
CKP_ID_RE = re.compile(r"^CKP-[0-9]{4}$")
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
    "ck.vector.federation.idempotency_after_key_revoke.v1",
    "ck.vector.webrtc.media_plaintext_downgrade.v1",
    "ck.vector.identity_link.eager_invalidation.v1",
    "ck.vector.identity_link.policy_tightening_invalidation.v1",
    "ck.vector.late_key_recovery.removed_actor.v1",
    "ck.vector.invite.oob_code_entropy.v1",
    "ck.vector.invite.failure_indistinguishable.v1",
    "ck.vector.consent.scope_cascade.v1",
    "ck.vector.consent.cache_invalidation.v1",
    "ck.vector.sync.soft_fail_reconcile.v1",
    "ck.vector.lattice.lww_open_set.v1",
    "ck.vector.e2ee_relaxed.window_exceeds_ceiling.v1",
}

REGISTRY_LATTICES = {
    "or_set",
    "mv_register",
    "cas_register",
    "fsm",
    "counter",
    "ordered_log",
    "lww_register",
    "rga",
}
REGISTRY_BOTTOMS = {"reject", "expose"}
LIFECYCLE_UNSAFE_LATTICES = {"lww_register", "rga"}

FULL_MARKDOWN_EXAMPLE_SCHEMAS = {
    "spec/v1/zh/models/realm-and-space.md": {
        1: "schemas/realm.schema.json",
        2: "schemas/space.schema.json",
    },
    "spec/v1/zh/models/flow-and-message.md": {
        1: "schemas/flow.schema.json",
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


def text_contract_files() -> list[Path]:
    files: set[Path] = set(markdown_files())
    files.update(raw_artifact_files())
    files.update(sorted((SPEC_ROOT / "en").rglob("*.md")))
    files.add(ROOT / "CHANGELOG.md")
    files.add(ROOT / "site" / "src" / "lib" / "site-meta.ts")
    return sorted(path for path in files if path.is_file())


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

MIGRATION_BOOKKEEPING_FILES = {
    "renames.json",
    "forbidden-wire-fields.json",
    "removed-event-kinds.json",
}

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
    "requires_frank_verification": "requires_franking_proof_verification",
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
    "scope_ref": "scope_circle_id",
    "default_scope_ref": "default_scope_circle_id",
    "retention_policy_ref": "retention_policy_id",
    "disclosure_policy_ref": "disclosure_policy_id",
    "rate_limit_policy_ref": "rate_limit_policy_id",
    "policy_ref": "policy_id for Policy objects, or policy_event_ref for policy-revision Event references",
    "allowed_view_refs": "allowed_view_ids",
    "allowed_flow_refs": "allowed_flow_ids",
    "allowed_circle_refs": "allowed_circle_ids",
    "denied_flow_refs": "denied_flow_ids",
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
    "reducer_profile_hash": "reducer_profile_digest",
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

FORBIDDEN_NAMING_STRING_ALIASES = {
    "ck:notif:": "ck:notification:",
    "ck:devmsg:": "ck:device_message:",
    "ck:keyevt:": "ck:key_event:",
    "ck:modq:": "ck:moderation_queue_item:",
    "ck:req:": "ck:request:",
    "ck:txn:": "ck:transaction:",
    "ck:frank:": "ck:franking_proof:",
    "ck:rtcpart:": "ck:rtc_participant:",
    "ck.agent.key.authorized": "ck.agent.key.authorize",
    "ck.agent.key.revoked": "ck.agent.key.revoke",
    "ck.agent.key.rotated": "ck.agent.key.rotate",
    "ck.device.authorized": "ck.device.authorize",
    "ck.device.revoked": "ck.device.revoke",
    "ck.relation.delete": "ck.relation.tombstone",
    "ck.read.marker": "ck.read.cursor",
    "ck.schema.read_marker.v1": "ck.schema.read_cursor.v1",
    "or-set": "or_set",
    "mv-register": "mv_register",
    "cas-register": "cas_register",
    "ordered-log": "ordered_log",
    "lww-register": "lww_register",
    "frank_unavailable": "franking_proof_unavailable",
    "frank_only": "franking_proof_only",
    "routing_hash": "routing_digest",
    "http_message_signature_hash": "http_message_signature_digest",
    "Request-Canonical-Hash": "Request-Canonical-Digest",
    "unsupported_hash": "unsupported_digest_algorithm",
    "series_sequence": "series_seq",
    "series_sequence_not_monotonic": "series_seq_not_monotonic",
    "flow_body": "flow_content",
    "message_body": "message_content",
    "body_only": "content_only",
    "body-only E2EE": "content-only E2EE",
    "space_bound": "realm_bound",
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
    # verb_noun_bridge_collapse — capability action MUST equal target event kind
    "ck.invite.create_third_party": "ck.invite.third_party",
    "ck.policy.rule.manage": "ck.policy.rule",
    "ck.policy.action.manage": "ck.policy.action",
    "ck.realm.link.manage": "ck.realm.link",
    "ck.realm.plaintext_visible_services.modify": "ck.realm.plaintext_visible_services",
    "ck.realm.moderate": "ck.realm.moderation_policy",
    "parent_ref": "parent_space_id",
    "default_realm_ref": "default_realm_id",
    "scope_ref": "scope_circle_id",
    "default_scope_ref": "default_scope_circle_id",
    "require_scope_ref": "require_scope_circle_id",
    "retention_policy_ref": "retention_policy_id",
    "disclosure_policy_ref": "disclosure_policy_id",
    "rate_limit_policy_ref": "rate_limit_policy_id",
}


def is_migration_bookkeeping_file(path: Path) -> bool:
    return path.name in MIGRATION_BOOKKEEPING_FILES or path.name == "CHANGELOG.md"


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
        if is_migration_bookkeeping_file(path):
            continue
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


STRIKETHROUGH_RE = re.compile(r"~~[^~]+~~")


def check_forbidden_naming_aliases(lint: Lint) -> None:
    """Reject old names from the naming-normalization pass.

    The drift registries and changelog intentionally mention legacy spellings;
    current schemas, fixtures, OpenAPI, and prose examples must not. This guard
    catches schema/property-name regressions that JSON Schema alone cannot
    detect, especially exact legacy keys inside examples.
    """

    def check_key(path: Path, where: str, key: str | None) -> None:
        if not key:
            return
        replacement = FORBIDDEN_NAMING_ALIAS_KEYS.get(key)
        if replacement:
            lint.fail(path, f"{where} uses forbidden legacy field `{key}`; use `{replacement}`")

    def check_json_value(path: Path, data: Any, where: str = "$") -> None:
        for json_path, _value, key in walk_json(data, where):
            check_key(path, json_path, key)

    json_paths = [p for p in all_json_files() if not is_migration_bookkeeping_file(p)]
    for path in json_paths:
        data = load_json(lint, path)
        if data is not None:
            check_json_value(path, data)

    text_paths = markdown_files()
    text_paths.extend(
        path
        for path in raw_artifact_files()
        if path.suffix.lower() in {".json", ".yaml", ".yml", ".md"}
        and not is_migration_bookkeeping_file(path)
    )
    for path in text_paths:
        if is_migration_bookkeeping_file(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            # Documentation-conversion-table lines may legitimately quote both old and new names side by side.
            # Convention: strike-through the old name with markdown ~~...~~ around it. The strike-through marker
            # is the explicit signal "this is a deprecation table cell, not a live use of the legacy name".
            stripped = line
            if "~~" in stripped:
                stripped = STRIKETHROUGH_RE.sub("", stripped)
            for old, replacement in FORBIDDEN_NAMING_STRING_ALIASES.items():
                pattern = rf"(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])"
                if re.search(pattern, stripped):
                    lint.fail(path, f"line {line_no}: legacy name `{old}` appears; use `{replacement}`")

        for match in JSON_FENCE_RE.finditer(text):
            try:
                data = json.loads(match.group("body"))
            except Exception:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            check_json_value(path, data, f"json block line {line_no}")


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
    ``ck:announce:<uuidv7>``; keeping this guard prevents examples or fixtures
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
                    "use `ck:announce:<uuidv7>`.",
                )


def check_join_policy_gate_id_uniqueness(lint: Lint) -> None:
    """Enforce property-level gate_id uniqueness within join_policy gates[].

    JSON Schema 2020-12 has no native "unique by property" keyword: ``uniqueItems``
    only catches whole-object duplicates. The wire contract for
    ``ck.realm.join_policy`` (see zh/governance/join-policy.md §3.1) requires that
    ``gate_id`` be unique across siblings in ``gates[]`` so that audit refs in
    ``ck.member.state{gate_proofs[gate_id=…]}`` remain unambiguous; the canonical
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
    """Reject legacy ``blocks`` spelling on ck.content.composite examples.

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
            if obj.get("kind") != "ck.content.composite":
                return
            if "blocks" in obj:
                lint.fail(
                    path,
                    f"{where}: ck.content.composite uses legacy `blocks`; "
                    "canonical wire field is `parts`.",
                )
            if "parts" not in obj:
                lint.fail(
                    path,
                    f"{where}: ck.content.composite is missing required `parts`.",
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


def check_no_rule_marker_emoji(lint: Lint) -> None:
    for path in markdown_files():
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), 1):
            if RULE_MARKER_EMOJI_RE.search(line):
                lint.fail(
                    path,
                    f"line {line_number} uses emoji rule marker; use textual allowed/forbidden/included/excluded",
                )


def check_proposal_merge_manifest(lint: Lint) -> None:
    path = ARTIFACTS / "registry" / "proposal-merge-manifest.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    if data.get("source_of_truth") is not True:
        lint.fail(path, "source_of_truth must be true")
    if data.get("scope") != "accepted_merged_ckp_v1":
        lint.fail(path, "scope must be accepted_merged_ckp_v1")

    policy = data.get("policy")
    if not isinstance(policy, dict):
        lint.fail(path, "policy must be an object")
        policy = {}
    if policy.get("accepted_proposals_are_historical") is not True:
        lint.fail(path, "policy.accepted_proposals_are_historical must be true")

    forbidden = policy.get("formal_zh_refs_forbidden")
    forbidden_ckps: set[str] = set()
    if not isinstance(forbidden, list) or not forbidden:
        lint.fail(path, "policy.formal_zh_refs_forbidden must be a non-empty list")
    else:
        for index, value in enumerate(forbidden):
            if not isinstance(value, str) or not CKP_ID_RE.fullmatch(value):
                lint.fail(path, f"policy.formal_zh_refs_forbidden[{index}] must be CKP-NNNN")
                continue
            forbidden_ckps.add(value)

    rows = data.get("merged_proposals")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "merged_proposals must be a non-empty list")
        return

    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            lint.fail(path, f"merged_proposals[{index}] must be an object")
            continue
        ckp = row.get("ckp")
        if not isinstance(ckp, str) or not CKP_ID_RE.fullmatch(ckp):
            lint.fail(path, f"merged_proposals[{index}].ckp must be CKP-NNNN")
            continue
        if ckp in seen:
            lint.fail(path, f"duplicate proposal merge row for {ckp}")
        seen.add(ckp)
        if row.get("status") != "accepted_merged":
            lint.fail(path, f"{ckp}.status must be accepted_merged")

        proposal_file = row.get("proposal_file")
        if not isinstance(proposal_file, str) or not proposal_file.startswith("proposals/"):
            lint.fail(path, f"{ckp}.proposal_file must be a proposals/ path")
        elif Path(proposal_file).is_absolute() or ".." in Path(proposal_file).parts:
            lint.fail(path, f"{ckp}.proposal_file escapes spec/v1: {proposal_file}")
        elif not (SPEC_ROOT / proposal_file).exists():
            lint.fail(path, f"{ckp}.proposal_file does not exist: {proposal_file}")

        sections = row.get("merged_sections")
        if not isinstance(sections, list) or not sections:
            lint.fail(path, f"{ckp}.merged_sections must be a non-empty list")
            continue
        for section_index, section in enumerate(sections):
            if not isinstance(section, dict):
                lint.fail(path, f"{ckp}.merged_sections[{section_index}] must be an object")
                continue
            targets = section.get("targets")
            if not isinstance(targets, list) or not targets:
                lint.fail(path, f"{ckp}.merged_sections[{section_index}].targets must be non-empty")
                continue
            for target in targets:
                if not isinstance(target, str) or not target:
                    lint.fail(path, f"{ckp}.merged_sections[{section_index}] has non-string target")
                    continue
                if Path(target).is_absolute() or ".." in Path(target).parts:
                    lint.fail(path, f"{ckp} target escapes spec/v1: {target}")
                    continue
                if not (SPEC_ROOT / target).exists():
                    lint.fail(path, f"{ckp} target does not exist: {target}")

    if forbidden_ckps != seen:
        lint.fail(
            path,
            "policy.formal_zh_refs_forbidden must match merged_proposals ckps: "
            f"forbidden-only={sorted(forbidden_ckps - seen)}, rows-only={sorted(seen - forbidden_ckps)}",
        )

    accepted_merged_from_frontmatter: set[str] = set()
    for proposal_path in sorted((SPEC_ROOT / "proposals").glob("[0-9][0-9][0-9][0-9]-*.md")):
        try:
            text = proposal_path.read_text(encoding="utf-8")
        except Exception as exc:
            lint.fail(proposal_path, f"unable to read proposal frontmatter: {exc}")
            continue
        fm, _body = _parse_frontmatter_block(text)
        if not isinstance(fm, dict):
            lint.fail(proposal_path, "proposal missing frontmatter")
            continue
        ckp = fm.get("ckp")
        status = fm.get("status")
        merged_to = fm.get("merged_to")
        if status == "accepted" and isinstance(merged_to, list) and merged_to:
            if not isinstance(ckp, str) or not CKP_ID_RE.fullmatch(ckp):
                lint.fail(proposal_path, "accepted merged proposal frontmatter must declare ckp: CKP-NNNN")
                continue
            accepted_merged_from_frontmatter.add(ckp)

    missing_from_manifest = accepted_merged_from_frontmatter - seen
    if missing_from_manifest:
        lint.fail(
            path,
            "merged_proposals must include accepted proposal frontmatter with merged_to: "
            f"frontmatter-only={sorted(missing_from_manifest)}",
        )

    for zh_path in sorted((SPEC_ROOT / "zh").rglob("*.md")):
        try:
            text = zh_path.read_text(encoding="utf-8")
        except Exception:
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            for ckp in sorted(forbidden_ckps):
                if ckp in line:
                    lint.fail(
                        zh_path,
                        f"line {line_number}: accepted merged proposal {ckp} must not be "
                        "referenced from formal zh/ normative text; use proposal-merge-manifest.json "
                        "for history and link formal v1 sections instead.",
                    )




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
    kind_pattern = re.compile(event_registry.get("kind_pattern", r"^ck\.[a-z0-9_]+(\.[a-z0-9_]+)*$"))
    wire_scopes = set((event_registry.get("wire_scope_definitions") or {}).keys())
    for row in event_by_kind.values():
        kind = row["event_kind"]
        if not kind_pattern.fullmatch(kind):
            lint.fail(event_path, f"event_kind does not match kind_pattern: {kind}")
        wire_scope = row.get("wire_scope")
        if wire_scope not in wire_scopes:
            lint.fail(event_path, f"{kind} has unknown wire_scope {wire_scope!r}")
        lattice = row.get("lattice")
        if lattice is not None and lattice not in REGISTRY_LATTICES:
            lint.fail(event_path, f"{kind} has unknown lattice {lattice!r}")
        bottom = row.get("bottom")
        if bottom is not None and bottom not in REGISTRY_BOTTOMS:
            lint.fail(event_path, f"{kind} has unknown bottom {bottom!r}")
        cell_family = row.get("cell_family")
        lifecycle_status_cell = (
            isinstance(cell_family, str) and ".status." in cell_family
        ) or kind.rsplit(".", 1)[-1] in {"pause", "resume", "deactivate"}
        if lifecycle_status_cell and lattice in LIFECYCLE_UNSAFE_LATTICES:
            lint.fail(event_path, f"{kind} lifecycle/status cell must not use {lattice}")

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
        if isinstance(kind, str) and isinstance(wire_form, str) and not wire_form.startswith(f"ck:{kind}:"):
            lint.fail(id_path, f"{kind} wire_form must start with ck:{kind}:")

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
        http_only_variant = row.get("http_only_variant") is True
        if not isinstance(http, str) or not http:
            lint.fail(operation_path, f"{operation_id} missing http binding")
        else:
            operation_http_map[operation_id] = http
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
    claimable_profiles: set[str] = set()
    if isinstance(profile_registry, dict):
        for key in ("implementation_profiles", "deployment_profiles", "hardening_profiles", "vector_profiles"):
            values = profile_registry.get(key)
            if isinstance(values, list):
                claimable_profiles.update(
                    item for item in values if isinstance(item, str) and item.startswith("ck.profile.")
                )
    for _, value, _ in walk_json(profile_registry):
        if isinstance(value, str) and value.startswith("ck.profile."):
            if value in event_kinds:
                continue
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

    constraint_fields = set(
        constraint_schema.get("properties", {}).keys()
        if isinstance(constraint_schema, dict) and isinstance(constraint_schema.get("properties"), dict)
        else []
    )
    action_path = ARTIFACTS / "registry" / "capability-action-registry.json"
    action_registry = load_json(lint, action_path) or {}
    for row in action_registry.get("actions", []) if isinstance(action_registry, dict) else []:
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
        "id_kinds": id_kinds,
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
    }


def check_schema_refs(lint: Lint, known: dict[str, set[str]]) -> None:
    # Tracking files exist precisely to list identifiers that have been
    # removed / deprecated; their bodies necessarily contain ids that are no
    # longer in the canonical registries. Skip cross-reference checks on them.
    drift_tracking_files = {
        "removed-event-kinds.json",
        "removed-operation-ids.json",
        "deprecated-profile-ids.json",
        "renames.json",
        "forbidden-wire-fields.json",
    }
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
    for key in ("implementation_profiles", "deployment_profiles", "hardening_profiles", "vector_profiles"):
        values = data.get(key, [])
        if isinstance(values, list):
            declared_profiles.update(item for item in values if isinstance(item, str) and item.startswith("ck.profile."))

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
    "ck.member.state": "membership_payload",
    "ck.circle.update": "circle_patch_payload",
    "ck.space.update": "space_patch_payload",
    "ck.profile.space_override": "profile_realm_override_payload",
}


# Legitimate kind → payload-class pairs where multiple kinds intentionally
# share a "category" payload class (object_lifecycle, state, audit, view,
# invite, capability_grant, generic_standard, reaction, container_position,
# call, message_redact, relation_update, space_state_transition, flow_patch,
# object_patch). Adding a new dispatch that doesn't match the last-segment
# rule MUST add the pair here, forcing reviewer awareness of the rename.
LEGACY_SHARED_PAYLOAD_DISPATCH: set[tuple[str, str]] = {
    ("ck.actor.discovery", "state_payload"),
    ("ck.applet.discovery", "state_payload"),
    ("ck.attestation.range_completeness", "audit_payload"),
    ("ck.audit.epoch_key_destruction", "audit_payload"),
    ("ck.audit.ryw_receipt", "audit_payload"),
    ("ck.call.recording.start", "call_payload"),
    ("ck.call.state", "call_payload"),
    ("ck.capability.delegate", "capability_grant_payload"),
    ("ck.capability.derived", "capability_grant_payload"),
    ("ck.circle.archive", "object_lifecycle_payload"),
    ("ck.circle.restore", "object_lifecycle_payload"),
    ("ck.circle.tombstone", "object_lifecycle_payload"),
    ("ck.container.move_item", "container_position_payload"),
    ("ck.container.rebalance", "container_position_payload"),
    ("ck.did.proof", "state_payload"),
    ("ck.flow.archive", "object_lifecycle_payload"),
    ("ck.flow.restore", "object_lifecycle_payload"),
    ("ck.flow.tracks.update", "flow_patch_payload"),
    ("ck.flow.update", "flow_patch_payload"),
    ("ck.handle.discovery", "state_payload"),
    ("ck.identity.accountability_grant", "state_payload"),
    ("ck.identity.disclosure_policy", "state_payload"),
    ("ck.identity.disclosure_receipt", "state_payload"),
    ("ck.identity.presentation_request", "state_payload"),
    ("ck.identity.presentation_response", "state_payload"),
    ("ck.invite.accept", "invite_payload"),
    ("ck.invite.cancel", "invite_payload"),
    ("ck.invite.claim", "invite_payload"),
    ("ck.invite.create", "invite_payload"),
    ("ck.invite.revoke", "invite_payload"),
    ("ck.invite.third_party", "invite_payload"),
    ("ck.moderation.franking_proof", "audit_payload"),
    ("ck.morph.archive", "object_lifecycle_payload"),
    ("ck.morph.restore", "object_lifecycle_payload"),
    ("ck.morph.update", "object_patch_payload"),
    ("ck.organization.discovery", "state_payload"),
    ("ck.organization.moderation_policy", "state_payload"),
    ("ck.policy.action", "state_payload"),
    ("ck.policy.rule", "state_payload"),
    ("ck.policy.set", "state_payload"),
    ("ck.profile.update", "object_patch_payload"),
    ("ck.reaction.add", "reaction_payload"),
    ("ck.reaction.remove", "reaction_payload"),
    ("ck.realm.asset_privacy_policy", "state_payload"),
    ("ck.realm.audit_policy_downgrade", "audit_payload"),
    ("ck.realm.delivery_binding_policy", "state_payload"),
    ("ck.realm.discovery", "state_payload"),
    ("ck.realm.history_sharing_policy", "state_payload"),
    ("ck.realm.history_visibility", "state_payload"),
    ("ck.realm.join_rule", "state_payload"),
    ("ck.realm.link", "state_payload"),
    ("ck.realm.media_service", "state_payload"),
    ("ck.realm.moderation_policy", "state_payload"),
    ("ck.realm.organization", "state_payload"),
    ("ck.realm.policy", "state_payload"),
    ("ck.realm.policy_components", "state_payload"),
    ("ck.realm.policy_server", "state_payload"),
    ("ck.realm.read_receipt_policy", "state_payload"),
    ("ck.realm.schema", "state_payload"),
    ("ck.realm.update", "object_patch_payload"),
    ("ck.realm.upgrade", "state_payload"),
    ("ck.redaction", "message_redact_payload"),
    ("ck.relation.tombstone", "relation_update_payload"),
    ("ck.schema.define", "state_payload"),
    ("ck.schema.update", "state_payload"),
    ("ck.sovereign.did_policy", "state_payload"),
    ("ck.space.archive", "generic_standard_payload"),
    ("ck.space.archive", "space_state_transition_payload"),
    ("ck.space.create", "generic_standard_payload"),
    ("ck.space.parent", "generic_standard_payload"),
    ("ck.space.restore", "generic_standard_payload"),
    ("ck.space.restore", "space_state_transition_payload"),
    ("ck.space.tombstone", "generic_standard_payload"),
    ("ck.view.create", "view_payload"),
    ("ck.view.reconcile", "view_payload"),
    ("ck.view.update", "view_payload"),
}


def collect_payload_dispatch_pairs(value: Any) -> list[tuple[str, str]]:
    """Return [(kind, payload_class_name)] for every `if kind=const → then payload $ref` block."""
    pairs: list[tuple[str, str]] = []
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
            if isinstance(payload_schema, dict):
                ref = payload_schema.get("$ref")
                if isinstance(ref, str):
                    match = PAYLOAD_DISPATCH_REF_RE.search(ref)
                    if match:
                        class_name = match.group(1)
                        if_properties = if_schema.get("properties")
                        kind_schema = (
                            if_properties.get("kind")
                            if isinstance(if_properties, dict)
                            else None
                        )
                        for kind in collect_kind_selector_tokens(kind_schema):
                            if kind.startswith("ck."):
                                pairs.append((kind, class_name))
        for child in value.values():
            pairs.extend(collect_payload_dispatch_pairs(child))
    elif isinstance(value, list):
        for child in value:
            pairs.extend(collect_payload_dispatch_pairs(child))
    return pairs


def check_event_schema_coverage(lint: Lint, known: dict[str, set[str]]) -> None:
    path = ARTIFACTS / "schemas" / "event-envelope.schema.json"
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
        if token.startswith("ck.") and not SCHEMA_ID_RE.fullmatch(token) and not PROFILE_ID_RE.fullmatch(token)
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
        if token.startswith("ck.") and not SCHEMA_ID_RE.fullmatch(token) and not PROFILE_ID_RE.fullmatch(token)
    }
    for token in sorted(active_envelope_event_kinds - payload_dispatch_kinds):
        lint.fail(path, f"active Event.kind missing payload schema dispatch: {token}")

    # Mis-routed dispatch detector: each (kind, payload_class) pair must either
    # appear in KIND_PAYLOAD_RENAME_EXEMPTIONS verbatim, or embed the kind's
    # last dot-segment as a case-insensitive substring of the class name.
    # Catches typo / copy-paste errors like `ck.self.agent.pause → agent_resume_payload`.
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

        path_match = re.match(r"^  (/.*):\s*$", line)
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
    openapi_path = ARTIFACTS / "openapi" / "cokret-service-api.openapi.yaml"
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
    http_only_operation_ids = known.get("http_only_operation_ids", set())
    for operation_id in sorted(binding_operation_ids - known["operation_ids"]):
        lint.fail(binding_path, f"non-HTTP binding references unregistered operation_id: {operation_id}")
    for operation_id in sorted(binding_operation_ids & http_only_operation_ids):
        lint.fail(binding_path, f"http-only operation_id must not appear in non-HTTP bindings: {operation_id}")
    for operation_id in sorted(known["operation_ids"] - binding_operation_ids - http_only_operation_ids):
        lint.fail(binding_path, f"registered operation_id missing from non-HTTP bindings: {operation_id}")


def check_service_describe_alignment(lint: Lint) -> None:
    openapi_path = ARTIFACTS / "openapi" / "cokret-service-api.openapi.yaml"
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
        "/_cokret/describe",
        "/_cokret/self/events/describe",
        "/_cokret/root/identity/describe",
        "/_cokret/self/account/describe",
        "/_cokret/find/directory/describe",
        "/_cokret/edge/applet/describe",
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
    openapi_path = ARTIFACTS / "openapi" / "cokret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return
    paths = openapi.get("paths")
    components = openapi.get("components", {}).get("schemas", {})
    if not isinstance(paths, dict) or not isinstance(components, dict):
        return
    if "/cokret/v1/check" in paths:
        lint.fail(openapi_path, "legacy /cokret/v1/check policy path must not be present; use /_cokret/self/policy/check")

    policy_path = paths.get("/_cokret/self/policy/check", {}).get("post", {})
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
        lint.fail(openapi_path, "/_cokret/self/policy/check requestBody must reference PolicyCheckRequest")
    if response_schema != {"$ref": "#/components/schemas/PolicyCheckResponse"}:
        lint.fail(openapi_path, "/_cokret/self/policy/check 200 response must reference PolicyCheckResponse")

    request_component = resolve_openapi_component_schema(lint, openapi_path, components, "PolicyCheckRequest")
    response_component = resolve_openapi_component_schema(lint, openapi_path, components, "PolicyCheckResponse")
    if not isinstance(request_component, dict):
        lint.fail(openapi_path, "components.schemas.PolicyCheckRequest missing")
    elif "realm_id" not in set(request_component.get("required") or []):
        lint.fail(openapi_path, "PolicyCheckRequest.required must include realm_id")
    if not isinstance(response_component, dict):
        lint.fail(openapi_path, "components.schemas.PolicyCheckResponse missing")
    elif "bound_to" not in set(response_component.get("required") or []):
        lint.fail(openapi_path, "PolicyCheckResponse.required must include bound_to")


def openapi_operations_by_id(openapi: dict[str, Any]) -> dict[str, dict[str, Any]]:
    paths = openapi.get("paths")
    if not isinstance(paths, dict):
        return {}
    operations: dict[str, dict[str, Any]] = {}
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete", "head"):
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
    openapi_path = ARTIFACTS / "openapi" / "cokret-service-api.openapi.yaml"
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
            for method in ("get", "post", "put", "patch", "delete", "head"):
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
        "ck.root.identity.submit_did_operation": ("DidOperationSubmitRequest", "DidOperationSubmitResponse"),
        "ck.gate.account.issue_session_grant": ("SessionGrantRequest", "SessionGrantResponse"),
        "ck.gate.account.oidc_callback": ("AccountOidcCallbackRequest", "AccountOidcCallbackResponse"),
        "ck.find.directory.announce": ("DirectoryAnnounceRequest", "DirectoryAnnounceResponse"),
        "ck.find.directory.withdraw": ("DirectoryWithdrawRequest", "DirectoryWithdrawResponse"),
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
        for method in ("get", "post", "put", "patch", "delete", "head"):
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
        (resolve_openapi_component_schema(lint, openapi_path, components, "SessionGrantRequest") or {})
        .get("properties", {})
        .get("proof", {})
        .get("required", [])
    )
    if "audience" not in session_grant_proof_required:
        lint.fail(openapi_path, "SessionGrantRequest.proof.required must include audience")

    projection_components = {
        "ck.self.projection.spaces": "ProjectionSpacesResponse",
        "ck.self.projection.flows": "ProjectionFlowsResponse",
        "ck.self.projection.morphs": "ProjectionMorphsResponse",
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
    openapi_path = ARTIFACTS / "openapi" / "cokret-service-api.openapi.yaml"
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
        actual = operation.get("x-cokret-required-any-of")
        if actual != expected:
            lint.fail(openapi_path, f"{operation_id} x-cokret-required-any-of must be {expected!r}")

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

    expect_any_of("ck.self.events.query", [["realms"], ["actors"]])
    expect_any_of("ck.self.events.subscribe", [["realms"], ["actors"]])
    expect_any_of("ck.self.events.frontier", [["actor_id"], ["realm_id"]])
    for operation_id in ("ck.self.events.query", "ck.self.events.subscribe"):
        expect_array_param(operation_id, "realms", "#/components/schemas/RealmId")
        expect_array_param(operation_id, "actors", "#/components/schemas/ActorDid")
    for name in ("before", "after"):
        expect_param_ref("ck.self.events.query", name, "#/components/schemas/Cursor")
    expect_param_ref("ck.self.events.subscribe", "after", "#/components/schemas/Cursor")
    expect_param_ref("ck.self.events.get", "event_id", "#/components/schemas/EventId")
    expect_param_ref("ck.self.events.frontier", "actor_id", "#/components/schemas/ActorDid")
    expect_param_ref("ck.self.events.frontier", "realm_id", "#/components/schemas/RealmId")
    expect_param_ref("ck.self.snapshot.head", "realm_id", "#/components/schemas/RealmId")

    query_post = op("ck.self.events.query_post")
    if query_post is not None:
        schema = resolve_openapi_schema_node(lint, openapi_path, openapi.get("components", {}).get("schemas", {}), openapi_request_schema(query_post))
        if not isinstance(schema, dict):
            lint.fail(openapi_path, "ck.self.events.query_post requestBody schema missing")
        else:
            expected_any_of = [{"required": ["realms"]}, {"required": ["actors"]}]
            if schema.get("anyOf") != expected_any_of:
                lint.fail(openapi_path, "ck.self.events.query_post requestBody must require realms or actors")
            properties = schema.get("properties")
            if not isinstance(properties, dict):
                lint.fail(openapi_path, "ck.self.events.query_post requestBody properties missing")
            else:
                for name, ref in (
                    ("realms", "#/components/schemas/RealmId"),
                    ("actors", "#/components/schemas/ActorDid"),
                ):
                    property_schema = properties.get(name)
                    if not isinstance(property_schema, dict):
                        lint.fail(openapi_path, f"ck.events.query_post.{name} property missing")
                        continue
                    if property_schema.get("type") != "array" or property_schema.get("minItems") != 1:
                        lint.fail(openapi_path, f"ck.events.query_post.{name} must be a non-empty array")
                    items = property_schema.get("items")
                    if not isinstance(items, dict) or not (
                        items.get("$ref") == ref or schema_ref_targets(items, ref.rsplit("/", 1)[-1])
                    ):
                        lint.fail(openapi_path, f"ck.events.query_post.{name}.items must reference {ref}")
                for name in ("before", "after"):
                    property_schema = properties.get(name)
                    if not schema_ref_targets(property_schema, "Cursor"):
                        lint.fail(openapi_path, f"ck.events.query_post.{name} must reference Cursor")


def check_openapi_auth_semantics(lint: Lint) -> None:
    """Distinguish public metadata, proof-in-body auth, user tokens, and admin tokens."""
    openapi_path = ARTIFACTS / "openapi" / "cokret-service-api.openapi.yaml"
    openapi = load_yaml(lint, openapi_path)
    if not isinstance(openapi, dict):
        return
    operations = openapi_operations_by_id(openapi)
    public_metadata_operations = {
        "ck.server.describe",
        "ck.self.events.describe",
        "ck.peer.events.describe",
        "ck.open.mimi.provider_directory",
        "ck.root.identity.describe_registry",
        "ck.self.account.describe",
        "ck.find.directory.describe",
        "ck.edge.applet.describe",
        "ck.edge.applet.protocol_metadata",
    }
    proof_in_body_operations = {
        "ck.gate.account.register",
        "ck.gate.account.issue_session_grant",
        "ck.gate.account.oidc_callback",
    }

    for operation_id, operation in operations.items():
        security = operation.get("security")
        if security == []:
            auth = operation.get("x-cokret-auth")
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
        auth = operation.get("x-cokret-auth")
        if not isinstance(auth, dict) or auth.get("public_metadata") is not False or auth.get("proof_in_body") is not True:
            lint.fail(openapi_path, f"{operation_id} must declare x-cokret-auth proof_in_body/public_metadata=false")

    def security_groups(operation: dict[str, Any]) -> list[dict[str, Any]]:
        groups = operation.get("security")
        return [group for group in groups if isinstance(group, dict)] if isinstance(groups, list) else []

    for operation_id, operation in operations.items():
        if not operation_id.startswith("ck.admin."):
            continue
        lint.fail(openapi_path, f"{operation_id} is product-local and must not be registered in Cokret OpenAPI")


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
            properties = read_scope.get("properties") or {}
            if "track_scope" not in properties:
                lint.fail(cursor_path, "read_cursor.read_scope must define track_scope for whole-flow cursors")
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
        if "flow_id" in properties or "track" in properties:
            lint.fail(receipt_path, "read receipt must not reintroduce top-level flow_id/track aliases")


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
        if batch.get("additionalProperties") is not False:
            lint.fail(batch_path, "event batch receipt root additionalProperties must be false")
        properties = batch.get("properties") or {}
        for name in ("receipt_scope", "frontier"):
            schema = properties.get(name)
            if not isinstance(schema, dict) or schema.get("additionalProperties") is not False:
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

    allowed_legacy_paths = {
        (ARTIFACTS / "migration" / "renames.json").resolve(),
        (ARTIFACTS / "registry" / "forbidden-wire-fields.json").resolve(),
    }
    for path in [*markdown_files(), *all_json_files()]:
        if path.resolve() in allowed_legacy_paths:
            continue
        if "ck:txn:" in path.read_text(encoding="utf-8"):
            lint.fail(path, "legacy ck:txn: prefix present outside migration/forbidden registries")


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


DEVICE_ID_PATTERN = r"^ck:device:[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
DID_LEGACY_PREFIX_PATTERN = r"^did:"
DID_LEGACY_GREEDY_PATTERN = r"^did:[a-z0-9]+:[^\s]+$"
DID_BARE_PATTERN = r"^did:[a-z0-9]+:[^\s#?]+$"
GENERIC_OPERATION_REQUEST_REF = "#/components/schemas/OperationRequest"
GENERIC_OPERATION_RESULT_REF = "#/components/schemas/OperationResult"


def check_openapi_error_enum_alignment(lint: Lint) -> None:
    """ErrorEnvelope.error.code must be generated from the canonical error registry."""
    registry_path = ARTIFACTS / "registry" / "error-code-registry.json"
    openapi_path = ARTIFACTS / "openapi" / "cokret-service-api.openapi.yaml"
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


def check_wire_schema_no_bare_scope(lint: Lint) -> None:
    """Wire schemas must use domain-prefixed scope field names."""
    for path in sorted((ARTIFACTS / "schemas").glob("*.schema.json")):
        data = load_json(lint, path)
        if not isinstance(data, dict):
            continue
        for json_path, value, key in walk_json(data):
            if key == "properties" and isinstance(value, dict) and "scope" in value:
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


def check_did_and_device_constraints(lint: Lint) -> None:
    """Reject ambiguous DID/DID URL and device_id constraints in machine artifacts."""
    openapi_path = ARTIFACTS / "openapi" / "cokret-service-api.openapi.yaml"

    for path in sorted((ARTIFACTS / "schemas").glob("*.schema.json")):
        data = load_json(lint, path)
        if not isinstance(data, dict):
            continue
        for json_path, value, key in walk_json(data):
            if key == "pattern" and value == DID_LEGACY_GREEDY_PATTERN:
                lint.fail(path, f"{json_path} uses legacy greedy DID pattern; use bare DID or DID URL pattern")
            if key == "properties" and isinstance(value, dict):
                vm_schema = value.get("verification_method")
                if isinstance(vm_schema, dict) and vm_schema.get("pattern") in {DID_LEGACY_GREEDY_PATTERN, DID_BARE_PATTERN}:
                    lint.fail(path, f"{json_path}.verification_method must use a DID URL pattern with a key fragment")

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
                lint.fail(openapi_path, f"{json_path}.device_id must use the canonical ck:device UUIDv7 pattern")

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
                lint.fail(openapi_path, f"{json_path}.schema must use the canonical ck:device UUIDv7 pattern")


def infer_openapi_success_shape(operation_id: str, method: str, schema: Any) -> str:
    if schema is None:
        if method == "head":
            return "metadata_headers"
        if operation_id in {"ck.self.events.subscribe", "ck.self.account.subscribe"}:
            return "event_stream"
        if operation_id == "ck.self.blob.get":
            return "binary_stream"
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
        for method in ("get", "post", "put", "patch", "delete", "head"):
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                continue
            request_schema = openapi_request_schema(operation)
            response_schema = (
                operation.get("responses", {})
                .get("200", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema")
            )
            facts[operation_id] = {
                "generic_request": isinstance(request_schema, dict)
                and request_schema.get("$ref") == GENERIC_OPERATION_REQUEST_REF,
                "generic_response": isinstance(response_schema, dict)
                and response_schema.get("$ref") == GENERIC_OPERATION_RESULT_REF,
                "request_schema_ref": openapi_artifact_schema_ref(request_schema, components),
                "response_schema_ref": openapi_artifact_schema_ref(response_schema, components),
                "success_shape_kind": infer_openapi_success_shape(operation_id, method, response_schema),
            }
    return facts


def check_operation_binding_metadata(lint: Lint) -> None:
    """Operation registry must machine-declare success shape and governed generic bindings."""
    operation_path = ARTIFACTS / "registry" / "operation-registry.json"
    openapi_path = ARTIFACTS / "openapi" / "cokret-service-api.openapi.yaml"
    operation_registry = load_json(lint, operation_path)
    if not isinstance(operation_registry, dict):
        return

    allowed_success_shapes = set((operation_registry.get("success_shape_kind_definitions") or {}).keys())
    if not allowed_success_shapes:
        lint.fail(operation_path, "operation registry missing success_shape_kind_definitions")

    tier_by_operation: dict[str, str] = {}
    for group in operation_registry.get("surface_groups", []) if isinstance(operation_registry.get("surface_groups"), list) else []:
        if not isinstance(group, dict):
            continue
        tier = group.get("tier")
        for operation_id in group.get("operations", []) or []:
            if isinstance(operation_id, str) and isinstance(tier, str):
                tier_by_operation[operation_id] = tier

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
            if tier_by_operation.get(operation_id) == "core":
                lint.fail(operation_path, f"{operation_id} is core tier and must not use generic OpenAPI bindings")
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
    catalog_path = ARTIFACTS / "registry" / "contract-catalog.json"
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
        if not line.startswith("| `ck."):
            continue
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) != 5:
            continue
        operation_id = cells[0].strip("`")
        if operation_id.startswith("ck."):
            rows[operation_id] = cells[4]
    return rows


def check_operation_field_table_schema_refs(lint: Lint) -> None:
    """Operation field table rows must mention registry-declared schema refs."""
    catalog_path = ARTIFACTS / "registry" / "contract-catalog.json"
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


def check_design_phase_legacy_compat_removed(lint: Lint) -> None:
    """Reject legacy wire compatibility hooks removed while v1 is still in design."""
    forbidden_by_path = {
        ARTIFACTS / "registry" / "error-code-registry.json": [
            "legacy_single_endpoint_media_service",
            "legacy_secret_storage_wire_form",
        ],
        ARTIFACTS / "registry" / "operations-error-mapping.json": [
            "legacy_single_endpoint_media_service",
            "legacy_secret_storage_wire_form",
        ],
        ARTIFACTS / "schemas" / "service-describe.schema.json": [
            "legacy_alias",
            "deprecated_alias",
        ],
        ARTIFACTS / "openapi" / "cokret-service-api.openapi.yaml": [
            "legacy_single_endpoint_media_service",
            "legacy_secret_storage_wire_form",
            "legacy_alias",
            "deprecated_alias",
            "deprecated single-`sfu_endpoint`",
        ],
        ARTIFACTS / "profiles" / "conformance-profiles.json": [
            "legacy single-endpoint",
            "single sfu_endpoint",
        ],
        SPEC_ROOT / "zh" / "crypto-media" / "media-service-binding.md": [
            "服务端 SHOULD 接受遗留单 `sfu_endpoint`",
            "legacy_single_endpoint_media_service",
        ],
        SPEC_ROOT / "zh" / "crypto-media" / "device-lifecycle.md": [
            "legacy_secret_storage_wire_form",
            "Wire deprecation",
            "现存远端 `ck.secret_storage.v1`",
        ],
        SPEC_ROOT / "zh" / "sync" / "service-surface.md": [
            "legacy_alias",
            "deprecated_alias",
            "旧版本只暴露 `supported_operations`",
            "向后兼容地追加",
        ],
    }
    for path, tokens in forbidden_by_path.items():
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            lint.fail(path, f"unable to read for legacy compatibility lint: {exc}")
            continue
        for token in tokens:
            if token in text:
                lint.fail(path, f"design-phase legacy compatibility token remains: {token}")


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
        if mapping_kind == "wire_compat_grandfather":
            if not isinstance(row.get("grandfathered_since"), str) or not row.get("grandfathered_since"):
                lint.fail(action_path, f"{action} uses wire_compat_grandfather and must declare grandfathered_since")
        elif "grandfathered_since" in row:
            lint.fail(action_path, f"{action} must not declare grandfathered_since unless event_mapping_kind=wire_compat_grandfather")


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

            if "/cokret/v1/check" in line:
                lint.fail(path, f"line {line_no}: legacy policy path /cokret/v1/check must be replaced with /_cokret/self/policy/check")

            if TRUST_DOMAIN_JSON_DID_RE.search(line):
                lint.fail(path, f"line {line_no}: trust_domain must use ck:trust_domain:<scope>, not a raw DID")

            if LEGACY_DID_METHOD_REGEX_RE.search(line):
                lint.fail(path, f"line {line_no}: DID regex must not allow ':'/'.'/'_' inside the method segment")

            for match in OPERATION_COUNT_RE.finditer(line):
                count = int(match.group(1))
                if count != operation_count:
                    lint.fail(path, f"line {line_no}: hard-coded operation count {count} differs from registry count {operation_count}")

            for event_kind in active_event_kinds:
                if re.search(rf"(?<![A-Za-z0-9_.-]){re.escape(event_kind)}\.v[0-9]+\b", line):
                    lint.fail(path, f"line {line_no}: active Event.kind {event_kind} must not be written with a .vN suffix")


def check_vector_registry(lint: Lint) -> None:
    path = ARTIFACTS / "registry" / "vector-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    if data.get("source_of_truth") is not True:
        lint.fail(path, "source_of_truth must be true")

    rows = data.get("vectors")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "vectors must be a non-empty list")
        return

    registered: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        label = f"vectors[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue

        vector_id = row.get("vector_id")
        if not isinstance(vector_id, str) or not VECTOR_ID_TOKEN_RE.fullmatch(vector_id):
            lint.fail(path, f"{label}.vector_id must be a ck.vector.*.vN identifier")
            continue
        if vector_id in registered:
            lint.fail(path, f"{label}.vector_id duplicates {vector_id}")
        registered[vector_id] = row

        if row.get("status") not in {"active", "reserved", "deprecated"}:
            lint.fail(path, f"{label}.status must be active, reserved, or deprecated")

        expected_domain = vector_id.removeprefix("ck.vector.").rsplit(".v", 1)[0].split(".", 1)[0]
        if row.get("domain") != expected_domain:
            lint.fail(path, f"{label}.domain must match vector id domain {expected_domain!r}")

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
                source_text = resolved.read_text(encoding="utf-8")
            except Exception as exc:
                lint.fail(path, f"{source_label} target cannot be read: {source_ref}: {exc}")
                continue
            if vector_id not in VECTOR_ID_TOKEN_RE.findall(source_text):
                lint.fail(path, f"{source_label} does not contain vector_id {vector_id}")

    for scan_path in markdown_files() + raw_artifact_files():
        try:
            text = scan_path.read_text(encoding="utf-8")
        except Exception:
            continue
        for vector_id in sorted(set(VECTOR_ID_TOKEN_RE.findall(text))):
            if vector_id not in registered:
                lint.fail(scan_path, f"references unregistered conformance vector id: {vector_id}")


def check_account_data_type_registry(lint: Lint, known: dict[str, set[str]]) -> None:
    path = ARTIFACTS / "registry" / "account-data-type-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    if data.get("source_of_truth") is not True:
        lint.fail(path, "source_of_truth must be true")

    rows = data.get("account_data_types")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "account_data_types must be a non-empty list")
        return

    seen: set[str] = set()
    allowed_status = {"active", "reserved", "deprecated"}
    allowed_storage = {"encrypted_account_data", "local_only", "encrypted_account_data_or_local"}
    for index, row in enumerate(rows):
        label = f"account_data_types[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue

        key_pattern = row.get("key_pattern")
        if not isinstance(key_pattern, str) or not key_pattern.startswith("ck."):
            lint.fail(path, f"{label}.key_pattern must be a ck.* key pattern")
            continue
        if key_pattern in seen:
            lint.fail(path, f"{label}.key_pattern duplicates {key_pattern}")
        seen.add(key_pattern)

        if row.get("status") not in allowed_status:
            lint.fail(path, f"{label}.status must be one of {sorted(allowed_status)}")
        if row.get("storage") not in allowed_storage:
            lint.fail(path, f"{label}.storage must be one of {sorted(allowed_storage)}")
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
            lint.fail(path, f"{json_path} has invalid ck:blob:sha256 reference")
        return
    if token_kind in known["id_kinds"]:
        candidate = rest[:36]
        if not UUID7_RE.fullmatch(candidate):
            lint.fail(path, f"{json_path} has invalid ck:{token_kind}: typed UUIDv7 reference")
        return
    if token_kind in known["special_id_kinds"]:
        if not rest:
            lint.fail(path, f"{json_path} has empty ck:{token_kind}: special reference")
        return
    lint.fail(path, f"{json_path} references unregistered typed ID kind: ck:{token_kind}:")


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
                and value.startswith("ck.")
                and not value.startswith("ck.content.")
            ):
                if value not in known["event_kinds"]:
                    lint.fail(path, f"{json_path} references unregistered Event.kind: {value}")

            if key in {"operation_id", "mapped_operation_id"} and value.startswith("ck."):
                if value not in known["operation_ids"]:
                    lint.fail(path, f"{json_path} references unregistered operation_id: {value}")
            if key == "call" and ".recovery.call" in json_path and value.startswith("ck."):
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
            signed_event.pop("unsigned", None)
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
            and value.startswith("ck.")
            and not value.startswith("ck.content.")
        ):
            if value not in known["event_kinds"]:
                lint.fail(path, f"{json_path} markdown JSON references unregistered Event.kind: {value}")

        if key in {"operation_id", "mapped_operation_id", "operationId"} and value.startswith("ck."):
            if value not in known["operation_ids"]:
                lint.fail(path, f"{json_path} markdown JSON references unregistered operation_id: {value}")

        if key == "constraint_type" and value not in known["constraint_types"]:
            lint.fail(path, f"{json_path} markdown JSON uses invalid constraint_type: {value}")

        for match in TYPED_ID_TOKEN_RE.finditer(value):
            kind, rest = match.group(1), match.group(2)
            if is_placeholder_typed_id(rest):
                if kind not in known["id_kinds"] and kind not in known["special_id_kinds"]:
                    lint.fail(path, f"{json_path} markdown JSON references unregistered typed ID kind: ck:{kind}:")
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


def load_json_schema_for_uri(uri: str) -> Any:
    prefix = "https://cokret.io/artifacts/"
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
    first_expected_error: str | None = None,
) -> None:
    errors = jsonschema_errors(lint, owner, schema_ref, instance)
    if expect_valid and errors:
        lint.fail(owner, f"{label} fails {schema_ref}: " + "; ".join(errors[:3]))
    if not expect_valid and not errors:
        lint.fail(owner, f"{label} expected to fail {schema_ref} but validated successfully")
    if not expect_valid and first_expected_error and errors and errors[0] != first_expected_error:
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

    if schema_ref not in {"schemas/event-envelope.schema.json", "schemas/capability-grant.schema.json"}:
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

        if "ck.moderation.policy_action" in text:
            lint.fail(path, "markdown references removed Event.kind ck.moderation.policy_action; use ck.policy.action")

        for schema_id in SCHEMA_ID_TOKEN_RE.findall(text):
            if schema_id not in known["schema_ids"]:
                lint.fail(path, f"markdown references unknown schema id: {schema_id}")
        for profile_id in PROFILE_ID_TOKEN_RE.findall(text):
            if profile_id not in known["profiles"]:
                lint.fail(path, f"markdown references unknown profile: {profile_id}")

        for prefix_match in TYPED_ID_PREFIX_TOKEN_RE.finditer(text):
            kind = prefix_match.group(1)
            if kind not in known["id_kinds"] and kind not in known["special_id_kinds"]:
                lint.fail(path, f"markdown references unregistered typed ID kind: ck:{kind}:")

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
            if schema_ref:
                expect_valid = expect_valid_from_fence_meta(meta)
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
    profile_tiers_count = len(profile_data.get("profile_tiers", []))

    expected: dict[str, int] = {
        "Event kind（active）": len(known["active_event_kinds"]),
        "Schema": len(known["schema_ids"]),
        "Typed ID kind": len(known["id_kinds"]),
        "Service operation": len(known["operation_ids"]),
        "Claimable conformance profile": len(known["claimable_profiles"]),
        "Profile id references": len(known["profiles"]),
        "profile_requirements": profile_requirements_count,
        "profile_tiers": profile_tiers_count,
    }

    # Match table rows like "| Event kind（active） | 152 | `...` |"
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
        "allow_child_privacy_tightening_against_required",
        "on_conflict",
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
    """Reject duplicate code strings within each error registry section.

    Top-level ``codes`` and item-level ``reason_codes`` may intentionally reuse
    a string during a migration window, but a duplicate inside the same section
    has no stable first/last-wins semantics for SDK generation or catalog UI.
    """
    path = ARTIFACTS / "registry" / "error-code-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return

    for section in ("codes", "reason_codes"):
        rows = data.get(section, [])
        if not isinstance(rows, list):
            lint.fail(path, f"{section} must be a list")
            continue
        seen: dict[str, int] = {}
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
    openapi_path = ARTIFACTS / "openapi" / "cokret-service-api.openapi.yaml"
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

    * Hard rules (errors) — wire-stable precedence and immediate-follow rules
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
    hard_precedence = rules.get("hard_precedence") or []
    hard_immediate = rules.get("hard_immediate_follow") or []
    ordered_groups = rules.get("ordered_groups") or {}
    role_rule = rules.get("role_after_subject") or {}
    subject_anchors = set(role_rule.get("subject_anchors") or [])
    role_field = role_rule.get("role_field")

    def check_order_of_keys(path: Path, json_path: str, keys: list[str], where: str) -> None:
        index = {key: position for position, key in enumerate(keys)}

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
            check_order_of_keys(path, json_path, list(props.keys()), "properties")
            required = node.get("required")
            if isinstance(required, list):
                # Check required entries in the order they are declared. A field
                # listed in required but absent from properties is left to the
                # existing schema-shape checks; we only order known property keys.
                req_keys = [r for r in required if isinstance(r, str)]
                check_order_of_keys(path, json_path, req_keys, "required")

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
            "ck.schema.realm.v1",
        ),
        (
            "spec/v1/zh/models/realm-and-space.md",
            "spec/v1/artifacts/schemas/space.schema.json",
            "ck.schema.space.v1",
        ),
        (
            "spec/v1/zh/models/flow-and-message.md",
            "spec/v1/artifacts/schemas/flow.schema.json",
            "ck.schema.flow.v1",
        ),
        (
            "spec/v1/zh/models/flow-and-message.md",
            "spec/v1/artifacts/schemas/message.schema.json",
            "ck.schema.message.v1",
        ),
        (
            "spec/v1/zh/models/relation.md",
            "spec/v1/artifacts/schemas/relation.schema.json",
            "ck.schema.relation.v1",
        ),
        (
            "spec/v1/zh/models/circle.md",
            "spec/v1/artifacts/schemas/circle.schema.json",
            "ck.schema.circle.v1",
        ),
        (
            "spec/v1/zh/models/morph.md",
            "spec/v1/artifacts/schemas/morph.schema.json",
            "ck.schema.morph.v1",
        ),
        (
            "spec/v1/zh/models/views.md",
            "spec/v1/artifacts/schemas/view.schema.json",
            "ck.schema.view.v1",
        ),
        (
            "spec/v1/zh/models/actor.md",
            "spec/v1/artifacts/schemas/actor-profile.schema.json",
            "ck.schema.actor_profile.v1",
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
    required = {"label", "context_fields", "output_length", "applies_to_profiles", "grandfathered"}
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
        if not isinstance(context_fields, list) or not context_fields:
            lint.fail(path, f"labels[{index}] context_fields MUST be a non-empty list")


def json_pointer_get(data: Any, pointer: str) -> Any:
    current = data
    for token in pointer.removeprefix("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
            continue
        return None
    return current


def check_signature_algorithm_registry(lint: Lint) -> None:
    path = ARTIFACTS / "registry" / "signature-alg-registry.json"
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return
    algorithms = data.get("algorithms")
    if not isinstance(algorithms, list) or not algorithms:
        lint.fail(path, "algorithms must be a non-empty array")
        return

    proof_algs: set[str] = set()
    raw_algs: set[str] = set()
    canonical_ids: set[str] = set()
    for index, row in enumerate(algorithms):
        label = f"algorithms[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue
        canonical_id = row.get("canonical_id")
        proof_alg = row.get("proof_alg")
        raw_alg = row.get("signature_algorithm")
        status = row.get("status")
        if not isinstance(canonical_id, str) or not canonical_id:
            lint.fail(path, f"{label}.canonical_id must be a non-empty string")
            continue
        if canonical_id in canonical_ids:
            lint.fail(path, f"duplicate canonical_id: {canonical_id}")
        canonical_ids.add(canonical_id)
        if status == "active":
            if not isinstance(proof_alg, str) or not proof_alg:
                lint.fail(path, f"{label}.proof_alg must be a non-empty string")
            else:
                proof_algs.add(proof_alg)
            if not isinstance(raw_alg, str) or not raw_alg:
                lint.fail(path, f"{label}.signature_algorithm must be a non-empty string")
            else:
                raw_algs.add(raw_alg)

    expected_proof = sorted(proof_algs)
    expected_raw = sorted(raw_algs)
    proof_enum_locations = [
        ("schemas/event-envelope.schema.json", "/$defs/event_proof/properties/alg/enum"),
        ("schemas/event-envelope.schema.json", "/$defs/proof/properties/alg/enum"),
        ("schemas/anchor.schema.json", "/$defs/signature/properties/alg/enum"),
        ("schemas/ice-config-response.schema.json", "/$defs/signature/properties/alg/enum"),
        ("schemas/attestation-evidence.schema.json", "/properties/attestation_key/properties/alg/enum"),
    ]
    raw_enum_locations = [
        ("schemas/member-identity.schema.json", "/properties/proof/properties/signature_algorithm/enum"),
    ]
    for file_ref, pointer in proof_enum_locations:
        schema_path = ARTIFACTS / file_ref
        schema = load_json(lint, schema_path)
        actual = json_pointer_get(schema, pointer) if isinstance(schema, dict) else None
        if sorted(actual or []) != expected_proof:
            lint.fail(schema_path, f"{pointer} must match signature-alg-registry proof_alg values {expected_proof}")
    for file_ref, pointer in raw_enum_locations:
        schema_path = ARTIFACTS / file_ref
        schema = load_json(lint, schema_path)
        actual = json_pointer_get(schema, pointer) if isinstance(schema, dict) else None
        if sorted(actual or []) != expected_raw:
            lint.fail(schema_path, f"{pointer} must match signature-alg-registry signature_algorithm values {expected_raw}")


# --- STR-002 / OPT-005: action prose-reference closure ------------------------
# (ck.profile.*.vN prose closure is already enforced for all markdown by
# check_markdown_examples; only the hand-maintained action list lacked a gate.)

# Action tokens that legitimately appear as a `- `ck.<...>`` bullet in
# capabilities.md §5 but are intentionally NOT capability-action-registry
# entries. Keep empty unless a real exception exists; every addition MUST carry
# a one-line reason.
ALLOWED_PROSE_ACTIONS: set[str] = set()

_ACTION_TOKEN_RE = re.compile(r"^ck\.[a-z0-9_]+(?:\.[a-z0-9_]+)*$")
_PROSE_ACTION_BULLET_RE = re.compile(r"^\s*-\s+`(ck\.[a-z0-9_.]+)`")


def check_action_reference_closure(lint: Lint) -> None:
    """STR-002 / OPT-005: every action declared in capabilities.md §5 (动作集合)
    bullet lists MUST resolve in capability-action-registry.json (the canonical
    action set generated from contract-catalog.json). Scope is deliberately
    restricted to the §5 action-declaration bullets (`- `ck.<...>``) so that
    event kinds, grandfathered old names in the §5.0 deviation table, and prose
    `ck.*` tokens elsewhere cannot produce false positives — closing the
    hand-maintained-list drift (e.g. ck.object.read_history) at its root."""
    registry_path = ARTIFACTS / "registry" / "capability-action-registry.json"
    data = load_json(lint, registry_path)
    if not isinstance(data, dict):
        return
    known = {
        a.get("action")
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
# waiver list can shrink as the underlying _spec_review findings are resolved.
NON_NORMATIVE_KEYWORD_WAIVERS: dict[str, str] = {
    # C-CON-01: spec-map.md declares normative:false but carries a
    # `(normative)` Parser-layering subsection and MUST/SHOULD prose. Tracked
    # separately; waived here so C-BET-04 does not double-report it.
    "spec/v1/zh/spec-map.md": "待 C-CON-01 处理（normative:false 却含 (normative) 小节与 MUST/SHOULD）",
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
_FRONTMATTER_BLOCK_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
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


def main() -> int:
    lint = Lint()
    check_text_files_utf8_no_nul(lint)
    if lint.errors:
        print("Artifact registry lint failed:", file=sys.stderr)
        for error in lint.errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    check_registry_manifest(lint)
    check_proposal_merge_manifest(lint)
    known = check_registries(lint)
    check_schema_refs(lint, known)
    check_profile_requirements(lint, known)
    check_event_schema_coverage(lint, known)
    check_operation_surfaces(lint, known)
    check_service_describe_alignment(lint)
    check_policy_check_alignment(lint)
    check_openapi_dedicated_operation_schemas(lint)
    check_openapi_core_selector_constraints(lint)
    check_openapi_auth_semantics(lint)
    check_openapi_error_enum_alignment(lint)
    check_wire_schema_no_bare_scope(lint)
    check_read_scope_schema_closure(lint)
    check_signed_object_closure(lint)
    check_reducer_payload_closure(lint)
    check_did_and_device_constraints(lint)
    check_operation_binding_metadata(lint)
    check_binding_completeness_index(lint)
    check_operation_field_table_schema_refs(lint)
    check_design_phase_legacy_compat_removed(lint)
    check_binding_variant_non_http(lint)
    check_capability_action_event_mapping(lint)
    check_text_reference_targets(lint)
    check_cross_source_drift(lint, known)
    check_account_data_type_registry(lint, known)
    check_vector_registry(lint)
    check_vector_reference_closure(lint)
    check_security_closure_vectors(lint)
    check_fixtures(lint, known)
    check_crypto_signature_fixture(lint)
    check_markdown_links(lint)
    check_no_rule_marker_emoji(lint)
    check_markdown_examples(lint, known)
    check_legacy_wire_fields(lint)
    check_forbidden_naming_aliases(lint)
    check_event_proof_digest_shape(lint)
    check_legacy_announce_id_form(lint)
    check_directory_field_drift(lint)
    check_typed_id_prose_consistency(lint)
    check_join_policy_gate_id_uniqueness(lint)
    check_content_composite_uses_parts(lint)
    check_release_readiness_counts(lint, known)
    check_error_code_registry_uniqueness(lint)
    check_operations_error_mapping_closure(lint)
    check_error_code_closure(lint)
    check_cross_doc_anchors(lint)
    check_openapi_no_floating_number(lint)
    check_canonical_digest_fixtures(lint)
    check_field_order(lint)
    check_model_required_field_table_coverage(lint)
    check_exporter_label_registry(lint)
    check_signature_algorithm_registry(lint)
    check_action_reference_closure(lint)
    check_non_normative_frontmatter(lint)

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
        f"{len(known['profiles'])} profile id references)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
