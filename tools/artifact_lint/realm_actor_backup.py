"""Native root custody KAT/schema gate, without a runtime durability claim."""
from __future__ import annotations

from tools.realm_actor_backup_contract import (
    fixture, canonical, digest, unb64, backup_aad, backup_info, envelope_bytes,
    open_backup, verify_native_receipt, verify_inventory, open_handover,
    verify_confirmation, verify_device_put_response, verify, check_recipient, execute_decision_cases,
)
from .core import ARTIFACTS, Lint, load_json, schema_validator, jsonschema_errors

FIXTURE = ARTIFACTS / "fixtures/realm-actor-content-backup-fixture.json"


def validate_fixture(data):
    """Actual crypto/source checks; caller/native storage qualification is separate."""
    packet=data["native_packet"]
    if data.get("decision_cases")!=execute_decision_cases(data):
        raise ValueError("native decision cases differ from actual crypto/reference outcomes")
    public=unb64(data["test_material"]["device_public_base64url"])
    plaintext=open_backup(packet,bytes.fromhex(data["test_material"]["archive_private_hex"]),public)
    if plaintext!=data["plaintext"]:
        raise ValueError("native root plaintext changed")
    for field,value in [("aad_hex",backup_aad(packet)),("info_hex",backup_info(packet)),("signature_input_hex",envelope_bytes(packet))]:
        if data["kat"][field]!=value.hex():raise ValueError("native packet transcript drift: "+field)
    verify_native_receipt(packet,data["native_source"])
    verify_device_put_response(packet,data["native_put_response"],unb64(data["admission_case"]["public_key_base64url"]))
    verify_inventory(data["archive_inventory"],data["inventory_cut"])
    case=data["private_handover"]
    new_public=unb64(data["manager_handover"]["new_manager_public_base64url"])
    opened=open_handover(case["sealed"],bytes.fromhex(data["test_material"]["next_archive_private_hex"]),new_public,
        data["inventory_cut"],"2026-11-08T00:00:02.000Z")
    if opened!=case["plaintext"]:raise ValueError("private archive transfer plaintext drift")
    verify_confirmation(case["confirmation"],case["sealed"]["offer"],opened,new_public)
    acceptance=data["manager_handover"]["acceptance_input"]
    if (acceptance["content_backup_inventory_digest"]!=digest(data["archive_inventory"])
            or acceptance["content_backup_handover_digest"]!=digest(opened)
            or not verify("ak.realm_actor_manager_acceptance_signature.v1",acceptance,data["manager_handover"]["acceptance"],new_public)):
        raise ValueError("public manager acceptance differs from the actual imported transfer")
    schema_validator(ARTIFACTS/"schemas/realm-actor.schema.json","#/$defs/manager_acceptance_transcript").validate(acceptance)
    check_recipient(acceptance["next_content_backup_recipient"],data["native_history"],2)
    for name in ["admission_case","handover_offer_case","handover_confirmation_case"]:
        case=data[name]
        file, _, pointer = case["unsigned_schema_ref"].partition("#")
        schema_validator(ARTIFACTS/file,"#"+pointer).validate(case["unsigned_projection"])
        if not verify(case["context"],case["unsigned_projection"],case["signature"],unb64(case["public_key_base64url"])):
            raise ValueError("registered detached KAT signature invalid: "+name)
        envelope={key:value for key,value in case["signature"].items() if key!="signature"}
        if (canonical(case["unsigned_projection"]).hex()!=case["canonical_hex"]
                or (case["context"].encode()+b"\n"+canonical(envelope)).hex()!=case["signature_input_hex"]):
            raise ValueError("registered detached KAT transcript drift: "+name)
    for case in data["schema_validation_cases"]:
        file,_,pointer=case["schema_ref"].partition("#")
        if schema_validator(ARTIFACTS/file,"#"+pointer if pointer else "").is_valid(case["instance"])!=case["expect_valid"]:
            raise ValueError("native schema case disagrees: "+case["name"])
        if not case["expect_valid"]:
            lint=Lint()
            errors=jsonschema_errors(lint,FIXTURE,case["schema_ref"],case["instance"])
            if lint.errors or not errors or case.get("first_expected_error")!=errors[0]:
                raise ValueError("native schema first-error evidence disagrees: "+case["name"])
    for field,definition in [("native_source","realm_actor_content_backup_source"),
            ("archive_inventory","realm_actor_archive_inventory_manifest"),
            ("native_put_response","keys_backups_replace_response_body"),
            ("device_head_response","realm_actor_backup_series_head_response_body"),
            ("device_unlock_response","realm_actor_backup_unlock_response_body"),
            ("manager_unlock_response","realm_actor_archive_unlock_response_body")]:
        schema_validator(ARTIFACTS/"schemas/keys-operations.schema.json","#/$defs/"+definition).validate(data[field])
    schema_validator(ARTIFACTS/"schemas/current-state.schema.json","#/$defs/current_realm_actor_key_backup_active_series").validate(data["native_current"])
    schema_validator(ARTIFACTS/"schemas/realm-actor-material.schema.json","#/$defs/current_entry").validate(data["native_current_entry"])
    private_scopes=data["native_source"]["device_authorization"]["event"]["payload"]["scopes"]
    current=packet["contents"][0]["root_context"]["effective_scope"]
    private_circles=[row["effective_scope"]["circle_id"] for row in private_scopes
        if row["effective_scope"]!=current and row["effective_scope"].get("kind")=="circle"]
    for field in ["native_put_response","device_head_response","device_unlock_response"]:
        if any(circle in canonical(data[field]).decode() for circle in private_circles):
            raise ValueError("Device reply leaks an unrelated private Circle")


def check_realm_actor_content_backup_contract(lint: Lint):
    data=load_json(lint,FIXTURE)
    if not isinstance(data,dict):return
    try:
        validate_fixture(data)
        if data!=fixture():raise ValueError("native custody KAT drift; run its official generator")
    except Exception as error:
        detail = getattr(error, "message", str(error))
        lint.fail(FIXTURE,"native root custody KAT: "+detail[:1000])
