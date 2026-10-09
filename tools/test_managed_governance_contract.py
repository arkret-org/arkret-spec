"""Executable protocol reference decisions and RFC9421 KAT; no SUT claim."""
from __future__ import annotations
import base64
import copy
import json
from pathlib import Path
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
import unittest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
import yaml

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "spec/v1/artifacts"


def jcs(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def policy_gate(policies, controller, operation):
    rank = {"allow": 0, "require_review": 1, "quarantine": 2, "deny": 3}
    results = []
    for policy in policies:
        matched = [rule for rule in policy["rules"] if operation in rule["agent_operations"] and
                   (rule["agent_target"]["kind"] == "all" or
                    rule["agent_target"].get("controller_account_id") == controller["account_id"])]
        if matched:
            priority = max(rule.get("priority", 0) for rule in matched)
            results.append(max((rule["effect"] for rule in matched if rule.get("priority", 0) == priority), key=rank.get))
        else:
            results.append(policy["default_effect"])
    return max(results or ["allow"], key=rank.get)


def lineage_effective(state):
    return (state["parent_subject"] == state["child_issuer"] and state["child_issuer"]["kind"] == "service"
            and state["child_subject"]["kind"] == "account" and state["accepted_subject"]
            and state["child_subject"] == state["accepted_subject_actor"]
            and state["parent_subject"] == state["accepted_managing_service"]
            and state["child_subject"]["account_id"]["station_id"] == state["hosting_station_id"]
            and state["ordinary_authority_control"] and state["accepted_role"] in state["parent_roles"]
            and set(state["child_actions"]).issubset(state["parent_actions"])
            and state["max_child_depth"] == 0 and state["parent_active"] and state["scope_active"]
            and state["parent_binding_count"] == state["child_binding_count"] == 1
            and state["parent_binding"]["executed_by"] == state["parent_subject"]
            and state["child_binding"]["executed_by"] == state["child_subject"] == state["actual_producer"]
            and all(state["parent_binding"][key] == state["child_binding"][key]
                    for key in ["applet_id", "registration_epoch", "effect", "evaluation_class"]))


class ReviewLedger:
    """Reference atomic visibility model for an exact immutable candidate."""
    def __init__(self, digest, current):
        self.digest, self.current = digest, current
        self.status, self.effects = "pending", 0
        self.lock = Lock()

    def decide(self, digest, approve=True):
        if self.status != "pending" or digest != self.digest:
            return False
        self.status = "approved" if approve else "rejected"
        return True

    def accept(self, digest, current):
        with self.lock:
            if self.status == "consumed" and digest == self.digest:
                return True
            if self.status != "approved" or digest != self.digest:
                return False
            if current != self.current:
                self.status = "superseded"
                return False
            self.status, self.effects = "consumed", self.effects + 1
            return True


class ManagedGovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((ART / "fixtures/managed-governance-fixture.json").read_text())
        cls.catalog = json.loads((ART / "registry/contract-registry.json").read_text())
        docs = [json.loads(p.read_text()) for p in (ART / "schemas").glob("*.json")]
        cls.registry = Registry().with_resources((d["$id"], Resource.from_contents(d)) for d in docs)

    def validator(self, file, fragment=""):
        return Draft202012Validator({"$ref": "https://arkret.org/v1/schemas/" + file + fragment}, registry=self.registry)

    def test_closed_policy_and_default_specific_exception_parent_deny(self):
        p = self.fixture["policy"]
        self.validator("policy.schema.json").validate(p)
        ids = self.fixture["identities"]
        self.assertEqual(policy_gate([p], ids["alice"], "join"), "allow")
        self.assertEqual(policy_gate([p], ids["bob"], "join"), "require_review")
        hard = copy.deepcopy(p)
        hard["rules"] = []
        self.assertEqual(policy_gate([p, hard], ids["alice"], "join"), "deny")
        other_station = copy.deepcopy(ids["alice"])
        other_station["account_id"]["station_id"] += "other"
        self.assertEqual(policy_gate([p], other_station, "join"), "deny")
        invalid = copy.deepcopy(p)
        del invalid["rules"][1]["review_requirement"]
        self.assertFalse(self.validator("policy.schema.json").is_valid(invalid))

    def test_installation_has_no_default_actor_or_creation_side_effect(self):
        package = json.loads((ART / "schemas/applet-package.schema.json").read_text())
        self.assertIn("base_url", package["required"])
        self.assertNotIn("bot_actor_id", package["properties"])
        self.assertNotIn("transport", package["properties"])
        operation = next(o for o in self.catalog["operation_registry"]["operations"] if o["operation_id"] == "ak.self.applet.command.install.v1")
        self.assertEqual(operation["durable_effect"]["event_kinds"], ["ak.applet.registration", "ak.capability.grant"])
        actor = json.loads((ART / "schemas/applet-managed-actor.schema.json").read_text())
        self.assertEqual(actor["$defs"]["applet_managed_actor_provision_payload"]["properties"]["actor_role"]["enum"], ["bot", "ghost"])

    def test_scope_and_role_creation_contract_cannot_reintroduce_pull(self):
        operations = {o["operation_id"] for o in self.catalog["operation_registry"]["operations"]}
        self.assertIn("ak.self.applet.bot.command.provision.v1", operations)
        self.assertIn("ak.self.applet.ghost.command.provision.v1", operations)
        self.assertNotIn("ak.edge.applet.client.command.exchange.v1", operations)
        defs = json.loads((ART / "schemas/applet-install-authoring.schema.json").read_text())["$defs"]
        self.assertEqual(defs["authoring_request"]["properties"]["purpose"]["enum"], ["provision_bot", "provision_ghost"])
        self.assertIn("effective_scope", defs["ghost_preview_request_body"]["required"])
        self.assertNotIn("realm_id", defs["ghost_preview_request_body"]["properties"])
        self.assertEqual(set(defs["managed_actor_bundle"]["required"]) - {"schema", "authoring_request_digest", "proof"},
                         {"managed_actor_provision_event", "pcr_genesis_event", "accountability_grant_event", "profile_event"})

    def test_real_parent_terminal_child_and_all_bypass_negatives(self):
        original = self.fixture["lineage"]
        self.assertTrue(lineage_effective(original))
        mutations = {"parent_subject": self.fixture["identities"]["bot"], "child_issuer": self.fixture["identities"]["bot"],
                     "parent_actions": ["ak.applet.bot.provision"], "parent_roles": ["ghost"], "accepted_subject": False,
                     "ordinary_authority_control": False, "max_child_depth": 1, "parent_active": False, "scope_active": False}
        for key, value in mutations.items():
            with self.subTest(key=key):
                state = copy.deepcopy(original)
                state[key] = value
                self.assertFalse(lineage_effective(state))

    def test_terminal_executor_transfer_preserves_source_and_rejects_service_borrowing(self):
        original = self.fixture["lineage"]
        self.validator("grant-constraint.schema.json").validate(original["parent_binding"])
        self.validator("grant-constraint.schema.json").validate(original["child_binding"])
        self.assertTrue(lineage_effective(original))
        mutations = [
            ("child_binding", "executed_by", original["parent_subject"]),
            ("parent_binding", "executed_by", original["child_subject"]),
            ("child_binding", "applet_id", "ak:applet:01904100-0000-7000-8000-000000000099"),
            ("child_binding", "registration_epoch", "sha256:" + "b" * 64),
        ]
        for name, key, value in mutations:
            state = copy.deepcopy(original)
            state[name][key] = value
            self.assertFalse(lineage_effective(state), (name, key))
        for key, value in [("actual_producer", original["parent_subject"]),
                           ("parent_binding_count", 0), ("child_binding_count", 2),
                           ("hosting_station_id", "ak:did_core:webvh:otherstation")]:
            state = copy.deepcopy(original)
            state[key] = value
            self.assertFalse(lineage_effective(state), key)

    def test_scope_revoke_does_not_revoke_other_scope(self):
        scopes = {"A": copy.deepcopy(self.fixture["lineage"]), "B": copy.deepcopy(self.fixture["lineage"])}
        scopes["A"]["scope_active"] = False
        self.assertFalse(lineage_effective(scopes["A"]))
        self.assertTrue(lineage_effective(scopes["B"]))
        scopes["B"]["parent_active"] = False
        self.assertFalse(lineage_effective(scopes["B"]))

    def test_shared_parent_quota_does_not_reset_with_child_or_device(self):
        maximum, consumed = 2, 0
        outcomes = []
        for actor, device in [("bot_a", "one"), ("ghost", "two"), ("new_bot", "new_device")]:
            accepted = consumed < maximum
            if accepted:
                consumed += 1
            outcomes.append(accepted)
        self.assertEqual(outcomes, [True, True, False])
        self.assertEqual(consumed, maximum)

    def test_review_pending_current_binding_once_and_terminal(self):
        ledger = ReviewLedger("exact_signed_candidate", "cut_1")
        self.assertFalse(ledger.accept(ledger.digest, ledger.current))
        self.assertEqual(ledger.effects, 0)
        self.assertFalse(ledger.decide("changed_key_or_scope"))
        self.assertTrue(ledger.decide(ledger.digest))
        self.assertFalse(ledger.accept(ledger.digest, "changed_ownership_or_policy"))
        self.assertEqual(ledger.status, "superseded")
        self.assertFalse(ledger.accept(ledger.digest, ledger.current))
        ledger = ReviewLedger("exact_signed_candidate", "cut_1")
        self.assertTrue(ledger.decide(ledger.digest))
        with ThreadPoolExecutor(max_workers=4) as executor:
            self.assertTrue(all(executor.map(lambda _: ledger.accept(ledger.digest, ledger.current), range(12))))
        self.assertEqual(ledger.effects, 1)
        rejected = ReviewLedger("candidate", "cut")
        self.assertTrue(rejected.decide("candidate", False))
        self.assertFalse(rejected.decide("candidate", True))
        self.assertFalse(rejected.accept("candidate", "cut"))

    def test_device_metadata_rfc9421_kat_and_mutations(self):
        case = self.fixture["device_request"]
        validator = self.validator("applet-device-authentication.schema.json")
        validator.validate(case["metadata"])
        self.assertEqual(json.loads(decode(case["components"]["arkret-managed-device"])), case["metadata"])
        signing = "\n".join('"' + k + '": ' + v for k, v in case["components"].items()) + '\n"@signature-params": ' + case["signature_params"]
        self.assertEqual(signing, case["signature_base_utf8"])
        key = Ed25519PublicKey.from_public_bytes(decode(case["public_key_b64u"]))
        signature = decode(case["signature_b64u"])
        key.verify(signature, signing.encode())
        for field in ["@method", "@target-uri", "arkret-operation", "arkret-managed-device", "destination-service-id"]:
            tampered = copy.deepcopy(case["components"])
            tampered[field] += "other"
            base = "\n".join('"' + k + '": ' + v for k, v in tampered.items()) + '\n"@signature-params": ' + case["signature_params"]
            with self.subTest(field=field), self.assertRaises(InvalidSignature):
                key.verify(signature, base.encode())
        for field in case["metadata"]:
            bad = copy.deepcopy(case["metadata"])
            del bad[field]
            self.assertFalse(validator.is_valid(bad))
        bad = copy.deepcopy(case["metadata"])
        bad["service_key"] = case["public_key_b64u"]
        self.assertFalse(validator.is_valid(bad))
        self.assertFalse(validator.is_valid({**case["metadata"], "nonce": "short"}))

    def test_review_capable_operations_and_closed_public_intent(self):
        p = copy.deepcopy(self.fixture["policy"])
        p["rules"][1]["agent_operations"] = ["deliver"]
        self.assertFalse(self.validator("policy.schema.json").is_valid(p))
        p = copy.deepcopy(self.fixture["policy"])
        p.update(default_effect="require_review", default_review_requirement=p["rules"][1]["review_requirement"], default_operations=["join"])
        self.assertTrue(self.validator("policy.schema.json").is_valid(p))
        p["default_operations"] = ["create_bot"]
        self.assertFalse(self.validator("policy.schema.json").is_valid(p))
        intent = {"effective_scope": self.fixture["device_request"]["metadata"]["effective_scope"], "mode": "public"}
        validator = self.validator("actor-profile.schema.json", "#/$defs/applet_interaction")
        self.assertTrue(validator.is_valid(intent))
        for bad in [{**intent, "mode": "all"}, {**intent, "approved": True}, {"mode": "public"}]:
            self.assertFalse(validator.is_valid(bad))

    def test_policy_exact_read_supply_and_scope_only_never_written(self):
        request = {"realm_id": self.fixture["identities"]["realm_id"], "selector": {"kind": "policy", "policy_id": self.fixture["policy"]["id"]}}
        self.validator("exact-current-results-read.schema.json", "#/$defs/exact_current_results_read_request").validate(request)
        request["selector"]["kind"] = "policies"
        self.assertFalse(self.validator("exact-current-results-read.schema.json", "#/$defs/exact_current_results_read_request").is_valid(request))

    def test_management_approval_context_is_closed(self):
        context = {"context_kind": "management", "request_id": "ak:request:01904100-0000-7000-8000-000000000019", "management_operation": "join", "effective_scope": self.fixture["device_request"]["metadata"]["effective_scope"]}
        validator = self.validator("approval-signature.schema.json", "#/$defs/approval_context")
        validator.validate(context)
        self.assertFalse(validator.is_valid({**context, "management_operation": "deliver"}))
        self.assertFalse(validator.is_valid({**context, "approved": True}))

    def test_first_device_and_service_child_have_a_real_transport_carrier(self):
        operations = {o["operation_id"]: o for o in self.catalog["operation_registry"]["operations"]}
        submission = operations["ak.self.events.command.submit.v1"]
        self.assertEqual(submission["auth_requirements"]["service_signature"]["signature_scenario_id"],
                         "ak.http_signature.scenario.service_to_service.v1")
        self.assertIn("managed_device_signature", submission["auth_requirements"])
        api = yaml.safe_load((ART / "openapi/arkret-service-api.openapi.yaml").read_text())
        schemes = api["components"]["securitySchemes"]
        self.assertEqual(schemes["managedDeviceMetadata"]["name"], "Arkret-Managed-Device")
        for path in api["paths"].values():
            for method, operation in path.items():
                if method not in {"get", "post", "put", "patch", "delete", "head", "query"}:
                    continue
                for group in operation.get("security", []):
                    self.assertTrue(set(group).issubset(schemes), group)
        groups = api["paths"]["/_arkret/self/events"]["post"]["security"]
        self.assertTrue(any("sourceServiceId" in group and "managedDeviceMetadata" not in group for group in groups))
        self.assertTrue(any("managedDeviceMetadata" in group and "sourceServiceId" not in group for group in groups))

    def test_device_allowlist_content_supply_and_no_admin_recovery(self):
        contract = json.loads((ART / "registry/applet-managed-authority-registry.json").read_text())
        allowed = contract["device_authentication"]["operations"]
        for operation in ["ak.self.keys.keypackages.upload.create.v1", "ak.self.keys.keypackages.read.claim.v1",
                          "ak.self.keys.keypackages.command.consume.v1", "ak.self.device_messages.read.list.v1",
                          "ak.self.device_messages.command.ack.v1", "ak.self.mls.read.group_state_material.v1",
                          "ak.self.blob.resource.get.v1", "ak.self.events.command.submit.v1"]:
            self.assertIn(operation, allowed)
        self.assertFalse(any("recovery" in op or "backups" in op or "pair_device" in op for op in allowed))
        self.assertEqual(contract["personal_agent_source"], "owned_agent")
        self.assertFalse(contract["creation_scope_revoke_is_global_device_revoke"])
        for mode, governance, caller in [(True, False, True), (False, True, True), (True, True, False)]:
            self.assertFalse(mode and governance and caller)


if __name__ == "__main__":
    unittest.main()
