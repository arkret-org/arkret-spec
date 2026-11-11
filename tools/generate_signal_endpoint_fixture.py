"""Regenerate the Signal section of the existing private KDF fixture."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from .content_history import b64, expand, jcs, vector_prefix

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec/v1/artifacts/fixtures/arkret-private-kdf-fixture.json"


def event(number):
    return "ak:event:" + b64(b"\x01" + hashlib.sha256(bytes([number])).digest())


def endpoint(seed, device=None, method=None, authorization=1, principal="signal.example", station="station.example"):
    key = Ed25519PrivateKey.from_private_bytes(bytes([seed]) * 32)
    return {
        "actor_id": {"kind": "account", "account_id": {
            "principal_id": "ak:did_core:web:" + principal,
            "station_id": "ak:did_core:web:" + station}},
        "endpoint": ({"kind": "device", "device_id": device} if device else
                     {"kind": "agent_runtime", "verification_method": method}),
        "authorization_event_ref": event(authorization),
        "signature_key_base64url": b64(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)),
    }


def build(source):
    result = copy.deepcopy(source)
    kat = next(row for row in result["cases"] if row["name"] == "signal_exporter_key_sha256_aes128gcm")
    given, expected = kat["input"], kat["expected"]
    phone = endpoint(1, "ak:device:01904100-0000-7000-8000-000000000006")
    laptop = endpoint(2, "ak:device:01904100-0000-7000-8000-00000000000e", authorization=2)
    agent = endpoint(3, method="did:web:agent.example#runtime-1", principal="agent.example", authorization=3)
    domains = {
        "human_phone": phone,
        "human_laptop": laptop,
        "human_other_actor": {**phone, "actor_id": endpoint(1, principal="other.example")["actor_id"]},
        "human_other_station": {**phone, "actor_id": endpoint(1, station="other-station.example")["actor_id"]},
        "human_reauthorized": {**phone, "authorization_event_ref": event(4)},
        "human_new_leaf_key": {**phone, "signature_key_base64url": laptop["signature_key_base64url"]},
        "agent_old": agent,
        "agent_new_key": {**agent, "signature_key_base64url": phone["signature_key_base64url"]},
        "agent_new_method": {**agent, "endpoint": {"kind": "agent_runtime", "verification_method": "did:web:agent.example#runtime-2"}},
        "agent_reauthorized": {**agent, "authorization_event_ref": event(5)},
    }
    exporter_secret = bytes.fromhex(given["exporter_secret_hex"])
    scope = given["realm_id_utf8"].encode()
    derived = expand(exporter_secret, "ak.signal-root-v1", b"", 32)
    root = expand(derived, "exported", hashlib.sha256(scope).digest(), 32)
    key = lambda context: expand(root, "ak.signal-v1", context, given["aead_nk"])
    given["verified_endpoint"] = phone
    given["verified_sender_domain_utf8"] = jcs(phone).decode()
    given["verified_sender_domain_hex"] = jcs(phone).hex()
    label = b"MLS 1.0 ak.signal-v1"
    expected["signal_root_hex"] = root.hex()
    expected["signal_expand_with_label_info_hex"] = (
        given["aead_nk"].to_bytes(2, "big") + vector_prefix(len(label)) + label
        + vector_prefix(len(jcs(phone))) + jcs(phone)).hex()
    expected["signal_key_hex"] = key(jcs(phone)).hex()
    expected["peer_verified_endpoint"] = laptop
    expected["peer_verified_sender_domain_utf8"] = jcs(laptop).decode()
    expected["peer_signal_key_hex"] = key(jcs(laptop)).hex()
    kat["note"] = "Direct RFC8785 JCS bytes of the closed verified endpoint instance, not Actor-only identity, bare DeviceId, a context hash or a JSON-wrapped string. Native authority remains an independent prerequisite."
    rows = []
    for name, domain in domains.items():
        rows.append({"name": name, "verified_endpoint": domain,
                     "sender_domain_utf8": jcs(domain).decode(),
                     "sender_domain_hex": jcs(domain).hex(),
                     "signal_key_hex": key(jcs(domain)).hex()})
    nonce = bytes(12)
    p1, p2 = b"first device confidential Signal", b"other device different Signal!!"
    aad1 = jcs({"sender_actor_id": phone["actor_id"], "sender_device_id": phone["endpoint"]["device_id"]})
    aad2 = jcs({"sender_actor_id": laptop["actor_id"], "sender_device_id": laptop["endpoint"]["device_id"]})
    result["signal_endpoint_contract"] = {
        "generated_by": "python -m tools.generate_signal_endpoint_fixture",
        "context_schema_ref": "schemas/content-encryption.schema.json#/$defs/endpoint",
        "authority_boundary": "Verified native endpoint and accepted MLS leaf provenance are test inputs; this fixture does not establish real Station admission, production persistence or deployment exploitability.",
        "domains": rows,
        "same_actor_equal_nonce_aead": {
            "first": "human_phone", "second": "human_laptop", "nonce_hex": nonce.hex(),
            "first_plaintext_hex": p1.hex(), "second_plaintext_hex": p2.hex(),
            "first_aad_hex": aad1.hex(), "second_aad_hex": aad2.hex(),
            "first_ciphertext_hex": AESGCM(key(jcs(phone))).encrypt(nonce, p1, aad1).hex(),
            "second_ciphertext_hex": AESGCM(key(jcs(laptop))).encrypt(nonce, p2, aad2).hex(),
            "aad_boundary": "Distinct synthetic associated-data inputs for the primitive KAT, not complete wire Signal headers or producer proofs.",
            "ciphertext_xor_equals_plaintext_xor": False,
        },
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = json.loads(FIXTURE.read_text(encoding="utf-8"))
    expected = build(source)
    if args.check and source != expected:
        print("Signal endpoint fixture drift")
        return 1
    if not args.check:
        FIXTURE.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Signal endpoint KDF and AEAD fixture: exact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
