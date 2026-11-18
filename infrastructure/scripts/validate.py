"""Validate monitoring configuration without AWS credentials or deployment."""
from pathlib import Path
import json
import re

import yaml

ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = ROOT / "vacation_planner/src/vacation_planner/monitoring_config.json"


def validate():
    settings = json.loads(SETTINGS_PATH.read_text())
    template = yaml.safe_load((ROOT / "infrastructure/serverless.yml").read_text())
    assert settings["notification_mode"] == "all"
    assert settings["log_retention_days"] in {7, 14, 30, 60, 90}
    assert settings["maximum_email_result_characters"] <= 12000
    assert 0 < settings["failure_count_threshold"] <= 100
    assert settings["slow_request_seconds"] > 0
    assert settings["alarm_period_seconds"] >= 60
    bootstrap = yaml.safe_load((ROOT / "infrastructure/bootstrap/github-deployment-role.yml").read_text())
    assert bootstrap["Parameters"]["ServiceName"]["Default"] == settings["service_name"]
    assert bootstrap["Parameters"]["Stage"]["Default"] == settings["stage"]
    assert settings["log_group_name"] == f"/apps/vacation-planner/{settings['stage']}"
    assert settings["topic_name"] == f"vacation-planner-{settings['stage']}-notifications"
    assert settings["alarm_name_prefix"] == f"vacation-planner-{settings['stage']}"
    assert settings["dashboard_name"] == f"vacation-planner-{settings['stage']}"
    assert "functions" not in template
    resources = template["resources"]["Resources"]
    assert not any(resource["Type"] in {"AWS::Lambda::Function", "AWS::DynamoDB::Table", "AWS::SQS::Queue"} for resource in resources.values())
    parameters = template["resources"]["Parameters"]
    assert parameters["NotificationEmail"]["NoEcho"] is True
    assert "Default" not in parameters["NotificationEmail"]
    assert resources["AdministratorSubscription"]["Properties"]["Endpoint"] == {"Ref": "NotificationEmail"}
    policy = resources["RuntimeMonitoringPolicy"]["Properties"]["PolicyDocument"]
    for statement in policy["Statement"]:
        assert statement["Action"] in {"logs:PutLogEvents", "sns:Publish"}
        assert statement["Resource"] != "*"
    source = (ROOT / "infrastructure/serverless.yml").read_text()
    assert not re.search(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", source)
    print("Monitoring configuration, private parameters, resource scope, and runtime permissions validated.")


if __name__ == "__main__":
    validate()
