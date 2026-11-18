"""Deploy only in GitHub Actions; never prints credentials or the recipient."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import boto3

ROOT = Path(__file__).resolve().parents[2]
INFRA = ROOT / "infrastructure"
SETTINGS = json.loads((ROOT / "vacation_planner/src/vacation_planner/monitoring_config.json").read_text())


def require_pipeline():
    if not (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_REPOSITORY") == "rohitjain2021/vacation-planner"
        and os.environ.get("GITHUB_REF") == "refs/heads/main"
        and os.environ.get("GITHUB_EVENT_NAME") in {"push", "workflow_dispatch"}
    ):
        raise RuntimeError("Deployment is allowed only through this repository's GitHub Actions workflow on main.")


def run():
    require_pipeline()
    from validate import validate
    validate()
    environment = dict(os.environ)
    for name in ("ALERT_EMAIL", "RUNTIME_IAM_USER_NAME"):
        if not environment.get(name):
            raise RuntimeError(f"Missing deployment setting: {name}")
    if not (environment.get("SERVERLESS_ACCESS_KEY") or environment.get("SERVERLESS_LICENSE_KEY")):
        raise RuntimeError("Configure SERVERLESS_ACCESS_KEY or SERVERLESS_LICENSE_KEY in repository Actions secrets.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", environment["ALERT_EMAIL"]):
        raise RuntimeError("ALERT_EMAIL must contain one valid recipient address.")
    session = boto3.Session(region_name=SETTINGS["region"])
    identity = session.client("sts").get_caller_identity()
    expected_role = f"{SETTINGS['service_name']}-{SETTINGS['stage']}-github-deploy"
    if not identity["Arn"].split(":")[-1].startswith(f"assumed-role/{expected_role}/"):
        raise RuntimeError("Deployment requires this project's OIDC deployment role.")
    environment["DEPLOYMENT_BUCKET_NAME"] = f"{SETTINGS['service_name']}-{SETTINGS['stage']}-{identity['Account']}-{SETTINGS['region']}"
    if not re.fullmatch(r"[\w+=,.@-]+", environment["RUNTIME_IAM_USER_NAME"]):
        raise RuntimeError("RUNTIME_IAM_USER_NAME must name an existing IAM user, not an ARN or role.")
    cf = session.client("cloudformation")
    subprocess.run(["npm", "exec", "--", "serverless", "package", "--conceal"], cwd=INFRA, env=environment, check=True)
    template_path = INFRA / ".serverless/cloudformation-template-update-stack.json"
    template = json.loads(template_path.read_text())
    assert not any(r.get("Type") == "AWS::Lambda::Function" for r in template["Resources"].values())
    # The generated JSON is private and ignored; no state or resolved parameters are uploaded.
    cf.validate_template(TemplateBody=json.dumps(template))
    subprocess.run(["npm", "run", "deploy"], cwd=INFRA, env=environment, check=True)
    stack_name = f"{SETTINGS['service_name']}-{SETTINGS['stage']}"
    stack = cf.describe_stacks(StackName=stack_name)["Stacks"][0]
    if stack["StackStatus"] not in {"CREATE_COMPLETE", "UPDATE_COMPLETE"}:
        raise RuntimeError("CloudFormation did not reach a successful final status.")
    outputs = {item["OutputKey"]: item["OutputValue"] for item in stack["Outputs"]}
    logs = session.client("logs")
    groups = logs.describe_log_groups(logGroupNamePrefix=SETTINGS["log_group_name"])["logGroups"]
    assert any(group["logGroupName"] == SETTINGS["log_group_name"] and group["retentionInDays"] == SETTINGS["log_retention_days"] for group in groups)
    sns = session.client("sns")
    subscriptions = sns.list_subscriptions_by_topic(TopicArn=outputs["NotificationTopicArn"])["Subscriptions"]
    recipient = [item for item in subscriptions if item.get("Protocol") == "email" and item.get("Endpoint") == environment["ALERT_EMAIL"]]
    assert recipient, "The configured administrator subscription was not created."
    confirmed = any(item["SubscriptionArn"] != "PendingConfirmation" for item in recipient)
    from vacation_planner.monitoring import RequestMonitor
    request_id = f"ci-{os.environ['GITHUB_RUN_ID']}"
    monitor = RequestMonitor(session=session)
    # IAM policy attachment can take a few seconds to propagate.
    for attempt in range(6):
        delivery = monitor.record("submitted", request_id, "CI monitoring verification (not a traveler request)")
        if all(delivery.values()):
            break
        if attempt == 5:
            raise RuntimeError("Post-deployment log/notification publishing verification failed.")
        time.sleep(5)
    delivery = monitor.record("succeeded", request_id, "CI monitoring verification (not a traveler request)", duration_seconds=0.01, result="Monitoring deployment verification completed. No model or search provider was invoked.")
    if not all(delivery.values()):
        raise RuntimeError("Post-deployment completion event publishing failed.")
    events = []
    for _ in range(12):
        events = logs.filter_log_events(logGroupName=SETTINGS["log_group_name"], filterPattern=f'{{ $.request_id = "{request_id}" }}')["events"]
        if len(events) >= 2:
            break
        time.sleep(5)
    if len(events) < 2:
        raise RuntimeError("Published smoke events were not found in CloudWatch Logs.")
    summary = {
        "stack_name": stack_name, "stack_status": stack["StackStatus"],
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "log_group_name": outputs["LogGroupName"], "dashboard_name": outputs["DashboardName"],
        "smoke_events_verified": True, "email_subscription_confirmed": confirmed,
    }
    (INFRA / "deployment-summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    if not confirmed:
        print("::warning::AWS created the email subscription. The recipient must confirm the AWS subscription email before delivery starts.")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write("## Monitoring deployment\n\n```json\n" + json.dumps(summary, indent=2) + "\n```\n")


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        # Configuration errors are deliberately written without private values.
        if isinstance(error, RuntimeError):
            print("::error::" + str(error))
        else:
            code = getattr(error, "response", {}).get("Error", {}).get("Code", "")
            print(f"::error::Deployment failed ({type(error).__name__} {code}); inspect the preceding sanitized deployment steps.")
        sys.exit(1)
