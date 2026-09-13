"""Offline AppTest coverage for dashboard reads and the real sidebar."""
import builtins
import os
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class AppShellTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('dotenv.load_dotenv'))
        self.stack.enter_context(patch('streamlit.secrets', {}))
        self.stack.enter_context(patch.dict(os.environ, {'GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT': ''}))
        # A forbidden read/write or network call must be observable even if UI catches it.
        self.forbidden = []
        original_open = builtins.open

        def guarded_open(file, mode='r', *args, **kwargs):
            if isinstance(file, (str, os.PathLike)):
                path = Path(file).absolute()
                if ROOT / 'data' in path.parents or path.name in ('.env', 'secrets.toml'):
                    self.forbidden.append(str(path))
                    raise AssertionError('Test attempted to access runtime data or credentials')
            return original_open(file, mode, *args, **kwargs)

        self.stack.enter_context(patch('builtins.open', guarded_open))
        self.network = self.stack.enter_context(patch('socket.socket.connect', side_effect=AssertionError('Unexpected network')))
        for target, value in {
            'services.pr_library.get_stats': {'total': 0, 'this_month': 0, 'total_coverage': 0},
            'services.pr_library.get_recent_packs': [],
            'services.pr_library.get_all_packs': [],
            'services.blog_library.get_all_blogs': [],
            'services.journalist_db.get_journalist_count': 0,
            'services.feedback.get_stats': {'up': 0, 'total': 0},
            'services.cultural_calendar.get_upcoming_events': [],
            'services.opportunity_tracker.get_inbox_count': 0,
            'services.opportunity_tracker.get_pending_opportunities': [],
            'services.ai_engine.is_configured': False,
        }.items():
            self.stack.enter_context(patch(target, return_value=value))
        self.generate = self.stack.enter_context(patch('services.autonomous_engine.run_daily_briefing', side_effect=AssertionError('Dashboard regenerated briefing')))
        self.load = self.stack.enter_context(patch('services.digest_delivery.load_briefing', return_value=None))
        self.upload = self.stack.enter_context(patch('services.drive_persistence.upload_json', side_effect=AssertionError('Unexpected write')))
        self.addCleanup(self.check_no_side_effects)

    def check_no_side_effects(self):
        self.assertEqual(self.forbidden, [])
        self.network.assert_not_called()
        self.generate.assert_not_called()
        self.upload.assert_not_called()

    def test_home_displays_saved_briefing_without_regeneration(self):
        self.load.return_value = {'id': '2026-09-09', 'created_at': '2026-09-09T07:00:00+00:00', 'opportunities': [
            {'id': 'synthetic', 'story_title': 'Saved synthetic briefing story', 'story_source': 'Fixture', 'riot_angle': 'Saved angle', 'relevance_score': 8}
        ]}
        at = AppTest.from_file(str(ROOT / 'app.py')).run()
        self.assertFalse(at.exception)
        rendered = '\n'.join(item.value for item in at.markdown)
        self.assertIn('Saved synthetic briefing story', rendered)
        self.assertIn('Saved angle', rendered)
        at.run()
        self.assertFalse(at.exception)

    def test_home_missing_briefing_does_not_generate(self):
        at = AppTest.from_file(str(ROOT / 'app.py')).run()
        self.assertFalse(at.exception)
        self.assertEqual(at.title[0].value, 'PR Desk')

    def test_real_sidebar_retains_workflows_and_removes_retired_pages(self):
        at = AppTest.from_file(str(ROOT / 'app.py')).run()
        self.assertFalse(at.exception)
        labels = [link.proto.label for link in at.sidebar.get('page_link')]
        self.assertIn('News Desk', labels)
        self.assertIn('Blog Writer', labels)
        self.assertIn('Regulatory Radar', labels)
        for label, filename in [('Story Ladder', '10_story_ladder.py'), ('Crisis Comms', '11_crisis_comms.py'), ('Quote Generator', '14_quote_generator.py')]:
            self.assertNotIn(label, labels)
            self.assertFalse((ROOT / 'pages' / filename).exists())

    def inbox(self):
        # Start at the actual entrypoint so multipage sidebar links resolve.
        at = AppTest.from_file(str(ROOT / 'app.py')).run()
        self.assertFalse(at.exception)
        self.load.reset_mock()
        return at.switch_page('pages/17_inbox.py')

    @staticmethod
    def opportunity(identifier, title, status='pending'):
        return {'id': identifier, 'story_title': title, 'status': status,
                'opportunity_type': 'pr_commentary', 'relevance_score': 8,
                'riot_angle': 'Synthetic angle'}

    def test_inbox_email_query_preserves_snapshot_and_live_decisions(self):
        saved = [self.opportunity('one', 'Emailed pending title'),
                 self.opportunity('two', 'Emailed handled title')]
        live = [self.opportunity('one', 'Changed live title'),
                self.opportunity('two', 'Changed handled title', 'skipped'),
                self.opportunity('three', 'New backlog title')]
        self.load.return_value = {'id': '2026-09-08', 'opportunities': saved}
        with patch('services.opportunity_tracker.get_all_opportunities', return_value=live), patch('services.opportunity_tracker.get_pending_opportunities', return_value=[live[0], live[2]]):
            at = self.inbox()
            at.query_params['briefing'] = '2026-09-08'
            at.run()
            self.assertFalse(at.exception)
            rendered = '\n'.join(item.value for item in at.markdown)
            self.assertIn('Emailed pending title', rendered)
            self.assertIn('Emailed handled title', rendered)
            self.assertIn('skipped', rendered)
            self.assertNotIn('Changed live title', rendered)
            self.assertNotIn('New backlog title', rendered)
            self.load.assert_called_with('2026-09-08')
            next(button for button in at.button if button.label == 'All pending ideas').click().run()
            self.assertFalse(at.exception)
            self.assertNotIn('briefing', at.query_params)
            self.assertIn('New backlog title', '\n'.join(item.value for item in at.markdown))

    def test_inbox_without_query_shows_sixth_pending_idea(self):
        live = [self.opportunity(str(i), f'Backlog story {i}') for i in range(6)]
        with patch('services.opportunity_tracker.get_pending_opportunities', return_value=live):
            at = self.inbox().run()
            self.assertFalse(at.exception)
            self.assertIn('Backlog story 5', '\n'.join(item.value for item in at.markdown))
            self.load.assert_not_called()

    def test_missing_email_snapshot_does_not_substitute_backlog(self):
        with patch('services.opportunity_tracker.get_pending_opportunities', return_value=[self.opportunity('one', 'Unrelated backlog')]):
            at = self.inbox()
            at.query_params['briefing'] = '2026-09-08'
            at.run()
            self.assertFalse(at.exception)
            self.assertTrue(at.error)
            self.assertNotIn('Unrelated backlog', '\n'.join(item.value for item in at.markdown))

if __name__ == '__main__':
    unittest.main()
