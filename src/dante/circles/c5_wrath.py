"""V · Wrath — sources at war with each other.

The same article is sold per piece in the master file, per box by the warehouse
and per metre by whoever maintained the third spreadsheet. No file is wrong on
its own. Together they cannot all be true, and no amount of source precedence
settles it, because the warehouse is simultaneously the most accurate source
and the least authoritative one.

So the engine sorts conflicts by what a wrong answer costs. A unit of measure
is off by a factor of fifty in stock value, and a supplier places real orders:
both go to a human. A description is cosmetic, so the engine takes the master
and keeps the alternative as a note. Nobody gets asked about a description.
"""

from __future__ import annotations

from ..pipeline import Context


def run(ctx: Context) -> None:
    master = ctx.candidates["article"].set_index("key", drop=False)
    uom_df = ctx.norm["art_uom"]
    supp_df = ctx.norm["art_supp"]
    known_suppliers = set(ctx.norm["supp_master"]["levnr"].astype(str))

    conflicts_uom = 0
    for _, row in uom_df.iterrows():
        key = str(row["artikel"])
        if key not in master.index:
            continue
        warehouse_uom = str(row["eenheid magazijn"]).strip().upper()
        master_uom = str(master.at[key, "uom"]).strip().upper()
        if warehouse_uom and master_uom and warehouse_uom != master_uom:
            conflicts_uom += 1
            ctx.finding("R-V-01", "article", key, "uom", row["_source"],
                        raw=f"{master_uom} (master) vs {warehouse_uom} (warehouse)",
                        repaired=None,
                        message="two sources, two units, a factor fifty in stock value",
                        master=master_uom, warehouse=warehouse_uom)

        warehouse_desc = str(row["omschrijving magazijn"]).strip()
        master_desc = str(master.at[key, "description"]).strip()
        if warehouse_desc and master_desc and warehouse_desc.lower() != master_desc.lower():
            ctx.finding("R-V-02", "article", key, "description", row["_source"],
                        raw=warehouse_desc, repaired=master_desc,
                        message="master wins, alternative kept as a note")

    for _, row in supp_df.iterrows():
        key = str(row["artikel"])
        if key not in master.index:
            continue
        claimed = str(row["leverancier"]).strip()
        master_supplier = str(master.at[key, "supplier_no"]).strip()
        if not claimed:
            continue
        if claimed not in known_suppliers:
            continue  # circle VIII owns references that point at nothing
        if claimed != master_supplier:
            ctx.finding("R-V-03", "article", key, "supplier_no", row["_source"],
                        raw=f"{master_supplier} (master) vs {claimed} (purchasing)",
                        repaired=None,
                        message="purchasing drives replenishment from this field",
                        master=master_supplier, purchasing=claimed)

    ctx.stats["uom_conflicts"] = conflicts_uom
