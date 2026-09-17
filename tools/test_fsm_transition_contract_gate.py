"""A typed current result lifecycle axis must have a machine behind it.

`check_fsm_state_reachability` has been running since before the
authority-commit clean break. The break renamed everything it reads:
`transition_contracts`, `transition_templates` and `cell_contracts` off the
registry, `cell_writes[].cell_family` and `effect_projection` off each write.
None of those names survived. Three `or {}` absorbed the first three, the write
loop then iterated an empty dict, and the gate returned without a word -- while
`zh/models/circle.md`, `zh/models/morph.md`, `zh/models/realm-and-space.md` and
`zh/models/strand-and-message.md` each still say, verbatim, that object
lifecycle transitions have their source of truth in `transition_contracts`.

That is worse than having no gate: `check` recorded "nobody looked" as "the
check passed". So the gate now reads `result_writes[]`, and an absent contract
block is a failure rather than an early return.

Declaring the machines exposed the second half. Three families were written by
two different vocabularies at once -- `ak.call.recording.start` and
`ak.realm.create` opened them with a `transition`, and every later change came
through a `set`. A whole-value `set` installs a state without consulting
`allowed_transitions`, so the transition table was decorative for exactly the
edges that matter. Those three writes are transitions now, and a non-transition
write to a family that declares a machine is an error.

Every mutation reads as a delta against the live baseline, so each test keeps
testing its own proposition as coverage grows.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as write_gate
from tools.artifact_lint import schemas as gate

CONTRACT_REGISTRY = gate.ARTIFACTS / "registry" / "contract-registry.json"
FSM_FAMILIES = (
    "agent_status",
    "realm_history_access",
    "call_recording_state",
    "call_transcript_state",
)


def row_of(registry: dict, kind: str) -> dict:
    for row in registry["event_kind_registry"]["event_kinds"]:
        if row["event_kind"] == kind:
            return row
    raise AssertionError(f"{kind} is not a registered Event kind")


def write_of(registry: dict, kind: str, family: str) -> dict:
    for write in row_of(registry, kind)["result_writes"]:
        if write["result_family"] == family:
            return write
    raise AssertionError(f"{kind} declares no write of {family}")


class FsmTransitionContractGateTest(unittest.TestCase):
    def _run(self, mutate=None) -> list[str]:
        original_load_json = gate.load_json
        documents = {}
        if mutate is not None:
            document = copy.deepcopy(original_load_json(gate.Lint(), CONTRACT_REGISTRY))
            mutate(document)
            documents[CONTRACT_REGISTRY.resolve()] = document

        def load_json_with_mutation(lint, path):
            return documents.get(path.resolve(), original_load_json(lint, path))

        gate.load_json = load_json_with_mutation
        try:
            lint = gate.Lint()
            gate.check_fsm_state_reachability(lint)
            return lint.errors
        finally:
            gate.load_json = original_load_json

    def _newly_reported(self, mutate) -> list[str]:
        baseline = set(self._run())
        return sorted(set(self._run(mutate)) - baseline)

    # ---- the live baseline ----------------------------------------------

    def test_the_live_registry_is_clean(self) -> None:
        """Absolute on purpose: a gate whose baseline is not zero cannot say
        whether the next edit broke something."""
        self.assertEqual(self._run(), [])

    def test_every_transition_write_has_a_declared_machine(self) -> None:
        registry = gate.load_json(gate.Lint(), CONTRACT_REGISTRY)
        contracts = registry["event_kind_registry"]["transition_contracts"]
        written: set[str] = set()
        for row in registry["event_kind_registry"]["event_kinds"]:
            for write in row.get("result_writes") or ():
                if write["result_projection"]["kind"] == "transition":
                    written.add(write["result_family"])
        self.assertEqual(written, set(contracts))
        self.assertEqual(sorted(contracts), sorted(FSM_FAMILIES))

    def test_no_fsm_family_is_written_by_a_whole_value_projection(self) -> None:
        """The defect this gate was blind to for the whole clean break."""
        registry = gate.load_json(gate.Lint(), CONTRACT_REGISTRY)
        contracts = registry["event_kind_registry"]["transition_contracts"]
        offenders = [
            (row["event_kind"], write["result_family"])
            for row in registry["event_kind_registry"]["event_kinds"]
            for write in row.get("result_writes") or ()
            if write["result_family"] in contracts
            and write["result_projection"]["kind"] != "transition"
        ]
        self.assertEqual(offenders, [])

    def test_the_agent_lifecycle_kinds_carry_the_edges_the_table_declares(self) -> None:
        """`account-lifecycle.md` section 9.1 is a four-edge table; before this
        batch three of the four edges had no registered writer at all."""
        registry = gate.load_json(gate.Lint(), CONTRACT_REGISTRY)
        edges = {
            ("ak.self.agent.pause", "paused"),
            ("ak.self.agent.resume", "active"),
            ("ak.self.agent.deactivate", "deactivated"),
        }
        for kind, to_state in edges:
            write = write_of(registry, kind, "agent_status")
            projection = write["result_projection"]
            self.assertEqual(projection["kind"], "transition")
            self.assertEqual(projection["to"], {"const": to_state})
            # The prestate is read from the payload rather than restated here:
            # deactivate legally starts from either non-terminal state, so no
            # single const could carry both of its edges.
            self.assertEqual(projection["from"], {"field": "payload.previous_status"})

    # ---- the gate cannot be silenced by removing its input ---------------

    def test_a_missing_contract_block_is_a_failure_not_a_no_op(self) -> None:
        def mutate(registry: dict) -> None:
            del registry["event_kind_registry"]["transition_contracts"]

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("transition_contracts must be a non-empty object", reported[0])

    def test_an_empty_contract_block_is_a_failure_too(self) -> None:
        def mutate(registry: dict) -> None:
            registry["event_kind_registry"]["transition_contracts"] = {}

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("transition_contracts must be a non-empty object", reported[0])

    # ---- the rules that make a declared machine bind ---------------------

    def test_a_transition_write_with_no_declared_machine_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            del registry["event_kind_registry"]["transition_contracts"]["agent_status"]

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("transition_contracts declares no machine for it", reported[0])

    def test_a_whole_value_write_to_an_fsm_family_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            write = write_of(registry, "ak.realm.history_access", "realm_history_access")
            write["result_projection"] = {
                "kind": "set",
                "value": {"field": "payload.to"},
            }

        reported = self._newly_reported(mutate)
        # The bypass itself, plus the edge that now has no transition writer:
        # the `set` was carrying that edge invisibly.
        self.assertEqual(len(reported), 2, reported)
        self.assertTrue(
            any("without passing allowed_transitions" in e for e in reported), reported
        )

    def test_a_machine_for_an_unregistered_family_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            contracts = registry["event_kind_registry"]["transition_contracts"]
            contracts["circle_lifecycle"] = copy.deepcopy(contracts["call_recording_state"])

        reported = self._newly_reported(mutate)
        # The unregistered family, plus the two ways a machine nothing writes
        # fails on its own terms: no writer for its edge, no way to reach its
        # second state.
        self.assertEqual(len(reported), 3, reported)
        self.assertTrue(
            any("no such typed current result family" in error for error in reported),
            reported,
        )

    # ---- the reachability and table rules still bind ---------------------

    def test_an_allowed_edge_with_no_writer_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            del row_of(registry, "ak.self.agent.resume")["result_writes"]

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("allowed transitions with no registered write", reported[0])
        self.assertIn("paused", reported[0])

    def test_a_state_no_write_can_reach_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            writes = row_of(registry, "ak.realm.create")["result_writes"]
            writes[:] = [w for w in writes if w["result_family"] != "agent_status"]

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 2, reported)
        self.assertTrue(
            any("unreachable from the entry set" in error for error in reported), reported
        )

    def test_an_edge_out_of_a_terminal_state_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            contract = registry["event_kind_registry"]["transition_contracts"]["agent_status"]
            contract["allowed_transitions"].append(["deactivated", "active"])

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 2, reported)
        self.assertTrue(
            any("terminal state has an outgoing transition" in e for e in reported), reported
        )

    def test_a_write_to_a_state_the_machine_never_declares_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            write = write_of(registry, "ak.self.agent.pause", "agent_status")
            write["result_projection"]["to"] = {"const": "retired"}

        reported = self._newly_reported(mutate)
        # The undeclared target, plus the edge and the state that pause was the
        # only writer of.
        self.assertEqual(len(reported), 3, reported)
        self.assertTrue(any("undeclared state retired" in e for e in reported), reported)

    def test_a_const_edge_outside_the_table_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            write = write_of(registry, "ak.call.state", "call_recording_state")
            write["result_projection"]["from"] = {"const": "stopped"}

        reported = self._newly_reported(mutate)
        self.assertTrue(
            any("outside allowed_transitions" in error for error in reported), reported
        )

    def test_two_entry_idioms_at_once_are_reported(self) -> None:
        def mutate(registry: dict) -> None:
            contract = registry["event_kind_registry"]["transition_contracts"]["agent_status"]
            contract["initial_states"] = ["uninitialized"]

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("exactly one of initial_state", reported[0])

    def test_a_replay_rule_that_contradicts_the_causal_model_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            contract = registry["event_kind_registry"]["transition_contracts"]["agent_status"]
            contract["idempotent_replay"] = "same_transition_same_basis_noop"

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("same_event_identity_replay_noop", reported[0])


class TransitionProjectionEndpointTest(unittest.TestCase):
    """`from` / `to` must name exactly one source.

    A `field` endpoint is what lets one row carry several edges, but it must not
    become a way to declare nothing: the gate above resolves the field against
    the payload schema, and an endpoint with neither source -- or with both --
    resolves to nothing at all.
    """

    def _run(self, mutate=None) -> list[str]:
        original_load_json = write_gate.load_json
        documents = {}
        if mutate is not None:
            document = copy.deepcopy(
                original_load_json(write_gate.Lint(), write_gate.EVENT_KIND_REGISTRY)
            )
            mutate(document)
            documents[write_gate.EVENT_KIND_REGISTRY.resolve()] = document

        def load_json_with_mutation(lint, path):
            return documents.get(path.resolve(), original_load_json(lint, path))

        write_gate.load_json = load_json_with_mutation
        try:
            lint = write_gate.Lint()
            write_gate.check_result_write_contracts(lint)
            return lint.errors
        finally:
            write_gate.load_json = original_load_json

    def _newly_reported(self, mutate) -> list[str]:
        baseline = set(self._run())
        return sorted(set(self._run(mutate)) - baseline)

    def _write(self, registry: dict) -> dict:
        for row in registry["event_kinds"]:
            if row["event_kind"] == "ak.self.agent.deactivate":
                return row["result_writes"][0]
        raise AssertionError("ak.self.agent.deactivate is not registered")

    def test_the_live_registry_is_clean(self) -> None:
        self.assertEqual(self._run(), [])

    def test_an_endpoint_with_no_source_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            self._write(registry)["result_projection"]["from"] = {}

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("exactly one of const/field", reported[0])

    def test_an_endpoint_with_both_sources_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            self._write(registry)["result_projection"]["from"] = {
                "const": "active",
                "field": "payload.previous_status",
            }

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("exactly one of const/field", reported[0])

    def test_an_unwalkable_field_path_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            self._write(registry)["result_projection"]["from"] = {
                "field": "payload.previous_status[0]"
            }

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("dot-separated named fields", reported[0])

    def test_an_unknown_projection_member_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            self._write(registry)["result_projection"]["transition_contract"] = "agent_status"

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("unknown member(s)", reported[0])


if __name__ == "__main__":
    unittest.main()
