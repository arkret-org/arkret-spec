"""Mutation tests for issuer-scoped SessionGrant identity and physical carriers."""

from __future__ import annotations

import copy
import inspect
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import core, foundation

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
REGISTRY = ARTIFACTS / "registry" / "id-kind-registry.json"
PROBE = ARTIFACTS / "schemas" / "issuer-identity-probe.schema.json"
UUID = foundation.PRODUCER_UUID_PAYLOAD_REGEX
DIGEST = foundation.EVENT_TOKEN_PAYLOAD_REGEX


class IssuerAllocatedIdentityLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.row = next(row for row in self.registry["id_kinds"] if row["kind"] == "session_grant")

    def contract_errors(self, row=None, registry=None) -> list[str]:
        lint = foundation.Lint()
        foundation.check_issuer_allocated_id_contract(
            lint, REGISTRY, self.row if row is None else row,
            self.registry if registry is None else registry,
        )
        return lint.errors

    def carrier_errors(self, pattern: str, check=None) -> list[str]:
        lint = foundation.Lint()
        documents = foundation.typed_id_validation_documents(lint)
        documents.append((PROBE, {"type": "string", "pattern": pattern}))
        with patch.object(foundation, "typed_id_validation_documents", return_value=documents):
            (check or foundation.check_typed_id_payload_form_closure)(lint)
        return lint.errors

    def token_errors(self, kind: str, payload: str) -> list[str]:
        lint = core.Lint()
        known = {
            "id_kinds": {"session_grant", "device", "event", "notification_projection"},
            "issuer_allocated_id_kinds": {"session_grant"},
            "event_derived_id_kinds": {"event"},
            "digest_token_id_kinds": {"notification_projection"},
            "special_id_kinds": set(),
            "active_digest_suite_wire_codes": {1},
        }
        core.check_typed_id_token(lint, PROBE, "$.id", kind, payload, known)
        return lint.errors

    def test_committed_issuer_contract_passes(self) -> None:
        self.assertEqual(self.contract_errors(), [])

    def test_issuer_contract_is_invoked_from_registry_gate(self) -> None:
        source = inspect.getsource(foundation.check_registries)
        self.assertIn('id_kind == "session_grant" or id_form == "issuer_allocated"', source)
        self.assertIn("check_issuer_allocated_id_contract(lint, id_path, row, id_registry)", source)
        self.assertIn('"issuer_allocated_id_kinds"', source)

    def test_every_row_authority_field_is_required(self) -> None:
        for field in ("kind", "id_form", "wire_form", "identity_authority", "derivation_contract_ref", "storage_identity_key"):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.row)
                changed.pop(field)
                self.assertTrue(self.contract_errors(row=changed))

    def test_retired_digest_or_producer_classification_is_rejected(self) -> None:
        for form in ("suite_tagged_full_digest", "producer_allocated", "event_derived"):
            with self.subTest(form=form):
                changed = dict(self.row, id_form=form)
                self.assertTrue(self.contract_errors(row=changed))

    def test_another_kind_cannot_borrow_the_issuer_contract(self) -> None:
        self.assertTrue(self.contract_errors(row=dict(self.row, kind="device")))

    def test_genesis_is_forbidden_even_if_null_or_empty(self) -> None:
        for value in (None, [], ["ak.auth.session_grant.issue"]):
            with self.subTest(value=value):
                self.assertTrue(self.contract_errors(row=dict(self.row, genesis_event_kinds=value)))

    def test_exact_contract_authority_and_opaque_shape_are_required(self) -> None:
        fields = (
            "applies_to_id_kinds", "identity_key", "authority", "id_form", "identity_authority",
            "record_identity_fields", "record_id_allocation", "secret_bytes", "secret_encoding",
            "secret_schema_ref", "credential_pattern", "reference_schema_ref", "metadata_schema_ref",
            "credential_lookup", "metadata_immutability", "conformance_suite",
        )
        for field in fields:
            with self.subTest(field=field):
                changed = copy.deepcopy(self.registry)
                changed["issuer_record_identity_contract"].pop(field)
                self.assertTrue(self.contract_errors(registry=changed))

    def test_cross_issuer_storage_cannot_collapse_to_a_bare_id(self) -> None:
        changed = copy.deepcopy(self.registry)
        changed["issuer_record_identity_contract"]["identity_key"] = ["typed_id"]
        self.assertTrue(self.contract_errors(registry=changed))
        self.assertTrue(self.contract_errors(row=dict(self.row, storage_identity_key=["typed_id"])))

    def test_retired_issuer_preimage_fields_are_rejected(self) -> None:
        for field in ("preimage_fields", "digest_input", "domain_separator", "canonicalization", "digest_suite_wire_code", "digest_suite_registry_ref", "token_layout"):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.registry)
                changed["issuer_record_identity_contract"][field] = None
                self.assertTrue(self.contract_errors(registry=changed))

    def test_canonical_issuer_uuid_carrier_passes(self) -> None:
        self.assertEqual(self.carrier_errors(f"^ak:session_grant:{UUID}$"), [])
        self.assertEqual(self.carrier_errors(f"^ak:session_grant:{UUID}$", foundation.check_id_form_wire_schema_alignment), [])

    def test_retired_digest_carrier_is_rejected_by_both_gates(self) -> None:
        pattern = f"^ak:session_grant:{DIGEST}$"
        for check in (foundation.check_typed_id_payload_form_closure, foundation.check_id_form_wire_schema_alignment):
            with self.subTest(check=check.__name__):
                self.assertTrue(self.carrier_errors(pattern, check))

    def test_widened_or_unterminated_uuid_carrier_is_rejected(self) -> None:
        for pattern in ("^ak:session_grant:[0-9a-f-]+$", f"^ak:session_grant:{UUID}", "^ak:session_grant:[A-Za-z0-9_-]{43}$"):
            with self.subTest(pattern=pattern):
                self.assertTrue(self.carrier_errors(pattern))

    def test_union_cannot_hide_one_legacy_issuer_branch(self) -> None:
        self.assertTrue(self.carrier_errors(f"^ak:(session_grant|notification_projection):{DIGEST}$"))

    def test_issuer_uuid_is_excluded_from_content_address_suite_checks(self) -> None:
        kinds = foundation.suite_tagged_content_address_kinds(self.registry)
        self.assertNotIn("session_grant", kinds)
        self.assertIn("notification_projection", kinds)
        self.assertFalse(kinds["notification_projection"])
        self.assertTrue(kinds["event"])

    def test_core_accepts_uuid_and_rejects_retired_digest_for_issuer(self) -> None:
        self.assertEqual(self.token_errors("session_grant", "0190c6aa-1234-7000-8000-000000000001"), [])
        failures = self.token_errors("session_grant", "AQ" + "A" * 42)
        self.assertTrue(any("issuer-allocated UUIDv7" in failure for failure in failures), failures)

    def test_core_rejects_noncanonical_issuer_uuid(self) -> None:
        for payload in ("0190c6aa-1234-4000-8000-000000000001", "0190C6AA-1234-7000-8000-000000000001", "0190c6aa-1234-7000-7000-000000000001"):
            with self.subTest(payload=payload):
                self.assertTrue(self.token_errors("session_grant", payload))

    def test_producer_uuid_and_notification_digest_gates_are_preserved(self) -> None:
        self.assertEqual(self.token_errors("device", "0190c6aa-1234-7000-8000-000000000001"), [])
        self.assertTrue(self.token_errors("device", "AQ" + "A" * 42))
        self.assertEqual(self.token_errors("notification_projection", "AQ" + "A" * 42), [])
        self.assertTrue(self.token_errors("notification_projection", "AA" + "A" * 42))
        self.assertTrue(self.token_errors("event", "AA" + "A" * 42))


if __name__ == "__main__":
    unittest.main()
