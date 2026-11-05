"""I · Limbo — data that is almost right.

Nothing here is a sin. The encoding drifted, a non-breaking space crept in, an
export wrote a BOM. These rows never had a chance to be correct, and all of it
is repairable without asking anyone. Everything below this circle depends on it
having run: you cannot match two names that differ by an invisible character.
"""

from __future__ import annotations

import pandas as pd

from ..normalise import collapse_ws, fix_mojibake, norm_code, strip_invisibles
from ..pipeline import Context

# Which column in which source holds an entity code that must be case-folded.
CODE_COLUMNS = {
    "cust_master": ["KLANTNR"], "cust_acc": ["klantnr"],
    "art_master": ["ARTIKELNR", "LEVNR"], "art_price": ["artikel"],
    "art_stock": ["artikelnr"], "art_uom": ["artikel"],
    "art_supp": ["artikel", "leverancier"], "supp_master": ["levnr"],
    "open_items": ["stuknr", "klantnr"], "discounts": ["afspraak", "klantnr", "artikelnr"],
    "trial_balance": ["klantnr"],
}
ENTITY_OF = {
    "cust_master": "customer", "cust_jan": "customer", "cust_sofie": "customer",
    "cust_acc": "customer", "art_master": "article", "art_price": "article",
    "art_stock": "article", "art_uom": "article", "art_supp": "article",
    "supp_master": "supplier", "open_items": "open_item", "discounts": "discount",
    "trial_balance": "open_item",
}
ENTITY_OF_FILE = {
    "01_klanten_mercurius.csv": "customer",
    "04_klanten_boekhouding.csv": "customer",
    "05_artikelen_mercurius.csv": "article",
}
KEY_COLUMN = {
    "cust_master": "KLANTNR", "cust_acc": "klantnr", "art_master": "ARTIKELNR",
    "art_price": "artikel", "art_stock": "artikelnr", "art_uom": "artikel",
    "art_supp": "artikel", "supp_master": "levnr", "open_items": "stuknr",
    "discounts": "afspraak", "trial_balance": "klantnr",
}


BOM_CANDIDATES = {
    "01_klanten_mercurius.csv": "customer",
    "04_klanten_boekhouding.csv": "customer",
    "05_artikelen_mercurius.csv": "article",
}


def _row_key(df, idx, keycol: str | None, codecols: list[str]) -> str:
    """The key as the rest of the descent will know it: folded, not as typed."""
    if not keycol:
        return f"row {df.at[idx, '_row']}"
    raw = str(df.at[idx, keycol])
    return norm_code(raw) if keycol in codecols else raw


def run(ctx: Context) -> None:
    repaired_cells = 0
    for name, df in ctx.sources.items():
        entity = ENTITY_OF[name]
        out = df.copy()
        keycol = KEY_COLUMN.get(name)
        codecols = CODE_COLUMNS.get(name, [])

        for col in out.columns:
            if col.startswith("_"):
                continue
            series = out[col].astype(str)
            new_values = []
            for idx, value in series.items():
                key = _row_key(out, idx, keycol, codecols)
                v = value
                v, moji = fix_mojibake(v)
                if moji:
                    ctx.finding("R-I-01", entity, key, col, df.at[idx, "_source"],
                                raw=value, repaired=v,
                                message="latin-1 bytes read as UTF-8")
                v, invisible = strip_invisibles(v)
                if invisible:
                    ctx.finding("R-I-02", entity, key, col, df.at[idx, "_source"],
                                raw=repr(value), repaired=v,
                                message="invisible character removed")
                v, spaced = collapse_ws(v)
                if spaced:
                    ctx.finding("R-I-03", entity, key, col, df.at[idx, "_source"],
                                raw=repr(value), repaired=v)
                if col in codecols:
                    folded = norm_code(v)
                    if folded != v:
                        ctx.finding("R-I-05", entity, key, col, df.at[idx, "_source"],
                                    raw=v, repaired=folded,
                                    message="entity code folded before matching")
                        v = folded
                if v != value:
                    repaired_cells += 1
                new_values.append(v)
            out[col] = new_values
        ctx.norm[name] = out

    # R-I-04 · the BOM, checked on the raw bytes.
    #
    # Every CSV reader has its own opinion about whether to hide a BOM, and
    # pandas hides it, so asking the parser whether the file has one always
    # answers no. The reader that hides it is the same reader that hands the
    # next tool in the chain an unaddressable first column, which is how this
    # surfaces in practice: not as an encoding error, but as a mandatory field
    # that went missing between two scripts.
    for csv_name, entity in BOM_CANDIDATES.items():
        path = ctx.raw_dir / csv_name
        if not path.exists():
            continue
        with open(path, "rb") as fh:
            if fh.read(3) != b"\xef\xbb\xbf":
                continue
        first = pd.read_csv(path, sep=";", nrows=0, encoding="utf-8").columns[0]
        ctx.finding("R-I-04", entity, "<header>", first.lstrip("﻿"), csv_name,
                    raw=f"BOM + {first.lstrip(chr(0xFEFF))!r}",
                    repaired=first.lstrip("﻿"),
                    message="byte order mark on the first column header")

    ctx.stats["limbo_repaired_cells"] = repaired_cells
