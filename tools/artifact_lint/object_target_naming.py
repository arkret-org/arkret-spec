"""Name ordinary operation targets from canonical payload types, not event names."""

from __future__ import annotations

import re

from .core import ARTIFACTS, Lint, load_json, resolve_json_pointer
from .naming_contracts import resolve_terminal_constraints


# common-fields.md 2.1.1 distinguishes these materialized objects from artifacts.
MATERIALIZED_KINDS = frozenset({
    'realm', 'space', 'circle', 'strand', 'message', 'morph', 'relation',
    'view', 'policy', 'actor_profile',
})


def object_target_name_errors(documents, file_name, name, shape, expected_kind):
    """Check a registry-declared operation target, including shared polymorphism.

    The canonical payload definition is inspected before event-specific branch
    refinements. Event/Commit/proof references are outside this ordinary-object
    role. The shared object_ref contract is an explicit polymorphic source;
    unknown terminals are never accepted as an implicit naming exception.
    """
    if expected_kind not in MATERIALIZED_KINDS:
        return []
    terminals = resolve_terminal_constraints(documents, file_name, shape)
    shared = resolve_terminal_constraints(documents, 'event-payload.schema.json',
        documents['event-payload.schema.json']['$defs']['object_ref'])
    shared_kinds = set()
    for category, value in shared:
        if category == 'pattern':
            for alternatives, literal in re.findall(r'ak:(?:\(([^)]+)\)|([a-z][a-z0-9_]*)):', value):
                shared_kinds.update(alternatives.split('|') if alternatives else [literal])
    if terminals == shared and len(shared_kinds) > 1:
        return [] if name.endswith('_ref') else ['shared polymorphic target must use _ref']
    kinds = set()
    for category, value in terminals:
        match = re.match(r'^\^ak:([a-z][a-z0-9_]*):', value) if category == 'pattern' else None
        if match is None or not value.endswith('$') or '|' in value:
            return ['operation target has an unclassified terminal; an explicit reference contract is required']
        kinds.add(match[1])
    if not kinds:
        return ['operation target has no resolved identifier terminal']
    if expected_kind not in kinds:
        return [f'operation target terminal does not admit selector kind {expected_kind}']
    if len(kinds) > 1:
        return [] if name.endswith('_ref') else ['polymorphic target must use _ref']
    suffix = expected_kind + '_id'
    if name != suffix and not name.endswith('_' + suffix):
        return [f'single-kind operation target must use {suffix} or <role>_{suffix}']
    return []


def object_target_contract_errors(documents, catalog):
    """Derive target roles from typed state selectors, without a field blacklist."""
    errors = []
    for row in catalog['event_kind_registry']['event_kinds']:
        for write in row.get('state_writes', []):
            selector = write.get('state_selector') or {}
            kind = selector.get('kind', '')
            field = selector.get('field', '')
            if not kind.startswith('id:') or kind[3:] not in MATERIALIZED_KINDS:
                continue
            if not field.startswith('payload.'):
                continue
            reference = row['payload_schema_ref']
            target, _, fragment = reference.partition('#')
            file_name = target.rsplit('/', 1)[-1]
            try:
                shape = resolve_json_pointer(documents[file_name], '#' + fragment)
                seen = set()
                for member in field.split('.')[1:]:
                    while '$ref' in shape:
                        edge = (file_name, shape['$ref'])
                        if edge in seen:
                            raise ValueError('cyclic payload reference')
                        seen.add(edge)
                        target, _, fragment = shape['$ref'].partition('#')
                        file_name = target.rsplit('/', 1)[-1] if target else file_name
                        shape = resolve_json_pointer(documents[file_name], '#' + fragment)
                    shape = shape['properties'][member]
            except (KeyError, TypeError, ValueError):
                errors.append(f"{row['event_kind']} {field}: operation target does not resolve in its canonical payload")
                continue
            for error in object_target_name_errors(documents, file_name, member, shape, kind[3:]):
                errors.append(f"{row['event_kind']} {field}: {error}")
    return sorted(set(errors))


def check_object_target_naming(lint: Lint) -> None:
    documents = {path.name: load_json(lint, path)
                 for path in sorted((ARTIFACTS / 'schemas').glob('*.schema.json'))}
    catalog_path = ARTIFACTS / 'registry/contract-registry.json'
    catalog = load_json(lint, catalog_path)
    if not isinstance(catalog, dict) or any(not isinstance(value, dict) for value in documents.values()):
        return
    for error in object_target_contract_errors(documents, catalog):
        lint.fail(catalog_path, error)
