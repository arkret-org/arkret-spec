"""Reference bytes with separated native-model inputs, not production admission."""

import copy
import hashlib
from datetime import datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from tools.content_history import b64, jcs, unb64

INTENT_FIELDS = {'replacement', 'inventory_digest', 'inventory_entry', 'nonce_base64url'}
SOURCE_FIELDS = INTENT_FIELDS | {'destination_service_id', 'delivery_challenge_base64url',
                                 'verification_method', 'attested_at', 'expires_at', 'signature'}


def digest(value):
    return 'sha256:' + hashlib.sha256(jcs(value)).hexdigest()


def request_intent(attestation):
    return {key: attestation[key] for key in INTENT_FIELDS}


def request_digest(attestation):
    return 'sha256:' + hashlib.sha256(
        b'ak.mls.recovery_scope_cleanup_request.v1\n' + jcs(request_intent(attestation))).hexdigest()


def terminal_source_digest(entry, source_ref, nonce):
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
    if set(attestation) != SOURCE_FIELDS:
        raise ValueError('source is not closed')
    verify_signature(attestation, route['origin_public_key'], source=True)
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


def settle_intent(ledger, authorization, first_eligible, candidate):
    """Native-model inner CAS. Existing terminal never re-runs first-finalization membership."""
    replacement = authorization['replacement']
    identity = (jcs(replacement['actor_id']), replacement['authorization_event_ref'], authorization['nonce_base64url'])
    intent = request_digest(authorization)
    intent_bytes = jcs(request_intent(authorization))
    if identity in ledger:
        row = ledger[identity]
        if row['request_digest'] != intent or row['intent_bytes'] != intent_bytes:
            raise ValueError('duplicate_conflict')
        if row['cleanup'] is not None:
            return copy.deepcopy(row['cleanup'])
    if first_eligible:
        raise ValueError('failed_precondition')
    ledger[identity] = {'request_digest': intent, 'intent_bytes': intent_bytes, 'cleanup': copy.deepcopy(candidate)}
    return copy.deepcopy(candidate) if candidate is not None else {'state': 'pending'}


def transport_replay(ledger, principal, operation, body, authorized, compute):
    """Full-body outer replay model; the caller performs all current delivery-window checks."""
    if not authorized:
        raise ValueError('not_found')
    encoded = jcs(body)
    identity = (principal, operation, digest(body))
    if identity in ledger:
        if ledger[identity]['body'] != encoded:
            raise ValueError('duplicate_conflict')
        return copy.deepcopy(ledger[identity]['response'])
    response = compute()
    ledger[identity] = {'body': encoded, 'response': copy.deepcopy(response)}
    return response


def observe_delivery(ledger, authorization, compute):
    """Check source/challenge replay before computing any new native effects."""
    identity = (request_digest(authorization), authorization['delivery_challenge_base64url'])
    source = digest(authorization)
    if identity in ledger:
        if ledger[identity]['authorization_digest'] != source:
            raise ValueError('duplicate_conflict')
        return copy.deepcopy(ledger[identity]['observation'])
    observation = compute()
    ledger[identity] = {'authorization_digest': source, 'observation': copy.deepcopy(observation)}
    return observation


def business_send_allowed(blockers, ordinary_gates, terminal=False):
    """Temporary episode blockers and permanent terminal lifecycle are independent."""
    return ordinary_gates and not blockers and not terminal


def fixture(replacement, entry, pcr_cut):
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
    inventory = {'actor_id': replacement['actor_id'], 'replacement': replacement,
                 'authorization_event_ref': replacement['authorization_event_ref'], 'pcr_cut': pcr_cut, 'entries': [entry]}
    authorization = sign({'replacement': replacement, 'inventory_digest': inventory_digest(inventory),
                          'inventory_entry': entry, 'destination_service_id': governor_id,
                          'nonce_base64url': b64(bytes([93]) * 32), 'delivery_challenge_base64url': b64(bytes([94]) * 32),
                          'verification_method': origin_method, 'attested_at': '2026-11-09T00:00:00.000Z',
                          'expires_at': '2026-11-09T00:05:00.000Z'}, origin, source=True)
    historical = {'authorization': authorization, 'origin_public_key': public(origin),
                  'origin_verification_method': origin_method, 'governor_public_key': public(governor),
                  'governor_verification_method': governor_method, 'eligible_at_completion': False,
                  'native_source_complete': True, 'episode_fenced': True, 'pending_admission_count': 0,
                  'old_endpoint_count': 0, 'governance_station_id': governor_id, 'governance_generation': 0,
                  'scope_cut': pcr_cut, 'group_state_ref': entry['base_group_state_ref'], 'epoch': entry['epoch'],
                  'terminal_irreversible': True, 'terminal_all_writes_blocked': True,
                  'terminal_source_digest': terminal_source_digest(entry, pcr_cut, authorization['nonce_base64url'])}
    removed = {'state': 'removed', 'replacement': replacement, 'inventory_digest': inventory_digest(inventory),
               'inventory_entry_digest': digest(entry), 'request_digest': request_digest(authorization),
               'effective_scope': entry['effective_scope'], 'genesis_event_ref': entry['genesis_event_ref'],
               'governance_station_id': governor_id, 'governance_generation': 0, 'scope_cut': pcr_cut,
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
             'origin_native_qualified': True, 'governance_active': True, 'governance_station_id': governor_id,
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
    after = {**route, 'governance_station_id': 'ak:did_core:web:successor.example', 'governance_generation': 1,
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
