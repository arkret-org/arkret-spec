"""Tests for the HTTP Message Signature contract closure gate.

Report 0110 found the same covered set copied into eight prose enumerations, two
conformance-profile sentences and a fixture, with nothing comparing the copies:
`federation.md` §3.2 had been reduced to a bare anchor years earlier and the
seven pages citing it for a window and a component list all still read as if it
carried them. The gate makes every copy a checked projection of
`http_signature_contract_registry`.

Each test below removes exactly one guarantee and asserts the gate turns red,
because a gate nobody can make fail is indistinguishable from no gate.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import http_signature as gate
from tools.artifact_lint.core import Lint

SCENARIO = "ak.probe.scenario.v1"
PROFILE = "ak.probe.freshness.v1"
BINDING = "zh/sync/service-http-binding.md"

PROSE = """# probe

<!-- BEGIN ak-http-signature-covered-set ak.probe.scenario.v1 -->
- `@method`、`@target-uri`、`@authority`
- `arkret-operation`
- `content-digest`（条件项：带 body 时必需）
- `idempotency-key`（条件项：参与幂等时必需）
<!-- END ak-http-signature-covered-set -->

<!-- BEGIN ak-http-signature-freshness ak.probe.freshness.v1 -->
- 签名寿命上限 300 秒。
- `created` 偏差上限 30 秒。
<!-- END ak-http-signature-freshness -->
"""


def catalog() -> dict:
    return {
        "http_signature_contract_registry": {
            "registry_rules": ["one scenario per signed request"],
            "component_vocabulary": [
                {"component": component}
                for component in (
                    "@method",
                    "@target-uri",
                    "@authority",
                    "arkret-operation",
                    "content-digest",
                    "idempotency-key",
                    "source-service-id",
                )
            ],
            "common_contract": {
                "covered_components": [
                    "@method",
                    "@target-uri",
                    "@authority",
                    "arkret-operation",
                ]
            },
            "freshness_profiles": [
                {
                    "freshness_profile_id": PROFILE,
                    "max_signature_lifetime_seconds": 300,
                    "created_skew_seconds": 30,
                }
            ],
            "scenarios": [
                {
                    "scenario_id": SCENARIO,
                    "applies_to": "the probe surface",
                    "additional_covered_components": ["content-digest"],
                    "conditional_covered_components": [
                        {
                            "component": "idempotency-key",
                            "condition": "the request is idempotency-keyed",
                        }
                    ],
                    "freshness_profile_id": PROFILE,
                    "prose_bindings": [BINDING],
                    "machine_projections": [],
                    "operations": ["ak.probe.command.v1"],
                    "vectors": [],
                }
            ],
        },
        "operation_registry": {
            "operations": [
                {
                    "operation_id": "ak.probe.command.v1",
                    "auth_requirements": {
                        "service_signature": {
                            "signature_scenario_id": SCENARIO,
                            "standard": "RFC 9421 HTTP Message Signature",
                        }
                    },
                }
            ]
        },
    }


class HttpSignatureContractClosureTest(unittest.TestCase):
    def run_gate(
        self,
        *,
        data: dict | None = None,
        prose: str | None = None,
        extra_pages: dict[str, str] | None = None,
        projections: dict[str, object] | None = None,
    ) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            spec_root = Path(directory) / "spec" / "v1"
            artifacts = spec_root / "artifacts"
            (spec_root / "zh" / "sync").mkdir(parents=True)
            (artifacts / "registry").mkdir(parents=True)
            (artifacts / "fixtures").mkdir(parents=True)
            (spec_root / BINDING).write_text(
                PROSE if prose is None else prose, encoding="utf-8", newline="\n"
            )
            for rel, body in (extra_pages or {}).items():
                target = spec_root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body, encoding="utf-8", newline="\n")
            for rel, body in (projections or {}).items():
                target = artifacts / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    json.dumps(body, ensure_ascii=False), encoding="utf-8", newline="\n"
                )
            registry_path = artifacts / "registry" / "contract-registry.json"
            registry_path.write_text(
                json.dumps(catalog() if data is None else data, ensure_ascii=False),
                encoding="utf-8",
                newline="\n",
            )
            lint = Lint()
            with (
                mock.patch.object(gate, "SPEC_ROOT", spec_root),
                mock.patch.object(gate, "ARTIFACTS", artifacts),
                mock.patch.object(gate, "CONTRACT_REGISTRY", registry_path),
            ):
                gate.check_http_signature_contract_closure(lint)
            return lint.errors

    def assertRedWith(self, errors: list[str], needle: str) -> None:
        self.assertTrue(any(needle in error for error in errors), errors)

    # ---------------------------------------------------------------- baseline

    def test_a_consistent_contract_and_prose_pass(self) -> None:
        self.assertEqual(self.run_gate(), [])

    def test_the_committed_spec_passes(self) -> None:
        lint = Lint()
        gate.check_http_signature_contract_closure(lint)
        self.assertEqual(lint.errors, [])

    # ---------------------------------------------------------------- prose blocks

    def test_a_block_that_drops_a_component_turns_the_gate_red(self) -> None:
        prose = PROSE.replace("- `arkret-operation`\n", "")
        self.assertRedWith(self.run_gate(prose=prose), "omits arkret-operation")

    def test_a_block_that_drops_a_conditional_component_turns_the_gate_red(self) -> None:
        prose = PROSE.replace("- `idempotency-key`（条件项：参与幂等时必需）\n", "")
        self.assertRedWith(self.run_gate(prose=prose), "omits idempotency-key")

    def test_a_block_that_adds_a_component_turns_the_gate_red(self) -> None:
        prose = PROSE.replace(
            "- `arkret-operation`\n", "- `arkret-operation`\n- `source-service-id`\n"
        )
        self.assertRedWith(self.run_gate(prose=prose), "adds source-service-id")

    def test_an_unterminated_block_turns_the_gate_red(self) -> None:
        prose = PROSE.replace("<!-- END ak-http-signature-covered-set -->\n", "")
        self.assertRedWith(self.run_gate(prose=prose), "is never closed")

    def test_a_block_naming_an_unregistered_scenario_turns_the_gate_red(self) -> None:
        prose = PROSE.replace(SCENARIO, "ak.probe.scenario.nope.v1", 1)
        self.assertRedWith(self.run_gate(prose=prose), "unregistered scenario")

    def test_an_enumeration_outside_a_block_turns_the_gate_red(self) -> None:
        """The failure the gate exists for: a second, drift-free-by-luck copy."""
        prose = PROSE + "\n覆盖 `@method`、`@target-uri`、`@authority` 与 `content-digest`。\n"
        self.assertRedWith(self.run_gate(prose=prose), "outside a declared covered-set block")

    def test_a_block_on_a_page_that_is_not_a_binding_turns_the_gate_red(self) -> None:
        self.assertRedWith(
            self.run_gate(extra_pages={"zh/sync/other.md": PROSE}),
            "is not a declared prose binding",
        )

    def test_a_binding_page_without_a_block_turns_the_gate_red(self) -> None:
        data = catalog()
        data["http_signature_contract_registry"]["scenarios"][0]["prose_bindings"] = [
            BINDING,
            "zh/sync/other.md",
        ]
        self.assertRedWith(
            self.run_gate(data=data, extra_pages={"zh/sync/other.md": "no block here\n"}),
            "carries no covered-set block",
        )

    def test_a_binding_that_does_not_exist_turns_the_gate_red(self) -> None:
        data = catalog()
        data["http_signature_contract_registry"]["scenarios"][0]["prose_bindings"] = [
            "zh/sync/missing.md"
        ]
        self.assertRedWith(self.run_gate(data=data), "prose binding does not exist")

    # ---------------------------------------------------------------- freshness

    def test_a_freshness_block_missing_a_numeral_turns_the_gate_red(self) -> None:
        prose = PROSE.replace("- `created` 偏差上限 30 秒。\n", "")
        self.assertRedWith(self.run_gate(prose=prose), "does not state created_skew_seconds=30")

    def test_a_registered_profile_with_no_block_turns_the_gate_red(self) -> None:
        prose = PROSE.split("<!-- BEGIN ak-http-signature-freshness")[0]
        self.assertRedWith(self.run_gate(prose=prose), "has no block in the prose")

    def test_a_freshness_block_on_another_page_turns_the_gate_red(self) -> None:
        block = "<!-- BEGIN ak-http-signature-freshness ak.probe.freshness.v1 -->\n300 30\n<!-- END ak-http-signature-freshness -->\n"
        self.assertRedWith(
            self.run_gate(extra_pages={"zh/sync/other.md": block}),
            "the freshness window is stated only in",
        )

    def test_the_window_phrase_outside_the_block_turns_the_gate_red(self) -> None:
        prose = PROSE + "\n窗口是 `expires - created ≤ 300` 秒。\n"
        self.assertRedWith(self.run_gate(prose=prose), "states the signature window outside")

    # ------------------------------------------------- no per-operation deviation

    def test_an_unregistered_scenario_key_turns_the_gate_red(self) -> None:
        """The successor to the deviation mechanism report 1240 removed.

        `operation_freshness_overrides` used to be a registered scenario key. It was
        removed with the two five-second ceilings it existed to carry. A key nobody
        reads is how a second window contract grows back, so the scenario key set is
        closed and anything outside it is a protocol change, not a comment.
        """
        data = catalog()
        data["http_signature_contract_registry"]["scenarios"][0][
            "operation_freshness_overrides"
        ] = [{"operation_id": "ak.probe.command.v1", "freshness_profile_id": PROFILE}]
        self.assertRedWith(self.run_gate(data=data), "unregistered key")

    def test_a_profile_no_scenario_resolves_turns_the_gate_red(self) -> None:
        data = catalog()
        data["http_signature_contract_registry"]["freshness_profiles"].append(
            {
                "freshness_profile_id": "ak.probe.freshness.tight.v1",
                "max_signature_lifetime_seconds": 5,
                "created_skew_seconds": 30,
            }
        )
        self.assertRedWith(self.run_gate(data=data), "named by no scenario")

    # ---------------------------------------------------------------- boundary vector

    def boundary_catalog(self, **overrides) -> dict:
        data = catalog()
        registry = data["http_signature_contract_registry"]
        binding = {
            "vector_id": "ak.probe.vector.v1",
            "fixture_pointer": "fixtures/probe-fixture.json#/cases/0",
            "resolved_by_operations": ["ak.probe.command.v1"],
        }
        binding.update(overrides)
        registry["freshness_profiles"][0]["boundary_vector"] = binding
        return data

    BOUNDARY_FIXTURE = {
        "cases": [
            {
                "vector_id": "ak.probe.vector.v1",
                "freshness_profile_id": PROFILE,
            }
        ]
    }

    def run_boundary_gate(self, data: dict, fixture: dict | None = None) -> list[str]:
        return self.run_gate(
            data=data,
            projections={
                "fixtures/probe-fixture.json": self.BOUNDARY_FIXTURE
                if fixture is None
                else fixture
            },
        )

    def test_a_boundary_vector_bound_to_its_operations_passes(self) -> None:
        self.assertEqual(self.run_boundary_gate(self.boundary_catalog()), [])

    def test_an_operation_that_resolves_another_profile_turns_the_gate_red(self) -> None:
        """Restoring a per-operation ceiling has to break the evidence that denies it."""
        data = self.boundary_catalog()
        registry = data["http_signature_contract_registry"]
        registry["freshness_profiles"].append(
            {
                "freshness_profile_id": "ak.probe.freshness.tight.v1",
                "max_signature_lifetime_seconds": 5,
                "created_skew_seconds": 30,
            }
        )
        registry["scenarios"][0]["freshness_profile_id"] = "ak.probe.freshness.tight.v1"
        self.assertRedWith(self.run_boundary_gate(data), "resolves ak.probe.freshness.tight.v1")

    def test_an_operation_with_no_scenario_binding_turns_the_gate_red(self) -> None:
        data = self.boundary_catalog(resolved_by_operations=["ak.probe.command.other.v1"])
        data["operation_registry"]["operations"].append(
            {"operation_id": "ak.probe.command.other.v1", "auth_requirements": {}}
        )
        self.assertRedWith(self.run_boundary_gate(data), "resolves no window at all")

    def test_a_boundary_vector_naming_no_operation_turns_the_gate_red(self) -> None:
        data = self.boundary_catalog(resolved_by_operations=[])
        self.assertRedWith(self.run_boundary_gate(data), "must name the operations it decides")

    def test_a_boundary_pointer_that_does_not_resolve_turns_the_gate_red(self) -> None:
        data = self.boundary_catalog(fixture_pointer="fixtures/probe-fixture.json#/cases/7")
        self.assertRedWith(self.run_boundary_gate(data), "does not resolve")

    def test_a_case_carrying_another_vector_turns_the_gate_red(self) -> None:
        fixture = {"cases": [{"vector_id": "ak.probe.vector.other.v1", "freshness_profile_id": PROFILE}]}
        self.assertRedWith(
            self.run_boundary_gate(self.boundary_catalog(), fixture=fixture),
            "but the profile claims",
        )

    def test_a_case_stating_another_profile_turns_the_gate_red(self) -> None:
        fixture = {
            "cases": [
                {"vector_id": "ak.probe.vector.v1", "freshness_profile_id": "ak.probe.freshness.other.v1"}
            ]
        }
        self.assertRedWith(
            self.run_boundary_gate(self.boundary_catalog(), fixture=fixture),
            "states profile 'ak.probe.freshness.other.v1'",
        )

    # ---------------------------------------------------------------- machine projections

    def test_a_drifted_machine_projection_turns_the_gate_red(self) -> None:
        data = catalog()
        data["http_signature_contract_registry"]["scenarios"][0]["machine_projections"] = [
            "fixtures/probe.json#/cases/0/required_components"
        ]
        projections = {
            "fixtures/probe.json": {
                "cases": [
                    {
                        "required_components": [
                            "@method",
                            "@target-uri",
                            "@authority",
                            "content-digest",
                            "idempotency-key",
                        ]
                    }
                ]
            }
        }
        self.assertRedWith(
            self.run_gate(data=data, projections=projections),
            "missing arkret-operation",
        )

    def test_a_matching_machine_projection_passes(self) -> None:
        data = catalog()
        data["http_signature_contract_registry"]["scenarios"][0]["machine_projections"] = [
            "fixtures/probe.json#/cases/0/required_components"
        ]
        projections = {
            "fixtures/probe.json": {
                "cases": [
                    {
                        "required_components": [
                            "@authority",
                            "@method",
                            "@target-uri",
                            "arkret-operation",
                            "content-digest",
                            "idempotency-key",
                        ]
                    }
                ]
            }
        }
        self.assertEqual(self.run_gate(data=data, projections=projections), [])

    def test_a_drifted_freshness_projection_turns_the_gate_red(self) -> None:
        data = catalog()
        data["http_signature_contract_registry"]["scenarios"][0]["freshness_projections"] = [
            {
                "pointer": "fixtures/probe.json#/cases/0/max_window_seconds",
                "profile_key": "max_signature_lifetime_seconds",
            }
        ]
        projections = {"fixtures/probe.json": {"cases": [{"max_window_seconds": 120}]}}
        self.assertRedWith(
            self.run_gate(data=data, projections=projections),
            "max_signature_lifetime_seconds",
        )

    # ---------------------------------------------------------------- operations

    def test_an_operation_restating_the_covered_set_turns_the_gate_red(self) -> None:
        data = catalog()
        signature = data["operation_registry"]["operations"][0]["auth_requirements"][
            "service_signature"
        ]
        signature["covered_components"] = ["@method"]
        self.assertRedWith(self.run_gate(data=data), "restates covered_components")

    def test_an_operation_restating_the_window_turns_the_gate_red(self) -> None:
        data = catalog()
        signature = data["operation_registry"]["operations"][0]["auth_requirements"][
            "service_signature"
        ]
        signature["freshness"] = {"max_signature_lifetime_seconds": 300}
        self.assertRedWith(self.run_gate(data=data), "restates freshness")

    def test_an_operation_naming_an_unregistered_scenario_turns_the_gate_red(self) -> None:
        data = catalog()
        data["operation_registry"]["operations"][0]["auth_requirements"]["service_signature"][
            "signature_scenario_id"
        ] = "ak.probe.scenario.absent.v1"
        self.assertRedWith(self.run_gate(data=data), "unregistered scenario")

    def test_a_scenario_listing_an_unbound_operation_turns_the_gate_red(self) -> None:
        data = catalog()
        data["operation_registry"]["operations"][0]["auth_requirements"] = {}
        self.assertRedWith(self.run_gate(data=data), "does not bind the scenario")

    def test_a_scenario_listing_an_unknown_operation_turns_the_gate_red(self) -> None:
        data = catalog()
        data["http_signature_contract_registry"]["scenarios"][0]["operations"] = [
            "ak.probe.command.absent.v1"
        ]
        self.assertRedWith(self.run_gate(data=data), "names unknown operation")

    def test_a_missing_registry_turns_the_gate_red(self) -> None:
        data = copy.deepcopy(catalog())
        del data["http_signature_contract_registry"]
        self.assertRedWith(self.run_gate(data=data), "is missing")

    # ---------------------------------------------------------------- wiring

    def test_the_runner_calls_this_gate(self) -> None:
        """An imported gate that no phase calls is indistinguishable from no gate."""
        source = (ROOT / "tools" / "artifact_lint" / "runner.py").read_text(encoding="utf-8")
        self.assertIn("check_http_signature_contract_closure(lint)", source)


class FreshnessWindowBoundaryVectorTest(unittest.TestCase):
    """The boundary vector report 0110 R3 asked for, checked against the algorithm.

    A table of hand-written accept/reject expectations is worth exactly as much
    as the reader who last checked it. These tests recompute every row from the
    registered profile, so a row that disagrees with the rules it claims to pin
    is a test failure rather than a plausible-looking line.
    """

    VECTOR = "ak.vector.service.http_signature_freshness_window_boundaries.v1"

    @classmethod
    def setUpClass(cls) -> None:
        registry = json.loads(
            (ROOT / "spec/v1/artifacts/registry/contract-registry.json").read_text(
                encoding="utf-8"
            )
        )["http_signature_contract_registry"]
        cls.profiles = {
            row["freshness_profile_id"]: row for row in registry["freshness_profiles"]
        }
        fixture = json.loads(
            (ROOT / "spec/v1/artifacts/fixtures/auth-session-proof-fixture.json").read_text(
                encoding="utf-8"
            )
        )
        cls.case = next(
            case for case in fixture["cases"] if case.get("vector_id") == cls.VECTOR
        )

    def test_every_rfc9421_row_follows_from_the_registered_profile(self) -> None:
        profile = self.profiles[self.case["freshness_profile_id"]]
        ceiling = profile["max_signature_lifetime_seconds"]
        skew = profile["created_skew_seconds"]
        now = self.case["now"]
        for row in self.case["boundaries"]:
            created, expires = row["created"], row["expires"]
            accepted = (
                0 < expires - created <= ceiling
                and abs(created - now) <= skew
                and now < expires
            )
            self.assertEqual(
                "accepted" if accepted else "rejected", row["expected"], row["name"]
            )

    def test_every_dpop_row_follows_from_the_separate_profile(self) -> None:
        dpop = self.case["dpop"]
        profile = self.profiles[dpop["freshness_profile_id"]]
        now = dpop["now"]
        for row in dpop["boundaries"]:
            delta = now - row["iat"]
            accepted = -profile["iat_future_seconds"] <= delta <= profile["iat_past_seconds"]
            self.assertEqual(
                "accepted" if accepted else "rejected", row["expected"], row["name"]
            )

    def test_the_dpop_row_the_rfc9421_ceiling_would_have_accepted_is_rejected(self) -> None:
        """The substitution the old prose invited: 300 seconds read as a DPoP window."""
        dpop = self.case["dpop"]
        row = next(
            item for item in dpop["boundaries"] if item["name"] == "rfc9421_ceiling_not_inherited"
        )
        rfc9421 = self.profiles["ak.http_signature.freshness.v1"]
        self.assertLessEqual(
            dpop["now"] - row["iat"], rfc9421["max_signature_lifetime_seconds"]
        )
        self.assertEqual("rejected", row["expected"])

    def test_jti_retention_outlives_the_acceptance_window(self) -> None:
        dpop = self.case["dpop"]
        profile = self.profiles[dpop["freshness_profile_id"]]
        self.assertGreaterEqual(
            profile["jti_retention_seconds"],
            profile["iat_past_seconds"] + profile["iat_future_seconds"],
        )

    def test_the_vector_covers_every_edge_the_ruling_named(self) -> None:
        names = {row["name"] for row in self.case["boundaries"]}
        self.assertLessEqual(
            {
                "lifetime_at_ceiling",
                "lifetime_over_ceiling",
                "lifetime_zero",
                "lifetime_negative",
                "created_past_boundary",
                "created_past_outside",
                "created_future_boundary",
                "created_future_outside",
                "expires_reached",
                "replay_after_cache_eviction",
            },
            names,
        )
        malformed = {row["name"] for row in self.case["malformed_parameters"]}
        self.assertLessEqual({"created_absent", "expires_absent", "created_not_integer"}, malformed)

    def test_every_shared_window_row_follows_from_the_profile(self) -> None:
        """The rows added when the two five-second ceilings were removed.

        Each row carries its own ``now`` because the point of the group is the
        relationship between the receiver clock and a declared lifetime, which a
        single case-level ``now`` cannot express.
        """
        profile = self.profiles[self.case["freshness_profile_id"]]
        ceiling = profile["max_signature_lifetime_seconds"]
        skew = profile["created_skew_seconds"]
        for row in self.case["removed_tightening_boundaries"]:
            created, expires, now = row["created"], row["expires"], row["now"]
            accepted = (
                0 < expires - created <= ceiling
                and abs(created - now) <= skew
                and now < expires
            )
            self.assertEqual(
                "accepted" if accepted else "rejected", row["expected"], row["name"]
            )

    def test_the_rows_prove_the_old_ceiling_no_longer_decides(self) -> None:
        """At least one accepted row must be one the removed ceiling would have rejected."""
        old_ceiling = 5
        witnesses = [
            row
            for row in self.case["removed_tightening_boundaries"]
            if row["expected"] == "accepted" and row["now"] - row["created"] > old_ceiling
        ]
        self.assertTrue(witnesses, "the group proves nothing about the removal")

    def test_a_short_declared_lifetime_still_expires(self) -> None:
        """Removing the ceiling did not turn every signature into a 300-second one."""
        rows = {row["name"]: row for row in self.case["removed_tightening_boundaries"]}
        self.assertEqual("rejected", rows["short_declared_lifetime_at_expires"]["expected"])
        self.assertEqual("rejected", rows["short_declared_lifetime_past_expires"]["expected"])
        self.assertEqual("accepted", rows["short_declared_lifetime_receiver_behind"]["expected"])

    def test_v1_registers_exactly_one_rfc9421_window(self) -> None:
        rfc9421 = {
            profile_id
            for profile_id, row in self.profiles.items()
            if "max_signature_lifetime_seconds" in row
        }
        self.assertEqual({"ak.http_signature.freshness.v1"}, rfc9421)

    def test_the_two_operations_that_carried_a_ceiling_resolve_the_shared_window(self) -> None:
        registry = json.loads(
            (ROOT / "spec/v1/artifacts/registry/contract-registry.json").read_text(
                encoding="utf-8"
            )
        )
        scenarios = {
            row["scenario_id"]: row
            for row in registry["http_signature_contract_registry"]["scenarios"]
        }
        operations = {
            row["operation_id"]: row
            for row in registry["operation_registry"]["operations"]
        }
        for operation_id in (
            "ak.peer.signal.command.relay.v1",
            "ak.peer.keys.read.lookup.v1",
        ):
            signature = operations[operation_id]["auth_requirements"]["service_signature"]
            scenario = scenarios[signature["signature_scenario_id"]]
            self.assertEqual(
                "ak.http_signature.freshness.v1",
                scenario["freshness_profile_id"],
                operation_id,
            )
            self.assertIn(operation_id, self.case["resolved_by_operations"])

    def test_the_vector_is_registered_and_carried_by_the_fixture(self) -> None:
        registry = json.loads(
            (ROOT / "spec/v1/artifacts/registry/vector-registry.json").read_text(
                encoding="utf-8"
            )
        )
        row = next(
            item for item in registry["vectors"] if item["vector_id"] == self.VECTOR
        )
        self.assertEqual("active", row["status"])
        self.assertEqual(["auth-session-proof-fixture.json"], row["applies_to_fixtures"])


if __name__ == "__main__":
    unittest.main()
