"""The clean world, as it would have existed if anyone had kept it clean.

This module builds the canonical truth for a fictional Flemish wholesaler.
The forge then degrades it into twelve source files, and the pipeline tries to
climb back out. Because the truth is generated first, every planted defect is
known, which is what lets the test suite measure detection instead of
asserting that the engine "looks right".
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

CLIENT = "Vanhulle Techniek nv"
CLIENT_CITY = "Roeselare"
LEGACY_SYSTEM = "Mercurius 4.2"

SURNAMES = [
    "Vanacker", "Deveux", "Vermeulen", "Deschacht", "Lammertyn", "Verhoeve",
    "Cottenier", "Bruggeman", "Debusschere", "Callewaert", "Maertens", "Dewitte",
    "Vanneste", "Goethals", "Vandenberghe", "Seynaeve", "Lefevere", "Desmet",
    "Pattyn", "Coussement", "Devos", "Vanhoutte", "Boussemaere", "Decroix",
    "Verschoore", "Noppe", "Tanghe", "Rommens", "Declercq", "Vandewalle",
    "Beernaert", "Hoornaert", "Vanbecelaere", "Loosveldt", "Deprez", "Mortier",
    "Vanlerberghe", "Depoorter", "Carron", "Vanden Broucke", "Delaere",
    "Vanhaverbeke", "Snauwaert", "Verhelst", "Baert", "Dekeyser", "Soenen",
]
TRADES = [
    "Sanitair", "Techniek", "Bouw", "Installaties", "Verwarming", "Dakwerken",
    "Loodgieterij", "Renovatie", "Elektro", "Klimaat",
]
FORMS = ["bvba", "nv", "bv", "comm.v", "vof", "& Zonen", "Groep", ""]

CITIES = [
    ("Roeselare", 8800), ("Kortrijk", 8500), ("Izegem", 8870), ("Tielt", 8700),
    ("Brugge", 8000), ("Gent", 9000), ("Waregem", 8790), ("Menen", 8930),
    ("Deinze", 9800), ("Ieper", 8900), ("Oostende", 8400), ("Torhout", 8820),
    ("Wevelgem", 8560), ("Harelbeke", 8530), ("Lichtervelde", 8810),
    ("Ardooie", 8850), ("Hooglede", 8830), ("Moorslede", 8890),
    ("Poperinge", 8970), ("Zonnebeke", 8980), ("Wielsbeke", 8710),
    ("Oudenaarde", 9700), ("Aalter", 9880), ("Diksmuide", 8600),
]
STREETS = [
    "Nieuwstraat", "Meensesteenweg", "Brugsesteenweg", "Kerkstraat", "Stationsstraat",
    "Industrielaan", "Ambachtenstraat", "Rijksweg", "Molenstraat", "Hoogstraat",
    "Gitsestraat", "Noordlaan", "Zuidstraat", "Vijverhoek", "Beverenstraat",
    "Oostlaan", "Mandellaan", "Diksmuidsesteenweg", "Kwadestraat", "Westlaan",
]

GROUP_UOM = {
    "SAN": ["ST", "ST", "ST", "PK"],
    "VRW": ["ST", "ST", "ST", "DS"],
    "LEI": ["M", "RL", "ST", "ST"],
    "GER": ["ST", "ST", "PK", "DS"],
}

ARTICLE_GROUPS = {
    "SAN": [
        'Radiatorkraan 1/2" recht verchroomd', "Wastafelmengkraan eengreeps",
        "Sifon wastafel 5/4 chroom", "Closetzitting softclose wit",
        "Inbouwreservoir 500 mm frontbediening", 'Doucheslang 1/2" 1750 mm',
        "Thermostatische badmengkraan", "Spoelbak inox 1 bak 500x400",
        'Koppeling messing 3/4" binnendraad', "Vloerafvoer inox 150x150",
    ],
    "VRW": [
        "Paneelradiator type 22 600x1000", "Thermostatische radiatorkraan haaks",
        "Circulatiepomp 25-60 180 mm", "Expansievat 18 liter rood",
        "Vloerverwarmingsbuis PE-RT 16x2 rol 240 m", "Verdeler 8 groepen messing",
        "Overstortventiel 3 bar", "Ontluchter automatisch 3/8",
        "Condensketel wandmodel 24 kW", "Boiler indirect 200 liter",
    ],
    "LEI": [
        "Meerlagenbuis 16x2 rol 100 m", "PVC afvoerbuis 110 mm lengte 3 m",
        "Koperbuis 15x1 stang 5 m", "Persfitting T-stuk 20x20x20",
        "Knelkoppeling recht 16x1/2", "Buisklem met rubber 22 mm",
        "PE-buis 32 mm rol 50 m", "Mof PVC 110 mm",
    ],
    "GER": [
        "Perstang accu 18V in koffer", "Pijpsnijder 6-35 mm",
        "Soldeerbrander set propaan", "Waterpas 600 mm magnetisch",
        "Afdichtingspasta 500 g", "Teflonband 12 mm rol 12 m",
        "Isolatieschaal 22/20 mm lengte 1 m", "Schroefset inox gemengd",
    ],
}


@dataclass
class Customer:
    cust_no: str
    name: str
    street: str
    house_no: str
    box: str
    postcode: int
    city: str
    country: str
    vat: str
    email: str
    phone: str
    payment_terms: int
    credit_limit: int
    created: date
    blocked: bool = False


@dataclass
class Supplier:
    supp_no: str
    name: str
    street: str
    house_no: str
    postcode: int
    city: str
    country: str
    vat: str
    email: str
    blocked: bool = False


@dataclass
class Article:
    article_no: str
    description: str
    group: str
    uom: str
    ean: str
    cost_price: float
    sales_price: float
    vat_rate: int
    supplier_no: str
    stock: int
    sellable: bool = True


@dataclass
class OpenItem:
    doc_no: str
    cust_no: str
    doc_date: date
    due_date: date
    amount: float


@dataclass
class Discount:
    agreement_no: str
    cust_no: str
    article_no: str
    pct: float


@dataclass
class World:
    customers: list[Customer] = field(default_factory=list)
    suppliers: list[Supplier] = field(default_factory=list)
    articles: list[Article] = field(default_factory=list)
    open_items: list[OpenItem] = field(default_factory=list)
    discounts: list[Discount] = field(default_factory=list)


def _vat_be(rng: random.Random) -> str:
    """A VAT number that satisfies the Belgian modulo-97 check."""
    body = f"0{rng.randint(400_000, 9_999_999):07d}"
    check = 97 - (int(body) % 97)
    return f"BE{body}{check:02d}"


def _company_name(rng: random.Random) -> str:
    name = rng.choice(SURNAMES)
    if rng.random() < 0.45:
        name = f"{name} {rng.choice(TRADES)}"
    form = rng.choice(FORMS)
    return f"{name} {form}".strip()


def build_world(seed: int = 1987, n_customers: int = 840, n_articles: int = 1180) -> World:
    rng = random.Random(seed)
    w = World()

    # ── suppliers ────────────────────────────────────────────────────────
    for i in range(1, 71):
        city, pc = rng.choice(CITIES)
        name = _company_name(rng)
        w.suppliers.append(
            Supplier(
                supp_no=f"L{i:04d}",
                name=name,
                street=rng.choice(STREETS),
                house_no=str(rng.randint(1, 240)),
                postcode=pc,
                city=city,
                country="BE",
                vat=_vat_be(rng),
                email=f"info@{name.split()[0].lower().replace(' ', '')}.be",
                blocked=rng.random() < 0.09,
            )
        )

    # ── customers ────────────────────────────────────────────────────────
    for i in range(1, n_customers + 1):
        city, pc = rng.choice(CITIES)
        name = _company_name(rng)
        slug = name.split()[0].lower().replace(" ", "")
        w.customers.append(
            Customer(
                cust_no=f"K{i:05d}",
                name=name,
                street=rng.choice(STREETS),
                house_no=str(rng.randint(1, 240)),
                box=rng.choice(["", "", "", "", "3", "A", "2", "0101"]),
                postcode=pc,
                city=city,
                country="BE",
                vat=_vat_be(rng),
                email=f"{rng.choice(['info', 'administratie', 'boekhouding', 'bestel'])}@{slug}.be",
                phone=f"0{rng.choice([5, 5, 5, 9, 4])}{rng.randint(1000000, 9999999)}",
                payment_terms=rng.choice([14, 30, 30, 30, 45, 60]),
                credit_limit=rng.choice([2500, 5000, 5000, 10000, 15000, 25000, 50000]),
                created=date(2004, 1, 1) + timedelta(days=rng.randint(0, 7600)),
                blocked=rng.random() < 0.05,
            )
        )

    # ── articles ─────────────────────────────────────────────────────────
    per_group = max(1, n_articles // len(ARTICLE_GROUPS))
    for group, descriptions in ARTICLE_GROUPS.items():
        for i in range(1, per_group + 1):
            base = rng.choice(descriptions)
            variant = rng.choice(["", " wit", " chroom", " inox", " zwart", " 10 st", " verzinkt"])
            cost = round(rng.uniform(1.2, 740.0), 2)
            margin = rng.uniform(1.22, 2.1)
            # Imported goods carry a UPC-A padded to 13 digits, so a tenth of
            # the catalogue has an EAN that starts with a zero. Excel eats it.
            if rng.random() < 0.12:
                ean_body = f"0{rng.randint(10_000_000_000, 99_999_999_999)}"[:12]
            else:
                ean_body = f"54{rng.randint(10_000_000_000, 99_999_999_999)}"[:12]
            w.articles.append(
                Article(
                    article_no=f"{group}-{i:04d}",
                    description=(base + variant).strip(),
                    group=group,
                    uom=rng.choice(GROUP_UOM[group]),
                    ean=ean_body + str(_ean_check(ean_body)),
                    cost_price=cost,
                    sales_price=round(cost * margin, 2),
                    vat_rate=rng.choice([21, 21, 21, 21, 6]),
                    supplier_no=rng.choice(w.suppliers).supp_no,
                    stock=rng.choice([0, 0, 2, 5, 12, 40, 120, 480]),
                    sellable=rng.random() > 0.04,
                )
            )

    # ── open items ───────────────────────────────────────────────────────
    doc = 240001
    for cust in w.customers:
        for _ in range(rng.choices([0, 1, 2, 3, 5], weights=[30, 34, 20, 11, 5])[0]):
            d = date(2025, 1, 1) + timedelta(days=rng.randint(0, 660))
            w.open_items.append(
                OpenItem(
                    doc_no=f"VF{doc}",
                    cust_no=cust.cust_no,
                    doc_date=d,
                    due_date=d + timedelta(days=cust.payment_terms),
                    amount=round(rng.uniform(18.0, 9400.0), 2),
                )
            )
            doc += 1

    # ── discount agreements ──────────────────────────────────────────────
    for i in range(1, 221):
        w.discounts.append(
            Discount(
                agreement_no=f"A{i:04d}",
                cust_no=rng.choice(w.customers).cust_no,
                article_no=rng.choice(w.articles).article_no,
                pct=rng.choice([2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0]),
            )
        )

    return w


def _ean_check(body12: str) -> int:
    total = sum(int(c) * (3 if i % 2 else 1) for i, c in enumerate(body12))
    return (10 - total % 10) % 10
