"""Verify the registered attachment exporter contract and frozen RFC 9420 KATs."""

import base64
import hashlib
import hmac
import json
import re

from .core import ARTIFACTS, ROOT, load_json, schema_validator

FIELDS = ["effective_scope", "genesis_event_ref", "epoch", "scheme",
          "encryption_algorithm", "content_key_salt"]
LABEL = "ak.blob-content-key-v1"


def jcs(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def expand(secret, label, context, length, hash_name):
    label = b"MLS 1.0 " + label.encode("ascii")
    # RFC 9420 opaque<V> uses the minimal MLS variable-length vector prefix.
    assert len(label) < 64 and len(context) < 64
    info = (length.to_bytes(2, "big") + bytes([len(label)]) + label
            + bytes([len(context)]) + context)
    output = b""
    block = b""
    for counter in range(1, 256):
        block = hmac.new(secret, block + info + bytes([counter]), hash_name).digest()
        output += block
        if len(output) >= length:
            return output[:length]
    raise ValueError("HKDF output too long")


def exporter(secret, context, hash_name):
    nh = hashlib.new(hash_name).digest_size
    derived = expand(secret, LABEL, b"", nh, hash_name)
    return expand(derived, "exported", hashlib.new(hash_name, jcs(context)).digest(),
                  32, hash_name)


def check(lint, registry):
    path = ARTIFACTS / "fixtures/blob-content-key-fixture.json"
    try:
        entry = next(row for row in registry["labels"] if row["label"] == LABEL)
        assert entry["primitive"] == "MLS-Exporter"
        assert entry["context_fields"] == FIELDS and entry["output_bytes"] == 32
        assert entry["empty_context_forbidden"] is True
        fixture = load_json(lint, path)
        assert len(fixture["kats"]) == 4
        for kat in fixture["kats"]:
            context = kat["context"]
            assert set(context) == set(FIELDS)
            assert jcs(context).decode() == kat["context_utf8"]
            secret = bytes.fromhex(kat["exporter_secret_hex"])
            expected = bytes.fromhex(kat["content_key_hex"])
            assert exporter(secret, context, kat["hash"]) == expected
            for field, replacement in kat["separation_inputs"].items():
                altered = {**context, field: replacement}
                assert exporter(secret, altered, kat["hash"]) != expected
        schema = load_json(lint, ARTIFACTS / "schemas/blob.schema.json")
        descriptor = schema["$defs"]["encrypted_attachment"]
        assert "content_key_salt" in descriptor["required"]
        pattern = descriptor["properties"]["content_key_salt"]["pattern"]
        for case in fixture["salt_cases"]:
            salt = case["value"]
            valid = re.fullmatch(pattern, salt) is not None
            if valid:
                raw = base64.urlsafe_b64decode(salt + "=")
                valid = (len(raw) == 32 and
                         base64.urlsafe_b64encode(raw).decode().rstrip("=") == salt)
            assert valid == case["valid"]
        validator = schema_validator(ARTIFACTS / "schemas/blob.schema.json",
                                     "#/$defs/encrypted_attachment")
        for case in fixture["descriptor_cases"]:
            assert validator.is_valid(case["descriptor"]) == case["valid"]
        prose = (ROOT / "spec/v1/zh/crypto-media/media-and-blob.md").read_text(encoding="utf-8")
        assert LABEL in prose and "content_key_salt" in prose
    except (AssertionError, KeyError, ValueError, TypeError, StopIteration) as exc:
        lint.fail(path, f"attachment content-key contract/KAT drift: {exc}")
