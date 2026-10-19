"""Execute the unified scope receipt policy contract and its negative probes."""

from __future__ import annotations

from .core import ARTIFACTS, Lint, canonical_json, load_json, schema_validator

FIXTURE = ARTIFACTS / "fixtures/read-receipt-scope-policy-fixture.json"
KIND = "ak.scope.read_receipt_policy"
FAMILY = "scope_read_receipt_policy"


def decide(value: dict) -> dict:
    """Evaluate already authenticated inputs; this does not verify signatures."""
    denied = {"send": False, "display": False}
    scope = value["scope_ref"]
    if scope.get("kind") not in {"realm", "circle"}:
        return denied
    if not all(value[key] for key in (
        "basis_verified", "complete", "scope_authorized", "target_verified"
    )) or any(value[key] != scope for key in (
        "signal_scope_ref", "target_scope_ref", "basis_scope_ref"
    )):
        return denied
    rows = [row for row in value["policies"] if row["selector"] == {
        "kind": FAMILY, "scope_ref": scope
    }]
    if value["current_status"] == "never_written" and not rows:
        policy = {}
    elif value["current_status"] == "present" and len(rows) == 1:
        row = rows[0]
        if row["source_stream_ref"] != scope:
            return denied
        validator = schema_validator(
            ARTIFACTS / "schemas/typed-current-result.schema.json",
            "#/$defs/scope_read_receipt_policy_result",
        )
        if list(validator.iter_errors(row)):
            return denied
        policy = row["value"]
    else:
        return denied
    disclosure = policy.get("disclosure", "optional")
    visibility = policy.get("visibility", "members")
    if disclosure == "disabled":
        return denied
    return {
        "send": disclosure == "required" or value["sender_preference"],
        "display": value["display_preference"] and value["viewer_observer"] and (
            visibility == "public"
            or visibility == "members" and value["viewer_member"]
            or visibility == "private" and value["viewer"] == value["target_author"]
        ),
    }


def check_read_receipt_scope_policy(lint: Lint) -> None:
    fixture = load_json(lint, FIXTURE)
    catalog = load_json(lint, ARTIFACTS / "registry/contract-registry.json")
    envelope = load_json(lint, ARTIFACTS / "schemas/event-envelope.schema.json")
    if not all(isinstance(value, dict) for value in (fixture, catalog, envelope)):
        return
    try:
        events = catalog["event_kind_registry"]["event_kinds"]
        writers = [(event, write) for event in events for write in event.get("result_writes", [])
                   if write["result_family"] == FAMILY]
        if len(writers) != 1 or writers[0][0]["event_kind"] != KIND:
            raise ValueError("one scope policy Event must be the sole current writer")
        event, write = writers[0]
        if write["result_selector"] != {"kind": "composite", "components": [
            {"kind": "canonical_json", "field": "envelope.scope_ref"}
        ]} or write["result_projection"] != {"kind": "set", "value": {"field": "payload"}}:
            raise ValueError("scope selector and complete payload replacement are mandatory")
        if event["payload_schema_ref"] != "schemas/event-payload.schema.json#/$defs/read_receipt_policy_payload":
            raise ValueError("the shared closed payload is required")
        if any(row["event_kind"] == "ak.realm.read_receipt_policy" for row in events):
            raise ValueError("legacy Realm-only writer must not remain registered")
        families = catalog["current_result_registry"]["result_kinds"]
        if sum(row["result_kind"] == FAMILY for row in families) != 1 or any(
            row["result_kind"] == "realm_read_receipt_policy" for row in families
        ):
            raise ValueError("only the unified scope family may be registered")
        branch = next(row["then"] for row in envelope["allOf"]
                      if row.get("if", {}).get("properties", {}).get("kind", {}).get("const") == KIND)
        if branch["properties"]["scope_ref"] != {"$ref": "#/$defs/read_receipt_policy_scope_ref"}:
            raise ValueError("policy Event must restrict its signed scope to Realm/Circle")
        names = set()
        for row in fixture["schema_cases"]:
            name = row["name"]
            if name in names:
                raise ValueError("duplicate schema probe: " + name)
            names.add(name)
            path, fragment = row["schema_ref"].split("#", 1)
            validator = schema_validator(ARTIFACTS / path, "#" + fragment)
            if (not list(validator.iter_errors(row["instance"]))) != row["expected_valid"]:
                raise ValueError("schema decision mismatch: " + name)
        if len(names) < 23:
            raise ValueError("missing closed schema probes")
        required = {
            "realm_disabled_does_not_disable_circle", "realm_required_does_not_override_circle_disabled",
            "circle_disabled_does_not_disable_realm", "sibling_disabled_does_not_override_circle",
            "verified_circle_absence_uses_own_defaults", "unverified_absence", "incomplete_absence",
            "wrong_signal_scope", "wrong_target_scope", "realm_member_without_circle_access",
            "private_same_principal_other_station", "wrong_source_stream", "missing_current",
        }
        names = [row["name"] for row in fixture["decision_cases"]]
        if len(names) != len(set(names)) or not required.issubset(names):
            raise ValueError("missing or duplicate independent/isolation cases")
        for row in fixture["decision_cases"]:
            if decide(row["input"]) != row["expected"]:
                raise ValueError("scope policy decision mismatch: " + row["name"])
        baseline = fixture["decision_cases"][0]["input"]
        for row in fixture["update_cases"]:
            seen = True
            decisions = []
            for index, policy in enumerate(row["writes"]):
                value = {**baseline, "scope_ref": row["scope_ref"], "viewer": row["viewer"],
                         "target_author": row["target_author"], "policies": [{
                             **baseline["policies"][0], "value": policy
                         }]}
                allowed = decide(value)["display"]
                if row.get("fresh_receipt_each_step", False):
                    seen = True
                seen = seen and allowed
                decisions.append(seen)
            if decisions != row["expected_display"]:
                raise ValueError("existing display transition mismatch: " + row["name"])
        subjects = [canonical_json(row["instance"]) for row in fixture["schema_cases"]
                    if row["name"] in {"scope_realm", "scope_circle", "scope_sibling"}]
        if len(set(subjects)) != 3:
            raise ValueError("Realm/Circle/sibling subjects must remain distinct")
    except (KeyError, TypeError, ValueError, StopIteration) as exc:
        lint.fail(FIXTURE, str(exc))
