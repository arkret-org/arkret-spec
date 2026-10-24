"""Generate deterministic Call current conformance bytes, never live admission."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.regenerate_crypto_signature_fixture import refresh_jws_input
from tools.regenerate_detached_object_signature_kat import (
    KEY_A_SEED, KEY_B_SEED, OLD_VM, b64u, jcs, make_signature, public_key,
)

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'spec/v1/artifacts/fixtures/call-current-fixture.json'
VECTOR = 'ak.vector.call_state.compact_current.v1'
T = '2026-09-20T00:00:00.000Z'
DEVICE = 'ak:device:01964137-0000-7000-8000-000000000001'
ISSUER_VM = 'did:web:media.example#issuer-1'
PRODUCER_VM = 'did:web:alice.example#' + DEVICE
ACTOR = {'kind': 'account', 'account_id': {
    'principal_id': 'ak:did_core:web:alice.example',
    'station_id': 'ak:did_core:web:station.example',
}}
OTHER = copy.deepcopy(ACTOR)
OTHER['account_id']['station_id'] = 'ak:did_core:web:other-station.example'


def call_write_indices():
    registry = json.loads((ROOT / 'spec/v1/artifacts/registry/contract-registry.json').read_text(encoding='utf-8'))
    event_row = next(row for row in registry['event_kind_registry']['event_kinds'] if row['event_kind'] == 'ak.call.state')
    return {row['state_family'][5:]: index for index, row in enumerate(event_row['state_writes'])
            if row['state_family'] in ('call_roster', 'call_moderation')}


def typed_id(kind, unsigned):
    return 'ak:' + kind + ':' + b64u(b'\x01' + hashlib.sha256(jcs(unsigned)).digest())


def revision(commit):
    return {k: commit[k] for k in ('commit_id', 'stream_position')}


def source(row, axis, index):
    return {'tag_id': row['event']['event_id'] + ':' + str(index),
            'source_commit': copy.deepcopy(row['commit']),
            'value': copy.deepcopy(row['event']['payload'][axis + '_delta'])}


def target(delta, axis):
    if axis == 'roster':
        value = delta['participant'] if delta['op'] == 'join' else delta
        return jcs([value['actor_id'], value['device_id']])
    value = delta['removal'] if delta['op'] == 'remove_participant' else delta
    action = value.get('action', 'ban')
    return jcs([action, value['actor_id'], value.get('device_id')])


def project(prior, row, axis, index, issuer_key):
    """Reference reducer used only by the specification fixture and lint."""
    entries = copy.deepcopy(prior['entries']) if prior else []
    current = source(row, axis, index)
    delta = current['value']
    key = target(delta, axis)
    if delta['op'] in ('leave', 'restore_participant'):
        if prior is None or delta['expected_revision'] != revision(prior['last_source']['source_commit']):
            raise ValueError('stale axis revision')
        if not any(target(e['value'], axis) == key for e in entries):
            raise ValueError('unknown target')
    entries = [e for e in entries if target(e['value'], axis) != key]
    if delta['op'] in ('join', 'remove_participant'):
        entry = copy.deepcopy(current)
        if axis == 'roster' and 'participant_binding' in delta['participant']:
            entry['participant_signing_key'] = {'public_key_base64url': issuer_key}
        entries.append(entry)
    return {'entries': sorted(entries, key=lambda e: e['tag_id']), 'last_source': current}


def participant(call_id, actor, serial):
    value = {'actor_id': copy.deepcopy(actor), 'device_id': DEVICE, 'joined_at': T,
             'participant_id': 'ak:rtc_participant:01964137-0000-7000-8000-' + f'{serial:012d}',
             'focus_id': 'fra-1', 'media': {'audio': True, 'video': False, 'screen': False}}
    binding = {'expires_at': '2026-09-20T00:10:00.000Z', 'issuer_kid': ISSUER_VM}
    fields = {k: value[k] for k in ('actor_id', 'device_id', 'participant_id', 'focus_id', 'media')}
    fields.update(realm_id=REALM, call_id=call_id, **binding)
    binding['signature'] = b64u(Ed25519PrivateKey.from_private_bytes(KEY_B_SEED).sign(
        b'ak.media.participant_binding.v1\0' + jcs(fields)))
    value['participant_binding'] = binding
    return value


REALM = typed_id('realm', {'fixture': 'call_current_realm'})
STREAM = {'kind': 'realm', 'realm_id': REALM}


def event(payload, position, kind='ak.call.state'):
    created_at = (datetime.fromisoformat(T.replace('Z', '+00:00')) + timedelta(milliseconds=position)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    body = {'kind': kind, 'realm_id': REALM, 'scope_ref': STREAM,
            'actor_id': ACTOR, 'created_at': created_at, 'payload': payload}
    digest = 'sha256:' + hashlib.sha256(jcs(body)).hexdigest()
    binding = {'context': 'ak.event_proof.v1', 'event_digest': digest, 'actor_id': ACTOR,
               'verification_method': PRODUCER_VM, 'created_at': created_at}
    signing_input = refresh_jws_input({'protected_header': {'alg': 'Ed25519'}}, jcs(binding))
    jws = signing_input.decode().split('.')[0] + '..' + b64u(
        Ed25519PrivateKey.from_private_bytes(KEY_B_SEED).sign(signing_input))
    return {**body, 'event_id': typed_id('event', body), 'producer_proof': {
        'kind': 'detached_jws', 'verification_method': PRODUCER_VM,
        'event_digest': digest, 'created_at': created_at, 'jws': jws}}


def sign_snapshot(snapshot):
    snapshot = dict(snapshot, purpose='full_recovery')
    unsigned = {k: v for k, v in snapshot.items() if k not in ('snapshot_id', 'signature')}
    value = {'snapshot_id': typed_id('realm_snapshot', unsigned), **unsigned}
    signature, _ = make_signature('ak.realm_snapshot_signature.v1', value, OLD_VM, KEY_A_SEED)
    return {**value, 'signature': signature}


def build_fixture():
    indices = call_write_indices()
    create = event({'initial_state': 'ringing'}, 1, 'ak.call.create')
    call_id = create['event_id'].replace('ak:event:', 'ak:call:')
    rows, checkpoints, axes = [], [], {}
    previous = typed_id('realm_commit', {'fixture': 'known_genesis_anchor'})
    def append(payload, kind='ak.call.state'):
        nonlocal previous
        pos = len(rows) + 1
        ev = create if kind == 'ak.call.create' else event({'call_id': call_id, **payload}, pos)
        core = {'realm_id': REALM, 'stream_ref': STREAM, 'stream_position': pos,
                'previous_commit_ref': previous, 'event_ref': ev['event_id'],
                'governance_generation': "1", 'authority_ref': create['event_id'], 'committed_at': ev['created_at']}
        commit = {'commit_id': typed_id('realm_commit', core), **core}
        signature, _ = make_signature('ak.realm_commit_signature.v1', commit, OLD_VM, KEY_A_SEED)
        commit['signature'] = signature
        previous = commit['commit_id']
        row = {'commit': commit, 'event': ev}
        rows.append(row)
        if kind == 'ak.call.state':
            for axis, index in indices.items():
                if axis + '_delta' in payload:
                    axes[axis] = project(axes.get(axis), row, axis, index, public_key(KEY_B_SEED))
        entries = [{
            'selector': {'kind': 'call_state', 'call_id': call_id}, 'source_stream_ref': STREAM,
            'revision': revision(rows[0]['commit']), 'value': {'from': None, 'to': 'ringing'},
        }]
        if len(rows) >= 2:
            entries.append({'selector': {'kind': 'call_focus', 'call_id': call_id},
                            'source_stream_ref': STREAM, 'revision': revision(rows[1]['commit']),
                            'value': {'mode': 'sfu', 'session_focus': 'fra-1'}})
        for axis in ('roster', 'moderation'):
            if axis in axes:
                entries.append({'selector': {'kind': 'call_' + axis, 'call_id': call_id},
                                'source_stream_ref': STREAM,
                                'revision': revision(axes[axis]['last_source']['source_commit']),
                                'value': copy.deepcopy(axes[axis])})
        snapshot = sign_snapshot({
            'realm_id': REALM, 'governance_generation': "1",
            'visible_stream_heads': [{'stream_ref': STREAM, **revision(commit)}],
            'current_state_entries': entries,
            'retention_and_history_floor': {'history_access': 'since_join', 'stream_floors': [
                {'stream_ref': STREAM, 'oldest_position': min(3, pos)}]}, 'created_at': ev['created_at'],
        })
        checkpoints.append(snapshot)
    def remove(actor, action):
        removal = {'actor_id': actor, 'action': action,
                   'removed_by': ACTOR['account_id']['principal_id'], 'removed_at': T}
        if action == 'kick':
            removal['device_id'] = DEVICE
        return {'op': 'remove_participant', 'removal': removal}
    append({}, 'ak.call.create')
    append({'focus': {'mode': 'sfu', 'session_focus': 'fra-1'}})
    append({'roster_delta': {'op': 'join', 'participant': participant(call_id, ACTOR, 1)}})
    append({'roster_delta': {'op': 'join', 'participant': participant(call_id, OTHER, 2)}})
    append({'moderation_delta': remove(OTHER, 'ban')})
    append({'moderation_delta': {'op': 'restore_participant', 'actor_id': OTHER,
            'restored_by': ACTOR['account_id']['principal_id'], 'restored_at': T,
            'expected_revision': revision(axes['moderation']['last_source']['source_commit'])}})
    append({'moderation_delta': remove(ACTOR, 'kick')})
    append({'roster_delta': {'op': 'join', 'participant': participant(call_id, ACTOR, 3)}})
    for actor in (OTHER, ACTOR):
        append({'roster_delta': {'op': 'leave', 'actor_id': actor, 'device_id': DEVICE,
                                'expected_revision': revision(axes['roster']['last_source']['source_commit'])}})
    append({'moderation_delta': remove(OTHER, 'ban'),
            'roster_delta': {'op': 'join', 'participant': participant(call_id, ACTOR, 4)}})
    restore_event = event({'call_id': call_id, 'moderation_delta': {
        'op': 'restore_participant', 'actor_id': OTHER,
        'restored_by': ACTOR['account_id']['principal_id'], 'restored_at': T,
        'expected_revision': revision(axes['moderation']['last_source']['source_commit']),
    }}, 12)
    restore_core = {'realm_id': REALM, 'stream_ref': STREAM, 'stream_position': 12,
                    'previous_commit_ref': rows[-1]['commit']['commit_id'],
                    'event_ref': restore_event['event_id'], 'governance_generation': "1",
                    'authority_ref': create['event_id'], 'committed_at': restore_event['created_at']}
    restore_commit = {'commit_id': typed_id('realm_commit', restore_core), **restore_core}
    restore_commit['signature'], _ = make_signature('ak.realm_commit_signature.v1', restore_commit, OLD_VM, KEY_A_SEED)
    followup_rows = {'restore_preserves_kick': {'event': restore_event, 'commit': restore_commit}}
    context = {'account_id': ACTOR['account_id'], 'station_base_url': 'https://station.example',
               'session_epoch': 1, 'realm_id': REALM, 'stream_ref': STREAM, 'call_id': call_id,
               'current_generation': 1, 'known_head': revision(rows[2]['commit'])}
    return {
        'version': '2026-10-24.1', 'suite': 'call_current', 'fixture_kind': 'cryptographic_transcript',
        'runner': {'kind': 'named_suite', 'entrypoint': 'ak.suite.call_state.compact_current.v1'},
        'generated_by': 'python -m tools.generate_call_current_fixture', 'covers_vectors': [VECTOR],
        'description': 'Synthetic full ActorId conformance transcripts. Actual Ed25519 Event, Commit, Snapshot and participant signatures; no live native DID authority, admission transaction, production performance or joint acceptance is claimed. The known genesis anchor and issuer authority keys are explicit fixture inputs. A below-floor current source does not authorize historical Event disclosure.',
        'test_keys': {'governance_public_key_b64u': public_key(KEY_A_SEED),
                      'producer_public_key_b64u': public_key(KEY_B_SEED),
                      'issuer_public_key_b64u': public_key(KEY_B_SEED)},
        'issuer_authority_input': {'verification_method': ISSUER_VM, 'accepted_at': T,
                                   'public_key_base64url': public_key(KEY_B_SEED)},
        'request_context': context, 'response_context': copy.deepcopy(context), 'write_indices': indices,
        'original_rows': rows, 'checkpoints': checkpoints, 'followup_rows': followup_rows,
        'cases': [
            {'name': name, 'vector_id': VECTOR, 'expected': outcome, **({'checkpoint': 7, 'omit_entry': 'non_last_source'} if name in ('omission_unsigned', 'omission_resigned_ordinary_trust_boundary', 'omission_resigned_complete_replica') else {})}
            for name, outcome in [
                ('complete_cold_recovery', 'accept'), ('empty_roster_latest_leave', 'accept'),
                ('empty_moderation_latest_restore', 'accept'), ('unwritten_axis_absent', 'accept'),
                ('two_axes_one_commit_distinct_dots', 'accept'), ('same_revision_same_bytes', 'accept'),
                ('below_floor_current_binding_key', 'accept'), ('kick_old_leg', 'reject'),
                ('kick_later_legal_join', 'accept'), ('restore_preserves_kick', 'accept'),
                ('full_actor_station_isolation', 'accept'), ('stale_leave_revision', 'reject'),
                ('stale_restore_revision', 'reject'), ('partial_value', 'reject'),
                ('accumulated_assertions', 'reject'), ('missing_last_source', 'reject'),
                ('missing_issuer_key', 'reject'), ('wrong_historical_issuer_key', 'reject'),
                ('wrong_binding_actor_station', 'reject'), ('wrong_binding_device', 'reject'),
                ('wrong_binding_participant', 'reject'), ('wrong_binding_media', 'reject'),
                ('wrong_scope', 'reject'), ('wrong_call', 'reject'), ('wrong_source_position', 'reject'),
                ('wrong_source_event', 'reject'), ('wrong_dot_index', 'reject'),
                ('duplicate_target', 'reject'), ('duplicate_position', 'reject'),
                ('source_after_axis_revision', 'reject'), ('revision_not_last_source', 'reject'),
                ('rollback_head', 'reject'), ('same_revision_different_value', 'reject'),
                ('old_tenure_as_current', 'reject'), ('historical_exact_basis', 'accept_historical'),
                ('wrong_historical_ref', 'reject'), ('wrong_authenticated_account', 'reject'),
                ('wrong_local_session', 'reject'), ('revoked_current_permission', 'unavailable'),
                ('missing_source_material', 'unavailable'), ('exact_history_below_floor', 'unavailable'),
                ('producer_signature_tampered', 'reject'), ('commit_signature_tampered', 'reject'),
                ('snapshot_signature_tampered', 'reject'), ('omission_unsigned', 'reject'),
                ('omission_resigned_ordinary_trust_boundary', 'accept'),
                ('omission_resigned_complete_replica', 'reject'), ('wrong_member_complete_replica', 'reject'),
            ]
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    fixture = build_fixture()
    if args.check:
        if json.loads(DEST.read_text(encoding='utf-8')) != fixture:
            raise SystemExit('Call current fixture drift')
        print('Call current deterministic fixture matches')
    else:
        DEST.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        print('Generated Call current cryptographic transcripts')


if __name__ == '__main__':
    main()
