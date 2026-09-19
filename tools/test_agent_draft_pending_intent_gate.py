"""Mutation tests for the Agent draft D3 pending-intent closure."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import agent_draft_pending_intent as gate
from tools.artifact_lint.core import Lint


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class AgentDraftPendingIntentGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = {
            gate.CONTRACT.resolve(): read(gate.CONTRACT),
            gate.ACCOUNT_DATA.resolve(): read(gate.ACCOUNT_DATA),
            gate.EVENT_PAYLOAD.resolve(): read(gate.EVENT_PAYLOAD),
            gate.PRIVATE_SCHEMA.resolve(): read(gate.PRIVATE_SCHEMA),
            gate.ACCOUNT_SUBSCRIBE.resolve(): read(gate.ACCOUNT_SUBSCRIBE),
            gate.VECTOR_REGISTRY.resolve(): read(gate.VECTOR_REGISTRY),
            gate.PROOF_CONTEXT.resolve(): read(gate.PROOF_CONTEXT),
            gate.FIXTURE.resolve(): read(gate.FIXTURE),
        }

    def run_gate(self, mutate=None) -> list[str]:
        documents = copy.deepcopy(self.documents)
        if mutate is not None:
            mutate(documents)
        original = gate.load_json

        def load_json(lint, path):  # type: ignore[no-untyped-def]
            resolved = Path(path).resolve()
            if resolved in documents:
                return documents[resolved]
            return original(lint, path)

        gate.load_json = load_json
        try:
            lint = Lint()
            gate.check_agent_draft_pending_intent(lint)
            return lint.errors
        finally:
            gate.load_json = original

    def assert_red(self, mutate, marker: str) -> None:
        errors = self.run_gate(mutate)
        self.assertTrue(any(marker in error for error in errors), errors)

    def test_complete_contract_passes(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_wrong_owner_fails(self) -> None:
        def mutate(documents: dict) -> None:
            documents[gate.CONTRACT.resolve()]["event_kind_registry"]["actor_private_contracts"]["event_writes"][gate.EVENT_KIND]["storage_owner"]["account_id_source"] = "envelope.actor_id"

        self.assert_red(mutate, "exact controller")

    def test_missing_lifecycle_branch_fails(self) -> None:
        def mutate(documents: dict) -> None:
            documents[gate.CONTRACT.resolve()]["event_kind_registry"]["actor_private_contracts"]["event_writes"][gate.EVENT_KIND]["pending_intent_lifecycle"].pop("failure_recovery")

        self.assert_red(mutate, "lifecycle must close")

    def test_pending_projection_cannot_drop_content_handoff(self) -> None:
        def mutate(documents: dict) -> None:
            projection = documents[gate.CONTRACT.resolve()]["event_kind_registry"]["actor_private_contracts"]["event_writes"][gate.EVENT_KIND]["value_projection"]
            projection["members"] = [
                member for member in projection["members"] if member["target"] != "content_handoff"
            ]

        self.assert_red(mutate, "map every closed schema member")

    def test_propose_cannot_enter_account_data_writer_allowlist(self) -> None:
        def mutate(documents: dict) -> None:
            row = gate._find(documents[gate.ACCOUNT_DATA.resolve()]["account_data_key_patterns"], "key_pattern", gate.KEY_PATTERN)
            row["write_event_kinds"].append(gate.EVENT_KIND)

        self.assert_red(mutate, "writer allowlist")

    def test_source_intent_cannot_be_dropped(self) -> None:
        def mutate(documents: dict) -> None:
            row = gate._find(documents[gate.ACCOUNT_DATA.resolve()]["account_data_key_patterns"], "key_pattern", gate.KEY_PATTERN)
            row.pop("source_intent")

        self.assert_red(mutate, "source-intent gate")

    def test_propose_requires_hpke_handoff(self) -> None:
        def mutate(documents: dict) -> None:
            propose = documents[gate.EVENT_PAYLOAD.resolve()]["$defs"]["agent_draft_propose_payload"]
            propose["required"].remove("content_handoff")

        self.assert_red(mutate, "content_handoff")

    def test_pending_intent_cannot_enter_shared_reducer(self) -> None:
        def mutate(documents: dict) -> None:
            documents[gate.CONTRACT.resolve()]["event_kind_registry"]["actor_private_contracts"]["event_writes"][gate.EVENT_KIND]["shared_realm_effect"] = "typed_current_result"

        self.assert_red(mutate, "shared reducer")

    def test_live_pending_intent_cannot_drop_handoff(self) -> None:
        def mutate(documents: dict) -> None:
            live = documents[gate.PRIVATE_SCHEMA.resolve()]["$defs"]["agent_draft_pending_intent_live"]
            live["required"].remove("content_handoff")

        self.assert_red(mutate, "live pending intent")

    def test_terminal_redacted_cannot_restore_ciphertext(self) -> None:
        def mutate(documents: dict) -> None:
            terminal = documents[gate.PRIVATE_SCHEMA.resolve()]["$defs"]["agent_draft_pending_intent_terminal_redacted"]
            terminal["properties"]["content_handoff"] = {"$ref": "#/$defs/content_handoff"}

        self.assert_red(mutate, "forbid ciphertext")

    def test_terminal_redacted_cannot_drop_source_identity(self) -> None:
        def mutate(documents: dict) -> None:
            terminal = documents[gate.PRIVATE_SCHEMA.resolve()]["$defs"]["agent_draft_pending_intent_terminal_redacted"]
            terminal["required"].remove("accepted_event_id")

        self.assert_red(mutate, "preserve identity/source")

    def test_dedicated_top_level_container_cannot_be_removed(self) -> None:
        def mutate(documents: dict) -> None:
            documents[gate.ACCOUNT_SUBSCRIBE.resolve()]["properties"].pop("agent_draft_pending_intents")

        self.assert_red(mutate, "top-level container")

    def test_baseline_channel_set_cannot_omit_pending_intents(self) -> None:
        def mutate(documents: dict) -> None:
            baseline = documents[gate.ACCOUNT_SUBSCRIBE.resolve()]["$defs"]["account_baseline_segment"]
            baseline["properties"]["channels"]["items"]["enum"].remove("agent_draft_pending_intents")

        self.assert_red(mutate, "exactly five global channels")

    def test_baseline_cannot_drop_frozen_cut_or_offsets(self) -> None:
        def mutate(documents: dict) -> None:
            baseline = documents[gate.ACCOUNT_SUBSCRIBE.resolve()]["$defs"]["agent_draft_pending_intent_baseline_container"]
            baseline["required"].remove("snapshot_cut_position")

        self.assert_red(mutate, "frozen cut and page offsets")

    def test_delta_cannot_drop_projection_position(self) -> None:
        def mutate(documents: dict) -> None:
            delta = documents[gate.ACCOUNT_SUBSCRIBE.resolve()]["$defs"]["agent_draft_pending_intent_delta_container"]
            delta["required"].remove("projection_position")

        self.assert_red(mutate, "independent projection position")

    def test_pending_changes_share_one_combined_item_bound(self) -> None:
        def mutate(documents: dict) -> None:
            delta = documents[gate.ACCOUNT_SUBSCRIBE.resolve()]["$defs"]["agent_draft_pending_intent_delta_container"]
            delta["properties"]["items"]["maxItems"] = 101

        self.assert_red(mutate, "combined 100-change bound")

    def test_pending_channel_cannot_impose_universal_baseline_offsets(self) -> None:
        def mutate(documents: dict) -> None:
            baseline = documents[gate.ACCOUNT_SUBSCRIBE.resolve()]["$defs"]["account_baseline_segment"]
            baseline["properties"]["channel_offsets"] = {"type": "object"}
            baseline["required"].append("channel_offsets")

        self.assert_red(mutate, "second universal baseline offset map")

    def test_authz_cannot_allow_agent_session(self) -> None:
        def mutate(documents: dict) -> None:
            rows = documents[gate.CONTRACT.resolve()]["schema_registry"]["schemas"]
            projection = gate._find(rows, "schema_id", "ak.schema.account_subscribe_frame.v1")["channel_contract"]
            projection["authorization"]["deny"].remove("agent_session")

        self.assert_red(mutate, "forbidden audiences")

    def test_projection_cannot_reuse_station_cas(self) -> None:
        def mutate(documents: dict) -> None:
            rows = documents[gate.CONTRACT.resolve()]["schema_registry"]["schemas"]
            projection = gate._find(rows, "schema_id", "ak.schema.account_subscribe_frame.v1")["channel_contract"]
            projection["top_level_field"] = "account_data.station_cas"

        self.assert_red(mutate, "dedicated top-level field")

    def test_projection_item_ref_must_name_ordered_change_union(self) -> None:
        def mutate(documents: dict) -> None:
            rows = documents[gate.CONTRACT.resolve()]["schema_registry"]["schemas"]
            projection = gate._find(rows, "schema_id", "ak.schema.account_subscribe_frame.v1")["channel_contract"]
            projection["item_schema_ref"] = "schemas/agent-draft-private.schema.json#/$defs/agent_draft_pending_intent"

        self.assert_red(mutate, "ordered change item refs")

    def test_sdk_channel_variant_must_be_registered(self) -> None:
        def mutate(documents: dict) -> None:
            rows = documents[gate.CONTRACT.resolve()]["schema_registry"]["schemas"]
            row = gate._find(rows, "schema_id", "ak.schema.account_subscribe_frame.v1")
            row["sdk_projection"]["baseline_channel_variant"] = "StationCas"

        self.assert_red(mutate, "SDK frame/container/channel")

    def test_fixture_cannot_drop_foreign_account_denial(self) -> None:
        def mutate(documents: dict) -> None:
            case = gate._find(documents[gate.FIXTURE.resolve()]["cases"], "name", "account_subscribe_projection")
            case["variants"].remove("foreign_account_denied")

        self.assert_red(mutate, "authz/forbidden-carrier variants")

    def test_fixture_cannot_drop_terminal_ciphertext_rejection(self) -> None:
        def mutate(documents: dict) -> None:
            fixture = documents[gate.FIXTURE.resolve()]
            fixture["schema_validation_cases"] = [
                row for row in fixture["schema_validation_cases"]
                if row.get("name") != "agent_draft_pending_intent_terminal_ciphertext_rejected"
            ]

        self.assert_red(mutate, "live/terminal/baseline/delta schema validation cases")

    def test_vector_must_cover_dedicated_sync_channel(self) -> None:
        def mutate(documents: dict) -> None:
            vector = gate._find(documents[gate.VECTOR_REGISTRY.resolve()]["vectors"], "vector_id", gate.VECTOR_ID)
            vector["source_refs"].remove("spec/v1/zh/sync/client-sync.md")

        self.assert_red(mutate, "dedicated sync channel")

    def test_fixture_requires_atomic_rollback_mutation(self) -> None:
        def mutate(documents: dict) -> None:
            case = gate._find(documents[gate.FIXTURE.resolve()]["cases"], "name", "holder_cas_consumption_and_recovery")
            case["variants"].remove("failure_between_account_data_and_intent_transition")

        self.assert_red(mutate, "rollback")

    def test_key_schema_cannot_restore_ambiguous_literal_segments(self) -> None:
        def mutate(documents: dict) -> None:
            schema = documents[gate.PRIVATE_SCHEMA.resolve()]["$defs"]["agent_draft_account_data_key"]
            schema["pattern"] = r"^ak\.agent\.draft\.v1:[^:]+:[^:]+$"

        self.assert_red(mutate, "fixed 105-character canonical digest key")

    def test_key_schema_cannot_accept_padding_or_wrong_length(self) -> None:
        def mutate(documents: dict) -> None:
            schema = documents[gate.PRIVATE_SCHEMA.resolve()]["$defs"]["agent_draft_account_data_key"]
            schema["maxLength"] = 256

        self.assert_red(mutate, "fixed 105-character canonical digest key")

    def test_event_source_branch_must_reuse_key_schema(self) -> None:
        def mutate(documents: dict) -> None:
            branches = documents[gate.EVENT_PAYLOAD.resolve()]["$defs"]["account_data_set_payload"]["allOf"]
            branches[1]["then"]["properties"]["key"] = {"type": "string"}

        self.assert_red(mutate, "reuse the canonical digest-key schema")

    def test_agent_and_draft_domains_cannot_be_reused(self) -> None:
        def mutate(documents: dict) -> None:
            row = gate._find(documents[gate.ACCOUNT_DATA.resolve()]["account_data_key_patterns"], "key_pattern", gate.KEY_PATTERN)
            row["key_encoding"]["components"]["draft_id"]["domain"] = gate.AGENT_DOMAIN

        self.assert_red(mutate, "draft_id digest component")

    def test_parser_must_require_canonical_round_trip(self) -> None:
        def mutate(documents: dict) -> None:
            row = gate._find(documents[gate.ACCOUNT_DATA.resolve()]["account_data_key_patterns"], "key_pattern", gate.KEY_PATTERN)
            row["key_encoding"]["parser"] = "split the key into two components"

        self.assert_red(mutate, "decode/re-encode equality")

    def test_source_binding_cannot_trust_caller_selector(self) -> None:
        def mutate(documents: dict) -> None:
            row = gate._find(documents[gate.ACCOUNT_DATA.resolve()]["account_data_key_patterns"], "key_pattern", gate.KEY_PATTERN)
            row["key_encoding"]["source_binding"] = "accept a caller-supplied decoded selector"

        self.assert_red(mutate, "source_pending_event_id")

    def test_registered_digest_construction_cannot_drift(self) -> None:
        def mutate(documents: dict) -> None:
            construction = gate._find(documents[gate.PROOF_CONTEXT.resolve()]["digest_constructions"], "construction_id", gate.CONSTRUCTION)
            construction["digest_suite"] = "SHA-512"

        self.assert_red(mutate, "digest construction drifted")

    def test_kat_digest_is_recomputed(self) -> None:
        def mutate(documents: dict) -> None:
            documents[gate.FIXTURE.resolve()]["key_derivation_kat"]["agent_component"]["digest_hex"] = "0" * 64

        self.assert_red(mutate, "KAT does not recompute byte-exactly")

    def test_kat_requires_wrong_domain_and_selector_negatives(self) -> None:
        def mutate(documents: dict) -> None:
            negatives = documents[gate.FIXTURE.resolve()]["key_derivation_kat"]["negative_cases"]
            negatives.remove("agent_domain_reused_for_draft")
            negatives.remove("caller_supplied_decoded_selector")

        self.assert_red(mutate, "negative closure drifted")

    def test_contract_must_recompute_from_source_row(self) -> None:
        def mutate(documents: dict) -> None:
            lifecycle = documents[gate.CONTRACT.resolve()]["event_kind_registry"]["actor_private_contracts"]["event_writes"][gate.EVENT_KIND]["pending_intent_lifecycle"]
            lifecycle["consumption"]["preconditions"] = "key has two components"

        self.assert_red(mutate, "source binding omits")

    def test_runner_invokes_gate(self) -> None:
        source = (ROOT / "tools/artifact_lint/runner.py").read_text(encoding="utf-8")
        self.assertIn("check_agent_draft_pending_intent(lint)", source)


if __name__ == "__main__":
    unittest.main()
