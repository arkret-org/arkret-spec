"""Mutation tests for the service-http-binding.md 2.2.2 supply-closure gate.

The gate only helps if it keeps failing when reality regresses: a demanded
evidence field whose exemption row is deleted must fail, a supplied echo field
whose read surface disappears must fail, a stale exemption row must fail, and
a malformed registry row must fail. Each case below is one of those
properties.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
MODULE_SPEC = importlib.util.spec_from_file_location(
    "lint_artifacts", ROOT / "tools" / "lint_artifacts.py"
)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
lint_artifacts = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(lint_artifacts)

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
REGISTRY_PATH = (
    ARTIFACTS / "registry" / "request-material-supply-exemption-registry.json"
).resolve()
AGENT_OPERATIONS_PATH = (ARTIFACTS / "schemas" / "agent-operations.schema.json").resolve()

DID_OPERATION_ROW = "ak.exemption.request_material_supply.root_submit_did_operation.v1"


class RequestMaterialSupplyLintTest(unittest.TestCase):
    def _run(self, *, json_mutations=None) -> list[str]:
        json_mutations = json_mutations or {}
        original_load_json = lint_artifacts.load_json

        mutated_json: dict[Path, object] = {}
        for path, mutate in json_mutations.items():
            document = copy.deepcopy(original_load_json(lint_artifacts.Lint(), path))
            mutate(document)
            mutated_json[path.resolve()] = document

        def load_json_with_mutation(lint, path):
            resolved = path.resolve()
            if resolved in mutated_json:
                return mutated_json[resolved]
            return original_load_json(lint, path)

        lint_artifacts.load_json = load_json_with_mutation
        try:
            lint = lint_artifacts.Lint()
            lint_artifacts.check_request_material_supply_closure(lint)
            return lint.errors
        finally:
            lint_artifacts.load_json = original_load_json

    def test_committed_tree_passes(self) -> None:
        self.assertEqual(self._run(), [])

    def test_deleting_an_exemption_row_resurfaces_the_demand(self) -> None:
        # An exemption is a live waiver, not a one-time blessing: removing the
        # row must make the underlying demand fail again immediately.
        def mutate(registry):
            registry["exemptions"] = [
                row
                for row in registry["exemptions"]
                if row["exemption_id"] != DID_OPERATION_ROW
            ]

        errors = self._run(json_mutations={REGISTRY_PATH: mutate})
        self.assertTrue(
            any(
                "ak.root.identity.command.submit_did_operation" in error
                and "operation" in error
                for error in errors
            ),
            errors,
        )

    def test_removing_the_echo_supply_fails_the_cas_field(self) -> None:
        # SUPPLY-004 regression guard: the participation read surface must keep
        # returning the verbatim next_replace_input echo container.
        def mutate(schema):
            entry = schema["$defs"]["agent_participation_entry"]
            entry["required"] = [
                name for name in entry["required"] if name != "next_replace_input"
            ]
            entry["properties"].pop("next_replace_input")

        errors = self._run(json_mutations={AGENT_OPERATIONS_PATH: mutate})
        self.assertTrue(
            any(
                "ak.self.agent.participation.resource.replace" in e
                and "expected_version" in e
                for e in errors
            ),
            errors,
        )

    def test_caller_signed_subtree_is_client_local(self) -> None:
        # SUPPLY-005 regression: the recovery terminal receipt is signed by the
        # replacement device that is also the caller, so neither the object nor
        # anything nested inside it is owed by a read surface. Without subtree
        # propagation the evidence-shaped leaves under it fail.
        errors = self._run()
        self.assertFalse(
            [
                error
                for error in errors
                if "issue_recovery_completion_grant" in error
                and "terminal_receipt" in error
            ],
            errors,
        )

    def test_stale_exemption_row_fails(self) -> None:
        # A row that matches nothing is debt bookkeeping rot: the finding it
        # covered was fixed, so the row must be deleted in the same change.
        def mutate(registry):
            registry["exemptions"].append(
                {
                    "exemption_id": "ak.exemption.request_material_supply.stale_row_probe.v1",
                    "status": "active",
                    "kind": "request_input",
                    "operation_id": "ak.self.contact.command.respond",
                    "json_path_prefix": "nonexistent_field",
                    "disposition": "external_form",
                    "rationale": "Probe row that matches no failing demand and must be reported stale.",
                    "review_anchor": None,
                }
            )

        errors = self._run(json_mutations={REGISTRY_PATH: mutate})
        self.assertTrue(any("stale exemption row" in e for e in errors), errors)

    def test_invalid_disposition_fails(self) -> None:
        def mutate(registry):
            registry["exemptions"][0]["disposition"] = "because_i_said_so"

        errors = self._run(json_mutations={REGISTRY_PATH: mutate})
        self.assertTrue(any("disposition" in e for e in errors), errors)

    def test_open_finding_requires_review_anchor(self) -> None:
        # An open finding must stay traceable to a live review entry, so that
        # closing the finding forces the row out in the same change.
        def mutate(registry):
            for row in registry["exemptions"]:
                if row["exemption_id"] == DID_OPERATION_ROW:
                    row["disposition"] = "open_finding"
                    row["review_anchor"] = None

        errors = self._run(json_mutations={REGISTRY_PATH: mutate})
        self.assertTrue(any("review_anchor" in error for error in errors), errors)

    def test_open_finding_anchor_must_resolve_to_a_live_review_entry(self) -> None:
        def mutate(registry):
            for row in registry["exemptions"]:
                if row["exemption_id"] == DID_OPERATION_ROW:
                    row["disposition"] = "open_finding"
                    row["review_anchor"] = {
                        "file": "arkret-work/review/spec-open/2026-08-10-request-evidence-tiering.md",
                        "heading": "A HEADING THAT WAS NEVER WRITTEN",
                    }

        errors = self._run(json_mutations={REGISTRY_PATH: mutate})
        self.assertTrue(
            any("review_anchor heading not found" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
