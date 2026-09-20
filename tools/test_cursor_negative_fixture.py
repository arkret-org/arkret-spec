from __future__ import annotations

import copy
import json
import unittest

from tools.check_cursor_negative_fixture import (
    CASE_ID,
    FIXTURE,
    MAX_DECODED_BODY_BYTES,
    MAX_ENCODED_BODY_CHARS,
    PREFIX,
    validation_errors,
)


class CursorNegativeFixtureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.document = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def oversized_case(self, document: dict | None = None) -> dict:
        source = document if document is not None else self.document
        return next(
            case
            for case in source["vectors"][0]["cases"]
            if case["name"] == CASE_ID
        )

    def test_committed_vector_hits_the_production_pre_decode_size_branch(self) -> None:
        self.assertEqual(MAX_DECODED_BODY_BYTES, 4096)
        self.assertEqual(MAX_ENCODED_BODY_CHARS, 5464)
        self.assertEqual(validation_errors(self.document), [])
        encoded = self.oversized_case()["input_cursor"].removeprefix(PREFIX)
        self.assertEqual(len(encoded), 6000)

    def test_old_1024_character_false_positive_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.document)
        self.oversized_case(mutated)["input_cursor"] = PREFIX + "A" * 1024
        self.assertTrue(
            any("requires > 5464" in error for error in validation_errors(mutated))
        )

    def test_exact_encoded_ceiling_does_not_count_as_oversized(self) -> None:
        mutated = copy.deepcopy(self.document)
        self.oversized_case(mutated)["input_cursor"] = (
            PREFIX + "A" * MAX_ENCODED_BODY_CHARS
        )
        self.assertTrue(
            any("requires > 5464" in error for error in validation_errors(mutated))
        )

    def test_oversized_non_base64url_does_not_satisfy_the_vector(self) -> None:
        mutated = copy.deepcopy(self.document)
        self.oversized_case(mutated)["input_cursor"] = PREFIX + "!" * 6000
        errors = validation_errors(mutated)
        self.assertTrue(any("base64url alphabet" in error for error in errors))
        self.assertTrue(any("not valid base64url" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
