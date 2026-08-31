"""Constructibility and named-rejection checks for private transfer and Views."""

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SCHEMAS = Path(__file__).resolve().parents[1] / "spec/v1/artifacts/schemas"


class PrivateTransferAndViewSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resources = []
        for path in SCHEMAS.glob("*.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            resources.append((document["$id"], Resource.from_contents(document)))
        cls.registry = Registry().with_resources(resources)

    def validator(self, schema, definition):
        return Draft202012Validator(
            {"$ref": f"https://arkret.org/v1/schemas/{schema}.schema.json#/$defs/{definition}"},
            registry=self.registry,
        )

    def descriptor(self):
        return {
            "scheme": "ak.blob.stream_aead.v1",
            "aead_profile": "ak.aead.xchacha20_poly1305.v1",
            "nonce_prefix": "A" * 26,
            "segment_bytes": 1024,
            "aad": {
                "schema": "ak.schema.file_transfer.v1", "purpose": "file_transfer",
                "transfer_id": "a" * 22,
                "origin_device_id": "ak:device:01904100-0000-7000-8000-000000000001",
                "created_at": "2026-08-31T00:00:00.000Z",
            },
            "key_delivery": {"method": "account_data_wrapped_key", "content_key": "A" * 43},
        }

    def test_stream_and_whole_file_constructible_without_wire_count(self):
        validator = self.validator("file-transfer", "encryption")
        stream = self.descriptor()
        validator.validate(stream)
        whole = copy.deepcopy(stream)
        whole.update(scheme="ak.blob.whole_file_aead.v1", nonce="A" * 32)
        del whole["nonce_prefix"], whole["segment_bytes"]
        validator.validate(whole)
        for descriptor in (stream, whole):
            for count in (None, 0, 1, 1048576):
                self.assertFalse(validator.is_valid({**descriptor, "segment_count": count}))
        for field, value in (("segment_bytes", 1023), ("segment_bytes", 8388609),
                             ("nonce_prefix", "A" * 25), ("nonce_prefix", "A" * 25 + "B"),
                             ("nonce", None), ("nonce", "A" * 32)):
            self.assertFalse(validator.is_valid({**stream, field: value}))
        for field in ("nonce_prefix", "segment_bytes"):
            self.assertFalse(validator.is_valid({**whole, field: None}))

    def test_open_view_config_rejects_only_named_forbidden_keys(self):
        cases = (("collection_config", {"item_object_kinds": ["strand"],
                                       "item_order_by": [{"field": "rank", "direction": "asc"}],
                                       "grouping": {"mode": "none"}}),
                 ("collection_grouping", {"mode": "none"}))
        for definition, value in cases:
            validator = self.validator("view", definition)
            validator.validate(value)
            validator.validate({**value, "x_custom": {"enabled": True}})
            for field in ("page_size", "selection_policy", "wip_limit_enforcement"):
                for rejected in (None, False, 20, "hard"):
                    with self.subTest(definition=definition, field=field, value=rejected):
                        self.assertFalse(validator.is_valid({**value, field: rejected}))


if __name__ == "__main__":
    unittest.main()
