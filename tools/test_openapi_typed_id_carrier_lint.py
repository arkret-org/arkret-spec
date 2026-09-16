"""Mutation tests for the typed-ID contract closure over the OpenAPI mirror.

The OpenAPI document is a published external contract, but the typed-ID gates
only globbed ``artifacts/schemas``. That gap let the mirror reject the canonical
44-character Event-derived token while accepting a UUID shape the protocol
declares permanently invalid. Each case below corrupts the OpenAPI document the
way that drift actually looks and asserts the gate rejects it, plus asserts the
gates really run from the artifact-lint entry point.
"""

from __future__ import annotations

import copy
import inspect
import sys
import unittest
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import foundation as lint_artifacts
from tools.artifact_lint import runner

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
OPENAPI = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"

RETIRED_UUIDV8 = "[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
PRODUCER_UUIDV7 = lint_artifacts.PRODUCER_UUID_PAYLOAD_REGEX
EVENT_TOKEN = lint_artifacts.EVENT_TOKEN_PAYLOAD_REGEX


class OpenApiTypedIdCarrierLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.real_documents = lint_artifacts.typed_id_validation_documents

    def tearDown(self) -> None:
        lint_artifacts.typed_id_validation_documents = self.real_documents

    # --- helpers --------------------------------------------------------

    def _documents(self) -> list[tuple[Path, Any]]:
        return self.real_documents(lint_artifacts.Lint())

    def _mutate_openapi(
        self, mutate: Callable[[dict], None]
    ) -> list[tuple[Path, Any]]:
        documents: list[tuple[Path, Any]] = []
        for path, document in self._documents():
            if path == OPENAPI:
                document = copy.deepcopy(document)
                mutate(document)
            documents.append((path, document))
        return documents

    def _run(
        self,
        check: Callable[[Any], None],
        documents: list[tuple[Path, Any]] | None = None,
    ) -> list[str]:
        if documents is not None:
            lint_artifacts.typed_id_validation_documents = lambda lint: documents
        lint = lint_artifacts.Lint()
        check(lint)
        return list(lint.errors)

    # --- committed tree -------------------------------------------------

    def test_committed_artifacts_pass(self) -> None:
        self.assertEqual(
            self._run(lint_artifacts.check_id_form_wire_schema_alignment), []
        )
        self.assertEqual(
            self._run(lint_artifacts.check_typed_id_carrier_sweep_closure), []
        )

    def test_openapi_is_inside_the_typed_id_carrier_sweep(self) -> None:
        self.assertIn(OPENAPI, [path for path, _ in self._documents()])

    def test_openapi_text_carries_no_retired_uuidv8_pattern(self) -> None:
        self.assertNotIn(RETIRED_UUIDV8, OPENAPI.read_text(encoding="utf-8"))

    def test_gates_run_from_the_artifact_lint_entry_point(self) -> None:
        self.assertIs(
            runner.check_id_form_wire_schema_alignment,
            lint_artifacts.check_id_form_wire_schema_alignment,
        )
        self.assertIs(
            runner.check_typed_id_carrier_sweep_closure,
            lint_artifacts.check_typed_id_carrier_sweep_closure,
        )
        source = inspect.getsource(runner.main)
        self.assertIn("check_id_form_wire_schema_alignment(lint)", source)
        self.assertIn("check_typed_id_carrier_sweep_closure(lint)", source)
        self.assertIn("check_typed_id_prefix_registry_closure(lint)", source)

    # --- OpenAPI id_form mutations --------------------------------------

    def test_retired_uuidv8_pattern_in_openapi_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["components"]["schemas"]["EventId"]["pattern"] = (
                f"^ak:event:{RETIRED_UUIDV8}$"
            )

        failures = self._run(
            lint_artifacts.check_id_form_wire_schema_alignment,
            self._mutate_openapi(mutate),
        )
        self.assertTrue(
            any(
                "validates event-derived ak:event with a UUID payload" in failure
                for failure in failures
            ),
            failures,
        )

    def test_producer_uuid_pattern_on_an_event_derived_kind_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["components"]["schemas"]["RealmId"]["pattern"] = (
                f"^ak:realm:{PRODUCER_UUIDV7}$"
            )

        failures = self._run(
            lint_artifacts.check_id_form_wire_schema_alignment,
            self._mutate_openapi(mutate),
        )
        self.assertTrue(
            any(
                "validates event-derived ak:realm with a UUID payload" in failure
                for failure in failures
            ),
            failures,
        )

    def test_event_token_pattern_on_a_producer_allocated_kind_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["components"]["schemas"]["MutationProbe"] = {
                "type": "string",
                "pattern": f"^ak:device:{EVENT_TOKEN}$",
            }

        failures = self._run(
            lint_artifacts.check_id_form_wire_schema_alignment,
            self._mutate_openapi(mutate),
        )
        self.assertTrue(
            any(
                "validates producer-allocated ak:device with a 44-character token payload"
                in failure
                for failure in failures
            ),
            failures,
        )

    def test_single_polluted_union_branch_in_openapi_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["components"]["schemas"]["MutationProbe"] = {
                "type": "string",
                "pattern": (
                    f"^(ak:(realm|space):{EVENT_TOKEN}"
                    f"|ak:view:{RETIRED_UUIDV8}|did:.+)$"
                ),
            }

        failures = self._run(
            lint_artifacts.check_id_form_wire_schema_alignment,
            self._mutate_openapi(mutate),
        )
        self.assertTrue(
            any(
                "validates event-derived ak:view with a UUID payload" in failure
                for failure in failures
            ),
            failures,
        )
        self.assertFalse(
            any("ak:realm with a UUID payload" in failure for failure in failures),
            failures,
        )

    def test_carrier_behind_a_local_ref_is_swept_at_its_definition(self) -> None:
        def mutate(document: dict) -> None:
            document["components"]["schemas"]["MutationProbe"] = {
                "type": "string",
                "pattern": f"^ak:morph:{RETIRED_UUIDV8}$",
            }
            document["components"]["schemas"]["MutationProbeHolder"] = {
                "type": "object",
                "properties": {
                    "morph_id": {
                        "allOf": [{"$ref": "#/components/schemas/MutationProbe"}]
                    }
                },
            }

        failures = self._run(
            lint_artifacts.check_id_form_wire_schema_alignment,
            self._mutate_openapi(mutate),
        )
        self.assertTrue(
            any(
                "validates event-derived ak:morph with a UUID payload" in failure
                for failure in failures
            ),
            failures,
        )

    # --- OpenAPI prefix closure mutation --------------------------------

    def test_unregistered_typed_id_prefix_in_openapi_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["components"]["schemas"]["MutationProbe"] = {
                "type": "string",
                "pattern": f"^ak:evt:{EVENT_TOKEN}$",
            }

        failures = self._run(
            lint_artifacts.check_typed_id_prefix_registry_closure,
            self._mutate_openapi(mutate),
        )
        self.assertTrue(
            any(
                "accepts unregistered typed ID prefix 'ak:evt:'" in failure
                for failure in failures
            ),
            failures,
        )

    def test_unregistered_typed_id_prefix_in_an_openapi_enum_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["components"]["schemas"]["MutationProbe"] = {
                "type": "string",
                "enum": ["ak:not_a_registered_kind:probe"],
            }

        failures = self._run(
            lint_artifacts.check_typed_id_prefix_registry_closure,
            self._mutate_openapi(mutate),
        )
        self.assertTrue(
            any(
                "accepts unregistered typed ID prefix 'ak:not_a_registered_kind:'"
                in failure
                for failure in failures
            ),
            failures,
        )

    # --- sweep closure --------------------------------------------------

    def test_ref_outside_the_sweep_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["components"]["schemas"]["MutationProbe"] = {
                "$ref": "../registry/id-kind-registry.json#/typed_event_token_pattern"
            }

        failures = self._run(
            lint_artifacts.check_typed_id_carrier_sweep_closure,
            self._mutate_openapi(mutate),
        )
        self.assertTrue(
            any(
                "a document outside the typed ID carrier sweep" in failure
                for failure in failures
            ),
            failures,
        )

    # --- branch expansion ------------------------------------------------

    def test_union_expansion_reports_one_payload_per_kind(self) -> None:
        branches = lint_artifacts.typed_id_payload_branches(
            f"^ak:(realm|space|view):{EVENT_TOKEN}$"
        )
        self.assertEqual(
            branches,
            [("realm", EVENT_TOKEN), ("space", EVENT_TOKEN), ("view", EVENT_TOKEN)],
        )

    def test_nested_union_expansion_keeps_each_payload(self) -> None:
        branches = lint_artifacts.typed_id_payload_branches(
            f"^((?:ak:(event):{EVENT_TOKEN}|ak:(receipt|policy):{PRODUCER_UUIDV7})"
            "|(?:sha256|blake3):[0-9a-f]{64})$"
        )
        self.assertEqual(
            branches,
            [
                ("event", EVENT_TOKEN),
                ("receipt", PRODUCER_UUIDV7),
                ("policy", PRODUCER_UUIDV7),
            ],
        )

    def test_open_kind_segment_yields_no_typed_branch(self) -> None:
        self.assertEqual(
            lint_artifacts.typed_id_payload_branches("^ak:[a-z][a-z0-9_]*:[A-Za-z0-9._:-]+$"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
