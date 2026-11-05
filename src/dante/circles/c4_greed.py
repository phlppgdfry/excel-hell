"""IV · Greed — money that will not say what it means.

Comma or dot. Euro sign, the word EUR, or nothing. VAT in or VAT out. A
discount already applied to the unit price by a sales rep in 2021 and applied
again by the ERP on day one. Every one of these is a cent that lands in the
wrong ledger, and unlike a misspelled street name, nobody forgives it.

The separator cases are repairable, because the position of the separators
settles the reading. The VAT question is not: a wrong answer moves 21 percent
of a sales price, so it goes to finance with the evidence attached.
"""

from __future__ import annotations

from decimal import Decimal

from ..normalise import parse_money
from ..pipeline import Context

AFFIRMATIVE = {"ja", "j", "x", "1", "yes", "y", "true", "waar"}


def run(ctx: Context) -> None:
    price_df = ctx.norm["art_price"]
    discounted = set(ctx.norm["discounts"]["artikelnr"].astype(str))

    # ── the article master: cost and sales price as the legacy system wrote them
    # The raw column is never overwritten. A parsed column is added beside it, so
    # every repaired amount can still be held against what the source said.
    articles = ctx.candidates["article"]
    for col in ("cost_price", "sales_price"):
        parsed: list[float | None] = []
        for _, row in articles.iterrows():
            raw = row[col]
            value, status = parse_money(raw)
            if status == "ok" and _needed_interpretation(raw):
                ctx.finding("R-IV-01", "article", str(row["key"]), col, row["_source"],
                            raw=raw, repaired=f"{value:.2f}",
                            message="decimal separator resolved by position")
            parsed.append(float(value) if status == "ok" and value is not None else None)
        articles[f"{col}_parsed"] = parsed
    ctx.candidates["article"] = articles
    art = articles.set_index("key", drop=False)

    # ── the hand-maintained price list ───────────────────────────────────
    for _, row in price_df.iterrows():
        key = str(row["artikel"])
        raw = row["prijs"]
        value, status = parse_money(raw)
        source = row["_source"]
        if status == "formula_error":
            ctx.finding("R-VII-05", "article", key, "price", source, raw=raw,
                        message="the cell never held a value")
            continue
        if status != "ok" or value is None:
            continue
        if _has_currency(raw):
            ctx.finding("R-IV-02", "article", key, "price", source, raw=raw,
                        repaired=f"{value:.2f}", message="currency text stripped")
        elif _needed_interpretation(raw):
            ctx.finding("R-IV-01", "article", key, "price", source, raw=raw,
                        repaired=f"{value:.2f}",
                        message="decimal separator resolved by position")

        sellable = (str(art.at[key, "sellable"]).upper().startswith("J")
                    if key in art.index else True)
        if value <= 0:
            if sellable:
                ctx.finding("R-IV-05", "article", key, "price", source, raw=raw,
                            message="a sellable article priced at zero or less")
            continue

        master_sales = art.at[key, "sales_price_parsed"] if key in art.index else None
        master_cost = art.at[key, "cost_price_parsed"] if key in art.index else None
        incl = str(row.get("incl btw?") or "").strip().lower()

        # R-IV-03 · the flag claims the price includes VAT, and the amount is
        # identical to the master's exclusive price. Both cannot be true.
        if incl in AFFIRMATIVE and master_sales and abs(float(value) - master_sales) < 0.01:
            ctx.finding("R-IV-03", "article", key, "price", source, raw=raw,
                        message="flag says VAT-inclusive, amount equals the exclusive price",
                        vat_rate=str(row.get("btw%")), flag=incl,
                        master_price=f"{master_sales:.2f}",
                        inclusive_would_be=f"{master_sales * (1 + _rate(row)):.2f}")

        # R-IV-04 · below cost while a discount agreement exists for the article
        if master_cost and float(value) < master_cost and key in discounted:
            ctx.finding("R-IV-04", "article", key, "price", source, raw=raw,
                        message="unit price below cost while a discount agreement exists",
                        cost=f"{master_cost:.2f}", price=f"{float(value):.2f}")

    # ── open receivables ─────────────────────────────────────────────────
    items = ctx.candidates["open_item"]
    parsed: list[float | None] = []
    for _, row in items.iterrows():
        raw = row["amount"]
        value, status = parse_money(raw)
        key = str(row["key"])
        if status == "formula_error":
            ctx.finding("R-VII-05", "open_item", key, "amount", row["_source"], raw=raw,
                        message="a receivable with no amount")
            parsed.append(None)
            continue
        if status != "ok":
            ctx.finding("R-IV-01", "open_item", key, "amount", row["_source"], raw=raw,
                        message=f"amount {status}")
            parsed.append(None)
            continue
        if _has_currency(raw):
            ctx.finding("R-IV-02", "open_item", key, "amount", row["_source"], raw=raw,
                        repaired=f"{value:.2f}", message="currency text stripped")
        elif _needed_interpretation(raw):
            ctx.finding("R-IV-01", "open_item", key, "amount", row["_source"], raw=raw,
                        repaired=f"{value:.2f}",
                        message="decimal separator resolved by position")
        parsed.append(float(value))
    items["amount_parsed"] = parsed
    ctx.candidates["open_item"] = items


def _rate(row) -> float:
    try:
        return float(str(row.get("btw%")).replace(",", ".")) / 100.0
    except (TypeError, ValueError):
        return 0.21


def _has_currency(raw: object) -> bool:
    s = str(raw).lower()
    return any(t in s for t in ("€", "eur", "euro"))


def _needed_interpretation(raw: object) -> bool:
    s = str(raw)
    return ("," in s) or (s.count(".") > 1) or (" " in s) or (" " in s.strip())


def as_decimal(v: object) -> Decimal | None:
    value, status = parse_money(str(v))
    return value if status == "ok" else None
