"""Offline regressions: synthetic feeds, no credentials, library or remote calls."""
import builtins
import io
import os
import json
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch, MagicMock

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
# Prevent importing the AI engine from loading local credentials.
with patch('dotenv.load_dotenv'):
    from services import ai_engine, content_generator


class AIUIRegressionTests(unittest.TestCase):
    def setUp(self):
        self.call_anthropic = ai_engine._call_anthropic
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch("dotenv.load_dotenv"))
        self.stack.enter_context(patch('streamlit.secrets', {}))
        self.forbidden = []
        original_open = builtins.open
        original_io_open = io.open

        def guard(opener):
            def guarded(file, mode='r', *args, **kwargs):
                if isinstance(file, (str, os.PathLike)):
                    path = Path(file).absolute()
                    if ROOT / 'data' in path.parents or path.name in ('.env', 'secrets.toml'):
                        self.forbidden.append(str(path))
                        raise AssertionError('Unexpected runtime data or credential access')
                return opener(file, mode, *args, **kwargs)
            return guarded

        self.stack.enter_context(patch('builtins.open', guard(original_open)))
        self.stack.enter_context(patch('io.open', guard(original_io_open)))
        self.network = self.stack.enter_context(patch('socket.socket.connect', side_effect=AssertionError('Unexpected network')))
        self.addCleanup(self.check_no_side_effects)
        styles = ModuleType('utils.styles')
        styles.apply_global_styles = lambda: None
        styles.render_sidebar = lambda: None
        styles.get_page_icon = lambda: '📰'
        self.stack.enter_context(patch.dict('sys.modules', {'utils.styles': styles}))
        self.stack.enter_context(patch.object(ai_engine, 'is_configured', return_value=True))
        self.stack.enter_context(patch.object(ai_engine, 'get_system_prompt', return_value='test'))
        self.stack.enter_context(patch.object(ai_engine, 'log_error'))
        self.stack.enter_context(patch('services.blog_library._load', return_value=[]))
        self.library_save = self.stack.enter_context(patch('services.blog_library._save', side_effect=AssertionError('Unexpected save')))
        self.stack.enter_context(patch.object(ai_engine, '_call_anthropic', side_effect=AssertionError('Unexpected AI')))
        self.stack.enter_context(patch.object(ai_engine, '_call_openai', side_effect=AssertionError('Unexpected AI')))
        for name in ('fetch_uk_vape_news', 'fetch_global_vape_news', 'fetch_trending_news', 'fetch_social_viral_news'):
            self.stack.enter_context(patch('services.news_monitor.' + name, return_value=[]))

    def check_no_side_effects(self):
        self.assertEqual(self.forbidden, [])
        self.network.assert_not_called()
        self.library_save.assert_not_called()

    def news(self):
        at = AppTest.from_file(str(ROOT / 'pages/1_news_desk.py'))
        at.session_state['news_uk'] = [{'title': 'Test story', 'description': 'Synthetic description', 'source': {'name': 'Test'}, 'url': '', 'publishedAt': ''}]
        for key in ('news_global', 'news_trending', 'news_social'):
            at.session_state[key] = []
        return at.run()

    def test_analyse_failure_is_actionable_not_uncaught(self):
        with patch.object(content_generator, 'triage_news', side_effect=RuntimeError('private provider details')):
            at = self.news()
            at.button(key='uk_tri_0').click().run()
            self.assertFalse(at.exception)
            self.assertTrue(at.error)
            self.assertNotIn('private provider details', at.error[0].value)

    def test_analyse_rejects_wrong_json_shapes(self):
        for response in ([], None, {'category': None}, {'category': ['respond']}):
            with self.subTest(response=response), patch.object(content_generator, 'generate_json', return_value=response):
                at = self.news()
                at.button(key='uk_tri_0').click().run()
                self.assertFalse(at.exception)
                self.assertTrue(at.error)

    def test_create_blog_handoff_bad_keywords_falls_back(self):
        with patch.object(ai_engine, 'generate', return_value=json.dumps({'blog_type': 'News-Jack', 'primary_keyword': 'test', 'secondary_keywords': ['valid', 7]})):
            at = self.news()
            # AppTest does not execute st.switch_page; verify handoff then open destination.
            with patch('streamlit.switch_page'):
                at.button(key='uk_blog_0').click().run()
            topic = at.session_state['blog_topic']
            blog = AppTest.from_file(str(ROOT / 'pages/16_blog_writer.py'))
            blog.session_state['blog_topic'] = topic
            blog.session_state['blog_suggest_on_load'] = True
            blog.run()
            self.assertFalse(blog.exception)
            self.assertEqual(blog.text_area(key='blog_topic').value, topic)
            self.assertTrue(blog.warning)

    def test_blog_quickstart_sets_topic_before_widget(self):
        at = AppTest.from_file(str(ROOT / 'pages/16_blog_writer.py')).run()
        at.button(key='blog_qs_Vape Tax Explainer').click().run()
        self.assertFalse(at.exception)
        self.assertIn('vaping products duty', at.text_area(key='blog_topic').value)

    def test_anthropic_model_override_for_sync_and_stream(self):
        client = MagicMock()
        client.messages.create.return_value.content = [SimpleNamespace(type='text', text='ok')]
        client.messages.stream.return_value.__enter__.return_value.text_stream = iter(['ok'])
        with patch('anthropic.Anthropic', return_value=client), patch.dict('os.environ', {'ANTHROPIC_MODEL': 'custom-model'}):
            self.assertEqual(self.call_anthropic('s', 'u'), 'ok')
            self.assertEqual(list(ai_engine._stream_anthropic('s', 'u')), ['ok'])
            self.assertEqual(client.messages.create.call_args.kwargs['model'], 'custom-model')
            self.assertEqual(client.messages.stream.call_args.kwargs['model'], 'custom-model')

    def test_empty_anthropic_model_uses_default(self):
        for value in ('', '   '):
            with self.subTest(value=value):
                client = MagicMock()
                client.messages.create.return_value.content = [SimpleNamespace(type='text', text='ok')]
                client.messages.stream.return_value.__enter__.return_value.text_stream = iter(['ok'])
                with patch('anthropic.Anthropic', return_value=client), patch.dict('os.environ', {'ANTHROPIC_MODEL': value}):
                    self.call_anthropic('s', 'u')
                    list(ai_engine._stream_anthropic('s', 'u'))
                self.assertEqual(client.messages.create.call_args.kwargs['model'], 'claude-sonnet-5')
                self.assertEqual(client.messages.stream.call_args.kwargs['model'], 'claude-sonnet-5')

    def test_valid_analysis_remains_available(self):
        with patch.object(content_generator, 'generate_json', return_value={'category': 'respond', 'suggested_angle': 'Test angle', 'reasoning': 'Relevant'}):
            at = self.news()
            at.button(key='uk_tri_0').click().run()
            self.assertFalse(at.exception)
            self.assertIn('Test angle', at.success[0].value)

    def test_blog_provider_failure_keeps_manual_inputs(self):
        with patch.object(ai_engine, 'generate', side_effect=RuntimeError('private details')):
            at = AppTest.from_file(str(ROOT / 'pages/16_blog_writer.py'))
            at.session_state['blog_topic'] = 'Test topic'
            at.session_state['blog_suggest_on_load'] = True
            at.run()
            self.assertFalse(at.exception)
            self.assertTrue(at.warning)
            self.assertEqual(at.text_area(key='blog_topic').value, 'Test topic')
            self.assertEqual(at.text_input(key='blog_primary_keyword').value, '')

    def test_stream_iteration_failure_is_wrapped(self):
        def failing_stream(*args):
            yield 'partial'
            raise ValueError('provider failed')
        with patch.object(ai_engine, '_stream_anthropic', failing_stream), patch.object(ai_engine, '_get_provider', return_value='anthropic'):
            with self.assertRaisesRegex(RuntimeError, 'AI streaming failed'):
                list(ai_engine.generate_stream('test', system_prompt='test'))

if __name__ == '__main__':
    unittest.main()
