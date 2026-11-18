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

Deployment secrets:

- `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`: the authorized current AWS deployment identity.
- `AWS_SESSION_TOKEN`: only when those credentials are temporary.
- `SERVERLESS_ACCESS_KEY` **or** `SERVERLESS_LICENSE_KEY`: Serverless Framework v4 authentication.
- `ALERT_EMAIL`: the administrator recipient, configured privately.

The optional repository variable `RUNTIME_IAM_USER_NAME` names the **existing IAM user whose AWS credentials Streamlit uses**. If it is omitted and the deployment credentials belong to an IAM user, that same user receives the scoped monitoring policy. When deployment credentials belong to a role, this variable is required. If Streamlit uses a different IAM user, explicitly set this variable before deployment so the policy is attached to the correct user.

The pipeline packages the Serverless service, validates the generated CloudFormation template, deploys it, checks the stack and log retention, and verifies submitted/completed smoke events without calling Bedrock or Serper. It records a sanitized summary in the Actions job summary. Serverless may create/use its normal deployment artifact bucket; it is not used to store travel plans. Generated Serverless state and resolved parameters remain ignored and are not uploaded as GitHub artifacts.

Local deployment, removal, and rollback commands are blocked by a pipeline-only guard. Review changes in Git and publish them through the workflow; no local or console infrastructure creation is part of this deployment process.

## Email confirmation and verification

AWS sends a one-time SNS subscription-confirmation email to the configured recipient. The recipient must opt in with **Confirm subscription** before messages are delivered. This is a mailbox ownership check required by SNS, separate from infrastructure provisioning.

After confirmation, submit a trip through the live app and verify one submission email followed by one success or failure email with the same request ID. The pipeline also publishes clearly labeled infrastructure verification messages; these are not traveler requests and make no model/search calls. SNS delivery is asynchronous and standard-topic messages can occasionally be delivered more than once.

Use the dashboard named `vacation-planner-prod` and the log group's request ID to correlate a submission and its final result. No API Gateway, Lambda application backend, DynamoDB, or queue is introduced by this monitoring stack.
