# Request monitoring and email notifications

This resources-only Serverless Framework service adds CloudWatch Logs, metric filters, a dashboard, alarms, SNS notifications, and scoped application write permissions. The Streamlit/CrewAI application keeps its existing hosting and model configuration.

## Parameters

All non-secret operational settings live in [`monitoring_config.json`](../vacation_planner/src/vacation_planner/monitoring_config.json), shared by Python and `serverless.yml`:

| Setting | Initial value |
| --- | --- |
| Stage / region | `prod` / `us-east-1` |
| Log group / stream | `/apps/vacation-planner/prod` / `requests` |
| Log retention | 30 days |
| Metric namespace | `VacationPlanner/Prod` |
| Failure alarm | 3 failures in 5 minutes |
| Slow planning alarm | A completed generation taking more than 120 seconds |
| Notification mode | `all`: submission and success/failure result |
| Result email limit | 12,000 characters, with an explicit truncation note |

The recipient is an AWS CloudFormation `NoEcho` parameter supplied through the `ALERT_EMAIL` GitHub Actions secret. It is not stored in source code or public build artifacts.

## What is recorded and sent

1. A valid **Plan my trip** submission creates a UUID request ID.
2. A `submitted` event records the destination and UTC time in CloudWatch and sends a submission email through SNS.
3. A `succeeded` event records generation duration and result length; its email includes the generated guide, bounded to the configured size.
4. A `failed` event records a controlled error category and duration; its email identifies the failed request and states that no new plan was generated.
5. Alarms provide additional aggregated failure, slow-generation, and notification-publishing alerts. Failure and latency alarms also send recovery notifications.

Blank input, typing into the form, normal reruns, and downloads do not send emails. Destinations are bounded, control characters and recognizable credential values are redacted, and raw provider exceptions are not logged or emailed. Operational logs do not contain the full generated guide. Request destinations and generated result emails can contain user-provided information, so access to the log group and subscriber mailbox should be restricted appropriately.

If AWS logging fails, email publishing is still attempted. If SNS publishing fails, a notification-failure event is written to CloudWatch when possible. A telemetry failure does not discard a valid travel plan. Invalid AWS credentials or a complete network outage can prevent both telemetry channels from working; this is not an external uptime monitor.

## Deployment: GitHub Actions only

The existing [Vacation Planner CI](https://github.com/rohitjain2021/vacation-planner/actions/workflows/ci.yml) deploys this stack from `main` only after Python tests and credential scanning pass. Pull requests validate code and configuration without credentials or AWS mutations.

Repository variables (the same OIDC convention used by `e-learning-platform`):

- `AWS_DEPLOY_ROLE_ARN`: the `DeploymentRoleArn` output from this project's bootstrap stack.
- `RUNTIME_IAM_USER_NAME`: the existing IAM user whose credentials the Streamlit app uses. This is a separate identity from the GitHub deployment role; confirm it before bootstrap.

Repository secrets:

- `SERVERLESS_ACCESS_KEY` **or** `SERVERLESS_LICENSE_KEY`: Serverless Framework v4 authentication.
- `ALERT_EMAIL`: the administrator recipient, configured privately.

GitHub receives temporary AWS credentials using `id-token: write` and the project's OIDC role. Do not add long-lived AWS access keys to Actions for deployment. Deployment refuses an unexpected role and never infers the application's IAM user from the CI identity. Streamlit's existing runtime credentials stay in its private hosting settings.

Secrets and variables are scoped per repository or environment. Settings in another repository are not automatically available here. This workflow uses repository settings; an environment-scoped setup requires an explicit matching job `environment` and trust-policy subject change, reviewed together.

### One-time OIDC bootstrap prerequisite

[`bootstrap/github-deployment-role.yml`](bootstrap/github-deployment-role.yml) prepares a dedicated deployment role and a private, encrypted, versioned deployment-artifact bucket. It reuses the existing account GitHub OIDC provider, trusts only this repository's `main` branch (including GitHub's numeric-ID subject format), and scopes permissions to this monitoring stack, its resources, and attaching its monitoring policy to the explicitly selected runtime user. It cannot modify its own role or another project's deployment role. The bucket stores deployment artifacts, not travel plans.

Bootstrap parameters are grouped at the top of that independent template. Supply the existing provider ARN and the confirmed Streamlit IAM user ARN. Save the `DeploymentRoleArn` output as `AWS_DEPLOY_ROLE_ARN`; the pipeline derives the bucket name from the shared service/stage/region and assumed AWS account.

**Bootstrap has not been applied.** The current CI/CD-only requirement also applies to this first creation. A repository cannot assume a role that does not yet exist: an authorized account-bootstrap pipeline must apply this template, or the owner must explicitly approve a one-time bootstrap exception. Do not broaden a different project's OIDC trust policy to bypass this prerequisite. All monitoring deployments and subsequent updates run through this repository's workflow.

Serverless Framework v4 authentication remains separate from AWS OIDC. The API-metering repository's optional Serverless packaging job was skipped during the configuration review; its green test run is not evidence that a Serverless key is available here.

The pipeline packages the Serverless service, validates the generated CloudFormation template, deploys it, checks the stack and log retention, and verifies submitted/completed smoke events without calling Bedrock or Serper. It records a sanitized summary in the Actions job summary. Serverless may create/use its normal deployment artifact bucket; it is not used to store travel plans. Generated Serverless state and resolved parameters remain ignored and are not uploaded as GitHub artifacts.

Local deployment, removal, and rollback commands are blocked by a pipeline-only guard. Review changes in Git and publish them through the workflow; no local or console infrastructure creation is part of this deployment process.

## Email confirmation and verification

AWS sends a one-time SNS subscription-confirmation email to the configured recipient. The recipient must opt in with **Confirm subscription** before messages are delivered. This is a mailbox ownership check required by SNS, separate from infrastructure provisioning.

After confirmation, submit a trip through the live app and verify one submission email followed by one success or failure email with the same request ID. The pipeline also publishes clearly labeled infrastructure verification messages; these are not traveler requests and make no model/search calls. SNS delivery is asynchronous and standard-topic messages can occasionally be delivered more than once.

Use the dashboard named `vacation-planner-prod` and the log group's request ID to correlate a submission and its final result. No API Gateway, Lambda application backend, DynamoDB, or queue is introduced by this monitoring stack.
