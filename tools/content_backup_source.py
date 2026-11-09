"""Backup-source byte checks after independent native role and storage validation."""
import datetime
import hashlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from tools.content_history import jcs, unb64

DOMAIN = b'ak.content.backup_source.v1\n'


def protections_digest(registered_slots):
    """The caller projects actual registered typed slots, never arbitrary JSON."""
    if not registered_slots:
        raise ValueError('a backup source requires registered encrypted content')
    paths = []
    for slot in registered_slots:
        if (set(slot) != {'content_path', 'protection'}
                or not slot['content_path'].startswith('/payload/')
                or not slot['protection']['root_refs'] or not slot['protection']['backup_refs']):
            raise ValueError('incomplete registered protection slot')
        paths.append(slot['content_path'])
    if len(set(paths)) != len(paths):
        raise ValueError('duplicate registered content path')
    ordered = sorted(registered_slots, key=lambda row: row['content_path'].encode('utf-8'))
    return 'sha256:' + hashlib.sha256(jcs(ordered)).hexdigest()


def signing_bytes(attestation):
    return DOMAIN + jcs({k: v for k, v in attestation.items() if k != 'signature'})


def verify_backup_source_bytes(attestation, original_event, actual_producer,
                               registered_slots, origin_key, destination, evaluated_at):
    """No storage access, service-history validation or writer authority is implied.

    actual_producer, registered_slots and origin_key must come from independent
    original-event, typed-slot and method-native service qualification.
    """
    actor = actual_producer['actor_id']
    if (actor.get('kind') != 'account'
            or origin_key['station_id'] != actor['account_id']['station_id']
            or origin_key['verification_method'] != attestation['verification_method']
            or attestation['signature']['kid'] != attestation['verification_method']
            or attestation['signature'].get('signature_algorithm', 'Ed25519') != 'Ed25519'):
        raise ValueError('backup source is not the exact owning Station method')
    public = unb64(origin_key['public_key_base64url'])
    signature = unb64(attestation['signature']['signature'])
    if len(signature) != 64:
        raise ValueError('invalid backup source signature width')
    Ed25519PublicKey.from_public_bytes(public).verify(signature, signing_bytes(attestation))
    expected = {
        'event_ref': original_event['event_id'],
        'event_original_digest': 'sha256:' + hashlib.sha256(jcs(original_event)).hexdigest(),
        'producer': actual_producer,
        'effective_scope': original_event['scope_ref'],
        'destination_service_id': destination,
        'protections_digest': protections_digest(registered_slots),
    }
    if (any(attestation[key] != value for key, value in expected.items())
            or actor != original_event.get('executed_by', original_event['actor_id'])):
        raise ValueError('backup source differs from original Event, producer or destination')
    parse = datetime.datetime.fromisoformat
    created, expires, now = map(parse, [attestation['attested_at'], attestation['expires_at'], evaluated_at])
    if not (datetime.timedelta(0) < expires - created <= datetime.timedelta(seconds=300)
            and created <= now < expires):
        raise ValueError('backup source is outside its bounded observation window')
