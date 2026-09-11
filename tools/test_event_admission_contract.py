"""Executable admission-selector, complete-Event and frozen-finality contracts.

These are specification checks, not signed server-admission or MLS integration
tests. Full Event vectors exercise schema; finality vectors exercise the explicit
authorization/finality decision table after its stated cryptographic prechecks.
"""

import copy
import itertools
import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.event_admission_contract import predicate_schema, schema_definitions, selected_branches, synchronize

ARTIFACTS = ROOT / "spec/v1/artifacts"


def read(path):
    return json.loads((ARTIFACTS / path).read_text(encoding="utf-8"))


class EventAdmissionContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = read("registry/contract-registry.json")["event_kind_registry"]
        cls.envelope = read("schemas/event-envelope.schema.json")
        resources = []
        for path in (ARTIFACTS / "schemas").glob("*.json"):
            doc = json.loads(path.read_text(encoding="utf-8"))
            resource = Resource.from_contents(doc)
            resources.extend([(doc.get("$id", path.as_uri()), resource), (path.as_uri(), resource)])
        cls.resources = Registry().with_resources(resources)

    def test_projection_matches_canonical_and_is_reachable(self):
        synchronize(ROOT, check=True)
        Draft202012Validator.check_schema(self.envelope)

    def test_zero_ref_count_matches_absence_but_positive_count_does_not(self):
        for count in [0, 1]:
            validator = Draft202012Validator(predicate_schema({"ref_role": "did_inception", "ref_exact_count": count}))
            self.assertEqual(validator.is_valid({}), count == 0)
            self.assertEqual(validator.is_valid({"refs": []}), count == 0)
            self.assertEqual(validator.is_valid({"refs": [{"role": "did_inception"}]}), count == 1)

    def test_negative_payload_selector_covers_absent_path(self):
        validator = Draft202012Validator(predicate_schema({"payload_path": "object.purpose", "not_const": "agent_control"}))
        self.assertTrue(validator.is_valid({}))
        self.assertFalse(validator.is_valid({"payload": {"object": {"purpose": "agent_control"}}}))

    def test_overlapping_native_and_capability_branches_both_fail_closed(self):
        row = {"admission": "conditional", "admission_variants": [
            {"when": {"top_level_fields_present": ["executed_by"]}, "admission": "self_authored_proof"},
            {"when": {"top_level_fields_present": ["authorization_ref"]}, "admission": "capability_gated"},
            {"when": {"otherwise": True}, "admission": "deny"},
        ]}
        event = {"executed_by": {}, "authorization_ref": "ref"}
        self.assertFalse(any(Draft202012Validator(guard).is_valid(event) for admission, guard in selected_branches(row) if admission != "deny"))

    def test_all_native_exception_classes_have_positive_selector_coverage(self):
        definitions = schema_definitions(self.canonical)
        history = copy.deepcopy(definitions["shared_history_event"])
        history["allOf"].pop(0)  # Selector test only; complete Events are tested below.
        validator = Draft202012Validator(history)
        classes = self.canonical["history_admission_contract"]["without_station_admission"]["selected_native_admission"]["admission_classes"]
        covered = set()
        for row in self.canonical["event_kinds"]:
            if row.get("wire_scope") != "durable_event":
                continue
            variants = row.get("admission_variants", [{"admission": row.get("admission"), "when": {}}])
            for variant in variants:
                if variant["admission"] not in classes or variant["when"].get("otherwise"):
                    continue
                event = {"kind": row["event_kind"], "proofs": [{"signer_resolution_evidence_ref": "fixture"}]}
                when = variant["when"]
                if "payload_path" in when:
                    target = event.setdefault("payload", {})
                    parts = when["payload_path"].split(".")
                    for part in parts[:-1]:
                        target = target.setdefault(part, {})
                    target[parts[-1]] = when["const"]
                for field in when.get("top_level_fields_present", []):
                    event[field] = "fixture"
                if "ref_role" in when and when.get("ref_exact_count", 1):
                    event["refs"] = [{"role": when["ref_role"], "critical": when.get("ref_critical", True)}]
                self.assertTrue(validator.is_valid(event), (row["event_kind"], variant))
                covered.add(variant["admission"])
        self.assertEqual(covered, set(classes))

    def test_complete_event_fixture_matrix(self):
        instances = {}
        tested = 0
        for case in read("fixtures/schema-validation-fixture.json")["schema_validation_cases"]:
            instance = copy.deepcopy(case.get("instance"))
            if instance is None and case.get("instance_from") in instances:
                instance = copy.deepcopy(instances[case["instance_from"]])
                for mutation in case["mutations"]:
                    path = mutation["path"].strip("/").split("/")
                    target = instance
                    for key in path[:-1]:
                        target = target[key]
                    if mutation["op"] == "remove":
                        del target[path[-1]]
                    else:
                        target[path[-1]] = mutation["value"]
            if instance is not None:
                instances[case["name"]] = instance
            if not case["name"].startswith(("agent_genesis_", "event_envelope_policy_reanchor_", "event_envelope_causal_recovery_", "event_envelope_recovery_", "event_federation_", "shared_history_")):
                continue
            schema_ref = "https://arkret.org/v1/" + case["schema_ref"]
            validator = Draft202012Validator({"$ref": schema_ref}, registry=self.resources)
            self.assertEqual(validator.is_valid(instance), case["expect_valid"], case["name"])
            tested += 1
        self.assertGreaterEqual(tested, 18)

    def test_control_finality_ignores_current_receiver_state_and_origin_proof(self):
        contract = self.canonical["history_admission_contract"]["control_history_evaluation"]
        for rule in contract["rules"]:
            self.assertLessEqual(set(rule["when"]), set(contract["allowed_inputs"]))
            self.assertFalse(set(rule["when"]) & set(contract["forbidden_inputs"]))
        for case in read("fixtures/station-admission-fixture.json")["control_finality_cases"]:
            for barrier, origin in itertools.product([False, True], repeat=2):
                state = dict(case, receiver_current_barrier=barrier, origin_admission_proof_present=origin)
                matches = [r["result"] for r in contract["rules"] if all(state[k] == v for k, v in r["when"].items())]
                self.assertEqual(matches, [case["expected"]], case["name"])

    def test_native_history_cannot_omit_original_signer_evidence(self):
        case = next(c for c in read("fixtures/schema-validation-fixture.json")["schema_validation_cases"]
                    if c["name"] == "shared_history_policy_recovery_without_station_admission_shape_valid")
        event = copy.deepcopy(case["instance"])
        del event["proofs"][0]["signer_resolution_evidence_ref"]
        validator = Draft202012Validator(
            {"$ref": self.envelope["$id"] + "#/$defs/shared_history_event"}, registry=self.resources
        )
        self.assertFalse(validator.is_valid(event))

    def test_capability_class_cannot_be_added_to_native_exceptions(self):
        registry = copy.deepcopy(self.canonical)
        registry["history_admission_contract"]["without_station_admission"]["selected_native_admission"]["admission_classes"].append("capability_gated")
        with self.assertRaises(ValueError):
            schema_definitions(registry)


if __name__ == "__main__":
    unittest.main()
