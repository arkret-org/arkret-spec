"""`actor_profile.status` projects the account lifecycle, and says so once.

`identity/account-lifecycle.md` section 3 closes the account status enum at six
values and calls itself the v1 wire truth. `actor-profile.schema.json` copies
that set and describes the member as the public projection of it.
`discovery/profiles-presence.md` section 2.2 copied it too -- as four values,
one of which (`deleted`) has never existed anywhere in the repository, while
`soft_logged_out`, `locked` and the actual irreversible terminal state
`erasure_pending` were all missing.

A hand-copied enum beside the schema that already closes it is the drift the
registry's own notes warn about, and a field table is exactly where an
implementer looks. Nothing mechanical connected the three: the schema is
validated against itself, and the prose table is prose.

The projection direction is the other half. Section 4 of account-lifecycle.md
is normative that an `AccountStatusRecord` is not an Event and enters no
reducer, so this member can never be produced by a registered write of the
profile family -- which is why it is tested here as a projection rather than
registered as a maintained value member.
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
ARTIFACTS = SPEC / "artifacts"

LIFECYCLE = SPEC / "zh" / "identity" / "account-lifecycle.md"
PROFILES = SPEC / "zh" / "discovery" / "profiles-presence.md"

_ENUM_HEADING = "## 3. Account Status Values"


def _account_status_values() -> list[str]:
    section = LIFECYCLE.read_text(encoding="utf-8").split(_ENUM_HEADING, 1)[1]
    bullets = section.split("\n**", 1)[0]
    return re.findall(r"^- `([a-z_]+)`$", bullets, flags=re.MULTILINE)


class ActorProfileStatusProjectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = json.loads(
            (ARTIFACTS / "schemas" / "actor-profile.schema.json").read_text(
                encoding="utf-8"
            )
        )
        cls.values = _account_status_values()
        cls.table_row = next(
            line
            for line in PROFILES.read_text(encoding="utf-8").splitlines()
            if line.startswith("| `status` |")
        )

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

    def test_the_schema_copies_that_set_exactly(self) -> None:
        self.assertEqual(self.profile["properties"]["status"]["enum"], self.values)

    def test_the_field_table_names_the_same_set(self) -> None:
        named = set(re.findall(r"`([a-z_]+)`", self.table_row))
        self.assertTrue(set(self.values) <= named, sorted(set(self.values) - named))

    def test_no_profile_surface_offers_a_deleted_status(self) -> None:
        """It was never a value; the irreversible terminal state is erasure_pending."""
        self.assertNotIn("deleted", self.values)
        self.assertNotIn("deleted", self.profile["properties"]["status"]["enum"])
        offered = [
            line
            for line in PROFILES.read_text(encoding="utf-8").splitlines()
            if "`deleted`" in line and "没有 `deleted` 这个值" not in line
        ]
        self.assertEqual(offered, [])

    def test_status_is_optional_because_no_registered_write_produces_it(self) -> None:
        """account-lifecycle.md section 4: AccountStatusRecord is not an Event.

        It never reaches a reducer, so no result_writes[] row of any profile
        family could derive this member. Requiring it would make the value
        unwritable by the protocol that is supposed to write it.
        """
        self.assertNotIn("status", self.profile["required"])
        text = LIFECYCLE.read_text(encoding="utf-8")
        self.assertIn("`AccountStatusRecord` 不是 Event", text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
