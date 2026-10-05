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
                gate.ARTIFACTS / "schemas" / "keys-operations.schema.json",
                gate.ARTIFACTS / "schemas" / "realm-commit.schema.json",
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
            docs[gate.AUTHORITY_SCHEMA.resolve()]["$defs"]["stream_scan_outcome"]["properties"]["committed_events"]["items"]["$ref"] = "#/$defs/committed_event_ref"

        self.assert_red(mutate, "per-stream scan")

    def test_account_subscribe_reuses_stream_row(self) -> None:
        def mutate(docs: dict) -> None:
            docs[gate.ACCOUNT_SYNC_SCHEMA.resolve()]["$defs"]["realm_sync_entry"]["properties"]["committed_events"]["items"]["$ref"] = "./event-envelope.schema.json"

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

    def test_fixture_requires_query_despite_product_changes(self) -> None:
        def mutate(docs: dict) -> None:
            docs[gate.FIXTURE.resolve()]["positive_flows"].remove(
                "changed_product_projection_still_resolves_historical_signer"
            )

        self.assert_red(mutate, "liveness flows")

    def test_fixture_rejects_waiting_for_reload(self) -> None:
        def mutate(docs: dict) -> None:
            docs[gate.FIXTURE.resolve()]["negative_cases"].remove(
                "agent_reply_waits_for_unrelated_account_frame_or_reload"
            )

        self.assert_red(mutate, "negative cases")

    def test_prose_keeps_resolution_liveness(self) -> None:
        def mutate(texts: dict) -> None:
            texts[gate.SERVER_PROSE.resolve()] = texts[gate.SERVER_PROSE.resolve()].replace(
                "历史签名证据解析的活性", "历史查询说明", 1
            )

        self.assert_red(marker="历史签名证据解析的活性", text_mutate=mutate)

    def test_sync_prose_forbids_third_carrier(self) -> None:
        def mutate(texts: dict) -> None:
            texts[gate.SYNC_PROSE.resolve()] = texts[gate.SYNC_PROSE.resolve()].replace("不得新增", "可以新增", 1)

        self.assert_red(marker="不得新增", text_mutate=mutate)

    def test_self_submission_rule_single_field_mutations(self) -> None:
        def leaves(value, prefix=()):
            for key, item in value.items():
                if isinstance(item, dict):
                    yield from leaves(item, prefix + (key,))
                else:
                    yield prefix + (key,)

        for path in leaves(gate.SELF_SUBMISSION_RULE):
            for target in (gate.CONTRACT, gate.FIXTURE):
                with self.subTest(path=path, target=target.name):
                    def mutate(docs, path=path, target=target):
                        if target == gate.CONTRACT:
                            value = docs[target.resolve()]["did_evidence_boundary_registry"]["governance_result_consumption_contract"]["self_submission_historical_source"]
                        else:
                            value = docs[target.resolve()]["self_submission_rule"]
                        for key in path[:-1]:
                            value = value[key]
                        value[path[-1]] = None
                    self.assert_red(mutate, "restricted PCR rules")

    def test_self_submission_cannot_add_raw_local_source(self) -> None:
        def mutate(docs):
            docs[gate.FIXTURE.resolve()]["construction_sources"].append("raw_local_event")
        self.assert_red(mutate, "close coordinate construction")

    def test_self_submission_negative_cases_are_required(self) -> None:
        for case in sorted(gate.NEGATIVE_CASES):
            if not case.startswith("self_submission_"):
                continue
            with self.subTest(case=case):
                def mutate(docs, case=case):
                    docs[gate.FIXTURE.resolve()]["negative_cases"].remove(case)
                self.assert_red(mutate, "negative cases")

    def test_self_submission_positive_flows_are_required(self) -> None:
        for flow in sorted(gate.SELF_SUBMISSION_FLOWS):
            with self.subTest(flow=flow):
                def mutate(docs, flow=flow):
                    docs[gate.FIXTURE.resolve()]["positive_flows"].remove(flow)
                self.assert_red(mutate, "no-scan flows")

    def test_runner_invokes_gate(self) -> None:
        def mutate(texts: dict) -> None:
            texts[gate.RUNNER.resolve()] = texts[gate.RUNNER.resolve()].replace("check_signer_key_historical_coordinate(lint)", "check_removed(lint)")

        self.assert_red(marker="phase-2 runner", text_mutate=mutate)


    def test_foreign_fact_target_commit_cannot_enter_digest_projection(self) -> None:
        def mutate(docs):
            fact = docs[gate.AUTHORITY_SCHEMA.resolve()]["$defs"]["human_historical_signer_fact"]
            fact["properties"]["commit_id"] = {"type": "string"}
        self.assert_red(mutate, "minimal, required and closed")

    def test_foreign_source_time_cannot_be_target_time(self) -> None:
        def mutate(docs):
            rule = docs[gate.CONTRACT.resolve()]["did_evidence_boundary_registry"]["governance_result_consumption_contract"]["foreign_human_historical_signer_delivery"]
            rule["source_accepted_time"] = "target_commit.committed_at"
        self.assert_red(mutate, "original authorization time")

    def test_peer_fact_metadata_cannot_enter_self_scan(self) -> None:
        def mutate(docs):
            defs = docs[gate.AUTHORITY_SCHEMA.resolve()]["$defs"]
            defs["stream_scan_outcome"]["properties"]["producer_signer_facts"] = {"type": "array"}
        self.assert_red(mutate, "self scan must not acquire")

    def test_directory_cannot_disclose_forward_source(self) -> None:
        def mutate(docs):
            path = (gate.ARTIFACTS / "schemas" / "keys-operations.schema.json").resolve()
            docs[path]["$defs"]["device_projection_attestation_core"]["properties"]["event_authorization"] = {"type": "object"}
        self.assert_red(mutate, "directory must remain closed")

    def test_forward_cannot_omit_event_bound_source(self) -> None:
        def mutate(docs):
            path = (gate.ARTIFACTS / "schemas" / "keys-operations.schema.json").resolve()
            docs[path]["$defs"]["forward_device_projection_attestation_core"]["required"].remove("event_authorization")
        self.assert_red(mutate, "forward must require")


    def test_foreign_human_real_signatures_recompute_independently(self) -> None:
        transcript = self.documents[gate.FIXTURE.resolve()]["foreign_human_historical_signer_delivery"]["crypto_transcript"]
        self.assertEqual(gate._foreign_human_transcript_errors(transcript), [])

    def test_foreign_human_every_signed_leaf_mutation_is_rejected(self) -> None:
        original = self.documents[gate.FIXTURE.resolve()]["foreign_human_historical_signer_delivery"]["crypto_transcript"]
        def leaves(value, path=()):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield from leaves(child, path+(key,))
            elif isinstance(value, list):
                for key, child in enumerate(value):
                    yield from leaves(child, path+(key,))
            else:
                yield path, value
        for root in ["event", "origin_attestation", "fact", "commit", "handoff", "handoff_inventory", "alternate_authentic_origin_attestation", "alternate_fact", "handoff_fenced_imported_originals"]:
            for path, value in leaves(original[root]):
                with self.subTest(layer=root, path=path):
                    changed = copy.deepcopy(original)
                    cursor = changed[root]
                    for key in path[:-1]:
                        cursor = cursor[key]
                    cursor[path[-1]] = (not value if isinstance(value, bool) else value+1 if isinstance(value, int) else 0 if value is None else value+"_changed")
                    self.assertTrue(gate._foreign_human_transcript_errors(changed))

    def test_same_event_same_key_second_authentic_origin_cannot_replace_governor_choice(self) -> None:
        transcript = copy.deepcopy(self.documents[gate.FIXTURE.resolve()]["foreign_human_historical_signer_delivery"]["crypto_transcript"])
        self.assertEqual(gate._foreign_human_transcript_errors(transcript), [])
        transcript["origin_attestation"] = transcript["alternate_authentic_origin_attestation"]
        transcript["origin_binding"] = transcript["alternate_origin_binding"]
        transcript["fact"] = transcript["alternate_fact"]
        self.assertIn("original_governor_fact_digest", gate._foreign_human_transcript_errors(transcript))

    def test_forward_core_only_signed_preimage_is_not_wrapper_proof(self) -> None:
        from tools.regenerate_foreign_human_signer_transcript import jws, sha, KEY_A_SEED
        transcript = copy.deepcopy(self.documents[gate.FIXTURE.resolve()]["foreign_human_historical_signer_delivery"]["crypto_transcript"])
        binding = copy.deepcopy(transcript["origin_binding"])
        binding["payload_digest"] = sha(transcript["origin_attestation"]["attestation"])
        transcript["origin_attestation"]["proof"]["jws"] = jws(binding, KEY_A_SEED)
        errors = gate._foreign_human_transcript_errors(transcript)
        self.assertTrue(any("InvalidSignature" in error for error in errors))

    def test_commit_valid_station_signature_does_not_replace_content_id_check(self) -> None:
        from tools.regenerate_detached_object_signature_kat import make_signature, KEY_A_SEED
        transcript = copy.deepcopy(self.documents[gate.FIXTURE.resolve()]["foreign_human_historical_signer_delivery"]["crypto_transcript"])
        commit = transcript["commit"]
        commit["stream_position"] += 1
        unsigned = {key:value for key,value in commit.items() if key != "signature"}
        commit["signature"], _ = make_signature("ak.realm_commit_signature.v1", unsigned, commit["signature"]["verification_method"], KEY_A_SEED)
        self.assertIn("commit_content_id", gate._foreign_human_transcript_errors(transcript))

    def test_peer_scan_and_handoff_missing_original_facts_are_rejected(self) -> None:
        original = self.documents[gate.FIXTURE.resolve()]["foreign_human_historical_signer_delivery"]["crypto_transcript"]
        for field in ["peer_scan", "handoff_inventory"]:
            transcript = copy.deepcopy(original)
            if field == "peer_scan":
                transcript[field]["producer_signer_facts"] = []
                expected = "scan_exact_one_fact"
            else:
                transcript[field] = []
                expected = "handoff_inventory_digest"
            self.assertIn(expected, gate._foreign_human_transcript_errors(transcript))

    def test_handoff_resigned_incomplete_inventory_cannot_replace_fenced_set(self) -> None:
        from tools.regenerate_foreign_human_signer_transcript import sha, typed_id
        from tools.regenerate_detached_object_signature_kat import make_signature, KEY_A_SEED, KEY_B_SEED
        t = copy.deepcopy(self.documents[gate.FIXTURE.resolve()]["foreign_human_historical_signer_delivery"]["crypto_transcript"])
        t["handoff_inventory"] = []
        h = t["handoff"]
        old_vm = h["old_authority_signature"]["verification_method"]
        new_vm = h["new_authority_acceptance_signature"]["verification_method"]
        h["historical_signer_facts_digest"] = sha([])
        unsigned = {k:v for k,v in h.items() if k not in ["handoff_id", "old_authority_signature", "new_authority_acceptance_signature"]}
        h["handoff_id"] = typed_id("realm_authority_handoff", unsigned)
        unsigned = {k:v for k,v in h.items() if k not in ["old_authority_signature", "new_authority_acceptance_signature"]}
        h["old_authority_signature"], _ = make_signature("ak.realm_authority_handoff_old_signature.v1", unsigned, old_vm, KEY_A_SEED)
        h["new_authority_acceptance_signature"], _ = make_signature("ak.realm_authority_handoff_new_acceptance_signature.v1", unsigned, new_vm, KEY_B_SEED)
        errors = gate._foreign_human_transcript_errors(t)
        self.assertIn("handoff_inventory_exact_fenced_set", errors)
        self.assertNotIn("handoff_inventory_digest", errors)
        self.assertFalse(any("InvalidSignature" in error for error in errors))

    def test_handoff_duplicate_and_extra_inventory_rejected(self) -> None:
        original = self.documents[gate.FIXTURE.resolve()]["foreign_human_historical_signer_delivery"]["crypto_transcript"]
        t = copy.deepcopy(original)
        t["handoff_inventory"].append(copy.deepcopy(t["handoff_inventory"][0]))
        self.assertIn("handoff_inventory_duplicate", gate._foreign_human_transcript_errors(t))
        t = copy.deepcopy(original)
        t["handoff_fenced_imported_originals"] = []
        self.assertIn("handoff_inventory_exact_fenced_set", gate._foreign_human_transcript_errors(t))


if __name__ == "__main__":
    unittest.main()
