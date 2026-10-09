"""Public current roots retain the registered reversible Realm gates."""
import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://arkret.org/v1/schemas/"


class TypedCurrentRootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        documents = [json.loads(path.read_text(encoding="utf-8")) for path in
                     (ROOT / "spec/v1/artifacts/schemas").glob("*.json")]
        registry = Registry().with_resources(
            (document["$id"], Resource.from_contents(document)) for document in documents)
        cls.current = Draft202012Validator(
            {"$ref": BASE + "typed-current-result.schema.json"}, registry=registry)

    def row(self, kind, field, value):
        return {
            "selector": {"kind": kind},
            "source_stream_ref": {"kind": "realm", "realm_id": "ak:realm:" + "A" * 44},
            "revision": {"commit_id": "ak:realm_commit:" + "B" * 44, "stream_position": 25},
            "value": {field: value},
        }

    def test_archive_restore_and_freeze_unfreeze_are_readable(self):
        for kind, field in [("realm_archive", "archived"), ("realm_freeze", "frozen")]:
            for value in [True, False]:
                with self.subTest(kind=kind, value=value):
                    self.current.validate(self.row(kind, field, value))

    def test_reversible_gate_values_remain_closed_and_boolean(self):
        for kind, field in [("realm_archive", "archived"), ("realm_freeze", "frozen")]:
            row = self.row(kind, field, True)
            for value in [{field: "true"}, {field: True, "undeclared_authority": True}]:
                with self.subTest(kind=kind, value=value):
                    self.assertFalse(self.current.is_valid({**row, "value": value}))

    def test_unknown_selector_and_source_fields_remain_rejected(self):
        row = self.row("realm_archive", "archived", True)
        unknown = copy.deepcopy(row)
        unknown["selector"]["kind"] = "unknown_realm_gate"
        self.assertFalse(self.current.is_valid(unknown))
        self.assertFalse(self.current.is_valid({**row, "unverified_source": True}))


if __name__ == "__main__":
    unittest.main()
