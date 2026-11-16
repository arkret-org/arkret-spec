"""Fixed vectors for the shared, explicitly bounded reference encoder."""

import unittest

from tools.reference_json import jcs_text


class ReferenceJsonTest(unittest.TestCase):
    def test_utf16_property_order_and_nested_values(self):
        value = {"\ue000": "private", "\U00010000": {"z": None, "a": [True, False, 1]}}
        self.assertEqual(
            jcs_text(value),
            '{"\U00010000":{"a":[true,false,1],"z":null},"\ue000":"private"}',
        )

    def test_string_escaping_is_byte_exact(self):
        self.assertEqual(jcs_text(['"', "\n", "\\", "\u0000"]), '["\\\"","\\n","\\\\","\\u0000"]')

    def test_numbers_outside_the_reference_subset_fail(self):
        for value in (1.0, float("nan"), float("inf"), 9_007_199_254_740_992):
            with self.subTest(value=value), self.assertRaises(ValueError):
                jcs_text(value)
        self.assertEqual(jcs_text(-9_007_199_254_740_991), "-9007199254740991")

    def test_invalid_unicode_and_object_names_fail(self):
        for value in ("\ud800", {"\udfff": "x"}, {1: "x"}):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                jcs_text(value)


if __name__ == "__main__":
    unittest.main()
