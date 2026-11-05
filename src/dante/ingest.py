"""Reading twelve files that were never meant to be read by a machine.

Three of them have a merged title cell above the header. One is latin-1. One
carries a BOM. One stores the same entity under a different column name. The
header row is found by anchor rather than by position, because the position is
whatever the last person to edit the file left behind.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from .errors import MissingSources


def read_csv_smart(path: Path, encoding: str, sep: str = ";") -> pd.DataFrame:
    df = pd.read_csv(path, sep=sep, dtype=str, encoding=encoding,
                     keep_default_na=False, na_values=[])
    # R-I-04 · strip a BOM off the first column name so it is addressable again
    df.columns = [c.lstrip("﻿").strip() for c in df.columns]
    df["_source"] = path.name
    df["_row"] = range(2, len(df) + 2)
    return df


def read_excel_smart(path: Path, sheet: str, anchor: str) -> pd.DataFrame:
    """Find the header row by looking for a column we know must be there."""
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    rows = [[("" if c is None else c) for c in r] for r in ws.iter_rows(values_only=True)]
    wb.close()

    header_idx = None
    for i, row in enumerate(rows[:25]):
        if any(str(c).strip().lower() == anchor.lower() for c in row):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"{path.name}!{sheet}: no header row containing {anchor!r}")

    header = [str(c).strip() for c in rows[header_idx]]
    width = len([h for h in header if h])
    header = header[:width]
    body = [r[:width] for r in rows[header_idx + 1:] if any(str(c).strip() for c in r[:width])]
    df = pd.DataFrame(body, columns=header).astype(str)
    df["_source"] = f"{path.name}!{sheet}"
    df["_row"] = range(header_idx + 2, header_idx + 2 + len(df))
    df["_header_row"] = header_idx + 1
    return df


EXPECTED_FILES = [
    "01_klanten_mercurius.csv", "02_klanten_verkoop_jan.xlsx",
    "03_klanten_verkoop_sofie.xlsx", "04_klanten_boekhouding.csv",
    "05_artikelen_mercurius.csv", "06_artikelen_prijzen_2024.xlsx",
    "07_artikelen_voorraad.xlsx", "08_artikelen_eenheden.xlsx",
    "09_artikelen_leverancier.xlsx", "10_leveranciers.xlsx",
    "11_openstaande_posten.xlsx", "12_korting_afspraken.xlsx",
]


def load_sources(raw: Path) -> dict[str, pd.DataFrame]:
    """Every source file, under the name the pipeline knows it by.

    Checked up front and reported together: finding out about one missing file
    per run, twelve times, is a worse morning than being told all twelve now.
    """
    missing = [f for f in EXPECTED_FILES if not (raw / f).exists()]
    if missing:
        raise MissingSources(raw, missing)

    s: dict[str, pd.DataFrame] = {}
    s["cust_master"] = read_csv_smart(raw / "01_klanten_mercurius.csv", "utf-8-sig")
    s["cust_jan"] = read_excel_smart(raw / "02_klanten_verkoop_jan.xlsx", "Blad1", "klant")
    s["cust_sofie"] = read_excel_smart(raw / "03_klanten_verkoop_sofie.xlsx", "klanten", "Bedrijf")
    s["cust_acc"] = read_csv_smart(raw / "04_klanten_boekhouding.csv", "latin-1")
    s["art_master"] = read_csv_smart(raw / "05_artikelen_mercurius.csv", "utf-8")
    s["art_price"] = read_excel_smart(raw / "06_artikelen_prijzen_2024.xlsx",
                                      "prijzen 2024", "artikel")
    s["art_stock"] = read_excel_smart(raw / "07_artikelen_voorraad.xlsx", "voorraad", "artikelnr")
    s["art_uom"] = read_excel_smart(raw / "08_artikelen_eenheden.xlsx", "eenheden", "artikel")
    s["art_supp"] = read_excel_smart(raw / "09_artikelen_leverancier.xlsx",
                                     "leverancier", "artikel")
    s["supp_master"] = read_excel_smart(raw / "10_leveranciers.xlsx", "leveranciers", "levnr")
    s["open_items"] = read_excel_smart(raw / "11_openstaande_posten.xlsx", "Posten", "stuknr")
    s["trial_balance"] = read_excel_smart(raw / "11_openstaande_posten.xlsx",
                                          "Saldilijst", "klantnr")
    s["discounts"] = read_excel_smart(raw / "12_korting_afspraken.xlsx", "afspraken", "afspraak")
    return s
