// Runs inside the webview. Draws what the extension sends; sends back commands.
(function () {
  "use strict";
  const vscode = acquireVsCodeApi();
  const $ = (id) => document.getElementById(id);
  const log = $("log");

  function run(line) {
    vscode.postMessage({ type: "run", line });
  }

  function el(tag, attrs = {}, text = "") {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (text) node.textContent = text;
    return node;
  }

  document.body.addEventListener("click", (event) => {
    const target = event.target.closest("[data-run]");
    if (target && !target.disabled) run(target.dataset.run);
  });

  $("prompt").addEventListener("submit", (event) => {
    event.preventDefault();
    const line = $("line").value.trim();
    $("line").value = "";
    if (line) run(line);
  });

  function drawSnapshot(s) {
    const done = s.map.filter((r) => r.status === "complete").length;
    $("status").textContent = `${s.player} the ${s.title} · ${s.xp} XP · ${done}/${s.map.length} rooms`;

    const room = $("room");
    room.replaceChildren(el("h2", {}, s.room_name), el("p", { class: "zone" }, s.zone));
    if (s.npc) room.append(el("p", {}, `${s.npc} is here.`));
    if (s.pages.length) room.append(el("p", { class: "dim" }, `Tome: ${s.pages_read}/${s.pages.length} pages read`));

    const quest = $("quest");
    quest.replaceChildren();
    if (s.quest) {
      quest.append(el("h3", {}, `${s.quest_done ? "✔" : "◇"} ${s.quest}`));
      if (s.last_check) {
        const list = el("ul", { class: "checklist" });
        for (const c of s.last_check) {
          const mark = c.ok ? "✔" : c.optional ? "○" : "✘";
          const cls = c.ok ? "ok" : c.optional ? "maybe" : "bad";
          const item = el("li", { class: cls }, `${mark} ${c.description.replace(/`/g, "")}`);
          if (!c.ok && c.detail) item.append(el("pre", {}, c.detail));
          list.append(item);
        }
        quest.append(list);
      }
    }

    const exits = $("exits");
    exits.replaceChildren();
    for (const e of s.exits) {
      const b = el("button", { "data-run": e.direction, title: e.name }, `${e.direction} → ${e.name}${e.locked ? " 🔒" : ""}`);
      b.disabled = e.locked;
      exits.append(b);
    }

    const map = $("map");
    map.replaceChildren();
    for (const r of s.map) {
      const icon = r.here ? "▶" : { complete: "✔", visited: "◐", undiscovered: "🔒" }[r.status];
      const li = el("li", { class: r.status + (r.here ? " here" : "") }, `${icon} ${r.name}`);
      if (r.status !== "undiscovered" && !r.here) {
        li.dataset.run = `goto ${r.id}`;
        li.classList.add("link");
      }
      map.append(li);
    }
  }

  function append(result) {
    const entry = el("div", { class: "entry" });
    if (result.command !== "start") entry.append(el("div", { class: "cmd" }, `› ${result.command}`));
    const out = el("pre", { class: "out" });
    out.innerHTML = result.html; // Rich's HTML export: text is escaped, styles are inline
    entry.append(out);
    log.append(entry);
    entry.scrollIntoView({ block: "start" });
  }

  window.addEventListener("message", (event) => {
    const msg = event.data;
    if (msg.type === "result") {
      document.body.classList.remove("busy");
      append(msg.result);
      drawSnapshot(msg.snapshot);
    } else if (msg.type === "busy") {
      document.body.classList.add("busy");
    } else if (msg.type === "fatal") {
      document.body.classList.remove("busy");
      log.append(el("pre", { class: "fatal" }, msg.text));
    } else if (msg.type === "clear") {
      log.replaceChildren();
    }
  });

  vscode.postMessage({ type: "ready" });
})();
