"""Mutation tests for the spec-side active vector -> fixture traceability gate.

The gate mirrors Cotest's strict vector registry gate. Before it existed, 61
active rows had no fixture source_ref at all and the spec release gate stayed
green while Cotest strict mode failed them as ActiveDocOnly. Each case below
reproduces one way a row can claim evidence it does not carry.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import check_vector_registry_traceability as gate

FIXTURE_REF = "spec/v1/artifacts/fixtures/example-fixture.json"
VECTOR = "ak.vector.example.traceable.v1"


class VectorRegistryTraceabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "spec/v1/artifacts/fixtures").mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _fixture(self, document: object, *, crlf: bool = False) -> dict[str, str]:
        text = json.dumps(document, indent=2) + "\n"
        data = text.replace("\n", "\r\n").encode("utf-8") if crlf else text.encode("utf-8")
        (self.root / FIXTURE_REF).write_bytes(data)
        return {FIXTURE_REF: gate.fixture_digest_hex(data)}

    def _run(self, row: dict, digests: dict[str, str] | None) -> list[str]:
        return gate.registry_errors({"vectors": [row]}, self.root, digests)

    def _active(self, source_refs: list[str]) -> dict:
        return {"vector_id": VECTOR, "status": "active", "description": "x", "source_refs": source_refs}

    def test_committed_registry_is_traceable(self) -> None:
        registry = json.loads(gate.VECTOR_REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(
            gate.registry_errors(registry, gate.ROOT, gate.load_fixture_digests(gate.FIXTURE_DIGESTS)), []
        )

    def test_active_doc_only_row_is_rejected(self) -> None:
        errors = self._run(self._active(["spec/v1/zh/conformance/conformance-vectors.md"]), {})
        self.assertTrue(any("active doc-only" in error for error in errors), errors)

    def test_each_evidence_member_is_accepted(self) -> None:
        for document in (
            {"cases": [{"vector_id": VECTOR}]},
            {"negative_cases_vector_id": VECTOR},
            {"vectors": [{"name": VECTOR}]},
            {"covers_vectors": [VECTOR]},
        ):
            with self.subTest(document=document):
                self.assertEqual(self._run(self._active([FIXTURE_REF]), self._fixture(document)), [])

    def test_description_mention_is_not_evidence(self) -> None:
        digests = self._fixture({"description": f"also exercises {VECTOR}", "covers_vectors": []})
        errors = self._run(self._active([FIXTURE_REF]), digests)
        self.assertTrue(any("vector_id not found" in error for error in errors), errors)

    def test_fixture_digest_drift_and_missing_listing_are_rejected(self) -> None:
        self._fixture({"covers_vectors": [VECTOR]})
        drift = self._run(self._active([FIXTURE_REF]), {FIXTURE_REF: "0" * 64})
        self.assertTrue(any("fixture digest drift" in error for error in drift), drift)
        unlisted = self._run(self._active([FIXTURE_REF]), {})
        self.assertTrue(any("not listed" in error for error in unlisted), unlisted)
        missing_report = self._run(self._active([FIXTURE_REF]), None)
        self.assertTrue(any("report" in error for error in missing_report), missing_report)

    def test_crlf_checkout_does_not_create_false_drift(self) -> None:
        lf = self._fixture({"covers_vectors": [VECTOR]})
        self._fixture({"covers_vectors": [VECTOR]}, crlf=True)
        self.assertEqual(self._run(self._active([FIXTURE_REF]), lf), [])

    def test_missing_fixture_file_is_rejected(self) -> None:
        errors = self._run(self._active(["spec/v1/artifacts/fixtures/absent.json"]), {})
        self.assertTrue(any("file not found" in error for error in errors), errors)

    def test_non_gating_rows_need_a_reason(self) -> None:
        for status in ("reserved", "unsupported"):
            with self.subTest(status=status):
                row = {"vector_id": VECTOR, "status": status, "description": "  ", "source_refs": []}
                self.assertTrue(self._run(row, {}))
                row["description"] = "Reserved until a fixture exists."
                self.assertEqual(self._run(row, {}), [])

    def test_other_status_is_rejected(self) -> None:
        row = {"vector_id": VECTOR, "status": "deprecated", "description": "x", "source_refs": []}
        errors = self._run(row, {})
        self.assertTrue(any("unsupported registry status" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
