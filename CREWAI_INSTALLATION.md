# CrewAI Installation

Install uv and the CrewAI CLI before setting up the Vacation Planner app. You need Python and pip available in your terminal.

## 1. Install uv

```shell
pip install uv
```

## 2. Check the uv version

```shell
uv --version
```

## 3. Install CrewAI

```shell
uv tool install crewai
```

## 4. List installed tools

```shell
uv tool list
```

Confirm that CrewAI appears in the output.

## 5. Update your shell

```shell
uv tool update-shell
```

This adds the tool executable directory to your shell's PATH. Close and reopen your terminal afterward so it picks up the change.

## 6. Create the Vacation Planner crew

Run the following command from the directory where you want to create the project:

```shell
crewai create crew vacation_planner --classic
```

### Use Amazon Bedrock Nova Pro

CrewAI 1.15.41 includes the `bedrock` provider and the model `bedrock/us.amazon.nova-pro-v1:0`. If you cannot find it in the interactive menu, skip provider selection and configure the generated project manually:

```shell
crewai create crew vacation_planner --classic --skip-provider
cd vacation_planner
uv add "crewai[tools,bedrock]"
```

The project in this repository has already been created and configured with Bedrock support. Do not create it again over the existing directory.

Open `vacation_planner/.env` from the repository root and fill in your AWS credentials locally:

```dotenv
MODEL=bedrock/us.amazon.nova-pro-v1:0
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
```

For temporary AWS credentials, also set `AWS_SESSION_TOKEN`. Leave it blank for long-lived access keys. Keep credentials in the ignored `.env` file; `.env.example` contains the shareable template. Do not paste credentials into chat or commit them.

Both generated agents explicitly use the Bedrock LLM in `src/vacation_planner/crew.py`. The example uses the US cross-region Nova Pro inference profile, with `us-east-1` as the source region. Use a supported region/profile for your account if you need another geography.

From the repository root, install dependencies and run the generated starter crew:

```powershell
cd vacation_planner
crewai install
crewai run
```

This runs the generated research/report starter, which still needs Vacation Planner agents and tasks. Bedrock calls incur AWS usage charges.

If you receive `AccessDeniedException`, check that your AWS identity can invoke Nova Pro through Bedrock, including the cross-region inference profile and its destination models. A region/profile mismatch can cause `ValidationException`; invalid or expired credentials require correcting the keys or session token in `.env`.

## References

- [CrewAI installation documentation](https://docs.crewai.com/en/installation)
- [uv installation documentation](https://docs.astral.sh/uv/getting-started/installation/)
- [uv tool management documentation](https://docs.astral.sh/uv/concepts/tools/)
- [CrewAI LLM connections](https://docs.crewai.com/en/learn/llm-connections)
- [AWS Nova Pro model IDs and supported regions](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-pro.html)

[Back to README](README.md)
