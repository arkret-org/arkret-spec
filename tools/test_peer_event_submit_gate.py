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
                gate.DTO_SCHEMA,
                gate.DIRECT_SCHEMA,
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
            for path in (
                gate.FIXTURE,
                gate.OPENAPI,
                *gate.PROSE_MARKERS,
                gate.SPEC_ROOT / "zh" / "sync" / "service-surface.md",
            )
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

    def schema_registry_row(self, documents: dict, schema_id: str) -> dict:
        rows = documents[gate.CONTRACT.resolve()]["schema_registry"]["schemas"]
        return gate._find(rows, "schema_id", schema_id)

    def error_code(self, documents: dict, code: str) -> dict:
        registry = documents[gate.ERRORS.resolve()]
        return gate._find([*registry["codes"], *registry["reason_codes"]], "code", code)

    def error_mapping(self, documents: dict, operation_id: str) -> dict:
        return gate._find(documents[gate.ERROR_MAPPING.resolve()]["operations"], "operation_id", operation_id)

    def founding_slot_invariant(self, documents: dict) -> tuple[list[str], int]:
        invariants = documents[gate.PROFILES.resolve()]["profile_requirements"]["ak.profile.direct_conversation_realm.v1"]["binding_invariants"]
        index = next(index for index, value in enumerate(invariants) if value.startswith("The founding slot admits"))
        return invariants, index

    def test_complete_contract_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])
        self.assertEqual(self.run_gate(closure=True), [])

    def test_branch_enum_is_closed(self) -> None:
        def mutate(documents: dict) -> None:
            self.defs(documents)["peer_submit_request"]["properties"]["branch"]["enum"].append("legacy_batch")

        self.assert_red(mutate, "exact closed three-value list")

    def test_replication_is_bounded(self) -> None:
        def mutate(documents: dict) -> None:
            self.defs(documents)["peer_submit_request"]["properties"]["replications"]["maxItems"] = 101

        self.assert_red(mutate, "bounded to 1..100")

    def test_committed_row_requires_source_commit(self) -> None:
        def mutate(documents: dict) -> None:
            self.defs(documents)["committed_event_submission"]["required"].remove("source_commit")

        self.assert_red(mutate, "source_commit")

    def test_replication_rejects_wire_witnesses(self) -> None:
        def mutate(documents: dict) -> None:
            row = self.defs(documents)["peer_submit_request"]
            row["properties"]["recipient_witnesses"] = {"type": "array"}

        self.assert_red(mutate, "deleted peer request field")

    def test_old_event_submission_type_alias_is_rejected(self) -> None:
        def mutate(documents: dict) -> None:
            documents[gate.DTO_SCHEMA.resolve()]["$defs"]["EventCommitSubmission"] = {
                "$ref": "#/$defs/EventAdmissionSubmission"
            }

        self.assert_red(mutate, "no old alias")

    def test_replication_item_rejects_optional_hint(self) -> None:
        def mutate(documents: dict) -> None:
            self.defs(documents)["committed_event_submission"]["properties"]["recipient_hint"] = {
                "type": "string"
            }

        self.assert_red(mutate, "no optional echoes or hints")

    def test_replication_outcome_record_rejects_optional_echo(self) -> None:
        def mutate(documents: dict) -> None:
            branch = self.defs(documents)["peer_committed_replication_outcome_record"]["oneOf"][0]
            branch["properties"]["source_echo"] = {"type": "string"}

        self.assert_red(mutate, "exact minimal set")

    def test_replication_rejects_processing_echo(self) -> None:
        def mutate(documents: dict) -> None:
            self.defs(documents)["peer_submit_request"]["properties"]["processing"] = {"const": "per_item"}

        self.assert_red(mutate, "deleted peer request field")

    def test_replication_branch_rejects_atomic_unit_field(self) -> None:
        def mutate(documents: dict) -> None:
            branch = self.defs(documents)["peer_submit_request"]["oneOf"][2]
            branch["not"]["anyOf"] = [
                item for item in branch["not"]["anyOf"] if item["required"] != ["unit"]
            ]

        self.assert_red(mutate, "reject every cross-branch field")

    def test_replication_rejects_committed_event_wrapper(self) -> None:
        def mutate(documents: dict) -> None:
            self.defs(documents)["replicated_committed_event_submission"] = {
                "type": "object",
                "properties": {"committed_event": {"$ref": "#/$defs/committed_event_submission"}},
            }

        self.assert_red(mutate, "deleted peer replication wrapper")

    def test_replication_result_rejects_redundant_index(self) -> None:
        def mutate(documents: dict) -> None:
            branch = self.defs(documents)["peer_committed_replication_outcome_record"]["oneOf"][0]
            branch["properties"]["index"] = {"type": "integer"}

        self.assert_red(mutate, "redundant index or committed_ref")

    def test_replication_result_rejects_redundant_committed_ref(self) -> None:
        def mutate(documents: dict) -> None:
            branch = self.defs(documents)["peer_committed_replication_outcome_record"]["oneOf"][0]
            branch["properties"]["committed_ref"] = {"$ref": "#/$defs/committed_event_ref"}

        self.assert_red(mutate, "redundant index or committed_ref")

    def test_replication_rejects_generic_results_name(self) -> None:
        def mutate(documents: dict) -> None:
            outcome = self.defs(documents)["peer_committed_replication_outcome"]
            outcome["properties"]["results"] = outcome["properties"].pop("replication_outcomes")

        self.assert_red(mutate, "deleted generic results/record names")

    def test_replication_cannot_restore_accepted_status(self) -> None:
        def mutate(documents: dict) -> None:
            branches = self.defs(documents)["peer_committed_replication_outcome_record"]["oneOf"]
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

    def test_peer_founding_requires_authority_evidence(self) -> None:
        def mutate(documents: dict) -> None:
            self.defs(documents)["direct_conversation_founding_federation_submission"]["required"].remove("founding_authority_evidence")

        self.assert_red(mutate, "four source rows and authority evidence")

    def test_peer_founding_rejects_deleted_receipt(self) -> None:
        def mutate(documents: dict) -> None:
            row = self.defs(documents)["direct_conversation_founding_federation_submission"]
            row["required"].append("source_acceptance_receipt")
            row["properties"]["source_acceptance_receipt"] = {"type": "object"}

        self.assert_red(mutate, "with no receipt")

    def test_founding_outcome_rejects_deleted_receipt(self) -> None:
        def mutate(documents: dict) -> None:
            row = self.defs(documents)["direct_conversation_founding_acceptance_outcome"]
            row["required"].append("receipt")
            row["properties"]["receipt"] = {"type": "object"}

        self.assert_red(mutate, "return only the four source commits")

    def test_deleted_founding_receipt_schema_cannot_return(self) -> None:
        def mutate(documents: dict) -> None:
            documents[gate.DIRECT_SCHEMA.resolve()]["$defs"]["direct_conversation_founding_acceptance_receipt"] = {
                "type": "object",
                "additionalProperties": False,
            }

        self.assert_red(mutate, "deleted Direct Conversation founding receipt")

    def test_founding_receipt_negative_case_must_remain(self) -> None:
        def text_mutate(texts: dict) -> None:
            path = gate.FIXTURE.resolve()
            texts[path] = texts[path].replace("peer_injects_deleted_receipt", "peer_without_second_finality")

        self.assert_red(marker="peer_injects_deleted_receipt", text_mutate=text_mutate)

    def test_direct_conversation_schema_description_keeps_commit_only_marker(self) -> None:
        def mutate(documents: dict) -> None:
            row = self.schema_registry_row(documents, "ak.schema.direct_conversation_operations.v1")
            row["description"] = row["description"].replace("verified founding-authority evidence", "founding transport data")

        self.assert_red(mutate, "Direct Conversation schema description omits commit-only marker")

    def test_direct_conversation_schema_description_rejects_deleted_receipt_semantic(self) -> None:
        def mutate(documents: dict) -> None:
            row = self.schema_registry_row(documents, "ak.schema.direct_conversation_operations.v1")
            row["description"] += " It carries the source founding acceptance receipt."

        self.assert_red(mutate, "Direct Conversation schema description restores deleted founding-receipt semantic")

    def test_self_submit_notes_keep_commit_only_marker(self) -> None:
        def mutate(documents: dict) -> None:
            row = self.operation(documents, "ak.self.events.command.submit.v1")
            row["notes"] = row["notes"].replace("fourth committed_at is the sole acceptance time", "acceptance time is stored separately")

        self.assert_red(mutate, "self Event-submit notes omits commit-only marker")

    def test_self_submit_notes_reject_deleted_receipt_semantic(self) -> None:
        def mutate(documents: dict) -> None:
            self.operation(documents, "ak.self.events.command.submit.v1")["notes"] += " It returns a source-signed receipt."

        self.assert_red(mutate, "self Event-submit notes restores deleted founding-receipt semantic")

    def test_unrelated_receipt_protocols_are_not_rejected(self) -> None:
        def mutate(documents: dict) -> None:
            self.operation(documents, "ak.self.events.command.submit.v1")["notes"] += (
                " Contact acceptance receipt, PCR genesis receipt and MLS claim receipt remain separate protocols."
            )

        self.assertEqual(self.run_gate(mutate), [])

    def test_materialization_conflict_code_keeps_commit_only_marker(self) -> None:
        def mutate(documents: dict) -> None:
            row = self.error_code(documents, "direct_conversation_pair_materialization_conflict")
            row["description"] = row["description"].replace("four consecutive source RealmCommits", "an opaque acceptance result")

        self.assert_red(mutate, "materialization-conflict code omits commit-only marker")

    def test_materialization_conflict_code_rejects_deleted_receipt_semantic(self) -> None:
        def mutate(documents: dict) -> None:
            self.error_code(documents, "direct_conversation_pair_materialization_conflict")["description"] += " Both carry source acceptance receipts."

        self.assert_red(mutate, "materialization-conflict code restores deleted founding-receipt semantic")

    def test_slot_committed_code_keeps_commit_only_marker(self) -> None:
        def mutate(documents: dict) -> None:
            row = self.error_code(documents, "direct_conversation_slot_already_committed")
            row["description"] = row["description"].replace("without changing the fourth committed_at", "without changing acceptance state")

        self.assert_red(mutate, "slot-committed code omits commit-only marker")

    def test_slot_committed_code_rejects_deleted_receipt_semantic(self) -> None:
        def mutate(documents: dict) -> None:
            self.error_code(documents, "direct_conversation_slot_already_committed")["description"] += " Replay returns the stored byte-identical receipt."

        self.assert_red(mutate, "slot-committed code restores deleted founding-receipt semantic")

    def test_self_submit_error_map_keeps_commit_only_marker(self) -> None:
        def mutate(documents: dict) -> None:
            row = self.error_mapping(documents, "ak.self.events.command.submit.v1")
            row["description"] = row["description"].replace("four consecutive RealmCommits", "one opaque result")

        self.assert_red(mutate, "self Event-submit error-map description omits commit-only marker")

    def test_self_submit_error_map_rejects_deleted_receipt_semantic(self) -> None:
        def mutate(documents: dict) -> None:
            self.error_mapping(documents, "ak.self.events.command.submit.v1")["description"] += " It commits one receipt atomically."

        self.assert_red(mutate, "self Event-submit error-map description restores deleted founding-receipt semantic")

    def test_direct_conversation_profile_keeps_commit_only_marker(self) -> None:
        def mutate(documents: dict) -> None:
            invariants, index = self.founding_slot_invariant(documents)
            invariants[index] = invariants[index].replace("without changing the fourth committed_at", "without changing acceptance state")

        self.assert_red(mutate, "founding-slot invariant omits commit-only marker")

    def test_direct_conversation_profile_rejects_deleted_receipt_semantic(self) -> None:
        def mutate(documents: dict) -> None:
            invariants, index = self.founding_slot_invariant(documents)
            invariants[index] += " Replay MUST return the stored receipt without advancing accepted_at."

        self.assert_red(mutate, "founding-slot invariant restores deleted founding-receipt semantic")

    def test_authority_schema_founding_slot_keeps_commit_only_marker(self) -> None:
        def mutate(documents: dict) -> None:
            row = self.defs(documents)["direct_conversation_founding_unit_submission"]["properties"]["idempotency_key"]
            row["description"] = row["description"].replace("same four byte-identical source RealmCommits", "same opaque result")

        self.assert_red(mutate, "authority schema founding-slot description omits commit-only marker")

    def test_authority_schema_founding_slot_rejects_deleted_receipt_semantic(self) -> None:
        def mutate(documents: dict) -> None:
            row = self.defs(documents)["direct_conversation_founding_unit_submission"]["properties"]["idempotency_key"]
            row["description"] += " Replay returns the stored receipt."

        self.assert_red(mutate, "authority schema founding-slot description restores deleted founding-receipt semantic")

    def test_service_surface_keeps_commit_only_marker(self) -> None:
        def text_mutate(texts: dict) -> None:
            path = (gate.SPEC_ROOT / "zh" / "sync" / "service-surface.md").resolve()
            texts[path] = texts[path].replace("第四个 Commit 的 `committed_at` 是唯一接受时间", "接受时间另行保存")

        self.assert_red(marker="service-surface Event-submit section omits commit-only marker", text_mutate=text_mutate)

    def test_service_surface_rejects_deleted_receipt_semantic(self) -> None:
        def text_mutate(texts: dict) -> None:
            path = (gate.SPEC_ROOT / "zh" / "sync" / "service-surface.md").resolve()
            texts[path] = texts[path].replace("不返回第二张 receipt", "不返回第二张 receipt，但返回 source-signed receipt")

        self.assert_red(marker="service-surface Event-submit section restores deleted founding-receipt semantic", text_mutate=text_mutate)

    def test_device_lifecycle_keeps_commit_only_marker(self) -> None:
        def text_mutate(texts: dict) -> None:
            path = (gate.SPEC_ROOT / "zh" / "crypto-media" / "device-lifecycle.md").resolve()
            texts[path] = texts[path].replace("不存在 founding receipt 输入或输出", "founding finality 由服务内部保存")

        self.assert_red(marker="device-lifecycle accepted-founding section omits commit-only marker", text_mutate=text_mutate)

    def test_device_lifecycle_rejects_deleted_receipt_semantic(self) -> None:
        def text_mutate(texts: dict) -> None:
            path = (gate.SPEC_ROOT / "zh" / "crypto-media" / "device-lifecycle.md").resolve()
            texts[path] = texts[path].replace("不存在 founding receipt 输入或输出", "不存在 founding receipt 输入或输出；peer carries a source acceptance receipt")

        self.assert_red(marker="device-lifecycle accepted-founding section restores deleted founding-receipt semantic", text_mutate=text_mutate)

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

    def test_independently_closed_reason_must_be_active(self) -> None:
        def mutate(documents: dict) -> None:
            rows = documents[gate.ERRORS.resolve()]["reason_codes"]
            row = gate._find(rows, "code", "direct_conversation_binding_invalid")
            row["status"] = "reserved"
            row["activation_condition"] = "mutation"

        self.assert_red(mutate, "must be active after its independent machine producer")

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
