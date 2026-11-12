"""Regression locks for the authority-commit protocol."""

import base64
import json
import re
import unittest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from pathlib import Path
from tools.artifact_lint.core import schema_assertions


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec/v1/artifacts"


def read(relative: str):
    return json.loads((ARTIFACTS / relative).read_text(encoding="utf-8"))


REMOVED_STATE_MACHINE_TERMS = {
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
}


def removed_state_machine_terms(text):
    return sorted(term for term in REMOVED_STATE_MACHINE_TERMS if term in text)


def protocol_registry_lifecycle_errors(document):
    """Check protocol catalog rows, never nested Actor lifecycle state."""
    errors = []
    events = document.get("event_kind_registry", document).get("event_kinds", [])
    for index, row in enumerate(events):
        if row.get("status") != "active":
            errors.append(f"event_kinds/{index}/status: expected active, got {row.get('status')!r}")
    operations = document.get("operation_registry", document).get("operations", [])
    for index, row in enumerate(operations):
        if "status" in row and row["status"] != "active":
            errors.append(f"operations/{index}/status: expected active, got {row['status']!r}")
        if row.get("deprecated") is True:
            errors.append(f"operations/{index}/deprecated: current operation cannot be deprecated")
    return errors


def openapi_operation_lifecycle_errors(document):
    from tools.artifact_lint.http_naming import HTTP_METHODS, _resolve

    errors = []
    for path, raw_item in document.get("paths", {}).items():
        where = "#/paths/" + path.replace("~", "~0").replace("/", "~1")
        item = _resolve(document, raw_item, where, errors, path_item=True)
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method in HTTP_METHODS and isinstance(operation, dict) and operation.get("deprecated") is True:
                errors.append(f"{where}/{method}/deprecated: current operation cannot be deprecated")
    return errors


class AuthorityCommitProtocolTest(unittest.TestCase):
    def test_member_bootstrap_genesis_fact_presence_binds_original_commit(self):
        schema = read("schemas/realm-join-intake.schema.json")
        response = schema["$defs"]["peer_bootstrap_response_body"]
        self.assertEqual(list(response["properties"]), [
            "request_id", "authority_bundle", "producer_signer_fact", "snapshot", "visible_stream_heads",
        ])
        self.assertFalse(response["additionalProperties"])
        self.assertEqual(response["properties"]["producer_signer_fact"]["$ref"],
            "./authority-commit-operations.schema.json#/$defs/historical_producer_signer_fact")
        # Evaluate the actual schema's conditional presence rule separately
        # from signatures and full carrier shape, which have other verifiers.
        presence = Draft202012Validator({"allOf": response["allOf"]})
        for digest, fact, valid in ((False, False, True), (False, True, False),
                                     (True, False, False), (True, True, True)):
            value = {"authority_bundle": {"genesis_commit": {}}}
            if digest:
                value["authority_bundle"]["genesis_commit"]["producer_signer_fact_digest"] = "sha256:" + "a" * 64
            if fact:
                value["producer_signer_fact"] = {}
            with self.subTest(digest=digest, fact=fact):
                self.assertEqual(presence.is_valid(value), valid)
        documents = [json.loads(path.read_text(encoding="utf-8"))
                     for path in (ARTIFACTS / "schemas").glob("*.json")]
        registry = Registry().with_resources((item["$id"], Resource.from_contents(item))
                                             for item in documents)
        fact_shape = Draft202012Validator({"$ref": schema["$id"] +
            "#/$defs/peer_bootstrap_response_body/properties/producer_signer_fact"}, registry=registry)
        for invalid in (None, {}, {"producer_signer_fact_digest": "sha256:" + "a" * 64}):
            self.assertFalse(fact_shape.is_valid(invalid))

    def test_pcr_station_binding_cases_replay_the_provenance_policy(self):
        # This is a semantic policy oracle, not a signature or storage verifier.
        # provenance_verified means the existing native verifier already succeeded.
        policy = read("profiles/conformance-profiles.json")["profile_requirements"][
            "ak.profile.principal_control_realm.v1"
        ]["pcr_governance_policy"]
        fixture = read("fixtures/pcr-genesis-fixture.json")
        cases = [{**row, "input": {**fixture["station_binding_baseline"], **row["input"]}}
                 for row in fixture["station_binding_cases"]]

        def admissible(value):
            if value.get("provenance_verified") is not True:
                return False
            human = policy["human"]
            if (value["purpose"], value["genesis_admission"]) == (
                human["purpose"], human["genesis_admission"]
            ):
                if value["authority_evidence"] != "registration_anchor":
                    return False
                if not value["account_station"] == value["genesis_governor"] == value["current_governor"]:
                    return False
                if value["stage"] in ["governance_change"] + human["rejected_stages"]:
                    return False
                if value["stage"] in {"endpoint_update", "key_update", "deployment_update"}:
                    return value["generation_before"] == value["generation_after"]
                return value["stage"] in {"genesis", "native_current"}
            agent = policy["agent"]
            if (value["purpose"], value["genesis_admission"]) == (agent["purpose"], agent["genesis_admission"]):
                if value["authority_evidence"] != "accepted_controller_provision":
                    return False
                if not (value["account_station"] == value.get("controller_station") == value["genesis_governor"] == value["current_governor"]):
                    return False
                if value.get("controller_account_distinct") is not True or value.get("generation_before") != 0 or value.get("generation_after") != 0:
                    return False
                if value["stage"] in ["governance_change"] + agent["rejected_stages"]:
                    return False
                return value["stage"] in {"genesis", "native_current", "public_authority_bundle", "endpoint_update", "key_update", "deployment_update"}
            if value["purpose"] == "collaboration":
                eligible = value["authority_evidence"] == "accepted_ordinary_genesis"
            else:
                eligible = any(all(value.get(key) == item for key, item in branch.items())
                               for branch in policy["transferable_provenance"])
            return eligible and all(value.get(key) is True for key in policy["transfer_preconditions"])

        self.assertEqual(len({row["name"] for row in cases}), len(cases))
        stages = {row["input"]["stage"] for row in cases}
        self.assertTrue(set(policy["human"]["rejected_stages"]).issubset(stages))
        for row in cases:
            with self.subTest(case=row["name"]):
                accepted = admissible(row["input"])
                self.assertEqual("accept" if accepted else "reject", row["expected"])
                self.assertEqual(not accepted, row["writes_nothing"])
        for branch in policy["transferable_provenance"]:
            self.assertTrue(any(row["expected"] == "accept" and all(
                row["input"].get(key) == value for key, value in branch.items()
            ) for row in cases))

    def test_call_case_preserves_freshness_without_a_human_handoff(self):
        fixture = read("fixtures/consent-cache-invalidation-fixture.json")
        case = fixture["cases"][11]
        self.assertEqual(case["name"], "call_invitation_older_read_retry_and_human_station_binding")
        assertions = " ".join(case["assertions"])
        for obligation in ("zero Event", "Older reads", "exact", "expired", "same-Station"):
            self.assertIn(obligation, assertions)
        evidence = next(point for row in fixture["security_evidence"]
                        for point in row["decision_points"] if point["id"] == case["name"])
        self.assertEqual(evidence["evidence"], ["/cases/11"])
        self.assertNotIn("non-Human", assertions)
        shared = read("fixtures/authority-commit-fixture.json")["handoff_private_manifest"]["transferable_pcr_runtime"]
        self.assertTrue(shared["independent_runtime_evidence_required"])
        self.assertFalse(shared["human_consent_suite_proves_this_contract"])
        for obligation in ("Organization", "complete planned handoff", "incomplete import", "stale old-authority", "exact outcomes/fences", "second writer"):
            self.assertIn(obligation, " ".join(shared["assertions"]))
        self.assertIn("transferable_pcr_runtime", evidence["requirement"])


    def test_reply_creation_convenience_uses_closed_payload_field(self):
        payload = read("schemas/event-payload.schema.json")["$defs"]["message_create_payload"]
        self.assertIn("reply_to_id", payload["properties"])
        for alias in ("reply_to", "in_reply_to"):
            self.assertNotIn(alias, payload["properties"])
        for relative in ("strand-and-message.md", "content-types.md"):
            prose = (ROOT / "spec/v1/zh/models" / relative).read_text(encoding="utf-8")
            self.assertIn("payload 可携带 `reply_to_id`", prose)
            self.assertNotIn("payload 可携带 `reply_to`", prose)

    def test_poll_registry_uses_partition_stream_positions(self):
        registry = read("registry/event-kind-registry.json")
        events = registry["event_kinds"]
        event = next(row for row in events if row["event_kind"] == "ak.message.create")
        effects = " ".join(event["reducer_effects"])
        self.assertIn("greatest stream_position", effects)
        self.assertIn("retain every accepted response", effects)
        self.assertNotIn("causal dominance", effects)

    def test_member_bootstrap_keeps_exact_stream_join_carrier(self):
        definitions = read("schemas/realm-join-intake.schema.json")["$defs"]
        request = definitions["peer_bootstrap_request_body"]
        self.assertEqual(request["required"], [
            "request_id", "realm_id", "member_account_id", "membership_commit_id",
        ])
        self.assertFalse(request["additionalProperties"])
        commit = request["properties"]["membership_commit_id"]
        self.assertEqual(commit["$ref"], "./common-ids.schema.json#/$defs/realm_commit_id")
        self.assertIn("ak.circle.member.state{join}", commit["description"])
        self.assertIn("cannot replace", commit["description"])
        self.assertIn("own history floors", definitions["peer_bootstrap_response_body"]["description"])
        prose = (ROOT / "spec/v1/zh/sync/federation.md").read_text(encoding="utf-8")
        self.assertIn("Circle stream 的 `ak.circle.member.state{join}`", prose)
        self.assertIn("不能以父 Realm join 替代", prose)

    def test_registered_circle_current_families_are_reachable(self):
        schema = read("schemas/current-state.schema.json")
        reachable = {branch.get("$ref") for branch in schema["oneOf"]}
        for name in ("current_circle", "current_circle_member_state"):
            self.assertIn(f"#/$defs/{name}", reachable)

    def test_every_current_state_binds_exact_source_stream(self):
        schema = read("schemas/current-state.schema.json")
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
                expected_stream = (
                    {"$ref": "./realm-actor.schema.json#/$defs/control_scope"}
                    if name.startswith("current_realm_actor_")
                    else {"$ref": "./realm-commit.schema.json#/$defs/stream_ref"}
                )
                if name == "current_applet_registration":
                    expected_stream["properties"] = {"kind": {"const": "realm"}}
                self.assertEqual(
                    schema_assertions(branch["properties"]["source_stream_ref"]),
                    expected_stream,
                )
                self.assertFalse(branch.get("additionalProperties", True))
        self.assertEqual(
            schema["$defs"]["revision"]["required"],
            ["commit_id", "stream_position"],
        )

    def test_current_v1_has_no_removed_state_machine_vocabulary(self):
        findings = []
        for root in (ROOT / "spec/v1/zh", ARTIFACTS):
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix not in {".md", ".json", ".yaml", ".yml"}:
                    continue
                text = path.read_text(encoding="utf-8")
                findings.extend(f"{path.relative_to(ROOT)}: {term}" for term in removed_state_machine_terms(text))
        for relative in ("registry/contract-registry.json", "registry/event-kind-registry.json",
                         "registry/operation-registry.json"):
            findings.extend(f"{relative}: {error}" for error in protocol_registry_lifecycle_errors(read(relative)))
        api = yaml.safe_load((ARTIFACTS / "openapi/arkret-service-api.openapi.yaml").read_text(encoding="utf-8"))
        findings.extend(openapi_operation_lifecycle_errors(api))
        self.assertEqual(findings, [])

    def test_protocol_lifecycle_gate_preserves_actor_terminal_states_without_file_exemptions(self):
        document = {"event_kinds": [{"event_kind": "ak.realm.actor.status.set", "status": "active",
            "notes": "A retired Realm Actor remains terminal, not a legacy protocol row.",
            "state_writes": [{"condition": {"kind": "field_equals", "field": "payload.state", "const": "retired"}}]}]}
        original = json.dumps(document, sort_keys=True)
        self.assertEqual(protocol_registry_lifecycle_errors(document), [])
        self.assertEqual(removed_state_machine_terms(json.dumps(document)), [])
        self.assertEqual(json.dumps(document, sort_keys=True), original)
        for status in ("retired", "Retired", "deprecated", "legacy", "退役", None):
            with self.subTest(status=status):
                changed = json.loads(original)
                changed["event_kinds"][0]["status"] = status
                self.assertTrue(protocol_registry_lifecycle_errors(changed))
        self.assertIn("ControlProposal", removed_state_machine_terms("ControlProposal must not return"))

    def test_current_operation_deprecation_is_checked_at_the_operation_object(self):
        api = {"paths": {"/_arkret/self/example": {"get": {"description": "Reject retired Actors",
            "deprecated": False}}}, "components": {"schemas": {"Actor": {"enum": ["retired"]}}}}
        self.assertEqual(openapi_operation_lifecycle_errors(api), [])
        api["paths"]["/_arkret/self/example"]["get"]["deprecated"] = True
        self.assertTrue(openapi_operation_lifecycle_errors(api))
        api["paths"] = {"/_arkret/self/example": {"$ref": "#/components/pathItems/Example"}}
        api["components"]["pathItems"] = {"Example": {"get": {"deprecated": True}}}
        self.assertTrue(openapi_operation_lifecycle_errors(api))
        for status in ("retired", "deprecated", "legacy"):
            self.assertTrue(protocol_registry_lifecycle_errors({"operations": [{"operation_id": "ak.self.example.read.list.v1", "status": status}]}))

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
        self.assertEqual(int(handoff["to_generation"]), int(handoff["from_generation"]) + 1)
        candidate = row["candidate"]
        self.assertEqual(candidate["signed_by_generation"], int(handoff["from_generation"]))
        self.assertEqual(row["expected"], "rejected")
        self.assertTrue(row["writes_nothing"])
        successor = row["new_generation_first_commit"]
        self.assertEqual(successor["signed_by_generation"], int(handoff["to_generation"]))
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
            ["realm", "circle", "sidecar", "realm_control"],
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
        request = read("schemas/authority-commit-operations.schema.json")["$defs"]["realm_authority_handoff_request_body"]
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
