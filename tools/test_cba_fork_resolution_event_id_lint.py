"""Tests for semantic Event-ID checks in CBA fork-resolution payloads."""

from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint.fixtures import _event_id_validation_error


def event_id_with_header(header: int) -> str:
    body = bytes([header]) + bytes(range(32))
    token = base64.urlsafe_b64encode(body).rstrip(b"=").decode("ascii")
    return "ak:event:" + token


class CbaForkResolutionEventIdLintTest(unittest.TestCase):
    def test_active_suite_header_passes(self) -> None:
        self.assertIsNone(_event_id_validation_error(event_id_with_header(0x01), {0x01, 0x02}))

    def test_zero_suite_header_fails(self) -> None:
        error = _event_id_validation_error(event_id_with_header(0x00), {0x01, 0x02})
        self.assertIn("invalid digest-suite code 0x0", error or "")

    def test_reserved_low_nibble_fails(self) -> None:
        error = _event_id_validation_error(event_id_with_header(0x03), {0x01, 0x02})
        self.assertIn("inactive or unassigned digest-suite code 0x3", error or "")

    def test_nonzero_reserved_high_nibble_fails(self) -> None:
        error = _event_id_validation_error(event_id_with_header(0x11), {0x01, 0x02})
        self.assertIn("non-zero reserved header nibble", error or "")


if __name__ == "__main__":
    unittest.main()
