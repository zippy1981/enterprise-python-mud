// Turn a check's failed criteria into editor problems (squiggles) on the right line.
"use strict";

const FILE = String.raw`([\w./\\-]+\.(?:py|toml|ya?ml|json|md|txt|cfg|ini))`;
// "hello.py line 3", "SyntaxError in hello.py line 3: ...", "`mood.py` line 7"
const FILE_LINE = new RegExp(String.raw`\x60?${FILE}\x60?,?\s+(?:on\s+)?line\s+(\d+)`, "gi");
// a file named anywhere in backticks, for "line N" without a file next to it
const BACKTICK_FILE = new RegExp(String.raw`\x60${FILE}\x60`, "i");
const LONE_LINE = /\bline\s+(\d+)\b/gi;

/**
 * @param {{description: string, ok: boolean, optional: boolean, detail: string|null}[]} criteria
 * @returns {{file: string, line: number, message: string, severity: "error"|"warning"}[]}
 *   ``line`` is 1-based, as the game reports it; ``file`` is relative to the workspace.
 */
function problemsFrom(criteria) {
  const found = [];
  const seen = new Set();
  for (const item of criteria || []) {
    if (item.ok) continue;
    const severity = item.optional ? "warning" : "error";
    const text = `${item.description}\n${item.detail || ""}`;
    const add = (file, line, message) => {
      const key = `${file}:${line}:${message}`;
      if (seen.has(key)) return;
      seen.add(key);
      found.push({ file: file.replace(/\\/g, "/"), line: Number(line), message, severity });
    };
    let matched = false;
    for (const raw of (item.detail || "").split("\n")) {
      const line = raw.trim();
      if (!line) continue;
      FILE_LINE.lastIndex = 0;
      let m;
      while ((m = FILE_LINE.exec(line))) {
        matched = true;
        add(m[1], m[2], `${stripTicks(item.description)}: ${line}`);
      }
    }
    if (matched) continue;
    const named = BACKTICK_FILE.exec(text);
    if (!named) continue;
    LONE_LINE.lastIndex = 0;
    let m;
    let any = false;
    while ((m = LONE_LINE.exec(item.detail || ""))) {
      any = true;
      add(named[1], m[1], `${stripTicks(item.description)}: ${firstLine(item.detail)}`);
    }
    if (!any) add(named[1], 1, `${stripTicks(item.description)}${item.detail ? `: ${firstLine(item.detail)}` : ""}`);
  }
  return found;
}

function stripTicks(text) {
  return text.replace(/\x60/g, "");
}

function firstLine(text) {
  return (text || "").trim().split("\n")[0];
}

module.exports = { problemsFrom };
