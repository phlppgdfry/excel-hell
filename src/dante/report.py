"""Two readers, two documents.

The audit report is for the people who have to decide: a verdict, what is
blocking it, and whose desk each open question is on. The site data is for the
descent, where the same run is walked circle by circle with real records in it.

Neither is written by hand. Both come out of the run, so they cannot drift from
what the engine actually did.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from jinja2 import Environment

from .measure import detected_keys, planted_addresses, recall

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"]

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Data migration audit — {{ s.client }}</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg'
 viewBox='0 0 16 16'><text y='13' font-size='13'>&#128213;</text></svg>">
<style>
 /* An audit report is a document, not an application, so this stays paper.
    The accents are Excel's, because it is the same workbook underneath. */
 :root{
   --ink:#1b1b1b;--mut:#5a5a58;--line:#d8d8d4;--bg:#fbfbfa;--cell:#fff;
   --excel:#217346;--excel-dark:#185c37;
   --bad:#c5221f;--bad-bg:#fde7e6;--warn:#9c6500;--good:#1d6f42;--good-bg:#e2efda;
 }
 @media (prefers-color-scheme:dark){
   :root{
     --ink:#eeeeec;--mut:#a9a9a4;--line:#3d3d3d;--bg:#171717;--cell:#1f1f1f;
     --excel:#33c481;--excel-dark:#6bcf96;
     --bad:#ff8782;--bad-bg:#3a1b1a;--warn:#ffc83d;--good:#6bcf96;--good-bg:#17301f;
   }
 }
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--ink);padding:44px 20px;
      font:15px/1.6 "Segoe UI",system-ui,-apple-system,Helvetica,Arial,sans-serif;
      -webkit-font-smoothing:antialiased}
 main{max-width:52rem;margin:0 auto}
 h1{font-size:1.85rem;margin:0 0 .2em;letter-spacing:-.018em;font-weight:700}
 h2{font-size:1.1rem;margin:2.5em 0 .6em;padding-bottom:.3em;font-weight:600;
    border-bottom:2px solid var(--excel)}
 h3{font-size:.95rem;margin:1.6em 0 .4em;font-weight:600}
 .sub{color:var(--mut);margin:0 0 2em;font-size:.95rem}
 .rail{height:4px;background:var(--excel);margin:0 0 1.6em}
 .verdict{display:flex;align-items:center;gap:1rem;border:1px solid var(--line);
          border-left:5px solid var(--bad);background:var(--cell);
          padding:.95rem 1.2rem;margin:0 0 1.6em}
 .verdict b{font-size:1.4rem;color:var(--bad);letter-spacing:.03em;
            font-family:ui-monospace,Menlo,monospace}
 .verdict span{color:var(--mut);font-size:.9rem}
 table{width:100%;border-collapse:collapse;font-size:.86rem;margin:.6em 0 1.4em;
       background:var(--cell)}
 th,td{text-align:left;padding:.42rem .55rem;border:1px solid var(--line);
       vertical-align:top}
 th{font-size:.7rem;letter-spacing:.07em;text-transform:uppercase;color:var(--mut);
    font-weight:600;background:var(--bg)}
 td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;
           font-family:ui-monospace,Menlo,monospace}
 .pass{color:var(--good);font-weight:600}.fail{color:var(--bad);font-weight:600}
 .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:0;
       border:1px solid var(--line);margin:0 0 1.6em}
 .grid div{background:var(--cell);padding:.85rem 1rem;border-right:1px solid var(--line)}
 .grid div:last-child{border-right:0}
 .grid b{display:block;font-size:1.45rem;font-variant-numeric:tabular-nums;
         font-family:ui-monospace,Menlo,monospace;font-weight:700}
 .grid small{color:var(--mut);font-size:.68rem;letter-spacing:.1em;
             text-transform:uppercase;font-family:ui-monospace,Menlo,monospace}
 .grid .up b{color:var(--good)}.grid .hold b{color:var(--warn)}.grid .down b{color:var(--bad)}
 code{font-family:ui-monospace,Menlo,monospace;font-size:.8rem;background:var(--bg);
      border:1px solid var(--line);padding:.05em .3em}
 blockquote{margin:0 0 1.2em;padding:.7rem 1rem;border-left:4px solid var(--excel);
            background:var(--cell);color:var(--mut);font-size:.9rem}
 footer{margin-top:3.2em;padding-top:1em;border-top:1px solid var(--line);
        color:var(--mut);font-size:.8rem}
 a{color:var(--excel)}
 @media print{
   :root{--bg:#fff;--cell:#fff;--ink:#000}
   body{padding:0}
   .verdict,table,.grid{break-inside:avoid}
   h2{break-after:avoid}
 }
</style></head><body><main>

<div class="rail"></div>
<h1>Data migration audit</h1>
<p class="sub">{{ s.client }} &middot; migration from {{ s.legacy_system }} &middot;
   dry run on {{ s.source_rows|num }} source rows from twelve files</p>

<div class="verdict"><b>{{ s.verdict }}</b>
 <span>{{ failed|length }} of {{ s.gates|length }} reconciliation gates failed.
 This load must not be executed.</span></div>

<div class="grid">
 <div><small>Load-ready</small><b>{{ s.totals.paradiso|num }}</b>
      rows, {{ pct(s.totals.paradiso) }} of source</div>
 <div><small>Held for a decision</small><b>{{ s.totals.purgatorio|num }}</b>
      rows, {{ s.backlog_total|num }} open questions</div>
 <div><small>Rejected</small><b>{{ s.totals.inferno|num }}</b>
      rows, {{ pct(s.totals.inferno) }} of source</div>
</div>

<h2>What is blocking the load</h2>
{% for g in s.gates %}
<h3>{{ g.rule }} &middot; {{ g.title }}
    <span class="{{ 'pass' if g.passed else 'fail' }}">
    {{ 'passed' if g.passed else 'FAILED' }}</span></h3>
<p>{{ g.message }}</p>
{% if g.rule == 'R-IX-03' and not g.passed %}
<blockquote>The totals agree. The difference against the legacy trial balance is
 {{ g.evidence.total_difference|money }}, and every cent of it is explained: orphan
 detail {{ g.evidence.explained_orphan_detail|money }} and rows whose amount could not be
 read {{ g.evidence.explained_unquantifiable|money }}. What is left over nets to
 {{ g.evidence.unexplained_net|money }} across {{ g.evidence.customers_affected }}
 customers, and moves {{ g.evidence.unexplained_gross|money }} gross.
 A reconciliation on the net total would have signed this off.</blockquote>
<table><thead><tr><th>Customer</th><th class="n">Legacy balance</th>
 <th class="n">Migration detail</th><th class="n">Difference</th></tr></thead><tbody>
{% for w in g.evidence.worst %}<tr><td><code>{{ w.customer }}</code></td>
 <td class="n">{{ w.trial|money }}</td><td class="n">{{ w.detail|money }}</td>
 <td class="n fail">{{ w.difference|money }}</td></tr>{% endfor %}
</tbody></table>
{% elif g.rule == 'R-IX-04' and not g.passed %}
<table><thead><tr><th>Customer</th><th class="n">Legacy balance</th>
 <th class="n">Would migrate</th></tr></thead><tbody>
{% for w in g.evidence.worst %}<tr><td><code>{{ w.customer }}</code></td>
 <td class="n">{{ w.trial|money }}</td>
     <td class="n fail">{{ w.migrated|money }}</td></tr>{% endfor %}
</tbody></table>
{% endif %}
{% endfor %}

<h2>The receivables ledger</h2>
<table><tbody>
 <tr><td>Legacy trial balance</td>
     <td class="n">{{ s.ledger.trial_balance_total|money }}</td></tr>
 <tr><td>Migration source detail</td>
     <td class="n">{{ s.ledger.source_detail_total|money }}</td></tr>
 <tr><td>Would be migrated</td><td class="n">{{ s.ledger.migrated|money }}</td></tr>
 <tr><td>Held for a decision</td><td class="n">{{ s.ledger.held|money }}</td></tr>
 <tr><td>Rejected</td><td class="n">{{ s.ledger.rejected|money }}</td></tr>
 <tr><td>Rows with an unreadable amount</td>
     <td class="n">{{ s.ledger.unparseable_rows }}</td></tr>
</tbody></table>

<h2>Open questions, by whose desk they are on</h2>
<table><thead><tr><th>Owner</th><th class="n">Questions</th><th>Dominant cause</th>
 </tr></thead><tbody>
{% for owner, n in s.backlog_by_owner|dictsort(by='value', reverse=true) %}
<tr><td>{{ owner }}</td><td class="n">{{ n|num }}</td><td>{{ dominant[owner] }}</td></tr>
{% endfor %}
</tbody></table>
<p>Each owner has a sheet in <code>out/purgatorio/</code> with the record, the raw
   value, the rule and the evidence. Many questions share one answer: a single
   ruling on the date format of the receivables file clears
   {{ s.findings_by_rule.get('R-VII-04', 0)|num }} of them.</p>

<h2>Findings per circle</h2>
<table><thead><tr><th>Circle</th><th>Sin</th><th class="n">Findings</th>
 <th class="n">Rules</th></tr></thead><tbody>
{% for c in s.circles %}<tr><td>{{ roman[c.number - 1] }} &middot; {{ c.name }}</td>
 <td>{{ c.sin }}</td><td class="n">{{ c.findings|num }}</td>
 <td class="n">{{ c.rules|length }}</td></tr>{% endfor %}
<tr><td colspan="2"><b>Total</b></td><td class="n"><b>{{ s.findings_total|num }}</b></td>
 <td class="n"><b>{{ rule_count }}</b></td></tr>
</tbody></table>

<h2>Every rule that fired</h2>
<table><thead><tr><th>Rule</th><th>What it caught</th><th>Action</th><th>Owner</th>
 <th class="n">Count</th></tr></thead><tbody>
{% for c in s.circles %}{% for r in c.rules %}{% if r.findings %}
<tr><td><code>{{ r.id }}</code></td><td>{{ r.title }}</td><td>{{ r.action }}</td>
 <td>{{ r.owner }}</td><td class="n">{{ r.findings|num }}</td></tr>
{% endif %}{% endfor %}{% endfor %}
</tbody></table>

<p><a href="index.html">&larr; Back to the descent</a></p>

<footer>Generated from the run by <code>dante report</code>. Every number on this
 page comes out of <code>out/report/run-summary.json</code>; none of it is typed by
 hand. {{ s.client }} is fictional and the data is synthetic.</footer>
</main></body></html>
"""


def attach_measurement(summary: dict[str, Any], out: Path,
                       truth_path: Path = Path("data/truth/planted-defects.json")
                       ) -> dict[str, Any]:
    """Score the run against the planted defects, if the ground truth is around.

    Deliberately not part of the pipeline: an engine that can see the answer key
    is not being measured, it is being graded by itself.
    """
    findings = out / "report" / "findings.csv"
    if not (truth_path.exists() and findings.exists()):
        return summary
    truth = json.loads(truth_path.read_text())
    summary["detection"] = recall(planted_addresses(truth), detected_keys(findings))
    summary["detection"]["planted_total"] = truth["planted_total"]
    return summary


def _money(v: Any) -> str:
    """A thin space for thousands: unambiguous whether the reader is Dutch or not."""
    try:
        return f"{float(v):,.2f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(v)


def render(summary: dict[str, Any], out: Path, site: Path) -> list[Path]:
    summary = attach_measurement(summary, out)
    env = Environment(autoescape=True)
    env.filters["num"] = lambda v: f"{int(v):,}".replace(",", " ")
    env.filters["money"] = _money
    total = max(1, summary["source_rows"])

    dominant: dict[str, str] = {}
    for owner in summary["backlog_by_owner"]:
        rules = [(r["findings"], r["title"]) for c in summary["circles"] for r in c["rules"]
                 if r["owner"] == owner and r["action"] == "quarantine"]
        dominant[owner] = max(rules)[1] if rules else "—"

    html = env.from_string(TEMPLATE).render(
        s=summary,
        roman=ROMAN,
        failed=[g for g in summary["gates"] if not g["passed"]],
        pct=lambda v: f"{v / total:.0%}",
        dominant=dominant,
        rule_count=sum(len(c["rules"]) for c in summary["circles"]),
    )

    written: list[Path] = []
    # The measurement is written back to the run summary as well, so the report
    # and the run cannot disagree about how the engine scored.
    (out / "report" / "run-summary.json").write_text(json.dumps(summary, indent=1))
    report_path = out / "report" / "audit-report.html"
    report_path.write_text(html)
    written.append(report_path)

    (site / "data").mkdir(parents=True, exist_ok=True)
    site_json = site / "data" / "run-summary.json"
    site_json.write_text(json.dumps(summary, indent=1))
    written.append(site_json)

    shutil.copy(report_path, site / "audit-report.html")
    written.append(site / "audit-report.html")
    return written
