"""Artifact checks and a CAS/replay reference model, not production acceptance."""

import copy
import json

from .core import ARTIFACTS, load_json

SCOPES = ["invite", "voice_call", "video_call", "presence"]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def valid_permissions(value):
    scopes = [entry.get("consent_scope") for entry in value]
    return (all(scope in SCOPES for scope in scopes) and len(set(scopes)) == len(scopes)
            and scopes == sorted(scopes, key=SCOPES.index))


def mimi_diff(before, after, scope, decision):
    """Compare complete signed values without filling, filtering or merging."""
    if scope not in SCOPES or not valid_permissions(before) or not valid_permissions(after):
        return False
    left = {entry["consent_scope"]: entry for entry in before}
    right = {entry["consent_scope"]: entry for entry in after}
    if canonical({k: v for k, v in left.items() if k != scope}) != canonical(
            {k: v for k, v in right.items() if k != scope}):
        return False
    if decision == "accept":
        return scope in right
    return decision in {"deny", "revoke"} and scope in left and scope not in right


class ConsentModel:
    """Authority validation is an input gate; real SQL/signatures are not modeled."""

    def __init__(self):
        self.current, self.accepted, self.position = {}, {}, 0

    def submit(self, event_id, payload, *, authorized=True, correlation=None):
        if not authorized:
            return "denied", None
        identity = canonical(payload)
        if event_id in self.accepted:
            old_identity, old_correlation, result = self.accepted[event_id]
            return ("replay", copy.deepcopy(result)) if (identity, correlation) == (
                old_identity, old_correlation) else ("conflict", None)
        peer = canonical(payload["peer"])
        old = self.current.get(peer)
        expected = {"state": "never_written"} if old is None else {
            "state": "present", "revision": old["revision"]}
        if payload["expected_current"] != expected:
            return "stale", None
        if not valid_permissions(payload["permissions"]):
            return "invalid", None
        if correlation is not None and (canonical(correlation["peer"]) != peer or not mimi_diff(
                [] if old is None else old["permissions"], payload["permissions"],
                correlation["scope"], correlation["decision"])):
            return "not_found", None
        self.position += 1
        result = {"revision": {"commit_id": event_id, "stream_position": self.position},
                  "permissions": copy.deepcopy(payload["permissions"])}
        self.current[peer] = result
        self.accepted[event_id] = (identity, copy.deepcopy(correlation), copy.deepcopy(result))
        return "accepted", copy.deepcopy(result)


def contract_errors(contract, operations, typed):
    errors = []
    events = contract["event_kind_registry"]["event_kinds"]
    kinds = {row["event_kind"] for row in events}
    if {"ak.consent.grant", "ak.consent.revoke"} & kinds or "ak.consent.replace" not in kinds:
        errors.append("Consent must have one replace writer")
    writers = [write for row in events for write in row.get("result_writes", [])
               if write["result_family"] == "consent"]
    if len(writers) != 1 or writers[0]["result_selector"] != {
            "kind": "composite", "components": [{"kind": "canonical_json", "field": "payload.peer.actor_id"}]}:
        errors.append("Consent selector must be one canonical exact ActorId in holder PCR")
    if set(typed["$defs"]["consent_value"]["properties"]) != {"permissions"}:
        errors.append("Consent value must be the whole permission set")
    if set(operations["$defs"]["consent_view"]["required"]) != {
            "peer", "permission_scopes", "updated_at", "revision"}:
        errors.append("Consent summary must keep exact peer and revision without stable ID/status")
    request = operations["$defs"]["consent_current_read_request_body"]
    if "consent_scope" in request["properties"]:
        errors.append("Consent editing read cannot filter scope")
    branches = operations["$defs"]["consent_current_read_outcome"]["properties"].get("current", {}).get("oneOf", [])
    if [x.get("properties", {}).get("state", {}).get("const") for x in branches] != ["present", "never_written"]:
        errors.append("Consent read must distinguish complete present from never_written")
    elif branches[0]["properties"].get("result", {}).get("$ref") != "./typed-current-result.schema.json#/$defs/consent_result":
        errors.append("Present read must supply the full typed current")
    bound = next(row for row in events if row["event_kind"] == "ak.direct_conversation.bound")
    projection = {"kind": "set", "value_projection": {"kind": "object", "members": [
        {"name": "binding_event_ref", "envelope_field": "event_id"}, {"name": "binding", "field": "payload"}]}}
    if len(bound["result_writes"]) != 1 or bound["result_writes"][0]["result_projection"] != projection:
        errors.append("Binding must store one original Event ref and exact payload")
    if set(typed["$defs"]["direct_conversation_binding_value"]["required"]) != {"binding_event_ref", "binding"}:
        errors.append("Binding cannot retain endorsement collections")
    guard = contract["event_kind_registry"].get("direct_conversation_binding_contract", {})
    if (guard.get("first_write_predicate") != "never_written" or guard.get("replacement_allowed") is not False
            or guard.get("source_ref") != "enclosing_bound_event_id"
            or guard.get("reset_on_withdrawal_leaf_removal_restart_or_handoff") is not False):
        errors.append("Binding must be write-once with permanent bootstrap exit")
    op_ids = {row["operation_id"] for row in contract["operation_registry"]["operations"]}
    if "ak.self.messages.command.prepare.v1" in op_ids:
        errors.append("Ordinary message prepare is retired")
    message = contract.get("message_authoring_contract", {})
    for supply in message.get("input_supply", []):
        if not set(supply.get("source_operations", [])) <= op_ids:
            errors.append("Local authoring supply names an unregistered read")
    if len(message.get("input_supply", [])) != 5:
        errors.append("Local authoring must close all five input groups")
    branches = message.get("branches", [])
    if {row.get("kind") for row in branches} != {
            "realm_default", "circle", "sidecar", "direct_participant", "direct_provisional_founder", "delegated_or_agent"}:
        errors.append("Local authoring must cover every registered message branch")
    for branch in branches:
        if not set(branch.get("source_operations", [])) <= op_ids:
            errors.append("Message branch supply names an unregistered operation")
    if contract.get("consent_current_contract", {}).get("permission_scopes") != SCOPES:
        errors.append("Consent scopes must be concrete and closed")
    return errors


def check_protocol_simplification(lint):
    path = ARTIFACTS / "registry/contract-registry.json"
    for error in contract_errors(load_json(lint, path), load_json(lint, ARTIFACTS / "schemas/consent-operations.schema.json"),
                                 load_json(lint, ARTIFACTS / "schemas/typed-current-result.schema.json")):
        lint.fail(path, error)
