"""`ak.relation.resolve` writes one family, and it is the adjudication one.

`models/relation.md` section 6.2 spells the whole write -- single carrier,
`current-value projection`, family `relation_conflict_resolution`, subject
determined entirely by `payload.conflict_domain` with the Realm taken from the
envelope -- and for as long as the row was missing that paragraph was prose
nothing replayed. Registering it closes the writer side, but three of its
properties are load-bearing in ways no existing gate measures:

* the subject MUST NOT respell the Realm or the Circle. `relation_conflict_domain`
  excludes both on purpose, so a composite that added either would let one domain
  be addressed two ways and split a `require_review` group in half;
* the value MUST keep `baseline`. Section 6.5 decides whether a newly discovered
  candidate re-triggers `require_review` by asking whether it sits inside the
  frozen baseline of the current adjudication. A value holding only `outcome`
  cannot answer that, and the family would then be unable to do the one job it
  is registered for;
* the write MUST stay off Relation content and off every security-permission
  family. Section 6.2 divides the two explicitly and
  `authz/event-auth-state-resolution.md` section 3 is why.

Each of those is a sentence in the registry today and a silent regression
tomorrow, because the artifact gates check the grammar of a row rather than
which family it names.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
FAMILY = "relation_conflict_resolution"
CONTENT_KINDS = ("ak.relation.create", "ak.relation.update", "ak.relation.tombstone")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class RelationConflictResolutionFamilyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = _load(ARTIFACTS / "registry" / "contract-registry.json")
        cls.typed = _load(ARTIFACTS / "schemas" / "typed-current-result.schema.json")
        cls.payloads = _load(ARTIFACTS / "schemas" / "event-payload.schema.json")
        cls.relation = _load(ARTIFACTS / "schemas" / "relation.schema.json")
        cls.rows = {
            row["event_kind"]: row
            for row in cls.registry["event_kind_registry"]["event_kinds"]
        }
        cls.write = cls.rows["ak.relation.resolve"]["result_writes"][0]

    # ---- the carrier -----------------------------------------------------

    def test_resolve_is_the_only_writer_and_writes_only_this_family(self) -> None:
        writers = sorted(
            kind
            for kind, row in self.rows.items()
            for write in row.get("result_writes") or []
            if write.get("result_family") == FAMILY
        )
        self.assertEqual(writers, ["ak.relation.resolve"])
        families = [
            write["result_family"]
            for write in self.rows["ak.relation.resolve"]["result_writes"]
        ]
        self.assertEqual(families, [FAMILY])

    def test_content_kinds_never_write_the_adjudication_family(self) -> None:
        """Section 6.2 keeps content and group adjudication apart."""
        for kind in CONTENT_KINDS:
            for write in self.rows[kind].get("result_writes") or []:
                self.assertNotEqual(write.get("result_family"), FAMILY, kind)

    # ---- the subject -----------------------------------------------------

    def test_the_subject_is_the_closed_conflict_domain_and_nothing_else(self) -> None:
        self.assertEqual(
            self.write["result_selector"],
            {
                "kind": "composite",
                "components": [
                    {"kind": "canonical_json", "field": "payload.conflict_domain"}
                ],
            },
        )

    def test_the_conflict_domain_still_excludes_realm_and_circle(self) -> None:
        """If the domain ever gained either, the subject would have two spellings."""
        domain = self.relation["$defs"]["relation_conflict_domain"]
        self.assertFalse(domain["additionalProperties"])
        self.assertEqual(
            sorted(domain["properties"]),
            ["domain_kind", "from_ref", "relation_kind", "to_ref"],
        )
        selector = self.typed["$defs"][f"{FAMILY}_result"]["properties"]["selector"]
        self.assertEqual(sorted(selector["properties"]), ["conflict_domain", "kind"])

    # ---- the value -------------------------------------------------------

    def test_the_value_keeps_the_frozen_baseline(self) -> None:
        """Section 6.5's uncovered-candidate rule is unmakeable without it."""
        self.assertEqual(
            self.write["result_projection"],
            {"kind": "set", "value": {"field": "payload"}},
        )
        value_ref = self.typed["$defs"][f"{FAMILY}_value"]["$ref"]
        self.assertEqual(
            value_ref, "./event-payload.schema.json#/$defs/relation_resolve_payload"
        )
        payload = self.payloads["$defs"]["relation_resolve_payload"]
        self.assertEqual(
            sorted(payload["required"]), ["baseline", "conflict_domain", "outcome"]
        )
        self.assertFalse(payload["additionalProperties"])

    def test_the_family_is_registered_and_listed_in_prose(self) -> None:
        kinds = {
            row["result_kind"]: row["schema_ref"]
            for row in self.registry["current_result_registry"]["result_kinds"]
        }
        self.assertEqual(
            kinds[FAMILY],
            f"schemas/typed-current-result.schema.json#/$defs/{FAMILY}_result",
        )
        prose = (ARTIFACTS.parent / "zh" / "sync" / "current-results.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"`{FAMILY}`", prose)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
