"""Mutation tests for the candidate-device possession transcript contract.

The three ``device_authorize_*possession_transcript`` ``$defs`` used to be a
three-line stub that ``allOf``-ed the closed ``device_authorize_payload``. That
made them structurally unsatisfiable: the payload *requires* ``device_signature``
-- the very signature the transcript produces -- and forbids ``account_id``,
which ``proof-context-registry.json`` says is injected from the Event envelope
actor_id. No instance could ever validate, so nothing did, and
``pcr-genesis-fixture.json`` shipped an eleven-member possession object with
``principal_id``, without ``account_id`` and without
``authorized_generation_ref`` while its stated digest stayed self-consistent.

The registry rule that was supposed to catch this is one-directional: it only
asks whether each ``binding_fields`` entry has a schema source. It cannot see a
schema that *forbids* a binding field, and it never asked whether a schema member
is a registered binding field. Both directions are asserted here.
"""

from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import core

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
EVENT_PAYLOAD_SCHEMA = ARTIFACTS / "schemas" / "event-payload.schema.json"
FIXTURE = ARTIFACTS / "fixtures" / "pcr-genesis-fixture.json"
PROOF_CONTEXT_REGISTRY = ARTIFACTS / "registry" / "proof-context-registry.json"

POSSESSION_ROWS = {
    "ak.device_authorize_possession_proof.v1": (
        "device_authorize_possession_transcript"
    ),
    "ak.device_authorize_recovery_possession_proof.v1": (
        "device_authorize_recovery_possession_transcript"
    ),
    "ak.device_authorize_applet_managed_possession_proof.v1": (
        "device_authorize_applet_managed_possession_transcript"
    ),
}


def _b64u_decode(text: str) -> bytes:
    import base64

    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class DevicePossessionTranscriptContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = core.parse_json_file(FIXTURE)
        cls.registry = core.parse_json_file(PROOF_CONTEXT_REGISTRY)
        cls.schema = core.parse_json_file(EVENT_PAYLOAD_SCHEMA)
        cls.transcript = cls.fixture["device_possession"]["canonical_object"]
        cls.payload = cls.fixture["founding_authorize"]["payload"]
        cls.validator = core.schema_validator(
            EVENT_PAYLOAD_SCHEMA, "#/$defs/device_authorize_possession_transcript"
        )
        cls.payload_validator = core.schema_validator(
            EVENT_PAYLOAD_SCHEMA, "#/$defs/device_authorize_payload"
        )

    def assertValid(self, instance) -> None:
        self.assertEqual(
            [error.message for error in self.validator.iter_errors(instance)], []
        )

    def assertRejected(self, instance) -> None:
        self.assertNotEqual(
            [error.message for error in self.validator.iter_errors(instance)],
            [],
            "instance was accepted but must be rejected",
        )

    def mutated(self, **changes):
        instance = copy.deepcopy(self.transcript)
        for key, value in changes.items():
            if value is _REMOVE:
                del instance[key]
            else:
                instance[key] = value
        return instance

    # --- the shipped instance ------------------------------------------------

    def test_fixture_possession_object_validates(self) -> None:
        self.assertValid(self.transcript)

    def test_fixture_payload_validates(self) -> None:
        self.assertEqual(
            [error.message for error in self.payload_validator.iter_errors(self.payload)],
            [],
        )

    # --- the signature is an output, never a member --------------------------

    def test_device_signature_member_is_rejected(self) -> None:
        self.assertRejected(
            self.mutated(device_signature=self.payload["device_signature"])
        )

    def test_event_identity_members_are_rejected(self) -> None:
        for member in ("event_id", "event_digest", "envelope_digest"):
            with self.subTest(member=member):
                self.assertRejected(self.mutated(**{member: "sha256:" + "0" * 64}))

    # --- the injected AccountId ----------------------------------------------

    def test_missing_account_id_is_rejected(self) -> None:
        self.assertRejected(self.mutated(account_id=_REMOVE))

    def test_principal_id_in_place_of_account_id_is_rejected(self) -> None:
        instance = self.mutated(account_id=_REMOVE)
        instance["principal_id"] = self.transcript["account_id"]["principal_id"]
        self.assertRejected(instance)

    def test_bare_principal_core_as_account_id_is_rejected(self) -> None:
        self.assertRejected(
            self.mutated(account_id=self.transcript["account_id"]["principal_id"])
        )

    # --- the generation the registry used to omit ----------------------------

    def test_missing_authorized_generation_ref_is_rejected(self) -> None:
        self.assertRejected(self.mutated(authorized_generation_ref=_REMOVE))

    def test_registration_generation_other_than_one_is_rejected(self) -> None:
        self.assertRejected(self.mutated(authorized_generation_ref=2))

    # --- required-and-nullable is what makes normalization executable --------

    def test_omitting_a_normalized_null_member_is_rejected(self) -> None:
        for member in ("expires_at", "scopes", "recovery_session_id"):
            with self.subTest(member=member):
                self.assertIsNone(self.transcript[member])
                self.assertRejected(self.mutated(**{member: _REMOVE}))

    def test_non_null_registration_branch_members_are_rejected(self) -> None:
        self.assertRejected(self.mutated(scopes=["ak.self.account.read.describe.v1"]))
        self.assertRejected(
            self.mutated(
                recovery_session_id=(
                    "ak:recovery_session:019a0000-0000-7000-8000-000000000002"
                )
            )
        )

    # --- self-closure and branch separation ----------------------------------

    def test_unregistered_member_is_rejected(self) -> None:
        self.assertRejected(self.mutated(pairing_challenge_transcript_digest="sha256:" + "0" * 64))
        self.assertRejected(self.mutated(unregistered_member="x"))

    def test_cross_branch_reuse_is_rejected(self) -> None:
        for kind in ("accepted_device", "pcr_recovery", "applet_managed_delegation"):
            with self.subTest(kind=kind):
                self.assertRejected(self.mutated(authorization_binding_kind=kind))

    # --- the real signature --------------------------------------------------

    def _signing_input(self, transcript) -> bytes:
        domain = self.schema["$defs"]["device_authorize_possession_transcript"][
            "x-arkret-signature-domain"
        ]
        return (domain + "\n").encode("utf-8") + core.canonical_json(transcript).encode(
            "utf-8"
        )

    def _device_public_key(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        multibase = self.transcript["device_public_key_did"].removeprefix("did:key:")
        alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        value = 0
        for char in multibase[1:]:
            value = value * 58 + alphabet.index(char)
        decoded = value.to_bytes((value.bit_length() + 7) // 8, "big")
        self.assertEqual(decoded[:2], b"\xed\x01", "not an ed25519-pub multikey")
        self.assertEqual(len(decoded), 34, "ed25519 multikey is 2 + 32 bytes")
        return Ed25519PublicKey.from_public_bytes(decoded[2:])

    def test_possession_signature_verifies(self) -> None:
        self._device_public_key().verify(
            _b64u_decode(self.payload["device_signature"]),
            self._signing_input(self.transcript),
        )

    def test_flipped_signature_bit_fails_verification(self) -> None:
        from cryptography.exceptions import InvalidSignature

        signature = bytearray(_b64u_decode(self.payload["device_signature"]))
        signature[0] ^= 0x01
        with self.assertRaises(InvalidSignature):
            self._device_public_key().verify(
                bytes(signature), self._signing_input(self.transcript)
            )

    def test_flipped_transcript_bit_fails_verification(self) -> None:
        from cryptography.exceptions import InvalidSignature

        tampered = self.mutated(authorized_generation_ref=1)
        tampered["not_before"] = "2026-08-09T00:00:00.001Z"
        with self.assertRaises(InvalidSignature):
            self._device_public_key().verify(
                _b64u_decode(self.payload["device_signature"]),
                self._signing_input(tampered),
            )

    # --- stated bytes and stated digests ------------------------------------

    def test_stated_canonical_bytes_round_trip(self) -> None:
        import json

        possession = self.fixture["device_possession"]
        self.assertEqual(json.loads(possession["canonical_json"]), self.transcript)
        self.assertEqual(
            core.canonical_json(self.transcript), possession["canonical_json"]
        )
        authorize = self.fixture["founding_authorize"]
        self.assertEqual(json.loads(authorize["canonical_payload_json"]), self.payload)
        self.assertEqual(
            core.canonical_json(self.payload), authorize["canonical_payload_json"]
        )

    def test_descriptor_commits_to_the_recomputed_payload_digest(self) -> None:
        recomputed = "sha256:" + hashlib.sha256(
            core.canonical_json(self.payload).encode("utf-8")
        ).hexdigest()
        self.assertEqual(self.fixture["founding_authorize"]["payload_digest"], recomputed)
        descriptor = self.fixture["founding_device_descriptor"]
        self.assertEqual(descriptor["founding_authorize_payload_digest"], recomputed)
        self.assertEqual(
            self.fixture["identity_creation_control_transcript"][
                "signature_omitted_object"
            ]["founding_authorize_payload_digest"],
            recomputed,
        )
        for field in ("device_id", "device_public_key_did", "hpke_key", "algorithms"):
            with self.subTest(field=field):
                self.assertEqual(descriptor[field], self.payload[field])

    def test_transcript_mirrors_the_payload_authorization_core(self) -> None:
        for field in (
            "device_id",
            "device_public_key_did",
            "hpke_key",
            "algorithms",
            "device_key_algorithm",
            "authorized_by",
            "authorization_binding_kind",
            "authorized_generation_ref",
            "not_before",
        ):
            with self.subTest(field=field):
                self.assertEqual(self.transcript[field], self.payload[field])

    def test_registration_authorized_by_equals_account_principal(self) -> None:
        self.assertEqual(
            self.transcript["authorized_by"],
            self.transcript["account_id"]["principal_id"],
        )

    def test_algorithms_are_bytewise_sorted_and_unique(self) -> None:
        algorithms = self.transcript["algorithms"]
        self.assertEqual(
            algorithms, sorted(set(algorithms), key=lambda item: item.encode("utf-8"))
        )

    # --- both directions of the registry binding relation --------------------

    def _schema_members(self, def_name: str) -> set[str]:
        defs = self.schema["$defs"]
        node = defs[def_name]
        members = set(node.get("properties") or {})
        for branch in node.get("allOf") or []:
            ref = branch.get("$ref", "")
            if ref.startswith("#/$defs/"):
                members |= set(defs[ref.removeprefix("#/$defs/")].get("properties") or {})
        return members

    def test_registry_binding_fields_are_declared_schema_members(self) -> None:
        for domain, def_name in POSSESSION_ROWS.items():
            row = self._row(domain)
            members = self._schema_members(def_name)
            binding = {field.removesuffix("?") for field in row["binding_fields"]}
            with self.subTest(domain=domain):
                self.assertEqual(binding - members, set())

    def test_every_transcript_member_is_a_registered_binding_field(self) -> None:
        """The direction the registry rule never checked.

        `binding_fields` naming a member the schema forbids was invisible, and so
        was a signed member no row declares: a transcript member nobody registered
        is a commitment no verifier knows it has to reproduce.
        """
        for domain, def_name in POSSESSION_ROWS.items():
            row = self._row(domain)
            binding = {field.removesuffix("?") for field in row["binding_fields"]}
            injected = {
                entry["field"] for entry in row.get("injected_fields") or []
            }
            with self.subTest(domain=domain):
                self.assertEqual(self._schema_members(def_name) - binding - injected, set())

    def test_possession_transcripts_declare_their_signature_domain(self) -> None:
        for domain, def_name in POSSESSION_ROWS.items():
            with self.subTest(domain=domain):
                self.assertEqual(
                    self.schema["$defs"][def_name]["x-arkret-signature-domain"], domain
                )
                self.assertEqual(self._row(domain)["primitive"], "detached_signature")

    def test_no_possession_transcript_binds_a_signature_or_digest_member(self) -> None:
        forbidden = {
            "device_signature",
            "event_id",
            "event_digest",
            "envelope_digest",
            "pairing_challenge_transcript_digest",
        }
        for domain, def_name in POSSESSION_ROWS.items():
            with self.subTest(domain=domain):
                self.assertEqual(self._schema_members(def_name) & forbidden, set())
                self.assertEqual(
                    {field.removesuffix("?") for field in self._row(domain)["binding_fields"]}
                    & forbidden,
                    set(),
                )

    def _row(self, domain: str) -> dict:
        for row in self.registry["domain_separations"]:
            if row.get("domain") == domain:
                return row
        raise AssertionError(f"{domain} is not registered")


class _Remove:
    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<remove>"


_REMOVE = _Remove()


if __name__ == "__main__":
    unittest.main()
