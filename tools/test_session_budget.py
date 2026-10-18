"""Mutation and independent arithmetic checks for the session budget contract."""

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.artifact_lint import session_budget as gate


class SessionBudgetTest(unittest.TestCase):
    def check(self, filename=None, mutate=None):
        original = gate.load_json

        def load(lint, path):
            data = copy.deepcopy(original(lint, path))
            if path.name == filename:
                mutate(data)
            return data

        with patch.object(gate, 'load_json', load):
            lint = gate.Lint()
            gate.check_session_budget(lint)
            return lint.errors

    def change_case(self, name, mutate):
        return self.check(gate.FIXTURE.name, lambda data: mutate(next(row for row in data['predicate_cases'] if row['name'] == name)))

    def change_lifecycle(self, name, mutate):
        return self.check(gate.FIXTURE.name, lambda data: mutate(next(row for row in data['lifecycle_cases'] if row['name'] == name)))

    def test_current_contract_and_executable_matrix(self):
        self.assertEqual(self.check(), [])

    def test_deadline_cannot_be_inclusive(self):
        self.assertTrue(self.change_case('session_boundary', lambda row: row.update(expected_predicate='match')))

    def test_refresh_cannot_replace_original_start(self):
        self.assertTrue(self.change_case('refresh_keeps_start', lambda row: row['facts']['session'].update(started_at='2026-10-19T10:59:00.000Z', last_activity_at=None)))

    def test_wrong_station_is_not_a_verified_match(self):
        self.assertTrue(self.change_case('wrong_station', lambda row: row.update(expected_predicate='match')))

    def test_missing_session_is_not_sessionless(self):
        self.assertTrue(self.change_case('missing_session_facts', lambda row: row['context'].update(auth_branch='registered_sessionless')))

    def test_missing_activity_is_not_confirmed_no_activity(self):
        self.assertTrue(self.change_case('missing_activity_facts', lambda row: row['facts']['session'].update(last_activity_at=None)))

    def test_explicit_wrong_dependency_class_is_unknown(self):
        self.assertTrue(self.change_case('wrong_evaluation_class', lambda row: row.update(expected_predicate='match')))

    def test_sessionless_cannot_remove_grant_budget(self):
        self.assertTrue(self.change_case('sessionless_grant_expired', lambda row: row.update(expected_predicate='not_applicable')))

    def test_unknown_deny_cannot_be_bypassed_by_another_grant(self):
        self.assertTrue(self.change_case('clock_overlap', lambda row: row['expected_by_effect'].update(deny=['Denied', 'Allowed'])))

    def test_revoked_session_cannot_use_another_grant(self):
        self.assertTrue(self.change_case('session_revoked', lambda row: row['expected_by_effect'].update(allow=['Denied', 'Allowed'])))

    def test_heartbeat_cannot_count_as_activity(self):
        self.assertTrue(self.change_lifecycle('heartbeat', lambda row: row['expected_outcomes'][0].update(activity_updated=True)))

    def test_exact_replay_cannot_refresh_idle(self):
        self.assertTrue(self.change_lifecycle('exact_replay', lambda row: row['expected_state'].update(last_activity_at='2026-10-19T10:31:00.000Z')))

    def test_late_activity_cannot_resurrect(self):
        self.assertTrue(self.change_lifecycle('late_activity', lambda row: row['expected_state'].update(active=True)))

    def test_local_grant_failure_cannot_log_out_session(self):
        self.assertTrue(self.change_lifecycle('local_grant_failure_not_logout', lambda row: row['expected_state'].update(active=False)))

    def test_missing_case_is_not_coverage(self):
        self.assertTrue(self.check(gate.FIXTURE.name, lambda data: data['predicate_cases'].pop()))

    def test_missing_effect_is_not_coverage(self):
        self.assertTrue(self.change_case('grant_valid', lambda row: row['expected_by_effect'].pop('require_review')))

    def test_business_activity_is_a_closed_set(self):
        self.assertTrue(self.check('contract-registry.json', lambda data: data['capability_action_registry']['constraint_evaluation_contract']['session_budget_contract']['activity_actions'].append('ak.presence.broadcast')))

    def test_external_session_state_cannot_be_cached_as_stateless(self):
        self.assertTrue(self.check('contract-registry.json', lambda data: data['capability_action_registry']['constraint_evaluation_contract']['session_budget_contract']['evaluation_class'].update(session_or_idle='stateless')))

    def test_fixture_is_required_by_core(self):
        self.assertTrue(self.check('conformance-profiles.json', lambda data: data['profile_requirements']['ak.profile.core_event_store.v1']['required_fixtures'].remove(gate.FIXTURE.name)))

    def test_utc_month_arithmetic_has_independent_known_answers(self):
        examples = [
            ('2026-01-31T12:00:00.000Z', 'P1M', '2026-02-28T12:00:00.000Z'),
            ('2024-02-29T12:00:00.000Z', 'P1Y', '2025-02-28T12:00:00.000Z'),
            ('2026-01-31T12:00:00.000Z', 'P1MT24H', '2026-03-01T12:00:00.000Z'),
            ('2026-01-31T12:00:00.000Z', 'P1Y1M', '2027-02-28T12:00:00.000Z'),
            ('2026-03-08T00:00:00.000Z', 'P1D', '2026-03-09T00:00:00.000Z'),
        ]
        for start, duration, expected in examples:
            with self.subTest(start=start, duration=duration):
                self.assertEqual(gate.add_duration(gate.instant(start), duration), gate.instant(expected))


if __name__ == '__main__':
    unittest.main()
