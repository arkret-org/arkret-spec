"""Measure canonical synthetic Call carriers; not a production benchmark."""

import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path

from tools.generate_call_current_fixture import (
    ACTOR, KEY_A_SEED, KEY_B_SEED, OLD_VM, REALM, STREAM, T,
    call_write_indices, event, jcs, make_signature, participant, project, public_key, revision, source, typed_id,
)


def measure():
    create = event({'initial_state': 'ringing'}, 1, 'ak.call.create')
    call_id = create['event_id'].replace('ak:event:', 'ak:call:')
    old = {'roster': [], 'moderation': []}
    compact = {}
    previous = typed_id('realm_commit', {'fixture': 'structural_measurement_anchor'})
    position = 0
    indices = call_write_indices()
    def append(axis, delta):
        nonlocal position, previous
        position += 1
        ev = event({'call_id': call_id, axis + '_delta': delta}, position)
        core = {'realm_id': REALM, 'stream_ref': STREAM, 'stream_position': position,
                'previous_commit_ref': previous, 'event_ref': ev['event_id'],
                'governance_generation': "1", 'authority_ref': create['event_id'], 'committed_at': ev['created_at']}
        commit = {'commit_id': typed_id('realm_commit', core), **core}
        signature, _ = make_signature('ak.realm_commit_signature.v1', commit, OLD_VM, KEY_A_SEED)
        commit['signature'] = signature
        previous = commit['commit_id']
        row = {'event': ev, 'commit': commit}
        index = indices[axis]
        old[axis].append(source(row, axis, index))
        compact[axis] = project(compact.get(axis), row, axis, index, public_key(KEY_B_SEED))
    members = []
    for number in range(10):
        actor = copy.deepcopy(ACTOR)
        actor['account_id']['principal_id'] = f'ak:did_core:web:member{number}.example'
        members.append(actor)
        append('roster', {'op': 'join', 'participant': participant(call_id, actor, number + 1)})
    banned = copy.deepcopy(ACTOR)
    banned['account_id']['principal_id'] = 'ak:did_core:web:banned.example'
    def ban():
        append('moderation', {'op': 'remove_participant', 'removal': {
            'actor_id': banned, 'action': 'ban', 'removed_by': ACTOR['account_id']['principal_id'],
            'removed_at': T}})
    ban()
    measurements = []
    for rounds in range(1001):
        if rounds in (0, 10, 100, 1000):
            full = {axis: {'assertions': sorted(entries, key=lambda e: e['tag_id'])} for axis, entries in old.items()}
            measurements.append({
                'rounds': rounds, 'active_roster': len(compact['roster']['entries']),
                'effective_moderation': len(compact['moderation']['entries']),
                'legacy_full_actor_assertions': sum(len(v) for v in old.values()),
                'legacy_full_actor_value_bytes': sum(len(jcs(v)) for v in full.values()),
                'compact_full_actor_value_bytes': sum(len(jcs(v)) for v in compact.values()),
                'compact_entry_sources': sum(len(v['entries']) for v in compact.values()),
                'compact_commit_carriers_including_axis_tips': sum(len(v['entries']) + 1 for v in compact.values()),
                'compact_unique_commits': len({e['source_commit']['commit_id'] for v in compact.values()
                                             for e in [*v['entries'], v['last_source']]}),
            })
        if rounds == 1000:
            break
        append('roster', {'op': 'leave', 'actor_id': members[0],
                         'device_id': compact['roster']['entries'][0]['value']['participant']['device_id'],
                         'expected_revision': revision(compact['roster']['last_source']['source_commit'])})
        append('roster', {'op': 'join', 'participant': participant(call_id, members[0], rounds + 100)})
        append('moderation', {'op': 'restore_participant', 'actor_id': banned,
                             'restored_by': ACTOR['account_id']['principal_id'], 'restored_at': T,
                             'expected_revision': revision(compact['moderation']['last_source']['source_commit'])})
        ban()
    root = Path(__file__).resolve().parents[1]
    sources = {}
    for path in [Path(__file__), root / 'tools/generate_call_current_fixture.py',
                 root / 'spec/v1/artifacts/schemas/current-state.schema.json',
                 root.parent / 'arkret-rust-sdk/crates/models-collaboration/src/events_payloads/generated/call_contracts.rs']:
        sources[str(path.relative_to(root.parent))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        'kind': 'synthetic_canonical_structure_only', 'identity': 'complete_ActorId_real_DeviceId',
        'measurements': measurements, 'source_sha256': sources,
        'spec_base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'sdk_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root.parent / 'arkret-rust-sdk', text=True).strip(),
        'limits': ['No Rust, PostgreSQL, HTTP, production timing or population measurement.',
                   'Values only, excluding enclosing row, Snapshot signature and transport compression.',
                   'Both use complete original delta and signed Commit; compact includes required issuer public keys and both last_source carriers.',
                   'Synthetic signed source coordinates are not actual accepted Events or native DID authority validation.',
                   'Ordinary current never promises producer envelope replay; producer/MLS checks use their existing authorized carriers.',
                   'Different-target bans and device kicks can grow independently of roster count.'],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = measure()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(result['measurements'], indent=2))


if __name__ == '__main__':
    main()
