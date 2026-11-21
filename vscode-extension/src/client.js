// Talks to the game: `python -m azurath.session` speaks JSON, one object per line.
// No VS Code APIs in here, so it can be tested with plain `node --test`.
"use strict";

const { spawn } = require("node:child_process");
const readline = require("node:readline");

class GameClient {
  /**
   * @param {string[]} command  e.g. ["python", "-m", "azurath.session"]
   * @param {{cwd?: string, args?: string[], env?: object}} options
   */
  constructor(command, options = {}) {
    const [program, ...rest] = command;
    this.nextId = 1;
    this.pending = new Map();
    this.stderr = "";
    this.exited = false;
    this.proc = spawn(program, [...rest, ...(options.args || [])], {
      cwd: options.cwd,
      env: { ...process.env, PYTHONIOENCODING: "utf-8", ...(options.env || {}) },
      stdio: ["pipe", "pipe", "pipe"],
    });
    this.ready = new Promise((resolve, reject) => {
      this._readyResolve = resolve;
      this._readyReject = reject;
    });
    readline.createInterface({ input: this.proc.stdout }).on("line", (line) => this._onLine(line));
    this.proc.stderr.on("data", (chunk) => {
      this.stderr = (this.stderr + chunk.toString()).slice(-4000);
    });
    this.proc.on("error", (err) => this._fail(err));
    this.proc.on("exit", (code) => {
      this.exited = true;
      this._fail(new Error(`the game stopped (exit code ${code}).\n${this.stderr}`));
    });
  }

  _onLine(line) {
    let message;
    try {
      message = JSON.parse(line);
    } catch {
      return; // not ours (a stray print); ignore it
    }
    if (message.type === "ready") {
      this._readyResolve(message);
      return;
    }
    const waiter = this.pending.get(message.id);
    if (!waiter) return;
    this.pending.delete(message.id);
    if (message.type === "error") waiter.reject(new Error(message.error));
    else waiter.resolve(message);
  }

  _fail(err) {
    this._readyReject(err);
    for (const waiter of this.pending.values()) waiter.reject(err);
    this.pending.clear();
  }

  /** Send a request ({type, line?, answers?}) and wait for its reply. */
  async request(message) {
    await this.ready;
    if (this.exited) throw new Error("the game isn't running");
    const id = this.nextId++;
    const reply = new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
    this.proc.stdin.write(JSON.stringify({ id, ...message }) + "\n");
    return reply;
  }

  start(answers = []) {
    return this.request({ type: "start", answers });
  }

  run(line, answers = []) {
    return this.request({ type: "run", line, answers });
  }

  snapshot() {
    return this.request({ type: "snapshot" });
  }

  dispose() {
    if (!this.exited) this.proc.kill();
  }
}

module.exports = { GameClient };
