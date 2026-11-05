"""IX · Treachery — the data that is clean, loads fine and is still wrong.

The deepest circle is reserved for betrayal, and in a migration betrayal looks
like a reconciliation that balances. Two documents, two customers, one amount:
one overstated by exactly as much as the other is understated. The grand total
matches the legacy trial balance to the cent. Every row validates. The loader
reports no errors. The accountant finds it in March, when a customer disputes a
statement, and by then the old system is switched off.

So this circle does not ask whether the totals match. It asks four questions
that a matching total cannot answer:

  R-IX-01  did every source row end up somewhere
  R-IX-02  do the parts add up to the whole, to the cent
  R-IX-03  does the gross movement agree with the net movement
  R-IX-04  did any single customer lose its entire balance

R-IX-03 is the gate that catches the betrayal. Net zero with gross movement is
not balance. The run fails, and failing here is the engine working.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from ..normalise import parse_money
from ..pipeline import Context
from ..triage import INFERNO, PARADISO, PURGATORIO

CENT = Decimal("0.01")


def run(ctx: Context, verdict: dict[str, Any] | None = None) -> dict[str, Any]:
    if verdict is None:
        return {}
    gates: list[dict[str, Any]] = []

    # ── R-IX-01 · every source row ends in exactly one destination ───────
    per_entity = []
    ok_rows = True
    for entity, c in verdict["counts"].items():
        placed = c[PARADISO] + c[PURGATORIO] + c[INFERNO]
        per_entity.append({"entity": entity, "source_rows": c["source_rows"],
                           "placed": placed, "delta": placed - c["source_rows"]})
        ok_rows &= placed == c["source_rows"]
    gates.append(_gate(ctx, "R-IX-01", ok_rows,
                       f"{verdict['source_rows']} source rows, "
                       f"{sum(p['placed'] for p in per_entity)} placed",
                       {"per_entity": per_entity}))

    # ── the receivables ledger ───────────────────────────────────────────
    items = ctx.candidates["open_item"]
    detail_total = Decimal("0")
    unparseable = 0
    detail_by_customer: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for _, row in items.iterrows():
        v = row.get("amount_parsed")
        if v is None or v != v:  # NaN
            unparseable += 1
            continue
        amount = Decimal(str(v)).quantize(CENT)
        detail_total += amount
        detail_by_customer[str(row["customer_no"]).strip()] += amount

    bucket_total = Decimal("0")
    migrated_by_customer: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    by_bucket: dict[str, Decimal] = {}
    for bucket, rows in verdict["buckets"]["open_item"].items():
        subtotal = sum((Decimal(str(r["amount"])).quantize(CENT)
                        for r in rows if r["amount"] is not None), Decimal("0"))
        by_bucket[bucket] = subtotal
        bucket_total += subtotal
    item_customer = {str(r["key"]): str(c).strip()
                     for r, c in zip(items.to_dict("records"), items["customer_no"],
                                     strict=False)}
    for r in verdict["buckets"]["open_item"][PARADISO]:
        if r["amount"] is not None:
            migrated_by_customer[item_customer.get(r["key"], "?")] += \
                Decimal(str(r["amount"])).quantize(CENT)

    # ── R-IX-02 · the parts add up to the whole ──────────────────────────
    diff = (detail_total - bucket_total).copy_abs()
    gates.append(_gate(ctx, "R-IX-02", diff <= CENT,
                       f"source detail {detail_total:,.2f} vs "
                       f"triaged {bucket_total:,.2f}, difference {diff:,.2f}",
                       {"source_detail": f"{detail_total:.2f}",
                        "paradiso": f"{by_bucket[PARADISO]:.2f}",
                        "purgatorio": f"{by_bucket[PURGATORIO]:.2f}",
                        "inferno": f"{by_bucket[INFERNO]:.2f}",
                        "unparseable_rows": unparseable}))

    # ── R-IX-03 · gross against net: the betrayal ────────────────────────
    # A single net difference is useless, because a legitimate cause and a
    # defect subtract from each other inside it. So every per-customer
    # difference is attributed to a cause first, and the gate is held against
    # what is left over. An unexplained difference is the only kind that means
    # anything, and a pair of them that cancels is the ninth circle.
    trial = {}
    for _, row in ctx.norm["trial_balance"].iterrows():
        v, status = parse_money(row["saldo"])
        if status == "ok" and v is not None:
            trial[str(row["klantnr"]).strip()] = v.quantize(CENT)
    trial_total = sum(trial.values(), Decimal("0"))

    unquantifiable: dict[str, int] = defaultdict(int)
    for _, row in items.iterrows():
        v = row.get("amount_parsed")
        if v is None or v != v:
            unquantifiable[str(row["customer_no"]).strip()] += 1

    waterfall = {"orphan_detail": Decimal("0"), "unquantifiable": Decimal("0"),
                 "unexplained_net": Decimal("0"), "unexplained_gross": Decimal("0")}
    unexplained: list[dict[str, Any]] = []
    orphans: list[dict[str, Any]] = []

    for cust in sorted(set(trial) | set(detail_by_customer)):
        detail = detail_by_customer.get(cust, Decimal("0"))
        book = trial.get(cust, Decimal("0"))
        diff = detail - book
        if cust not in trial:
            waterfall["orphan_detail"] += detail
            orphans.append({"customer": cust, "detail": f"{detail:.2f}"})
            continue
        if unquantifiable.get(cust):
            waterfall["unquantifiable"] += diff
            continue
        if diff != 0:
            waterfall["unexplained_net"] += diff
            waterfall["unexplained_gross"] += diff.copy_abs()
            unexplained.append({"customer": cust, "trial": f"{book:.2f}",
                                "detail": f"{detail:.2f}", "difference": f"{diff:.2f}"})

    # A total order: the two halves of a compensating pair tie on size, and a
    # tie broken by set iteration order makes the whole run unreproducible.
    unexplained.sort(key=lambda o: (-abs(Decimal(o["difference"])), o["customer"]))
    net_unexplained = waterfall["unexplained_net"]
    gross_unexplained = waterfall["unexplained_gross"]
    betrayal = net_unexplained.copy_abs() <= CENT and gross_unexplained > CENT

    message = (
        f"unexplained difference nets to {net_unexplained:,.2f} "
        f"while gross movement is {gross_unexplained:,.2f} "
        f"across {len(unexplained)} customers"
    )
    if betrayal:
        message += " — net zero with gross movement is betrayal, not balance"

    gates.append(_gate(ctx, "R-IX-03", gross_unexplained <= CENT, message, {
        "trial_balance_total": f"{trial_total:.2f}",
        "source_detail_total": f"{detail_total:.2f}",
        "total_difference": f"{detail_total - trial_total:.2f}",
        "explained_orphan_detail": f"{waterfall['orphan_detail']:.2f}",
        "explained_unquantifiable": f"{waterfall['unquantifiable']:.2f}",
        "unexplained_net": f"{net_unexplained:.2f}",
        "unexplained_gross": f"{gross_unexplained:.2f}",
        "compensating_pattern": bool(betrayal),
        "customers_affected": len(unexplained),
        "orphan_customers": len(orphans),
        "worst": unexplained[:12],
    }))

    # ── R-IX-04 · nobody loses their whole balance ───────────────────────
    wiped = [
        {"customer": c, "trial": f"{bal:.2f}",
         "migrated": f"{migrated_by_customer.get(c, Decimal('0')):.2f}"}
        for c, bal in trial.items()
        if bal != 0 and migrated_by_customer.get(c, Decimal("0")) == 0
    ]
    wiped.sort(key=lambda w: (-Decimal(w["trial"]), w["customer"]))
    wiped_total = sum(Decimal(w["trial"]) for w in wiped)
    gates.append(_gate(ctx, "R-IX-04", not wiped,
                       f"{len(wiped)} customers would arrive with a zero balance, "
                       f"holding {wiped_total:,.2f} between them",
                       {"customers": len(wiped), "amount": f"{wiped_total:.2f}",
                        "worst": wiped[:12]}))

    passed = all(g["passed"] for g in gates)
    return {
        "gates": gates,
        "verdict": "GO" if passed else "NO-GO",
        "ledger": {
            "trial_balance_total": f"{trial_total:.2f}",
            "source_detail_total": f"{detail_total:.2f}",
            "migrated": f"{by_bucket[PARADISO]:.2f}",
            "held": f"{by_bucket[PURGATORIO]:.2f}",
            "rejected": f"{by_bucket[INFERNO]:.2f}",
            "unparseable_rows": unparseable,
        },
    }


def _gate(ctx: Context, rid: str, passed: bool, message: str,
          evidence: dict[str, Any]) -> dict[str, Any]:
    rule = ctx.rule(rid)
    if not passed:
        ctx.finding(rid, "all", "<run>", "reconciliation", "pipeline",
                    raw=None, repaired=None, message=message, **evidence)
    return {"rule": rid, "title": rule["title"], "owner": rule["owner"],
            "passed": bool(passed), "message": message, "evidence": evidence}
