"""Positive semantic roles and exact-owner enum authorities for v1 names."""
from __future__ import annotations

import re
from typing import Any

from .core import ARTIFACTS, ROOT, Lint, load_json, load_yaml, resolve_json_pointer
from .naming import enumerate_schema_nodes, enumerate_schema_properties

ROLE_TAILS = {
    "request_body": "request_body", "response_body": "response_body",
    "decision": "decision", "verdict": "verdict", "key_resolution": "resolution",
    "page": "page", "set": "set", "snapshot": "snapshot",
    "status_view": "view", "view": "view", "parameters": "parameters",
    "shared_fields": "fields", "problem_extensions": "problem_extensions",
    "attempt_outcome": "outcome", "terminal_outcome": "outcome",
    "planned_event": "planned_event", "status_record": "record",
}
MEMBER_PATTERNS = {
    "count": r"(?:[a-z][a-z0-9_]*_)?count(?:_per_[a-z][a-z0-9_]*)?",
    "instant": r"[a-z][a-z0-9_]*_at",
    "permission": r"[a-z][a-z0-9_]*_allowed",
    "obligation": r"[a-z][a-z0-9_]*_required",
    "url": r"[a-z][a-z0-9_]*_url",
    "binary_encoding": r"[a-z][a-z0-9_]*_base64(?:url)?",
}
SNAKE = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*\Z")
NAMESPACED = re.compile(r"ak\.[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*\Z")
NONTERMINAL = {"pending", "prepared", "preparing", "unknown", "in_progress", "running"}


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def type_role_errors(name: str, node: dict) -> list[str]:
    role = node.get("x-arkret-name-role")
    normalized = snake(name) if name[:1].isupper() else name
    errors = []
    if normalized == "result" or normalized.endswith("_result"):
        errors.append("Result is not a semantic protocol role")
    if normalized == "row" or normalized.endswith("_row") or role == "row":
        errors.append("Row is not a public protocol role; use the actual domain role")
    if role == "current_state" and not normalized.startswith("current_"):
        errors.append("current state type must retain the Current<Family> prefix")
    if role in ROLE_TAILS and not normalized.endswith(ROLE_TAILS[role]):
        errors.append(f"{role} type must end {ROLE_TAILS[role]}")
    if normalized.endswith("_outcome"):
        if role not in {"terminal_outcome", "attempt_outcome"}:
            errors.append("Outcome requires an explicitly scoped settled processing role")
        if not node.get("x-arkret-outcome-scope"):
            errors.append("Outcome requires a nonempty processing scope")
        for _pointer, child in enumerate_schema_nodes("role", node):
            if isinstance(child, dict) and any(isinstance(value, str) and value in NONTERMINAL
                                             for value in child.get("enum", [child.get("const")])):
                errors.append("Outcome admits an unsettled status")
    props = node.get("properties", {})
    if normalized.endswith("_page"):
        if not any(k in props for k in ("next_cursor", "continuation", "next_after", "has_more")):
            errors.append("Page requires a continuation contract")
    if normalized.endswith("_list") and any(k in props for k in ("next_cursor", "next_after", "has_more")):
        errors.append("List cannot carry a page continuation")
    if normalized.endswith("_set") and node.get("type") == "array":
        if node.get("uniqueItems") is not True or not node.get("x-arkret-canonical-order"):
            errors.append("Set requires uniqueness and a canonical ordering contract")
    return errors


def member_role_errors(name: str, node: dict) -> list[str]:
    if not isinstance(node,dict):
        return []
    role = node.get("x-arkret-member-role")
    pattern = MEMBER_PATTERNS.get(role)
    if pattern and not re.fullmatch(pattern, name):
        return [f"{role} member violates its positive name grammar"]
    if role in ("permission", "obligation") and node.get("type") != "boolean":
        return [f"{role} member must be boolean"]
    return []


def canonical_body_alias_errors(name: str, node: dict) -> list[str]:
    annotations = {'title', 'description', '$comment', 'x-arkret-name-role'}
    def transparent_reference(shape):
        assertions = {key: value for key, value in shape.items() if key not in annotations}
        if set(assertions) == {'$ref'}:
            return isinstance(assertions['$ref'], str)
        for operator in ('allOf', 'anyOf', 'oneOf'):
            branches = assertions.get(operator)
            if set(assertions) == {operator} and isinstance(branches, list) and len(branches) == 1 and isinstance(branches[0], dict):
                return transparent_reference(branches[0])
        return False
    normalized = snake(name) if name[:1].isupper() else name
    if normalized.endswith(('_request_body', '_response_body')) and transparent_reference(node):
        return ['use the canonical referenced type directly instead of a duplicate Body alias']
    return []


def enum_errors(node: dict, owner: str | None = None) -> list[str]:
    values = node.get("enum", [node["const"]] if "const" in node else [])
    if not values:
        return []
    metadata = node.get("x-arkret-value-ownership")
    if not isinstance(metadata, dict) or set(metadata) != {"class", "authority", "values", "owner"}:
        return ["every enum/const requires exact-owner value classification and authority"]
    if owner is not None and metadata['owner'] != owner:
        return ["enum authority cannot propagate to a different owner"]
    if metadata["values"] != values:
        return ["enum authority is stale or expanded beyond its exact registered values"]
    kind, authority = metadata["class"], metadata["authority"]
    if not isinstance(authority, str) or not authority:
        return ["enum authority is empty"]
    if kind == "owned_symbol" and any(v is not None and (not isinstance(v,str) or not SNAKE.fullmatch(v)) for v in values):
        return ["Arkret symbolic values must use snake_case"]
    if kind == "namespaced_symbol" and any(v is not None and (not isinstance(v,str) or not NAMESPACED.fullmatch(v)) for v in values):
        return ["Arkret namespaced symbols violate their registered grammar"]
    if kind == "numeric" and any(not isinstance(v,(int,float,bool)) and v is not None for v in values):
        return ["numeric literals must preserve their scalar type"]
    if kind == "external_literal" and not re.fullmatch(r"https://[^\s#]+#\S+", authority):
        return ["external enum authority must be an exact HTTPS section anchor"]
    if kind == 'symbol_or_media_type' and any(v is not None and (not isinstance(v,str) or not (SNAKE.fullmatch(v) or NAMESPACED.fullmatch(v) or re.fullmatch(r'[a-z][a-z0-9.+-]*/[^\s]+',v))) for v in values):
        return ['typed token union admits an unclassified literal']
    if kind not in {"owned_symbol","namespaced_symbol","numeric","decimal_text","version_text","uri","media_type","external_literal","human_text","selector_grammar","structured_literal","symbol_or_media_type"}:
        return ["unknown enum ownership class"]
    return []


def capture_member_reference_errors(text: str) -> list[str]:
    errors = []
    for legacy in ('recording_transition.result', 'transcript_transition.result',
                   'payload.result', 'result.retention'):
        if legacy in text:
            errors.append(f'capture member reference uses retired path {legacy}')
    if 'outcome="blocked_by_legal_hold"' in text:
        errors.append('deletion audit records a lifecycle status, not an Outcome')
    return errors


def retired_contract_reference_errors(text: str) -> list[str]:
    replacements = {'MlsGroupCurrent': 'MlsGroupValue', 'TypedCurrentRow': 'CurrentState',
                    'AccountCurrentView': 'AccountStateView'}
    replacements.update({'MorphRow': 'MorphView', 'SpaceRow': 'SpaceView', 'StrandRow': 'StrandView', 'RealmListRow': 'AccountRealmView', 'ContactListRow': 'ContactView', 'RealmOrganizationRelationshipRow': 'RealmOrganizationRelationshipView', 'EffectiveCapabilityGrantRow': 'EffectiveCapabilityGrantView', 'RealmStreamRow': 'RealmStreamView', 'AccountDataRow': 'AccountDataEntry', 'DeviceMessageDeliveredRow': 'DeviceMessageDeliveredEntry', 'DeviceMessageUnknownRow': 'DeviceMessageUnknownEntry', 'CalendarScheduleSourceExactRow': 'CurrentCalendarScheduleSource', 'MimiRoomBindingCurrentRow': 'CurrentMimiRoomBinding', 'WebvhWitnessRow': 'WebvhWitnessIdentity', 'realm_list_row': 'account_realm_view', 'contact_list_row': 'contact_view', 'realm_organization_relationship_row': 'realm_organization_relationship_view', 'realm_stream_row': 'realm_stream_view', 'pending_sidecar_access_reconciliation_row': 'pending_sidecar_access_reconciliation', 'rejected_event_row': 'applet_event_rejection', 'rejected_scope_row': 'applet_scope_rejection', 'stream_row': 'CommittedEventView'})
    return [f'retired contract reference {old}; use {new}' for old, new in replacements.items()
            if re.search(r'\b' + old + r'\b', text)]


def check_semantic_naming(lint: Lint) -> None:
    text_paths = sorted((ROOT / 'spec/v1/zh').rglob('*.md'))
    text_paths += sorted(ARTIFACTS.rglob('*.json'))
    for path in text_paths:
        for error in retired_contract_reference_errors(path.read_text(encoding='utf-8')):
            lint.fail(path, error)
    for relative in ('crypto-media/call-state.md', 'crypto-media/bindings/livekit.md'):
        path = ROOT / 'spec/v1/zh' / relative
        for error in capture_member_reference_errors(path.read_text(encoding='utf-8')):
            lint.fail(path, error)
    paths = sorted((ARTIFACTS / "schemas").glob("*.json"))
    paths += sorted((ARTIFACTS / "openapi").glob("*.yaml"))
    for path in paths:
        document = load_yaml(lint,path) if path.suffix == ".yaml" else load_json(lint,path)
        if not isinstance(document,dict):
            continue
        def role_shape(node, seen=None, context_path=path, context_document=document):
            seen = set() if seen is None else seen
            reference = node.get("$ref")
            if not isinstance(reference, str) or reference in seen:
                return node
            seen.add(reference)
            file_name, _, fragment = reference.partition("#")
            if file_name.startswith("https://arkret.org/v1/schemas/"):
                target_path = ARTIFACTS / "schemas" / file_name.rsplit("/", 1)[-1]
            else:
                target_path = (context_path.parent / file_name).resolve() if file_name else context_path
            if not target_path.resolve().is_relative_to(ARTIFACTS.resolve()):
                return node
            target_document = context_document if target_path == context_path else load_json(lint, target_path)
            target = target_document
            if not isinstance(target, dict):
                return node
            try:
                target = resolve_json_pointer(target, "#" + fragment)
            except (KeyError, IndexError, TypeError, ValueError):
                lint.fail(path, f"semantic role reference does not resolve: {reference}")
                return node
            if not isinstance(target, dict):
                return node
            resolved = role_shape(target, seen, target_path, target_document)
            return {**{key: value for key, value in resolved.items() if key != "x-arkret-name-role"},
                    **{key: value for key, value in node.items() if key != "$ref"}}
        for pointer,node in enumerate_schema_nodes(path.name,document):
            if not isinstance(node,dict):
                continue
            if "/$defs/" in pointer and pointer.rsplit("/$defs/",1)[-1].count("/") == 0:
                for error in type_role_errors(pointer.rsplit("/",1)[-1],role_shape(node)):
                    lint.fail(path,f"{pointer}: {error}")
                for error in canonical_body_alias_errors(pointer.rsplit('/', 1)[-1], node):
                    lint.fail(path, f'{pointer}: {error}')
            if pointer.startswith("/components/schemas/") and pointer.count("/") == 3:
                for error in type_role_errors(pointer.rsplit("/",1)[-1],role_shape(node)):
                    lint.fail(path,f"{pointer}: {error}")
            for error in enum_errors(node,path.name+'#'+pointer):
                lint.fail(path,f"{pointer}: {error}")
        for occurrence in enumerate_schema_properties(path.name,document):
            for error in member_role_errors(occurrence.name,occurrence.shape):
                lint.fail(path,f"{occurrence.pointer}: {error}")


def check_protocol_member_contract(lint: Lint) -> None:
    try:
        from ..protocol_member_contract import check
    except ImportError:
        from protocol_member_contract import check
    from .core import ROOT
    for error in check(ROOT):
        lint.fail(ROOT / "tools/protocol-member-contract.json", error)
