"""Signal carrier closure and class-independent ciphertext size regression checks."""

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


SCHEMAS = Path(__file__).resolve().parents[1] / "spec/v1/artifacts/schemas"


class SignalEnvelopeSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources = []
        for path in SCHEMAS.glob("*.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            resources.append((document["$id"], Resource.from_contents(document)))
        cls.validator = Draft202012Validator(
            {"$ref": "https://arkret.org/v1/schemas/signal-envelope.schema.json"},
            registry=Registry().with_resources(resources),
        )

    def envelope(self):
        realm = "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5"
        device = "ak:device:01964137-1000-7000-8000-000000000011"
        return {
            "realm_id": realm,
            "scope_ref": {"kind": "realm", "realm_id": realm},
            "sender_actor_id": {
                "kind": "account",
                "account_id": {
                    "principal_id": "ak:did_core:webvh:z6mkfixture",
                    "station_id": "ak:did_core:webvh:z6mkfixturestation",
                },
            },
            "sender_device_id": device,
            "seal_ref": "ak:seal:sha256:" + "a" * 64,
            "signal_class": "session",
            "sent_at": "2026-08-31T00:00:00.000Z",
            "expires_at": "2026-08-31T00:00:30.000Z",
            "encrypted_payload": {
                "scheme": "ak.signal_exporter_aead.v1",
                "key_ref": {
                    "algorithm": "MLS-EXPORTER-AEAD",
                    "group_state_ref": "sha256:" + "b" * 64,
                },
                "purpose": "ak.signal.v1",
                "aead_profile": "ak.aead.aes128_gcm.v1",
                "epoch": 1,
                "nonce": "A" * 16,
                "ciphertext": "A" * 22,
                "aad_digest": "sha256:" + "c" * 64,
            },
            "proof": {
                "kind": "detached_jws",
                "verification_method": "did:webvh:z6mkfixture:alice.example#" + device,
                "envelope_digest": "sha256:" + "d" * 64,
                "created_at": "2026-08-31T00:00:00.000Z",
                "jws": "eyJhbGciOiJFZDI1NTE5In0.." + "A" * 86,
            },
        }

    def test_ciphertext_limit_matches_46_kib_plaintext_plus_tag(self):
        maximum = ((46 * 1024 + 16) * 8 + 5) // 6
        self.assertEqual(maximum, 62827)
        for size in (22, maximum - 1, maximum):
            envelope = self.envelope()
            envelope["encrypted_payload"]["ciphertext"] = "A" * size
            self.validator.validate(envelope)
        for size in (21, maximum + 1, 65558):
            envelope = self.envelope()
            envelope["encrypted_payload"]["ciphertext"] = "A" * size
            self.assertFalse(self.validator.is_valid(envelope))

    def test_proof_schema_is_required_and_closed(self):
        envelope = self.envelope()
        self.validator.validate(envelope)
        for member in envelope["proof"]:
            mutated = copy.deepcopy(envelope)
            del mutated["proof"][member]
            self.assertFalse(self.validator.is_valid(mutated))
        for value in (None, {}, {**envelope["proof"], "device_evidence": {}}):
            self.assertFalse(self.validator.is_valid({**envelope, "proof": value}))

    def test_closed_ordinary_and_agent_sender_branches(self):
        envelope = self.envelope()
        for member in ("device_projection_attestation", "authorization_chain", "sender_agent_id"):
            self.assertFalse(self.validator.is_valid({**envelope, member: {}}))
        agent = copy.deepcopy(envelope)
        del agent["sender_device_id"]
        agent["proof"]["verification_method"] = "did:webvh:z6mkfixture:agent.example#runtime-key"
        self.validator.validate(agent)
        for invalid in (None, "", "agent"):
            mutated = copy.deepcopy(agent)
            mutated["sender_device_id"] = invalid
            self.assertFalse(self.validator.is_valid(mutated))

    def test_schema_acceptance_does_not_assert_signature_authenticity(self):
        envelope = self.envelope()
        self.validator.validate(envelope)
        envelope["proof"]["jws"] = "eyJhbGciOiJFZDI1NTE5In0.." + "B" * 86
        self.validator.validate(envelope)


if __name__ == "__main__":
    unittest.main()
