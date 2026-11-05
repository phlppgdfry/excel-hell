"""The audit report is a deliverable, and nothing was checking that it renders.

It is the document the business reads, built from a Jinja template with about
forty substitutions in it. A renamed key in the run summary would have produced
a page with blank cells in it, and the first person to notice would have been
whoever opened it.
"""

from __future__ import annotations

import json
import re


def report_html(run) -> str:
    return (run["out"] / "report" / "audit-report.html").read_text()


def test_the_report_renders(run):
    html = report_html(run)
    assert html.startswith("<!doctype html>")
    assert "</html>" in html
    assert len(html) > 8000, "suspiciously short for a full report"


def test_no_substitution_was_left_empty(run):
    """A missing key renders as nothing, which looks deliberate and is not."""
    html = report_html(run)
    assert "{{" not in html and "{%" not in html, "an unrendered template tag survived"
    blanks = re.findall(r"<td[^>]*>\s*</td>", html)
    assert len(blanks) <= 2, f"{len(blanks)} empty cells in the report"
    assert ">None<" not in html and ">nan<" not in html


def test_the_report_states_the_verdict_and_the_blocking_gates(run):
    html = report_html(run)
    s = run["summary"]
    assert s["verdict"] in html
    for gate in s["gates"]:
        assert gate["rule"] in html
        assert gate["title"] in html
    failed = [g for g in s["gates"] if not g["passed"]]
    assert f"{len(failed)} of {len(s['gates'])} reconciliation gates failed" in html


def test_the_report_routes_every_owner(run):
    html = report_html(run)
    for owner in run["summary"]["backlog_by_owner"]:
        assert owner in html, f"{owner} has questions but no row in the report"


def test_the_report_escapes_what_it_prints(run):
    """Source values end up in this page, so they are data and not markup."""
    html = report_html(run)
    body = html.split("</style>", 1)[-1]
    assert "<script" not in body.lower()


def test_the_site_data_matches_the_run(run):
    published = json.loads((run["site"] / "data" / "run-summary.json").read_text())
    assert published["verdict"] == run["summary"]["verdict"]
    assert published["totals"] == run["summary"]["totals"]
    assert published["detection"]["overall"] == run["recall"]["overall"]


def test_the_site_gets_its_own_copy_of_the_report(run):
    assert (run["site"] / "audit-report.html").exists()
