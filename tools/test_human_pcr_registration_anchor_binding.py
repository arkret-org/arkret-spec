"""Mutation tests for the human PCR `registration_anchor` evidence.

`tools/test_human_pcr_admission_selector.py` already proves the routing half of
this branch: the four executor-pair combinations, null members counting as
present, the two branches never overlapping, and the retired `did_inception`
role no longer routing or validating. What it cannot prove is that the branch is
*constructible*, because a selector only reads the envelope. Until 2026-09-19 the
branch had no instance at all: no anchor, no identity-root control proof, and a
create Event whose producer proof named the founding device, which is the one
verification method the branch's verifier is forbidden to accept.

The positive instance now exists and the lint recomputes every digest,
`versionId`, prerotation commitment and signature it asserts. These tests cover
the other direction -- that a substituted or missing piece of that evidence is
actually rejected. Each test mutates one endpoint and asserts the gate fails,
because a gate that only ever sees the correct fixture proves that the fixture
is self-consistent, not that the rule is enforced.

The mutations are the substitutions the evidence itself enumerates: the anchor
replaced or re-digested, the control key swapped for a published document key,
the DID or its terminal `versionId` re-pointed, the history head asserted rather
than hashed, the PCR Realm or the create payload digest re-pointed, the unit
contract's closure dropped, and -- for the delegated branch -- the executor
collapsed back onto the subject principal or onto the anchor root.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as fixtures_lint
from tools.artifact_lint.core import Lint

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
FIXTURES = ARTIFACTS / "fixtures"
PCR = "pcr-genesis-fixture.json"
CONTENT_BOUND = "content-bound-event-id-fixture.json"
CREATE_CASE = "principal_control_realm_id_is_event_derived_and_nonzero_nibble_rejected"
DELEGATED_CASE = "organization_governed_pcr_genesis_derives_a_distinct_realm"

EVIDENCE = "principal_registration_anchor_evidence"
TRANSCRIPT = "identity_creation_control_transcript"

# A second published Ed25519 conformance key. Substituting it is the realistic
# failure: it is valid material, it is registered, and it is the key the DID
# document publishes -- so only the rule "the identity root is the method-native
# update key" can tell the substitution apart from the real thing.
PUBLISHED_DOCUMENT_KEY = "z6MkehRgf7yJbgaGfYsdoAsKdBPE3dj2CYhowQdcjqSJgvVd"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class MutatingLintCase(unittest.TestCase):
    """Run one lint check against in-memory fixture mutations.

    The check reads its inputs through `load_json`, so a mutation is applied by
    intercepting that call rather than by writing to the working tree: a test
    that rewrote a fixture on disk would leave the repository dirty if it failed
    part way through.
    """

    def run_checks(self, overrides: dict[str, dict]) -> list[str]:
        real_load_json = fixtures_lint.load_json

        def load_json(lint: Lint, path: Path):
            document = overrides.get(path.name)
            if document is not None and path.parent.name == "fixtures":
                return document
            return real_load_json(lint, path)

        lint = Lint()
        fixtures_lint.load_json = load_json
        try:
            fixtures_lint.check_human_pcr_registration_anchor_binding(lint)
            fixtures_lint.check_derived_relation_evidence(lint)
        finally:
            fixtures_lint.load_json = real_load_json
        return lint.errors

    def assert_rejected(self, overrides: dict[str, dict], because: str) -> None:
        errors = self.run_checks(overrides)
        self.assertTrue(errors, f"the gate accepted a fixture where {because}")

    def setUp(self) -> None:
        self.pcr = load(PCR)
        self.content = load(CONTENT_BOUND)
        self.evidence = self.pcr[EVIDENCE]
        self.anchor = self.evidence["anchor"]
        self.entry = self.anchor["log_entries"][-1]
        self.transcript = self.pcr[TRANSCRIPT]
        self.cases = {case["name"]: case for case in self.content["cases"]}

    @property
    def overrides(self) -> dict[str, dict]:
        return {PCR: self.pcr, CONTENT_BOUND: self.content}

    # --- the fixture as shipped -------------------------------------------
    def test_the_shipped_evidence_passes(self) -> None:
        self.assertEqual([], self.run_checks(self.overrides))

    # --- anchor substitution ----------------------------------------------
    def test_a_missing_anchor_is_not_a_constructible_branch(self) -> None:
        del self.pcr[EVIDENCE]
        self.assert_rejected(self.overrides, "the branch carries no anchor at all")

    def test_a_resolver_summary_cannot_stand_in_for_the_log(self) -> None:
        self.anchor["log_entries"] = []
        self.assert_rejected(self.overrides, "log_entries is empty")

    def test_the_operation_wrapper_cannot_diverge_from_the_terminal_entry(self) -> None:
        operation = self.anchor["registration_did_operation"]["operation"]
        operation["versionTime"] = "2026-08-10T00:00:00Z"
        self.assert_rejected(
            self.overrides, "the wrapper and the terminal log entry disagree"
        )

    def test_the_wrapper_cannot_carry_prev_event_digest(self) -> None:
        self.anchor["registration_did_operation"]["prev_event_digest"] = "sha256:" + "00" * 32
        self.assert_rejected(self.overrides, "the anchor mirrors its predecessor as a digest")

    def test_seq_must_be_the_terminal_version_number(self) -> None:
        self.anchor["registration_did_operation"]["seq"] = 2
        self.assert_rejected(self.overrides, "seq does not number the terminal entry")

    def test_the_anchor_digest_must_be_over_the_whole_anchor(self) -> None:
        self.evidence["anchor_canonical_json_sha256"] = self.entry["versionId"]
        self.assert_rejected(
            self.overrides, "the versionId entry hash stands in for the anchor digest"
        )

    def test_a_re_digested_anchor_invalidates_the_control_proof(self) -> None:
        self.anchor["witness_records"] = []
        self.entry["versionTime"] = "2026-08-10T00:00:00Z"
        self.assert_rejected(
            self.overrides,
            "the anchor changed while the control proof still commits to the old digest",
        )

    # --- DID, head and version identity -----------------------------------
    def test_the_wrapper_did_must_be_the_did_the_entry_establishes(self) -> None:
        self.anchor["registration_did_operation"]["did"] = "did:webvh:z6mkfixture:bob.example"
        self.assert_rejected(self.overrides, "the wrapper names a different DID")

    def test_the_did_must_carry_the_validated_scid(self) -> None:
        self.entry["parameters"]["scid"] = "z6mkfixtureother"
        self.assert_rejected(
            self.overrides, "the DID's method-specific segment is not parameters.scid"
        )

    def test_the_history_head_cannot_be_asserted(self) -> None:
        self.evidence["derivations"]["method_history_head"] = "sha256:" + "88" * 32
        self.assert_rejected(
            self.overrides, "method_history_head is a constant the entry does not hash to"
        )

    def test_the_terminal_version_id_cannot_be_relabelled(self) -> None:
        self.entry["versionId"] = "1-QmNotTheEntryHashOfThisEntryAtAllXXXXXXXXXXX"
        self.assert_rejected(self.overrides, "the versionId is not the entry hash")

    def test_the_version_number_must_match_the_log_length(self) -> None:
        self.entry["versionId"] = "2-" + self.entry["versionId"].split("-", 1)[1]
        self.assert_rejected(
            self.overrides, "a one-entry log claims to be at version 2"
        )

    def test_the_control_proof_must_name_the_terminal_version(self) -> None:
        self.transcript["signature_omitted_object"]["did_version_id"] = "1-QmSomethingElse"
        self.assert_rejected(
            self.overrides, "the control proof binds a version the anchor does not establish"
        )

    # --- the identity root key --------------------------------------------
    def test_the_control_key_cannot_be_the_published_document_key(self) -> None:
        self.transcript["signature_omitted_object"]["verification_key_multibase"] = (
            PUBLISHED_DOCUMENT_KEY
        )
        self.transcript["signing_material"]["public_key_multibase"] = PUBLISHED_DOCUMENT_KEY
        self.transcript["signing_material"]["public_key_did"] = (
            "did:key:" + PUBLISHED_DOCUMENT_KEY
        )
        self.assert_rejected(
            self.overrides,
            "the identity root is a DID document verification method rather than the "
            "method-native update key",
        )

    def test_the_control_key_digest_must_be_over_the_update_key(self) -> None:
        self.evidence["derivations"]["control_key_digest"] = "sha256:" + "99" * 32
        self.assert_rejected(self.overrides, "control_key_digest is a constant")

    def test_the_normalized_document_must_not_republish_the_update_key(self) -> None:
        methods = self.anchor["normalized_did_document"]["verification_methods"]
        methods.append(
            {
                "verification_method": f"{self.anchor['normalized_did_document']['did']}#root",
                "controller_did": self.anchor["normalized_did_document"]["did"],
                "verification_method_suite": "Multikey",
                "public_key_material": {"publicKeyMultibase": self.entry["parameters"]["updateKeys"][0]},
                "extensions": [],
            }
        )
        self.assert_rejected(
            self.overrides, "the normalized document publishes the identity root as a DID method"
        )

    def test_the_normalized_document_must_project_the_published_methods(self) -> None:
        self.anchor["normalized_did_document"]["verification_methods"] = []
        self.assert_rejected(
            self.overrides, "the normalized document drops the state's verification methods"
        )

    def test_the_prerotation_commitment_must_be_recomputable(self) -> None:
        self.entry["parameters"]["nextKeyHashes"] = ["QmUnrelatedCommitmentValueXXXXXXXXXXXXXXXXXXXX"]
        self.assert_rejected(self.overrides, "nextKeyHashes commits to nothing recomputable")

    def test_the_controller_proof_must_verify(self) -> None:
        self.entry["proof"][0]["proofValue"] = "z" + "1" * 64
        self.assert_rejected(self.overrides, "the terminal entry's controller proof is invalid")

    def test_the_control_proof_signature_must_verify(self) -> None:
        body = self.transcript["signature_omitted_object"]
        body["origin"] = "https://attacker.example"
        self.transcript["signed_object"]["origin"] = "https://attacker.example"
        self.assert_rejected(
            self.overrides, "the signed object changed but the signature did not"
        )

    def test_the_signed_object_must_be_the_body_plus_the_signature(self) -> None:
        self.transcript["signed_object"]["purpose"] = "something_else"
        self.assert_rejected(
            self.overrides, "the published object differs from the signed one"
        )

    def test_a_forbidden_member_cannot_reappear(self) -> None:
        forbidden = self.transcript["forbidden_fields"][0]
        self.transcript["signature_omitted_object"][forbidden] = "sha256:" + "aa" * 32
        self.transcript["signed_object"][forbidden] = "sha256:" + "aa" * 32
        self.assert_rejected(self.overrides, f"the closed proof carries {forbidden}")

    def test_the_forbidden_list_cannot_be_emptied(self) -> None:
        self.transcript["forbidden_fields"] = []
        self.assert_rejected(
            self.overrides, "every removed member became re-addable without a failure"
        )

    # --- PCR Realm and payload digests ------------------------------------
    def test_the_signed_pcr_realm_must_be_the_realm_the_event_derives(self) -> None:
        self.transcript["signature_omitted_object"]["pcr_realm_id"] = self.cases[
            "human_pcr_genesis_on_a_second_station_derives_a_distinct_realm_id"
        ]["derived_realm_id"]
        self.assert_rejected(
            self.overrides, "the control proof is re-pointed at a different genesis"
        )

    def test_the_bound_realm_must_be_the_bound_case_s_realm(self) -> None:
        self.evidence["binds"]["pcr_realm_id"] = "ak:realm:" + "A" * 43 + "Q"
        self.assert_rejected(self.overrides, "the evidence asserts an unrelated PCR Realm")

    def test_the_signed_create_payload_digest_must_be_over_the_create_payload(self) -> None:
        self.transcript["signature_omitted_object"]["realm_create_payload_digest"] = (
            "sha256:" + "bb" * 32
        )
        self.assert_rejected(self.overrides, "the signed payload digest is a constant")

    def test_the_signed_authorize_payload_digest_must_be_the_descriptor_s(self) -> None:
        self.transcript["signature_omitted_object"]["founding_authorize_payload_digest"] = (
            "sha256:" + "cc" * 32
        )
        self.assert_rejected(
            self.overrides, "the signed authorize digest is not the root-signed descriptor's"
        )

    def test_the_signed_session_digest_must_be_over_the_session_request(self) -> None:
        self.transcript["signature_omitted_object"]["initial_session_request_digest"] = (
            "sha256:" + "dd" * 32
        )
        self.assert_rejected(self.overrides, "the bound session request is a constant")

    def test_the_account_subject_must_be_the_domain_separated_digest(self) -> None:
        self.transcript["signature_omitted_object"]["account_subject"] = "sha256:" + "ee" * 32
        self.assert_rejected(self.overrides, "account_subject is a constant")

    # --- unit and receipt closure -----------------------------------------
    def test_the_genesis_unit_kinds_must_be_the_unit_contract_s(self) -> None:
        self.transcript["signature_omitted_object"]["genesis_unit_kinds"] = ["ak.realm.create"]
        self.assert_rejected(
            self.overrides, "the signed unit omits the authorize Event the unit contract orders"
        )

    def test_witness_receipts_must_close_against_the_witness_policy(self) -> None:
        self.anchor["witness_records"] = [{"witness": "did:key:zWitness", "proof": {}}]
        self.assert_rejected(
            self.overrides, "the anchor carries receipts no witness policy required"
        )

    def test_a_declared_witness_policy_requires_receipts(self) -> None:
        self.entry["parameters"]["witness"] = {"threshold": 1, "witnesses": []}
        self.assert_rejected(
            self.overrides, "a witness policy is declared with no receipts to close it"
        )

    def test_the_forbidden_substitution_list_cannot_be_emptied(self) -> None:
        self.evidence["forbidden_substitutions"] = []
        self.assert_rejected(
            self.overrides, "the negative half of the branch is prose again"
        )

    # --- the create unit's producer proof ---------------------------------
    def test_the_create_proof_cannot_be_the_founding_device(self) -> None:
        create = self.cases[CREATE_CASE]
        device_method = self.pcr["founding_event_proof_binding"]["authorize_event"][
            "verification_method"
        ]
        create["complete_wire_event"]["producer_proof"]["verification_method"] = device_method
        self.assert_rejected(
            self.overrides,
            "the registration_anchor branch accepted a device DID URL as its producer method",
        )

    def test_the_create_proof_must_verify_under_the_anchor_update_key(self) -> None:
        create = self.cases[CREATE_CASE]
        create["admission_evidence"]["proof_binding"]["binding_object"]["created_at"] = (
            "2026-08-09T00:00:01.000Z"
        )
        self.assert_rejected(
            self.overrides, "the binding object changed but the detached JWS did not"
        )

    def test_the_create_binding_key_source_must_resolve_to_the_update_key(self) -> None:
        self.pcr["founding_event_proof_binding"]["create_event"]["public_key_source"] = (
            "/founding_device_descriptor/device_public_key_did"
        )
        self.assert_rejected(
            self.overrides, "the create proof's key is sourced from the device descriptor"
        )

    def test_a_genesis_event_carries_no_predecessor_digest(self) -> None:
        create = self.cases[CREATE_CASE]
        create["complete_wire_event"]["prev_event_digest"] = "sha256:" + "ff" * 32
        self.assert_rejected(self.overrides, "a genesis Event claims a predecessor")

    def test_the_initial_resolution_must_be_the_anchor_s_version(self) -> None:
        create = self.cases[CREATE_CASE]
        create["complete_wire_event"]["payload"]["object"]["initial_resolution"][
            "version_id"
        ] = "1-QmSomethingTheAnchorNeverDerived"
        self.assert_rejected(
            self.overrides, "the create Event resolves a version the anchor does not establish"
        )

    def test_the_initial_resolution_head_must_be_the_anchor_s_head(self) -> None:
        create = self.cases[CREATE_CASE]
        create["complete_wire_event"]["payload"]["object"]["initial_resolution"][
            "method_history_head"
        ] = "sha256:" + "12" * 32
        self.assert_rejected(
            self.overrides, "the create Event asserts a history head the anchor does not hash to"
        )

    # --- the delegated branch ---------------------------------------------
    def test_the_delegated_executor_cannot_be_the_anchor_root(self) -> None:
        delegated = self.cases[DELEGATED_CASE]
        root = self.pcr["founding_event_proof_binding"]["create_event"]["verification_method"]
        delegated["complete_wire_event"]["producer_proof"]["verification_method"] = root
        delegated["admission_evidence"]["proof_binding"]["binding_object"][
            "verification_method"
        ] = root
        self.assert_rejected(
            self.overrides,
            "the organization-delegated branch resolved its key from the subject's anchor",
        )

    def test_the_delegated_executor_cannot_sign_under_the_subject_did(self) -> None:
        delegated = self.cases[DELEGATED_CASE]
        subject = self.anchor["registration_did_operation"]["did"]
        method = f"{subject}#ak:device:019a0000-0000-7000-8000-00000000000b"
        delegated["complete_wire_event"]["producer_proof"]["verification_method"] = method
        delegated["admission_evidence"]["proof_binding"]["binding_object"][
            "verification_method"
        ] = method
        self.assert_rejected(
            self.overrides, "the executor signed under the subject principal's own DID"
        )

    def test_the_delegated_proof_must_verify_under_the_executor_key(self) -> None:
        delegated = self.cases[DELEGATED_CASE]
        delegated["admission_evidence"]["executor_signing_material"][
            "public_key_multibase"
        ] = self.entry["parameters"]["updateKeys"][0]
        self.assert_rejected(
            self.overrides, "the executor's declared key does not verify its own proof"
        )

    def test_the_wire_proof_and_the_binding_object_must_name_one_method(self) -> None:
        delegated = self.cases[DELEGATED_CASE]
        delegated["complete_wire_event"]["producer_proof"]["verification_method"] = (
            "did:webvh:z6mkfixtureorgexecutor:org.example#ak:device:"
            "019a0000-0000-7000-8000-00000000000c"
        )
        self.assert_rejected(
            self.overrides, "the wire proof and the signed binding name different methods"
        )

    def test_the_delegated_executor_cannot_be_the_subject_principal(self) -> None:
        delegated = self.cases[DELEGATED_CASE]
        subject = self.cases[CREATE_CASE]["complete_wire_event"]["actor_id"]
        delegated["complete_wire_event"]["executed_by"] = subject
        self.assert_rejected(
            self.overrides,
            "the self-principal branch is wearing the delegated branch's label",
        )

    def test_the_delegated_branch_cannot_act_on_no_authority(self) -> None:
        delegated = self.cases[DELEGATED_CASE]
        del delegated["complete_wire_event"]["authorization_ref"]
        self.assert_rejected(
            self.overrides,
            "an organization-governed genesis carries no governing authority reference",
        )

    # --- the asserted SCID stays a declared exception ----------------------
    def test_an_unreserved_scid_is_not_an_acceptable_assertion(self) -> None:
        self.evidence["scid_derivation"]["asserted_segment"] = "zQmRealLookingScid"
        self.entry["parameters"]["scid"] = "zQmRealLookingScid"
        self.assert_rejected(
            self.overrides,
            "a hand-written SCID outside the reserved conformance prefixes can collide with "
            "material a deployment produced",
        )

    def test_the_scid_exception_must_name_a_real_derivation_vector(self) -> None:
        self.evidence["scid_derivation"]["derivation_vector"] = (
            "fixtures/did-webvh-v1-fixture.json#/cases/<no_such_case>"
        )
        self.assert_rejected(
            self.overrides, "the SCID exception points at a case that does not exist"
        )

    def test_dropping_the_scid_exception_is_a_failure(self) -> None:
        del self.evidence["scid_derivation"]
        self.assert_rejected(
            self.overrides,
            "the one relation the anchor asserts instead of deriving is no longer declared",
        )


class RequiredDeclarationsTest(unittest.TestCase):
    """Deleting a relation declaration MUST fail, not silently lose the check."""

    def test_every_anchor_relation_is_in_the_required_table(self) -> None:
        document = load(PCR)
        declared = {
            (row["relation"], json.dumps(row["output"], sort_keys=True))
            for row in document["derived_relations"]
        }
        required = {
            (relation, output)
            for fixture, relation, output in fixtures_lint.REQUIRED_DERIVED_RELATIONS
            if fixture == PCR
        }
        for relation, output_json in declared:
            output = json.loads(output_json)
            key = (
                relation,
                f"case:{output['case']}#{output['pointer']}"
                if "case" in output
                else f"fixture:{output['fixture']}#{output['pointer']}",
            )
            self.assertIn(
                key,
                required,
                f"{relation} -> {key[1]} is declared but not required, so it can be deleted",
            )

    def test_deleting_a_declaration_fails_the_gate(self) -> None:
        document = load(PCR)
        document["derived_relations"] = document["derived_relations"][:-1]
        real_load_json = fixtures_lint.load_json

        def load_json(lint: Lint, path: Path):
            return document if path.name == PCR else real_load_json(lint, path)

        lint = Lint()
        fixtures_lint.load_json = load_json
        try:
            fixtures_lint.check_derived_relation_evidence(lint)
        finally:
            fixtures_lint.load_json = real_load_json
        self.assertTrue(lint.errors, "a deleted relation declaration was not reported")


class AnchorSchemaBindingTest(unittest.TestCase):
    """The anchor and the signed control proof are bound to real schemas."""

    def test_both_objects_are_registered_in_the_binding_registry(self) -> None:
        registry = json.loads(
            (ROOT / "tools" / "fixture-schema-instance-binding-registry.json").read_text(
                encoding="utf-8"
            )
        )
        bound = {(row["fixture"], row["pointer"]) for row in registry["bindings"]}
        for pointer in (
            f"/{EVIDENCE}/anchor",
            f"/{TRANSCRIPT}/signed_object",
        ):
            self.assertIn(
                (PCR, pointer),
                bound,
                f"{pointer} carries no schema discriminator, so without a binding row no "
                "schema validates it and a deleted member stays silently valid",
            )

    def test_neither_object_carries_its_own_schema_member(self) -> None:
        document = load(PCR)
        self.assertNotIn("schema", document[EVIDENCE]["anchor"])
        self.assertNotIn("schema", document[TRANSCRIPT]["signed_object"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
