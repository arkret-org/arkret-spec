"""Executable long-text media-type and closed-attachment contract checks."""

import copy
import json
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "spec/v1/artifacts/schemas"


class LongTextSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources = []
        for path in SCHEMAS.glob("*.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            resources.append((document["$id"], Resource.from_contents(document)))
        registry = Registry().with_resources(resources)
        cls.validator = Draft202012Validator(
            {"$ref": "https://arkret.org/v1/schemas/event-payload.schema.json#/$defs/content_block_long_text"},
            registry=registry,
        )
        prose = (ROOT / "spec/v1/zh/models/content-types.md").read_text(encoding="utf-8")
        section = prose.split("### 4.1.1 ", 1)[1].split("### 4.1.2 ", 1)[0]
        cls.examples = [json.loads(block) for block in re.findall(r"```json\n(.*?)\n```", section, re.S)]
        assert len(cls.examples) == 2

    def test_prose_examples_and_both_media_types_are_constructible(self):
        for example in self.examples:
            for media_type in ("text/plain", "text/markdown"):
                block = copy.deepcopy(example)
                block.get("attachment", block)["media_type"] = media_type
                with self.subTest(encrypted="attachment" in block, media_type=media_type):
                    self.validator.validate(block)

    def test_media_type_is_required_and_closed_in_both_branches(self):
        for example in self.examples:
            for invalid in (None, "text/html", "text/plain; charset=utf-8", "text/markdown; charset=utf-8", "markdown", "Text/Plain", 42):
                block = copy.deepcopy(example)
                carrier = block.get("attachment", block)
                carrier.pop("media_type")
                if invalid is not None:
                    carrier["media_type"] = invalid
                with self.subTest(encrypted="attachment" in block, invalid=invalid):
                    self.assertFalse(self.validator.is_valid(block))

    def test_legacy_format_is_rejected_even_when_consistent(self):
        for example in self.examples:
            for value in ("plain", "markdown", "prosemirror_json"):
                with self.subTest(encrypted="attachment" in example, format=value):
                    self.assertFalse(self.validator.is_valid({**example, "format": value}))

    def test_encrypted_metadata_has_one_carrier(self):
        example = next(block for block in self.examples if "attachment" in block)
        self.assertFalse(self.validator.is_valid({**example, "media_type": "text/plain"}))
        for member, value in (("segment_count", 3), ("epoch", 42), ("format", "plain")):
            block = copy.deepcopy(example)
            block["attachment"][member] = value
            with self.subTest(member=member):
                self.assertFalse(self.validator.is_valid(block))

    def test_fixture_covers_media_type_changes(self):
        fixture = json.loads((SCHEMAS.parent / "fixtures/long-text-content-fixture.json").read_text(encoding="utf-8"))
        for case in fixture["cases"]:
            generator = case["input"]["generator"]
            if generator["kind"] in ("long_text_plaintext_descriptor", "long_text_e2ee_descriptor"):
                self.assertEqual(generator["media_types"], ["text/plain", "text/markdown"])
                self.assertTrue({"media_type_missing", "media_type_unknown", "media_type_has_charset", "legacy_format"}.issubset(generator["mutations"]))


if __name__ == "__main__":
    unittest.main()
