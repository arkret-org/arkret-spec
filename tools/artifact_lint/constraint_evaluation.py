"""Keep the core support floor and effect-aware constraint matrix aligned."""

import json

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .core import ARTIFACTS, Lint, load_json


def check_constraint_evaluation(lint: Lint) -> None:
    catalog_path = ARTIFACTS / "registry/contract-registry.json"
    catalog = load_json(lint, catalog_path)
    contract = catalog.get("capability_action_registry", {}).get("constraint_evaluation_contract", {})
    required = {
        "predicate_results": ["match", "no_match", "unknown"],
        "allow_satisfied_by": ["match"],
        "refusal_applies_on": ["match", "unknown"],
        "global_refusal_order": ["deny", "quarantine", "require_review"],
        "allow_within_grant": "all",
        "allow_across_grants": "any",
        "action_mismatch": "neutral_for_effect",
        "unknown_semantics": "unknown",
        "missing_verified_facts": "unknown",
        "support_evidence": ["positive_consumer", "refusal_boundaries", "unknown_boundaries"],
        "fixture_ref": "fixtures/constraint-evaluation-fixture.json",
    }
    for key, expected in required.items():
        if contract.get(key) != expected:
            lint.fail(catalog_path, f"constraint evaluation {key} must equal {expected!r}")
    profiles_path = ARTIFACTS / "profiles/conformance-profiles.json"
    core = load_json(lint, profiles_path).get("profile_requirements", {}).get("ak.profile.core_event_store.v1", {})
    if core.get("required_constraint_subkinds") != ["window", "session", "rate"]:
        lint.fail(profiles_path, "core must require temporal window/session and quota rate")
    if "constraint-evaluation-fixture.json" not in core.get("required_fixtures", []):
        lint.fail(profiles_path, "core must require the constraint evaluation fixture")
    fixture_path = ARTIFACTS / "fixtures/constraint-evaluation-fixture.json"
    fixture = load_json(lint, fixture_path)
    cases = fixture.get("schema_validation_cases", [])
    expected_groups = {
        "unknown_timezone": "unknown", "unsupported_frequency": "unknown",
        "dst_gap": "unknown", "dst_ambiguity": "unknown",
        "inside_window": "match", "outside_window": "no_match",
        "other_action": "not_applicable", "missing_target": "unknown",
        "missing_condition_facts": "unknown", "unsupported_extension": "unknown",
        "wrong_evaluation_class": "unknown", "missing_session_facts": "unknown",
    }
    effects = {"allow": None, "deny": "Denied", "quarantine": "Quarantined", "require_review": "RequiresReview"}
    expected_names = {f"{group}_{effect}" for group in expected_groups for effect in effects}
    if {row.get("name") for row in cases} != expected_names or len(cases) != len(expected_names):
        lint.fail(fixture_path, "constraint matrix must cover each registered group and all four effects exactly once")

    def retrieve(uri):
        prefix = "https://arkret.org/v1/schemas/"
        if not uri.startswith(prefix) or "/" in uri[len(prefix):]:
            raise ValueError(f"unregistered schema reference: {uri}")
        return Resource.from_contents(json.loads((ARTIFACTS / "schemas" / uri[len(prefix):]).read_text(encoding="utf-8")))

    schema = load_json(lint, ARTIFACTS / "schemas/grant-constraint.schema.json")
    validator = Draft202012Validator(schema, registry=Registry(retrieve=retrieve))
    for row in cases:
        name = row.get("name", "")
        effect = row.get("instance", {}).get("effect")
        result = next((value for group, value in expected_groups.items() if name == f"{group}_{effect}"), None)
        if result is None or effect not in effects:
            continue
        refusal = effect != "allow" and result in ("match", "unknown")
        single = effects[effect] if refusal else (
            "Unsatisfied" if effect == "allow" and result not in ("match", "not_applicable") else "Allowed"
        )
        if (row.get("predicate_result"), row.get("expected_single_grant"), row.get("expected_with_unrestricted_grant")) != (
            result, single, effects[effect] if refusal else "Allowed"
        ):
            lint.fail(fixture_path, f"{name}: effect-aware verdict differs from the normative fold")
        if row.get("expect_valid") is not True or row.get("schema_ref") != "schemas/grant-constraint.schema.json":
            lint.fail(fixture_path, f"{name}: must validate a legal grant constraint")
        for error in validator.iter_errors(row.get("instance")):
            lint.fail(fixture_path, f"{name}: invalid constraint instance: {error.message}")
