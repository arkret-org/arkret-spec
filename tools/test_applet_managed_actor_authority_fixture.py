import json
import copy
import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_applet_managed_actor_authority_fixture as runner


class AppletManagedActorAuthorityFixtureTest(unittest.TestCase):
    def fixture(self):
        return json.loads(runner.FIXTURE.read_text(encoding="utf-8"))

    def catalog(self):
        return json.loads(runner.CONTRACT.read_text(encoding="utf-8"))

    def create(self, catalog):
        return next(row for row in catalog["event_kind_registry"]["event_kinds"]
                    if row["event_kind"] == "ak.realm.create")

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

    def test_missing_managed_initializer_is_rejected(self) -> None:
        catalog = self.catalog()
        row = self.create(catalog)
        row["result_writes"] = [write for write in row["result_writes"]
                                if write["result_family"] != "device_generation"]
        self.assertTrue(runner.run_named_suite(self.fixture(), catalog))

    def test_initializer_cannot_write_other_purposes(self) -> None:
        for purpose in ("collaboration", "agent_control", "principal_control"):
            with self.subTest(purpose=purpose):
                catalog = self.catalog()
                writer = next(write for write in self.create(catalog)["result_writes"]
                              if write["result_family"] == "device_generation")
                writer["condition"]["const"] = purpose
                self.assertTrue(runner.run_named_suite(self.fixture(), catalog))

    def test_initializer_is_the_closed_literal_one(self) -> None:
        catalog = self.catalog()
        writer = next(write for write in self.create(catalog)["result_writes"]
                      if write["result_family"] == "device_generation")
        self.assertEqual(writer["condition"], {
            "kind": "field_equals", "field": "payload.object.purpose", "const": "applet_managed_control"
        })
        self.assertEqual(writer["result_projection"], {
            "kind": "set", "value_projection": {"kind": "object", "members": [
                {"name": "current_device_generation_ref", "literal": 1}
            ]}
        })
        writer["result_projection"]["value_projection"]["members"][0]["literal"] = 7
        self.assertTrue(runner.run_named_suite(self.fixture(), catalog))

    def test_genesis_never_creates_a_device(self) -> None:
        fixture = self.fixture()
        row = next(row for row in fixture["cases"]
                   if row["name"] == "pcr_genesis_materializes_resolution_and_history_only")
        row["expect_device_count"] = 1
        self.assertTrue(runner.run_named_suite(fixture))

    def test_unconsumed_generation_case_is_rejected(self) -> None:
        fixture = self.fixture()
        fixture["generation_projection_cases"].pop()
        self.assertTrue(runner.run_named_suite(fixture))

    def test_generation_rebuild_must_keep_accepted_stream_order(self) -> None:
        fixture = self.fixture()
        row = next(row for row in fixture["generation_projection_cases"]
                   if row["name"] == "managed_history_restart_rebuilds_genesis")
        row["replay_order"] = [1, 0, 2]
        self.assertTrue(runner.run_named_suite(fixture))

    def test_delegated_authorize_cannot_become_a_generation_writer(self) -> None:
        catalog = self.catalog()
        authorize = next(row for row in catalog["event_kind_registry"]["event_kinds"]
                         if row["event_kind"] == "ak.device.authorize")
        writer = copy.deepcopy(next(row for row in authorize["result_writes"]
                                    if row["result_family"] == "device_generation"))
        writer["condition"]["const"] = "applet_managed_delegation"
        writer["result_projection"]["value_projection"]["members"][0]["literal"] = 1
        authorize["result_writes"].append(writer)
        self.assertTrue(runner.run_named_suite(self.fixture(), catalog))

    def test_resolution_rotation_cannot_write_generation(self) -> None:
        catalog = self.catalog()
        resolution = next(row for row in catalog["event_kind_registry"]["event_kinds"]
                          if row["event_kind"] == "ak.identity.resolution.update")
        writer = copy.deepcopy(next(write for write in self.create(catalog)["result_writes"]
                                    if write["result_family"] == "device_generation"))
        writer.pop("condition")
        writer["result_projection"]["value_projection"]["members"][0]["literal"] = 1
        resolution.setdefault("result_writes", []).append(writer)
        self.assertTrue(runner.run_named_suite(self.fixture(), catalog))

    def test_generation_source_is_not_the_later_resolution_commit(self) -> None:
        fixture = self.fixture()
        row = next(row for row in fixture["generation_projection_cases"]
                   if row["name"] == "managed_resolution_rotation_keeps_generation")
        row["expect_generation_source_index"] = 1
        self.assertTrue(runner.run_named_suite(fixture))


if __name__ == "__main__":
    unittest.main()
