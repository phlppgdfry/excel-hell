"""The second pass: what a human answer does, and what it may not do.

Two halves. The first runs the decision sheets this repository ships against
the real descent, because a demonstration that has gone stale against the rules
is worse than none. The second builds a context by hand and feeds it bad
answers, because every refusal in decisions.py is a claim about who is allowed
to decide, and a claim nobody tests is a comment.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import pytest

from dante import decisions as D
from dante.errors import MalformedDecisions, NoDecisions, RefusedDecisions
from dante.finding import Finding
from dante.pipeline import Context, load_registry

ROOT = Path(__file__).resolve().parents[1]
RULES, CIRCLES = load_registry(ROOT / "rules/rules.yaml")


# ── the sheets this repository ships, against the real run ──────────────
def test_the_committed_sheets_still_apply(decided):
    d = decided["decisions"]
    assert d["applied"] > 500, "the demonstration should answer real volume"
    assert d["stale"] == 0, \
        "a shipped sheet that answers a question the rules no longer ask is stale"
    assert set(d["files"]) == {"finance.csv", "operations.csv",
                               "purchasing.csv", "sales.csv"}


def test_answering_questions_moves_rows_into_the_load(run, decided):
    before, after = run["summary"]["totals"], decided["totals"]
    assert after["paradiso"] > before["paradiso"]
    assert after["purgatorio"] < before["purgatorio"]
    # and nothing escapes: every source row is still placed exactly once
    assert sum(after.values()) == sum(before.values()) == decided["source_rows"]


def test_answering_questions_empties_the_backlog_by_exactly_that_much(run, decided):
    answered = decided["decided_findings"]
    assert answered == decided["decisions"]["applied"]
    assert decided["backlog_total"] == run["summary"]["backlog_total"] - answered


def test_answering_questions_moves_a_reconciliation_gate(run, decided):
    def wiped(summary):
        gate = next(g for g in summary["gates"] if g["rule"] == "R-IX-04")
        return gate["evidence"]["customers"]

    assert wiped(decided) < wiped(run["summary"]), \
        "releasing held receivables should leave fewer customers at zero"


def test_the_betrayal_survives_every_answer(decided):
    """The point of the ninth circle: a thousand answers do not clear it.

    R-IX-04 moves because it is a consequence of triage. R-IX-03 does not,
    because the compensating pair is wrong in the source data and no amount of
    sign-off makes two errors that cancel into one truth.
    """
    gate = next(g for g in decided["gates"] if g["rule"] == "R-IX-03")
    assert not gate["passed"]
    assert gate["evidence"]["compensating_pattern"] is True
    assert decided["verdict"] == "NO-GO"


def test_a_ruling_writes_the_reading_it_selected(decided):
    """`dmy` has to reach the repair, not just the audit trail."""
    ruled = decided["samples"].get("R-VII-04", [])
    assert ruled, "the sample set should still contain the ruled rule"
    answered = [f for f in ruled if f["decision"] == "ruling"]
    assert answered, "finance ruled on this rule in the committed sheets"
    for f in answered:
        assert f["repaired"] == f["evidence"]["european"]
        assert f["effective_action"] == "repair"


def test_every_declared_ruling_matches_the_evidence_its_rule_publishes(run):
    """A ruling selects an evidence field. The field has to exist.

    This is the join between the registry and the code: the rule declares
    `dmy: european`, and circle VII has to actually publish `european`. Nothing
    else in the suite would notice if one of them was renamed.
    """
    samples = run["summary"]["samples"]
    declared = {r["id"]: r["ruling"] for r in RULES.values() if "ruling" in r}
    assert declared, "the registry should declare at least one ruling"
    for rule_id, ruling in declared.items():
        assert RULES[rule_id]["action"] == "quarantine", \
            f"{rule_id} takes a ruling but is not an open question"
        for answer, evidence_key in ruling["answers"].items():
            found = samples.get(rule_id, [])
            assert found, f"{rule_id} declares a ruling and never fired"
            assert all(evidence_key in f["evidence"] for f in found), \
                f"{rule_id} answer {answer!r} selects {evidence_key!r}, " \
                f"which its findings do not publish"


def test_the_sheet_the_run_writes_is_a_sheet_the_run_can_read(run):
    """The loop closes without anybody retyping a key."""
    sheet = run["out"] / "purgatorio" / "finance.csv"
    with open(sheet, newline="") as fh:
        header = next(csv.reader(fh))
    for column in (*D.REQUIRED, "corrected_value"):
        assert column in header, f"{column} missing from the decision sheet"


# ── refusals, on a context built for the purpose ─────────────────────────
@pytest.fixture
def ctx() -> Context:
    c = Context(raw_dir=Path("."), rules=RULES, circles=CIRCLES)
    c.candidates["customer"] = pd.DataFrame([
        {"key": "K00001", "vat": "BE0000000000", "country": "XX",
         "credit_limit": "100", "_source": "01_klanten_mercurius.csv",
         "_row": 2, "_feed": "cust_master"},
    ]).astype(object)
    c.candidates["open_item"] = pd.DataFrame([
        {"key": "VF1", "due_date": "03/04/2024", "due_date_parsed": None,
         "_source": "11.xlsx!Posten", "_row": 2, "_feed": "open_items"},
    ]).astype(object)
    c.findings = [
        Finding(rule="R-II-04", circle=2, entity="customer", key="K00001",
                field="vat", source="01_klanten_mercurius.csv",
                action="quarantine", owner="finance", raw="BE0000000000"),
        Finding(rule="R-VI-01", circle=6, entity="customer", key="K00001",
                field="vat", source="01_klanten_mercurius.csv",
                action="quarantine", owner="finance", raw="BE0000000000"),
        Finding(rule="R-VII-05", circle=7, entity="open_item", key="VF1",
                field="amount", source="11.xlsx!Posten",
                action="reject", owner="engine", raw="#REF!"),
        Finding(rule="R-VII-04", circle=7, entity="open_item", key="VF1",
                field="due_date", source="11.xlsx!Posten",
                action="quarantine", owner="finance", raw="03/04/2024",
                evidence={"european": "2024-04-03", "american": "2024-03-04"}),
    ]
    return c


def sheet(tmp_path: Path, *rows: tuple[str, ...], name: str = "finance.csv") -> Path:
    path = tmp_path / name
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rule", "entity", "key", "field", "decision", "corrected_value"])
        w.writerows(rows)
    return tmp_path


def refuse(ctx: Context, folder: Path) -> str:
    with pytest.raises(RefusedDecisions) as err:
        D.apply(ctx, D.load(folder))
    return err.value.problem


def test_a_blank_decision_is_not_an_answer(ctx, tmp_path):
    folder = sheet(tmp_path, ("R-II-04", "customer", "K00001", "vat", "", ""))
    assert D.apply(ctx, D.load(folder))["applied"] == 0
    assert all(f.decision is None for f in ctx.findings)


def test_accepting_a_question_releases_it(ctx, tmp_path):
    folder = sheet(tmp_path, ("R-II-04", "customer", "K00001", "vat", "accept", ""))
    result = D.apply(ctx, D.load(folder))
    answered = next(f for f in ctx.findings if f.rule == "R-II-04")
    assert result["applied"] == 1
    assert answered.decision == "accept"
    assert answered.decided_by == "finance", "the file name names the owner"
    assert answered.effective_action == "repair"
    assert answered.action == "quarantine", "the engine's own verdict is kept"


def test_correcting_a_question_reaches_the_column(ctx, tmp_path):
    folder = sheet(tmp_path, ("R-VI-05", "customer", "K00001", "country",
                              "correct", "BE"))
    ctx.findings.append(Finding(
        rule="R-VI-05", circle=6, entity="customer", key="K00001",
        field="country", source="01_klanten_mercurius.csv",
        action="quarantine", owner="sales", raw="XX"))
    D.apply(ctx, D.load(folder))
    assert ctx.candidates["customer"].at[0, "country"] == "BE"


def test_a_ruling_answers_every_record_that_asked(ctx, tmp_path):
    folder = sheet(tmp_path, ("R-VII-04", "open_item", "*", "due_date",
                              "ruling", "dmy"))
    result = D.apply(ctx, D.load(folder))
    assert result["applied"] == 1
    assert result["by_verdict"] == {"ruling": 1}
    # written on the parsed twin, because that is the column that loads
    assert ctx.candidates["open_item"].at[0, "due_date_parsed"] == "2024-04-03"


def test_a_ruling_may_not_overrule_the_engine(ctx, tmp_path):
    folder = sheet(tmp_path, ("R-VII-05", "open_item", "VF1", "amount",
                              "accept", ""))
    assert "is a reject rule" in refuse(ctx, folder)
    assert all(f.decision is None for f in ctx.findings), "nothing was applied"


def test_a_ruling_needs_a_rule_that_declares_one(ctx, tmp_path):
    folder = sheet(tmp_path, ("R-II-04", "customer", "*", "vat", "ruling", "yes"))
    assert "does not take a ruling" in refuse(ctx, folder)


def test_a_ruling_answer_outside_the_declared_set_is_refused(ctx, tmp_path):
    folder = sheet(tmp_path, ("R-VII-04", "open_item", "*", "due_date",
                              "ruling", "iso"))
    problem = refuse(ctx, folder)
    assert "dmy or mdy" in problem


def test_a_ruling_with_a_key_is_refused(ctx, tmp_path):
    folder = sheet(tmp_path, ("R-VII-04", "open_item", "VF1", "due_date",
                              "ruling", "dmy"))
    assert "applies to every record that asked" in refuse(ctx, folder)


def test_a_record_verb_without_a_key_is_refused(ctx, tmp_path):
    folder = sheet(tmp_path, ("R-II-04", "customer", "*", "vat", "accept", ""))
    assert "needs a key" in refuse(ctx, folder)


def test_an_unknown_rule_is_refused(ctx, tmp_path):
    folder = sheet(tmp_path, ("R-XI-99", "customer", "K00001", "vat", "accept", ""))
    assert "no rule 'R-XI-99'" in refuse(ctx, folder)


def test_an_unknown_verb_is_refused(ctx, tmp_path):
    folder = sheet(tmp_path, ("R-II-04", "customer", "K00001", "vat", "maybe", ""))
    assert "is not an answer" in refuse(ctx, folder)


def test_a_correction_without_a_value_is_refused(ctx, tmp_path):
    folder = sheet(tmp_path, ("R-II-04", "customer", "K00001", "vat", "correct", ""))
    assert "no corrected_value" in refuse(ctx, folder)


def test_a_correction_that_does_not_parse_is_refused(ctx, tmp_path):
    folder = sheet(tmp_path, ("R-VII-04", "open_item", "VF1", "due_date",
                              "correct", "17/13/2024"))
    assert "not a date the engine can read" in refuse(ctx, folder)


def test_a_correction_that_cannot_reach_a_column_stops_the_run(ctx, tmp_path):
    """An answer the load file never sees is worse than a refused one."""
    ctx.findings.append(Finding(
        rule="R-III-04", circle=3, entity="customer", key="K00001",
        field="address", source="01_klanten_mercurius.csv",
        action="quarantine", owner="sales", raw="achter de kerk"))
    folder = sheet(tmp_path, ("R-III-04", "customer", "K00001", "address",
                              "correct", "Kwadestraat 206"))
    assert "nothing in the load file carries that value" in refuse(ctx, folder)


def test_one_refused_line_applies_none_of_them(ctx, tmp_path):
    folder = sheet(tmp_path,
                   ("R-II-04", "customer", "K00001", "vat", "accept", ""),
                   ("R-VII-05", "open_item", "VF1", "amount", "accept", ""))
    refuse(ctx, folder)
    assert all(f.decision is None for f in ctx.findings)


def test_an_answer_to_a_question_nobody_asked_is_stale_not_fatal(ctx, tmp_path):
    folder = sheet(tmp_path, ("R-II-04", "customer", "K99999", "vat", "accept", ""))
    result = D.apply(ctx, D.load(folder))
    assert (result["applied"], result["stale"]) == (0, 1)


def test_a_missing_decision_directory_says_where_the_sheets_are(tmp_path):
    with pytest.raises(NoDecisions) as err:
        D.load(tmp_path / "nope")
    assert "out/purgatorio" in err.value.fix


def test_a_sheet_without_the_identifying_columns_is_refused(tmp_path):
    (tmp_path / "finance.csv").write_text("rule,decision\nR-II-04,accept\n")
    with pytest.raises(MalformedDecisions) as err:
        D.load(tmp_path)
    assert "entity" in err.value.problem
