"""Execute the closed Chat/Topic wire vectors and pin participant boundaries."""

from __future__ import annotations

import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .core import ARTIFACTS, Lint, load_json


CONTRACT = ARTIFACTS / "registry/contract-registry.json"
PROFILE = ARTIFACTS / "profiles/conformance-profiles.json"
FIXTURE = ARTIFACTS / "fixtures/direct-conversation-structure-fixture.json"
STRUCTURAL_ACTIONS = {
    "ak.strand.create", "ak.strand.update", "ak.strand.archive", "ak.strand.restore",
    "ak.space.create", "ak.space.update",
    "ak.space.archive", "ak.space.restore", "ak.space.tombstone",
}


def check_direct_conversation_structure(lint: Lint) -> None:
    contract = load_json(lint, CONTRACT)
    profile = load_json(lint, PROFILE)
    fixture = load_json(lint, FIXTURE)
    source = next(row for row in contract["authority_source_registry"]["sources"]
                  if row["authority_source_id"] == "ak.authority.direct_conversation_participant.v1")
    scope = source.get("structural_contract", {})
    expected = {
        "chat_update_paths": ["encrypted_metadata", "topic"],
        "space_update_paths": ["rank", "encrypted_metadata"],
        "space_kinds": ["topic"],
        "topic_parent": "root_in_same_realm",
        "scope": "realm_default_only",
        "main_archive": "forbidden",
        "bootstrap": "no_structural_extension_before_stable_binding",
        "revocation": "current_contact_or_owned_agent_controller_gate_for_all_structural_actions",
        "topic": "strand_topic_whole_set_or_unset_with_required_expected_state_digest",
        "topic_current": "strand_current_only_no_board_position_or_relation",
        "update_metadata": "whole_envelope_set_only_no_ciphertext_subpaths",
        "denial": "direct_conversation_participant_authority_denied",
    }
    for key, value in expected.items():
        if scope.get(key) != value:
            lint.fail(CONTRACT, f"DM structural boundary drift: {key}")
    if set(source.get("structural_actions", [])) != STRUCTURAL_ACTIONS:
        lint.fail(CONTRACT, "DM structure actions must be the exact closed nine-action set")
    for key in ("action_allowlist", "event_action_allowlist"):
        if not STRUCTURAL_ACTIONS <= set(source.get(key, [])):
            lint.fail(CONTRACT, f"DM structure actions missing from {key}")
    requirement = profile["profile_requirements"]["ak.profile.direct_conversation_realm.v1"]
    watch = {
        "action": "ak.strand.watch.set",
        "watcher": "full_payload_watcher_actor_id_equals_envelope_actor_id",
        "target": "actual_non_circle_chat_strand_in_same_direct_realm",
        "authority": "stable_participant_and_accepted_binding_endorsement_only",
        "bootstrap": "forbidden",
        "others": "forbidden_including_the_other_stable_participant",
        "preimage": "existing_whole_value_cas",
        "default": "mentions_only_when_never_written",
        "disclosure": "existing_actor_private_watch_current_rules",
        "denial": "direct_conversation_participant_authority_denied",
    }
    if source.get("personal_watch_contract") != watch or requirement["participant_authority"].get("personal_watch_contract") != watch:
        lint.fail(CONTRACT, "DM personal watch must retain its exact self-only stable binding contract")
    for key in ("action_allowlist", "event_action_allowlist"):
        actions = set(source.get(key, []))
        if "ak.strand.watch.set" not in actions or "ak.strand.watch.set.others" in actions:
            lint.fail(CONTRACT, "DM watch requires the self action and forbids others")
    bootstrap = next(row for row in contract["authority_source_registry"]["sources"]
                     if row["authority_source_id"] == "ak.authority.direct_conversation_bootstrap_participant.v1")
    if any(action.startswith("ak.strand.watch.set") for action in bootstrap["action_allowlist"]):
        lint.fail(CONTRACT, "DM bootstrap cannot authorize watch")
    if requirement["participant_authority"].get("structural_contract") != scope:
        lint.fail(PROFILE, "DM profile must carry the exact canonical structure contract")
    if not STRUCTURAL_ACTIONS <= set(requirement["required_event_kinds"]):
        lint.fail(PROFILE, "DM profile must require every structural writer")
    if STRUCTURAL_ACTIONS & set(requirement["rejected_event_kinds"]):
        lint.fail(PROFILE, "DM structural kinds cannot remain unconditionally rejected")
    cases = fixture.get("cases", [])
    resources = []
    for path in (ARTIFACTS / "schemas").glob("*.json"):
        document = load_json(lint, path)
        resource = Resource.from_contents(document, default_specification=DRAFT202012)
        resources.append((path.as_uri(), resource))
        if "$id" in document:
            resources.append((document["$id"], resource))
    registry = Registry().with_resources(resources)
    if len(cases) < 20 or len({row.get("case_id") for row in cases}) != len(cases):
        lint.fail(FIXTURE, "structure fixture requires unique executed positive and negative cases")
    for case in cases:
        file_name, _, fragment = case["schema_ref"].partition("#")
        document = load_json(lint, ARTIFACTS / file_name)
        reference = document.get("$id", (ARTIFACTS / file_name).as_uri()) + ("#" + fragment if fragment else "")
        valid = jsonschema.Draft202012Validator({"$ref": reference}, registry=registry).is_valid(case["value"])
        if valid != case["expect_valid"]:
            lint.fail(FIXTURE, f"structure wire vector failed: {case['case_id']}")
