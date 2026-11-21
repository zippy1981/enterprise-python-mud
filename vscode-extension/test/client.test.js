"use strict";
// Starts the real game (`python -m azurath.session`) and plays a few commands.
// AZURATH_SESSION_CMD is a JSON array; the default suits a checkout of this repo.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { GameClient } = require("../src/client");

const repo = path.resolve(__dirname, "..", "..");
const command = JSON.parse(
  process.env.AZURATH_SESSION_CMD || '["uv", "run", "--project", ' + JSON.stringify(repo) + ', "python", "-m", "azurath.session"]'
);

test("the client plays the game over JSON lines", { timeout: 120000 }, async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "azurath-vscode-"));
  const gitconfig = path.join(tmp, "gitconfig");
  fs.writeFileSync(gitconfig, "[user]\n\tname = Ada Lovelace\n\temail = ada@example.com\n");
  const client = new GameClient(command, {
    cwd: tmp,
    args: ["--workspace", path.join(tmp, "proj"), "--dungeon", "pythonwood", "--width", "60"],
    env: { GIT_CONFIG_GLOBAL: gitconfig, GIT_CONFIG_NOSYSTEM: "1" },
  });
  try {
    const ready = await client.ready;
    assert.equal(ready.protocol, 1);

    const start = await client.start();
    assert.equal(start.snapshot.dungeon, "pythonwood");
    assert.ok(start.result.html.includes(start.snapshot.room_name));

    await client.run("scaffold");
    const quest = start.snapshot.quest;
    assert.ok(quest);

    const check = await client.run("check");
    assert.equal(check.snapshot.check_passed, false);
    assert.ok(check.snapshot.last_check.length > 0);

    const edit = await client.run("edit " + Object.keys({ "hello.py": 1 })[0]);
    assert.deepEqual(edit.result.opened, ["hello.py"]);

    await assert.rejects(client.request({ type: "nonsense" }), /unknown message type/);
  } finally {
    client.dispose();
  }
});
