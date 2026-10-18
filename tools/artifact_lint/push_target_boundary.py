"""Push HMAC known answers and removal of public derivation claims."""

from __future__ import annotations

import base64
import hashlib
import hmac

from .core import ARTIFACTS, Lint, canonical_json, load_json, schema_validator

FIXTURE = ARTIFACTS / "fixtures/push-target-boundary-fixture.json"
DESCRIBE = ARTIFACTS / "schemas/service-describe.schema.json"
FIELDS = {"account_id", "device_id", "push_route_id", "salt_epoch_id"}
CASES = {"base", "same_context_replay", "other_principal", "other_station", "other_device", "other_gateway", "other_channel", "other_epoch", "other_secret"}


def check_push_target_boundary(lint: Lint) -> None:
    data = load_json(lint, FIXTURE)
    describe = load_json(lint, DESCRIBE)
    if not isinstance(data, dict) or not isinstance(describe, dict):
        return
    try:
        if "privacy_derivation" in describe["properties"] or "privacy_derivation" in str(describe.get("allOf", [])):
            raise ValueError("Describe must not restore retired derivation claims")
        if describe["additionalProperties"] is not False:
            raise ValueError("Describe must remain closed")
        target_validator = schema_validator(ARTIFACTS / "schemas/common-ids.schema.json", "#/$defs/push_target_id")
        account_validator = schema_validator(ARTIFACTS / "schemas/common-ids.schema.json", "#/$defs/account_id")
        cases = data["derivations"]
        if {row["name"] for row in cases} != CASES or len(cases) != len(CASES):
            raise ValueError("missing or duplicate HMAC context probes")
        targets = {}
        for row in cases:
            context = row["context"]
            if set(context) != FIELDS or list(account_validator.iter_errors(context["account_id"])):
                raise ValueError("HMAC input must bind the complete closed AccountId and route context")
            encoded = canonical_json(context)
            if encoded != row["expected_canonical_input"]:
                raise ValueError("canonical HMAC input mismatch: " + row["name"])
            key = bytes.fromhex(row["test_secret_hex"])
            if len(key) != 32:
                raise ValueError("test secret must have 32 octets")
            tag = hmac.new(key, encoded.encode(), hashlib.sha256).digest()
            target = "ak:pseudonym:push:" + base64.urlsafe_b64encode(tag).decode().rstrip("=")
            if target != row["expected_push_target_id"] or list(target_validator.iter_errors(target)):
                raise ValueError("full-length HMAC target mismatch: " + row["name"])
            targets[row["name"]] = target
        if targets["base"] != targets["same_context_replay"]:
            raise ValueError("same context must derive the same target")
        if len(set(targets.values())) != len(CASES) - 1:
            raise ValueError("changed context test cases must derive distinct targets")
        probes = data["schema_validation_cases"]
        names = {kind + suffix for kind in ("station", "push_gateway") for suffix in ("_without_derivation", "_derivation_claim_rejected")}
        if {row["name"] for row in probes} != names or len(probes) != len(names):
            raise ValueError("missing or duplicate role-scoped Describe probes")
        validator = schema_validator(DESCRIBE, "#")
        for row in probes:
            if (not list(validator.iter_errors(row["instance"]))) != row["expect_valid"]:
                raise ValueError("Describe schema probe mismatch: " + row["name"])
    except (KeyError, TypeError, ValueError) as exc:
        lint.fail(FIXTURE, str(exc))
