import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

with patch("dotenv.load_dotenv"), patch.dict("os.environ", {}, clear=True):
    from services import drive_persistence as drive, opportunity_tracker as tracker


class OpportunityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / 'opportunities.json'
        self.base.write_text(json.dumps([{'id': 'old', 'story_title': 'Keep this idea',
            'status': 'pending', 'expires_at': '2000-01-01T00:00:00+00:00', 'relevance_score': 8}]))
        for p in (patch.object(tracker, 'DATA_DIR', str(self.root)),
                  patch.object(tracker, 'OPP_FILE', str(self.base)),
                  patch.object(drive, 'is_configured', return_value=False)):
            p.start()
            self.addCleanup(p.stop)

    def test_pending_ideas_do_not_expire_on_read(self):
        self.assertEqual([o['id'] for o in tracker.get_pending_opportunities()], ['old'])

    def test_approval_survives_stale_briefing_write(self):
        stale = json.loads(self.base.read_text())
        tracker.update_opportunity_status('old', 'generated', pack_id='pack-1')
        tracker._save(stale)
        current = tracker.get_opportunity('old')
        self.assertEqual(current['status'], 'generated')
        self.assertEqual(current['pack_id'], 'pack-1')

    def test_failed_cloud_save_does_not_change_local_records(self):
        before = self.base.read_text()
        with patch.object(drive, 'is_configured', return_value=True), \
             patch.object(drive, 'upload_json', side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError):
                tracker._save([])
        self.assertEqual(self.base.read_text(), before)


class StrictDriveTests(unittest.TestCase):
    def test_configured_read_errors_are_not_missing_records(self):
        with patch.object(drive, 'is_configured', return_value=True), \
             patch.object(drive, '_get_drive', side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError):
                drive.download_json('daily.json', strict=True)

    def test_required_upload_without_configuration_fails(self):
        with patch.object(drive, 'is_configured', return_value=False):
            with self.assertRaises(RuntimeError):
                drive.upload_json('daily.json', {}, strict=True)

    def test_duplicate_drive_names_fail_instead_of_picking_stale_state(self):
        from unittest.mock import MagicMock
        transport = MagicMock()
        transport.files().list().execute.return_value = {'files': [{'id': 'one'}, {'id': 'two'}]}
        with self.assertRaises(RuntimeError):
            drive._find_file_id(transport, 'briefing_2026-07-01.json')

    def test_action_event_pagination_and_incremental_download(self):
        from unittest.mock import MagicMock
        transport = MagicMock()
        transport.files().list().execute.side_effect = [
            {'files': [{'id': 'known', 'name': 'riot_db_opportunity_action_known.json'}], 'nextPageToken': 'next'},
            {'files': [{'id': 'new', 'name': 'riot_db_opportunity_action_new.json'}]}]
        transport.files().get_media().execute.return_value = b'{"id":"new","opportunity_id":"a","created_at":"2026-01-01","changes":{"status":"approved"}}'
        with patch.object(drive, 'is_configured', return_value=True), patch.object(drive, '_get_drive', return_value=transport):
            events = drive.download_action_events({'opportunity_action_known.json'})
        self.assertEqual(list(events), ['opportunity_action_new.json'])
        self.assertEqual(events['opportunity_action_new.json']['changes'], {'status': 'approved'})



class DigestTests(unittest.TestCase):
    def setUp(self):
        from services import digest_delivery
        self.delivery = digest_delivery
        self.remote = {}
        self.sent = []
        for p in (patch.object(drive, 'is_configured', return_value=True),
                  patch.object(drive, 'download_json', side_effect=lambda name, **kw: copy.deepcopy(self.remote.get(name))),
                  patch.object(drive, 'upload_json', side_effect=lambda name, value, **kw: self.remote.__setitem__(name, copy.deepcopy(value)))):
            p.start()
            self.addCleanup(p.stop)
        self.now = datetime(2026, 7, 1, 7, 10, tzinfo=timezone.utc)
        self.opps = [{'id': 'abc', 'story_title': 'Exact email idea', 'opportunity_type': 'blog', 'relevance_score': 9}]

    def test_dst_and_late_slot_rules(self):
        due = self.delivery.scheduled_run_due
        cases = [('2026-07-01T07:10:00+00:00', '0 7 * * 1-5', True),
                 ('2026-07-01T08:10:00+00:00', '0 8 * * 1-5', False),
                 ('2026-12-01T08:10:00+00:00', '0 8 * * 1-5', True),
                 ('2026-12-01T08:10:00+00:00', '0 7 * * 1-5', False),
                 ('2026-07-01T10:00:00+00:00', '0 7 * * 1-5', True),
                 ('2026-07-04T07:10:00+00:00', '0 7 * * 1-5', False)]
        for iso, schedule, want in cases:
            with self.subTest(iso=iso, schedule=schedule):
                self.assertEqual(due(datetime.fromisoformat(iso), schedule), want)

    def deliver(self, sender=None, builder=None):
        return self.delivery.deliver_digest('test@example.invalid',
            build=builder or (lambda: self.opps),
            send=sender or (lambda records, address, **kw: self.sent.append(copy.deepcopy(records)) or True),
            now=lambda: self.now)

    def test_inbox_keeps_snapshot_text_and_current_decision(self):
        pending, handled = self.delivery.inbox_opportunities(
            {'opportunities': [{'id': 'a', 'story_title': 'Emailed angle'},
                               {'id': 'b', 'story_title': 'Approved idea'},
                               {'id': 'missing', 'story_title': 'Unavailable idea'}]},
            [{'id': 'a', 'story_title': 'Later changed angle', 'status': 'pending'},
             {'id': 'b', 'status': 'generated', 'pack_id': 'pack-1'}])
        self.assertEqual(pending[0]['story_title'], 'Emailed angle')
        self.assertEqual([o['status'] for o in handled], ['generated', 'unavailable'])
        self.assertEqual(handled[0]['pack_id'], 'pack-1')

    def test_duplicate_does_not_rebuild_or_resend(self):
        self.deliver()
        self.opps[0]['story_title'] = 'Changed later'
        self.deliver(builder=lambda: self.fail('duplicate rebuilt'))
        self.assertEqual(self.sent, [[{'id': 'abc', 'story_title': 'Exact email idea', 'opportunity_type': 'blog', 'relevance_score': 9}]])
        self.assertEqual(self.remote['briefing_2026-07-01.json']['opportunities'], self.sent[0])

    def test_crash_after_send_requires_recovery(self):
        def crash(*a, **kw):
            raise RuntimeError('SMTP outcome unknown')
        with self.assertRaises(RuntimeError):
            self.deliver(sender=crash)
        with self.assertRaises(RuntimeError):
            self.deliver()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.remote['briefing_2026-07-01.json']['status'], 'sending')

    def test_failed_snapshot_save_never_sends(self):
        with patch.object(drive, 'upload_json', side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError):
                self.deliver()
        self.assertEqual(self.sent, [])

    def test_read_failure_never_sends(self):
        with patch.object(drive, 'download_json', side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError):
                self.deliver()
        self.assertEqual(self.sent, [])

    def test_generation_failure_does_not_send_empty_digest(self):
        def fail():
            raise RuntimeError('no feeds')
        with self.assertRaises(RuntimeError):
            self.deliver(builder=fail)
        self.assertEqual(self.sent, [])

    def test_smtp_delay_past_nine_still_sends(self):
        def slow_smtp(records, address, **kwargs):
            self.now = datetime(2026, 7, 1, 8, 1, tzinfo=timezone.utc)
            kwargs['before_send']()
            self.sent.append(records)
            return True
        self.assertEqual(self.deliver(sender=slow_smtp), 'sent')
        self.assertEqual(self.sent, [self.opps])

    def test_generation_finishing_late_still_sends(self):
        def slow():
            self.now = datetime(2026, 7, 1, 8, 5, tzinfo=timezone.utc)
            return self.opps
        self.assertEqual(self.deliver(builder=slow), 'sent')
        self.assertEqual(self.sent, [self.opps])

    def test_afternoon_start_sends_once_despite_later_retry(self):
        self.now = datetime(2026, 7, 1, 14, 30, tzinfo=timezone.utc)
        self.assertEqual(self.deliver(), 'sent')
        self.now = datetime(2026, 7, 1, 18, 0, tzinfo=timezone.utc)
        self.assertEqual(self.deliver(), 'already_sent')
        self.assertEqual(self.sent, [self.opps])

    def test_smtp_crossing_midnight_does_not_send_previous_days_digest(self):
        self.now = datetime(2026, 7, 1, 22, 59, tzinfo=timezone.utc)
        def slow_smtp(records, address, **kwargs):
            self.now = datetime(2026, 7, 1, 23, 1, tzinfo=timezone.utc)
            kwargs['before_send']()
            self.sent.append(records)
            return True
        with self.assertRaises(RuntimeError):
            self.deliver(sender=slow_smtp)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.remote['briefing_2026-07-01.json']['status'], 'ready')


if __name__ == '__main__':
    unittest.main()
