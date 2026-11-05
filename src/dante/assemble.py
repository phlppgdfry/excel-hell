"""Four files describing customers, none of them agreeing on column names.

Mapping the sources onto one candidate shape is the dull half of a migration
and the half that decides whether anything below it works. Records from the two
sales-rep files carry no customer number at all: they only have a name and an
address, which is exactly why circle II exists.
"""

from __future__ import annotations

import pandas as pd

from .pipeline import Context

CANON = {
    "customer": ["key", "name", "street", "house_no", "box", "postcode", "city",
                 "country", "vat", "email", "phone", "payment_terms", "credit_limit",
                 "created", "blocked", "address_raw"],
    "supplier": ["key", "name", "street", "house_no", "postcode", "city", "country",
                 "vat", "email", "blocked"],
    "article": ["key", "description", "group", "uom", "ean", "cost_price",
                "sales_price", "vat_rate", "supplier_no", "sellable"],
    "open_item": ["key", "customer_no", "doc_date", "due_date", "amount"],
    "discount": ["key", "customer_no", "article_no", "pct"],
}

MAPS: dict[str, tuple[str, dict[str, str]]] = {
    "cust_master": ("customer", {
        "KLANTNR": "key", "NAAM": "name", "STRAAT": "street", "NR": "house_no",
        "BUS": "box", "POSTCODE": "postcode", "GEMEENTE": "city", "LAND": "country",
        "BTWNR": "vat", "EMAIL": "email", "TEL": "phone",
        "BETAALTERMIJN": "payment_terms", "KREDIETLIMIET": "credit_limit",
        "AANGEMAAKT": "created", "GEBLOKKEERD": "blocked",
    }),
    "cust_jan": ("customer", {
        "klant": "name", "adres volledig": "address_raw", "tel": "phone", "mail": "email",
    }),
    "cust_sofie": ("customer", {
        "Bedrijf": "name", "Straat + nr": "address_raw", "PC": "postcode",
        "Plaats": "city", "Contact e-mail": "email", "Btw": "vat",
        "Betaling": "payment_terms", "Limiet": "credit_limit",
    }),
    "cust_acc": ("customer", {
        "klantnr": "key", "naam": "name", "gemeente": "city", "btw": "vat",
        "limiet": "credit_limit",
    }),
    "supp_master": ("supplier", {
        "levnr": "key", "naam": "name", "straat": "street", "nr": "house_no",
        "pc": "postcode", "gemeente": "city", "land": "country", "btw": "vat",
        "email": "email", "geblokkeerd": "blocked",
    }),
    "art_master": ("article", {
        "ARTIKELNR": "key", "OMSCHRIJVING": "description", "GROEP": "group",
        "EENHEID": "uom", "EAN": "ean", "AANKOOP": "cost_price",
        "VERKOOP": "sales_price", "BTW": "vat_rate", "LEVNR": "supplier_no",
        "VERKOOPBAAR": "sellable",
    }),
    "open_items": ("open_item", {
        "stuknr": "key", "klantnr": "customer_no", "stukdatum": "doc_date",
        "vervaldatum": "due_date", "bedrag": "amount",
    }),
    "discounts": ("discount", {
        "afspraak": "key", "klantnr": "customer_no", "artikelnr": "article_no",
        "korting %": "pct",
    }),
}


def assemble(ctx: Context) -> None:
    frames: dict[str, list[pd.DataFrame]] = {}
    for source, (entity, mapping) in MAPS.items():
        df = ctx.norm[source]
        out = pd.DataFrame(index=df.index)
        for src_col, canon_col in mapping.items():
            out[canon_col] = df[src_col] if src_col in df.columns else None
        for col in CANON[entity]:
            if col not in out.columns:
                out[col] = None
        out = out[CANON[entity]].copy()
        out["_source"] = df["_source"]
        out["_row"] = df["_row"]
        out["_feed"] = source
        frames.setdefault(entity, []).append(out)

    for entity, parts in frames.items():
        ctx.candidates[entity] = pd.concat(parts, ignore_index=True)

    ctx.stats["candidates"] = {k: len(v) for k, v in ctx.candidates.items()}
