import json
import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_applet_managed_actor_authority_fixture as runner


class AppletManagedActorAuthorityFixtureTest(unittest.TestCase):
    def test_named_suite_consumes_every_case(self) -> None:
        fixture = json.loads(runner.FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual([], runner.run_named_suite(fixture))

    def test_install_events_cannot_join_bot_provisioning(self) -> None:
        fixture = json.loads(runner.FIXTURE.read_text(encoding="utf-8"))
        fixture["fixed_bot_unit_order"].insert(0, "ak.applet.registration")
        self.assertTrue(runner.run_named_suite(fixture))

    def test_unknown_case_fails_closed(self) -> None:
        fixture = json.loads(runner.FIXTURE.read_text(encoding="utf-8"))
        fixture["cases"].append({"name": "unregistered_case", "expect": "accepted"})
        self.assertTrue(runner.run_named_suite(fixture))


if __name__ == "__main__":
    unittest.main()
