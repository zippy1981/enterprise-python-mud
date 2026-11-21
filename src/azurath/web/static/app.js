// Azurath in the browser: draws the map and the room, and sends commands to the game.
(function () {
  "use strict";

  const token = new URLSearchParams(location.hash.slice(1)).get("t") || sessionStorageGet("azurath-token");
  if (token) sessionStorageSet("azurath-token", token);

  const $ = (id) => document.getElementById(id);
  let snapshot = null;
  let layout = {};
  let currentFile = null;
  let dirty = false;

  function sessionStorageGet(key) {
    try { return sessionStorage.getItem(key); } catch { return null; }
  }
  function sessionStorageSet(key, value) {
    try { sessionStorage.setItem(key, value); } catch { /* private window: fine */ }
  }

  // --- talking to the game ------------------------------------------------------------

  async function api(method, path, body) {
    const response = await fetch(path, {
      method,
      headers: { "Content-Type": "application/json", "X-Azurath-Token": token || "" },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || response.statusText);
    return data;
  }

  async function run(line, where) {
    document.body.classList.add("busy");
    try {
      const data = await api("POST", "/api/run", { line });
      const before = snapshot;
      update(data);
      showOutput(data.result.html, where || outputFor(line));
      if (data.result.opened.length) openFile(data.result.opened[0]);
      celebrate(before, data.snapshot);
      if (data.result.quit) showOutput("<b>The game has stopped. Close this tab.</b>", "story-out");
    } catch (err) {
      showOutput(escapeHtml(err.message), where || "story-out");
    } finally {
      document.body.classList.remove("busy");
    }
  }

  function outputFor(line) {
    const verb = line.split(" ")[0];
    if (["read", "next", "pages"].includes(verb)) { switchTab("lesson"); return "lesson-out"; }
    if (["check", "hint", "scaffold", "quest", "solution"].includes(verb)) {
      if (activeTab() !== "code") switchTab("quest");
      return activeTab() === "code" ? "code-out" : "quest-out";
    }
    if (["python", "pytest", "sh"].includes(verb) || line.startsWith("!")) return "code-out";
    switchTab("story");
    return "story-out";
  }

  function showOutput(html, id) {
    const box = $(id);
    const pre = document.createElement("pre");
    pre.innerHTML = html; // Rich's HTML export: text escaped, styles inline
    if (id === "quest-out") {
      // The checklist above already shows the result; keep the game's own words folded away.
      const details = document.createElement("details");
      details.className = "raw";
      details.innerHTML = "<summary>What the game said</summary>";
      details.append(pre);
      box.replaceChildren(details);
    } else {
      box.replaceChildren(pre);
    }
  }

  // --- drawing ------------------------------------------------------------------------

  function update(data) {
    snapshot = data.snapshot;
    layout = data.layout || layout;
    const s = snapshot;
    $("dungeon-name").textContent = s.dungeon_name;
    const done = s.map.filter((r) => r.status === "complete").length;
    $("player").textContent = `${s.player} the ${s.title}`;
    $("xp-text").textContent = `${s.xp} XP · ${done}/${s.map.length} rooms`;
    $("xp-bar").style.width = `${Math.round((100 * done) / s.map.length)}%`;
    $("room-name").textContent = s.room_name;
    $("room-zone").textContent = s.zone;
    $("description").innerHTML = markdown(s.description);
    $("npc").innerHTML = s.npc
      ? `<button data-run="talk">💬 Talk to ${escapeHtml(s.npc)}</button>`
      : "";
    drawExits(s);
    drawPages(s);
    drawQuest(s);
    drawMap(s);
  }

  function drawExits(s) {
    const box = $("exits");
    box.replaceChildren();
    for (const e of s.exits) {
      const b = button(`${arrow(e.direction)} ${e.name}${e.locked ? " 🔒" : ""}`, e.direction);
      b.disabled = e.locked;
      b.title = e.locked ? "Finish this room's quest to open the way" : `Go ${e.direction}`;
      box.append(b);
    }
  }

  function drawPages(s) {
    const box = $("pages");
    box.replaceChildren();
    s.pages.forEach((title, i) => {
      const b = button(`${i < s.pages_read ? "✔" : "📖"} ${title}`, `read ${i + 1}`);
      box.append(b);
    });
    if (!s.pages.length) box.textContent = "There's no tome in this room.";
  }

  function drawQuest(s) {
    $("quest-title").textContent = s.quest ? `${s.quest_done ? "✔ " : ""}${s.quest}` : "No quest here";
    $("quest-brief").innerHTML = markdown(s.quest_brief || "");
    const list = $("checklist");
    list.replaceChildren();
    for (const c of s.last_check || []) {
      const li = document.createElement("li");
      li.className = c.ok ? "ok" : c.optional ? "maybe" : "bad";
      li.innerHTML = inline(escapeHtml(c.description));
      if (!c.ok && c.detail) {
        const d = document.createElement("span");
        d.className = "detail";
        d.textContent = c.detail;
        li.append(d);
      }
      list.append(li);
    }
  }

  const SVG = "http://www.w3.org/2000/svg";
  function svg(tag, attrs, parent) {
    const node = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.append(node);
    return node;
  }

  function drawMap(s) {
    const map = $("map");
    map.replaceChildren();
    const dx = 150, dy = 92, pad = 60;
    const xs = Object.values(layout).map((p) => p[0]);
    const ys = Object.values(layout).map((p) => p[1]);
    const w = (Math.max(...xs) + 1) * dx + pad, h = (Math.max(...ys) + 1) * dy + pad / 2;
    map.setAttribute("viewBox", `0 0 ${w} ${h}`);
    const at = (id) => [layout[id][0] * dx + pad, layout[id][1] * dy + pad / 1.4];
    const byId = Object.fromEntries(s.map.map((r) => [r.id, r]));
    const drawn = new Set();
    for (const room of s.map) {
      for (const target of Object.values(room.exits)) {
        const key = [room.id, target].sort().join("|");
        if (drawn.has(key) || !layout[target]) continue;
        drawn.add(key);
        const [x1, y1] = at(room.id), [x2, y2] = at(target);
        const open = byId[target] && byId[target].status !== "undiscovered" && room.status !== "undiscovered";
        svg("line", { x1, y1, x2, y2, class: `edge${open ? " open" : ""}` }, map);
      }
    }
    for (const room of s.map) {
      const [x, y] = at(room.id);
      const reachable = room.status !== "undiscovered" && !room.here;
      const g = svg("g", { class: `node ${room.status}${room.here ? " here" : ""}${reachable ? " clickable" : ""}`, tabindex: reachable ? 0 : -1 }, map);
      if (room.here) svg("circle", { cx: x, cy: y, r: 18, class: "ring" }, g);
      svg("circle", { cx: x, cy: y, r: room.guided ? 13 : 18 }, g);
      const icon = svg("text", { x, y, class: "icon" }, g);
      icon.textContent = room.status === "complete" ? "✔" : room.status === "undiscovered" ? "🔒" : room.guided ? "" : "★";
      const label = svg("text", { x, y: y + 34 }, g);
      label.textContent = room.name.length > 22 ? room.name.slice(0, 21) + "…" : room.name;
      const title = svg("title", {}, g);
      title.textContent = `${room.name} · ${room.zone} · ${room.status}`;
      if (reachable) {
        g.addEventListener("click", () => run(`goto ${room.id}`));
        g.addEventListener("keydown", (e) => { if (e.key === "Enter") run(`goto ${room.id}`); });
      }
    }
  }

  function celebrate(before, after) {
    if (!before || !after || before.xp === after.xp) return;
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = `🎉 Quest complete! +${after.xp - before.xp} XP`;
    document.body.append(toast);
    setTimeout(() => toast.remove(), 3500);
  }

  // --- code tab -------------------------------------------------------------------------

  async function refreshFiles(select) {
    const { files } = await api("GET", "/api/files");
    const box = $("file");
    const wanted = select || currentFile || files[0];
    const scaffold = snapshot && snapshot.quest ? [] : [];
    box.replaceChildren();
    for (const f of [...new Set([...files, ...scaffold, ...(wanted ? [wanted] : [])])].sort()) {
      const o = document.createElement("option");
      o.value = o.textContent = f;
      box.append(o);
    }
    if (wanted) box.value = wanted;
  }

  async function openFile(path) {
    if (dirty && currentFile && !confirm(`Discard your unsaved changes to ${currentFile}?`)) return;
    switchTab("code");
    await refreshFiles(path);
    const data = await api("GET", `/api/file?path=${encodeURIComponent(path)}`);
    currentFile = path;
    $("editor").value = data.content;
    setDirty(false);
    drawSteps(data.steps);
  }

  async function save() {
    if (!currentFile) return;
    const data = await api("PUT", "/api/file", { path: currentFile, content: $("editor").value });
    setDirty(false);
    drawSteps(data.steps);
    $("save-state").textContent = "saved";
  }

  function setDirty(value) {
    dirty = value;
    $("save-state").textContent = value ? "unsaved changes" : "";
  }

  function drawSteps(steps) {
    const box = $("steps");
    box.replaceChildren();
    if (!steps) return;
    const intro = document.createElement("p");
    intro.className = "dim";
    intro.textContent = "Pick the right card for each STEP. It switches that line on in your file.";
    box.append(intro);
    for (const step of steps) {
      const div = document.createElement("div");
      div.className = "step";
      const h = document.createElement("h3");
      h.textContent = `STEP ${step.label}: ${step.prompt}`;
      div.append(h);
      const cards = document.createElement("div");
      cards.className = "cards";
      step.choices.forEach((choice, index) => {
        const b = document.createElement("button");
        b.className = `card${choice.chosen ? " chosen" : ""}`;
        b.textContent = choice.code.replace(/^\s+/gm, (m) => m); // keep the indentation: it matters!
        b.addEventListener("click", () => choose(step.label, index));
        cards.append(b);
      });
      div.append(cards);
      box.append(div);
    }
  }

  async function choose(step, index) {
    if (dirty) await save();
    try {
      const data = await api("POST", "/api/choose", { path: currentFile, step, index });
      $("editor").value = data.content;
      setDirty(false);
      drawSteps(data.steps);
    } catch (err) {
      showOutput(escapeHtml(err.message), "code-out");
    }
  }

  // --- little helpers ------------------------------------------------------------------

  function button(label, line) {
    const b = document.createElement("button");
    b.textContent = label;
    b.dataset.run = line;
    return b;
  }

  function arrow(direction) {
    return { north: "⬆", south: "⬇", east: "➡", west: "⬅", up: "⤴", down: "⤵", northeast: "↗", northwest: "↖", southeast: "↘", southwest: "↙" }[direction] || "•";
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  }

  function inline(html) {
    return html
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
  }

  // Just enough Markdown for room text: paragraphs, lists, tables, code blocks.
  function markdown(source) {
    const lines = escapeHtml(source || "").split("\n");
    const out = [];
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (line.startsWith("```")) {
        const code = [];
        for (i++; i < lines.length && !lines[i].startsWith("```"); i++) code.push(lines[i]);
        out.push(`<pre><code>${code.join("\n")}</code></pre>`);
        i++;
      } else if (line.trim().startsWith("|")) {
        const rows = [];
        for (; i < lines.length && lines[i].trim().startsWith("|"); i++) rows.push(lines[i].trim());
        const cells = (r) => r.replace(/^\||\|$/g, "").split("|").map((c) => inline(c.trim()));
        const body = rows.filter((r) => !/^\|[\s:|-]+\|$/.test(r));
        out.push(`<table>${body.map((r, n) => `<tr>${cells(r).map((c) => (n ? `<td>${c}</td>` : `<th>${c}</th>`)).join("")}</tr>`).join("")}</table>`);
      } else if (/^\s*([*-]|\d+\.)\s/.test(line)) {
        const items = [];
        for (; i < lines.length && /^\s*([*-]|\d+\.)\s/.test(lines[i]); i++) items.push(`<li>${inline(lines[i].replace(/^\s*([*-]|\d+\.)\s/, ""))}</li>`);
        out.push(`<ul>${items.join("")}</ul>`);
      } else if (!line.trim()) {
        i++;
      } else {
        const para = [];
        for (; i < lines.length && lines[i].trim() && !/^(```|\s*\||\s*([*-]|\d+\.)\s)/.test(lines[i]); i++) para.push(lines[i]);
        out.push(`<p>${inline(para.join(" "))}</p>`);
      }
    }
    return out.join("");
  }

  function switchTab(name) {
    for (const b of document.querySelectorAll(".tabs button")) b.classList.toggle("active", b.dataset.tab === name);
    for (const t of document.querySelectorAll(".tab")) t.hidden = t.id !== `tab-${name}`;
    if (name === "code" && !currentFile) refreshFiles().then(() => $("file").value && openFile($("file").value));
  }

  function activeTab() {
    const b = document.querySelector(".tabs button.active");
    return b ? b.dataset.tab : "story";
  }

  // --- wiring ------------------------------------------------------------------------

  document.addEventListener("click", (event) => {
    const tab = event.target.closest(".tabs button");
    if (tab) return switchTab(tab.dataset.tab);
    const target = event.target.closest("[data-run]");
    if (target && !target.disabled) run(target.dataset.run);
  });
  $("command").addEventListener("submit", (event) => {
    event.preventDefault();
    const line = $("line").value.trim();
    $("line").value = "";
    if (line) run(line);
  });
  $("file").addEventListener("change", () => openFile($("file").value));
  $("save").addEventListener("click", save);
  $("run-file").addEventListener("click", async () => {
    if (!currentFile) return;
    if (dirty) await save();
    run(`python ${currentFile}`, "code-out");
  });
  const editor = $("editor");
  editor.addEventListener("input", () => setDirty(true));
  editor.addEventListener("keydown", (event) => {
    if (event.key === "Tab") { // Tab types 4 spaces, the Pythonwood way
      event.preventDefault();
      const { selectionStart: a, selectionEnd: b, value } = editor;
      editor.value = value.slice(0, a) + "    " + value.slice(b);
      editor.selectionStart = editor.selectionEnd = a + 4;
      setDirty(true);
    } else if ((event.ctrlKey || event.metaKey) && event.key === "s") {
      event.preventDefault();
      save();
    }
  });

  api("GET", "/api/state")
    .then((data) => {
      update(data);
      run("look", "story-out");
    })
    .catch((err) => {
      document.body.innerHTML = `<p style="padding:24px">Couldn't reach the game: ${escapeHtml(err.message)}. Open it from the address the game printed.</p>`;
    });
})();
