"""Check the exact Signal endpoint contract and independently evaluate its KATs."""

import hashlib
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
from jsonschema import ValidationError

from .core import ARTIFACTS, load_json
from ..signal_endpoint import CONTEXT_ENCODING, CONTEXT_SCHEMA, FIELDS, sender_domain


def label_info(label, context, length):
    def vector(size):
        if size < 64:
            return bytes([size])
        if size < 16384:
            return (0x4000 | size).to_bytes(2, "big")
        return (0x80000000 | size).to_bytes(4, "big")
    label_bytes = ("MLS 1.0 " + label).encode("ascii")
    return length.to_bytes(2, "big") + vector(len(label_bytes)) + label_bytes + vector(len(context)) + context


def derive(secret, label, context, length):
    return HKDFExpand(algorithm=hashes.SHA256(), length=length,
                      info=label_info(label, context, length)).derive(secret)


def verify_fixture(fixture):
    kat = next(row for row in fixture["cases"] if row["name"] == "signal_exporter_key_sha256_aes128gcm")
    given, expected = kat["input"], kat["expected"]
    assert given["signal_root_label"] == "ak.signal-root-v1" and given["signal_label"] == "ak.signal-v1"
    assert given["aead_nk"] == 16
    secret = bytes.fromhex(given["exporter_secret_hex"])
    root = derive(derive(secret, "ak.signal-root-v1", b"", 32), "exported",
                  hashlib.sha256(given["realm_id_utf8"].encode()).digest(), 32)
    domain = sender_domain(given["verified_endpoint"])
    assert domain.decode() == given["verified_sender_domain_utf8"] and domain.hex() == given["verified_sender_domain_hex"]
    assert root.hex() == expected["signal_root_hex"]
    assert label_info("ak.signal-v1", domain, 16).hex() == expected["signal_expand_with_label_info_hex"]
    assert derive(root, "ak.signal-v1", domain, 16).hex() == expected["signal_key_hex"]
    peer = sender_domain(expected["peer_verified_endpoint"])
    assert peer.decode() == expected["peer_verified_sender_domain_utf8"]
    assert derive(root, "ak.signal-v1", peer, 16).hex() == expected["peer_signal_key_hex"]
    assert given["verified_endpoint"]["actor_id"] == expected["peer_verified_endpoint"]["actor_id"]
    assert domain != peer and expected["signal_key_hex"] != expected["peer_signal_key_hex"]
    contract = fixture["signal_endpoint_contract"]
    assert contract["context_schema_ref"] == CONTEXT_SCHEMA
    rows = {row["name"]: row for row in contract["domains"]}
    assert len(rows) == len(contract["domains"]) == 10
    assert set(rows) == {"human_phone", "human_laptop", "human_other_actor", "human_other_station",
                         "human_reauthorized", "human_new_leaf_key", "agent_old", "agent_new_key",
                         "agent_new_method", "agent_reauthorized"}
    for row in rows.values():
        context = sender_domain(row["verified_endpoint"])
        assert context.decode() == row["sender_domain_utf8"] and context.hex() == row["sender_domain_hex"]
        assert derive(root, "ak.signal-v1", context, 16).hex() == row["signal_key_hex"]
    assert len({row["signal_key_hex"] for row in rows.values()}) == len(rows)
    aead = contract["same_actor_equal_nonce_aead"]
    assert aead["first"] == "human_phone" and aead["second"] == "human_laptop"
    assert aead["nonce_hex"] == "00" * 12
    assert rows["human_phone"]["verified_endpoint"] == given["verified_endpoint"]
    assert rows["human_laptop"]["verified_endpoint"] == expected["peer_verified_endpoint"]
    plains, ciphertexts = [], []
    for prefix, name in (("first", aead["first"]), ("second", aead["second"])):
        key = bytes.fromhex(rows[name]["signal_key_hex"])
        plaintext = bytes.fromhex(aead[prefix + "_plaintext_hex"])
        aad = bytes.fromhex(aead[prefix + "_aad_hex"])
        ciphertext = bytes.fromhex(aead[prefix + "_ciphertext_hex"])
        assert AESGCM(key).encrypt(bytes(12), plaintext, aad) == ciphertext
        assert AESGCM(key).decrypt(bytes(12), ciphertext, aad) == plaintext
        plains.append(plaintext)
        ciphertexts.append(ciphertext[:-16])
    assert aead["first_aad_hex"] != aead["second_aad_hex"]
    assert bytes(a ^ b for a, b in zip(*plains)) != bytes(a ^ b for a, b in zip(*ciphertexts))
    assert aead["ciphertext_xor_equals_plaintext_xor"] is False


def check_signal_endpoint_contract(lint):
    path = ARTIFACTS / "fixtures/arkret-private-kdf-fixture.json"
    registry_path = ARTIFACTS / "registry/exporter-label-registry.json"
    try:
        registry = load_json(lint, registry_path)
        entry = next(row for row in registry["labels"] if row["label"] == "ak.signal-v1")
        assert entry["primitive"] == "ExpandWithLabel" and entry["parent_secret"] == "ak.signal-root-v1"
        assert entry["context_fields"] == FIELDS and entry["context_schema_ref"] == CONTEXT_SCHEMA
        assert entry["context_encoding"] == CONTEXT_ENCODING and entry["output_bytes"] == "AEAD.Nk"
        assert entry["empty_context_forbidden"] is True and entry["grandfathered"] is False
        verify_fixture(load_json(lint, path))
    except (AssertionError, KeyError, ValueError, TypeError, StopIteration, ValidationError) as error:
        lint.fail(path, "Signal verified endpoint registry/KDF/AEAD contract drift: " + str(error))
