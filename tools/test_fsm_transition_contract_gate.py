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


class FsmTemplateIdiomTest(unittest.TestCase):
    """The third entry idiom, which no registered contract uses.

    `sync/current-results.md` section 2.1 says a transition contract declares
    exactly one of `initial_state` / `initial_states` / `template`, and the
    registry rule repeats it. Nothing has ever declared a template: the
    `transition_templates` block has been absent for the whole life of the
    registry, not renamed away by the clean break like the keys around it. So
    the template half of this gate has never once executed against real data,
    which is the same position `check_fsm_state_reachability` as a whole was in
    until 2026-09-18 -- the difference being that here the silence is correct.

    These tests are what keeps it correct: they drive every branch of the
    template path with a synthetic registry, so the day someone writes the first
    template the merge, the key closure and the conditional-edge lookup are
    known to work rather than assumed to.
    """

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

    @staticmethod
    def _templatize(registry: dict, *, name: str = "agent_lifecycle") -> dict:
        """Rewrite `agent_status` into template form without changing meaning.

        Every key except `axis` is a template key, so the merged view must come
        back byte-identical to the contract the other tests in this file run
        against. Returns the template body for the caller to perturb.
        """
        block = registry["event_kind_registry"]
        contract = block["transition_contracts"]["agent_status"]
        template = {key: value for key, value in contract.items() if key != "axis"}
        block["transition_templates"] = {name: template}
        block["transition_contracts"]["agent_status"] = {
            "axis": contract["axis"],
            "template": name,
        }
        return template

    def test_the_live_registry_declares_no_template(self) -> None:
        """Pinned on purpose. An absent block is the correct state, and if one
        appears these tests stop describing the gate's real input."""
        registry = gate.load_json(gate.Lint(), CONTRACT_REGISTRY)
        self.assertNotIn(
            "transition_templates", registry["event_kind_registry"]
        )
        self.assertEqual(self._run(), [])

    def test_a_template_based_contract_is_equivalent_to_an_inline_one(self) -> None:
        self.assertEqual(self._newly_reported(self._templatize), [])

    def test_a_contract_declaring_an_unknown_template_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            self._templatize(registry)
            registry["event_kind_registry"]["transition_contracts"]["agent_status"][
                "template"
            ] = "no_such_template"

        reported = self._newly_reported(mutate)
        self.assertTrue(
            any("unknown template no_such_template" in error for error in reported),
            reported,
        )

    def test_a_contract_declaring_both_a_template_and_an_initial_state_is_reported(
        self,
    ) -> None:
        """The three entry idioms are exclusive, and a template that carries its
        own entry plus an overriding one is how a machine ends up with two."""

        def mutate(registry: dict) -> None:
            self._templatize(registry)
            registry["event_kind_registry"]["transition_contracts"]["agent_status"][
                "initial_state"
            ] = "uninitialized"

        reported = self._newly_reported(mutate)
        self.assertTrue(
            any("exactly one of initial_state" in error for error in reported),
            reported,
        )

    def test_a_template_key_outside_the_closed_set_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            self._templatize(registry)["axis"] = "lifecycle"

        reported = self._newly_reported(mutate)
        self.assertTrue(
            any("unknown keys ['axis']" in error for error in reported), reported
        )

    def test_a_present_but_empty_template_block_is_reported(self) -> None:
        """An absent block means "no contract uses templates"; an empty one
        means "the template registry is here and says nothing", which is the
        shape a lost block has."""

        def mutate(registry: dict) -> None:
            registry["event_kind_registry"]["transition_templates"] = {}

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("must be a non-empty object", reported[0])

    def test_a_declared_parameter_schema_is_reported(self) -> None:
        def mutate(registry: dict) -> None:
            self._templatize(registry)["parameter_schema"] = {
                "type": "object",
                "properties": {"tier": {"type": "string"}},
            }

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("parameter_schema is not enforced", reported[0])

    def test_state_preserving_profiles_is_reported(self) -> None:
        """The one family that used to declare this
        (`ak.component.mls_last_resort_keypackage.*`) is gone, and no gate ever
        read it. Accepting it again would register an unchecked claim."""

        def mutate(registry: dict) -> None:
            registry["event_kind_registry"]["transition_contracts"]["agent_status"][
                "state_preserving_profiles"
            ] = [
                {
                    "profile": "ak.feature.mls_last_resort_keypackage.v1",
                    "action": "claim_or_consume",
                    "required_state": "published",
                }
            ]

        reported = self._newly_reported(mutate)
        self.assertEqual(len(reported), 1, reported)
        self.assertIn("has no reader in this gate", reported[0])

    # ---- conditional transitions ----------------------------------------

    # The one const -> const edge in the family (`ak.realm.create`). Withholding
    # a field-sourced edge changes nothing the gate can see, so it would not
    # tell a real reader from one that admits every conditional edge.
    _CONDITIONAL_EDGE = ["uninitialized", "active"]

    def _templatize_with_conditional_edge(
        self, registry: dict, *, tier: str
    ) -> None:
        """Move one live edge out of `allowed_transitions` and back in as a
        conditional edge the instance parameters do or do not select."""
        template = self._templatize(registry)
        template["allowed_transitions"] = [
            pair
            for pair in template["allowed_transitions"]
            if pair != self._CONDITIONAL_EDGE
        ]
        template["conditional_transitions"] = [
            {
                "when": {"parameter": "tier", "const": "full"},
                "transition": self._CONDITIONAL_EDGE,
            }
        ]
        registry["event_kind_registry"]["transition_contracts"]["agent_status"][
            "instance_parameters"
        ] = {"tier": tier}

    def test_a_conditional_edge_is_admitted_when_its_parameter_matches(self) -> None:
        def mutate(registry: dict) -> None:
            self._templatize_with_conditional_edge(registry, tier="full")

        self.assertEqual(self._newly_reported(mutate), [])

    def test_a_conditional_edge_is_withheld_when_its_parameter_does_not(self) -> None:
        """The negative half. Without it, a `conditional_transitions` reader that
        admitted every edge unconditionally would pass the test above."""

        def mutate(registry: dict) -> None:
            self._templatize_with_conditional_edge(registry, tier="reduced")

        reported = self._newly_reported(mutate)
        self.assertTrue(reported, "withholding the edge must change something")
        self.assertTrue(
            any("uninitialized -> active" in error for error in reported), reported
        )


if __name__ == "__main__":
    unittest.main()
