"""Executable lifetime, graph-order and cache-dependency regressions."""

import copy
import itertools
import json
import re
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.grant_lineage import derive_lineage, moderation_dependency, run_case, window_covered


class GrantLineageTest(unittest.TestCase):
    def setUp(self):
        self.root = {"kind": "realm_root", "realm_id": "realm", "authority_event_ref": "genesis",
                     "authority_generation": "0"}
        self.actor = {"kind": "account", "account_id": {"principal_id": "alice", "station_id": "station"}}
        self.parent = {"realm_id": "realm", "subject": self.actor, "current": True,
                       "created_position": 2, "authority_depth": 1, "authority_root_ref": self.root}

    def test_parent_order_and_depth_are_checked_without_searching_a_graph(self):
        result = derive_lineage([self.parent], realm_id="realm", issuer=self.actor,
                                current_root=self.root, child_position=3)
        self.assertEqual(result, {"authority_depth": 2, "authority_root_ref": self.root})
        for member, value in (("created_position", 3), ("authority_depth", 4),
                              ("current", False), ("terminal", True)):
            parent = dict(self.parent, **{member: value})
            with self.subTest(member=member), self.assertRaises(ValueError):
                derive_lineage([parent], realm_id="realm", issuer=self.actor,
                               current_root=self.root, child_position=3)

    def test_full_actor_and_current_root_cannot_be_substituted(self):
        for member in ("subject", "authority_root_ref", "realm_id"):
            parent = copy.deepcopy(self.parent)
            if member == "subject":
                parent[member]["account_id"]["station_id"] = "other"
            elif member == "authority_root_ref":
                parent[member]["authority_generation"] = "1"
            else:
                parent[member] = "other-realm"
            with self.subTest(member=member), self.assertRaises(ValueError):
                derive_lineage([parent], realm_id="realm", issuer=self.actor,
                               current_root=self.root, child_position=3)

    def test_multi_parent_has_one_root_and_maximum_static_depth(self):
        parents = [self.parent, dict(self.parent, created_position=3, authority_depth=2)]
        result = derive_lineage(parents, realm_id="realm", issuer=self.actor,
                                current_root=self.root, child_position=4)
        self.assertEqual(result["authority_depth"], 3)
        self.assertEqual(result["authority_root_ref"], self.root)
        self.assertNotIn("authority_root_refs", result)

    def test_root_can_make_a_new_finite_approval_after_the_first_day(self):
        source = {"rights": [["broadcast", "x"]], "windows": [[None, None]]}
        for now in (0, 86400001, 864000000):
            self.assertTrue(window_covered("broadcast", "x", [now, now + 1000], [source],
                                           finite_required=True, committed_at=now))
            self.assertFalse(window_covered("broadcast", "x", [now, now + 86400001], [source],
                                            finite_required=True, committed_at=now))

    def test_finite_parent_is_never_refreshed(self):
        source = {"rights": [["write", "x"]], "windows": [[0, 100]]}
        self.assertTrue(window_covered("write", "x", [10, 100], [source], finite_required=True, committed_at=10))
        self.assertFalse(window_covered("write", "x", [10, 101], [source], finite_required=True, committed_at=10))

    def test_disjoint_windows_and_resource_cross_products_do_not_expand_authority(self):
        source = {"rights": [["write", "x"]], "windows": [[0, 10], [20, 30]]}
        self.assertFalse(window_covered("write", "x", [5, 25], [source], finite_required=True, committed_at=5))
        mixed = [{"rights": [["read", "x"]], "windows": [[0, 100]]},
                 {"rights": [["write", "y"]], "windows": [[0, 100]]}]
        self.assertFalse(window_covered("write", "x", [5, 25], mixed, finite_required=True, committed_at=5))

    def test_true_union_coverage_matches_pointwise_integer_oracle(self):
        intervals = list(itertools.combinations(range(5), 2))
        for windows in itertools.combinations(intervals, 2):
            source = {"rights": [["write", "x"]], "windows": windows}
            for start, end in intervals:
                expected = all(any(lo <= point < hi for lo, hi in windows) for point in range(start, end))
                self.assertEqual(window_covered("write", "x", [start, end], [source],
                                                finite_required=True, committed_at=0), expected)

    def test_unrestricted_chat_is_not_forced_to_renew(self):
        source = {"rights": [["chat", "x"]], "windows": [[None, None]]}
        self.assertTrue(window_covered("chat", "x", [None, None], [source], finite_required=False, committed_at=0))
        self.assertFalse(window_covered("chat", "x", [None, None], [source], finite_required=True, committed_at=0))

    def test_required_deadline_overflow_fails_closed(self):
        source = {"rights": [["write", "x"]], "windows": [[None, None]]}
        self.assertFalse(window_covered("write", "x", [0, 10], [source], finite_required=True,
                                        committed_at=253402300799999))

    def test_cache_dependency_comes_from_semantics_not_a_producer_boolean(self):
        self.assertTrue(moderation_dependency(["ak.moderation.decision"]))
        self.assertTrue(moderation_dependency([], ["moderation_state"]))
        self.assertTrue(moderation_dependency([], (), ["moderation_state"]))
        self.assertFalse(moderation_dependency(["ak.message.create"]))
        with self.assertRaises(ValueError):
            moderation_dependency([], known=False)

    def test_registered_fixture_cases_execute(self):
        path = ROOT / "spec/v1/artifacts/fixtures/grant-lineage-lifetime-fixture.json"
        fixture = json.loads(path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(fixture["cases"]), 12)
        for case in fixture["cases"]:
            with self.subTest(case=case["name"]):
                self.assertEqual(run_case(case), case["expected"])

    def test_wire_schema_uses_single_root_and_rejects_producer_hint(self):
        schemas = ROOT / "spec/v1/artifacts/schemas"
        documents = [json.loads(path.read_text(encoding="utf-8")) for path in schemas.glob("*.schema.json")]
        registry = Registry().with_resources((d["$id"], Resource.from_contents(d)) for d in documents if "$id" in d)
        grant = json.loads((schemas / "capability-grant.schema.json").read_text(encoding="utf-8"))
        self.assertIn("authority_root_ref", grant["required"])
        self.assertNotIn("authority_root_refs", grant["properties"])
        self.assertNotIn("depends_on_moderation_state", json.dumps(grant))
        constraint = json.loads((schemas / "grant-constraint.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(constraint, registry=registry)
        ordinary = {"constraint_kind": "temporal", "effect": "allow", "expires_at": "2026-11-14T23:00:00.000Z"}
        self.assertTrue(validator.is_valid(ordinary))
        self.assertFalse(validator.is_valid(dict(ordinary, depends_on_moderation_state=True)))

    def test_materialized_owned_root_cannot_be_relabelled_as_realm_control(self):
        schemas = ROOT / "spec/v1/artifacts/schemas"
        documents = [json.loads(path.read_text(encoding="utf-8")) for path in schemas.glob("*.schema.json")]
        registry = Registry().with_resources((d["$id"], Resource.from_contents(d)) for d in documents if "$id" in d)
        schema = json.loads((schemas / "capability-grant.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, registry=registry)
        prose = (ROOT / "spec/v1/zh/authz/capabilities.md").read_text(encoding="utf-8")
        sample = json.loads(re.search(r"```json schema=schemas/capability-grant.schema.json\n(.*?)\n```", prose, re.S)[1])
        validator.validate(sample)
        owned = {"kind": "owned_agent", "realm_id": sample["realm_id"],
                 "controller_account_id": sample["issuer_id"]["account_id"],
                 "controller_join_event_id": sample["issuer_authority_refs"][0]["authority_event_ref"],
                 "agent_join_event_id": sample["issuer_authority_refs"][0]["authority_event_ref"]}
        ordinary_root = copy.deepcopy(sample["authority_root_ref"])
        sample["issuer_authority_refs"] = [owned]
        sample["authority_root_ref"] = owned
        sample["constraints"].append({"constraint_kind": "authority_control", "effect": "allow",
                                      "max_authority_depth": 0, "authority_regrant_allowed": False})
        validator.validate(sample)
        self.assertFalse(validator.is_valid(dict(sample, authority_root_ref=ordinary_root)))
        self.assertFalse(validator.is_valid(dict(sample, authority_depth=2)))


if __name__ == "__main__":
    unittest.main()
