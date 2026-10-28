"""Regenerate named JSON primitive KATs from their explicit unsigned inputs."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'spec/v1/artifacts/fixtures'
NAMES = ['applet-registration-epoch-fixture.json', 'handle-claim-kat.json',
         'encoding-fixture.json', 'blob-content-key-fixture.json', 'mls-roster-client-roles-fixture.json',
         'websocket-binding-fixture.json']


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha(value):
    return 'sha256:' + hashlib.sha256(value.encode()).hexdigest()


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


def replace_values(value, replacements):
    if isinstance(value, dict):
        return {key: replace_values(child, replacements) for key, child in value.items()}
    if isinstance(value, list):
        return [replace_values(child, replacements) for child in value]
    return replacements.get(value, value) if isinstance(value, str) else value


def build(name, source):
    result = copy.deepcopy(source)
    if name == 'applet-registration-epoch-fixture.json':
        positive = result['positive']
        positive['canonical_bytes_utf8'] = canonical(positive['transcript'])
        positive['expected_registration_epoch'] = sha(result['domain_separator_utf8'] + positive['canonical_bytes_utf8'])
    elif name == 'handle-claim-kat.json':
        status = result['status']
        unsigned = {key: value for key, value in status['preimage'].items() if key != 'status_proof'}
        status['expected_digest'] = sha(status['domain'] + '\n' + canonical(unsigned))
        status['preimage']['status_proof']['payload_digest'] = status['expected_digest']
    elif name == 'encoding-fixture.json':
        for node in nodes(result):
            if 'expected_canonical_bytes_utf8' in node and 'expected_digest' in node:
                node['expected_digest'] = sha(node.get('domain_separator_utf8', '') + node['expected_canonical_bytes_utf8'])
        for node in nodes(result):
            if 'payload_metadata' in node:
                wire = canonical(node['payload_metadata'])
                node['expected_metadata_canonical_bytes_utf8'] = wire
                ciphertext = base64.urlsafe_b64decode(node['ciphertext_base64url'] + '===')
                node['expected_digest'] = 'sha256:' + hashlib.sha256(wire.encode() + ciphertext).hexdigest()
    elif name == 'blob-content-key-fixture.json':
        alias = next(row for row in result['cases'] if row['name'] == 'equivalent_refs')
        replacements = {}
        for field, digest_field in [('event_preimage_canonical_bytes_utf8', 'proof_hash'), ('wrong_preimage_utf8', 'wrong_proof_hash')]:
            event = json.loads(alias[field])
            for node in nodes(event):
                for key in ('governance_generation', 'covers_key_access_revision', 'key_access_revision', 'previous_epoch', 'next_epoch'):
                    if isinstance(node.get(key), int):
                        node[key] = str(node[key])
            preimage = canonical(event)
            digest = sha(preimage)
            replacements[alias[digest_field]] = digest
            alias[field] = preimage
            if field == 'event_preimage_canonical_bytes_utf8':
                replacements[alias['event_ref']] = 'ak:event:' + b64(b'\x01' + bytes.fromhex(digest[7:]))
        result = replace_values(result, replacements)
        # The exporter context is JSON; its epoch uses the canonical full-width representation.
        try:
            from .artifact_lint.blob_content_key import exporter
        except ImportError:
            from artifact_lint.blob_content_key import exporter
        for kat in result['kats']:
            kat['context']['epoch'] = str(kat['context']['epoch'])
            kat['context_utf8'] = canonical(kat['context'])
            kat['content_key_hex'] = exporter(bytes.fromhex(kat['exporter_secret_hex']), kat['context'], kat['hash']).hex()
    elif name == 'mls-roster-client-roles-fixture.json':
        kat = result['signature_binding_kat']
        for object_name, key_name, domain, seed in [
            ('claim_receipt', 'claim_receipt_signing_key', 'ak.peer-keypackage-claim-receipt-v1\n', bytes(range(32))),
            ('attestation', 'attestation_signing_key', 'ak.mls_add_authority_attestation.v1\n', bytes(range(32, 64))),
        ]:
            key = Ed25519PrivateKey.from_private_bytes(seed)
            kat[key_name]['public_key_base64url'] = b64(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
            value = kat[object_name]
            unsigned = {key: item for key, item in value.items() if key != 'signature'}
            value['signature']['signature'] = b64(key.sign(domain.encode() + canonical(unsigned).encode()))
    elif name == 'websocket-binding-fixture.json':
        case = next(row for row in result['frame_schema_cases'] if row['name'] == 'signal_data')
        frame = json.loads(case['wire_utf8'])
        envelope = frame['payload']['envelope']
        unsigned = {key: value for key, value in envelope.items() if key != 'proof'}
        envelope['proof']['envelope_digest'] = sha(canonical(unsigned))
        case['wire_utf8'] = canonical(frame)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    drift = []
    for name in NAMES:
        path = FIXTURES / name
        source = json.loads(path.read_text(encoding='utf-8'))
        expected = build(name, source)
        if expected != source:
            if args.check:
                drift.append(name)
            else:
                path.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    if drift:
        print('Named primitive KAT drift: ' + ', '.join(drift))
        return 1
    print('Named primitive KATs: canonical inputs, digests, exporter keys and real Ed25519 signatures regenerated')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
