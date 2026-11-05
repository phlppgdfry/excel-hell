"""VIII · Fraud — references to things that do not exist.

The keys look fine. A discount agreement names customer K87412, an article
names supplier L937, an invoice names a customer number that is in no master
file. Every one of those strings is the right shape. None of them points at
anything.

A loader will drop these rows silently, which is the real fraud: the migration
report says 100 percent loaded and the receivable is gone. So the severity here
follows what disappears. Money that is owed cannot be dropped quietly, and a
broken replenishment link does not justify throwing away a sellable article.
"""

from __future__ import annotations

from ..pipeline import Context


def run(ctx: Context) -> None:
    customers = ctx.candidates["customer"]
    known_customers = {
        str(k).strip() for k, feed in zip(customers["key"], customers["_feed"], strict=False)
        if feed == "cust_master" and str(k).strip() not in ("", "None")
    }
    suppliers = set(ctx.norm["supp_master"]["levnr"].astype(str).str.strip())
    blocked = {
        str(r["levnr"]).strip() for _, r in ctx.norm["supp_master"].iterrows()
        if str(r["geblokkeerd"]).strip().upper() == "J"
    }
    articles = set(ctx.candidates["article"]["key"].astype(str).str.strip())

    # R-VIII-01 · agreements for customers that were deleted years ago
    for _, row in ctx.candidates["discount"].iterrows():
        cust = str(row["customer_no"]).strip()
        if cust and cust not in known_customers:
            ctx.finding("R-VIII-01", "discount", str(row["key"]), "customer_no",
                        row["_source"], raw=cust,
                        message="orphan agreement; a loader would drop it silently")
        art = str(row["article_no"]).strip()
        if art and art not in articles:
            ctx.finding("R-VIII-01", "discount", str(row["key"]), "article_no",
                        row["_source"], raw=art, message="agreement on an unknown article")

    # R-VIII-02 / R-VIII-04 · the supply side
    for _, row in ctx.norm["art_supp"].iterrows():
        art, supp = str(row["artikel"]).strip(), str(row["leverancier"]).strip()
        if art not in articles or not supp:
            continue
        if supp not in suppliers:
            ctx.finding("R-VIII-02", "article", art, "supplier_no", row["_source"],
                        raw=supp, repaired=None,
                        message="the article is real and sellable; only its "
                                "replenishment link is broken")
        elif supp in blocked:
            ctx.finding("R-VIII-04", "article", art, "supplier_no", row["_source"],
                        raw=supp, repaired=None,
                        message="reference intact, business fact broken: reroute or block")

    # R-VIII-03 · money owed by nobody
    for _, row in ctx.candidates["open_item"].iterrows():
        cust = str(row["customer_no"]).strip()
        if cust and cust not in known_customers:
            ctx.finding("R-VIII-03", "open_item", str(row["key"]), "customer_no",
                        row["_source"], raw=cust,
                        message="a receivable with no customer; it must be reported, "
                                "not dropped",
                        amount=str(row.get("amount_parsed")))
