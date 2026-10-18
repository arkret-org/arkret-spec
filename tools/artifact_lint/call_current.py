"""Executable Call current projection, source and signature conformance."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from functools import lru_cache

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .core import ARTIFACTS, Lint, load_json
from tools.generate_call_current_fixture import (
    ACTOR, OTHER, VECTOR, build_fixture, call_write_indices, jcs, project, revision,
    sign_snapshot, source, target, typed_id,
)

FIXTURE = ARTIFACTS / 'fixtures/call-current-fixture.json'


@lru_cache(maxsize=1)
def schema_registry():
    resources = []
    for path in sorted((ARTIFACTS / 'schemas').glob('*.schema.json')):
        document = json.loads(path.read_text(encoding='utf-8'))
        if '$id' in document:
            resources.append((document['$id'], Resource.from_contents(document)))
    return Registry().with_resources(resources)


@lru_cache(maxsize=None)
def schema_validator(path, fragment):
    document = json.loads(path.read_text(encoding='utf-8'))
    return Draft202012Validator({'$ref': document['$id'] + fragment}, registry=schema_registry())


def unb64(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def verify_detached(value, member, key, domain):
    sig = value[member]
    core = {k: v for k, v in value.items() if k != member}
    if sig['context'] != domain or sig['signature_algorithm'] != 'Ed25519':
        raise ValueError('signature purpose')
    if sig['signed_digest'] != 'sha256:' + hashlib.sha256(jcs(core)).hexdigest():
        raise ValueError('signed bytes')
    envelope = {k: v for k, v in sig.items() if k != 'sig'}
    Ed25519PublicKey.from_public_bytes(unb64(key)).verify(
        unb64(sig['sig']), domain.encode() + b'\n' + jcs(envelope))


def verify_producer(event, key):
    body = {k: v for k, v in event.items() if k not in ('event_id', 'producer_proof')}
    if typed_id('event', body) != event['event_id']:
        raise ValueError('Event ID')
    proof = event['producer_proof']
    digest = 'sha256:' + hashlib.sha256(jcs(body)).hexdigest()
    if proof['event_digest'] != digest:
        raise ValueError('producer digest')
    binding = {'context': 'ak.event_proof.v1', 'event_digest': digest,
               'actor_id': event['actor_id'], 'verification_method': proof['verification_method'],
               'created_at': proof['created_at']}
    header, empty, sig = proof['jws'].split('.')
    if empty or json.loads(unb64(header)) != {'alg': 'Ed25519'}:
        raise ValueError('producer JWS')
    message = header.encode() + b'.' + base64.urlsafe_b64encode(jcs(binding)).rstrip(b'=')
    Ed25519PublicKey.from_public_bytes(unb64(key)).verify(unb64(sig), message)


def verify_binding(entry, realm_id, call_id):
    participant = entry['value']['participant']
    if 'participant_binding' not in participant:
        if 'participant_signing_key' in entry:
            raise ValueError('P2P key')
        return
    binding = participant['participant_binding']
    fields = {k: participant[k] for k in ('actor_id', 'device_id', 'participant_id', 'focus_id', 'media')}
    fields.update(realm_id=realm_id, call_id=call_id,
                  expires_at=binding['expires_at'], issuer_kid=binding['issuer_kid'])
    key = entry['participant_signing_key']['public_key_b64u']
    Ed25519PublicKey.from_public_bytes(unb64(key)).verify(
        unb64(binding['sig']), b'ak.media.participant_binding.v1\0' + jcs(fields))


def axis_row(snapshot, axis):
    return next(r for r in snapshot['current_state_entries'] if r['selector']['kind'] == 'call_' + axis)


def validate_snapshot(snapshot, request, response, keys, *, known_rows=(), historical_ref=None,
                      permitted=True, source_available=True, reference_rows=None):
    """Conformance policy with explicit test authority keys, not native DID verification."""
    indices = call_write_indices()
    for key in ('account_id', 'station_base_url', 'session_epoch', 'realm_id', 'stream_ref', 'call_id'):
        if request[key] != response[key]:
            raise ValueError('authenticated local context')
    if not permitted or not source_available:
        return 'unavailable'
    schema_validator(ARTIFACTS / 'schemas/realm-state-snapshot.schema.json', '').validate(snapshot)
    verify_detached(snapshot, 'signature', keys['governance_public_key_b64u'], 'ak.realm_snapshot_signature.v1')
    unsigned = {k: v for k, v in snapshot.items() if k not in ('signature', 'snapshot_id')}
    if snapshot['snapshot_id'] != typed_id('realm_snapshot', unsigned):
        raise ValueError('Snapshot ID')
    if snapshot['realm_id'] != request['realm_id']:
        raise ValueError('Realm')
    generation = snapshot['governance_generation']
    if historical_ref is None:
        if generation != request['current_generation']:
            raise ValueError('current authority generation')
    elif historical_ref != snapshot['snapshot_id'] or generation > request['current_generation']:
        raise ValueError('exact historical basis')
    heads = snapshot['visible_stream_heads']
    if len(heads) != 1 or heads[0]['stream_ref'] != request['stream_ref']:
        raise ValueError('scope or cut')
    head = heads[0]
    known = request['known_head']
    if historical_ref is None and (head['stream_position'] < known['stream_position'] or (
        head['stream_position'] == known['stream_position'] and head['commit_id'] != known['commit_id'])):
        raise ValueError('head rollback or equivocation')
    provided = {jcs(row['selector']) for row in snapshot['current_state_entries']}
    if historical_ref is None and any(jcs(row['selector']) not in provided for row in known_rows):
        raise ValueError('missing previously known axis')
    if reference_rows is not None and provided != {jcs(row['selector']) for row in reference_rows}:
        raise ValueError('complete replica/materializer missing axis')
    seen = set()
    for row in snapshot['current_state_entries']:
        selector = row['selector']
        selector_key = jcs(selector)
        if selector_key in seen or selector['call_id'] != request['call_id']:
            raise ValueError('duplicate selector or Call')
        seen.add(selector_key)
        if row['source_stream_ref'] != head['stream_ref'] or row['revision']['stream_position'] > head['stream_position']:
            raise ValueError('row source/cut')
        for old in known_rows:
            if old['selector'] == selector and historical_ref is None:
                if row['revision']['stream_position'] < old['revision']['stream_position']:
                    raise ValueError('axis rollback')
                if row['revision'] == old['revision'] and row != old:
                    raise ValueError('same revision different bytes')
        if selector['kind'] not in ('call_roster', 'call_moderation'):
            continue
        axis = selector['kind'][5:]
        entries = row['value']['entries']
        last = row['value']['last_source']
        if row['revision'] != revision(last['source_commit']):
            raise ValueError('last source revision')
        if entries != sorted(entries, key=lambda e: e['tag_id']):
            raise ValueError('canonical entry order')
        dots, targets, positions = set(), set(), set()
        for entry in entries:
            dot, identity, position = entry['tag_id'], target(entry['value'], axis), entry['source_commit']['stream_position']
            if dot in dots or identity in targets or position in positions:
                raise ValueError('duplicate source or target')
            dots.add(dot)
            targets.add(identity)
            positions.add(position)
            if dot == last['tag_id'] and {k: entry[k] for k in ('tag_id', 'source_commit', 'value')} != last:
                raise ValueError('conflicting repeated last source')
        for entry in [*entries, last]:
            commit = entry['source_commit']
            verify_detached(commit, 'signature', keys['governance_public_key_b64u'], 'ak.realm_commit_signature.v1')
            core = {k: v for k, v in commit.items() if k not in ('commit_id', 'signature')}
            if typed_id('realm_commit', core) != commit['commit_id']:
                raise ValueError('Commit ID')
            index = indices[axis]
            if entry['tag_id'] != commit['event_ref'] + ':' + str(index):
                raise ValueError('source dot Event/index')
            if commit['stream_ref'] != row['source_stream_ref'] or commit['realm_id'] != request['realm_id']:
                raise ValueError('source scope')
            if commit['governance_generation'] > generation or commit['stream_position'] > row['revision']['stream_position']:
                raise ValueError('source beyond accepted axis')
        if last['value']['op'] in ('join', 'remove_participant'):
            if not any(entry['tag_id'] == last['tag_id'] for entry in entries):
                raise ValueError('observable latest source omitted')
        elif any(entry['source_commit']['stream_position'] >= last['source_commit']['stream_position'] for entry in entries):
            raise ValueError('leave/restore must follow every retained entry')
        if axis == 'roster':
            for entry in entries:
                verify_binding(entry, snapshot['realm_id'], selector['call_id'])
        if reference_rows is not None:
            expected = next(r for r in reference_rows if r['selector'] == selector)
            if row != expected:
                raise ValueError('complete replica/materializer mismatch')
    return 'accept' if historical_ref is None else 'accept_historical'


def refresh_allowed(roster, moderation, actor, device):
    join = next((e for e in roster['entries'] if e['value']['participant']['actor_id'] == actor
                 and e['value']['participant']['device_id'] == device), None)
    if join is None:
        return False
    for entry in moderation['entries']:
        removal = entry['value']['removal']
        if removal['actor_id'] != actor:
            continue
        if removal['action'] == 'ban':
            return False
        if removal['device_id'] == device:
            if entry['source_commit']['stream_ref'] != join['source_commit']['stream_ref']:
                return False
            if entry['source_commit']['stream_position'] > join['source_commit']['stream_position']:
                return False
    return True


def run_case(fixture, name):
    case = next((case for case in fixture['cases'] if case['name'] == name), {})
    snapshot = copy.deepcopy(fixture['checkpoints'][case.get('checkpoint', -1)])
    request, response = copy.deepcopy(fixture['request_context']), copy.deepcopy(fixture['response_context'])
    keys = fixture['test_keys']
    indices = fixture['write_indices']
    kwargs = {}
    resign = True
    if name in ('empty_roster_latest_leave', 'empty_moderation_latest_restore', 'unwritten_axis_absent',
                'kick_old_leg', 'kick_later_legal_join', 'restore_preserves_kick', 'full_actor_station_isolation'):
        if name == 'empty_roster_latest_leave':
            row = axis_row(fixture['checkpoints'][9], 'roster')
            return 'accept' if row['value']['entries'] == [] and row['value']['last_source']['value']['op'] == 'leave' and row['revision'] == revision(fixture['original_rows'][9]['commit']) else 'reject'
        if name == 'empty_moderation_latest_restore':
            row = axis_row(fixture['checkpoints'][5], 'moderation')
            return 'accept' if row['value']['entries'] == [] and row['value']['last_source']['value']['op'] == 'restore_participant' and row['revision'] == revision(fixture['original_rows'][5]['commit']) else 'reject'
        if name == 'unwritten_axis_absent':
            return 'accept' if not any(r['selector']['kind'] in ('call_roster', 'call_moderation') for r in fixture['checkpoints'][0]['current_state_entries']) else 'reject'
        if name == 'full_actor_station_isolation':
            entries = axis_row(fixture['checkpoints'][3], 'roster')['value']['entries']
            return 'accept' if len(entries) == 2 and {jcs(e['value']['participant']['actor_id']) for e in entries} == {jcs(ACTOR), jcs(OTHER)} else 'reject'
        if name == 'restore_preserves_kick':
            prior = axis_row(snapshot, 'moderation')['value']
            fake = copy.deepcopy(fixture['original_rows'][5])
            fake['event']['payload']['moderation_delta']['expected_revision'] = revision(prior['last_source']['source_commit'])
            result = project(prior, fake, 'moderation', indices['moderation'], keys['issuer_public_key_b64u'])
            return 'accept' if len(result['entries']) == 1 and result['entries'][0]['value']['removal']['action'] == 'kick' else 'reject'
        checkpoint = fixture['checkpoints'][6 if name == 'kick_old_leg' else 7]
        allowed = refresh_allowed(axis_row(checkpoint, 'roster')['value'], axis_row(checkpoint, 'moderation')['value'], ACTOR,
                                  fixture['original_rows'][2]['event']['payload']['roster_delta']['participant']['device_id'])
        return 'accept' if allowed else 'reject'
    if name in ('stale_leave_revision', 'stale_restore_revision'):
        axis, pos = ('roster', 8) if name == 'stale_leave_revision' else ('moderation', 5)
        prior = axis_row(fixture['checkpoints'][pos - 1], axis)['value']
        event_row = copy.deepcopy(fixture['original_rows'][pos])
        event_row['event']['payload'][axis + '_delta']['expected_revision']['stream_position'] -= 1
        project(prior, event_row, axis, indices[axis], keys['issuer_public_key_b64u'])
        return 'accept'
    row = axis_row(snapshot, 'roster')
    entry = row['value']['entries'][0]
    if name == 'partial_value':
        row['value']['partial'] = True
    elif name == 'accumulated_assertions':
        row['value'] = {'assertions': [row['value']['last_source']]}
    elif name == 'missing_last_source':
        del row['value']['last_source']
    elif name == 'missing_issuer_key':
        del entry['participant_signing_key']
    elif name == 'wrong_historical_issuer_key':
        entry['participant_signing_key']['public_key_b64u'] = keys['governance_public_key_b64u']
    elif name.startswith('wrong_binding_'):
        participant = entry['value']['participant']
        field = name[len('wrong_binding_'):]
        if field == 'actor_station':
            participant['actor_id'] = OTHER
        elif field == 'device':
            participant['device_id'] = participant['device_id'][:-1] + '2'
        elif field == 'participant':
            participant['participant_id'] = participant['participant_id'][:-1] + '9'
        elif field == 'media':
            participant['media']['screen'] = True
    elif name == 'wrong_scope':
        snapshot['visible_stream_heads'][0]['stream_ref'] = {'kind': 'circle', 'realm_id': request['realm_id'], 'circle_id': typed_id('circle', {})}
    elif name == 'wrong_call':
        row['selector']['call_id'] = typed_id('call', {})
    elif name in ('wrong_source_position', 'wrong_source_event'):
        commit = entry['source_commit']
        commit['stream_position' if name == 'wrong_source_position' else 'event_ref'] = 1 if name == 'wrong_source_position' else typed_id('event', {})
    elif name == 'wrong_dot_index':
        entry['tag_id'] = entry['tag_id'][:-1] + '6'
    elif name in ('duplicate_target', 'duplicate_position'):
        duplicate = copy.deepcopy(entry)
        duplicate['tag_id'] = typed_id('event', {}) + ':7'
        if name == 'duplicate_position':
            duplicate['value']['participant']['actor_id'] = OTHER
        row['value']['entries'].append(duplicate)
        row['value']['entries'].sort(key=lambda e: e['tag_id'])
    elif name == 'source_after_axis_revision':
        row['revision'] = revision(fixture['original_rows'][2]['commit'])
        row['value']['last_source'] = source(fixture['original_rows'][2], 'roster', indices['roster'])
    elif name == 'revision_not_last_source':
        row['revision']['stream_position'] -= 1
    elif name == 'rollback_head':
        request['known_head'] = revision(snapshot['visible_stream_heads'][0])
        snapshot = copy.deepcopy(fixture['checkpoints'][3])
    elif name in ('same_revision_same_bytes', 'same_revision_different_value'):
        kwargs['known_rows'] = copy.deepcopy(snapshot['current_state_entries'])
        if name.endswith('different_value'):
            row['value']['entries'] = []
    elif name == 'old_tenure_as_current':
        request['current_generation'] = 2
    elif name in ('historical_exact_basis', 'wrong_historical_ref'):
        request['current_generation'] = 2
        kwargs['historical_ref'] = snapshot['snapshot_id'] if name == 'historical_exact_basis' else typed_id('realm_snapshot', {})
    elif name == 'wrong_authenticated_account':
        response['account_id'] = OTHER['account_id']
    elif name == 'wrong_local_session':
        response['session_epoch'] += 1
    elif name == 'revoked_current_permission':
        kwargs['permitted'] = False
    elif name == 'missing_source_material':
        kwargs['source_available'] = False
    elif name == 'exact_history_below_floor':
        position = fixture['original_rows'][0]['commit']['stream_position']
        floor = snapshot['retention_and_history_floor']['stream_floors'][0]['oldest_position']
        return 'unavailable' if position < floor else 'accept'
    elif name == 'producer_signature_tampered':
        ev = copy.deepcopy(fixture['original_rows'][2]['event'])
        proof = ev['producer_proof']
        proof['jws'] = proof['jws'][:-1] + ('A' if proof['jws'][-1] != 'A' else 'B')
        verify_producer(ev, keys['producer_public_key_b64u'])
        return 'accept'
    elif name == 'commit_signature_tampered':
        entry['source_commit']['signature']['sig'] = 'A' * 86
    elif name in ('snapshot_signature_tampered', 'omission_unsigned'):
        resign = False
        if name == 'snapshot_signature_tampered':
            snapshot['signature']['sig'] = 'A' * 86
        else:
            row['value']['entries'] = [entry for entry in row['value']['entries'] if entry['tag_id'] == row['value']['last_source']['tag_id']]
    elif name.startswith('omission_resigned_') or name == 'wrong_member_complete_replica':
        if name == 'wrong_member_complete_replica':
            older = copy.deepcopy(axis_row(fixture['checkpoints'][3], 'roster')['value']['entries'])
            row['value']['entries'] = older
        else:
            row['value']['entries'] = [entry for entry in row['value']['entries'] if entry['tag_id'] == row['value']['last_source']['tag_id']]
        if name.endswith('complete_replica'):
            kwargs['reference_rows'] = fixture['checkpoints'][case.get('checkpoint', -1)]['current_state_entries']
    elif name == 'two_axes_one_commit_distinct_dots':
        mod = axis_row(snapshot, 'moderation')
        if row['revision'] != mod['revision'] or row['value']['last_source']['tag_id'] == mod['value']['last_source']['tag_id']:
            raise ValueError('two-axis atomic source')
    elif name == 'below_floor_current_binding_key':
        snapshot = copy.deepcopy(fixture['checkpoints'][7])
        snapshot['retention_and_history_floor']['stream_floors'][0]['oldest_position'] = 8
        entries = axis_row(snapshot, 'roster')['value']['entries']
        if not any(e['source_commit']['stream_position'] < 8 and 'participant_signing_key' in e for e in entries):
            raise AssertionError('below-floor binding case lacks an actual retained source/key')
    elif name != 'complete_cold_recovery':
        raise NotImplementedError('unknown fixture case: ' + name)
    if resign:
        snapshot = sign_snapshot(snapshot)
    return validate_snapshot(snapshot, request, response, keys, **kwargs)


def check_call_current(lint: Lint) -> None:
    fixture = load_json(lint, FIXTURE)
    try:
        if fixture != build_fixture():
            raise ValueError('fixture differs from deterministic generator')
        contract = load_json(lint, ARTIFACTS / 'registry/contract-registry.json')
        policy = contract['current_result_registry']['call_current_contract']
        if fixture['write_indices'] != call_write_indices():
            raise ValueError('canonical registry Call write indices')
        writer = next(row for row in contract['event_kind_registry']['event_kinds'] if row['event_kind'] == 'ak.call.state')
        for axis, index in fixture['write_indices'].items():
            write = writer['result_writes'][index]
            if write['condition'] != {'kind': 'field_present', 'field': 'payload.' + axis + '_delta'} or write['result_selector'] != {'kind': 'composite', 'components': ['payload.call_id']}:
                raise ValueError('Call axis conditional selector')
        if policy['value_members'] != ['entries', 'last_source'] or policy['partial_allowed'] is not False:
            raise ValueError('closed complete Call value contract')
        for key in ('independent_omission_proof', 'new_operations', 'history_floor_bypass', 'reusable_allow',
                    'moderation_bounded_by_roster_count', 'kick_expiry', 'private_receipt'):
            if policy[key] is not False:
                raise ValueError('Call boundary drift: ' + key)
        for original in fixture['original_rows']:
            schema_validator(ARTIFACTS / 'schemas/event-envelope.schema.json', '').validate(original['event'])
            kind = original['event']['kind']
            schema_validator(ARTIFACTS / 'schemas/event-payload.schema.json',
                             '#/$defs/' + ('call_create_payload' if kind == 'ak.call.create' else 'call_state_payload')).validate(original['event']['payload'])
            schema_validator(ARTIFACTS / 'schemas/realm-commit.schema.json', '').validate(original['commit'])
            verify_producer(original['event'], fixture['test_keys']['producer_public_key_b64u'])
            verify_detached(original['commit'], 'signature', fixture['test_keys']['governance_public_key_b64u'], 'ak.realm_commit_signature.v1')
        for snapshot in fixture['checkpoints']:
            schema_validator(ARTIFACTS / 'schemas/realm-state-snapshot.schema.json', '').validate(snapshot)
        for case in fixture['cases']:
            try:
                actual = run_case(fixture, case['name'])
            except (ValueError, KeyError) as exc:
                actual = 'reject'
            except Exception as exc:
                from cryptography.exceptions import InvalidSignature
                from jsonschema.exceptions import ValidationError
                if not isinstance(exc, (InvalidSignature, ValidationError)):
                    raise
                actual = 'reject'
            if actual != case['expected']:
                lint.fail(FIXTURE, f"{case['name']}: expected {case['expected']}, got {actual}")
        if fixture['covers_vectors'] != [VECTOR]:
            raise ValueError('Call vector registration')
    except Exception as exc:
        lint.fail(FIXTURE, f'Call current contract: {getattr(exc, "message", str(exc))}')
