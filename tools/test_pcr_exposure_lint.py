"""Mutation tests for the Principal Control Realm outward-exposure gate.

The PCR write allowlist has always been closed; the read direction was not, so
an outward path could be added in prose and never be noticed. Each case below
corrupts the registry the way that failure would actually look and asserts the
gate rejects it.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import foundation as lint_artifacts

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
REGISTRY = ARTIFACTS / "registry" / "pcr-exposure-registry.json"
PROFILES = ARTIFACTS / "profiles" / "conformance-profiles.json"
OPERATIONS = ARTIFACTS / "registry" / "operation-registry.json"


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


class PcrExposureLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = _load(REGISTRY)
        self.real_load_json = lint_artifacts.load_json

    def tearDown(self) -> None:
        lint_artifacts.load_json = self.real_load_json

    def _run(self, registry: object) -> list[str]:
        def fake_load_json(lint: object, path: Path) -> object:
            if path == REGISTRY:
                return registry
            return self.real_load_json(lint, path)

        lint_artifacts.load_json = fake_load_json
        lint = lint_artifacts.Lint()
        lint_artifacts.check_pcr_exposure_registry(lint)
        return list(lint.errors)

    def _mutate(self) -> dict:
        return copy.deepcopy(self.registry)

    def test_committed_registry_passes(self) -> None:
        self.assertEqual(self._run(self.registry), [])

    def test_allowlist_kind_without_exposure_decision_is_rejected(self) -> None:
        registry = self._mutate()
        registry["event_kinds"] = [
            row for row in registry["event_kinds"] if row["event_kind"] != "ak.policy.set"
        ]
        failures = self._run(registry)
        self.assertTrue(
            any("without an exposure decision" in failure for failure in failures), failures
        )

    def test_exposure_for_unwritable_kind_is_rejected(self) -> None:
        registry = self._mutate()
        registry["event_kinds"].append({"event_kind": "ak.message.create", "exposures": []})
        failures = self._run(registry)
        self.assertTrue(
            any("outside the PCR allowlist" in failure for failure in failures), failures
        )

    def test_unregistered_operation_is_rejected(self) -> None:
        registry = self._mutate()
        for row in registry["event_kinds"]:
            for exposure in row["exposures"]:
                if exposure.get("surface") == "operation":
                    exposure["operation_id"] = "ak.self.events.read.definitely_not_registered"
                    break
            else:
                continue
            break
        failures = self._run(registry)
        self.assertTrue(
            any("is not a registered operation" in failure for failure in failures), failures
        )

    def test_unresolvable_json_pointer_is_rejected(self) -> None:
        registry = self._mutate()
        for row in registry["event_kinds"]:
            if row["exposures"] and row["exposures"][0].get("json_pointers"):
                row["exposures"][0]["json_pointers"] = ["/$defs/no_such_definition"]
                break
        failures = self._run(registry)
        self.assertTrue(
            any("does not resolve" in failure for failure in failures), failures
        )

    def test_unregistered_authorization_policy_is_rejected(self) -> None:
        registry = self._mutate()
        for row in registry["event_kinds"]:
            if row["exposures"]:
                row["exposures"][0]["authorization_policy_id"] = "ak.pcr_exposure_policy.made_up.v1"
                break
        failures = self._run(registry)
        self.assertTrue(
            any("authorization_policy_id is not registered" in failure for failure in failures),
            failures,
        )

    def test_missing_authorization_policy_is_not_read_as_public(self) -> None:
        registry = self._mutate()
        for row in registry["event_kinds"]:
            if row["exposures"]:
                row["exposures"][0].pop("authorization_policy_id", None)
                break
        failures = self._run(registry)
        self.assertTrue(
            any("authorization_policy_id is not registered" in failure for failure in failures),
            failures,
        )

    def test_operation_surface_without_direction_is_rejected(self) -> None:
        registry = self._mutate()
        for row in registry["event_kinds"]:
            for exposure in row["exposures"]:
                if exposure.get("surface") == "operation":
                    exposure.pop("direction", None)
                    break
            else:
                continue
            break
        failures = self._run(registry)
        self.assertTrue(
            any("direction must be request or response" in failure for failure in failures),
            failures,
        )

    def test_private_kind_reachable_through_a_registered_carrier_is_rejected(self) -> None:
        # The real regression shape: a carrier is widened to admit one more kind
        # while that kind is still declared PCR-private.
        registry = self._mutate()
        for row in registry["event_kinds"]:
            if row["event_kind"] == "ak.contact.requested":
                row["exposures"][0]["schema_ref"] = (
                    "schemas/contact-operations.schema.json#/$defs/peer_contact_submit_request"
                )
        for row in registry["event_kinds"]:
            if row["event_kind"] == "ak.contact.scope.update":
                row["exposures"] = []
        failures = self._run(registry)
        self.assertTrue(
            any("is reachable inside the outward carrier" in failure for failure in failures),
            failures,
        )

    def test_duplicate_event_kind_row_is_rejected(self) -> None:
        registry = self._mutate()
        registry["event_kinds"].append(copy.deepcopy(registry["event_kinds"][0]))
        failures = self._run(registry)
        self.assertTrue(
            any("duplicate event_kind rows" in failure for failure in failures), failures
        )


if __name__ == "__main__":
    unittest.main()
