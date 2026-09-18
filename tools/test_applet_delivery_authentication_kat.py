"""Mutation tests for the Applet delivery-authentication record KAT.

The vector this checker guards spent its whole life asserting
`delivery_authentication_record_digest_is_domain_separated` while carrying a
digest nobody could recompute: no record, no preimage, no derivation. A green
run proved only that a hex string was still spelled the same way.

So every test here breaks one obligation of `applet-integration.md` §7.3.1 and
requires the checker to notice. A KAT that cannot be made red by inserting the
domain into the record is the same kind of decoration the old digest was.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import check_applet_delivery_authentication_kat as kat


class AppletDeliveryAuthenticationKatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = kat.load_json(kat.CONTRACT_PATH)
        cls.generated = kat.load_json(kat.GENERATED_OPERATION_PATH)
        cls.prose = kat.PROSE_PATH.read_text(encoding="utf-8")
        cls.fixture = kat.load_json(kat.FIXTURE_PATH)
        cls.algorithms = kat.load_json(kat.SIGNATURE_ALG_PATH)

    def _check(
        self,
        *,
        contract=None,
        generated=None,
        prose=None,
        fixture=None,
        algorithms=None,
    ) -> list[str]:
        return kat.check_documents(
            copy.deepcopy(self.contract if contract is None else contract),
            copy.deepcopy(self.generated if generated is None else generated),
            self.prose if prose is None else prose,
            copy.deepcopy(self.fixture if fixture is None else fixture),
            copy.deepcopy(self.algorithms if algorithms is None else algorithms),
        )

    def _fixture_case(self, fixture: dict) -> dict:
        cases = [
            case
            for case in fixture["cases"]
            if case.get("vector_id") == kat.VECTOR_ID
        ]
        self.assertEqual(1, len(cases))
        return cases[0]

    def _transaction(self, fixture: dict, name: str) -> dict:
        case = self._fixture_case(fixture)
        for transaction in case["transactions"]:
            if transaction.get("name") == name:
                return transaction
        raise AssertionError(f"fixture has no {name!r} transaction")

    def _record_holder(self, fixture: dict, name: str) -> dict:
        transaction = self._transaction(fixture, name)
        for holder in (transaction.get("expected", {}), transaction):
            if kat.RECORD_KEY in holder:
                return holder
        raise AssertionError(f"{name!r} carries no {kat.RECORD_KEY}")

    def assertRedWith(self, errors: list[str], needle: str) -> None:
        self.assertTrue(errors, f"expected a failure mentioning {needle!r}")
        self.assertTrue(
            any(needle in error for error in errors),
            f"{needle!r} not in {errors}",
        )

    # ---------------------------------------------------------------- baseline

    def test_the_checked_in_artifacts_pass(self) -> None:
        self.assertEqual([], self._check())

    def test_the_pinned_digest_is_the_one_the_formula_produces(self) -> None:
        """Recompute the accepted delivery's digest here, not only inside the KAT."""
        holder = self._record_holder(self.fixture, "valid_inbound")
        preimage, digest = kat.record_digest(
            "ak.applet.delivery_authentication_record.v1", holder[kat.RECORD_KEY]
        )
        self.assertEqual(holder[kat.DIGEST_KEY], digest)
        self.assertEqual(holder[kat.PREIMAGE_KEY], preimage)

    # ------------------------------------------------- the record is derivable

    def test_a_member_edited_without_the_digest_turns_the_kat_red(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        holder = self._record_holder(fixture, "valid_inbound")
        holder[kat.RECORD_KEY]["idempotency_key"] = "tx-002"
        self.assertRedWith(self._check(fixture=fixture), "is not the recomputed")

    def test_a_digest_edited_without_the_record_turns_the_kat_red(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        holder = self._record_holder(fixture, "valid_inbound")
        holder[kat.DIGEST_KEY] = "sha256:" + "0" * 64
        self.assertRedWith(self._check(fixture=fixture), "is not the recomputed")

    def test_stale_canonical_bytes_turn_the_kat_red(self) -> None:
        """The stated preimage must be the JCS of the record beside it."""
        fixture = copy.deepcopy(self.fixture)
        holder = self._record_holder(fixture, "valid_inbound")
        holder[kat.PREIMAGE_KEY] = holder[kat.PREIMAGE_KEY].replace("tx-001", "tx-002")
        self.assertRedWith(self._check(fixture=fixture), "pinned canonical bytes")

    def test_dropping_the_record_entirely_turns_the_kat_red(self) -> None:
        """The failure the original fixture should have had from the first day."""
        fixture = copy.deepcopy(self.fixture)
        for transaction in self._fixture_case(fixture)["transactions"]:
            for holder in (transaction.get("expected", {}), transaction):
                holder.pop(kat.RECORD_KEY, None)
        self.assertRedWith(self._check(fixture=fixture), "carries no")

    # ------------------------------------------------- the record set is closed

    def test_inserting_the_domain_as_a_member_turns_the_kat_red(self) -> None:
        """§7.3.1: the domain label is a UTF-8 prefix, never a record member."""
        fixture = copy.deepcopy(self.fixture)
        holder = self._record_holder(fixture, "valid_inbound")
        record = holder[kat.RECORD_KEY]
        record["domain"] = "ak.applet.delivery_authentication_record.v1"
        errors = self._check(fixture=fixture)
        self.assertRedWith(errors, "forbidden member 'domain'")
        self.assertRedWith(errors, "outside the closed set")

    def test_inserting_a_profile_member_turns_the_kat_red(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        holder = self._record_holder(fixture, "valid_inbound")
        holder[kat.RECORD_KEY]["profile"] = "ak.applet.transaction.v1"
        self.assertRedWith(self._check(fixture=fixture), "forbidden member 'profile'")

    def test_copying_the_signature_bytes_in_turns_the_kat_red(self) -> None:
        """§7.3.1: 记录不复制随机或可变长的 Signature bytes."""
        fixture = copy.deepcopy(self.fixture)
        holder = self._record_holder(fixture, "valid_inbound")
        holder[kat.RECORD_KEY]["signature"] = "sig1=:YmFzZTY0:"
        self.assertRedWith(self._check(fixture=fixture), "forbidden member 'signature'")

    def test_dropping_a_closed_member_turns_the_kat_red(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        holder = self._record_holder(fixture, "valid_inbound")
        holder[kat.RECORD_KEY].pop("registration_epoch")
        self.assertRedWith(self._check(fixture=fixture), "omits closed member")

    def test_an_unregistered_direction_turns_the_kat_red(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        holder = self._record_holder(fixture, "valid_inbound")
        holder[kat.RECORD_KEY]["direction"] = "inbound"
        self.assertRedWith(self._check(fixture=fixture), "is not one of")

    def test_an_unregistered_signature_algorithm_turns_the_kat_red(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        holder = self._record_holder(fixture, "valid_inbound")
        holder[kat.RECORD_KEY]["signature_algorithm"] = "ed25519-ph"
        self.assertRedWith(
            self._check(fixture=fixture), "active http_message_signature_algorithm"
        )

    # ------------------------------------ the record answers to the real request

    def test_a_record_that_contradicts_the_verified_request_turns_the_kat_red(self) -> None:
        """`source_id` is cross-verified, not copied from whatever the record says."""
        fixture = copy.deepcopy(self.fixture)
        holder = self._record_holder(fixture, "valid_inbound")
        holder[kat.RECORD_KEY]["source_id"] = "ak:did_core:webvh:z6mkfixturemalloryexample"
        self.assertRedWith(
            self._check(fixture=fixture), "does not match the verified request"
        )

    def test_dropping_the_operation_selector_from_coverage_turns_the_kat_red(self) -> None:
        """api-conventions.md §2.4.1 puts `arkret-operation` in the signature base."""
        fixture = copy.deepcopy(self.fixture)
        transaction = self._transaction(fixture, "valid_inbound")
        holder = self._record_holder(fixture, "valid_inbound")
        record = holder[kat.RECORD_KEY]
        # A receiver that never covered the selector would report exactly that,
        # so the request and the record are dropped together: what must still
        # fail is the contract's required set, not the cross-check.
        for covered in (transaction["covered_components"], record["covered_components"]):
            self.assertIn("arkret-operation", covered)
            covered.remove("arkret-operation")
        preimage, digest = kat.record_digest(
            "ak.applet.delivery_authentication_record.v1", record
        )
        holder[kat.PREIMAGE_KEY] = preimage
        holder[kat.DIGEST_KEY] = digest
        self._transaction(fixture, "exact_replay")[kat.DIGEST_KEY] = digest
        self.assertEqual(
            ["valid_inbound: covered_components omits required component(s) "
             "['arkret-operation']"],
            self._check(fixture=fixture),
        )

    def _service_signature(self, contract: dict) -> dict:
        return next(
            operation
            for operation in contract["operation_registry"]["operations"]
            if operation.get("operation_id") == kat.OPERATION_ID
        )["auth_requirements"]["service_signature"]

    def test_an_operation_that_names_no_signature_scenario_turns_the_kat_red(self) -> None:
        """The required floor is resolved through the canonical signature contract.

        Report 0110 moved the covered set off the operation: if the binding is
        gone the floor is empty, and every covered_components list would pass
        for free.
        """
        contract = copy.deepcopy(self.contract)
        self._service_signature(contract).pop("signature_scenario_id")
        self.assertRedWith(
            self._check(contract=contract), "names no signature_scenario_id"
        )

    def test_an_unregistered_signature_scenario_turns_the_kat_red(self) -> None:
        contract = copy.deepcopy(self.contract)
        self._service_signature(contract)["signature_scenario_id"] = (
            "ak.http_signature.scenario.does_not_exist.v1"
        )
        self.assertRedWith(
            self._check(contract=contract), "names unregistered signature scenario"
        )

    def test_a_component_added_to_the_scenario_turns_the_kat_red(self) -> None:
        """The floor follows the contract, so widening it must fail the fixture."""
        contract = copy.deepcopy(self.contract)
        scenario_id = self._service_signature(contract)["signature_scenario_id"]
        for scenario in contract["http_signature_contract_registry"]["scenarios"]:
            if scenario.get("scenario_id") == scenario_id:
                scenario["additional_covered_components"].append("x-arkret-wait-for")
        self.assertRedWith(
            self._check(contract=contract), "omits required component(s)"
        )

    # -------------------------------------------------- replay equality is digest

    def test_a_replay_that_caches_a_different_digest_turns_the_kat_red(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        replay = self._transaction(fixture, "exact_replay")
        replay[kat.DIGEST_KEY] = "sha256:" + "1" * 64
        self.assertRedWith(
            self._check(fixture=fixture), "cached digest differs from the accepted"
        )

    def test_a_body_drift_delivery_with_the_accepted_digest_turns_the_kat_red(self) -> None:
        """If drift recomputed to the cached digest, duplicate_conflict is unreachable."""
        fixture = copy.deepcopy(self.fixture)
        accepted = self._record_holder(fixture, "valid_inbound")
        drift = self._record_holder(fixture, "idempotency_body_drift")
        drift[kat.RECORD_KEY] = copy.deepcopy(accepted[kat.RECORD_KEY])
        drift[kat.PREIMAGE_KEY] = accepted[kat.PREIMAGE_KEY]
        drift[kat.DIGEST_KEY] = accepted[kat.DIGEST_KEY]
        self.assertRedWith(
            self._check(fixture=fixture), "duplicate_conflict could not be detected"
        )

    # ------------------------------------------- one source, prose and projection

    def test_a_diverging_projection_turns_the_kat_red(self) -> None:
        generated = copy.deepcopy(self.generated)
        for operation in generated["operations"]:
            if operation.get("operation_id") == kat.OPERATION_ID:
                record = operation["auth_requirements"]["service_signature"][kat.RECORD_KEY]
                record["digest_domain"] = "ak.applet.delivery_authentication_record.v2"
        self.assertRedWith(self._check(generated=generated), "projection differs")

    def test_a_contract_domain_the_prose_never_states_turns_the_kat_red(self) -> None:
        contract = copy.deepcopy(self.contract)
        for operation in contract["operation_registry"]["operations"]:
            if operation.get("operation_id") == kat.OPERATION_ID:
                record = operation["auth_requirements"]["service_signature"][kat.RECORD_KEY]
                record["digest_domain"] = "ak.applet.delivery_authentication_record.v2"
        errors = self._check(contract=contract)
        self.assertRedWith(errors, "does not carry digest domain")

    def test_prose_that_hashes_jcs_without_the_prefix_turns_the_kat_red(self) -> None:
        """Deleting the UTF8(domain || LF) construction is exactly the misreading
        §7.3.1 forbids: SHA256(JCS(record)) with the domain stuffed inside."""
        prose = self.prose.replace(
            'UTF8("ak.applet.delivery_authentication_record.v1\\n") ||', "", 1
        )
        self.assertNotEqual(prose, self.prose)
        self.assertRedWith(
            self._check(prose=prose), "UTF8(domain || LF) prefix construction"
        )

    def test_a_closed_field_the_prose_never_names_turns_the_kat_red(self) -> None:
        contract = copy.deepcopy(self.contract)
        for operation in contract["operation_registry"]["operations"]:
            if operation.get("operation_id") == kat.OPERATION_ID:
                record = operation["auth_requirements"]["service_signature"][kat.RECORD_KEY]
                record["closed_fields"].append("verification_nonce")
        self.assertRedWith(self._check(contract=contract), "never names closed field")


class JcsTests(unittest.TestCase):
    """RFC 8785 orders by UTF-16 code unit, which is not Python's str order."""

    def test_property_names_sort_by_utf16_code_unit(self) -> None:
        # U+FFFD is below U+10000 by code point, but its UTF-16 encoding
        # (FFFD) is above the high surrogate (D800) that starts U+10000.
        # Python's own `sorted` would emit these the other way round.
        members = {"�": 2, "𐀀": 1}
        self.assertEqual(
            '{"𐀀":1,"�":2}', kat.jcs_text(members)
        )
        self.assertEqual(["�", "𐀀"], sorted(members))

    def test_integers_keep_their_bare_form(self) -> None:
        self.assertEqual('{"created":1786550400}', kat.jcs_text({"created": 1786550400}))


if __name__ == "__main__":
    unittest.main()
