#!/usr/bin/env python3
"""Recompute the normative Contact round-id known-answer vectors."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "contact-round-kat.json"
CORE_DOMAIN = "ak.contact.request_acceptance_core.v1"
TEST_PUBLIC_KEY = "A6EHv_POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg"
TEST_DIDS = {
    "ak:did_core:webvh:z6mkfixturealice": "did:webvh:z6mkfixturealice:alice.example",
    "ak:did_core:webvh:z6mkfixturebob": "did:webvh:z6mkfixturebob:bob.example",
    "ak:did_core:webvh:z6mkfixturestationa": "did:webvh:z6mkfixturestationa:station-a.example",
    "ak:did_core:webvh:z6mkfixturestationb": "did:webvh:z6mkfixturestationb:station-b.example",
}


def b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def unb64u(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def digest(value: object, domain: str | None = None) -> str:
    prefix = "" if domain is None else domain + "\n"
    return "sha256:" + hashlib.sha256((prefix + canonical_json(value)).encode()).hexdigest()


def signed_fact(body: dict, method: str, created_at: str) -> dict:
    # Published conformance seed 00..1f; never a production authority input.
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    return {**body, "signature": {
        "verification_method": method,
        "created_at": created_at,
        "jws": b64u(key.sign(canonical_json(body).encode())),
    }}


def rebuild_producer_vectors(fixture: dict) -> None:
    """Derive every dependent byte from fixed public conformance inputs."""
    cases = {case["name"]: case for case in fixture["cases"]}
    pair = cases["normal"]["contact_round"]["sorted_pair_member_ids"]
    peers = [{"kind": "human", "account_id": member["account_id"]} for member in pair]
    request_refs = [row["request_event_ref"] for row in cases["glare"]["contact_round"]["requests"]]
    at = fixture["outgoing_slot_absence"]["case"]["transcript"]["observed_at"]
    receipts = []
    vectors = []
    for index, event_ref in enumerate(request_refs):
        # Complete DID locators are explicit fixture inputs, never reconstructed
        # from the deliberately location-free core identifier.
        station = TEST_DIDS[pair[index]["account_id"]["station_id"]]
        principal = TEST_DIDS[pair[index]["account_id"]["principal_id"]]
        core = {
            "holder": peers[index], "peer": peers[1-index], "slot_version": 1,
            "request_event_ref": event_ref,
            "producer_signer": {"verification_method": principal + "#device-fixture", "public_key_b64u": TEST_PUBLIC_KEY},
            "source_checkpoint": "sha256:" + str(index + 1) * 64,
            "accepted_at": at, "issuer_id": pair[index]["account_id"]["station_id"],
        }
        receipt = signed_fact({"core": core, "receipt_digest": digest(core, CORE_DOMAIN)}, station + "#assertion-fixture", at)
        receipts.append(receipt)
        vectors.append({"name": "request_" + str(index), "schema_def": "request_acceptance_receipt", "signed_object": receipt,
                        "canonical_unsigned": canonical_json({k:v for k,v in receipt.items() if k != "signature"}),
                        "expected_signed_digest": digest(receipt)})
    cases["normal"]["contact_round"]["request_acceptance_receipt_digest"] = digest(receipts[0])
    for row, receipt in zip(cases["glare"]["contact_round"]["requests"], receipts):
        row["request_acceptance_receipt_digest"] = digest(receipt)
    for case in fixture["cases"]:
        case["canonical_contact_round"] = canonical_json(case["contact_round"])
        case["expected_contact_round_id"] = digest(case["contact_round"], fixture["domain"])
    absence = fixture["outgoing_slot_absence"]["case"]
    round_id = cases["normal"]["expected_contact_round_id"]
    absence["transcript"]["contact_round_id"] = round_id
    absence["canonical_transcript"] = canonical_json(absence["transcript"])
    absence["expected_digest"] = digest(absence["transcript"], fixture["outgoing_slot_absence"]["domain"])
    producer = receipts[1]["core"]["producer_signer"]
    response_ref = "ak:event:" + b64u(bytes([1]) + bytes([0x42]) * 32)
    reject_ref = "ak:event:" + b64u(bytes([1]) + bytes([0x43]) * 32)
    method = receipts[1]["signature"]["verification_method"]
    bodies = [
        ("normal_response_acceptance_receipt", {
            "contact_round_id": round_id, "request_receipt": receipts[0], "response_event_ref": response_ref,
            "producer_signer": producer, "outgoing_slot_absence_digest": absence["expected_digest"],
            "accepted_at": at, "issuer_id": receipts[1]["core"]["issuer_id"],
        }),
        ("reject_acceptance_receipt", {
            "request_receipt": receipts[0], "reject_event_ref": reject_ref, "producer_signer": producer,
            "accepted_at": at, "issuer_id": receipts[1]["core"]["issuer_id"],
        }),
        ("contact_lineage", {
            "contact_round_id": round_id, "issuer": peers[1], "peer": peers[0], "version": 1,
            "event_ref": response_ref, "producer_signer": producer, "granted_to_peer_scopes": ["direct_message"],
        }),
    ]
    for definition, body in bodies:
        signed = signed_fact(body, method, at)
        vectors.append({"name": definition, "schema_def": definition, "signed_object": signed,
                        "canonical_unsigned": canonical_json(body), "expected_signed_digest": digest(signed)})
    fixture["producer_signer_kat"] = {
        "scope": "Source signature, closed producer descriptor, and complete receipt-to-round digest chain only. Event holder proof and historical Station authority validation require the separate production verifier; these vectors do not claim either.",
        "source_public_key_b64u": TEST_PUBLIC_KEY,
        "source_private_seed_b64u": b64u(bytes(range(32))),
        "linked_round_cases": ["normal", "glare"],
        "hash_only_round_cases": ["glare_wire_order_not_digest_order"],
        "cases": vectors,
        "negative_cases": ["missing_producer_signer", "null_producer_signer", "unknown_member", "short_key", "long_key", "padded_key", "noncanonical_key", "substituted_method", "substituted_key"],
    }


def check_producer_vectors(fixture: dict) -> None:
    section = fixture["producer_signer_kat"]
    documents = [json.loads(path.read_text(encoding="utf-8")) for path in (ROOT / "spec/v1/artifacts/schemas").glob("*.json")]
    registry = Registry().with_resources((doc["$id"], Resource.from_contents(doc)) for doc in documents)
    base = "https://arkret.org/v1/schemas/contact-operations.schema.json"
    source_key = Ed25519PublicKey.from_public_bytes(unb64u(section["source_public_key_b64u"]))
    rebuilt = deepcopy(fixture)
    rebuild_producer_vectors(rebuilt)
    if rebuilt["producer_signer_kat"] != section:
        raise SystemExit("Contact producer KAT differs from fixed conformance source inputs")
    for case in section["cases"]:
        signed = case["signed_object"]
        validator = Draft202012Validator({"$ref": base + "#/$defs/" + case["schema_def"]}, registry=registry)
        validator.validate(signed)
        unsigned = {k: v for k, v in signed.items() if k != "signature"}
        canonical = canonical_json(unsigned)
        if canonical != case["canonical_unsigned"] or digest(signed) != case["expected_signed_digest"]:
            raise SystemExit(case["name"] + ": signed object canonical bytes/digest drifted")
        signature = unb64u(signed["signature"]["jws"])
        source_key.verify(signature, canonical.encode())
        if "core" in signed and digest(signed["core"], CORE_DOMAIN) != signed["receipt_digest"]:
            raise SystemExit("request core digest mismatch")
        for mutation in section["negative_cases"]:
            tampered = deepcopy(signed)
            body = tampered.get("core", tampered)
            descriptor = body["producer_signer"]
            if mutation == "missing_producer_signer": del body["producer_signer"]
            elif mutation == "null_producer_signer": body["producer_signer"] = None
            elif mutation == "unknown_member": descriptor["algorithm"] = "Ed25519"
            elif mutation == "short_key": descriptor["public_key_b64u"] = b64u(bytes(31))
            elif mutation == "long_key": descriptor["public_key_b64u"] = b64u(bytes(33))
            elif mutation == "padded_key": descriptor["public_key_b64u"] += "="
            elif mutation == "noncanonical_key": descriptor["public_key_b64u"] = descriptor["public_key_b64u"][:-1] + "B"
            elif mutation == "substituted_method": descriptor["verification_method"] += "-other"
            elif mutation == "substituted_key": descriptor["public_key_b64u"] = b64u(bytes(32))
            else: raise SystemExit("unknown producer mutation")
            if mutation not in {"substituted_method", "substituted_key"} and validator.is_valid(tampered):
                raise SystemExit(case["name"] + ": schema accepted " + mutation)
            transcript = canonical_json({k:v for k,v in tampered.items() if k != "signature"}).encode()
            try:
                source_key.verify(signature, transcript)
            except InvalidSignature:
                pass
            else:
                raise SystemExit(case["name"] + ": source signature accepted " + mutation)
    receipts = [case["signed_object"] for case in section["cases"] if case["schema_def"] == "request_acceptance_receipt"]
    by_ref = {receipt["core"]["request_event_ref"]: receipt for receipt in receipts}
    for case in fixture["cases"]:
        if case["name"] not in section["linked_round_cases"]: continue
        rows = case["contact_round"].get("requests", [case["contact_round"]])
        for row in rows:
            if row["request_acceptance_receipt_digest"] != digest(by_ref[row["request_event_ref"]]):
                raise SystemExit(case["name"] + ": round does not bind complete signed receipt")


def rebuild_delegated_actor_vectors(fixture: dict) -> None:
    """Add independent source-transcript vectors without rewriting round inputs."""
    direct = fixture["producer_signer_kat"]["cases"][0]["signed_object"]
    core = direct["core"]
    account = core["holder"]["account_id"]
    agent_did = "did:webvh:z6mkfixtureagent:agents.example:assistant"
    agent_account = {"principal_id": "ak:did_core:webvh:z6mkfixtureagent", "station_id": account["station_id"]}
    agent = {"kind": "agent", "actor_id": {"kind": "account", "account_id": agent_account}, "controller_account_id": account}
    rows = []
    for branch in ("human", "agent_runtime", "agent_controller_device"):
        body = deepcopy(core)
        identity = {"actor_id": {"kind": "account", "account_id": deepcopy(account)}}
        if branch != "human":
            body["holder"] = deepcopy(agent)
            identity["actor_id"] = deepcopy(agent["actor_id"])
        if branch == "agent_runtime":
            body["producer_signer"]["verification_method"] = agent_did + "#runtime-key"
        if branch == "agent_controller_device":
            identity["executed_by"] = {"kind": "account", "account_id": deepcopy(account)}
            body["producer_signer"]["delegated_actor_did"] = agent_did
        signed = signed_fact({"core": body, "receipt_digest": digest(body, CORE_DOMAIN)}, direct["signature"]["verification_method"], core["accepted_at"])
        rows.append({"name": branch, "event_identity": identity, "signed_request_receipt": signed,
                     "canonical_unsigned": canonical_json({k:v for k,v in signed.items() if k != "signature"})})
    fixture["delegated_actor_locator_kat"] = {
        "scope": "Closed producer branches, actual peer-carrier conditional schema, locator core binding and original source signature coverage only. Event identity inputs are not full Event proofs; native Agent history authentication, source admission custody and offline direction recovery require production SDK/server tests.",
        "cases": rows,
        "negative_cases": ["controller_missing_locator", "human_with_locator", "runtime_with_locator", "human_with_executor", "null_locator", "core_instead_of_did", "wrong_agent_principal", "changed_locator_with_original_signature", "unregistered_descriptor_member", "wrong_controller_station", "wrong_executor_account", "wrong_actor_account"],
    }


def check_delegated_actor_vectors(fixture: dict) -> None:
    section = fixture["delegated_actor_locator_kat"]
    rebuilt = deepcopy(fixture)
    rebuild_delegated_actor_vectors(rebuilt)
    if rebuilt["delegated_actor_locator_kat"] != section:
        raise SystemExit("delegated Actor locator KAT drifted")
    documents = [json.loads(path.read_text(encoding="utf-8")) for path in (ROOT / "spec/v1/artifacts/schemas").glob("*.json")]
    registry = Registry().with_resources((doc["$id"], Resource.from_contents(doc)) for doc in documents)
    base = "https://arkret.org/v1/schemas/contact-operations.schema.json"
    schema = next(doc for doc in documents if doc["$id"] == base)
    # Use all five actual carrier conditionals, not a second copy of their iff rules.
    conditionals = {branch["properties"]["kind"]["const"]: Draft202012Validator(
        {"$id": base, "$defs": schema["$defs"], "allOf": branch["allOf"]}, registry=registry)
        for branch in schema["$defs"]["peer_contact_submit_request"]["oneOf"][:5]}
    receipt_schema = Draft202012Validator({"$ref": base + "#/$defs/request_acceptance_receipt"}, registry=registry)
    source_key = Ed25519PublicKey.from_public_bytes(unb64u(TEST_PUBLIC_KEY))

    def valid(row: dict, carrier_kind: str | None = None) -> bool:
        signed = row["signed_request_receipt"]
        identity = row["event_identity"]
        receipt_schema.validate(signed)
        core = signed["core"]
        holder = core["holder"]
        expected_actor = ({"kind": "account", "account_id": holder["account_id"]}
                          if holder["kind"] == "human" else holder["actor_id"])
        if identity["actor_id"] != expected_actor:
            raise ValueError("source fact does not bind the exact Event actor")
        if holder["kind"] == "agent":
            controller = holder["controller_account_id"]
            if controller["station_id"] != expected_actor["account_id"]["station_id"]:
                raise ValueError("Agent and controller are different Station accounts")
            if "executed_by" in identity and identity["executed_by"] != {"kind": "account", "account_id": controller}:
                raise ValueError("Event executor is not the exact controller account")
        for kind, conditional in conditionals.items():
            if carrier_kind is not None and kind != carrier_kind: continue
            partial = {"signed_event": identity}
            if kind == "request": partial["request_receipt"] = signed
            elif kind in {"response", "reject"}:
                partial[kind + "_receipt"] = {"producer_signer": core["producer_signer"], "request_receipt": {"core": {"peer": core["holder"]}}}
            else: partial["lineage"] = {"issuer": core["holder"], "producer_signer": core["producer_signer"]}
            conditional.validate(partial)
        locator = core["producer_signer"].get("delegated_actor_did")
        if locator is not None:
            # These fixtures exercise the registered WebVH core projection only.
            parts = locator.split(":")
            if len(parts) < 4 or parts[:2] != ["did", "webvh"]:
                raise ValueError("invalid complete WebVH locator")
            if "ak:did_core:webvh:" + parts[2] != identity["actor_id"]["account_id"]["principal_id"]:
                raise ValueError("locator does not project to the exact Agent actor")
        if digest(core, CORE_DOMAIN) != signed["receipt_digest"]:
            raise ValueError("changed signed receipt core")
        transcript = canonical_json({k:v for k,v in signed.items() if k != "signature"}).encode()
        source_key.verify(unb64u(signed["signature"]["jws"]), transcript)
        return True

    rows = {row["name"]: row for row in section["cases"]}
    for row in rows.values():
        valid(row)
        if row["canonical_unsigned"] != canonical_json({k:v for k,v in row["signed_request_receipt"].items() if k != "signature"}):
            raise SystemExit("delegated locator canonical bytes drifted")
    from jsonschema.exceptions import ValidationError
    for name in section["negative_cases"]:
        branch = "human" if name.startswith("human_") else "agent_runtime" if name.startswith("runtime_") else "agent_controller_device"
        row = deepcopy(rows[branch])
        descriptor = row["signed_request_receipt"]["core"]["producer_signer"]
        locator = rows["agent_controller_device"]["signed_request_receipt"]["core"]["producer_signer"]["delegated_actor_did"]
        if name == "controller_missing_locator": del descriptor["delegated_actor_did"]
        elif name in {"human_with_locator", "runtime_with_locator"}: descriptor["delegated_actor_did"] = locator
        elif name == "human_with_executor": row["event_identity"]["executed_by"] = row["event_identity"]["actor_id"]
        elif name == "null_locator": descriptor["delegated_actor_did"] = None
        elif name == "core_instead_of_did": descriptor["delegated_actor_did"] = "ak:did_core:webvh:z6mkfixtureagent"
        elif name == "wrong_agent_principal": descriptor["delegated_actor_did"] = "did:webvh:z6mkother:agents.example"
        elif name == "changed_locator_with_original_signature": descriptor["delegated_actor_did"] = locator + ":elsewhere"
        elif name == "unregistered_descriptor_member": descriptor["actor_did"] = locator
        elif name == "wrong_controller_station": row["signed_request_receipt"]["core"]["holder"]["controller_account_id"]["station_id"] = "ak:did_core:webvh:z6mkotherstation"
        elif name == "wrong_executor_account": row["event_identity"]["executed_by"]["account_id"]["principal_id"] = "ak:did_core:webvh:z6mkothercontroller"
        elif name == "wrong_actor_account": row["event_identity"]["actor_id"]["account_id"]["station_id"] = "ak:did_core:webvh:z6mkotherstation"
        else: raise SystemExit("unknown delegated Actor mutation")
        # Re-sign every structural mutation so a failure proves the relevant
        # branch/core predicate rather than merely a stale signature/digest.
        if name != "changed_locator_with_original_signature":
            signed = row["signed_request_receipt"]
            row["signed_request_receipt"] = signed_fact({"core": signed["core"], "receipt_digest": digest(signed["core"], CORE_DOMAIN)}, signed["signature"]["verification_method"], signed["signature"]["created_at"])
        else:
            row["signed_request_receipt"]["receipt_digest"] = digest(row["signed_request_receipt"]["core"], CORE_DOMAIN)
        for carrier_kind in conditionals:
            try:
                valid(row, carrier_kind)
            except (ValidationError, ValueError, InvalidSignature):
                pass
            else:
                raise SystemExit("delegated Actor KAT accepted " + carrier_kind + ":" + name)
    print(f"Contact delegated Actor locator KAT: {len(rows)} signed branches and {len(section['negative_cases'])} negative mutations across {len(conditionals)} carrier conditionals OK")


def canonical_json(value: object) -> str:
    # The KAT deliberately uses only strings, arrays and objects, so this is
    # byte-identical to RFC 8785 without relying on number formatting behavior.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_request_order(contact_round: dict) -> bool:
    requests = contact_round.get("requests")
    if not isinstance(requests, list) or len(requests) != 2:
        return False
    keys = [row["request_event_ref"].encode("utf-8") for row in requests]
    return keys[0] < keys[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="regenerate linked producer/receipt/round/absence vectors")
    args = parser.parse_args()
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if args.write:
        rebuild_producer_vectors(fixture)
        rebuild_delegated_actor_vectors(fixture)
        FIXTURE.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    check_producer_vectors(fixture)
    check_delegated_actor_vectors(fixture)
    domain = fixture.get("domain")
    if domain != "ak.contact.round.v1":
        raise SystemExit(f"unexpected Contact round domain: {domain!r}")
    if fixture.get("minimum_independent_runners") != 2:
        raise SystemExit("Contact round KAT must require exactly two independent runners")

    round_ids: dict[str, str] = {}
    round_members: dict[str, list[object]] = {}
    for case in fixture.get("cases", []):
        name = case["name"]
        contact_round = case["contact_round"]
        members = contact_round.get("sorted_pair_member_ids")
        member_bytes = [canonical_json(member).encode() for member in members or []]
        if (
            not isinstance(members, list)
            or len(members) != 2
            or member_bytes != sorted(set(member_bytes))
        ):
            raise SystemExit(f"{name}: sorted_pair_member_ids is not canonical and distinct")
        if contact_round.get("kind") == "glare":
            if not canonical_request_order(contact_round):
                raise SystemExit(f"{name}: glare requests are not canonical and distinct")

        canonical = canonical_json(contact_round)
        if canonical != case["canonical_contact_round"]:
            raise SystemExit(f"{name}: canonical Contact round bytes drifted")
        preimage = f"{domain}\n{canonical}".encode()
        actual = f"sha256:{hashlib.sha256(preimage).hexdigest()}"
        if actual != case["expected_contact_round_id"]:
            raise SystemExit(f"{name}: expected {case['expected_contact_round_id']}, got {actual}")
        round_ids[name] = actual
        round_members[name] = members

    ordering = fixture["request_ordering"]
    if (
        ordering["key"] != "request_event_ref"
        or ordering["encoding"] != "complete_wire_string_utf8"
        or ordering["comparison"] != "unsigned_byte_lexicographic_strict_ascending"
        or ordering["receipt_digest_is_tiebreaker"] is not False
        or ordering["receiver_normalizes"] is not False
    ):
        raise SystemExit("request ordering contract drifted")
    for case in ordering["negative_cases"]:
        if case["expected"] != "reject" or canonical_request_order(case["contact_round"]):
            raise SystemExit(f"{case['name']}: noncanonical request order was accepted")

    absence = fixture.get("outgoing_slot_absence")
    if not isinstance(absence, dict):
        raise SystemExit("missing outgoing-slot-absence KAT")
    absence_domain = absence.get("domain")
    if absence_domain != "ak.contact.no_outgoing_slot.v1":
        raise SystemExit(f"unexpected outgoing-slot-absence domain: {absence_domain!r}")
    required = absence.get("required_fields")
    case = absence.get("case", {})
    transcript = case.get("transcript")
    if not isinstance(required, list) or not isinstance(transcript, dict):
        raise SystemExit("invalid outgoing-slot-absence KAT shape")
    if list(transcript) != required or set(transcript) != set(required):
        raise SystemExit("outgoing-slot-absence transcript fields/order drifted")
    members = transcript["sorted_pair_member_ids"]
    member_bytes = [canonical_json(member).encode() for member in members]
    if len(members) != 2 or member_bytes != sorted(set(member_bytes)):
        raise SystemExit("outgoing-slot-absence pair is not canonical and distinct")
    if transcript["request_slot_owner"] not in members:
        raise SystemExit("outgoing-slot-absence owner is not an exact pair member")
    if transcript["contact_round_id"] != round_ids.get("normal"):
        raise SystemExit("outgoing-slot-absence round id is not the normal-round KAT result")
    if members != round_members.get("normal"):
        raise SystemExit("outgoing-slot-absence pair is not the normal-round KAT pair")
    frontier = transcript["cas_frontier"]
    if not frontier or frontier != sorted(set(frontier)):
        raise SystemExit("outgoing-slot-absence frontier is not canonical and distinct")
    if transcript["cas_sequence"] < 1 or transcript["outgoing_request_state"] != "absent":
        raise SystemExit("outgoing-slot-absence state is invalid")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", transcript["observed_at"]):
        raise SystemExit("outgoing-slot-absence observed_at is not canonical milliseconds")
    canonical = canonical_json(transcript)
    if canonical != case.get("canonical_transcript"):
        raise SystemExit("outgoing-slot-absence canonical bytes drifted")
    digest = f"sha256:{hashlib.sha256(f'{absence_domain}\n{canonical}'.encode()).hexdigest()}"
    if digest != case.get("expected_digest"):
        raise SystemExit(
            f"outgoing-slot-absence expected {case.get('expected_digest')}, got {digest}"
        )

    expected_negatives = {
        "missing_observed_at",
        "omitted_slot_predecessor",
        "null_outgoing_request_state",
        "swapped_pair",
        "wrong_contact_round_id",
        "stale_cas_frontier",
        "non_canonical_json",
    }
    if set(absence.get("negative_cases", [])) != expected_negatives:
        raise SystemExit("outgoing-slot-absence negative-case coverage drifted")
    mutations: dict[str, object] = {}
    for name in expected_negatives - {"non_canonical_json"}:
        value = deepcopy(transcript)
        if name == "missing_observed_at":
            del value["observed_at"]
        elif name == "omitted_slot_predecessor":
            del value["slot_predecessor"]
        elif name == "null_outgoing_request_state":
            value["outgoing_request_state"] = None
        elif name == "swapped_pair":
            value["sorted_pair_member_ids"].reverse()
        elif name == "wrong_contact_round_id":
            value["contact_round_id"] = "sha256:" + "0" * 64
        elif name == "stale_cas_frontier":
            value["cas_frontier"] = value["cas_frontier"][:1]
        mutations[name] = value
    for name, value in mutations.items():
        if isinstance(value, dict) and set(value) == set(required):
            mutated = canonical_json(value)
            mutated_digest = f"sha256:{hashlib.sha256(f'{absence_domain}\n{mutated}'.encode()).hexdigest()}"
            if mutated_digest == digest:
                raise SystemExit(f"{name}: mutation did not change digest")
    non_canonical = json.dumps(transcript, ensure_ascii=False, separators=(", ", ": "))
    if non_canonical == canonical:
        raise SystemExit("non_canonical_json vector unexpectedly canonical")

    print(
        f"contact round KAT: {len(fixture['producer_signer_kat']['cases'])} signed producer facts, "
        f"45 producer mutations, {len(fixture['cases'])} round cases and "
        f"{len(expected_negatives)} outgoing-slot negatives and "
        f"{len(ordering['negative_cases'])} request-order negatives OK"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
