"""The `capability_grant` family must have all four of its writers.

`zh/authz/capabilities.md` section 12.1 says a Grant's closed current result
carries a status, and section 10.4 says two different authorities can close a
Grant: `ak.capability.revoke` under issuer or root-controller authority, and
`ak.capability.relinquish` under the target subject's own signature, which MUST
NOT require `ak.capability.revoke`. Neither Event kind declared a
`result_writes[]` row, so nothing in the registry could ever move a projected
Grant out of `active`, and the value schema had no slot to move it into --
`revoked_at` alone cannot say which of the two authorities closed it.

`ak.capability.derived` was missing for the same reason on the create side:
`models/realm-links.md` section 6 fixes its payload as the complete derived
grant plus a verbatim `grant_id`, and that is a projection of this family.

Each test states one proposition about the closed lifecycle.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import proof_context_schemas as gate
from tools.artifact_lint.core import CELL_WRITE_DERIVATIONS

REGISTRY = ROOT / "spec/v1/artifacts/registry/contract-registry.json"
SCHEMAS = ROOT / "spec/v1/artifacts/schemas"

FAMILY = "capability_grant"
TERMINAL_STATUSES = ("revoked", "relinquished")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def writes_by_kind() -> dict[str, list[dict]]:
    registry = load(REGISTRY)
    found: dict[str, list[dict]] = {}
    for row in registry["event_kind_registry"]["event_kinds"]:
        writes = [
            write
            for write in (row.get("result_writes") or ())
            if write["result_family"] == FAMILY
        ]
        if writes:
            found[row["event_kind"]] = writes
    return found


class CapabilityGrantLifecycleTest(unittest.TestCase):
    def test_the_family_has_exactly_its_four_writers(self) -> None:
        self.assertEqual(
            sorted(writes_by_kind()),
            [
                "ak.capability.derived",
                "ak.capability.grant",
                "ak.capability.relinquish",
                "ak.capability.revoke",
            ],
        )

    def test_the_value_schema_carries_the_three_registered_statuses(self) -> None:
        grant = load(SCHEMAS / "capability-grant.schema.json")
        status = grant["properties"]["status"]
        self.assertEqual(status["enum"], ["active", "revoked", "relinquished"])
        self.assertIn("status", grant["required"])

    def test_an_author_cannot_declare_the_status(self) -> None:
        """Section 3.0.1: the genesis body is closed and reducer-derived members
        are absent from it, so a producer-supplied status is a schema violation
        rather than a value anyone has to decide whether to trust."""
        body = load(SCHEMAS / "event-payload.schema.json")["$defs"][
            "capability_grant_payload"
        ]["properties"]["grant"]
        self.assertFalse(body["additionalProperties"])
        self.assertNotIn("status", body["properties"])

    def test_every_writer_derives_the_status(self) -> None:
        """One field, one mechanism. A write that set it any other way would be a
        second definition of what `active` means."""
        self.assertIn("capability_status", CELL_WRITE_DERIVATIONS)
        for kind, writes in writes_by_kind().items():
            with self.subTest(kind=kind):
                derived = [
                    member["derivation"] for member in writes[0].get("derived_members") or ()
                ]
                self.assertIn("capability_status", derived)

    def test_the_station_sidecar_derivation_is_gone(self) -> None:
        """Section 3.0.1 says the reducer no longer copies or derives
        `issuer_station_id`; the account's routing authority is closed inside
        ActorId. It was a derivation no registry row and no prose named."""
        self.assertNotIn("capability_issuer_station_id", CELL_WRITE_DERIVATIONS)

    def test_the_two_closes_are_told_apart_by_which_pair_they_write(self) -> None:
        found = writes_by_kind()
        revoke = found["ak.capability.revoke"][0]["result_projection"]
        relinquish = found["ak.capability.relinquish"][0]["result_projection"]
        self.assertEqual(revoke["kind"], "merge")
        self.assertEqual(relinquish["kind"], "merge")
        revoke_members = {
            member["name"] for member in revoke["value_projection"]["members"]
        }
        relinquish_members = {
            member["name"] for member in relinquish["value_projection"]["members"]
        }
        self.assertEqual(revoke_members, {"revoked_by", "revoked_at"})
        self.assertEqual(relinquish_members, {"updated_by", "updated_at"})
        self.assertEqual(revoke_members & relinquish_members, set())

    def test_a_close_reads_its_actor_and_time_from_the_signed_envelope(self) -> None:
        """The authority that closed a Grant is the Event's signer, so a payload
        field there would let the producer name someone else as the closer."""
        found = writes_by_kind()
        for kind in ("ak.capability.revoke", "ak.capability.relinquish"):
            with self.subTest(kind=kind):
                members = found[kind][0]["result_projection"]["value_projection"][
                    "members"
                ]
                self.assertEqual(
                    [member.get("envelope_field") for member in members],
                    ["actor_id", "created_at"],
                )

    def test_a_close_merges_rather_than_overwrites(self) -> None:
        """A `set` would drop the immutable grant body that section 12.1 requires
        compaction to keep."""
        found = writes_by_kind()
        for kind in ("ak.capability.revoke", "ak.capability.relinquish"):
            with self.subTest(kind=kind):
                self.assertEqual(found[kind][0]["result_projection"]["kind"], "merge")

    def test_only_genesis_retypes_its_own_event_id(self) -> None:
        """`ak.capability.grant` is the one kind whose Event id becomes the
        GrantId; the other three name an existing grant_id, so a fieldless
        subject there would silently address the wrong object."""
        found = writes_by_kind()
        self.assertEqual(
            found["ak.capability.grant"][0]["result_selector"], {"kind": "id:grant"}
        )
        for kind in (
            "ak.capability.derived",
            "ak.capability.revoke",
            "ak.capability.relinquish",
        ):
            with self.subTest(kind=kind):
                self.assertEqual(
                    found[kind][0]["result_selector"],
                    {"kind": "id:grant", "field": "payload.grant_id"},
                )

    def test_every_writer_selector_passes_the_registered_grammar(self) -> None:
        registry = load(REGISTRY)
        rows = {
            row["event_kind"]: row for row in registry["event_kind_registry"]["event_kinds"]
        }
        lint = gate.Lint()
        for kind, writes in writes_by_kind().items():
            gate._check_result_selector(
                lint,
                f"{kind}.result_writes[0].result_selector",
                writes[0]["result_selector"],
                rows[kind].get("id_source"),
            )
        self.assertEqual(lint.errors, [])

    def test_every_writer_names_the_grant_body_as_its_value(self) -> None:
        for kind, writes in writes_by_kind().items():
            with self.subTest(kind=kind):
                self.assertEqual(
                    writes[0]["value_schema_ref"],
                    "schemas/capability-grant.schema.json",
                )

    def test_the_terminal_statuses_stay_distinguishable(self) -> None:
        """Section 10.4 gives revoke and relinquish different authorities, so
        collapsing them into one terminal value would erase which authority
        closed the Grant."""
        grant = load(SCHEMAS / "capability-grant.schema.json")
        for status in TERMINAL_STATUSES:
            self.assertIn(status, grant["properties"]["status"]["enum"])


if __name__ == "__main__":
    unittest.main()
