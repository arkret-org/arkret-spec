"""Mutation tests for the Agent runtime key binding digest chain.

`agent-vectors-fixture.json` once rewrote the Agent identity inside
`canonical_binding_json` without recomputing `expected_binding_digest`, the
proof's `runtime_key_binding_digest`, the possession transcript that embeds it,
or the transcript digest. Every stated value stayed a well-formed digest, so no
shape gate noticed that no verifier could reproduce the vector. The chain is now
recomputed from its preimages; each case below corrupts one link.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as fixture_lint

FIXTURE = ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "agent-vectors-fixture.json"


def _runtime_case() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return next(case for case in data["cases"] if case.get("name") == "agent_runtime_key_binding")


def _run(case: dict) -> list[str]:
    lint = fixture_lint.Lint()
    fixture_lint.check_agent_runtime_key_binding_digest_chain(
        lint, FIXTURE, case, case["proof_of_possession"]
    )
    return list(lint.errors)


class AgentRuntimeKeyBindingDigestChainTest(unittest.TestCase):
    def test_committed_chain_recomputes(self) -> None:
        self.assertEqual(_run(_runtime_case()), [])

    def test_identity_rewrite_without_digest_recompute_is_rejected(self) -> None:
        case = _runtime_case()
        binding = json.loads(case["canonical_binding_json"])
        binding["agent_id"] = "ak:did_core:webvh:z6mkagent"
        case["canonical_binding_json"] = fixture_lint.canonical_json(binding)
        case["pairing_request_binding_input"]["agent_id"] = binding["agent_id"]
        failures = _run(case)
        self.assertTrue(any("expected_binding_digest drifted" in failure for failure in failures), failures)
        self.assertTrue(
            any("canonical_possession_transcript_json is not the JCS signing input" in failure for failure in failures),
            failures,
        )

    def test_stale_transcript_digest_is_rejected(self) -> None:
        case = _runtime_case()
        case["proof_of_possession"]["transcript_digest"] = "sha256:" + "0" * 64
        failures = _run(case)
        self.assertTrue(
            any("proof_of_possession.transcript_digest drifted" in failure for failure in failures), failures
        )

    def test_public_key_digest_is_bound_to_raw_key_bytes(self) -> None:
        case = copy.deepcopy(_runtime_case())
        case["source_public_key"]["key"] = "AQ" + case["source_public_key"]["key"][2:]
        failures = _run(case)
        self.assertTrue(any("drifted from the raw public key" in failure for failure in failures), failures)

    def test_gate_is_wired_into_the_agent_fixture_check(self) -> None:
        import inspect

        self.assertIn(
            "check_agent_runtime_key_binding_digest_chain(",
            inspect.getsource(fixture_lint.check_agent_requested_scope_commitment_digest),
        )


if __name__ == "__main__":
    unittest.main()
