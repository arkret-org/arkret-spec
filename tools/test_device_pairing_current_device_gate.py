"""Mutation tests for the device-pairing current-device gate closure."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import device_pairing_current_gate as gate
from tools.artifact_lint.core import Lint


def load(relative: str) -> dict:
    return json.loads((ROOT / "spec" / "v1" / relative).read_text(encoding="utf-8"))


class DevicePairingCurrentDeviceGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = load("artifacts/schemas/device-revocation-state.schema.json")
        self.contract = load("artifacts/registry/contract-registry.json")
        self.vectors = load("artifacts/registry/vector-registry.json")
        self.fixture = load("artifacts/fixtures/protocol-edge-cases-fixture.json")
        self.device_prose = (
            ROOT / "spec/v1/zh/crypto-media/device-lifecycle.md"
        ).read_text(encoding="utf-8")
        self.binding_prose = (
            ROOT / "spec/v1/zh/sync/service-http-binding.md"
        ).read_text(encoding="utf-8")

    def run_gate(
        self,
        *,
        schema: dict | None = None,
        contract: dict | None = None,
        vectors: dict | None = None,
        fixture: dict | None = None,
        device_prose: str | None = None,
        binding_prose: str | None = None,
    ) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = root / "artifacts"
            paths = {
                "schema": artifacts / "schemas/device-revocation-state.schema.json",
                "contract": artifacts / "registry/contract-registry.json",
                "vectors": artifacts / "registry/vector-registry.json",
                "fixture": artifacts / "fixtures/protocol-edge-cases-fixture.json",
                "device_prose": root / "zh/crypto-media/device-lifecycle.md",
                "binding_prose": root / "zh/sync/service-http-binding.md",
            }
            for path in paths.values():
                path.parent.mkdir(parents=True, exist_ok=True)
            for key, value in {
                "schema": schema or self.schema,
                "contract": contract or self.contract,
                "vectors": vectors or self.vectors,
                "fixture": fixture or self.fixture,
            }.items():
                paths[key].write_text(
                    json.dumps(value, ensure_ascii=False), encoding="utf-8", newline="\n"
                )
            paths["device_prose"].write_text(
                device_prose or self.device_prose, encoding="utf-8", newline="\n"
            )
            paths["binding_prose"].write_text(
                binding_prose or self.binding_prose, encoding="utf-8", newline="\n"
            )
            lint = Lint()
            with (
                mock.patch.object(gate, "ARTIFACTS", artifacts),
                mock.patch.object(gate, "SPEC_ROOT", root),
                mock.patch.object(gate, "SCHEMA", paths["schema"]),
                mock.patch.object(gate, "CONTRACT", paths["contract"]),
                mock.patch.object(gate, "VECTOR_REGISTRY", paths["vectors"]),
                mock.patch.object(gate, "FIXTURE", paths["fixture"]),
                mock.patch.object(gate, "DEVICE_PROSE", paths["device_prose"]),
                mock.patch.object(gate, "BINDING_PROSE", paths["binding_prose"]),
            ):
                gate.check_device_pairing_current_device_gate(lint)
            return lint.errors

    def assert_red(self, errors: list[str], marker: str) -> None:
        self.assertTrue(any(marker in error for error in errors), errors)

    def test_complete_contract_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_pending_denied_action_set_is_closed(self) -> None:
        schema = copy.deepcopy(self.schema)
        schema["$defs"]["denied_actions"]["prefixItems"].pop(1)
        self.assert_red(self.run_gate(schema=schema), "closed ordered set")

    def test_code_claim_has_a_dedicated_action_class(self) -> None:
        schema = copy.deepcopy(self.schema)
        values = schema["$defs"]["gate_action_class"]["enum"]
        values[values.index(gate.ACTION_CLASS)] = "event_write"
        self.assert_red(self.run_gate(schema=schema), "dedicated")

    def test_code_claim_cannot_omit_expected_selectors(self) -> None:
        schema = copy.deepcopy(self.schema)
        schema["$defs"]["device_revocation_gate_check_request_body"]["allOf"][0][
            "if"
        ]["properties"]["action_class"]["enum"].append(gate.ACTION_CLASS)
        self.assert_red(self.run_gate(schema=schema), "only the two issue")

    def test_code_claim_cannot_require_the_session_issue_proof(self) -> None:
        schema = copy.deepcopy(self.schema)
        schema["$defs"]["device_revocation_gate_check_request_body"]["allOf"][1][
            "if"
        ]["properties"]["action_class"]["enum"].append(gate.ACTION_CLASS)
        self.assert_red(self.run_gate(schema=schema), "must not require")

    def test_intent_digest_must_hide_plaintext_code(self) -> None:
        schema = copy.deepcopy(self.schema)
        description = schema["$defs"]["device_revocation_gate_check_request_body"][
            "properties"
        ]["intent_digest"]["description"]
        schema["$defs"]["device_revocation_gate_check_request_body"]["properties"][
            "intent_digest"
        ]["description"] = description.replace("plaintext pairing code", "request material")
        self.assert_red(self.run_gate(schema=schema), "without disclosing")

    def test_claim_operation_must_call_the_registered_gate(self) -> None:
        contract = copy.deepcopy(self.contract)
        operation = gate._operation(contract, gate.CLAIM_OPERATION)
        self.assertIsNotNone(operation)
        operation["notes"] = operation["notes"].replace(gate.GATE_OPERATION, "private.lookup")
        self.assert_red(self.run_gate(contract=contract), gate.CLAIM_OPERATION)

    def test_gate_operation_must_forbid_event_write_substitution(self) -> None:
        contract = copy.deepcopy(self.contract)
        operation = gate._operation(contract, gate.GATE_OPERATION)
        self.assertIsNotNone(operation)
        operation["notes"] = operation["notes"].replace("event_write", "resource_write")
        self.assert_red(self.run_gate(contract=contract), gate.GATE_OPERATION)

    def test_both_normative_pages_must_name_the_action(self) -> None:
        source = self.binding_prose.replace(gate.ACTION_CLASS, "device_pairing_claim")
        self.assert_red(self.run_gate(binding_prose=source), gate.ACTION_CLASS)

    def test_fixture_covers_revocation_pending(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        case = gate._vector_case(fixture)
        self.assertIsNotNone(case)
        case["variants"].remove("claim_current_device_gate_revocation_pending")
        self.assert_red(self.run_gate(fixture=fixture), "negative variants")

    def test_fixture_pins_auth_gate_lookup_and_budget_order(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        case = gate._vector_case(fixture)
        self.assertIsNotNone(case)
        order = case["expected"]["current_device_gate_order"]
        order[2], order[3] = order[3], order[2]
        self.assert_red(self.run_gate(fixture=fixture), "closed safe order")

    def test_vector_rejects_session_grant_only_authorization(self) -> None:
        vectors = copy.deepcopy(self.vectors)
        row = next(row for row in vectors["vectors"] if row["vector_id"] == gate.VECTOR_ID)
        row["description"] = row["description"].replace(gate.ACTION_CLASS, "session_grant_only")
        self.assert_red(self.run_gate(vectors=vectors), "current-device gate closure")

    def test_runner_invokes_the_gate(self) -> None:
        source = (ROOT / "tools/artifact_lint/runner.py").read_text(encoding="utf-8")
        self.assertIn("check_device_pairing_current_device_gate(lint)", source)


if __name__ == "__main__":
    unittest.main()
