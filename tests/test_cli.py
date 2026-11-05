"""The commands themselves, in process, so what they print is actually checked.

The error paths were covered by driving the CLI as a subprocess, which proves
the exit codes but tells coverage nothing and never looked at the happy path.
`dante rule` in particular prints the thing a reader is most likely to try
first, and until now nothing read its output.
"""

from __future__ import annotations

from typer.testing import CliRunner

from dante.cli import app
from tests.conftest import ROOT

RULES = str(ROOT / "rules" / "rules.yaml")

runner = CliRunner()


def test_version():
    out = runner.invoke(app, ["--version"])
    assert out.exit_code == 0
    assert out.stdout.strip().startswith("dante ")


def test_no_arguments_shows_help_rather_than_an_error():
    out = runner.invoke(app, [])
    assert "forge" in out.stdout and "run" in out.stdout and "rule" in out.stdout


def test_rule_explains_a_rule(run):
    out = runner.invoke(app, ["rule", "R-IX-03", "--out", str(run["out"]),
                              "--rules", RULES], catch_exceptions=False)
    text = out.stdout
    assert "R-IX-03" in text
    assert "Compensating errors detected by gross movement" in text
    assert "circle IX" in text and "Treachery" in text
    assert "action: gate" in text and "owner: finance" in text
    assert "betrayal, not balance" in text, "the rationale should be printed in full"


def test_rule_is_case_insensitive_and_counts_its_findings(run):
    out = runner.invoke(app, ["rule", "r-vii-04", "--out", str(run["out"]),
                              "--rules", RULES, "--limit", "2"])
    expected = run["summary"]["findings_by_rule"]["R-VII-04"]
    assert f"{expected} findings in the last run" in out.stdout
    assert "and " in out.stdout and "more in" in out.stdout, "the tail should be summarised"


def test_rule_suggests_a_near_miss(run):
    out = runner.invoke(app, ["rule", "RIX03", "--out", str(run["out"]),
                              "--rules", RULES])
    assert out.exit_code == 2
    assert "Did you mean R-IX-03" in out.stdout


def test_rule_rejects_a_rule_that_does_not_exist(run):
    out = runner.invoke(app, ["rule", "R-XIV-99", "--out", str(run["out"]),
                              "--rules", RULES])
    assert out.exit_code == 2
    assert "no rule" in out.stdout


def test_singular_and_plural_are_handled(run):
    """One finding is a finding, and the gate rules have exactly one."""
    out = runner.invoke(app, ["rule", "R-IX-04", "--out", str(run["out"]),
                              "--rules", RULES])
    assert "1 finding in the last run" in out.stdout


def test_forge_and_run_and_report_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import shutil
    shutil.copytree(ROOT / "rules", tmp_path / "rules")

    assert runner.invoke(app, ["forge", "--out", "data/raw"]).exit_code == 0
    done = runner.invoke(app, ["run", "--raw", "data/raw", "--out", "out"])
    assert done.exit_code == 1, "a failing gate is the expected outcome"
    assert "NO-GO" in done.stdout
    rendered = runner.invoke(app, ["report", "--out", "out", "--site", "site"])
    assert rendered.exit_code == 0
    assert (tmp_path / "site" / "audit-report.html").exists()
    assert (tmp_path / "site" / "data" / "run-summary.json").exists()
