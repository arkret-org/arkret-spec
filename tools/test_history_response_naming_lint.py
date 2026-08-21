"""Mutation coverage for the sealed capability-addressed response-stream naming gate."""

from __future__ import annotations

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.artifact_lint.foundation import history_response_naming_violations


class HistoryResponseNamingLintTest(unittest.TestCase):
    def test_machine_retired_terms_fail(self) -> None:
        for mutation in (
            '"reply_mailbox_id"',
            '"history_mailbox_id"',
            '"ak.hpke_surface.history-mailbox-capability.v1"',
            'Authorization: Arkret-Mailbox token',
            'ak.vector.history_key.closed_mailbox_delivery.v1',
            'private history-key request and mailbox delivery',
        ):
            self.assertTrue(history_response_naming_violations(mutation), mutation)

    def test_response_stream_terms_pass(self) -> None:
        self.assertEqual(
            history_response_naming_violations(
                'response_capability_commitment history_response_page_entry '
                'Arkret-History-Capability'
            ),
            [],
        )

    def test_strict_prose_scope_rejects_all_three_retired_roots(self) -> None:
        violations = history_response_naming_violations(
            "mailbox inbox reply response stream", strict_prose=True
        )
        self.assertEqual([token for _, token in violations], ["mailbox", "inbox", "reply"])


if __name__ == "__main__":
    unittest.main()
