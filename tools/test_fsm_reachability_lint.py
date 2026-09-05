"""Mutation tests for the service-http-binding.md 2.2.2 FSM reachability gate.

OPEN-FLOW-PROTO-013 survived because no lint walked the machines: the agent
status family declared uninitialized -> active as allowed but no registered
write performed it. Each case below recreates one variant of that rot and
expects the gate to fail.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import schemas as lint_artifacts

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
CONTRACT_PATH = (ARTIFACTS / "registry" / "contract-registry.json").resolve()

AGENT_FAMILY = "ak.component.agent.status.v1"


def _agent_entry_write_index(contract: dict) -> int:
    writes = contract["event_kind_registry"]["cell_contracts"]["ak.realm.create"][
        "cell_writes"
    ]
    for index, write in enumerate(writes):
        if write.get("cell_family") == AGENT_FAMILY:
            return index
    raise AssertionError("agent status entry write not found on ak.realm.create")


class FsmReachabilityLintTest(unittest.TestCase):
    def _run(self, *, mutate=None) -> list[str]:
        original_load_json = lint_artifacts.load_json
        mutated = None
        if mutate is not None:
            mutated = copy.deepcopy(
                original_load_json(lint_artifacts.Lint(), CONTRACT_PATH)
            )
            mutate(mutated)

        def load_json_with_mutation(lint, path):
            if mutated is not None and path.resolve() == CONTRACT_PATH:
                return mutated
            return original_load_json(lint, path)

        lint_artifacts.load_json = load_json_with_mutation
        try:
            lint = lint_artifacts.Lint()
            lint_artifacts.check_fsm_state_reachability(lint)
            return lint.errors
        finally:
            lint_artifacts.load_json = original_load_json

    def test_committed_tree_passes(self) -> None:
        self.assertEqual(self._run(), [])

    def test_removing_the_agent_entry_write_recreates_proto_013(self) -> None:
        # Deleting the uninitialized -> active genesis write must bring the
        # exact OPEN-FLOW-PROTO-013 shape back as a lint failure.
        def mutate(contract):
            writes = contract["event_kind_registry"]["cell_contracts"][
                "ak.realm.create"
            ]["cell_writes"]
            writes.pop(_agent_entry_write_index(contract))

        errors = self._run(mutate=mutate)
        self.assertTrue(
            any(AGENT_FAMILY in e and "unreachable" in e for e in errors),
            errors,
        )

    def test_two_entry_idioms_fail(self) -> None:
        def mutate(contract):
            family = contract["event_kind_registry"]["fsm_contracts"][AGENT_FAMILY]
            family["initial_states"] = ["uninitialized"]

        errors = self._run(mutate=mutate)
        self.assertTrue(
            any("exactly one of initial_state" in e for e in errors), errors
        )

    def test_unknown_contract_key_fails(self) -> None:
        # The entry idiom key set is closed so that a fourth spelling cannot
        # slip in unnoticed and evade the reachability analysis.
        def mutate(contract):
            family = contract["event_kind_registry"]["fsm_contracts"][AGENT_FAMILY]
            family["boot_state"] = "active"

        errors = self._run(mutate=mutate)
        self.assertTrue(any("unknown keys" in e for e in errors), errors)

    def test_transition_out_of_a_terminal_state_fails(self) -> None:
        # `terminal_states` is declared by every fsm contract and read by no
        # implementation: the SDK's `Fsm` carries only the transition table and
        # the initial state. So terminality holds exactly as far as the table
        # does, and an edge leaving a terminal state would simply be taken.
        def mutate(contract):
            family = contract["event_kind_registry"]["fsm_contracts"][AGENT_FAMILY]
            family["allowed_transitions"].append(["deactivated", "active"])

        errors = self._run(mutate=mutate)
        self.assertTrue(
            any("terminal state has an outgoing transition" in e for e in errors),
            errors,
        )

    def test_a_terminal_self_loop_stays_legal(self) -> None:
        # A self-loop out of a terminal state is a repeated declaration, not an
        # escape; `ak.component.realm.link.v1` relies on exactly that so a
        # redeclared tombstone is idempotent rather than a sibling conflict.
        def mutate(contract):
            family = contract["event_kind_registry"]["fsm_contracts"][AGENT_FAMILY]
            family["allowed_transitions"].append(["deactivated", "deactivated"])

        errors = self._run(mutate=mutate)
        self.assertFalse(
            any("terminal state has an outgoing transition" in e for e in errors),
            errors,
        )

    def test_a_terminal_state_outside_states_fails(self) -> None:
        def mutate(contract):
            family = contract["event_kind_registry"]["fsm_contracts"][AGENT_FAMILY]
            family["terminal_states"].append("retired")

        errors = self._run(mutate=mutate)
        self.assertTrue(
            any("terminal state retired not in states" in e for e in errors), errors
        )

    def test_write_outside_allowed_transitions_fails(self) -> None:
        def mutate(contract):
            writes = contract["event_kind_registry"]["cell_contracts"][
                "ak.realm.create"
            ]["cell_writes"]
            write = writes[_agent_entry_write_index(contract)]
            write["effect_projection"]["to"] = {"const": "paused"}

        errors = self._run(mutate=mutate)
        self.assertTrue(
            any("outside allowed_transitions" in e for e in errors), errors
        )

    def test_allowed_transition_without_write_fails(self) -> None:
        def mutate(contract):
            family = contract["event_kind_registry"]["fsm_contracts"][AGENT_FAMILY]
            family["allowed_transitions"].append(["deactivated", "active"])

        errors = self._run(mutate=mutate)
        self.assertTrue(
            any("no registered write" in e for e in errors), errors
        )


if __name__ == "__main__":
    unittest.main()
