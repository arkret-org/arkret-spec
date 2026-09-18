"""The two namespaces `ak.policy.action` writes, and why they stay apart.

`models/governance-objects.md` section 3.4 registers one typed current result,
`policy_action`, behind a payload whose top level is a closed XOR over
`policy_id` and `action_id`. That XOR is TWO subject spaces, not one coalesced
subject, and v1's selector grammar has no `coalesce` kind and no literal
constant inside a `composite` -- so the only way to register it is two writes
under complementary conditions with the branch tag carried explicitly in the
result schema. Each of those pieces is load-bearing and none of them is
implied by the generic write-contract gates: `check_result_write_contracts`
closes the per-row grammar, `check_result_write_target_uniqueness` admits the
pair because the conditions are disjoint, and neither one can tell whether the
branches still name different things.

These tests read the live artifacts and state what would be lost. They are also
the record that `ak.policy.rule` was deleted rather than left standing: it
carried no `policy_id`, so its `rule_id` resolved to nothing, and editing a rule
submits the whole authorized Policy document through `ak.policy.set`.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate
from tools.artifact_lint.foundation import complementary_conditions

ARTIFACTS = gate.ARTIFACTS
KIND = "ak.policy.action"
FAMILY = "policy_action"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class PolicyActionFamilyContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = _load(gate.EVENT_KIND_REGISTRY)
        cls.results = _load(ARTIFACTS / "schemas" / "typed-current-result.schema.json")
        cls.payloads = _load(ARTIFACTS / "schemas" / "event-payload.schema.json")
        cls.row = next(
            row
            for row in cls.registry["event_kinds"]
            if row["event_kind"] == KIND
        )

    # ---- the pair -------------------------------------------------------

    def test_the_kind_registers_exactly_the_two_branches(self) -> None:
        writes = self.row["result_writes"]
        self.assertEqual([write["result_family"] for write in writes], [FAMILY] * 2)

    def test_the_branches_are_disjoint_by_construction(self) -> None:
        """Not merely different conditions -- provably exclusive ones.

        `check_result_write_target_uniqueness` admits two writes on one family
        only for an atomic keyed-set remove-then-add or a pair
        `complementary_conditions` can prove can never both fire. This pair is
        the second kind, and a condition pair that merely looks different would
        be two writes racing on one result.
        """
        left, right = (write["condition"] for write in self.row["result_writes"])
        self.assertTrue(
            complementary_conditions(left, right),
            f"{left} and {right} are not provably disjoint",
        )
        self.assertEqual({left["field"], right["field"]}, {"payload.policy_id"})

    def test_the_policy_ref_key_includes_the_action(self) -> None:
        """One Policy document may configure several actions.

        Keying this branch on `policy_id` alone would make configuring a second
        action of the same document overwrite the first, silently and with every
        gate green: the row would still be grammatical, the schema would still
        validate, and the loss would only show up as a configuration that
        stopped existing.
        """
        write = next(
            write
            for write in self.row["result_writes"]
            if write["condition"]["kind"] == "field_present"
        )
        self.assertEqual(
            write["result_selector"]["components"],
            ["payload.policy_id", "payload.value.action"],
        )

    def test_the_realm_action_key_hangs_off_no_policy(self) -> None:
        write = next(
            write
            for write in self.row["result_writes"]
            if write["condition"]["kind"] == "field_absent"
        )
        self.assertEqual(write["result_selector"]["components"], ["payload.action_id"])

    def test_both_branches_replace_the_whole_value(self) -> None:
        for write in self.row["result_writes"]:
            self.assertEqual(write["result_projection"]["kind"], "set")
            self.assertEqual(write["result_projection"]["value"], {"field": "payload.value"})

    # ---- the tag --------------------------------------------------------

    def test_the_selector_carries_the_branch_tag(self) -> None:
        """Without the tag the two key spaces would be an untagged coalesce.

        `(policy_id, action)` and `(action_id)` have different arities today, so
        a reader might call the tag redundant. It is not: the tag is what makes
        the two spaces distinguishable as a matter of contract rather than as an
        accident of the members that happen to be registered.
        """
        selector = self.results["$defs"]["policy_action_result"]["properties"]["selector"]
        self.assertIn("branch", selector["required"])
        self.assertEqual(
            selector["properties"]["branch"]["enum"], ["policy_ref", "realm_action"]
        )
        self.assertFalse(selector["additionalProperties"])

    def test_neither_branch_admits_the_other_branch_members(self) -> None:
        selector = self.results["$defs"]["policy_action_result"]["properties"]["selector"]
        branches = {
            option["properties"]["branch"]["const"]: option
            for option in selector["oneOf"]
        }
        self.assertEqual(set(branches), {"policy_ref", "realm_action"})
        self.assertEqual(branches["policy_ref"]["required"], ["policy_id", "action"])
        self.assertEqual(branches["policy_ref"]["not"], {"required": ["action_id"]})
        self.assertEqual(branches["realm_action"]["required"], ["action_id"])
        self.assertEqual(
            branches["realm_action"]["not"],
            {"anyOf": [{"required": ["policy_id"]}, {"required": ["action"]}]},
        )

    def test_the_value_is_the_payload_value_verbatim(self) -> None:
        """A second copy of the closed value would be a second truth."""
        self.assertEqual(
            self.results["$defs"]["policy_action_value"]["$ref"],
            "./event-payload.schema.json#/$defs/policy_action_state_payload/properties/value",
        )

    # ---- the deletion ---------------------------------------------------

    def test_the_rule_kind_is_gone_everywhere(self) -> None:
        self.assertNotIn(
            "ak.policy.rule",
            [row["event_kind"] for row in self.registry["event_kinds"]],
        )
        self.assertNotIn("policy_rule_state_payload", self.payloads["$defs"])
        envelope = (ARTIFACTS / "schemas" / "event-envelope.schema.json").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("ak.policy.rule", envelope)

    def test_rule_id_stays_a_document_local_symbol(self) -> None:
        """The deletion did not delete rules -- it deleted a subject claim.

        `PolicyRule.rule_id` still exists inside `policy.schema.json`; what it
        never did was name a result, which is why one rule is not its own
        Event kind.
        """
        policy = _load(ARTIFACTS / "schemas" / "policy.schema.json")
        self.assertIn("rule_id", policy["$defs"]["policy_rule"]["properties"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
