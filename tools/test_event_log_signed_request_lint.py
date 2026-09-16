"""Mutation tests for the event_log-operation signed-request gate.

The state this gate exists to make visible: an operation declares
`durable_effect.kind = "event_log"` — it writes a signed Event into the log — while
its request carries no Event to sign with, and the service is forbidden from
signing one itself. soland implements these operations through
`accept_local_operations`, which builds no wire Event at all; several of them went
on to mint the object id the missing Event would have derived.

The mutation tests deliberately use synthetic operation ids rather than whichever
real ones are still listed: the list is designed to shrink to empty, so a test
pinned to a real entry rots the moment that entry is closed.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import prose as lint_artifacts

REGISTRY = ROOT / "spec" / "v1" / "artifacts" / "registry" / "operation-registry.json"


SYNTHETIC_OPERATION_ID = "ak.self.example.command.create.v1"


class EventLogSignedRequestLintTest(unittest.TestCase):
    def _lint(self, mutate=None, listed: dict[str, str] | None = None) -> list[str]:
        target = REGISTRY.resolve()
        original = lint_artifacts.load_json
        document = original(lint_artifacts.Lint(), target)
        mutated = copy.deepcopy(document)
        if mutate is not None:
            mutate(mutated)

        def load_json_with_mutation(lint, path):
            if path.resolve() == target:
                return mutated
            return original(lint, path)

        recorded = lint_artifacts.EVENT_LOG_OPERATIONS_WITHOUT_A_SIGNED_REQUEST
        lint_artifacts.load_json = load_json_with_mutation
        if listed is not None:
            lint_artifacts.EVENT_LOG_OPERATIONS_WITHOUT_A_SIGNED_REQUEST = {
                **recorded,
                **listed,
            }
        try:
            lint = lint_artifacts.Lint()
            lint_artifacts.check_event_log_operations_carry_a_signed_event(lint)
            return lint.errors
        finally:
            lint_artifacts.load_json = original
            lint_artifacts.EVENT_LOG_OPERATIONS_WITHOUT_A_SIGNED_REQUEST = recorded

    def test_the_recorded_list_matches_the_registry(self) -> None:
        # Passes only when every unsigned event_log operation is recorded and every
        # recorded one is still unsigned.
        self.assertEqual(self._lint(), [])

    def test_a_new_unsigned_event_log_operation_fails(self) -> None:
        def mutate(registry):
            registry["operations"].append(
                {
                    "operation_id": SYNTHETIC_OPERATION_ID,
                    "http": "POST /_arkret/self/examples",
                    "idempotency_mechanism": "none",
                    "request_schema_ref": "schemas/circle-operations.schema.json#/$defs/circle_view",
                    "durable_effect": {"kind": "event_log", "event_kinds": ["ak.circle.create"]},
                }
            )

        errors = self._lint(mutate)
        self.assertTrue(
            any(SYNTHETIC_OPERATION_ID in error for error in errors),
            errors,
        )

    def test_an_operation_that_starts_carrying_an_event_must_be_delisted(self) -> None:
        # The list may only shrink. Pointing a recorded operation at a body that
        # carries `EventCommitSubmission` is what closing one looks like, and the
        # gate must then demand the entry be dropped.
        def mutate(registry):
            registry["operations"].append(
                {
                    "operation_id": SYNTHETIC_OPERATION_ID,
                    "http": "POST /_arkret/self/examples",
                    "idempotency_mechanism": "none",
                    "request_schema_ref": (
                        "schemas/service-operation-dtos.schema.json#/$defs/EventCommitSubmission"
                    ),
                    "durable_effect": {"kind": "event_log", "event_kinds": ["ak.circle.create"]},
                }
            )

        errors = self._lint(mutate, listed={SYNTHETIC_OPERATION_ID: "synthetic entry under test"})
        self.assertTrue(
            any(
                SYNTHETIC_OPERATION_ID in error and "drop it from" in error
                for error in errors
            ),
            errors,
        )

    def test_the_closed_circle_create_shape_is_what_closing_looks_like(self) -> None:
        # `ak.self.circle.command.create.v1` was the first entry closed: its request body
        # is now nothing but the caller-signed `ak.circle.create` submission.
        self.assertTrue(
            lint_artifacts._request_schema_reaches_signed_event(
                lint_artifacts.Lint(),
                "schemas/circle-operations.schema.json#/$defs/circle_create_request_body",
            )
        )

    def test_the_envelope_shape_counts_too(self) -> None:
        # `applet.command.install` references the Event envelope directly rather than
        # the submission wrapper. Both are caller-signed Events, so both must pass.
        self.assertTrue(
            lint_artifacts._request_schema_reaches_signed_event(
                lint_artifacts.Lint(),
                "schemas/applet-install-operations.schema.json#/$defs/applet_install_request_body",
            )
        )


if __name__ == "__main__":
    unittest.main()
