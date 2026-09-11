"""Shared paths, constants, parsers, and cross-domain lint helpers."""


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



ROOT = Path(__file__).resolve().parents[2]

TOOLS_ROOT = Path(__file__).resolve().parent.parent

SPEC_ROOT = ROOT / "spec" / "v1"

ARTIFACTS = SPEC_ROOT / "artifacts"


EVENT_KIND_TOKEN_RE = re.compile(r"\bak\.[a-z0-9_]+(?:\.[a-z0-9_]+)+\b")

OPERATION_ID_RE = re.compile(r"^ak\.[a-z0-9_]+(?:\.[a-z0-9_]+)+\.v1$")

# zh/sync/api-conventions.md §2.4: ak.<surface>.<domain...>.<kind>.<action>.
OPERATION_KINDS = frozenset({"read", "stream", "resource", "command", "upload", "exchange"})

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

EVENT_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{44}$")

SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

CONTENT_ADDRESSED_BLOB_PAYLOAD_RE = re.compile(r"^(?:sha256|blake3):[0-9a-f]{64}$")

OPENAPI_OPERATION_ID_RE = re.compile(r"^\s*operationId:\s*([A-Za-z0-9_.-]+)\s*$", re.MULTILINE)

YAML_REF_RE = re.compile(r"\$ref:\s*['\"]?([^'\"\s#]+(?:#[^'\"\s]+)?)")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)

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

DID_BARE_PATTERN = r"^did:[a-z0-9]+:[^\s/?#]+$"

DID_URL_PROFILE_PATTERN = r"^did:[a-z0-9]+:[^\s#?]+#[A-Za-z0-9._:-]+$"

TRUST_DOMAIN_PATTERN = r"^ak:trust_domain:[a-z0-9][a-z0-9._\-:]{0,127}$"

GENERIC_OPERATION_REQUEST_REF = "#/components/schemas/OperationRequest"

GENERIC_OPERATION_RESULT_REF = "#/components/schemas/OperationResult"


SECURITY_CLOSURE_VECTOR_IDS = {
    "ak.vector.account.blocklist_projection.v1",
    "ak.vector.account_status.issuer_ledger.v1",
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

# zh/conformance/encoding.md 4.1 closes the set of top-level `cell_subject`
# kinds. `canonical_json` and `string_set_digest` are `components[]`
# descriptors: a structured single-field subject MUST be spelled as a
# one-component composite so exactly one embedding row applies to it.
CELL_SUBJECT_KINDS = {
    "did",
    "typed_id",
    "string",
    "uri",
    "coalesce",
    "composite",
    "tuple",
}

CELL_SUBJECT_COMPONENT_ONLY_KINDS = {"canonical_json", "string_set_digest"}


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

    def rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            return str(path)

    def fail(self, path: Path, message: str) -> None:
        self.errors.append(f"{self.rel(path)}: {message}")


EVENT_ENVELOPE_IDENTITY_FIELDS = frozenset({"event_id", "realm_id", "payload"})

FORBIDDEN_EVENT_ENVELOPE_FIELDS = frozenset(
    {"effects", "conflict_keys_digest", "effective_scope"}
)



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
    "frank": "franking_proof",
    "requires_frank_verification": "franking_proof_verification_required",
    "retention_until": "retention_expires_at",
    "queue_item_id": "id",
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
    "did_document_hash": "document_digest",
    "old_did_document_hash": "old_document_digest",
    "new_did_document_hash": "new_document_digest",
    "old_did_document_canonical_hash": "old_document_digest",
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



NAMING_RULES_PATH = TOOLS_ROOT / "naming-convention-rules.json"

NAMING_DEBT_PATH = TOOLS_ROOT / "naming-debt-baseline.json"

CANONICAL_LEXEME_REGISTRY_PATH = ARTIFACTS / "registry" / "canonical-lexeme-registry.json"

EVIDENCE_MATERIAL_AUDIT_PATH = TOOLS_ROOT / "evidence-material-audit.json"

COMMON_OBJECT_FIELD_MATRIX_PATH = TOOLS_ROOT / "common-object-field-matrix.json"

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



LEGACY_ANNOUNCE_ID_RE = re.compile(r"\bann_(?:[0-9a-f]{16,64}|<hex>|\*)\b")



VALUE_PROJECTION_DIGEST_INPUTS = {
    "base64url_decoded_bytes",
    "canonical_json_bytes",
    "event_payload_canonical_bytes",
}


# The normalization contexts a projected member may apply to a string set. It is
# the same normalization the `string_set_digest` cell-subject component uses, so
# a family that keys its cell by a scope set and also projects that set into the
# value cannot disagree with itself about what the set is.
NORMALIZED_STRING_SET_CONTEXTS = {
    "ak.accountability_scope_set.v1",
}


VALUE_PROJECTION_DERIVATIONS = {
    "event_digest_from_event_id",
    "mls_commit_transition_digest",
    "mls_genesis_transition_digest",
}


# Closed semantic carrier metadata for projected object members.  The metadata
# makes an otherwise schema-less reducer-derived field machine-classifiable by
# the naming contract without changing its wire representation.
VALUE_PROJECTION_IDENTITY_SUBJECTS = {
    "did_core_id": {"principal", "service", "station", "hardware_module"},
    "account_id": {"account"},
    "actor_id": {"actor"},
}


# Reducer derivations a cell write may add on top of the projected payload.
#
# The projected cell value is what a `state_root` leaf hashes, so a field the
# reducer computes rather than copies has to be named here or two conforming
# implementations could disagree on the root while both matching the schema.
# The set is closed: a derivation is a normative reducer rule, not an
# implementation's private cache. See zh/authz/capabilities.md section 10.
CELL_WRITE_DERIVATIONS = {
    "capability_issuer_station_id",
    "capability_authority_depth",
    "capability_authority_root_refs",
}


# encoding.md 9.5.1: a registered path is dot-separated *named* fields only.
# Array indices, wildcards and empty segments have no defined evaluation, so a
# registry carrying one would pass lint yet be underivable.
# JSON Schema documents carry their canonical identity in the reserved `$id`
# member. Registry field paths are JSON object-member paths (not language
# identifiers), so permit that exact reserved segment while keeping indexes,
# wildcards and arbitrary `$` names closed.
FIELD_PATH_RE = re.compile(
    r"^(?:[A-Za-z_][A-Za-z0-9_]*|\$id)(?:\.(?:[A-Za-z_][A-Za-z0-9_]*|\$id))*$"
)



CONFLICT_RECOVERY_KIND = "ak.conflict.recovery"
# The notary configuration cell is deliberately outside the recovery allowlist:
# verifying any Seal reads it, so a recovery Seal targeting it can never be accepted.
NOTARY_CELL_FAMILY = "ak.component.notary.v1"



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
# Scoping this check to `event_log` alone hid `ak.self.account_data.resource.delete.v1`,
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
# See arkret-work/work/active/2026-08-06-1723-event-log-operations-need-a-signed-request.md.
EVENT_LOG_OPERATIONS_WITHOUT_A_SIGNED_REQUEST: dict[str, str] = {}



# Matches dispatch refs of the form `[./]?<filename>.schema.json#/$defs/<class>`.
# Covers `event-payload.schema.json#/$defs/...` (canonical) and sibling-schema
# refs such as `accountability-grant.schema.json#/$defs/grant_payload`.
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
# invite, reaction, message_redact, space_state_transition, strand_patch,
# object_patch). Adding a new dispatch that doesn't match the last-segment
# rule MUST add the pair here, forcing reviewer awareness of the rename.
SHARED_PAYLOAD_DISPATCH: set[tuple[str, str]] = {
    ("ak.realm.restore", "realm_archive_payload"),
    ("ak.realm.unfreeze", "realm_freeze_payload"),
    ("ak.audit.ryw_receipt", "audit_payload"),
    ("ak.circle.archive", "object_lifecycle_payload"),
    ("ak.circle.restore", "object_lifecycle_payload"),
    ("ak.circle.tombstone", "object_lifecycle_payload"),
    ("ak.strand.archive", "object_lifecycle_payload"),
    ("ak.strand.restore", "object_lifecycle_payload"),
    ("ak.strand.tracks.update", "strand_patch_payload"),
    ("ak.strand.update", "strand_patch_payload"),
    ("ak.invite.accept", "invite_accept_payload"),
    ("ak.invite.cancel", "invite_cancel_payload"),
    ("ak.invite.claim", "invite_claim_payload"),
    ("ak.invite.create", "invite_create_payload"),
    ("ak.invite.revoke", "invite_revoke_payload"),
    ("ak.invite.third_party", "invite_third_party_create_payload"),
    ("ak.morph.archive", "object_lifecycle_payload"),
    ("ak.morph.restore", "object_lifecycle_payload"),
    ("ak.reaction.add", "reaction_payload"),
    ("ak.reaction.remove", "reaction_payload"),
    ("ak.realm.profile", "realm_profile_payload"),
    ("ak.space.archive", "space_state_transition_payload"),
    ("ak.space.restore", "space_state_transition_payload"),
    ("ak.view.create", "view_payload"),
    ("ak.view.update", "view_payload"),
}



# Class A / class B wording. encoding.md 6.0.1 makes these unconditional: no
# registry row can exempt them, because the shape has no fixed point at all.
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


# Class C wording: a one-way forward declaration naming a later Event from another
# submission. Constructible, but only allowed once named in the exemption registry.
PREIMAGE_FORWARD_DECLARATION_PHRASES = (
    "not yet submitted",
    "not yet been submitted",
    "another submission",
    "a later submission",
    "separate submission",
    "forward declaration",
    "forward-declares",
    "forward declares",
)


# The candidate scope is the Event-identity name family plus every field whose own
# description says its value is derived from an Event identity. Restricting to the
# name family alone would miss exactly the interesting case: an id that is a retype
# of some Event id and therefore just as much an Event identity commitment.
PREIMAGE_IDENTITY_NAME_SUFFIXES = ("_event_id", "_event_ref", "_event_digest")

PREIMAGE_IDENTITY_EXACT_NAMES = frozenset({"event_id"})

PREIMAGE_IDENTITY_DERIVATION_RE = re.compile(
    r"retype\(|retype of|event[- ]derived|derived from (?:the )?(?:accepted )?(?:genesis )?event"
    r"|derives from (?:the )?event"
)


PREIMAGE_EXEMPTION_REGISTRY_PATH = ARTIFACTS / "registry" / "preimage-identity-exemption-registry.json"

PREIMAGE_EXEMPTION_SECTION_ANCHOR = "601-原像内禁止承诺-event-标识normative"

PREIMAGE_EXEMPTION_SECTION_PATH = SPEC_ROOT / "zh" / "conformance" / "encoding.md"

PREIMAGE_EXEMPTION_ID_RE = re.compile(r"\bak\.exemption\.preimage_identity\.[a-z0-9_]+\.v[0-9]+\b")

PREIMAGE_EXEMPTION_ROW_KEYS = (
    "exemption_id",
    "status",
    "kind",
    "subject",
    "commitment_direction",
    "one_way_rationale",
    "target_fixed_when",
    "admission_compensating_checks",
    "absent_target_semantics",
    "conformance_vector_ids",
    "spec_anchor",
)

PREIMAGE_EXEMPTION_KINDS = frozenset({"envelope_omission", "forward_declaration"})

PREIMAGE_EXEMPTION_STATUS = frozenset({"active", "retired"})

# Class A / class B directions. A row carrying one of these is a defective registry,
# not a ruling: encoding.md 6.0.1 says those shapes are never exemptible.
PREIMAGE_FORBIDDEN_DIRECTIONS = frozenset({"self_identity", "same_unit_sibling"})


# encoding.md 4.0.1: a closed object that already carries a complete content-addressed
# typed ref must not carry a sibling digest of the same bytes. Every other digest next
# to such a ref states its distinct preimage in this closed registry. Only refs whose
# whole pattern is one content-addressed form count; unions that also admit UUID, Event
# or DID forms are outside the gate by construction.
SIBLING_DIGEST_EXEMPTION_REGISTRY_PATH = ARTIFACTS / "registry" / "content-addressed-ref-digest-exemption-registry.json"

SIBLING_DIGEST_SECTION_ANCHOR = "401-content-addressed-typed-ref-唯一表示normative"

SIBLING_DIGEST_SECTION_PATH = SPEC_ROOT / "zh" / "conformance" / "encoding.md"

SIBLING_DIGEST_EXEMPTION_ROW_KEYS = (
    "exemption_id",
    "status",
    "kind",
    "subject",
    "preimage",
    "spec_anchor",
)

SIBLING_DIGEST_EXEMPTION_KINDS = frozenset({"distinct_preimage"})

SIBLING_DIGEST_EXEMPTION_STATUS = frozenset({"active", "retired"})

# A bare digest property: exactly one (or the registered pair of) active suite names
# followed by 64 lowercase hex characters.
SIBLING_DIGEST_PATTERN_RE = re.compile(
    r"^\^\(?(?:\?:)?(?:sha256(?:\|blake3)?|blake3)\)?:\[0-9a-f\]\{64\}\$$"
)

CONTENT_ADDRESSED_HEX64 = "[0-9a-f]{64}"



# Fixture branches that deliberately carry a malformed token as the conformance
# negative.  Validating them would assert the very wire form they exist to reject,
# so only the typed-ID kind is checked there.
NEGATIVE_TOKEN_PATH_SEGMENTS = (".rejected_form.", ".rejected_forms.")


def json_path_to_pointer(json_path: str) -> str:
    """Rewrite a `$.a.b[0]` walker path as the RFC 6901 pointer `/a/b/0`.

    The fixture exemption registry keys on JSON Pointers so an entry names one
    exact carrier position rather than a field-name convention; the fixture
    walker reports the dotted form, so the two notations meet here.
    """
    body = json_path[1:] if json_path.startswith("$") else json_path
    body = re.sub(r"\[(\d+)\]", r".\1", body)
    return "".join(f"/{segment}" for segment in body.split(".") if segment)



FIXTURE_REJECT_DECISION_KEYS = ("decision", "result", "seal_result", "event_state")

_REJECT_REASON_CODE_RE = re.compile(r"^[a-z][a-z0-9_]+$")



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
    ("canonical_preimage_utf8", "sha256_digest_hex", "utf8", "raw_hex", ""),
    ("request_canonical_bytes_utf8", "request_digest", "utf8", "sha256_hex", ""),
    # PCR genesis receipt device/HPKE key digests: SHA-256 over the canonical
    # multikey, written with the sha256: prefix the receipt schema requires.
    ("preimage_utf8", "expected", "utf8", "sha256_hex", ""),
    ("rejected_retired_preimage_utf8", "rejected_retired_expected", "utf8", "sha256_hex", ""),
    (
        "canonical_bytes_utf8",
        "expected_registration_epoch",
        "utf8",
        "sha256_hex",
        "arkret-applet-registration-epoch-v1\n",
    ),
    ("canonical_bytes_base64url", "digest", "base64url", "sha256_hex", ""),
    (
        "leaf_canonical_preimage_b64u",
        "leaf_digest",
        "base64url",
        "sha256_hex",
        "\x00",
    ),
    # Snapshot state_digest KAT: the section 6.2.1 cell leaf H(0x00 || preimage),
    # spelled as canonical JSON text beside the leaf it must hash to.
    ("leaf_preimage", "leaf", "utf8", "sha256_hex", "\x00"),
    (
        "identity_link_proof_preimage_hex",
        "identity_link_proof_payload_digest",
        "hex",
        "sha256_hex",
        "",
    ),
)


# Keys that state canonical bytes but carry no digest the lint can check them
# against. Every one needs a reason, because "no digest beside it" is also what a
# silently deleted digest looks like.
UNPAIRED_STATED_PREIMAGE_KEYS: dict[str, str] = {
    "proof_canonical_bytes_utf8": (
        "Agent initial proof bytes are verified against the fixture Ed25519 signature "
        "and closed schema by check_session_grant_kat.py; no separate digest is transmitted"
    ),
    "create_event_digest_preimage_canonical_bytes_utf8": (
        "hash-transition fixture uses a suite-aware Event digest and EventId; the Rust "
        "hash_transition_fixture test recomputes both"
    ),
    "accepted_event_canonical_bytes_utf8": (
        "hash-transition receipt KAT hashes these bytes with the case's historical digest suite "
        "and an explicit domain separator in the Rust fixture test"
    ),
    "bytes_digest_preimage_hex": (
        "hash-transition receipt KAT carries already domain-framed binary bytes and is checked "
        "by the suite-aware Rust fixture test"
    ),
    "receipt_core_canonical_bytes_utf8": (
        "hash-transition receipt signature payload preimage is checked by the suite-aware Rust "
        "fixture test"
    ),
    "signature_transcript_canonical_bytes_utf8": (
        "hash-transition receipt transcript is checked against the registered binding by the "
        "suite-aware Rust fixture test"
    ),
    "receipt_canonical_bytes_utf8": (
        "hash-transition full receipt digest uses the historical suite and is recomputed by the "
        "suite-aware Rust fixture test"
    ),
    "state_leaf_preimage_canonical_bytes_utf8": (
        "hash-transition state leaf uses the live digest suite and is recomputed by the Rust KAT"
    ),
    "state_leaf_preimage_hex": (
        "hash-transition state leaf is an RFC 6962 framed binary preimage checked by the Rust KAT"
    ),
    "control_event_leaf_preimage_hex": (
        "hash-transition control root leaf is an RFC 6962 framed raw digest checked by the Rust KAT"
    ),
    "completeness_leaf_preimage_hex": (
        "hash-transition completeness root leaf is an RFC 6962 framed JCS record checked by the Rust KAT"
    ),
    "seal_body_canonical_bytes_utf8": (
        "hash-transition Seal id and signature payload use the verified Seal suite and are checked by the Rust KAT"
    ),
    "snapshot_canonical_bytes_utf8": (
        "hash-transition snapshot commitment uses the predecessor suite and is checked by the Rust KAT"
    ),
    "transition_event_digest_preimage_canonical_bytes_utf8": (
        "hash-transition Move uses the predecessor suite and is checked by the Rust KAT"
    ),
    "previous_state_leaf_preimage_canonical_bytes_utf8": (
        "hash-transition previous state root uses the predecessor suite and is checked by the Rust KAT"
    ),
    "previous_state_leaf_preimage_hex": (
        "hash-transition previous state leaf framing is checked by the Rust KAT"
    ),
    "next_state_leaf_preimage_canonical_bytes_utf8": (
        "hash-transition next state root uses the successor suite and is checked by the Rust KAT"
    ),
    "next_state_leaf_preimage_hex": (
        "hash-transition next state leaf framing is checked by the Rust KAT"
    ),
    "successor_event_digest_preimage_canonical_bytes_utf8": (
        "hash-transition successor Event uses the successor suite and is checked by the Rust KAT"
    ),
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
    "receiver_without_retained_canonical_bytes": (
        "names the receiver behaviour when the bytes are absent; under a full-digest "
        "collision no digest can identify which preimage the Seal covered, which is the "
        "point of the vector"
    ),
    "materialized_reducer_output_from": (
        "names which colliding variant's bytes the receiver already applied; the two "
        "variants share one digest, so no digest can distinguish them"
    ),
    "event_preimage_digest": "a digest field, not a stated preimage",
    "public_key_canonical_bytes": (
        "carries the assertion word 'stable' in the device-pairing edge case, not bytes"
    ),
}


# `schema-validation-fixture.json` primarily asserts JSON-Schema admissibility,
# so ordinary digest fields remain shaped placeholders. CanonicalPublicMaterial
# is the exception: its value/bytes/digest relationship is the type's defining
# structural contract and is checked explicitly below.
PLACEHOLDER_DIGEST_FIXTURES = {"schema-validation-fixture.json"}


# The naming convention for "this string is canonical preimage bytes". The pair
# table above MAY register key names outside the convention (`canonical_event_payload`);
# the convention is what the completeness guard enumerates.
STATED_PREIMAGE_KEY_RE = re.compile(r"preimage|canonical_bytes")



ONE_OF_REFERENCE_RE = re.compile(
    r"^(?:https://arkret\.org/v1/schemas/|schemas/|\./|\.\./schemas/)?"
    r"([A-Za-z0-9._-]+\.json)(#.*)?$"
)



FIELD_ORDER_RULES_PATH = TOOLS_ROOT / "field-order-rules.json"



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



# ---------------------------------------------------------------------------
# service-http-binding.md 2.2.2: request material supply closure
# ---------------------------------------------------------------------------

SUPPLY_EXEMPTION_REGISTRY_PATH = (
    ARTIFACTS / "registry" / "request-material-supply-exemption-registry.json"
)

SUPPLY_EXEMPTION_ID_RE = re.compile(
    r"^ak\.exemption\.request_material_supply\.[a-z0-9_]+\.v[0-9]+$"
)

_SUPPLY_ROW_KEYS_REQUEST = frozenset(
    {
        "exemption_id",
        "status",
        "kind",
        "operation_id",
        "json_path_prefix",
        "disposition",
        "rationale",
        "review_anchor",
    }
)

_SUPPLY_ROW_KEYS_FSM = frozenset(
    {
        "exemption_id",
        "status",
        "kind",
        "fsm_family",
        "states",
        "transitions",
        "disposition",
        "rationale",
        "review_anchor",
    }
)

_SUPPLY_ROW_KINDS = frozenset({"request_input", "fsm_transition"})

_SUPPLY_DISPOSITIONS = frozenset({"external_form", "open_finding", "deferred_supply"})


# Caller-owned material: self-signed proofs and signatures, caller-chosen
# parameters and content, caller-generated keys/nonces/ids, OAuth/PKCE values,
# W3C Data Integrity proof members, and digests over caller-authored content.
_SUPPLY_CLIENT_LOCAL_RE = re.compile(
    r"(^signature$|_signature$|^signed_|idempotency_key|request_id$|^nonce$|"
    r"client_|display_name|^name$|^slug$|^text$|^body$|^content$|^message$|"
    r"^reason$|^label$|^title$|^description$|public_key|keypackage|^keys$|"
    r"^payload_bytes$|^ciphertext|plaintext|^password|^locale$|^timezone$|"
    r"^limit$|^cursor$|^page|^filter|^query$|^purpose$|^kind$|^mode$|^scope$|"
    r"_proof$|^proof$|proof_kind|proof_jwt|^code$|code_verifier|redirect_uri|"
    r"blinded|^introduction_evidence$|^auth_data$|^proofPurpose$|^proofValue$|^verificationMethod$|"
    r"^cryptosuite$|^argument_digest$|recovery_secret)",
    re.I,
)

# Evidence-shaped leaves: third-party-signed facts a verifier relies on.
_SUPPLY_EVIDENCE_RE = re.compile(
    r"(receipt|evidence|attestation|bundle|notary|continuity|countersign|"
    r"service_binding)",
    re.I,
)

# CAS / echo-shaped leaves: server-state snapshots the caller must echo.
_SUPPLY_CAS_ECHO_RE = re.compile(
    r"(_ref$|_refs$|_digest$|predecessor|basis|lineage|_version$|_chain$)",
    re.I,
)

# Caller-signed objects: the schema pins the signing key to the caller itself,
# so the caller authors the bytes and no read surface owes them to it.
# join-policy.md 7 applicant/reviewer receipts; the recovery terminal receipt
# is signed by the replacement device's accepted device key (recovery-receipt
# .schema.json auth_data forbids service keys) and that same device is the
# issue_recovery_completion_grant caller. The security-rotation local commit is
# likewise authored from the returned transaction coordinates plus client-local
# device/time state and authenticated by the enclosing client_step_attestation;
# it is not third-party material for which a server supply surface is owed.
# Entries are schema identities: a $defs name or a bare-file schema path.
_SUPPLY_CALLER_SIGNED_SCHEMAS = frozenset(
    {
        "application_receipt",
        "review_receipt",
        "cancel_receipt",
        "AcceptedDevicePossessionProof",
        "PairwiseEndpointPossessionProof",
        "AgentSessionRefreshProof",
        "keypackages_claim_service_binding",
        "security_rotation_local_commit",
        "schemas/recovery-receipt.schema.json",
    }
)

# peer/edge submitters are servers or applet hosts presenting their own
# projections; open is the out-of-band handoff surface (QR / external
# protocol), so its inputs arrive outside the HTTP contract by design.
_SUPPLY_STRUCTURAL_SURFACES = frozenset({"peer", "edge", "open"})

_SUPPLY_PAYLOAD_SUPPLY_FILES = ("payload", "event-envelope.schema.json")



# ---------------------------------------------------------------------------
# service-http-binding.md 2.2.2: FSM state reachability
# ---------------------------------------------------------------------------

_FSM_CONTRACT_KEYS = frozenset(
    {
        "axis",
        "states",
        "terminal_states",
        "idempotent_replay",
        "concurrent_sibling_conflict",
        "allowed_transitions",
        "initial_state",
        "initial_states",
        "template",
        "instance_parameters",
        "state_preserving_profiles",
    }
)

_FSM_TEMPLATE_KEYS = frozenset(
    {
        "states",
        "initial_state",
        "initial_states",
        "terminal_states",
        "idempotent_replay",
        "concurrent_sibling_conflict",
        "allowed_transitions",
        "conditional_transitions",
        "parameter_schema",
    }
)

_FSM_ABSENT = "<absent>"



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



def markdown_section_body(text: str, anchor: str) -> str | None:
    """Text of the section owned by `anchor`, or None when it does not exist.

    The section runs from its heading line to the next heading of the same or
    higher level. Line endings are normalized so callers see the same bytes on
    every checkout.
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
    return "\n".join(lines[start:end]).rstrip() + "\n"



def markdown_section_digest(text: str, anchor: str) -> str | None:
    """sha256 of the section owned by `anchor`, or None when it does not exist."""
    body = markdown_section_body(text, anchor)
    if body is None:
        return None
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()



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



LONE_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")


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
        if LONE_SURROGATE_RE.search(value) is not None:
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
    def reject_legacy_auth_context_actor(
        event: dict[str, Any],
        event_path: str,
    ) -> None:
        auth_context = event.get("auth_context")
        if isinstance(auth_context, dict) and "actor_id" in auth_context:
            lint.fail(
                owner,
                f"{label}{event_path}.auth_context contains forbidden legacy actor_id; "
                "derive the signer from executed_by or actor_id",
            )

    for json_path, event, is_negative in event_envelope_candidates(
        value,
        negative_context=negative_context,
    ):
        reject_legacy_auth_context_actor(event, json_path)
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

    # Canonical transcript fixtures carry Event digest preimages as JSON strings.
    # Parse only the registered transcript field names so a removed wire member
    # cannot survive lint merely because it was escaped inside a string.
    transcript_fields = {
        "canonical_event_payload",
        "expected_canonical_bytes_utf8",
        "unsigned_jcs",
        "wire_utf8",
    }
    preimage_fields = {"kind", "actor_id", "actor_seq", "auth_context", "payload"}
    for string_path, child, key in walk_json(value):
        if key not in transcript_fields or not isinstance(child, str):
            continue
        try:
            parsed = json.loads(child)
        except json.JSONDecodeError:
            continue
        for parsed_path, candidate, _ in event_envelope_candidates(parsed):
            reject_legacy_auth_context_actor(candidate, f"{string_path}:{parsed_path}")
        if isinstance(parsed, dict) and preimage_fields.issubset(parsed):
            reject_legacy_auth_context_actor(parsed, f"{string_path}:$")
        for parsed_path, candidate, _ in walk_json(parsed):
            if isinstance(candidate, dict) and preimage_fields.issubset(candidate):
                reject_legacy_auth_context_actor(candidate, f"{string_path}:{parsed_path}")



def split_ref(ref: str) -> str:
    return ref.split("#", 1)[0]



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



def check_typed_id_token(lint: Lint, path: Path, json_path: str, token_kind: str, rest: str, known: dict[str, set[str]]) -> None:
    if token_kind == "blob" and (rest.startswith("sha256:") or rest.startswith("blake3:")):
        # id-kind-registry special form ak:blob:<digest-suite>:<digest>: every active
        # suite of digest-suite-registry.json, not only sha256 (encoding.md section 4).
        if not CONTENT_ADDRESSED_BLOB_PAYLOAD_RE.fullmatch(rest):
            lint.fail(path, f"{json_path} has invalid ak:blob:<digest-suite> content-addressed reference")
        return
    if token_kind in known["id_kinds"]:
        candidate = rest[:44] if token_kind in known.get("event_derived_id_kinds", set()) or token_kind in known.get("digest_token_id_kinds", set()) else rest[:36]
        # encoding.md section 4: the construction is fixed per registry kind.
        # event_derived kinds carry a canonical 33-byte suite-tagged token;
        # producer_allocated kinds stay UUIDv7.
        if token_kind == "realm":
            if not EVENT_TOKEN_RE.fullmatch(candidate):
                lint.fail(
                    path,
                    f"{json_path} has invalid ak:realm: expected canonical 44-char derivation-tagged token",
                )
                return
            try:
                token = base64.urlsafe_b64decode(candidate + "=" * (-len(candidate) % 4))
            except (ValueError, binascii.Error):
                lint.fail(path, f"{json_path} has invalid ak:realm: malformed Base64URL token")
                return
            if len(token) != 33:
                lint.fail(path, f"{json_path} has invalid ak:realm: decoded token must be 33 bytes")
                return
            reserved_nibble = token[0] >> 4
            digest_suite = token[0] & 0x0F
            if reserved_nibble != 0:
                lint.fail(
                    path,
                    f"{json_path} has invalid ak:realm: reserved high nibble must be 0x0, found 0x{reserved_nibble:x}",
                )
            if digest_suite != 1:
                lint.fail(path, f"{json_path} has invalid ak:realm: v1 Realm derivation is fixed to SHA-256")
        elif token_kind in known.get("digest_token_id_kinds", set()):
            if not EVENT_TOKEN_RE.fullmatch(candidate):
                lint.fail(
                    path,
                    f"{json_path} has invalid ak:{token_kind}: expected canonical 44-char suite-tagged token",
                )
                return
            try:
                token = base64.urlsafe_b64decode(candidate + "=" * (-len(candidate) % 4))
            except (ValueError, binascii.Error):
                lint.fail(path, f"{json_path} has invalid ak:{token_kind}: malformed Base64URL token")
                return
            if len(token) != 33 or token[0] != 0x01:
                lint.fail(path, f"{json_path} has invalid ak:{token_kind}: expected sha256 suite code plus 32 digest bytes")
        elif token_kind in known.get("event_derived_id_kinds", set()):
            if not EVENT_TOKEN_RE.fullmatch(candidate):
                lint.fail(
                    path,
                    f"{json_path} has invalid ak:{token_kind}: expected canonical 44-char Event-derived token",
                )
                return
            try:
                token = base64.urlsafe_b64decode(candidate + "=" * (-len(candidate) % 4))
            except (ValueError, binascii.Error):
                lint.fail(path, f"{json_path} has invalid ak:{token_kind}: malformed Base64URL token")
                return
            if (
                len(token) != 33
                or base64.urlsafe_b64encode(token).decode("ascii").rstrip("=") != candidate
            ):
                lint.fail(path, f"{json_path} has invalid ak:{token_kind}: non-canonical 33-byte token")
                return
            if token[0] >> 4 != 0:
                lint.fail(path, f"{json_path} has invalid ak:{token_kind}: Event reserved nibble must be zero")
                return
            # The leading byte is the digest-suite wire code, and only the
            # registry's active codes exist. Checking the shape but not the code
            # is how a placeholder token of zero bytes passed as an Event id.
            active_codes = known.get("active_digest_suite_wire_codes") or set()
            if active_codes and (token[0] & 0x0F) not in active_codes:
                lint.fail(
                    path,
                    f"{json_path} has invalid ak:{token_kind}: digest-suite wire code "
                    f"0x{token[0] & 0x0F:x} is not an active registered suite",
                )
                return
        elif not UUID7_RE.fullmatch(candidate):
            lint.fail(path, f"{json_path} has invalid ak:{token_kind}: typed UUIDv7 reference")
        return
    if token_kind in known["special_id_kinds"]:
        if not rest:
            lint.fail(path, f"{json_path} has empty ak:{token_kind}: special reference")
        return
    lint.fail(path, f"{json_path} references unregistered typed ID kind: ak:{token_kind}:")



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



def jsonschema_errors(
    lint: Lint,
    owner: Path,
    schema_ref: str,
    instance: Any,
    *,
    first_only: bool = False,
) -> list[str]:
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
            error_iter = validator.iter_errors(instance)
            if first_only:
                first = next(error_iter, None)
                errors = [] if first is None else [first]
            else:
                errors = sorted(error_iter, key=lambda error: list(error.path))
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
    errors = jsonschema_errors(
        lint,
        owner,
        schema_ref,
        instance,
        first_only=not expect_valid and first_expected_error is None,
    )
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



def _supply_schema_files(lint: Lint) -> dict[str, Any]:
    files: dict[str, Any] = {}
    for path in sorted((ARTIFACTS / "schemas").glob("*.json")):
        data = load_json(lint, path)
        if isinstance(data, dict):
            files[f"schemas/{path.name}"] = data
    return files



def _supply_resolve_ref(
    schema_files: dict[str, Any], cur_file: str, ref: str
) -> tuple[str, str, str, Any] | None:
    if ref.startswith("#"):
        file = cur_file
        frag = ref[1:]
    else:
        file_part, _, frag = ref.partition("#")
        file = file_part
        if file.startswith("./"):
            file = "schemas/" + file[2:]
        elif not file.startswith("schemas/"):
            file = "schemas/" + file.rsplit("/", 1)[-1]
    node = schema_files.get(file)
    if node is None:
        return None
    defname = f"<root:{file}>"
    frag = frag.lstrip("/")
    if frag:
        for part in frag.split("/"):
            if not isinstance(node, dict):
                return None
            node = node.get(part)
            if node is None:
                return None
            defname = part
    identity = f"#/{frag}" if frag else f"<root:{file}>"
    return (file, defname, identity, node)



def _supply_load_exemptions(lint: Lint) -> list[dict[str, Any]]:
    path = SUPPLY_EXEMPTION_REGISTRY_PATH
    data = load_json(lint, path)
    if not isinstance(data, dict):
        return []
    rows = data.get("exemptions")
    if not isinstance(rows, list) or not rows:
        lint.fail(path, "exemptions must be a non-empty list")
        return []
    workspace_root = ROOT.parent
    seen_ids: set[str] = set()
    valid_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        label = f"exemptions[{index}]"
        if not isinstance(row, dict):
            lint.fail(path, f"{label} must be an object")
            continue
        row_kind = row.get("kind")
        if row_kind not in _SUPPLY_ROW_KINDS:
            lint.fail(
                path,
                f"{label}.kind must be one of {sorted(_SUPPLY_ROW_KINDS)}",
            )
            continue
        expected_keys = (
            _SUPPLY_ROW_KEYS_REQUEST
            if row_kind == "request_input"
            else _SUPPLY_ROW_KEYS_FSM
        )
        if set(row.keys()) != expected_keys:
            lint.fail(
                path,
                f"{label} keys must be exactly {sorted(expected_keys)} for kind {row_kind}",
            )
            continue
        exemption_id = row.get("exemption_id")
        if not isinstance(exemption_id, str) or not SUPPLY_EXEMPTION_ID_RE.fullmatch(
            exemption_id
        ):
            lint.fail(path, f"{label}.exemption_id must match the registry id pattern")
            continue
        label = exemption_id
        if exemption_id in seen_ids:
            lint.fail(path, f"{label}: duplicate exemption_id")
            continue
        seen_ids.add(exemption_id)
        if row.get("status") not in ("active", "retired"):
            lint.fail(path, f"{label}.status must be active or retired")
            continue
        disposition = row.get("disposition")
        if disposition not in _SUPPLY_DISPOSITIONS:
            lint.fail(
                path,
                f"{label}.disposition must be one of {sorted(_SUPPLY_DISPOSITIONS)}",
            )
            continue
        if row_kind == "request_input":
            if not isinstance(row.get("operation_id"), str) or not isinstance(
                row.get("json_path_prefix"), str
            ):
                lint.fail(
                    path, f"{label}: operation_id and json_path_prefix must be strings"
                )
                continue
        else:
            transitions = row.get("transitions")
            states = row.get("states")
            if (
                not isinstance(row.get("fsm_family"), str)
                or not isinstance(states, list)
                or not all(isinstance(state, str) for state in states)
                or not isinstance(transitions, list)
                or not all(
                    isinstance(pair, list)
                    and len(pair) == 2
                    and all(isinstance(state, str) for state in pair)
                    for pair in transitions
                )
            ):
                lint.fail(
                    path,
                    f"{label}: fsm_transition rows need fsm_family, states[] and transitions[][2]",
                )
                continue
        rationale = row.get("rationale")
        if not isinstance(rationale, str) or len(rationale) < 40:
            lint.fail(
                path,
                f"{label}.rationale must explain the exemption (>= 40 chars)",
            )
            continue
        anchor = row.get("review_anchor")
        if disposition in ("open_finding", "deferred_supply"):
            if (
                not isinstance(anchor, dict)
                or not isinstance(anchor.get("file"), str)
                or not isinstance(anchor.get("heading"), str)
            ):
                lint.fail(
                    path,
                    f"{label}: {disposition} rows must carry review_anchor.file and .heading",
                )
                continue
            anchor_path = workspace_root / anchor["file"]
            if (workspace_root / "arkret-work").is_dir():
                if not anchor_path.is_file():
                    lint.fail(
                        path,
                        f"{label}: review_anchor file {anchor['file']} does not exist",
                    )
                    continue
                if anchor["heading"] not in anchor_path.read_text(encoding="utf-8"):
                    lint.fail(
                        path,
                        f"{label}: review_anchor heading not found in {anchor['file']}",
                    )
                    continue
        elif anchor is not None:
            lint.fail(path, f"{label}: external_form rows must set review_anchor null")
            continue
        if row.get("status") == "active":
            valid_rows.append(row)
    return valid_rows
