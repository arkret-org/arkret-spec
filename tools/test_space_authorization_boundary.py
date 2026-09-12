"""Authorization selectors cannot inherit access through Space ancestry."""
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://arkret.org/v1/schemas/"


class SpaceAuthorizationBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        documents = [json.loads(p.read_text(encoding="utf-8")) for p in
                     (ROOT / "spec/v1/artifacts/schemas").glob("*.json")]
        cls.registry = Registry().with_resources(
            (doc["$id"], Resource.from_contents(doc)) for doc in documents)
        cls.selector = Draft202012Validator(
            {"$ref": BASE + "resource-selector.schema.json"}, registry=cls.registry)
        cls.grant_resources = Draft202012Validator(
            {"$ref": BASE + "capability-grant.schema.json#/properties/resources"},
            registry=cls.registry)

    def target(self):
        return {"kind": "space", "realm_id": "ak:realm:" + "A" * 44,
                "space_id": "ak:space:" + "B" * 44}

    def test_explicit_space_and_realm_scope_remain_valid(self):
        for selector in [self.target(), {**self.target(), "match_scope": "exact"},
                         {"kind": "space", "realm_id": self.target()["realm_id"],
                          "match_scope": "realm_wide"}]:
            with self.subTest(selector=selector):
                self.selector.validate(selector)
                self.grant_resources.validate([selector])

    def test_hierarchy_selector_invalidates_grant_resources(self):
        for scope in ["children", "subtree"]:
            with self.subTest(scope=scope):
                invalid = {**self.target(), "match_scope": scope}
                self.assertFalse(self.selector.is_valid(invalid))
                self.assertFalse(self.grant_resources.is_valid([self.target(), invalid]))

    def test_ancestry_cannot_be_supplied_as_an_authorization_field(self):
        for field in ["parent_space_id", "creation_parent_space_id", "ancestor_space_ids"]:
            with self.subTest(field=field):
                invalid = {**self.target(), field: self.target()["space_id"]}
                self.assertFalse(self.selector.is_valid(invalid))


if __name__ == "__main__":
    unittest.main()
