"""Primitive/reference retirement checks; native facts must be qualified separately."""

import copy
import hashlib
from datetime import datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from tools.content_history import b64, jcs, unb64


def digest(value):
    return 'sha256:' + hashlib.sha256(jcs(value)).hexdigest()


def request_intent(attestation):
    return {k: v for k, v in attestation.items()
            if k not in {'verification_method', 'attested_at', 'expires_at', 'signature'}}


def request_digest(attestation):
    return 'sha256:' + hashlib.sha256(
        b'ak.mls.recovery_scope_cleanup_request.v1\n' + jcs(request_intent(attestation))).hexdigest()


def terminal_source_digest(entry, source_ref, nonce):
    binding = {'effective_scope': entry['effective_scope'], 'genesis_event_ref': entry['genesis_event_ref'],
               'terminal_event_ref': source_ref, 'nonce_base64url': nonce}
    return 'sha256:' + hashlib.sha256(b'ak.mls.scope_terminal_source.v1\n' + jcs(binding)).hexdigest()


def signing_bytes(value, source=False):
    domain = (b'ak.mls.recovery_scope_cleanup_authorization.v1\n' if source
              else b'ak.mls.scope_retirement.v1\n')
    return domain + jcs({k: v for k, v in value.items() if k != 'signature'})


def verify_signature(value, public_key, source=False):
    signature = value['signature']
    if (set(signature) != {'kid', 'signature_algorithm', 'signature'}
            or signature['kid'] != value['verification_method']
            or signature['signature_algorithm'] != 'Ed25519'):
        raise ValueError('retirement signer mismatch')
    Ed25519PublicKey.from_public_bytes(unb64(public_key)).verify(
        unb64(signature['signature']), signing_bytes(value, source))


def qualify_source(attestation, inventory, entry, facts, now):
    """Compose native-qualified origin, current episode and admission facts.

    This function does not implement native method-history or ledger verification.
    """
    from tools.content_history import inventory_digest
    if set(attestation) != {'replacement', 'inventory_digest', 'inventory_entry',
                            'destination_service_id', 'nonce_base64url', 'verification_method',
                            'attested_at', 'expires_at', 'signature'}:
        raise ValueError('source is not closed')
    verify_signature(attestation, facts['origin_public_key'], source=True)
    if (not facts['current_episode'] or not facts['native_source_complete']
            or facts['origin_service_id'] != inventory['replacement']['actor_id']['account_id']['station_id']
            or attestation['verification_method'] != facts['origin_verification_method']
            or attestation['replacement'] != inventory['replacement']
            or attestation['inventory_digest'] != inventory_digest(inventory)
            or attestation['inventory_entry'] != entry
            or attestation['destination_service_id'] != facts['governance_station_id']
            or facts['current_eligible']):
        raise ValueError('source lacks the exact current native retirement role')
    nonce = unb64(attestation['nonce_base64url'])
    if len(nonce) != 32 or b64(nonce) != attestation['nonce_base64url']:
        raise ValueError('invalid canonical nonce')
    moment = lambda value: datetime.fromisoformat(value.replace('Z', '+00:00'))
    issued, expiry, current = map(moment, (attestation['attested_at'], attestation['expires_at'], now))
    if not issued <= current < expiry or not 0 < (expiry - issued).total_seconds() <= 300:
        raise ValueError('source outside the admission window')


def verify_retirement(result, attestation, inventory, entry, facts, public_key):
    """Verify exact bytes plus independently qualified native completion facts.

    Native cut, RFC roster, lifecycle, origin authority, episode and fence inputs
    are not caller assertions or inferred from the signatures below.
    """
    from tools.content_history import inventory_digest
    if set(result) != {'state', 'effective_scope', 'genesis_event_ref', 'retirement_proof'}:
        raise ValueError('retirement result is not closed')
    proof = result['retirement_proof']
    state = result['state']
    if state not in {'removed', 'terminated'} or state != proof['state']:
        raise ValueError('wrong retirement branch')
    verify_signature(proof, public_key)
    if proof['verification_method'] != facts['governor_verification_method']:
        raise ValueError('proof method differs from native historical service role')
    expected = {'state', 'replacement', 'inventory_digest', 'inventory_entry_digest', 'request_digest',
                'effective_scope', 'genesis_event_ref', 'governance_station_id', 'governance_generation',
                'scope_cut', 'group_state_ref', 'epoch', 'nonce_base64url', 'attested_at', 'verification_method', 'signature'}
    expected.add('remaining_old_leaf_count' if state == 'removed' else 'terminal_source_digest')
    if set(proof) != expected:
        raise ValueError('retirement proof is not closed')
    for key in ('effective_scope', 'genesis_event_ref'):
        if result[key] != entry[key] or proof[key] != entry[key]:
            raise ValueError('retirement selected another scope')
    if (proof['replacement'] != inventory['replacement']
            or proof['inventory_digest'] != inventory_digest(inventory)
            or proof['inventory_entry_digest'] != digest(entry)
            or proof['request_digest'] != request_digest(attestation)
            or proof['nonce_base64url'] != attestation['nonce_base64url']
            or not facts['current_episode'] or facts['current_eligible']
            or not facts['episode_fenced'] or not facts['native_source_complete']
            or facts['pending_admission_count'] != 0):
        raise ValueError('retirement lacks complete episode/fence/admission evidence')
    for key in ('governance_station_id', 'governance_generation', 'scope_cut', 'group_state_ref', 'epoch'):
        if proof[key] != facts[key]:
            raise ValueError('retirement cut or governance mismatch')
    moment = lambda value: datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not moment(attestation['attested_at']) <= moment(proof['attested_at']) < moment(attestation['expires_at']):
        raise ValueError('proof was not finalized within its original authorization window')
    if state == 'removed':
        if proof['remaining_old_leaf_count'] != 0 or facts['old_endpoint_count'] != 0:
            raise ValueError('displaced endpoints still exist')
    elif (not facts['terminal_irreversible'] or not facts['terminal_all_writes_blocked']
          or proof['terminal_source_digest'] != facts['terminal_source_digest']):
        raise ValueError('no native irreversible terminal source')
    return proof


def sign(value, key, source=False):
    value = copy.deepcopy(value)
    value.pop('signature', None)
    value['signature'] = {'kid': value['verification_method'], 'signature_algorithm': 'Ed25519',
                          'signature': b64(key.sign(signing_bytes(value, source)))}
    return value


def verify_self_retirement(response, attestation, inventory, entry, facts, public_key):
    """Check the own-Station projection against independently bound native inputs."""
    if response == {'cleanup': {'state': 'pending'}}:
        return None
    if set(response) != {'cleanup', 'attestor_signing_key'}:
        raise ValueError('self retirement wrapper is not closed')
    proof = response['cleanup']['retirement_proof']
    expected = {'proof_digest': digest(proof), 'verification_method': proof['verification_method'],
                'public_key_base64url': public_key}
    if response['attestor_signing_key'] != expected:
        raise ValueError('self projection is not bound to the exact proof and historical key')
    return verify_retirement(response['cleanup'], attestation, inventory, entry, facts, public_key)


def fixture(replacement, entry, pcr_cut):
    """Deterministic signature KAT; coordinates are not accepted native results."""
    from tools.content_history import inventory_digest
    replacement = copy.deepcopy(replacement)
    replacement['actor_id']['account_id']['station_id'] = 'ak:did_core:web:origin.example'
    origin = Ed25519PrivateKey.from_private_bytes(bytes([234]) * 32)
    governor = Ed25519PrivateKey.from_private_bytes(bytes([235]) * 32)
    origin_id = replacement['actor_id']['account_id']['station_id']
    governor_id = 'ak:did_core:web:governor.example'
    origin_method = origin_id.replace('ak:did_core:', 'did:') + '#retirement'
    governor_method = 'did:web:governor.example#retirement'
    inventory = {'actor_id': replacement['actor_id'], 'replacement': replacement,
                 'authorization_event_ref': replacement['authorization_event_ref'],
                 'pcr_cut': pcr_cut, 'entries': [entry]}
    authorization = sign({'replacement': replacement, 'inventory_digest': inventory_digest(inventory),
                          'inventory_entry': entry, 'destination_service_id': governor_id,
                          'nonce_base64url': b64(bytes([93]) * 32), 'verification_method': origin_method,
                          'attested_at': '2026-11-09T00:00:00.000Z',
                          'expires_at': '2026-11-09T00:05:00.000Z'}, origin, source=True)
    facts = {'origin_service_id': origin_id,
             'origin_verification_method': origin_method, 'governor_verification_method': governor_method,
             'origin_public_key': b64(origin.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)),
             'current_episode': True, 'native_source_complete': True, 'current_eligible': False,
             'episode_fenced': True, 'pending_admission_count': 0, 'old_endpoint_count': 0,
             'governance_station_id': governor_id, 'governance_generation': 0,
             'scope_cut': pcr_cut, 'group_state_ref': entry['base_group_state_ref'], 'epoch': entry['epoch'],
             'terminal_irreversible': True, 'terminal_all_writes_blocked': True,
             'terminal_source_digest': terminal_source_digest(entry, pcr_cut, authorization['nonce_base64url'])}
    removed = {'state': 'removed', 'replacement': replacement, 'inventory_digest': inventory_digest(inventory),
               'inventory_entry_digest': digest(entry), 'request_digest': request_digest(authorization),
               'effective_scope': entry['effective_scope'], 'genesis_event_ref': entry['genesis_event_ref'],
               'governance_station_id': governor_id, 'governance_generation': 0,
               'scope_cut': pcr_cut, 'group_state_ref': entry['base_group_state_ref'], 'epoch': entry['epoch'],
               'nonce_base64url': authorization['nonce_base64url'], 'attested_at': '2026-11-09T00:00:01.000Z',
               'verification_method': governor_method, 'remaining_old_leaf_count': 0}
    terminated = copy.deepcopy(removed)
    terminated['state'] = 'terminated'
    terminated.pop('remaining_old_leaf_count')
    terminated['terminal_source_digest'] = facts['terminal_source_digest']
    results = {}
    for state, proof in [('removed', removed), ('terminated', terminated)]:
        results[state] = {'state': state, 'effective_scope': entry['effective_scope'],
                          'genesis_event_ref': entry['genesis_event_ref'],
                          'retirement_proof': sign(proof, governor)}
    return {'inventory': inventory, 'authorization': authorization, 'results': results,
            'native_qualified_inputs': facts,
            'governor_public_key': b64(governor.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)),
            'origin_signing_seed_hex': (bytes([234]) * 32).hex(),
            'governor_signing_seed_hex': (bytes([235]) * 32).hex(),
            'authorization_signing_hex': signing_bytes(authorization, source=True).hex(),
            'removed_signing_hex': signing_bytes(results['removed']['retirement_proof']).hex(),
            'terminated_signing_hex': signing_bytes(results['terminated']['retirement_proof']).hex(),
            'qualification': 'Primitive signature and closed contract KAT only. Native inputs are explicit model '
                             'assumptions, not accepted RFC tree, lifecycle, Station method history, fence durability or production evidence.'}
