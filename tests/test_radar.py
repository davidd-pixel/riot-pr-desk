import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from services import regulator_monitor as radar
from services import news_monitor


class RadarTests(unittest.TestCase):
    def setUp(self):
        radar._cache.clear()
        news_monitor._cache.clear()

    def article(self, title, date):
        return {'title': title, 'publishedAt': date, 'url': title}

    def test_default_excludes_old_unknown_future_and_sorts_dates(self):
        now = datetime.now(timezone.utc)
        articles = [self.article('old', (now-timedelta(days=31)).isoformat()),
                    self.article('unknown', 'invalid'), self.article('missing', None),
                    self.article('future', (now+timedelta(days=1)).isoformat()),
                    self.article('recent', (now-timedelta(days=2)).strftime('%a, %d %b %Y %H:%M:%S GMT')),
                    self.article('newest', (now-timedelta(hours=1)).replace(tzinfo=None).isoformat())]
        with patch.object(radar, '_search_gnews', return_value=articles):
            self.assertEqual([a['title'] for a in radar.get_news_for_body('MHRA')], ['newest', 'recent'])

    def test_history_cache_and_refresh(self):
        old = self.article('old', (datetime.now(timezone.utc)-timedelta(days=45)).isoformat())
        new = self.article('new', datetime.now(timezone.utc).isoformat())
        with patch.object(radar, '_search_gnews', return_value=[old]) as feed:
            self.assertEqual(radar.get_news_for_body('MHRA'), [])
            self.assertEqual(radar.get_news_for_body('MHRA', lookback_days=90), [old])
            feed.return_value = [new]
            self.assertEqual(radar.get_news_for_body('MHRA', lookback_days=90), [old])
            self.assertEqual(radar.get_news_for_body('MHRA', lookback_days=90, force_refresh=True), [new])

    def test_refresh_bypasses_rss_cache(self):
        xml = b'<rss><channel><item><title>Fresh</title><pubDate>Wed, 09 Sep 2026 10:00:00 GMT</pubDate></item></channel></rss>'
        with patch.object(news_monitor, 'urlopen') as fetch:
            fetch.return_value.read.return_value = xml
            first = news_monitor._search_gnews('MHRA')
            fetch.return_value.read.return_value = xml.replace(b'Fresh', b'Updated')
            self.assertEqual(news_monitor._search_gnews('MHRA'), first)
            self.assertEqual(news_monitor._search_gnews('MHRA', force_refresh=True)[0]['title'], 'Updated')

if __name__ == '__main__':
    unittest.main()
