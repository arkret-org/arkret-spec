"""Account status reaches a profile reader as a projection, and only there.

`identity/account-lifecycle.md` section 3 closes the account status enum at six
values and calls itself the v1 wire truth, and section 4 is normative that an
`AccountStatusRecord` is not an Event and enters no authority stream, no
RealmCommit, no Control Proposal and no reducer.

`actor-profile.schema.json` used to carry a `status` member that copied that
enum, and `discovery/profiles-presence.md` section 2.2 copied it a third time --
as four values, one of which (`deleted`) has never existed anywhere in the
repository, while `soft_logged_out`, `locked` and the actual irreversible
terminal state `erasure_pending` were all missing.

The copies were the smaller half of the defect. A durable member of the profile
object that no reducer may produce and no author may self-report is unwritable
by construction: it sat optional forever, and every reader that saw it absent
was free to guess. The member now lives in the read response as
`actor-profile-operations.schema.json#/$defs/account_status_projection`, which
carries the record identity and `status_seq` the reader needs in order to check
what it is being handed, and whose absence is defined to mean unknown.

So: one closed enum in the account contract, one copy in the read projection
that must equal it exactly, nothing on the durable object, and nothing
hand-copied into prose.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SPEC = ROOT / "spec" / "v1"
SCHEMAS = SPEC / "artifacts" / "schemas"

LIFECYCLE = SPEC / "zh" / "identity" / "account-lifecycle.md"
PROFILES = SPEC / "zh" / "discovery" / "profiles-presence.md"

_ENUM_HEADING = "## 3. Account Status Values"


def _account_status_values() -> list[str]:
    section = LIFECYCLE.read_text(encoding="utf-8").split(_ENUM_HEADING, 1)[1]
    bullets = section.split("\n**", 1)[0]
    return re.findall(r"^- `([a-z_]+)`$", bullets, flags=re.MULTILINE)


def _load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


class ActorProfileStatusProjectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = _load("actor-profile.schema.json")
        cls.operations = _load("actor-profile-operations.schema.json")
        cls.account = _load("account-operations.schema.json")
        cls.projection = cls.operations["$defs"]["account_status_projection"]
        cls.values = _account_status_values()

    def test_the_lifecycle_enum_is_the_six_closed_values(self) -> None:
        self.assertEqual(
            self.values,
            [
                "active",
                "soft_logged_out",
                "locked",
                "suspended",
                "deactivated",
                "erasure_pending",
            ],
        )

    def test_the_account_contract_closes_the_same_set(self) -> None:
        record = self.account["$defs"]["account_status_record"]
        self.assertEqual(record["properties"]["status"]["enum"], self.values)

    def test_the_read_projection_copies_the_account_contract_exactly(self) -> None:
        self.assertEqual(self.projection["properties"]["status"]["enum"], self.values)

    def test_the_durable_object_carries_no_status_member(self) -> None:
        """account-lifecycle.md section 4: AccountStatusRecord is not an Event.

        It never reaches a reducer, so no `result_writes[]` row of the
        actor_profile family could derive this member, and no author may be
        trusted to report a value the Account Authority signs elsewhere. A
        durable member with no possible producer is not an optional field, it
        is an unwritable one.
        """
        self.assertNotIn("status", self.profile["properties"])
        self.assertNotIn("status", self.profile.get("required", []))
        definition = self.profile["$defs"]["actor_profile_definition"]
        self.assertNotIn("status", definition["properties"])
        text = LIFECYCLE.read_text(encoding="utf-8")
        self.assertIn("`AccountStatusRecord` 不是 Event", text)

    def test_the_projection_carries_what_a_reader_must_re_check(self) -> None:
        """A bare status string cannot be checked against anything.

        The reader is told which account and which record it is looking at, and
        gets the `status_seq` it needs to order the record against its own
        replica head. All four are required together: a projection missing any
        of them is a value the caller can only take on faith.
        """
        self.assertEqual(
            sorted(self.projection["required"]),
            ["account_id", "account_status_record_id", "status", "status_seq"],
        )
        self.assertFalse(self.projection["additionalProperties"])

    def test_the_projection_is_optional_and_its_absence_means_unknown(self) -> None:
        resolved = self.operations["$defs"]["resolved_actor_profile"]
        self.assertEqual(
            resolved["properties"]["account_status"],
            {"$ref": "#/$defs/account_status_projection"},
        )
        self.assertNotIn("account_status", resolved.get("required", []))
        prose = PROFILES.read_text(encoding="utf-8")
        self.assertIn("**省略表示未知**", prose)
        self.assertIn("MUST NOT 把缺失", prose)

    def test_no_profile_surface_offers_a_deleted_status(self) -> None:
        """It was never a value; the irreversible terminal state is erasure_pending."""
        self.assertNotIn("deleted", self.values)
        self.assertNotIn("deleted", self.projection["properties"]["status"]["enum"])
        offered = [
            line
            for line in PROFILES.read_text(encoding="utf-8").splitlines()
            if "`deleted`" in line
        ]
        self.assertEqual(offered, [])

    def test_the_prose_hand_copies_no_status_enum(self) -> None:
        """The table row that copied the six values is gone with the member.

        What replaces it is a pointer to the two schemas, so there is no third
        place for the set to drift in.
        """
        prose = PROFILES.read_text(encoding="utf-8")
        self.assertNotIn("| `status` |", prose)
        self.assertIn("`status` 不是 durable profile 成员（normative）", prose)
        self.assertIn("account_status_projection", self.operations["$defs"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
