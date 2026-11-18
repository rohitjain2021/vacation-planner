"use strict";

class PipelineOnly {
  constructor(serverless) {
    this.hooks = {
      initialize: () => {
        const commands = serverless.processedInput.commands;
        if (!commands.some((command) => ["deploy", "remove", "rollback"].includes(command))) return;
        if (
          process.env.GITHUB_ACTIONS !== "true" ||
          process.env.GITHUB_REPOSITORY !== "rohitjain2021/vacation-planner" ||
          process.env.GITHUB_REF !== "refs/heads/main" ||
          !["push", "workflow_dispatch"].includes(process.env.GITHUB_EVENT_NAME)
        ) {
          throw new Error("Infrastructure mutations must run in this repository's GitHub Actions pipeline on main.");
        }
      },
    };
  }
}

module.exports = PipelineOnly;
