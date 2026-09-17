"""`ak.agent.provision` declares four writes, and each one has a reason.

`result_writes[]` is a kind's complete shared-face contract, so the interesting
failure for this kind is not a malformed row -- the ordinary contract lint
catches those -- it is a row set that quietly shrinks, or one member that
quietly becomes a plain field copy. Neither has a gate anywhere else: the lint
has no second list of a kind's writes to compare against, which is exactly why
`zh/models/realm-and-space.md` section 2.5.1 states the completeness rule as
prose rather than as a check.

So the propositions under test are the ones that a future edit could break
without any other gate noticing:

* all four registered families are present, and they are the four the prose
  enumerates -- `agent_provisioning`, `identity_accountability`,
  `agent_selector_claim`, `agent_pcr_genesis_declaration`;
* the selector target comes from the registered derivation and never from a
  field: `payload.agent_id` is a bare principal, and a bare principal as a
  selector target is the ambiguity `zh/models/strand-and-message.md` makes
  resolution fail closed on;
* that derivation is in the closed set the lint validates against, so the row
  cannot survive the set being reverted;
* the accountability row reads `not_before` from the envelope and pins
  `grant_status` to a literal, and projects no `expires_at` -- absence means
  non-expiring and `zh/models/actor.md` section 3.3.1 forbids both a JSON null
  and the server's receive time;
* the two DID-keyed subjects stay principal-scoped and Station-free.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.core import VALUE_PROJECTION_DERIVATIONS

CONTRACT_REGISTRY = ROOT / "spec" / "v1" / "artifacts" / "registry" / "contract-registry.json"
PROVISION = "ak.agent.provision"

EXPECTED_FAMILIES = [
    "agent_provisioning",
    "identity_accountability",
    "agent_selector_claim",
    "agent_pcr_genesis_declaration",
]


def load_writes() -> list[dict]:
    registry = json.loads(CONTRACT_REGISTRY.read_text(encoding="utf-8"))
    for row in registry["event_kind_registry"]["event_kinds"]:
        if row["event_kind"] == PROVISION:
            return row["result_writes"]
    raise AssertionError(f"{PROVISION} is not a registered Event kind")


def write_of(family: str) -> dict:
    for write in load_writes():
        if write["result_family"] == family:
            return write
    raise AssertionError(f"{PROVISION} no longer writes {family}")


def members(write: dict) -> dict[str, dict]:
    projection = write["result_projection"]["value_projection"]
    return {member["name"]: member for member in projection["members"]}


class AgentProvisionFourWritesTest(unittest.TestCase):
    # ---- the row set is complete -----------------------------------------

    def test_exactly_the_four_registered_families_in_prose_order(self) -> None:
        self.assertEqual([write["result_family"] for write in load_writes()], EXPECTED_FAMILIES)

    def test_every_row_declares_a_value_schema(self) -> None:
        for write in load_writes():
            with self.subTest(family=write["result_family"]):
                self.assertTrue(write.get("value_schema_ref"))

    def test_no_row_is_conditional(self) -> None:
        """All four are written in one reducer transaction and a partially
        completed state MUST NOT be observable, so none of them may be gated on
        a payload member being present."""
        for write in load_writes():
            with self.subTest(family=write["result_family"]):
                self.assertNotIn("condition", write)

    # ---- the selector target is derived, never copied ---------------------

    def test_the_selector_target_uses_the_registered_derivation(self) -> None:
        target = members(write_of("agent_selector_claim"))["subject_account_id"]
        self.assertEqual(target.get("derivation"), "agent_account_id_from_provision")
        self.assertNotIn("field", target)

    def test_that_derivation_is_in_the_closed_lint_set(self) -> None:
        self.assertIn("agent_account_id_from_provision", VALUE_PROJECTION_DERIVATIONS)

    def test_the_target_is_never_the_bare_payload_principal(self) -> None:
        """payload.agent_id is a DidCoreId. One principal on two Stations is two
        accounts, and resolution MUST fail closed on that ambiguity rather than
        deduplicate by principal, so a bind target is always a complete
        AccountId."""
        target = members(write_of("agent_selector_claim"))["subject_account_id"]
        self.assertNotEqual(target.get("field"), "payload.agent_id")

    # ---- the accountability row's derived values --------------------------

    def test_not_before_comes_from_the_envelope(self) -> None:
        row = members(write_of("identity_accountability"))
        self.assertEqual(row["not_before"].get("envelope_field"), "created_at")

    def test_grant_status_is_the_active_literal(self) -> None:
        row = members(write_of("identity_accountability"))
        self.assertEqual(row["grant_status"].get("literal"), "active")

    def test_expires_at_is_not_projected(self) -> None:
        self.assertNotIn("expires_at", members(write_of("identity_accountability")))

    def test_the_scope_member_is_normalized_and_not_a_field_copy(self) -> None:
        """This payload's scope is a bare const string and the standalone
        writer's MAY be a one-element array; both have to reach one value."""
        member = members(write_of("identity_accountability"))["accountability_scope"]
        self.assertEqual(
            member.get("normalized_string_set"),
            {"field": "payload.accountability_scope", "context": "ak.accountability_scope_set.v1"},
        )

    # ---- the subjects stay principal-scoped -------------------------------

    def test_the_provisioning_subject_is_the_agent_did_alone(self) -> None:
        selector = write_of("agent_provisioning")["result_selector"]
        self.assertEqual(selector, {"kind": "composite", "components": ["payload.agent_id"]})

    def test_the_selector_subject_carries_no_station(self) -> None:
        selector = write_of("agent_selector_claim")["result_selector"]
        self.assertEqual(
            selector,
            {
                "kind": "composite",
                "components": ["payload.controller_principal_id", "payload.agent_slug"],
            },
        )

    def test_the_declaration_subject_is_the_forward_declared_realm_id(self) -> None:
        selector = write_of("agent_pcr_genesis_declaration")["result_selector"]
        self.assertEqual(
            selector,
            {"kind": "composite", "components": ["payload.principal_control_realm_id"]},
        )

    def test_the_declaration_value_is_the_one_member_index(self) -> None:
        self.assertEqual(list(members(write_of("agent_pcr_genesis_declaration"))), ["agent_id"])


if __name__ == "__main__":
    unittest.main()
