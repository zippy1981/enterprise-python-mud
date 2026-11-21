// The Azurath VS Code extension: the game in a side panel, next to your code.
"use strict";

const path = require("node:path");
const crypto = require("node:crypto");
const vscode = require("vscode");
const { GameClient } = require("./client");
const { problemsFrom } = require("./diagnostics");

/** @type {GameProvider | undefined} */
let provider;

function activate(context) {
  provider = new GameProvider(context);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider("azurath.game", provider, {
      webviewOptions: { retainContextWhenHidden: true },
    }),
    vscode.commands.registerCommand("azurath.check", () => provider.run("check")),
    vscode.commands.registerCommand("azurath.hint", () => provider.run("hint")),
    vscode.commands.registerCommand("azurath.run", async () => {
      const line = await vscode.window.showInputBox({ prompt: "Game command", placeHolder: "look" });
      if (line) provider.run(line);
    }),
    vscode.commands.registerCommand("azurath.restart", () => provider.restart()),
    vscode.workspace.onDidSaveTextDocument((doc) => provider.onSave(doc)),
    provider
  );
}

function deactivate() {
  provider?.dispose();
}

class GameProvider {
  constructor(context) {
    this.context = context;
    this.view = undefined;
    this.client = undefined;
    this.busy = false;
    this.diagnostics = vscode.languages.createDiagnosticCollection("azurath");
    this.status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
    this.status.command = "azurath.check";
    this.status.text = "$(shield) Azurath";
    this.status.tooltip = "Check your quest (Ctrl+Alt+C)";
    this.status.show();
    this.saveTimer = undefined;
  }

  // --- the panel -------------------------------------------------------------------

  resolveWebviewView(view) {
    this.view = view;
    const media = vscode.Uri.joinPath(this.context.extensionUri, "media");
    view.webview.options = { enableScripts: true, localResourceRoots: [media] };
    view.webview.html = this.html(view.webview, media);
    view.webview.onDidReceiveMessage((msg) => {
      if (msg.type === "run") this.run(msg.line);
      else if (msg.type === "ready") this.ensureStarted();
    });
  }

  html(webview, media) {
    const nonce = crypto.randomBytes(16).toString("base64");
    const css = webview.asWebviewUri(vscode.Uri.joinPath(media, "panel.css"));
    const js = webview.asWebviewUri(vscode.Uri.joinPath(media, "panel.js"));
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="${css}">
<title>Azurath</title>
</head>
<body>
  <header id="status">Starting the game…</header>
  <section id="room"></section>
  <section id="quest"></section>
  <nav id="exits"></nav>
  <nav id="actions">
    <button data-run="look">Look</button><button data-run="read">Read</button>
    <button data-run="talk">Talk</button><button data-run="hint">Hint</button>
    <button data-run="scaffold">Scaffold</button><button data-run="check" class="primary">Check</button>
  </nav>
  <details id="map-box"><summary>Map</summary><ol id="map"></ol></details>
  <section id="log" aria-live="polite"></section>
  <form id="prompt"><input id="line" placeholder="Type a command (help, look, read…)" autocomplete="off"></form>
  <script nonce="${nonce}" src="${js}"></script>
</body>
</html>`;
  }

  post(message) {
    this.view?.webview.postMessage(message);
  }

  // --- the game ----------------------------------------------------------------------

  folder() {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  }

  async ensureStarted() {
    if (this.client) return;
    const folder = this.folder();
    if (!folder) {
      this.post({ type: "fatal", text: "Open your project folder first (File → Open Folder)." });
      return;
    }
    const config = vscode.workspace.getConfiguration("azurath");
    const args = ["--workspace", folder];
    if (config.get("dungeon")) args.push("--dungeon", config.get("dungeon"));
    args.push("--width", "56"); // Rich draws panels this wide; the log scrolls sideways if needed
    this.client = new GameClient(config.get("command"), { cwd: folder, args });
    try {
      await this.client.ready;
    } catch (err) {
      this.client = undefined;
      this.post({
        type: "fatal",
        text:
          `Couldn't start the game: ${err.message}\n` +
          "Check the azurath.command setting (it must run `python -m azurath.session`).",
      });
      return;
    }
    await this.send({ type: "start" }, "start");
  }

  async run(line) {
    if (!this.client) await this.ensureStarted();
    if (!this.client || this.busy) return;
    await this.send({ type: "run", line }, line);
  }

  async send(request, label) {
    this.busy = true;
    this.post({ type: "busy", line: label });
    try {
      const reply = await this.client.request(request);
      this.show(reply);
    } catch (err) {
      this.post({ type: "fatal", text: err.message });
      this.client?.dispose();
      this.client = undefined;
    } finally {
      this.busy = false;
    }
  }

  show(reply) {
    const { result, snapshot } = reply;
    this.post({ type: "result", result, snapshot });
    for (const rel of result.opened || []) this.open(snapshot.workspace, rel);
    if (snapshot.last_check) this.markProblems(snapshot);
    const done = snapshot.map.filter((r) => r.status === "complete").length;
    this.status.text = `$(shield) ${snapshot.quest_done ? "$(pass-filled)" : "$(circle-large-outline)"} ${snapshot.room_name} · ${done}/${snapshot.map.length}`;
    if (result.quit) {
      this.client?.dispose();
      this.client = undefined;
    }
  }

  async open(workspace, rel) {
    const uri = rel ? vscode.Uri.file(path.join(workspace, rel)) : vscode.Uri.file(workspace);
    if (!rel) {
      vscode.commands.executeCommand("revealInExplorer", uri);
      return;
    }
    const doc = await vscode.workspace.openTextDocument(uri);
    await vscode.window.showTextDocument(doc, { viewColumn: vscode.ViewColumn.One, preview: false });
  }

  markProblems(snapshot) {
    this.diagnostics.clear();
    const byFile = new Map();
    for (const p of problemsFrom(snapshot.last_check)) {
      const uri = vscode.Uri.file(path.join(snapshot.workspace, p.file));
      const line = Math.max(0, p.line - 1);
      const diag = new vscode.Diagnostic(
        new vscode.Range(line, 0, line, Number.MAX_SAFE_INTEGER),
        p.message,
        p.severity === "error" ? vscode.DiagnosticSeverity.Error : vscode.DiagnosticSeverity.Warning
      );
      diag.source = "Azurath";
      const list = byFile.get(uri.toString()) || [uri, []];
      list[1].push(diag);
      byFile.set(uri.toString(), list);
    }
    for (const [uri, diags] of byFile.values()) this.diagnostics.set(uri, diags);
  }

  onSave(doc) {
    const folder = this.folder();
    const config = vscode.workspace.getConfiguration("azurath");
    if (!this.client || !folder || !config.get("checkOnSave")) return;
    if (!doc.uri.fsPath.startsWith(folder)) return;
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => this.run("check"), 400); // one check for "Save All"
  }

  restart() {
    this.client?.dispose();
    this.client = undefined;
    this.diagnostics.clear();
    this.post({ type: "clear" });
    this.ensureStarted();
  }

  dispose() {
    this.client?.dispose();
    this.diagnostics.dispose();
    this.status.dispose();
  }
}

module.exports = { activate, deactivate };
