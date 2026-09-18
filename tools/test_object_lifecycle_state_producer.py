"""The object `state` axis has exactly one producer after create, and it is the kind.

`models/common-fields.md` section 5.2 is the normative map: `ak.<kind>.archive`
-> archived, `ak.<kind>.restore` -> active, `ak.<kind>.tombstone` -> tombstoned,
with the legal prior states and the one terminal marked. Before the 2200
landing that map had no machine counterpart at all. `state` sits in
`universal_forbidden_patch_paths` as `dedicated_event_owned`, so no patch may
reach it; `object_initial_state` only makes the create value; and every one of
the dedicated lifecycle kinds was a `reducer_input` row declaring
`result_writes: []`. The terminal state of every object with a lifecycle was
therefore unreachable by any registered write -- the axis was owned by kinds
that wrote nothing.

`object_lifecycle_state` is that producer. The tests here pin the three things
that make it a closed rule rather than a new author permission:

* the registry map and the prose map are the same map, in both directions;
* the value is never carried by the author, so the payload cannot name a target
  state and no `allowed_paths` may reach the member;
* the two members of the state axis are produced together, since a state that
  moved without a `state_changed_at` is indistinguishable from one that did not.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SPEC = ROOT / "spec" / "v1"
ARTIFACTS = SPEC / "artifacts"
COMMON_FIELDS = SPEC / "zh" / "models" / "common-fields.md"

LIFECYCLE_DERIVATION = "object_lifecycle_state"
TRANSITION_TIME_DERIVATION = "object_state_transition_time"

# section 5.2, read the way an implementer reads it: the kind's last segment
# determines the value, and nothing else does.
PROSE_MAP = {"archive": "archived", "restore": "active", "tombstone": "tombstoned"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ObjectLifecycleStateProducerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = _load(ARTIFACTS / "registry" / "contract-registry.json")
        cls.kinds = cls.registry["event_kind_registry"]["event_kinds"]
        cls.rmp = _load(ARTIFACTS / "registry" / "reducer-managed-path-registry.json")
        cls.payloads = _load(ARTIFACTS / "schemas" / "event-payload.schema.json")
        cls.prose = COMMON_FIELDS.read_text(encoding="utf-8")
        cls.producers = {
            row["event_kind"]: write
            for row in cls.kinds
            for write in row.get("result_writes") or ()
            for member in write.get("derived_members") or ()
            if member["derivation"] == LIFECYCLE_DERIVATION
        }

    # ---- the map ---------------------------------------------------------

    def test_the_prose_table_is_the_three_shapes(self) -> None:
        table = re.findall(
            r"^\| `ak\.<kind>\.([a-z]+)` \| `([a-z]+)` \| ([^|]+)\| (\S+) \|$",
            self.prose,
            flags=re.MULTILINE,
        )
        self.assertEqual({verb: state for verb, state, _, _ in table}, PROSE_MAP)
        terminal = {verb: flag for verb, _, _, flag in table}
        self.assertEqual(terminal["tombstone"], "**是**")
        self.assertEqual(terminal["archive"], "否")
        self.assertEqual(terminal["restore"], "否")

    def test_every_producer_is_one_of_the_three_shapes(self) -> None:
        """No fourth verb, and no kind smuggling the derivation onto a plain update."""
        for kind in self.producers:
            self.assertIn(kind.rsplit(".", 1)[-1], PROSE_MAP, kind)

    def test_every_dedicated_lifecycle_kind_of_a_stateful_object_produces_it(self) -> None:
        """The gap this landing closed: these kinds owned the axis and wrote nothing.

        A stateful object is one whose value schema declares `state`. If such an
        object has an `ak.<kind>.<verb>` Event for one of the three verbs, that
        Event is by section 5.2 the only carrier of the value, so it must
        produce it.
        """
        stateful = set()
        for row in self.rmp["objects"]:
            ref = row.get("value_schema_ref")
            if not ref or "#" in ref:
                continue
            schema = _load(ARTIFACTS / ref)
            if "state" in schema.get("properties", {}):
                stateful.add(row["object_kind"])
        self.assertTrue(stateful, "no object row declares a value schema with state")

        expected = {
            row["event_kind"]
            for row in self.kinds
            for parts in [row["event_kind"].split(".")]
            if len(parts) == 3 and parts[1] in stateful and parts[2] in PROSE_MAP
        }
        self.assertEqual(sorted(self.producers), sorted(expected))

    # ---- the value is never authored -------------------------------------

    def test_the_payload_cannot_name_a_target_state(self) -> None:
        """`target_state` is gone from the generic lifecycle payload.

        It survives only where the kind genuinely cannot determine the terminal
        -- an FSM-shaped lifecycle -- and in v1 that is Invite alone. A generic
        archive payload carrying a target state hands the author the axis the
        kind already decides.
        """
        payload = self.payloads["$defs"]["object_lifecycle_payload"]
        self.assertNotIn("target_state", payload["properties"])
        self.assertNotIn("state", payload["properties"])

    def test_no_write_lets_a_patch_reach_the_member(self) -> None:
        universal = {
            entry["path"]: entry for entry in self.rmp["universal_forbidden_patch_paths"]
        }
        self.assertEqual(universal["state"]["basis"], "dedicated_event_owned")
        exempt = {
            entry["owner"]
            for row in self.rmp["objects"]
            for entry in row.get("universal_exemptions") or ()
            if entry["path"] == "state" and entry["owner_kind"] == "event_kind"
        }
        self.assertEqual(exempt, {"ak.view.update"})
        for row in self.kinds:
            if row["event_kind"] in exempt:
                continue
            for write in row.get("result_writes") or ():
                allowed = write.get("result_projection", {}).get("allowed_paths")
                if allowed is None:
                    continue
                self.assertNotIn(
                    "state", allowed, "%s patches state" % row["event_kind"]
                )

    def test_a_lifecycle_write_patches_nothing_at_all(self) -> None:
        """It moves one axis. An `allowed_paths` here would make one Event both
        the state carrier and a content editor, and the prior-state guard of
        section 5.2 only covers the state."""
        for kind, write in self.producers.items():
            projection = write["result_projection"]
            self.assertEqual(projection["kind"], "apply_patch", kind)
            self.assertEqual(projection["allowed_paths"], [], kind)

    # ---- the axis moves as one -------------------------------------------

    def test_the_two_members_of_the_axis_are_produced_together(self) -> None:
        for kind, write in self.producers.items():
            derived = {member["name"] for member in write["derived_members"]}
            self.assertIn("state", derived, kind)
            self.assertIn("state_changed_at", derived, kind)
            transition = next(
                member
                for member in write["derived_members"]
                if member["name"] == "state_changed_at"
            )
            self.assertEqual(transition["derivation"], TRANSITION_TIME_DERIVATION, kind)
        self.assertIn("两者 MUST 在同一次写入内一起产出", self.prose)

    def test_a_lifecycle_write_never_retains_the_state_it_moves(self) -> None:
        for kind, write in self.producers.items():
            retained = write.get("retained_members") or []
            self.assertNotIn("state", retained, kind)
            self.assertNotIn("state_changed_at", retained, kind)

    # ---- the exception stays a single exception --------------------------

    def test_view_is_still_the_only_object_without_a_dedicated_lifecycle_kind(self) -> None:
        exemptions = [
            (row["object_kind"], entry)
            for row in self.rmp["objects"]
            for entry in row.get("universal_exemptions") or ()
        ]
        self.assertEqual([kind for kind, _ in exemptions], ["view"])
        entry = exemptions[0][1]
        self.assertEqual(entry["path"], "state")
        self.assertEqual(entry["owner"], "ak.view.update")
        self.assertIn("no separate tombstone event kind", entry["justification"])

    def test_realm_is_excluded_because_it_has_no_materialized_state(self) -> None:
        """`ak.realm.archive` writes a facet, not an object lifecycle.

        Registering it with this derivation would require a `state` member the
        Realm schema does not have, and the facet it really writes is a
        different family with a different value.
        """
        self.assertNotIn("ak.realm.archive", self.producers)
        self.assertNotIn("ak.realm.restore", self.producers)
        self.assertIn("Realm 没有 materialized `state` 字段", self.prose)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
