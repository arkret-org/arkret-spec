"""Tests for the proof-context object-family schema gate.

The gate exists because `controller_account_gate_attestation` sat in
`proof-context-registry.json` as a `detached_signature` domain separation with ten
`binding_fields` and no schema at all: the registry promised a signed wire object
whose members and closure lived only in prose, and a downstream `schema` member
spelling an unregistered `ak.schema.*.v1` id could not be caught anywhere.

These tests pin the four rules -- an in-scope row must name a schema, the file
must be an active row of the schema registry, the pointer must resolve, and the
node must be covered by a registered schema id -- plus the rule that the gate is
actually invoked by the runner. The last one matters: a gate that is imported and
never called is indistinguishable from no gate at all.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate
from tools.artifact_lint.core import Lint

SCHEMA_FILE = "schemas/probe.schema.json"
SCHEMA_DOCUMENT = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$defs": {
        "probe_receipt": {
            "type": "object",
            "properties": {"domain": {"type": "string"}},
        }
    },
}


def run(registry: dict, schema_registry: dict, documents: dict[str, dict] | None = None) -> list[str]:
    with tempfile.TemporaryDirectory() as directory:
        artifacts = Path(directory)
        (artifacts / "registry").mkdir(parents=True)
        (artifacts / "schemas").mkdir(parents=True)
        (artifacts / "registry" / "proof-context-registry.json").write_text(
            json.dumps(registry), encoding="utf-8"
        )
        (artifacts / "registry" / "schema-registry.json").write_text(
            json.dumps(schema_registry), encoding="utf-8"
        )
        for name, document in (documents or {SCHEMA_FILE: SCHEMA_DOCUMENT}).items():
            (artifacts / name).write_text(json.dumps(document), encoding="utf-8")
        lint = Lint()
        with (
            mock.patch.object(gate, "ARTIFACTS", artifacts),
            mock.patch.object(
                gate, "PROOF_CONTEXT_REGISTRY", artifacts / "registry" / "proof-context-registry.json"
            ),
            mock.patch.object(
                gate, "SCHEMA_REGISTRY", artifacts / "registry" / "schema-registry.json"
            ),
        ):
            gate.check_proof_context_object_family_schemas(lint)
        return lint.errors


def separation(**overrides) -> dict:
    row = {
        "domain": "ak.probe.receipt.v1",
        "object_family": "probe_receipt",
        "primitive": "detached_signature",
        "binding_fields": ["domain"],
    }
    row.update(overrides)
    return row


def registry(*rows: dict) -> dict:
    return {"contexts": [], "domain_separations": list(rows)}


def schema_registry(*, fragment: str | None = None, file: str = SCHEMA_FILE) -> dict:
    row = {"schema_id": "ak.schema.probe.v1", "file": file, "status": "active"}
    if fragment is not None:
        row["fragment"] = fragment
    return {"schemas": [row]}


class ProofContextObjectFamilySchemaTest(unittest.TestCase):
    def test_signature_row_without_any_schema_reference_fails(self) -> None:
        errors = run(registry(separation()), schema_registry())
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("signs a wire object but names no schema", errors[0])

    def test_signature_row_with_resolvable_registered_schema_passes(self) -> None:
        errors = run(
            registry(separation(schema_ref=f"{SCHEMA_FILE}#/$defs/probe_receipt")),
            schema_registry(),
        )
        self.assertEqual(errors, [])

    def test_unregistered_schema_file_fails(self) -> None:
        errors = run(
            registry(separation(schema_ref=f"{SCHEMA_FILE}#/$defs/probe_receipt")),
            schema_registry(file="schemas/other.schema.json"),
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("is not an active row of registry/schema-registry.json", errors[0])

    def test_inactive_schema_row_does_not_count_as_registered(self) -> None:
        inactive = schema_registry()
        inactive["schemas"][0]["status"] = "withdrawn"
        errors = run(
            registry(separation(schema_ref=f"{SCHEMA_FILE}#/$defs/probe_receipt")),
            inactive,
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("is not an active row", errors[0])

    def test_unresolvable_pointer_fails(self) -> None:
        errors = run(
            registry(separation(schema_ref=f"{SCHEMA_FILE}#/$defs/absent")),
            schema_registry(),
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("does not resolve to a schema object", errors[0])

    def test_node_outside_every_registered_fragment_fails(self) -> None:
        errors = run(
            registry(separation(schema_ref=f"{SCHEMA_FILE}#/$defs/probe_receipt")),
            schema_registry(fragment="#/$defs/other_family"),
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("is not covered by any registered schema id", errors[0])

    def test_transcript_schema_refs_satisfy_the_rule(self) -> None:
        errors = run(
            registry(
                separation(transcript_schema_refs=[f"{SCHEMA_FILE}#/$defs/probe_receipt"])
            ),
            schema_registry(),
        )
        self.assertEqual(errors, [])

    def test_non_object_bearing_primitive_is_out_of_scope(self) -> None:
        errors = run(
            registry(separation(primitive="merkle_leaf_sha256")),
            schema_registry(),
        )
        self.assertEqual(errors, [])

    def test_context_rows_are_in_scope_without_a_primitive(self) -> None:
        errors = run(
            {
                "contexts": [
                    {
                        "context": "ak.probe_receipt_proof.v1",
                        "object_family": "probe_receipt",
                        "binding_fields": ["domain"],
                    }
                ],
                "domain_separations": [],
            },
            schema_registry(),
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("signs a wire object but names no schema", errors[0])


class ResultWriteContractTest(unittest.TestCase):
    """`result_writes[]` coverage is partial by design, so the danger is prose over-promising."""

    def run_gate(self, event_kinds: list[dict], prose: dict[str, str] | None = None) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            artifacts = Path(directory) / "artifacts"
            (artifacts / "registry").mkdir(parents=True)
            (artifacts / "registry" / "event-kind-registry.json").write_text(
                json.dumps({"event_kinds": event_kinds}), encoding="utf-8"
            )
            zh = Path(directory) / "zh"
            zh.mkdir()
            for name, text in (prose or {}).items():
                (zh / name).write_text(text, encoding="utf-8")
            lint = Lint()
            with (
                mock.patch.object(gate, "ARTIFACTS", artifacts),
                mock.patch.object(
                    gate, "EVENT_KIND_REGISTRY", artifacts / "registry" / "event-kind-registry.json"
                ),
            ):
                gate.check_result_write_contracts(lint)
            return lint.errors

    @staticmethod
    def kind(**overrides) -> dict:
        row = {
            "event_kind": "ak.probe.write",
            "reducer_input": True,
            "result_writes": [
                {
                    "result_family": "probe_result",
                    "result_selector": None,
                    "result_projection": {"kind": "set", "value": {"field": "payload.value"}},
                }
            ],
        }
        row.update(overrides)
        return row

    def test_minimal_contract_passes(self) -> None:
        self.assertEqual(self.run_gate([self.kind()]), [])

    def test_missing_result_selector_fails(self) -> None:
        row = self.kind()
        del row["result_writes"][0]["result_selector"]
        errors = self.run_gate([row])
        self.assertTrue(any("result_selector is required" in e for e in errors), errors)

    def test_selector_kind_outside_the_closed_table_fails(self) -> None:
        row = self.kind()
        row["result_writes"][0]["result_selector"] = {"kind": "canonical_json", "field": "payload.x"}
        errors = self.run_gate([row])
        self.assertTrue(any("closed subject table" in e for e in errors), errors)

    def test_unregistered_derivation_fails(self) -> None:
        row = self.kind()
        row["result_writes"][0]["derived_members"] = [
            {"name": "whatever", "derivation": "invented_derivation"}
        ]
        errors = self.run_gate([row])
        self.assertTrue(any("derivation must be one of" in e for e in errors), errors)

    def test_non_reducer_input_kind_may_not_declare_writes(self) -> None:
        errors = self.run_gate([self.kind(reducer_input=False)])
        self.assertTrue(any("not a reducer_input Event kind" in e for e in errors), errors)

    def test_prose_may_cite_a_declared_kind(self) -> None:
        errors = self.run_gate(
            [self.kind()],
            prose={"probe.md": "see ak.probe.write.result_writes[] for the contract"},
        )
        self.assertEqual(errors, [])

    def test_prose_citing_an_undeclared_kind_fails(self) -> None:
        errors = self.run_gate(
            [self.kind()],
            prose={"probe.md": "see ak.other.kind.result_writes[] for the contract"},
        )
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("declares no result_writes", errors[0])


class GateIsWiredTest(unittest.TestCase):
    """A gate that is imported but never called is the failure mode this repo has hit."""

    def test_runner_calls_both_new_gates(self) -> None:
        source = (ROOT / "tools" / "artifact_lint" / "runner.py").read_text(encoding="utf-8")
        for name in (
            "check_proof_context_object_family_schemas",
            "check_result_write_contracts",
        ):
            self.assertIn(f"{name}(lint)", source, f"{name} is imported but never invoked")

    def test_live_registry_passes_the_gate(self) -> None:
        lint = Lint()
        gate.check_proof_context_object_family_schemas(lint)
        self.assertEqual(lint.errors, [])

    def test_live_result_write_contracts_pass(self) -> None:
        lint = Lint()
        gate.check_result_write_contracts(lint)
        self.assertEqual(lint.errors, [])


if __name__ == "__main__":
    unittest.main()
