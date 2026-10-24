"""Generate closed registration carriers and a reproducible control signature."""
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ART = Path(__file__).resolve().parents[1] / 'spec/v1/artifacts'
OUT = ART / 'fixtures/published-did-registration-fixture.json'
SEED = bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60')
DOMAIN = b'ak.account_registration_control_proof.v1\n'


def jcs(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def digest(value):
    return 'sha256:' + hashlib.sha256(jcs(value)).hexdigest()


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def request_digest(request):
    value = deepcopy(request)
    value['proof'].pop('signature', None)
    value['proof'].pop('request_canonical_digest', None)
    return digest(value)


def build():
    genesis = json.loads((ART / 'fixtures/pcr-genesis-fixture.json').read_text(encoding='utf-8'))
    content = json.loads((ART / 'fixtures/content-bound-event-id-fixture.json').read_text(encoding='utf-8'))
    root = genesis['identity_creation_control_transcript']['signed_object']
    anchor = deepcopy(genesis['principal_registration_anchor_evidence']['anchor'])
    create_case = next(x for x in content['cases'] if x['name'].startswith('principal_control_realm_id_is_event_derived'))
    create = deepcopy(create_case['complete_wire_event'])
    authorize = deepcopy(create)
    authorize['kind'] = 'ak.device.authorize'
    authorize['payload'] = deepcopy(genesis['founding_authorize']['payload'])
    authorize['event_id'] = next(x for x in content['cases'] if x['name'] == 'human_founding_device_authorize_binds_the_derived_realm')['derived_event_id']
    session = {
        'device_id': genesis['founding_device_descriptor']['device_id'],
        'session_public_key': genesis['initial_session_request']['value']['session_public_key'],
        'audience_id': root['audience_id'],
    }
    evidence = {
        'principal_id': root['principal_id'], 'did': root['did'],
        'adapter_version': 'did:webvh:1.0',
        'method_history_head': anchor and genesis['principal_registration_anchor_evidence']['derivations']['method_history_head'],
        'version_id': root['did_version_id'], 'control_key_digest': root['control_key_digest'],
        'method_evidence': {'kind': 'ak.did.binding_evidence.v1', 'method': 'webvh',
            'document_digest': digest(anchor['normalized_did_document']), 'method_proofs': []},
        'control_proof': {'verification_method': genesis['principal_registration_anchor_evidence']['derivations']['root_verification_method'],
            'created_at': root['issued_at']},
    }
    evidence_transcript = {key: evidence[key] for key in ('principal_id', 'did', 'adapter_version', 'method_history_head', 'version_id', 'control_key_digest')}
    evidence_transcript.update(context='ak.registration_did_evidence_control_proof.v1', method_evidence_digest=digest(evidence['method_evidence']), **evidence['control_proof'])
    header = b64(jcs({'alg': 'Ed25519'}))
    signing_input = (header + '.' + b64(jcs(evidence_transcript))).encode()
    evidence['control_proof']['jws'] = header + '..' + b64(Ed25519PrivateKey.from_private_bytes(SEED).sign(signing_input))
    published = {
        'identity_creation_lease_id': root['identity_creation_lease_id'], 'lease_fence': root['lease_fence'],
        'did': root['did'], 'principal_registration_anchor': anchor,
        'registration_did_evidence_draft': evidence,
        'pcr_genesis_unit': {'events': [create, authorize]}, 'initial_session': session,
    }
    proof = {key: deepcopy(root[key]) for key in ('challenge_id', 'challenge', 'account_subject', 'principal_id', 'did', 'did_version_id', 'control_key_digest', 'registration_anchor_digest', 'pcr_realm_id', 'genesis_unit_kinds', 'identity_creation_lease_id', 'lease_fence', 'dpop_jkt', 'audience_id', 'origin', 'trust_domain', 'issued_at', 'expires_at')}
    proof.update(proof_kind='did_bound_signature', purpose='account_binding_for_published_did',
        realm_create_payload_digest=digest(create['payload']),
        founding_authorize_payload_digest=digest(authorize['payload']),
        initial_session_request_digest=digest(session),
        verification_method=evidence['control_proof']['verification_method'], signature_algorithm='Ed25519')
    request = {'principal_id': root['principal_id'], 'did': root['did'], 'proof': proof, 'published_identity': published}
    proof['request_canonical_digest'] = request_digest(request)
    proof['signature'] = b64(Ed25519PrivateKey.from_private_bytes(SEED).sign(DOMAIN + jcs(proof)))
    creation = deepcopy(published)
    creation['control_proof'] = deepcopy(root)
    new_request = {'principal_id': root['principal_id'], 'did': root['did'], 'identity_creation': creation}
    challenge = {key: deepcopy(published[key]) for key in ('identity_creation_lease_id', 'lease_fence', 'did', 'principal_registration_anchor')}
    challenge.update(request_id='ak:request:019a0000-0000-7000-8000-000000000001', principal_id=root['principal_id'])
    for key in ('pcr_realm_id', 'realm_create_payload_digest', 'founding_authorize_payload_digest', 'initial_session_request_digest'):
        challenge[key] = proof[key]
    complete_external = dict(evidence, validated_at='2026-08-09T00:00:01.000Z')
    complete_new = dict(evidence, accepted_at='2026-08-08T00:00:00.000Z')
    cases = []
    def case(name, definition, instance, valid):
        cases.append({'name': name, 'schema_ref': 'schemas/' + definition, 'instance': instance, 'expect_valid': valid})
        if not valid:
            if name.startswith('published_missing_'):
                expected = repr(name.removeprefix('published_missing_')) + ' is a required property'
            elif name == 'old_did_only_challenge':
                expected = "'identity_creation_lease_id' is a required property"
            elif name == 'partial_genesis':
                expected = 'is too short'
            elif name == 'reversed_genesis':
                expected = "'ak.realm.create' was expected"
            elif name == 'forbidden_outer_device_id':
                expected = 'Additional properties are not allowed'
            else:
                expected = 'is not valid under any of the given schemas'
            cases[-1]['first_expected_error'] = 'contains:' + expected
    register = 'account-operations.schema.json#/$defs/account_register_request_body'
    case('complete_published_registration', register, request, True)
    case('existing_new_did_request_shape_preserved', register, new_request, True)
    for member in ('published_identity', 'proof'):
        bad = deepcopy(request)
        del bad[member]
        case('missing_' + member, register, bad, False)
    for member in published:
        bad = deepcopy(request)
        del bad['published_identity'][member]
        case('published_missing_' + member, register, bad, False)
    for member, value in [('identity_creation', creation), ('device_id', session['device_id'])]:
        case('forbidden_outer_' + member, register, dict(request, **{member: value}), False)
    bad = deepcopy(request)
    bad['published_identity']['pcr_genesis_unit']['events'].pop()
    case('partial_genesis', register, bad, False)
    bad = deepcopy(request)
    bad['published_identity']['pcr_genesis_unit']['events'].reverse()
    case('reversed_genesis', register, bad, False)
    case('complete_did_challenge', 'account-operations.schema.json#/$defs/did_binding_challenge_request_body', challenge, True)
    case('old_did_only_challenge', 'account-operations.schema.json#/$defs/did_binding_challenge_request_body', {k: challenge[k] for k in ('request_id', 'principal_id', 'did')}, False)
    for name, value, valid in [('external_validation', complete_external, True), ('new_registry_acceptance', complete_new, True), ('mixed_time_roles', dict(complete_external, accepted_at=complete_new['accepted_at']), False)]:
        case(name, 'registration-did-evidence.schema.json#/$defs/accepted_registration_did_evidence', value, valid)
    return {
        'version': 2, 'suite': 'published_did_registration', 'fixture_kind': 'schema_only',
        'generated_by': 'tools/generate_published_did_registration_fixture.py',
        'covers_vectors': ['ak.vector.identity.published_did_registration.v1'],
        'runner': {'kind': 'json_schema_and_semantic_cases', 'command': 'python -B -m unittest tools.test_published_did_registration_contract'},
        'description': 'Schema-only genesis/draft objects include placeholder signatures and do not prove method, witness or Event verification. The outer account-control Ed25519 signature is real and reproducible under a published test key. Existing method/rotation/witness and genesis vectors remain independent prerequisites; this is not live external hosting, database atomicity or product acceptance.',
        'control_public_key': b64(Ed25519PrivateKey.from_private_bytes(SEED).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)),
        'request': request, 'challenge': challenge,
        'method_and_genesis_prerequisites': ['did-webvh-v1-fixture.json', 'did-webvh-witness-fixture.json', 'pcr-genesis-fixture.json'],
        'schema_validation_cases': cases,
    }


if __name__ == '__main__':
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(OUT.name)
