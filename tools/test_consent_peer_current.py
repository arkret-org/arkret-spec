"""Reference-model cases; real signatures, SQL and MLS remain downstream."""

import copy
import itertools
import unittest

from tools.artifact_lint.protocol_simplification import ConsentModel, canonical, mimi_diff, valid_permissions

PEER = {"kind": "actor", "actor_id": {"kind": "account", "account_id": {
    "principal_id": "alice", "station_id": "station-a"}}}
VOICE = {"consent_scope": "voice_call", "expires_at": "2020-01-01T00:00:00Z"}
PRESENCE = {"consent_scope": "presence", "not_before": "2030-01-01T00:00:00Z", "constraints": [{"unknown": "keep"}]}


def payload(entries, revision=None, peer=PEER):
    return {"peer": copy.deepcopy(peer), "permissions": copy.deepcopy(entries), "expected_current":
            {"state": "never_written"} if revision is None else {"state": "present", "revision": revision}}


class ConsentPeerCurrentTest(unittest.TestCase):
    def test_competition_in_both_orders(self):
        for a, b in itertools.permutations([[], [VOICE]]):
            m = ConsentModel()
            self.assertEqual(m.submit("a", payload(a))[0], "accepted")
            before = copy.deepcopy(m.current)
            self.assertEqual(m.submit("b", payload(b))[0], "stale")
            self.assertEqual(m.current, before)
            self.assertEqual(m.position, 1)

    def test_empty_is_not_never_written(self):
        m = ConsentModel()
        _, empty = m.submit("a", payload([]))
        self.assertEqual(m.submit("b", payload([VOICE]))[0], "stale")
        self.assertEqual(m.submit("c", payload([VOICE], empty["revision"]))[0], "accepted")

    def test_replay_preserves_later_empty(self):
        m = ConsentModel()
        original = payload([VOICE, PRESENCE])
        _, first = m.submit("a", original)
        _, empty = m.submit("b", payload([], first["revision"]))
        self.assertEqual(m.submit("a", original), ("replay", first))
        self.assertEqual(m.current[canonical(PEER)], empty)
        self.assertEqual(m.position, 2)

    def test_same_id_different_bytes(self):
        m = ConsentModel()
        m.submit("a", payload([]))
        self.assertEqual(m.submit("a", payload([VOICE]))[0], "conflict")

    def test_station_is_identity(self):
        m = ConsentModel()
        other = copy.deepcopy(PEER)
        other["actor_id"]["account_id"]["station_id"] = "station-b"
        m.submit("a", payload([VOICE]))
        self.assertEqual(m.submit("b", payload([], peer=other))[0], "accepted")
        self.assertEqual(len(m.current), 2)

    def test_revoke_preserves_all_other_fields(self):
        self.assertTrue(mimi_diff([VOICE, PRESENCE], [PRESENCE], "voice_call", "revoke"))
        self.assertFalse(mimi_diff([VOICE, PRESENCE], [], "voice_call", "revoke"))
        changed = {**PRESENCE, "constraints": []}
        self.assertFalse(mimi_diff([VOICE, PRESENCE], [changed], "voice_call", "revoke"))

    def test_optional_presence_matters(self):
        self.assertFalse(mimi_diff([VOICE, {"consent_scope": "presence", "constraints": []}],
                                   [{"consent_scope": "presence"}], "voice_call", "deny"))

    def test_deny_expired_is_legal_missing_is_not(self):
        self.assertTrue(mimi_diff([VOICE], [], "voice_call", "deny"))
        self.assertFalse(mimi_diff([], [], "voice_call", "deny"))
        self.assertFalse(mimi_diff([PRESENCE], [PRESENCE], "voice_call", "revoke"))

    def test_accept_only_correlated_scope(self):
        self.assertTrue(mimi_diff([PRESENCE], [VOICE, PRESENCE], "voice_call", "accept"))
        self.assertFalse(mimi_diff([PRESENCE], [VOICE], "voice_call", "accept"))
        self.assertFalse(mimi_diff([], [], "voice_call", "accept"))

    def test_two_correlations_and_historical_retry(self):
        m = ConsentModel()
        one = {"id": "one", "peer": PEER, "scope": "voice_call", "decision": "accept"}
        two = {"id": "two", "peer": PEER, "scope": "presence", "decision": "accept"}
        original = payload([VOICE])
        _, first = m.submit("a", original, correlation=one)
        self.assertEqual(m.submit("b", payload([PRESENCE]), correlation=two)[0], "stale")
        _, later = m.submit("c", payload([VOICE, PRESENCE], first["revision"]), correlation=two)
        self.assertEqual(m.submit("a", original, correlation=one), ("replay", first))
        self.assertEqual(m.current[canonical(PEER)], later)
        self.assertEqual(m.submit("a", original, correlation=two)[0], "conflict")

    def test_retry_rechecks_disclosure(self):
        m = ConsentModel()
        m.submit("a", payload([]))
        self.assertEqual(m.submit("a", payload([]), authorized=False), ("denied", None))

    def test_duplicate_any_and_order_reject(self):
        for entries in [[VOICE, VOICE], [PRESENCE, VOICE], [{"consent_scope": "any"}]]:
            self.assertFalse(valid_permissions(entries))
            m = ConsentModel()
            self.assertEqual(m.submit("a", payload(entries))[0], "invalid")
            self.assertEqual(m.current, {})


if __name__ == "__main__":
    unittest.main()
