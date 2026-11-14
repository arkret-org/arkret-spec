"""Independent capture permission and result carrier counterexamples."""
import copy
from pathlib import Path
import unittest

from tools.artifact_lint.core import schema_validator, Lint
from tools.artifact_lint.foundation import lint_value_projection
from tools.artifact_lint.call_current import validate_capture_transcripts
from tools.generate_call_current_fixture import build_fixture

SCHEMAS = Path(__file__).resolve().parents[1] / 'spec/v1/artifacts/schemas'


class CallCaptureResultContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.transcript = build_fixture()['capture_transcripts']

    def event_validator(self):
        return schema_validator(SCHEMAS / 'event-payload.schema.json', '#/$defs/call_state_payload')

    def test_all_signed_capture_payloads_use_the_canonical_branches(self):
        for row in self.transcript['original_rows']:
            fragment = '#/$defs/call_recording_start_payload' if row['event']['kind'] == 'ak.call.recording.start' else '#/$defs/call_state_payload'
            validator = schema_validator(SCHEMAS / 'event-payload.schema.json', fragment)
            self.assertTrue(validator.is_valid(row['event']['payload']), list(validator.iter_errors(row['event']['payload'])))

    def test_results_require_one_scalar_artifact_revision(self):
        ready = copy.deepcopy(self.transcript['original_rows'][3]['event']['payload'])
        validator = self.event_validator()
        for replacement in (None, {'commit_id': ready['recording_transition']['expected_commit_id'], 'stream_position': 20}):
            changed = copy.deepcopy(ready)
            changed['recording_transition']['expected_commit_id'] = replacement
            self.assertFalse(validator.is_valid(changed))
        ready['recording_transition'].pop('expected_commit_id')
        self.assertFalse(validator.is_valid(ready))

    def test_stop_cannot_carry_a_result_guard_or_reopen_capture(self):
        for index, capture in ((1, 'recording'), (5, 'transcript')):
            stop = copy.deepcopy(self.transcript['original_rows'][index]['event']['payload'])
            self.assertTrue(self.event_validator().is_valid(stop))
            stop[capture + '_transition']['expected_commit_id'] = self.transcript['original_rows'][0]['commit']['commit_id']
            self.assertFalse(self.event_validator().is_valid(stop))
            stop[capture + '_transition'].pop('expected_commit_id')
            stop[capture + '_transition']['from'] = 'stopped'
            self.assertFalse(self.event_validator().is_valid(stop))

    def test_start_pending_and_stop_have_independent_revisions(self):
        rows = self.transcript['checkpoints']
        pending = next(x for x in rows[0]['current_state_entries'] if x['selector']['kind'] == 'call_recording_artifact')
        stopped = rows[1]['current_state_entries']
        self.assertEqual(pending, next(x for x in stopped if x['selector']['kind'] == 'call_recording_artifact'))
        self.assertNotEqual(pending['revision'], next(x for x in stopped if x['selector']['kind'] == 'call_recording_state')['revision'])
        after_ready = rows[3]['current_state_entries']
        self.assertEqual('stopped', next(x for x in after_ready if x['selector']['kind'] == 'call_recording_state')['value'])

    def test_complete_currents_have_status_and_no_duplicate_write_guard(self):
        validator = schema_validator(SCHEMAS / 'current-state.schema.json', '')
        for checkpoint in self.transcript['checkpoints']:
            for current in checkpoint['current_state_entries']:
                self.assertTrue(validator.is_valid(current), list(validator.iter_errors(current)))
                if current['selector']['kind'].endswith('_artifact'):
                    for mutation in ('raw_metadata', 'missing_status', 'guard_mirror'):
                        changed = copy.deepcopy(current)
                        if mutation == 'raw_metadata': changed['value'] = changed['value']['details']
                        elif mutation == 'missing_status': changed['value'].pop('status')
                        else: changed['value']['expected_commit_id'] = changed['revision']['commit_id']
                        self.assertFalse(validator.is_valid(changed))

    def test_ready_artifact_and_pending_details_cannot_be_mixed(self):
        validator = schema_validator(SCHEMAS / 'current-state.schema.json', '')
        rows = self.transcript['checkpoints']
        ready = copy.deepcopy(next(x for x in rows[3]['current_state_entries'] if x['selector']['kind'] == 'call_recording_artifact'))
        for status in ('pending', 'failed'):
            changed = copy.deepcopy(ready)
            changed['value']['status'] = status
            self.assertFalse(validator.is_valid(changed))
        ready['value']['details']['recording_stop_event_id'] = self.transcript['original_rows'][1]['event']['event_id']
        self.assertFalse(validator.is_valid(ready))

    def test_receiver_pending_derivation_is_finite(self):
        for name, accepted in (('call_capture_pending_details', True), ('arbitrary_capture_details', False)):
            lint = Lint()
            lint_value_projection(lint, SCHEMAS / 'current-state.schema.json', 'capture',
                                  {'kind': 'object', 'members': [{'name': 'details', 'derivation': name}]})
            self.assertEqual(not lint.errors, accepted)

    def test_signed_sources_independently_determine_both_currents(self):
        fixture = build_fixture()
        validate_capture_transcripts(fixture)
        changed = copy.deepcopy(fixture)
        changed['capture_transcripts']['checkpoints'][1]['current_state_entries'][0]['revision']['stream_position'] += 1
        with self.assertRaises(ValueError): validate_capture_transcripts(changed)

    def test_ready_producer_shape_obeys_executor_precedence(self):
        validator = schema_validator(SCHEMAS / 'event-envelope.schema.json', '')
        event = copy.deepcopy(self.transcript['original_rows'][3]['event'])
        self.assertTrue(validator.is_valid(event))
        service = event['executed_by']
        account = event['actor_id']
        event['actor_id'] = service
        event['executed_by'] = account
        self.assertFalse(validator.is_valid(event))
        event.pop('executed_by')
        self.assertTrue(validator.is_valid(event))
        event['actor_id'] = account
        self.assertFalse(validator.is_valid(event))

    def test_start_binds_the_actual_selected_grant_in_its_signed_envelope(self):
        validator = schema_validator(SCHEMAS / 'event-envelope.schema.json', '')
        event = copy.deepcopy(self.transcript['original_rows'][0]['event'])
        self.assertTrue(validator.is_valid(event))
        event['authorization_ref'] = event['event_id']
        self.assertFalse(validator.is_valid(event))
        event.pop('authorization_ref')
        self.assertFalse(validator.is_valid(event))


if __name__ == '__main__':
    unittest.main()
