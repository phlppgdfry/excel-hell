"""The ninth circle, which is the only one with a verdict attached.

The planted betrayal is two documents on two customers: one overstated by
1247.50 and one understated by the same amount. The grand total still matches
the legacy trial balance, so these tests exist to prove that matching totals is
not the control anybody thinks it is.
"""

from __future__ import annotations

from decimal import Decimal


def gate(run, rule: str) -> dict:
    return next(g for g in run["summary"]["gates"] if g["rule"] == rule)


def test_row_count_gate_passes(run):
    assert gate(run, "R-IX-01")["passed"]


def test_the_parts_add_up_to_the_whole_to_the_cent(run):
    g = gate(run, "R-IX-02")
    assert g["passed"], g["message"]
    e = g["evidence"]
    parts = sum(Decimal(e[k]) for k in ("paradiso", "purgatorio", "inferno"))
    assert parts == Decimal(e["source_detail"])


def test_the_compensating_pair_is_caught_although_the_total_balances(run):
    g = gate(run, "R-IX-03")
    e = g["evidence"]
    assert not g["passed"], "the betrayal went undetected"
    assert Decimal(e["unexplained_net"]) == Decimal("0.00"), \
        "the net difference should be zero: that is the whole point"
    assert Decimal(e["unexplained_gross"]) == Decimal("2495.00")
    assert e["compensating_pattern"] is True
    assert e["customers_affected"] == 2
    a, b = (Decimal(w["difference"]) for w in e["worst"][:2])
    assert a == -b, "the pair must be equal and opposite"


def test_the_whole_difference_against_the_legacy_ledger_is_accounted_for(run):
    """Nothing is allowed to sit in a residual nobody can explain."""
    e = gate(run, "R-IX-03")["evidence"]
    total = Decimal(e["total_difference"])
    explained = (Decimal(e["explained_orphan_detail"])
                 + Decimal(e["explained_unquantifiable"])
                 + Decimal(e["unexplained_net"]))
    assert explained == total, f"{explained} explained of {total}"


def test_a_customer_losing_its_whole_balance_blocks_the_run(run):
    g = gate(run, "R-IX-04")
    assert not g["passed"]
    assert g["evidence"]["customers"] > 0
    assert Decimal(g["evidence"]["amount"]) > 0


def test_the_run_refuses_to_sign_off(run):
    assert run["summary"]["verdict"] == "NO-GO"
    failed = [g["rule"] for g in run["summary"]["gates"] if not g["passed"]]
    assert failed == ["R-IX-03", "R-IX-04"]


def test_the_date_format_verdict_is_evidence_based(run):
    stats = run["summary"]["stats"]
    due = stats["date_format_due_date"]
    doc = stats["date_format_doc_date"]
    assert due["verdict"] == "mixed", "the receivables file does mix date formats"
    assert due["evidence"]["dmy"] > 0 and due["evidence"]["mdy"] > 0
    assert doc["verdict"] == "dmy", "the document date is consistent and needs no human"
    assert "mdy" not in doc["evidence"]
