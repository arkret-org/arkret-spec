"""Executable single-submit Recovery transcript and durable reference model.

This checks real Ed25519/Event/Commit bytes and explicit qualified inputs. It
does not implement DID method history, storage durability or production APIs.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.regenerate_crypto_signature_fixture import refresh_jws_input

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'spec/v1/artifacts/fixtures/security-transaction-resilience-fixture.json'
SEED = bytes(range(1, 33))
SERVICE_SEED = bytes(range(33, 65))
T = '2026-11-14T12:00:00.000Z'
END = '2026-11-14T12:15:00.000Z'
IDENTITY_SOURCE = ROOT / 'spec/v1/artifacts/fixtures/resolution-commitment-fixture.json'
METHOD_DID = json.loads(IDENTITY_SOURCE.read_text(encoding='utf-8'))['vectors'][3]['commitment']['did']
VM = METHOD_DID + '#ak:device:019ba000-0000-7000-8000-000000000001'
SERVICE_VM = 'did:web:station.example#service-1'
ACCOUNT = {'principal_id': 'ak:did_core:webvh:' + METHOD_DID.split(':', 3)[2], 'station_id': 'ak:did_core:web:station.example'}
ACTOR = {'kind': 'account', 'account_id': ACCOUNT}
DEVICE = 'ak:device:019ba000-0000-7000-8000-000000000001'
SESSION = 'ak:recovery_session:019ba000-0000-7000-8000-000000000002'
POLICY = 'ak:policy:019ba000-0000-7000-8000-000000000003'


def jcs(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def b64u(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def unb64(value):
    raw = base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))
    if b64u(raw) != value:
        raise ValueError('noncanonical_signature')
    return raw


def digest(value):
    return 'sha256:' + hashlib.sha256(jcs(value)).hexdigest()


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def later(value, seconds):
    return (timestamp(value) + timedelta(seconds=seconds)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def sign_commit(body):
    envelope = {'context': 'ak.realm_commit_signature.v1', 'signature_algorithm': 'Ed25519', 'verification_method': SERVICE_VM, 'signed_digest': digest(body), 'created_at': T}
    return {**envelope, 'signature': b64u(Ed25519PrivateKey.from_private_bytes(SERVICE_SEED).sign(b'ak.realm_commit_signature.v1\n' + jcs(envelope)))}


def typed(kind, value):
    return 'ak:' + kind + ':' + b64u(b'\x01' + hashlib.sha256(jcs(value)).digest())


def key_did():
    alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    raw = b'\xed\x01' + Ed25519PrivateKey.from_private_bytes(SEED).public_key().public_bytes_raw()
    number, text = int.from_bytes(raw, 'big'), ''
    while number:
        number, rem = divmod(number, 58)
        text = alphabet[rem] + text
    return 'did:key:z' + text


REALM = typed('realm', {'fixture': 'single_submit_recovery'})
STREAM = {'kind': 'realm', 'realm_id': REALM}
PREDECESSOR = typed('realm_commit', {'fixture': 'prior_accepted_pcr_head'})
AUTHORITY = typed('event', {'fixture': 'accepted_pcr_governance_genesis'})


def signed_event(kind, payload):
    body = {'kind': kind, 'realm_id': REALM, 'scope_ref': STREAM, 'actor_id': ACTOR, 'created_at': T, 'payload': payload}
    event_digest = digest(body)
    binding = {'context': 'ak.event_proof.v1', 'event_digest': event_digest, 'actor_id': ACTOR, 'verification_method': VM, 'created_at': T}
    signing = refresh_jws_input({'protected_header': {'alg': 'Ed25519'}}, jcs(binding))
    proof = {'kind': 'detached_jws', 'verification_method': VM, 'event_digest': event_digest, 'created_at': T, 'jws': signing.decode().split('.')[0] + '..' + b64u(Ed25519PrivateKey.from_private_bytes(SEED).sign(signing))}
    return {**body, 'event_id': typed('event', body), 'producer_proof': proof}


def resign_receipt(receipt):
    unsigned = {name: item for name, item in receipt.items() if name != 'signature_proof'}
    receipt['signature_proof'] = {'verification_method': VM, 'signature_algorithm': 'Ed25519', 'signature': b64u(Ed25519PrivateKey.from_private_bytes(SEED).sign(b'ak.identity.recovery_receipt.signature.v1\n' + jcs(unsigned)))}
    return receipt


def specimen():
    authorize = {'device_id': DEVICE, 'device_public_key_did': key_did(), 'hpke_key': b64u(bytes(range(32))), 'algorithms': ['Ed25519'], 'device_key_algorithm': 'Ed25519', 'authorized_by': ACCOUNT['principal_id'], 'authorization_binding_kind': 'pcr_recovery', 'authorized_generation_ref': 2, 'not_before': T, 'recovery_session_id': SESSION}
    possession = {'account_id': ACCOUNT, **authorize, 'expires_at': None, 'scopes': None}
    authorize['device_signature'] = b64u(Ed25519PrivateKey.from_private_bytes(SEED).sign(b'ak.device_authorize_recovery_possession_proof.v1\n' + jcs(possession)))
    reanchor = {'account_id': ACCOUNT, 'recovery_authority_kind': 'pcr_policy', 'recovery_policy_id': POLICY, 'recovery_policy_version': 1, 'recovery_session_id': SESSION, 'previous_device_generation': 1, 'new_device_generation': 2, 'replacement_authorize_payload_digest': digest(authorize)}
    receipt = {'schema': 'ak.schema.recovery_receipt.v1', 'receipt_id': 'ak:receipt:019ba000-0000-7000-8000-000000000004', 'transaction_id': 'ak:transaction:019ba000-0000-7000-8000-000000000005', 'account_id': copy.deepcopy(ACCOUNT), 'expires_at': END, 'recovery_session_id': SESSION, 'session_grant_ref': {'issuer_id': ACCOUNT['station_id'], 'id': 'ak:session_grant:019ba000-0000-7000-8000-000000000006'}, 'session_grant_cnf_jkt': 'A' * 43, 'policy_id': POLICY, 'policy_version': 1, 'trust_domain': 'ak:trust_domain:single-submit-recovery', 'new_device_id': DEVICE, 'identity_model': 'pcr_policy', 'recovery_authority_kind': 'pcr_policy', 'previous_model_generation_ref': 1, 'new_model_generation_ref': 2, 'proof_summary': {'kind': 'recovery_unlock', 'proof_digest': 'sha256:' + '11' * 32}, 'recovery_unit': {'predecessor_ref': PREDECESSOR, 'events': [{'event': signed_event('ak.device.reanchor', reanchor)}, {'event': signed_event('ak.device.authorize', authorize)}]}, 'unlocked_backups': [], 'welcome_count': 0, 'outcome': 'completed', 'started_at': T, 'completed_at': T}
    resign_receipt(receipt)
    qualified = {name: copy.deepcopy(receipt[name]) for name in ['account_id', 'recovery_session_id', 'session_grant_ref', 'session_grant_cnf_jkt', 'policy_id', 'policy_version', 'trust_domain', 'new_device_id', 'proof_summary', 'previous_model_generation_ref']}
    qualified.update(candidate_public_key=b64u(Ed25519PrivateKey.from_private_bytes(SEED).public_key().public_bytes_raw()), candidate_method=VM, candidate_key_did=key_did(), predecessor_ref=PREDECESSOR, policy_active=True, session_verified=True, grant_active=True, session_consumed=False, current_reader_authorized=True, current_generation=1, now=T, session_expires_at=END, grant_expires_at=END, candidate_already_authorized=False)
    return receipt, qualified


def verify_event(event, public):
    body = {name: item for name, item in event.items() if name not in ['event_id', 'producer_proof']}
    proof = event['producer_proof']
    if event['event_id'] != typed('event', body) or proof['event_digest'] != digest(body):
        raise ValueError('event_content_mismatch')
    binding = {'context': 'ak.event_proof.v1', 'event_digest': digest(body), 'actor_id': event['actor_id'], 'verification_method': proof['verification_method'], 'created_at': event['created_at']}
    protected, empty, signature = proof['jws'].split('.')
    header = json.loads(unb64(protected))
    if empty or proof['verification_method'] != VM or proof['created_at'] != event['created_at'] or header.get('alg') != 'Ed25519':
        raise ValueError('event_method_mismatch')
    public.verify(unb64(signature), (protected + '.' + b64u(jcs(binding))).encode())


def admit(receipt, qualified, ledger):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if not qualified['current_reader_authorized'] or qualified['account_id'] != receipt['account_id']:
        raise ValueError('current_exact_result_reader')
    key = (jcs(receipt['account_id']), receipt['transaction_id'])
    frozen = jcs(receipt)
    if key in ledger:
        if ledger[key][0] != frozen:
            raise ValueError('duplicate_conflict')
        return copy.deepcopy(ledger[key][1])
    public = Ed25519PublicKey.from_public_bytes(unb64(qualified['candidate_public_key']))
    unsigned = {name: item for name, item in receipt.items() if name != 'signature_proof'}
    if receipt['signature_proof']['verification_method'] != qualified['candidate_method'] or receipt['signature_proof']['signature_algorithm'] != 'Ed25519':
        raise ValueError('candidate_method_mismatch')
    public.verify(unb64(receipt['signature_proof']['signature']), b'ak.identity.recovery_receipt.signature.v1\n' + jcs(unsigned))
    for name in ['account_id', 'recovery_session_id', 'session_grant_ref', 'session_grant_cnf_jkt', 'policy_id', 'policy_version', 'trust_domain', 'new_device_id', 'proof_summary', 'previous_model_generation_ref']:
        if receipt[name] != qualified[name]:
            raise ValueError('recovery_evidence_unbound:' + name)
    if not all(qualified[name] for name in ['policy_active', 'session_verified', 'grant_active']) or qualified['session_consumed']:
        raise ValueError('current_recovery_gate')
    if receipt['expires_at'] <= qualified['now']:
        raise ValueError('first_admission_expired')
    if receipt['expires_at'] > min(qualified['session_expires_at'], qualified['grant_expires_at']):
        raise ValueError('recovery_deadline_widening')
    previous = receipt['previous_model_generation_ref']
    if previous >= 9_007_199_254_740_991 or previous != qualified['current_generation'] or receipt['new_model_generation_ref'] != previous + 1:
        raise ValueError('generation_conflict')
    unit = receipt['recovery_unit']
    if unit['predecessor_ref'] != qualified['predecessor_ref'] or len(unit['events']) != 2:
        raise ValueError('predecessor_or_cardinality')
    events = [item['event'] for item in unit['events']]
    if [event['kind'] for event in events] != ['ak.device.reanchor', 'ak.device.authorize']:
        raise ValueError('slot_order')
    for event in events:
        verify_event(event, public)
        if event['actor_id'] != {'kind': 'account', 'account_id': receipt['account_id']} or event['scope_ref'] != STREAM or event['realm_id'] != REALM:
            raise ValueError('event_account_or_scope')
    reanchor, authorize = [event['payload'] for event in events]
    if authorize['device_id'] != receipt['new_device_id'] or authorize['device_public_key_did'] != qualified['candidate_key_did'] or authorize['authorized_generation_ref'] != previous + 1 or authorize['recovery_session_id'] != receipt['recovery_session_id'] or authorize['authorization_binding_kind'] != 'pcr_recovery':
        raise ValueError('replacement_binding')
    if reanchor['replacement_authorize_payload_digest'] != digest(authorize) or reanchor['new_device_generation'] != previous + 1 or reanchor['previous_device_generation'] != previous or reanchor['account_id'] != receipt['account_id'] or reanchor['recovery_policy_id'] != receipt['policy_id'] or reanchor['recovery_policy_version'] != receipt['policy_version'] or reanchor['recovery_session_id'] != receipt['recovery_session_id'] or reanchor['recovery_authority_kind'] != receipt['recovery_authority_kind']:
        raise ValueError('reanchor_binding')
    possession = {name: item for name, item in authorize.items() if name != 'device_signature'}
    possession.update(account_id=receipt['account_id'], expires_at=authorize.get('expires_at'), scopes=authorize.get('scopes'))
    public.verify(unb64(authorize['device_signature']), b'ak.device_authorize_recovery_possession_proof.v1\n' + jcs(possession))
    commits = []
    predecessor = qualified['predecessor_ref']
    for index, event in enumerate(events):
        body = {'realm_id': REALM, 'governance_generation': '0', 'authority_ref': AUTHORITY, 'stream_ref': STREAM, 'stream_position': index + 10, 'previous_commit_ref': predecessor, 'event_ref': event['event_id'], 'committed_at': T}
        commit = {**body, 'commit_id': typed('realm_commit', body)}
        commit['signature'] = sign_commit(commit)
        commits.append(commit)
        predecessor = commit['commit_id']
    refs = [{'event_id': event['event_id'], 'commit_id': commit['commit_id'], 'stream_ref': STREAM, 'stream_position': commit['stream_position']} for event, commit in zip(events, commits)]
    completion = {'schema': 'ak.schema.recovery_completion_attestation.v1', 'transaction_id': receipt['transaction_id'], 'account_id': receipt['account_id'], 'recovery_session_id': receipt['recovery_session_id'], 'terminal_receipt_id': receipt['receipt_id'], 'terminal_receipt_digest': digest(receipt), 'replacement_device_id': receipt['new_device_id'], 'new_model_generation_ref': previous + 1, 'completed_at': T, 'reanchor_event_ref': refs[0], 'device_authorization_event_ref': refs[1]}
    completion['signature_proof'] = {'verification_method': SERVICE_VM, 'signature_algorithm': 'Ed25519', 'signature': b64u(Ed25519PrivateKey.from_private_bytes(SERVICE_SEED).sign(jcs(completion)))}
    outcome = {'transaction_id': receipt['transaction_id'], 'kind': 'recovery', 'account_id': receipt['account_id'], 'created_at': T, 'recovery_receipt': copy.deepcopy(receipt), 'completion_attestation': completion}
    ledger[key] = (frozen, copy.deepcopy(outcome), commits)
    qualified.update(session_consumed=True, current_generation=previous + 1, candidate_already_authorized=True)
    return outcome


def make_completion_request(receipt, now=T):
    holder = Ed25519PrivateKey.from_private_bytes(bytes(range(65, 97)))
    jwk = {'crv': 'Ed25519', 'kty': 'OKP', 'x': b64u(holder.public_key().public_bytes_raw())}
    jkt = b64u(hashlib.sha256(jcs(jwk)).digest())
    initial = {'device_id': DEVICE, 'session_public_key': jcs(jwk).decode(), 'audience_id': ACCOUNT['station_id']}
    proof = {'context': 'ak.session_grant_accepted_device_possession_proof.v1', 'purpose': 'recovery_completion_grant_issue', 'request_id': 'ak:request:019ba000-0000-7000-8000-000000000008', 'account_subject': 'sha256:' + '22' * 32, 'account_handoff_grant_digest': 'sha256:' + '33' * 32, 'account_id': ACCOUNT, 'device_id': DEVICE, 'audience_id': ACCOUNT['station_id'], 'holder_jkt': jkt, 'session_intent_digest': digest({'receipt_digest': digest(receipt), 'initial_session': initial}), 'issued_at': now, 'expires_at': later(now, 300), 'verification_method': VM}
    proof['signature'] = b64u(Ed25519PrivateKey.from_private_bytes(SEED).sign(b'ak.session_grant_accepted_device_possession_proof.v1\n' + jcs(proof)))
    request = {'terminal_receipt': copy.deepcopy(receipt), 'initial_session': initial, 'accepted_device_possession_proof': proof}
    request['canonical_request_digest'] = digest(request)
    qualified = {'account_id': copy.deepcopy(ACCOUNT), 'issuer_id': ACCOUNT['station_id'], 'audience_id': ACCOUNT['station_id'], 'holder_jkt': jkt, 'account_subject': proof['account_subject'], 'handoff_digest': proof['account_handoff_grant_digest'], 'authenticated_handoff': True, 'dpop_verified': True, 'device_id': DEVICE, 'current_generation': 2, 'current_device_active': True, 'account_state': 'deactivated', 'allow_reactivation': True, 'now': now, 'candidate_method': VM, 'candidate_public_key': b64u(Ed25519PrivateKey.from_private_bytes(SEED).public_key().public_bytes_raw()), 'secret_entropy': b64u(bytes(range(97, 129)))}
    return request, qualified


def issue_completion(request, completion, qualified, ledger):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    receipt = request['terminal_receipt']
    proof = request['accepted_device_possession_proof']
    initial = request['initial_session']
    identity = (qualified['issuer_id'], 'ak.gate.account.command.issue_recovery_completion_grant.v1', jcs(receipt['account_id']), receipt['transaction_id'])
    if not qualified['authenticated_handoff'] or not qualified['dpop_verified'] or qualified['account_id'] != receipt['account_id'] or not qualified['current_device_active'] or qualified['device_id'] != receipt['new_device_id'] or qualified['current_generation'] != receipt['new_model_generation_ref']:
        raise ValueError('current_completion_authentication')
    if initial['audience_id'] != qualified['audience_id'] or initial['device_id'] != qualified['device_id']:
        raise ValueError('completion_scope')
    jwk = json.loads(initial['session_public_key'])
    if jcs(jwk).decode() != initial['session_public_key'] or b64u(hashlib.sha256(jcs(jwk)).digest()) != qualified['holder_jkt'] or proof['holder_jkt'] != qualified['holder_jkt']:
        raise ValueError('completion_holder')
    frozen = jcs(request)
    if identity in ledger:
        stored = ledger[identity]
        if stored['request'] != frozen:
            raise ValueError('duplicate_conflict')
        if stored['state'] != 'active':
            raise ValueError('session_grant_replay_terminal')
        if qualified['now'] >= stored['outcome']['issued_session']['expires_at']:
            raise ValueError('session_grant_replay_expired')
        return copy.deepcopy(stored['outcome'])
    if qualified['account_state'] not in ['active', 'deactivated'] or qualified['account_state'] == 'deactivated' and not qualified['allow_reactivation']:
        raise ValueError('account_reactivation_denied')
    unsigned_request = {name: item for name, item in request.items() if name != 'canonical_request_digest'}
    if request['canonical_request_digest'] != digest(unsigned_request):
        raise ValueError('completion_request_digest')
    if proof['context'] != 'ak.session_grant_accepted_device_possession_proof.v1' or proof['purpose'] != 'recovery_completion_grant_issue' or proof['session_intent_digest'] != digest({'receipt_digest': digest(receipt), 'initial_session': initial}) or proof['account_id'] != qualified['account_id'] or proof['account_subject'] != qualified['account_subject'] or proof['account_handoff_grant_digest'] != qualified['handoff_digest'] or proof['verification_method'] != qualified['candidate_method'] or proof['device_id'] != qualified['device_id'] or proof['audience_id'] != qualified['audience_id']:
        raise ValueError('completion_possession_binding')
    if not proof['issued_at'] <= qualified['now'] < proof['expires_at'] or not 0 < (timestamp(proof['expires_at']) - timestamp(proof['issued_at'])).total_seconds() <= 300:
        raise ValueError('completion_possession_window')
    candidate = Ed25519PublicKey.from_public_bytes(unb64(qualified['candidate_public_key']))
    candidate.verify(unb64(proof['signature']), b'ak.session_grant_accepted_device_possession_proof.v1\n' + jcs({name: item for name, item in proof.items() if name != 'signature'}))
    if not isinstance(completion, dict):
        raise ValueError('native_completion_unavailable')
    if completion['signature_proof']['verification_method'] != SERVICE_VM or completion['signature_proof']['signature_algorithm'] != 'Ed25519':
        raise ValueError('native_completion_signer')
    service = Ed25519PrivateKey.from_private_bytes(SERVICE_SEED).public_key()
    service.verify(unb64(completion['signature_proof']['signature']), jcs({name: item for name, item in completion.items() if name != 'signature_proof'}))
    if completion['account_id'] != qualified['account_id'] or completion['account_id']['station_id'] != qualified['issuer_id'] or completion['transaction_id'] != receipt['transaction_id'] or completion['terminal_receipt_digest'] != digest(receipt) or completion['replacement_device_id'] != qualified['device_id'] or completion['new_model_generation_ref'] != qualified['current_generation']:
        raise ValueError('native_completion_binding')
    candidate.verify(unb64(receipt['signature_proof']['signature']), b'ak.identity.recovery_receipt.signature.v1\n' + jcs({name: item for name, item in receipt.items() if name != 'signature_proof'}))
    token = qualified['secret_entropy']
    if len(unb64(token)) != 32:
        raise ValueError('invalid_entropy')
    outcome = {'transaction_id': receipt['transaction_id'], 'issued_session': {'account_id': receipt['account_id'], 'issuer_id': qualified['issuer_id'], 'device_id': qualified['device_id'], 'session_grant': token, 'expires_at': later(qualified['now'], 3600), 'session_grant_id': 'ak:session_grant:019ba000-0000-7000-8000-000000000009', 'session_public_key': initial['session_public_key'], 'audience_id': initial['audience_id'], 'granted_scope': ['ak.self.security_transaction.resource.get.v1']}, 'issued_at': qualified['now']}
    ledger[identity] = {'request': frozen, 'outcome': copy.deepcopy(outcome), 'state': 'active'}
    qualified['account_state'] = 'active'
    return outcome


def check_fixture(fixture):
    errors = []
    kat = fixture.get('single_submit_recovery_kat')
    if not isinstance(kat, dict):
        return ['missing executable single_submit_recovery_kat']
    try:
        identity = kat['identity_projection']
        if identity != {'did': METHOD_DID, 'principal_id': ACCOUNT['principal_id'], 'source_ref': 'spec/v1/artifacts/fixtures/resolution-commitment-fixture.json#/vectors/3/commitment/did'} or VM != identity['did'] + '#' + DEVICE:
            errors.append('qualified native method identity projection mismatch')
        receipt = kat['receipt']
        qualified = copy.deepcopy(kat['qualified_inputs'])
        ledger = {}
        outcome = admit(receipt, qualified, ledger)
        if outcome != kat['expected_outcome'] or digest(receipt) != kat['receipt_digest']:
            errors.append('single-submit canonical output mismatch')
        qualified['now'] = END
        if admit(receipt, qualified, ledger) != outcome or len(ledger) != 1:
            errors.append('response-loss exact replay changed the accepted result')
        service = Ed25519PrivateKey.from_private_bytes(SERVICE_SEED).public_key()
        proof = outcome['completion_attestation']['signature_proof']
        unsigned = {name: item for name, item in outcome['completion_attestation'].items() if name != 'signature_proof'}
        service.verify(unb64(proof['signature']), jcs(unsigned))
        native = kat['native_commits']
        if len(native) != 2:
            errors.append('native Commit pair cardinality')
        for index, commit in enumerate(native):
            unsigned_commit = {name: item for name, item in commit.items() if name != 'signature'}
            body = {name: item for name, item in unsigned_commit.items() if name != 'commit_id'}
            if commit['commit_id'] != typed('realm_commit', body) or commit['signature']['signed_digest'] != digest(unsigned_commit):
                errors.append('native Commit content-address/signature digest mismatch')
            envelope = {name: item for name, item in commit['signature'].items() if name != 'signature'}
            service.verify(unb64(commit['signature']['signature']), b'ak.realm_commit_signature.v1\n' + jcs(envelope))
            source = outcome['completion_attestation'][['reanchor_event_ref', 'device_authorization_event_ref'][index]]
            if source != {'event_id': commit['event_ref'], 'commit_id': commit['commit_id'], 'stream_ref': commit['stream_ref'], 'stream_position': commit['stream_position']}:
                errors.append('native completion reference mismatch')
        if native[1]['previous_commit_ref'] != native[0]['commit_id'] or native[1]['stream_position'] != native[0]['stream_position'] + 1:
            errors.append('native Commit pair continuity mismatch')
        request, fresh = kat['completion_request'], copy.deepcopy(kat['completion_qualified_inputs'])
        issuer_ledger = {}
        issued = issue_completion(request, outcome['completion_attestation'], fresh, issuer_ledger)
        if issued != kat['completion_expected_outcome'] or fresh['account_state'] != 'active':
            errors.append('completion issuer atomic outcome mismatch')
        fresh.update(now='2026-11-14T12:06:00.000Z', handoff_digest='sha256:' + '44' * 32)
        if issue_completion(request, None, fresh, issuer_ledger) != issued or len(issuer_ledger) != 1:
            errors.append('completion response-loss replay repeated issuance')
    except (KeyError, ValueError, InvalidSignature, TypeError) as error:
        errors.append('single-submit KAT invalid: ' + str(error))
    return errors


def regenerate():
    fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))
    receipt, qualified = specimen()
    native_ledger = {}
    outcome = admit(receipt, copy.deepcopy(qualified), native_ledger)
    request, fresh = make_completion_request(receipt)
    issued = issue_completion(request, outcome['completion_attestation'], copy.deepcopy(fresh), {})
    fixture['single_submit_recovery_kat'] = {'boundary': 'Real Ed25519/Event/Commit and fresh completion-holder PoP bytes over explicit qualified inputs; not native DID/HTTP authentication or production storage.', 'identity_projection': {'did': METHOD_DID, 'principal_id': ACCOUNT['principal_id'], 'source_ref': 'spec/v1/artifacts/fixtures/resolution-commitment-fixture.json#/vectors/3/commitment/did'}, 'receipt': receipt, 'receipt_digest': digest(receipt), 'qualified_inputs': qualified, 'expected_outcome': outcome, 'native_commits': next(iter(native_ledger.values()))[2], 'completion_request': request, 'completion_qualified_inputs': fresh, 'completion_expected_outcome': issued}
    fixture['schema_validation_cases'] = [case for case in fixture['schema_validation_cases'] if 'recovery_commit_intent' not in case['name'] and not case['name'].startswith('single_submit')]
    fixture['schema_validation_cases'].append({'name': 'single_submit_recovery_receipt', 'schema_ref': 'schemas/recovery-receipt.schema.json', 'expect_valid': True, 'instance': receipt})
    fixture['schema_validation_cases'].append({'name': 'single_submit_recovery_result', 'schema_ref': 'schemas/security-transaction.schema.json#/$defs/recovery_transaction_completion', 'expect_valid': True, 'instance': outcome})
    fixture['schema_validation_cases'].append({'name': 'single_submit_recovery_completion_request', 'schema_ref': 'schemas/recovery-authority.schema.json#/$defs/recovery_completion_grant_request_body', 'expect_valid': True, 'instance': request})
    fixture['schema_validation_cases'].append({'name': 'single_submit_recovery_issuance_outcome', 'schema_ref': 'schemas/recovery-authority.schema.json#/$defs/issue_recovery_completion_grant_response_body', 'expect_valid': True, 'instance': issued})
    for index, commit in enumerate(next(iter(native_ledger.values()))[2]):
        fixture['schema_validation_cases'].append({'name': 'single_submit_recovery_native_commit_' + str(index), 'schema_ref': 'schemas/realm-commit.schema.json', 'expect_valid': True, 'instance': commit})
    fixture.pop('recovery_terminal_commit_cases', None)
    fixture['recovery_submit_cases'] = [{'name': name, 'expected': expected} for name, expected in [
        ('candidate_not_previously_authorized', 'atomic_completed'), ('same_signed_receipt_response_lost', 'same_outcome'), ('changed_signature_bytes_same_transaction', 'duplicate_conflict'), ('swapped_slots', 'reject_zero_effects'), ('wrong_candidate', 'reject_zero_effects'), ('wrong_session_grant_issuer', 'reject_zero_effects'), ('stale_head_or_generation', 'reject_zero_effects'), ('policy_revoked', 'reject_zero_effects'), ('expired_before_first_acceptance', 'reject_zero_effects'), ('deactivated_completion_response_lost', 'fresh_handoff_original_closure_no_recommit'), ('new_holder_without_identity_pop', 'reject_zero_issuance')]]
    fixture['continue_cases'] = [row for row in fixture['continue_cases'] if row.get('transaction_kind') != 'recovery'] + [{'name': 'recovery_continue_is_not_a_submission_route', 'transaction_kind': 'recovery', 'expected': 'reject_without_side_effect', 'reason_code': 'failed_precondition'}]
    fixture['assertions'] = [text for text in fixture['assertions'] if not any(word in text.lower() for word in ['recovery', 'reanchor'])] + ['Recovery is one exact signed receipt containing two EventAdmissionSubmission slots; it has no prepare plan or outer terminal signature.', 'Recovery success atomically creates distinct consecutive Commits, device/generation/session terminal and native content-recovery fence.', 'The existing completion operation obtains the original success closure server-side and verifies a fresh accepted-device PoP for the new holder.']
    FIXTURE.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    import sys
    if '--regenerate' in sys.argv:
        regenerate()
    failures = check_fixture(json.loads(FIXTURE.read_text(encoding='utf-8')))
    if failures:
        raise SystemExit('\n'.join(failures))
    print('single-submit Recovery KAT: passed')
