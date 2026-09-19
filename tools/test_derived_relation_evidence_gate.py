"""Mutation tests for the general derived-relation evidence gate.

A fixture case used to be able to claim a derivation and carry nothing that
could produce it: the human Principal Control Realm case asserted
``retype_is_byte_identical`` with no preimage, no digest, no Event token and no
Realm token, and every gate passed because each gate was comparing the case's
labels against the labels it expected. The relation gate recomputes each
declared derivation from the exact inputs it names, and the chain gate holds the
case shape so the bytes cannot be deleted while the labels survive.

Each mutation below is either a state one of these fixtures was actually in, or
the cheapest way to fake the relation it now has to prove.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as lint_artifacts

FIXTURES = ROOT / "spec" / "v1" / "artifacts" / "fixtures"
CONTENT_BOUND = "content-bound-event-id-fixture.json"
PCR_GENESIS = "pcr-genesis-fixture.json"

STEP1 = "principal_control_realm_id_is_event_derived_and_nonzero_nibble_rejected"
SECOND_STATION = "human_pcr_genesis_on_a_second_station_derives_a_distinct_realm_id"
AUTHORIZE = "human_founding_device_authorize_binds_the_derived_realm"
UNIQUENESS = "same_account_second_genesis_rejected_by_station_account_uniqueness"


def case(fixture: dict, name: str) -> dict:
    for entry in fixture["cases"]:
        if entry.get("name") == name:
            return entry
    raise AssertionError(f"missing case {name}")


def rehash(entry: dict, envelope: dict) -> None:
    """Write an envelope back into a case and refresh every derived value.

    Recomputing the digest after a mutation is exactly what an author who wants
    the gate quiet would do, so the tests that use this helper are asserting
    that rehashing does not launder an illegal Event or a broken binding.
    """
    body = lint_artifacts.canonical_json(envelope)
    digest = hashlib.sha256(body.encode("utf-8")).digest()
    token = bytes((entry.get("suite_wire_code", 1),)) + digest
    encoded = base64.urlsafe_b64encode(token).rstrip(b"=").decode("ascii")
    entry["digest_preimage_canonical_bytes_utf8"] = body
    entry["event_digest"] = "sha256:" + digest.hex()
    entry["event_id_bytes_hex"] = token.hex()
    entry["derived_event_id"] = "ak:event:" + encoded
    if "derived_realm_id" in entry:
        entry["derived_realm_id"] = "ak:realm:" + encoded


class DerivedRelationEvidenceGateTest(unittest.TestCase):
    def _errors(self, mutate, checks=None) -> list[str]:
        """Run the named checks over mutated in-memory copies of both fixtures."""
        targets = {
            (FIXTURES / name).resolve(): name for name in (CONTENT_BOUND, PCR_GENESIS)
        }
        original_load_json = lint_artifacts.load_json
        documents = {
            name: copy.deepcopy(original_load_json(lint_artifacts.Lint(), path))
            for path, name in targets.items()
        }
        mutate(documents[CONTENT_BOUND], documents[PCR_GENESIS])

        def load_json_with_mutation(lint, path):
            resolved = Path(path).resolve()
            if resolved in targets:
                return documents[targets[resolved]]
            return original_load_json(lint, path)

        lint_artifacts.load_json = load_json_with_mutation
        try:
            lint = lint_artifacts.Lint()
            for check in checks or (
                lint_artifacts.check_derived_relation_evidence,
                lint_artifacts.check_content_bound_event_id_fixture,
            ):
                check(lint)
            return lint.errors
        finally:
            lint_artifacts.load_json = original_load_json

    def test_unmutated_fixtures_pass(self) -> None:
        lint = lint_artifacts.Lint()
        lint_artifacts.check_derived_relation_evidence(lint)
        lint_artifacts.check_content_bound_event_id_fixture(lint)
        lint_artifacts.check_stated_event_preimage_is_a_valid_event(lint)
        self.assertEqual(lint.errors, [])

    # --- the original defect: an assertion with no bytes under it ------------

    def test_deleting_every_byte_but_keeping_the_assertion_fails(self) -> None:
        def mutate(bound, _pcr):
            entry = case(bound, STEP1)
            for member in (
                "digest_preimage_canonical_bytes_utf8",
                "event_digest",
                "suite_wire_code",
                "event_id_bytes_hex",
                "derived_event_id",
                "derived_realm_id",
            ):
                entry.pop(member, None)
            self.assertIs(entry["accepted_form"]["retype_is_byte_identical"], True)

        self.assertTrue(self._errors(mutate))

    def test_deleting_a_relation_declaration_fails(self) -> None:
        def mutate(bound, _pcr):
            bound["derived_relations"] = [
                row
                for row in bound["derived_relations"]
                if not (
                    row.get("relation") == "retype_typed_id"
                    and row.get("output", {}).get("case") == STEP1
                )
            ]

        errors = self._errors(mutate)
        self.assertTrue(
            any("required derived relation is not declared" in error for error in errors),
            errors,
        )

    def test_emptying_the_relation_array_fails(self) -> None:
        def mutate(bound, _pcr):
            bound["derived_relations"] = []

        self.assertTrue(self._errors(mutate))

    # --- faking the arithmetic ----------------------------------------------

    def test_wrong_event_digest_fails(self) -> None:
        def mutate(bound, _pcr):
            case(bound, STEP1)["event_digest"] = "sha256:" + "11" * 32

        self.assertTrue(self._errors(mutate))

    def test_wrong_suite_wire_code_fails(self) -> None:
        def mutate(bound, _pcr):
            case(bound, STEP1)["suite_wire_code"] = 2

        self.assertTrue(self._errors(mutate))

    def test_wrong_retype_fails(self) -> None:
        def mutate(bound, _pcr):
            entry = case(bound, STEP1)
            entry["derived_realm_id"] = case(bound, SECOND_STATION)["derived_realm_id"]

        self.assertTrue(self._errors(mutate))

    def test_a_genesis_that_rehashes_but_stays_illegal_fails(self) -> None:
        """Dropping initial_resolution and rehashing keeps every digest
        self-consistent. The Event is still one no implementation may accept,
        and the identity readback no longer has a DID to project."""

        def mutate(bound, _pcr):
            entry = case(bound, STEP1)
            envelope = json.loads(entry["digest_preimage_canonical_bytes_utf8"])
            del envelope["payload"]["object"]["initial_resolution"]
            rehash(entry, envelope)

        errors = self._errors(
            mutate,
            checks=(
                lint_artifacts.check_derived_relation_evidence,
                lint_artifacts.check_stated_event_preimage_is_a_valid_event,
            ),
        )
        self.assertTrue(errors)

    def test_non_zero_reserved_nibble_negative_must_stay_a_mutation(self) -> None:
        def mutate(bound, _pcr):
            case(bound, STEP1)["rejected_form"]["realm_id"] = (
                "ak:realm:EZhLpW4uz0hs-0000000000000000000000000000000"
            )

        self.assertTrue(self._errors(mutate))

    def test_a_zero_nibble_negative_is_not_a_negative(self) -> None:
        def mutate(bound, _pcr):
            entry = case(bound, STEP1)
            entry["rejected_form"]["realm_id"] = entry["derived_realm_id"]

        self.assertTrue(self._errors(mutate))

    # --- cross-fixture material ---------------------------------------------

    def test_descriptor_digest_drift_fails(self) -> None:
        def mutate(_bound, pcr):
            pcr["founding_device_descriptor"]["founding_authorize_payload_digest"] = (
                "sha256:" + "22" * 32
            )

        self.assertTrue(self._errors(mutate))

    def test_authorize_payload_drift_fails(self) -> None:
        """Changing the shared authorize payload breaks both the descriptor
        digest and the equality with the Event that carries it, so the two
        fixtures cannot drift apart while each stays internally consistent."""

        def mutate(_bound, pcr):
            payload = pcr["founding_authorize"]["payload"]
            payload["authorized_generation_ref"] = 2
            body = lint_artifacts.canonical_json(payload)
            pcr["founding_authorize"]["canonical_payload_json"] = body
            digest = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
            pcr["founding_authorize"]["payload_digest"] = digest
            pcr["founding_device_descriptor"]["founding_authorize_payload_digest"] = digest

        self.assertTrue(self._errors(mutate))

    def test_forged_possession_signature_fails(self) -> None:
        def mutate(_bound, pcr):
            signature = pcr["device_possession"]["device_signature"]
            raw = bytearray(base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)))
            raw[0] ^= 0x01
            pcr["device_possession"]["device_signature"] = (
                base64.urlsafe_b64encode(bytes(raw)).rstrip(b"=").decode("ascii")
            )

        self.assertTrue(self._errors(mutate))

    def test_unresolvable_reference_fails(self) -> None:
        def mutate(bound, _pcr):
            for row in bound["derived_relations"]:
                if row.get("relation") == "sha256_of_canonical_json":
                    row["inputs"]["object"]["pointer"] = "/founding_authorize/absent"
                    return
            raise AssertionError("no sha256_of_canonical_json relation to break")

        errors = self._errors(mutate)
        self.assertTrue(any("does not resolve" in error for error in errors), errors)

    def test_reference_to_a_missing_fixture_fails(self) -> None:
        def mutate(bound, _pcr):
            for row in bound["derived_relations"]:
                if row.get("relation") == "sha256_of_canonical_json":
                    row["inputs"]["object"]["fixture"] = "no-such-fixture.json"
                    return
            raise AssertionError("no sha256_of_canonical_json relation to break")

        self.assertTrue(self._errors(mutate))

    def test_self_referential_relation_fails(self) -> None:
        """An output that is one of its own inputs proves nothing."""

        def mutate(bound, _pcr):
            for row in bound["derived_relations"]:
                if row.get("relation") == "retype_typed_id":
                    row["output"] = copy.deepcopy(row["inputs"]["source_typed_id"])
                    return
            raise AssertionError("no retype_typed_id relation to break")

        self.assertTrue(self._errors(mutate))

    def test_unknown_relation_name_fails(self) -> None:
        def mutate(bound, _pcr):
            bound["derived_relations"][0] = dict(
                bound["derived_relations"][0], relation="looks_derived_to_me"
            )

        self.assertTrue(self._errors(mutate))

    # --- the identity bindings ----------------------------------------------

    def test_wrong_account_station_in_the_second_event_fails(self) -> None:
        """Both Events of one genesis unit carry the same account ActorId.
        Moving the authorize Event to another Station and rehashing keeps its
        own digest right and the unit wrong."""

        def mutate(bound, _pcr):
            entry = case(bound, AUTHORIZE)
            envelope = json.loads(entry["digest_preimage_canonical_bytes_utf8"])
            envelope["actor_id"]["account_id"]["station_id"] = (
                "ak:did_core:webvh:z6mkfixturestationb"
            )
            rehash(entry, envelope)

        self.assertTrue(self._errors(mutate))

    def test_authorize_bound_to_another_realm_fails(self) -> None:
        def mutate(bound, _pcr):
            entry = case(bound, AUTHORIZE)
            other = case(bound, SECOND_STATION)["derived_realm_id"]
            entry["realm_id"] = other
            entry["scope_ref"]["realm_id"] = other

        self.assertTrue(self._errors(mutate))

    def test_wrong_projected_principal_fails(self) -> None:
        def mutate(bound, _pcr):
            case(bound, STEP1)["identity_bindings"]["projected_principal_id"] = (
                "ak:did_core:webvh:z6mkfixtureother"
            )

        self.assertTrue(self._errors(mutate))

    def test_undeclared_difference_between_the_two_stations_fails(self) -> None:
        """The distinct-Realm claim is only worth something if the second
        genesis really differs from the first in exactly the paths it names."""

        def mutate(bound, _pcr):
            entry = case(bound, SECOND_STATION)
            envelope = json.loads(entry["digest_preimage_canonical_bytes_utf8"])
            envelope["created_at"] = "2026-08-09T00:00:01.000Z"
            rehash(entry, envelope)

        errors = self._errors(mutate)
        self.assertTrue(any("but the case declares" in error for error in errors), errors)

    def test_second_station_deriving_the_same_realm_fails(self) -> None:
        def mutate(bound, _pcr):
            entry = case(bound, SECOND_STATION)
            entry["derived_realm_id"] = case(bound, STEP1)["derived_realm_id"]

        self.assertTrue(self._errors(mutate))

    # --- the state judgement -------------------------------------------------

    def test_account_uniqueness_case_must_not_carry_bytes(self) -> None:
        """Account-dimension uniqueness is decided from Station state. Giving
        the case a digest invites the reading that the rejection follows from
        the bytes, which under event-derived ids it never can."""

        def mutate(bound, _pcr):
            entry = case(bound, UNIQUENESS)
            entry["event_digest"] = case(bound, STEP1)["event_digest"]

        errors = self._errors(mutate)
        self.assertTrue(any(UNIQUENESS in error for error in errors), errors)

    def test_account_uniqueness_case_must_state_zero_writes(self) -> None:
        def mutate(bound, _pcr):
            case(bound, UNIQUENESS)["expected"]["writes"] = 1

        self.assertTrue(self._errors(mutate))

    def test_account_uniqueness_must_not_be_decided_by_id_collision(self) -> None:
        def mutate(bound, _pcr):
            case(bound, UNIQUENESS)["expected"]["decided_by_id_collision"] = True

        self.assertTrue(self._errors(mutate))

    def test_account_uniqueness_must_not_fold_back_into_the_byte_case(self) -> None:
        def mutate(bound, _pcr):
            case(bound, STEP1)["expected"]["same_account_second_genesis"] = "rejected"

        self.assertTrue(self._errors(mutate))


if __name__ == "__main__":
    unittest.main()
