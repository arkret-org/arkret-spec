"""Single-point mutation tests for the peer Event-submit semantic union."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import peer_event_submit as gate
from tools.artifact_lint.core import Lint


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class PeerEventSubmitGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = {
            path.resolve(): read(path)
            for path in (
                gate.SCHEMA,
                gate.CONTRACT,
                gate.ERRORS,
                gate.ERROR_MAPPING,
                gate.PROFILES,
                gate.VECTORS,
                gate.FIXTURE,
            )
        }
        self.texts = {
            path.resolve(): path.read_text(encoding="utf-8")
            for path in (gate.FIXTURE, gate.OPENAPI, *gate.PROSE_MARKERS)
        }

    def run_gate(self, mutate=None, text_mutate=None, closure=False) -> list[str]:
        documents = copy.deepcopy(self.documents)
        texts = copy.deepcopy(self.texts)
        if mutate is not None:
            mutate(documents)
        if text_mutate is not None:
            text_mutate(texts)
        original_json = gate.load_json
        original_text = gate.read_text

        def load_json(lint, path):  # type: ignore[no-untyped-def]
            resolved = Path(path).resolve()
            return documents.get(resolved) if resolved in documents else original_json(lint, path)

        def read_text(path):  # type: ignore[no-untyped-def]
            resolved = Path(path).resolve()
            return texts.get(resolved) if resolved in texts else original_text(path)

        gate.load_json = load_json
        gate.read_text = read_text
        try:
            lint = Lint()
            if closure:
                gate.check_profile_wire_contract_refs(lint)
            else:
                gate.check_peer_event_submit_semantic_union(lint)
            return lint.errors
        finally:
            gate.load_json = original_json
            gate.read_text = original_text

    def assert_red(self, mutate=None, marker="", text_mutate=None, closure=False) -> None:
        errors = self.run_gate(mutate, text_mutate, closure)
        self.assertTrue(any(marker in error for error in errors), errors)

    def defs(self, documents: dict) -> dict:
        return documents[gate.SCHEMA.resolve()]["$defs"]

    def operation(self, documents: dict, operation_id: str) -> dict:
        rows = documents[gate.CONTRACT.resolve()]["operation_registry"]["operations"]
        return gate._find(rows, "operation_id", operation_id)

    def test_complete_contract_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])
        self.assertEqual(self.run_gate(closure=True), [])

    def test_branch_enum_is_closed(self) -> None:
        def mutate(documents: dict) -> None:
            self.defs(documents)["peer_submit_request"]["properties"]["branch"]["enum"].append("legacy_batch")

        self.assert_red(mutate, "exact closed three-value list")

    def test_replication_is_bounded(self) -> None:
        def mutate(documents: dict) -> None:
            self.defs(documents)["peer_submit_request"]["properties"]["submissions"]["maxItems"] = 101

        self.assert_red(mutate, "bounded to 1..100")

    def test_committed_row_requires_source_commit(self) -> None:
        def mutate(documents: dict) -> None:
            self.defs(documents)["committed_event_submission"]["required"].remove("source_commit")

        self.assert_red(mutate, "source_commit")

    def test_replication_requires_witnesses(self) -> None:
        def mutate(documents: dict) -> None:
            self.defs(documents)["replicated_committed_event_submission"]["required"].remove("recipient_witnesses")

        self.assert_red(mutate, "recipient_witnesses")

    def test_replication_cannot_restore_accepted_status(self) -> None:
        def mutate(documents: dict) -> None:
            branches = self.defs(documents)["peer_committed_replication_record"]["oneOf"]
            branches[0]["properties"]["status"]["enum"][0] = "accepted"

        self.assert_red(mutate, "stored|duplicate|rejected")

    def test_founding_order_uses_fourth_strand_event(self) -> None:
        def mutate(documents: dict) -> None:
            items = self.defs(documents)["direct_conversation_founding_unit_submission"]["properties"]["events"]["prefixItems"]
            items[2], items[3] = items[3], items[2]

        self.assert_red(mutate, "realm/create, founder/join, peer/join, strand/create")

    def test_self_founding_rejects_evidence_echo(self) -> None:
        def mutate(documents: dict) -> None:
            self.defs(documents)["direct_conversation_founding_unit_submission"]["properties"]["founding_authority_evidence"] = {}

        self.assert_red(mutate, "reject founding_authority_evidence echo")

    def test_peer_founding_requires_receipt_and_evidence(self) -> None:
        def mutate(documents: dict) -> None:
            self.defs(documents)["direct_conversation_founding_federation_submission"]["required"].remove("source_acceptance_receipt")

        self.assert_red(mutate, "receipt and authority evidence")

    def test_atomic_unit_registry_is_closed(self) -> None:
        def mutate(documents: dict) -> None:
            self.defs(documents)["peer_registered_atomic_unit"]["oneOf"].append({"$ref": "#/$defs/submit_request"})

        self.assert_red(mutate, "exactly founding and compensation")

    def test_compensation_requires_terminal_certificate(self) -> None:
        def mutate(documents: dict) -> None:
            self.defs(documents)["membership_compensation_evidence"]["required"].remove("terminal_certificate")

        self.assert_red(mutate, "closed three-part carrier")

    def test_peer_registry_uses_endpoint_schema(self) -> None:
        def mutate(documents: dict) -> None:
            self.operation(documents, "ak.peer.events.command.submit.v1")["request_schema_ref"] = "schemas/authority-commit-operations.schema.json#/$defs/submit_request"

        self.assert_red(mutate, "peer submit must use endpoint-specific")

    def test_replication_durable_effect_is_none(self) -> None:
        def mutate(documents: dict) -> None:
            effect = self.operation(documents, "ak.peer.events.command.submit.v1")["durable_effect"]
            effect["effect_branches"][1]["effect"] = {"kind": "event_log", "event_kinds": ["ak.message.create"]}

        self.assert_red(mutate, "committed_replication durable effect must be none")

    def test_atomic_rationale_forbids_second_fanout(self) -> None:
        def mutate(documents: dict) -> None:
            effect = self.operation(documents, "ak.peer.events.command.submit.v1")["durable_effect"]
            effect["effect_branches"][2]["effect"]["rationale"] = "local_store"

        self.assert_red(mutate, "rationale omits")

    def test_reason_code_must_be_active(self) -> None:
        def mutate(documents: dict) -> None:
            row = gate._find(documents[gate.ERRORS.resolve()]["codes"], "code", "membership_compensation_conflict")
            row["status"] = "reserved"

        self.assert_red(mutate, "membership_compensation_conflict must be active")

    def test_reason_without_machine_producer_stays_reserved(self) -> None:
        def mutate(documents: dict) -> None:
            rows = documents[gate.ERRORS.resolve()]["reason_codes"]
            row = gate._find(rows, "code", "direct_conversation_binding_invalid")
            row["status"] = "active"
            row.pop("activation_condition", None)

        self.assert_red(mutate, "must remain reserved")

    def test_error_map_covers_source_ref_failure(self) -> None:
        def mutate(documents: dict) -> None:
            row = gate._find(documents[gate.ERROR_MAPPING.resolve()]["operations"], "operation_id", "ak.peer.events.command.submit.v1")
            row["operation_specific"].remove("source_refs_unverifiable")

        self.assert_red(mutate, "error map omits")

    def test_profile_uses_current_compensation_carriers(self) -> None:
        def mutate(documents: dict) -> None:
            profile = documents[gate.PROFILES.resolve()]["profile_requirements"]["ak.profile.membership_join_compensation.v1"]
            profile["wire_contract_refs"] = ["schemas/service-operation-dtos.schema.json#/$defs/EventFederationSubmission"]

        self.assert_red(mutate, "both current aggregate carriers")

    def test_profile_wire_ref_fragment_must_resolve(self) -> None:
        def mutate(documents: dict) -> None:
            profile = documents[gate.PROFILES.resolve()]["profile_requirements"]["ak.profile.membership_join_compensation.v1"]
            profile["wire_contract_refs"][0] = "schemas/authority-commit-operations.schema.json#/$defs/missing"

        self.assert_red(mutate, "fragment does not resolve", closure=True)

    def test_profile_wire_ref_cannot_target_schema_root(self) -> None:
        def mutate(documents: dict) -> None:
            profile = documents[gate.PROFILES.resolve()]["profile_requirements"]["ak.profile.membership_join_compensation.v1"]
            profile["wire_contract_refs"][0] = "schemas/authority-commit-operations.schema.json#"

        self.assert_red(mutate, "named $defs fragment", closure=True)

    def test_vector_keeps_fourth_event_derivation(self) -> None:
        def mutate(documents: dict) -> None:
            row = gate._find(documents[gate.VECTORS.resolve()]["vectors"], "vector_id", "ak.vector.direct_conversation.founding_unit.v1")
            row["description"] = row["description"].replace("first and fourth", "first and third")

        self.assert_red(mutate, "fourth Event")

    def test_fixture_covers_wrong_authority_generation(self) -> None:
        def text_mutate(texts: dict) -> None:
            path = gate.FIXTURE.resolve()
            texts[path] = texts[path].replace("wrong_authority_generation", "wrong_generation_removed")

        self.assert_red(marker="wrong_authority_generation", text_mutate=text_mutate)

    def test_deleted_federation_wrapper_is_rejected(self) -> None:
        def text_mutate(texts: dict) -> None:
            path = gate.FIXTURE.resolve()
            texts[path] += "\nEventFederationSubmission\n"

        self.assert_red(marker="must not be restored", text_mutate=text_mutate)

    def test_openapi_must_bind_peer_endpoint_union(self) -> None:
        def text_mutate(texts: dict) -> None:
            path = gate.OPENAPI.resolve()
            texts[path] = texts[path].replace("#/$defs/peer_submit_request", "#/$defs/submit_request")

        self.assert_red(marker="OpenAPI binding omits", text_mutate=text_mutate)

    def test_runner_invokes_both_gates(self) -> None:
        source = gate.RUNNER.read_text(encoding="utf-8")
        self.assertIn("check_peer_event_submit_semantic_union(lint)", source)
        self.assertIn("check_profile_wire_contract_refs(lint)", source)


if __name__ == "__main__":
    unittest.main()
