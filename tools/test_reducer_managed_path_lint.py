"""Mutation tests for the reducer-managed patch-path gate.

Before the registry existed, the section 4.2.5 path set lived only in prose and
every implementation carried its own copy: the SDK and the server each spelled
an object-agnostic list that had drifted apart from the spec and from each
other. Each case below reproduces the shape a regression would actually take --
a dropped universal path, an unclassified new patch surface, a payload guard
that forbids something nobody registered, a registry row that claims a guard it
does not have, an object-specific ban that silently generalises to every object
-- and asserts the gate rejects it.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import redactable_fields as lint_module

REGISTRY = lint_module.REDUCER_MANAGED_REGISTRY_PATH

EVENT_PAYLOAD = lint_module.EVENT_PAYLOAD_PATH


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


class ReducerManagedPathLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = _load(REGISTRY)
        self.payloads = _load(EVENT_PAYLOAD)
        self.real_load_json = lint_module.load_json

    def tearDown(self) -> None:
        lint_module.load_json = self.real_load_json

    def _run(self, registry: object | None = None, payloads: object | None = None) -> list[str]:
        registry = self.registry if registry is None else registry
        payloads = self.payloads if payloads is None else payloads

        def fake_load_json(lint: object, path: Path) -> object:
            if path == REGISTRY:
                return registry
            if path == EVENT_PAYLOAD:
                return payloads
            return self.real_load_json(lint, path)

        lint_module.load_json = fake_load_json
        lint = lint_module.Lint()
        lint_module.check_reducer_managed_path_registry(lint)
        return list(lint.errors)

    def _mutate(self) -> dict:
        return copy.deepcopy(self.registry)

    def _object(self, registry: dict, object_kind: str) -> dict:
        for row in registry["objects"]:
            if row["object_kind"] == object_kind:
                return row
        raise AssertionError(f"missing object row {object_kind}")

    def test_committed_registry_passes(self) -> None:
        self.assertEqual(self._run(), [])

    def test_relation_effective_scope_is_registered(self) -> None:
        # The exact 2338 gap: the ban existed only inside each implementation.
        row = self._object(self.registry, "relation")
        paths = {entry["path"]: entry for entry in row["forbidden_patch_paths"]}
        self.assertIn("effective_scope", paths)
        self.assertEqual(paths["effective_scope"]["reason_code"], "effective_scope_reducer_managed")
        self.assertTrue(paths["effective_scope"]["schema_enforced"])

    def test_dropping_a_prose_listed_universal_path_is_rejected(self) -> None:
        registry = self._mutate()
        registry["universal_forbidden_patch_paths"] = [
            row for row in registry["universal_forbidden_patch_paths"] if row["path"] != "updated_at"
        ]
        errors = self._run(registry)
        self.assertTrue(any("section 4.2.5 lists 'updated_at'" in error for error in errors), errors)

    def test_universal_path_absent_from_prose_is_rejected(self) -> None:
        registry = self._mutate()
        extra = copy.deepcopy(registry["universal_forbidden_patch_paths"][0])
        extra["path"] = "labels"
        registry["universal_forbidden_patch_paths"].append(extra)
        errors = self._run(registry)
        self.assertTrue(any("section 4.2.5 does not list it" in error for error in errors), errors)

    def test_object_specific_path_restated_as_universal_is_rejected(self) -> None:
        registry = self._mutate()
        relation = self._object(registry, "relation")
        relation["forbidden_patch_paths"][0]["path"] = "state_changed_at"
        errors = self._run(registry)
        self.assertTrue(
            any("already in the universal minimum set" in error for error in errors), errors
        )

    def test_unclassified_patch_surface_is_rejected(self) -> None:
        payloads = copy.deepcopy(self.payloads)
        payloads["$defs"]["invented_update_payload"] = {
            "type": "object",
            "required": ["patch"],
            "properties": {"patch": {"$ref": "#/$defs/patch"}},
            "additionalProperties": False,
        }
        errors = self._run(payloads=payloads)
        self.assertTrue(
            any("invented_update_payload" in error and "no object row classifies" in error for error in errors),
            errors,
        )

    def test_payload_guard_without_a_registry_row_is_rejected(self) -> None:
        payloads = copy.deepcopy(self.payloads)
        payloads["$defs"]["space_patch_payload"]["properties"]["patch"] = {
            "allOf": [
                {"$ref": "#/$defs/patch"},
                {"propertyNames": {"not": {"pattern": "^title(?:\\.|$)"}}},
            ]
        }
        errors = self._run(payloads=payloads)
        self.assertTrue(
            any("forbids patch path 'title'" in error for error in errors), errors
        )

    def test_schema_enforced_claim_without_a_guard_is_rejected(self) -> None:
        registry = self._mutate()
        strand = self._object(registry, "strand")
        for entry in strand["forbidden_patch_paths"]:
            entry["schema_enforced"] = True
        errors = self._run(registry)
        self.assertTrue(any("claims schema_enforced but" in error for error in errors), errors)

    def test_guarded_path_declared_unenforced_is_rejected(self) -> None:
        registry = self._mutate()
        relation = self._object(registry, "relation")
        relation["forbidden_patch_paths"][0]["schema_enforced"] = False
        errors = self._run(registry)
        self.assertTrue(
            any("declares schema_enforced=false but" in error for error in errors), errors
        )

    def test_unregistered_exemption_path_is_rejected(self) -> None:
        registry = self._mutate()
        space = self._object(registry, "space")
        space["universal_exemptions"] = [
            {
                "path": "title",
                "owner_kind": "event_kind",
                "owner": "ak.space.update",
                "justification": "irrelevant",
            }
        ]
        errors = self._run(registry)
        self.assertTrue(
            any("is not in the universal minimum set" in error for error in errors), errors
        )

    def test_view_state_exemption_is_declared_not_deleted(self) -> None:
        # views.md section 3.1: a shared View reaches its terminal state through
        # an ak.view.update patch, so `state` is authored on exactly this kind.
        view = self._object(self.registry, "view")
        self.assertEqual([row["path"] for row in view["universal_exemptions"]], ["state"])
        self.assertNotIn(
            "state_changed_at",
            {row["path"] for row in view["universal_exemptions"]},
        )

    def test_path_absent_from_the_object_schema_is_rejected(self) -> None:
        registry = self._mutate()
        relation = self._object(registry, "relation")
        relation["forbidden_patch_paths"][0]["path"] = "mls_group_ref"
        errors = self._run(registry)
        self.assertTrue(
            any("is not a declared property of this object schema" in error for error in errors), errors
        )

    def test_unknown_event_kind_owner_is_rejected(self) -> None:
        registry = self._mutate()
        morph = self._object(registry, "morph")
        morph["forbidden_patch_paths"][0]["owner"] = "ak.morph.retype"
        errors = self._run(registry)
        self.assertTrue(
            any("unknown or inactive event kind" in error for error in errors), errors
        )

    def test_two_object_kinds_claiming_one_payload_is_rejected(self) -> None:
        registry = self._mutate()
        space = self._object(registry, "space")
        space["update_payload_refs"].append(
            "schemas/event-payload.schema.json#/$defs/strand_patch_payload"
        )
        errors = self._run(registry)
        self.assertTrue(any("already classified by object kind" in error for error in errors), errors)

    def test_non_machine_readable_guard_pattern_is_rejected(self) -> None:
        payloads = copy.deepcopy(self.payloads)
        payloads["$defs"]["relation_update_payload"]["properties"]["patch"]["allOf"][1] = {
            "propertyNames": {"not": {"pattern": "effective"}}
        }
        errors = self._run(payloads=payloads)
        self.assertTrue(
            any("prefix-ban form" in error for error in errors), errors
        )


class ReducerManagedErrorCodeBindingTest(unittest.TestCase):
    """The reason code description must delegate to the registry, not restate it."""

    def setUp(self) -> None:
        self.real_load_json = lint_module.load_json
        self.error_codes = _load(lint_module.ERROR_CODE_PATH)

    def tearDown(self) -> None:
        lint_module.load_json = self.real_load_json

    def _run(self, error_codes: object) -> list[str]:
        def fake_load_json(lint: object, path: Path) -> object:
            if path == lint_module.ERROR_CODE_PATH:
                return error_codes
            return self.real_load_json(lint, path)

        lint_module.load_json = fake_load_json
        lint = lint_module.Lint()
        lint_module._check_reducer_managed_error_code_description(lint)
        return list(lint.errors)

    def test_description_without_registry_pointer_is_rejected(self) -> None:
        codes = copy.deepcopy(self.error_codes)
        for row in codes["reason_codes"]:
            if row.get("code") == lint_module.REDUCER_MANAGED_REASON_CODE:
                row["description"] = (
                    "A patch path touched id / schema / realm_id / created_by / created_at."
                )
        errors = self._run(codes)
        self.assertTrue(
            any("reducer-managed-path-registry.json" in error for error in errors), errors
        )

    def test_missing_reason_code_row_is_rejected(self) -> None:
        codes = copy.deepcopy(self.error_codes)
        codes["reason_codes"] = [
            row
            for row in codes["reason_codes"]
            if row.get("code") != lint_module.REDUCER_MANAGED_REASON_CODE
        ]
        errors = self._run(codes)
        self.assertTrue(any("missing error code row" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
