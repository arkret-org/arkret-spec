"""Single-point mutations for the device-pairing split-admission saga."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import device_pairing_split_admission as gate
from tools.artifact_lint.core import Lint


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class DevicePairingSplitAdmissionGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = {
            path.resolve(): read_json(path)
            for path in (gate.CONTRACT, gate.ERROR_MAPPING, gate.VECTORS, gate.FIXTURE)
        }
        self.texts = {
            path.resolve(): path.read_text(encoding="utf-8")
            for path in (
                gate.OPENAPI,
                gate.DEVICE_PROSE,
                gate.BINDING_PROSE,
                gate.SURFACE_PROSE,
                gate.VECTOR_PROSE,
                gate.RUNNER,
            )
        }

    def run_gate(self, mutate=None, text_mutate=None) -> list[str]:
        documents = copy.deepcopy(self.documents)
        texts = copy.deepcopy(self.texts)
        if mutate:
            mutate(documents)
        if text_mutate:
            text_mutate(texts)
        original_json = gate.load_json
        original_text = gate.read_text

        def load_json(lint, path):  # type: ignore[no-untyped-def]
            return documents.get(Path(path).resolve(), original_json(lint, path))

        def read_text(path):  # type: ignore[no-untyped-def]
            return texts.get(Path(path).resolve(), original_text(path))

        gate.load_json = load_json
        gate.read_text = read_text
        try:
            lint = Lint()
            gate.check_device_pairing_split_admission_saga(lint)
            return lint.errors
        finally:
            gate.load_json = original_json
            gate.read_text = original_text

    def assert_red(self, mutate=None, marker="", text_mutate=None) -> None:
        errors = self.run_gate(mutate, text_mutate)
        self.assertTrue(any(marker in error for error in errors), errors)

    def contract(self, docs: dict) -> dict:
        return docs[gate.CONTRACT.resolve()]

    def operation(self, docs: dict, operation_id: str) -> dict:
        return gate._operation(self.contract(docs), operation_id)

    def relation(self, docs: dict) -> dict:
        return gate._find(
            self.contract(docs)["operation_registry"]["coordination_relations"],
            "coordination_id",
            gate.COORDINATION_ID,
        )

    def test_complete_contract_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_internal_stage_reuses_public_dto(self) -> None:
        def mutate(docs: dict) -> None:
            self.operation(docs, gate.PROXIES[0][1])["request_schema_ref"] = "private.schema.json#/$defs/stage"

        self.assert_red(mutate, "exact public DTO")

    def test_internal_ops_require_service_signature(self) -> None:
        def mutate(docs: dict) -> None:
            self.operation(docs, gate.PROXIES[1][1])["auth_requirements"] = {}

        self.assert_red(mutate, "service signature")

    def test_public_stage_stays_non_retry_safe(self) -> None:
        def mutate(docs: dict) -> None:
            self.operation(docs, gate.PROXIES[0][0])["retry_safe"] = True

        self.assert_red(mutate, "public stage")

    def test_internal_stage_has_station_key_dedup(self) -> None:
        def mutate(docs: dict) -> None:
            self.operation(docs, gate.PROXIES[0][1])["idempotency_mechanism"] = "none"

        self.assert_red(mutate, "durably deduplicate")

    def test_internal_reads_cannot_claim_durable_effect(self) -> None:
        def mutate(docs: dict) -> None:
            self.operation(docs, gate.PROXIES[2][1])["durable_effect"] = {"kind": "none"}

        self.assert_red(mutate, "read-only proxy")

    def test_public_bundle_cannot_absorb_internal_ops(self) -> None:
        def mutate(docs: dict) -> None:
            bundle = gate._bundle(self.contract(docs), "ak.operation_bundle.station.device_pairing_handoff.v1")
            bundle["members"].append({"operation_id": gate.PROXIES[0][1], "binding_kind": "http_json"})

        self.assert_red(mutate, "three-public-operation")

    def test_pair_registers_event_submission_path(self) -> None:
        def mutate(docs: dict) -> None:
            self.operation(docs, gate.PAIR)["durable_effect"].pop("event_submission_path")

        self.assert_red(mutate, "/authorize_event")

    def test_coordination_owner_is_authority(self) -> None:
        def mutate(docs: dict) -> None:
            self.relation(docs)["ledger_owner"] = "station"

        self.assert_red(mutate, "sole pairing ledger")

    def test_proxy_body_mappings_are_exact(self) -> None:
        def mutate(docs: dict) -> None:
            self.relation(docs)["public_proxy_mappings"][1]["response_mapping"] = "translated"

        self.assert_red(mutate, "byte-identical")

    def test_event_leg_is_authority_forward(self) -> None:
        def mutate(docs: dict) -> None:
            self.relation(docs)["event_admission"]["branch"] = "bounded_committed_replication"

        self.assert_red(mutate, "authority_forward")

    def test_receipt_must_bind_frozen_event(self) -> None:
        def mutate(docs: dict) -> None:
            self.relation(docs)["event_admission"]["receipt_verification"].remove("frozen_event_bytes_unchanged")

        self.assert_red(mutate, "committed/duplicate exact replay")

    def test_fence_key_is_closed(self) -> None:
        def mutate(docs: dict) -> None:
            self.relation(docs)["fence"]["key_fields"].pop()

        self.assert_red(mutate, "owner/key")

    def test_fence_state_graph_is_closed(self) -> None:
        def mutate(docs: dict) -> None:
            self.relation(docs)["fence"]["states"].append("in_progress")

        self.assert_red(mutate, "prepared -> station_accepted -> completed")

    def test_terminal_rejection_abort_is_registered(self) -> None:
        def mutate(docs: dict) -> None:
            self.relation(docs)["fence"]["transitions"].pop()

        self.assert_red(mutate, "terminal-rejection abort")

    def test_fenced_record_is_ttl_immune(self) -> None:
        def mutate(docs: dict) -> None:
            self.relation(docs)["fence"]["nonterminal_protections"].remove("ttl_cleanup_forbidden")

        self.assert_red(mutate, "immune to TTL")

    def test_all_five_crash_cuts_are_registered(self) -> None:
        def mutate(docs: dict) -> None:
            self.relation(docs)["crash_recovery"].pop(2)

        self.assert_red(mutate, "five crash cuts")

    def test_error_translation_is_closed(self) -> None:
        def mutate(docs: dict) -> None:
            self.relation(docs)["downstream_error_translation"].pop(0)

        self.assert_red(mutate, "closed downstream error")

    def test_pair_error_map_carries_terminal_rejection(self) -> None:
        def mutate(docs: dict) -> None:
            rows = docs[gate.ERROR_MAPPING.resolve()]["operations"]
            gate._find(rows, "operation_id", gate.PAIR)["operation_specific"].remove("failed_precondition")

        self.assert_red(mutate, "unified terminal rejection")

    def test_vector_points_to_dedicated_fixture(self) -> None:
        def mutate(docs: dict) -> None:
            rows = docs[gate.VECTORS.resolve()]["vectors"]
            gate._find(rows, "vector_id", gate.VECTOR_ID)["applies_to_fixtures"] = []

        self.assert_red(mutate, "dedicated fixture")

    def test_fixture_covers_receipt_mismatch(self) -> None:
        def mutate(docs: dict) -> None:
            fixture = docs[gate.FIXTURE.resolve()]
            fixture["negative_cases"] = [row for row in fixture["negative_cases"] if row["case_id"] != "peer_receipt_event_ref_mismatch"]

        self.assert_red(mutate, "peer_receipt_event_ref_mismatch")

    def test_openapi_exposes_internal_stage(self) -> None:
        def mutate(texts: dict) -> None:
            texts[gate.OPENAPI.resolve()] = texts[gate.OPENAPI.resolve()].replace("/_arkret/gate/account/device-pairing/stages:", "/missing:", 1)

        self.assert_red(marker="OpenAPI", text_mutate=mutate)

    def test_normative_prose_carries_fence_states(self) -> None:
        def mutate(texts: dict) -> None:
            texts[gate.DEVICE_PROSE.resolve()] = texts[gate.DEVICE_PROSE.resolve()].replace("prepared -> station_accepted -> completed", "prepared -> completed", 1)

        self.assert_red(marker="station_accepted", text_mutate=mutate)

    def test_runner_invokes_gate(self) -> None:
        def mutate(texts: dict) -> None:
            texts[gate.RUNNER.resolve()] = texts[gate.RUNNER.resolve()].replace("check_device_pairing_split_admission_saga(lint)", "check_removed(lint)")

        self.assert_red(marker="phase-1 runner", text_mutate=mutate)


if __name__ == "__main__":
    unittest.main()
