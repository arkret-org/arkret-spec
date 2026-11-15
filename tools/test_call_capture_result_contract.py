"""Independent capture permission and result carrier counterexamples."""
import copy
import hashlib
from pathlib import Path
import unittest

from tools.artifact_lint.core import schema_validator, Lint
from tools.artifact_lint.foundation import lint_value_projection
from tools.artifact_lint.call_current import validate_capture_transcripts
from tools.generate_call_current_fixture import build_fixture
from tools import call_recording_codec as codec

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

    def test_recording_start_and_pending_freeze_key_ref_but_transcript_does_not(self):
        validator = schema_validator(SCHEMAS / 'event-payload.schema.json', '#/$defs/call_recording_start_payload')
        start = copy.deepcopy(self.transcript['original_rows'][0]['event']['payload'])
        self.assertTrue(validator.is_valid(start))
        del start['capture_metadata']['key_ref']
        self.assertFalse(validator.is_valid(start))
        transcript = copy.deepcopy(self.transcript['original_rows'][4]['event']['payload'])
        self.assertTrue(validator.is_valid(transcript))
        transcript['capture_metadata']['key_ref'] = self.transcript['original_rows'][0]['event']['payload']['capture_metadata']['key_ref']
        self.assertFalse(validator.is_valid(transcript))
        current_validator = schema_validator(SCHEMAS / 'current-state.schema.json', '')
        pending = copy.deepcopy(next(row for row in self.transcript['checkpoints'][0]['current_state_entries'] if row['selector']['kind'] == 'call_recording_artifact'))
        self.assertTrue(current_validator.is_valid(pending))
        del pending['value']['details']['key_ref']
        self.assertFalse(current_validator.is_valid(pending))

    def test_exporter_uses_both_rfc9420_steps_not_a_shortcut(self):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
        kat = self.transcript['recording_codec_kat']
        vector = kat['vectors'][0]
        secret = codec.unb64u(kat['qualified_source']['exporter_secret'], 32)
        context = codec.jcs(vector['artifact']['encryption']['context'])
        def independent_expand(secret, label, context):
            full = b'MLS 1.0 ' + label.encode('ascii')
            self.assertLess(len(full), 64)
            self.assertLess(len(context), 64)
            info = (32).to_bytes(2, 'big') + bytes([len(full)]) + full + bytes([len(context)]) + context
            return HKDFExpand(algorithm=hashes.SHA256(), length=32, info=info).derive(secret)
        derived = independent_expand(secret, codec.LABEL, b'')
        actual = independent_expand(derived, 'exported', hashlib.sha256(context).digest())
        self.assertEqual(codec.b64u(actual), vector['expected']['key'])
        self.assertNotEqual(actual, independent_expand(secret, codec.LABEL, hashlib.sha256(context).digest()))

    def test_real_stream_vectors_include_empty_and_exact_segment_without_an_empty_tail(self):
        kat = self.transcript['recording_codec_kat']
        for vector in kat['vectors']:
            with self.subTest(vector=vector['name']):
                raw = codec.unb64u(vector['expected']['ciphertext'])
                plaintext = codec.unb64u(vector['plaintext'])
                size, count = codec.dimensions(len(raw), vector['artifact']['encryption']['segment_bytes'])
                self.assertEqual(size, len(plaintext))
                self.assertEqual(count, len(vector['expected']['segment_nonces']))
                self.assertEqual(codec.open_recording(raw, vector['artifact'], kat['start_event'], kat['qualified_source']), plaintext)
                if vector['name'] in ('empty', 'exact_segment'):
                    self.assertEqual(count, 1)

    def test_correct_blob_digest_does_not_bypass_a_bad_aead_tag_or_aad(self):
        kat = self.transcript['recording_codec_kat']
        for name in ('tag_changed_digest_updated', 'wrong_aad_media_type', 'wrong_epoch_secret',
                     'truncate_updated_length_and_digest', 'append_updated_length_and_digest'):
            with self.subTest(mutation=name):
                with self.assertRaisesRegex(ValueError, 'segment authentication'):
                    codec.run_codec_case(kat, 'recording_codec_' + name)

    def test_ciphertext_length_inversion_is_unique_and_rejects_noncanonical_gaps(self):
        for length in (1024, 262144, 8388608):
            for size in (0, 1, length - 1, length, length + 1, 2 * length, 2 * length + 1):
                count = max(1, (size + length - 1) // length)
                self.assertEqual(codec.dimensions(size + 16 * count, length), (size, count))
            for ciphertext in (*range(16), *range(length + 17, length + 33)):
                with self.assertRaises(ValueError): codec.dimensions(ciphertext, length)
        for value in (True, 1.5, -1, 1 << 64):
            with self.assertRaises(ValueError): codec.dimensions(value, 1024)

    def test_online_aad_excludes_future_totals_and_mutable_metadata(self):
        artifact = copy.deepcopy(self.transcript['recording_codec_kat']['vectors'][0]['artifact'])
        prior = codec.segment_aad(artifact, 0, False)
        artifact['size_bytes'] += 1000
        artifact['blob_ref'] = 'ak:blob:sha256:' + 'f' * 64
        artifact['retention']['retention_expires_at'] = '2028-09-20T00:00:00.000Z'
        self.assertEqual(codec.segment_aad(artifact, 0, False), prior)
        self.assertNotEqual(codec.segment_aad(artifact, 0, True), prior)
        self.assertNotEqual(codec.segment_aad(artifact, 1, False), prior)

    def test_recording_codec_is_closed_and_cannot_rebind_the_original_state(self):
        kat = self.transcript['recording_codec_kat']
        for name, expected in codec.CODEC_CASES:
            with self.subTest(case=name):
                try: actual = codec.run_codec_case(kat, name)
                except (ValueError, KeyError): actual = 'reject'
                self.assertEqual(actual, expected)
        with self.assertRaisesRegex(ValueError, 'changed after Start'):
            codec.run_codec_case(kat, 'recording_codec_changed_key_ref_encoding')


if __name__ == '__main__':
    unittest.main()
