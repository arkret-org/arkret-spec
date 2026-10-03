"""The `capability_grant` family must have exactly its three local writers.

`zh/authz/capabilities.md` section 12.1 says a Grant's closed current result
carries a status, and section 10.4 says two different authorities can close a
Grant: `ak.capability.revoke` under issuer or root-controller authority, and
`ak.capability.relinquish` under the target subject's own signature, which MUST
NOT require `ak.capability.revoke`. Neither Event kind declared a
`result_writes[]` row, so nothing in the registry could ever move a projected
Grant out of `active`, and the value schema had no slot to move it into --
`revoked_at` alone cannot say which of the two authorities closed it.

Each test states one proposition about the closed lifecycle.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate
from tools.artifact_lint.core import CELL_WRITE_DERIVATIONS

REGISTRY = ROOT / "spec/v1/artifacts/registry/contract-registry.json"
SCHEMAS = ROOT / "spec/v1/artifacts/schemas"

FAMILY = "capability_grant"
TERMINAL_STATUSES = ("revoked", "relinquished")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def writes_by_kind() -> dict[str, list[dict]]:
    registry = load(REGISTRY)
    found: dict[str, list[dict]] = {}
    for row in registry["event_kind_registry"]["event_kinds"]:
        writes = [
            write
            for write in (row.get("result_writes") or ())
            if write["result_family"] == FAMILY
        ]
        if writes:
            found[row["event_kind"]] = writes
    return found


class CapabilityGrantLifecycleTest(unittest.TestCase):
    def test_owner_can_grant_only_the_exact_native_bridge_error_exception(self) -> None:
        from tools.artifact_pipeline import capability_action_derivations

        registry = load(REGISTRY)
        actions = {
            row["action"]: row
            for row in registry["capability_action_registry"]["actions"]
        }
        owner = actions["ak.realm.owner"]
        derived = capability_action_derivations(registry)["ak.realm.owner"]
        self.assertIn("ak.applet.bridge_error", owner["grant_authority_rule"]["include_actions"])
        self.assertIn("ak.applet.bridge_error", derived["grant_authority_actions"])
        self.assertNotIn("ak.applet.bridge_error", derived["target_event_kinds"])
        for action, row in actions.items():
            if row.get("profile") == "ak.profile.applet_bridge.v1":
                with self.subTest(action=action):
                    self.assertEqual(
                        action in derived["grant_authority_actions"],
                        action == "ak.applet.bridge_error",
                    )
        bridge_error = actions["ak.applet.bridge_error"]
        self.assertEqual(bridge_error["required_constraints"], ["applet_id", "registration_epoch"])
        self.assertIn("active_applet_registration_exact", bridge_error["required_evaluator_checks"])

    def test_the_family_has_exactly_its_three_local_writers(self) -> None:
        self.assertEqual(
            sorted(writes_by_kind()),
            [
                "ak.capability.grant",
                "ak.capability.relinquish",
                "ak.capability.revoke",
            ],
        )

    def test_the_value_schema_carries_the_three_registered_statuses(self) -> None:
        grant = load(SCHEMAS / "capability-grant.schema.json")
        status = grant["properties"]["status"]
        self.assertEqual(status["enum"], ["active", "revoked", "relinquished"])
        for member in ("status", "authority_depth", "authority_root_refs"):
            with self.subTest(member=member):
                self.assertIn(member, grant["required"])

    def test_an_author_cannot_declare_the_status(self) -> None:
        """Section 3.0.1: the genesis body is closed and reducer-derived members
        are absent from it, so a producer-supplied status is a schema violation
        rather than a value anyone has to decide whether to trust."""
        body = load(SCHEMAS / "event-payload.schema.json")["$defs"][
            "capability_grant_payload"
        ]["properties"]["grant"]
        self.assertFalse(body["additionalProperties"])
        for member in ("status", "authority_depth", "authority_root_refs"):
            with self.subTest(member=member):
                self.assertNotIn(member, body["properties"])

    def test_authority_refs_are_semantic_lineage_not_client_selected_state(self) -> None:
        grant = load(SCHEMAS / "capability-grant.schema.json")
        alternatives = grant["properties"]["issuer_authority_refs"]["items"]["oneOf"]
        by_kind = {
            alternative["properties"]["kind"]["const"]: alternative
            for alternative in alternatives
        }
        self.assertEqual(set(by_kind), {"grant", "realm_root"})
        forbidden = {
            "expected_revision",
            "auth_state_digest",
            "governance_station_id",
            "basis",
        }
        for kind, alternative in by_kind.items():
            with self.subTest(kind=kind):
                self.assertFalse(alternative["additionalProperties"])
                self.assertEqual(forbidden & set(alternative["properties"]), set())

    def test_cross_realm_automatic_derivation_is_absent(self) -> None:
        registry = load(REGISTRY)
        payloads = load(SCHEMAS / "event-payload.schema.json")["$defs"]
        kinds = {
            row["event_kind"]
            for row in registry["event_kind_registry"]["event_kinds"]
        }
        actions = {
            row["action"]
            for row in registry["capability_action_registry"]["actions"]
        }
        self.assertNotIn("ak.capability.derived", kinds)
        self.assertNotIn("ak.capability.derived", actions)
        self.assertNotIn("capability_derived_payload", payloads)

    def test_automatic_realm_inheritance_cluster_is_absent(self) -> None:
        registry = load(REGISTRY)
        payloads = load(SCHEMAS / "event-payload.schema.json")["$defs"]
        typed = load(SCHEMAS / "typed-current-result.schema.json")["$defs"]
        link_schema = load(SCHEMAS / "realm-link-operations.schema.json")
        event_kinds = {
            row["event_kind"]
            for row in registry["event_kind_registry"]["event_kinds"]
        }
        operation_ids = {
            row["operation_id"]
            for row in registry["operation_registry"]["operations"]
        }
        result_kinds = {
            row["result_kind"]
            for row in registry["current_result_registry"]["result_kinds"]
        }
        core_link_kinds = link_schema["$defs"]["link_kind"]["anyOf"][0]["enum"]

        self.assertNotIn("ak.realm.inheritance_policy", event_kinds)
        self.assertNotIn("realm_inheritance_policy_payload", payloads)
        self.assertNotIn("realm_inheritance_policy_result", typed)
        self.assertNotIn("realm_inheritance_policy", result_kinds)
        self.assertNotIn(
            "ak.self.realm_link.read.effective_policy.v1", operation_ids
        )
        self.assertNotIn("realm_effective_policy_outcome", link_schema["$defs"])
        self.assertNotIn("inherits_policy_from", core_link_kinds)

        read_receipt = payloads["read_receipt_policy_payload"]["properties"]
        self.assertNotIn("child_privacy_tightening_against_required", read_receipt)
        errors = load(ROOT / "spec/v1/artifacts/registry/error-code-registry.json")
        self.assertNotIn(
            "read_receipt_compliance_floor_violated",
            {row["code"] for row in errors["codes"]},
        )

    def test_parent_membership_is_co_governed_and_wire_shape_stays_closed(self) -> None:
        payloads = load(SCHEMAS / "event-payload.schema.json")["$defs"]
        gates = payloads["join_policy_gate"]["oneOf"]
        parent = next(
            branch
            for branch in gates
            if branch["allOf"][1]["properties"]["kind"].get("const")
            == "parent_membership"
        )["allOf"][1]
        self.assertEqual(
            set(parent["required"]),
            {"kind", "membership_source_realm_ids", "require_min_membership"},
        )
        self.assertEqual(
            set(parent["properties"]),
            {"kind", "membership_source_realm_ids", "require_min_membership"},
        )
        description = parent["properties"]["kind"]["description"]
        self.assertIn("authority-tenure service_id", description)
        self.assertIn("generation numbers are not compared across Realms", description)
        self.assertIn("at least one source must be joined", description)

        prose = (ROOT / "spec/v1/zh/governance/join-policy.md").read_text(
            encoding="utf-8"
        )
        for required in (
            'link_kind="join_gate_from"',
            "同一内部事务 cut",
            "不能用 saga 补偿",
            "不级联撤销",
        ):
            with self.subTest(required=required):
                self.assertIn(required, prose)

    def test_authority_generation_is_reset_not_station_tenure(self) -> None:
        typed = load(SCHEMAS / "typed-current-result.schema.json")
        description = typed["$defs"]["realm_authority_root_value"]["properties"][
            "authority_generation"
        ]["description"]
        self.assertIn("ak.realm.authority.reset", description)
        self.assertIn("handoff preserve", description)

    def test_every_writer_derives_the_status(self) -> None:
        """One field, one mechanism. A write that set it any other way would be a
        second definition of what `active` means."""
        self.assertIn("capability_status", CELL_WRITE_DERIVATIONS)
        for kind, writes in writes_by_kind().items():
            with self.subTest(kind=kind):
                derived = [
                    member["derivation"] for member in writes[0].get("derived_members") or ()
                ]
                self.assertIn("capability_status", derived)

    def test_the_station_sidecar_derivation_is_gone(self) -> None:
        """Section 3.0.1 says the reducer no longer copies or derives
        `issuer_station_id`; the account's routing authority is closed inside
        ActorId. It was a derivation no registry row and no prose named."""
        self.assertNotIn("capability_issuer_station_id", CELL_WRITE_DERIVATIONS)

    def test_the_two_closes_are_told_apart_by_which_pair_they_write(self) -> None:
        found = writes_by_kind()
        revoke = found["ak.capability.revoke"][0]["result_projection"]
        relinquish = found["ak.capability.relinquish"][0]["result_projection"]
        self.assertEqual(revoke["kind"], "merge")
        self.assertEqual(relinquish["kind"], "merge")
        revoke_members = {
            member["name"] for member in revoke["value_projection"]["members"]
        }
        relinquish_members = {
            member["name"] for member in relinquish["value_projection"]["members"]
        }
        self.assertEqual(revoke_members, {"revoked_by", "revoked_at"})
        self.assertEqual(relinquish_members, {"updated_by", "updated_at"})
        self.assertEqual(revoke_members & relinquish_members, set())

    def test_a_close_reads_its_actor_and_time_from_the_signed_envelope(self) -> None:
        """The authority that closed a Grant is the Event's signer, so a payload
        field there would let the producer name someone else as the closer."""
        found = writes_by_kind()
        for kind in ("ak.capability.revoke", "ak.capability.relinquish"):
            with self.subTest(kind=kind):
                members = found[kind][0]["result_projection"]["value_projection"][
                    "members"
                ]
                self.assertEqual(
                    [member.get("envelope_field") for member in members],
                    ["actor_id", "created_at"],
                )

    def test_a_close_merges_rather_than_overwrites(self) -> None:
        """A `set` would drop the immutable grant body that section 12.1 requires
        compaction to keep."""
        found = writes_by_kind()
        for kind in ("ak.capability.revoke", "ak.capability.relinquish"):
            with self.subTest(kind=kind):
                self.assertEqual(found[kind][0]["result_projection"]["kind"], "merge")

    def test_only_genesis_retypes_its_own_event_id(self) -> None:
        """`ak.capability.grant` is the one kind whose Event id becomes the
        GrantId; the other two name an existing grant_id, so a fieldless
        subject there would silently address the wrong object."""
        found = writes_by_kind()
        self.assertEqual(
            found["ak.capability.grant"][0]["result_selector"], {"kind": "id:grant"}
        )
        for kind in (
            "ak.capability.revoke",
            "ak.capability.relinquish",
        ):
            with self.subTest(kind=kind):
                self.assertEqual(
                    found[kind][0]["result_selector"],
                    {"kind": "id:grant", "field": "payload.grant_id"},
                )

    def test_every_writer_selector_passes_the_registered_grammar(self) -> None:
        registry = load(REGISTRY)
        rows = {
            row["event_kind"]: row for row in registry["event_kind_registry"]["event_kinds"]
        }
        lint = gate.Lint()
        for kind, writes in writes_by_kind().items():
            gate._check_result_selector(
                lint,
                f"{kind}.result_writes[0].result_selector",
                writes[0]["result_selector"],
                rows[kind].get("id_source"),
            )
        self.assertEqual(lint.errors, [])

    def test_every_writer_names_the_grant_body_as_its_value(self) -> None:
        for kind, writes in writes_by_kind().items():
            with self.subTest(kind=kind):
                self.assertEqual(
                    writes[0]["value_schema_ref"],
                    "schemas/capability-grant.schema.json",
                )

    def test_the_terminal_statuses_stay_distinguishable(self) -> None:
        """Section 10.4 gives revoke and relinquish different authorities, so
        collapsing them into one terminal value would erase which authority
        closed the Grant."""
        grant = load(SCHEMAS / "capability-grant.schema.json")
        for status in TERMINAL_STATUSES:
            self.assertIn(status, grant["properties"]["status"]["enum"])


if __name__ == "__main__":
    unittest.main()
