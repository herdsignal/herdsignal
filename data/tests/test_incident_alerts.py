import unittest
from unittest.mock import Mock, patch

import requests

from scheduler.incident_alerts import (
    IncidentAlertConfig,
    build_scheduler_message,
    send_scheduler_alert,
)


class IncidentAlertsTest(unittest.TestCase):
    def test_failure_message_limits_long_ticker_list(self):
        result = {
            "status": "PARTIAL_FAILURE",
            "total": 20,
            "success": ["SPY"],
            "failed": [f"T{i}" for i in range(12)],
        }
        message = build_scheduler_message(result)
        self.assertIn("성공 1/20", message)
        self.assertIn("외 2개", message)

    def test_success_is_silent_by_default(self):
        config = IncidentAlertConfig(webhook_url="https://example.test")
        with patch("scheduler.incident_alerts.requests.post") as post:
            sent = send_scheduler_alert({"status": "SUCCESS", "total": 1}, config)
        self.assertFalse(sent)
        post.assert_not_called()

    def test_webhook_failure_does_not_raise(self):
        response = Mock()
        response.raise_for_status.side_effect = requests.RequestException("unavailable")
        config = IncidentAlertConfig(webhook_url="https://example.test")
        with patch("scheduler.incident_alerts.requests.post", return_value=response):
            sent = send_scheduler_alert({"status": "FAILED", "total": 0}, config)
        self.assertFalse(sent)


if __name__ == "__main__":
    unittest.main()
