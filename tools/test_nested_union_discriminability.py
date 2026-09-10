"""Required nested selectors can discriminate closed self results without duplicate tags."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.artifact_lint import fixtures
from tools.artifact_lint.core import Lint


class NestedUnionTests(unittest.TestCase):
    def branches(self):
        return [{"type": "object", "required": ["selector"], "properties": {
            "selector": {"type": "object", "required": ["sender_kind"], "properties": {
                "sender_kind": {"const": kind}}, "additionalProperties": False}
        }, "additionalProperties": False} for kind in ("agent", "account_device")]

    def errors(self, branches):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "schemas").mkdir()
            (root / "schemas/probe.schema.json").write_text(json.dumps({
                "$defs": {"result": {"oneOf": branches}}
            }), encoding="utf-8")
            lint = Lint()
            with patch.object(fixtures, "ARTIFACTS", root):
                fixtures.check_one_of_branch_discriminability(lint)
            return lint.errors

    def test_required_nested_constants_are_disjoint(self):
        self.assertFalse(self.errors(self.branches()))

    def test_optional_selector_cannot_discriminate(self):
        branches = self.branches()
        for branch in branches:
            branch["required"] = []
        # Add refs so the lint treats these as a DTO union rather than a field constraint.
        for branch in branches:
            branch["required"] = ["key"]
            branch["properties"]["key"] = {"type": "string"}
        self.assertTrue(self.errors(branches))

    def test_optional_nested_field_cannot_discriminate(self):
        branches = self.branches()
        for branch in branches:
            branch["properties"]["selector"]["required"] = []
        self.assertTrue(self.errors(branches))

    def test_mixed_values_are_not_a_single_discriminator(self):
        branches = self.branches()
        branches[1]["properties"]["selector"]["properties"]["sender_kind"] = {
            "enum": ["agent", "account_device"]}
        self.assertTrue(self.errors(branches))

    def test_one_overlapping_pair_rejects_whole_union(self):
        branches = self.branches()
        branches.append(copy.deepcopy(branches[0]))
        self.assertTrue(self.errors(branches))


if __name__ == "__main__":
    unittest.main()
