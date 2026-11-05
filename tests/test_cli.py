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


# ── why: one record, and why it is where it is ───────────────────────────
def test_why_explains_a_held_record(run):
    held = next(r for r in run["summary"]["desk"]["finance"]
                if r["entity"] == "open_item")
    out = runner.invoke(app, ["why", held["key"], "--out", str(run["out"]),
                              "--rules", RULES], catch_exceptions=False)
    assert out.exit_code == 0
    assert "PURGATORIO" in out.stdout
    assert "waiting on finance" in out.stdout
    assert "loads once finance answers" in out.stdout


def test_why_explains_a_repaired_record(run):
    out = runner.invoke(app, ["why", "K00001", "--out", str(run["out"]),
                              "--rules", RULES], catch_exceptions=False)
    assert "PARADISO" in out.stdout
    assert "01_klanten_mercurius.csv row 2" in out.stdout


def test_why_names_the_person_who_released_a_record(decided, decided_out):
    """After an answer, the record says who answered rather than who owes one."""
    ruled = next(f for f in decided["samples"]["R-VII-04"]
                 if f["decision"] == "ruling")
    out = runner.invoke(app, ["why", ruled["key"], "--out", str(decided_out),
                              "--rules", RULES], catch_exceptions=False)
    assert "released by finance" in out.stdout
    assert "ruling" in out.stdout


def test_why_rejects_a_key_that_is_not_there(run):
    out = runner.invoke(app, ["why", "NOPE-1", "--out", str(run["out"]),
                              "--rules", RULES])
    assert out.exit_code == 2
    assert "no record 'NOPE-1'" in out.output


def test_why_suggests_a_near_miss(run):
    out = runner.invoke(app, ["why", "K0000", "--out", str(run["out"]),
                              "--rules", RULES])
    assert out.exit_code == 2
    assert "Did you mean K00001" in out.output


def test_why_needs_a_run_first(tmp_path):
    out = runner.invoke(app, ["why", "K00001", "--out", str(tmp_path),
                              "--rules", RULES])
    assert out.exit_code == 2
    assert "no run to report on" in out.output


# ── load: the target's own tables ────────────────────────────────────────
def test_load_shapes_the_target_tables(run):
    out = runner.invoke(app, ["load", "--out", str(run["out"]), "--mapping",
                              str(ROOT / "mapping/business-central.yaml")],
                        catch_exceptions=False)
    assert out.exit_code == 0
    assert "Business Central" in out.stdout
    assert "Customer" in out.stdout and "Gen. Journal Line" in out.stdout
    assert "will not insert until a setup record exists" in out.stdout
    assert "codes: DS, M, PK, RL, ST" in out.stdout
    assert "not migrated" in out.stdout
    assert (run["out"] / "load" / "customer.csv").exists()
    assert (run["out"] / "load" / "gen-journal-line.csv").exists()


def test_load_needs_a_run_first(tmp_path):
    out = runner.invoke(app, ["load", "--out", str(tmp_path), "--mapping",
                              str(ROOT / "mapping/business-central.yaml")])
    assert out.exit_code == 2
    assert "no load-ready data" in out.output


def test_load_says_where_the_mapping_should_be(run, tmp_path):
    out = runner.invoke(app, ["load", "--out", str(run["out"]), "--mapping",
                              str(tmp_path / "nope.yaml")])
    assert out.exit_code == 2
    assert "no target mapping" in out.output


# ── run with decisions, through the command line ─────────────────────────
def test_run_takes_the_decision_sheets(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import shutil
    shutil.copytree(ROOT / "rules", tmp_path / "rules")
    shutil.copytree(ROOT / "decisions", tmp_path / "decisions")
    assert runner.invoke(app, ["forge", "--out", "data/raw"]).exit_code == 0

    plain = runner.invoke(app, ["run", "--raw", "data/raw", "--out", "out"])
    answered = runner.invoke(app, ["run", "--raw", "data/raw", "--out", "out2",
                                   "--decisions", "decisions"])
    assert answered.exit_code == 1, "the betrayal still blocks the load"
    assert "applied" in answered.stdout and "ruling" in answered.stdout
    assert "ruleset" in answered.stdout, "the verdict names the rules behind it"
    held = [line for line in plain.stdout.splitlines() if "PURGATORIO" in line][0]
    held_after = [line for line in answered.stdout.splitlines()
                  if "PURGATORIO" in line][0]
    assert held != held_after, "answers should move rows out of purgatorio"


def test_run_refuses_a_decision_it_may_not_apply(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import shutil
    shutil.copytree(ROOT / "rules", tmp_path / "rules")
    (tmp_path / "decisions").mkdir()
    (tmp_path / "decisions" / "sales.csv").write_text(
        "rule,entity,key,field,decision,corrected_value\n"
        "R-VII-05,open_item,VF240006,amount,accept,\n")
    assert runner.invoke(app, ["forge", "--out", "data/raw"]).exit_code == 0
    out = runner.invoke(app, ["run", "--raw", "data/raw", "--out", "out",
                              "--decisions", "decisions"])
    assert out.exit_code == 2
    assert "is a reject rule" in out.output
