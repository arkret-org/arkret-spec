"""Regression locks for the authority-commit protocol."""

import base64
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec/v1/artifacts"


def read(relative: str):
    return json.loads((ARTIFACTS / relative).read_text(encoding="utf-8"))


class AuthorityCommitProtocolTest(unittest.TestCase):
    def test_registered_circle_current_families_are_reachable(self):
        schema = read("schemas/typed-current-result.schema.json")
        reachable = {branch.get("$ref") for branch in schema["oneOf"]}
        for name in ("circle_result", "circle_member_state_result"):
            self.assertIn(f"#/$defs/{name}", reachable)

    def test_every_typed_current_result_binds_exact_source_stream(self):
        schema = read("schemas/typed-current-result.schema.json")
        branches = {
            name: definition
            for name, definition in schema["$defs"].items()
            if "selector" in definition.get("required", [])
            and "revision" in definition.get("required", [])
        }
        self.assertGreaterEqual(len(branches), 80)
        for name, branch in branches.items():
            with self.subTest(name=name):
                self.assertIn("source_stream_ref", branch["required"])
                self.assertEqual(
                    branch["properties"]["source_stream_ref"],
                    {"$ref": "./realm-commit.schema.json#/$defs/stream_ref"},
                )
                self.assertFalse(branch.get("additionalProperties", True))
        self.assertEqual(
            schema["$defs"]["revision"]["required"],
            ["commit_id", "stream_position"],
        )

    def test_current_v1_has_no_removed_state_machine_vocabulary(self):
        roots = [ROOT / "spec/v1/zh", ARTIFACTS]
        forbidden = {
            "EventInitialSubmission",
            "Control Move",
            "Move",
            "ordinary Event",
            "Lattice",
            "lattice",
            "sequenced_state",
            "causal_register",
            "or_set",
            "ordered_log",
            "state_model",
            "observed-remove",
            "observed_dot",
            "dot_ids",
            "authority_revision",
            "auth_context",
            "data_basis",
            "reducer_profile",
            "reducer profile",
            "supported_reducer_profiles",
            "state-slot:",
            "ak.component.",
            "head_eq",
            "effect_projection",
            "notary",
            "Notary",
            "ControlProposal",
            "control_proposal",
            "peer reconciliation",
            "frontier_digest",
            "frontier_ref",
            "control_frontier",
            "Retired",
            "retired",
            "deprecated",
            "legacy",
            "退役",
        }
        findings = []
        for root in roots:
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix not in {".md", ".json", ".yaml", ".yml"}:
                    continue
                text = path.read_text(encoding="utf-8")
                for term in forbidden:
                    if term in text:
                        findings.append(f"{path.relative_to(ROOT)}: {term}")
        self.assertEqual(findings, [])

    def test_reducer_profile_registry_is_not_part_of_current_v1(self):
        self.assertFalse((ARTIFACTS / "registry/reducer-profile-registry.json").exists())
        manifest = read("registry/registry-manifest.json")
        self.assertNotIn("reducer_profiles", json.dumps(manifest, sort_keys=True))

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

    def test_every_fixture_commit_id_is_a_real_suite_tagged_token(self):
        # Placeholder tokens decode to a zero suite byte, so an SDK that checks
        # the digest suite cannot parse the fixture at all.
        raw = (ARTIFACTS / "fixtures/authority-commit-fixture.json").read_text(encoding="utf-8")
        values = set(re.findall(r"ak:realm_commit:([A-Za-z0-9_-]+)", raw))
        self.assertTrue(values)
        sha256_suite_code = 1
        for value in sorted(values):
            self.assertEqual(len(value), 44, value)
            body = base64.urlsafe_b64decode(value + "==")
            self.assertEqual(len(body), 33, value)
            self.assertEqual(body[0], sha256_suite_code, value)

    def test_fixture_covers_every_vector_the_registry_says_it_carries(self):
        # covers_vectors is the fixture's own claim; the registry's carrier
        # indexing is the independent one. Comparing them as sets keeps both
        # directions: a registered vector that names this fixture but is absent
        # from covers_vectors has no case here, and a covers_vectors entry the
        # registry does not route here is a claim nothing backs. The check is
        # domain-agnostic on purpose, because this fixture now carries the
        # authority_commit_projection admission transcripts as well.
        name = "authority-commit-fixture.json"
        fixture = read(f"fixtures/{name}")
        rows = read("registry/vector-registry.json")["vectors"]
        carried = set()
        for row in rows:
            if row["status"] != "active":
                continue
            refs = [ref for ref in row.get("source_refs", []) if isinstance(ref, str)]
            if name in row.get("applies_to_fixtures", []) or any(
                ref.endswith(f"/artifacts/fixtures/{name}") for ref in refs
            ):
                carried.add(row["vector_id"])
        self.assertEqual(set(fixture["covers_vectors"]), carried)
        for row in rows:
            if row["domain"] == "authority_commit" and row["status"] == "active":
                self.assertEqual(row["applies_to_fixtures"], [name])

    def test_broken_chain_and_position_gap_are_rejected_without_writes(self):
        fixture = read("fixtures/authority-commit-fixture.json")
        rows = fixture["rejected_commits"]
        heads = {
            json.dumps(stream["stream_ref"], sort_keys=True): stream["commits"][-1]
            for stream in fixture["independent_streams"]
        }
        self.assertEqual(
            {row["name"] for row in rows},
            {
                "predecessor_from_another_stream_is_rejected",
                "broken_predecessor_within_the_same_stream_is_rejected",
                "position_gap_is_rejected",
                "nonzero_position_with_null_predecessor_is_rejected",
            },
        )
        for row in rows:
            self.assertEqual(row["expected"], "rejected", row["name"])
            self.assertTrue(row["writes_nothing"], row["name"])
            self.assertEqual(
                row["vector_id"],
                "ak.vector.authority_commit.stream_continuity_negative.v1",
                row["name"],
            )
            head = heads[json.dumps(row["stream_ref"], sort_keys=True)]
            self.assertEqual(row["accepted_head"]["commit_id"], head["commit_id"], row["name"])
            candidate = row["candidate"]
            # Every row must actually break exactly the continuity rule it names.
            continuous = (
                candidate["stream_position"] == head["stream_position"] + 1
                and candidate["previous_commit_ref"] == head["commit_id"]
            )
            self.assertFalse(continuous, row["name"])

    def test_equivocation_freezes_the_stream_without_choosing_a_winner(self):
        row = read("fixtures/authority-commit-fixture.json")["equivocation_freeze"]
        self.assertEqual(
            row["vector_id"], "ak.vector.authority_commit.equivocation_freeze.v1"
        )
        self.assertEqual(
            set(row["coordinate"]),
            {"realm_id", "stream_ref", "governance_generation", "stream_position"},
        )
        observed = row["observed_commits"]
        self.assertEqual(len(observed), 2)
        self.assertTrue(all(entry["signature_valid"] for entry in observed))
        self.assertNotEqual(observed[0]["commit_id"], observed[1]["commit_id"])
        self.assertEqual(observed[0]["previous_commit_ref"], observed[1]["previous_commit_ref"])
        expected = row["expected"]
        self.assertEqual(expected["stream_state"], "frozen")
        self.assertFalse(expected["winner_selected"])
        self.assertTrue(expected["auto_resolution_forbidden"])
        self.assertTrue(expected["other_streams_unaffected"])
        anchor = row["spec_anchor"].split("#", 1)[0]
        self.assertTrue((ROOT / anchor).is_file())

    def test_old_station_cannot_write_after_a_planned_handoff(self):
        row = read("fixtures/authority-commit-fixture.json")["post_handoff_write_rejected"]
        self.assertEqual(
            row["vector_id"],
            "ak.vector.authority_commit.post_handoff_write_rejected.v1",
        )
        handoff = row["handoff"]
        self.assertTrue(handoff["acceptance_signed"])
        self.assertTrue(handoff["final_stream_heads_imported"])
        self.assertEqual(handoff["to_generation"], handoff["from_generation"] + 1)
        candidate = row["candidate"]
        self.assertEqual(candidate["signed_by_generation"], handoff["from_generation"])
        self.assertEqual(row["expected"], "rejected")
        self.assertTrue(row["writes_nothing"])
        successor = row["new_generation_first_commit"]
        self.assertEqual(successor["signed_by_generation"], handoff["to_generation"])
        self.assertEqual(successor["expected"], "accepted")
        # The new generation continues the imported final head at the same position
        # the old generation was refused, so no position is skipped or duplicated.
        self.assertEqual(successor["stream_position"], candidate["stream_position"])
        self.assertEqual(
            successor["previous_commit_ref"], candidate["previous_commit_ref"]
        )

    def test_cross_stream_workflow_is_a_saga_not_an_atomic_write(self):
        row = read("fixtures/authority-commit-fixture.json")["cross_stream_saga"]
        self.assertEqual(
            row["vector_id"], "ak.vector.authority_commit.cross_stream_saga.v1"
        )
        self.assertTrue(row["streams_share_governance_station"])
        self.assertTrue(row["streams_share_serializable_store"])
        self.assertEqual(row["protocol_atomicity_scope"], "one_authority_stream")

        steps = row["steps"]
        self.assertEqual(steps[0]["expected"], "committed")
        self.assertEqual(steps[1]["expected"], "retryable_unavailable")
        self.assertTrue(steps[1]["writes_nothing"])
        self.assertEqual(steps[2]["request_key"], steps[1]["request_key"])
        self.assertEqual(steps[2]["bytes"], "exact_same_canonical_bytes")
        self.assertEqual(steps[2]["expected"], "committed_once")
        self.assertEqual(steps[3]["expected"], "original_committed_outcome")

        failure = row["terminal_failure_branch"]
        self.assertTrue(failure["target_writes_nothing"])
        self.assertTrue(failure["source_commit_remains_immutable"])
        self.assertTrue(failure["rollback_forbidden"])
        self.assertIn("compensating Event", failure["cancellation_requires"])
        self.assertIn("cross_stream_all_or_nothing", row["forbidden_claims"])
        self.assertIn(
            "shared_store_expands_protocol_atomicity", row["forbidden_claims"]
        )

    def test_event_has_no_removed_causality_or_cbs_fields(self):
        event = read("schemas/event-envelope.schema.json")
        removed = {
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
        self.assertTrue(removed.isdisjoint(event["required"]))
        self.assertTrue(removed.isdisjoint(event["properties"]))

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

    def test_removed_shared_event_kinds_are_absent(self):
        rows = read("registry/event-kind-registry.json")["event_kinds"]
        kinds = {row["event_kind"] for row in rows if row["status"] == "active"}
        removed = {
            "ak.fork.resolution",
            "ak.mls.commit_failed",
            "ak.mls.keypackage",
            "ak.mls.proposal",
            "ak.mls.welcome",
            "ak.notary.fault.censorship",
            "ak.notary.fault.equivocation",
            "ak.realm.digest_suite_transition",
            "ak.realm.notary",
            "ak.realm.organization_recovery_key.register",
            "ak.realm.organization_recovery_key.rotate",
            "ak.realm.upgrade",
        }
        self.assertTrue(removed.isdisjoint(kinds))
        self.assertIn("ak.realm.governance_station.change", kinds)
        # ak.realm.authority.reset sat in this list for one reason only: the
        # mechanical sweep of c473e3c4 dropped it together with the kinds the
        # frozen architecture really does eliminate. Nothing in that
        # architecture removes an authority-generation reset, and the prose
        # (authz/capabilities.md) plus the root-owner mask of
        # profiles/conformance-profiles.json kept naming it as the only act
        # that invalidates a delegated authority generation. It is registered
        # again, and the two counters are now spelled apart: this kind advances
        # the Realm authority-root authority_generation, while a governing
        # Station tenure is governance_generation.
        self.assertIn("ak.realm.authority.reset", kinds)

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
