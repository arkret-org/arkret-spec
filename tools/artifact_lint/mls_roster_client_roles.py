"""Pin the roster role split and execute original signature/key binding vectors."""

from __future__ import annotations

import base64
import copy
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .core import ARTIFACTS, Lint, load_json


def signing_bytes(value: dict, domain: str) -> bytes:
    unsigned = {key: item for key, item in value.items() if key != "signature"}
    return domain.encode() + json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def verify_signature(value: dict, key: dict, domain: str) -> bool:
    if value["signature"]["kid"] != key["verification_method"]:
        return False
    try:
        public = base64.urlsafe_b64decode(key["public_key_b64u"] + "=")
        signature = base64.urlsafe_b64decode(value["signature"]["sig"] + "==")
        Ed25519PublicKey.from_public_bytes(public).verify(signature, signing_bytes(value, domain))
        return True
    except (InvalidSignature, ValueError):
        return False


def check_mls_roster_client_roles(lint: Lint) -> None:
    path = ARTIFACTS / "registry/contract-registry.json"
    contract = load_json(lint, path)
    boundary = contract["did_evidence_boundary_registry"]
    rules = boundary.get("mls_roster_verification_contract", {})
    roles = rules.get("roles", {})
    client = roles.get("ordinary_client", {})
    if client.get("method_history_verifier") is not False or client.get("live_did_discovery") is not False:
        lint.fail(path, "ordinary MLS client must have neither method history nor live discovery")
    required = {"recipient_claim_receipt_signature", "recipient_add_attestation_signature", "rfc9420_credential_leaf_and_proposal_binding"}
    if not required <= set(client.get("checks", [])):
        lint.fail(path, "ordinary client must independently verify both original signatures and RFC leaf")
    for role in ("account_station", "governance_station", "independent_auditor"):
        if roles.get(role, {}).get("method_history_verifier") is not True:
            lint.fail(path, f"{role} must verify native historical authority")
    for name in ("self_result_portable", "network_from_retained_commit_signer", "historical_closure_is_current_route"):
        if rules.get(name) is not False:
            lint.fail(path, f"roster boundary cannot enable {name}")
    retained = next((row for row in boundary["boundaries"] if row["boundary_id"] == "mls_roster_retained_attestor_history"), {})
    if retained.get("route_evidence") != "authorized inline frozen closure only; no network request":
        lint.fail(path, "retained roster closure must not authorize network discovery")
    operations = {row["operation_id"]: row for row in contract["operation_registry"]["operations"]}
    for surface, definition in (("self", "self_roster_read_outcome"), ("peer", "roster_read_outcome")):
        operation = operations[f"ak.{surface}.mls.read.roster_authority.v1"]
        if operation["response_schema_ref"] != f"schemas/mls-roster-authority.schema.json#/$defs/{definition}":
            lint.fail(path, f"{surface} roster carrier must retain its role boundary")
    selector = rules.get("member_selector", {})
    if selector.get("genesis_source") != "own_station_same_authorized_cut_immutable_accepted_provenance" or selector.get("requires_client_prejoin_genesis_or_complete_current_baseline") is not False:
        lint.fail(path, "member roster must authorize before deriving immutable Genesis without a client baseline")
    for surface, definition in (("self", "member_roster_read_request"), ("peer", "roster_read_request")):
        if operations[f"ak.{surface}.mls.read.roster_authority.v1"]["request_schema_ref"] != f"schemas/mls-roster-authority.schema.json#/$defs/{definition}":
            lint.fail(path, f"{surface} roster selector must retain its role boundary")
    profile_path = ARTIFACTS / "profiles/conformance-profiles.json"
    profiles = load_json(lint, profile_path)["profile_requirements"]
    for profile, role in (("full_client", "ordinary_client"), ("e2ee_client", "ordinary_client"), ("station", "account_station")):
        row = profiles[f"ak.profile.{profile}.v1"]
        if row.get("mls_roster_verification") != roles.get(role):
            lint.fail(profile_path, f"{profile} must match canonical roster responsibilities")
        if "ak.vector.mls.roster_client_roles.v1" not in row.get("required_vectors", []):
            lint.fail(profile_path, f"{profile} must require roster role vectors")
    schema_path = ARTIFACTS / "schemas/mls-roster-authority.schema.json"
    definitions = load_json(lint, schema_path)["$defs"]
    for name, fields in (
        ("member_roster_read_request", ["realm_id", "effective_scope", "mls_group_id", "target_commit_event_ref", "target_epoch", "caller_actor_id", "cursor"]),
        ("self_roster_read_outcome", ["roster", "manifest_signing_key", "add_signing_keys"]),
        ("roster_add_signing_keys", ["record_digest", "claim_receipt_signing_key", "attestation_signing_key"]),
        ("roster_signing_key", ["verification_method", "public_key_b64u"]),
    ):
        row = definitions.get(name, {})
        if row.get("required") != [field for field in fields if field != "cursor"] or list(row.get("properties", {})) != fields or row.get("additionalProperties") is not False:
            lint.fail(schema_path, f"{name} must retain its exact closed required key bindings")
    fixture_path = ARTIFACTS / "fixtures/mls-roster-client-roles-fixture.json"
    fixture = load_json(lint, fixture_path)
    required_cases = {
        "legal_cross_station_no_client_history", "original_times_key_rotation", "wrong_station_core",
        "wrong_service_role", "truncated_or_tampered_native_history", "unknown_method_version",
        "historically_revoked_assertion_method", "retained_commit_signer_discovery_without_source",
        "inline_history_as_current_endpoint", "remote_self_shaped_keys", "boolean_only_result",
        "ordinary_profile_forced_native_verifier", "original_double_signature_missing",
        "leaf_credential_or_proposal_mismatch", "self_projection_over_response_limit",
        "missing_registered_governance_locator",
    }
    names = {row["name"] for row in fixture["cases"]}
    if not required_cases <= names:
        lint.fail(fixture_path, "required native/role/network/MLS named-suite cases missing")
    kat = fixture["signature_binding_kat"]
    for object_name, key_name, domain in (
        ("claim_receipt", "claim_receipt_signing_key", "ak.peer-keypackage-claim-receipt-v1\n"),
        ("attestation", "attestation_signing_key", "ak.mls_add_authority_attestation.v1\n"),
    ):
        value, key = kat[object_name], kat[key_name]
        if not verify_signature(value, key, domain):
            lint.fail(fixture_path, f"{object_name} original signature KAT failed")
        wrong = copy.deepcopy(key)
        other = "attestation_signing_key" if key_name == "claim_receipt_signing_key" else "claim_receipt_signing_key"
        wrong["public_key_b64u"] = kat[other]["public_key_b64u"]
        if verify_signature(value, wrong, domain):
            lint.fail(fixture_path, f"{object_name} wrongly accepts the other historical key")
        tampered = copy.deepcopy(value)
        tampered["claimed_at" if object_name == "claim_receipt" else "attested_at"] = "2026-09-29T00:00:01.000Z"
        if verify_signature(tampered, key, domain):
            lint.fail(fixture_path, f"{object_name} wrongly accepts tampered signed time")
        wrong["verification_method"] = "did:web:other.example#key1"
        if verify_signature(value, wrong, domain):
            lint.fail(fixture_path, f"{object_name} wrongly accepts another key selector")
