"""Mutation tests for the two wire lexical closures of common-fields.md.

Both closures answer a question that no other gate asks, so both need a mutation
that proves the gate can actually fail:

* NC-FIELDCASE-001 -- a declared property name that is not snake_case. The gate
  only exempts an object that declares ``x-arkret-external-literal-object`` on
  its own schema node, so the mutations here cover the three ways that mechanism
  can be broken: a camelCase name on an unmarked object, an annotation without an
  external anchor, and an annotation that no longer exempts anything.
* NC-IDENTIFIER-001 lexical disjointness -- an identifier field whose value
  category does not own the ``ak:`` namespace but whose terminal constraint
  admits an ``ak:`` value anyway. This is the direction the typed-ID prefix
  closure cannot see: that closure only decides whether an ``ak:<kind>:`` it
  finds is registered.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.core import (
    ARTIFACTS,
    Lint,
    parse_json_file,
    parse_yaml_file,
    read_text,
)
from tools.artifact_lint.naming import (
    EXTERNAL_LITERAL_OBJECT_KEYWORD,
    nc_fieldcase_001,
    pattern_excludes_prefix,
    terminal_excludes_typed_id_namespace,
)
from tools.artifact_lint.naming_contracts import check_identifier_value_categories

SCHEMA_DIR = ARTIFACTS / "schemas"
DTO_SCHEMA = SCHEMA_DIR / "service-operation-dtos.schema.json"
PUSH_SCHEMA = SCHEMA_DIR / "push-operations.schema.json"
PATCH_SCHEMA = SCHEMA_DIR / "patch.schema.json"

# The verbatim did:webvh parameters mirror: the only reason the exemption
# mechanism exists, and the object every exemption mutation below targets.
WEBVH_PARAMETERS = "ServiceWebvhInceptionParameters"
# An ordinary Arkret-owned DTO in the same file, used to prove the exemption
# cannot leak out of the object that declares it.
ARKRET_OWNED_DTO = "DirectoryTakedownAppealRequestBody"


def drop_reader_caches() -> None:
    read_text.cache_clear()
    parse_json_file.cache_clear()
    parse_yaml_file.cache_clear()


def run_closure() -> Lint:
    drop_reader_caches()
    lint = Lint()
    check_identifier_value_categories(lint)
    return lint


class MutationHarness(unittest.TestCase):
    def errors_with(self, path: Path, mutate) -> list[str]:
        """Apply a mutation, run the closure, always restore the original bytes."""

        original = path.read_bytes()
        document = json.loads(original.decode("utf-8"))
        mutate(document)
        try:
            path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            return run_closure().errors
        finally:
            path.write_bytes(original)
            drop_reader_caches()

    def assertAnyContains(self, errors: list[str], needle: str) -> None:
        self.assertTrue(
            any(needle in error for error in errors),
            f"expected an error mentioning {needle!r}, got {errors}",
        )


class BaselineTest(unittest.TestCase):
    def test_closure_reports_no_lexical_violation(self) -> None:
        errors = [
            error
            for error in run_closure().errors
            if "NC-FIELDCASE-001" in error
            or EXTERNAL_LITERAL_OBJECT_KEYWORD in error
            or "typed-ID namespace" in error
        ]
        self.assertEqual(errors, [])


class FieldCasePredicateTest(unittest.TestCase):
    def test_snake_case_names_are_accepted(self) -> None:
        for name in ("id", "pairing_request_id", "x_vendor_hint", "a1_b2"):
            self.assertFalse(nc_fieldcase_001(name), name)

    def test_foreign_lexicon_names_are_rejected(self) -> None:
        for name in ("nextKeyHashes", "@context", "serviceEndpoint", "Realm_id", "trailing_"):
            self.assertTrue(nc_fieldcase_001(name), name)

    def test_reserved_directive_sigil_still_judges_the_remainder(self) -> None:
        # `$op` is the patch grammar's discriminator; the sigil is what keeps it
        # out of the data-field namespace, so only the remainder is judged.
        self.assertFalse(nc_fieldcase_001("$op"))
        self.assertTrue(nc_fieldcase_001("$Op"))
        self.assertTrue(nc_fieldcase_001("$nextOp"))


class FieldCaseGateTest(MutationHarness):
    def test_camel_case_property_on_an_unmarked_object_fails(self) -> None:
        def mutate(document):
            target = document["$defs"][ARKRET_OWNED_DTO]["properties"]
            target["pushRouteToken"] = {"type": "string"}

        errors = self.errors_with(DTO_SCHEMA, mutate)
        self.assertAnyContains(errors, "NC-FIELDCASE-001")
        self.assertAnyContains(errors, "pushRouteToken")

    def test_camel_case_property_inside_a_marked_object_is_exempt(self) -> None:
        def mutate(document):
            document["$defs"][WEBVH_PARAMETERS]["properties"]["witnessThreshold"] = {
                "type": "integer"
            }

        errors = [
            error for error in self.errors_with(DTO_SCHEMA, mutate) if "NC-FIELDCASE-001" in error
        ]
        self.assertEqual(errors, [])

    def test_annotation_without_an_external_anchor_fails(self) -> None:
        def mutate(document):
            document["$defs"][WEBVH_PARAMETERS][EXTERNAL_LITERAL_OBJECT_KEYWORD] = {
                "specification": "did:webvh v1.0",
                "anchor": "https://identity.foundation/didwebvh/v1.0/",
            }

        errors = self.errors_with(DTO_SCHEMA, mutate)
        self.assertAnyContains(errors, "section fragment")

    def test_annotation_that_exempts_nothing_is_stale(self) -> None:
        def mutate(document):
            document["$defs"][ARKRET_OWNED_DTO][
                EXTERNAL_LITERAL_OBJECT_KEYWORD
            ] = {
                "specification": "did:webvh v1.0, did:webvh DID method parameters",
                "anchor": "https://identity.foundation/didwebvh/v1.0/#didwebvh-did-method-parameters",
            }

        errors = self.errors_with(DTO_SCHEMA, mutate)
        self.assertAnyContains(errors, "stale annotation")

    def test_exemption_does_not_leak_to_a_same_named_type_elsewhere(self) -> None:
        # The annotation is exact by construction: another object may not borrow
        # it by declaring the same property name.
        def mutate(document):
            document["$defs"][ARKRET_OWNED_DTO]["properties"]["updateKeys"] = {
                "type": "array",
                "items": {"type": "string"},
            }

        errors = self.errors_with(DTO_SCHEMA, mutate)
        self.assertAnyContains(errors, "updateKeys")

    def test_reserved_directive_key_stays_legal_in_the_patch_grammar(self) -> None:
        document = json.loads(PATCH_SCHEMA.read_text(encoding="utf-8"))
        op_form = document["additionalProperties"]["oneOf"][1]
        self.assertIn("$op", op_form["properties"])
        self.assertFalse(nc_fieldcase_001("$op"))


class NamespaceDisjointnessAnalyzerTest(unittest.TestCase):
    def test_lookahead_and_diverging_heads_exclude_the_namespace(self) -> None:
        for pattern in (
            "^(?!ak:)[A-Za-z0-9._:-]{1,128}$",
            "^appeal:[A-Za-z0-9._-]{1,128}$",
            "^(sha256|blake3):[0-9a-f]{64}$",
            "^[1-9][0-9]*-[^\\s]+$",
            "^ak\\.[A-Za-z0-9._:-]+$",
        ):
            self.assertTrue(pattern_excludes_prefix(pattern, "ak:"), pattern)

    def test_a_colon_free_alphabet_excludes_the_namespace(self) -> None:
        for pattern in ("^[A-Za-z0-9._-]{1,128}$", "^[a-z][a-z0-9_]{0,63}$", "^AK-SDK-[0-9]{3}$"):
            self.assertTrue(pattern_excludes_prefix(pattern, "ak:"), pattern)

    def test_a_colon_bearing_open_class_does_not_exclude_the_namespace(self) -> None:
        for pattern in (
            "^[A-Za-z0-9._:-]{1,128}$",
            "^[a-z0-9][a-z0-9._+-]{0,127}:[a-z0-9.-]{1,253}$",
            "[A-Za-z0-9._:-]{1,128}",
        ):
            self.assertFalse(pattern_excludes_prefix(pattern, "ak:"), pattern)

    def test_const_and_enum_terminals_are_judged_by_value(self) -> None:
        self.assertTrue(terminal_excludes_typed_id_namespace("const", "routing_digest"))
        self.assertFalse(terminal_excludes_typed_id_namespace("const", "ak:pushreg:1"))
        self.assertFalse(terminal_excludes_typed_id_namespace("enum", "hidden|ak:pushreg:1"))

    def test_a_bare_type_terminal_is_undecidable_rather_than_safe(self) -> None:
        self.assertIsNone(terminal_excludes_typed_id_namespace("type", '"string"'))


class NamespaceDisjointnessGateTest(MutationHarness):
    def test_reopening_the_colon_class_on_an_opaque_correlation_fails(self) -> None:
        def mutate(document):
            document["$defs"]["registration_id"]["pattern"] = "^[A-Za-z0-9._:-]{1,128}$"

        errors = self.errors_with(PUSH_SCHEMA, mutate)
        self.assertAnyContains(errors, "typed-ID namespace")

    def test_an_explicitly_typed_prefix_on_a_non_typed_field_fails(self) -> None:
        def mutate(document):
            document["$defs"]["registration_id"]["pattern"] = "^ak:pushreg:[A-Za-z0-9]{1,64}$"

        errors = self.errors_with(PUSH_SCHEMA, mutate)
        # `pushreg` is not a registered kind, so the type system cannot derive a
        # typed_object_id and the widened terminal has no classification row yet.
        # An occurrence nobody classified is judged as owning nothing, so the gate
        # fires rather than waiting for the registry to catch up.
        self.assertAnyContains(errors, "typed-ID namespace")


if __name__ == "__main__":
    unittest.main()
