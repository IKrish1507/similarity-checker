"use strict";

/* ============================================================
   Helpers
   ============================================================ */

const $ = (selector, root = document) => root.querySelector(selector);

/** Create an element: h("div", {class: "x", onclick: fn}, "text", childNode). */
function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value == null || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "style") el.style.cssText = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    el.append(child instanceof Node ? child : String(child)); // strings become text, never HTML
  }
  return el;
}

// Icon shapes are fixed strings written here, so building them with innerHTML is safe.
const ICONS = {
  logo: '<rect x="3" y="3" width="12" height="12" rx="3"/><rect x="9" y="9" width="12" height="12" rx="3"/>',
  sidebar: '<rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M9 4v16"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  sliders: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  monitor: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M20.5 13.5A8.5 8.5 0 1 1 10.5 3.5a6.5 6.5 0 0 0 10 10z"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7M12 17h.01"/>',
  clip: '<path d="m20.5 11.5-8.4 8.4a5 5 0 0 1-7.1-7.1l8.4-8.4a3.4 3.4 0 0 1 4.8 4.8l-8.4 8.4a1.7 1.7 0 0 1-2.4-2.4l7.7-7.7"/>',
  arrowUp: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
  sparkle: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 16l.7 1.8 1.8.7-1.8.7L19 21l-.7-1.8-1.8-.7 1.8-.7z"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/>',
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  columns: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  up: '<path d="m6 15 6-6 6 6"/>',
  down: '<path d="m6 9 6 6 6-6"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 21V5M8 7h7"/>',
  retry: '<path d="M4 12a8 8 0 0 1 14-5.3L20 9M20 4v5h-5M20 12a8 8 0 0 1-14 5.3L4 15M4 20v-5h5"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  alert: '<path d="M12 9v4M12 17h.01"/><path d="M10.3 4 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 4a2 2 0 0 0-3.4 0z"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
};

// The three kinds of check the composer can run.
const MODES = {
  compare: {
    icon: "columns", label: "Compare", title: "Compare documents",
    text: "Find passages shared between two or more documents.",
    placeholder: "Paste a document here, or attach .txt files…",
    thinking: "Comparing documents…",
  },
  ai: {
    icon: "sparkle", label: "AI check", title: "AI-writing check",
    text: "Estimate AI-style writing patterns in one document. Not proof.",
    placeholder: "Paste the document to check for AI-style writing…",
    thinking: "Looking for AI-style patterns…",
  },
  web: {
    icon: "globe", label: "Web check", title: "Web source check",
    text: "Search the web for pages that contain passages from one document.",
    placeholder: "Paste the document to search the web for…",
    thinking: "Searching the web and reading pages… this can take up to a minute",
  },
};

function icon(name) {
  const wrap = document.createElement("span");
  wrap.innerHTML = `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]}</svg>`;
  return wrap.firstChild;
}

const pct = (x) => `${Math.round(x * 100)}%`;
const uid = () => Math.random().toString(36).slice(2, 9) + Date.now().toString(36);
const wordCount = (text) => (text.match(/[\p{L}\p{N}]+/gu) || []).length;
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const isMobile = () => window.matchMedia("(max-width: 800px)").matches;

/* ============================================================
   Browser storage (history and preferences live only in this browser)
   ============================================================ */

const KEYS = {
  history: "simcheck.history.v1",
  settings: "simcheck.settings.v1",
  theme: "simcheck.theme.v1",
  sidebar: "simcheck.sidebar.v1",
};
const DEFAULTS = { k: 5, w: 4 };
const MAX_SAVED_CHECKS = 40;
const MAX_FILE_BYTES = 2 * 1024 * 1024;

// Storage can be blocked (private windows, full quota), so every access is guarded.
const store = {
  get(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw == null ? fallback : JSON.parse(raw);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch {
      return false;
    }
  },
};

function loadSettings() {
  const saved = store.get(KEYS.settings, {});
  const valid = (v) => Number.isInteger(v) && v >= 1 && v <= 15;
  return { k: valid(saved?.k) ? saved.k : DEFAULTS.k, w: valid(saved?.w) ? saved.w : DEFAULTS.w };
}

function loadHistory() {
  const saved = store.get(KEYS.history, []);
  return Array.isArray(saved) ? saved.filter((c) => c && Array.isArray(c.documents) && Array.isArray(c.turns)) : [];
}

/* ============================================================
   State
   ============================================================ */

const state = {
  conversations: loadHistory(), // newest first
  currentId: null,
  pending: [], // documents waiting in the composer: {id, name, text}
  settings: loadSettings(),
  theme: store.get(KEYS.theme, "system"),
  engine: null,
  webSearch: false, // whether the server has a search API key
  mode: "compare",
  busy: false,
  pasteCount: 0,
  storageWarned: false,
};

const current = () => state.conversations.find((c) => c.id === state.currentId) || null;

const el = {
  app: $("#app"), main: $("#main"), thread: $("#thread"), scroll: $("#scroll"), dock: $("#dock"),
  composerWrap: $("#composer-wrap"), chips: $("#chips"), input: $("#input"), files: $("#files"),
  addText: $("#add-text"), send: $("#send"), docCount: $("#doc-count"), hint: $("#hint"),
  history: $("#history"), search: $("#search"), title: $("#title"), badge: $("#engine-badge"),
  settings: $("#settings"), settingsBtn: $("#settings-btn"), k: $("#k"), w: $("#w"),
  kVal: $("#k-val"), wVal: $("#w-val"), guarantee: $("#guarantee"), engineLine: $("#engine-line"),
  dialog: $("#dialog"), dialogTitle: $("#dialog-title"), dialogBody: $("#dialog-body"), toasts: $("#toasts"),
  modeBtn: $("#mode-btn"), modeMenu: $("#mode-menu"), modeIcon: $("#mode-icon"), modeLabel: $("#mode-label"),
};

/* ============================================================
   Small UI pieces: toasts, dialog, theme, sidebar
   ============================================================ */

function toast(message, kind = "") {
  const t = h("div", { class: `toast ${kind}` }, message);
  el.toasts.append(t);
  setTimeout(() => t.remove(), 3200);
}

function openDialog(title, ...content) {
  el.dialogTitle.textContent = title;
  el.dialogBody.replaceChildren(...content);
  el.dialog.showModal();
}

function applyTheme(choice) {
  state.theme = ["light", "dark"].includes(choice) ? choice : "system";
  if (state.theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = state.theme;
  document.querySelectorAll("[data-theme-choice]").forEach((b) => {
    b.setAttribute("aria-pressed", String(b.dataset.themeChoice === state.theme));
  });
  store.set(KEYS.theme, state.theme);
}

function setSidebar(open) {
  if (isMobile()) {
    el.app.classList.toggle("sidebar-open", open);
  } else {
    el.app.classList.toggle("sidebar-collapsed", !open);
    store.set(KEYS.sidebar, open);
  }
}
const sidebarIsOpen = () =>
  isMobile() ? el.app.classList.contains("sidebar-open") : !el.app.classList.contains("sidebar-collapsed");

function toggleSettings(open = el.settings.hidden) {
  el.settings.hidden = !open;
  el.settingsBtn.setAttribute("aria-expanded", String(open));
}

function renderSettings() {
  const { k, w } = state.settings;
  el.k.value = k;
  el.w.value = w;
  el.kVal.textContent = k;
  el.wVal.textContent = w;
  el.guarantee.textContent =
    `Any copied run of ${k + w - 1}+ words is always caught. ` +
    "Smaller numbers find shorter matches but also flag common phrases.";
  el.engineLine.textContent = state.engine ? `Engine: ${state.engine}` : "Engine: unknown";
}

/* ============================================================
   Mode menu: Compare / AI check / Web check
   ============================================================ */

function setMode(mode) {
  state.mode = MODES[mode] ? mode : "compare";
  const m = MODES[state.mode];
  el.modeIcon.replaceChildren(icon(m.icon));
  el.modeLabel.textContent = m.label;
  el.modeBtn.className = `mode-btn ${state.mode}`;
  el.input.placeholder = m.placeholder;
  toggleModeMenu(false);
  updateComposer();
}

function toggleModeMenu(open = el.modeMenu.hidden) {
  if (open) {
    el.modeMenu.replaceChildren(...Object.entries(MODES).map(([key, m]) => {
      const needsSetup = key === "web" && !state.webSearch;
      return h("button", {
        class: "mode-item", role: "menuitemradio", "aria-checked": String(key === state.mode),
        "aria-disabled": needsSetup ? "true" : null,
        onclick: () => (needsSetup ? showHelp("web") : setMode(key)),
      },
      icon(m.icon),
      h("span", {}, h("b", {}, m.title), h("span", {}, needsSetup ? "Needs a Brave Search API key. Click for setup steps." : m.text)),
      key === state.mode ? h("span", { class: "tick" }, icon("check")) : h("span"));
    }));
  }
  el.modeMenu.hidden = !open;
  el.modeBtn.setAttribute("aria-expanded", String(open));
  if (open) el.modeMenu.querySelector(".mode-item")?.focus();
}

/* ============================================================
   Sidebar history
   ============================================================ */

function groupLabel(timestamp) {
  const startOfToday = new Date().setHours(0, 0, 0, 0);
  const day = 24 * 60 * 60 * 1000;
  if (timestamp >= startOfToday) return "Today";
  if (timestamp >= startOfToday - day) return "Yesterday";
  if (timestamp >= startOfToday - 7 * day) return "Previous 7 days";
  return "Older";
}

function renderHistory() {
  const query = el.search.value.trim().toLowerCase();
  const items = state.conversations.filter(
    (c) => !query || c.title.toLowerCase().includes(query) || c.documents.some((d) => d.name.toLowerCase().includes(query)),
  );
  el.history.replaceChildren();
  if (!items.length) {
    el.history.append(h("p", { class: "history-empty" }, query ? "No checks match your search." : "Your checks will appear here."));
    return;
  }
  let lastGroup = null;
  for (const conv of items) {
    const group = groupLabel(conv.updated);
    if (group !== lastGroup) {
      el.history.append(h("div", { class: "history-group" }, group));
      lastGroup = group;
    }
    el.history.append(
      h("div",
        {
          class: `history-item${conv.id === state.currentId ? " active" : ""}`,
          role: "button", tabindex: "0", title: conv.title,
          "aria-current": conv.id === state.currentId ? "page" : null,
          onclick: () => openConversation(conv.id),
          onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openConversation(conv.id); } },
        },
        h("span", { class: "history-title" }, conv.title),
        h("button",
          {
            class: "icon-btn small", title: "Delete", "aria-label": `Delete ${conv.title}`,
            onclick: (e) => { e.stopPropagation(); deleteConversation(conv.id); },
          },
          icon("trash")),
      ),
    );
  }
}

function saveHistory() {
  state.conversations.sort((a, b) => b.updated - a.updated);
  state.conversations = state.conversations.slice(0, MAX_SAVED_CHECKS);
  if (!store.set(KEYS.history, state.conversations) && !state.storageWarned) {
    toast("Browser storage is full or blocked, so history may not be saved.", "error");
    state.storageWarned = true;
  }
}

function openConversation(id) {
  state.currentId = id;
  if (isMobile()) setSidebar(false);
  render();
}

function newCheck() {
  state.currentId = null;
  if (isMobile()) setSidebar(false);
  render();
  el.input.focus();
}

function deleteConversation(id) {
  const conv = state.conversations.find((c) => c.id === id);
  if (!conv || !confirm(`Delete "${conv.title}"?`)) return;
  state.conversations = state.conversations.filter((c) => c.id !== id);
  if (state.currentId === id) state.currentId = null;
  saveHistory();
  render();
}

/* ============================================================
   Thread: the conversation of checks and results
   ============================================================ */

function render() {
  const conv = current();
  el.main.classList.toggle("empty", !conv);
  el.title.textContent = conv ? conv.title : "New check";
  document.title = conv ? `${conv.title} · simcheck` : "simcheck";
  el.thread.replaceChildren();
  if (conv) {
    conv.turns.forEach((turn) => el.thread.append(renderTurn(conv, turn)));
    el.dock.append(el.composerWrap);
    // Show the start of the newest result, so its summary is read first.
    requestAnimationFrame(() => el.thread.lastElementChild?.scrollIntoView({ block: "start" }));
  } else {
    el.thread.append(renderHero());
  }
  renderHistory();
  updateComposer();
}

function renderHero() {
  const slot = h("div");
  slot.append(el.composerWrap); // the composer sits in the middle until the first check
  return h("div", { class: "hero" },
    h("h2", {}, icon("logo"), "What should we compare?"),
    h("p", { class: "lead" }, "Compare documents, estimate AI-style writing, or search the web for matching sources."),
    slot,
    h("div", { class: "suggestions" },
      suggestion("columns", "Try a comparison", "Three short documents, one partly copied", runSamples),
      suggestion("sparkle", "Try an AI check", "A sample written in typical AI style", runAiSample),
      suggestion("clip", "Attach .txt files", "Or drag them anywhere on this page", () => el.files.click()),
      suggestion("book", "How it works", "What each check measures, and its limits", () => showHelp()),
    ),
  );
}

function suggestion(iconName, title, text, onclick) {
  return h("button", { class: "suggestion", onclick }, icon(iconName), h("b", {}, title), h("span", {}, text));
}

function docChip(doc) {
  return h("button", { class: "chip", title: "Preview", onclick: () => previewDoc(doc) },
    icon("file"),
    h("span", { class: "chip-info" },
      h("span", { class: "chip-name" }, doc.name),
      h("span", { class: "chip-meta" }, `${wordCount(doc.text).toLocaleString()} words`)),
  );
}

function previewDoc(doc) {
  openDialog(doc.name, h("pre", { class: "doc-text" }, doc.text));
}

function renderTurn(conv, turn) {
  const kind = MODES[turn.kind] ? turn.kind : "compare"; // checks saved before modes existed are comparisons
  const docs = conv.documents.slice(0, turn.docCount);
  const added = docs.slice(turn.docCount - turn.addedCount);
  let label;
  if (kind === "ai") label = "AI-writing check";
  else if (kind === "web") label = "Web source check";
  else if (turn.docCount === turn.addedCount) label = `Compare ${plural(added.length, "document")} · k=${turn.k}, w=${turn.w}`;
  else label = `Add ${plural(added.length, "document")} and compare with the ${turn.docCount - turn.addedCount} already here · k=${turn.k}, w=${turn.w}`;

  let body;
  if (turn.result && kind === "ai") body = renderAiResult(added[0], turn.result);
  else if (turn.result && kind === "web") body = renderWebResult(added[0], turn.result);
  else if (turn.result) body = renderResult(docs, turn.result);
  else if (turn.error) body = h("div", { class: "error-box" },
    h("p", {}, turn.error),
    h("button", { class: "ghost-btn", onclick: () => runTurn(conv, turn) }, icon("retry"), "Try again"));
  else body = h("div", { class: "thinking" }, h("span", { class: "dots" }, h("i"), h("i"), h("i")), MODES[kind].thinking);

  return h("section", { class: "turn" },
    h("div", { class: "user-msg" },
      h("div", { class: "user-bubble" },
        h("div", { class: "bubble-label" }, label),
        h("div", { class: "chips" }, added.map(docChip)))),
    h("div", { class: "assistant-msg" },
      h("div", { class: "avatar", "aria-hidden": "true" }, icon("logo")),
      h("div", { class: "assistant-body" }, body)),
  );
}

function level(score) {
  if (score >= 0.4) return ["high", "High"];
  if (score >= 0.15) return ["medium", "Medium"];
  if (score > 0) return ["low", "Low"];
  return ["none", "None"];
}

function summarize(docs, result) {
  const overlapping = result.pairs.filter((p) => p.score > 0);
  const notable = result.pairs.filter((p) => p.score >= 0.15);
  const minRun = result.k + result.w - 1;
  if (!overlapping.length) {
    return `No shared passages. None of these ${docs.length} documents share a run of ${minRun}+ words.`;
  }
  if (!notable.length) {
    return `Only small overlaps: ${plural(overlapping.length, "pair")} share a phrase or two, which is often just common wording.`;
  }
  const top = notable[0];
  return `${notable.length} of ${plural(result.pairs.length, "pair")} ${notable.length === 1 ? "has" : "have"} notable overlap. ` +
    `The strongest is ${docs[top.a].name} and ${docs[top.b].name}: ${pct(top.score)} of one appears in the other.`;
}

function renderResult(docs, result) {
  const overlapping = result.pairs.filter((p) => p.score > 0);
  const clean = result.pairs.filter((p) => p.score === 0);

  const parts = [
    h("p", { class: "summary" }, summarize(docs, result)),
    h("p", { class: "meta" },
      `${plural(docs.length, "document")} · ${result.engine} engine · k=${result.k}, w=${result.w} · ${result.elapsed_ms} ms`),
  ];

  if (docs.length >= 3) parts.push(collapsible("Similarity grid", docs.length <= 8, renderMatrix(docs, result.pairs)));
  overlapping.forEach((p, i) => parts.push(pairCard(docs, p, i === 0 && p.score >= 0.15)));
  if (clean.length) {
    parts.push(collapsible(`${plural(clean.length, "pair")} with no shared passages`, false,
      h("ul", { class: "none-list" }, clean.map((p) => h("li", {}, `${docs[p.a].name} ↔ ${docs[p.b].name}`)))));
  }
  parts.push(h("div", { class: "actions" },
    h("button", { class: "ghost-btn", onclick: () => copyText(summaryMarkdown(docs, result), "Summary copied") }, icon("copy"), "Copy summary"),
    h("button", { class: "ghost-btn", onclick: () => downloadJson(docs, result) }, icon("download"), "Download JSON"),
  ));
  return h("div", {}, parts);
}

function collapsible(title, open, content) {
  return h("details", { class: "more", open },
    h("summary", {}, icon("chevron"), title),
    h("div", { class: "more-body" }, content));
}

function renderMatrix(docs, pairs) {
  // cell[row][col] = how much of the row's document appears in the column's document
  const cell = docs.map(() => docs.map(() => 0));
  for (const p of pairs) {
    cell[p.a][p.b] = p.a_in_b;
    cell[p.b][p.a] = p.b_in_a;
  }
  const table = h("table", { class: "matrix" },
    h("thead", {}, h("tr", {}, h("th"), docs.map((d, j) => h("th", { title: d.name, scope: "col" }, `#${j + 1}`)))),
    h("tbody", {}, docs.map((d, i) => h("tr", {},
      h("th", { title: d.name, scope: "row" }, `#${i + 1} ${d.name}`),
      docs.map((_, j) => i === j
        ? h("td", { class: "self" }, "–")
        : h("td", {
          class: cell[i][j] >= 0.55 ? "dark" : null,
          style: `--v:${Math.round(cell[i][j] * 100)}`,
          title: `${pct(cell[i][j])} of ${d.name} appears in ${docs[j].name}`,
        }, cell[i][j] ? pct(cell[i][j]) : "·"))))),
  );
  return h("div", {},
    h("div", { class: "matrix-wrap" }, table),
    h("p", { class: "matrix-note" }, "Each cell shows how much of the row's document appears in the column's document."));
}

function pairCard(docs, p, openViewer) {
  const A = docs[p.a];
  const B = docs[p.b];
  const [lvlClass, lvlText] = level(p.score);
  const card = h("article", { class: "pair" });
  const toggleLabel = h("span");
  let viewer = null;

  const toggle = () => {
    if (viewer) {
      viewer.remove();
      viewer = null;
    } else {
      viewer = buildViewer(A, B, p);
      card.append(viewer);
    }
    toggleLabel.textContent = viewer ? "Hide comparison" : "Compare side by side";
  };

  card.append(
    h("div", { class: "pair-head" },
      h("div", { class: "ring", style: `--p:${Math.round(p.score * 100)};--c:var(--${lvlClass === "none" ? "faint" : lvlClass})` },
        h("span", {}, pct(p.score))),
      h("div", { class: "pair-info" },
        h("div", { class: "pair-names" },
          h("span", {}, A.name), h("span", { class: "vs" }, "↔"), h("span", {}, B.name),
          h("span", { class: `badge ${lvlClass}` }, lvlText)),
        h("div", { class: "pair-metrics" },
          `${pct(p.a_in_b)} of ${A.name} found in ${B.name} · ${pct(p.b_in_a)} the other way · ` +
          `Jaccard ${pct(p.jaccard)} · ${plural(p.a_ranges.length, "passage")}`))),
    h("div", { class: "pair-actions" },
      h("button", { class: "ghost-btn", onclick: toggle }, icon("columns"), toggleLabel),
      h("button", { class: "ghost-btn", onclick: () => copyText(passagesText(A, p.a_ranges), "Passages copied") },
        icon("copy"), "Copy passages")),
  );
  toggleLabel.textContent = "Compare side by side";
  if (openViewer) toggle();
  return card;
}

function buildViewer(A, B, p) {
  const colA = viewerColumn(A, `${pct(p.a_in_b)} shared`, p.a_ranges);
  const colB = viewerColumn(B, `${pct(p.b_in_a)} shared`, p.b_ranges);
  const total = Math.max(p.a_ranges.length, p.b_ranges.length);
  const counter = h("span", { class: "grow" }, `${plural(total, "highlighted passage")}`);
  let index = -1;

  const step = (delta) => {
    index = (index + delta + total) % total;
    focusMark(colA.text, index);
    focusMark(colB.text, index);
    counter.textContent = `Passage ${index + 1} of ${total}`;
  };

  return h("div", { class: "viewer" },
    h("div", { class: "viewer-bar" },
      counter,
      h("button", { class: "icon-btn small", title: "Previous passage", "aria-label": "Previous passage", onclick: () => step(-1) }, icon("up")),
      h("button", { class: "icon-btn small", title: "Next passage", "aria-label": "Next passage", onclick: () => step(1) }, icon("down"))),
    h("div", { class: "viewer-cols" }, colA.node, colB.node));
}

function viewerColumn(doc, note, ranges) {
  const text = h("div", { class: "viewer-text", tabindex: "0" });
  highlight(text, doc.text, ranges);
  return {
    text,
    node: h("div", { class: "viewer-col" }, h("h4", {}, h("b", { title: doc.name }, doc.name), h("span", {}, note)), text),
  };
}

/**
 * Fill `container` with text, wrapping each [start, end) range in <mark>.
 * `decorate(mark, index)` can add a class or tooltip to each mark.
 */
function highlight(container, text, ranges, decorate) {
  container.replaceChildren();
  let pos = 0;
  ranges.forEach(([start, end], i) => {
    if (start < pos) return; // ranges are sorted and never overlap; skip anything malformed
    if (start > pos) container.append(text.slice(pos, start));
    const mark = h("mark", {}, text.slice(start, end));
    decorate?.(mark, i);
    container.append(mark);
    pos = end;
  });
  container.append(text.slice(pos));
}

function ring(fraction, color, label = pct(fraction)) {
  return h("div", { class: "ring", style: `--p:${Math.round(fraction * 100)};--c:var(--${color})` }, h("span", {}, label));
}

/* ---------- AI-writing check result ---------- */

function renderAiResult(doc, r) {
  const notProof = h("div", { class: "notice" }, icon("alert"),
    h("p", {}, h("b", {}, "This is an estimate, not proof. "),
      "It measures writing patterns common in AI text. Careful human writers, formal academic style and " +
      "non-native English writers can score high, and edited AI text can score low. Don't use it as " +
      "evidence about anyone's work, including yours."));

  if (!r.enough_text) {
    return h("div", {},
      h("p", { class: "summary" }, `This document is too short to estimate. It has ${r.words} words, and the check needs at least ${r.min_words} in five or more sentences.`),
      notProof);
  }

  const color = r.score >= 60 ? "high" : r.score >= 30 ? "medium" : "low";
  const view = h("div", { class: "doc-view", tabindex: "0" });
  highlight(view, doc.text, r.flagged.map((f) => [f.start, f.end]), (mark, i) => {
    mark.classList.add("ai");
    mark.title = r.flagged[i].reasons.join("\n");
  });

  return h("div", {},
    h("div", { class: "score-head" },
      ring(r.score / 100, color, String(r.score)),
      h("div", {},
        h("h3", {}, r.band),
        h("p", {}, `AI-style score ${r.score} out of 100 · ${r.words.toLocaleString()} words · ${r.sentences} sentences`))),
    notProof,
    h("div", { class: "signals" }, r.signals.map((s) => h("div", { class: "signal" },
      h("span", { class: "signal-name" }, s.name),
      h("span", { class: "meter", title: `${Math.round(s.score * 100)}% of this signal's maximum` },
        h("i", { style: `width:${Math.round(s.score * 100)}%` })),
      h("span", { class: "signal-value" }, `${Math.round(s.weight * 100)}% weight`),
      h("span", { class: "signal-why" }, `${s.value}. ${s.explanation}`)))),
    collapsible(`Sentences with AI-style patterns (${r.flagged.length})`, r.flagged.length > 0,
      h("div", {},
        h("p", { class: "legend" }, "Hover or long-press a highlight to see why it was flagged."),
        view)),
  );
}

/* ---------- Web source check result ---------- */

const safeLink = (url) => (/^https?:\/\//i.test(url) ? url : null); // never render javascript: or other schemes

function renderWebResult(doc, r) {
  const found = r.sources.length;
  const summary = found
    ? `About ${pct(r.overall)} of this document's fingerprints were found on ${plural(found, "web page")}.`
    : `No matching pages found for the ${plural(r.queries.length, "phrase")} searched.`;

  const allMatches = h("div", { class: "doc-view", tabindex: "0" });
  highlight(allMatches, doc.text, r.ranges);

  return h("div", {},
    h("p", { class: "summary" }, summary),
    h("p", { class: "meta" },
      `${plural(r.queries.length, "phrase")} searched · ${plural(r.pages_checked, "page")} checked` +
      `${r.skipped.length ? ` · ${r.skipped.length} couldn't be read` : ""} · ${(r.elapsed_ms / 1000).toFixed(1)} s`),
    r.sources.map((s) => sourceCard(doc, s, r)),
    found ? collapsible("Your document with every match highlighted", false, allMatches) : null,
    collapsible("What was searched", false,
      h("ul", { class: "plain-list" }, r.queries.map((q) => h("li", {}, h("code", {}, q.query), ` · ${plural(q.results, "result")}`)))),
    r.skipped.length ? collapsible("Pages that couldn't be checked", false,
      h("ul", { class: "plain-list" }, r.skipped.map((s) => h("li", {}, `${s.url} (${s.reason})`)))) : null,
    h("div", { class: "notice" }, icon("alert"),
      h("p", {}, "Only pages returned for these phrases were checked. Pages behind logins or paywalls, PDFs and " +
        "private sources (like other students' submissions) aren't included, so a low result doesn't guarantee " +
        "the text is original.")),
  );
}

function sourceCard(doc, s) {
  const href = safeLink(s.url);
  const card = h("article", { class: "pair" });
  const label = h("span", {}, "Show matches");
  let view = null;
  card.append(
    h("div", { class: "source" },
      ring(s.score, s.score >= 0.4 ? "high" : s.score >= 0.15 ? "medium" : "low"),
      h("div", { class: "pair-info" },
        href ? h("a", { href, target: "_blank", rel: "noopener noreferrer" }, s.title, icon("external")) : h("b", {}, s.title),
        h("div", { class: "source-domain" }, `${s.domain} · ${pct(s.score)} of your document found here · ${plural(s.ranges.length, "passage")}`))),
    h("div", { class: "pair-actions" },
      h("button", {
        class: "ghost-btn",
        onclick: () => {
          if (view) { view.remove(); view = null; } else {
            const text = h("div", { class: "doc-view", tabindex: "0" });
            highlight(text, doc.text, s.ranges);
            view = h("div", { class: "viewer" }, h("div", { class: "viewer-bar" }, `Passages from your document found on ${s.domain}`),
              h("div", { style: "padding:0 14px 12px;background:var(--surface)" }, text));
            card.append(view);
          }
          label.textContent = view ? "Hide matches" : "Show matches";
        },
      }, icon("columns"), label),
      href ? h("button", { class: "ghost-btn", onclick: () => copyText(href, "Link copied") }, icon("copy"), "Copy link") : null),
  );
  return card;
}

function focusMark(container, index) {
  const marks = container.querySelectorAll("mark");
  marks.forEach((m) => m.classList.remove("current"));
  if (!marks.length) return;
  const mark = marks[Math.min(index, marks.length - 1)];
  mark.classList.add("current");
  container.scrollTo({ top: Math.max(0, mark.offsetTop - 48), behavior: "smooth" });
}

/* ============================================================
   Copy and download
   ============================================================ */

const clean = (s) => s.replace(/\s+/g, " ").trim();

function passagesText(doc, ranges) {
  return ranges.map(([s, e]) => `"${clean(doc.text.slice(s, e))}"`).join("\n\n");
}

function summaryMarkdown(docs, result) {
  const lines = [`simcheck results (${result.engine} engine, k=${result.k}, w=${result.w})`, "", summarize(docs, result), ""];
  for (const p of result.pairs) {
    lines.push(`- ${pct(p.score)}  ${docs[p.a].name} <-> ${docs[p.b].name}  ` +
      `(${pct(p.a_in_b)} / ${pct(p.b_in_a)} contained, ${p.a_ranges.length} passages)`);
  }
  return lines.join("\n");
}

async function copyText(text, message) {
  try {
    await navigator.clipboard.writeText(text);
    toast(message);
  } catch {
    toast("Couldn't access the clipboard.", "error");
  }
}

function downloadJson(docs, result) {
  const report = {
    generated: new Date().toISOString(),
    engine: result.engine, k: result.k, w: result.w,
    documents: docs.map((d, i) => ({ index: i, name: d.name, words: wordCount(d.text) })),
    pairs: result.pairs.map((p) => ({
      a: docs[p.a].name, b: docs[p.b].name,
      score: p.score, a_in_b: p.a_in_b, b_in_a: p.b_in_a, jaccard: p.jaccard,
      passages: p.a_ranges.map(([s, e]) => clean(docs[p.a].text.slice(s, e))),
    })),
  };
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
  const link = h("a", { href: url, download: `simcheck-${Date.now()}.json` });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ============================================================
   Composer: collecting documents
   ============================================================ */

function nameFromText(text) {
  const words = clean(text).split(" ").slice(0, 5).join(" ");
  return words.length > 34 ? `${words.slice(0, 34)}…` : `${words}…`;
}

function addPending(name, text) {
  state.pending.push({ id: uid(), name, text });
  renderChips();
}

function addTextAsDocument() {
  const text = el.input.value;
  if (!text.trim()) return;
  addPending(nameFromText(text), text);
  el.input.value = "";
  autosize();
  updateComposer();
}

async function addFiles(fileList) {
  for (const file of fileList) {
    if (file.size > MAX_FILE_BYTES) {
      toast(`${file.name} is over 2 MB, so it was skipped.`, "error");
      continue;
    }
    const text = await file.text();
    if (!text.trim()) {
      toast(`${file.name} is empty.`, "error");
      continue;
    }
    addPending(file.name, text);
  }
  el.input.focus();
}

function renderChips() {
  el.chips.replaceChildren(...state.pending.map((doc) =>
    h("div", { class: "chip" },
      icon("file"),
      h("span", { class: "chip-info" },
        h("span", { class: "chip-name", title: `${doc.name} (double-click to rename)`, ondblclick: () => renamePending(doc) }, doc.name),
        h("span", { class: "chip-meta" }, `${wordCount(doc.text).toLocaleString()} words`)),
      h("button", {
        class: "chip-x", title: "Remove", "aria-label": `Remove ${doc.name}`,
        onclick: () => { state.pending = state.pending.filter((d) => d.id !== doc.id); renderChips(); },
      }, icon("x")))));
  el.chips.hidden = !state.pending.length;
  updateComposer();
}

function renamePending(doc) {
  const name = prompt("Document name", doc.name);
  if (name && name.trim()) {
    doc.name = name.trim();
    renderChips();
  }
}

function updateComposer() {
  const conv = current();
  const existing = conv ? conv.documents.length : 0;
  const typed = el.input.value.trim() ? 1 : 0;
  const incoming = state.pending.length + typed;
  const total = existing + incoming;

  el.addText.hidden = !typed || state.mode !== "compare";
  el.docCount.textContent = incoming ? plural(incoming, "new document") : "";

  if (state.mode === "compare") {
    el.send.disabled = state.busy || incoming === 0 || total < 2;
    if (conv) el.hint.textContent = `New documents are compared with the ${plural(existing, "document")} already in this check · Ctrl+Enter to compare`;
    else if (total < 2) el.hint.textContent = `Add at least two documents${total ? " (one more to go)" : ""} · Ctrl+Enter to compare`;
    else el.hint.textContent = "Ready · Ctrl+Enter to compare";
    return;
  }
  // AI and web checks look at exactly one document.
  const webBlocked = state.mode === "web" && !state.webSearch;
  el.send.disabled = state.busy || incoming !== 1 || webBlocked;
  if (incoming > 1) el.hint.textContent = `${MODES[state.mode].title} works on one document at a time. Remove ${incoming - 1}.`;
  else if (webBlocked) el.hint.textContent = "Web check needs a Brave Search API key. Open \"How it works\" for setup.";
  else if (state.mode === "ai") el.hint.textContent = "An estimate of AI-style patterns, not proof · runs on this computer · Ctrl+Enter";
  else el.hint.textContent = "Sends up to 8 short phrases from your document to Brave Search · Ctrl+Enter";
}

function autosize() {
  el.input.style.height = "auto";
  el.input.style.height = `${Math.min(el.input.scrollHeight, 240)}px`;
}

/* ============================================================
   Running comparisons
   ============================================================ */

function makeTitle(docs) {
  const names = docs.map((d) => d.name);
  if (names.length <= 2) return names.join(" vs ");
  return `${names[0]}, ${names[1]} +${names.length - 2}`;
}

async function send() {
  if (state.busy) return;
  if (el.input.value.trim()) addTextAsDocument();
  const added = state.pending.map(({ name, text }) => ({ name, text }));
  if (!added.length) return;

  const kind = state.mode;
  let conv = current();
  const existing = conv ? conv.documents : [];
  const limit = state.limits?.max_documents ?? 50;
  if (kind !== "compare" && added.length !== 1) return toast(`${MODES[kind].title} works on one document at a time.`, "error");
  if (kind === "compare" && existing.length + added.length < 2) return toast("Add at least two documents to compare.", "error");
  if (existing.length + added.length > limit) return toast(`A check can hold up to ${limit} documents.`, "error");

  if (!conv) {
    conv = { id: uid(), title: "", created: Date.now(), updated: Date.now(), documents: [], turns: [] };
    state.conversations.unshift(conv);
  }
  conv.documents = [...existing, ...added];
  conv.title = makeTitle(conv.documents);
  const turn = {
    kind, at: Date.now(), addedCount: added.length, docCount: conv.documents.length,
    k: state.settings.k, w: state.settings.w, result: null, error: null,
  };
  conv.turns.push(turn);
  state.currentId = conv.id;
  state.pending = [];
  renderChips();
  await runTurn(conv, turn);
}

async function runTurn(conv, turn) {
  turn.result = null;
  turn.error = null;
  conv.updated = Date.now();
  state.busy = true;
  render();
  const kind = MODES[turn.kind] ? turn.kind : "compare";
  const target = conv.documents[turn.docCount - 1]; // AI and web checks look at the document they added
  const request = {
    compare: ["/api/compare", { documents: conv.documents.slice(0, turn.docCount), k: turn.k, w: turn.w }],
    ai: ["/api/ai-check", { text: target.text }],
    web: ["/api/web-check", { text: target.text }],
  }[kind];
  try {
    const response = await fetch(request[0], {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request[1]),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `The server answered ${response.status}.`);
    turn.result = data;
  } catch (err) {
    turn.error = err instanceof TypeError
      ? "Can't reach the simcheck server. Is `python -m simcheck.web` still running?"
      : err.message;
  } finally {
    state.busy = false;
    saveHistory();
    if (state.currentId === conv.id) render();
    else renderHistory();
  }
}

async function runSamples() {
  try {
    const samples = await (await fetch("/api/samples")).json();
    if (!Array.isArray(samples) || samples.length < 2) throw new Error();
    state.currentId = null;
    state.pending = [];
    setMode("compare");
    samples.forEach((s) => addPending(s.name, s.text));
    await send();
  } catch {
    toast("Couldn't load the sample documents.", "error");
  }
}

async function runAiSample() {
  try {
    const samples = await (await fetch("/api/samples?set=ai")).json();
    const sample = samples.find((s) => s.name === "ai_style.txt") || samples[0];
    if (!sample) throw new Error();
    state.currentId = null;
    state.pending = [];
    setMode("ai");
    addPending(sample.name, sample.text);
    await send();
  } catch {
    toast("Couldn't load the sample document.", "error");
  }
}

function showHelp(section) {
  toggleModeMenu(false);
  const compare = [
    h("h3", {}, "Compare documents"),
    h("ol", {},
      h("li", {}, h("b", {}, "Words. "), "Each document is lowercased and split into words, ignoring punctuation."),
      h("li", {}, h("b", {}, "k-grams. "), "Every run of k words in a row (default 5) is turned into a number with a hash function."),
      h("li", {}, h("b", {}, "Winnowing. "), "Only the smallest number in each window of w hashes is kept. These are the document's fingerprints. ",
        "Any shared run of k + w − 1 words is guaranteed to produce a shared fingerprint."),
      h("li", {}, h("b", {}, "Scores. "), "Shared fingerprints give the scores: how much of A appears in B, the reverse, and the Jaccard overlap of both."),
      h("li", {}, h("b", {}, "Passages. "), "Shared fingerprints are mapped back to the original text and highlighted.")),
    h("p", {}, "Fingerprinting finds copied wording; it can't detect paraphrasing. Algorithm: Schleimer, Wilkerson & Aiken, ",
      h("i", {}, "Winnowing: Local Algorithms for Document Fingerprinting"), " (2003)."),
  ];
  const ai = [
    h("h3", {}, "AI-writing check"),
    h("p", {}, "Measures five patterns that AI assistants produce more often than most people: evenly sized sentences, ",
      "overused words (\"delve\", \"pivotal\"…), stock transitions (\"Furthermore\"…), three-part lists and em dashes. ",
      "Each is scored 0–1, weighted, and combined into a score out of 100. It needs at least 150 words."),
    h("p", {}, h("b", {}, "It is not proof. "), "No AI detector, including commercial ones, can prove who wrote a text. ",
      "Formal and non-native English writing often scores high; edited AI text can score low. Runs entirely on this computer."),
  ];
  const web = [
    h("h3", {}, "Web source check"),
    h("p", {}, "Picks up to 8 distinctive phrases from your document, searches for each as an exact quote with the ",
      "Brave Search API, downloads up to 12 of the pages found, and fingerprints them like a comparison. ",
      "Those phrases are sent to Brave; nothing else leaves your computer."),
    h("p", {}, h("b", {}, "Setup: "), state.webSearch ? "a key is configured, so web check is ready." : "web check is off until you add a key."),
    h("ol", {},
      h("li", {}, "Create a Brave Search API account at api-dashboard.search.brave.com (needs a card; the plan includes monthly free credit). Set a spending limit if you want to stay within the free credit."),
      h("li", {}, "Copy your API key. Keep it private: don't paste it into chats or commit it to GitHub."),
      h("li", {}, "In PowerShell, save it for your user account: ", h("code", {}, "setx BRAVE_SEARCH_API_KEY \"your-key\"")),
      h("li", {}, "Open a new terminal and restart the server: ", h("code", {}, ".venv\\Scripts\\python -m simcheck.web"))),
  ];
  const sections = { compare, ai, web };
  const order = section && sections[section] ? [section, ...Object.keys(sections).filter((s) => s !== section)] : Object.keys(sections);
  openDialog("How simcheck works",
    ...order.flatMap((s) => sections[s]),
    h("p", {}, "Checks are saved only in this browser."));
}

/* ============================================================
   Events and start-up
   ============================================================ */

function bindEvents() {
  $("#new-check").onclick = newCheck;
  $("#new-check-top").onclick = newCheck;
  $("#collapse").onclick = () => setSidebar(false);
  $("#open-sidebar").onclick = () => setSidebar(true);
  $("#backdrop").onclick = () => setSidebar(false);
  $("#help").onclick = () => showHelp();
  el.modeBtn.onclick = () => toggleModeMenu();
  document.addEventListener("click", (e) => {
    if (!el.modeMenu.hidden && !el.modeMenu.contains(e.target) && !el.modeBtn.contains(e.target)) toggleModeMenu(false);
  });
  $("#dialog-close").onclick = () => el.dialog.close();
  el.dialog.addEventListener("click", (e) => { if (e.target === el.dialog) el.dialog.close(); });

  el.search.oninput = renderHistory;
  el.settingsBtn.onclick = () => toggleSettings();
  document.addEventListener("click", (e) => {
    if (!el.settings.hidden && !el.settings.contains(e.target) && !el.settingsBtn.contains(e.target)) toggleSettings(false);
  });
  for (const key of ["k", "w"]) {
    el[key].oninput = () => {
      state.settings[key] = Number(el[key].value);
      store.set(KEYS.settings, state.settings);
      renderSettings();
    };
  }
  $("#reset-settings").onclick = () => {
    state.settings = { ...DEFAULTS };
    store.set(KEYS.settings, state.settings);
    renderSettings();
  };
  document.querySelectorAll("[data-theme-choice]").forEach((b) => { b.onclick = () => applyTheme(b.dataset.themeChoice); });

  el.input.addEventListener("input", () => { autosize(); updateComposer(); });
  el.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(); }
  });
  el.addText.onclick = addTextAsDocument;
  el.send.onclick = send;
  el.files.onchange = async () => { await addFiles(el.files.files); el.files.value = ""; };

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      toggleSettings(false);
      toggleModeMenu(false);
      if (isMobile()) setSidebar(false);
    }
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "o") { e.preventDefault(); newCheck(); }
  });

  // Drag and drop files anywhere on the page.
  let dragDepth = 0;
  const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
  window.addEventListener("dragenter", (e) => { if (hasFiles(e)) { dragDepth++; document.body.classList.add("dragging"); } });
  window.addEventListener("dragleave", (e) => { if (hasFiles(e) && --dragDepth <= 0) { dragDepth = 0; document.body.classList.remove("dragging"); } });
  window.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
  window.addEventListener("drop", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    dragDepth = 0;
    document.body.classList.remove("dragging");
    addFiles(e.dataTransfer.files);
  });
}

async function loadInfo() {
  try {
    const info = await (await fetch("/api/info")).json();
    state.engine = info.engine;
    state.webSearch = Boolean(info.web_search);
    state.limits = info;
    updateComposer();
    el.badge.hidden = false;
    el.badge.textContent = `${info.engine} engine`;
    el.badge.classList.toggle("rust", info.engine === "rust");
    el.badge.title = info.engine === "rust" ? "Fingerprints computed by the compiled Rust core" : "Fingerprints computed in Python";
  } catch {
    el.badge.hidden = true;
  }
  renderSettings();
}

function init() {
  document.querySelectorAll("[data-icon]").forEach((slot) => slot.replaceWith(icon(slot.dataset.icon)));
  applyTheme(state.theme);
  if (!isMobile() && store.get(KEYS.sidebar, true) === false) el.app.classList.add("sidebar-collapsed");
  bindEvents();
  setMode("compare");
  renderSettings();
  renderChips();
  render();
  loadInfo();
}

init();
