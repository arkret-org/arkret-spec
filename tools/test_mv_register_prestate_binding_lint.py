"""Mutation tests for the `mv_register` apply_patch prestate-binding contract.

`event-and-patch.md` §2.4.2: an `mv_register` keeps every concurrent write, so
its frozen pre-state is not single-valued and nothing but `expected_prestate`
says which head the patch was computed against. Two conformant reducers would
otherwise apply the same patch to different heads and disagree on the cell.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import foundation as lint_artifacts

ARTIFACTS = ROOT / "spec/v1/artifacts"


class MvRegisterPrestateBindingLintTest(unittest.TestCase):
    def _lint(self, projection: dict, lattice: str) -> list[str]:
        lint = lint_artifacts.Lint()
        lint_artifacts.lint_effect_projection(
            lint,
            Path("registry/contract-registry.json"),
            "probe",
            projection,
            lattice,
        )
        return list(lint.errors)

    def test_bound_mv_register_patch_is_accepted(self) -> None:
        self.assertEqual(
            self._lint(
                {
                    "kind": "apply_patch",
                    "patch": {"field": "payload.patch"},
                    "expected_prestate": {"field": "payload.expected_state_digest"},
                },
                "mv_register",
            ),
            [],
        )

    def test_unbound_mv_register_patch_is_rejected(self) -> None:
        failures = self._lint(
            {"kind": "apply_patch", "patch": {"field": "payload.patch"}},
            "mv_register",
        )
        self.assertTrue(
            any("expected_prestate" in item for item in failures), failures
        )

    def test_cas_register_keeps_the_optional_binding(self) -> None:
        """The absent-binding exception is `cas_register`'s alone.

        There the write supersedes exactly the heads its own basis observed, so
        the frozen pre-state is single-valued with or without a binding.
        """
        self.assertEqual(
            self._lint(
                {"kind": "apply_patch", "patch": {"field": "payload.patch"}},
                "cas_register",
            ),
            [],
        )

    def test_every_registered_mv_register_patch_declares_its_binding(self) -> None:
        """The rule holds over the shipped registry, not just over a probe."""
        import json

        registry = json.loads(
            (ARTIFACTS / "registry/contract-registry.json").read_text(encoding="utf-8")
        )
        contracts = registry["event_kind_registry"]["cell_contracts"]
        unbound = [
            (kind, write.get("cell_family"))
            for kind, contract in contracts.items()
            for write in contract.get("cell_writes", [])
            if write.get("lattice") == "mv_register"
            and write.get("effect_projection", {}).get("kind") == "apply_patch"
            and "expected_prestate" not in write.get("effect_projection", {})
        ]
        self.assertEqual(unbound, [])


if __name__ == "__main__":
    unittest.main()
