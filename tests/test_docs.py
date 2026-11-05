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

ANCHOR = re.compile(r"\*\*([^*]+?)\*\*<!--@(\w+)-->")


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
    if "detection" in s:
        expected["detection_found"] = s["detection"]["found"]
        expected["detection_planted"] = s["detection"]["planted"]
        expected["recall_overall"] = round(s["detection"]["overall"] * 100, 1)

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
    m = re.search(r"pytest -q\s+# (\d+) tests", readme())
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
