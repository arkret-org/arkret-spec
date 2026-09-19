"""Single-point mutations for historical signer authority-commit coordinates."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import signer_key_historical_coordinate as gate
from tools.artifact_lint.core import Lint


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class SignerKeyHistoricalCoordinateGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = {
            path.resolve(): load(path)
            for path in (
                gate.SCHEMA,
                gate.AUTHORITY_SCHEMA,
                gate.ACCOUNT_SYNC_SCHEMA,
                gate.CONTRACT,
                gate.ERROR_MAPPING,
                gate.VECTORS,
                gate.FIXTURE,
            )
        }
        self.texts = {
            path.resolve(): path.read_text(encoding="utf-8")
            for path in (gate.SERVER_PROSE, gate.SYNC_PROSE, gate.VECTOR_PROSE, gate.RUNNER)
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
            gate.check_signer_key_historical_coordinate(lint)
            return lint.errors
        finally:
            gate.load_json = original_json
            gate.read_text = original_text

    def assert_red(self, mutate=None, marker="", text_mutate=None) -> None:
        errors = self.run_gate(mutate, text_mutate)
        self.assertTrue(any(marker in error for error in errors), errors)

    def defs(self, docs: dict) -> dict:
        return docs[gate.SCHEMA.resolve()]["$defs"]

    def test_complete_contract_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_device_history_requires_committed_ref(self) -> None:
        def mutate(docs: dict) -> None:
            required = self.defs(docs)["historical_account_device_selector"]["required"]
            required[required.index("committed_event_ref")] = "event_id"

        self.assert_red(mutate, "reject bare event_id")

    def test_agent_history_uses_canonical_ref(self) -> None:
        def mutate(docs: dict) -> None:
            self.defs(docs)["historical_agent_selector"]["properties"]["committed_event_ref"]["$ref"] = "./common-ids.schema.json#/$defs/event_id"

        self.assert_red(mutate, "canonical committed_event_ref")

    def test_current_selector_rejects_coordinate(self) -> None:
        def mutate(docs: dict) -> None:
            self.defs(docs)["current_agent_selector"]["properties"]["committed_event_ref"] = {"$ref": gate.COMMITTED_REF}

        self.assert_red(mutate, "must not accept")

    def test_key_authorization_is_committed_ref(self) -> None:
        def mutate(docs: dict) -> None:
            self.defs(docs)["query_signing_key"]["properties"]["authorization_ref"]["$ref"] = "./common-ids.schema.json#/$defs/event_id"

        self.assert_red(mutate, "authorization_ref")

    def test_key_requires_revision(self) -> None:
        def mutate(docs: dict) -> None:
            self.defs(docs)["query_signing_key"]["required"].remove("revision")

        self.assert_red(mutate, "revision and generation")

    def test_key_requires_governance_generation(self) -> None:
        def mutate(docs: dict) -> None:
            self.defs(docs)["query_signing_key"]["required"].remove("governance_generation")

        self.assert_red(mutate, "revision and generation")

    def test_revision_is_closed(self) -> None:
        def mutate(docs: dict) -> None:
            self.defs(docs)["query_signing_key"]["properties"]["revision"]["additionalProperties"] = True

        self.assert_red(mutate, "closed current commit coordinate")

    def test_historical_device_cannot_return_key_only(self) -> None:
        def mutate(docs: dict) -> None:
            self.defs(docs)["historical_account_device_outcome"]["properties"]["key"]["$ref"] = "#/$defs/public_key_only"

        self.assert_red(mutate, "complete query_signing_key")

    def test_no_legacy_partial_key_definition(self) -> None:
        def mutate(docs: dict) -> None:
            self.defs(docs)["historical_device_signing_key"] = {"type": "object"}

        self.assert_red(mutate, "partial-success")

    def test_committed_ref_keeps_all_four_coordinates(self) -> None:
        def mutate(docs: dict) -> None:
            docs[gate.AUTHORITY_SCHEMA.resolve()]["$defs"]["committed_event_ref"]["required"].remove("stream_position")

        self.assert_red(mutate, "four-coordinate")

    def test_scan_reuses_stream_row(self) -> None:
        def mutate(docs: dict) -> None:
            docs[gate.AUTHORITY_SCHEMA.resolve()]["$defs"]["stream_scan_outcome"]["properties"]["commits"]["items"]["$ref"] = "#/$defs/committed_event_ref"

        self.assert_red(mutate, "per-stream scan")

    def test_account_subscribe_reuses_stream_row(self) -> None:
        def mutate(docs: dict) -> None:
            docs[gate.ACCOUNT_SYNC_SCHEMA.resolve()]["$defs"]["realm_sync_entry"]["properties"]["commits"]["items"]["$ref"] = "./event-envelope.schema.json"

        self.assert_red(mutate, "account subscribe")

    def test_operation_forbids_current_fallback(self) -> None:
        def mutate(docs: dict) -> None:
            rows = docs[gate.CONTRACT.resolve()]["operation_registry"]["operations"]
            row = gate._find(rows, "operation_id", gate.OPERATION_ID)
            row["notes"] = row["notes"].replace("without current-query fallback", "with best-effort fallback")

        self.assert_red(mutate, "current-query fallback")

    def test_error_mapping_names_missing_coordinate(self) -> None:
        def mutate(docs: dict) -> None:
            rows = docs[gate.ERROR_MAPPING.resolve()]["operations"]
            row = gate._find(rows, "operation_id", gate.OPERATION_ID)
            row["description"] = row["description"].replace("committed_event_ref", "historical target")

        self.assert_red(mutate, "committed_event_ref")

    def test_vector_points_to_fixture(self) -> None:
        def mutate(docs: dict) -> None:
            rows = docs[gate.VECTORS.resolve()]["vectors"]
            gate._find(rows, "vector_id", gate.VECTOR_ID)["applies_to_fixtures"] = []

        self.assert_red(mutate, "dedicated fixture")

    def test_fixture_keeps_exact_two_carriers(self) -> None:
        def mutate(docs: dict) -> None:
            docs[gate.FIXTURE.resolve()]["carrier_sources"].append("signer_private_history")

        self.assert_red(mutate, "exactly the two existing")

    def test_target_and_authorization_may_differ(self) -> None:
        def mutate(docs: dict) -> None:
            fixture = docs[gate.FIXTURE.resolve()]
            fixture["positive_case"]["resolved_key"]["authorization_ref"] = copy.deepcopy(
                fixture["positive_case"]["selector"]["committed_event_ref"]
            )

        self.assert_red(mutate, "independent unequal")

    def test_fixture_rejects_projection_fabrication(self) -> None:
        def mutate(docs: dict) -> None:
            docs[gate.FIXTURE.resolve()]["negative_cases"].remove("current_projection_nested_event_used_as_coordinate")

        self.assert_red(mutate, "negative cases")

    def test_prose_keeps_dual_reference_semantics(self) -> None:
        def mutate(texts: dict) -> None:
            texts[gate.SERVER_PROSE.resolve()] = texts[gate.SERVER_PROSE.resolve()].replace("MAY 相同", "MUST 相同", 1)

        self.assert_red(marker="MAY 相同", text_mutate=mutate)

    def test_sync_prose_forbids_third_carrier(self) -> None:
        def mutate(texts: dict) -> None:
            texts[gate.SYNC_PROSE.resolve()] = texts[gate.SYNC_PROSE.resolve()].replace("不得新增", "可以新增", 1)

        self.assert_red(marker="不得新增", text_mutate=mutate)

    def test_runner_invokes_gate(self) -> None:
        def mutate(texts: dict) -> None:
            texts[gate.RUNNER.resolve()] = texts[gate.RUNNER.resolve()].replace("check_signer_key_historical_coordinate(lint)", "check_removed(lint)")

        self.assert_red(marker="phase-2 runner", text_mutate=mutate)


if __name__ == "__main__":
    unittest.main()
