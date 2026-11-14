"""Keep authorization names separate from the existing Event evidence heuristic."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import check_event_kind_vector_gaps as gate


KIND = "ak.moderation.decision"
TOKENS = [KIND, KIND.replace(".", "_"), "moderation_decision"]


class EventKindVectorGapTest(unittest.TestCase):
    def run_check(self, fixture, *, declared=True, vector=None, prose=""):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = root / "spec/v1/artifacts"
            documents = {
                artifacts / "fixtures/authority.json": fixture,
                artifacts / "registry/vector-registry.json": vector or {},
                artifacts / "profiles/conformance-profiles.json": {},
                artifacts / "registry/event-kind-registry.json": {
                    "event_kinds": [{"event_kind": KIND, "status": "active"}]},
                artifacts / "registry/event-kind-vector-gap-registry.json": {
                    "uncovered_event_kinds": [{"event_kind": KIND, "priority": "high",
                                               "rationale": "Acceptance evidence is pending."}]
                    if declared else []},
            }
            for path, document in documents.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(document), encoding="utf-8")
            page = root / "spec/v1/zh/conformance/conformance-vectors.md"
            page.parent.mkdir(parents=True)
            page.write_text(prose, encoding="utf-8")
            output = io.StringIO()
            with (patch.object(gate, "ROOT", root), patch.object(gate, "ARTIFACTS", artifacts),
                  patch.object(gate, "REGISTRY", artifacts / "registry/event-kind-vector-gap-registry.json"),
                  contextlib.redirect_stdout(output)):
                result = gate.main()
            return result, output.getvalue()

    def test_action_and_permission_lists_cannot_erase_an_existing_gap(self):
        for field in ("actions", "permissions", "applies_to_actions", "parent_actions",
                      "required_capability_actions", "granted_permissions"):
            for token in TOKENS:
                with self.subTest(field=field, token=token):
                    self.assertEqual(self.run_check({"grant": {field: [token]}})[0], 0)

    def test_a_permission_only_mention_still_requires_the_declared_gap(self):
        result, output = self.run_check({"actions": [KIND]}, declared=False)
        self.assertEqual(result, 1)
        self.assertIn("missing=['ak.moderation.decision']", output)

    def test_canonical_json_permissions_do_not_supply_event_evidence(self):
        fixture = {"canonical_json": json.dumps({"grant": {"actions": [KIND]}})}
        self.assertEqual(self.run_check(fixture)[0], 0)

    def test_event_kind_remains_evidence_beside_its_permission_payload(self):
        fixture = {"event": {"kind": KIND, "payload": {"actions": ["ak.event.read"]}}}
        self.assertEqual(self.run_check(fixture, declared=False)[0], 0)
        result, output = self.run_check(fixture)
        self.assertEqual(result, 1)
        self.assertIn("stale=['ak.moderation.decision']", output)

    def test_canonical_json_event_kind_is_retained(self):
        fixture = {"canonical_json": json.dumps({"event": {"kind": KIND, "payload": {}}})}
        self.assertEqual(self.run_check(fixture, declared=False)[0], 0)

    def test_explicit_vectors_and_prose_keep_the_existing_topic_heuristic(self):
        for token in TOKENS:
            with self.subTest(source="vector", token=token):
                self.assertEqual(self.run_check({}, declared=False, vector={"vector": token})[0], 0)
            with self.subTest(source="prose", token=token):
                self.assertEqual(self.run_check({}, declared=False, prose=token)[0], 0)


if __name__ == "__main__":
    unittest.main()
