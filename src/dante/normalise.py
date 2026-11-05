"""Circle I, and the value parsers every circle below it depends on.

These functions are deliberately boring and deliberately strict. Each one
either returns a value it can defend or admits it cannot parse the input. The
moment a parser starts guessing, the migration starts inventing data, and an
invented value is worse than a rejected one: it loads without complaint.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

EXCEL_EPOCH = date(1899, 12, 30)

INVISIBLES = {
    " ": " ",   # non-breaking space
    " ": " ",   # narrow no-break space
    "​": "",    # zero-width space
    "﻿": "",    # byte order mark
    " ": " ",   # line separator
}

FORMULA_ERRORS = {"#REF!", "#N/B", "#N/A", "#DIV/0!", "#WAARDE!", "#VALUE!",
                  "#NAAM?", "#NAME?", "#NUL!", "#GETAL!", "#NUM!", "#LEEG!"}

SENTINEL_DATES = {"01/01/1900", "1900-01-01", "1899-12-30", "30/12/1899",
                  "9999-12-31", "31/12/9999", "01-01-1900"}

PLACEHOLDER_EMAILS = {"noreply@noreply.be", "geen@geen.be", "x@x.x", "/", "-",
                      "nvt", "geen", "noreply@", "test@test.be"}
PLACEHOLDER_PHONES = {"000000000", "0000000000", "/", "-", "0", "nvt", "geen", "00000"}
PLACEHOLDER_VAT = {"BE0000000000", "BE9999999999", "BE1111111111", "BE0123456749"}
SCRATCH_NAMES = re.compile(
    r"^(test|tst|proef|dummy|aaa+|zzz+|xxx+|klant nieuw|nieuwe klant|niet gebruiken)\b"
    r"|niet gebruiken|^zzz|test leverancier",
    re.IGNORECASE,
)

ISO_COUNTRIES = {"BE", "NL", "FR", "DE", "LU", "GB", "IT", "ES", "PL", "AT", "DK", "SE"}
COUNTRY_RECOVERY = {"BELGIE": "BE", "BELGIË": "BE", "BELG": "BE", "BELGIUM": "BE",
                    "NEDERLAND": "NL", "FRANKRIJK": "FR", "DUITSLAND": "DE"}

_SCI = re.compile(r"^-?\d(?:[.,]\d+)?E\+?\d+$", re.IGNORECASE)
_VAT_IN_TEXT = re.compile(r"\b(BE\s?0?\d{9,10})\b", re.IGNORECASE)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_BE_POSTCODE_CITY = re.compile(r"[,;]?\s*(\d{4})\s+([A-Za-zÀ-ÿ'’\-\. ]{2,40})$")
_HOUSE_BOX = re.compile(
    r"^(?P<nr>\d+[A-Za-z]?)\s*(?:/|bus|bs|b|box)\s*(?P<box>[0-9A-Za-z]{1,5})$",
    re.IGNORECASE,
)


# ── circle I · the unbaptised ────────────────────────────────────────────
def fix_mojibake(s: str) -> tuple[str, bool]:
    """UTF-8 bytes that were read as latin-1. Reversible, so safe to repair.

    Repaired run by run rather than string by string. A whole-string round trip
    fails as soon as one byte in the string is not part of a UTF-8 sequence, and
    a stray non-breaking space is exactly such a byte. Doing it per run means a
    name carrying both kinds of damage still gets its accents back, instead of
    silently keeping them because of a space three characters away.
    """
    if not any(m in s for m in ("Ã", "Â", "â", "Å", "Ä")):
        return s, False
    out = _MOJI_RUN.sub(_decode_run, s)
    return (out, True) if out != s else (s, False)


_MOJI_RUN = re.compile(r"[\u00c2-\u00f4][\u0080-\u00bf]+")


def _decode_run(m: re.Match[str]) -> str:
    try:
        return m.group(0).encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return m.group(0)


def strip_invisibles(s: str) -> tuple[str, bool]:
    out = s
    for bad, good in INVISIBLES.items():
        out = out.replace(bad, good)
    return out, out != s


def collapse_ws(s: str) -> tuple[str, bool]:
    out = re.sub(r"\s+", " ", s).strip()
    return out, out != s


def norm_code(s: str) -> str:
    """Entity codes are matched on this form, never on what the user typed."""
    return re.sub(r"[\s ]+", "", str(s)).upper().replace("_", "-")


def norm_name(s: str) -> str:
    """A comparison key for matching. Never written to the target."""
    s = s.lower()
    s = re.sub(r"\b(bvba|b\.v\.b\.a\.|nv|n\.v\.|bv|b\.v\.|comm\.v|commv|vof|srl|sa)\b", " ", s)
    s = s.replace("&", " en ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# ── money ────────────────────────────────────────────────────────────────
def parse_money(raw: str) -> tuple[Decimal | None, str]:
    """Returns (amount, status). status is ok, empty, formula_error or unparseable.

    Separator order decides the decimal mark, never the locale. "1.247,50" and
    "1,247.50" are both 1247.50; whichever mark sits furthest right is the
    decimal one.
    """
    if raw is None:
        return None, "empty"
    s = str(raw)
    s, _ = strip_invisibles(s)
    s = s.strip()
    if not s:
        return None, "empty"
    if s.upper() in FORMULA_ERRORS:
        return None, "formula_error"

    neg = s.startswith("-") or s.endswith("-") or (s.startswith("(") and s.endswith(")"))
    s = re.sub(r"(?i)(eur|euro|€|bef|\(|\)|-)", "", s).strip()
    s = s.replace(" ", "")
    if not s or not re.search(r"\d", s):
        return None, "unparseable"
    if not re.fullmatch(r"[\d.,]+", s):
        return None, "unparseable"

    last_comma, last_dot = s.rfind(","), s.rfind(".")
    if last_comma >= 0 and last_dot >= 0:
        dec = "," if last_comma > last_dot else "."
        thou = "." if dec == "," else ","
        s = s.replace(thou, "").replace(dec, ".")
    elif last_comma >= 0:
        s = s.replace(",", ".") if len(s) - last_comma - 1 in (1, 2) else s.replace(",", "")
    elif last_dot >= 0 and len(s) - last_dot - 1 == 3 and s.count(".") == 1:
        s = s.replace(".", "")  # 1.247 is a thousand separator in this dataset
    try:
        value = Decimal(s)
    except InvalidOperation:
        return None, "unparseable"
    return (-value if neg else value), "ok"


# ── dates ────────────────────────────────────────────────────────────────
def parse_date(raw: str) -> tuple[date | None, str]:
    """Returns (value, status): ok, empty, sentinel, serial, ambiguous, unparseable.

    ambiguous means the string is a valid date under both the European and the
    US reading and the two disagree. The engine refuses to pick.
    """
    if raw is None:
        return None, "empty"
    s, _ = strip_invisibles(str(raw))
    s = s.strip()
    if not s:
        return None, "empty"
    if s in SENTINEL_DATES:
        return None, "sentinel"
    if s.upper() in FORMULA_ERRORS:
        return None, "unparseable"

    if re.fullmatch(r"\d{4,5}", s):  # an Excel serial number
        try:
            return EXCEL_EPOCH + timedelta(days=int(s)), "serial"
        except (OverflowError, ValueError):
            return None, "unparseable"

    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return (_safe(y, mo, d), "ok") if _safe(y, mo, d) else (None, "unparseable")

    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", s)
    if m:
        a, b, y = (int(x) for x in m.groups())
        eu, us = _safe(y, b, a), _safe(y, a, b)
        if eu and us and eu != us:
            return eu, "ambiguous"
        if eu:
            return eu, "ok"
        if us:
            return us, "ok"
    return None, "unparseable"


def _safe(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


# ── identifiers ──────────────────────────────────────────────────────────
def vat_status(raw: str) -> tuple[str | None, str]:
    """Returns (normalised, status): ok, empty, placeholder, bad_checksum, malformed."""
    if raw is None:
        return None, "empty"
    s = re.sub(r"[\s.\-]", "", str(raw)).upper()
    if not s:
        return None, "empty"
    if not s.startswith("BE"):
        s = "BE" + s if s.isdigit() else s
    if not re.fullmatch(r"BE\d{9,10}", s):
        return s, "malformed"
    digits = s[2:].zfill(10)
    s = "BE" + digits
    if s in PLACEHOLDER_VAT or digits == digits[0] * 10:
        return s, "placeholder"
    body, check = digits[:8], int(digits[8:])
    return (s, "ok") if 97 - (int(body) % 97) == check else (s, "bad_checksum")


def extract_vat(text: str) -> str | None:
    m = _VAT_IN_TEXT.search(text or "")
    if not m:
        return None
    cand, status = vat_status(m.group(1))
    return cand if status in ("ok", "placeholder") else None


def ean_fix(raw: str) -> tuple[str | None, str]:
    """Returns (ean13, status): ok, padded, empty, bad_check, malformed.

    A stripped leading zero is recoverable because the length is fixed and the
    check digit confirms the result. Nothing else about an EAN is guessable.
    """
    if raw is None:
        return None, "empty"
    s = re.sub(r"\D", "", str(raw))
    if not s:
        return None, "empty"
    if len(s) == 13:
        return (s, "ok") if _ean_ok(s) else (s, "bad_check")
    if len(s) < 13:
        padded = s.zfill(13)
        return (padded, "padded") if _ean_ok(padded) else (s, "bad_check")
    return s, "malformed"


def _ean_ok(s: str) -> bool:
    body, check = s[:12], int(s[12])
    total = sum(int(c) * (3 if i % 2 else 1) for i, c in enumerate(body))
    return (10 - total % 10) % 10 == check


def is_scientific(raw: str) -> bool:
    return bool(_SCI.fullmatch(str(raw).strip()))


def email_status(raw: str) -> tuple[str | None, str]:
    """Returns (primary, status): ok, empty, placeholder, multi, malformed."""
    if raw is None:
        return None, "empty"
    s, _ = strip_invisibles(str(raw))
    s = s.strip()
    if not s:
        return None, "empty"
    if s.lower() in PLACEHOLDER_EMAILS:
        return None, "placeholder"
    parts = [p.strip() for p in re.split(r"[;,/]| en ", s) if p.strip()]
    if len(parts) > 1:
        return (parts[0], "multi") if _EMAIL.fullmatch(parts[0]) else (parts[0], "malformed")
    return (s, "ok") if _EMAIL.fullmatch(s) else (s, "malformed")


def phone_status(raw: str) -> tuple[str | None, str]:
    s, _ = strip_invisibles(str(raw or ""))
    s = s.strip()
    if not s:
        return None, "empty"
    if s.lower() in PLACEHOLDER_PHONES:
        return None, "placeholder"
    digits = re.sub(r"\D", "", s)
    if len(set(digits)) <= 1:
        return None, "placeholder"
    return (digits, "ok") if 8 <= len(digits) <= 13 else (s, "malformed")


def country_status(raw: str) -> tuple[str | None, str]:
    s = str(raw or "").strip().upper()
    if not s:
        return None, "empty"
    if s in ISO_COUNTRIES:
        return s, "ok"
    if s in COUNTRY_RECOVERY:
        return COUNTRY_RECOVERY[s], "recoverable"
    return s, "unknown"


# ── addresses ────────────────────────────────────────────────────────────
def split_address(raw: str) -> dict[str, str | None]:
    """Pull street, number, box, postcode and city out of one overstuffed cell.

    Returns status=unparseable rather than a guess when the cell holds a
    delivery instruction instead of an address, which happens more than anyone
    would like.
    """
    out: dict[str, str | None] = {"street": None, "house_no": None, "box": None,
                                  "postcode": None, "city": None, "status": "ok"}
    s, _ = strip_invisibles(str(raw or ""))
    s, _ = collapse_ws(s)
    if not s:
        out["status"] = "empty"
        return out

    m = _BE_POSTCODE_CITY.search(s)
    if m:
        pc = int(m.group(1))
        if 1000 <= pc <= 9999:
            out["postcode"] = str(pc)
            out["city"] = m.group(2).strip(" ,.")
            s = s[: m.start()].strip(" ,;")

    m = re.search(r"^(?P<street>.*?)\s+(?P<tail>\d+\s*(?:[A-Za-z]|/\s*\w+|bus\s*\w+|b\s*\d+)?)$",
                  s, re.IGNORECASE)
    if not m:
        if not out["postcode"] and not re.search(r"\d", s):
            out["status"] = "unparseable" if len(s.split()) > 3 or _looks_like_prose(s) else "ok"
            out["street"] = s or None
            return out
        out["street"] = s or None
        return out

    out["street"] = m.group("street").strip(" ,") or None
    tail = m.group("tail").strip()
    hb = _HOUSE_BOX.fullmatch(tail.replace(" ", ""))
    if hb:
        out["house_no"], out["box"] = hb.group("nr"), hb.group("box")
    else:
        out["house_no"] = tail
    return out


def _looks_like_prose(s: str) -> bool:
    prose = ("bellen", "zie ", "zelfde", "volgt", "achter", "werf", "afspraak", "nvt",
             "onbekend", "poort")
    return any(p in s.lower() for p in prose)
