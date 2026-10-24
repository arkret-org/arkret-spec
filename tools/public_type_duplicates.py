"""Find equivalent object assertions without merging distinct protocol purposes."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS = {'$schema', '$id', '$comment', 'title', 'description', 'examples'}

# Exact reviewed owner sets, never shape-wide or suffix-wide exceptions.
# A third use of the same shape requires an explicit new semantic review.
DISTINCT_PURPOSES = {
    frozenset({
        'account-operations.schema.json#/$defs/account_request_erasure_request_body',
        'management-review-operations.schema.json#/$defs/management_review_status_request_body',
    }): 'Erasure idempotency intent and lookup of a management-review request are different operation contracts.',
    frozenset({
        'keys-operations.schema.json#/$defs/keys_backups_issue_delete_challenge_request_body',
        'keys-operations.schema.json#/$defs/keys_backups_issue_unlock_challenge_request_body',
    }): 'Independent erasure, delete-challenge and unlock-challenge idempotency domains.',
    frozenset({
        'account-subscribe-frame.schema.json#/$defs/realm_list_removal',
        'account-subscribe-frame.schema.json#/$defs/realm_invalidation',
    }): 'List membership removal and invalidation of a retained Realm are different frame actions.',
    frozenset({
        'applet-configuration-operations.schema.json#/$defs/signature',
        'consent-operations.schema.json#/$defs/consent_current_read_proof',
        'call-invitation-operations.schema.json#/$defs/invitation_proof',
        'call-invitation-operations.schema.json#/$defs/admission_proof',
        'call-invitation-operations.schema.json#/$defs/voluntary_join_proof',
    }): 'Configuration, Consent read, invitation, holder admission and voluntary join bind different registered transcripts.',
    frozenset({
        'blob-operations.schema.json#/$defs/signature',
        'media-ice-configuration-response-body.schema.json#/$defs/signature',
    }): 'Blob receipt signatures and Media ICE response signatures cover different purpose-bound preimages.',
    frozenset({
        'event-payload.schema.json#/$defs/capability_relinquish_payload',
        'event-payload.schema.json#/$defs/capability_revoke_payload',
    }): 'Subject relinquishment and issuer revocation require different authority.',
    frozenset({
        'event-payload.schema.json#/$defs/realm_archive_payload',
        'event-payload.schema.json#/$defs/realm_freeze_payload',
    }): 'Archive visibility and freeze write admission have independent lifecycle semantics.',
}


def object_duplicates(documents: dict[str, dict]) -> set[frozenset[str]]:
    def resolve(reference: str, owner: str):
        if '://' in reference and not reference.startswith('https://arkret.org/v1/schemas/'):
            return None
        file_name, _, pointer = reference.partition('#')
        file_name = file_name.rsplit('/', 1)[-1] if file_name else owner
        if file_name not in documents:
            return None
        node = documents[file_name]
        for part in pointer.lstrip('/').split('/') if pointer else []:
            part = part.replace('~1', '/').replace('~0', '~')
            node = node[int(part)] if isinstance(node, list) else node[part]
        return file_name, node

    def shape(value, owner, seen):
        if isinstance(value, list):
            return [shape(child, owner, seen) for child in value]
        if not isinstance(value, dict):
            return value
        result = {key: shape(child, owner, seen) for key, child in value.items()
                  if key not in ANNOTATIONS and not key.startswith('x-arkret-') and key != '$defs'}
        reference = value.get('$ref')
        if reference:
            target = resolve(reference, owner)
            identity = (owner, reference)
            if target and identity not in seen:
                result.pop('$ref', None)
                base = shape(target[1], target[0], seen | {identity})
                if isinstance(base, dict):
                    # A sibling constrains the referenced schema as well; it
                    # cannot replace an assertion with a weaker dictionary key.
                    result = {'allOf': [base, result]} if result else base
        return result

    groups = defaultdict(list)
    for file_name, document in documents.items():
        declarations = [('', document), *[('/$defs/' + name, node)
                                         for name, node in document.get('$defs', {}).items()]]
        for pointer, node in declarations:
            if not isinstance(node, dict) or node.get('type') != 'object' or not node.get('properties'):
                continue
            normalized = shape(node, file_name, set())
            key = json.dumps(normalized, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
            groups[key].append(file_name + '#' + pointer)
    return {frozenset(owners) for owners in groups.values() if len(owners) > 1}


def check(root: Path = ROOT) -> list[str]:
    documents = {path.name: json.loads(path.read_text(encoding='utf-8'))
                 for path in (root / 'spec/v1/artifacts/schemas').glob('*.json')}
    try:
        actual = object_duplicates(documents)
    except (KeyError, IndexError, TypeError, ValueError) as error:
        return [f'cannot resolve duplicate-review assertions: {error}']
    errors = ['unreviewed equivalent object declarations: ' + ', '.join(sorted(group))
              for group in actual - DISTINCT_PURPOSES.keys()]
    errors += ['stale distinct-purpose review: ' + ', '.join(sorted(group))
               for group in DISTINCT_PURPOSES.keys() - actual]
    return sorted(errors)


if __name__ == '__main__':
    errors = check()
    for error in errors:
        print(error)
    if not errors:
        print('Equivalent object declarations: canonical sharing or exact distinct-purpose review')
    raise SystemExit(bool(errors))
