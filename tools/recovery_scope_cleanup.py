"""Reference bytes with separated native-model inputs, not production admission."""

import copy
import hashlib
from datetime import datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from tools.content_history import b64, jcs, unb64

INTENT_FIELDS = {'replacement', 'inventory_digest', 'inventory_entry', 'nonce_base64url'}
SOURCE_FIELDS = INTENT_FIELDS | {'destination_service_id', 'delivery_challenge_base64url',
                                 'predecessor_authorization_event_refs',
                                 'verification_method', 'attested_at', 'expires_at', 'signature'}


def digest(value):
    return 'sha256:' + hashlib.sha256(jcs(value)).hexdigest()


def request_intent(attestation):
    return {key: attestation[key] for key in INTENT_FIELDS}


def request_digest(attestation):
    return 'sha256:' + hashlib.sha256(
        b'ak.mls.recovery_scope_cleanup_request.v1\n' + jcs(request_intent(attestation))).hexdigest()


def terminal_source_digest(entry, source_ref, nonce):
    """Commit to the actual native source; registered cascades can cross streams."""
    binding = {'effective_scope': entry['effective_scope'], 'genesis_event_ref': entry['genesis_event_ref'],
               'terminal_event_ref': source_ref, 'nonce_base64url': nonce}
    return 'sha256:' + hashlib.sha256(b'ak.mls.scope_terminal_source.v1\n' + jcs(binding)).hexdigest()


def signing_bytes(value, source=False, delivery=False):
    if source and delivery:
        raise ValueError('signature roles are disjoint')
    domain = (b'ak.mls.recovery_scope_cleanup_authorization.v1\n' if source else
              b'ak.mls.scope_retirement_delivery.v1\n' if delivery else b'ak.mls.scope_retirement.v1\n')
    return domain + jcs({key: val for key, val in value.items() if key != 'signature'})


def sign(value, key, source=False, delivery=False):
    value = copy.deepcopy(value)
    value.pop('signature', None)
    value['signature'] = {'kid': value['verification_method'], 'signature_algorithm': 'Ed25519',
                          'signature': b64(key.sign(signing_bytes(value, source, delivery)))}
    return value


def verify_signature(value, public_key, source=False, delivery=False):
    signature = value['signature']
    if (set(signature) != {'kid', 'signature_algorithm', 'signature'}
            or signature['kid'] != value['verification_method']
            or signature['signature_algorithm'] != 'Ed25519'):
        raise ValueError('signature role or method mismatch')
    Ed25519PublicKey.from_public_bytes(unb64(public_key)).verify(
        unb64(signature['signature']), signing_bytes(value, source, delivery))


def moment(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def canonical_nonce(value):
    decoded = unb64(value)
    if len(decoded) != 32 or b64(decoded) != value:
        raise ValueError('invalid canonical 32-byte nonce')


def qualify_reader(inventory, reader):
    """Current authenticated reader/episode/custody only; no old scope membership."""
    if (not reader['current_authorized'] or not reader['episode_current'] or not reader['inventory_prepared']
            or reader['subject_actor_id'] != inventory['actor_id']
            or reader['authorization_event_ref'] != inventory['authorization_event_ref']
            or reader['role'] not in {'subject_holder', 'agent_custodian'}
            or (reader['role'] == 'agent_custodian' and not reader['custody_current'])):
        raise ValueError('no current reader authority for this subject and episode')


def qualify_source(attestation, inventory, entry, reader, route, now):
    """Current native transport/reader checks before a native intent-ledger lookup.

    Membership eligibility belongs to first finalization, not historical reading.
    These qualified inputs do not implement Service history or native storage.
    """
    from tools.content_history import inventory_digest
    qualify_reader(inventory, reader)
    qualify_scope_governance(inventory, entry, route)
    if set(attestation) != SOURCE_FIELDS:
        raise ValueError('source is not closed')
    verify_signature(attestation, route['origin_public_key'], source=True)
    predecessors = attestation['predecessor_authorization_event_refs']
    if (predecessors != sorted(set(predecessors), key=lambda ref: ref.encode('utf-8'))
            or attestation['replacement']['authorization_event_ref'] in predecessors
            or predecessors != route['predecessor_authorization_event_refs']):
        raise ValueError('predecessor association lacks complete native source qualification')
    if (not route['governance_active'] or not route['origin_native_qualified']
            or route['origin_service_id'] != inventory['replacement']['actor_id']['account_id']['station_id']
            or attestation['verification_method'] != route['origin_verification_method']
            or attestation['replacement'] != inventory['replacement']
            or attestation['inventory_digest'] != inventory_digest(inventory)
            or attestation['inventory_entry'] != entry
            or attestation['destination_service_id'] != route['governance_station_id']):
        raise ValueError('source does not bind current origin, route and exact inventory')
    for key in ('nonce_base64url', 'delivery_challenge_base64url'):
        canonical_nonce(attestation[key])
    if not moment(attestation['attested_at']) <= moment(now) < moment(attestation['expires_at']):
        raise ValueError('source expired or future-dated')
    if not 0 < (moment(attestation['expires_at']) - moment(attestation['attested_at'])).total_seconds() <= 300:
        raise ValueError('source window exceeds 300 seconds')


def verify_retirement(result, attestation, inventory, entry, historical):
    """Original finalization facts and method keys only; no current membership/route."""
    from tools.content_history import inventory_digest
    if set(result) != {'state', 'effective_scope', 'genesis_event_ref', 'retirement_proof'}:
        raise ValueError('retirement result is not closed')
    qualify_scope_governance(inventory, entry, historical)
    proof = result['retirement_proof']
    state = result['state']
    if state not in {'removed', 'terminated'} or state != proof['state']:
        raise ValueError('wrong retirement branch')
    expected = {'state', 'replacement', 'inventory_digest', 'inventory_entry_digest', 'request_digest',
                'effective_scope', 'genesis_event_ref', 'governance_station_id', 'governance_generation',
                'scope_cut', 'group_state_ref', 'epoch', 'nonce_base64url', 'attested_at', 'verification_method', 'signature'}
    expected.add('remaining_old_leaf_count' if state == 'removed' else 'terminal_source_digest')
    if set(proof) != expected:
        raise ValueError('retirement proof is not closed')
    verify_signature(proof, historical['governor_public_key'])
    original = historical['authorization']
    if set(original) != SOURCE_FIELDS:
        raise ValueError('original source is not closed')
    verify_signature(original, historical['origin_public_key'], source=True)
    if (proof['verification_method'] != historical['governor_verification_method']
            or original['verification_method'] != historical['origin_verification_method']
            or not historical['native_source_complete'] or historical['eligible_at_completion']
            or not historical['episode_fenced'] or historical['pending_admission_count'] != 0
            or request_intent(original) != request_intent(attestation)
            or original['predecessor_authorization_event_refs'] != attestation['predecessor_authorization_event_refs']
            or original['destination_service_id'] != historical['governance_station_id']):
        raise ValueError('original finalization authority or intent mismatch')
    for key in ('effective_scope', 'genesis_event_ref'):
        if result[key] != entry[key] or proof[key] != entry[key]:
            raise ValueError('retirement selected another scope')
    if (proof['replacement'] != inventory['replacement']
            or proof['inventory_digest'] != inventory_digest(inventory)
            or proof['inventory_entry_digest'] != digest(entry)
            or proof['request_digest'] != request_digest(attestation)
            or proof['nonce_base64url'] != attestation['nonce_base64url']):
        raise ValueError('proof does not bind the immutable inventory and intent')
    for key in ('governance_station_id', 'governance_generation', 'scope_cut', 'group_state_ref', 'epoch'):
        if proof[key] != historical[key]:
            raise ValueError('original governance or cut mismatch')
    if not moment(original['attested_at']) <= moment(proof['attested_at']) < moment(original['expires_at']):
        raise ValueError('proof finalized outside its original authorization window')
    if not 0 < (moment(original['expires_at']) - moment(original['attested_at'])).total_seconds() <= 300:
        raise ValueError('original source window exceeds 300 seconds')
    for key in ('nonce_base64url', 'delivery_challenge_base64url'):
        canonical_nonce(original[key])
    if state == 'removed':
        if proof['remaining_old_leaf_count'] != 0 or historical['old_endpoint_count'] != 0:
            raise ValueError('displaced endpoints existed at finalization')
    elif (not historical['terminal_irreversible'] or not historical['terminal_all_writes_blocked']
          or not historical['terminal_source_native_qualified']
          or historical['terminal_source_digest'] != terminal_source_digest(
              entry, historical['terminal_source_ref'], attestation['nonce_base64url'])
          or proof['terminal_source_digest'] != historical['terminal_source_digest']):
        raise ValueError('no original irreversible terminal source')
    return proof


def verify_delivery(peer, authorization, route, now):
    """Fresh current-governor delivery, separate from the immutable historical proof."""
    if set(peer) != {'cleanup', 'delivery_attestation'}:
        raise ValueError('terminal delivery wrapper is not closed')
    proof = peer['cleanup']['retirement_proof']
    delivery = peer['delivery_attestation']
    expected_fields = {'request_digest', 'authorization_digest', 'proof_digest', 'recipient_service_id',
                       'governance_station_id', 'governance_generation', 'nonce_base64url',
                       'delivery_challenge_base64url', 'attested_at', 'expires_at', 'verification_method', 'signature'}
    if set(delivery) != expected_fields:
        raise ValueError('delivery attestation is not closed')
    verify_signature(delivery, route['governor_public_key'], delivery=True)
    if (not route['governance_active'] or not route['proof_and_fence_retained']
            or digest(proof) not in route['retained_proof_digests']
            or delivery['verification_method'] != route['governor_verification_method']
            or delivery['governance_station_id'] != route['governance_station_id']
            or delivery['governance_generation'] != route['governance_generation']
            or delivery['recipient_service_id'] != route['origin_service_id']
            or delivery['request_digest'] != request_digest(authorization)
            or delivery['authorization_digest'] != digest(authorization)
            or delivery['proof_digest'] != digest(proof)
            or any(delivery[key] != authorization[key] for key in ('nonce_base64url', 'delivery_challenge_base64url'))):
        raise ValueError('delivery route, import, audience, intent or challenge mismatch')
    issued, expiry = moment(delivery['attested_at']), moment(delivery['expires_at'])
    if (not moment(authorization['attested_at']) <= issued < expiry <= moment(authorization['expires_at'])
            or not issued <= moment(now) < expiry
            or not 0 < (expiry - issued).total_seconds() <= 300):
        raise ValueError('delivery is not fresh within its current source window')
    return delivery


def verify_self_retirement(response, authorization, inventory, entry, reader, historical, route, now):
    """Compose current reader, original proof and current delivery with two key projections."""
    qualify_source(authorization, inventory, entry, reader, route, now)
    if response == {'delivery': {'state': 'pending'}}:
        return None
    if set(response) != {'delivery', 'attestor_signing_key', 'delivery_signing_key'}:
        raise ValueError('self delivery wrapper is not closed')
    peer = response['delivery']
    proof = verify_retirement(peer['cleanup'], authorization, inventory, entry, historical)
    delivery = verify_delivery(peer, authorization, route, now)
    expected_old = {'proof_digest': digest(proof), 'verification_method': proof['verification_method'],
                    'public_key_base64url': historical['governor_public_key']}
    expected_current = {'delivery_digest': digest(delivery), 'verification_method': delivery['verification_method'],
                        'public_key_base64url': route['governor_public_key']}
    if response['attestor_signing_key'] != expected_old or response['delivery_signing_key'] != expected_current:
        raise ValueError('self projections do not bind the two exact signatures')
    return proof


class FirstFinalizationRejected(ValueError):
    """A deterministic domain outcome after current/native qualification."""

    def __init__(self):
        super().__init__('failed_precondition')


def reserve_intent(ledger, authorization):
    """Durable minimal binding, after native qualification and before domain evaluation.

    The origin uses this CAS across all destinations before signing/sending a
    source; each governor retains the same binding locally. No scope fence,
    obligation or terminal is created by this reservation.
    """
    replacement = authorization['replacement']
    identity = (jcs(replacement['actor_id']), replacement['authorization_event_ref'], authorization['nonce_base64url'])
    intent = request_digest(authorization)
    intent_bytes = jcs(request_intent(authorization))
    predecessors = copy.deepcopy(authorization['predecessor_authorization_event_refs'])
    if identity in ledger:
        row = ledger[identity]
        if (row['request_digest'] != intent or row['intent_bytes'] != intent_bytes
                or row['predecessor_authorization_event_refs'] != predecessors):
            raise ValueError('duplicate_conflict')
    else:
        ledger[identity] = {'request_digest': intent, 'intent_bytes': intent_bytes,
                            'predecessor_authorization_event_refs': predecessors, 'cleanup': None}
    return ledger[identity]


def settle_intent(ledger, authorization, first_eligible, candidate):
    """Native-model inner CAS; a domain rejection retains the reserved I."""
    row = reserve_intent(ledger, authorization)
    if row['cleanup'] is not None:
        return copy.deepcopy(row['cleanup'])
    if first_eligible:
        raise FirstFinalizationRejected()
    row['cleanup'] = copy.deepcopy(candidate)
    return copy.deepcopy(candidate) if candidate is not None else {'state': 'pending'}


def transport_replay(ledger, principal, operation, body, authorized, compute):
    """Cache domain outcomes after caller current/window checks, not arbitrary failures."""
    if not authorized:
        raise ValueError('not_found')
    encoded = jcs(body)
    identity = (principal, operation, digest(body))
    if identity in ledger:
        row = ledger[identity]
        if row['body'] != encoded:
            raise ValueError('duplicate_conflict')
        if row.get('failure') == 'failed_precondition':
            raise FirstFinalizationRejected()
        return copy.deepcopy(row['response'])
    try:
        response = compute()
    except FirstFinalizationRejected:
        ledger[identity] = {'body': encoded, 'failure': 'failed_precondition'}
        raise
    ledger[identity] = {'body': encoded, 'response': copy.deepcopy(response)}
    return response


def observe_delivery(ledger, authorization, compute):
    """Bind a challenge's domain outcome without freezing settlement of stable I."""
    identity = (request_digest(authorization), authorization['delivery_challenge_base64url'])
    source = digest(authorization)
    if identity in ledger:
        row = ledger[identity]
        if row['authorization_digest'] != source:
            raise ValueError('duplicate_conflict')
        if row.get('failure') == 'failed_precondition':
            raise FirstFinalizationRejected()
        return copy.deepcopy(row['observation'])
    try:
        observation = compute()
    except FirstFinalizationRejected:
        ledger[identity] = {'authorization_digest': source, 'failure': 'failed_precondition'}
        raise
    ledger[identity] = {'authorization_digest': source, 'observation': copy.deepcopy(observation)}
    return observation


def business_send_allowed(blockers, ordinary_gates, terminal=False):
    """Temporary episode blockers and permanent terminal lifecycle are independent."""
    return ordinary_gates and not blockers and not terminal


def fixture(replacement, entry, pcr_cut, scope_kind='ordinary_realm', terminal_source_ref=None):
    """Deterministic multi-signature transcript with explicit native-model assumptions."""
    from tools.content_history import inventory_digest
    replacement = copy.deepcopy(replacement)
    replacement['actor_id']['account_id']['station_id'] = 'ak:did_core:web:origin.example'
    origin = Ed25519PrivateKey.from_private_bytes(bytes([234]) * 32)
    governor = Ed25519PrivateKey.from_private_bytes(bytes([235]) * 32)
    successor = Ed25519PrivateKey.from_private_bytes(bytes([236]) * 32)
    public = lambda key: b64(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    origin_id = replacement['actor_id']['account_id']['station_id']
    origin_method = 'did:web:origin.example#retirement'
    governor_id, governor_method = 'ak:did_core:web:governor.example', 'did:web:governor.example#retirement'
    if scope_kind in {'human_pcr', 'user_managed_agent_pcr'}:
        governor_id, governor_method = origin_id, 'did:web:origin.example#scope-retirement'
    scope_cut = {**copy.deepcopy(pcr_cut), 'stream_ref': copy.deepcopy(entry['effective_scope']),
                 'event_id': entry['base_group_state_ref'],
                 'commit_id': 'ak:realm_commit:' + b64(b'\x01' + bytes([211]) * 32), 'stream_position': 17}
    if terminal_source_ref is None:
        if entry['effective_scope']['kind'] == 'sidecar':
            raise ValueError('Sidecar terminal requires its actual upstream source')
        terminal_source_ref = scope_cut
    scope_authority = {'kind': scope_kind, 'native_source_complete': True,
                       'effective_scope': copy.deepcopy(entry['effective_scope']),
                       'genesis_event_ref': entry['genesis_event_ref'], 'inception_governor': governor_id}
    inventory = {'actor_id': replacement['actor_id'], 'replacement': replacement,
                 'authorization_event_ref': replacement['authorization_event_ref'], 'pcr_cut': pcr_cut, 'entries': [entry]}
    authorization = sign({'replacement': replacement, 'inventory_digest': inventory_digest(inventory),
                          'inventory_entry': entry, 'destination_service_id': governor_id,
                          'predecessor_authorization_event_refs': [],
                          'nonce_base64url': b64(bytes([93]) * 32), 'delivery_challenge_base64url': b64(bytes([94]) * 32),
                          'verification_method': origin_method, 'attested_at': '2026-11-09T00:00:00.000Z',
                          'expires_at': '2026-11-09T00:05:00.000Z'}, origin, source=True)
    historical = {'authorization': authorization, 'origin_public_key': public(origin),
                  'origin_verification_method': origin_method, 'governor_public_key': public(governor),
                  'governor_verification_method': governor_method, 'eligible_at_completion': False,
                  'native_source_complete': True, 'episode_fenced': True, 'pending_admission_count': 0,
                  'old_endpoint_count': 0, 'governance_station_id': governor_id, 'governance_generation': 0,
                  'scope_authority': scope_authority, 'handoff_native_qualified': False,
                  'scope_cut': scope_cut, 'group_state_ref': entry['base_group_state_ref'], 'epoch': entry['epoch'],
                  'terminal_irreversible': True, 'terminal_all_writes_blocked': True,
                  'terminal_source_ref': copy.deepcopy(terminal_source_ref), 'terminal_source_native_qualified': True,
                  'terminal_source_digest': terminal_source_digest(entry, terminal_source_ref, authorization['nonce_base64url'])}
    removed = {'state': 'removed', 'replacement': replacement, 'inventory_digest': inventory_digest(inventory),
               'inventory_entry_digest': digest(entry), 'request_digest': request_digest(authorization),
               'effective_scope': entry['effective_scope'], 'genesis_event_ref': entry['genesis_event_ref'],
               'governance_station_id': governor_id, 'governance_generation': 0, 'scope_cut': scope_cut,
               'group_state_ref': entry['base_group_state_ref'], 'epoch': entry['epoch'],
               'nonce_base64url': authorization['nonce_base64url'], 'attested_at': '2026-11-09T00:00:01.000Z',
               'verification_method': governor_method, 'remaining_old_leaf_count': 0}
    terminated = copy.deepcopy(removed)
    terminated['state'] = 'terminated'
    terminated.pop('remaining_old_leaf_count')
    terminated['terminal_source_digest'] = historical['terminal_source_digest']
    results = {state: {'state': state, 'effective_scope': entry['effective_scope'],
                       'genesis_event_ref': entry['genesis_event_ref'], 'retirement_proof': sign(proof, governor)}
               for state, proof in [('removed', removed), ('terminated', terminated)]}
    reader = {'subject_actor_id': inventory['actor_id'], 'authorization_event_ref': inventory['authorization_event_ref'],
              'role': 'subject_holder', 'current_authorized': True, 'episode_current': True,
              'inventory_prepared': True, 'custody_current': False}
    route = {'origin_service_id': origin_id, 'origin_verification_method': origin_method, 'origin_public_key': public(origin),
             'predecessor_authorization_event_refs': [],
             'origin_native_qualified': True, 'governance_active': True, 'governance_station_id': governor_id,
             'scope_authority': scope_authority, 'handoff_native_qualified': False,
             'governance_generation': 0, 'governor_verification_method': governor_method, 'governor_public_key': public(governor),
             'proof_and_fence_retained': True, 'retained_proof_digests': [digest(row['retirement_proof']) for row in results.values()]}

    def deliveries(source, current, signer, at, expiry):
        peers, selves = {}, {}
        for state, cleanup in results.items():
            proof = cleanup['retirement_proof']
            attestation = sign({'request_digest': request_digest(source), 'authorization_digest': digest(source),
                                'proof_digest': digest(proof), 'recipient_service_id': origin_id,
                                'governance_station_id': current['governance_station_id'],
                                'governance_generation': current['governance_generation'],
                                'nonce_base64url': source['nonce_base64url'],
                                'delivery_challenge_base64url': source['delivery_challenge_base64url'],
                                'attested_at': at, 'expires_at': expiry,
                                'verification_method': current['governor_verification_method']}, signer, delivery=True)
            peers[state] = {'cleanup': cleanup, 'delivery_attestation': attestation}
            selves[state] = {'delivery': peers[state], 'attestor_signing_key': {
                'proof_digest': digest(proof), 'verification_method': governor_method, 'public_key_base64url': public(governor)},
                'delivery_signing_key': {'delivery_digest': digest(attestation),
                    'verification_method': current['governor_verification_method'], 'public_key_base64url': current['governor_public_key']}}
        return peers, selves

    peers, selves = deliveries(authorization, route, governor, '2026-11-09T00:00:02.000Z', '2026-11-09T00:05:00.000Z')
    after = {**route, 'handoff_native_qualified': True, 'governance_station_id': 'ak:did_core:web:successor.example', 'governance_generation': 1,
             'governor_verification_method': 'did:web:successor.example#retirement', 'governor_public_key': public(successor)}
    renewed = sign({**authorization, 'destination_service_id': after['governance_station_id'],
                    'delivery_challenge_base64url': b64(bytes([95]) * 32), 'attested_at': '2026-11-09T00:06:00.000Z',
                    'expires_at': '2026-11-09T00:11:00.000Z'}, origin, source=True)
    later_peers, later_selves = deliveries(renewed, after, successor, '2026-11-09T00:06:01.000Z', '2026-11-09T00:11:00.000Z')
    return {'inventory': inventory, 'authorization': authorization, 'results': results, 'reader_authority': reader,
            'historical_completion_basis': historical, 'current_delivery': route, 'deliveries': peers, 'self_deliveries': selves,
            'handoff': {'authorization': renewed, 'current_delivery': after, 'deliveries': later_peers, 'self_deliveries': later_selves},
            'origin_signing_seed_hex': (bytes([234]) * 32).hex(), 'governor_signing_seed_hex': (bytes([235]) * 32).hex(),
            'successor_signing_seed_hex': (bytes([236]) * 32).hex(),
            'authorization_signing_hex': signing_bytes(authorization, source=True).hex(),
            'removed_signing_hex': signing_bytes(results['removed']['retirement_proof']).hex(),
            'terminated_signing_hex': signing_bytes(results['terminated']['retirement_proof']).hex(),
            'delivery_signing_hex': signing_bytes(peers['removed']['delivery_attestation'], delivery=True).hex(),
            'handoff_delivery_signing_hex': signing_bytes(later_peers['removed']['delivery_attestation'], delivery=True).hex(),
            'qualification': 'Primitive signatures and separated native-model assumptions only; no real Station history, '
                             'RFC admission, durable transaction, physical import or production recovery is claimed.'}


def qualify_scope_governance(inventory, entry, facts):
    """Consume explicit qualified native-model origin facts, never infer eligibility from a signature.

    Child scopes follow their natively qualified parent Realm, never an
    independently chosen governor. This reference does not implement a native
    genesis verifier or an
    Organization PCR eligibility path. Unknown origins fail closed.
    """
    origin = facts['scope_authority']
    if (not origin['native_source_complete']
            or origin['effective_scope'] != entry['effective_scope']
            or origin['genesis_event_ref'] != entry['genesis_event_ref']
            or ('scope_cut' in facts and facts['scope_cut']['stream_ref'] != entry['effective_scope'])):
        raise ValueError('scope has no exact accepted native origin')
    kind = origin['kind']
    is_subject_pcr = entry['effective_scope'] == inventory['pcr_cut']['stream_ref']
    governing_realm_id = entry['effective_scope']['realm_id']
    if not governing_realm_id or entry['effective_scope']['kind'] not in {'realm', 'circle', 'sidecar'}:
        raise ValueError('scope has no exact native governing Realm mapping')
    parent_is_subject_pcr = governing_realm_id == inventory['pcr_cut']['stream_ref']['realm_id']
    fixed_station = inventory['replacement']['actor_id']['account_id']['station_id']
    governor, generation = facts['governance_station_id'], facts['governance_generation']
    if kind == 'ordinary_realm':
        if parent_is_subject_pcr:
            raise ValueError('ordinary Realm classification cannot replace a PCR origin')
        if (generation < 0 or (generation == 0 and governor != origin['inception_governor'])
                or (generation > 0 and not facts['handoff_native_qualified'])):
            raise ValueError('ordinary Realm handoff is not natively qualified')
    elif kind in {'human_pcr', 'user_managed_agent_pcr', 'direct'}:
        if (generation != 0 or governor != origin['inception_governor']
                or (kind != 'direct' and governor != fixed_station)
                or (kind == 'human_pcr' and not is_subject_pcr)
                or (kind in {'human_pcr', 'user_managed_agent_pcr'} and entry['effective_scope']['kind'] != 'realm')
                or (kind == 'direct' and parent_is_subject_pcr)):
            raise ValueError('fixed native origin forbids governance migration')
    else:
        raise ValueError('unknown native scope origin')


def accept_self_retirement(ledger, response, authorization, inventory, entry, reader, historical, route, now):
    """Model an atomic protected-store write after successful live source consumption."""
    proof = verify_self_retirement(response, authorization, inventory, entry, reader, historical, route, now)
    if proof is None:
        raise ValueError('pending is not a durable retirement acceptance')
    identity = digest({'authorization': authorization, 'response': response})
    candidate = {'authorization': copy.deepcopy(authorization), 'response': copy.deepcopy(response),
                 'inventory_digest': digest(inventory), 'entry_digest': digest(entry),
                 'accepted_at': now, 'historical': copy.deepcopy(historical), 'route': copy.deepcopy(route)}
    if identity in ledger:
        if any(ledger[identity][key] != candidate[key] for key in candidate if key != 'accepted_at'):
            raise ValueError('acceptance binding conflict')
    else:
        ledger[identity] = candidate
    return identity


def resume_accepted_retirement(ledger, identity, inventory, entry, reader):
    """Reverify the protected original transcript at its durable acceptance time.

    The ledger is a protected local-store model, not a caller-supplied portable
    proof. Current reader/episode/custody remain independent prerequisites.
    """
    qualify_reader(inventory, reader)
    if identity not in ledger:
        raise ValueError('no durable acceptance; a fresh live delivery is required')
    row = ledger[identity]
    if (row['inventory_digest'] != digest(inventory) or row['entry_digest'] != digest(entry)
            or identity != digest({'authorization': row['authorization'], 'response': row['response']})):
        raise ValueError('durable acceptance binds another inventory or transcript')
    return verify_self_retirement(row['response'], row['authorization'], inventory, entry, reader,
                                  row['historical'], row['route'], row['accepted_at'])



def scope_episode_identity(authorization):
    entry, replacement = authorization['inventory_entry'], authorization['replacement']
    return (jcs(replacement['actor_id']), replacement['authorization_event_ref'],
            jcs(entry['effective_scope']), entry['genesis_event_ref'])


def settle_retirement_for_scope(terminals, ledger, authorization, first_eligible, candidate):
    """Shared native-model scope/episode CAS; the narrow command never returns roots."""
    identity = scope_episode_identity(authorization)
    if identity in terminals:
        terminal = terminals[identity]
        if terminal['inventory_digest'] != authorization['inventory_digest']:
            raise ValueError('duplicate_conflict')
        if terminal['cleanup']['state'] == 'rekeyed':
            reserve_intent(ledger, authorization)
            raise FirstFinalizationRejected()
        if terminal['cleanup']['retirement_proof']['request_digest'] != request_digest(authorization):
            raise ValueError('duplicate_conflict')
        if not any(row['request_digest'] == request_digest(authorization)
                   and row['intent_bytes'] == jcs(request_intent(authorization))
                   and row['cleanup'] == terminal['cleanup'] for row in ledger.values()):
            raise ValueError('revision_unavailable')
    cleanup = settle_intent(ledger, authorization, first_eligible, candidate)
    if cleanup.get('state') in {'removed', 'terminated'}:
        terminal = {'inventory_digest': authorization['inventory_digest'], 'cleanup': copy.deepcopy(cleanup)}
        if identity in terminals and terminals[identity] != terminal:
            raise ValueError('duplicate_conflict')
        terminals[identity] = terminal
    return cleanup


def complete_scope_rekey(terminals, blockers, authorization, result, native):
    """An already qualified normal External Commit finalizes exactly one scope episode.

    Qualified facts model the native RFC, backup durability and current scope
    gates. This helper does not perform those verifiers or create a Commit.
    """
    entry = authorization['inventory_entry']
    if (result.get('state') != 'rekeyed' or result.get('remaining_old_leaf_count') != 0
            or result.get('effective_scope') != entry['effective_scope']
            or result.get('genesis_event_ref') != entry['genesis_event_ref']
            or not result.get('root_refs') or not result.get('backup_refs')
            or result.get('winning_commit') != native['winning_commit']
            or result['winning_commit']['stream_ref'] != entry['effective_scope']
            or not native['current_eligible'] or not native['accepted_rfc_complete']
            or not native['all_old_endpoints_removed'] or not native['roots_and_backups_durable']
            or native['replacement'] != authorization['replacement']
            or native['epoch'] <= int(entry['epoch'])):
        raise ValueError('rekeyed completion is not natively qualified')
    identity = scope_episode_identity(authorization)
    terminal = {'inventory_digest': authorization['inventory_digest'], 'cleanup': copy.deepcopy(result)}
    if identity in terminals and terminals[identity] != terminal:
        raise ValueError('duplicate_conflict')
    # The following models one durable atomic transaction. Other episodes and
    # ordinary policy gates remain independent; the endpoint fence is retained.
    terminals[identity] = terminal
    blockers.discard(identity)
    return copy.deepcopy(result)


def satisfy_predecessor_obligation(terminals, obligations, satisfactions, blockers,
                                   predecessor, successor, native):
    """Private native audit CAS, never an old-episode cleanup or a reader permit.

    Inputs model complete retained native sources and causality, not network
    attestations or caller assertions. The source terminal must already have
    passed its normal RFC/retirement verifiers. Each predecessor is settled
    separately, even when one successor terminal covers several predecessors.
    """
    old, new = scope_episode_identity(predecessor), scope_episode_identity(successor)
    if (old == new or old[0] != new[0] or old[2:] != new[2:]
            or old[1] not in successor['predecessor_authorization_event_refs']
            or old not in obligations or old in terminals or new not in terminals):
        raise ValueError('no exact pending predecessor and qualified successor terminal')
    obligation, terminal = obligations[old], terminals[new]
    cleanup = terminal['cleanup']
    source_cut = (cleanup['winning_commit'] if cleanup['state'] == 'rekeyed'
                  else cleanup['retirement_proof']['scope_cut'])
    chain = native['supersedes_chain']
    if (obligation['request_digest'] != request_digest(predecessor)
            or obligation['intent_bytes'] != jcs(request_intent(predecessor))
            or terminal['inventory_digest'] != successor['inventory_digest']
            or native['subject_actor_id'] != successor['replacement']['actor_id']
            or native['effective_scope'] != successor['inventory_entry']['effective_scope']
            or native['genesis_event_ref'] != successor['inventory_entry']['genesis_event_ref']
            or native['source_cleanup_digest'] != digest(terminal['cleanup'])
            or native['coverage_source_ref'] != source_cut
            or not native['source_native_qualified'] or not native['source_facts_durable']
            or not native['supersedes_chain_qualified'] or len(chain) < 2
            or len(set(chain)) != len(chain) or chain[0] != old[1] or chain[-1] != new[1]
            or not set(obligation['endpoint_ids']) <= set(native['covered_endpoint_ids'])
            or not set(obligation['admission_ids']) <= set(native['closed_admission_ids'])
            or not set(obligation['endpoint_ids']) <= set(native['retained_fence_endpoint_ids'])
            or not native['all_admission_paths_closed']):
        raise ValueError('predecessor coverage, fences or native causality unavailable')
    state = terminal['cleanup']['state']
    if ((state in {'rekeyed', 'removed'} and not native['all_old_endpoints_removed'])
            or (state == 'terminated' and (not native['terminal_irreversible']
                                          or not native['terminal_all_writes_blocked']))
            or state not in {'rekeyed', 'removed', 'terminated'}):
        raise ValueError('source does not safely satisfy predecessor obligation')
    record = {'predecessor_request_digest': request_digest(predecessor),
              'successor_authorization_event_ref': new[1],
              'source_cleanup_digest': native['source_cleanup_digest'], 'source_state': state,
              'source_scope_cut': copy.deepcopy(source_cut),
              'supersedes_chain': copy.deepcopy(chain),
              'endpoint_ids': sorted(set(obligation['endpoint_ids'])),
              'admission_ids': sorted(set(obligation['admission_ids']))}
    if old in satisfactions:
        if satisfactions[old] != record:
            raise ValueError('duplicate_conflict')
        return copy.deepcopy(satisfactions[old])
    # One native transaction persists the audit record and releases only this
    # obligation. Immutable old results, observations and fences are untouched.
    satisfactions[old] = record
    blockers.discard(old)
    return copy.deepcopy(record)


def successor_completion_ready(terminals, obligations, satisfactions, successor, predecessors):
    """Qualified complete census gates outward completion, not a new wire flag.

    The predecessor list must come from the complete native census, not a
    client selector. No audit record is delivered to a reader by this helper.
    """
    current = scope_episode_identity(successor)
    refs = sorted(old['replacement']['authorization_event_ref'] for old in predecessors)
    if (current not in terminals or refs != successor['predecessor_authorization_event_refs']):
        return False
    for old in predecessors:
        identity = scope_episode_identity(old)
        if identity == current or identity[0] != current[0] or identity[2:] != current[2:]:
            return False
        own_terminal = terminals.get(identity)
        if own_terminal is not None and own_terminal['inventory_digest'] == old['inventory_digest']:
            continue
        if identity not in obligations or identity not in satisfactions:
            return False
    return True


def finalize_successor_rekey(terminals, obligations, satisfactions, blockers,
                             successor, result, rekey_native, predecessor_sources):
    """Stage all native checks before the terminal/coverage atomic publication.

    predecessor_sources is the complete trusted census paired with historical
    coverage at this result's exact cut. Copies model a transaction rollback,
    not a production persistence implementation.
    """
    staged_terminals, staged_records, staged_blockers = copy.deepcopy((terminals, satisfactions, blockers))
    refs = sorted(old['replacement']['authorization_event_ref'] for old, _ in predecessor_sources)
    if refs != successor['predecessor_authorization_event_refs']:
        raise ValueError('revision_unavailable: incomplete signed predecessor census')
    complete_scope_rekey(staged_terminals, staged_blockers, successor, result, rekey_native)
    for predecessor, native in predecessor_sources:
        old = scope_episode_identity(predecessor)
        if old not in staged_terminals:
            satisfy_predecessor_obligation(staged_terminals, obligations, staged_records, staged_blockers,
                                            predecessor, successor, native)
    if not successor_completion_ready(staged_terminals, obligations, staged_records, successor,
                                      [old for old, _ in predecessor_sources]):
        raise ValueError('revision_unavailable')
    terminals.clear()
    terminals.update(staged_terminals)
    satisfactions.clear()
    satisfactions.update(staged_records)
    blockers.clear()
    blockers.update(staged_blockers)
    return copy.deepcopy(result)


def combination_fixture(base):
    """Signed combination inputs; endpoint/admission IDs are native-model handles."""
    from tools.content_history import inventory_digest
    event = lambda seed: 'ak:event:' + b64(b'\x01' + bytes([seed]) * 32)
    origin = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(base['origin_signing_seed_hex']))
    inventory = copy.deepcopy(base['inventory'])
    entry = inventory['entries'][0]
    other = {**copy.deepcopy(entry), 'effective_scope': {'kind': 'realm',
             'realm_id': 'ak:realm:' + b64(b'\x01' + bytes([230]) * 32)},
             'genesis_event_ref': event(231), 'base_group_state_ref': event(232)}
    inventory['entries'] = sorted([entry, other], key=lambda row: jcs({
        'effective_scope': row['effective_scope'], 'genesis_event_ref': row['genesis_event_ref']}))
    first = sign({**base['authorization'], 'inventory_digest': inventory_digest(inventory)}, origin, source=True)
    second = sign({**first, 'inventory_entry': other,
                   'delivery_challenge_base64url': b64(bytes([102]) * 32)}, origin, source=True)
    other_route = fixture(inventory['replacement'], other, inventory['pcr_cut'])['current_delivery']
    replacement = copy.deepcopy(base['inventory']['replacement'])
    replacement['authorization_event_ref'] = event(233)
    replacement['endpoint']['device_id'] = 'ak:device:019a0000-0000-7000-8000-000000000003'
    key = Ed25519PrivateKey.from_private_bytes(bytes([240]) * 32)
    replacement['signature_key_base64url'] = b64(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    cut = {**base['inventory']['pcr_cut'], 'event_id': replacement['authorization_event_ref'],
           'commit_id': 'ak:realm_commit:' + b64(b'\x01' + bytes([234]) * 32), 'stream_position': 3}
    later = fixture(replacement, entry, cut)
    predecessor_refs = [base['authorization']['replacement']['authorization_event_ref']]
    source = sign({**later['authorization'], 'predecessor_authorization_event_refs': predecessor_refs,
                   'attested_at': '2026-11-09T00:10:00.000Z',
                   'expires_at': '2026-11-09T00:15:00.000Z'}, origin, source=True)
    historical = {**later['historical_completion_basis'], 'authorization': source}
    governor = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(later['governor_signing_seed_hex']))
    retired = copy.deepcopy(later['results'])
    for value in retired.values():
        value['retirement_proof'] = sign({**value['retirement_proof'],
            'attested_at': '2026-11-09T00:10:01.000Z'}, governor)
    winning = {**historical['scope_cut'], 'stream_position': 19,
               'event_id': event(235), 'commit_id': 'ak:realm_commit:' + b64(b'\x01' + bytes([236]) * 32)}
    rekeyed = {'state': 'rekeyed', 'effective_scope': entry['effective_scope'],
               'genesis_event_ref': entry['genesis_event_ref'], 'winning_commit': winning,
               'remaining_old_leaf_count': 0, 'root_refs': ['sha256:' + '1' * 64],
               'backup_refs': ['ak:backup:019b0000-0000-7000-8000-000000000001']}
    rekey_native = {'winning_commit': winning, 'current_eligible': True, 'accepted_rfc_complete': True,
                    'all_old_endpoints_removed': True, 'roots_and_backups_durable': True,
                    'replacement': replacement, 'epoch': int(entry['epoch']) + 1}
    obligation = {'request_digest': request_digest(base['authorization']),
                  'intent_bytes_hex': jcs(request_intent(base['authorization'])).hex(),
                  'endpoint_ids': ['old-native-endpoint', 'other-displaced-native-endpoint'],
                  'admission_ids': ['issued-claim', 'inflight-outgoing', 'claimed-not-consumed']}
    coverage = {'subject_actor_id': replacement['actor_id'], 'effective_scope': entry['effective_scope'],
                'genesis_event_ref': entry['genesis_event_ref'], 'source_cleanup_digest': digest(rekeyed),
                'coverage_source_ref': winning,
                'source_native_qualified': True, 'source_facts_durable': True,
                'supersedes_chain': [base['authorization']['replacement']['authorization_event_ref'],
                                     replacement['authorization_event_ref']],
                'supersedes_chain_qualified': True,
                'covered_endpoint_ids': obligation['endpoint_ids'] + ['displaced-D1'],
                'closed_admission_ids': obligation['admission_ids'],
                'retained_fence_endpoint_ids': obligation['endpoint_ids'] + ['displaced-D1'],
                'all_admission_paths_closed': True,
                'all_old_endpoints_removed': True, 'terminal_irreversible': True, 'terminal_all_writes_blocked': True}
    return {'qualification': 'Real primitive source/proof signatures and explicit native-model premises only; '
                             'no real RFC, causal authority, native transaction or production recovery.',
            'first_rejection': {'inventory': inventory, 'first_source': first, 'other_source': second,
                                'other_route': other_route, 'expected_other_same_nonce': 'duplicate_conflict'},
            'continuous_recovery': {'authorization': source, 'inventory': later['inventory'],
                                    'reader': later['reader_authority'],
                                    'route': {**later['current_delivery'],
                                        'predecessor_authorization_event_refs': predecessor_refs,
                                        'retained_proof_digests': [
                                        digest(value['retirement_proof']) for value in retired.values()]},
                                    'historical': historical, 'retirement_results': retired,
                                    'rekeyed': rekeyed, 'rekey_native': rekey_native,
                                    'predecessor_obligation': obligation, 'coverage': coverage,
                                    'expected': 'private_satisfaction_releases_exact_predecessor_not_old_ready'}}
