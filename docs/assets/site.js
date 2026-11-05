/* Excel Hell — rendered from the run itself. No build step, no dependencies.
   Every number and every record on this page comes out of data/run-summary.json,
   which `dante report` writes. */

const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"];
const COLS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

/* The workbook is a Flemish wholesaler's, so the formula bar speaks Dutch Excel. */
const CIRCLE_FX = {
  1: ['bron!B2', '=SPATIES.WISSEN(SUBSTITUEREN(B2;TEKEN(160);" "))'],
  2: ['klanten!B2', '=ALS(GELIJKENIS(naam1;naam2)>=92;"samenvoegen";"beslissen")'],
  3: ['klanten!C2', '=TEKST.SPLITSEN(C2;", ";WAAR)'],
  4: ['prijzen!B2', '=WAARDE(SUBSTITUEREN(SUBSTITUEREN(B2;".";"");",";"."))'],
  5: ['artikelen!D2', '=ALS(master<>magazijn;"conflict";"")'],
  6: ['klanten!I2', '=ALS(OF(I2="BE0000000000";I2="");"ketterij";"")'],
  7: ['posten!C2', '=ALS(ISGETAL(C2);C2+DATUM(1899;12;30);DATUMWAARDE(C2))'],
  8: ['korting!B2', '=ALS(ISNB(VERT.ZOEKEN(B2;klanten!A:A;1;ONWAAR));"wees";"")'],
  9: ['afstemming!E9', '=SOMPRODUCT(ABS(detail-saldo))'],
};

const FILE_NOTES = {
  cust_master:  "Customer master, straight out of Mercurius. Semicolon-separated, and it writes a BOM.",
  cust_jan:     "A sales rep's own list, kept since 2011. One address cell, no customer numbers at all.",
  cust_sofie:   "The other rep's list. Different column names, several email addresses per cell.",
  cust_acc:     "The accounting export. Latin-1, read as UTF-8 by everything downstream.",
  art_master:   "Article master. Comma decimals, and the occasional #REF! where a price belongs.",
  art_price:    "The price list, maintained by hand. The sheet is called DEFINITIEF (versie 7).",
  art_stock:    "Stock count. Article codes Excel decided were numbers.",
  art_uom:      "Units of measure according to the warehouse. Disagrees with the master.",
  art_supp:     "Primary supplier per article according to purchasing. Also disagrees.",
  supp_master:  "Supplier master, including the ones that are blocked.",
  open_items:   "Open receivables. Five ways of writing an amount, two ways of writing a date.",
  trial_balance:"The legacy trial balance: the number the accountant will check against.",
  discounts:    "Discount agreements, some of them for customers deleted in 2019."
};

const CHOICES = {
  "R-II-02":  ["Same company — merge them", "Separate legal entities — keep both"],
  "R-II-03":  ["Keep the master's terms", "Take the rep's terms", "Ask the customer"],
  "R-II-04":  ["One entity — merge them", "Trading name — keep separate"],
  "R-III-04": ["I'll supply the real address", "Migrate without an address"],
  "R-IV-03":  ["The price is VAT-exclusive", "It includes VAT — recalculate"],
  "R-IV-04":  ["Discount already applied — keep it", "Restore the list price"],
  "R-V-01":   ["The master unit is right", "The warehouse unit is right"],
  "R-V-03":   ["Keep the master supplier", "Purchasing's supplier is right"],
  "R-VI-05":  ["It is Belgium (BE)", "Something else — I'll specify"],
  "R-VII-01": ["Matched on EAN — accept it", "Not recoverable — drop the stock line"],
  "R-VII-04": ["The pasted block is mm/dd", "Read the whole file as dd/mm"],
  "R-VIII-02":["Assign a different supplier", "Leave it unassigned for now"],
  "R-VIII-04":["Reroute to another supplier", "Block the article as well"]
};
const DEFAULT_CHOICES = ["Accept the proposal", "Keep the source value", "Send it back"];

/* ── helpers ───────────────────────────────────────────────────────── */
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined && text !== null) n.textContent = String(text);
  return n;
};
const THIN = " ";
const fmt = n => Number(n).toLocaleString("en-GB").replace(/,/g, THIN);
const money = s => {
  const v = Number(String(s).replace(/[^\d.-]/g, ""));
  return Number.isFinite(v)
    ? v.toLocaleString("en-GB", {minimumFractionDigits: 2, maximumFractionDigits: 2})
       .replace(/,/g, THIN)
    : String(s);
};

let DATA = null;

fetch("data/run-summary.json")
  .then(r => r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status)))
  .then(data => { DATA = data; render(data); })
  .catch(err => {
    document.getElementById("verdict-text").textContent =
      "Could not load the run data (" + err.message + "). Run `dante run && dante report`.";
  });

function render(d) {
  renderStart(d);
  renderFiles(d);
  renderDiagram(d);
  renderCircles(d);
  renderNinth(d);
  renderRecall(d);
  renderDesk(d);
  renderSheetTabs();
  watchSections();
}

/* ── start ─────────────────────────────────────────────────────────── */
function renderStart(d) {
  const failed = d.gates.filter(g => !g.passed);
  // twelve files, thirteen tables: the receivables workbook has a second sheet
  const files = new Set(d.stats.sources.map(s => s.file.split("!")[0])).size;

  document.getElementById("stamp").textContent = d.verdict;
  document.getElementById("verdict-text").innerHTML =
    `<b>${failed.length} of ${d.gates.length} reconciliation gates failed</b> on
     ${fmt(d.source_rows)} source rows from ${files} files.
     ${d.client} cannot load this. The totals match; that is the problem.`;

  const total = Math.max(1, d.source_rows);
  [["par", "paradiso"], ["pur", "purgatorio"], ["inf", "inferno"]].forEach(([id, key]) => {
    document.getElementById("d-" + id).textContent = fmt(d.totals[key]);
    document.getElementById("bar-" + id).style.width =
      (d.totals[key] / total * 100).toFixed(1) + "%";
  });
  document.getElementById("d-pur-sub").textContent =
    `rows held · ${fmt(d.backlog_total)} open questions`;
  document.title = `Excel Hell — ${d.verdict} on ${fmt(d.source_rows)} rows`;
}

/* ── the twelve files ──────────────────────────────────────────────── */
function renderFiles(d) {
  const host = document.getElementById("files");
  d.stats.sources.forEach(s => {
    const card = el("div", "file");
    card.append(el("div", "fn", s.file));
    card.append(el("div", "fs", `${fmt(s.rows)} rijen · ${s.columns} kolommen`));
    card.append(el("div", "fd", FILE_NOTES[s.feed] || ""));
    host.append(card);
  });
}

function renderDiagram(d) {
  const bands = document.getElementById("bands");
  if (!bands) return;
  const NS = "http://www.w3.org/2000/svg";
  d.circles.forEach((c, i) => {
    const x = 150 + i * 38;
    const h = 96 - i * 7;
    const r = document.createElementNS(NS, "rect");
    r.setAttribute("x", x);
    r.setAttribute("y", 27 + (96 - h) / 2);
    r.setAttribute("width", 30);
    r.setAttribute("height", h);
    r.setAttribute("fill", "currentColor");
    r.setAttribute("opacity", (0.07 + i * 0.045).toFixed(3));
    r.setAttribute("stroke", "currentColor");
    r.setAttribute("stroke-opacity", ".35");
    bands.append(r);
    const t = document.createElementNS(NS, "text");
    t.setAttribute("x", x + 15);
    t.setAttribute("y", 140);
    t.setAttribute("text-anchor", "middle");
    t.setAttribute("font-size", "10");
    t.setAttribute("opacity", ".7");
    t.textContent = ROMAN[i];
    bands.append(t);
  });
  ["par", "pur", "inf"].forEach((id, i) => {
    const key = ["paradiso", "purgatorio", "inferno"][i];
    document.getElementById("dg-" + id).textContent = fmt(d.totals[key]);
  });
}

/* ── a spreadsheet grid ────────────────────────────────────────────── */
function sheetGrid(caption, headers, rows, opts = {}) {
  const wrap = el("div", "sheet");
  const t = el("table");
  if (caption) t.append(el("caption", null, caption));

  const thead = el("thead");
  const colRow = el("tr", "cols");
  colRow.append(el("th", "rowhead", ""));
  headers.forEach((_, i) => colRow.append(el("th", null, COLS[i])));
  thead.append(colRow);

  const nameRow = el("tr", "names");
  nameRow.append(el("th", "rowhead", ""));
  headers.forEach(h => nameRow.append(el("th", null, h)));
  thead.append(nameRow);
  t.append(thead);

  const tb = el("tbody");
  rows.forEach((cells, i) => {
    const tr = el("tr");
    if (opts.rowClass) tr.className = opts.rowClass(i);
    tr.append(el("td", "rowhead", opts.rowLabel ? opts.rowLabel(i) : i + 2));
    cells.forEach(cell => {
      if (cell && cell.nodeType) { tr.append(cell); return; }
      const c = typeof cell === "object" && cell !== null ? cell : {v: cell};
      const td = el("td", c.cls || null, c.v === null || c.v === undefined ? "" : c.v);
      if (c.style) td.setAttribute("style", c.style);
      tr.append(td);
    });
    tb.append(tr);
  });
  t.append(tb);
  wrap.append(t);
  return wrap;
}

/* ── the descent ───────────────────────────────────────────────────── */
function renderCircles(d) {
  const host = document.getElementById("circles");
  d.circles.filter(c => c.number < 9).forEach(c => {
    const sec = el("div", "circle");
    sec.id = "circle-" + c.number;
    sec.dataset.heat = String(c.number);
    sec.style.setProperty("--heat", String(c.number));
    sec.dataset.tab = `${ROMAN[c.number - 1]} · ${c.name}`;
    const fx = CIRCLE_FX[c.number] || ["", ""];
    sec.dataset.cell = fx[0];
    sec.dataset.fx = fx[1];

    const head = el("div", "circle-head");
    head.append(el("div", "roman", ROMAN[c.number - 1]));
    const body = el("div");
    body.append(el("h3", null, c.name));
    body.append(el("p", "sin", c.sin));
    body.append(el("p", "desc", c.description));
    body.append(el("p", "tally",
      `${fmt(c.findings)} findings · ${c.rules.length} rules`));
    head.append(body);
    sec.append(head);

    const rules = el("div", "rules");
    c.rules.forEach(r => rules.append(renderRule(r, d)));
    sec.append(rules);
    host.append(sec);
  });
}

function renderRule(r, d) {
  const wrap = el("div", "rule");
  const btn = el("button");
  btn.type = "button";
  btn.setAttribute("aria-expanded", "false");
  btn.append(el("span", "caret", "▶"));
  btn.append(el("span", "rid", r.id));
  btn.append(el("span", null, r.title));
  btn.append(el("span", "tag " + r.action, r.action));
  btn.append(el("span", "cnt", r.findings ? fmt(r.findings) : "—"));
  wrap.append(btn);

  const panel = el("div", "rule-body");
  panel.append(el("p", "why", r.rationale));
  panel.append(el("p", "tally",
    `owner: ${r.owner} · entities: ${(r.entity || []).join(", ")}`));

  const samples = (d.samples || {})[r.id] || [];
  if (samples.length) {
    const file = samples[0].source;
    const outcome = s => {
      if (s.repaired !== null && s.repaired !== undefined) {
        return {v: s.repaired, cls: "now"};
      }
      return r.action === "reject"
        ? {v: "rejected", cls: "was txt"}
        : {v: "\u2192 " + r.owner + " decides", cls: "held txt"};
    };
    const rows = samples.map(s => [
      {v: s.key, cls: "txt"},
      {v: s.field, cls: "txt"},
      {v: s.raw === null ? "(empty)" : s.raw,
       cls: "was flag " + (r.action === "repair" ? "" : "bad")},
      outcome(s),
      {v: s.message, cls: "txt"},
    ]);
    panel.append(sheetGrid(
      `selectie uit ${file}  —  ${fmt(r.findings)} ${r.findings === 1 ? "rij" : "rijen"} geraakt`,
      ["record", "veld", "wat de bron zei", "wat de engine deed", "waarom"],
      rows, {rowLabel: i => i + 2}));
  } else if (r.action === "gate") {
    const g = d.gates.find(x => x.rule === r.id);
    if (g) panel.append(el("p", "tally",
      (g.passed ? "passed · " : "FAILED · ") + g.message));
  }
  wrap.append(panel);

  btn.addEventListener("click", () => {
    const open = wrap.classList.toggle("open");
    btn.setAttribute("aria-expanded", String(open));
  });
  return wrap;
}

/* ── the ninth circle ──────────────────────────────────────────────── */
function renderNinth(d) {
  const g = d.gates.find(x => x.rule === "R-IX-03");
  const e = g ? g.evidence : {};

  const rows = [
    ["Legacy trial balance", "=SOM(saldilijst!B:B)", e.trial_balance_total, ""],
    ["Migration source detail", "=SOM(posten!E:E)", e.source_detail_total, ""],
    ["Difference", "=C3-C2", e.total_difference, ""],
    ["explained · detail on customers outside the trial balance", "",
     e.explained_orphan_detail, ""],
    ["explained · rows whose amount cannot be read", "", e.explained_unquantifiable, ""],
    ["Unexplained, net", "=C4-C5-C6", e.unexplained_net, "now"],
    ["Unexplained, gross movement", "=SOMPRODUCT(ABS(detail-saldo))",
     e.unexplained_gross, "was"],
  ];
  const grid = sheetGrid(
    "afstemming.xlsx — the left column is the reconciliation everybody writes",
    ["controle", "formule", "resultaat", ""],
    rows.map(([label, formula, value, cls]) => [
      {v: label, cls: "txt"},
      {v: formula, cls: "fx"},
      {v: money(value), cls: "n " + (cls || "")},
      {v: cls === "now" ? "looks like balance" : cls === "was" ? "the betrayal" : "",
       cls: "txt"},
    ]),
    {rowLabel: i => i + 2});
  document.getElementById("reconciliation").replaceWith(grid);
  grid.id = "reconciliation";

  const worst = (e.worst || []).slice(0, 2);
  const pair = document.getElementById("pair");
  if (worst.length === 2) {
    worst.forEach((w, i) => {
      if (i === 1) {
        const eq = el("div", "eq");
        eq.append(el("div", null, "net"));
        eq.append(el("div", null, "0.00"));
        eq.append(el("div", null, "───"));
        eq.append(el("div", null, "gross"));
        eq.append(el("div", null, money(e.unexplained_gross)));
        pair.append(eq);
      }
      const side = el("div", "side " + (Number(w.difference) > 0 ? "plus" : "minus"));
      side.append(el("div", "lbl", "klant " + w.customer));
      side.append(el("span", "num", money(w.difference)));
      side.append(el("div", "det",
        `saldilijst ${money(w.trial)} · detail ${money(w.detail)}`));
      pair.append(side);
    });
  }

  // The four gate rules carry the best rationales in the registry and circle IX
  // is not part of the descent list, so they would otherwise never be readable.
  const ninthRules = document.getElementById("ninth-rules");
  const circleNine = d.circles.find(c => c.number === 9);
  if (ninthRules && circleNine) {
    circleNine.rules.forEach(r => ninthRules.append(renderRule(r, d)));
  }

  const host = document.getElementById("gates");
  d.gates.forEach(gate => {
    const row = el("div", "gate");
    row.append(el("span", "mark " + (gate.passed ? "ok" : "no"),
      gate.passed ? "pass" : "fail"));
    const what = el("div", "what");
    what.append(document.createTextNode(gate.rule + " · " + gate.title));
    what.append(el("small", null, gate.message));
    row.append(what);
    host.append(row);
  });
}

/* ── detection rate, with Excel data bars ──────────────────────────── */
function renderRecall(d) {
  const host = document.getElementById("recall");
  if (!d.detection) { host.remove(); return; }

  const rows = Object.entries(d.detection.per_rule).map(([rule, m]) => {
    const pct = Math.round(m.recall * 100);
    const colour = m.recall < 0.9 ? "var(--warn)" : "var(--good)";
    return [
      {v: rule, cls: "txt"},
      {v: fmt(m.planted), cls: "n"},
      {v: fmt(m.found), cls: "n"},
      {v: pct + "%", cls: "n",
       style: `background:linear-gradient(90deg,color-mix(in srgb,${colour} 26%,transparent)` +
              ` ${pct}%,transparent ${pct}%)`},
    ];
  });
  rows.push([
    {v: "Overall", cls: "txt"},
    {v: fmt(d.detection.planted), cls: "n"},
    {v: fmt(d.detection.found), cls: "n"},
    {v: (d.detection.overall * 100).toFixed(1) + "%", cls: "n now"},
  ]);

  const grid = sheetGrid(
    "meting.xlsx — planted by the forge, found by the engine, which never reads the forge",
    ["regel", "geplant", "gevonden", "recall"], rows,
    {rowLabel: i => i + 2});
  host.replaceWith(grid);
  grid.id = "recall";
}

/* ── the quarantine desk ───────────────────────────────────────────── */
const STORE = "excel-hell-decisions";
let currentOwner = null;
let queue = [];
let position = 0;

function decisions() {
  try { return JSON.parse(localStorage.getItem(STORE) || "{}"); }
  catch { return {}; }
}
function remember(id, choice) {
  try {
    const all = decisions();
    all[id] = choice;
    localStorage.setItem(STORE, JSON.stringify(all));
  } catch { /* private window, or storage blocked. The desk still works. */ }
}

function renderDesk(d) {
  const owners = Object.keys(d.desk || {});
  if (!owners.length) return;
  const host = document.getElementById("owners");
  owners.forEach(owner => {
    const b = el("button");
    b.type = "button";
    b.setAttribute("role", "tab");
    b.dataset.owner = owner;
    b.append(document.createTextNode(owner + " "));
    b.append(el("span", "n", fmt(d.backlog_by_owner[owner])));
    b.addEventListener("click", () => selectOwner(owner));
    host.append(b);
  });
  document.getElementById("reset").addEventListener("click", () => {
    try { localStorage.removeItem(STORE); } catch { /* nothing to clear */ }
    showCase();
  });
  selectOwner(owners[0]);
}

function selectOwner(owner) {
  currentOwner = owner;
  queue = DATA.desk[owner] || [];
  position = 0;
  document.querySelectorAll("#owners button").forEach(b =>
    b.setAttribute("aria-selected", String(b.dataset.owner === owner)));
  showCase();
}

function showCase() {
  const host = document.getElementById("case");
  host.textContent = "";
  if (!queue.length) { host.append(el("p", "muted", "Nothing on this desk.")); return; }

  const c = queue[position % queue.length];
  const id = `${c.rule}:${c.key}:${c.field}`;
  const taken = decisions()[id];

  host.append(el("div", "meta",
    `${c.rule} · ${c.source} · ${c.entity} ${c.key} · veld ${c.field}`));
  host.append(el("h4", null, c.message));

  const dl = el("dl", "ev");
  const add = (label, value) => {
    const row = el("div", "row");
    row.append(el("dt", null, label));
    row.append(el("dd", null, value));
    dl.append(row);
  };
  if (c.raw !== null && c.raw !== undefined) add("source value", c.raw);
  if (c.repaired) add("engine proposal", c.repaired);
  Object.entries(c.evidence || {}).forEach(([k, v]) => {
    if (v === null || v === undefined || k === "evidence") return;
    add(k.replace(/_/g, " "), Array.isArray(v) ? v.join("  ·  ") : v);
  });
  host.append(dl);

  const clears = DATA.findings_by_rule[c.rule] || 1;
  if (clears > 5) {
    host.append(el("p", "tally",
      `One ruling on this rule clears ${fmt(clears)} findings at once.`));
  }

  const choices = el("div", "choices");
  (CHOICES[c.rule] || DEFAULT_CHOICES).forEach(label => {
    const b = el("button", null, label);
    b.type = "button";
    b.addEventListener("click", () => { remember(id, label); position++; showCase(); });
    choices.append(b);
  });
  const skip = el("button", "ghost", "skip →");
  skip.type = "button";
  skip.addEventListener("click", () => { position++; showCase(); });
  choices.append(skip);
  host.append(choices);

  if (taken) host.append(el("p", "ruled", `You already ruled: ${taken}`));

  const made = Object.keys(decisions()).length;
  document.getElementById("progress-text").textContent =
    `${currentOwner} · case ${(position % queue.length) + 1} of ${queue.length} shown` +
    ` · ${made} decision${made === 1 ? "" : "s"} recorded in this browser` +
    ` · ${fmt(DATA.backlog_total)} in the real backlog`;
}

/* ── sheet tabs and the formula bar ────────────────────────────────── */
function tabTargets() {
  const out = [];
  document.querySelectorAll("section[data-tab]").forEach(sec => {
    if (sec.id === "descent") {
      sec.querySelectorAll(".circle[data-tab]").forEach(c => out.push(c));
      return;
    }
    out.push(sec);
  });
  return out;
}

function renderSheetTabs() {
  const bar = document.getElementById("sheetbar");
  tabTargets().forEach(node => {
    const a = el("a");
    a.href = "#" + node.id;
    const label = node.dataset.tab;
    const m = label.match(/^([IVX]+)\s·\s(.*)$/);
    if (m) {
      a.append(el("span", "tabnum", m[1]));
      a.append(document.createTextNode(" " + m[2]));
    } else {
      a.append(document.createTextNode(label));
    }
    a.dataset.for = node.id;
    bar.append(a);
  });
}

function watchSections() {
  const nodes = tabTargets();
  const namebox = document.getElementById("namebox");
  const fx = document.getElementById("fx");
  const bar = document.getElementById("sheetbar");

  const mark = node => {
    bar.querySelectorAll("a").forEach(a =>
      a.setAttribute("aria-current", String(a.dataset.for === node.id)));
    namebox.textContent = node.dataset.cell || "A1";
    fx.textContent = node.dataset.fx || "";
    const active = bar.querySelector('a[aria-current="true"]');
    if (active && bar.scrollWidth > bar.clientWidth) {
      const left = active.offsetLeft - bar.clientWidth / 2 + active.offsetWidth / 2;
      bar.scrollTo({left, behavior: "smooth"});
    }
  };

  if (!("IntersectionObserver" in window)) { mark(nodes[0]); return; }
  let current = null;
  const seen = new Map();
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => seen.set(e.target, e.intersectionRatio));
    let best = null;
    let bestRatio = 0;
    seen.forEach((ratio, node) => {
      if (ratio > bestRatio) { bestRatio = ratio; best = node; }
    });
    if (best && best !== current) { current = best; mark(best); }
  }, {rootMargin: "-90px 0px -55% 0px", threshold: [0, 0.05, 0.25, 0.5, 1]});
  nodes.forEach(n => io.observe(n));
  mark(nodes[0]);
}
