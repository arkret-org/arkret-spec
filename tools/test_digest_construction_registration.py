"""Mutation tests for the canonical-JSON digest-construction registry gate."""

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

from tools import regenerate_fixture_digests
from tools.artifact_lint import proof_context_schemas as gate
from tools.artifact_lint.core import Lint

REGISTRY = ROOT / "spec" / "v1" / "artifacts" / "registry" / "proof-context-registry.json"
CONTACT_KAT = ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "contact-round-kat.json"


def _row(document: dict, domain: str) -> dict:
    return next(row for row in document["domain_separations"] if row.get("domain") == domain)


class DigestConstructionRegistrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.document = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.fixture = json.loads(CONTACT_KAT.read_text(encoding="utf-8"))

    def errors_after(self, mutate, fixture_mutate=None) -> list[str]:
        document = copy.deepcopy(self.document)
        fixture = copy.deepcopy(self.fixture)
        mutate(document)
        if fixture_mutate is not None:
            fixture_mutate(fixture)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = root / "artifacts"
            registry_path = artifacts / "registry" / "proof-context-registry.json"
            fixture_path = artifacts / "fixtures" / "contact-round-kat.json"
            registry_path.parent.mkdir(parents=True)
            fixture_path.parent.mkdir(parents=True)
            registry_path.write_text(json.dumps(document), encoding="utf-8", newline="\n")
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8", newline="\n")
            lint = Lint()
            with (
                mock.patch.object(gate, "ARTIFACTS", artifacts),
                mock.patch.object(gate, "PROOF_CONTEXT_REGISTRY", registry_path),
            ):
                gate.check_digest_construction_registration(lint)
            return lint.errors

    def assert_red(self, mutate, phrase: str, fixture_mutate=None) -> None:
        errors = self.errors_after(mutate, fixture_mutate)
        self.assertTrue(any(phrase in error for error in errors), errors)

    def test_shipped_registry_passes(self) -> None:
        self.assertEqual(self.errors_after(lambda _: None), [])

    def test_p01_construction_table_is_required(self) -> None:
        self.assert_red(lambda d: d.pop("digest_constructions"), "must be a non-empty array")

    def test_p02_construction_rows_are_closed(self) -> None:
        self.assert_red(
            lambda d: d["digest_constructions"][0].__setitem__("algorithm_alias", "sha2"),
            "closed construction keys",
        )

    def test_p03_construction_ids_are_unique(self) -> None:
        def mutate(document: dict) -> None:
            document["digest_constructions"][1]["construction_id"] = document[
                "digest_constructions"
            ][0]["construction_id"]

        self.assert_red(mutate, "duplicate digest construction")

    def test_p04_primitive_dispatch_is_non_empty(self) -> None:
        self.assert_red(
            lambda d: d["digest_constructions"][0].__setitem__("applies_to_primitives", []),
            "non-empty unique string array",
        )

    def test_p05_domain_is_not_a_transcript_member(self) -> None:
        self.assert_red(
            lambda d: d["digest_constructions"][0].__setitem__(
                "domain_is_a_transcript_member", True
            ),
            "domain_is_a_transcript_member must be false",
        )

    def test_p06_defining_literal_must_occur_in_the_normative_source(self) -> None:
        self.assert_red(
            lambda d: d["digest_constructions"][0].__setitem__(
                "defining_literal", "SHA512(unregistered bytes)"
            ),
            "defining_literal does not occur",
        )

    def test_p07_canonical_digest_rows_are_closed(self) -> None:
        self.assert_red(
            lambda d: _row(d, "ak.contact.no_outgoing_slot.v1").__setitem__(
                "prefix_hex", _row(d, "ak.contact.no_outgoing_slot.v1")["prefix_bytes_hex"]
            ),
            "open or incomplete shape",
        )

    def test_p08_every_row_selects_a_registered_construction(self) -> None:
        self.assert_red(
            lambda d: _row(d, "ak.contact.no_outgoing_slot.v1").__setitem__(
                "digest_construction", "missing"
            ),
            "digest_construction is not registered",
        )

    def test_p09_selected_construction_must_apply_to_the_primitive(self) -> None:
        self.assert_red(
            lambda d: d["digest_constructions"][0].__setitem__(
                "applies_to_primitives", ["detached_signature"]
            ),
            "does not apply to canonical_json_sha256",
        )

    def test_p10_prefix_bytes_are_recomputed_from_domain(self) -> None:
        self.assert_red(
            lambda d: _row(d, "ak.contact.no_outgoing_slot.v1").__setitem__(
                "domain", "ak.contact.no_outgoing_slot.v2"
            ),
            "recomputed from domain",
        )

    def test_p11_transcript_definition_must_define_its_domain(self) -> None:
        self.assert_red(
            lambda d: _row(d, "ak.contact.no_outgoing_slot.v1").__setitem__(
                "transcript_defined_in",
                "zh/models/actor.md#331-accountable_principal_ids-的可验证性normative",
            ),
            "does not contain its domain literal",
        )

    def test_p12_missing_kat_requires_a_reason_and_owner(self) -> None:
        self.assert_red(
            lambda d: _row(d, "ak.contact.glare_unconsumed_slot.v1").pop("owner_report"),
            "requires a spec-open owner_report",
        )

    def test_p12b_known_answer_digest_is_recomputed(self) -> None:
        def mutate_fixture(document: dict) -> None:
            document["outgoing_slot_absence"]["case"]["expected_digest"] = "sha256:" + "0" * 64

        self.assert_red(
            lambda _: None,
            "digest does not match its registered construction",
            fixture_mutate=mutate_fixture,
        )

    def test_p13_fixture_regenerator_does_not_rewrite_transcript_pairs(self) -> None:
        """A transcript rename must not silently lose the domain prefix (0930 P13)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.json"
            original = {
                "transcript": {"a": 1},
                "expected_digest": "sha256:" + "f" * 64,
                "domain_separator_utf8": "ak.probe.v1\n",
            }
            path.write_text(json.dumps(original), encoding="utf-8", newline="\n")
            self.assertEqual(regenerate_fixture_digests.update_file(path), 0)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), original)


if __name__ == "__main__":
    unittest.main()
