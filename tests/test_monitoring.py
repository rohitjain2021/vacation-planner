"""Exercise event logging and notifications using SDK fakes, never real AWS."""
import importlib.util
import json
from pathlib import Path
import os
import unittest
from unittest.mock import Mock, patch

PATH = Path(__file__).resolve().parents[1] / "vacation_planner/src/vacation_planner/monitoring.py"
spec = importlib.util.spec_from_file_location("monitoring_under_test", PATH)
monitoring = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitoring)


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.logs, self.sns, self.sts = Mock(), Mock(), Mock()
        self.logs.put_log_events.return_value = {}
        self.sts.get_caller_identity.return_value = {"Account": "123456789012"}
        self.session = Mock()
        self.session.client.side_effect = {"logs": self.logs, "sns": self.sns, "sts": self.sts}.get
        self.session.get_partition_for_region.return_value = "aws"
        # Side effects receive region/config keyword arguments as well.
        self.session.client.side_effect = lambda name, **kwargs: {"logs": self.logs, "sns": self.sns, "sts": self.sts}[name]
        self.monitor = monitoring.RequestMonitor(session=self.session)

    def test_submission_is_logged_and_emailed(self):
        self.assertEqual(self.monitor.record("submitted", "request-1", "London"), {"logs": True, "email": True})
        event = json.loads(self.logs.put_log_events.call_args.kwargs["logEvents"][0]["message"])
        self.assertEqual(event["destination"], "London")
        self.assertEqual(event["event"], "submitted")
        message = self.sns.publish.call_args.kwargs["Message"]
        self.assertIn("London", message)
        self.assertIn("request-1", message)

    def test_success_email_contains_result_while_logs_store_only_result_length(self):
        self.monitor.record("succeeded", "request-1", "London", duration_seconds=3.5, result="A detailed travel guide")
        event = json.loads(self.logs.put_log_events.call_args.kwargs["logEvents"][0]["message"])
        self.assertEqual(event["duration_seconds"], 3.5)
        self.assertEqual(event["result_characters"], len("A detailed travel guide"))
        self.assertNotIn("A detailed travel guide", json.dumps(event))
        self.assertIn("A detailed travel guide", self.sns.publish.call_args.kwargs["Message"])

    def test_failure_uses_safe_category_without_raw_exception(self):
        self.monitor.record("failed", "request-2", "Paris", duration_seconds=2, error=RuntimeError("Unable to locate credentials: private-detail"))
        message = self.sns.publish.call_args.kwargs["Message"]
        self.assertIn("authentication", message)
        self.assertIn("No travel plan was generated", message)
        self.assertNotIn("private-detail", message)

    def test_environment_secret_values_are_redacted_before_transmission(self):
        value = "test-only" + "-private-value" * 3
        with patch.dict(os.environ, {"SERPER_API_KEY": value}):
            self.monitor.record("succeeded", "request-3", value, result=value)
        self.assertNotIn(value, str(self.logs.put_log_events.call_args))
        self.assertNotIn(value, str(self.sns.publish.call_args))

    def test_sns_failure_is_logged_and_does_not_raise(self):
        self.sns.publish.side_effect = RuntimeError("private-failure-detail")
        with self.assertLogs("vacation_planner.monitoring", level="WARNING") as messages:
            delivery = self.monitor.record("submitted", "request-4", "Tokyo")
        self.assertEqual(delivery, {"logs": True, "email": False})
        self.assertNotIn("private-failure-detail", " ".join(messages.output))
        final = json.loads(self.logs.put_log_events.call_args.kwargs["logEvents"][0]["message"])
        self.assertEqual(final["event"], "notification_failed")

    def test_cloudwatch_failure_does_not_prevent_email(self):
        self.logs.put_log_events.side_effect = RuntimeError("log delivery unavailable")
        with self.assertLogs("vacation_planner.monitoring", level="WARNING"):
            delivery = self.monitor.record("failed", "request-5", "Rome", error=ValueError())
        self.assertEqual(delivery, {"logs": False, "email": True})

    def test_oversized_results_are_bounded_for_email(self):
        self.monitor.record("succeeded", "request-6", "Bali", result="a" * 20000)
        message = self.sns.publish.call_args.kwargs["Message"]
        self.assertIn("[Truncated;", message)
        self.assertLess(len(message.encode()), 256 * 1024)

    def test_unknown_event_is_rejected_without_aws_calls(self):
        with self.assertRaises(ValueError):
            self.monitor.record("unknown", "request-7", "London")
        self.session.client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
