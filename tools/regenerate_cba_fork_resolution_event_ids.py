"""Regenerate valid Event IDs in the CBA fork-resolution fixture cases."""

from __future__ import annotations

import base64
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "spec/v1/artifacts/fixtures/cba-lattice-fixture.json"

TARGET_CARDINALITIES = {
    "resolution_voids_complete_sibling_position": 17,
    "resolution_cross_bucket_overflow_uses_sixty_five_siblings": 65,
    "resolution_bucket_overflow_below_minimal_evidence_rejected": 16,
    "resolution_domain_non_joinable_reruns_registered_cell_family": 2,
    "resolution_winner_outside_evidence_set_rejected": 17,
    "resolution_subject_carrying_bucket_digest_rejected": 17,
}


def event_id(ordinal: int) -> str:
    """Return a canonical v1 SHA-256 Event ID for a deterministic digest ordinal."""

    if not 0 < ordinal < 1 << 256:
        raise ValueError("ordinal must fit in a non-zero 256-bit digest")
    body = bytes([0x01]) + ordinal.to_bytes(32, "big")
    token = base64.urlsafe_b64encode(body).rstrip(b"=").decode("ascii")
    return "ak:event:" + token


def main() -> int:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    vector = next(
        row
        for row in fixture["vectors"]
        if row.get("name") == "sealed_control_move_full_digest_collision"
    )
    cases = {row["name"]: row for row in vector["resolution_cases"]}
    if not set(TARGET_CARDINALITIES) <= set(cases):
        missing = sorted(set(TARGET_CARDINALITIES) - set(cases))
        raise ValueError(f"missing fork-resolution cases: {missing}")

    for name, cardinality in TARGET_CARDINALITIES.items():
        ids = sorted(event_id(index + 1) for index in range(cardinality))
        evidence = cases[name]["payload"]["conflict_evidence"]
        if len(evidence.get("event_ids", [])) != cardinality:
            raise ValueError(f"{name} cardinality drifted from {cardinality}")
        evidence["event_ids"] = ids
        verdict = cases[name]["payload"]["verdict"]
        if verdict.get("kind") == "canonical_winner":
            verdict["winner_event_id"] = (
                event_id(10_000)
                if name == "resolution_winner_outside_evidence_set_rejected"
                else ids[0]
            )

    FIXTURE.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
