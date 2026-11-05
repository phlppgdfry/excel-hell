/* The descent, rendered from the run itself. No build step, no dependencies.
   Every number and every record on this page comes out of data/run-summary.json,
   which is written by `dante report`. */

const ROMAN = ["I","II","III","IV","V","VI","VII","VIII","IX"];

const FILE_NOTES = {
  cust_master:  "Customer master, straight out of Mercurius. Semicolon-separated, and it writes a BOM.",
  cust_jan:     "A sales rep's own list, kept since 2011. One address cell, no customer numbers at all.",
  cust_sofie:   "The other rep's list. Different column names, several email addresses per cell.",
  cust_acc:     "The accounting export. Latin-1, read as UTF-8 by everything downstream.",
  art_master:   "Article master. Comma decimals, and the occasional #REF! where a price belongs.",
  art_price:    "The price list, maintained by hand. The sheet is called DEFINITIEF (versie 7).",
  art_stock:    "Stock count. Article codes that Excel decided were numbers.",
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

const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined && text !== null) n.textContent = String(text);
  return n;
};
const fmt = n => Number(n).toLocaleString("en-GB").replace(/,/g, " ");
const money = s => {
  const v = Number(String(s).replace(/[^\d.-]/g, ""));
  return Number.isFinite(v)
    ? v.toLocaleString("en-GB", {minimumFractionDigits: 2, maximumFractionDigits: 2})
       .replace(/,/g, " ")
    : s;
};

let DATA = null;

fetch("data/run-summary.json")
  .then(r => r.ok ? r.json() : Promise.reject(new Error(r.status)))
  .then(data => { DATA = data; render(data); })
  .catch(err => {
    document.getElementById("verdict-text").textContent =
      "Could not load the run data (" + err.message + "). Run `dante run && dante report`.";
  });

function render(d) {
  renderHero(d);
  renderFiles(d);
  renderCircles(d);
  renderNinth(d);
  renderRecall(d);
  renderDesk(d);
}

/* ── hero ──────────────────────────────────────────────────────────── */
function renderHero(d) {
  const failed = d.gates.filter(g => !g.passed);
  document.getElementById("stamp").textContent = d.verdict;
  // twelve files, thirteen tables: the receivables workbook has a second sheet
  const files = new Set(d.stats.sources.map(s => s.file.split("!")[0])).size;
  document.getElementById("verdict-text").innerHTML =
    `<b>${failed.length} of ${d.gates.length} reconciliation gates failed</b> on
     ${fmt(d.source_rows)} source rows from ${files} files.
     ${d.client} cannot load this. The totals match; that is the problem.`;
  document.getElementById("d-par").textContent = fmt(d.totals.paradiso);
  document.getElementById("d-pur").textContent = fmt(d.totals.purgatorio);
  document.getElementById("d-inf").textContent = fmt(d.totals.inferno);
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
    card.append(el("div", "fd",
      `${fmt(s.rows)} rows · ${s.columns} columns`));
    card.append(el("div", "fd", FILE_NOTES[s.feed] || ""));
    host.append(card);
  });
}

/* ── the descent ───────────────────────────────────────────────────── */
function renderCircles(d) {
  const host = document.getElementById("circles");
  d.circles.forEach(c => {
    const sec = el("div", "circle");
    sec.id = "circle-" + c.number;

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
  btn.append(el("span", "rid", r.id));
  btn.append(el("span", null, r.title));
  btn.append(el("span", "tag " + r.action, r.action));
  btn.append(el("span", "cnt", r.findings ? fmt(r.findings) : "—"));
  wrap.append(btn);

  const panel = el("div", "rule-body");
  panel.append(el("p", "why", r.rationale));
  if (r.action !== "gate") {
    panel.append(el("p", "tally",
      `owner: ${r.owner} · entities: ${(r.entity || []).join(", ")}`));
  }
  const samples = (d.samples || {})[r.id] || [];
  if (samples.length) panel.append(sampleTable(samples));
  else if (r.action === "gate") panel.append(gateNote(r, d));
  wrap.append(panel);

  btn.addEventListener("click", () => {
    const open = wrap.classList.toggle("open");
    btn.setAttribute("aria-expanded", String(open));
  });
  return wrap;
}

function sampleTable(samples) {
  const t = el("table");
  const thead = el("thead");
  const hr = el("tr");
  ["Record", "Field", "What the source said", "What the engine did"]
    .forEach(h => hr.append(el("th", null, h)));
  thead.append(hr);
  t.append(thead);

  const tb = el("tbody");
  samples.forEach(s => {
    const tr = el("tr");
    const k = el("td");
    k.append(el("code", null, s.key));
    tr.append(k);
    tr.append(el("td", null, s.field));

    const was = el("td");
    was.append(el("code", "was", s.raw === null ? "(empty)" : s.raw));
    tr.append(was);

    const now = el("td");
    if (s.repaired !== null && s.repaired !== undefined) {
      now.append(el("code", "now", s.repaired));
      now.append(el("div", "tally", s.message));
    } else {
      now.append(el("span", "tally", s.message));
    }
    tr.append(now);
    tb.append(tr);
  });
  t.append(tb);
  return t;
}

function gateNote(r, d) {
  const g = d.gates.find(x => x.rule === r.id);
  const p = el("p", "tally");
  if (!g) return p;
  p.textContent = (g.passed ? "passed · " : "FAILED · ") + g.message;
  return p;
}

/* ── the ninth circle ──────────────────────────────────────────────── */
function renderNinth(d) {
  const g = d.gates.find(x => x.rule === "R-IX-03");
  const e = g ? g.evidence : {};

  const rows = [
    ["Legacy trial balance", e.trial_balance_total, ""],
    ["Migration source detail", e.source_detail_total, ""],
    ["Difference", e.total_difference, "sum"],
    ["Explained · detail on customers outside the trial balance",
     e.explained_orphan_detail, ""],
    ["Explained · rows whose amount cannot be read",
     e.explained_unquantifiable, ""],
    ["Unexplained, net", e.unexplained_net, "sum"],
    ["Unexplained, gross movement", e.unexplained_gross, ""]
  ];
  const t = document.getElementById("waterfall");
  const tb = el("tbody");
  rows.forEach(([label, value, cls]) => {
    const tr = el("tr", cls);
    tr.append(el("td", null, label));
    tr.append(el("td", "r", money(value)));
    tb.append(tr);
  });
  t.append(tb);

  const worst = (e.worst || []).slice(0, 2);
  const pair = document.getElementById("pair");
  if (worst.length === 2) {
    worst.forEach((w, i) => {
      if (i === 1) {
        const eq = el("div", "eq");
        eq.innerHTML = "net<br>0.00";
        pair.append(eq);
      }
      const side = el("div", "side " + (Number(w.difference) > 0 ? "plus" : "minus"));
      side.append(el("div", "tally", "customer " + w.customer));
      side.append(el("span", "num", money(w.difference)));
      side.append(el("div", "tally",
        `ledger ${money(w.trial)} · migration ${money(w.detail)}`));
      pair.append(side);
    });
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

/* ── detection rate ────────────────────────────────────────────────── */
function renderRecall(d) {
  const t = document.getElementById("recall");
  if (!d.detection) { t.remove(); return; }
  const thead = el("thead");
  const hr = el("tr");
  ["Rule", "Planted", "Found", "Recall"].forEach((h, i) =>
    hr.append(el("th", i ? "r" : null, h)));
  thead.append(hr);
  t.append(thead);

  const tb = el("tbody");
  Object.entries(d.detection.per_rule).forEach(([rule, m]) => {
    const tr = el("tr");
    const c = el("td");
    c.append(el("code", null, rule));
    tr.append(c);
    tr.append(el("td", "r", fmt(m.planted)));
    tr.append(el("td", "r", fmt(m.found)));
    const rc = el("td", "r", (m.recall * 100).toFixed(0) + "%");
    if (m.recall < 0.9) rc.classList.add("was");
    tr.append(rc);
    tb.append(tr);
  });
  const total = el("tr", "sum");
  total.append(el("td", null, "Overall"));
  total.append(el("td", "r", fmt(d.detection.planted)));
  total.append(el("td", "r", fmt(d.detection.found)));
  total.append(el("td", "r", (d.detection.overall * 100).toFixed(1) + "%"));
  tb.append(total);
  t.append(tb);
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
    b.setAttribute("aria-selected",
      String(b.textContent.trim().startsWith(owner))));
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
    `${c.rule} · ${c.source} · ${c.entity} ${c.key} · field ${c.field}`));
  host.append(el("h4", null, c.message));

  const ev = el("div", "ev");
  const add = (label, value) => {
    const row = el("div");
    row.append(el("dt", null, label));
    const dd = el("dd");
    dd.style.margin = "0";
    dd.append(el("code", null, value));
    row.append(dd);
    ev.append(row);
  };
  if (c.raw !== null && c.raw !== undefined) add("source value", c.raw);
  if (c.repaired) add("engine proposal", c.repaired);
  Object.entries(c.evidence || {}).forEach(([k, v]) => {
    if (v === null || v === undefined || k === "evidence") return;
    add(k.replace(/_/g, " "), Array.isArray(v) ? v.join("  ·  ") : v);
  });
  host.append(ev);

  const clears = DATA.findings_by_rule[c.rule] || 1;
  if (clears > 5) {
    host.append(el("p", "tally",
      `One ruling on this rule clears ${fmt(clears)} findings at once.`));
  }

  const choices = el("div", "choices");
  (CHOICES[c.rule] || DEFAULT_CHOICES).forEach(label => {
    const b = el("button", null, label);
    b.type = "button";
    b.addEventListener("click", () => {
      remember(id, label);
      position++;
      showCase();
    });
    choices.append(b);
  });
  const skip = el("button", null, "skip →");
  skip.type = "button";
  skip.addEventListener("click", () => { position++; showCase(); });
  choices.append(skip);
  host.append(choices);

  if (taken) {
    host.append(el("p", "tally", `You already ruled: ${taken}`));
  }

  const made = Object.keys(decisions()).length;
  document.getElementById("progress-text").textContent =
    `${currentOwner} · case ${(position % queue.length) + 1} of ${queue.length} shown` +
    ` · ${made} decision${made === 1 ? "" : "s"} recorded in this browser` +
    ` · ${fmt(DATA.backlog_total)} in the real backlog`;
}
