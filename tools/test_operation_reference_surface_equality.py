"""Mutations for parsed non-HTTP binding and internal operation-set equality."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from artifact_lint.bindings import (
    check_internal_operation_set_subset,
    check_non_http_binding_exactness,
)
from artifact_lint.core import Lint


OP_ONE = "ak.self.probe.command.one.v1"
OP_TWO = "ak.peer.probe.read.two.v1"
PATH = Path("probe/non-http-bindings.yaml")

KNOWN = {
    "operation_grpc_map": {
        OP_ONE: "SelfProbe/One",
        OP_TWO: "PeerProbe/Two",
    },
    "operation_mq_map": {
        OP_ONE: "self.probe.command.one",
        OP_TWO: "peer.probe.query.two",
    },
}

BINDING = {
    "grpc": {
        "services": {
            "SelfProbe": {"One": OP_ONE},
            "PeerProbe": {"Two": OP_TWO},
        }
    },
    "mq": {
        "topics": {
            "self.probe.command.one": OP_ONE,
            "peer.probe.query.two": OP_TWO,
        }
    },
}


class OperationReferenceSurfaceEqualityTest(unittest.TestCase):
    def errors(self, binding: dict) -> list[str]:
        lint = Lint()
        check_non_http_binding_exactness(lint, PATH, binding, KNOWN)
        return lint.errors

    def test_exact_maps_are_green(self) -> None:
        self.assertEqual([], self.errors(copy.deepcopy(BINDING)))

    def test_wrong_grpc_method_is_red(self) -> None:
        binding = copy.deepcopy(BINDING)
        binding["grpc"]["services"]["SelfProbe"] = {"Set": OP_ONE}
        errors = self.errors(binding)
        self.assertTrue(any("gRPC binding mismatch" in error for error in errors), errors)

    def test_wrong_mq_topic_is_red(self) -> None:
        binding = copy.deepcopy(BINDING)
        binding["mq"]["topics"]["self.probe.command.wrong"] = binding["mq"]["topics"].pop(
            "self.probe.command.one"
        )
        errors = self.errors(binding)
        self.assertTrue(any("MQ binding mismatch" in error for error in errors), errors)

    def test_empty_grpc_service_is_red(self) -> None:
        binding = copy.deepcopy(BINDING)
        binding["grpc"]["services"]["EmptyProbe"] = None
        errors = self.errors(binding)
        self.assertTrue(any("must contain at least one method" in error for error in errors), errors)

    def test_registry_grpc_binding_missing_from_yaml_is_red(self) -> None:
        binding = copy.deepcopy(BINDING)
        del binding["grpc"]["services"]["PeerProbe"]
        errors = self.errors(binding)
        self.assertTrue(any("registry gRPC binding absent" in error for error in errors), errors)

    def test_registry_mq_binding_missing_from_yaml_is_red(self) -> None:
        binding = copy.deepcopy(BINDING)
        del binding["mq"]["topics"]["peer.probe.query.two"]
        errors = self.errors(binding)
        self.assertTrue(any("registry MQ binding absent" in error for error in errors), errors)

    def test_duplicate_transport_binding_is_red(self) -> None:
        binding = copy.deepcopy(BINDING)
        binding["grpc"]["services"]["AliasProbe"] = {"One": OP_ONE}
        errors = self.errors(binding)
        self.assertTrue(any("duplicate bindings" in error for error in errors), errors)

    def test_internal_operation_set_must_be_registry_subset(self) -> None:
        lint = Lint()
        check_internal_operation_set_subset(
            lint,
            PATH,
            {OP_ONE},
            {"public_metadata_operations": {OP_ONE, OP_TWO}},
        )
        self.assertTrue(any("unregistered operation_id" in error for error in lint.errors), lint.errors)


if __name__ == "__main__":
    unittest.main()
