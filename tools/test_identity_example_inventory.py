from __future__ import annotations

import unittest
from unittest import mock

from tools.artifact_lint import test_material as gate
from tools.artifact_lint.core import Lint

RESERVED = "did:webvh:z6mkfixture:alice.example"
DEPLOYMENT = "did:webvh:z6Mkreal:deploy.example"
DERIVED = "did:webvh:QmDerived:derive.example"
SOURCES = {
    RESERVED: ["spec/v1/zh/a.md"],
    DEPLOYMENT: ["spec/v1/zh/b.md"],
    DERIVED: ["spec/v1/artifacts/fixtures/derived.json"],
}
RULES = [
    {
        "kind": "did",
        "match": {"method": "webvh", "scid_segment_prefixes": ["z6mkfixture"]},
    }
]


def registry() -> dict:
    return {
        "identity_examples": [
            {"value": RESERVED, "role": "test_material", "sources": SOURCES[RESERVED]},
            {
                "value": DEPLOYMENT,
                "role": "deployment_like_example",
                "sources": SOURCES[DEPLOYMENT],
            },
            {
                "value": DERIVED,
                "role": "derived_positive",
                "sources": SOURCES[DERIVED],
                "derivation_ref": "fixture.json#/value",
            },
        ]
    }


class IdentityExampleInventoryMutationTest(unittest.TestCase):
    def check_document(self, document: dict) -> list[str]:
        lint = Lint()
        with (
            mock.patch.object(gate, "_identity_example_sources", return_value=SOURCES),
            mock.patch.object(gate, "load_json", return_value={"value": DERIVED}),
        ):
            gate._check_identity_example_inventory(lint, document, RULES)
        return lint.errors

    def test_baseline_passes(self) -> None:
        self.assertEqual(self.check_document(registry()), [])

    def test_p1_missing_live_value_fails(self) -> None:
        body = registry()
        body["identity_examples"].pop()
        self.assertTrue(any("misses live values" in e for e in self.check_document(body)))

    def test_p2_unknown_role_fails(self) -> None:
        body = registry()
        body["identity_examples"][1]["role"] = "example"
        self.assertTrue(any("role must be one of" in e for e in self.check_document(body)))

    def test_p3_unreserved_test_material_fails(self) -> None:
        body = registry()
        body["identity_examples"][1]["role"] = "test_material"
        self.assertTrue(any("matches no reserved" in e for e in self.check_document(body)))

    def test_p4_reserved_deployment_example_fails(self) -> None:
        body = registry()
        body["identity_examples"][0]["role"] = "deployment_like_example"
        self.assertTrue(any("MUST NOT enter the reserved" in e for e in self.check_document(body)))

    def test_p5_source_set_drift_fails(self) -> None:
        body = registry()
        body["identity_examples"][1]["sources"] = ["spec/v1/zh/elsewhere.md"]
        self.assertTrue(any("live occurrence set" in e for e in self.check_document(body)))

    def test_p6_derived_positive_requires_pointer(self) -> None:
        body = registry()
        del body["identity_examples"][2]["derivation_ref"]
        self.assertTrue(any("key set must be exactly" in e for e in self.check_document(body)))

    def test_p7_derived_pointer_must_resolve_to_value(self) -> None:
        body = registry()
        with mock.patch.object(gate, "_identity_example_sources", return_value=SOURCES), mock.patch.object(
            gate, "load_json", return_value={"value": "did:webvh:QmOther:derive.example"}
        ):
            lint = Lint()
            gate._check_identity_example_inventory(lint, body, RULES)
        self.assertTrue(any("does not resolve to its value" in e for e in lint.errors))

    def test_live_inventory_covers_all_roles_and_runner_is_wired(self) -> None:
        lint = Lint()
        document = gate.load_json(lint, gate._registry_path())
        self.assertIsInstance(document, dict)
        gate._check_identity_example_inventory(
            lint,
            document,
            document["reserved_identifiers"],
        )
        self.assertEqual(lint.errors, [])
        roles = {row["role"] for row in document["identity_examples"]}
        self.assertEqual(roles, gate._IDENTITY_ROLES)
        self.assertGreater(
            sum(row["role"] == "derived_positive" for row in document["identity_examples"]),
            0,
        )
        runner_source = (gate.ROOT / "tools" / "artifact_lint" / "runner.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("check_test_material_registry(lint)", runner_source)


if __name__ == "__main__":
    unittest.main()
