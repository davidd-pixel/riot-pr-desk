"""AI story schema regressions with synthetic input and no external calls."""
import unittest
from unittest.mock import patch

with patch('dotenv.load_dotenv'):
    from services import ai_engine
from services.autonomous_engine import analyse_story_for_riot


class StoryAnalysisTests(unittest.TestCase):
    def analyse(self, response):
        with patch.object(ai_engine, 'generate_json', return_value=response):
            return analyse_story_for_riot({'title': 'Synthetic story', 'description': 'Fixture only'})

    def test_invalid_scores_are_rejected(self):
        for score in ('8', True, None, 8.5, 0, 11, [], {}):
            with self.subTest(score=score):
                self.assertIn('error', self.analyse({'relevance_score': score, 'riot_angle': 'Angle'}))

    def test_non_string_output_fields_are_rejected(self):
        for field in ('riot_angle', 'suggested_position', 'why_it_matters', 'newsjacking_concept',
                      'newsjacking_hook', 'newsjacking_execution', 'newsjacking_format', 'newsjacking_speed'):
            for value in (None, [], 7):
                with self.subTest(field=field, value=value):
                    self.assertIn('error', self.analyse({'relevance_score': 8, field: value}))

    def test_malformed_opportunity_types_are_rejected(self):
        for types in ([['blog']], [{'kind': 'blog'}], [True], {'blog': True}, ['invalid'], []):
            with self.subTest(types=types):
                self.assertIn('error', self.analyse({'relevance_score': 8, 'opportunity_types': types}))

    def test_valid_response_retained_and_optional_strings_normalised(self):
        result = self.analyse({'relevance_score': 8, 'riot_angle': 'Keep this angle', 'opportunity_types': ['blog', 'pr_commentary']})
        self.assertNotIn('error', result)
        self.assertEqual(result['relevance_score'], 8)
        self.assertEqual(result['riot_angle'], 'Keep this angle')
        self.assertEqual(result['opportunity_types'], ['blog', 'pr_commentary'])
        self.assertEqual(result['newsjacking_hook'], '')
        self.assertEqual(result['suggested_position'], '')

    def test_legacy_single_type_is_supported(self):
        result = self.analyse({'relevance_score': 6, 'opportunity_type': 'blog'})
        self.assertEqual(result['opportunity_types'], ['blog'])

if __name__ == '__main__':
    unittest.main()
