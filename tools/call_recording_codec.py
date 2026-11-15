"""Reference bytes for the registered RTC recording STREAM binding.

MLS public source/authorization are explicit qualified fixture inputs. This
module proves RFC 9420/XChaCha bytes, not native MLS admission, HTTP or storage.
It deliberately does not construct an EncryptedAttachment or its Context.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import re

from nacl.bindings import (
    crypto_aead_xchacha20poly1305_ietf_decrypt,
    crypto_aead_xchacha20poly1305_ietf_encrypt,
)
from nacl.exceptions import CryptoError

from tools.content_history import expand, jcs

ALGORITHM = "mls_exporter_aead_xchacha20poly1305_stream"
LABEL = "ak.rtc-recording-key/v1"
MIN_SEGMENT_BYTES = 1024
MAX_SEGMENT_BYTES = 8 * 1024 * 1024
MAX_SEGMENTS = 1 << 20
TAG_BYTES = 16
CONTEXT_FIELDS = {
    "realm_id", "call_id", "focus_id", "recording_id", "media_service_id",
    "recording_start_event_id",
}
ENCRYPTION_FIELDS = {
    "encryption_algorithm", "exporter_label", "context", "key_ref",
    "nonce_prefix", "segment_bytes",
}
CODEC_CASES = [
    ("recording_codec_" + name, "accept")
    for name in ("multi_segment", "empty", "single_octet", "exact_segment")
] + [
    ("recording_codec_" + name, "reject")
    for name in (
        "tag_changed_digest_updated", "wrong_aad_media_type", "wrong_epoch_secret",
        "truncate_updated_length_and_digest", "append_updated_length_and_digest",
        "segment_reordered", "prefix_padding", "prefix_noncanonical_tail", "prefix_short",
        "legacy_whole_algorithm", "legacy_aes_stream_algorithm", "scheme_mirror",
        "plaintext_size_mirror", "missing_start_key_ref", "changed_key_ref_encoding",
        "wrong_source_scope", "wrong_source_event", "wrong_context_start",
        "wrong_segment_bytes", "invalid_ciphertext_length_gap",
    )
]


def b64u(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def unb64u(value, width=None):
    if not isinstance(value, str):
        raise ValueError("binary value is not a string")
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except Exception as exc:
        raise ValueError("binary alphabet") from exc
    if b64u(raw) != value or (width is not None and len(raw) != width):
        raise ValueError("binary canonical form or width")
    return raw


def dimensions(ciphertext_bytes, segment_bytes):
    """Uniquely invert B=P+16 max(1,ceil(P/L)); never trust a count mirror."""
    if type(ciphertext_bytes) is not int or type(segment_bytes) is not int:
        raise ValueError("non-integer length")
    if not MIN_SEGMENT_BYTES <= segment_bytes <= MAX_SEGMENT_BYTES:
        raise ValueError("segment size bound")
    if not TAG_BYTES <= ciphertext_bytes <= MAX_SEGMENTS * (segment_bytes + TAG_BYTES):
        raise ValueError("ciphertext length bound")
    width = segment_bytes + TAG_BYTES
    count = max(1, ciphertext_bytes // width + bool(ciphertext_bytes % width))
    size = ciphertext_bytes - TAG_BYTES * count
    if size < 0 or count != max(1, size // segment_bytes + bool(size % segment_bytes)):
        raise ValueError("noncanonical ciphertext length gap")
    if not 1 <= count <= MAX_SEGMENTS or count > 1 << 32:
        raise ValueError("segment count bound")
    return size, count


def state_event_id(key_ref):
    if not isinstance(key_ref, dict) or set(key_ref) != {"algorithm", "group_state_ref"}:
        raise ValueError("closed MLS key reference")
    if key_ref["algorithm"] != "MLS":
        raise ValueError("MLS key reference algorithm")
    value = key_ref["group_state_ref"]
    if isinstance(value, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        return "ak:event:" + b64u(b"\x01" + bytes.fromhex(value[7:]))
    if not isinstance(value, str) or not value.startswith("ak:event:"):
        raise ValueError("group-state reference")
    raw = unb64u(value[9:], 33)
    if raw[0] != 1:
        raise ValueError("group-state Event identity suite")
    return value


def header(artifact, start, source):
    encryption = artifact["encryption"]
    if not isinstance(encryption, dict) or set(encryption) != ENCRYPTION_FIELDS:
        raise ValueError("closed recording encryption")
    if encryption["encryption_algorithm"] != ALGORITHM or encryption["exporter_label"] != LABEL:
        raise ValueError("recording algorithm or label")
    context = encryption["context"]
    if not isinstance(context, dict) or set(context) != CONTEXT_FIELDS:
        raise ValueError("closed RTC Context")
    for field in ("realm_id", "call_id", "recording_id", "recording_start_event_id"):
        if context[field] != artifact[field]:
            raise ValueError("recording parent Context")
    if context["media_service_id"] != artifact["produced_by"]:
        raise ValueError("recording producer Context")
    if context["focus_id"] != source["focus_id"]:
        raise ValueError("recording accepted focus")
    if start["kind"] != "ak.call.recording.start" or start["payload"]["capture_kind"] != "recording":
        raise ValueError("recording original Start")
    payload = start["payload"]
    if (start["event_id"] != artifact["recording_start_event_id"]
            or start["realm_id"] != artifact["realm_id"]
            or payload["call_id"] != artifact["call_id"]
            or payload["recording_id"] != artifact["recording_id"]
            or payload["recording_agent_id"] != artifact["produced_by"]):
        raise ValueError("recording Start binding")
    if encryption["key_ref"] != payload["capture_metadata"]["key_ref"]:
        raise ValueError("recording key reference changed after Start")
    event_id = state_event_id(encryption["key_ref"])
    if (event_id != source["group_state_event_ref"]
            or source["effective_scope"] != start["scope_ref"]
            or source["effective_scope"]["realm_id"] != artifact["realm_id"]):
        raise ValueError("qualified winning group-state source")
    # Source availability/winning authority are the declared reference boundary;
    # no serialized bool here is a production authorization assertion.
    if not re.fullmatch(r"0|[1-9][0-9]*", source["epoch"]):
        raise ValueError("source epoch")
    state_event_id({"algorithm": "MLS", "group_state_ref": source["genesis_event_ref"]})
    prefix = unb64u(encryption["nonce_prefix"], 19)
    dimensions(artifact["size_bytes"], encryption["segment_bytes"])
    return encryption, prefix


def recording_key(exporter_secret, context):
    """RFC 9420 MLS-Exporter: DeriveSecret then exported/Hash(Context)."""
    if len(exporter_secret) != 32:
        raise ValueError("fixture exporter secret width")
    derived = expand(exporter_secret, LABEL, b"", 32)
    return expand(derived, "exported", hashlib.sha256(jcs(context)).digest(), 32)


def segment_aad(artifact, index, last):
    encryption = artifact["encryption"]
    return jcs({
        "encryption_algorithm": encryption["encryption_algorithm"],
        "exporter_label": encryption["exporter_label"],
        "context": encryption["context"], "key_ref": encryption["key_ref"],
        "nonce_prefix": encryption["nonce_prefix"],
        "segment_bytes": encryption["segment_bytes"], "media_type": artifact["media_type"],
        "segment_index": index, "last_segment_flag": 1 if last else 0,
    })


def segment_nonce(prefix, index, last):
    if len(prefix) != 19 or not 0 <= index < MAX_SEGMENTS:
        raise ValueError("segment nonce input")
    return prefix + index.to_bytes(4, "big") + bytes([1 if last else 0])


def seal(plaintext, artifact, start, source):
    artifact = copy.deepcopy(artifact)
    length = artifact["encryption"]["segment_bytes"]
    count = max(1, len(plaintext) // length + bool(len(plaintext) % length))
    artifact["size_bytes"] = len(plaintext) + TAG_BYTES * count
    encryption, prefix = header(artifact, start, source)
    key = recording_key(unb64u(source["exporter_secret"], 32), encryption["context"])
    chunks, aads, nonces = [], [], []
    for index in range(count):
        last = index == count - 1
        aad, nonce = segment_aad(artifact, index, last), segment_nonce(prefix, index, last)
        chunks.append(crypto_aead_xchacha20poly1305_ietf_encrypt(
            plaintext[index * length:(index + 1) * length], aad, nonce, key))
        aads.append(b64u(aad))
        nonces.append(b64u(nonce))
    ciphertext = b"".join(chunks)
    artifact["blob_ref"] = "ak:blob:sha256:" + hashlib.sha256(ciphertext).hexdigest()
    return artifact, {"key": b64u(key), "segment_aad": aads, "segment_nonces": nonces,
                      "ciphertext": b64u(ciphertext)}


def open_recording(ciphertext, artifact, start, source):
    encryption, prefix = header(artifact, start, source)
    size, count = dimensions(artifact["size_bytes"], encryption["segment_bytes"])
    if len(ciphertext) != artifact["size_bytes"]:
        raise ValueError("actual ciphertext length")
    # This registered byte KAT explicitly selects the active SHA-256 Blob suite.
    # Other active Blob suites remain owned by the general Blob implementation.
    if artifact["blob_ref"] != "ak:blob:sha256:" + hashlib.sha256(ciphertext).hexdigest():
        raise ValueError("ciphertext Blob commitment")
    key = recording_key(unb64u(source["exporter_secret"], 32), encryption["context"])
    plaintext, offset = [], 0
    for index in range(count):
        last = index == count - 1
        width = (size - index * encryption["segment_bytes"] if last
                 else encryption["segment_bytes"]) + TAG_BYTES
        segment = ciphertext[offset:offset + width]
        try:
            plaintext.append(crypto_aead_xchacha20poly1305_ietf_decrypt(
                segment, segment_aad(artifact, index, last), segment_nonce(prefix, index, last), key))
        except CryptoError as exc:
            raise ValueError("recording segment authentication") from exc
        offset += width
    if offset != len(ciphertext):
        raise ValueError("trailing ciphertext")
    return b"".join(plaintext)


def run_codec_case(kat, name):
    suffix = name.removeprefix("recording_codec_")
    positive = next((v for v in kat["vectors"] if v["name"] == suffix), None)
    vector = copy.deepcopy(positive or kat["vectors"][0])
    artifact = vector["artifact"]
    start, source = copy.deepcopy(kat["start_event"]), copy.deepcopy(kat["qualified_source"])
    ciphertext = unb64u(vector["expected"]["ciphertext"])
    encryption = artifact["encryption"]
    if positive is None:
        if suffix == "tag_changed_digest_updated":
            ciphertext = ciphertext[:-1] + bytes([ciphertext[-1] ^ 1])
        elif suffix == "wrong_aad_media_type": artifact["media_type"] = "video/mp4"
        elif suffix == "wrong_epoch_secret": source["exporter_secret"] = b64u(bytes(32))
        elif suffix == "truncate_updated_length_and_digest":
            ciphertext = ciphertext[:encryption["segment_bytes"] + TAG_BYTES]
        elif suffix == "append_updated_length_and_digest": ciphertext += ciphertext[:16]
        elif suffix == "segment_reordered":
            width = encryption["segment_bytes"] + TAG_BYTES
            ciphertext = ciphertext[width:] + ciphertext[:width]
        elif suffix == "prefix_padding": encryption["nonce_prefix"] += "=="
        elif suffix == "prefix_noncanonical_tail":
            encryption["nonce_prefix"] = encryption["nonce_prefix"][:-1] + "h"
        elif suffix == "prefix_short": encryption["nonce_prefix"] = b64u(bytes(18))
        elif suffix == "legacy_whole_algorithm": encryption["encryption_algorithm"] = ALGORITHM.removesuffix("_stream")
        elif suffix == "legacy_aes_stream_algorithm": encryption["encryption_algorithm"] = "mls_exporter_aead_aes_256_gcm_stream"
        elif suffix == "scheme_mirror": encryption["scheme"] = "ak.blob.stream_aead.v1"
        elif suffix == "plaintext_size_mirror": encryption["plaintext_size"] = 1041
        elif suffix == "missing_start_key_ref": del start["payload"]["capture_metadata"]["key_ref"]
        elif suffix == "changed_key_ref_encoding":
            raw = unb64u(encryption["key_ref"]["group_state_ref"][9:], 33)
            encryption["key_ref"]["group_state_ref"] = "sha256:" + raw[1:].hex()
        elif suffix == "wrong_source_scope": source["effective_scope"] = {"kind": "realm", "realm_id": "ak:realm:wrong"}
        elif suffix == "wrong_source_event": source["group_state_event_ref"] = source["genesis_event_ref"]
        elif suffix == "wrong_context_start": encryption["context"]["recording_start_event_id"] = source["genesis_event_ref"]
        elif suffix == "wrong_segment_bytes": encryption["segment_bytes"] = 2048
        elif suffix == "invalid_ciphertext_length_gap":
            artifact["size_bytes"] = encryption["segment_bytes"] + 17
        else: raise ValueError("unregistered recording codec case")
        if suffix in ("tag_changed_digest_updated", "truncate_updated_length_and_digest", "append_updated_length_and_digest", "segment_reordered"):
            artifact["size_bytes"] = len(ciphertext)
            artifact["blob_ref"] = "ak:blob:sha256:" + hashlib.sha256(ciphertext).hexdigest()
    plaintext = open_recording(ciphertext, artifact, start, source)
    if plaintext != unb64u(vector["plaintext"]):
        raise ValueError("recording plaintext bytes")
    return "accept"
