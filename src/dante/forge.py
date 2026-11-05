"""The forge: turns the clean world into the twelve source files it really is.

Twelve files, four of which describe customers and none of which agree. This is
not a caricature. Every defect class here was chosen because it is the kind of
thing that survives twenty years of an ERP nobody dares to replace: a sales rep
with their own spreadsheet, an export in the wrong encoding, a postcode that
lost its leading zero the first time someone opened the file in Excel.

The forge records every defect it plants in data/truth/planted-defects.json.
The pipeline never reads that file. The test suite does, to measure how much of
the filth the engine actually catches.
"""

from __future__ import annotations

import csv
import json
import random
from datetime import date
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from .world import CLIENT, LEGACY_SYSTEM, World, build_world

EXCEL_EPOCH = date(1899, 12, 30)
MOJIBAKE = {"é": "Ã©", "ë": "Ã«", "ï": "Ã¯", "è": "Ã¨", "ö": "Ã¶", "ü": "Ã¼"}


class Forge:
    def __init__(self, world: World, out: Path, seed: int = 1987) -> None:
        self.w = world
        self.out = out
        self.rng = random.Random(seed)
        self.defects: list[dict[str, Any]] = []
        self.compensating_delta = 0.0

    # ── bookkeeping ──────────────────────────────────────────────────────
    def plant(self, rule: str, file: str, key: str, field: str, planted: Any,
              truth: Any = None, note: str = "", engine_key: str | None = None) -> None:
        """Record a defect, and how the engine will be able to address the row.

        Two of the twelve files carry no customer number at all, so the only
        address the engine has for those rows is feed#row. Recording that next
        to the real key is what makes recall measurable on them instead of
        merely plausible.
        """
        self.defects.append({
            "rule": rule, "file": file, "key": str(key), "field": field,
            "engine_key": engine_key or str(key),
            "planted": str(planted)[:120],
            "truth": None if truth is None else str(truth)[:120],
            "note": note,
        })

    def _plant_money(self, file: str, key: str, field: str, written: str,
                     truth: float) -> None:
        """Label the amount by what is actually wrong with it, not by both."""
        if any(t in str(written).lower() for t in ("€", "eur")):
            self.plant("R-IV-02", file, key, field, written, truth)
        elif "," in str(written) or "\u00a0" in str(written):
            self.plant("R-IV-01", file, key, field, written, truth)

    def chance(self, p: float) -> bool:
        return self.rng.random() < p

    # ── helpers ──────────────────────────────────────────────────────────
    def mojibake(self, s: str) -> str:
        for k, v in MOJIBAKE.items():
            s = s.replace(k, v)
        return s

    def scramble_name(self, name: str) -> str:
        """How the same company gets written down by three different people."""
        style = self.rng.randrange(6)
        if style == 0:
            return name.upper()
        if style == 1:
            return name.replace("bvba", "b.v.b.a.").replace("nv", "n.v.")
        if style == 2:
            return name.replace(" & Zonen", " en Zonen")
        if style == 3:
            head = name.split()[0]
            return f"{head} {name.split()[-1]}" if len(name.split()) > 2 else head
        if style == 4:
            # one transposed character: the classic manual-entry typo
            parts = list(name)
            i = self.rng.randrange(1, max(2, len(parts) - 2))
            parts[i], parts[i + 1] = parts[i + 1], parts[i]
            return "".join(parts)
        return name.lower()

    def excel_serial(self, d: date) -> int:
        return (d - EXCEL_EPOCH).days

    def money_text(self, v: float) -> str:
        """One amount, written the five ways users actually write it."""
        style = self.rng.randrange(5)
        if style == 0:
            return f"{v:,.2f}".replace(",", " ").replace(".", ",")
        if style == 1:  # Belgian convention: dot for thousands, comma for decimals
            return "€ " + f"{v:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
        if style == 2:
            return f"EUR {v:.2f}".replace(".", ",")
        if style == 3:
            return f"{v:.2f}".replace(".", ",")
        return f"{v:.2f}"

    def _sheet(self, wb: Workbook, title: str, header_note: str, columns: list[str],
               junk_rows: int = 0) -> Any:
        fresh = wb.active.max_row == 1 and wb.active.max_column == 1
        ws = wb.active if fresh else wb.create_sheet()
        ws.title = title
        if junk_rows:
            ws["A1"] = header_note
            ws["A1"].font = Font(bold=True, size=14)
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(4, len(columns)))
            ws["A2"] = f"Export {LEGACY_SYSTEM} — niet wijzigen aub"
            for _ in range(junk_rows - 2):
                ws.append([])
        ws.append(columns)
        for i, _ in enumerate(columns, start=1):
            ws.column_dimensions[get_column_letter(i)].width = 22
        return ws

    # ── 01 · customer master, straight out of Mercurius ──────────────────
    def file_01_customers_master(self) -> None:
        name = "01_klanten_mercurius.csv"
        path = self.out / name
        rows = []
        test_names = ["TEST", "ZZZ OUD - NIET GEBRUIKEN", "KLANT NIEUW", "aaa", "proefklant"]
        for idx, c in enumerate(self.w.customers):
            cust_no, cname = c.cust_no, c.name
            vat, email, phone = c.vat, c.email, c.phone
            country, postcode = c.country, str(c.postcode)
            created: Any = c.created.isoformat()

            if self.chance(0.06):  # R-I-05 · codes in mixed case, with spaces
                cust_no = cust_no.lower().replace("k", "k ")
                self.plant("R-I-05", name, c.cust_no, "KLANTNR", cust_no, c.cust_no)
            if self.chance(0.012):  # R-VI-01 · placeholder VAT
                vat = self.rng.choice(["BE0000000000", "BE9999999999", "BE0123456749"])
                self.plant("R-VI-01", name, c.cust_no, "BTWNR", vat, c.vat)
            if self.chance(0.03):  # R-VI-02 · sentinel dates
                created = self.rng.choice(["01/01/1900", "1899-12-30", "9999-12-31"])
                self.plant("R-VI-02", name, c.cust_no, "AANGEMAAKT", created, c.created)
            elif self.chance(0.05):  # R-VII-03 · date as Excel serial
                created = str(self.excel_serial(c.created))
                self.plant("R-VII-03", name, c.cust_no, "AANGEMAAKT", created, c.created)
            if idx % 173 == 7:  # R-VI-04 · scratch records nobody dared delete
                cname = self.rng.choice(test_names)
                self.plant("R-VI-04", name, c.cust_no, "NAAM", cname, c.name)
            if self.chance(0.015):  # R-VI-05 · country code outside ISO
                country = self.rng.choice(["XX", "B", "BELG", "Belgie"])
                self.plant("R-VI-05", name, c.cust_no, "LAND", country, c.country)
            if self.chance(0.02):  # R-VI-03 · absence written as presence
                email = self.rng.choice(["noreply@noreply.be", "geen@geen.be", "/", "x@x.x"])
                self.plant("R-VI-03", name, c.cust_no, "EMAIL", email, c.email)
            if self.chance(0.02):
                phone = self.rng.choice(["000000000", "/", "0", "nvt"])
                self.plant("R-VI-03", name, c.cust_no, "TEL", phone, c.phone)
            if self.chance(0.02):  # R-III-05 · VAT typed into the name field
                cname = f"{cname} ({c.vat})"
                vat = ""
                self.plant("R-III-05", name, c.cust_no, "NAAM", cname, c.vat)

            rows.append({
                "KLANTNR": cust_no, "NAAM": cname, "STRAAT": c.street, "NR": c.house_no,
                "BUS": c.box, "POSTCODE": postcode, "GEMEENTE": c.city, "LAND": country,
                "BTWNR": vat, "EMAIL": email, "TEL": phone,
                "BETAALTERMIJN": c.payment_terms, "KREDIETLIMIET": c.credit_limit,
                "AANGEMAAKT": created, "GEBLOKKEERD": "J" if c.blocked else "N",
            })

        # R-I-04 · the export writes a BOM, so the first column is unaddressable
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        self.plant("R-I-04", name, "<header>", "KLANTNR", "\\ufeffKLANTNR", "KLANTNR")

    # ── 02 · the sales rep who kept his own list ─────────────────────────
    def file_02_customers_jan(self) -> None:
        name = "02_klanten_verkoop_jan.xlsx"
        wb = Workbook()
        ws = self._sheet(wb, "Blad1", "Klantenlijst Jan — bijgehouden sinds 2011",
                         ["klant", "adres volledig", "tel", "mail", "opmerking"], junk_rows=4)
        sample = self.rng.sample(self.w.customers, 310)
        for c in sample:
            ek = f"cust_jan#{ws.max_row + 1}"
            cname = self.scramble_name(c.name) if self.chance(0.55) else c.name
            if cname != c.name:
                self.plant("R-II-01", name, c.cust_no, "klant", cname, c.name,
                           "same entity, written differently", engine_key=ek)
            # R-III-01 / R-III-02 · everything in one address cell
            box = f" bus {c.box}" if c.box else ""
            addr = f"{c.street} {c.house_no}{box}, {c.postcode} {c.city}"
            self.plant("R-III-01", name, c.cust_no, "adres volledig", addr,
                       f"{c.postcode}|{c.city}", engine_key=ek)
            if c.box:
                self.plant("R-III-02", name, c.cust_no, "adres volledig", addr, c.box,
                           engine_key=ek)
            if self.chance(0.04):  # R-III-04 · a delivery instruction, not an address
                addr = self.rng.choice([
                    "achter de kerk, bellen bij de poort",
                    "werf Izegem - zie Jan",
                    "nieuw adres volgt",
                    "zelfde als facturatie",
                ])
                self.plant("R-III-04", name, c.cust_no, "adres volledig", addr,
                           "unparseable", engine_key=ek)
            ws.append([cname, addr, c.phone, c.email, ""])
        wb.save(self.out / name)

    # ── 03 · the other sales rep, other columns, other truth ────────────
    def file_03_customers_sofie(self) -> None:
        name = "03_klanten_verkoop_sofie.xlsx"
        wb = Workbook()
        ws = self._sheet(wb, "klanten", "Sofie - klanten West",
                         ["Bedrijf", "Straat + nr", "PC", "Plaats", "Contact e-mail",
                          "Btw", "Betaling", "Limiet"], junk_rows=3)
        sample = self.rng.sample(self.w.customers, 260)
        for c in sample:
            ek = f"cust_sofie#{ws.max_row + 1}"
            cname = self.scramble_name(c.name) if self.chance(0.6) else c.name
            if cname != c.name:
                self.plant("R-II-01", name, c.cust_no, "Bedrijf", cname, c.name,
                           engine_key=ek)
            email = c.email
            if self.chance(0.22):  # R-III-03 · several addresses in one cell
                box = self.rng.choice(["bestel", "info", "jan", "sofie"])
                extra = f"{box}@{c.email.split('@')[1]}"
                email = self.rng.choice([f"{c.email}; {extra}", f"{c.email} / {extra}",
                                         f"{c.email}, {extra}"])
                self.plant("R-III-03", name, c.cust_no, "Contact e-mail", email, c.email,
                           engine_key=ek)
            terms, limit = c.payment_terms, c.credit_limit
            if self.chance(0.12):  # R-II-03 · survivorship conflict
                terms = self.rng.choice([t for t in (14, 30, 45, 60, 90) if t != c.payment_terms])
                limit = c.credit_limit * self.rng.choice([2, 2, 4])
                # Reported against the record that survives the merge, which is
                # the master row, not the rep's row that triggered it.
                self.plant("R-II-03", name, c.cust_no, "Betaling/Limiet",
                           f"{terms}/{limit}", f"{c.payment_terms}/{c.credit_limit}",
                           "merge would silently change credit terms")
            ws.append([cname, f"{c.street} {c.house_no}", c.postcode, c.city, email,
                       c.vat, terms, limit])
        # R-II-02 · the grey band: a parent and its subsidiary
        for c in self.rng.sample(self.w.customers, 26):
            head = c.name.split()[0]
            sub = f"{head} {self.rng.choice(['Zonen', 'Projects', 'West', 'Invest'])} bvba"
            ws.append([sub, f"{c.street} {c.house_no}", c.postcode, c.city,
                       f"info@{head.lower()}.be", "", 30, 5000])
            self.plant("R-II-02", name, c.cust_no, "Bedrijf", sub, c.name,
                       "grey band: parent and subsidiary, separate credit limits",
                       engine_key=f"cust_sofie#{ws.max_row}")
        wb.save(self.out / name)

    # ── 04 · the accounting export, in the wrong encoding ───────────────
    def file_04_customers_accounting(self) -> None:
        name = "04_klanten_boekhouding.csv"
        rows = []
        sample = self.rng.sample(self.w.customers, 420)
        for c in sample:
            cname, city = c.name, c.city
            if self.chance(0.3):  # R-I-01 · latin-1 read as UTF-8
                cname = self.mojibake(cname.replace("e", "é", 1))
                city = self.mojibake(city.replace("i", "ï", 1))
                self.plant("R-I-01", name, c.cust_no, "naam", cname, c.name)
            if self.chance(0.25):  # R-I-02 · non-breaking and zero-width space
                cname = cname + " " if self.chance(0.5) else cname.replace(" ", " ", 1)
                self.plant("R-I-02", name, c.cust_no, "naam", repr(cname), c.name)
            if self.chance(0.25):  # R-I-03 · whitespace
                cname = f"  {cname}  ".replace(" b", "  b")
                self.plant("R-I-03", name, c.cust_no, "naam", repr(cname), c.name)
            rows.append([c.cust_no, cname, city, c.vat, f"{c.credit_limit},00"])
        # R-II-04 · one VAT number, two names
        for c in self.rng.sample(sample, 18):
            trade = f"{c.name.split()[0]} {self.rng.choice(['Shop', 'Store', 'Direct'])}"
            rows.append([f"{c.cust_no}B", trade, c.city, c.vat, "0,00"])
            self.plant("R-II-04", name, c.cust_no, "btw", c.vat, c.name,
                       "trading name sharing the legal entity's VAT number")
        with open(self.out / name, "w", encoding="latin-1", newline="", errors="replace") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["klantnr", "naam", "gemeente", "btw", "limiet"])
            w.writerows(rows)

    # ── 05 · article master ──────────────────────────────────────────────
    def file_05_articles_master(self) -> None:
        name = "05_artikelen_mercurius.csv"
        rows = []
        for a in self.w.articles:
            art_no, cost, sales = a.article_no, a.cost_price, a.sales_price
            if self.chance(0.05):  # R-I-05
                art_no = a.article_no.replace("-", " ").lower()
                self.plant("R-I-05", name, a.article_no, "ARTIKELNR", art_no,
                           a.article_no, engine_key=art_no.replace(" ", "").upper())
            cost_s = f"{cost:.2f}".replace(".", ",")  # R-IV-01 · decimal comma
            sales_s = self.money_text(sales)
            self.plant("R-IV-01", name, a.article_no, "AANKOOP", cost_s, cost)
            if self.chance(0.012):  # R-VII-05 · a formula error where a number belongs
                sales_s = self.rng.choice(["#REF!", "#N/B", "#DIV/0!", "#WAARDE!"])
                self.plant("R-VII-05", name, a.article_no, "VERKOOP", sales_s, sales)
            rows.append([art_no, a.description, a.group, a.uom, a.ean, cost_s, sales_s,
                         a.vat_rate, a.supplier_no, "J" if a.sellable else "N"])
        with open(self.out / name, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["ARTIKELNR", "OMSCHRIJVING", "GROEP", "EENHEID", "EAN",
                        "AANKOOP", "VERKOOP", "BTW", "LEVNR", "VERKOOPBAAR"])
            w.writerows(rows)

    # ── 06 · the price list, maintained by hand since 2019 ──────────────
    def file_06_prices(self) -> None:
        name = "06_artikelen_prijzen_2024.xlsx"
        wb = Workbook()
        ws = self._sheet(wb, "prijzen 2024", "Prijslijst 2024 - DEFINITIEF (versie 7)",
                         ["artikel", "prijs", "incl btw?", "btw%", "actie"], junk_rows=4)
        discounted = {d.article_no for d in self.w.discounts}
        for a in self.w.articles:
            price: Any = self.money_text(a.sales_price)
            self._plant_money(name, a.article_no, "prijs", price, a.sales_price)
            incl = ""
            if self.chance(0.61):
                incl = self.rng.choice(["ja", "JA", "x", "1", "nee", "N"])
                if incl.lower() in ("ja", "x", "1") and self.chance(0.35):
                    # R-IV-03 · the "incl" flag contradicts the article VAT rate
                    price = self.money_text(a.sales_price)
                    self.plant("R-IV-03", name, a.article_no, "incl btw?", incl, a.vat_rate,
                               "flag says VAT-inclusive, amount matches the exclusive price")
            if a.article_no in discounted and self.chance(0.22):
                # R-IV-04 · discount already baked into the unit price
                price = self.money_text(round(a.cost_price * 0.88, 2))
                self.plant("R-IV-04", name, a.article_no, "prijs", price, a.sales_price,
                           "price below cost while a discount agreement exists")
            if self.chance(0.01) and a.sellable:  # R-IV-05
                price = self.rng.choice(["0", "0,00", f"-{a.sales_price:.2f}".replace('.', ',')])
                self.plant("R-IV-05", name, a.article_no, "prijs", price, a.sales_price)
            ws.append([a.article_no, price, incl, a.vat_rate, ""])
        wb.save(self.out / name)

    # ── 07 · stock, after a round trip through Excel ────────────────────
    def file_07_stock(self) -> None:
        name = "07_artikelen_voorraad.xlsx"
        wb = Workbook()
        ws = self._sheet(wb, "voorraad", "Voorraadtelling", ["artikelnr", "ean", "aantal"],
                         junk_rows=3)
        for a in self.w.articles:
            art_no: Any = a.article_no
            ean: Any = a.ean
            if self.chance(0.035):  # R-VII-01 · the code became a float
                art_no = f"{float(int(a.ean)):.2E}".replace("E+", "E+")
                self.plant("R-VII-01", name, a.article_no, "artikelnr", art_no, a.article_no,
                           "digits lost to float precision, not recoverable from this cell",
                           engine_key=str(art_no))
            if a.ean.startswith("0") and self.chance(0.75):
                # R-VII-02 · the cell was numeric, so the leading zero is gone.
                # Recoverable: an EAN is fixed-length and carries a check digit.
                ean = str(int(a.ean))
                self.plant("R-VII-02", name, a.article_no, "ean", ean, a.ean)
            ws.append([art_no, ean, a.stock])
        wb.save(self.out / name)

    # ── 08 · units of measure, per warehouse, per opinion ───────────────
    def file_08_units(self) -> None:
        name = "08_artikelen_eenheden.xlsx"
        wb = Workbook()
        ws = self._sheet(wb, "eenheden", "Eenheden magazijn (Patrick)",
                         ["artikel", "eenheid magazijn", "omschrijving magazijn"], junk_rows=3)
        for a in self.w.articles:
            uom = a.uom
            desc = a.description
            if self.chance(0.07):  # R-V-01 · a different unit, and not obviously wrong
                uom = self.rng.choice([u for u in ("ST", "DS", "M", "RL", "PK") if u != a.uom])
                self.plant("R-V-01", name, a.article_no, "eenheid magazijn", uom, a.uom,
                           "warehouse is the most accurate and the least authoritative source")
            if self.chance(0.3):  # R-V-02 · a different description, nobody cares
                desc = a.description.upper()[:24] + self.rng.choice([" (OUD)", " 2", ""])
                self.plant("R-V-02", name, a.article_no, "omschrijving magazijn", desc,
                           a.description)
            ws.append([a.article_no, uom, desc])
        wb.save(self.out / name)

    # ── 09 · who we actually buy it from ────────────────────────────────
    def file_09_article_supplier(self) -> None:
        name = "09_artikelen_leverancier.xlsx"
        wb = Workbook()
        ws = self._sheet(wb, "leverancier", "Hoofdleverancier per artikel",
                         ["artikel", "leverancier", "laatste aankoop"], junk_rows=3)
        blocked = [s.supp_no for s in self.w.suppliers if s.blocked]
        for a in self.w.articles:
            supp = a.supplier_no
            if self.chance(0.045):  # R-V-03 · a different primary supplier
                supp = self.rng.choice([s.supp_no for s in self.w.suppliers
                                        if s.supp_no != a.supplier_no])
                self.plant("R-V-03", name, a.article_no, "leverancier", supp, a.supplier_no,
                           "purchasing orders from this field")
            elif self.chance(0.025):  # R-VIII-02 · a supplier that is not in the master
                supp = f"L{self.rng.randint(900, 999)}"
                self.plant("R-VIII-02", name, a.article_no, "leverancier", supp, a.supplier_no)
            elif supp in blocked and self.chance(0.6):  # R-VIII-04
                self.plant("R-VIII-04", name, a.article_no, "leverancier", supp, supp,
                           "reference is intact, the business fact is the problem")
            ws.append([a.article_no, supp, ""])
        wb.save(self.out / name)

    # ── 10 · supplier master ────────────────────────────────────────────
    def file_10_suppliers(self) -> None:
        name = "10_leveranciers.xlsx"
        wb = Workbook()
        ws = self._sheet(wb, "leveranciers", "Leveranciers", 
                         ["levnr", "naam", "straat", "nr", "pc", "gemeente", "land",
                          "btw", "email", "geblokkeerd"], junk_rows=3)
        for s in self.w.suppliers:
            sname, vat = s.name, s.vat
            if self.chance(0.08):  # R-I-03
                sname = f" {sname}  "
                self.plant("R-I-03", name, s.supp_no, "naam", repr(sname), s.name)
            if self.chance(0.04):  # R-VI-01
                vat = "BE0000000000"
                self.plant("R-VI-01", name, s.supp_no, "btw", vat, s.vat)
            if self.chance(0.04):  # R-VI-04
                sname = "TEST LEVERANCIER"
                self.plant("R-VI-04", name, s.supp_no, "naam", sname, s.name)
            if self.chance(0.05):  # R-III-05
                sname = f"{sname} {s.vat}"
                vat = ""
                self.plant("R-III-05", name, s.supp_no, "naam", sname, s.vat)
            if self.chance(0.05):  # R-VI-05
                self.plant("R-VI-05", name, s.supp_no, "land", "B", s.country)
                land = "B"
            else:
                land = s.country
            email = s.email
            if self.chance(0.07):  # R-VI-03
                email = "noreply@noreply.be"
                self.plant("R-VI-03", name, s.supp_no, "email", email, s.email)
            if self.chance(0.07):  # R-III-03
                email = f"{s.email}; aankoop@{s.email.split('@')[1]}"
                self.plant("R-III-03", name, s.supp_no, "email", email, s.email)
            if self.chance(0.06):  # R-III-01 · postcode and city in the street field
                street = f"{s.street} {s.house_no}, {s.postcode} {s.city}"
                self.plant("R-III-01", name, s.supp_no, "straat", street, s.city)
            else:
                street = s.street
            if self.chance(0.05):  # R-I-01
                sname = self.mojibake(sname.replace("e", "é", 1))
                self.plant("R-I-01", name, s.supp_no, "naam", sname, s.name)
            if self.chance(0.05):  # R-I-02
                sname = sname.replace(" ", " ", 1)
                self.plant("R-I-02", name, s.supp_no, "naam", repr(sname), s.name)
            if self.chance(0.05):  # R-II-04
                self.plant("R-II-04", name, s.supp_no, "btw", vat, s.name,
                           "supplier sharing a VAT number with a customer record")
            if self.chance(0.04):  # R-I-05
                self.plant("R-I-05", name, s.supp_no, "levnr", s.supp_no.lower(), s.supp_no)
            ws.append([s.supp_no, sname, street, s.house_no, s.postcode, s.city, land,
                       vat, email, "J" if s.blocked else "N"])
        wb.save(self.out / name)

    # ── 11 · open receivables, and the ninth circle ─────────────────────
    def file_11_open_items(self) -> None:
        name = "11_openstaande_posten.xlsx"
        wb = Workbook()
        ws = self._sheet(wb, "Posten", "Openstaande posten klanten",
                         ["stuknr", "klantnr", "stukdatum", "vervaldatum", "bedrag"],
                         junk_rows=3)
        known = {c.cust_no for c in self.w.customers}
        per_customer: dict[str, float] = {}
        rows: list[list[Any]] = []

        for o in self.w.open_items:
            cust = o.cust_no
            amount = o.amount
            doc_d: Any = o.doc_date.strftime("%d/%m/%Y")
            due_d: Any = o.due_date.strftime("%d/%m/%Y")

            if self.chance(0.12):
                # Whoever consolidated this file pasted a block from a system set
                # to US dates. Rows with a day past the 12th still prove their own
                # reading; the rest are ambiguous, and the file now proves both.
                due_d = o.due_date.strftime("%m/%d/%Y")
                if o.due_date.day <= 12:
                    self.plant("R-VII-04", name, o.doc_no, "vervaldatum", due_d,
                               o.due_date.isoformat(), "both readings are valid dates")
            if self.chance(0.03):  # R-VII-03
                doc_d = self.excel_serial(o.doc_date)
                self.plant("R-VII-03", name, o.doc_no, "stukdatum", doc_d, o.doc_date)
            if self.chance(0.02):  # R-VI-02
                due_d = "01/01/1900"
                self.plant("R-VI-02", name, o.doc_no, "vervaldatum", due_d, o.due_date)
            if self.chance(0.012):  # R-VIII-03 · an invoice for nobody
                cust = f"K{self.rng.randint(90000, 99999)}"
                while cust in known:
                    cust = f"K{self.rng.randint(90000, 99999)}"
                self.plant("R-VIII-03", name, o.doc_no, "klantnr", cust, o.cust_no)
            if self.chance(0.008):  # R-VII-05
                amount_s: Any = "#REF!"
                self.plant("R-VII-05", name, o.doc_no, "bedrag", amount_s, o.amount)
            else:
                amount_s = self.money_text(amount)
                self._plant_money(name, o.doc_no, "bedrag", amount_s, o.amount)

            # The trial balance is the legacy system's own summary of these same
            # documents, so it agrees with the detail on both the customer number
            # and the amount — including the orphan numbers, which are a broken
            # link to the customer master and not a reconciliation break. What it
            # cannot know about is anything edited in Excel after the export.
            per_customer[cust] = round(per_customer.get(cust, 0.0) + o.amount, 2)
            rows.append([o.doc_no, cust, doc_d, due_d, amount_s])

        # ── R-IX-03 · the betrayal ───────────────────────────────────────
        # Two documents, two customers, one amount. One is overstated by exactly
        # as much as the other is understated. The grand total still matches the
        # legacy trial balance to the cent, so a net-total reconciliation signs
        # off and the error only surfaces when a customer disputes a statement.
        delta = 1247.50
        # Pick two rows that are otherwise unremarkable: a real customer and a
        # parseable amount. An error hiding behind another defect is not the
        # point; the point is a pair of clean rows that reconcile to nothing.
        clean = [
            i for i, r in enumerate(rows)
            if r[1] == self.w.open_items[i].cust_no and not str(r[4]).startswith("#")
        ]
        a_idx, b_idx = clean[11], clean[97]
        for idx, sign in ((a_idx, +1), (b_idx, -1)):
            doc_no, cust_no, _, _, _ = rows[idx]
            true_amount = self.w.open_items[idx].amount
            new_amount = round(true_amount + sign * delta, 2)
            rows[idx][4] = self.money_text(new_amount)
            self.plant("R-IX-03", name, doc_no, "bedrag", new_amount, true_amount,
                       f"compensating error on customer {cust_no}, net effect zero")
        self.compensating_delta = delta

        for r in rows:
            ws.append(r)

        # The legacy trial balance: the number the accountant will check against.
        ws2 = wb.create_sheet("Saldilijst")
        ws2.append(["Saldilijst klanten — bron: Mercurius 4.2"])
        ws2.append([])
        ws2.append(["klantnr", "saldo"])
        for cust_no, total in sorted(per_customer.items()):
            ws2.append([cust_no, f"{total:.2f}".replace(".", ",")])
        wb.save(self.out / name)
        self.trial_balance = per_customer

    # ── 12 · discount agreements ────────────────────────────────────────
    def file_12_discounts(self) -> None:
        name = "12_korting_afspraken.xlsx"
        wb = Workbook()
        ws = self._sheet(wb, "afspraken", "Kortingafspraken klanten",
                         ["afspraak", "klantnr", "artikelnr", "korting %", "geldig tot"],
                         junk_rows=3)
        known = {c.cust_no for c in self.w.customers}
        for d in self.w.discounts:
            cust = d.cust_no
            if self.chance(0.08):  # R-VIII-01 · an agreement with a deleted customer
                cust = f"K{self.rng.randint(85000, 89999)}"
                while cust in known:
                    cust = f"K{self.rng.randint(85000, 89999)}"
                self.plant("R-VIII-01", name, d.agreement_no, "klantnr", cust, d.cust_no)
            pct: Any = f"{d.pct:.1f}".replace(".", ",")
            ws.append([d.agreement_no, cust, d.article_no, pct, ""])
        wb.save(self.out / name)

    # ── run ──────────────────────────────────────────────────────────────
    def run(self) -> dict[str, Any]:
        self.out.mkdir(parents=True, exist_ok=True)
        for fn in (
            self.file_01_customers_master, self.file_02_customers_jan,
            self.file_03_customers_sofie, self.file_04_customers_accounting,
            self.file_05_articles_master, self.file_06_prices, self.file_07_stock,
            self.file_08_units, self.file_09_article_supplier, self.file_10_suppliers,
            self.file_11_open_items, self.file_12_discounts,
        ):
            fn()
        truth = Path("data/truth")
        truth.mkdir(parents=True, exist_ok=True)
        by_rule: dict[str, int] = {}
        for d in self.defects:
            by_rule[d["rule"]] = by_rule.get(d["rule"], 0) + 1
        payload = {
            "client": CLIENT,
            "legacy_system": LEGACY_SYSTEM,
            "source_ar_total": round(sum(o.amount for o in self.w.open_items), 2),
            "compensating_delta": self.compensating_delta,
            "planted_total": len(self.defects),
            "planted_by_rule": dict(sorted(by_rule.items())),
            "defects": self.defects,
        }
        (truth / "planted-defects.json").write_text(json.dumps(payload, indent=1))
        return payload


def forge(seed: int = 1987, out: Path = Path("data/raw")) -> dict[str, Any]:
    return Forge(build_world(seed=seed), out, seed=seed).run()
