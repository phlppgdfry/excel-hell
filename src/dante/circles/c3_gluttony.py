"""III · Gluttony — one cell, swallowing everything.

A single column holding a street, a box number, a postcode, a VAT number and
two email addresses. The legacy system had no field for it, so the users made
one. Splitting it back apart is mostly deterministic, and the engine stops the
moment it would have to guess: "achter de kerk, bellen bij de poort" is a real
delivery instruction, and inventing a street for it would be worse than
admitting it cannot be parsed.
"""

from __future__ import annotations

from ..normalise import email_status, extract_vat, split_address, vat_status
from ..pipeline import Context


def run(ctx: Context) -> None:
    for entity in ("customer", "supplier"):
        df = ctx.candidates[entity]
        for idx, row in df.iterrows():
            key = _key(df, idx)
            source = row["_source"]

            # ── address, all in one cell ──────────────────────────────────
            raw_addr = str(row.get("address_raw") or "").strip()
            if not raw_addr and entity == "supplier":
                street = str(row.get("street") or "")
                raw_addr = street if ("," in street or _has_postcode(street)) else ""
            if raw_addr and raw_addr not in ("None", "nan"):
                parts = split_address(raw_addr)
                if parts["status"] == "unparseable":
                    ctx.finding("R-III-04", entity, key, "address", source,
                                raw=raw_addr, repaired=None,
                                message="a delivery instruction, not an address")
                else:
                    if parts["postcode"]:
                        ctx.finding("R-III-01", entity, key, "address", source,
                                    raw=raw_addr,
                                    repaired=f"{parts['street']} {parts['house_no'] or ''}"
                                             f" | {parts['postcode']} {parts['city']}",
                                    message="postcode and city split off the street field",
                                    **{k: v for k, v in parts.items() if k != "status"})
                        df.at[idx, "postcode"] = row.get("postcode") or parts["postcode"]
                        df.at[idx, "city"] = row.get("city") or parts["city"]
                    if parts["box"]:
                        ctx.finding("R-III-02", entity, key, "house_no", source,
                                    raw=raw_addr,
                                    repaired=f"nr {parts['house_no']} / bus {parts['box']}",
                                    message="box number separated from the house number")
                        df.at[idx, "box"] = parts["box"] if "box" in df.columns else None
                    df.at[idx, "street"] = parts["street"]
                    df.at[idx, "house_no"] = parts["house_no"]

            # ── several addresses in one email cell ───────────────────────
            primary, status = email_status(row.get("email"))
            if status == "multi":
                ctx.finding("R-III-03", entity, key, "email", source,
                            raw=row.get("email"), repaired=primary,
                            message="first address kept as primary, rest as extra contacts")
                df.at[idx, "email"] = primary

            # ── a VAT number typed into the name ─────────────────────────
            name = str(row.get("name") or "")
            _, vstat = vat_status(row.get("vat"))
            if vstat in ("empty", "malformed"):
                found = extract_vat(name)
                if found:
                    cleaned = _strip_vat(name, found)
                    ctx.finding("R-III-05", entity, key, "vat", source,
                                raw=name, repaired=f"{cleaned} | {found}",
                                message="VAT number recovered from the name field")
                    df.at[idx, "vat"] = found
                    df.at[idx, "name"] = cleaned
        ctx.candidates[entity] = df


def _has_postcode(s: str) -> bool:
    import re
    return bool(re.search(r"\b\d{4}\b", s))


def _strip_vat(name: str, vat: str) -> str:
    import re
    out = re.sub(r"\(?\s*BE\s?0?\d{9,10}\s*\)?", "", name, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", out).strip(" ()-")


def _key(df, idx: int) -> str:
    k = str(df.at[idx, "key"] or "").strip()
    return k if k and k != "None" else f"{df.at[idx, '_feed']}#{df.at[idx, '_row']}"
