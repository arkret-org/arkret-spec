#!/usr/bin/env python3
"""Recompute the normative Contact round-id known-answer vectors."""

from __future__ import annotations

import hashlib
import json
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

    for case in fixture.get("cases", []):
        name = case["name"]
        contact_round = case["contact_round"]
        members = contact_round.get("sorted_pair_members")
        if not isinstance(members, list) or len(members) != 2 or members != sorted(set(members)):
            raise SystemExit(f"{name}: sorted_pair_members is not canonical and distinct")
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

    print(f"contact round KAT: {len(fixture['cases'])} cases OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
