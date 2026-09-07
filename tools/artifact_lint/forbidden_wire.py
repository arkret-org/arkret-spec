"""Validate the forbidden-wire vocabulary and executable matchers."""

import json
import re
from pathlib import Path

from .core import ARTIFACTS, Lint


def instance_pointer_resolves(schemas: Path, file: str, schema, pointer: str, seen=None) -> bool:
    """Resolve an instance domain through properties, references and union branches."""
    if not pointer:
        return True
    if not isinstance(schema, dict):
        return False
    seen = set() if seen is None else seen
    marker = (file, json.dumps(schema, sort_keys=True), pointer)
    if marker in seen:
        return False
    seen = seen | {marker}
    ref = schema.get('$ref')
    if ref:
        ref_file, _, fragment = ref.partition('#')
        ref_file = ref_file or file
        target = json.loads((schemas / ref_file).read_text(encoding='utf-8'))
        for token in fragment.lstrip('/').split('/') if fragment else []:
            token = token.replace('~1', '/').replace('~0', '~')
            target = target[int(token)] if isinstance(target, list) else target[token]
        if instance_pointer_resolves(schemas, ref_file, target, pointer, seen):
            return True
    for keyword in ('allOf', 'oneOf', 'anyOf'):
        if any(instance_pointer_resolves(schemas, file, branch, pointer, seen)
               for branch in schema.get(keyword, [])):
            return True
    token, _, tail = pointer[1:].partition('/')
    token = token.replace('~1', '/').replace('~0', '~')
    rest = '/' + tail if tail else ''
    candidates = []
    properties = schema.get('properties', {})
    if token == '*':
        candidates.extend(properties.values())
        candidates.extend(schema.get('patternProperties', {}).values())
        if isinstance(schema.get('additionalProperties'), dict):
            candidates.append(schema['additionalProperties'])
        if 'items' in schema:
            candidates.append(schema['items'])
    elif token in properties:
        candidates.append(properties[token])
    elif token.isdecimal() and 'items' in schema:
        candidates.append(schema['items'])
    return any(instance_pointer_resolves(schemas, file, child, rest, seen) for child in candidates)


def vocabulary_errors(registry: dict, schemas: Path) -> list[str]:
    errors = []
    definitions = registry.get('context_definitions', {})
    kinds = registry.get('context_matching', {}).get('document_kinds', [])
    used = {entry.get('context') for entry in registry.get('entries', [])}
    if set(definitions) != used:
        errors.append(f'context vocabulary mismatch: {set(definitions) ^ used}')
    for name, definition in definitions.items():
        selectors = definition.get('selectors')
        if definition.get('status') == 'retired':
            if selectors != [] or not definition.get('retirement_reason'):
                errors.append(f'{name}: retired context requires an explicit empty domain and reason')
            continue
        if not isinstance(selectors, list) or not selectors:
            errors.append(f'{name}: nonempty selectors required')
            continue
        for selector in selectors:
            if set(selector) != {'document_kind', 'schema_ref', 'instance_pointer', 'match_scope'}:
                errors.append(f'{name}: selector must use the closed selector shape')
            if selector.get('document_kind') not in kinds:
                errors.append(f'{name}: unknown document kind')
            if selector.get('match_scope') not in ('root', 'descendants', 'patch'):
                errors.append(f'{name}: unknown match scope')
            pointer = selector.get('instance_pointer', '')
            if not isinstance(pointer, str) or (pointer and not pointer.startswith('/')) or re.search(r'~(?![01])', pointer):
                errors.append(f'{name}: invalid instance pointer')
            ref = selector.get('schema_ref', '')
            if ref == '*':
                if selector.get('document_kind') == 'schema_instance':
                    errors.append(f'{name}: schema_instance must name its owning schema')
                continue
            file, _, fragment = ref.partition('#')
            try:
                target = (schemas / file).resolve()
                if target.parent != schemas.resolve():
                    raise ValueError('schema reference escapes schema directory')
                value = json.loads(target.read_text(encoding='utf-8'))
                for token in fragment.lstrip('/').split('/') if fragment else []:
                    token = token.replace('~1', '/').replace('~0', '~')
                    value = value[int(token)] if isinstance(value, list) else value[token]
                if not instance_pointer_resolves(schemas, file, value, pointer):
                    errors.append(f'{name}: instance_pointer {pointer} has no declared domain in {ref}')
                if selector.get('match_scope') == 'patch' and not instance_pointer_resolves(schemas, file, value, pointer + '/patch'):
                    errors.append(f'{name}: patch scope requires a declared canonical patch member')
            except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
                errors.append(f'{name}: unresolved schema_ref {ref}: {error}')
    for entry in registry.get('entries', []):
        matcher = entry.get('match', {})
        if matcher.get('kind') not in ('field', 'path', 'patch_path', 'value', 'prefix', 'pattern'):
            errors.append(f'{entry.get("id")}: invalid matcher kind')
        values = matcher.get('values')
        if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v for v in values):
            errors.append(f'{entry.get("id")}: nonempty literal matcher values required')
        elif matcher.get('kind') == 'pattern':
            for value in values:
                try:
                    re.compile(value)
                except re.error:
                    errors.append(f'{entry.get("id")}: invalid matcher pattern')
        if set(matcher) - {'kind', 'values', 'value_pointer'}:
            errors.append(f'{entry.get("id")}: unknown matcher property')
        if entry.get('context') not in definitions:
            errors.append(f'{entry.get("id")}: undefined context')
        elif any(s.get('match_scope') == 'patch' for s in definitions[entry['context']].get('selectors', [])) and matcher.get('kind') not in ('field', 'path'):
            errors.append(f'{entry.get("id")}: create-context patch scope requires a field or path matcher')
        pointer = matcher.get('value_pointer', '')
        if not isinstance(pointer, str) or (pointer and not pointer.startswith('/')) or re.search(r'~(?![01])', pointer):
            errors.append(f'{entry.get("id")}: invalid matcher value_pointer')
    return errors


def check_forbidden_wire_contexts(lint: Lint) -> None:
    path = ARTIFACTS / 'registry/forbidden-wire-fields.json'
    registry = json.loads(path.read_text(encoding='utf-8'))
    for error in vocabulary_errors(registry, ARTIFACTS / 'schemas'):
        lint.fail(path, error)
