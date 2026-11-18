"""Validate the monitoring template and deployment guard without AWS writes."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("monitoring_deployment", ROOT / "infrastructure/scripts/deploy.py")
deployment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deployment)


class InfrastructureTests(unittest.TestCase):
    def test_deployment_requires_main_in_the_expected_github_repository(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                deployment.require_pipeline()
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "rohitjain2021/vacation-planner", "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "pull_request"}, clear=True):
            with self.assertRaises(RuntimeError):
                deployment.require_pipeline()
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "rohitjain2021/vacation-planner", "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "push"}, clear=True):
            deployment.require_pipeline()

    def test_recipient_is_private_and_runtime_writes_are_resource_scoped(self):
        template = yaml.safe_load((ROOT / "infrastructure/serverless.yml").read_text())
        parameters = template["resources"]["Parameters"]
        self.assertTrue(parameters["NotificationEmail"]["NoEcho"])
        self.assertNotIn("Default", parameters["NotificationEmail"])
        resources = template["resources"]["Resources"]
        for statement in resources["RuntimeMonitoringPolicy"]["Properties"]["PolicyDocument"]["Statement"]:
            self.assertNotEqual(statement["Resource"], "*")
            self.assertIn(statement["Action"], {"logs:PutLogEvents", "sns:Publish"})
        self.assertFalse(any(resource["Type"] in {"AWS::Lambda::Function", "AWS::DynamoDB::Table", "AWS::SQS::Queue"} for resource in resources.values()))


if __name__ == "__main__":
    unittest.main()
