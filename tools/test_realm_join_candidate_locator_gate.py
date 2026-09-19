"""Mutation tests for the closed RealmJoinCandidate locator contract."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate
from tools.artifact_lint.core import Lint

PROOF_REGISTRY = ROOT / "spec" / "v1" / "artifacts" / "registry" / "proof-context-registry.json"
SCHEMA_REGISTRY = ROOT / "spec" / "v1" / "artifacts" / "registry" / "schema-registry.json"
CONTRACT_REGISTRY = ROOT / "spec" / "v1" / "artifacts" / "registry" / "contract-registry.json"
SERVICE_REGISTRY = (
    ROOT / "spec" / "v1" / "artifacts" / "registry" / "service-kind-registry.json"
)
VECTOR_REGISTRY = ROOT / "spec" / "v1" / "artifacts" / "registry" / "vector-registry.json"
CANDIDATE_SCHEMA = (
    ROOT / "spec" / "v1" / "artifacts" / "schemas" / "realm-join-candidate.schema.json"
)
CANDIDATE_FIXTURE = (
    ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "realm-join-candidate-locator-fixture.json"
)


def _schema_row(document: dict) -> dict:
    return next(
        row
        for row in document["schemas"]
        if row.get("schema_id") == gate.REALM_JOIN_CANDIDATE_SCHEMA_ID
    )


def _contract_schema_row(document: dict) -> dict:
    return next(
        row
        for row in document["schema_registry"]["schemas"]
        if row.get("schema_id") == gate.REALM_JOIN_CANDIDATE_SCHEMA_ID
    )


def _service_context(document: dict) -> dict:
    return next(row for row in document["contexts"] if row.get("id") == "realm_join_candidate")


class RealmJoinCandidateLocatorGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = {
            "proof": json.loads(PROOF_REGISTRY.read_text(encoding="utf-8")),
            "schema_registry": json.loads(SCHEMA_REGISTRY.read_text(encoding="utf-8")),
            "contract": json.loads(CONTRACT_REGISTRY.read_text(encoding="utf-8")),
            "service": json.loads(SERVICE_REGISTRY.read_text(encoding="utf-8")),
            "vector": json.loads(VECTOR_REGISTRY.read_text(encoding="utf-8")),
            "schema": json.loads(CANDIDATE_SCHEMA.read_text(encoding="utf-8")),
            "fixture": json.loads(CANDIDATE_FIXTURE.read_text(encoding="utf-8")),
        }

    def errors_after(self, mutate) -> list[str]:
        documents = copy.deepcopy(self.documents)
        mutate(documents)
        with tempfile.TemporaryDirectory() as directory:
            artifacts = Path(directory) / "artifacts"
            registry = artifacts / "registry"
            schemas = artifacts / "schemas"
            registry.mkdir(parents=True)
            schemas.mkdir(parents=True)
            paths = {
                "proof": registry / "proof-context-registry.json",
                "schema_registry": registry / "schema-registry.json",
                "contract": registry / "contract-registry.json",
                "service": registry / "service-kind-registry.json",
                "vector": registry / "vector-registry.json",
                "schema": schemas / "realm-join-candidate.schema.json",
                "fixture": artifacts / "fixtures" / "realm-join-candidate-locator-fixture.json",
            }
            paths["fixture"].parent.mkdir(parents=True)
            for name, path in paths.items():
                path.write_text(
                    json.dumps(documents[name]), encoding="utf-8", newline="\n"
                )

            lint = Lint()
            with (
                mock.patch.object(gate, "ARTIFACTS", artifacts),
                mock.patch.object(gate, "PROOF_CONTEXT_REGISTRY", paths["proof"]),
                mock.patch.object(gate, "SCHEMA_REGISTRY", paths["schema_registry"]),
                mock.patch.object(gate, "CONTRACT_REGISTRY", paths["contract"]),
                mock.patch.object(gate, "SERVICE_KIND_REGISTRY", paths["service"]),
                mock.patch.object(gate, "VECTOR_REGISTRY", paths["vector"]),
                mock.patch.object(gate, "REALM_JOIN_CANDIDATE_SCHEMA", paths["schema"]),
                mock.patch.object(gate, "REALM_JOIN_CANDIDATE_FIXTURE", paths["fixture"]),
            ):
                gate.check_realm_join_candidate_locator_contract(lint)
            return lint.errors

    def assert_red(self, mutate, phrase: str) -> None:
        errors = self.errors_after(mutate)
        self.assertTrue(any(phrase in error for error in errors), errors)

    def test_shipped_contract_passes(self) -> None:
        self.assertEqual(self.errors_after(lambda _: None), [])

    def test_removed_proof_context_cannot_return(self) -> None:
        self.assert_red(
            lambda d: d["proof"]["contexts"].append(
                {
                    "context": gate.REALM_JOIN_CANDIDATE_REMOVED_CONTEXT,
                    "object_family": "probe",
                }
            ),
            "removed RealmJoinCandidate proof context",
        )

    def test_removed_proof_domain_cannot_return(self) -> None:
        self.assert_red(
            lambda d: d["proof"]["domain_separations"].append(
                {
                    "domain": gate.REALM_JOIN_CANDIDATE_REMOVED_CONTEXT,
                    "object_family": "probe",
                }
            ),
            "removed RealmJoinCandidate proof context",
        )

    def test_locator_cannot_become_a_proof_object_family(self) -> None:
        self.assert_red(
            lambda d: d["proof"]["domain_separations"].append(
                {
                    "domain": "ak.probe.v1",
                    "object_family": gate.REALM_JOIN_CANDIDATE_REMOVED_FAMILY,
                }
            ),
            "promotes the RealmJoinCandidate locator",
        )

    def test_schema_property_set_is_closed(self) -> None:
        self.assert_red(
            lambda d: d["schema"]["properties"].__setitem__("proofs", {"type": "array"}),
            "exact closed RealmJoinCandidate locator field set",
        )

    def test_schema_required_set_is_fixed(self) -> None:
        self.assert_red(
            lambda d: d["schema"]["required"].remove("expires_at"),
            "required must equal",
        )

    def test_schema_is_closed(self) -> None:
        self.assert_red(
            lambda d: d["schema"].__setitem__("additionalProperties", True),
            "additionalProperties must be false",
        )

    def test_service_kind_is_station_only(self) -> None:
        self.assert_red(
            lambda d: d["schema"]["properties"]["service_kind"].__setitem__(
                "enum", ["station", "directory_service"]
            ),
            "service_kind.enum must equal ['station']",
        )

    def test_source_vocabulary_is_fixed(self) -> None:
        self.assert_red(
            lambda d: d["schema"]["properties"]["source"]["enum"].append("peer"),
            "source.enum must equal",
        )

    def test_removed_authority_fields_are_rejected_at_any_schema_depth(self) -> None:
        for field in sorted(gate.REALM_JOIN_CANDIDATE_FORBIDDEN_FIELDS):
            with self.subTest(field=field):
                self.assert_red(
                    lambda d, field=field: d["schema"]["properties"]["realm_id"].__setitem__(
                        "properties", {field: {"type": "string"}}
                    ),
                    "authority-elevating fields",
                )

    def test_schema_description_must_say_untrusted(self) -> None:
        self.assert_red(
            lambda d: d["schema"].__setitem__(
                "description", "A locator for obtaining a RealmAuthorityBundle."
            ),
            "description must contain 'untrusted'",
        )

    def test_schema_description_must_say_locator(self) -> None:
        self.assert_red(
            lambda d: d["schema"].__setitem__(
                "description", "An untrusted hint for obtaining a RealmAuthorityBundle."
            ),
            "description must contain 'locator'",
        )

    def test_schema_description_cannot_claim_preselection(self) -> None:
        self.assert_red(
            lambda d: d["schema"].__setitem__(
                "description", "An untrusted locator for the already selected Station."
            ),
            "authority-elevating claim 'already selected'",
        )

    def test_schema_registry_description_is_guarded(self) -> None:
        self.assert_red(
            lambda d: _schema_row(d["schema_registry"]).__setitem__(
                "description", "A locator used during Realm join."
            ),
            "schema-registry row description must contain 'untrusted'",
        )

    def test_contract_projection_description_is_guarded(self) -> None:
        self.assert_red(
            lambda d: _contract_schema_row(d["contract"]).__setitem__(
                "description", "An untrusted Realm join hint."
            ),
            "contract-registry row description must contain 'locator'",
        )

    def test_service_kind_description_cannot_restore_forwarding_authority(self) -> None:
        self.assert_red(
            lambda d: _service_context(d["service"]).__setitem__(
                "description", "An untrusted locator and join-forwarding target."
            ),
            "authority-elevating claim 'join-forwarding target'",
        )

    def test_canonical_schema_row_must_exist_once(self) -> None:
        self.assert_red(
            lambda d: d["schema_registry"]["schemas"].remove(
                _schema_row(d["schema_registry"])
            ),
            "expected exactly one schema_id='ak.schema.realm_join_candidate.v1' row",
        )

    def test_service_kind_context_must_exist_once(self) -> None:
        self.assert_red(
            lambda d: d["service"]["contexts"].remove(_service_context(d["service"])),
            "expected exactly one id='realm_join_candidate' row",
        )

    def test_vector_must_bind_the_locator_fixture(self) -> None:
        self.assert_red(
            lambda d: next(
                row for row in d["vector"]["vectors"]
                if row.get("vector_id") == gate.REALM_JOIN_CANDIDATE_VECTOR_ID
            ).__setitem__("applies_to_fixtures", []),
            "must be active and bind its sole fixture",
        )

    def test_fixture_trust_contract_cannot_promote_candidate(self) -> None:
        self.assert_red(
            lambda d: d["fixture"]["trust_contract"].__setitem__(
                "candidate_is_authority", True
            ),
            "locator-only authority semantics",
        )

    def test_fixture_must_cover_all_removed_fields(self) -> None:
        self.assert_red(
            lambda d: d["fixture"]["rejected_additional_members"].remove("proofs"),
            "reject every authority-elevating field",
        )


if __name__ == "__main__":
    unittest.main()
