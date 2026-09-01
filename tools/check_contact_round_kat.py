#!/usr/bin/env python3
"""Recompute the normative Contact round-id known-answer vectors."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "contact-round-kat.json"


def canonical_json(value: object) -> str:
    # The KAT deliberately uses only strings, arrays and objects, so this is
    # byte-identical to RFC 8785 without relying on number formatting behavior.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> int:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
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
            requests = contact_round.get("requests")
            if not isinstance(requests, list) or len(requests) != 2:
                raise SystemExit(f"{name}: glare must carry exactly two requests")
            request_keys = [
                (row["request_event_ref"], row["request_acceptance_receipt_digest"])
                for row in requests
            ]
            if request_keys != sorted(set(request_keys)):
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
        f"contact round KAT: {len(fixture['cases'])} round cases and "
        f"{len(expected_negatives)} outgoing-slot negatives OK"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
