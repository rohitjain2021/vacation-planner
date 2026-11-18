"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const PipelineOnly = require("./pipeline-only.cjs");

function initialize(command) {
  return new PipelineOnly({ processedInput: { commands: [command] } }).hooks.initialize();
}

test("deployment, removal, and rollback are blocked locally", () => {
  const previous = process.env.GITHUB_ACTIONS;
  process.env.GITHUB_ACTIONS = "false";
  try {
    for (const command of ["deploy", "remove", "rollback"]) {
      assert.throws(() => initialize(command), /GitHub Actions/);
    }
  } finally {
    if (previous === undefined) delete process.env.GITHUB_ACTIONS;
    else process.env.GITHUB_ACTIONS = previous;
  }
});

test("package validation is allowed without deployment credentials", () => {
  assert.doesNotThrow(() => initialize("package"));
});
