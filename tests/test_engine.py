import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from email import message_from_string

with patch('dotenv.load_dotenv'), patch.dict('os.environ', {}, clear=True):
    from services import autonomous_engine as engine
    from services import opportunity_tracker as tracker
    from services import drive_persistence as drive


class EngineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.backlog = [{'id': 'keep', 'story_title': 'Existing', 'status': 'pending', 'relevance_score': 8}]
        (self.root / 'opportunities.json').write_text(json.dumps(self.backlog))
        replacements = [patch('dotenv.load_dotenv'), patch.dict('os.environ', {}, clear=True),
            patch.object(engine, 'DATA_DIR', str(self.root)),
            patch.object(engine, 'BRIEFING_CACHE_FILE', str(self.root / 'cache.json')),
            patch.object(tracker, 'DATA_DIR', str(self.root)),
            patch.object(tracker, 'OPP_FILE', str(self.root / 'opportunities.json')),
            patch.object(drive, 'is_configured', return_value=False),
            patch('services.x_monitor.is_configured', return_value=False),
            patch('services.source_credibility.is_credible', return_value=True)]
        for replacement in replacements:
            replacement.start()
            self.addCleanup(replacement.stop)
        self.feeds = []
        for name in ['fetch_uk_vape_news', 'fetch_global_vape_news', 'fetch_trending_news']:
            replacement = patch('services.news_monitor.' + name, return_value=[{'error': 'offline'}])
            self.feeds.append(replacement.start())
            self.addCleanup(replacement.stop)
        for path in ['services.competitor_monitor.fetch_all_competitor_news', 'services.regulator_monitor.get_all_regulator_news']:
            replacement = patch(path, return_value={'body': [{'error': 'offline'}]})
            replacement.start()
            self.addCleanup(replacement.stop)

    def test_all_feed_failures_raise_and_keep_backlog(self):
        with self.assertRaisesRegex(RuntimeError, 'feed'):
            engine.run_daily_briefing(force=True)
        self.assertEqual(tracker.get_pending_opportunities(), self.backlog)
        self.assertFalse((self.root / 'cache.json').exists())

    def test_one_healthy_empty_feed_is_a_quiet_day(self):
        self.feeds[0].return_value = []
        self.assertEqual(engine.run_daily_briefing(force=True), self.backlog)

    def test_failure_of_first_feed_still_tries_other_feeds(self):
        self.feeds[0].side_effect = RuntimeError('offline')
        self.feeds[1].return_value = []
        self.assertEqual(engine.run_daily_briefing(force=True), self.backlog)

    def test_all_analysis_failures_raise_without_clearing_backlog(self):
        self.feeds[0].return_value = [{'title': 'New story', 'source': {'name': 'BBC'}}]
        with patch.object(engine, 'analyse_story_for_riot', return_value={'error': 'AI unavailable'}):
            with self.assertRaisesRegex(RuntimeError, 'analys'):
                engine.run_daily_briefing(force=True)
        self.assertEqual(tracker.get_pending_opportunities(), self.backlog)

    def test_successful_low_relevance_analysis_is_a_quiet_day(self):
        self.feeds[0].return_value = [{'title': 'New story', 'source': {'name': 'BBC'}}]
        with patch.object(engine, 'analyse_story_for_riot', return_value={'relevance_score': 1}):
            self.assertEqual(engine.run_daily_briefing(force=True), self.backlog)

    def test_email_empty_app_url_uses_absolute_snapshot_link_in_both_parts(self):
        with patch.dict('os.environ', {'SMTP_USER': 'test@example.invalid', 'SMTP_PASSWORD': 'fake', 'PR_DESK_APP_URL': ''}), patch('smtplib.SMTP_SSL') as smtp:
            self.assertTrue(engine.send_digest_email([], 'test@example.invalid', briefing_id='2026-09-09'))
            message = message_from_string(smtp.return_value.__enter__.return_value.sendmail.call_args.args[2])
        for part in message.get_payload():
            self.assertIn('https://riot-pr-desk-5k9kicamlm6rxkugrrymxq.streamlit.app/inbox?briefing=2026-09-09', part.get_payload(decode=True).decode())
