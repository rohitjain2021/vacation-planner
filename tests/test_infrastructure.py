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

    def test_oidc_bootstrap_trusts_only_this_repository_main_and_cannot_change_roles(self):
        template = yaml.safe_load((ROOT / "infrastructure/bootstrap/github-deployment-role.yml").read_text())
        role = template["Resources"]["DeploymentRole"]["Properties"]
        trust = role["AssumeRolePolicyDocument"]["Statement"][0]
        conditions = trust["Condition"]["StringEquals"]
        self.assertEqual(conditions["token.actions.githubusercontent.com:aud"], "sts.amazonaws.com")
        self.assertEqual(set(conditions["token.actions.githubusercontent.com:sub"]), {
            "repo:rohitjain2021/vacation-planner:ref:refs/heads/main",
            "repo:rohitjain2021@44851658/vacation-planner@1460177139:ref:refs/heads/main",
        })
        for statement in role["Policies"][0]["PolicyDocument"]["Statement"]:
            actions = statement["Action"]
            actions = [actions] if isinstance(actions, str) else actions
            self.assertFalse(any(action in {"iam:*", "iam:CreateRole", "iam:UpdateAssumeRolePolicy", "iam:PassRole", "iam:PutUserPolicy", "iam:AttachRolePolicy"} for action in actions))
            if "iam:AttachUserPolicy" in actions:
                self.assertEqual(statement["Resource"], {"Ref": "RuntimeIamUserArn"})
                self.assertIn("iam:PolicyARN", statement["Condition"]["ArnLike"])

    def test_only_deployment_job_receives_oidc_and_no_aws_key_secrets_are_used(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
        self.assertNotIn("id-token", workflow["permissions"])
        job = workflow["jobs"]["deploy-monitoring"]
        self.assertEqual(job["permissions"]["id-token"], "write")
        credential_step = next(step for step in job["steps"] if step.get("uses", "").startswith("aws-actions/configure-aws-credentials@"))
        self.assertEqual(credential_step["with"]["role-to-assume"], "${{ env.AWS_DEPLOY_ROLE_ARN }}")
        self.assertNotIn("aws-access-key-id", credential_step["with"])
        self.assertNotIn("aws-secret-access-key", credential_step["with"])


if __name__ == "__main__":
    unittest.main()
