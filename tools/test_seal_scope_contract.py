"""Structural conformance for independent admission and scoped execution.

These tests validate schemas, canonical contracts, and signature transcripts.
They do not implement a production reducer or prove BFT liveness.
"""
from __future__ import annotations

import copy
import base64
import itertools
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from cryptography.exceptions import InvalidSignature
from tools.artifact_lint.core import canonical_json

from tools.event_execution_contract import condition_guard, schema_definition

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "spec/v1/artifacts"


def read(relative):
    return json.loads((ARTIFACTS / relative).read_text(encoding="utf-8"))


class SealScopeContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = read("registry/contract-registry.json")
        cls.events = cls.catalog["event_kind_registry"]
        resources = []
        for path in (ARTIFACTS / "schemas").glob("*.json"):
            doc = json.loads(path.read_text(encoding="utf-8"))
            resources.append((doc["$id"], Resource.from_contents(doc)))
        cls.resources = Registry().with_resources(resources)
        cls.execution = Draft202012Validator(schema_definition(cls.events))
        cls.envelope = cls.validator("event-envelope.schema.json#/$defs/shared_history_event")
        cases = read("fixtures/schema-validation-fixture.json")["schema_validation_cases"]
        cls.message = copy.deepcopy(next(c["instance"] for c in cases
            if c["name"] == "shared_history_portable_capability_message_valid"))
        cls.message["proofs"][0]["signer_resolution_evidence_ref"] = "ak:signer_evidence:sha256:" + "e" * 64

    @classmethod
    def validator(cls, schema):
        return Draft202012Validator({"$ref": "https://arkret.org/v1/schemas/" + schema}, registry=cls.resources)

    def assert_shape(self, validator, instance, expected):
        errors = list(validator.iter_errors(instance))
        self.assertEqual(not errors, expected, [e.message for e in errors])

    def test_shared_chat_needs_no_new_seal_or_origin_proof(self):
        self.assert_shape(self.envelope, self.message, True)
        self.assertNotIn("seal_ref", self.message)
        self.assertNotIn("seal_basis", self.message)
        self.assertEqual(len(self.message["proofs"]), 1)

    def test_secret_release_cannot_be_admitted_as_ordinary_data(self):
        shape = {"kind": "ak.audit.release", "payload": {}}
        self.assert_shape(self.execution, shape, False)
        shape["seal_basis"] = {"leaves": ["ak:seal:sha256:" + "a" * 64]}
        self.assert_shape(self.execution, shape, True)
        contract = self.events["cell_contracts"]["ak.audit.release"]
        self.assertTrue(all(w["execution"] == "security" and w["state_model"] == "sequenced_state"
                            for w in contract["cell_writes"]))

    def test_proof_authenticated_submission_needs_no_session(self):
        validator = self.validator("service-operation-dtos.schema.json#/$defs/ProofAuthenticatedPublication")
        self.assert_shape(validator, {"event": self.message}, True)
        item = {"event": copy.deepcopy(self.message)}
        item["event"]["seal_basis"] = {"leaves": self.message["auth_context"]["authority_refs"]}
        self.assert_shape(validator, item, False)
        self.assert_shape(validator, {"events": [{"event": self.message}]}, False)

    def test_producer_evidence_is_not_optional(self):
        message = copy.deepcopy(self.message)
        del message["proofs"][0]["signer_resolution_evidence_ref"]
        self.assert_shape(self.envelope, message, False)

    def test_extra_service_proof_is_rejected(self):
        message = copy.deepcopy(self.message)
        message["proofs"].append(copy.deepcopy(message["proofs"][0]))
        self.assert_shape(self.envelope, message, False)

    def test_chat_cannot_carry_safety_basis_or_retired_root_anchor(self):
        for key, value in [("seal_basis", {"leaves": self.message["auth_context"]["authority_refs"]}),
                           ("seal_ref", self.message["auth_context"]["authority_refs"][0])]:
            with self.subTest(key=key):
                message = copy.deepcopy(self.message)
                message[key] = value
                self.assert_shape(self.envelope, message, False)

    def test_missing_authority_context_is_rejected(self):
        for key in ["auth_context", "authority_refs"]:
            message = copy.deepcopy(self.message)
            if key == "auth_context":
                del message[key]
            else:
                del message["auth_context"][key]
            self.assert_shape(self.envelope, message, False)

    def test_space_appearance_and_child_policy_select_different_execution(self):
        appearance = {"kind": "ak.space.update", "payload": {"patch": {"title": "x"}},
                      "auth_context": {}, "causal_refs": ["base"]}
        policy = {"kind": "ak.space.update", "payload": {"child_scope_policy": {}}, "seal_basis": {}}
        self.assert_shape(self.execution, appearance, True)
        self.assert_shape(self.execution, policy, True)
        for source in [appearance, policy]:
            changed = copy.deepcopy(source)
            changed["seal_basis" if "auth_context" in changed else "auth_context"] = {}
            self.assert_shape(self.execution, changed, False)

    def test_empty_conditional_update_has_no_effect(self):
        self.assert_shape(self.execution, {"kind": "ak.space.update", "payload": {}, "auth_context": {}}, False)

    def test_capture_outcome_does_not_reopen_capture_authority(self):
        outcome = {"kind": "ak.call.state", "payload": {"recording_transition": {"to": "ready", "result": {}}}, "auth_context": {}}
        stop = {"kind": "ak.call.state", "payload": {"recording_transition": {"to": "stopped"}}, "seal_basis": {}}
        self.assert_shape(self.execution, outcome, True)
        self.assert_shape(self.execution, stop, True)
        del stop["seal_basis"]
        stop["auth_context"] = {}
        self.assert_shape(self.execution, stop, False)

    def test_capture_result_requires_confirmed_stop_reference(self):
        validator = self.validator("event-payload.schema.json#/$defs/call_state_payload/properties/transcript_transition")
        item = {"recording_id": "segment", "from": "stopped", "to": "failed", "result": {"transcript_stop_event_id": self.message["event_id"]}}
        self.assert_shape(validator, item, True)
        item["from"] = "transcribing"
        self.assert_shape(validator, item, False)
        item["from"] = "stopped"
        del item["result"]["transcript_stop_event_id"]
        self.assert_shape(validator, item, False)

    def test_closed_model_catalog_and_family_consistency(self):
        models = {"causal_register", "sequenced_state", "or_set", "ordered_log", "counter"}
        self.assertEqual(set(self.catalog["state_model_contracts"]), models)
        families = {}
        for contract in self.events["cell_contracts"].values():
            for write in contract["cell_writes"]:
                self.assertIn(write["state_model"], models)
                self.assertEqual(write["execution"] == "security", write["state_model"] == "sequenced_state")
                shape = (write["execution"], write["state_model"], write["value_shape"])
                self.assertEqual(families.setdefault(write["cell_family"], shape), shape)
                if write["execution"] == "security":
                    self.assertNotIn("bottom", write)

    def test_unknown_execution_condition_is_rejected(self):
        with self.assertRaises(ValueError):
            condition_guard({"kind": "receiver_now", "field": "payload.time"})

    def test_presence_selectors_handle_missing_nested_paths(self):
        for path in ["payload.a", "payload.a.b"]:
            present = Draft202012Validator(condition_guard({"kind": "field_present", "field": path}))
            absent = Draft202012Validator(condition_guard({"kind": "field_absent", "field": path}))
            for payload in [{}, {"a": {}}, {"a": {"b": None}}]:
                value = {"payload": payload}
                self.assertNotEqual(present.is_valid(value), absent.is_valid(value))

    def test_seal_identity_is_independent_of_certificate_view(self):
        schema = read("schemas/seal.schema.json")
        self.assertNotIn("view", schema["properties"])
        self.assertIn("view", schema["$defs"]["multi_signature"]["required"])
        unsigned = schema["$defs"]["unsigned_seal"]
        self.assertEqual(set(unsigned["properties"]), set(schema["properties"]) - {"id", "notary_signature"})
        self.assertEqual(schema["properties"]["predecessor_refs"]["maxItems"], 1)
        self.assertNotIn("data_view_root", schema["properties"])

    def test_snapshot_causal_state_requires_coverage(self):
        validator = self.validator("realm-state-snapshot-chunk.schema.json#/$defs/heads_state")
        state = {"heads": [{"event_id": self.message["event_id"], "value": None}]}
        self.assert_shape(validator, state, False)
        state["covered_event_ids"] = [self.message["event_id"]]
        self.assert_shape(validator, state, True)

    def test_single_use_approval_requires_security_confirmation_and_exact_publication(self):
        approval = copy.deepcopy(self.message)
        approval['kind'] = 'ak.agent.action_approve'
        approval.pop('auth_context')
        approval['seal_basis'] = {'leaves': ['ak:seal:sha256:' + 'a' * 64]}
        approval['payload'] = {
            'approval_id': 'approval-test', 'agent_id': 'ak:did_core:key:z6MkTestAgent',
            'proposed_action': 'ak.message.send',
            'target': {'kind': 'realm', 'realm_id': approval['realm_id']},
            'approved_event_id': self.message['event_id'],
            'approval_nonce': 'a' * 22,
            'approved_at': '2026-09-12T00:00:00.000Z', 'expires_at': '2026-09-12T00:05:00.000Z',
        }
        self.assert_shape(self.execution, approval, True)
        self.assert_shape(self.envelope, approval, True)
        wrapper = self.validator('service-operation-dtos.schema.json#/$defs/EventInitialSubmission')
        self.assert_shape(wrapper, {'event': approval}, False)
        self.assert_shape(wrapper, {'event': approval, 'publication_event': self.message}, True)
        approval.pop('seal_basis')
        approval['auth_context'] = self.message['auth_context']
        self.assert_shape(self.execution, approval, False)

    def test_commit_signature_cannot_cross_phase_view_or_configuration(self):
        vector = next(v for v in read('fixtures/cbs-lattice-fixture.json')['vectors']
                      if v['name'] == 'seal_canonical_no_self_reference')
        proof = vector['certificate']['signatures'][0]
        header, _, signature = proof['jws'].split('.')
        seed = base64.urlsafe_b64decode(vector['test_key']['private_key_seed'] + '=')
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        key = Ed25519PrivateKey.from_private_bytes(seed).public_key()
        def verify(transcript):
            payload = base64.urlsafe_b64encode(canonical_json(transcript).encode()).rstrip(b'=').decode()
            key.verify(base64.urlsafe_b64decode(signature + '=='), (header + '.' + payload).encode())
        verify(vector['commit_transcript'])
        for field, value in [('context', 'ak.seal.prepare.v1'), ('view', 1),
                             ('configuration_ref', self.message['event_id'])]:
            transcript = dict(vector['commit_transcript'], **{field: value})
            with self.assertRaises(InvalidSignature):
                verify(transcript)

    def test_view_change_wire_rejects_extra_fields_and_unknown_phase(self):
        vote = self.validator('seal.schema.json#/$defs/vote_transcript')
        vector = next(v for v in read('fixtures/cbs-lattice-fixture.json')['vectors']
                      if v['name'] == 'seal_canonical_no_self_reference')
        self.assert_shape(vote, vector['commit_transcript'], True)
        self.assert_shape(vote, dict(vector['commit_transcript'], context='ak.seal.unknown.v1'), False)
        self.assert_shape(vote, dict(vector['commit_transcript'], receiver_order=1), False)

    def test_causal_join_retains_distinct_same_value_heads_and_coverage(self):
        def join(a, b):
            ca, ha = a
            cb, hb = b
            return ca | cb, (ha & hb) | (ha - cb) | (hb - ca)
        states = [(frozenset(), frozenset()), (frozenset({"a"}), frozenset({"a"})),
                  (frozenset({"b"}), frozenset({"b"})),
                  (frozenset({"a", "c"}), frozenset({"c"}))]
        self.assertEqual(join(states[1], states[2])[1], {"a", "b"})
        self.assertEqual(join(states[1], states[3])[1], {"c"})
        for a, b, c in itertools.product(states, repeat=3):
            self.assertEqual(join(a, a), a)
            self.assertEqual(join(a, b), join(b, a))
            self.assertEqual(join(join(a, b), c), join(a, join(b, c)))


class CausalConvergenceModelTest(unittest.TestCase):
    """Bounded algebra checks independent of schema generation or production code."""
    writes = {"a": set(), "b": set(), "c": {"a"}, "d": {"a", "b", "c"}}

    @classmethod
    def oracle(cls, events):
        covered = set(events)
        suppressed = set().union(*(cls.writes[e] for e in events)) if events else set()
        return covered, covered - suppressed

    @staticmethod
    def merge(left, right):
        c1, h1 = left
        c2, h2 = right
        return c1 | c2, (h1 & h2) | (h1 - c2) | (h2 - c1)

    def test_all_causally_complete_replica_subsets_agree_with_history_oracle(self):
        subsets = [set(xs) for n in range(5) for xs in itertools.combinations(self.writes, n)]
        subsets = [xs for xs in subsets if all(self.writes[e] <= xs for e in xs)]
        for a, b, c in itertools.product(subsets, repeat=3):
            sa, sb, sc = map(self.oracle, (a, b, c))
            self.assertEqual(self.merge(sa, sa), sa)
            self.assertEqual(self.merge(sa, sb), self.merge(sb, sa))
            self.assertEqual(self.merge(self.merge(sa, sb), sc), self.merge(sa, self.merge(sb, sc)))
            self.assertEqual(self.merge(self.merge(sa, sb), sc), self.oracle(a | b | c))

    def test_partial_observation_keeps_unseen_branch(self):
        self.assertEqual(self.oracle({"a", "b", "c"})[1], {"b", "c"})

    def test_revoked_write_loses_coverage_authority(self):
        self.assertEqual(self.oracle({"a", "c"})[1], {"c"})
        self.assertEqual(self.oracle({"a"})[1], {"a"})

    def test_equal_values_do_not_collapse_identities(self):
        values = {"a": None, "b": None}
        heads = self.oracle(set(values))[1]
        self.assertEqual(len(heads), 2)
        self.assertNotEqual(self.oracle(set()), self.oracle({"a"}))

    def test_closure_intersection_is_order_independent(self):
        cuts = [{"a", "b", "c"}, {"a", "b"}, {"a", "c"}]
        for order in itertools.permutations(cuts):
            self.assertEqual(set.intersection(*order), {"a"})

    def test_safety_revision_detects_aba(self):
        state = {"revision": "r0", "value": None}
        outcomes = []
        for event, revision, value in [("r1", "r0", "occupied"), ("r2", "r1", None), ("r3", "r0", "other")]:
            if revision != state["revision"]:
                outcomes.append("rejected")
            else:
                state = {"revision": event, "value": value}
                outcomes.append("committed")
        self.assertEqual(outcomes, ["committed", "committed", "rejected"])
        self.assertEqual(state, {"revision": "r2", "value": None})


if __name__ == "__main__":
    unittest.main()
