"""Proof-context object families must own a registered schema.

``proof-context-registry.json`` is the closed inventory of signing surfaces: a
``contexts[]`` row anchors a terminal use point of the shared Event detached-proof
leaf, and a ``domain_separations[]`` row with primitive ``detached_signature``
anchors a locally declared signature leaf. Either way the row names an
``object_family`` -- a real wire object that some producer signs and some
receiver verifies.

Before this gate a row could name an object family that no schema described.
``controller_account_gate_attestation`` sat in ``domain_separations[]`` with ten
``binding_fields`` and no ``schema_ref`` at all, so the registry promised a
signed object whose members, types and closure existed only in prose; a
downstream implementation had to guess them, and a ``schema`` member spelling an
unregistered ``ak.schema.*.v1`` id could not be caught anywhere. The existing
``check_proof_context_registry`` closes the shared-proof surface in both
directions but treats ``domain_separations[].schema_ref`` as optional, so this
hole was invisible to it.

The rule, per in-scope row:

* the row MUST declare ``schema_ref`` or a non-empty ``transcript_schema_refs``;
* every referenced file MUST be an ``active`` row of ``schema-registry.json``,
  so the object family is covered by a registered ``ak.schema.*.v1`` id;
* every reference MUST resolve to a real schema object inside that file.

Primitives that are transcripts or namespaces rather than standalone wire
objects (``merkle_*``, ``hpke_info``, ``replay_cache_namespace``,
``canonical_json_sha256``, ``http_message_signature``) are out of scope by
construction: they bind bytes assembled from an enclosing carrier, not an object
family of their own.

``check_result_write_contracts`` is in the same module for the same reason: a
``result_writes[]`` contract that no gate reads is the same failure mode one
level down.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import posixpath
import re
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .core import (
    ARTIFACTS,
    CELL_WRITE_DERIVATIONS,
    Lint,
    SPEC_ROOT,
    TOOLS_ROOT,
    load_json,
    jsonschema_errors,
    read_text,
    resolve_json_pointer,
)

PROOF_CONTEXT_REGISTRY = ARTIFACTS / "registry" / "proof-context-registry.json"
SCHEMA_REGISTRY = ARTIFACTS / "registry" / "schema-registry.json"
EVENT_KIND_REGISTRY = ARTIFACTS / "registry" / "event-kind-registry.json"
CONTRACT_REGISTRY = ARTIFACTS / "registry" / "contract-registry.json"
SERVICE_KIND_REGISTRY = ARTIFACTS / "registry" / "service-kind-registry.json"
VECTOR_REGISTRY = ARTIFACTS / "registry" / "vector-registry.json"
REALM_JOIN_CANDIDATE_SCHEMA = ARTIFACTS / "schemas" / "realm-join-candidate.schema.json"
REALM_JOIN_CANDIDATE_FIXTURE = ARTIFACTS / "fixtures" / "realm-join-candidate-locator-fixture.json"
DETACHED_OBJECT_SIGNATURE_SCHEMA = ARTIFACTS / "schemas" / "detached-object-signature.schema.json"
DETACHED_OBJECT_SIGNATURE_FIXTURE = ARTIFACTS / "fixtures" / "detached-object-signature-kat-fixture.json"
REALM_JOIN_INTAKE_SCHEMA = ARTIFACTS / "schemas" / "realm-join-intake.schema.json"
INVITE_DELIVERY_REQUEST_SCHEMA = ARTIFACTS / "schemas" / "invite-delivery-request.schema.json"
INVITE_DELIVERY_SCHEMA = ARTIFACTS / "schemas" / "invite-delivery.schema.json"
DIRECTORY_OPERATIONS_SCHEMA = ARTIFACTS / "schemas" / "directory-operations.schema.json"
REALM_JOIN_LOCATOR_PROSE_FILES = (
    SPEC_ROOT / "zh" / "discovery" / "discovery-directory.md",
    SPEC_ROOT / "zh" / "governance" / "join-policy.md",
    SPEC_ROOT / "zh" / "sync" / "invite-addressing.md",
    SPEC_ROOT / "zh" / "sync" / "service-surface.md",
)

# Only these primitives describe a standalone signed wire object. Everything else
# in DOMAIN_SEPARATION_PRIMITIVES binds bytes gathered from an enclosing carrier.
OBJECT_BEARING_PRIMITIVES = frozenset({"detached_signature"})

REALM_JOIN_CANDIDATE_SCHEMA_ID = "ak.schema.realm_join_candidate.v1"
REALM_JOIN_CANDIDATE_VECTOR_ID = "ak.vector.realm_join_candidate.untrusted_locator.v1"
REALM_JOIN_CANDIDATE_REMOVED_CONTEXT = "ak.realm_join_candidate_proof.v1"
REALM_JOIN_CANDIDATE_REMOVED_FAMILY = "realm_join_candidate"
REALM_JOIN_CANDIDATE_PROPERTIES = (
    "service_kind",
    "service_id",
    "endpoint_url",
    "source",
)
REALM_JOIN_CANDIDATE_REQUIRED = (
    "service_kind",
    "service_id",
    "source",
)
REALM_JOIN_CANDIDATE_SOURCES = ("invite", "directory", "cache")
REALM_JOIN_CANDIDATE_FORBIDDEN_FIELDS = frozenset(
    {
        "realm_id",
        "observed_at",
        "expires_at",
        "proof",
        "proofs",
        "signature",
        "verification_method",
        "seal_basis",
        "frontier_ref",
        "source_refs",
        "role",
        "operations",
        "join_methods",
        "encryption_profile",
        "digest_profile",
        "priority",
        "authority",
        "authority_generation",
        "governance_station_id",
        "current_authority",
        "authority_bundle",
    }
)
REALM_JOIN_CANDIDATE_FORBIDDEN_DESCRIPTION_CLAIMS = (
    "already selected",
    "join-forwarding target",
    "join-forwarding authority",
)
REALM_JOIN_CANDIDATE_FIXTURE_FORBIDDEN_FIELDS = (
    # current-v1's vocabulary guard rejects this historical token even in a
    # negative fixture; the dedicated schema mutation test still covers it.
    REALM_JOIN_CANDIDATE_FORBIDDEN_FIELDS - {"frontier_ref"}
)


def _unique_registry_row(
    lint: Lint,
    path: Path,
    rows: Any,
    key: str,
    value: str,
) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        lint.fail(path, f"expected an array containing the {value!r} row")
        return None
    matches = [row for row in rows if isinstance(row, dict) and row.get(key) == value]
    if len(matches) != 1:
        lint.fail(path, f"expected exactly one {key}={value!r} row, found {len(matches)}")
        return None
    return matches[0]


def _schema_property_names(node: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict):
            names.update(name for name in properties if isinstance(name, str))
        for value in node.values():
            names.update(_schema_property_names(value))
    elif isinstance(node, list):
        for value in node:
            names.update(_schema_property_names(value))
    return names


def _check_locator_description(lint: Lint, path: Path, where: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        lint.fail(path, f"{where} description must be a non-empty string")
        return
    lowered = value.casefold()
    for required in ("untrusted", "locator"):
        if required not in lowered:
            lint.fail(path, f"{where} description must contain {required!r}")
    for forbidden in REALM_JOIN_CANDIDATE_FORBIDDEN_DESCRIPTION_CLAIMS:
        if forbidden in lowered:
            lint.fail(
                path,
                f"{where} description retains the authority-elevating claim {forbidden!r}",
            )
    if "time-bounded" in lowered:
        lint.fail(path, f"{where} description must not assign locator-specific time bounds")


def check_realm_join_candidate_locator_contract(lint: Lint) -> None:
    """Keep RealmJoinCandidate a closed, untrusted authority-bundle locator.

    A discovery candidate only gives an invitee Station somewhere to request a
    nonce-bound authority bundle. It is not a proof, a current-authority
    selection, or permission to submit a join directly. This gate binds that
    distinction across the schema, both schema catalogs, the service-kind
    context, and the proof-context registry so no one surface can silently
    promote the locator back into authority.
    """

    proof_registry = load_json(lint, PROOF_CONTEXT_REGISTRY)
    if isinstance(proof_registry, dict):
        for collection in ("contexts", "domain_separations"):
            rows = proof_registry.get(collection)
            if not isinstance(rows, list):
                continue
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                if (
                    row.get("context") == REALM_JOIN_CANDIDATE_REMOVED_CONTEXT
                    or row.get("domain") == REALM_JOIN_CANDIDATE_REMOVED_CONTEXT
                ):
                    lint.fail(
                        PROOF_CONTEXT_REGISTRY,
                        f"{collection}[{index}] restores the removed RealmJoinCandidate proof "
                        "context",
                    )
                if row.get("object_family") == REALM_JOIN_CANDIDATE_REMOVED_FAMILY:
                    lint.fail(
                        PROOF_CONTEXT_REGISTRY,
                        f"{collection}[{index}] promotes the RealmJoinCandidate locator to a proof "
                        "object family",
                    )

    schema = load_json(lint, REALM_JOIN_CANDIDATE_SCHEMA)
    if isinstance(schema, dict):
        properties = schema.get("properties")
        property_names = set(properties) if isinstance(properties, dict) else set()
        if property_names != set(REALM_JOIN_CANDIDATE_PROPERTIES):
            lint.fail(
                REALM_JOIN_CANDIDATE_SCHEMA,
                "properties must be the exact closed RealmJoinCandidate locator field set "
                f"{list(REALM_JOIN_CANDIDATE_PROPERTIES)!r}",
            )
        if set(schema.get("required") or ()) != set(REALM_JOIN_CANDIDATE_REQUIRED):
            lint.fail(
                REALM_JOIN_CANDIDATE_SCHEMA,
                f"required must equal {list(REALM_JOIN_CANDIDATE_REQUIRED)!r}",
            )
        if schema.get("additionalProperties") is not False:
            lint.fail(REALM_JOIN_CANDIDATE_SCHEMA, "additionalProperties must be false")
        if isinstance(properties, dict):
            service_kind = properties.get("service_kind")
            if not isinstance(service_kind, dict) or service_kind.get("enum") != ["station"]:
                lint.fail(
                    REALM_JOIN_CANDIDATE_SCHEMA,
                    "properties.service_kind.enum must equal ['station']",
                )
            source = properties.get("source")
            if not isinstance(source, dict) or set(source.get("enum") or ()) != set(
                REALM_JOIN_CANDIDATE_SOURCES
            ):
                lint.fail(
                    REALM_JOIN_CANDIDATE_SCHEMA,
                    f"properties.source.enum must equal {list(REALM_JOIN_CANDIDATE_SOURCES)!r}",
                )
            endpoint = properties.get("endpoint_url")
            if (
                not isinstance(endpoint, dict)
                or endpoint.get("type") != "string"
                or endpoint.get("format") != "uri"
                or endpoint.get("pattern") != "^https://"
            ):
                lint.fail(
                    REALM_JOIN_CANDIDATE_SCHEMA,
                    "properties.endpoint_url must retain the canonical HTTPS URI constraint",
                )
        forbidden_fields = sorted(
            _schema_property_names(schema) & REALM_JOIN_CANDIDATE_FORBIDDEN_FIELDS
        )
        if forbidden_fields:
            lint.fail(
                REALM_JOIN_CANDIDATE_SCHEMA,
                f"locator schema contains authority-elevating fields {forbidden_fields!r}",
            )
        _check_locator_description(
            lint, REALM_JOIN_CANDIDATE_SCHEMA, "schema", schema.get("description")
        )

    schema_registry = load_json(lint, SCHEMA_REGISTRY)
    if isinstance(schema_registry, dict):
        row = _unique_registry_row(
            lint,
            SCHEMA_REGISTRY,
            schema_registry.get("schemas"),
            "schema_id",
            REALM_JOIN_CANDIDATE_SCHEMA_ID,
        )
        if row is not None:
            _check_locator_description(
                lint, SCHEMA_REGISTRY, "schema-registry row", row.get("description")
            )

    contract_registry = load_json(lint, CONTRACT_REGISTRY)
    if isinstance(contract_registry, dict):
        embedded = contract_registry.get("schema_registry")
        rows = embedded.get("schemas") if isinstance(embedded, dict) else None
        row = _unique_registry_row(
            lint,
            CONTRACT_REGISTRY,
            rows,
            "schema_id",
            REALM_JOIN_CANDIDATE_SCHEMA_ID,
        )
        if row is not None:
            _check_locator_description(
                lint, CONTRACT_REGISTRY, "contract-registry row", row.get("description")
            )

    service_registry = load_json(lint, SERVICE_KIND_REGISTRY)
    if isinstance(service_registry, dict):
        row = _unique_registry_row(
            lint,
            SERVICE_KIND_REGISTRY,
            service_registry.get("contexts"),
            "id",
            "realm_join_candidate",
        )
        if row is not None:
            _check_locator_description(
                lint, SERVICE_KIND_REGISTRY, "service-kind context", row.get("description")
            )

    vector_registry = load_json(lint, VECTOR_REGISTRY)
    if isinstance(vector_registry, dict):
        row = _unique_registry_row(
            lint,
            VECTOR_REGISTRY,
            vector_registry.get("vectors"),
            "vector_id",
            REALM_JOIN_CANDIDATE_VECTOR_ID,
        )
        if row is not None:
            if row.get("status") != "active" or row.get("applies_to_fixtures") != [
                REALM_JOIN_CANDIDATE_FIXTURE.name
            ]:
                lint.fail(
                    VECTOR_REGISTRY,
                    "RealmJoinCandidate locator vector must be active and bind its sole fixture",
                )

    fixture = load_json(lint, REALM_JOIN_CANDIDATE_FIXTURE)
    if isinstance(fixture, dict):
        if fixture.get("vector_id") != REALM_JOIN_CANDIDATE_VECTOR_ID:
            lint.fail(REALM_JOIN_CANDIDATE_FIXTURE, "fixture vector_id is not the registered locator vector")
        candidate = fixture.get("accepted_candidate")
        if not isinstance(candidate, dict) or set(candidate) != set(REALM_JOIN_CANDIDATE_PROPERTIES):
            lint.fail(REALM_JOIN_CANDIDATE_FIXTURE, "accepted candidate must use the exact locator field set")
        trust = fixture.get("trust_contract")
        required_trust = {
            "candidate_is_authority": False,
            "candidate_is_authorization": False,
            "candidate_is_identity_selector": False,
            "candidate_signature_can_raise_trust": False,
            "client_submits_to_own_station": True,
            "own_station_fetches_nonce_bound_authority_bundle": True,
            "current_governance_station_source": "verified_realm_genesis_and_continuous_handoff_chain",
            "conflicting_authority_chains": "fail_closed",
        }
        if trust != required_trust:
            lint.fail(REALM_JOIN_CANDIDATE_FIXTURE, "fixture trust contract must pin locator-only authority semantics")
        rejected = fixture.get("rejected_additional_members")
        if not isinstance(rejected, list) or not REALM_JOIN_CANDIDATE_FIXTURE_FORBIDDEN_FIELDS.issubset(
            {value for value in rejected if isinstance(value, str)}
        ):
            lint.fail(REALM_JOIN_CANDIDATE_FIXTURE, "fixture must reject every authority-elevating field")


def realm_join_locator_array_errors(value: Any) -> list[str]:
    """Validate the non-JSON-Schema ordering and semantic-identity contract."""

    errors: list[str] = []
    if not isinstance(value, list):
        return ["locator array must be an array"]
    if not 1 <= len(value) <= 8:
        errors.append("locator array item count must be within 1..8")
    previous: bytes | None = None
    seen: set[str] = set()
    for index, candidate in enumerate(value):
        if not isinstance(candidate, dict):
            errors.append(f"locator[{index}] must be an object")
            continue
        service_id = candidate.get("service_id")
        if not isinstance(service_id, str) or not service_id:
            errors.append(f"locator[{index}].service_id must be a non-empty string")
            continue
        key = service_id.encode("utf-8")
        if service_id in seen:
            errors.append(f"locator[{index}] duplicates semantic service_id {service_id!r}")
        seen.add(service_id)
        if previous is not None and key <= previous:
            errors.append("locator array must be strictly sorted by service_id UTF-8 bytes")
        previous = key
    return errors


def _nested_schema_node(document: Any, *keys: str) -> Any:
    node = document
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _check_realm_join_locator_array_schema(
    lint: Lint,
    path: Path,
    document: Any,
    node_keys: tuple[str, ...],
    *,
    required_owner_keys: tuple[str, ...],
    field_name: str,
    must_be_required: bool,
) -> None:
    node = _nested_schema_node(document, *node_keys)
    if not isinstance(node, dict):
        lint.fail(path, f"{'.'.join(node_keys)} must define a locator array")
        return
    expected_ref = "./realm-join-candidate.schema.json"
    if (
        node.get("type") != "array"
        or node.get("minItems") != 1
        or node.get("maxItems") != 8
        or node.get("uniqueItems") is not True
        or node.get("items") != {"$ref": expected_ref}
    ):
        lint.fail(
            path,
            f"{'.'.join(node_keys)} must be a 1..8 uniqueItems array directly referencing {expected_ref}",
        )
    description = node.get("description")
    if not isinstance(description, str) or not all(
        phrase in description
        for phrase in ("service_id", "UTF-8 bytes", "semantic identity", "entire array")
    ):
        lint.fail(
            path,
            f"{'.'.join(node_keys)} must register bytewise ordering, semantic identity, and whole-array rejection",
        )
    owner = _nested_schema_node(document, *required_owner_keys)
    required = owner.get("required") if isinstance(owner, dict) else None
    present = isinstance(required, list) and field_name in required
    if present != must_be_required:
        disposition = "required" if must_be_required else "optional for disclosure"
        lint.fail(path, f"{'.'.join(node_keys)} must remain {disposition}")


def check_realm_join_locator_carriers_and_bounds(lint: Lint) -> None:
    """Pin one locator core, all carrier refs, bounds, and semantic uniqueness."""

    intake = load_json(lint, REALM_JOIN_INTAKE_SCHEMA)
    if isinstance(intake, dict):
        definitions = intake.get("$defs")
        if isinstance(definitions, dict) and "authority_locator_hint" in definitions:
            lint.fail(REALM_JOIN_INTAKE_SCHEMA, "$defs.authority_locator_hint must not exist")
        _check_realm_join_locator_array_schema(
            lint,
            REALM_JOIN_INTAKE_SCHEMA,
            intake,
            ("$defs", "join_target", "properties", "authority_locator_hints"),
            required_owner_keys=("$defs", "join_target"),
            field_name="authority_locator_hints",
            must_be_required=True,
        )

    invite_request = load_json(lint, INVITE_DELIVERY_REQUEST_SCHEMA)
    if isinstance(invite_request, dict):
        _check_realm_join_locator_array_schema(
            lint,
            INVITE_DELIVERY_REQUEST_SCHEMA,
            invite_request,
            ("properties", "authority_locator_hints"),
            required_owner_keys=(),
            field_name="authority_locator_hints",
            must_be_required=True,
        )

    invite_delivery = load_json(lint, INVITE_DELIVERY_SCHEMA)
    if isinstance(invite_delivery, dict):
        _check_realm_join_locator_array_schema(
            lint,
            INVITE_DELIVERY_SCHEMA,
            invite_delivery,
            ("$defs", "delivery_entry", "properties", "authority_locator_hints"),
            required_owner_keys=("$defs", "delivery_entry"),
            field_name="authority_locator_hints",
            must_be_required=True,
        )

    fixture = load_json(lint, REALM_JOIN_CANDIDATE_FIXTURE)
    if isinstance(fixture, dict):
        array_contract = fixture.get("locator_array_contract")
        expected_contract = {
            "min_items": 1,
            "max_items": 8,
            "sort_key": "service_id_utf8_bytes",
            "semantic_identity_key": "service_id",
            "duplicate_or_conflicting_identity": "reject_entire_array",
            "directory_field_may_be_omitted": True,
            "explicit_empty_array_is_valid": False,
        }
        if array_contract != expected_contract:
            lint.fail(REALM_JOIN_CANDIDATE_FIXTURE, "locator_array_contract must pin bounds, ordering, identity, and omission")
        accepted = fixture.get("accepted_sorted_candidates")
        errors = realm_join_locator_array_errors(accepted)
        if errors:
            lint.fail(REALM_JOIN_CANDIDATE_FIXTURE, f"accepted_sorted_candidates is invalid: {errors!r}")
        rejected = fixture.get("rejected_locator_arrays")
        required_cases = {
            "exact_duplicate",
            "same_service_different_source",
            "same_service_different_endpoint",
            "same_service_missing_endpoint",
            "reverse_service_id_order",
            "empty_array",
        }
        actual_cases = {
            row.get("name") for row in rejected if isinstance(row, dict)
        } if isinstance(rejected, list) else set()
        if actual_cases != required_cases:
            lint.fail(REALM_JOIN_CANDIDATE_FIXTURE, "rejected_locator_arrays must cover every duplicate, conflict, order, and empty case")
        expected_freshness = {
            "directory": "enclosing_as_of_and_stale",
            "invite": "enclosing_invite_expires_at",
            "join": "enclosing_realm_id_and_nonce_bound_current_assertion",
            "locator_specific_ttl_or_skew": False,
        }
        if fixture.get("freshness_contract") != expected_freshness:
            lint.fail(REALM_JOIN_CANDIDATE_FIXTURE, "freshness_contract must keep scope and freshness on enclosing carriers")
        assertion_cases = fixture.get("authority_assertion_cases")
        expected_assertion_cases = {
            "directory_stale_false_only": "reject_as_authority",
            "invite_unexpired_only": "reject_as_authority",
            "endpoint_reachable_only": "reject_as_authority",
            "current_assertion_missing": "reject_join",
            "current_assertion_expired": "reject_join",
            "current_assertion_nonce_mismatch": "reject_join",
            "verified_chain_and_valid_nonce_bound_current_assertion": "accept_current_authority",
        }
        actual_assertion_cases = {
            row.get("name"): row.get("expected")
            for row in assertion_cases
            if isinstance(row, dict)
        } if isinstance(assertion_cases, list) else {}
        if actual_assertion_cases != expected_assertion_cases:
            lint.fail(REALM_JOIN_CANDIDATE_FIXTURE, "authority_assertion_cases must reject weak freshness signals and require a valid nonce-bound assertion")

    forbidden_prose = (
        "`realm_id` MUST 等于解析结果的 canonical Realm ID",
        "`observed_at` 与 `expires_at` 定义 locator 缓存窗口",
        '"observed_at": "2026-05-10T07:55:12Z"',
        '"expires_at": "2026-05-10T08:05:12Z"',
    )
    for path in REALM_JOIN_LOCATOR_PROSE_FILES:
        text = read_text(path)
        for snippet in forbidden_prose:
            if snippet in text:
                lint.fail(path, f"prose restores removed per-locator scope/time material: {snippet!r}")
        if re.search(r"\bauthority_locator_hint\b", text):
            lint.fail(path, "prose restores the removed private authority_locator_hint DTO name")


def _registered_schema_files(lint: Lint) -> tuple[set[str], dict[str, str]] | None:
    registry = load_json(lint, SCHEMA_REGISTRY)
    rows = registry.get("schemas") if isinstance(registry, dict) else None
    if not isinstance(rows, list) or not rows:
        lint.fail(SCHEMA_REGISTRY, "schemas[] must be a non-empty array")
        return None
    files: set[str] = set()
    effective: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("status", "active") != "active":
            continue
        file_ref = row.get("file")
        schema_id = row.get("schema_id")
        if not isinstance(file_ref, str) or not isinstance(schema_id, str):
            continue
        files.add(file_ref)
        fragment = row.get("fragment")
        effective[file_ref + (fragment if isinstance(fragment, str) else "")] = schema_id
    return files, effective


def _covering_schema_id(effective: dict[str, str], file_ref: str, fragment: str) -> str | None:
    """The registered id whose effective reference best covers ``file_ref#fragment``."""
    best: tuple[int, str] | None = None
    for reference, schema_id in effective.items():
        ref_file, _, ref_fragment = reference.partition("#")
        if ref_file != file_ref:
            continue
        ref_pointer = f"#{ref_fragment}" if ref_fragment else ""
        if ref_pointer and not (fragment == ref_pointer or fragment.startswith(ref_pointer + "/")):
            continue
        if best is None or len(ref_pointer) > best[0]:
            best = (len(ref_pointer), schema_id)
    return None if best is None else best[1]


def _in_scope_rows(data: dict[str, Any]) -> list[tuple[str, int, dict[str, Any]]]:
    rows: list[tuple[str, int, dict[str, Any]]] = []
    for index, row in enumerate(data.get("contexts") or []):
        if isinstance(row, dict):
            rows.append(("contexts", index, row))
    for index, row in enumerate(data.get("domain_separations") or []):
        if isinstance(row, dict) and row.get("primitive") in OBJECT_BEARING_PRIMITIVES:
            rows.append(("domain_separations", index, row))
    return rows


def check_proof_context_object_family_schemas(lint: Lint) -> None:
    """Every signing object family must resolve to a registered schema."""
    data = load_json(lint, PROOF_CONTEXT_REGISTRY)
    if not isinstance(data, dict):
        lint.fail(PROOF_CONTEXT_REGISTRY, "proof context registry must be an object")
        return
    registered = _registered_schema_files(lint)
    if registered is None:
        return
    files, effective = registered

    documents: dict[str, Any] = {}

    def document(file_ref: str) -> Any:
        if file_ref not in documents:
            path = ARTIFACTS / file_ref
            documents[file_ref] = load_json(lint, path) if path.is_file() else None
        return documents[file_ref]

    for array_name, index, row in _in_scope_rows(data):
        where = f"{array_name}[{index}]"
        family = row.get("object_family")
        label = family if isinstance(family, str) and family else where
        references: list[str] = []
        schema_ref = row.get("schema_ref")
        if isinstance(schema_ref, str) and schema_ref:
            references.append(schema_ref)
        transcript_refs = row.get("transcript_schema_refs")
        if isinstance(transcript_refs, list):
            references.extend(item for item in transcript_refs if isinstance(item, str) and item)
        if not references:
            lint.fail(
                PROOF_CONTEXT_REGISTRY,
                f"{where} object_family {label!r} signs a wire object but names no schema; "
                "declare schema_ref (or transcript_schema_refs) pointing at a schema registered "
                "in registry/schema-registry.json",
            )
            continue
        for reference in references:
            file_ref, separator, fragment_body = reference.partition("#")
            fragment = f"#{fragment_body}" if separator else ""
            if file_ref not in files:
                lint.fail(
                    PROOF_CONTEXT_REGISTRY,
                    f"{where} object_family {label!r} points at {file_ref}, which is not an "
                    "active row of registry/schema-registry.json",
                )
                continue
            node = document(file_ref)
            if node is None:
                lint.fail(
                    PROOF_CONTEXT_REGISTRY,
                    f"{where} object_family {label!r} points at {file_ref}, which does not exist",
                )
                continue
            try:
                resolved = resolve_json_pointer(node, fragment)
            except (KeyError, IndexError, ValueError):
                resolved = None
            if not isinstance(resolved, dict):
                lint.fail(
                    PROOF_CONTEXT_REGISTRY,
                    f"{where} object_family {label!r} reference {reference} does not resolve to a "
                    "schema object",
                )
                continue
            if _covering_schema_id(effective, file_ref, fragment) is None:
                lint.fail(
                    PROOF_CONTEXT_REGISTRY,
                    f"{where} object_family {label!r} reference {reference} is not covered by any "
                    "registered schema id",
                )


ANCHOR_EXEMPTIONS = TOOLS_ROOT / "proof-context-anchor-exemptions.json"
FORBIDDEN_WIRE_FIELDS = ARTIFACTS / "registry" / "forbidden-wire-fields.json"
FORBIDDEN_EVENT_CONTEXT = "producer_event_envelope_root"


def _row_is_anchored(row: dict[str, Any]) -> bool:
    """Require an explicit independent definition; a bare occurrence is not one.

    Schema references are resolved by the proof-context schema gates and prose
    fragments by ``check_artifact_fragment_targets``.  This gate owns the
    structural requirement that a row name one of those anchors instead of
    searching a large corpus for an unqualified family/domain substring.  A
    fixture, profile or generated view may exercise or project a contract, but
    merely repeating its label cannot define that contract.
    """
    if isinstance(row.get("schema_ref"), str) and row["schema_ref"]:
        return True
    transcript_refs = row.get("transcript_schema_refs")
    if isinstance(transcript_refs, list) and any(
        isinstance(item, str) and item for item in transcript_refs
    ):
        return True
    for field in ("defined_in", "transcript_defined_in"):
        if isinstance(row.get(field), str) and row[field]:
            return True
    return False


def check_proof_context_carrier_family_anchors(lint: Lint) -> None:
    """A carrier-bound domain separation must be defined somewhere, not only here.

    ``check_proof_context_object_family_schemas`` deliberately exempts the
    primitives that bind bytes assembled from an enclosing carrier -- they have
    no standalone wire object to point a ``schema_ref`` at. That exemption left
    the whole carrier half of ``domain_separations[]`` with no reachability
    requirement at all, and ``ak.events.checkpoint.leaf/node/root.v1`` lived
    there for exactly that reason: three registered Merkle separators whose
    producer, verifier, commitment and failure mode appeared in no prose, no
    schema, no vector and no fixture, while ``zh/sync/authority-commit-log.md``
    section 7 states that a v1 Snapshot carries no state root and no sparse
    Merkle proof. A registered domain separation is a promise that some byte
    string is computed under that label; when nothing defines it the promise is
    unimplementable, and the next reader cannot tell a live separator from a
    fossil.

    So each carrier-bound row must declare an independent reference of its own
    (``schema_ref``, ``transcript_schema_refs``, ``defined_in`` or
    ``transcript_defined_in``). A bare ``object_family`` or ``domain`` occurrence
    in prose, a schema, a fixture, a profile or a generated view is not a
    definition and cannot anchor the row. Rows that predate this gate and have
    not been adjudicated are named one by one in
    ``tools/proof-context-anchor-exemptions.json``; that file is a ratchet, so a
    listed row that has since acquired an anchor is itself an error and must be
    removed from the list rather than left as cover for the next orphan.
    """
    data = load_json(lint, PROOF_CONTEXT_REGISTRY)
    if not isinstance(data, dict):
        lint.fail(PROOF_CONTEXT_REGISTRY, "proof context registry must be an object")
        return
    rows = data.get("domain_separations")
    if not isinstance(rows, list):
        return

    exemptions: dict[str, str] = {}
    if ANCHOR_EXEMPTIONS.is_file():
        document = load_json(lint, ANCHOR_EXEMPTIONS)
        entries = document.get("unanchored_families") if isinstance(document, dict) else None
        if not isinstance(entries, list):
            lint.fail(ANCHOR_EXEMPTIONS, "unanchored_families[] must be an array")
            entries = []
        for entry in entries:
            if not isinstance(entry, dict):
                lint.fail(ANCHOR_EXEMPTIONS, "unanchored_families[] entries must be objects")
                continue
            family = entry.get("object_family")
            reason = entry.get("reason")
            if not isinstance(family, str) or not family:
                lint.fail(ANCHOR_EXEMPTIONS, "every entry must name an object_family")
                continue
            if not isinstance(reason, str) or not reason:
                lint.fail(ANCHOR_EXEMPTIONS, f"{family} must state a reason")
                continue
            exemptions[family] = reason

    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("primitive") in OBJECT_BEARING_PRIMITIVES:
            continue
        family = row.get("object_family")
        label = family if isinstance(family, str) and family else f"domain_separations[{index}]"
        if isinstance(family, str):
            seen.add(family)
        anchored = _row_is_anchored(row)
        exempted = isinstance(family, str) and family in exemptions
        if anchored and exempted:
            lint.fail(
                ANCHOR_EXEMPTIONS,
                f"{family} is exempted but now has an anchor; remove the exemption",
            )
            continue
        if anchored or exempted:
            continue
        lint.fail(
            PROOF_CONTEXT_REGISTRY,
            f"domain_separations[{index}] object_family {label!r} is defined nowhere: the row "
            "declares no schema_ref, transcript_schema_refs, defined_in or transcript_defined_in. "
            "A bare family/domain occurrence in prose or an artifact is not a definition. Define "
            "it, withdraw it, or record it in "
            "tools/proof-context-anchor-exemptions.json with a reason",
        )

    for family in sorted(set(exemptions) - seen):
        lint.fail(
            ANCHOR_EXEMPTIONS,
            f"{family} is exempted but is no longer a carrier-bound domain separation; "
            "remove the exemption",
        )


def check_domain_separation_binding_fields_are_carriable(lint: Lint) -> None:
    """No proof context may bind a field the Event wire forbids.

    ``ak.events.checkpoint.leaf.v1`` hashed ``producer_revision`` into its Merkle
    leaf while ``zh/models/event-and-patch.md`` and
    ``zh/sync/authority-commit-log.md`` both place that field in the closed
    forbidden set for ``producer_event_envelope_root``. A binding field that can
    never appear leaves an implementer two bad choices: derive no digest at all,
    or silently skip the missing member, which discards the very separation the
    row exists to provide. Either way the registry states a commitment nobody can
    reproduce.

    This rule is independent of whether any particular family survives: binding a
    forbidden field is wrong whether the family is withdrawn or fleshed out.
    """
    forbidden = load_json(lint, FORBIDDEN_WIRE_FIELDS)
    entries = forbidden.get("entries") if isinstance(forbidden, dict) else None
    if not isinstance(entries, list) or not entries:
        lint.fail(FORBIDDEN_WIRE_FIELDS, "entries[] must be a non-empty array")
        return
    names: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("context") != FORBIDDEN_EVENT_CONTEXT:
            continue
        match = entry.get("match")
        if not isinstance(match, dict) or match.get("kind") != "field":
            continue
        names.update(value for value in (match.get("values") or []) if isinstance(value, str))
    if not names:
        lint.fail(
            FORBIDDEN_WIRE_FIELDS,
            f"no field entries registered for context {FORBIDDEN_EVENT_CONTEXT}; "
            "the proof-context binding gate would silently pass",
        )
        return

    data = load_json(lint, PROOF_CONTEXT_REGISTRY)
    if not isinstance(data, dict):
        lint.fail(PROOF_CONTEXT_REGISTRY, "proof context registry must be an object")
        return
    for array_name in ("contexts", "domain_separations"):
        rows = data.get(array_name)
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            fields = row.get("binding_fields")
            if not isinstance(fields, list):
                continue
            offending = sorted(
                {item.removesuffix("?") for item in fields if isinstance(item, str)} & names
            )
            if offending:
                lint.fail(
                    PROOF_CONTEXT_REGISTRY,
                    f"{array_name}[{index}] binds {', '.join(offending)}, which the Event wire "
                    f"forbids in the {FORBIDDEN_EVENT_CONTEXT} context; a binding field that can "
                    "never appear makes the separation unimplementable",
                )


def check_local_signature_binding_fields_match_schema(lint: Lint) -> None:
    """Close raw local signatures without treating an outer proof carrier as its transcript."""

    registry = load_json(lint, PROOF_CONTEXT_REGISTRY)
    if not isinstance(registry, dict):
        return
    algorithm_path = ARTIFACTS / "registry" / "signature-alg-registry.json"
    algorithm_registry = load_json(lint, algorithm_path)
    algorithms = algorithm_registry.get("algorithms") if isinstance(algorithm_registry, dict) else None
    if not isinstance(algorithms, list):
        lint.fail(algorithm_path, "algorithms[] must be an array")
        return
    active_raw_algorithms = {
        row.get("raw_signature_algorithm")
        for row in algorithms
        if isinstance(row, dict)
        and row.get("status") == "active"
        and "raw_detached_signature" in (row.get("proof_kinds") or [])
        and isinstance(row.get("raw_signature_algorithm"), str)
    }

    rows = registry.get("domain_separations")
    if not isinstance(rows, list):
        return
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("primitive") != "detached_signature":
            continue
        reference = row.get("schema_ref")
        if not isinstance(reference, str):
            continue
        file_ref, separator, fragment = reference.partition("#")
        schema_path = ARTIFACTS / file_ref
        document = load_json(lint, schema_path)
        if not isinstance(document, dict):
            continue
        try:
            node = resolve_json_pointer(document, "#" + fragment) if separator else document
        except (KeyError, IndexError, ValueError):
            continue
        if not isinstance(node, dict):
            continue
        properties = node.get("properties")
        required = node.get("required")
        if not isinstance(properties, dict) or not isinstance(required, list):
            continue
        # A shared proof carrier may be a closed object too, but its registry
        # fields describe the nested proof leaf. Only a raw local object that
        # directly carries both algorithm and signature selects this equality.
        if not {"signature", "signature_algorithm"}.issubset(properties):
            continue
        where = f"domain_separations[{index}]"
        domain = row.get("domain")
        if node.get("x-arkret-signature-domain") != domain:
            lint.fail(
                schema_path,
                f"{reference} must annotate x-arkret-signature-domain={domain!r}",
            )
        if node.get("additionalProperties") is not False:
            lint.fail(schema_path, f"{reference} local signature object must be closed")
        if not {"signature", "signature_algorithm"}.issubset(required):
            lint.fail(schema_path, f"{reference} must require signature and signature_algorithm")
            continue
        fields = row.get("binding_fields")
        if not isinstance(fields, list) or not all(isinstance(field, str) for field in fields):
            continue
        expected = set(required) - {"signature"}
        actual = set(fields)
        if len(fields) != len(actual) or actual != expected:
            lint.fail(
                PROOF_CONTEXT_REGISTRY,
                f"{where}.binding_fields must equal required(schema_ref) minus signature; "
                f"missing={sorted(expected - actual)!r}, extra={sorted(actual - expected)!r}",
            )
        algorithm_schema = properties.get("signature_algorithm")
        algorithm = algorithm_schema.get("const") if isinstance(algorithm_schema, dict) else None
        if algorithm not in active_raw_algorithms:
            lint.fail(
                schema_path,
                f"{reference} signature_algorithm must const-select an active raw_signature_algorithm; "
                f"got {algorithm!r}",
            )


DETACHED_SIGNATURE_CONTEXTS: dict[str, dict[str, Any]] = {
    "ak.realm_commit_signature.v1": {
        "object_family": "realm_commit_signature",
        "schema_ref": "schemas/realm-commit.schema.json",
        "signature_member": "signature",
        "excluded_signature_members": ["signature"],
        "definition": "realm_commit_signature",
        "defined_in": "zh/sync/authority-commit-log.md#3-realmcommit-与逐-stream-单链",
        "case_id": "realm_commit",
        "test_key_ref": "conformance_ed25519_fixture_key",
        "signer_authority": "governance_generation exact governance Station service signing key authorized by the verified authority chain; verification_method belongs to that exact service identity",
    },
    "ak.realm_authority_handoff_old_signature.v1": {
        "object_family": "realm_authority_handoff_old_signature",
        "schema_ref": "schemas/realm-authority-handoff.schema.json",
        "signature_member": "old_authority_signature",
        "excluded_signature_members": [
            "old_authority_signature",
            "new_authority_acceptance_signature",
        ],
        "definition": "realm_authority_handoff_old_signature",
        "defined_in": "zh/sync/authority-commit-log.md#8-治理-station-更换",
        "case_id": "realm_authority_handoff_old",
        "test_key_ref": "conformance_ed25519_fixture_key",
        "signer_authority": "from_generation and from_service_id exact old governance Station service signing key that remains current at the frozen handoff cut",
    },
    "ak.realm_authority_handoff_new_acceptance_signature.v1": {
        "object_family": "realm_authority_handoff_new_acceptance_signature",
        "schema_ref": "schemas/realm-authority-handoff.schema.json",
        "signature_member": "new_authority_acceptance_signature",
        "excluded_signature_members": [
            "old_authority_signature",
            "new_authority_acceptance_signature",
        ],
        "definition": "realm_authority_handoff_new_acceptance_signature",
        "defined_in": "zh/sync/authority-commit-log.md#8-治理-station-更换",
        "case_id": "realm_authority_handoff_new_acceptance",
        "test_key_ref": "rfc8032_test_1_ed25519_key",
        "signer_authority": "to_generation and to_service_id exact new governance Station service signing key after complete validation and import of the frozen handoff",
    },
    "ak.realm_authority_current_assertion_signature.v1": {
        "object_family": "realm_authority_current_assertion_signature",
        "schema_ref": "schemas/realm-authority-bundle.schema.json#/$defs/current_assertion",
        "signature_member": "signature",
        "excluded_signature_members": ["signature"],
        "definition": "realm_authority_current_assertion_signature",
        "defined_in": "zh/sync/service-surface.md#26-service-did-权威入口与路由解析normative",
        "case_id": "realm_authority_current_assertion",
        "test_key_ref": "rfc8032_test_1_ed25519_key",
        "signer_authority": "current_generation and current_service_id exact current governance Station service signing key derived from the verified genesis-to-handoff chain",
    },
    "ak.realm_snapshot_signature.v1": {
        "object_family": "realm_snapshot_signature",
        "schema_ref": "schemas/realm-state-snapshot.schema.json",
        "signature_member": "signature",
        "excluded_signature_members": ["signature"],
        "definition": "realm_snapshot_signature",
        "defined_in": "zh/conformance/realm-state-snapshot-schema.md#4-创建与验证",
        "case_id": "realm_snapshot",
        "test_key_ref": "rfc8032_test_1_ed25519_key",
        "signer_authority": "governance_generation exact current governance Station service signing key verified through the current authority bundle",
    },
    "ak.mls_welcome_delivery_signature.v1": {
        "object_family": "mls_welcome_delivery_signature",
        "schema_ref": "schemas/mls-welcome-delivery.schema.json",
        "signature_member": "producer_proof",
        "excluded_signature_members": ["producer_proof"],
        "definition": "mls_welcome_delivery_signature",
        "defined_in": "zh/crypto-media/encryption-and-audit.md#261-welcome-producer-proof",
        "case_id": "mls_welcome_delivery",
        "test_key_ref": "conformance_ed25519_fixture_key",
        "signer_authority": "commit_event_ref exact winning ak.mls.commit Event producer signing authority and its already verified verification_method",
    },
}
DETACHED_SIGNATURE_BINDING_FIELDS = [
    "context",
    "signature_algorithm",
    "verification_method",
    "signed_digest",
    "created_at",
]
REMOVED_REALM_SNAPSHOT_PROOF_CONTEXT = "ak.realm_state_snapshot_proof.v1"
DETACHED_SIGNATURE_ROW_KEYS = frozenset(
    {
        "domain",
        "object_family",
        "primitive",
        "schema_ref",
        "transcript_schema_refs",
        "signature_member",
        "excluded_signature_members",
        "binding_fields",
        "canonicalization",
        "digest_suite",
        "digest_input",
        "digest_encoding",
        "prefix_form",
        "prefix_bytes_hex",
        "signature_input",
        "signature_algorithm",
        "signature_encoding",
        "domain_is_a_transcript_member",
        "signer_authority",
        "defined_in",
        "known_answer_ref",
    }
)


def _detached_jcs(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _detached_schema_node(lint: Lint, schema_ref: str) -> dict[str, Any] | None:
    file_ref, separator, body = schema_ref.partition("#")
    document = load_json(lint, ARTIFACTS / file_ref)
    if not isinstance(document, dict):
        return None
    try:
        node = resolve_json_pointer(document, f"#{body}" if separator else "")
    except (KeyError, IndexError, ValueError):
        lint.fail(DETACHED_OBJECT_SIGNATURE_SCHEMA, f"host schema reference does not resolve: {schema_ref}")
        return None
    if not isinstance(node, dict):
        lint.fail(DETACHED_OBJECT_SIGNATURE_SCHEMA, f"host schema reference is not an object: {schema_ref}")
        return None
    return node


def _detached_authority_basis(case: dict[str, Any]) -> dict[str, Any] | None:
    context = case.get("context")
    host = case.get("host_object")
    public_key = case.get("public_key_b64u")
    verification_method = (
        case.get("signature_envelope_without_sig", {}).get("verification_method")
        if isinstance(case.get("signature_envelope_without_sig"), dict)
        else None
    )
    test_key_ref = case.get("test_key_ref")
    if not isinstance(host, dict):
        return None
    if context == "ak.realm_commit_signature.v1":
        return {
            "basis_kind": "governance_generation_current_station",
            "coordinate": {
                "governance_generation": host.get("governance_generation"),
                "service_id": "ak:did_core:webvh:z6mkfixturestationa",
            },
            "resolved_controller_did": "did:webvh:z6mkfixturestationa:station-a.example",
            "authorized_verification_method": verification_method,
            "public_key_b64u": public_key,
            "test_key_ref": test_key_ref,
        }
    if context == "ak.realm_authority_handoff_old_signature.v1":
        return {
            "basis_kind": "handoff_old_current_at_frozen_cut",
            "coordinate": {
                "generation": host.get("from_generation"),
                "service_id": host.get("from_service_id"),
            },
            "resolved_controller_did": "did:webvh:z6mkfixturestationa:station-a.example",
            "authorized_verification_method": verification_method,
            "public_key_b64u": public_key,
            "test_key_ref": test_key_ref,
        }
    if context == "ak.realm_authority_handoff_new_acceptance_signature.v1":
        return {
            "basis_kind": "handoff_new_after_verified_import",
            "coordinate": {
                "generation": host.get("to_generation"),
                "service_id": host.get("to_service_id"),
            },
            "resolved_controller_did": "did:webvh:z6mkfixturestationb:station-b.example",
            "authorized_verification_method": verification_method,
            "public_key_b64u": public_key,
            "test_key_ref": test_key_ref,
        }
    if context == "ak.realm_authority_current_assertion_signature.v1":
        return {
            "basis_kind": "verified_chain_current_station",
            "coordinate": {
                "current_generation": host.get("current_generation"),
                "current_service_id": host.get("current_service_id"),
            },
            "resolved_controller_did": "did:webvh:z6mkfixturestationb:station-b.example",
            "authorized_verification_method": verification_method,
            "public_key_b64u": public_key,
            "test_key_ref": test_key_ref,
        }
    if context == "ak.realm_snapshot_signature.v1":
        return {
            "basis_kind": "current_bundle_generation_station",
            "coordinate": {
                "governance_generation": host.get("governance_generation"),
                "service_id": "ak:did_core:webvh:z6mkfixturestationb",
            },
            "resolved_controller_did": "did:webvh:z6mkfixturestationb:station-b.example",
            "authorized_verification_method": verification_method,
            "public_key_b64u": public_key,
            "test_key_ref": test_key_ref,
        }
    if context == "ak.mls_welcome_delivery_signature.v1":
        return {
            "basis_kind": "winning_commit_event_exact_producer",
            "coordinate": {
                "commit_event_ref": host.get("commit_event_ref"),
                "producer_actor_id": {
                    "kind": "service",
                    "service_id": "ak:did_core:webvh:z6mkfixturealice",
                },
            },
            "resolved_controller_did": "did:webvh:z6mkfixturealice:alice.example",
            "authorized_verification_method": verification_method,
            "public_key_b64u": public_key,
            "test_key_ref": test_key_ref,
        }
    return None


def _decode_detached_b64u(value: Any) -> bytes | None:
    if not isinstance(value, str) or len(value) != 86 or "=" in value:
        return None
    if re.fullmatch(r"[A-Za-z0-9_-]{86}", value) is None:
        return None
    try:
        raw = base64.urlsafe_b64decode(value + "==")
    except (ValueError, TypeError):
        return None
    if len(raw) != 64 or base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != value:
        return None
    return raw


def check_detached_object_signature_registration(lint: Lint) -> None:
    """Close and execute all six raw detached-object signature transcripts."""

    signature_schema = load_json(lint, DETACHED_OBJECT_SIGNATURE_SCHEMA)
    registry = load_json(lint, PROOF_CONTEXT_REGISTRY)
    fixture = load_json(lint, DETACHED_OBJECT_SIGNATURE_FIXTURE)
    vector_registry = load_json(lint, VECTOR_REGISTRY)
    if not all(isinstance(value, dict) for value in (signature_schema, registry, fixture, vector_registry)):
        return

    contexts = registry.get("contexts")
    if any(
        isinstance(row, dict)
        and row.get("context") == REMOVED_REALM_SNAPSHOT_PROOF_CONTEXT
        for row in contexts or []
    ):
        lint.fail(
            PROOF_CONTEXT_REGISTRY,
            f"removed snapshot proof context must not return: {REMOVED_REALM_SNAPSHOT_PROOF_CONTEXT}",
        )

    expected_contexts = list(DETACHED_SIGNATURE_CONTEXTS)
    properties = signature_schema.get("properties")
    defs = signature_schema.get("$defs")
    enum = properties.get("context", {}).get("enum") if isinstance(properties, dict) else None
    if enum != expected_contexts:
        lint.fail(DETACHED_OBJECT_SIGNATURE_SCHEMA, "context enum must contain exactly the six registered detached-object contexts in canonical order")
    if not isinstance(defs, dict) or set(defs) != {
        config["definition"] for config in DETACHED_SIGNATURE_CONTEXTS.values()
    }:
        lint.fail(DETACHED_OBJECT_SIGNATURE_SCHEMA, "$defs must contain exactly one branch for each of the six contexts")
    else:
        for context, config in DETACHED_SIGNATURE_CONTEXTS.items():
            branch = defs.get(config["definition"])
            try:
                branch_context = branch["allOf"][1]["properties"]["context"]["const"]
            except (KeyError, IndexError, TypeError):
                branch_context = None
            if branch_context != context:
                lint.fail(DETACHED_OBJECT_SIGNATURE_SCHEMA, f"$defs.{config['definition']} must const-bind {context}")
    digest_schema = properties.get("signed_digest") if isinstance(properties, dict) else None
    if digest_schema != {
        "type": "string",
        "pattern": "^sha256:[0-9a-f]{64}$",
        "description": "SHA-256 of the RFC8785 JCS bytes of the complete registered unsigned host projection. A verifier MUST recompute this value from the host object before signature verification.",
    }:
        lint.fail(DETACHED_OBJECT_SIGNATURE_SCHEMA, "signed_digest must be the closed sha256:lowercase_hex carrier")

    rows = registry.get("domain_separations")
    detached_rows = {
        row.get("domain"): row
        for row in rows or []
        if isinstance(row, dict) and row.get("domain") in DETACHED_SIGNATURE_CONTEXTS
    }
    if set(detached_rows) != set(DETACHED_SIGNATURE_CONTEXTS):
        lint.fail(PROOF_CONTEXT_REGISTRY, "domain_separations must contain exactly the six detached-object signature rows")

    cases = fixture.get("cases")
    if not isinstance(cases, list) or len(cases) != 6:
        lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, "cases must contain exactly six detached-object KATs")
        return
    case_by_context = {
        case.get("context"): case for case in cases if isinstance(case, dict)
    }
    if set(case_by_context) != set(DETACHED_SIGNATURE_CONTEXTS):
        lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, "fixture contexts must map one-to-one to the six registered domains")

    vector_rows = vector_registry.get("vectors")
    vector = next(
        (
            row
            for row in vector_rows or []
            if isinstance(row, dict)
            and row.get("vector_id") == "ak.vector.detached_object_signature_transcripts.v1"
        ),
        None,
    )
    if not isinstance(vector, dict) or vector.get("status") != "active" or vector.get("applies_to_fixtures") != [DETACHED_OBJECT_SIGNATURE_FIXTURE.name]:
        lint.fail(VECTOR_REGISTRY, "detached-object transcript vector must be active and execute the dedicated fixture")

    for index, context in enumerate(expected_contexts):
        config = DETACHED_SIGNATURE_CONTEXTS[context]
        row = detached_rows.get(context)
        case = case_by_context.get(context)
        where = f"domain_separations[{context}]"
        if not isinstance(row, dict) or not isinstance(case, dict):
            continue
        if set(row) != DETACHED_SIGNATURE_ROW_KEYS:
            lint.fail(PROOF_CONTEXT_REGISTRY, f"{where} must have the closed detached-signature row shape")
        exact_row = {
            "domain": context,
            "object_family": config["object_family"],
            "primitive": "detached_signature",
            "schema_ref": config["schema_ref"],
            "transcript_schema_refs": [
                f"schemas/detached-object-signature.schema.json#/$defs/{config['definition']}"
            ],
            "signature_member": config["signature_member"],
            "excluded_signature_members": config["excluded_signature_members"],
            "binding_fields": DETACHED_SIGNATURE_BINDING_FIELDS,
            "canonicalization": "RFC8785_JCS",
            "digest_suite": "SHA-256",
            "digest_input": "RFC8785_JCS(unsigned_projection)",
            "digest_encoding": "sha256:lowercase_hex",
            "prefix_form": "UTF8(domain + LF)",
            "prefix_bytes_hex": (context + "\n").encode("utf-8").hex(),
            "signature_input": "prefix_bytes || RFC8785_JCS(signature_envelope_without_sig)",
            "signature_algorithm": "Ed25519",
            "signature_encoding": "base64url_no_pad_64_bytes",
            "domain_is_a_transcript_member": True,
            "signer_authority": config["signer_authority"],
            "defined_in": config["defined_in"],
            "known_answer_ref": f"fixtures/{DETACHED_OBJECT_SIGNATURE_FIXTURE.name}#/cases/{index}",
        }
        for key, value in exact_row.items():
            if row.get(key) != value:
                lint.fail(PROOF_CONTEXT_REGISTRY, f"{where}.{key} does not match the closed construction")

        host_schema = _detached_schema_node(lint, config["schema_ref"])
        host_properties = host_schema.get("properties") if isinstance(host_schema, dict) else None
        member_schema = host_properties.get(config["signature_member"]) if isinstance(host_properties, dict) else None
        expected_ref = f"./detached-object-signature.schema.json#/$defs/{config['definition']}"
        if not isinstance(member_schema, dict) or member_schema.get("$ref") != expected_ref:
            lint.fail(DETACHED_OBJECT_SIGNATURE_SCHEMA, f"{config['schema_ref']} must directly reference {expected_ref} at {config['signature_member']}")

        if case.get("case_id") != config["case_id"] or case.get("schema_ref") != config["schema_ref"]:
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} has the wrong case_id or schema_ref")
        if case.get("signature_member") != config["signature_member"] or case.get("excluded_signature_members") != config["excluded_signature_members"]:
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} has the wrong signature member exclusions")
        if case.get("expected_result") != "accept" or case.get("test_key_ref") != config["test_key_ref"]:
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} has the wrong result or test key authority")

        host = case.get("host_object")
        if not isinstance(host, dict):
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} host_object must be an object")
            continue
        for error in jsonschema_errors(lint, DETACHED_OBJECT_SIGNATURE_FIXTURE, config["schema_ref"], host):
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} host schema validation failed: {error}")
        excluded = config["excluded_signature_members"]
        if not all(member in host for member in excluded):
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} host must contain every excluded signature member")
            continue
        projection = {key: copy.deepcopy(value) for key, value in host.items() if key not in excluded}
        unsigned_bytes = _detached_jcs(projection)
        digest = "sha256:" + hashlib.sha256(unsigned_bytes).hexdigest()
        if case.get("unsigned_projection") != projection:
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} unsigned_projection must be rebuilt from the complete host object")
        if case.get("unsigned_jcs_utf8_hex") != unsigned_bytes.hex():
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} unsigned_jcs_utf8_hex does not match recomputed RFC8785 JCS bytes")
        if case.get("expected_signed_digest") != digest:
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} expected_signed_digest does not match recomputed host digest")

        carrier = host.get(config["signature_member"])
        if not isinstance(carrier, dict):
            continue
        envelope = {key: copy.deepcopy(value) for key, value in carrier.items() if key != "sig"}
        if set(envelope) != set(DETACHED_SIGNATURE_BINDING_FIELDS):
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} signature envelope must contain exactly the five bound members")
        if envelope.get("context") != context or envelope.get("signed_digest") != digest:
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} carrier context or signed_digest differs from recomputation")
        if envelope.get("signature_algorithm") != "Ed25519":
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} signature_algorithm must be Ed25519")
        if case.get("signature_envelope_without_sig") != envelope:
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} envelope expected field differs from the host carrier")
        prefix = (context + "\n").encode("utf-8")
        signature_input = prefix + _detached_jcs(envelope)
        if case.get("prefix_bytes_hex") != prefix.hex():
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} prefix_bytes_hex must be recomputed from context plus one LF")
        if case.get("signature_input_hex") != signature_input.hex():
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} signature_input_hex differs from the reconstructed transcript")
        if case.get("expected_sig") != carrier.get("sig"):
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} expected_sig differs from the host carrier")

        public_text = case.get("public_key_b64u")
        signature = _decode_detached_b64u(carrier.get("sig"))
        try:
            public_raw = base64.urlsafe_b64decode(str(public_text) + "==")
            canonical_public = base64.urlsafe_b64encode(public_raw).rstrip(b"=").decode("ascii")
        except (ValueError, TypeError):
            public_raw = b""
            canonical_public = ""
        if len(public_raw) != 32 or public_text != canonical_public:
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} public key must be canonical base64url of 32 bytes")
        elif signature is None:
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} sig must be canonical unpadded base64url of exactly 64 bytes")
        else:
            try:
                Ed25519PublicKey.from_public_bytes(public_raw).verify(signature, signature_input)
            except (InvalidSignature, ValueError):
                lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} Ed25519 signature does not verify over reconstructed input")

        expected_basis = _detached_authority_basis(case)
        if case.get("authority_basis") != expected_basis:
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, f"case {context} authority_basis does not bind the host coordinate, exact method, key and authority class")

    old_case = case_by_context.get("ak.realm_authority_handoff_old_signature.v1")
    new_case = case_by_context.get("ak.realm_authority_handoff_new_acceptance_signature.v1")
    if isinstance(old_case, dict) and isinstance(new_case, dict):
        if old_case.get("unsigned_projection") != new_case.get("unsigned_projection") or old_case.get("expected_signed_digest") != new_case.get("expected_signed_digest"):
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, "handoff old and new cases must share the identical unsigned projection and digest")
        if old_case.get("public_key_b64u") == new_case.get("public_key_b64u") or old_case.get("test_key_ref") == new_case.get("test_key_ref"):
            lint.fail(DETACHED_OBJECT_SIGNATURE_FIXTURE, "handoff old and new cases must use two distinct registered test keys")


_DIGEST_CONSTRUCTION_KEYS = frozenset(
    {
        "construction_id",
        "applies_to_primitives",
        "canonicalization",
        "digest_suite",
        "prefix_form",
        "digest_input",
        "digest_encoding",
        "domain_is_a_transcript_member",
        "defined_in",
        "defining_literal",
    }
)
_CANONICAL_DIGEST_ROW_KEYS = frozenset(
    {
        "domain",
        "object_family",
        "primitive",
        "binding_fields",
        "digest_construction",
        "prefix_bytes_hex",
        "transcript_defined_in",
        "known_answer_ref",
        "kat_absence_reason",
        "owner_report",
    }
)
_BYTE_EXACT_DIGEST_KAT_KEYS = frozenset(
    {
        "name",
        "domain",
        "prefix_bytes_hex",
        "transcript",
        "canonical_transcript_utf8",
        "digest_input_hex",
        "expected_digest",
    }
)
_SHA256_LOWERCASE_HEX_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _digest_reference(lint: Lint, reference: object, *, prose: bool) -> Any:
    """Resolve one registry-owned reference without treating its text as authority."""
    if not isinstance(reference, str) or not reference:
        return None
    file_ref, separator, fragment_body = reference.partition("#")
    root = SPEC_ROOT if prose else ARTIFACTS
    path = root / file_ref
    if not path.is_file():
        lint.fail(PROOF_CONTEXT_REGISTRY, f"digest reference does not resolve: {reference}")
        return None
    if prose:
        return read_text(path)
    document = load_json(lint, path)
    if document is None:
        return None
    fragment = f"#{fragment_body}" if separator else ""
    try:
        return resolve_json_pointer(document, fragment)
    except (KeyError, IndexError, ValueError):
        lint.fail(PROOF_CONTEXT_REGISTRY, f"digest reference fragment does not resolve: {reference}")
        return None


def _digest_kat_pairs(node: Any) -> list[tuple[dict[str, Any], str]]:
    """Return the two explicitly registered exact-pointer KAT shapes."""
    if isinstance(node, dict) and isinstance(node.get("transcript"), dict) and isinstance(
        node.get("expected_digest"), str
    ):
        return [(node["transcript"], node["expected_digest"])]
    if isinstance(node, dict) and isinstance(node.get("core"), dict) and isinstance(
        node.get("receipt_digest"), str
    ):
        return [(node["core"], node["receipt_digest"])]
    return []


def _check_digest_kat_binding_fields(
    lint: Lint,
    where: str,
    row: dict[str, Any],
    transcript: dict[str, Any],
) -> None:
    fields = row.get("binding_fields")
    if not isinstance(fields, list) or not all(isinstance(field, str) and field for field in fields):
        return
    required = {field for field in fields if not field.endswith("?")}
    allowed = {field.removesuffix("?") for field in fields}
    actual = set(transcript)
    if not required <= actual or not actual <= allowed:
        lint.fail(
            PROOF_CONTEXT_REGISTRY,
            f"{where}.known_answer_ref transcript does not cover binding_fields exactly; "
            f"missing={sorted(required - actual)}, unknown={sorted(actual - allowed)}",
        )


def _check_byte_exact_digest_kat(
    lint: Lint,
    where: str,
    row: dict[str, Any],
    target: dict[str, Any],
    expected_prefix: str,
) -> None:
    if set(target) != _BYTE_EXACT_DIGEST_KAT_KEYS:
        lint.fail(
            PROOF_CONTEXT_REGISTRY,
            f"{where}.known_answer_ref byte KAT must have exactly the closed KAT keys",
        )
    domain = row.get("domain")
    if target.get("domain") != domain:
        lint.fail(PROOF_CONTEXT_REGISTRY, f"{where}.known_answer_ref KAT domain must equal row domain")
    if target.get("prefix_bytes_hex") != expected_prefix:
        lint.fail(
            PROOF_CONTEXT_REGISTRY,
            f"{where}.known_answer_ref KAT prefix must equal UTF8(domain + LF)",
        )
    transcript = target.get("transcript")
    if not isinstance(transcript, dict):
        return
    canonical = json.dumps(
        transcript, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    try:
        canonical_text = canonical.decode("utf-8")
        digest_input_hex = (bytes.fromhex(expected_prefix) + canonical).hex()
    except ValueError:
        return
    if target.get("canonical_transcript_utf8") != canonical_text:
        lint.fail(
            PROOF_CONTEXT_REGISTRY,
            f"{where}.known_answer_ref canonical_transcript_utf8 is not RFC8785_JCS(transcript)",
        )
    if target.get("digest_input_hex") != digest_input_hex:
        lint.fail(
            PROOF_CONTEXT_REGISTRY,
            f"{where}.known_answer_ref digest_input_hex must include the exact domain LF prefix",
        )

    if row.get("digest_construction") == "domain_prefixed_jcs_sha256_over_normalized_string_set":
        scopes = transcript.get("scopes")
        normalized = (
            sorted(scopes, key=lambda value: value.encode("utf-8"))
            if isinstance(scopes, list) and all(isinstance(value, str) for value in scopes)
            else None
        )
        if not isinstance(scopes, list) or not scopes or scopes != normalized or len(scopes) != len(set(scopes)):
            lint.fail(
                PROOF_CONTEXT_REGISTRY,
                f"{where}.known_answer_ref scopes must be a non-empty UTF-8 bytewise sorted unique array",
            )


def check_digest_construction_registration(lint: Lint) -> None:
    """Close the construction contract for every canonical-JSON digest domain.

    The construction table is deliberately closed.  The short defining literal
    is checked in its normative source instead of comparing an entire prose
    line, so harmless wrapping and punctuation changes do not become protocol
    changes.  Prefix bytes are always recomputed from ``domain`` plus one LF;
    the registry's hex is never trusted as an independent source.
    """
    data = load_json(lint, PROOF_CONTEXT_REGISTRY)
    if not isinstance(data, dict):
        lint.fail(PROOF_CONTEXT_REGISTRY, "proof context registry must be an object")
        return

    construction_rows = data.get("digest_constructions")
    if not isinstance(construction_rows, list) or not construction_rows:
        lint.fail(PROOF_CONTEXT_REGISTRY, "digest_constructions[] must be a non-empty array")
        return

    constructions: dict[str, dict[str, Any]] = {}
    for index, construction in enumerate(construction_rows):
        where = f"digest_constructions[{index}]"
        if not isinstance(construction, dict):
            lint.fail(PROOF_CONTEXT_REGISTRY, f"{where} must be an object")
            continue
        unknown = set(construction) - _DIGEST_CONSTRUCTION_KEYS
        missing = _DIGEST_CONSTRUCTION_KEYS - set(construction)
        if unknown or missing:
            lint.fail(
                PROOF_CONTEXT_REGISTRY,
                f"{where} must have exactly the closed construction keys; "
                f"missing={sorted(missing)}, unknown={sorted(unknown)}",
            )
        construction_id = construction.get("construction_id")
        if not isinstance(construction_id, str) or not construction_id:
            lint.fail(PROOF_CONTEXT_REGISTRY, f"{where}.construction_id must be a non-empty string")
            continue
        if construction_id in constructions:
            lint.fail(PROOF_CONTEXT_REGISTRY, f"duplicate digest construction {construction_id!r}")
        constructions[construction_id] = construction
        primitives = construction.get("applies_to_primitives")
        if (
            not isinstance(primitives, list)
            or not primitives
            or not all(isinstance(item, str) and item for item in primitives)
            or len(primitives) != len(set(primitives))
        ):
            lint.fail(
                PROOF_CONTEXT_REGISTRY,
                f"{where}.applies_to_primitives must be a non-empty unique string array",
            )
        for member in (
            "canonicalization",
            "digest_suite",
            "prefix_form",
            "digest_input",
            "digest_encoding",
            "defined_in",
            "defining_literal",
        ):
            if not isinstance(construction.get(member), str) or not construction[member].strip():
                lint.fail(PROOF_CONTEXT_REGISTRY, f"{where}.{member} must be a non-empty string")
        if construction.get("domain_is_a_transcript_member") is not False:
            lint.fail(PROOF_CONTEXT_REGISTRY, f"{where}.domain_is_a_transcript_member must be false")
        source = _digest_reference(lint, construction.get("defined_in"), prose=True)
        literal = construction.get("defining_literal")
        if isinstance(source, str) and isinstance(literal, str) and literal not in source:
            lint.fail(
                PROOF_CONTEXT_REGISTRY,
                f"{where}.defining_literal does not occur in {construction.get('defined_in')}",
            )

    separation_rows = data.get("domain_separations")
    if not isinstance(separation_rows, list):
        lint.fail(PROOF_CONTEXT_REGISTRY, "domain_separations[] must be an array")
        return
    selected: set[str] = set()
    for index, row in enumerate(separation_rows):
        if not isinstance(row, dict) or row.get("primitive") != "canonical_json_sha256":
            continue
        where = f"domain_separations[{index}]"
        unknown = set(row) - _CANONICAL_DIGEST_ROW_KEYS
        required = _CANONICAL_DIGEST_ROW_KEYS - {"kat_absence_reason", "owner_report"}
        missing = required - set(row)
        if unknown or missing:
            lint.fail(
                PROOF_CONTEXT_REGISTRY,
                f"{where} canonical_json_sha256 row has an open or incomplete shape; "
                f"missing={sorted(missing)}, unknown={sorted(unknown)}",
            )
        construction_id = row.get("digest_construction")
        construction = constructions.get(construction_id) if isinstance(construction_id, str) else None
        if construction is None:
            lint.fail(PROOF_CONTEXT_REGISTRY, f"{where}.digest_construction is not registered")
        else:
            selected.add(construction_id)
            primitives = construction.get("applies_to_primitives")
            if not isinstance(primitives, list) or row.get("primitive") not in primitives:
                lint.fail(
                    PROOF_CONTEXT_REGISTRY,
                    f"{where} selects a construction that does not apply to canonical_json_sha256",
                )

        domain = row.get("domain")
        expected_prefix = (domain + "\n").encode("utf-8").hex() if isinstance(domain, str) else None
        if row.get("prefix_bytes_hex") != expected_prefix:
            lint.fail(
                PROOF_CONTEXT_REGISTRY,
                f"{where}.prefix_bytes_hex must equal UTF8(domain + LF), recomputed from domain",
            )
        transcript_source = _digest_reference(lint, row.get("transcript_defined_in"), prose=True)
        if isinstance(transcript_source, str) and isinstance(domain, str) and domain not in transcript_source:
            lint.fail(
                PROOF_CONTEXT_REGISTRY,
                f"{where}.transcript_defined_in does not contain its domain literal",
            )

        known_answer_ref = row.get("known_answer_ref")
        absence = row.get("kat_absence_reason")
        owner = row.get("owner_report")
        if isinstance(known_answer_ref, str) and known_answer_ref:
            if absence is not None or owner is not None:
                lint.fail(PROOF_CONTEXT_REGISTRY, f"{where} with a KAT must not declare an absence owner")
            target = _digest_reference(lint, known_answer_ref, prose=False)
            pairs = _digest_kat_pairs(target)
            if not pairs:
                lint.fail(PROOF_CONTEXT_REGISTRY, f"{where}.known_answer_ref resolves no registered KAT pair")
            if isinstance(target, dict) and "domain" in target:
                _check_byte_exact_digest_kat(lint, where, row, target, expected_prefix or "")
            for transcript, expected_digest in pairs:
                _check_digest_kat_binding_fields(lint, where, row, transcript)
                canonical = json.dumps(
                    transcript, ensure_ascii=False, separators=(",", ":"), sort_keys=True
                ).encode("utf-8")
                digest = "sha256:" + hashlib.sha256(bytes.fromhex(expected_prefix or "") + canonical).hexdigest()
                if _SHA256_LOWERCASE_HEX_RE.fullmatch(expected_digest) is None:
                    lint.fail(
                        PROOF_CONTEXT_REGISTRY,
                        f"{where}.known_answer_ref digest must use sha256:lowercase_hex",
                    )
                if digest != expected_digest:
                    lint.fail(
                        PROOF_CONTEXT_REGISTRY,
                        f"{where}.known_answer_ref digest does not match its registered construction",
                    )
                    break
        elif known_answer_ref is None:
            if not isinstance(absence, str) or not absence.strip():
                lint.fail(PROOF_CONTEXT_REGISTRY, f"{where} without a KAT requires kat_absence_reason")
            if (
                not isinstance(owner, str)
                or not owner.startswith("arkret-work/tasks/spec-open/")
                or not owner.endswith(".md")
            ):
                lint.fail(PROOF_CONTEXT_REGISTRY, f"{where} without a KAT requires a spec-open owner_report")
        else:
            lint.fail(PROOF_CONTEXT_REGISTRY, f"{where}.known_answer_ref must be a string or null")

    canonical_json_constructions = {
        construction_id
        for construction_id, construction in constructions.items()
        if "canonical_json_sha256" in (construction.get("applies_to_primitives") or [])
    }
    for construction_id in sorted(canonical_json_constructions - selected):
        lint.fail(PROOF_CONTEXT_REGISTRY, f"digest construction {construction_id!r} is unused")


# `set` / `merge` / `transition` cover a register-shaped family. `agent_key` is
# not register-shaped: zh/identity/key-management.md section 3.6.1 fixes its
# registered reducer projection as a tagged set whose element tag is the
# canonical `<event_id>:<write_index>` Event dot of event-and-patch.md section
# 2.4.2, and typed-current-result.schema.json backs that with a closed
# `agent_key_authorization_entry` of exactly `{tag_id, value}`. A register kind
# cannot express it, and spelling it as `set` would silently collapse a
# tagged-set family into whole-value overwrite -- the shell this file exists to
# refuse. The three keyed-set kinds below carry over the shapes of the retired
# pre-v1 set vocabulary that still sits dormant in foundation.py, under the v1
# names that zh/models/pins.md and zh/models/strand-and-message.md already use,
# so nothing is invented here and the retired spelling is not resurrected.
_RESULT_PROJECTION_KINDS = frozenset(
    {
        "set",
        "merge",
        "apply_patch",
        "transition",
        "keyed_set_add",
        "keyed_set_remove_observed",
        "keyed_set_remove_dots",
    }
)
_RESULT_KEYED_SET_KINDS = frozenset({"keyed_set_add", "keyed_set_remove_observed", "keyed_set_remove_dots"})

# The exact Agent supersedes remove of foundation.py lines 1186-1193 is the only
# per-item expansion; anything else would be an open-ended loop over arbitrary
# families.
_AGENT_SUPERSEDES_FOR_EACH = {"field": "payload.supersedes", "max_items": 256}
_AGENT_SUPERSEDES_SELECTOR = {
    "kind": "composite",
    "components": ["payload.agent_id", "item.key_id"],
}
_AGENT_SUPERSEDES_PROJECTION = {
    "kind": "keyed_set_remove_dots",
    "dots": {"agent_authorization_dot": {"field": "item.authorized_event_ref"}},
}

# An `allowed_paths` entry names one top-level member of the family value, which
# is the only granularity a closed value schema can check. `encoding.md` 9.5.1
# dotted paths are deliberately not accepted: a nested path would let a patch
# reach into a member whose own shape the registry never enumerates.
PATCH_PATH_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# The two payload-comparing pre-state predicates. `stored_field_matches_payload`
# is three-valued on purpose: both absent passes, both present and equal passes,
# anything else fails.
_PRE_STATE_PAYLOAD_PREDICATES = frozenset(
    {"stored_field_equals_payload", "stored_field_matches_payload"}
)

ERROR_CODE_REGISTRY = ARTIFACTS / "registry" / "error-code-registry.json"


def _registered_error_codes(lint: Lint) -> set[str] | None:
    """Every registered error code, so a pre-state failure cannot invent one."""
    data = load_json(lint, ERROR_CODE_REGISTRY)
    codes: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            code = node.get("code")
            if isinstance(code, str):
                codes.add(code)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return codes or None

REDUCER_MANAGED_PATH_REGISTRY = ARTIFACTS / "registry" / "reducer-managed-path-registry.json"


def _row_paths(rows: Any) -> list[str]:
    """The `path` strings of one registry array, in order."""
    if not isinstance(rows, list):
        return []
    return [row["path"] for row in rows if isinstance(row, dict) and isinstance(row.get("path"), str)]


def _declared_schema_members(lint: Lint, reference: str) -> set[str] | None:
    """Top-level members a schema reference declares, following $ref and allOf."""
    members: set[str] = set()
    seen: set[str] = set()

    def visit(file_ref: str, fragment: str) -> bool:
        key = f"{file_ref}#{fragment}"
        if key in seen:
            return True
        seen.add(key)
        path = ARTIFACTS / file_ref
        document = load_json(lint, path) if path.is_file() else None
        if document is None:
            return False
        try:
            node = resolve_json_pointer(document, fragment)
        except (KeyError, IndexError, ValueError):
            return False
        return descend(node, file_ref)

    def descend(node: Any, file_ref: str) -> bool:
        if not isinstance(node, dict):
            return False
        ok = True
        properties = node.get("properties")
        if isinstance(properties, dict):
            members.update(name for name in properties if isinstance(name, str))
        reference = node.get("$ref")
        if isinstance(reference, str):
            target_file, separator, body = reference.partition("#")
            target_file = target_file.lstrip("./") or file_ref
            if not target_file.startswith("schemas/"):
                target_file = f"schemas/{target_file}"
            ok = visit(target_file, f"#{body}" if separator else "") and ok
        for branch in node.get("allOf") or []:
            ok = descend(branch, file_ref) and ok
        return ok

    file_ref, separator, body = reference.partition("#")
    if not visit(file_ref, f"#{body}" if separator else ""):
        return None
    return members


def _required_schema_members(lint: Lint, reference: str) -> set[str]:
    """Members a schema reference requires unconditionally, following $ref and allOf."""
    required: set[str] = set()
    seen: set[str] = set()

    def visit(file_ref: str, fragment: str) -> None:
        key = f"{file_ref}#{fragment}"
        if key in seen:
            return
        seen.add(key)
        path = ARTIFACTS / file_ref
        document = load_json(lint, path) if path.is_file() else None
        if document is None:
            return
        try:
            node = resolve_json_pointer(document, fragment)
        except (KeyError, IndexError, ValueError):
            return
        descend(node, file_ref)

    def descend(node: Any, file_ref: str) -> None:
        if not isinstance(node, dict):
            return
        names = node.get("required")
        if isinstance(names, list):
            required.update(name for name in names if isinstance(name, str))
        reference = node.get("$ref")
        if isinstance(reference, str):
            target_file, separator, body = reference.partition("#")
            target_file = target_file.lstrip("./") or file_ref
            if not target_file.startswith("schemas/"):
                target_file = f"schemas/{target_file}"
            visit(target_file, f"#{body}" if separator else "")
        for branch in node.get("allOf") or []:
            descend(branch, file_ref)

    file_ref, separator, body = reference.partition("#")
    visit(file_ref, f"#{body}" if separator else "")
    return required


def _forbidden_member_names(node: Any) -> set[str]:
    """Members an `allOf` branch bans through `not: {anyOf: [{required: [name]}]}`."""
    banned: set[str] = set()

    def descend(current: Any) -> None:
        if not isinstance(current, dict):
            return
        negation = current.get("not")
        if isinstance(negation, dict):
            branches = negation.get("anyOf")
            if isinstance(branches, list):
                for branch in branches:
                    if isinstance(branch, dict):
                        names = branch.get("required")
                        if isinstance(names, list) and len(names) == 1:
                            banned.update(name for name in names if isinstance(name, str))
            names = negation.get("required")
            if isinstance(names, list) and len(names) == 1:
                banned.update(name for name in names if isinstance(name, str))
        for branch in current.get("allOf") or []:
            descend(branch)

    descend(node)
    return banned


def _patch_target(lint: Lint, where: str, write: dict) -> dict | None:
    """Resolve the one registry row that owns this write's field ownership.

    `reducer-managed-path-registry.json` answers one question per object kind,
    and the effective forbidden set its own `registry_rules` define is per
    object: the universal list restricted to the members that object declares,
    MINUS that object's `universal_exemptions`, PLUS its own bans. The first
    reader of this file did none of that. It walked the whole document and
    collected every `path` key it met into one flat set, so the single v1
    exemption -- `state`, the member `views.md` section 3.1 requires
    `ak.view.update` to write because a shared View has no tombstone event kind
    -- came back as a prohibition, and the one write the spec makes normatively
    load-bearing could not be registered at all: registering it turned the gate
    red. The same flattening merged every object's private bans, so
    `resolution`, `stage`, `morph_kind`, `effective_scope`, `child_scope_policy`,
    `parent_space_id`, `scope_circle_id` and `mls_group_id` were enforced against
    every family that happened to declare a member of the same name. View did not
    collide, which is the only reason exactly one write was blocked rather than
    several.

    The target is resolved from `value_schema_ref`, cross-checked against
    `result_family`, and -- for an object row -- against the object schema the
    value is built on. Guessing from a family name or a field spelling is
    refused, and so is falling back to a flat set or an empty one.
    """
    data = load_json(lint, REDUCER_MANAGED_PATH_REGISTRY)
    if not isinstance(data, dict):
        lint.fail(REDUCER_MANAGED_PATH_REGISTRY, "registry must be an object")
        return None
    value_schema_ref = write.get("value_schema_ref")
    family = write.get("result_family")
    if not isinstance(value_schema_ref, str) or not value_schema_ref:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{where} is a partial-update write with no value_schema_ref, so nothing says which "
            "registered value's field ownership applies to it",
        )
        return None
    matches: list[tuple[str, dict]] = []
    for row in data.get("objects") or []:
        if isinstance(row, dict) and row.get("value_schema_ref") == value_schema_ref:
            matches.append(("objects", row))
    for row in data.get("non_object_results") or []:
        if isinstance(row, dict) and row.get("value_schema_ref") == value_schema_ref:
            matches.append(("non_object_results", row))
    if len(matches) != 1:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{where}.value_schema_ref {value_schema_ref!r} resolves to {len(matches)} rows of "
            "registry/reducer-managed-path-registry.json; a registered patch surface MUST name exactly "
            "one owning object kind or one non-object result",
        )
        return None
    array_name, row = matches[0]
    if row.get("result_family") != family:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{where}.result_family {family!r} disagrees with the "
            f"reducer-managed-path-registry {array_name}[] row for {value_schema_ref!r}, which owns "
            f"family {row.get('result_family')!r}",
        )
        return None
    if array_name == "objects":
        object_schema_ref = row.get("object_schema_ref")
        members = _declared_schema_members(lint, value_schema_ref)
        object_members = (
            _declared_schema_members(lint, object_schema_ref)
            if isinstance(object_schema_ref, str)
            else None
        )
        if members is None or object_members is None or not members <= object_members:
            lint.fail(
                REDUCER_MANAGED_PATH_REGISTRY,
                f"objects[] row {row.get('object_kind')!r} declares value_schema_ref "
                f"{value_schema_ref!r}, which is not built on its object_schema_ref "
                f"{object_schema_ref!r}; the Event payload, the result value schema and the object "
                "registry MUST be checked against each other, not assumed to agree",
            )
            return None
    return {"array": array_name, "row": row, "registry": data}


def _effective_forbidden_paths(lint: Lint, where: str, write: dict, kind: str) -> set[str] | None:
    """The forbidden set of THIS write's target, solved per the registry's own rules."""
    target = _patch_target(lint, where, write)
    if target is None:
        return None
    row = target["row"]
    if target["array"] == "non_object_results":
        return set(_row_paths(row.get("forbidden_patch_paths")))
    data = target["registry"]
    declared = _declared_schema_members(lint, row.get("object_schema_ref"))
    if declared is None:
        lint.fail(
            REDUCER_MANAGED_PATH_REGISTRY,
            f"objects[] row {row.get('object_kind')!r} object_schema_ref does not resolve",
        )
        return None
    universal = set(_row_paths(data.get("universal_forbidden_patch_paths")))
    forbidden = (universal & declared) | set(_row_paths(row.get("forbidden_patch_paths")))
    for exemption in row.get("universal_exemptions") or []:
        if not isinstance(exemption, dict):
            continue
        path = exemption.get("path")
        if not isinstance(path, str):
            continue
        # An exemption is a carve-out assigned to one named owner, not a
        # blanket relaxation: it subtracts the ban for the write it names and
        # for no other.
        if exemption.get("owner_kind") == "event_kind" and exemption.get("owner") != kind:
            continue
        forbidden.discard(path)
    return forbidden


def _names_a_forbidden_path(candidate: str, forbidden: set[str]) -> bool:
    """A banned path and every dotted descendant of it are banned together."""
    if candidate in forbidden:
        return True
    return any(candidate.startswith(f"{banned}.") for banned in forbidden)


def _check_projection_value_source(lint: Lint, ref: str, value: Any) -> None:
    """A projection's whole-value source MUST name exactly one registered origin.

    ``result_projection.value`` had no validator at all outside the keyed-set
    branch: ``check_result_write_contracts`` checked that ``value`` or
    ``value_projection`` was present and then read neither. The grammar that did
    validate it, ``foundation.lint_effect_source``, was written for
    ``effect_projection`` and lost its only caller when the ``cell_writes[]``
    loop went dead, so every registered whole value was passing unread. That
    grammar is gone entirely now: 65e4daf3 deleted the function with the rest of
    the dead half of ``check_registries``.

    The closure is the one already in force for ``keyed_set_add`` in this file,
    and it is wider than what the live rows use: all 30 whole values in the
    registry (27 ``set`` and 3 ``keyed_set_add``) name ``field``, and none names
    ``envelope_field``. The retired grammar also admitted ``const``,
    ``projected_value``, ``object_without_fields`` and ``dot``; no registered row
    uses any of them for a whole value, and re-admitting a spelling nothing needs
    is how removed vocabulary comes back. A row that genuinely needs one makes
    that an explicit decision here rather than passing unnoticed.
    """
    if not isinstance(value, dict):
        lint.fail(EVENT_KIND_REGISTRY, f"{ref} must be an object")
        return
    unknown = set(value) - {"field", "envelope_field", "const"}
    if unknown:
        lint.fail(EVENT_KIND_REGISTRY, f"{ref} has unknown member(s) {sorted(unknown)}")
    named = [member for member in ("field", "envelope_field", "const") if member in value]
    if len(named) != 1:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{ref} must declare exactly one of field/envelope_field/const",
        )
        return
    if "const" in value:
        # The explicit decision this function's docstring asks for. A release
        # write has no payload field to read: `governance-objects.md` section on
        # invites returns the live-target slot to the absent state, and the only
        # value that expresses "absent" is null. `transition.from` already spells
        # that same absent state `{"const": null}` in five registered rows, so
        # the release write reuses the live spelling instead of adding a second
        # one. Only the literal null is admitted -- a general whole-value const
        # would let a row carry protocol state no payload and no envelope
        # supplies, which is exactly the vocabulary this closure keeps out.
        if value["const"] is not None:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{ref}.const may only be null; a whole value that is not read from the "
                "signed Event has no other registered source",
            )
        return
    if "field" in value:
        from .foundation import lint_field_path

        lint_field_path(lint, EVENT_KIND_REGISTRY, f"{ref}.field", value["field"])
        return
    from .core import EFFECT_PROJECTION_ENVELOPE_FIELDS

    if value["envelope_field"] not in EFFECT_PROJECTION_ENVELOPE_FIELDS:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{ref}.envelope_field must be one of "
            f"{sorted(EFFECT_PROJECTION_ENVELOPE_FIELDS)}",
        )


def _check_result_apply_patch_projection(
    lint: Lint, where: str, write: dict, projection: dict, kind: str
) -> None:
    """Validate one `apply_patch` `result_projection` and its closed path set.

    `views.md` section 3.2 has always required a patch projection and the kind
    was never in the v1 closed set, so `check_partial_update_base_producers`
    named it in `_PARTIAL_UPDATE_PROJECTIONS` while no row could legally carry
    it -- a gate reading a key nothing could spell. It is admitted here with the
    one property that makes a patch decidable: the set of value paths an author
    may touch is enumerated in the registry, not inferred from the value schema.

    `allowed_paths` is that enumeration. It names top-level members of the
    family's registered value schema, so a patch can never reach a member the
    reducer owns. `patch` is the payload field carrying the author's object and
    is required exactly when `allowed_paths` is non-empty; a write with no
    author-writable path carries no patch at all (`capabilities.md` section on
    authority-root successor counters: the reset write has no `payload.patch`)
    and MUST then change the value only through `derived_members[]`.

    Two disjointness rules close the loop. A path may not be both
    author-writable and reducer-derived, and a path registered in
    `reducer-managed-path-registry.json` may never appear in `allowed_paths` --
    that registry exists precisely to say which members an ordinary patch must
    not reach.
    """
    unknown = set(projection) - {"kind", "patch", "allowed_paths"}
    if unknown:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{where}.result_projection has unknown member(s) {sorted(unknown)}",
        )
    allowed = projection.get("allowed_paths")
    if (
        not isinstance(allowed, list)
        or not all(isinstance(item, str) and PATCH_PATH_RE.fullmatch(item) for item in allowed)
        or len(allowed) != len(set(allowed))
    ):
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{where}.result_projection.allowed_paths must be a unique array of top-level "
            "value member names",
        )
        return
    patch = projection.get("patch")
    if allowed and not isinstance(patch, dict):
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{where}.result_projection.patch is required when allowed_paths is non-empty",
        )
    elif not allowed and patch is not None:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{where}.result_projection declares no allowed_paths, so it MUST NOT carry a "
            "patch field; only derived_members[] may change the value",
        )
    elif isinstance(patch, dict):
        if set(patch) != {"field"}:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{where}.result_projection.patch must be exactly {{field}}",
            )
        else:
            from .foundation import lint_field_path

            lint_field_path(
                lint, EVENT_KIND_REGISTRY, f"{where}.result_projection.patch.field", patch["field"]
            )
    derived = {
        member.get("name")
        for member in (write.get("derived_members") or [])
        if isinstance(member, dict)
    }
    if not allowed and not derived:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{where}.result_projection is an apply_patch with neither an allowed path nor a "
            "derived member, so it writes nothing",
        )
    both = sorted(set(allowed) & derived)
    if both:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{where}.result_projection.allowed_paths and derived_members[] share {both}; a "
            "member is either author-writable or reducer-derived, never both",
        )
    forbidden = _effective_forbidden_paths(lint, where, write, kind)
    if forbidden is None:
        return
    reserved = sorted(path for path in allowed if _names_a_forbidden_path(path, forbidden))
    if reserved:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{where}.result_projection.allowed_paths names reducer-managed path(s) {reserved} "
            "registered in reducer-managed-path-registry.json for this write's own target",
        )


def _authored_members(lint: Lint, where: str, payload_schema_ref: Any, field: Any) -> set[str] | None:
    """Members the closed author payload region a whole-value projection reads declares."""
    if not isinstance(payload_schema_ref, str) or not isinstance(field, str):
        return None
    segments = field.split(".")
    if segments[0] != "payload" or len(segments) < 2:
        return None
    pointer = payload_schema_ref
    for segment in segments[1:]:
        pointer = f"{pointer}/properties/{segment}" if "#" in pointer else f"{pointer}#/properties/{segment}"
    file_ref, separator, body = pointer.partition("#")
    path = ARTIFACTS / file_ref
    document = load_json(lint, path) if path.is_file() else None
    if document is None:
        return None
    try:
        node = resolve_json_pointer(document, f"#{body}" if separator else "")
    except (KeyError, IndexError, ValueError):
        return None
    members = _declared_schema_members(lint, pointer)
    if members is None:
        return None
    return members - _forbidden_member_names(node)


def _owner_author_paths(lint: Lint, where: str, write: dict, kind: Any) -> set[str]:
    """Paths this very Event kind is registered to author exclusively.

    `_effective_forbidden_paths` returns strings, so the basis and the owner of
    each row are gone by the time the whole-value check reads it. This re-reads
    the same row and keeps create-locked fields on their creator plus
    dedicated-event-owned fields on their one dedicated writer. Both remain
    forbidden to every generic patch and every other Event kind.
    """
    target = _patch_target(lint, where, write)
    if target is None:
        return set()
    return {
        entry["path"]
        for entry in target["row"].get("forbidden_patch_paths") or []
        if isinstance(entry, dict)
        and isinstance(entry.get("path"), str)
        and entry.get("basis") in {"create_locked", "dedicated_event_owned"}
        and entry.get("owner_kind") == "event_kind"
        and entry.get("owner") == kind
    }


def check_result_value_member_closure(lint: Lint) -> None:
    """Every member of a covered result value has a registered source on every write.

    A schema declaration is not a maintenance rule. `view_value` declares
    `updated_by`, `updated_at` and `state_changed_at`; all three are in
    `universal_forbidden_patch_paths`, so no author can ever supply them, and
    before this gate nothing required any write to produce them. The result was
    visible in the registry and invisible to every check: `ak.view.create` set
    the whole `payload.object` snapshot, which carried author-supplied
    `updated_by` / `updated_at` straight into the family, while the update path
    had no producer at all -- the same three members, author-written on one write
    of one family and unwritten on another. The only thing the old gate asked was
    whether a `derived_members[]` name it found was in the closed vocabulary; it
    never asked whether a member that MUST be maintained had a producer, and
    omitting `derived_members[]` entirely passed.

    So the check runs in both directions, per result family that declares
    `value_member_maintenance` in `reducer-managed-path-registry.json`:

    * every name a write declares -- author-writable, derived or retained -- MUST
      be a declared member of that family's value schema, and the three roles are
      disjoint;
    * every unconditionally required member of the value schema MUST be accounted
      for by exactly one of the three on every write into the family;
    * `always_maintained` members MUST be produced by every write, which is what
      an optional-but-reducer-owned metadata field needs and what a
      required-members-only rule cannot express;
    * a `conditional_producers` member MUST be produced by the writes it names and
      by no others;
    * a `create_locked` member MUST be produced by the writes its `producer_kinds`
      names and retained verbatim by every other write of the family, which is the
      half a "who derives it" rule cannot state: nothing stopped a later write from
      silently re-authoring an identity member it was supposed to carry.

    Optional members may legitimately be absent, so absence alone is not a
    failure. The coverage frontier is declared rather than assumed: a family
    without `value_member_maintenance` is not measured here, and its registry row
    names the owner that closes it.
    """
    data = load_json(lint, REDUCER_MANAGED_PATH_REGISTRY)
    if not isinstance(data, dict):
        lint.fail(REDUCER_MANAGED_PATH_REGISTRY, "registry must be an object")
        return
    covered: dict[str, dict[str, Any]] = {}
    for array_name in ("objects", "non_object_results"):
        for row in data.get(array_name) or []:
            if not isinstance(row, dict):
                continue
            maintenance = row.get("value_member_maintenance")
            if not isinstance(maintenance, dict):
                continue
            family = row.get("result_family")
            value_schema_ref = row.get("value_schema_ref")
            if not isinstance(family, str) or not isinstance(value_schema_ref, str):
                lint.fail(
                    REDUCER_MANAGED_PATH_REGISTRY,
                    f"{array_name}[] row declaring value_member_maintenance MUST carry "
                    "result_family and value_schema_ref",
                )
                continue
            if not isinstance(maintenance.get("owner"), str) or not maintenance["owner"]:
                lint.fail(
                    REDUCER_MANAGED_PATH_REGISTRY,
                    f"value_member_maintenance for family {family!r} MUST name the normative owner",
                )
            covered[family] = {"row": row, "maintenance": maintenance, "value": value_schema_ref}
    if not covered:
        lint.fail(
            REDUCER_MANAGED_PATH_REGISTRY,
            "no result family declares value_member_maintenance; the member-source closure would "
            "then be vacuous",
        )
        return

    registry = load_json(lint, EVENT_KIND_REGISTRY)
    rows = registry.get("event_kinds") if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        return

    seen_writes: dict[str, list[str]] = {family: [] for family in covered}
    produced: dict[str, dict[str, set[str]]] = {family: {} for family in covered}
    carried: dict[str, dict[str, set[str]]] = {family: {} for family in covered}

    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = row.get("event_kind")
        for index, write in enumerate(row.get("result_writes") or []):
            if not isinstance(write, dict):
                continue
            family = write.get("result_family")
            entry = covered.get(family) if isinstance(family, str) else None
            if entry is None:
                continue
            where = f"{kind}.result_writes[{index}]"
            seen_writes[family].append(where)
            value_schema_ref = write.get("value_schema_ref")
            if value_schema_ref != entry["value"]:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.value_schema_ref {value_schema_ref!r} is not the registered value schema "
                    f"{entry['value']!r} of covered family {family!r}",
                )
                continue
            declared = _declared_schema_members(lint, value_schema_ref)
            if declared is None:
                lint.fail(EVENT_KIND_REGISTRY, f"{where}.value_schema_ref does not resolve")
                continue
            required = _required_schema_members(lint, value_schema_ref)
            projection = write.get("result_projection")
            projection = projection if isinstance(projection, dict) else {}
            projection_kind = projection.get("kind")
            projected: set[str] = set()
            if projection_kind == "apply_patch":
                authored = {
                    item for item in projection.get("allowed_paths") or [] if isinstance(item, str)
                }
            elif projection_kind in {"set", "merge"}:
                value = projection.get("value")
                if isinstance(value, dict) and "field" in value:
                    authored = _authored_members(
                        lint, where, row.get("payload_schema_ref"), value.get("field")
                    )
                    if authored is None:
                        lint.fail(
                            EVENT_KIND_REGISTRY,
                            f"{where}.result_projection.value.field does not resolve to a closed author "
                            "payload region, so its authored members cannot be checked against "
                            f"{value_schema_ref!r}",
                        )
                        continue
                else:
                    # A value_projection names its members outright.
                    value_projection = projection.get("value_projection")
                    members = (
                        value_projection.get("members")
                        if isinstance(value_projection, dict)
                        else None
                    )
                    if not isinstance(members, list):
                        lint.fail(
                            EVENT_KIND_REGISTRY,
                            f"{where} writes a covered family but names neither a payload field nor "
                            "value_projection members, so no member source can be resolved",
                        )
                        continue
                    # A value_projection member is author input only when it
                    # reads a payload field. `literal` and `envelope_field`
                    # members are produced by the projection itself from the
                    # signed envelope or from a fixed constant, so they account
                    # for the member without handing it to the author -- the
                    # genesis authority root is exactly that shape.
                    authored = {
                        item["name"]
                        for item in members
                        if isinstance(item, dict)
                        and isinstance(item.get("name"), str)
                        and "field" in item
                    }
                    projected = {
                        item["name"]
                        for item in members
                        if isinstance(item, dict)
                        and isinstance(item.get("name"), str)
                        and "field" not in item
                    }
            else:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.result_projection.kind {projection_kind!r} has no registered member-source "
                    f"reading for covered family {family!r}",
                )
                continue
            derived = {
                item.get("name")
                for item in write.get("derived_members") or []
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            }
            retained_rows = write.get("retained_members")
            if retained_rows is not None and (
                not isinstance(retained_rows, list)
                or not retained_rows
                or not all(isinstance(item, str) and item for item in retained_rows)
                or len(retained_rows) != len(set(retained_rows))
            ):
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.retained_members must be a unique non-empty array of value member names",
                )
                retained_rows = None
            retained = set(retained_rows or [])
            for label, names in (
                ("authored", authored),
                ("projection-derived", projected),
                ("derived", derived),
                ("retained", retained),
            ):
                unknown = sorted(names - declared)
                if unknown:
                    lint.fail(
                        EVENT_KIND_REGISTRY,
                        f"{where} declares {label} member(s) {unknown} that {value_schema_ref} does not "
                        "declare",
                    )
            for left_label, left, right_label, right in (
                ("authored", authored, "retained", retained),
                ("derived", derived, "retained", retained),
            ):
                overlap = sorted(left & right)
                if overlap:
                    lint.fail(
                        EVENT_KIND_REGISTRY,
                        f"{where} lists {overlap} as both {left_label} and {right_label}; one member has "
                        "exactly one source on one write",
                    )
            unaccounted = sorted(required - (authored | projected | derived | retained))
            if unaccounted:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where} leaves required member(s) {unaccounted} of {value_schema_ref} with no "
                    "registered source: name them as author input, derived_members[] or retained_members[]",
                )
            for name in retained:
                carried[family].setdefault(name, set()).add(where)
            for name in derived:
                produced[family].setdefault(name, set()).add(where)
            for item in write.get("derived_members") or []:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                if isinstance(name, str):
                    produced[family].setdefault(name, set()).add(where)
            forbidden = _effective_forbidden_paths(lint, where, write, kind)
            if forbidden is not None:
                # A `create_locked` ban owned by THIS event kind is not a ban on
                # this write. The basis says the member is decided once, at
                # create, and may never be patched afterwards -- and for a member
                # no derivation can produce, deciding it once IS author input on
                # the create kind. `actor_profile.principal_id` is the case that
                # made this explicit: nothing can derive which principal a
                # profile is for, `profiles-presence.md` section 2.3 has the
                # create declare it, and closing the patch surface against it
                # would otherwise have closed the create surface too, leaving a
                # required member with no source at all. The carve-out is as
                # narrow as the universal_exemptions one above it: the row's
                # `owner_kind` must be `event_kind` and its `owner` must be the
                # kind now writing, so a create-lock owned by another kind stays
                # forbidden here, and the patch surface is untouched in every
                # case -- `_check_result_apply_patch_projection` solves against
                # the full set.
                exempt = _owner_author_paths(lint, where, write, kind)
                reserved = sorted(
                    path
                    for path in authored
                    if _names_a_forbidden_path(path, forbidden - exempt)
                )
                if reserved:
                    lint.fail(
                        EVENT_KIND_REGISTRY,
                        f"{where} lets the author supply reducer-managed member(s) {reserved}; a "
                        "whole-value projection MUST NOT reach what a patch may not reach",
                    )

    for family, entry in covered.items():
        maintenance = entry["maintenance"]
        writes = seen_writes[family]
        if not writes:
            lint.fail(
                REDUCER_MANAGED_PATH_REGISTRY,
                f"family {family!r} declares value_member_maintenance but has no registered write",
            )
            continue
        for item in maintenance.get("always_maintained") or []:
            if not isinstance(item, dict):
                continue
            path = item.get("name") or item.get("path")
            derivation = item.get("derivation")
            if not isinstance(path, str):
                continue
            if derivation not in CELL_WRITE_DERIVATIONS:
                lint.fail(
                    REDUCER_MANAGED_PATH_REGISTRY,
                    f"always_maintained {path!r} of family {family!r} names derivation "
                    f"{derivation!r}, which is not in the closed derivation vocabulary",
                )
            missing = sorted(set(writes) - produced[family].get(path, set()))
            if missing:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"family {family!r} requires {path!r} to be maintained by every write, but "
                    f"{missing} produce no such derived member",
                )
        for item in maintenance.get("create_locked") or []:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            derivation = item.get("derivation")
            producer_kinds = item.get("producer_kinds")
            if not isinstance(path, str) or not isinstance(producer_kinds, list):
                lint.fail(
                    REDUCER_MANAGED_PATH_REGISTRY,
                    f"create_locked row of family {family!r} MUST carry path and producer_kinds",
                )
                continue
            if derivation not in CELL_WRITE_DERIVATIONS:
                lint.fail(
                    REDUCER_MANAGED_PATH_REGISTRY,
                    f"create_locked {path!r} of family {family!r} names derivation {derivation!r}, "
                    "which is not in the closed derivation vocabulary",
                )
            if not isinstance(item.get("justification"), str) or not item["justification"]:
                lint.fail(
                    REDUCER_MANAGED_PATH_REGISTRY,
                    f"create_locked {path!r} of family {family!r} MUST say why the member cannot be "
                    "author input",
                )
            creators = {
                where for where in writes if where.split(".result_writes[")[0] in producer_kinds
            }
            if not creators:
                lint.fail(
                    REDUCER_MANAGED_PATH_REGISTRY,
                    f"create_locked {path!r} of family {family!r} names producer_kinds "
                    f"{producer_kinds}, none of which registers a write into the family",
                )
            missing = sorted(creators - produced[family].get(path, set()))
            if missing:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"family {family!r} locks {path!r} at create, but {missing} declare no "
                    f"derived_members[] entry producing it",
                )
            re_derived = sorted(produced[family].get(path, set()) - creators)
            if re_derived:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{re_derived} re-derive create-locked member {path!r} of family {family!r}; "
                    "after create it may only be retained",
                )
            uncarried = sorted(set(writes) - creators - carried[family].get(path, set()))
            if uncarried:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"family {family!r} locks {path!r} at create, but {uncarried} neither retain it "
                    "nor are registered creators: a create-locked member MUST be carried verbatim by "
                    "every other write",
                )
        # A path may carry more than one conditional_producers row, because one
        # member can have two producers with two different derivations: after
        # `object_lifecycle_state` was registered, `state` is produced by the
        # create kind through `object_initial_state` AND by the lifecycle kind
        # through `object_lifecycle_state`. A row names exactly one derivation,
        # so the two cases are two rows -- and the "no other write produces this"
        # check has to be solved against the union of the rows for that path,
        # not against one row at a time, or each row would report the other row's
        # producer as an intruder.
        conditional_expected: dict[str, set[str]] = {}
        for item in maintenance.get("conditional_producers") or []:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            allowed_kinds = item.get("producer_kinds")
            if not isinstance(path, str) or not isinstance(allowed_kinds, list):
                continue
            conditional_expected.setdefault(path, set()).update(
                where for where in writes if where.split(".result_writes[")[0] in allowed_kinds
            )
        for item in maintenance.get("conditional_producers") or []:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            derivation = item.get("derivation")
            allowed_kinds = item.get("producer_kinds")
            if not isinstance(path, str) or not isinstance(allowed_kinds, list):
                lint.fail(
                    REDUCER_MANAGED_PATH_REGISTRY,
                    f"conditional_producers row of family {family!r} MUST carry path and producer_kinds",
                )
                continue
            if derivation not in CELL_WRITE_DERIVATIONS:
                lint.fail(
                    REDUCER_MANAGED_PATH_REGISTRY,
                    f"conditional_producers {path!r} of family {family!r} names derivation "
                    f"{derivation!r}, which is not in the closed derivation vocabulary",
                )
            if not isinstance(item.get("condition"), str) or not item["condition"]:
                lint.fail(
                    REDUCER_MANAGED_PATH_REGISTRY,
                    f"conditional_producers {path!r} of family {family!r} MUST state the condition under "
                    "which the member is produced",
                )
            actual = produced[family].get(path, set())
            expected = {
                where for where in writes if where.split(".result_writes[")[0] in allowed_kinds
            }
            if not expected:
                lint.fail(
                    REDUCER_MANAGED_PATH_REGISTRY,
                    f"conditional_producers {path!r} of family {family!r} names producer_kinds "
                    f"{allowed_kinds}, none of which registers a write into the family",
                )
            missing = sorted(expected - actual)
            if missing:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"family {family!r} registers {allowed_kinds} as the producer(s) of {path!r}, but "
                    f"{missing} declare no such derived member",
                )
            extra = sorted(actual - conditional_expected.get(path, expected))
            if extra:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{extra} produce {path!r} for family {family!r}, which "
                    "reducer-managed-path-registry.json assigns to the producer_kinds of its "
                    "conditional_producers row(s) alone",
                )


def _check_result_keyed_set_projection(lint: Lint, where: str, write: dict, projection: dict) -> None:
    """Validate one keyed-set `result_projection` and its `for_each` closure.

    The add tag MUST be the write's own canonical dot. `key-management.md`
    section 3.6.1 says so in as many words ("绝不是裸 `event_id`"), and the reason
    is mechanical: one Event may carry several writes on one subject, so a bare
    `event_id` is not unique among them and two entries would collide on one tag.

    `keyed_set_remove_observed.match` has two spellings, and until
    `ak.agent.key.revoke` was registered it had neither a user nor a prose
    definition -- lint vocabulary with no reader, which is what this file exists
    to refuse one level down.

    * `{element_field, source}` is an equality predicate: the named element
      member must equal the value at the named source path.
    * `{element_field, present: true}` is an existence predicate: every observed
      element that HAS the named member is removed.

    The existence spelling exists for exactly one obligation the equality
    spelling cannot express. `identity/key-management.md` section 3.6.1 scopes
    the revoke removal to every *active authorize* dot and says in the same
    sentence that a revocation marker is not an active authorization, and line
    163 confirms a marker outlives a later re-attach -- so a match-less removal,
    which takes every observed element in scope (`zh/models/pins.md` section
    4.1), would drop the earlier boundary. The discrimination itself is already
    determinate on the wire: `agent_key_authorization_entry.value` is a oneOf of
    `agent_key_authorize_payload` and `agent_key_revoke_payload`, both
    `additionalProperties: false` with disjoint required sets, so
    `verification_method` is present on every authorize element and forbidden on
    every marker. What was missing was only the word for it, and no field of the
    revoke payload equals an authorize-only member, so equality could not stand
    in.

    `present: false` is refused. The complement set is strictly wider, nothing
    needs it, and in the one registered use it would remove precisely the
    markers the section requires the value to keep.
    """
    kind = projection["kind"]
    if kind == "keyed_set_add":
        unknown = set(projection) - {"kind", "tag", "value"}
        if unknown:
            lint.fail(EVENT_KIND_REGISTRY, f"{where}.result_projection has unknown member(s) {sorted(unknown)}")
        if projection.get("tag") != {"dot": True}:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f'{where}.result_projection.tag must be exactly {{"dot": true}}; the stable element '
                "tag is the canonical <event_id>:<write_index> dot, never a bare event_id",
            )
        _check_projection_value_source(
            lint, f"{where}.result_projection.value", projection.get("value")
        )
    elif kind == "keyed_set_remove_observed":
        unknown = set(projection) - {"kind", "match"}
        if unknown:
            lint.fail(EVENT_KIND_REGISTRY, f"{where}.result_projection has unknown member(s) {sorted(unknown)}")
        match = projection.get("match")
        if match is None:
            return
        if not isinstance(match, dict) or set(match) - {"element_field", "source", "present"}:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{where}.result_projection.match must be {{element_field, source}} or "
                "{element_field, present}",
            )
            return
        from .foundation import lint_field_path

        lint_field_path(
            lint, EVENT_KIND_REGISTRY, f"{where}.result_projection.match.element_field", match.get("element_field")
        )
        named = [member for member in ("source", "present") if member in match]
        if len(named) != 1:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{where}.result_projection.match must declare exactly one of source/present",
            )
            return
        if "present" in match and match["present"] is not True:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{where}.result_projection.match.present may only be true; an absence predicate "
                "would remove the elements that LACK the field, which is the strictly wider set and "
                "in the one registered use would delete the revocation boundary markers it must keep",
            )
    elif kind == "keyed_set_remove_dots":
        if "for_each" not in write:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{where}.result_projection keyed_set_remove_dots is legal only inside the registered "
                "for_each supersedes remove; a payload-enumerated dot array with no per-item bound is "
                "an open removal loop",
            )


RESULT_FAMILY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_COVERAGE_NOTE_RE = re.compile(
    r"(\d+) of the (\d+) reducer_input kinds declare it; the remaining (\d+)"
)
CURRENT_RESULT_REGISTRY = ARTIFACTS / "registry" / "current-result-registry.json"


def _registered_result_families(lint: Lint) -> set[str] | None:
    """The closed typed current result families, with each row's schema resolved."""
    data = load_json(lint, CURRENT_RESULT_REGISTRY)
    kinds = data.get("result_kinds") if isinstance(data, dict) else None
    if not isinstance(kinds, list) or not kinds:
        lint.fail(CURRENT_RESULT_REGISTRY, "result_kinds[] must be a non-empty array")
        return None
    families: set[str] = set()
    documents: dict[str, Any] = {}
    for index, row in enumerate(kinds):
        where = f"result_kinds[{index}]"
        if not isinstance(row, dict):
            lint.fail(CURRENT_RESULT_REGISTRY, f"{where} must be an object")
            continue
        kind = row.get("result_kind")
        if not isinstance(kind, str) or not RESULT_FAMILY_RE.fullmatch(kind):
            lint.fail(
                CURRENT_RESULT_REGISTRY,
                f"{where}.result_kind must be a snake_case typed current result family name",
            )
        elif kind in families:
            lint.fail(CURRENT_RESULT_REGISTRY, f"{where}.result_kind duplicates {kind!r}")
        else:
            families.add(kind)
        schema_ref = row.get("schema_ref")
        if not isinstance(schema_ref, str) or not schema_ref.startswith("schemas/"):
            lint.fail(
                CURRENT_RESULT_REGISTRY,
                f"{where}.schema_ref must point into artifacts/schemas",
            )
            continue
        file_ref, separator, fragment_body = schema_ref.partition("#")
        if file_ref not in documents:
            path = ARTIFACTS / file_ref
            documents[file_ref] = load_json(lint, path) if path.is_file() else None
        document = documents[file_ref]
        if document is None:
            lint.fail(
                CURRENT_RESULT_REGISTRY,
                f"{where}.schema_ref does not resolve: {schema_ref}",
            )
            continue
        try:
            node = resolve_json_pointer(document, f"#{fragment_body}" if separator else "")
        except (KeyError, IndexError, ValueError):
            node = None
        if not isinstance(node, dict):
            lint.fail(
                CURRENT_RESULT_REGISTRY,
                f"{where}.schema_ref does not resolve to a schema object: {schema_ref}",
            )
    return families


# `canonical_json` and `string_set_digest` describe how one component of a
# multi-component subject is reduced to bytes. Neither has a row in the closed
# embedding table, so neither has a defined wire id on its own, and neither is a
# member of CELL_SUBJECT_KINDS -- a top-level use is already rejected there, and
# is spelled as a single-component composite instead (ruling 2026-09-05-1200,
# conformance/encoding.md section 9.5.1).
_SUBJECT_COMPONENT_KINDS = frozenset({"canonical_json", "string_set_digest"})
_MULTI_COMPONENT_SUBJECT_KINDS = frozenset({"composite", "tuple"})


def _check_subject_component(
    lint: Lint, ref: str, component: Any, event_kind: Any = None
) -> None:
    """One component of a `composite` or `tuple` subject.

    A `string_set_digest` component carries a third member, `context`, and it is
    not decoration: the digest is domain-separated, so the same scope set under
    two contexts is two different keys. `zh/models/actor.md:141` fixes both sides
    of the `identity_accountability` selector as
    `string_set_digest(payload.accountability_scope, ak.accountability_scope_set.v1)`
    precisely so the general grant and the provision projection land on one
    result. The component grammar closed to `{kind, field}` when it was written
    here, which made that sentence unregisterable; `context` is validated by
    `foundation.lint_string_set_digest_component`, which the retired
    `cell_writes[]` loop was the only caller of.
    """
    from .foundation import lint_string_set_digest_component, lint_subject_field_path

    if isinstance(component, str):
        lint_subject_field_path(lint, EVENT_KIND_REGISTRY, ref, component)
        return
    if not isinstance(component, dict):
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{ref} must be an explicit field path or a {{kind, field}} descriptor",
        )
        return
    kind = component.get("kind")
    if kind == "string_set_digest":
        lint_string_set_digest_component(
            lint, EVENT_KIND_REGISTRY, ref, component, event_kind=event_kind
        )
        return
    unknown = set(component) - {"kind", "field"}
    if unknown:
        lint.fail(EVENT_KIND_REGISTRY, f"{ref} has unknown member(s) {sorted(unknown)}")
    if kind not in _SUBJECT_COMPONENT_KINDS:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{ref}.kind must be one of {sorted(_SUBJECT_COMPONENT_KINDS)}, not {kind!r}; "
            "those are the only registered component descriptors, and a typed-ID component "
            "belongs to a typed_pair subject rather than to this one",
        )
    if "field" not in component:
        lint.fail(EVENT_KIND_REGISTRY, f"{ref}.field is required")
        return
    lint_subject_field_path(lint, EVENT_KIND_REGISTRY, f"{ref}.field", component["field"])


def _check_result_selector(
    lint: Lint, ref: str, selector: Any, id_source: Any = None, event_kind: Any = None
) -> None:
    """A singleton is JSON null; anything else is a closed subject descriptor.

    conformance/encoding.md section 9.5.1 is the whole rule: "subject 的 registry
    字段来源必须显式命名", and a bare field name or a payload-then-envelope
    fallback is undefined and MUST be rejected. Before this closure only the
    `kind` itself was checked against the closed table, plus a shallow
    non-empty/no-duplicate pass over `composite.components` -- so a subject could
    name no source at all, name one through an unregistered envelope field, or
    carry members nobody reads, and the registry would still pass.

    That was not hypothetical: `authz/capabilities.md` says the revoke selector
    derives from `payload.grant_id` and `extensions/mimi-interop.md` says the
    room-binding subject is `payload.mimi_room_uri` under a `uri` kind, and
    neither sentence could be spelled in the grammar, because a non-composite
    subject had nowhere to name its field.

    A fieldless `id:<object kind>` subject stays legal only where it already
    means something: an `id_source: "event_derived"` Event kind, where the
    object's id is this Event's own id retyped. `ak.capability.grant` and
    `ak.strand.create` are the two live uses and both say so in their notes. On
    any other row a missing `field` is exactly the undefined bare source that
    section 9.5.1 rejects.
    """
    from .foundation import is_registered_cell_subject_kind, lint_subject_field_path

    if selector is None:
        return
    if not isinstance(selector, dict):
        lint.fail(EVENT_KIND_REGISTRY, f"{ref} must be JSON null or an object")
        return
    kind = selector.get("kind")
    if not isinstance(kind, str) or not is_registered_cell_subject_kind(kind):
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{ref}.kind is not in the encoding.md section 4.1 closed subject table: {kind!r}",
        )
        return
    if kind in _MULTI_COMPONENT_SUBJECT_KINDS:
        unknown = set(selector) - {"kind", "components"}
        if unknown:
            lint.fail(EVENT_KIND_REGISTRY, f"{ref} has unknown member(s) {sorted(unknown)}")
        components = selector.get("components")
        if not isinstance(components, list) or not components:
            lint.fail(EVENT_KIND_REGISTRY, f"{ref}.components must be a non-empty array")
            return
        if len(components) != len({json.dumps(part, sort_keys=True) for part in components}):
            lint.fail(EVENT_KIND_REGISTRY, f"{ref}.components must not repeat a component")
        for index, component in enumerate(components):
            _check_subject_component(
                lint, f"{ref}.components[{index}]", component, event_kind
            )
        return
    if kind == "typed_pair":
        _check_typed_pair_components(lint, ref, selector)
        return
    if kind == "coalesce":
        unknown = set(selector) - {"kind", "fields"}
        if unknown:
            lint.fail(EVENT_KIND_REGISTRY, f"{ref} has unknown member(s) {sorted(unknown)}")
        fields = selector.get("fields")
        if not isinstance(fields, list) or not fields:
            lint.fail(EVENT_KIND_REGISTRY, f"{ref}.fields must be a non-empty array")
            return
        if len(fields) != len({json.dumps(part, sort_keys=True) for part in fields}):
            lint.fail(EVENT_KIND_REGISTRY, f"{ref}.fields must not repeat a field")
        for index, field in enumerate(fields):
            lint_subject_field_path(lint, EVENT_KIND_REGISTRY, f"{ref}.fields[{index}]", field)
        return
    unknown = set(selector) - {"kind", "field"}
    if unknown:
        lint.fail(EVENT_KIND_REGISTRY, f"{ref} has unknown member(s) {sorted(unknown)}")
    if "field" in selector:
        lint_subject_field_path(lint, EVENT_KIND_REGISTRY, f"{ref}.field", selector["field"])
        if id_source == "event_derived" and kind.startswith("id:"):
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{ref} names a source field on an id_source=event_derived Event kind; the "
                "fieldless form already means this Event's own id retyped, so naming a field "
                "here says the object id comes from the payload and contradicts the row",
            )
    elif id_source == "event_derived" and kind.startswith("id:"):
        return
    else:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{ref}.field is required for a {kind!r} subject; encoding.md section 9.5.1 says a "
            "subject's registry field source MUST be named explicitly, and only an "
            "id_source=event_derived id:<object kind> subject may omit it (it is then this "
            "Event's own id retyped)",
        )


def _check_typed_pair_components(lint: Lint, ref: str, selector: Any) -> None:
    """A `typed_pair` subject is a reversible two-component typed-ID encoding.

    `zh/models/realm-and-space.md` section 3.6 is the only paragraph that pins a
    family to this kind, and it pins the reason too: the wire form
    `strand_position:<board_space_id>:<strand_id>` MUST stay invertible, so the
    SHA-256 subject of `tuple`/`composite` is explicitly not applicable and a
    reader MUST validate BOTH typed-ID components rather than slicing the tail.
    Neither property survives a free-form component list: two components in a
    fixed order, each naming its own registered id kind, is what makes the
    encoding reversible and the pair-wise validation possible.

    So the shape is closed here rather than left to `composite`'s weaker "any
    non-repeating list" rule. Without this branch `typed_pair` would sit in the
    closed subject table with no grammar behind it -- a subject kind spelled in
    prose and in the registry that nothing agrees on, which is the same shell
    one level down from the family shells the writer gate refuses.
    """
    from .foundation import CELL_SUBJECT_ID_KIND_RE, lint_field_path
    from .naming_contracts import ID_KIND_REGISTRY_PATH, registered_id_kinds

    unknown = set(selector) - {"kind", "components"}
    if unknown:
        lint.fail(EVENT_KIND_REGISTRY, f"{ref} has unknown member(s) {sorted(unknown)}")
    components = selector.get("components")
    if not isinstance(components, list) or len(components) != 2:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{ref}.components must be exactly two ordered components; the reversible "
            "typed_pair encoding of zh/models/realm-and-space.md section 3.6 has no other arity",
        )
        return
    id_kinds = registered_id_kinds(load_json(lint, ID_KIND_REGISTRY_PATH))
    fields: list[str] = []
    for index, part in enumerate(components):
        where = f"{ref}.components[{index}]"
        if not isinstance(part, dict) or set(part) != {"kind", "field"}:
            lint.fail(EVENT_KIND_REGISTRY, f"{where} must be exactly {{kind, field}}")
            continue
        part_kind = part["kind"]
        if not isinstance(part_kind, str) or CELL_SUBJECT_ID_KIND_RE.fullmatch(part_kind) is None:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{where}.kind must be an `id:<object kind>` typed-ID kind, not {part_kind!r}; "
                "a typed_pair component that is not typed cannot be validated on parse",
            )
        elif id_kinds and part_kind[len("id:") :] not in id_kinds:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{where}.kind {part_kind!r} is not a registered id_kinds[] row of "
                "registry/id-kind-registry.json",
            )
        lint_field_path(lint, EVENT_KIND_REGISTRY, f"{where}.field", part["field"])
        if isinstance(part["field"], str):
            fields.append(part["field"])
    if len(fields) == 2 and fields[0] == fields[1]:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{ref}.components must not read the same field twice; the two ordered components "
            "are what make the subject invertible",
        )


_VALUE_SCHEMA_REF_DEPTH = 6


def _value_schema_alternatives(
    lint: Lint, file_ref: str, node: Any, depth: int = 0
) -> list[tuple[set[str], set[str]]]:
    """Resolve one registered value schema to its alternative member shapes.

    A `value_projection` builds the stored value out of members named one at a
    time, so the question a reader has -- is this member part of the value this
    family stores, and does a whole-value `set` write all of it? -- is answered
    by the write's own `value_schema_ref`. Nothing read it, so a member name
    could be anything: `ak.member.state` pointed its ref at the enclosing
    `member_state_result` envelope, whose own members are selector/revision/value,
    and wrote `membership` into it.

    Each entry is one alternative the value may take, as (declared, required).
    Resolution follows the three shapes the registered value schemas use: a
    direct `properties` map, a `$ref` (local `#/$defs/...` or a sibling artifact
    file), and `oneOf`/`anyOf` branches, which are alternatives rather than a
    union because `required` only binds inside the branch that matched. An
    `allOf` member is a conjunction and folds into the enclosing alternative. A
    `{"type": "null"}` branch is dropped rather than reported: it is a real
    registered state -- `strand_position_value` spells pre-placement that way --
    but an object projection can never produce it, so it constrains nothing.
    """
    if depth > _VALUE_SCHEMA_REF_DEPTH or not isinstance(node, dict):
        return []
    ref = node.get("$ref")
    if isinstance(ref, str):
        target_file, separator, fragment = ref.partition("#")
        if target_file in ("", "."):
            target_ref = file_ref
        else:
            target_ref = posixpath.normpath(
                posixpath.join(posixpath.dirname(file_ref), target_file)
            )
        path = ARTIFACTS / target_ref
        document = load_json(lint, path) if path.is_file() else None
        if not isinstance(document, dict):
            return []
        try:
            target = resolve_json_pointer(document, f"#{fragment}") if separator else document
        except (KeyError, IndexError, ValueError):
            return []
        return _value_schema_alternatives(lint, target_ref, target, depth + 1)
    branches = node.get("oneOf") or node.get("anyOf")
    if isinstance(branches, list) and branches:
        alternatives: list[tuple[set[str], set[str]]] = []
        for branch in branches:
            if isinstance(branch, dict) and branch.get("type") == "null":
                continue
            alternatives.extend(_value_schema_alternatives(lint, file_ref, branch, depth + 1))
        return alternatives
    declared = set(node["properties"]) if isinstance(node.get("properties"), dict) else set()
    required = set(node["required"]) if isinstance(node.get("required"), list) else set()
    for member in node.get("allOf") or ():
        for member_declared, member_required in _value_schema_alternatives(
            lint, file_ref, member, depth + 1
        ):
            declared |= member_declared
            required |= member_required
    if not declared:
        return []
    return [(declared, required)]


def check_result_write_contracts(lint: Lint) -> None:
    """Validate the registered shared-state ``result_writes[]`` of each Event kind.

    ``zh/models/realm-and-space.md`` section 2.5.1 makes ``contract-registry.json``
    the machine source for which typed current results an Event kind writes. A
    registry array nobody validates is how the previous ``cell_writes[]`` promise
    stayed a promise, so the grammar is closed here from the start.

    Every declared ``result_family`` MUST also be a registered ``result_kinds[]``
    row of ``current-result-registry.json`` whose ``schema_ref`` resolves: a write
    into an unregistered family is the same failure mode one level down -- prose
    and reducers would share a family name that no closed selector/value schema
    defines.
    """
    registered_families = _registered_result_families(lint)
    if registered_families is None:
        return
    registry = load_json(lint, EVENT_KIND_REGISTRY)
    rows = registry.get("event_kinds") if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        lint.fail(EVENT_KIND_REGISTRY, "event_kinds[] must be an array")
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        writes = row.get("result_writes")
        if writes is None:
            continue
        kind = row.get("event_kind")
        if not isinstance(writes, list) or not writes:
            lint.fail(EVENT_KIND_REGISTRY, f"{kind}.result_writes must be a non-empty array")
            continue
        if row.get("reducer_input") is not True:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{kind} declares result_writes but is not a reducer_input Event kind",
            )
        for index, write in enumerate(writes):
            where = f"{kind}.result_writes[{index}]"
            if not isinstance(write, dict):
                lint.fail(EVENT_KIND_REGISTRY, f"{where} must be an object")
                continue
            unknown = set(write) - {
                "result_family",
                "result_selector",
                "for_each",
                "condition",
                "result_projection",
                "derived_members",
                "retained_members",
                "value_schema_ref",
                "notes",
            }
            if unknown:
                lint.fail(EVENT_KIND_REGISTRY, f"{where} has unknown member(s) {sorted(unknown)}")
            if "for_each" in write:
                agent_supersedes = (
                    kind != "ak.agent.key.authorize"
                    or index != 0
                    or write["for_each"] != _AGENT_SUPERSEDES_FOR_EACH
                    or write.get("result_selector") != _AGENT_SUPERSEDES_SELECTOR
                    or write.get("result_projection") != _AGENT_SUPERSEDES_PROJECTION
                ) is False
                if not agent_supersedes:
                    lint.fail(
                        EVENT_KIND_REGISTRY,
                        f"{where}.for_each is restricted to the exact Agent supersedes remove; "
                        "arbitrary per-item loops have no atomicity or field-source contract",
                    )
            elif kind == "ak.agent.key.authorize" and index == 0:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where} must enumerate the bounded exact supersedes set before the add",
                )
            family = write.get("result_family")
            if not isinstance(family, str) or not RESULT_FAMILY_RE.fullmatch(family):
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.result_family must be a snake_case typed current result family name",
                )
            elif family not in registered_families:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.result_family {family!r} is not a registered result_kinds[] row of "
                    "registry/current-result-registry.json",
                )
            if "result_selector" not in write:
                lint.fail(EVENT_KIND_REGISTRY, f"{where}.result_selector is required (JSON null for a singleton)")
            else:
                _check_result_selector(
                    lint,
                    f"{where}.result_selector",
                    write["result_selector"],
                    row.get("id_source"),
                    kind,
                )
            derived_members = write.get("derived_members")
            if derived_members is not None:
                from .foundation import lint_derived_members

                lint_derived_members(
                    lint, EVENT_KIND_REGISTRY, f"{where}.derived_members", derived_members
                )
            projection = write.get("result_projection")
            if not isinstance(projection, dict) or projection.get("kind") not in _RESULT_PROJECTION_KINDS:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.result_projection.kind must be one of {sorted(_RESULT_PROJECTION_KINDS)}",
                )
                continue
            if projection["kind"] == "transition":
                unknown = set(projection) - {"kind", "from", "to"}
                if unknown:
                    lint.fail(
                        EVENT_KIND_REGISTRY,
                        f"{where}.result_projection has unknown member(s) {sorted(unknown)}",
                    )
                # A const endpoint is the sharper declaration and stays the norm.
                # A field endpoint exists because one row can carry several edges
                # whose prestate only the payload knows: agent_deactivate_payload
                # closes previous_status to [active, paused], and
                # history_access_payload closes from to null plus both states. In
                # those two shapes a const would have to pick one edge and drop
                # the rest, or restate a closed set the payload schema already
                # holds. check_fsm_state_reachability resolves a field endpoint
                # against that schema, so the edge stays as narrow as the schema
                # is -- an unresolvable field widens to the whole state list
                # rather than inventing reachability.
                for member in ("from", "to"):
                    source = projection.get(member)
                    if not isinstance(source, dict) or len(
                        [key for key in ("const", "field") if key in source]
                    ) != 1:
                        lint.fail(
                            EVENT_KIND_REGISTRY,
                            f"{where}.result_projection.{member} must declare exactly one of "
                            "const/field",
                        )
                    elif "field" in source:
                        from .foundation import lint_field_path

                        lint_field_path(
                            lint,
                            EVENT_KIND_REGISTRY,
                            f"{where}.result_projection.{member}.field",
                            source["field"],
                        )
            elif projection["kind"] == "apply_patch":
                _check_result_apply_patch_projection(lint, where, write, projection, kind)
            elif projection["kind"] in _RESULT_KEYED_SET_KINDS:
                _check_result_keyed_set_projection(lint, where, write, projection)
            elif "value" not in projection and "value_projection" not in projection:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.result_projection must declare value or value_projection",
                )
            elif "value" in projection:
                _check_projection_value_source(
                    lint, f"{where}.result_projection.value", projection["value"]
                )
            condition = write.get("condition")
            if condition is not None:
                from .foundation import lint_cell_write_condition

                lint_cell_write_condition(lint, EVENT_KIND_REGISTRY, f"{where}.condition", condition)
            value_projection = projection.get("value_projection")
            if value_projection is not None:
                from .foundation import lint_value_projection

                lint_value_projection(
                    lint,
                    EVENT_KIND_REGISTRY,
                    f"{where}.result_projection.value_projection",
                    value_projection,
                )
            value_schema_ref = write.get("value_schema_ref")
            projected_members = (
                value_projection.get("members")
                if isinstance(value_projection, dict)
                else None
            )
            if projected_members and value_schema_ref is None:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where} names value_projection members but declares no value_schema_ref, "
                    "so nothing says which object those members belong to",
                )
            if value_schema_ref is not None:
                if not isinstance(value_schema_ref, str) or not value_schema_ref.startswith("schemas/"):
                    lint.fail(EVENT_KIND_REGISTRY, f"{where}.value_schema_ref must point into artifacts/schemas")
                    continue
                file_ref, separator, fragment_body = value_schema_ref.partition("#")
                path = ARTIFACTS / file_ref
                document = load_json(lint, path) if path.is_file() else None
                if document is None:
                    lint.fail(EVENT_KIND_REGISTRY, f"{where}.value_schema_ref does not resolve: {value_schema_ref}")
                    continue
                try:
                    node = resolve_json_pointer(document, f"#{fragment_body}" if separator else "")
                except (KeyError, IndexError, ValueError):
                    node = None
                if not isinstance(node, dict):
                    lint.fail(
                        EVENT_KIND_REGISTRY,
                        f"{where}.value_schema_ref does not resolve to a schema object: {value_schema_ref}",
                    )
                elif projected_members:
                    _check_projected_members(
                        lint, where, write, projection, value_schema_ref, file_ref, node
                    )

    _check_prose_result_write_citations(lint, rows)


def _check_projected_members(
    lint: Lint,
    where: str,
    write: dict,
    projection: dict,
    value_schema_ref: str,
    file_ref: str,
    node: Any,
) -> None:
    """Hold a value_projection to the value schema the same write names."""
    alternatives = _value_schema_alternatives(lint, file_ref, node)
    if not alternatives:
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{where}.value_schema_ref declares no members, so its value_projection cannot be "
            f"checked against it: {value_schema_ref}",
        )
        return
    declared: set[str] = set()
    for alternative_declared, _ in alternatives:
        declared |= alternative_declared
    projected: set[str] = set()
    for member in projection["value_projection"]["members"]:
        if not isinstance(member, dict):
            continue
        name = member.get("name")
        if not isinstance(name, str):
            continue
        projected.add(name)
        if name not in declared:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{where}.result_projection.value_projection member {name!r} is not declared by "
                f"value_schema_ref {value_schema_ref}",
            )
    if projection["kind"] != "set" or write.get("derived_members"):
        # `merge` writes only the members it names, so an unnamed required member
        # is the already-projected value's, not this write's. A write that also
        # materialises derived members is undecidable here for a different
        # reason: `derived_members[].name` is the registered reducer derivation,
        # and which value member that derivation lands in is fixed by the
        # normative rule rather than by this row.
        return
    # A `set` replaces the whole value, so anything a matching alternative
    # requires and this projection does not write produces a value that violates
    # its own registered schema on the first replay.
    floor: set[str] | None = None
    for _, alternative_required in alternatives:
        floor = alternative_required if floor is None else floor & alternative_required
    for name in sorted((floor or set()) - projected):
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{where}.result_projection is a whole-value set but does not write {name!r}, which "
            f"value_schema_ref {value_schema_ref} requires",
        )


def check_result_write_coverage_note(lint: Lint) -> None:
    """The coverage note MUST count the rows that are actually there.

    ``registry_rules`` calls partial ``result_writes[]`` coverage a known gap and
    tells the next editor to shrink the note as coverage grows. Nothing read it,
    so it stayed at the numbers it was written with while four commits raised
    coverage -- a source-of-truth registry describing itself wrongly, which is
    the same defect class as a stale generated mirror except that no digest
    catches it. The note carried an enumeration of the declaring kinds too;
    ``event_kinds[]`` already is that list, so the copy is gone and only the two
    counts remain, recomputed here from the rows.
    """
    block = load_json(lint, EVENT_KIND_REGISTRY)
    rows = block.get("event_kinds") if isinstance(block, dict) else None
    if not isinstance(rows, list):
        lint.fail(
            EVENT_KIND_REGISTRY,
            "event_kinds[] is missing, so result_writes[] coverage cannot be counted",
        )
        return
    reducer_inputs = [row for row in rows if isinstance(row, dict) and row.get("reducer_input")]
    covered = [row for row in reducer_inputs if row.get("result_writes")]
    notes = [
        rule
        for rule in (block.get("registry_rules") or ())
        if isinstance(rule, str) and "COVERAGE IS PARTIAL" in rule
    ]
    if len(notes) != 1:
        lint.fail(
            EVENT_KIND_REGISTRY,
            "event_kind_registry.registry_rules must carry exactly one result_writes[] coverage "
            f"note, found {len(notes)}",
        )
        return
    match = _COVERAGE_NOTE_RE.search(notes[0])
    if match is None:
        lint.fail(
            EVENT_KIND_REGISTRY,
            "the result_writes[] coverage note must state coverage as "
            "'<n> of the <total> reducer_input kinds declare it; the remaining <rest>'",
        )
        return
    declared, total, remaining = (int(group) for group in match.groups())
    if (declared, total, remaining) != (
        len(covered),
        len(reducer_inputs),
        len(reducer_inputs) - len(covered),
    ):
        lint.fail(
            EVENT_KIND_REGISTRY,
            "the result_writes[] coverage note says "
            f"{declared} of {total} with {remaining} remaining, but event_kinds[] has "
            f"{len(covered)} of {len(reducer_inputs)} with "
            f"{len(reducer_inputs) - len(covered)} remaining",
        )
    if "ak." in notes[0]:
        lint.fail(
            EVENT_KIND_REGISTRY,
            "the result_writes[] coverage note must not enumerate the declaring kinds: "
            "event_kinds[] is that list and the copy went stale",
        )


def check_every_result_family_has_a_writer(lint: Lint) -> None:
    """Every registered typed current result family MUST have at least one writer.

    ``check_result_write_contracts`` closes the write -> family direction: a
    ``result_writes[]`` row may only name a registered family. This closes the
    other direction, which is where the ``cell_writes[]`` promise actually
    decayed. A family can sit in ``current-result-registry.json`` with a closed
    selector/value schema and a resolvable ``$defs`` entry and still have no
    Event kind that produces it. Prose then reads as if that state exists,
    reducers have nothing to replay, and no gate says a word -- a registered
    shell.

    Partial ``result_writes[]`` coverage is a known and recorded gap (see the
    ``event_kind_registry`` rule), so this check deliberately does NOT require
    every ``reducer_input`` kind to declare a contract. It requires only the one
    invariant that holds regardless of how far coverage has been extended: a
    family nobody writes MUST NOT stay registered. Either register its writer or
    withdraw the family.
    """
    registered = _registered_result_families(lint)
    if registered is None:
        return
    registry = load_json(lint, EVENT_KIND_REGISTRY)
    rows = registry.get("event_kinds") if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        # check_result_write_contracts reports the shape failure; one is enough.
        return
    written: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        writes = row.get("result_writes")
        if not isinstance(writes, list):
            continue
        for write in writes:
            if isinstance(write, dict) and isinstance(write.get("result_family"), str):
                written.add(write["result_family"])
    for family in sorted(registered - written):
        lint.fail(
            CURRENT_RESULT_REGISTRY,
            f"result family {family!r} is registered but no Event kind declares a "
            "result_writes[] row that produces it; register its writer or withdraw "
            "the family",
        )



ASSERTED_FAMILY_EXEMPTIONS = TOOLS_ROOT / "asserted-result-family-exemptions.json"
EVENT_PAYLOAD_SCHEMA = ARTIFACTS / "schemas" / "event-payload.schema.json"
_ASSERTED_FAMILY_RE = re.compile(
    r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+) typed current result\b"
)
_ASSERTED_SINGLE_WORD_FAMILY_RE = re.compile(
    r"\b(?:stable|registered|canonical|sole(?: registered)?|one registered) "
    r"([a-z][a-z0-9]*) typed current result (?:family|subject|target|write)\b",
    re.IGNORECASE,
)
_NEGATED_RESULT_ASSERTION_RE = re.compile(
    r"(?:\bno\b|\bnot\b|\bnever\b|\bwithout\b|\bdoes not\b|\bdo not\b|"
    r"\bis not\b|\bare not\b|\bmust not\b)[^.!?]{0,120}$",
    re.IGNORECASE,
)


def _asserted_result_families(text: str) -> set[str]:
    """Return family names from the deliberately closed assertion grammar.

    A token immediately before ``typed current result`` remains the broad
    snake_case form used by the original gate.  Single-word names are accepted
    only when an assignment word and a role noun make the sentence a claim
    (for example, ``stable policy typed current result subject``).  This avoids
    treating titles and ordinary phrases as family declarations while closing
    the old ``policy`` / ``consent`` blind spot.

    A syntactic negation in the same clause suppresses the candidate.  Negative
    vectors say that a write/result does *not* exist; rejecting the family name
    in such a sentence would turn a safety assertion into a registration claim.
    """

    asserted: set[str] = set()
    for pattern in (_ASSERTED_FAMILY_RE, _ASSERTED_SINGLE_WORD_FAMILY_RE):
        for match in pattern.finditer(text):
            clause_prefix = text[max(0, match.start() - 160) : match.start()]
            if _NEGATED_RESULT_ASSERTION_RE.search(clause_prefix):
                continue
            family = match.group(1).lower()
            # ``the sole registered typed current result subject`` asserts
            # uniqueness but names no family.  Backtracking in the assignment
            # pattern can otherwise misread ``registered`` as the name.
            if family in {"registered", "typed", "current"}:
                continue
            asserted.add(family)
    return asserted


def _asserted_result_family_sources() -> list[Path]:
    """All JSON artifact surfaces, including profiles, fixtures and reports.

    Generated views are intentionally included.  They are not independent
    proof of a registration, but their prose is still consumed by implementers;
    scanning both source and projection also makes a generated/source wording
    split fail instead of hiding in the projection.  Projection equality is
    enforced separately by the artifact generator.
    """

    return sorted(ARTIFACTS.rglob("*.json"))


def check_asserted_result_families_are_registered(lint: Lint) -> None:
    """A description that names a typed current result family must name a registered one.

    ``artifacts/**`` descriptions are a normative surface, not commentary: they
    are the text ``zh`` prose defers to for closed field sets, subjects and write
    contracts, and implementers read them as binding. So a payload description
    saying "rule_id is the stable policy_rule typed current result subject" is a
    registration claim. Nothing checked it. ``check_result_write_contracts`` and
    ``check_every_result_family_has_a_writer`` both start from the registry, so
    neither can see a family that was only ever asserted in prose -- and seven of
    them accumulated exactly that way, including one
    (``mimi_room_binding_payload``) whose description told the reader to consult a
    ``result_selector`` in ``event-kind-registry.json`` that the registry does not
    contain.

    The scanner covers every JSON file under ``artifacts/**`` rather than two
    hand-picked files.  Snake-case assertions retain their broad historical
    grammar.  A single-word family is recognized only in the stronger assignment
    grammar ``<stable/registered/canonical/...> NAME typed current result
    <family/subject/target/write>``; a syntactically negated clause is not an
    assertion.  This is still an auxiliary prose audit, not a general natural
    language parser.  Correctness continues to come from the registered writer,
    selector, schema and maintenance gates.

    ``tools/asserted-result-family-exemptions.json`` is a ratchet in the same
    shape as the proof-context anchor ledger: entries may only be removed, and an
    exempted name that becomes registered is itself an error.
    """
    registered = _registered_result_families(lint)
    if registered is None:
        return

    exemptions: dict[str, str] = {}
    if ASSERTED_FAMILY_EXEMPTIONS.is_file():
        document = load_json(lint, ASSERTED_FAMILY_EXEMPTIONS)
        entries = (
            document.get("unregistered_families") if isinstance(document, dict) else None
        )
        if not isinstance(entries, list):
            lint.fail(
                ASSERTED_FAMILY_EXEMPTIONS, "unregistered_families[] must be an array"
            )
            entries = []
        for entry in entries:
            if not isinstance(entry, dict):
                lint.fail(
                    ASSERTED_FAMILY_EXEMPTIONS,
                    "unregistered_families[] entries must be objects",
                )
                continue
            family = entry.get("result_family")
            reason = entry.get("reason")
            if not isinstance(family, str) or not family:
                lint.fail(
                    ASSERTED_FAMILY_EXEMPTIONS, "every entry must name a result_family"
                )
                continue
            if not isinstance(reason, str) or not reason:
                lint.fail(ASSERTED_FAMILY_EXEMPTIONS, f"{family} must state a reason")
                continue
            exemptions[family] = reason

    asserted: dict[str, Path] = {}
    for path in _asserted_result_family_sources():
        if not path.is_file():
            continue
        for family in _asserted_result_families(path.read_text(encoding="utf-8")):
            asserted.setdefault(family, path)

    for family, path in sorted(asserted.items()):
        if family in registered:
            if family in exemptions:
                lint.fail(
                    ASSERTED_FAMILY_EXEMPTIONS,
                    f"{family} is exempted but is now registered; remove the exemption",
                )
            continue
        if family in exemptions:
            continue
        lint.fail(
            path,
            f"a description asserts the {family!r} typed current result, but "
            "current-result-registry.json registers no such family. An artifact "
            "description is normative, so this either registers the family (a "
            "result_kinds[] row, a typed-current-result.schema.json $defs entry, a "
            "result_writes[] row on its writer and a line in the "
            "zh/sync/current-results.md section 2 list) or rewrites the sentence to "
            "stop asserting one. Record a deliberate lag in "
            "tools/asserted-result-family-exemptions.json with a reason",
        )

    for family in sorted(set(exemptions) - set(asserted)):
        lint.fail(
            ASSERTED_FAMILY_EXEMPTIONS,
            f"{family} is exempted but no description asserts it any more; "
            "remove the exemption",
        )


CURRENT_RESULTS_PROSE = ARTIFACTS.parent / "zh" / "sync" / "current-results.md"
CURRENT_RESULTS_PROSE_HEADING = "## 2. 领域 selector 与 revision"
_PROSE_FAMILY_TOKEN_RE = re.compile(r"`([a-z][a-z0-9_]*)`")


def check_registered_families_are_listed_in_prose(lint: Lint) -> None:
    """Every registered family MUST appear in the normative selector list.

    ``sync/current-results.md`` section 2 opens with "v1 登记的 selector kind 为"
    and then enumerates the families. That sentence is a closure claim: it tells
    an implementer that an unlisted selector is one it MUST reject. The registry
    is what reducers and schemas are generated from, so when a batch adds
    families and leaves the list alone, the prose starts telling implementers to
    reject state the registry requires them to carry -- and nothing said a word,
    because no gate connected the two. That is what happened when fifteen Realm
    facet families landed against a list still naming twenty-three.

    This gate mechanizes one direction only: registry -> this list. The reverse
    on THIS file still is not mechanized, because a backticked token in section 2
    also spells payload fields, subject kinds and Event kinds, so a matcher loose
    enough to catch a stray family name would mostly catch those.

    The reverse direction is NOT the harmless one, and the claim that used to sit
    here -- that an unregistered family name "has no schema and no writer" so the
    naming and writer gates "bite the moment anyone tries to make it real" -- was
    false. Both of those gates start from the registry, so neither can see a name
    that was never registered. The wording asserted a safety property nothing
    implemented, and under it seven families were asserted as registered inside
    ``artifacts/**`` descriptions while no ``result_kinds[]`` row existed for any
    of them. ``check_asserted_result_families_are_registered`` below closes that
    hole for the machine-artifact surface, which is where the assertions actually
    live; this file stays one-directional on purpose and says so.
    """
    registered = _registered_result_families(lint)
    if registered is None:
        return
    if not CURRENT_RESULTS_PROSE.is_file():
        lint.fail(CURRENT_RESULTS_PROSE, "normative selector list is missing")
        return
    text = CURRENT_RESULTS_PROSE.read_text(encoding="utf-8")
    parts = text.split(CURRENT_RESULTS_PROSE_HEADING)
    if len(parts) != 2:
        # Renaming the heading would silently disable this gate, so the anchor is
        # itself part of the contract.
        lint.fail(
            CURRENT_RESULTS_PROSE,
            f"expected exactly one {CURRENT_RESULTS_PROSE_HEADING!r} heading to anchor the "
            "registered selector list",
        )
        return
    section = parts[1].split("\n## ")[0]
    listed = set(_PROSE_FAMILY_TOKEN_RE.findall(section))
    missing = sorted(registered - listed)
    if missing:
        lint.fail(
            CURRENT_RESULTS_PROSE,
            f"section 2 enumerates the registered selector kinds but omits {missing}; "
            "the section tells implementers to reject an unlisted selector, so an omitted "
            "family is prose instructing them to reject state the registry requires",
        )


_PROSE_RESULT_WRITE_CITATION_RE = re.compile(r"(ak\.[a-z0-9_]+(?:\.[a-z0-9_]+)*)\.result_writes")


def _check_prose_result_write_citations(lint: Lint, rows: list[Any]) -> None:
    """Normative prose/artifacts may cite writes only when the kind declares them.

    Coverage is partial on purpose (see the event_kind_registry rule), so the
    dangerous direction is prose promising a machine contract that the registry
    does not carry. That is exactly how `ak.realm.create.result_writes[]` and
    `ak.capability.grant.result_writes[].derived_members[]` sat dangling.
    """
    declared = {
        row.get("event_kind")
        for row in rows
        if isinstance(row, dict) and "result_writes" in row
    }
    prose_root = ARTIFACTS.parent / "zh"
    sources = list(_asserted_result_family_sources())
    if prose_root.is_dir():
        sources.extend(sorted(prose_root.rglob("*.md")))
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for match in _PROSE_RESULT_WRITE_CITATION_RE.finditer(text):
            kind = match.group(1)
            if kind not in declared:
                lint.fail(
                    path,
                    f"cites {kind}.result_writes[] but that Event kind declares no result_writes "
                    "in contract-registry.json; register the contract or stop citing it",
                )


# A whole prior value has to exist before anything can update part of it.
# `set` writes one outright; a `transition` out of the absent state creates the
# object the same way. Everything else builds on what a previous write left.
_PARTIAL_UPDATE_PROJECTIONS = frozenset({"merge", "apply_patch"})
PATCH_BASE_PRODUCER_BASELINE = TOOLS_ROOT / "patch-base-producer-baseline.json"


def _is_base_producer(projection: Any) -> bool:
    if not isinstance(projection, dict):
        return False
    kind = projection.get("kind")
    if kind == "set":
        return True
    if kind != "transition":
        return False
    source = projection.get("from")
    # `from: {"const": null}` is the genesis edge out of the absent state; a
    # transition between two real states changes one axis of a value someone
    # else created.
    return isinstance(source, dict) and "const" in source and source["const"] is None


def _selector_shape(write: dict) -> str:
    selector = write.get("result_selector")
    if selector is None:
        return "null"
    if isinstance(selector, dict):
        return str(selector.get("kind"))
    return str(selector)


def check_pre_state_requirement_closure(lint: Lint) -> None:
    """A pre-state requirement MUST be a closed stored-field predicate.

    `governance-objects.md` states the rule verbatim for `ak.invite.accept`: the
    stored live-target slot and the accept payload MUST be either both absent or
    both present and byte-equal, and a mismatch fails the Event. That is a
    precondition on a *stored value*, not on a revision, and the clean break
    deleted the mechanism that expressed it (`7c9d64db` / `616f3550`) while
    leaving the obligation in the prose -- the recurring defect of a normative
    paragraph describing a structure no artifact defines.

    It comes back in its original shape, with one adaptation. The retired
    version required the requirement's family to be an FSM family, because the
    only rows that carried one were FSM rows. An ordinary slot has no state
    machine, so the family only has to be a registered typed current result
    family here; the rest of the closure (closed member set, the conditional
    payload grammar a conditional write already uses, a registered failure code
    and reason code) is unchanged.

    Three predicates are registered, exactly as before:

    * `stored_field_present` -- the slot member exists;
    * `stored_field_equals_payload` -- it exists and equals the payload field;
    * `stored_field_matches_payload` -- both absent, or both present and equal.

    The third one is what the invite rule needs, and it is not interchangeable
    with the second: a two-valued equality cannot express "both absent" as a
    pass, and reading absence as a mismatch would make the very first invite
    unacceptable.

    A revision compare is deliberately not expressible here. `expected_revision`
    on a shared-face payload is the typed `{commit_id, stream_position}` of the
    value the producer read; a stored-value precondition is this. Two mechanisms,
    two spellings, no overlap.
    """
    registered_families = _registered_result_families(lint)
    if registered_families is None:
        return
    registry = load_json(lint, EVENT_KIND_REGISTRY)
    rows = registry.get("event_kinds") if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        lint.fail(EVENT_KIND_REGISTRY, "event_kinds[] must be an array")
        return
    error_codes = _registered_error_codes(lint)
    valid_predicates = sorted({"stored_field_present"} | _PRE_STATE_PAYLOAD_PREDICATES)
    for row in rows:
        if not isinstance(row, dict):
            continue
        requirements = row.get("pre_state_requirements")
        if requirements is None:
            continue
        kind = row.get("event_kind")
        if not isinstance(requirements, list) or not requirements:
            lint.fail(
                EVENT_KIND_REGISTRY, f"{kind}.pre_state_requirements must be a non-empty array"
            )
            continue
        if row.get("reducer_input") is not True:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{kind} declares pre_state_requirements but is not a reducer_input Event kind",
            )
        for index, requirement in enumerate(requirements):
            where = f"{kind}.pre_state_requirements[{index}]"
            if not isinstance(requirement, dict):
                lint.fail(EVENT_KIND_REGISTRY, f"{where} must be an object")
                continue
            unknown = set(requirement) - {
                "result_family",
                "subject",
                "condition",
                "predicate",
                "failure",
            }
            if unknown:
                lint.fail(EVENT_KIND_REGISTRY, f"{where} has unknown member(s) {sorted(unknown)}")
            family = requirement.get("result_family")
            if family not in registered_families:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.result_family {family!r} is not a registered typed current "
                    "result family",
                )
            if "subject" in requirement:
                _check_result_selector(
                    lint,
                    f"{where}.subject",
                    requirement["subject"],
                    row.get("id_source"),
                    kind,
                )
            if "condition" in requirement:
                from .foundation import lint_cell_write_condition

                lint_cell_write_condition(
                    lint, EVENT_KIND_REGISTRY, f"{where}.condition", requirement["condition"]
                )
            predicate = requirement.get("predicate")
            if not isinstance(predicate, dict) or not isinstance(predicate.get("field"), str):
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.predicate must be an object naming a stored field",
                )
            elif predicate.get("kind") == "stored_field_present":
                if set(predicate) != {"kind", "field"}:
                    lint.fail(
                        EVENT_KIND_REGISTRY,
                        f"{where}.predicate stored_field_present takes exactly "
                        "{kind, field}",
                    )
            elif predicate.get("kind") in _PRE_STATE_PAYLOAD_PREDICATES:
                payload_field = predicate.get("payload_field")
                if set(predicate) != {"kind", "field", "payload_field"} or not (
                    isinstance(payload_field, str) and payload_field.startswith("payload.")
                ):
                    lint.fail(
                        EVENT_KIND_REGISTRY,
                        f"{where}.predicate {predicate['kind']} takes exactly "
                        "{kind, field, payload_field} with a payload.* field",
                    )
                else:
                    from .foundation import lint_field_path

                    lint_field_path(
                        lint,
                        EVENT_KIND_REGISTRY,
                        f"{where}.predicate.payload_field",
                        payload_field,
                    )
            else:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.predicate.kind must be one of {valid_predicates}",
                )
            failure = requirement.get("failure")
            if (
                not isinstance(failure, dict)
                or set(failure) != {"code", "reason_code"}
                or not isinstance(failure.get("code"), str)
                or not isinstance(failure.get("reason_code"), str)
            ):
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.failure must be exactly {{code, reason_code}}",
                )
            elif error_codes is not None and failure["code"] not in error_codes:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.failure.code {failure['code']!r} is not a registered error code",
                )


def check_partial_update_base_producers(lint: Lint) -> None:
    """A partial update needs a base value, and only a registered write supplies it.

    `zh/models/views.md` section 3.2 argues it in full and the argument is not
    about views: an update that lands on a typed current result nobody has
    written has no pre-state, the current-value contract forbids closing the gap
    with a registered `initial_value`, and `null` or an empty object MUST NOT be
    treated as implicit initialization. So the base has to come from a
    registered create or genesis write, and the first partial update MUST NOT
    become the object's definition by default.

    The gate was written for `apply_patch` and has been dead since the
    authority-commit clean break renamed `cell_writes[].cell_family` /
    `effect_projection` to `result_writes[].result_family` /
    `result_projection`. `apply_patch` is not in the v1 `result_projection`
    closed set at all -- views.md section 3.2 still requires it and the three
    patch kinds are still uncovered, which is its own open question -- but
    `merge` is the live partial update and the same sentence covers it verbatim.
    Both are checked here so the rule binds today and keeps binding if the patch
    vocabulary comes back.

    Keyed-set projections are deliberately not partial updates: a keyed set
    begins empty, `keyed_set_add` is its genesis, and a remove over the observed
    set (`zh/models/pins.md` section 3) needs no whole prior value. Requiring a
    `set` producer for `agent_key` would be demanding a base its own contract
    says it does not have.
    """
    registry = load_json(lint, EVENT_KIND_REGISTRY)
    rows = registry.get("event_kinds") if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        lint.fail(EVENT_KIND_REGISTRY, "event_kinds[] must be an array")
        return

    producers: dict[str, set[str]] = {}
    producer_shapes: dict[str, set[str]] = {}
    other_writers: dict[str, set[str]] = {}
    updaters: dict[str, set[str]] = {}
    updater_shapes: dict[str, set[str]] = {}
    writes_seen = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = row.get("event_kind")
        for write in row.get("result_writes") or []:
            if not isinstance(write, dict):
                continue
            writes_seen += 1
            family = write.get("result_family")
            if not isinstance(family, str):
                continue
            projection = write.get("result_projection")
            projection_kind = (
                projection.get("kind") if isinstance(projection, dict) else None
            )
            if projection_kind in _PARTIAL_UPDATE_PROJECTIONS:
                updaters.setdefault(family, set()).add(kind)
                updater_shapes.setdefault(family, set()).add(_selector_shape(write))
            elif _is_base_producer(projection):
                producers.setdefault(family, set()).add(kind)
                producer_shapes.setdefault(family, set()).add(_selector_shape(write))
            else:
                other_writers.setdefault(family, set()).add(kind)

    if not writes_seen:
        lint.fail(
            EVENT_KIND_REGISTRY,
            "check_partial_update_base_producers inspected no result_writes[] entry at all; "
            "the registry either lost its writes or spells the array under another key, and "
            "either way this gate's silence means nothing",
        )
        return

    unproduced = {family for family in updaters if not producers.get(family)}

    # decisions/0029 section 3.2: a producer has to be usable as this update's
    # base, not merely present. A producer that addresses a different selector
    # shape names a different object, so it supplies no base for this one.
    for family in sorted(set(updaters) - unproduced):
        if not updater_shapes[family] <= producer_shapes[family]:
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{family} is partially updated on selector shape(s) "
                f"{sorted(updater_shapes[family])} but its base-value producer(s) address "
                f"{sorted(producer_shapes[family])}; a base value has to be written to the same "
                "object the update addresses",
            )
    for family in sorted(unproduced & set(other_writers)):
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{family} has only writer(s) {sorted(other_writers[family])} beside its partial "
            "update(s); none of them writes a whole value, so none can be the base the update "
            "resolves against",
        )

    baseline = load_json(lint, PATCH_BASE_PRODUCER_BASELINE) or {}
    known = {
        entry.get("result_family")
        for entry in baseline.get("families_without_base_producer") or []
        if isinstance(entry, dict)
    }
    for family in sorted(unproduced - known):
        lint.fail(
            EVENT_KIND_REGISTRY,
            f"{family} is the target of partial update write(s) {sorted(updaters[family])} but no "
            "registered write produces a base value for it; an update has no pre-state and the "
            "current-value contract forbids closing the gap with a registered initial_value",
        )
    for family in sorted(known - unproduced):
        detail = (
            "now has a registered base-value producer"
            if family in updaters
            else "is no longer the target of any partial update write"
        )
        lint.fail(
            PATCH_BASE_PRODUCER_BASELINE,
            f"{family} {detail}; remove it from families_without_base_producer "
            "(the baseline only shrinks)",
        )


def check_result_family_write_agreement(lint: Lint) -> None:
    """All writers of one family must agree on the value schema they write.

    This is what survives of `check_concurrency_class_closure`, which required
    every writer of a family to share one `execution` / `state_model` /
    `value_shape` contract. The clean break removed all three members, so that
    gate compared three absent values on an absent array and said nothing; its
    only live rule was the retired-`concurrency_class` row guard, which now sits
    with the other removed-field guards in `check_registries`.

    The proposition still holds, and in v1 it has one spelling: a family has one
    value, so two rows that both name a `value_schema_ref` for it MUST name the
    same one. A row may still omit it -- a `transition` writes no projection
    members and has nothing to declare -- so this checks agreement among the
    rows that declare one, not presence.
    """
    registry = load_json(lint, EVENT_KIND_REGISTRY)
    rows = registry.get("event_kinds") if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        lint.fail(EVENT_KIND_REGISTRY, "event_kinds[] must be an array")
        return
    declared: dict[str, dict[str, set[str]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = row.get("event_kind")
        for write in row.get("result_writes") or []:
            if not isinstance(write, dict):
                continue
            family = write.get("result_family")
            ref = write.get("value_schema_ref")
            if isinstance(family, str) and isinstance(ref, str):
                declared.setdefault(family, {}).setdefault(ref, set()).add(kind)
    for family, refs in sorted(declared.items()):
        if len(refs) > 1:
            detail = "; ".join(
                f"{ref} ({', '.join(sorted(str(kind) for kind in kinds))})"
                for ref, kinds in sorted(refs.items())
            )
            lint.fail(
                EVENT_KIND_REGISTRY,
                f"{family} is written under {len(refs)} different value_schema_ref values, so its "
                f"writers do not agree on what the family's value is: {detail}",
            )


# zh/models/pins.md section 3: a keyed set's add and its remove are the two
# halves of one atomic re-key, so they are the one pair that may legally share a
# target inside a single Event.
_RESULT_SET_ADD_PROJECTIONS = frozenset({"keyed_set_add"})
_RESULT_SET_REMOVE_PROJECTIONS = frozenset(
    {"keyed_set_remove_observed", "keyed_set_remove_dots"}
)


def _result_target_key(write: dict) -> str:
    return json.dumps(
        [write.get("result_family"), write.get("result_selector")],
        sort_keys=True,
        ensure_ascii=False,
    )


def check_result_write_target_uniqueness(lint: Lint) -> None:
    """Two writes of one Event MUST NOT address the same typed current result.

    ``zh/models/event-and-patch.md`` section 2.4.2 lets one Event carry several
    ops of the same family only where the kind's closed contract registers them
    explicitly. Anything else is a duplicate target: two ops on one result are
    indistinguishable to a receiver, which is the same ambiguity the registry
    exists to remove.

    Two repeats are legal and both are provable from the row itself:

    * a keyed set's atomic remove-then-add. ``zh/identity/key-management.md``
      section 3.6.1 requires exactly that shape for Agent key re-authorization,
      and ``ak.agent.key.authorize`` is the live use;
    * a provably disjoint condition pair -- complementary presence tests, or
      unequal exact constants on one field. Anything weaker would be a guess,
      and a wrong guess means two writes racing on one result.

    The rule and its two exceptions were written for ``cell_writes[]`` and went
    down with it in the clean break; ``check_result_write_contracts`` closed the
    per-write grammar but says nothing about two rows agreeing on a target. The
    same-row coalesce agreement below has the same history.
    """
    registry = load_json(lint, EVENT_KIND_REGISTRY)
    rows = registry.get("event_kinds") if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        lint.fail(EVENT_KIND_REGISTRY, "event_kinds[] must be an array")
        return

    from .foundation import complementary_conditions

    writes_seen = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = row.get("event_kind")
        seen: dict[str, tuple[Any, Any]] = {}
        for index, write in enumerate(row.get("result_writes") or []):
            if not isinstance(write, dict):
                continue
            writes_seen += 1
            where = f"{kind}.result_writes[{index}]"
            projection = write.get("result_projection")
            projection_kind = (
                projection.get("kind") if isinstance(projection, dict) else None
            )
            condition = write.get("condition")

            # event-and-patch.md 2.4.2: when an `any_field_present` condition
            # selects the same alternative paths a `coalesce` selector derives
            # from, the two lists MUST agree item-for-item and in order. A
            # mismatch means the result can be required on a payload shape whose
            # key cannot be derived, or keyed on a shape where it must not be
            # written. The other legitimate use of `any_field_present` -- one
            # result carrying several distinct fields, addressed by an
            # unconditional selector -- is not constrained here.
            selector = write.get("result_selector")
            if (
                isinstance(condition, dict)
                and condition.get("kind") == "any_field_present"
                and isinstance(condition.get("fields"), list)
                and isinstance(selector, dict)
                and selector.get("kind") == "coalesce"
                and selector.get("fields") != condition["fields"]
            ):
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where}.condition.fields must equal the result_selector coalesce fields "
                    "item-for-item and in order, or the result can be required on a payload "
                    "shape whose key cannot be derived",
                )

            key = _result_target_key(write)
            previous = seen.get(key)
            if previous is not None:
                previous_kind, previous_condition = previous
                pair = {previous_kind, projection_kind}
                paired = bool(pair & _RESULT_SET_ADD_PROJECTIONS) and bool(
                    pair & _RESULT_SET_REMOVE_PROJECTIONS
                )
                if not paired and not complementary_conditions(
                    previous_condition, condition
                ):
                    lint.fail(
                        EVENT_KIND_REGISTRY,
                        f"{where} addresses the same (result_family, result_selector) as an "
                        "earlier write of this Event without being a keyed-set "
                        "remove-then-add pair or carrying a provably disjoint condition; two "
                        "ops on one result are indistinguishable to a receiver",
                    )
            seen[key] = (projection_kind, condition)

    if not writes_seen:
        lint.fail(
            EVENT_KIND_REGISTRY,
            "check_result_write_target_uniqueness inspected no result_writes[] entry at all; "
            "the registry either lost its writes or spells the array under another key, and "
            "either way this gate's silence means nothing",
        )


# `models/common-fields.md` section 5 names `state` as the one shared spelling
# for an object's current lifecycle state, so it is the registry's own
# vocabulary rather than a guess about field names.
AUTHOR_STATE_AXIS_MEMBER = "state"
VECTOR_REGISTRY = ARTIFACTS / "registry" / "vector-registry.json"


def _executed_vector_domains(lint: Lint) -> set[str]:
    """Domains of active vectors some fixture actually runs.

    A vector row on its own is a sentence in a registry. What makes it a check
    is a fixture naming it in `covers_vectors`, which is the link
    `ak.vector.view.terminal_state_patch.v1` did not have until
    `view-write-contract-fixture.json` was written -- it sat `active` and
    description-only while the write it describes could not even be registered.
    """

    registry = load_json(lint, VECTOR_REGISTRY)
    rows = registry.get("vectors") if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        lint.fail(VECTOR_REGISTRY, "vectors[] must be an array")
        return set()
    domain_of: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("status") != "active":
            continue
        vector_id = row.get("vector_id")
        domain = row.get("domain")
        if isinstance(vector_id, str) and isinstance(domain, str):
            domain_of[vector_id] = domain
    executed: set[str] = set()
    for path in sorted((ARTIFACTS / "fixtures").glob("*.json")):
        document = load_json(lint, path)
        if not isinstance(document, dict):
            continue
        for vector_id in document.get("covers_vectors") or []:
            if isinstance(vector_id, str) and vector_id in domain_of:
                executed.add(domain_of[vector_id])
    return executed


def _member_subschema(lint: Lint, reference: Any, member: str) -> dict | None:
    """The subschema a reference declares for one top-level member."""

    if not isinstance(reference, str) or not reference:
        return None
    seen: set[str] = set()

    def visit(file_ref: str, fragment: str) -> dict | None:
        key = f"{file_ref}#{fragment}"
        if key in seen:
            return None
        seen.add(key)
        path = ARTIFACTS / file_ref
        document = load_json(lint, path) if path.is_file() else None
        if document is None:
            return None
        try:
            node = resolve_json_pointer(document, fragment)
        except (KeyError, IndexError, ValueError):
            return None
        return descend(node, file_ref)

    def descend(node: Any, file_ref: str) -> dict | None:
        if not isinstance(node, dict):
            return None
        properties = node.get("properties")
        if isinstance(properties, dict) and isinstance(properties.get(member), dict):
            found = properties[member]
            inner = found.get("$ref")
            if isinstance(inner, str) and "enum" not in found:
                target_file, separator, body = inner.partition("#")
                target_file = target_file.lstrip("./") or file_ref
                if target_file and not target_file.startswith("schemas/"):
                    target_file = f"schemas/{target_file}"
                resolved = visit(target_file, f"#{body}" if separator else "")
                if isinstance(resolved, dict):
                    return resolved
            return found
        nested = node.get("$ref")
        if isinstance(nested, str):
            target_file, separator, body = nested.partition("#")
            target_file = target_file.lstrip("./") or file_ref
            if not target_file.startswith("schemas/"):
                target_file = f"schemas/{target_file}"
            found = visit(target_file, f"#{body}" if separator else "")
            if found is not None:
                return found
        for branch in node.get("allOf") or []:
            found = descend(branch, file_ref)
            if found is not None:
                return found
        return None

    file_ref, separator, body = reference.partition("#")
    return visit(file_ref, f"#{body}" if separator else "")


def check_author_writable_state_axis_contract(lint: Lint) -> None:
    """The third lifecycle carrier has to pay for itself.

    ``sync/current-results.md`` section 2.1 used to say a stored lifecycle axis
    had exactly two registered carriers, and that the choice between them
    followed from one field name: *every family whose payload carries
    ``expected_revision`` MUST take form 2, the rest take form 1*. Both halves
    were wrong against the registry they described.
    ``ak.moderation.decision.lift`` carries ``expected_revision`` and writes a
    keyed set -- neither form -- and ``view`` carries none while its ``state``
    is an author-written member inside ``allowed_paths``: a third carrier the
    binary said could not exist. Nothing failed, because no gate ever read the
    rule; the two carriers were prose, and prose that contradicts the registry
    loses silently.

    The corrected section registers that third carrier and prices it. An author
    writes the state directly, so the transition table is NOT closed by a
    machine artifact -- only the domain prose has it. Everything that keeps
    that affordable is checked here:

    * the value schema MUST close the state's value set, or the reducer has no
      registered vocabulary to refuse an unknown state against;
    * the write MUST register ``object_state_transition_time``, and the member
      it produces MUST be reducer-managed on this write's own target. Without
      it an author who can set ``state`` can also author *when* the transition
      happened, and the object's own audit trail becomes self-reported;
    * the family MUST NOT also appear in ``transition_contracts`` -- two state
      sources in one family is the one thing all three carriers forbid;
    * the domain MUST have an active vector some fixture actually executes,
      because the terminal state and the non-resurrection rule live in prose
      and a vector is the only thing that reads them back.
    """

    registry = load_json(lint, EVENT_KIND_REGISTRY)
    rows = registry.get("event_kinds") if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        lint.fail(EVENT_KIND_REGISTRY, "event_kinds[] must be an array")
        return
    transition_contracts = registry.get("transition_contracts")
    if not isinstance(transition_contracts, dict):
        transition_contracts = {}
    executed_domains = _executed_vector_domains(lint)

    carriers = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = row.get("event_kind")
        category = row.get("category")
        for index, write in enumerate(row.get("result_writes") or []):
            if not isinstance(write, dict):
                continue
            projection = write.get("result_projection")
            if not isinstance(projection, dict) or projection.get("kind") != "apply_patch":
                continue
            allowed_paths = projection.get("allowed_paths")
            if not isinstance(allowed_paths, list):
                continue
            if AUTHOR_STATE_AXIS_MEMBER not in allowed_paths:
                continue

            carriers += 1
            where = f"{kind}.result_writes[{index}]"
            family = write.get("result_family")

            if family in transition_contracts:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where} lets the author patch {AUTHOR_STATE_AXIS_MEMBER!r} while "
                    f"transition_contracts.{family} also declares a machine for it; a family has "
                    "exactly one state source (sync/current-results.md section 2.1)",
                )

            state_schema = _member_subschema(
                lint, write.get("value_schema_ref"), AUTHOR_STATE_AXIS_MEMBER
            )
            enum_values = state_schema.get("enum") if isinstance(state_schema, dict) else None
            if not isinstance(enum_values, list) or not enum_values:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where} lets the author patch {AUTHOR_STATE_AXIS_MEMBER!r}, so "
                    f"{write.get('value_schema_ref')!r} MUST close that member with an enum: the "
                    "author-writable carrier has no transition table, so the value set is the only "
                    "registered thing an unknown state can be refused against",
                )

            transition_time_members = {
                member.get("name")
                for member in write.get("derived_members") or []
                if isinstance(member, dict)
                and member.get("derivation") == "object_state_transition_time"
                and isinstance(member.get("name"), str)
            }
            if not transition_time_members:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where} lets the author patch {AUTHOR_STATE_AXIS_MEMBER!r} but registers no "
                    "object_state_transition_time derived member; an author who writes the state "
                    "would also be writing when the transition happened",
                )
                continue

            forbidden = _effective_forbidden_paths(lint, where, write, kind)
            if forbidden is not None:
                for member_name in sorted(transition_time_members):
                    if member_name in allowed_paths or not _names_a_forbidden_path(
                        member_name, forbidden
                    ):
                        lint.fail(
                            EVENT_KIND_REGISTRY,
                            f"{where} derives {member_name!r} from the transition but the member is "
                            "not reducer-managed on this write's own target; a derivation an author "
                            "may also patch is a default, not a rule",
                        )

            if not isinstance(category, str) or category not in executed_domains:
                lint.fail(
                    EVENT_KIND_REGISTRY,
                    f"{where} takes the author-writable state carrier, whose terminal states and "
                    f"non-resurrection rule live only in prose, but domain {category!r} has no "
                    "active vector that any fixture executes via covers_vectors",
                )

    if carriers == 0:
        lint.fail(
            EVENT_KIND_REGISTRY,
            "no registered write lets an author patch a lifecycle state, so this gate reported "
            "success over nothing; sync/current-results.md section 2.1 registers the carrier and "
            "ak.view.update is its one v1 use -- if that write is gone, the section goes with it",
        )
