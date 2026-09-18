"""Tests for the test-material, SDK clause evidence and claim binding gates.

Report 0230 found `AK-SDK-014` asserting a MUST whose entire existence was its
own table row: the truth source pointed at a section that never existed, no
vector covered it, and `conformance-profiles.json` nevertheless graded it V and
demanded a `vector_result`. Landing it produced three artifacts that only mean
something if they can be made to fail: a registry of published signing material,
a clause-to-vector evidence mapping, and a claim whose signature and contract
digest are recomputable.

Each test removes exactly one guarantee and asserts the gate turns red, because
a gate nobody can make fail is indistinguishable from no gate.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from base64 import urlsafe_b64encode
from pathlib import Path
from unittest import mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import test_material as gate
from tools.artifact_lint.core import Lint

SEED = bytes(range(32))
PUBLIC_KEY = Ed25519PrivateKey.from_private_bytes(SEED).public_key()
PUBLIC_BYTES = PUBLIC_KEY.public_bytes_raw()
FINGERPRINT = "sha256:" + hashlib.sha256(PUBLIC_BYTES).hexdigest()

KEY_FIXTURE = "probe-key-fixture.json"
CARRIER_FIXTURE = "probe-carrier-fixture.json"
CLAIM_FIXTURE = "sdk-conformance-claim-fixture.json"

VECTOR = "ak.vector.probe.material_rejected.v1"
CLAUSE = "AK-SDK-777"


def b64u(raw: bytes) -> str:
    return urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def jcs(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def key_fixture() -> dict:
    return {
        "suite": "probe_key",
        "test_private_key_jwk": {"kty": "OKP", "crv": "Ed25519", "d": b64u(SEED)},
        "public_jwk": {"kty": "OKP", "crv": "Ed25519", "x": b64u(PUBLIC_BYTES)},
    }


def material_registry() -> dict:
    return {
        "version": "probe",
        "source_of_truth": True,
        "rules": ["the fingerprint is over algorithm-defined public key bytes"],
        "published_signing_material_field_names": ["test_private_key_jwk"],
        "public_key_encodings": {
            "ed25519_rfc8032_public_key": {
                "length_bytes": 32,
                "definition": "RFC 8032 section 5.1.5 Ed25519 public key octet string.",
            }
        },
        "recomputation_schemes": {"jwk_okp_x_b64u": "one pointer to the OKP x member"},
        "published_signing_material": [
            {
                "id": "probe_key",
                "algorithm": "Ed25519",
                "public_key_encoding": "ed25519_rfc8032_public_key",
                "fingerprint": FINGERPRINT,
                "why": "The private key ships with the probe fixture.",
                "source_fixtures": [f"spec/v1/artifacts/fixtures/{KEY_FIXTURE}"],
                "recomputation": {
                    "fixture": f"spec/v1/artifacts/fixtures/{KEY_FIXTURE}",
                    "scheme": "jwk_okp_x_b64u",
                    "pointers": ["/public_jwk/x"],
                },
            }
        ],
        "reserved_identifiers": [
            {
                "id": "probe_did",
                "kind": "did",
                "why": "A hand-written SCID cannot collide with a derived one.",
                "match": {
                    "terminal": "did",
                    "method": "webvh",
                    "scid_segment_prefixes": ["z6mkfixture"],
                },
                "examples": ["did:webvh:z6mkfixture:alice.example"],
                "non_examples": ["did:webvh:z6Mkreal:alice.example", "did:web:z6mkfixture.example"],
            },
            {
                "id": "probe_key_id",
                "kind": "key_id",
                "why": "The rule matches the fragment alone.",
                "match": {"terminal": "did_url", "fragment_suffixes": ["-fixture"]},
                "examples": ["did:webvh:acmelive:acme.example#assertion-fixture"],
                "non_examples": ["did:webvh:acmelive:acme.example#fixture-2026"],
            },
            {
                "id": "probe_trust_domain",
                "kind": "trust_domain",
                "why": "Trust domains are compared as typed identifier values.",
                "match": {
                    "typed_identifier": "ak:trust_domain",
                    "values": ["recovery-fixture"],
                    "reserved_top_labels": ["example"],
                },
                "examples": ["ak:trust_domain:recovery-fixture", "ak:trust_domain:a.example"],
                "non_examples": ["ak:trust_domain:a.example.net", "recovery-fixture"],
            },
        ],
    }


def vector_registry() -> dict:
    return {
        "version": "probe",
        "source_of_truth": True,
        "vectors": [
            {
                "vector_id": VECTOR,
                "status": "active",
                "domain": "probe",
                "applies_to_fixtures": [CARRIER_FIXTURE],
                "description": "probe",
                "source_refs": [f"spec/v1/artifacts/fixtures/{CARRIER_FIXTURE}"],
            }
        ],
    }


def carrier_fixture() -> dict:
    return {
        "suite": "probe_carrier",
        "runner": {"kind": "named_suite", "entrypoint": "ak.suite.probe.carrier.v1"},
        "version": "probe",
        "covers_vectors": [VECTOR],
        "cases": [],
    }


def contract_body() -> dict:
    return {
        "contract_version": "1",
        "evidence_kinds": ["vector_result", "code_audit"],
        "evidence_coverage_semantics": "acceptable_set",
        "contract_digest_computation": "sha256 over the JCS bytes of this contract object.",
        "vector_evidence_rule": "every vector_result clause carries vector_evidence",
        "vector_evidence_carrier_ratchet_rule": "the ratchet only shrinks",
        "vector_evidence_carrier_ratchet": [],
        "vector_evidence_carrier_ratchet_ceiling_rule": (
            "the frozen set of pairs the ratchet was ever allowed to hold"
        ),
        # Wide enough that the ratchet tests below exercise the rule each is
        # named for; the ceiling itself gets its own test.
        "vector_evidence_carrier_ratchet_ceiling": [
            {"clause_id": CLAUSE, "vector_id": VECTOR},
            {"clause_id": "AK-SDK-778", "vector_id": "ak.vector.probe.absent.v1"},
        ],
        "rules": [],
        "clauses": [
            {
                "clause_id": CLAUSE,
                "grades": ["V"],
                "source_anchor": "spec/v1/zh/probe.md#probe",
                "summary": "probe",
                "required_evidence": ["vector_result"],
                "vector_evidence": {
                    "vectors": [VECTOR],
                    "decision_points": [
                        {
                            "id": "published_material_is_refused",
                            "requirement": "Registered published material is refused although the signature verifies.",
                            "vectors": [VECTOR],
                        }
                    ],
                },
            }
        ],
    }


def contract(body: dict | None = None) -> dict:
    return {"version": "probe", "sdk_conformance_contract": body or contract_body()}


def claim_fixture(contract_document: dict) -> dict:
    digest = "sha256:" + hashlib.sha256(
        jcs(contract_document["sdk_conformance_contract"])
    ).hexdigest()
    instance = {
        "sdk_name": "probe-sdk",
        "spec_revision": "0" * 39 + "1",
        "contract_digest": digest,
        "clause_claims": [
            {
                "clause_id": CLAUSE,
                "result": "pass",
                "evidence": [
                    {
                        "kind": "vector_result",
                        "evidence_ref": "ci://probe/run/1",
                        "digest": "sha256:" + "44" * 32,
                        "covers_vectors": [VECTOR],
                    }
                ],
            }
        ],
    }
    signature = Ed25519PrivateKey.from_private_bytes(SEED).sign(
        gate.CLAIM_DOMAIN + jcs(instance)
    )
    instance["proof"] = {
        "kid": "did:key:z6MkehRgf7yJbgaGfYsdoAsKdBPE3dj2CYhowQdcjqSJgvVd"
        "#z6MkehRgf7yJbgaGfYsdoAsKdBPE3dj2CYhowQdcjqSJgvVd",
        "signature": b64u(signature),
        "signature_algorithm": "Ed25519",
    }
    return {
        "suite": "sdk_conformance_claim",
        "version": "probe",
        "schema_validation_cases": [
            {"name": "valid", "expect_valid": True, "instance": instance}
        ],
    }


class TestMaterialGateTest(unittest.TestCase):
    def run_gates(
        self,
        *,
        registry: dict | None = None,
        vectors: dict | None = None,
        contract_document: dict | None = None,
        fixtures: dict[str, dict] | None = None,
        claim: dict | None = None,
        which: str = "all",
    ) -> list[str]:
        contract_document = contract_document or contract()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = root / "spec" / "v1" / "artifacts"
            for name in ("registry", "fixtures", "profiles"):
                (artifacts / name).mkdir(parents=True)

            def dump(path: Path, body: dict) -> None:
                path.write_text(
                    json.dumps(body, ensure_ascii=False), encoding="utf-8", newline="\n"
                )

            dump(
                artifacts / "registry" / "test-material-registry.json",
                material_registry() if registry is None else registry,
            )
            dump(
                artifacts / "registry" / "vector-registry.json",
                vector_registry() if vectors is None else vectors,
            )
            dump(artifacts / "profiles" / "conformance-profiles.json", contract_document)
            supplied = (
                {KEY_FIXTURE: key_fixture(), CARRIER_FIXTURE: carrier_fixture()}
                if fixtures is None
                else fixtures
            )
            for name, body in supplied.items():
                dump(artifacts / "fixtures" / name, body)
            dump(
                artifacts / "fixtures" / CLAIM_FIXTURE,
                claim_fixture(contract_document) if claim is None else claim,
            )

            lint = Lint()
            with (
                mock.patch.object(gate, "ARTIFACTS", artifacts),
                mock.patch.object(gate, "ROOT", root),
            ):
                if which in ("all", "material"):
                    gate.check_test_material_registry(lint)
                if which in ("all", "evidence"):
                    gate.check_sdk_clause_vector_evidence(lint)
                if which in ("all", "claim"):
                    gate.check_sdk_claim_contract_binding(lint)
            return lint.errors

    def assertRedWith(self, errors: list[str], needle: str) -> None:
        self.assertTrue(any(needle in error for error in errors), errors)

    # ---------------------------------------------------------------- baseline

    def test_the_probe_tree_passes(self) -> None:
        self.assertEqual(self.run_gates(), [])

    def test_the_committed_spec_passes(self) -> None:
        lint = Lint()
        gate.check_test_material_registry(lint)
        gate.check_sdk_clause_vector_evidence(lint)
        gate.check_sdk_claim_contract_binding(lint)
        self.assertEqual(lint.errors, [])

    # ------------------------------------------------- the registry recomputes

    def test_a_rotated_fixture_key_turns_the_gate_red(self) -> None:
        other = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
        body = key_fixture()
        body["public_jwk"]["x"] = b64u(other.public_key().public_bytes_raw())
        errors = self.run_gates(
            fixtures={KEY_FIXTURE: body, CARRIER_FIXTURE: carrier_fixture()}, which="material"
        )
        self.assertRedWith(errors, "does not match the key its recomputation block points at")

    def test_a_row_without_a_recomputation_block_turns_the_gate_red(self) -> None:
        body = material_registry()
        del body["published_signing_material"][0]["recomputation"]
        self.assertRedWith(
            self.run_gates(registry=body, which="material"),
            "must carry a recomputation block",
        )

    def test_a_dangling_recomputation_pointer_turns_the_gate_red(self) -> None:
        body = material_registry()
        body["published_signing_material"][0]["recomputation"]["pointers"] = ["/public_jwk/nope"]
        self.assertRedWith(self.run_gates(registry=body, which="material"), "does not resolve in")

    def test_a_wrong_length_public_key_turns_the_gate_red(self) -> None:
        body = key_fixture()
        body["public_jwk"]["x"] = b64u(PUBLIC_BYTES[:16])
        errors = self.run_gates(
            fixtures={KEY_FIXTURE: body, CARRIER_FIXTURE: carrier_fixture()}, which="material"
        )
        self.assertRedWith(errors, "public key bytes")

    def test_an_unregistered_published_private_key_turns_the_gate_red(self) -> None:
        errors = self.run_gates(
            fixtures={
                KEY_FIXTURE: key_fixture(),
                CARRIER_FIXTURE: carrier_fixture(),
                "probe-extra-fixture.json": key_fixture(),
            },
            which="material",
        )
        self.assertRedWith(errors, "publishes a private signing key but no published_signing_material")

    # --------------------------------------------- the matchers are executable

    def test_a_did_rule_that_stops_matching_its_example_turns_the_gate_red(self) -> None:
        body = material_registry()
        body["reserved_identifiers"][0]["match"]["scid_segment_prefixes"] = ["z6mkother"]
        self.assertRedWith(
            self.run_gates(registry=body, which="material"),
            "examples entry does not match its rule",
        )

    def test_a_trust_domain_rule_widened_to_a_dns_suffix_turns_the_gate_red(self) -> None:
        body = material_registry()
        body["reserved_identifiers"][2]["match"]["values"].append("a.example.net")
        self.assertRedWith(
            self.run_gates(registry=body, which="material"),
            "non_examples entry matches its rule",
        )

    def test_a_key_id_rule_widened_past_its_non_example_turns_the_gate_red(self) -> None:
        body = material_registry()
        body["reserved_identifiers"][1]["match"]["fragment_suffixes"].append("-2026")
        self.assertRedWith(
            self.run_gates(registry=body, which="material"),
            "non_examples entry matches its rule",
        )

    def test_a_key_id_rule_that_stops_matching_its_example_turns_the_gate_red(self) -> None:
        body = material_registry()
        body["reserved_identifiers"][1]["match"]["fragment_suffixes"] = ["-probe"]
        self.assertRedWith(
            self.run_gates(registry=body, which="material"),
            "examples entry does not match its rule",
        )

    def test_dropping_a_reserved_identifier_rule_turns_the_gate_red(self) -> None:
        body = material_registry()
        del body["reserved_identifiers"][2]
        self.assertRedWith(
            self.run_gates(registry=body, which="material"),
            "reserved_identifiers is missing the trust_domain rule",
        )

    # ------------------------------------------- the SDK evidence mapping bites

    def test_a_vector_result_clause_without_a_mapping_turns_the_gate_red(self) -> None:
        body = contract_body()
        del body["clauses"][0]["vector_evidence"]
        self.assertRedWith(
            self.run_gates(contract_document=contract(body), which="evidence"),
            "accepts vector_result but carries no vector_evidence mapping",
        )

    def test_a_non_vector_clause_carrying_a_mapping_turns_the_gate_red(self) -> None:
        body = contract_body()
        body["clauses"][0]["required_evidence"] = ["code_audit"]
        self.assertRedWith(
            self.run_gates(contract_document=contract(body), which="evidence"),
            "does not accept vector_result",
        )

    def test_an_unregistered_vector_turns_the_gate_red(self) -> None:
        body = contract_body()
        body["clauses"][0]["vector_evidence"]["vectors"] = ["ak.vector.probe.absent.v1"]
        self.assertRedWith(
            self.run_gates(contract_document=contract(body), which="evidence"),
            "names an unregistered vector",
        )

    def test_an_inactive_vector_turns_the_gate_red(self) -> None:
        registry = vector_registry()
        registry["vectors"][0]["status"] = "superseded"
        self.assertRedWith(
            self.run_gates(vectors=registry, which="evidence"), "which is not active"
        )

    def test_an_empty_family_expansion_turns_the_gate_red(self) -> None:
        body = contract_body()
        body["clauses"][0]["vector_evidence"]["vectors"] = ["ak.vector.absent.*"]
        self.assertRedWith(
            self.run_gates(contract_document=contract(body), which="evidence"),
            "family expands to nothing",
        )

    def test_a_family_expansion_reaching_an_inactive_member_turns_the_gate_red(self) -> None:
        registry = vector_registry()
        registry["vectors"].append(
            {
                "vector_id": "ak.vector.probe.other.v1",
                "status": "superseded",
                "domain": "probe",
                "applies_to_fixtures": [CARRIER_FIXTURE],
                "description": "probe",
                "source_refs": [f"spec/v1/artifacts/fixtures/{CARRIER_FIXTURE}"],
            }
        )
        body = contract_body()
        body["clauses"][0]["vector_evidence"]["vectors"] = ["ak.vector.probe.*"]
        self.assertRedWith(
            self.run_gates(vectors=registry, contract_document=contract(body), which="evidence"),
            "which is not active",
        )

    def test_an_empty_decision_point_list_turns_the_gate_red(self) -> None:
        body = contract_body()
        body["clauses"][0]["vector_evidence"]["decision_points"] = []
        self.assertRedWith(
            self.run_gates(contract_document=contract(body), which="evidence"),
            "decision_points must be non-empty",
        )

    def test_duplicate_decision_point_ids_turn_the_gate_red(self) -> None:
        body = contract_body()
        points = body["clauses"][0]["vector_evidence"]["decision_points"]
        points.append(copy.deepcopy(points[0]))
        self.assertRedWith(
            self.run_gates(contract_document=contract(body), which="evidence"),
            "duplicates published_material_is_refused",
        )

    def test_a_placeholder_requirement_turns_the_gate_red(self) -> None:
        body = contract_body()
        body["clauses"][0]["vector_evidence"]["decision_points"][0]["requirement"] = "tbd"
        self.assertRedWith(
            self.run_gates(contract_document=contract(body), which="evidence"),
            "must state the decision in at least",
        )

    def test_a_decision_point_outside_the_clause_vector_set_turns_the_gate_red(self) -> None:
        registry = vector_registry()
        registry["vectors"].append(
            {
                "vector_id": "ak.vector.probe.other.v1",
                "status": "active",
                "domain": "probe",
                "applies_to_fixtures": [CARRIER_FIXTURE],
                "description": "probe",
                "source_refs": [f"spec/v1/artifacts/fixtures/{CARRIER_FIXTURE}"],
            }
        )
        body = contract_body()
        body["clauses"][0]["vector_evidence"]["decision_points"][0]["vectors"] = [
            "ak.vector.probe.other.v1"
        ]
        self.assertRedWith(
            self.run_gates(vectors=registry, contract_document=contract(body), which="evidence"),
            "which is outside the clause's expanded vector set",
        )

    # -------------------------------------------------- the carrier ratchet

    def test_an_uncarried_vector_outside_the_ratchet_turns_the_gate_red(self) -> None:
        registry = vector_registry()
        registry["vectors"][0].pop("applies_to_fixtures")
        registry["vectors"][0]["source_refs"] = ["spec/v1/zh/conformance/conformance-vectors.md"]
        self.assertRedWith(
            self.run_gates(vectors=registry, which="evidence"),
            "which no fixture carries and which vector_evidence_carrier_ratchet does not record",
        )

    def test_a_ratchet_row_for_a_now_carried_vector_turns_the_gate_red(self) -> None:
        body = contract_body()
        body["vector_evidence_carrier_ratchet"] = [
            {"clause_id": CLAUSE, "vector_id": VECTOR, "owner_report": "report.md"}
        ]
        self.assertRedWith(
            self.run_gates(contract_document=contract(body), which="evidence"),
            "which now has a fixture carrier; the ratchet only shrinks",
        )

    def test_a_ratchet_row_no_clause_reaches_turns_the_gate_red(self) -> None:
        body = contract_body()
        body["vector_evidence_carrier_ratchet"] = [
            {
                "clause_id": "AK-SDK-778",
                "vector_id": "ak.vector.probe.absent.v1",
                "owner_report": "report.md",
            }
        ]
        self.assertRedWith(
            self.run_gates(contract_document=contract(body), which="evidence"),
            "which no clause mapping reaches",
        )

    def test_a_ratchet_row_without_an_owner_report_turns_the_gate_red(self) -> None:
        registry = vector_registry()
        registry["vectors"][0].pop("applies_to_fixtures")
        registry["vectors"][0]["source_refs"] = ["spec/v1/zh/conformance/conformance-vectors.md"]
        body = contract_body()
        body["vector_evidence_carrier_ratchet"] = [
            {"clause_id": CLAUSE, "vector_id": VECTOR}
        ]
        self.assertRedWith(
            self.run_gates(vectors=registry, contract_document=contract(body), which="evidence"),
            "must name the report that owns the gap",
        )

    def test_a_ratchet_row_outside_the_frozen_ceiling_turns_the_gate_red(self) -> None:
        # The prose says the list only shrinks; this is what makes that a check
        # rather than a promise. A brand new uncarried pair cannot be silenced
        # by writing one more row, because the row is not in the baseline.
        registry = vector_registry()
        registry["vectors"][0].pop("applies_to_fixtures")
        registry["vectors"][0]["source_refs"] = ["spec/v1/zh/conformance/conformance-vectors.md"]
        body = contract_body()
        body["vector_evidence_carrier_ratchet_ceiling"] = []
        body["vector_evidence_carrier_ratchet"] = [
            {"clause_id": CLAUSE, "vector_id": VECTOR, "owner_report": "report.md"}
        ]
        self.assertRedWith(
            self.run_gates(vectors=registry, contract_document=contract(body), which="evidence"),
            "the frozen vector_evidence_carrier_ratchet_ceiling does not contain",
        )

    def test_a_ratchet_row_inside_the_frozen_ceiling_passes(self) -> None:
        registry = vector_registry()
        registry["vectors"][0].pop("applies_to_fixtures")
        registry["vectors"][0]["source_refs"] = ["spec/v1/zh/conformance/conformance-vectors.md"]
        body = contract_body()
        body["vector_evidence_carrier_ratchet"] = [
            {"clause_id": CLAUSE, "vector_id": VECTOR, "owner_report": "report.md"}
        ]
        self.assertEqual(
            self.run_gates(vectors=registry, contract_document=contract(body), which="evidence"),
            [],
        )

    def test_dropping_the_ceiling_turns_the_gate_red(self) -> None:
        body = contract_body()
        del body["vector_evidence_carrier_ratchet_ceiling"]
        self.assertRedWith(
            self.run_gates(contract_document=contract(body), which="evidence"),
            "vector_evidence_carrier_ratchet_ceiling must be a list",
        )

    def test_dropping_the_ceiling_rule_turns_the_gate_red(self) -> None:
        body = contract_body()
        del body["vector_evidence_carrier_ratchet_ceiling_rule"]
        self.assertRedWith(
            self.run_gates(contract_document=contract(body), which="evidence"),
            "vector_evidence_carrier_ratchet_ceiling_rule must state the rule",
        )

    def test_a_carrier_fixture_without_a_runner_turns_the_gate_red(self) -> None:
        body = carrier_fixture()
        del body["runner"]
        self.assertRedWith(
            self.run_gates(
                fixtures={KEY_FIXTURE: key_fixture(), CARRIER_FIXTURE: body}, which="evidence"
            ),
            "declares no runner",
        )

    # ------------------------------------------------------ the claim binding

    def test_a_stale_contract_digest_turns_the_gate_red(self) -> None:
        document = contract()
        claim = claim_fixture(document)
        claim["schema_validation_cases"][0]["instance"]["contract_digest"] = "sha256:" + "11" * 32
        self.assertRedWith(
            self.run_gates(contract_document=document, claim=claim, which="claim"),
            "binds a stale contract_digest",
        )

    def test_editing_the_contract_without_resigning_turns_the_gate_red(self) -> None:
        document = contract()
        claim = claim_fixture(document)
        edited = contract()
        edited["sdk_conformance_contract"]["rules"] = ["a new rule"]
        self.assertRedWith(
            self.run_gates(contract_document=edited, claim=claim, which="claim"),
            "binds a stale contract_digest",
        )

    def test_a_signature_that_does_not_verify_turns_the_gate_red(self) -> None:
        document = contract()
        claim = claim_fixture(document)
        claim["schema_validation_cases"][0]["instance"]["sdk_name"] = "renamed-after-signing"
        self.assertRedWith(
            self.run_gates(contract_document=document, claim=claim, which="claim"),
            "its signature does not verify",
        )

    def test_a_claim_fixture_without_a_positive_case_turns_the_gate_red(self) -> None:
        document = contract()
        claim = claim_fixture(document)
        claim["schema_validation_cases"][0]["expect_valid"] = False
        self.assertRedWith(
            self.run_gates(contract_document=document, claim=claim, which="claim"),
            "must carry at least one expect_valid case",
        )

    def test_dropping_the_digest_computation_rule_turns_the_gate_red(self) -> None:
        body = contract_body()
        del body["contract_digest_computation"]
        document = contract(body)
        self.assertRedWith(
            self.run_gates(contract_document=document, which="claim"),
            "must state how the digest a claim binds is computed",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
