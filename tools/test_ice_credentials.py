"""Mutation checks for ICE privacy, closed DTOs and allocation migration."""

import copy
import base64
import hashlib
import hmac
import json
import unittest
from unittest.mock import patch

from tools.artifact_lint import ice_credentials as gate


class IceCredentialTest(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(gate.FIXTURE.read_text(encoding="utf-8"))
        self.schema = json.loads(gate.SCHEMA.read_text(encoding="utf-8"))

    def run_gate(self, fixture=None, schema=None, prose=None):
        original = gate.load_json

        def load(lint, path):
            if path == gate.FIXTURE:
                return fixture if fixture is not None else self.fixture
            if path == gate.SCHEMA:
                return schema if schema is not None else self.schema
            return original(lint, path)

        lint = gate.Lint()
        with patch.object(gate, "load_json", side_effect=load):
            if prose is None:
                gate.check_ice_credentials(lint)
            else:
                with patch.object(gate, "read_text", return_value=prose):
                    gate.check_ice_credentials(lint)
        return lint.errors

    def test_committed_material(self):
        self.assertEqual(self.run_gate(), [])

    def test_same_bucket_refresh_is_independent(self):
        first, refresh = self.fixture["issuances"][:2]
        self.assertEqual(first["request_body"], refresh["request_body"])
        self.assertEqual(first["issued_at_unix"], refresh["issued_at_unix"])
        self.assertNotEqual(first["expected_username"], refresh["expected_username"])

    def test_bucket_is_canonical_utc_timestamp_in_hmac_input(self):
        first = self.fixture["issuances"][0]
        context = {key: first["request_body"][key] for key in ("realm_id", "call_id", "actor_id", "device_id")}
        context.update(media_service_id=first["media_service_id"], ice_bucket="2026-10-18T17:00:00.000Z", nonce=first["test_nonce_hex"])
        encoded = json.dumps(context, sort_keys=True, separators=(",", ":")).encode()
        raw = hmac.new(bytes.fromhex(self.fixture["test_pseudonym_secret_hex"]), encoded, hashlib.sha256).digest()[:16]
        expected = "ak_pseudonym_call_" + base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
        self.assertEqual(first["expected_username"].split(":", 1)[1], expected)

    def test_issuance_mutations(self):
        for mutation in ("nonce_reuse", "short_nonce", "old_username", "wrong_hmac", "omit_phase", "station_change", "issuer_change"):
            with self.subTest(mutation=mutation):
                data = copy.deepcopy(self.fixture)
                row = data["issuances"][1]
                if mutation == "nonce_reuse":
                    row["test_nonce_hex"] = data["issuances"][0]["test_nonce_hex"]
                elif mutation == "short_nonce":
                    row["test_nonce_hex"] = "01"
                elif mutation == "old_username":
                    row["expected_username"] = data["issuances"][0]["expected_username"]
                elif mutation == "wrong_hmac":
                    row["expected_credential"] = "wrong"
                elif mutation == "omit_phase":
                    data["issuances"].pop()
                elif mutation == "station_change":
                    row["request_body"]["actor_id"]["account_id"]["station_id"] = "ak:did_core:web:other.example"
                else:
                    row["media_service_id"] = "ak:did_core:web:other-media.example"
                self.assertTrue(self.run_gate(fixture=data))

    def test_closed_body_cannot_grow(self):
        for mutation in ("extra", "open"):
            schema = copy.deepcopy(self.schema)
            body = schema["$defs"]["media_ice_configuration_request_body"]
            if mutation == "extra":
                body["properties"]["pseudonym"] = {"type": "string"}
            else:
                body["additionalProperties"] = True
            self.assertTrue(self.run_gate(schema=schema))

    def test_every_identity_coordinate_binds_with_nonce_and_time_held_fixed(self):
        first = self.fixture["issuances"][0]
        secret = self.fixture["test_pseudonym_secret_hex"]
        bucket = first["issued_at_unix"] // 300 * 300
        nonce = first["test_nonce_hex"]
        baseline = gate.derive(first["request_body"], first["media_service_id"], bucket, nonce, secret)
        for field in ("realm", "call", "principal", "station", "device", "issuer", "bucket"):
            with self.subTest(field=field):
                req = copy.deepcopy(first["request_body"])
                issuer, current_bucket = first["media_service_id"], bucket
                if field in ("realm", "call", "device"):
                    req[field + "_id"] += "changed"
                elif field in ("principal", "station"):
                    req["actor_id"]["account_id"][field + "_id"] += "changed"
                elif field == "issuer":
                    issuer += "changed"
                else:
                    current_bucket += 300
                self.assertNotEqual(gate.derive(req, issuer, current_bucket, nonce, secret), baseline)

    def test_lifecycle_cannot_claim_username_takeover_or_permission_delete(self):
        for wrong in ("refresh_old_with_new_username", "create_permission_to_delete", "reuse_pseudonym_to_restore_leg"):
            data = copy.deepcopy(self.fixture)
            data["transitions"][0]["actions"][-1] = wrong
            self.assertTrue(self.run_gate(fixture=data))

    def test_prose_cannot_restore_old_requirement(self):
        prose = gate.PROSE.read_text(encoding="utf-8")
        self.assertTrue(self.run_gate(prose=prose + "\nRefresh 请求 MUST 与原 ICE config 请求一致地携带 pseudonym"))


if __name__ == "__main__":
    unittest.main()
