"""The README has to still be true.

Numbers in a readme rot the moment the code changes, and a portfolio repository
whose own figures are stale is worse than one with no figures. So every number
that matters carries an anchor, and this test holds it against the run.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

# A number may be anchored without being bold: emphasis is a writing decision,
# and forcing it would have made five of six ledger rows shout at once.
ANCHOR = re.compile(r"(?:\*\*)?([^*|<]+?)(?:\*\*)?<!--@(\w+)-->")


def readme() -> str:
    return (ROOT / "README.md").read_text()


def claimed() -> dict[str, str]:
    found = {name: value for value, name in ANCHOR.findall(readme())}
    assert found, "no anchored numbers found in README.md"
    return found


def as_number(s: str) -> float:
    return float(re.sub(r"[^\d.\-]", "", s.replace(" ", "").replace(",", "")))


def test_readme_numbers_match_the_run(run):
    s = run["summary"]
    rules = yaml.safe_load((ROOT / "rules/rules.yaml").read_text())
    gate = next(g for g in s["gates"] if g["rule"] == "R-IX-03")

    expected: dict[str, float] = {
        "circles": len(rules["circles"]),
        "rules_total": len(rules["rules"]),
        "source_rows": s["source_rows"],
        "findings_total": s["findings_total"],
        "backlog_total": s["backlog_total"],
        "gross": float(gate["evidence"]["unexplained_gross"]),
    }
    due = s["stats"]["date_format_due_date"]["evidence"]
    expected["date_dmy"] = due["dmy"]
    expected["date_mdy"] = due["mdy"]
    expected["date_doc"] = s["stats"]["date_format_doc_date"]["evidence"]["dmy"]
    expected["ambiguous"] = s["findings_by_rule"]["R-VII-04"]
    expected["ambiguous2"] = s["findings_by_rule"]["R-VII-04"]
    expected["vat_clears"] = s["findings_by_rule"]["R-IV-03"]
    expected["ledger_trial"] = float(s["ledger"]["trial_balance_total"])
    expected["ledger_detail"] = float(s["ledger"]["source_detail_total"])
    expected["ledger_diff"] = abs(float(gate["evidence"]["total_difference"]))

    if "detection" in s:
        expected["detection_found"] = s["detection"]["found"]
        expected["detection_planted"] = s["detection"]["planted"]
        expected["recall_overall"] = round(s["detection"]["overall"] * 100, 1)
        from tests.test_detection import STABLE_SAMPLE
        expected["stable_sample"] = STABLE_SAMPLE

    said = claimed()
    wrong = {}
    for name, want in expected.items():
        got = said.get(name)
        if got is None:
            wrong[name] = "missing from README"
        elif abs(as_number(got) - float(want)) > 0.005:
            wrong[name] = f"README says {got}, the run says {want}"
    assert not wrong, f"README is out of date: {wrong}"


def test_readme_destination_counts_match(run):
    """The headline block is quoted CLI output, so check what the CLI prints."""
    text = readme()
    totals = run["summary"]["totals"]
    for label in ("paradiso", "purgatorio", "inferno"):
        value = totals[label]
        assert re.search(rf"{label.upper()}\s+{value}\b", text), \
            f"README block does not show {label.upper()} as {value}"


def test_readme_verdict_matches(run):
    assert f"verdict: {run['summary']['verdict']}" in readme()


def test_readme_test_count_is_honest():
    """A promise of N tests is itself a claim worth checking."""
    m = re.search(r"pytest -q\s+# (\d+) (?:tests|checks)", readme())
    assert m, "README should state how many tests there are"
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                          str(ROOT / "tests")], capture_output=True, text=True, cwd=ROOT)
    collected = re.search(r"(\d+) tests? collected", out.stdout)
    assert collected, out.stdout[-400:]
    assert int(m.group(1)) == int(collected.group(1)), \
        f"README claims {m.group(1)} tests, pytest collects {collected.group(1)}"


def test_every_circle_is_described_in_the_readme(run):
    text = readme()
    for circle in run["summary"]["circles"]:
        assert circle["name"] in text, f"circle {circle['name']} is missing from README"


def test_readme_per_circle_table_matches_the_run(run):
    """The nine findings counts in the README table are not anchored numbers.

    They sat in a markdown table where nothing checked them, and two of them
    were wrong for a while because the progress output they were copied from
    counted findings per module rather than per rule. Nine numbers nobody
    verifies is how a portfolio readme starts lying quietly.
    """
    roman = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"]
    text = readme()
    wrong = {}
    for n in range(1, 10):
        expected = run["summary"]["findings_by_circle"][str(n)]
        m = re.search(rf"^\| {roman[n - 1]} \| [^|]+\| [^|]+\| ([\d  ]+) \|$",
                      text, re.M)
        if not m:
            wrong[roman[n - 1]] = "row missing from the README table"
            continue
        got = int(re.sub(r"\D", "", m.group(1)))
        if got != expected:
            wrong[roman[n - 1]] = f"README says {got}, the run says {expected}"
    assert not wrong, f"the per-circle table is out of date: {wrong}"


def test_readme_names_every_circle_in_order(run):
    text = readme()
    positions = [text.index(c["name"]) for c in run["summary"]["circles"]]
    assert positions == sorted(positions), "the circles are out of order in the README"


def test_the_site_markup_carries_no_run_numbers(run):
    """Everything on the page comes from the run, so nothing may be typed into it.

    The social-preview alt text and the row count in the pipeline diagram were
    both hardcoded, which meant they would have kept claiming last week's totals
    long after the code moved. Numbers belong in run-summary.json; the markup
    may only hold the placeholder that JavaScript fills.
    """
    html = (ROOT / "docs" / "index.html").read_text()
    s = run["summary"]
    literals = {
        "source_rows": s["source_rows"],
        **s["totals"],
        "findings_total": s["findings_total"],
        "backlog_total": s["backlog_total"],
    }
    found = {}
    for name, value in literals.items():
        for spelling in (str(value), f"{value:,}", f"{value:,}".replace(",", " "),
                         f"{value:,}".replace(",", "&#8201;")):
            if re.search(rf"(?<![\d.]){re.escape(spelling)}(?![\d])", html):
                found[name] = spelling
                break
    assert not found, f"run numbers hardcoded in docs/index.html: {found}"


def test_readme_quotes_the_gate_messages_it_claims_to(run):
    """The headline block is pasted CLI output and nothing checked its gate lines.

    Three of those numbers were stale at once — the receivables total, the
    customer count and the amount — because they sat inside a fenced code block
    that no anchor covered.
    """
    text = readme()
    for gate in run["summary"]["gates"]:
        mark = "pass" if gate["passed"] else "FAIL"
        assert f"[{mark}] {gate['rule']}" in text, f"{gate['rule']} missing from the block"

    detail = f"{float(run['summary']['ledger']['source_detail_total']):,.2f}"
    assert f"source detail {detail} vs triaged {detail}" in text

    wiped = next(g for g in run["summary"]["gates"] if g["rule"] == "R-IX-04")
    assert f"{wiped['evidence']['customers']} customers would arrive" in text
    assert f"{float(wiped['evidence']['amount']):,.2f}" in text
