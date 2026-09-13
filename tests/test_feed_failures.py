import unittest
from unittest.mock import patch
from services import news_monitor as news, competitor_monitor as competitors, regulator_monitor as radar


class FeedFailureTests(unittest.TestCase):
    def setUp(self):
        news._cache.clear()
        competitors._cache.clear()
        radar._cache.clear()

    def all_feeds(self):
        yield news.fetch_uk_vape_news()
        yield news.fetch_global_vape_news()
        yield news.fetch_trending_news()
        yield news.fetch_social_viral_news()
        yield from competitors.fetch_all_competitor_news().values()
        yield from competitors.fetch_regulator_news().values()
        yield from radar.get_all_regulator_news().values()

    def test_transport_outage_remains_error_through_actual_aggregators(self):
        with patch.object(news, 'urlopen', side_effect=OSError('offline')), patch('services.error_logger.log_error'):
            for feed in self.all_feeds():
                self.assertTrue(feed)
                self.assertTrue(all('error' in article for article in feed))

    def test_valid_empty_rss_is_a_quiet_feed(self):
        with patch.object(news, 'urlopen') as fetch:
            fetch.return_value.read.return_value = b'<rss><channel/></rss>'
            self.assertTrue(all(feed == [] for feed in self.all_feeds()))

    def test_one_successful_empty_source_does_not_become_total_failure(self):
        with patch.object(news, '_search_gnews', side_effect=[[], [{'error': 'offline'}], [{'error': 'offline'}], [{'error': 'offline'}]]):
            self.assertEqual(news.fetch_uk_vape_news(), [])
