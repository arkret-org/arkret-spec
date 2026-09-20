"""D1 keeps one Relation current result per primary conflict domain.

The old multi-candidate adjudication surface is intentionally gone. These tests
are reverse gates: no resolve carrier/family/query may return, while all three
remaining writes must address the same closed domain and preserve exact CAS and
create-locked identity.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
CONTENT_KINDS = ("ak.relation.create", "ak.relation.update", "ak.relation.tombstone")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class RelationPrimaryDomainCasTest(unittest.TestCase):
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

    def test_old_adjudication_surface_is_absent(self) -> None:
        self.assertNotIn("ak.relation.resolve", self.rows)
        self.assertNotIn(
            "relation_conflict_resolution",
            {
                row["result_kind"]
                for row in self.registry["current_result_registry"]["result_kinds"]
            },
        )
        self.assertNotIn("relation_resolve_payload", self.payloads["$defs"])
        self.assertNotIn("relation_conflict_resolution_result", self.typed["$defs"])
        self.assertFalse(
            any(
                row["operation_id"]
                == "ak.self.relation_conflicts.read.candidates.v1"
                for row in self.registry["operation_registry"]["operations"]
            )
        )

    def test_all_writers_share_one_closed_domain_subject(self) -> None:
        expected = {
            "kind": "composite",
            "components": [
                {
                    "kind": "canonical_json",
                    "field": "payload.primary_conflict_domain",
                }
            ],
        }
        for kind in CONTENT_KINDS:
            writes = self.rows[kind]["result_writes"]
            self.assertEqual([write["result_family"] for write in writes], ["relation"])
            self.assertEqual(writes[0]["result_selector"], expected, kind)

        domain = self.relation["$defs"]["relation_primary_conflict_domain"]
        self.assertFalse(domain["additionalProperties"])
        self.assertEqual(
            sorted(domain["properties"]),
            ["domain_kind", "from_ref", "relation_kind", "to_ref"],
        )
        selector = self.typed["$defs"]["relation_result"]["properties"]["selector"]
        self.assertEqual(
            sorted(selector["properties"]), ["kind", "primary_conflict_domain"]
        )

    def test_every_writer_carries_the_domain_and_revision(self) -> None:
        for name in (
            "relation_create_payload",
            "relation_update_payload",
            "relation_tombstone_payload",
        ):
            required = set(self.payloads["$defs"][name]["required"])
            self.assertTrue(
                {"primary_conflict_domain", "expected_revision"} <= required, name
            )

        create_revision = self.payloads["$defs"]["relation_create_payload"][
            "properties"
        ]["expected_revision"]
        self.assertEqual(
            create_revision["oneOf"][1], {"type": "null"}
        )

    def test_create_has_one_closed_authoring_shape_and_one_rank_carrier(self) -> None:
        create = self.payloads["$defs"]["relation_create_payload"]
        self.assertEqual(
            sorted(create["properties"]),
            ["expected_revision", "primary_conflict_domain", "relation"],
        )
        self.assertNotIn("rank", create["properties"])
        self.assertEqual(
            create["properties"]["relation"],
            {"$ref": "#/$defs/relation_create_object"},
        )
        self.assertEqual(
            self.payloads["$defs"]["relation_create_object"]["$ref"],
            "./relation.schema.json#/$defs/relation_definition",
        )

        definition = self.relation["$defs"]["relation_definition"]
        self.assertFalse(definition["additionalProperties"])
        self.assertEqual(
            sorted(definition["properties"]),
            [
                "fields",
                "from_ref",
                "rank",
                "relation_kind",
                "scope_circle_id",
                "to_ref",
            ],
        )
        self.assertEqual(
            set(definition["required"]), {"relation_kind", "from_ref", "to_ref"}
        )
        for reducer_owned in (
            "schema",
            "realm_id",
            "id",
            "effective_scope",
            "state",
            "state_changed_at",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ):
            self.assertNotIn(reducer_owned, definition["properties"])

        create_row = self.rows["ak.relation.create"]
        self.assertEqual(
            create_row["result_writes"][0]["result_projection"]["value"],
            {"field": "payload.relation"},
        )
        self.assertNotIn(
            "payload.rank",
            json.dumps(create_row["result_writes"], ensure_ascii=False),
        )

    def test_update_cannot_move_primary_domain(self) -> None:
        write = self.rows["ak.relation.update"]["result_writes"][0]
        self.assertEqual(
            write["result_projection"]["allowed_paths"],
            ["scope_circle_id", "rank", "fields"],
        )
        self.assertTrue(
            {"relation_kind", "from_ref", "to_ref"}
            <= set(write["retained_members"])
        )
        patch_schema = self.payloads["$defs"]["relation_update_payload"][
            "properties"
        ]["patch"]
        patterns = {
            branch["propertyNames"]["not"]["pattern"]
            for branch in patch_schema["allOf"][1:]
        }
        self.assertEqual(
            patterns,
            {
                r"^effective_scope(?:\.|$)",
                r"^relation_kind(?:\.|$)",
                r"^from_ref(?:\.|$)",
                r"^to_ref(?:\.|$)",
            },
        )

    def test_relation_uses_the_shared_canonical_lifecycle_timestamp(self) -> None:
        prose = (ROOT / "spec" / "v1" / "zh" / "models" / "relation.md").read_text(
            encoding="utf-8"
        )
        common = (
            ROOT / "spec" / "v1" / "zh" / "models" / "common-fields.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("state_changed_at = Event.created_at", prose)
        self.assertIn(
            "max(Event.created_at, accepting RealmCommit.committed_at)", prose
        )
        self.assertIn(
            "max(Event.created_at, accepting_committed_at)", common
        )

        create = self.rows["ak.relation.create"]["result_writes"][0]
        update = self.rows["ak.relation.update"]["result_writes"][0]
        tombstone = self.rows["ak.relation.tombstone"]["result_writes"][0]
        self.assertIn(
            {"name": "created_at", "derivation": "object_create_time"},
            create["derived_members"],
        )
        self.assertIn(
            {"name": "updated_at", "derivation": "object_update_time"},
            update["derived_members"],
        )
        self.assertIn(
            {"name": "state_changed_at", "derivation": "object_state_transition_time"},
            tombstone["derived_members"],
        )
        self.assertIn(
            {"name": "updated_at", "derivation": "object_update_time"},
            tombstone["derived_members"],
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
