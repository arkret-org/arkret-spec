"""Regression locks for the authority-commit protocol."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec/v1/artifacts"


def read(relative: str):
    return json.loads((ARTIFACTS / relative).read_text(encoding="utf-8"))


class AuthorityCommitProtocolTest(unittest.TestCase):
    def test_fixture_has_independent_predecessor_chains(self):
        fixture = read("fixtures/authority-commit-fixture.json")
        streams = fixture["independent_streams"]
        self.assertEqual(
            [stream["stream_ref"]["kind"] for stream in streams],
            ["realm", "circle", "sidecar"],
        )
        for stream in streams:
            commits = stream["commits"]
            self.assertEqual(commits[0]["stream_position"], 0)
            self.assertIsNone(commits[0]["previous_commit_ref"])
            for previous, current in zip(commits, commits[1:]):
                self.assertEqual(
                    current["stream_position"], previous["stream_position"] + 1
                )
                self.assertEqual(
                    current["previous_commit_ref"], previous["commit_id"]
                )
        self.assertEqual(
            fixture["handoff_private_manifest"]["head_count"], len(streams)
        )
        self.assertEqual(
            fixture["handoff_private_manifest"]["public_bundle_head_count"], 1
        )

    def test_event_has_no_retired_causality_or_cbs_fields(self):
        event = read("schemas/event-envelope.schema.json")
        retired = {
            "actor_seq",
            "hlc",
            "prev_refs",
            "causal_refs",
            "preconditions",
            "auth_context",
            "data_basis",
            "seal_basis",
            "requirements",
            "unsigned",
        }
        self.assertTrue(retired.isdisjoint(event["required"]))
        self.assertTrue(retired.isdisjoint(event["properties"]))

    def test_realm_circle_and_sidecar_are_independent_streams(self):
        stream = read("schemas/realm-commit.schema.json")["$defs"]["stream_ref"]
        branches = stream["oneOf"]
        self.assertEqual(
            [branch["properties"]["kind"]["const"] for branch in branches],
            ["realm", "circle", "sidecar"],
        )
        required = [set(branch["required"]) for branch in branches]
        self.assertEqual(required[0], {"kind", "realm_id"})
        self.assertEqual(required[1], {"kind", "realm_id", "circle_id"})
        self.assertEqual(required[2], {"kind", "realm_id", "sidecar_id"})

    def test_predecessor_is_commit_owned_not_event_owned(self):
        event = read("schemas/event-envelope.schema.json")
        commit = read("schemas/realm-commit.schema.json")
        self.assertNotIn("previous_commit_ref", event["properties"])
        self.assertIn("previous_commit_ref", commit["required"])
        self.assertIn("stream_position", commit["required"])
        self.assertEqual(
            commit["allOf"][0]["then"]["properties"]["previous_commit_ref"],
            {"type": "null"},
        )

    def test_handoff_binds_private_stream_manifest_without_public_leak(self):
        handoff = read("schemas/realm-authority-handoff.schema.json")
        self.assertIn("final_stream_heads_digest", handoff["required"])
        self.assertNotIn("final_stream_heads", handoff["properties"])
        request = read("schemas/authority-commit-operations.schema.json")["$defs"]["handoff_request"]
        self.assertIn("final_stream_heads", request["required"])
        self.assertEqual(
            request["properties"]["final_stream_heads"]["items"]["$ref"],
            "./realm-commit.schema.json#/$defs/stream_head",
        )
        public_bundle = read("schemas/realm-authority-bundle.schema.json")
        self.assertIn("realm_stream_head", public_bundle["required"])
        self.assertNotIn("current_heads", public_bundle["properties"])

    def test_retired_shared_event_kinds_are_absent(self):
        rows = read("registry/event-kind-registry.json")["event_kinds"]
        kinds = {row["event_kind"] for row in rows if row["status"] == "active"}
        retired = {
            "ak.fork.resolution",
            "ak.mls.commit_failed",
            "ak.mls.keypackage",
            "ak.mls.proposal",
            "ak.mls.welcome",
            "ak.notary.fault.censorship",
            "ak.notary.fault.equivocation",
            "ak.realm.authority.reset",
            "ak.realm.digest_suite_transition",
            "ak.realm.notary",
            "ak.realm.organization_recovery_key.register",
            "ak.realm.organization_recovery_key.rotate",
            "ak.realm.upgrade",
        }
        self.assertTrue(retired.isdisjoint(kinds))
        self.assertIn("ak.realm.governance_station.change", kinds)

    def test_mls_binding_is_minimal_and_revision_based(self):
        binding = read("schemas/event-payload.schema.json")["$defs"]["mls_governance_binding"]
        self.assertEqual(
            set(binding["required"]),
            {
                "effective_scope",
                "base_group_state_ref",
                "previous_epoch",
                "next_epoch",
                "key_access_revision",
            },
        )
        self.assertTrue(
            {
                "security_frontier_digest",
                "binding_profile",
                "reducer_profile",
                "content_scheme",
                "durability_policy",
            }.isdisjoint(binding["properties"])
        )


if __name__ == "__main__":
    unittest.main()
