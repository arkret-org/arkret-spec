"""Mutation tests for the schema -> id-kind-registry typed-ID prefix closure.

The registry direction has always been checked: a registered kind must have a
matching schema regex. Nothing checked the other direction, so a schema could
mint a typed prefix that no registry row declares while the wire contract says
an unregistered ``ak:<kind>:`` MUST fail closed. Each case below corrupts an
artifact the way that failure actually looks and asserts the gate rejects it.
"""

from __future__ import annotations

import copy
import inspect
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import foundation as lint_artifacts
from tools.artifact_lint import runner

ARTIFACTS = ROOT / "spec" / "v1" / "artifacts"
ID_KIND_REGISTRY = ARTIFACTS / "registry" / "id-kind-registry.json"
SYNTHETIC = ARTIFACTS / "schemas" / "synthetic.schema.json"


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def pattern_carriers(*patterns: str) -> list[tuple[Path, str, str, set[str]]]:
    """Build carrier rows through the real regex expander."""
    rows: list[tuple[Path, str, str, set[str]]] = []
    for index, pattern in enumerate(patterns):
        found: set[str] = set()
        for text, _complete in lint_artifacts.regex_literal_branches(pattern):
            found |= lint_artifacts.literal_typed_id_prefixes(text)
        rows.append((SYNTHETIC, f"$.$defs.case_{index}.pattern", pattern, found))
    return rows


class TypedIdPrefixClosureLintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = _load(ID_KIND_REGISTRY)
        self.real_load_json = lint_artifacts.load_json
        self.real_carriers = lint_artifacts.schema_typed_id_prefix_carriers

    def tearDown(self) -> None:
        lint_artifacts.load_json = self.real_load_json
        lint_artifacts.schema_typed_id_prefix_carriers = self.real_carriers

    def _run(self, registry: object, carriers: object | None) -> list[str]:
        def fake_load_json(lint: object, path: Path) -> object:
            if path == ID_KIND_REGISTRY:
                return registry
            return self.real_load_json(lint, path)

        lint_artifacts.load_json = fake_load_json
        if carriers is not None:
            lint_artifacts.schema_typed_id_prefix_carriers = lambda lint: carriers
        lint = lint_artifacts.Lint()
        lint_artifacts.check_typed_id_prefix_registry_closure(lint)
        return list(lint.errors)

    def _mutate(self) -> dict:
        return copy.deepcopy(self.registry)

    # --- committed tree -------------------------------------------------

    def test_committed_artifacts_pass(self) -> None:
        self.assertEqual(self._run(self.registry, None), [])

    def test_gate_runs_from_the_artifact_lint_entry_point(self) -> None:
        self.assertIs(
            runner.check_typed_id_prefix_registry_closure,
            lint_artifacts.check_typed_id_prefix_registry_closure,
        )
        self.assertIn(
            "check_typed_id_prefix_registry_closure(lint)",
            inspect.getsource(runner.main),
        )

    # --- schema-side mutations -----------------------------------------

    def test_unknown_snake_prefix_is_rejected(self) -> None:
        failures = self._run(
            self.registry,
            pattern_carriers("^ak:organization_registration_challenges:[0-9a-f]{64}$"),
        )
        self.assertTrue(
            any(
                "ak:organization_registration_challenges:" in failure for failure in failures
            ),
            failures,
        )

    def test_unknown_kebab_prefix_is_rejected(self) -> None:
        failures = self._run(
            self.registry,
            pattern_carriers("^ak:organization-registration-challenge:[0-9a-f]{64}$"),
        )
        self.assertTrue(
            any(
                "ak:organization-registration-challenge:" in failure for failure in failures
            ),
            failures,
        )

    def test_spelling_drift_inside_a_registered_family_is_rejected(self) -> None:
        failures = self._run(
            self.registry,
            pattern_carriers("^ak:organization_registration_reciept:[0-9a-f]{64}$"),
        )
        self.assertTrue(
            any("ak:organization_registration_reciept:" in failure for failure in failures),
            failures,
        )

    def test_grouped_regex_branch_is_expanded(self) -> None:
        failures = self._run(
            self.registry,
            pattern_carriers("^ak:(message|not_a_registered_kind):[A-Za-z0-9_-]{44}$"),
        )
        self.assertTrue(
            any("ak:not_a_registered_kind:" in failure for failure in failures), failures
        )
        self.assertFalse(any("ak:message:" in failure for failure in failures), failures)

    def test_union_pattern_with_only_registered_branches_passes(self) -> None:
        self.assertEqual(
            self._run(
                self.registry,
                pattern_carriers(
                    "^((?:ak:(message|strand):[A-Za-z0-9_-]{44}"
                    "|ak:(blob):[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}"
                    "-[89ab][0-9a-f]{3}-[0-9a-f]{12})|ak:blob:(sha256|blake3):[0-9a-f]{64})$"
                ),
            ),
            [],
        )

    def test_registered_special_form_segment_is_recognized(self) -> None:
        self.assertEqual(
            self._run(
                self.registry,
                pattern_carriers(
                    "^ak:membership_compensation_delegation:sha256:[0-9a-f]{64}$"
                ),
            ),
            [],
        )

    def test_open_kind_segment_declares_no_literal_prefix(self) -> None:
        self.assertEqual(
            self._run(self.registry, pattern_carriers("^ak:[a-z][a-z0-9_]*:[A-Za-z0-9._:-]+$")),
            [],
        )

    def test_const_carrier_is_swept(self) -> None:
        carriers = lint_artifacts.typed_id_prefix_carriers_in_document(
            SYNTHETIC, {"$defs": {"row": {"const": "ak:not_a_registered_kind:abc"}}}
        )
        failures = self._run(self.registry, carriers)
        self.assertTrue(
            any("ak:not_a_registered_kind:" in failure for failure in failures), failures
        )

    def test_enum_carrier_is_swept(self) -> None:
        carriers = lint_artifacts.typed_id_prefix_carriers_in_document(
            SYNTHETIC,
            {"$defs": {"row": {"enum": ["ak:cursor:abc", "ak:not_a_registered_kind:abc"]}}},
        )
        failures = self._run(self.registry, carriers)
        self.assertEqual(len(failures), 1, failures)
        self.assertIn(
            "unregistered typed ID prefix 'ak:not_a_registered_kind:'", failures[0]
        )

    def test_shape_reused_through_a_local_ref_is_swept_at_its_definition(self) -> None:
        document = {
            "$defs": {
                "shared_id": {
                    "type": "string",
                    "pattern": "^ak:not_a_registered_kind:[0-9a-f]{64}$",
                }
            },
            "properties": {"target_id": {"$ref": "#/$defs/shared_id"}},
        }
        carriers = lint_artifacts.typed_id_prefix_carriers_in_document(SYNTHETIC, document)
        self.assertEqual(len(carriers), 1)
        failures = self._run(self.registry, carriers)
        self.assertTrue(
            any("ak:not_a_registered_kind:" in failure for failure in failures), failures
        )

    # --- registry-side mutations ---------------------------------------

    def test_wire_segment_differing_from_kind_is_rejected(self) -> None:
        registry = self._mutate()
        registry["special_forms"][0]["wire_form"] = registry["special_forms"][0][
            "wire_form"
        ].replace("ak:", "ak:not-the-kind-", 1)
        failures = self._run(registry, [])
        self.assertTrue(
            any("MUST equal its snake_case kind verbatim" in failure for failure in failures),
            failures,
        )

    def test_a_wire_segment_rationale_no_longer_buys_an_exception(self) -> None:
        registry = self._mutate()
        registry["special_forms"][0]["wire_segment_rationale"] = "historical spelling"
        failures = self._run(registry, [])
        self.assertTrue(
            any("no longer admit spelling exceptions" in failure for failure in failures),
            failures,
        )

    def test_unparsable_wire_form_is_rejected(self) -> None:
        registry = self._mutate()
        registry["special_forms"][0]["wire_form"] = "cursor:<base64url>"
        failures = self._run(registry, [])
        self.assertTrue(
            any("does not start with a parsable" in failure for failure in failures), failures
        )

    def test_two_kinds_claiming_one_prefix_are_rejected(self) -> None:
        registry = self._mutate()
        registry["special_forms"].append(
            {
                "kind": "cursor_shadow",
                "wire_form": "ak:cursor:<base64url>",
                "status": "active",
                "storage_recommendation": "n/a",
                "description": "n/a",
            }
        )
        failures = self._run(registry, [])
        self.assertTrue(
            any("MUST resolve to exactly one registered kind" in failure for failure in failures),
            failures,
        )

    def test_organization_special_forms_are_registered(self) -> None:
        prefixes, errors = lint_artifacts.registered_typed_id_wire_prefixes(self.registry)
        self.assertEqual(errors, [])
        self.assertEqual(
            prefixes.get("ak:organization_registration_challenge:"),
            "organization_registration_challenge",
        )
        self.assertEqual(
            prefixes.get("ak:organization_registration_receipt:"),
            "organization_registration_receipt",
        )
        self.assertNotIn("ak:service-registration:", prefixes)


if __name__ == "__main__":
    unittest.main()
