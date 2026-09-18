"""Mutation tests for the resolver-policy / adapter-registry alignment gate.

identity-did.md section 4.1 tells deployments to derive every role method set
from did-method-adapter-registry.json, and then its own example contradicted
both the registry and the bullet directly above it: did:key was handed
``human_anchor_immutable`` plus ``allow_for_human_anchor`` admissions while the
registry carries ``human_principal_anchor=false`` for it, and the did:plc block
used the ``long_lived_principal`` condition the bullet forbids by name. Each
mutation below is a state the document was actually in, or the neighbouring
drift the same gate has to catch.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import core
from tools.artifact_lint import prose

IDENTITY_DID = ROOT / "spec" / "v1" / "zh" / "identity" / "identity-did.md"


class ResolverPolicyRegistryAlignmentTest(unittest.TestCase):
    def _errors(self, *replacements: tuple[str, str]) -> list[str]:
        original_read_text = prose.read_text
        text = original_read_text(IDENTITY_DID)
        for old, new in replacements:
            self.assertEqual(text.count(old), 1, f"anchor text is not unique: {old!r}")
            text = text.replace(old, new)

        def read_text_with_mutation(path: Path) -> str:
            if Path(path).resolve() == IDENTITY_DID.resolve():
                return text
            return original_read_text(path)

        prose.read_text = read_text_with_mutation
        try:
            lint = core.Lint()
            prose.check_resolver_policy_matches_did_method_adapter_registry(lint)
            return lint.errors
        finally:
            prose.read_text = original_read_text

    def assertFails(self, errors: list[str], needle: str) -> None:
        self.assertTrue(any(needle in error for error in errors), errors)

    def test_unmutated_document_passes(self) -> None:
        self.assertEqual(self._errors(), [])

    def test_private_role_vocabulary_fails(self) -> None:
        errors = self._errors(
            ('      "role": [],\n      "human_anchor_admission"', '      "role": ["human_anchor_immutable", "local_verifiable_material"],\n      "human_anchor_admission"')
        )
        self.assertFails(errors, "role_requirements keys")

    def test_did_key_claiming_human_anchor_admission_fails(self) -> None:
        errors = self._errors(
            (
                '    "did:key": {\n      "role": [],\n      "human_anchor_admission": "unsupported_did_method"\n    }',
                '    "did:key": {\n      "role": [],\n      "account_registration": "allow_for_human_anchor",\n      "principal_control_realm": "allow_for_human_anchor"\n    }',
            )
        )
        self.assertFails(errors, "restates role admission through")
        self.assertFails(errors, "must be 'unsupported_did_method'")

    def test_did_key_claiming_the_service_role_fails(self) -> None:
        errors = self._errors(
            ('      "role": [],\n      "human_anchor_admission"', '      "role": ["service"],\n      "human_anchor_admission"')
        )
        self.assertFails(errors, "satisfy exactly []")

    def test_dropping_the_non_anchor_admission_fails(self) -> None:
        errors = self._errors(
            (
                '      "role": ["service"],\n      "https_required": true,\n      "human_anchor_admission": "unsupported_did_method"\n',
                '      "role": ["service"],\n      "https_required": true\n',
            )
        )
        self.assertFails(errors, "human_anchor_admission must be")

    def test_human_anchor_method_carrying_an_admission_branch_fails(self) -> None:
        errors = self._errors(
            (
                '      "outage_max_duration_ms": 86400000\n',
                '      "outage_max_duration_ms": 86400000,\n      "human_anchor_admission": "unsupported_did_method"\n',
            )
        )
        self.assertFails(errors, "must not carry human_anchor_admission")

    def test_dropping_a_satisfied_role_fails(self) -> None:
        errors = self._errors(('        "human_relocatable",\n', ""))
        self.assertFails(errors, "satisfy exactly")

    def test_prose_sentence_widening_the_anchor_set_fails(self) -> None:
        errors = self._errors(
            (
                "human anchor 当前只有 `did:webvh`",
                "human anchor 当前为 `did:webvh` + `did:web` + `did:key`",
            )
        )
        self.assertFails(errors, "but the registry derives")

    def test_unregistered_method_claiming_a_role_fails(self) -> None:
        errors = self._errors(
            ('    "role": [],\n    "directory"', '    "role": ["interop_principal"],\n    "directory"')
        )
        self.assertFails(errors, "has no active adapter row, so role must be []")

    def test_long_lived_principal_condition_fails(self) -> None:
        errors = self._errors(
            (
                '    "interop_claim_boundary": "atproto"\n',
                '    "long_lived_principal": "interop_only"\n',
            )
        )
        self.assertFails(errors, "restates role admission through ['long_lived_principal']")

    def test_allowed_methods_diverging_from_the_registry_fails(self) -> None:
        errors = self._errors(
            (
                '  "allowed_methods": ["did:webvh", "did:web", "did:key"],\n',
                '  "allowed_methods": ["did:webvh", "did:web"],\n',
            )
        )
        self.assertFails(errors, "must be the active adapter method set")

    def test_default_principal_method_outside_the_anchor_set_fails(self) -> None:
        errors = self._errors(
            (
                '  "default_principal_method": "did:webvh",\n',
                '  "default_principal_method": "did:web",\n',
            )
        )
        self.assertFails(errors, "must be the sole registry-derived human anchor method")


if __name__ == "__main__":
    unittest.main()
