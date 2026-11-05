"""Every source row ends up exactly once, and nothing dubious reaches Paradiso."""

from __future__ import annotations

import re

import pandas as pd

from dante.normalise import PLACEHOLDER_EMAILS, PLACEHOLDER_PHONES

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
NUMERIC = re.compile(r"-?\d+(\.\d+)?")


def test_every_row_lands_in_exactly_one_destination(run):
    counts = run["summary"]["counts"]
    for entity, c in counts.items():
        placed = c["paradiso"] + c["purgatorio"] + c["inferno"]
        assert placed == c["source_rows"], f"{entity}: {placed} placed of {c['source_rows']}"


def test_totals_agree_with_the_per_entity_counts(run):
    s = run["summary"]
    for bucket in ("paradiso", "purgatorio", "inferno"):
        assert s["totals"][bucket] == sum(c[bucket] for c in s["counts"].values())
    assert s["source_rows"] == sum(c["source_rows"] for c in s["counts"].values())


def test_nothing_needing_a_decision_was_quietly_loaded(run):
    """A row with a quarantine or reject finding must not be in Paradiso."""
    findings = pd.read_csv(run["out"] / "report" / "findings.csv")
    blocked = {
        (r["entity"], str(r["key"]))
        for _, r in findings.iterrows()
        if r["action"] in ("quarantine", "reject")
    }
    leaked = []
    for entity in run["summary"]["counts"]:
        path = run["out"] / "paradiso" / f"{entity}.csv"
        if not path.exists():
            continue
        loaded = pd.read_csv(path, dtype=str)
        if "key" not in loaded.columns:
            continue
        leaked += [(entity, k) for k in loaded["key"].astype(str) if (entity, k) in blocked]
    assert not leaked, f"rows needing a decision reached Paradiso: {leaked[:5]}"


def test_every_held_row_names_an_owner(run):
    backlog = run["summary"]["backlog_by_owner"]
    assert backlog, "nothing was routed to a human"
    assert "engine" not in backlog, "the engine cannot be the owner of a decision"
    assert sum(backlog.values()) == run["summary"]["backlog_total"]


def test_load_ready_output_is_actually_clean(run):
    """Paradiso is data somebody loads, so it has to be loadable.

    This test was too weak once and let real defects through: twenty-two
    receivables reached Paradiso with an Excel serial number in a date column,
    and a customer arrived with "/" as an email address. Both had been reported
    as findings and neither was written back. Reporting a repair and then
    shipping the original is worse than not repairing at all, because the report
    claims it was handled.
    """
    customers = pd.read_csv(run["out"] / "paradiso" / "customer.csv", dtype=str)
    assert len(customers) > 100
    for col in ("key", "name"):
        assert col in customers.columns

    names = customers["name"].dropna().astype(str)
    joined = " ".join(names)
    assert " " not in joined, "a non-breaking space survived into load-ready data"
    assert "Ã" not in joined, "mojibake survived into load-ready data"
    assert not any(n != n.strip() for n in names), "untrimmed name in load-ready data"

    # no staging columns: the target system has no field for them
    leaked = [c for c in customers.columns
              if c.startswith("_") or c.endswith("_parsed") or c == "address_raw"]
    assert not leaked, f"customer.csv still carries staging columns: {leaked}"

    # every date is ISO or empty: no Excel serials, no ambiguous source formats
    items = pd.read_csv(run["out"] / "paradiso" / "open_item.csv", dtype=str)
    for col in ("doc_date", "due_date"):
        bad = [v for v in items[col].dropna() if not ISO_DATE.fullmatch(str(v))]
        assert not bad, f"open_item.{col} is not ISO in Paradiso: {bad[:4]}"
    created = [v for v in customers["created"].dropna() if not ISO_DATE.fullmatch(str(v))]
    assert not created, f"customer.created is not ISO in Paradiso: {created[:4]}"

    # placeholders reported as nulled have to actually be gone
    for col, placeholders in (("email", PLACEHOLDER_EMAILS), ("phone", PLACEHOLDER_PHONES)):
        present = [v for v in customers[col].dropna()
                   if str(v).strip().lower() in placeholders]
        assert not present, f"placeholder {col} survived into Paradiso: {present[:4]}"

    # amounts are numbers, not the five ways people wrote them down
    amounts = [v for v in items["amount"].dropna() if not NUMERIC.fullmatch(str(v))]
    assert not amounts, f"open_item.amount is not numeric in Paradiso: {amounts[:4]}"

    articles = pd.read_csv(run["out"] / "paradiso" / "article.csv", dtype=str)
    for col in ("cost_price", "sales_price"):
        bad = [v for v in articles[col].dropna() if not NUMERIC.fullmatch(str(v))]
        assert not bad, f"article.{col} is not numeric in Paradiso: {bad[:4]}"
