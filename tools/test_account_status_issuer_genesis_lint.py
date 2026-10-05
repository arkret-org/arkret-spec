"""Mutation tests for the Account Authority issuer-ledger genesis contract."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import account_status_issuer as gate


def _fixture() -> dict:
    return json.loads(gate.FIXTURE_PATH.read_text(encoding="utf-8"))


class AccountStatusIssuerGenesisLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.body = _fixture()
        self.real_load_json = gate.load_json

    def tearDown(self) -> None:
        gate.load_json = self.real_load_json

    def run_gate(self, body: dict) -> list[str]:
        gate.load_json = (
            lambda lint, path: body
            if path == gate.FIXTURE_PATH
            else self.real_load_json(lint, path)
        )
        lint = gate.Lint()
        gate.check_account_status_issuer_genesis(lint)
        return list(lint.errors)

    def point(self, body: dict) -> dict:
        return body["security_evidence"][0]["decision_points"][0]

    def test_committed_fixture_passes(self) -> None:
        self.assertEqual(self.run_gate(self.body), [])

    def test_station_checkpoint_wait_turns_the_gate_red(self) -> None:
        body = copy.deepcopy(self.body)
        body["genesis_rules"]["waits_for_station_checkpoint"] = True
        self.assertTrue(
            any("waits_for_station_checkpoint" in error for error in self.run_gate(body))
        )

    def test_realm_commit_wait_turns_the_gate_red(self) -> None:
        body = copy.deepcopy(self.body)
        body["genesis_rules"]["waits_for_realm_commit"] = True
        self.assertTrue(any("waits_for_realm_commit" in error for error in self.run_gate(body)))

    def test_reversed_requirement_turns_the_gate_red(self) -> None:
        body = copy.deepcopy(self.body)
        self.point(body)["requirement"] = (
            "The genesis record waits for the Station checkpoint and the RealmCommit."
        )
        self.assertTrue(any("no-wait contract" in error for error in self.run_gate(body)))

    def test_wrong_evidence_pointer_turns_the_gate_red(self) -> None:
        body = copy.deepcopy(self.body)
        self.point(body)["evidence"] = ["/ledger"]
        self.assertTrue(any("evidence must be exactly" in error for error in self.run_gate(body)))

    def test_runner_wires_the_gate(self) -> None:
        source = (ROOT / "tools" / "artifact_lint" / "runner.py").read_text(encoding="utf-8")
        self.assertIn("check_account_status_issuer_genesis(lint)", source)

    def test_gate_unsigned_core_digest_substitution_is_rejected(self):
        body = copy.deepcopy(self.body)
        case = body["controller_gate_basis_contract"]["cases"][2]
        case["gate"]["basis"]["status_record_digest"] = case["private_current_record"]["proof"]["payload_digest"]
        self.assertTrue(self.run_gate(body))

    def test_successor_active_may_not_restore_binding_default(self):
        body = copy.deepcopy(self.body)
        cases = body["controller_gate_basis_contract"]["cases"]
        cases[1]["gate"]["basis"] = copy.deepcopy(cases[0]["gate"]["basis"])
        self.assertTrue(self.run_gate(body))

    def test_actual_signed_record_or_gate_leaf_mutations_are_rejected(self):
        from tools.regenerate_controller_gate_basis_fixture import verify_case
        mutations = [
            lambda c: c["private_current_record"].__setitem__("binding_version", 2),
            lambda c: c["private_current_record"]["account_id"].__setitem__("station_id", "ak:did_core:webvh:zOtherStation"),
            lambda c: c["private_current_record"].__setitem__("principal_control_realm_id", "ak:realm:" + "A"*44),
            lambda c: c["private_current_record"]["proof"].__setitem__("jws", c["private_predecessor"]["proof"]["jws"]),
            lambda c: c["gate"].__setitem__("eligibility", "active"),
            lambda c: c["gate"]["basis"].__setitem__("status_record_digest", "sha256:" + "0"*64),
            lambda c: c["gate"]["basis"].__setitem__("account_status_record_id", c["private_predecessor"]["account_status_record_id"]),
            lambda c: c["gate"]["proof"].__setitem__("jws", c["private_current_record"]["proof"]["jws"]),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                case = copy.deepcopy(self.body["controller_gate_basis_contract"]["cases"][2])
                mutation(case)
                with self.assertRaises(Exception):
                    verify_case(case)

    def test_gate_schema_accepts_original_six_statuses_and_rejects_old_or_private_fields(self):
        import jsonschema
        root = ROOT / "spec/v1/artifacts/schemas"
        schema = json.loads((root / "agent-authority-evidence.schema.json").read_text())
        store = {(root/name).resolve().as_uri(): json.loads((root/name).read_text()) for name in ["agent-authority-evidence.schema.json", "common-ids.schema.json", "account-operations.schema.json", "string-profiles.schema.json"]}
        resolver = jsonschema.RefResolver(base_uri=(root/"agent-authority-evidence.schema.json").resolve().as_uri(), referrer=schema, store=store)
        v = jsonschema.Draft202012Validator(schema["$defs"]["controller_account_gate_attestation"], resolver=resolver)
        cases = self.body["controller_gate_basis_contract"]["cases"]
        for case in cases:
            v.validate(case["gate"])
        base = cases[2]["gate"]
        bad = [
            {"kind": "account_status_event", "status_event_id": "ak:event:"+"A"*44, "status_checkpoint_digest": "sha256:"+"b"*64},
            dict(base["basis"], account_status_record_id="ak:event:"+"A"*44),
            dict(base["basis"], status_record_digest="blake3:"+"b"*64),
            dict(base["basis"], status_record_digest=None),
            dict(base["basis"], status_seq=2),
            dict(base["basis"], account_id=cases[2]["private_current_record"]["account_id"]),
            dict(base["basis"], principal_control_realm_id=cases[2]["private_current_record"]["principal_control_realm_id"]),
            dict(base["basis"], record=cases[2]["private_current_record"]),
        ]
        for basis in bad:
            body=copy.deepcopy(base); body["basis"]=basis
            self.assertTrue(list(v.iter_errors(body)))

    def test_binding_default_inactive_schema_is_rejected(self):
        import jsonschema
        root=ROOT / "spec/v1/artifacts/schemas"
        schema=json.loads((root/"agent-authority-evidence.schema.json").read_text())
        resolver=jsonschema.RefResolver(base_uri=(root/"agent-authority-evidence.schema.json").resolve().as_uri(),referrer=schema)
        validator=jsonschema.Draft202012Validator(schema["$defs"]["controller_account_gate_attestation"],resolver=resolver)
        gate=copy.deepcopy(self.body["controller_gate_basis_contract"]["cases"][0]["gate"])
        gate["status"]="locked"; gate["eligibility"]="inactive"
        self.assertTrue(list(validator.iter_errors(gate)))

    def test_true_resigned_other_binding_record_is_not_the_current_binding(self):
        from tools.regenerate_controller_gate_basis_fixture import record, verify_case, digest, jws, gate_bytes, basis_digest_for_gate
        case=copy.deepcopy(self.body["controller_gate_basis_contract"]["cases"][2])
        changed=copy.deepcopy(case["private_current_record"]); changed["binding_version"]+=1
        changed=record(changed,2,"soft_logged_out",case["private_predecessor"])
        case["private_current_record"]=changed
        case["gate"]["basis"]={"kind":"account_status_record","account_status_record_id":changed["account_status_record_id"],"status_record_digest":digest(changed)}
        case["gate"]["basis_digest"]=basis_digest_for_gate(case["gate"])
        case["gate"]["proof"]["jws"]=jws(gate_bytes(case["gate"]))
        with self.assertRaisesRegex(ValueError,"complete private binding"):
            verify_case(case)

    def test_stable_default_source_decisions_cover_absence_and_complete_initial_tuple(self):
        from tools.regenerate_controller_gate_basis_fixture import default_allowed
        decisions=self.body["controller_gate_basis_contract"]["default_decisions"]
        self.assertEqual(len(decisions),8)
        for decision in decisions:
            self.assertIs(default_allowed(decision["binding"],decision["head"],decision["user_active"]),decision["allowed"])
        body=copy.deepcopy(self.body)
        body["controller_gate_basis_contract"]["default_decisions"][3]["allowed"]=True
        self.assertTrue(self.run_gate(body))

    def test_true_resigned_gate_with_old_basis_only_digest_is_rejected(self):
        from tools.regenerate_controller_gate_basis_fixture import verify_case, digest, jws, gate_bytes, verify_jws
        case=copy.deepcopy(self.body["controller_gate_basis_contract"]["cases"][2])
        case["gate"]["basis_digest"]=digest(case["gate"]["basis"])
        case["gate"]["proof"]["jws"]=jws(gate_bytes(case["gate"]))
        verify_jws(case["gate"]["proof"]["jws"],gate_bytes(case["gate"]))
        with self.assertRaisesRegex(ValueError,"basis digest"):
            verify_case(case)

    def test_true_resigned_gate_with_other_accepted_id_projection_is_rejected(self):
        from tools.regenerate_controller_gate_basis_fixture import verify_case, digest, jws, gate_bytes, verify_jws
        case=copy.deepcopy(self.body["controller_gate_basis_contract"]["cases"][2]);gate=case["gate"]
        gate["basis_digest"]=digest({"principal_id":gate["principal_id"],"accepted_id":"ak:did_core:webvh:zOtherStation","status":gate["status"],"basis":gate["basis"]})
        gate["proof"]["jws"]=jws(gate_bytes(gate))
        verify_jws(gate["proof"]["jws"],gate_bytes(gate))
        with self.assertRaisesRegex(ValueError,"basis digest"):
            verify_case(case)


if __name__ == "__main__":
    unittest.main()
