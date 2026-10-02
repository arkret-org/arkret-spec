"""Pairing identity context remains closed and retains full account identity."""

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


class AgentPairingBootstrapSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schemas = Path(__file__).resolve().parents[1] / "spec/v1/artifacts/schemas"
        resources = []
        for path in schemas.glob("*.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            resources.append((document["$id"], Resource.from_contents(document)))
        cls.validator = Draft202012Validator(
            {"$ref": "https://arkret.org/v1/schemas/agent-operations.schema.json#/$defs/agent_pairing_bootstrap"},
            registry=Registry().with_resources(resources),
        )

    def test_runtime_identity_is_complete_and_closed(self):
        bootstrap = {
            "arkret_base_url": "https://station.example",
            "service_id": "ak:did_core:web:station.example",
            "agent_id": "ak:did_core:web:agent.example",
            "pairing_request_id": "pair-1",
            "pairing_code": "01234567",
            "pairing_expires_at": "2026-09-08T00:00:00.000Z",
            "runtime_identity": {
                "controller_account_id": {
                    "principal_id": "ak:did_core:web:controller.example",
                    "station_id": "ak:did_core:web:station.example",
                },
                "verification_method": "did:web:agent.example#runtime-pairing",
            },
        }
        self.validator.validate(bootstrap)
        for code in ("00000000", "99999999"):
            valid = copy.deepcopy(bootstrap)
            valid["pairing_code"] = code
            self.validator.validate(valid)
        for code in ("1234567", "123456789", "1234567a", "１２３４５６７８", "abcdefghijklmnopqrstuvwxyz123456"):
            invalid_code = copy.deepcopy(bootstrap)
            invalid_code["pairing_code"] = code
            self.assertFalse(self.validator.is_valid(invalid_code), code)
        legacy = copy.deepcopy(bootstrap)
        del legacy["runtime_identity"]
        self.validator.validate(legacy)
        for field in ("controller_account_id", "verification_method"):
            invalid = copy.deepcopy(bootstrap)
            del invalid["runtime_identity"][field]
            self.assertFalse(self.validator.is_valid(invalid))
        invalid = copy.deepcopy(bootstrap)
        del invalid["runtime_identity"]["controller_account_id"]["station_id"]
        self.assertFalse(self.validator.is_valid(invalid))
        invalid = copy.deepcopy(bootstrap)
        invalid["runtime_identity"]["scope"] = []
        self.assertFalse(self.validator.is_valid(invalid))
        invalid = copy.deepcopy(bootstrap)
        invalid["runtime_identity"]["verification_method"] = "ak:did_core:web:agent.example#runtime-1"
        self.assertFalse(self.validator.is_valid(invalid))


if __name__ == "__main__":
    unittest.main()
