"""Best-effort request telemetry and notifications; never expose provider errors."""

from datetime import datetime, timezone
from functools import lru_cache
from importlib.resources import files
import json
import logging
import os
from pathlib import Path
import re

import boto3
from botocore.config import Config
from dotenv import load_dotenv


SETTINGS = json.loads(files("vacation_planner").joinpath("monitoring_config.json").read_text())
LOGGER = logging.getLogger("vacation_planner.monitoring")
EVENTS = {"submitted", "succeeded", "failed"}


def sanitize(value, limit):
    """Redact known runtime secrets and common credential shapes before transmission."""
    text = str(value)
    for key, secret in os.environ.items():
        if re.search(r"key|secret|token|password", key, re.I) and len(secret) >= 8:
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(
        r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|\bsk-[A-Za-z0-9_-]{16,}|"
        r"\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{16,}",
        "[REDACTED]", text,
    )
    text = re.sub(
        r"(?i)((?:api[_-]?key|secret[_-]?(?:access[_-]?)?key|session[_-]?token|password)"
        r"\s*[:=]\s*)[^\s,;]+", r"\1[REDACTED]", text,
    )
    # Strip control characters; multiline Markdown is intentionally retained in results.
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text if len(text) <= limit else text[:limit] + "\n[Truncated; open the app for the full plan.]"


def error_category(error):
    """Return only a controlled label, never a raw exception or traceback."""
    name = type(error).__name__
    response = getattr(error, "response", {})
    code = response.get("Error", {}).get("Code", "") if isinstance(response, dict) else ""
    description = (name + " " + code + " " + str(error)).lower()
    if any(word in description for word in ("credential", "expiredtoken", "invalidclienttoken", "unauthorized")):
        return "authentication"
    if "accessdenied" in description or "permission" in description:
        return "permission"
    if "throttl" in description or "ratelimit" in description:
        return "rate_limit"
    if "timeout" in description or "timed out" in description:
        return "timeout"
    if "empty itinerary" in description:
        return "empty_result"
    return "generation_error"


class RequestMonitor:
    def __init__(self, session=None, settings=None):
        self.settings = settings or SETTINGS
        self.session = session
        self._logs = None
        self._sns = None
        self._topic_arn = None

    def _client(self, service):
        if self.session is None:
            self.session = boto3.Session()
        return self.session.client(
            service, region_name=self.settings["region"],
            config=Config(connect_timeout=2, read_timeout=4, retries={"total_max_attempts": 2}),
        )

    def _write_log(self, event):
        if self._logs is None:
            self._logs = self._client("logs")
        timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        response = self._logs.put_log_events(
            logGroupName=self.settings["log_group_name"],
            logStreamName=self.settings["log_stream_name"],
            logEvents=[{"timestamp": timestamp, "message": json.dumps(event, ensure_ascii=False)}],
        )
        if response.get("rejectedLogEventsInfo"):
            raise RuntimeError("CloudWatch rejected an event timestamp")

    def _publish(self, event, result):
        if self._sns is None:
            self._sns = self._client("sns")
        if self._topic_arn is None:
            account = self._client("sts").get_caller_identity()["Account"]
            partition = self.session.get_partition_for_region(self.settings["region"])
            self._topic_arn = (
                f"arn:{partition}:sns:{self.settings['region']}:{account}:{self.settings['topic_name']}"
            )
        labels = {"submitted": "Request submitted", "succeeded": "Plan generated", "failed": "Plan failed"}
        lines = [
            f"Status: {labels[event['event']]}", f"Destination: {event['destination']}",
            f"Request ID: {event['request_id']}", f"Time (UTC): {event['timestamp']}",
        ]
        if "duration_seconds" in event:
            lines.append(f"Generation duration: {event['duration_seconds']:.2f} seconds")
        if event["event"] == "failed":
            lines += [f"Error category: {event['error_category']}", "No travel plan was generated for this request."]
        elif result is not None:
            lines += ["", "Generated result:", sanitize(result, self.settings["maximum_email_result_characters"])]
        self._sns.publish(
            TopicArn=self._topic_arn, Subject=f"Vacation Planner | {labels[event['event']]}",
            Message="\n".join(lines),
        )

    def record(self, event, request_id, destination, *, duration_seconds=None, result=None, error=None):
        if event not in EVENTS:
            raise ValueError("Unsupported monitoring event")
        record = {
            "event": event, "request_id": str(request_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "destination": sanitize(destination, self.settings["maximum_destination_characters"]),
        }
        if duration_seconds is not None:
            record["duration_seconds"] = round(max(0, duration_seconds), 3)
        if result is not None:
            record["result_characters"] = len(result)
        if event == "failed":
            record["error_category"] = error_category(error)
        LOGGER.info(json.dumps(record, ensure_ascii=False))
        delivered = {"logs": False, "email": False}
        try:
            self._write_log(record)
            delivered["logs"] = True
        except Exception as exc:
            LOGGER.warning("monitoring_log_delivery_failed request_id=%s error_type=%s", request_id, type(exc).__name__)
        if self.settings["notification_mode"] == "all" or event == "failed":
            try:
                self._publish(record, result)
                delivered["email"] = True
            except Exception as exc:
                LOGGER.warning("monitoring_email_delivery_failed request_id=%s error_type=%s", request_id, type(exc).__name__)
                try:
                    self._write_log({
                        "event": "notification_failed", "request_id": str(request_id),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception:
                    pass
        return delivered


@lru_cache(maxsize=1)
def get_monitor():
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    return RequestMonitor()
