"""Positive semantic roles and exact-owner enum authorities for v1 names."""
from __future__ import annotations

import re
import posixpath
import math
import json
from typing import Any

from .core import ARTIFACTS, ROOT, Lint, load_json, load_yaml, resolve_json_pointer
from .naming import PASCAL_CASE_RE, enumerate_schema_nodes, external_anchor_is_valid, SchemaReferenceContext
from .naming_contracts import openapi_schema_positions

ROLE_TAILS = {
    "request_body": "request_body", "response_body": "response_body",
    "decision": "decision", "verdict": "verdict", "key_resolution": "resolution",
    "page": "page", "set": "set", "snapshot": "snapshot",
    "status_view": "view", "view": "view", "parameters": "parameters",
    "shared_fields": "fields", "problem_extensions": "problem_extensions",
    "attempt_outcome": "outcome", "terminal_outcome": "outcome",
    "planned_event": "planned_event", "status_record": "record",
    "progress": "progress", "retained_fact": "record", "keyed_entry": "entry",
    "lookup_response": "lookup_response_body", "signature_input": "signature_input",
}
NAME_ROLES = set(ROLE_TAILS) | {"current_state", "domain_value"}
MEMBER_PATTERNS = {
    "count": r"(?:[a-z][a-z0-9_]*_)?count(?:_per_[a-z][a-z0-9_]*)?",
    "instant": r"[a-z][a-z0-9_]*_at",
    "permission": r"[a-z][a-z0-9_]*_allowed",
    "obligation": r"[a-z][a-z0-9_]*_required",
    "url": r"[a-z][a-z0-9_]*_url",
    "binary_encoding": r"[a-z][a-z0-9_]*_base64(?:url)?",
}
SNAKE = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*\Z")
NAMESPACED = re.compile(r"ak\.[a-z][a-z0-9]*(?:_[a-z0-9]+)*(?:\.[a-z][a-z0-9]*(?:_[a-z0-9]+)*)*\Z")
NONTERMINAL = {"pending", "prepared", "preparing", "unknown", "in_progress", "running"}
ALIAS_ANNOTATIONS = {'title', 'description', '$comment', 'examples', 'default',
                     'deprecated', 'readOnly', 'writeOnly'}
DECIMAL_TEXT = re.compile(r'(?:0|[1-9][0-9]*)\Z')
VERSION_TEXT = re.compile(r'(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))*\Z|[0-9]{4}[a-z]\Z')
URI_LITERAL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+\Z")
MEDIA_TOKEN = r"[!#$%&'*+.^_`|~0-9A-Za-z-]+"
MEDIA_TYPE = re.compile(MEDIA_TOKEN + '/' + MEDIA_TOKEN
                        + r'(?:[ \t]*;[ \t]*' + MEDIA_TOKEN + r'=(?:' + MEDIA_TOKEN + r'|"(?:[^"\\\r\n]|\\[^\r\n])*"))*\Z')
# This is a reviewed schema-local protocol constant, not an external literal.
SCHEMA_LOCAL_REGISTERED_LITERALS = {
    'websocket-dpop-proof.schema.json#/$defs/claims/properties/htm': ['ARKRET-WEBSOCKET-AUTH'],
}


def settled_scope(node: dict) -> bool:
    scope = node.get('x-arkret-outcome-scope')
    return (isinstance(scope, str) and SNAKE.fullmatch(scope) is not None
            and scope not in {'outcome', 'result', 'terminal', 'attempt', 'processing'})


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def type_role_errors(name: str, node: dict) -> list[str]:
    role = node.get("x-arkret-name-role")
    normalized = snake(name) if name[:1].isupper() else name
    errors = []
    if 'x-arkret-name-role' in node and (not isinstance(role, str) or role not in NAME_ROLES):
        errors.append('unknown semantic type role; declare the actual registered contract role')
        role = None
    if normalized in {"result", "results"} or normalized.endswith(("_result", "_results")):
        errors.append("Result is not a semantic protocol role")
    if normalized in {"row", "rows"} or normalized.endswith(("_row", "_rows")) or role == "row":
        errors.append("Row is not a public protocol role; use the actual domain role")
    if role == "current_state" and not normalized.startswith("current_"):
        errors.append("current state type must retain the Current<Family> prefix")
    if role in ROLE_TAILS and not normalized.endswith(ROLE_TAILS[role]):
        errors.append(f"{role} type must end {ROLE_TAILS[role]}")
    if normalized.endswith("_outcome"):
        if role not in {"terminal_outcome", "attempt_outcome"}:
            errors.append("Outcome requires an explicitly scoped settled processing role")
        if not settled_scope(node):
            errors.append("Outcome requires a named domain processing scope")
        for _pointer, child in enumerate_schema_nodes("role", node):
            if isinstance(child, dict) and any(isinstance(value, str) and value in NONTERMINAL
                                             for value in child.get("enum", [child.get("const")])):
                errors.append("Outcome admits an unsettled status")
    props = node.get("properties", {})
    if (normalized == 'problem' or normalized.endswith('_problem')) and node.get('type') == 'object' and props:
        standard = {'type', 'title', 'status', 'detail'}
        if not standard <= set(props) or not standard <= set(node.get('required', [])):
            errors.append('Problem names a complete RFC 9457 body; a field fragment uses ProblemExtensions')
    if role == 'problem_extensions' and {'type', 'title', 'status', 'detail', 'instance'} & set(props):
        errors.append('ProblemExtensions must not redeclare standard Problem members')
    if normalized.endswith('_snapshot'):
        boundary = node.get('x-arkret-snapshot-boundary', {})
        required = set(node.get('required', []))
        for axis in ('cut_fields', 'coverage_fields'):
            fields = boundary.get(axis)
            if not isinstance(fields, list) or not fields or len(fields) != len(set(fields)):
                errors.append(f'Snapshot requires explicit nonempty {axis}')
            elif any(field not in props or field not in required for field in fields):
                errors.append(f'Snapshot {axis} must name required canonical members')
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
    if name in {'row', 'rows', 'result', 'results'} or name.endswith(('_row', '_rows', '_result', '_results')):
        return ['generic Row/Result is not an owned protocol member role']
    if not isinstance(node,dict):
        node = {}
    kinds = node.get('type')
    kinds = kinds if isinstance(kinds, list) else [kinds]
    if any(kind in ('integer', 'number') for kind in kinds) and name.endswith(
            ('_entries', '_records', '_items', '_views', '_outcomes')):
        return ['an element count must use _count, not a collection name']
    if name == 'outcome' or name.endswith('_outcome'):
        if not settled_scope(node):
            return ['Outcome member requires its exact settled processing scope']
        for _pointer, child in enumerate_schema_nodes('member', node):
            if isinstance(child, dict) and any(value in NONTERMINAL for value in
                    child.get('enum', [child.get('const')]) if isinstance(value, str)):
                return ['Outcome member admits an unsettled status in its processing scope']
    role = node.get("x-arkret-member-role")
    if 'x-arkret-member-role' in node and (not isinstance(role, str) or role not in MEMBER_PATTERNS):
        return ['unknown semantic member role; role metadata cannot waive the naming contract']
    pattern = MEMBER_PATTERNS.get(role)
    if pattern and not re.fullmatch(pattern, name):
        return [f"{role} member violates its positive name grammar"]
    if role in ("permission", "obligation") and node.get("type") != "boolean":
        return [f"{role} member must be boolean"]
    return []


def canonical_body_alias_errors(name: str, node: dict) -> list[str]:
    def transparent_reference(shape):
        if not isinstance(shape, dict):
            return False
        assertions = {key: value for key, value in shape.items()
                      if key not in ALIAS_ANNOTATIONS and not key.startswith('x-')}
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


def openapi_component_alias_errors(components: dict) -> list[str]:
    def target(node):
        if not isinstance(node, dict):
            return None
        assertions = {key: value for key, value in node.items()
                      if key not in ALIAS_ANNOTATIONS
                      and not key.startswith('x-')}
        if set(assertions) == {'$ref'} and isinstance(assertions['$ref'], str):
            return assertions['$ref']
        for operator in ('allOf', 'anyOf', 'oneOf'):
            branches = assertions.get(operator)
            if set(assertions) == {operator} and isinstance(branches, list) and len(branches) == 1:
                return target(branches[0])
        return None
    errors = []

    def canonical(name, seen):
        if name in seen:
            errors.append(f'cyclic OpenAPI component alias: {name}')
            return None
        reference = target(components[name])
        if reference is None:
            return '#/components/schemas/' + name
        prefix = '#/components/schemas/'
        if reference.startswith(prefix):
            destination = reference[len(prefix):]
            if destination not in components:
                errors.append(f'unknown OpenAPI component alias target: {reference}')
                return None
            return canonical(destination, seen | {name})
        file_name, separator, fragment = reference.partition('#')
        if file_name.startswith('https://arkret.org/v1/schemas/'):
            file_name = '../schemas/' + file_name.rsplit('/', 1)[-1]
        if '://' not in file_name:
            file_name = posixpath.normpath(file_name)
        return file_name + (separator + fragment if separator else '')

    owners = {}
    for name in components:
        reference = canonical(name, set())
        if reference is None:
            continue
        if reference in owners:
            errors.append(f'duplicate OpenAPI component aliases {owners[reference]} and {name}: {reference}')
        else:
            owners[reference] = name
    return errors


def openapi_component_name_errors(components: dict) -> list[str]:
    return [f'OpenAPI schema component must use PascalCase with folded acronyms: {name}'
            for name in components
            if not isinstance(name, str) or not PASCAL_CASE_RE.fullmatch(name)
            or re.search(r'[A-Z]{2,}', name)]



def enum_errors(node: dict, owner: str | None = None, registered_values: list | None = None) -> list[str]:
    values = node.get("enum", [node["const"]] if "const" in node else [])
    if not values:
        return []
    metadata = node.get("x-arkret-value-ownership")
    if not isinstance(metadata, dict) or set(metadata) != {"class", "authority", "values", "owner"}:
        return ["every enum/const requires exact-owner value classification and authority"]
    if owner is not None and metadata['owner'] != owner:
        return ["enum authority cannot propagate to a different owner"]
    if json.dumps(metadata["values"], sort_keys=True) != json.dumps(values, sort_keys=True):
        return ["enum authority is stale or expanded beyond its exact registered values"]
    kind, authority = metadata["class"], metadata["authority"]
    if not isinstance(kind, str):
        return ['unknown enum ownership class']
    if not isinstance(authority, str) or not authority:
        return ["enum authority is empty"]
    if kind == "owned_symbol" and any(v is not None and (not isinstance(v,str) or not SNAKE.fullmatch(v)) for v in values):
        return ["Arkret symbolic values must use snake_case"]
    if kind == "namespaced_symbol" and any(v is not None and (not isinstance(v,str) or not NAMESPACED.fullmatch(v)) for v in values):
        return ["Arkret namespaced symbols violate their registered grammar"]
    if kind == "numeric" and any(not isinstance(v,(int,float,bool)) and v is not None for v in values):
        return ["numeric literals must preserve their scalar type"]
    if kind == 'numeric' and any(isinstance(v, float) and not math.isfinite(v) for v in values):
        return ['numeric literals must be finite JSON scalars']
    patterns = {'decimal_text': DECIMAL_TEXT, 'version_text': VERSION_TEXT,
                'uri': URI_LITERAL, 'media_type': MEDIA_TYPE}
    if kind in patterns and any(v is not None and (not isinstance(v, str) or not patterns[kind].fullmatch(v)) for v in values):
        return [f'{kind} literal violates its scalar type or lexical grammar']
    if kind == 'media_type' and any(isinstance(v, str) and any(ord(c) < 32 and c != '\t' or ord(c) == 127 for c in v) for v in values):
        return ['media type literal contains a forbidden control character']
    if kind == 'uri' and any(isinstance(v, str) and re.search(r'%(?![0-9A-Fa-f]{2})', v) for v in values):
        return ['URI literal contains an invalid percent escape']
    if kind == 'numeric_range':
        for value in values:
            if value is None:
                continue
            if not isinstance(value, str) or not re.fullmatch(r'(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*)|\+)?', value):
                return ['numeric range labels require canonical nonnegative decimal endpoints']
            if '-' in value and int(value.split('-')[0]) >= int(value.split('-')[1]):
                return ['numeric range endpoints must increase']
    if kind == 'human_text' and any(v is not None and (not isinstance(v, str) or not v.strip()) for v in values):
        return ['human text literals must be nonempty text']
    if kind == 'structured_literal' and any(v is not None and not isinstance(v, (dict, list)) for v in values):
        return ['structured literals must be arrays or objects']
    if kind == 'selector_grammar' and any(v is not None and (not isinstance(v, str) or (v != '*' and not SNAKE.fullmatch(v))) for v in values):
        return ['selector grammar terminals must be a snake_case kind or wildcard']
    if kind == 'registered_literal' and (registered_values is None or json.dumps(values, sort_keys=True) != json.dumps(registered_values, sort_keys=True)):
        return ['registered literal must equal the exact resolved authority values']
    if kind == "external_literal" and not external_anchor_is_valid(authority):
        return ["external enum authority must be an exact HTTPS section anchor"]
    if kind == 'external_literal' and any(v is not None and (not isinstance(v, str) or not v) for v in values):
        return ['external symbolic literals must preserve nonempty string values']
    if kind == 'symbol_or_media_type' and any(v is not None and (not isinstance(v,str) or not (SNAKE.fullmatch(v) or NAMESPACED.fullmatch(v) or MEDIA_TYPE.fullmatch(v))) for v in values):
        return ['typed token union admits an unclassified literal']
    if kind not in {"owned_symbol","namespaced_symbol","numeric","decimal_text","version_text","uri","media_type","external_literal","human_text","selector_grammar","structured_literal","symbol_or_media_type","numeric_range","registered_literal"}:
        return ["unknown enum ownership class"]
    return []


def registered_literal_values(node: dict, owner: str, path, document: dict, loader) -> list | None:
    metadata = node.get('x-arkret-value-ownership', {})
    if not isinstance(metadata, dict) or metadata.get('class') != 'registered_literal':
        return None
    authority = metadata.get('authority')
    if not isinstance(authority, str) or '#' not in authority:
        return None
    if authority == owner:
        return SCHEMA_LOCAL_REGISTERED_LITERALS.get(owner)
    file_name, fragment = authority.split('#', 1)
    target_path = (path.parent / file_name).resolve()
    registry_root = (ARTIFACTS / 'registry').resolve()
    if not file_name or not fragment.startswith('/') or not target_path.is_relative_to(registry_root):
        return None
    manifest = loader(ARTIFACTS / 'registry/registry-manifest.json')
    canonical = {entry.get('file') for entry in manifest.get('registries', [])
                 if isinstance(entry, dict) and entry.get('source_role') == 'canonical'} if isinstance(manifest, dict) else set()
    if target_path.relative_to(ARTIFACTS.resolve()).as_posix() not in canonical:
        return None
    target = loader(target_path)
    try:
        target = resolve_json_pointer(target, '#' + fragment)
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    # Scalar registry terminals never authorize a sibling row or an array.
    return [target] if isinstance(target, (str, int, float, bool)) or target is None else None


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
    replacements.update({'PeerKeyPackagesClaimRequestBody': 'KeyPackagesClaimRequestBody', 'PeerKeyPackagesClaimResponseBody': 'PeerKeyPackagesClaimCommandResponseBody', 'ErasureReceiptResource': 'ErasureReceiptPackage', 'ErasureReceiptSubmitRequestBody': 'ErasureReceiptPackage', 'AppletThirdPartyLocationLookupResponseBody': 'AppletRealmView'})
    replacements.update({'MorphRow': 'MorphView', 'SpaceRow': 'SpaceView', 'StrandRow': 'StrandView', 'RealmListRow': 'AccountRealmView', 'ContactListRow': 'ContactView', 'RealmOrganizationRelationshipRow': 'RealmOrganizationRelationshipView', 'EffectiveCapabilityGrantRow': 'EffectiveCapabilityGrantView', 'RealmStreamRow': 'RealmStreamView', 'AccountDataRow': 'AccountDataEntry', 'DeviceMessageDeliveredRow': 'DeviceMessageDeliveredEntry', 'DeviceMessageUnknownRow': 'DeviceMessageUnknownEntry', 'CalendarScheduleSourceExactRow': 'CurrentCalendarScheduleSource', 'MimiRoomBindingCurrentRow': 'CurrentMimiRoomBinding', 'WebvhWitnessRow': 'DidBindingWitness', 'realm_list_row': 'account_realm_view', 'contact_list_row': 'contact_view', 'realm_organization_relationship_row': 'realm_organization_relationship_view', 'realm_stream_row': 'realm_stream_view', 'pending_sidecar_access_reconciliation_row': 'pending_sidecar_access_reconciliation', 'rejected_event_row': 'applet_event_rejection', 'rejected_scope_row': 'applet_scope_rejection', 'stream_row': 'CommittedEventView'})
    replacements.update({'AccountDataCasConflict': 'AccountDataRevisionProblemExtensions', 'AccountDataCasConflictDetails': 'AccountDataRevisionProblemExtensions', 'account_data_cas_conflict_details': 'account_data_revision_problem_extensions', 'InviteLiveTargetOccupiedProblem': 'InviteLiveTargetOccupiedProblemExtensions'})
    return [f'retired contract reference {old}; use {new}' for old, new in replacements.items()
            if re.search(r'\b' + old + r'\b', text)]


def http_problem_response_errors(document: dict) -> list[str]:
    errors = []
    methods = {'get', 'post', 'put', 'patch', 'delete', 'query', 'options'}
    for path, item in document.get('paths', {}).items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method not in methods or not isinstance(operation, dict):
                continue
            for status, response in operation.get('responses', {}).items():
                if str(status) != 'default' and not (str(status).isdigit() and 400 <= int(status) < 600):
                    continue
                seen = set()
                try:
                    while isinstance(response, dict) and '$ref' in response:
                        ref = response['$ref']
                        if not isinstance(ref, str) or ref in seen or not ref.startswith('#/'):
                            raise ValueError('unresolved or cyclic response reference')
                        seen.add(ref)
                        response = resolve_json_pointer(document, ref)
                except (KeyError, IndexError, ValueError, TypeError):
                    errors.append(f'{method.upper()} {path} {status}: failure response reference does not resolve')
                    continue
                content = response.get('content', {}) if isinstance(response, dict) else {}
                media = content.get('application/problem+json', {}) if isinstance(content, dict) else {}
                if (not isinstance(content, dict) or set(content) != {'application/problem+json'}
                        or not isinstance(media, dict) or not isinstance(media.get('schema'), dict) or not media['schema']):
                    errors.append(f'{method.upper()} {path} {status}: HTTP failures must declare only application/problem+json with a nonempty schema')
    return errors


def check_semantic_naming(lint: Lint) -> None:
    try:
        from tools.public_type_duplicates import check as check_duplicates
    except ImportError:
        from public_type_duplicates import check as check_duplicates
    for error in check_duplicates(ROOT):
        lint.fail(ARTIFACTS / 'schemas', error)
    text_paths = sorted((ROOT / 'spec/v1/zh').rglob('*.md'))
    text_paths += sorted(ARTIFACTS.rglob('*.json'))
    text_paths += sorted((ARTIFACTS / 'openapi').glob('*.yaml'))
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
        if path.suffix == '.yaml':
            for error in openapi_component_name_errors(document.get('components', {}).get('schemas', {})):
                lint.fail(path, error)
            for error in http_problem_response_errors(document):
                lint.fail(path, error)
            for error in openapi_component_alias_errors(document.get('components', {}).get('schemas', {})):
                lint.fail(path, error)
        try:
            schema_nodes = list(openapi_schema_positions(document) if path.suffix == ".yaml" else
                                enumerate_schema_nodes(path.name, document, reference_document=document))
        except ValueError as error:
            lint.fail(path, f"semantic schema positions cannot be enumerated: {error}")
            continue
        context_cache = {}
        def role_context(context_document):
            key = id(context_document)
            if key not in context_cache:
                roots = list(openapi_schema_positions(context_document, follow_references=False)) if "openapi" in context_document else None
                resolver = SchemaReferenceContext(context_document, roots)
                context_cache[key] = (resolver, {id(value): pointer for pointer, value in resolver.nodes.items()})
            return context_cache[key]
        def role_shape(node, seen=None, context_path=path, context_document=document, source_pointer=None):
            if not isinstance(node, dict):
                return {}
            seen = set() if seen is None else seen
            reference = node.get("$ref", node.get("$dynamicRef"))
            if not isinstance(reference, str):
                return node
            resolver, pointers = role_context(context_document)
            source_pointer = pointers.get(id(node), "") if source_pointer is None else source_pointer
            edge = (str(context_path), source_pointer, reference)
            if edge in seen:
                return node
            seen.add(edge)
            try:
                local = resolver.resolve(reference, source_pointer)
            except ValueError as error:
                lint.fail(path, f"semantic role reference does not resolve: {reference}: {error}")
                return node
            if local is not None:
                target_pointer, target = local
                target_path, target_document = context_path, context_document
            else:
                file_name, _, fragment = reference.partition("#")
                if file_name.startswith("https://arkret.org/v1/schemas/"):
                    target_path = ARTIFACTS / "schemas" / file_name.rsplit("/", 1)[-1]
                else:
                    target_path = (context_path.parent / file_name).resolve() if file_name else context_path
                if not target_path.resolve().is_relative_to(ARTIFACTS.resolve()):
                    return node
                target_document = context_document if target_path == context_path else load_json(lint, target_path)
                if not isinstance(target_document, dict):
                    return node
                try:
                    local = role_context(target_document)[0].resolve("#" + fragment)
                    if local is None:
                        raise ValueError("target resource is unavailable")
                    target_pointer, target = local
                except (KeyError, IndexError, TypeError, ValueError) as error:
                    lint.fail(path, f"semantic role reference does not resolve: {reference}: {error}")
                    return node
            if not isinstance(target, dict):
                return node
            resolved = role_shape(target, seen, target_path, target_document, target_pointer)
            return {**{key: value for key, value in resolved.items() if key != "x-arkret-name-role"},
                    **{key: value for key, value in node.items() if key not in {"$ref", "$dynamicRef"}}}
        for pointer,node in schema_nodes:
            if not isinstance(node,dict):
                continue
            if pointer == '' and path.suffix == '.json':
                root_name = path.name.removesuffix('.schema.json').replace('-', '_')
                for error in type_role_errors(root_name, role_shape(node)):
                    lint.fail(path, f'root: {error}')
            if "/$defs/" in pointer and pointer.rsplit("/$defs/",1)[-1].count("/") == 0:
                for error in type_role_errors(pointer.rsplit("/",1)[-1],role_shape(node)):
                    lint.fail(path,f"{pointer}: {error}")
                for error in canonical_body_alias_errors(pointer.rsplit('/', 1)[-1], node):
                    lint.fail(path, f'{pointer}: {error}')
            if pointer.startswith("/components/schemas/") and pointer.count("/") == 3:
                for error in type_role_errors(pointer.rsplit("/",1)[-1],role_shape(node)):
                    lint.fail(path,f"{pointer}: {error}")
            owner = path.name+'#'+pointer
            registered = registered_literal_values(node, owner, path, document,
                                                  lambda target: load_json(lint, target))
            for error in enum_errors(node,owner,registered):
                lint.fail(path,f"{pointer}: {error}")
        for pointer, node in schema_nodes:
            if not isinstance(node, dict) or not isinstance(node.get("properties"), dict):
                continue
            for name, shape in node["properties"].items():
                if not isinstance(name, str):
                    lint.fail(path, f"{pointer}/properties: property names must be strings")
                    continue
                member_pointer = pointer + "/properties/" + name.replace("~", "~0").replace("/", "~1")
                for error in member_role_errors(name, role_shape(shape)):
                    lint.fail(path, f"{member_pointer}: {error}")


def check_protocol_member_contract(lint: Lint) -> None:
    try:
        from ..protocol_member_contract import check
    except ImportError:
        from protocol_member_contract import check
    from .core import ROOT
    for error in check(ROOT):
        lint.fail(ROOT / "tools/protocol-member-contract.json", error)
