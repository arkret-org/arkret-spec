import json
import unittest

import check_applet_managed_actor_authority_fixture as runner


class AppletManagedActorAuthorityFixtureTest(unittest.TestCase):
    def test_named_suite_consumes_every_case(self) -> None:
        fixture = json.loads(runner.FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual([], runner.run_named_suite(fixture))

    def test_unknown_case_fails_closed(self) -> None:
        fixture = json.loads(runner.FIXTURE.read_text(encoding="utf-8"))
        fixture["cases"].append({"name": "unregistered_case", "expect": "accepted"})
        self.assertTrue(runner.run_named_suite(fixture))


if __name__ == "__main__":
    unittest.main()
