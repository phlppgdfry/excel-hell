"""VII · Violence — what Excel did to the data on its way here.

Nobody edited these cells. An article code was stored as a float and came back
as 1.23E+11 with its last digits gone. A leading zero was eaten off an EAN. A
date became the number 45291. The user did nothing wrong, and the damage is
worse than anything a user could type.

Two of these are recoverable and one is not, and the difference is whether the
value can be verified rather than guessed. An EAN has a fixed length and a check
digit, so padding it back is provable. A truncated float has lost the digits for
good, and the only honest move is to go back to the other source and ask.

The date format is inferred per file from the rows that prove it. A file whose
own rows prove both readings is a mixed file, and its ambiguous rows are the
only ones a human ever sees.
"""

from __future__ import annotations

import re
from collections import Counter

from ..normalise import FORMULA_ERRORS, ean_fix, is_scientific, parse_date
from ..pipeline import Context

_DMY = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$")


def infer_date_format(values: list[str]) -> tuple[str, Counter]:
    """Decide dd/mm or mm/dd from the rows that can only be read one way."""
    ev: Counter = Counter()
    for v in values:
        m = _DMY.fullmatch(str(v).strip())
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12 and b <= 12:
            ev["dmy"] += 1
        elif b > 12 and a <= 12:
            ev["mdy"] += 1
    if ev["dmy"] and ev["mdy"]:
        return "mixed", ev
    if ev["dmy"]:
        return "dmy", ev
    if ev["mdy"]:
        return "mdy", ev
    return "unknown", ev


def run(ctx: Context) -> None:
    # ── article codes that became floats ─────────────────────────────────
    master_keys = set(ctx.candidates["article"]["key"].astype(str))
    stock = ctx.norm["art_stock"]
    for _, row in stock.iterrows():
        code = str(row["artikelnr"]).strip()
        if is_scientific(code):
            ctx.finding("R-VII-01", "article", code, "article_no", row["_source"],
                        raw=code, repaired=None,
                        message="digits lost to float precision; not recoverable from "
                                "this cell",
                        stock=str(row["aantal"]),
                        hint="match against the master file on EAN before accepting")
            continue
        if code not in master_keys:
            continue
        ean_value, ean_status = ean_fix(row["ean"])
        if ean_status == "padded":
            ctx.finding("R-VII-02", "article", code, "ean", row["_source"],
                        raw=row["ean"], repaired=ean_value,
                        message="leading zero restored and confirmed by the check digit")
        elif ean_status == "bad_check":
            ctx.finding("R-VII-02", "article", code, "ean", row["_source"],
                        raw=row["ean"], repaired=None,
                        message="padding does not satisfy the check digit")

    # ── formula errors in the article master ─────────────────────────────
    art_master = ctx.norm["art_master"]
    for _, row in art_master.iterrows():
        for col in ("AANKOOP", "VERKOOP", "BTW"):
            if str(row[col]).strip().upper() in FORMULA_ERRORS:
                ctx.finding("R-VII-05", "article", str(row["ARTIKELNR"]), col.lower(),
                            row["_source"], raw=row[col],
                            message="the cell never held a value")

    # ── dates ────────────────────────────────────────────────────────────
    # Each field gets a parsed column beside the raw one, in ISO. The raw value
    # stays so the finding remains auditable; the parsed value is what Paradiso
    # exports, because a load file carrying 45966 in a date column is not clean,
    # it is merely unreported.
    items = ctx.candidates["open_item"]
    for fieldname in ("doc_date", "due_date"):
        fmt, evidence = infer_date_format(items[fieldname].astype(str).tolist())
        ctx.stats[f"date_format_{fieldname}"] = {"verdict": fmt, "evidence": dict(evidence)}
        parsed: list[str | None] = []
        for _, row in items.iterrows():
            raw = row[fieldname]
            value, status = parse_date(raw)
            key = str(row["key"])
            iso = value.isoformat() if value else None
            if status == "serial":
                ctx.finding("R-VII-03", "open_item", key, fieldname, row["_source"],
                            raw=raw, repaired=iso,
                            message="Excel serial number converted back to a date")
            elif status == "ambiguous":
                if fmt == "mixed":
                    iso = None  # held, so nothing is written to the target
                    ctx.finding("R-VII-04", "open_item", key, fieldname, row["_source"],
                                raw=raw, repaired=None,
                                message="this file proves both readings, so neither "
                                        "can be assumed",
                                european=_read(raw, "dmy"), american=_read(raw, "mdy"),
                                evidence=dict(evidence))
                else:
                    iso = _read(raw, fmt if fmt != "unknown" else "dmy")
                    ctx.finding("R-VII-03", "open_item", key, fieldname, row["_source"],
                                raw=raw, repaired=iso,
                                message=f"read as {fmt} on {sum(evidence.values())} "
                                        "unambiguous rows in the same file")
            elif status == "unparseable" and str(raw).strip():
                ctx.finding("R-VII-05", "open_item", key, fieldname, row["_source"], raw=raw,
                            message="not a date in any reading")
            parsed.append(iso)
        items[f"{fieldname}_parsed"] = parsed
    ctx.candidates["open_item"] = items

    # dates in the customer master
    customers = ctx.candidates["customer"]
    created_parsed: list[str | None] = []
    for idx, row in customers.iterrows():
        raw = row.get("created")
        if raw in (None, "", "nan", "None"):
            created_parsed.append(None)
            continue
        value, status = parse_date(raw)
        if status == "serial":
            ctx.finding("R-VII-03", "customer", _key(customers, idx), "created",
                        row["_source"], raw=raw,
                        repaired=value.isoformat() if value else None,
                        message="Excel serial number converted back to a date")
        created_parsed.append(value.isoformat() if value else None)
    customers["created_parsed"] = created_parsed
    ctx.candidates["customer"] = customers


def _read(raw: object, fmt: str) -> str | None:
    m = _DMY.fullmatch(str(raw).strip())
    if not m:
        return None
    a, b, y = (int(x) for x in m.groups())
    day, month = (a, b) if fmt == "dmy" else (b, a)
    try:
        from datetime import date
        return date(y, month, day).isoformat()
    except ValueError:
        return None


def _key(df, idx: int) -> str:
    k = str(df.at[idx, "key"] or "").strip()
    return k if k and k != "None" else f"{df.at[idx, '_feed']}#{df.at[idx, '_row']}"
