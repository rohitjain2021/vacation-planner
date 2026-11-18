# VacationPlanner Crew

Welcome to the VacationPlanner Crew project, powered by [crewAI](https://crewai.com). This template is designed to help you set up a multi-agent AI system with ease, leveraging the powerful and flexible framework provided by crewAI. Our goal is to enable your agents to collaborate effectively on complex tasks, maximizing their collective intelligence and capabilities.

## Installation

Ensure you have Python >=3.10 <3.14 installed on your system. This project uses [UV](https://docs.astral.sh/uv/) for dependency management and package handling, offering a seamless setup and execution experience.

First, if you haven't already, install uv:

```bash
pip install uv
```

Next, navigate to your project directory and install the dependencies:

(Optional) Lock the dependencies and install them by using the CLI command:
```bash
crewai install
```
### Customizing

Add your `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` into the ignored `.env` file. For temporary credentials, also set `AWS_SESSION_TOKEN`. The project uses Amazon Bedrock Nova Pro with `MODEL=bedrock/us.amazon.nova-pro-v1:0` and `AWS_DEFAULT_REGION=us-east-1`.

See the [installation and Bedrock setup guide](../CREWAI_INSTALLATION.md#use-amazon-bedrock-nova-pro) for details. Both agents are configured for Bedrock in `src/vacation_planner/crew.py`.

- Modify `src/vacation_planner/config/agents.yaml` to define your agents
- Modify `src/vacation_planner/config/tasks.yaml` to define your tasks
- Modify `src/vacation_planner/crew.py` to add your own logic, tools and specific args
- Modify `src/vacation_planner/main.py` to add custom inputs for your agents and tasks

## Running the Project

To kickstart your crew of AI agents and begin task execution, run this from the root folder of your project:

```bash
$ crewai run
```

This command initializes the vacation_planner Crew, assembling the agents and assigning them tasks as defined in your configuration.

This example, unmodified, will run the create a `report.md` file with the output of a research on LLMs in the root folder.

## Understanding Your Crew

The vacation_planner Crew is composed of multiple AI agents, each with unique roles, goals, and tools. These agents collaborate on a series of tasks, defined in `config/tasks.yaml`, leveraging their collective skills to achieve complex objectives. The `config/agents.yaml` file outlines the capabilities and configurations of each agent in your crew.

## Support

For support, questions, or feedback regarding the VacationPlanner Crew or crewAI.
- Visit our [documentation](https://docs.crewai.com)
- Reach out to us through our [GitHub repository](https://github.com/joaomdmoura/crewai)
- [Join our Discord](https://discord.com/invite/X4JWnZnxPb)
- [Chat with our docs](https://chatg.pt/DWjSBZn)

Let's create wonders together with the power and simplicity of crewAI.

## Local credentials

Keep real credentials in `vacation_planner/.env` (this directory), which Git ignores. Commit only `.env.example` with empty values. The crew loads this project's `.env` automatically without overwriting environment variables already set by your shell or deployment.

Set `SERPER_API_KEY` in your local `.env` for web search. Its spelling must be uppercase. AWS Bedrock uses the standard AWS credential chain: a configured local AWS profile, temporary credentials, or an IAM role in deployment. Never put AWS keys, session tokens, or other API keys in Python, YAML, reports, or committed configuration.

Before committing, run `git status --short` and `git diff --cached --name-only` from the repository root. `.env` and credential files must not appear among staged files. Git ignore rules do not remove files already tracked by Git.

If a real credential is ever pushed or shared, revoke/rotate it with its provider first. Removing it from the latest code does not remove it from Git history. Supply deployment credentials through the deployment platform's secret settings rather than committing `.env`.
