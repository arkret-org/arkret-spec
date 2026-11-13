"""History selector/key primitives; callers independently qualify native originals.

This is not an Event/Commit, current authorization, MLS provenance or replay
verifier. The caller also qualifies the target's registered typed location;
shape matching alone never registers an arbitrary extension as a key slot.
The opener must authenticate each parent envelope and its plaintext schema
before returning a value; no root is an input to selector resolution.
"""
import re
from functools import lru_cache

from tools.artifact_lint.core import ARTIFACTS, schema_validator
from tools.content_history import key_commitment


@lru_cache
def validator(name, fragment):
    return schema_validator(ARTIFACTS / "schemas" / name, fragment)


def is_envelope(value):
    return (isinstance(value, dict) and "encryption_scheme" in value
            and validator("encrypted-envelope.schema.json", "#").is_valid(value))


def locate_key_target(original, selector, open_envelope):
    validator("content-encryption.schema.json", "#/$defs/key_selector").validate(selector)
    if selector["kind"] != "content_key" or selector["source_event_ref"] != original["event_id"]:
        raise ValueError("selector is not for this original Event")
    node, consumed = original, []
    for encoded in selector["content_path"].split("/")[1:]:
        if is_envelope(node):
            path = "/" + "/".join(consumed)
            node = open_envelope(path, node)
        token = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", token) or int(token) >= len(node):
                raise ValueError("noncanonical or missing array index")
            node = node[int(token)]
        elif isinstance(node, dict) and token in node:
            node = node[token]
        else:
            raise ValueError("missing content path")
        consumed.append(encoded)
    if is_envelope(node):
        return "envelope", node
    validator("blob.schema.json", "#/$defs/encrypted_attachment").validate(node)
    return "attachment", node


def attachment_dek(material, descriptor, context):
    """Check an already HPKE-opened selected key, without R or another KDF.

    The context comes from independently authenticated original group/producer
    facts. AEAD, immutable AAD, ciphertext commitment and replay follow this
    check; it does not itself confer any read/disclosure authority.
    """
    validator("blob.schema.json", "#/$defs/encrypted_attachment").validate(descriptor)
    if (len(material) != 32
            or context["scheme"] != descriptor.get("scheme", "ak.blob.whole_file_aead.v1")
            or any(context[field] != descriptor[field] for field in
                   ("producer", "encryption_algorithm", "content_key_salt"))
            or key_commitment(material, context) != descriptor["key_commitment"]):
        raise ValueError("wrong selected attachment key or original context")
    return material


def require_epoch_root_disclosure(epoch_closed, entire_epoch_authorized):
    if not epoch_closed or not entire_epoch_authorized:
        raise ValueError("a partial or open epoch permits selected DEKs only")
