"""Focused regression tests for Event-derived typed-ID prose."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.prose import event_derived_uuid_wording_errors


class EventDerivedIdProseLintTest(unittest.TestCase):
    def test_rejects_retired_event_uuid_wording(self) -> None:
        stale = (
            "the reducer materialises it by retyping the event_id UUID; "
            "scope_key is realm:<realm_uuid>; "
            "the target is ak:strand:<uuidv7>"
        )
        self.assertEqual(len(event_derived_uuid_wording_errors(stale)), 3)

    def test_accepts_complete_token_wording_and_producer_uuid(self) -> None:
        current = (
            "the reducer retypes the complete EventId token; "
            "scope_key is realm:<realm_id>, where realm_id is the complete typed token; "
            "a producer-allocated device remains ak:device:<uuidv7>"
        )
        self.assertEqual(event_derived_uuid_wording_errors(current), [])


if __name__ == "__main__":
    unittest.main()
