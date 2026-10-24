"""Execute own-account peer Watch contract, presence and delivery vectors."""

from __future__ import annotations

import copy
import json

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .core import ARTIFACTS, Lint, load_json

CONTRACT = ARTIFACTS / "registry/contract-registry.json"
FIXTURE = ARTIFACTS / "fixtures/strand-watch-current-read-fixture.json"
PEER = "ak.peer.strand.watch.read.current.v1"
SELF = "ak.self.strand.watch.read.current.v1"
REQUIRED_CASES = {
    "cross_station_never_written_without_local_tenure",
    "cross_station_current_clear_without_local_row",
    "handoff_nonzero_generation_proven_never_written",
    "generation_zero_alone_does_not_prove_absence",
    "snapshot_omission_does_not_prove_never_written",
    "missing_handoff_import_fails_closed",
    "others_author_write_prevents_never_written",
    "handoff_omitted_clear_row_fails_closed",
    "same_principal_other_station_is_private_cell",
    "authorized_circle_self_read",
    "parent_membership_cannot_read_hidden_circle",
    "session_revoked_before_delivery_withholds",
    "device_replaced_before_delivery_withholds",
    "agent_content_gate_cannot_be_bypassed",
    "known_membership_loss_before_delivery_withholds",
    "handoff_late_response_is_discarded",
    "wrong_response_realm_rejected",
    "wrong_response_selector_rejected",
    "wrong_response_generation_rejected",
    "wrong_response_stream_rejected",
    "wrong_response_revision_rejected",
}


def evaluate_read(value: dict) -> str:
    """Abstract evidence oracle; no cryptographic or production-store claim."""
    if not value["authenticated_peer"]:
        return "authentication_rejected"
    request = value["request"]
    actor = request["watcher_actor_id"]
    if actor["kind"] != "account" or actor["account_id"]["station_id"] != value["source_service_id"]:
        return "not_found"
    if not value["readable_realm"] or not value["readable_scope"]:
        return "not_found"
    if (
        not value["current_authority_verified"]
        or value["destination_service_id"] != value["current_governor"]
        or not all(value[key] for key in (
            "head_confirmed", "namespace_complete", "materialization_complete", "handoff_import_complete",
        ))
    ):
        return "revision_unavailable"
    written = any(
        row["watcher_actor_id"] == actor and row["strand_id"] == request["strand_id"]
        for row in value["accepted_writes"]
    )
    row = value["durable_row"]
    if written != (row is not None):
        return "revision_unavailable"
    status = "current" if row is not None else "never_written"
    response = value["response"]
    selector = response.get("selector") if response.get("status") == "never_written" else response.get("current_state", {}).get("selector")
    wanted_selector = {"kind": "strand_watch", "strand_id": request["strand_id"], "watcher_actor_id": actor}
    if (
        response.get("realm_id") != request["realm_id"]
        or int(response.get("governance_generation", "-1")) != value["generation"]
        or response.get("status") != status
        or selector != wanted_selector
        or response.get("stream_head") != value["confirmed_head"]
        or value["confirmed_head"]["stream_ref"] != value["scope_stream_ref"]
    ):
        return "revision_unavailable"
    if row is not None:
        result = response.get("current_state", {})
        revision = result.get("revision", {})
        head = value["confirmed_head"]
        if (
            result != row
            or result.get("source_stream_ref") != head["stream_ref"]
            or revision.get("stream_position", -1) > head["stream_position"]
            or (revision.get("stream_position") == head["stream_position"] and revision.get("commit_id") != head["commit_id"])
        ):
            return "revision_unavailable"
    if value["higher_generation_observed"]:
        return "revision_unavailable"
    if not all(value[key] for key in ("session_current", "device_current", "account_delivery_authorized")) or value["known_authority_loss"]:
        return "delivery_rejected"
    return status


def evaluate_cas(value: dict) -> str:
    if value["has_current"] != value["expected_present"]:
        return "failed_precondition"
    if value["has_current"] and value["current_value"] != value["expected_value"]:
        return "failed_precondition"
    return "accepted"


def case_input(fixture: dict, case: dict) -> dict:
    value = copy.deepcopy(fixture["cross_station_basis"])
    value.update(copy.deepcopy(case["input"]))
    return value


def contract_errors(catalog: dict, fixture: dict) -> list[str]:
    errors = []
    operations = {row["operation_id"]: row for row in catalog["operation_registry"]["operations"]}
    peer = operations.get(PEER, {})
    own = operations[SELF]
    if peer.get("http") != "POST /_arkret/peer/strands/watch/current":
        errors.append("Missing dedicated peer Watch current operation")
    for field in ("request_schema_ref", "response_schema_ref", "max_canonical_body_bytes"):
        if peer.get(field) != own[field]:
            errors.append("Peer/self shared closed DTO or budget drift: " + field)
    signature = peer.get("auth_requirements", {}).get("service_signature", {})
    if signature.get("signature_scenario_id") != "ak.http_signature.scenario.service_to_service.v1" or signature.get("bearer_only_allowed") is not False:
        errors.append("Peer Watch current requires the canonical S2S signature")
    if peer.get("durable_effect", {}).get("kind") != "none":
        errors.append("Peer Watch read must have no durable Event effect")
    if fixture.get("cross_station_operation_id") != PEER:
        errors.append("Fixture must bind the exact peer Watch operation")
    cases = fixture.get("cross_station_cases", [])
    names = [case["name"] for case in cases]
    if len(names) != len(set(names)) or not REQUIRED_CASES.issubset(names):
        errors.append("Cross-Station Watch required vector coverage is incomplete or duplicated")
    for case in cases:
        if evaluate_read(case_input(fixture, case)) != case["expected"]:
            errors.append("Cross-Station Watch verdict drift: " + case["name"])
    for case in fixture.get("submit_cas_cases", []):
        if evaluate_cas(case) != case["expected"]:
            errors.append("Watch whole-value CAS verdict drift: " + case["name"])
    cas_names = {case["name"] for case in fixture.get("submit_cas_cases", [])}
    if not {"written_clear_omission_rejected", "whole_public_flag_mismatch_rejected", "read_then_concurrent_write_rejected_at_submit"}.issubset(cas_names):
        errors.append("Watch submit-time CAS vector coverage is incomplete")
    return errors


def check_peer_watch_current(lint: Lint) -> None:
    catalog = load_json(lint, CONTRACT)
    fixture = load_json(lint, FIXTURE)
    for error in contract_errors(catalog, fixture):
        lint.fail(FIXTURE, error)
    resources = []
    for path in (ARTIFACTS / "schemas").glob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        resource = Resource.from_contents(schema, default_specification=DRAFT202012)
        resources.append((path.as_uri(), resource))
        if "$id" in schema:
            resources.append((schema["$id"], resource))
    registry = Registry().with_resources(resources)
    cases = fixture.get("schema_validation_cases", [])
    if len(cases) < 14:
        lint.fail(FIXTURE, "Watch wire schema cases missing")
    for case in cases:
        file, fragment = case["schema_ref"].split("#")
        schema = json.loads((ARTIFACTS / file).read_text(encoding="utf-8"))
        validator = Draft202012Validator({"$ref": schema["$id"] + "#" + fragment}, registry=registry)
        if (not list(validator.iter_errors(case["instance"]))) != case["expect_valid"]:
            lint.fail(FIXTURE, "Watch wire schema verdict drift: " + case["name"])
