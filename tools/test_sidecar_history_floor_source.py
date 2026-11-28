"""G02 carrier checks, not a simulation of Station issuance or delivery.

Native authority, accepted MLS lineage, current disclosure and floor computation
remain independently verified inputs. Fixture keys prove only signed bindings.
"""
from __future__ import annotations

import copy
import json
import unittest

from tools.artifact_lint import agent_session_content
from tools.artifact_lint.call_current import ARTIFACTS, schema_validator, verify_detached
from tools.generate_reaction_current_fixture import sign_snapshot, typed_id
from tools.regenerate_detached_object_signature_kat import KEY_A_SEED, make_signature, public_key

H, G = "ak:did_core:web:home.example", "ak:did_core:web:station.example"
AGENT = {"principal_id": "ak:did_core:web:agent.example", "station_id": H}
CONTROLLER = {"principal_id": "ak:did_core:web:controller.example", "station_id": H}
REALM = typed_id("realm", {"fixture": "realm"})
SIDECAR = typed_id("event", {"fixture": "sidecar_create"}).replace("ak:event:", "ak:sidecar:")
G_VM = "did:web:station.example#notary-fixture"
PARENT = {"kind": "realm", "realm_id": REALM}
STREAM = {"kind": "sidecar", "realm_id": REALM, "sidecar_id": SIDECAR}


def coordinate(label, position):
    return {"event_id": typed_id("event", {"fixture": label}),
            "commit_id": typed_id("realm_commit", {"fixture": label}),
            "stream_ref": PARENT, "stream_position": position}


JOIN, CREATE = coordinate("current_agent_join", 6), coordinate("sidecar_create", 8)
REQUEST = {"request_id": "ak:request:01964137-0000-7000-8000-000000000001", "realm_id": REALM,
           "member_account_id": AGENT, "membership_commit_id": JOIN["commit_id"], "history_stream_ref": PARENT}


def sign_basis(value):
    value = sign_snapshot(value)
    del value["signature"]
    value["signature"], _ = make_signature("ak.realm_snapshot_signature.v1", value, G_VM, KEY_A_SEED)
    return value


def signed_basis():
    """An independently established G cut expressed in existing fields only."""
    anchor = typed_id("realm_commit", {"fixture": "accepted_project_head"})
    row = {"selector": {"kind": "member_state", "actor_id": {"kind": "account", "account_id": AGENT}},
           "source_stream_ref": PARENT, "revision": {key: JOIN[key] for key in ("commit_id","stream_position")},
           "value": {"membership": "join"}}
    return sign_basis({"realm_id": REALM, "governance_generation": "0", "purpose": "stream_history",
        "history_basis": {"account_id": AGENT, "stream_ref": PARENT, "anchor_position": 8,
                          "anchor_commit_ref": anchor, "accepted_dependency_refs": [JOIN]},
        "visible_stream_heads": [{"stream_ref": PARENT, "stream_position": 8, "commit_id": anchor}],
        "current_state_entries": [row], "retention_and_history_floor": {"history_access": "since_join",
            "stream_floors": [{"stream_ref": PARENT, "oldest_position": 6}]},
        "created_at": "2026-11-18T00:00:00.000Z"})


def bound_floor(snapshot, request, current_join):
    """Check signed carrier bindings; never determine current read permission."""
    schema_validator(ARTIFACTS / "schemas/realm-join-intake.schema.json", "#/$defs/peer_bootstrap_request_body").validate(request)
    schema_validator(ARTIFACTS / "schemas/realm-state-snapshot.schema.json", "").validate(snapshot)
    if snapshot["signature"]["verification_method"].split("#")[0] != "did:" + G.removeprefix("ak:did_core:"):
        raise ValueError("fixture G signing method")
    verify_detached(snapshot, "signature", public_key(KEY_A_SEED), "ak.realm_snapshot_signature.v1")
    unsigned = {k: v for k, v in snapshot.items() if k not in ("snapshot_id", "signature")}
    basis = snapshot.get("history_basis", {})
    if (snapshot["snapshot_id"] != typed_id("realm_snapshot", unsigned) or snapshot["purpose"] != "stream_history"
            or snapshot["realm_id"] != request["realm_id"] or snapshot["governance_generation"] != "0"
            or basis.get("account_id") != request["member_account_id"]
            or basis.get("stream_ref") != request["history_stream_ref"]
            or current_join["commit_id"] != request["membership_commit_id"]
            or current_join not in basis.get("accepted_dependency_refs", [])):
        raise ValueError("exact signed Account, join, target or tenure")
    member = {"kind": "member_state", "actor_id": {"kind": "account", "account_id": request["member_account_id"]}}
    matching = [r for r in snapshot["current_state_entries"] if r["selector"] == member]
    if (len(matching) != 1 or matching[0]["value"]["membership"] != "join"
            or matching[0]["source_stream_ref"] != current_join["stream_ref"]
            or matching[0]["revision"] != {k: current_join[k] for k in ("commit_id", "stream_position")}):
        raise ValueError("complete current membership dependency")
    target = basis["stream_ref"]
    heads = [h for h in snapshot["visible_stream_heads"] if h["stream_ref"] == target]
    floors = [f for f in snapshot["retention_and_history_floor"]["stream_floors"] if f["stream_ref"] == target]
    if (len(heads) != 1 or len(floors) != 1 or heads[0]["commit_id"] != basis["anchor_commit_ref"]
            or heads[0]["stream_position"] != basis["anchor_position"]
            or not 0 <= floors[0]["oldest_position"] <= basis["anchor_position"]):
        raise ValueError("same signed target head and floor")
    return floors[0]["oldest_position"]


class ProjectHistoryFloorSourceTest(unittest.TestCase):
    def test_distinct_stations_use_existing_signed_account_join_stream_and_floor(self):
        self.assertNotEqual(H, G)
        self.assertEqual(bound_floor(signed_basis(), REQUEST, JOIN), 6)

    def test_same_agent_rejoin_rejects_old_signed_basis(self):
        joined = coordinate("new_agent_join", 9)
        with self.assertRaises(ValueError):
            bound_floor(signed_basis(), REQUEST | {"membership_commit_id": joined["commit_id"]}, joined)

    def test_resigned_wrong_agent_stream_tenure_or_incomplete_membership_rejected(self):
        for change in (lambda q: q["history_basis"].update(account_id=CONTROLLER),
                       lambda q: q["history_basis"].update(stream_ref=STREAM),
                       lambda q: q.update(governance_generation="1"),
                       lambda q: q["history_basis"].update(accepted_dependency_refs=[CREATE]),
                       lambda q: q["current_state_entries"].pop(0),
                       lambda q: q["retention_and_history_floor"]["stream_floors"][0].update(oldest_position=9)):
            q = signed_basis()
            change(q)
            with self.assertRaises(ValueError):
                bound_floor(sign_basis(q), REQUEST, JOIN)

    def test_floor_tampering_fails_the_existing_signature_verifier(self):
        q = signed_basis()
        q["retention_and_history_floor"]["stream_floors"][0]["oldest_position"] = 0
        with self.assertRaises(ValueError):
            bound_floor(q, REQUEST, JOIN)

    def test_floor_is_not_pending_payload_authority_or_a_handshake_prerequisite(self):
        fixture = json.loads((ARTIFACTS / "fixtures/agent-vectors-fixture.json").read_text())["session_content_authority_contract"]
        for name, expected in (("bootstrap_desired_not_yet_effective", "allow"), ("desired_cannot_read_payload", "deny")):
            case = next(row for row in fixture["cases"] if row["name"] == name)
            inputs = copy.deepcopy(fixture["defaults"] | case["input"])
            self.assertNotIn("history_floor", inputs)
            self.assertEqual(agent_session_content.decide(inputs), expected)
            inputs["history_floor"] = bound_floor(signed_basis(), REQUEST, JOIN)
            self.assertEqual(agent_session_content.decide(inputs), expected)


def content_exchange():
    request = dict(REQUEST)
    del request["history_stream_ref"]
    request["content_intent"] = {
        "controller_account_id": CONTROLLER,
        "controller_membership_commit_id": CREATE["commit_id"],
        "agent_key_authorization_ref": CREATE["event_id"],
        "action": "ak.object.read_content",
        "effective_scope": PARENT,
        "request_digest": "sha256:" + "a" * 64,
    }
    response = {
        "request_id": request["request_id"], "content_intent": request["content_intent"],
        "membership_commit_id": JOIN["commit_id"],
        "scope_details": {
            "controller_principal_id": CONTROLLER["principal_id"],
            "agent_key_authorization_ref": CREATE["event_id"],
            "realm_ids": [REALM], "strand_ids": [],
            "resources": {"realm_ids": [REALM], "strand_ids": []},
            "constraints": {"allowed_tracks": [], "allowed_data_labels": [], "allowed_endpoints": []},
            "capability_grant_refs": [], "policy_refs": [],
        },
    }
    return request, response


class OwnedAgentWireTest(unittest.TestCase):
    def test_only_home_sidecar_rosters_carry_the_backup_strategy(self):
        validator = schema_validator(ARTIFACTS / "schemas/mls-roster-authority.schema.json", "#/$defs/roster_manifest")
        fixture = json.loads((ARTIFACTS / "fixtures/mls-roster-client-roles-fixture.json").read_text(encoding="utf-8"))
        def manifest(tree):
            if isinstance(tree, dict):
                if "manifest" in tree:
                    yield tree["manifest"]
                for value in tree.values():
                    yield from manifest(value)
            elif isinstance(tree, list):
                for value in tree:
                    yield from manifest(value)
        example = next(manifest(fixture["schema_validation_cases"]))
        normal = dict(example, effective_scope=PARENT)
        private = dict(example, effective_scope=STREAM)
        strategy = {"sidecar_backup_strategy": "ak.encryption_backup.epoch_content_roots.v1"}
        validator.validate(normal)
        validator.validate({**private, **strategy})
        self.assertFalse(validator.is_valid({**normal, **strategy}))
        self.assertFalse(validator.is_valid(private))
        self.assertFalse(validator.is_valid({**private, "sidecar_backup_strategy": "unknown"}))

    def test_private_reply_requires_explicit_permission_on_a_join(self):
        check = schema_validator(ARTIFACTS / "schemas/event-payload.schema.json", "#/$defs/sidecar_member_state_payload")
        join = {"agent_account_id": AGENT, "membership": "join"}
        check.validate(join)
        check.validate({**join, "private_reply_allowed": True})
        check.validate({**join, "membership": "leave"})
        for value in (False, None, "true"):
            self.assertFalse(check.is_valid({**join, "private_reply_allowed": value}))
        self.assertFalse(check.is_valid({**join, "membership": "leave", "private_reply_allowed": True}))

    def test_session_source_and_history_are_exclusive(self):
        validator = schema_validator(ARTIFACTS / "schemas/realm-join-intake.schema.json",
                                     "#/$defs/peer_bootstrap_request_body")
        request, single = content_exchange()
        validator.validate(request)
        self.assertFalse(validator.is_valid({**request, "history_stream_ref": STREAM}))
        for member in request["content_intent"]:
            partial = copy.deepcopy(request)
            del partial["content_intent"][member]
            self.assertFalse(validator.is_valid(partial), member)

        response = schema_validator(ARTIFACTS / "schemas/realm-join-intake.schema.json",
                                    "#/$defs/peer_bootstrap_response_body")
        response.validate(single)
        self.assertFalse(response.is_valid({**single, "visible_stream_heads": []}))

        scan = schema_validator(ARTIFACTS / "schemas/authority-commit-operations.schema.json",
                                "#/$defs/peer_stream_scan_request_body")
        page = {"realm_id": REALM, "stream_ref": PARENT, "after_position": None, "limit": 1}
        scan.validate(page)
        delivery = {k: v for k, v in request.items() if k != "realm_id"}
        delivery.update(session_grant_id="ak:session_grant:01964137-0000-7000-8000-000000000001", scan=page)
        scan.validate(delivery)
        self.assertFalse(scan.is_valid({**page, "content_intent": request["content_intent"]}))

    def test_project_authorities_cannot_request_personal_material(self):
        request, response = content_exchange()
        schema = ARTIFACTS / "schemas/realm-join-intake.schema.json"
        for branch, body in (("request", request), ("response", response)):
            validator = schema_validator(schema, f"#/$defs/peer_bootstrap_{branch}_body")
            validator.validate(body)
            for overrides in ({"effective_scope": STREAM}, {"backup_root_context": {}}):
                self.assertFalse(validator.is_valid(dict(body, content_intent=dict(body["content_intent"], **overrides))))
        selector = dict(REQUEST, history_stream_ref=PARENT)
        validator = schema_validator(schema, "#/$defs/peer_bootstrap_request_body")
        validator.validate(selector)
        self.assertFalse(validator.is_valid(dict(selector, history_stream_ref=STREAM)))

    def test_first_writer_sidecar_packet_is_single_root_and_agent_signed(self):
        packet = json.loads((ARTIFACTS / "fixtures/content-history-fixture.json").read_text("utf-8"))["root_backup"]["envelope"]
        del packet["source_commit_ref"]
        packet["actor_id"] = {"kind": "account", "account_id": AGENT}
        packet["custodian_actor_id"] = {"kind": "account", "account_id": CONTROLLER}
        packet["custody_authorization_ref"] = CREATE["event_id"]
        proof = packet["signature_proof"]
        del proof["device_id"], proof["device_authorize_event_id"]
        proof["agent_authorization_event_ref"] = JOIN["event_id"]
        item = packet["contents"][0]
        item["root_context"]["effective_scope"] = {"kind": "sidecar", "realm_id": REALM, "sidecar_id": SIDECAR}
        validator = schema_validator(ARTIFACTS / "schemas/key-backup.schema.json", "#")
        validator.validate(packet)
        self.assertFalse(validator.is_valid({**packet, "contents": [item, item]}))
        self.assertFalse(validator.is_valid({**packet, "expires_at": packet["created_at"]}))
        self.assertFalse(validator.is_valid({**packet, "device_id": "ak:device:01964137-0000-7000-8000-000000000001"}))

    def test_first_writer_preparation_selects_only_one_sidecar(self):
        validator = schema_validator(ARTIFACTS / "schemas/keys-operations.schema.json",
                                     "#/$defs/keys_backups_list_query")
        validator.validate({"sidecar_id": SIDECAR})
        for extra in ({"cursor": "other"}, {"limit": 1}, {"agent_id": AGENT["principal_id"]}):
            self.assertFalse(validator.is_valid({"sidecar_id": SIDECAR, **extra}))

        histories = json.loads((ARTIFACTS / "fixtures/content-history-fixture.json").read_text("utf-8"))
        envelope = histories["root_backup"]["envelope"]
        backups = json.loads((ARTIFACTS / "fixtures/key-backup-fixture.json").read_text("utf-8"))
        policy = next(case["instance"] for case in backups["schema_validation_cases"]
                      if case["name"] == "recovery_policy_recovery_unlock_distinct_signing_and_hpke_keys_valid")
        context = dict(envelope["contents"][0]["root_context"],
                       effective_scope={"kind": "sidecar", "realm_id": REALM, "sidecar_id": SIDECAR})
        prepared = {
            "sidecar_id": SIDECAR, "root_context": context, "series_id": envelope["series_id"],
            "custody_authorization_ref": CREATE["event_id"],
            "series_sequence": 0, "recovery_policy_ref": envelope["recovery_policy_ref"],
            "backup_hpke": policy["methods"][0]["keys"][0]["backup_hpke"],
        }
        response = schema_validator(ARTIFACTS / "schemas/keys-operations.schema.json",
                                    "#/$defs/keys_backups_list_response_body")
        response.validate(prepared)
        self.assertFalse(response.is_valid({k: v for k, v in prepared.items() if k != "custody_authorization_ref"}))
        self.assertFalse(response.is_valid({**prepared, "custody_authorization_ref": None}))
        self.assertFalse(response.is_valid({**prepared, "provision_event": {}}))
        registry = json.loads((ARTIFACTS / "registry/pcr-exposure-registry.json").read_text("utf-8"))
        provision = next(row for row in registry["event_kinds"] if row["event_kind"] == "ak.agent.provision")
        [entry] = [row for row in provision["exposures"] if row.get("authorization_policy_id") == "ak.pcr_exposure_policy.current_sidecar_root_writer.v1"]
        self.assertEqual((entry["carrier"], entry["operation_id"], entry["direction"], entry["json_pointers"]),
                         ("derived_field", "ak.self.keys.backups.read.list.v1", "response",
                          ["/$defs/sidecar_backup_prepare_response_body/properties/custody_authorization_ref"]))

        previous = {"supersedes_id": envelope["backup_id"], "supersedes_digest": "sha256:" + "a" * 64}
        self.assertFalse(response.is_valid({**prepared, **previous}))
        self.assertFalse(response.is_valid({**prepared, "series_sequence": 1}))
        response.validate({**prepared, "series_sequence": 1, **previous})
        self.assertFalse(response.is_valid({**prepared, "backups": []}))

if __name__ == "__main__":
    unittest.main()
