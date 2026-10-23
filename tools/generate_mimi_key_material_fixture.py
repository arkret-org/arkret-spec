"""Generate native claim carriers and MIMI adapter boundary counterexamples."""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'spec/v1/artifacts'
OUT = ART / 'fixtures/mimi-key-material-claim-fixture.json'
OP = 'ak.open.mimi.exchange.request_key_material.v1'
REQUEST = 'schemas/keypackage-operations.schema.json#/$defs/keypackages_claim_request_body'
OUTCOME = 'schemas/keypackage-operations.schema.json#/$defs/peer_keypackages_claim_command_outcome'


def jcs(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def digest(value):
    return 'sha256:' + hashlib.sha256(jcs(value)).hexdigest()


def build():
    native = json.loads((ART / 'fixtures/keypackage-lifecycle-fixture.json').read_text(encoding='utf-8'))
    request = deepcopy(native['schema_validation_cases'][0]['instance'])
    request['required_capabilities'] = ['ak.content.v1', 'mimi.content.v1']
    request['last_resort_allowed'] = False
    kat = json.loads((ART / 'fixtures/mls-keypackage-endpoint-kat-fixture.json').read_text(encoding='utf-8'))['cases'][0]
    publication = json.loads(kat['upload_entry_jcs'])
    signed_at = publication['created_at']
    request['requester_authorization']['signed_at'] = signed_at
    request['expires_at'] = (datetime.fromisoformat(signed_at.replace('Z', '+00:00')) + timedelta(minutes=5)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    request['target_account_id'] = kat['endpoint']['actor_id']['account_id']
    request['target_device_ids'] = [kat['endpoint']['device_id']]
    request['service_binding']['destination_id'] = request['target_account_id']['station_id']
    participant = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    destination = Ed25519PrivateKey.from_private_bytes(bytes(range(32, 64)))
    unsigned = {k: v for k, v in request.items() if k not in ('requester_authorization', 'service_binding')}
    authorization = {k: v for k, v in request['requester_authorization'].items() if k not in ('kind', 'signature')}
    participant_input = b'ak.peer-keypackage-claim-authorization-v1\n' + jcs({
        'authorization': authorization, 'request': unsigned, 'service_binding': request['service_binding']})
    request['requester_authorization']['signature']['sig'] = b64(participant.sign(participant_input))
    claim = {
        'claim_id': 'ak:keypackage_claim:0199eeee-eeee-7eee-8eee-eeeeeeeeeeee',
        'keypackage_ref': kat['keypackage_ref'],
        'actor_id': kat['endpoint']['actor_id'],
        'principal_id': kat['endpoint']['actor_id']['account_id']['principal_id'],
        'device_id': kat['endpoint']['device_id'],
        'device_authorize_event_id': request['requester_authorization']['device_authorize_event_id'],
        'keypackage': kat['keypackage'],
        'capabilities': ['ak.content.v1', 'mimi.content.v1'],
        'expires_at': request['expires_at'],
    }
    receipt = {
        'claim_request_id': request['claim_request_id'], 'request_digest': digest(request),
        'claims_digest': digest([claim]), **request['service_binding'], 'request': unsigned,
        'claimed_at': signed_at, 'expires_at': request['expires_at'],
    }
    receipt['signature'] = {
        'kid': 'did:webvh:z6mkfixturestationa:station.example#service-1',
        'signature_algorithm': 'Ed25519',
        'sig': b64(destination.sign(b'ak.peer-keypackage-claim-receipt-v1\n' + jcs(receipt))),
    }
    outcome = {'claim_request_id': request['claim_request_id'], 'state': 'claimed', 'claim_outcome': {
        'claim_request_id': request['claim_request_id'], 'claims': [claim], 'claim_receipt': receipt}}
    cases = []
    schemas = [json.loads(p.read_text(encoding='utf-8')) for p in (ART / 'schemas').glob('*.json')]
    registry = Registry().with_resources((d['$id'], Resource.from_contents(d)) for d in schemas)

    def case(name, ref, value, valid):
        row = {'name': name, 'schema_ref': ref, 'instance': deepcopy(value), 'expect_valid': valid}
        if not valid:
            errors = list(Draft202012Validator({'$ref': 'https://arkret.org/v1/' + ref}, registry=registry).iter_errors(value))
            if not errors:
                raise ValueError('Negative contract case became valid: ' + name)
            row['first_expected_error'] = 'contains:' + errors[0].message
        cases.append(row)

    case('native_participant_authorized_request', REQUEST, request, True)
    case('complete_original_claim_outcome', OUTCOME, outcome, True)
    case('pending_uses_native_state', OUTCOME, {
        'claim_request_id': request['claim_request_id'], 'state': 'pending', 'retry_after_ms': 100}, True)
    case('old_provider_only_request_rejected', REQUEST, {
        'requester_id': request['service_binding']['source_id'], 'strand_id': 'ak:strand:' + request['intended_realm_id'].split(':')[-1],
        'device_id': claim['device_id']}, False)
    case('old_narrow_keypackages_outcome_rejected', OUTCOME, {'keypackages': [{
        'device_id': claim['device_id'], 'keypackage_ref': claim['keypackage_ref'],
        'mls_keypackage': claim['keypackage']}]}, False)
    for field in ('requester_authorization', 'service_binding', 'claim_request_id', 'target_account_id'):
        changed = deepcopy(request)
        del changed[field]
        case('missing_' + field, REQUEST, changed, False)
    for field in ('claim_id', 'keypackage_ref', 'device_id', 'expires_at', 'capabilities'):
        changed = deepcopy(outcome)
        del changed['claim_outcome']['claims'][0][field]
        case('claim_missing_' + field, OUTCOME, changed, False)
    changed = deepcopy(outcome)
    del changed['claim_outcome']['claim_receipt']
    case('missing_native_signed_receipt', OUTCOME, changed, False)
    for field, value in (('signature', {'kid': 'provider', 'sig': 'AA'}), ('available_count', 1), ('failures', [])):
        changed = deepcopy(outcome)
        changed[field] = value
        case('no_mimi_' + field + '_mirror', OUTCOME, changed, False)
    world = {
        'provider_id': request['service_binding']['source_id'],
        'source_id': request['service_binding']['source_id'],
        'destination_id': request['service_binding']['destination_id'],
        'idempotency_key': request['claim_request_id'],
        'room_uri': 'mimi://station.example/room',
        'binding_room_uri': 'mimi://station.example/room',
        'binding_realm_id': request['intended_realm_id'],
        'binding_group_id': request['mls_group_id'],
        'binding_active': True, 'native_authorized': True,
    }
    decisions = [{'name': 'eligible_native_source', 'overrides': {}, 'expect_valid': True}]
    for field, value in (
        ('provider_id', request['service_binding']['destination_id']),
        ('source_id', request['service_binding']['destination_id']),
        ('destination_id', request['service_binding']['source_id']),
        ('idempotency_key', 'another-request'), ('binding_room_uri', 'mimi://station.example/other'),
        ('binding_realm_id', 'another-realm'), ('binding_group_id', 'another-group'),
        ('binding_active', False), ('native_authorized', False),
    ):
        decisions.append({'name': 'reject_' + field, 'overrides': {field: value}, 'expect_valid': False})
    return {
        'version': '2026-10-23.3', 'profile': 'ak.profile.mimi_interop.v1',
        'suite': 'mimi_key_material_claim', 'operation_id': OP,
        'runner': {'kind': 'json_schema_and_semantic_cases', 'command': 'python -B -m unittest tools.test_mimi_key_material_claim_contract'},
        'generated_by': 'tools/generate_mimi_key_material_fixture.py',
        'description': 'Native closed carriers, real participant/receipt Ed25519 signatures and adapter boundary mutations. Authority facts are synthetic inputs; this fixture is not live provider, MLS processing, database atomicity or product acceptance evidence.',
        'machine_contracts': [REQUEST, OUTCOME],
        'participant_public_key': b64(participant.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)),
        'destination_public_key': b64(destination.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)),
        'request': request, 'outcome': outcome, 'world': world,
        'schema_validation_cases': cases, 'decision_cases': decisions,
        'native_lifecycle_cases': [
            {'fixture': 'keypackage-lifecycle-fixture.json', 'case': name} for name in (
                'peer_claim_atomic_idempotency', 'peer_claim_double_authorization_privacy',
                'welcome_add_commit_and_claim_record_binding', 'welcome_consume_only_after_durable_group_state')],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    content = json.dumps(build(), ensure_ascii=False, indent=2) + '\n'
    if args.check:
        if OUT.read_text(encoding='utf-8') != content:
            raise SystemExit('MIMI claim fixture drift')
    else:
        OUT.write_text(content, encoding='utf-8', newline='\n')
