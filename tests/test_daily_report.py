import unittest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from database.queries import get_daily_house_stats
from utils.scheduler import send_refill_notification_to_super_admins

class TestDailyReport(unittest.TestCase):

    def setUp(self):
        self.start = datetime.now() - timedelta(days=1)
        self.end = datetime.now()

    @patch('database.queries.get_db_session')
    def test_get_daily_house_stats(self, mock_session):
        mock_query = MagicMock()
        mock_session.return_value.__enter__.return_value.query.return_value.join.return_value.filter.return_value.scalar.side_effect = [10000, 8000]

        stats = get_daily_house_stats(self.start, self.end)
        self.assertEqual(stats['total_bets'], 10000)
        self.assertEqual(stats['total_payouts'], 8000)
        self.assertEqual(stats['house_profit'], 2000)

    @patch('database.queries.get_db_session')
    @patch('config.constants.SUPER_ADMINS', [123])
    @patch('telegram.Bot')
    @patch('utils.user_utils.get_user_display_name')
    def test_send_refill_notification(self, mock_display, mock_bot, mock_session):
        mock_display.return_value = 'TestAdmin'
        mock_session.return_value.__enter__.return_value.query.return_value.join.return_value.filter.return_value.scalar.side_effect = [10000, 8000]
        refill_details = [{'admin_id': '1', 'username': 'admin', 'refills': [{'chat_id': '1', 'old_amount': 0, 'new_amount': 1000}]}]
        asyncio.run(send_refill_notification_to_super_admins(refill_details, 1))
        mock_bot.return_value.send_message.assert_called()

if __name__ == '__main__':
    unittest.main()