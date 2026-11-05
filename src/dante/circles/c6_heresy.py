"""VI · Heresy — values that pass every format check and are still false.

BE0000000000 satisfies the modulo-97 check. 1900-01-01 is a valid date.
noreply@noreply.be is a valid address. "TEST" is a valid company name. None of
them identifies anything, and all of them will load into the new ERP without a
single warning. That is what makes them heretics rather than sinners: they look
exactly like believers, and a schema validator will defend them.

The split here is between absence and falsehood. A placeholder that stands in
for "unknown" becomes null, which is what it always meant. A placeholder that
stands in for a real identifier cannot be migrated at all.
"""

from __future__ import annotations

import re

from ..normalise import (
    SCRATCH_NAMES,
    country_status,
    email_status,
    parse_date,
    phone_status,
    vat_status,
)
from ..pipeline import Context


def run(ctx: Context) -> None:
    for entity in ("customer", "supplier"):
        df = ctx.candidates[entity]
        for idx, row in df.iterrows():
            key = _key(df, idx)
            source = row["_source"]

            value, status = vat_status(row.get("vat"))
            if status == "placeholder":
                ctx.finding("R-VI-01", entity, key, "vat", source, raw=row.get("vat"),
                            message="structurally valid, identifies nobody")
            elif status == "bad_checksum":
                ctx.finding("R-VI-01", entity, key, "vat", source, raw=row.get("vat"),
                            message="fails the modulo-97 check")

            name = str(row.get("name") or "").strip()
            if name and SCRATCH_NAMES.search(name):
                ctx.finding("R-VI-04", entity, key, "name", source, raw=name,
                            message="a working note with order history behind it")

            _, estatus = email_status(row.get("email"))
            if estatus == "placeholder":
                ctx.finding("R-VI-03", entity, key, "email", source, raw=row.get("email"),
                            repaired=None, message="absence written as presence")
            _, pstatus = phone_status(row.get("phone"))
            if pstatus == "placeholder":
                ctx.finding("R-VI-03", entity, key, "phone", source, raw=row.get("phone"),
                            repaired=None, message="absence written as presence")

            country = row.get("country")
            if country not in (None, "", "nan", "None"):
                cvalue, cstatus = country_status(country)
                if cstatus == "recoverable":
                    ctx.finding("R-VI-05", entity, key, "country", source, raw=country,
                                repaired=cvalue, message="recoverable, but ask anyway")
                elif cstatus == "unknown":
                    ctx.finding("R-VI-05", entity, key, "country", source, raw=country,
                                repaired=None,
                                message='"B" is a legacy code for Belgium and a valid '
                                        "code for nothing")

            created = row.get("created")
            if created not in (None, "", "nan", "None"):
                _, dstatus = parse_date(created)
                if dstatus == "sentinel":
                    ctx.finding("R-VI-02", entity, key, "created", source, raw=created,
                                repaired=None, message="the legacy system's way of saying null")

    # scratch records in the article master too
    for _, row in ctx.candidates["article"].iterrows():
        desc = str(row.get("description") or "")
        if desc and SCRATCH_NAMES.search(desc):
            ctx.finding("R-VI-04", "article", str(row["key"]), "description",
                        row["_source"], raw=desc, message="scratch record in the master")

    # sentinel due dates on receivables
    for _, row in ctx.candidates["open_item"].iterrows():
        for fieldname in ("doc_date", "due_date"):
            _, status = parse_date(row.get(fieldname))
            if status == "sentinel":
                ctx.finding("R-VI-02", "open_item", str(row["key"]), fieldname,
                            row["_source"], raw=row.get(fieldname), repaired=None,
                            message="a receivable with no real due date")


def _key(df, idx: int) -> str:
    k = str(df.at[idx, "key"] or "").strip()
    return k if k and k != "None" else f"{df.at[idx, '_feed']}#{df.at[idx, '_row']}"


_ = re
