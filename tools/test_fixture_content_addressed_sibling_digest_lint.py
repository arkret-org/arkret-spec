"""Tests for the fixture-side `encoding.md` 4.0.1 sibling-digest gate.

The schema-side gate proves each registered sibling digest is gone from its
schema. This one covers the instances, including the case that motivated it: a
record carried as an embedded JSON *string* is opaque to both the schema walk and
`additionalProperties`, so it can keep shipping a sibling the schema deleted.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.fixtures import content_addressed_sibling_digest_violations

REMOVALS = (("file-transfer.schema.json", (), "blob_ref", "content_digest"),)
HEX64 = "0a864a277e1ab492e45fb633188b9a934afd51804b7ac22279bea9f117bc95f8"
CONTENT_ADDRESSED_REF = f"ak:blob:sha256:{HEX64}"


class FixtureContentAddressedSiblingDigestLintTest(unittest.TestCase):
    def test_ref_without_sibling_passes(self) -> None:
        instance = {"kind": "file_transfer", "blob_ref": CONTENT_ADDRESSED_REF}
        self.assertEqual(content_addressed_sibling_digest_violations(instance, REMOVALS), [])

    def test_sibling_beside_content_addressed_ref_fails(self) -> None:
        instance = {
            "kind": "file_transfer",
            "blob_ref": CONTENT_ADDRESSED_REF,
            "content_digest": f"sha256:{HEX64}",
        }
        self.assertEqual(
            content_addressed_sibling_digest_violations(instance, REMOVALS),
            [("", "blob_ref", "content_digest")],
        )

    def test_sibling_inside_an_embedded_json_string_fails(self) -> None:
        record = {
            "kind": "file_transfer",
            "blob_ref": CONTENT_ADDRESSED_REF,
            "content_digest": f"sha256:{HEX64}",
        }
        fixture = {"kat": {"record_json": json.dumps(record, separators=(",", ":"))}}
        self.assertEqual(
            content_addressed_sibling_digest_violations(fixture, REMOVALS),
            [("/kat/record_json(decoded)", "blob_ref", "content_digest")],
        )

    def test_embedded_string_that_is_not_json_is_ignored(self) -> None:
        fixture = {"kat": {"record_json": "not json at all"}}
        self.assertEqual(content_addressed_sibling_digest_violations(fixture, REMOVALS), [])

    def test_union_ref_holding_a_uuid_is_not_a_mirror(self) -> None:
        # A union-shaped ref may hold a branch that carries no digest, so its
        # neighbour is not a mirror and this gate must stay silent about it.
        instance = {
            "blob_ref": "ak:blob:01964137-0000-7000-8000-000000000000",
            "content_digest": f"sha256:{HEX64}",
        }
        self.assertEqual(content_addressed_sibling_digest_violations(instance, REMOVALS), [])

    def test_declared_negative_case_is_exempt(self) -> None:
        instance = {
            "expect_valid": False,
            "blob_ref": CONTENT_ADDRESSED_REF,
            "content_digest": f"sha256:{HEX64}",
        }
        self.assertEqual(content_addressed_sibling_digest_violations(instance, REMOVALS), [])

    def test_negative_named_subtree_is_exempt(self) -> None:
        instance = {
            "rejected_records": [
                {"blob_ref": CONTENT_ADDRESSED_REF, "content_digest": f"sha256:{HEX64}"}
            ]
        }
        self.assertEqual(content_addressed_sibling_digest_violations(instance, REMOVALS), [])

    def test_shipped_fixtures_are_clean(self) -> None:
        fixtures = ROOT / "spec" / "v1" / "artifacts" / "fixtures"
        found: list[tuple[str, str, str, str]] = []
        for path in sorted(fixtures.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for pointer, id_field, digest_field in content_addressed_sibling_digest_violations(data):
                found.append((path.name, pointer, id_field, digest_field))
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
