"""Byte-exact reference primitives for the recoverable application contract."""
import base64
import hashlib
import hmac
import json

ROOT_LABEL = "ak.epoch-content-root-v1"
CONTENT_LABEL = "ak.content-v1"
SCHEME = "ak.encryption.epoch_content_aead.v1"
STRATEGY = "ak.encryption_backup.epoch_content_roots.v1"


def jcs(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def unb64(value):
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if b64(raw) != value:
        raise ValueError("noncanonical binary encoding")
    return raw


def vector_prefix(length):
    if length < 64:
        return bytes([length])
    if length < 16384:
        return (length | 0x4000).to_bytes(2, "big")
    if length < 1 << 30:
        return (length | 0x80000000).to_bytes(4, "big")
    raise ValueError("MLS vector too long")


def expand(secret, label, context, length):
    full_label = b"MLS 1.0 " + label.encode("ascii")
    info = length.to_bytes(2, "big") + vector_prefix(len(full_label)) + full_label + vector_prefix(len(context)) + context
    previous = b""
    output = b""
    for counter in range(1, 256):
        previous = hmac.new(secret, previous + info + bytes([counter]), "sha256").digest()
        output += previous
        if len(output) >= length:
            return output[:length]
    raise ValueError("HKDF length")


def content_root(exporter_secret, root_context):
    derived = expand(exporter_secret, ROOT_LABEL, b"", 32)
    return expand(derived, "exported", hashlib.sha256(jcs(root_context)).digest(), 32)


def root_ref(root, context):
    return "sha256:" + hashlib.sha256(b"ak.content.root_ref.v1\n" + jcs(context) + root).hexdigest()


def content_key(root, context, length=16):
    return expand(root, CONTENT_LABEL, hashlib.sha256(jcs(context)).digest(), length)


def key_commitment(key, context):
    return "sha256:" + hashlib.sha256(b"ak.content.key_commitment.v1\n" + jcs(context) + key).hexdigest()


def aad(outer_event, envelope, context):
    frozen = {k: v for k, v in outer_event.items() if k not in {"event_id", "payload", "producer_proof", "unsigned"}}
    metadata = {k: v for k, v in envelope.items() if k != "ciphertext"}
    return jcs({"outer_event": frozen, "envelope": metadata, "content_context": context})
