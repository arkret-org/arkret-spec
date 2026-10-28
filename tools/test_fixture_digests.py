"""Fixture integrity depends on exact bytes and membership, never revision counters."""
import unittest
from tools.check_fixture_digests import compare


class FixtureDigestTest(unittest.TestCase):
    def test_exact_content_is_accepted_without_revision_metadata(self):
        value = {"files": [{"path": "fixtures/example.json", "sha256": "a" * 64}]}
        self.assertEqual(compare(value, value), [])

    def test_changed_content_is_rejected(self):
        old = {"files": [{"path": "fixtures/example.json", "sha256": "a" * 64}]}
        new = {"files": [{"path": "fixtures/example.json", "sha256": "b" * 64}]}
        self.assertIn("digest mismatch", compare(new, old)[0])

    def test_removed_added_and_duplicate_files_are_rejected(self):
        row = {"path": "fixtures/example.json", "sha256": "a" * 64}
        self.assertIn("missing fixture", compare({"files": []}, {"files": [row]})[0])
        self.assertIn("new fixture", compare({"files": [row]}, {"files": []})[0])
        self.assertIn("repeats", compare({"files": [row, row]}, {"files": []})[0])


if __name__ == "__main__":
    unittest.main()
