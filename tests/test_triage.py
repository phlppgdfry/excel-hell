"""Every source row ends up exactly once, and nothing dubious reaches Paradiso."""

from __future__ import annotations

import pandas as pd


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
    """Paradiso is data, not a row list, so it has to be usable as data."""
    customers = pd.read_csv(run["out"] / "paradiso" / "customer.csv", dtype=str)
    assert len(customers) > 100
    for col in ("key", "name"):
        assert col in customers.columns
    joined = " ".join(customers["name"].dropna().astype(str))
    assert " " not in joined, "a non-breaking space survived into load-ready data"
    assert "Ã" not in joined, "mojibake survived into load-ready data"
    assert not any(n != n.strip() for n in customers["name"].dropna().astype(str))
