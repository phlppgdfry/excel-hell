"""The parsers. Every case here came out of the source files, not out of my head."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from dante.normalise import (
    country_status,
    ean_fix,
    email_status,
    extract_vat,
    fix_mojibake,
    is_scientific,
    parse_date,
    parse_money,
    phone_status,
    split_address,
    vat_status,
)


@pytest.mark.parametrize(("raw", "expected"), [
    ("€ 1.247,50", Decimal("1247.50")),
    ("1,247.50", Decimal("1247.50")),
    ("1 247,50", Decimal("1247.50")),
    ("1 247,50", Decimal("1247.50")),
    ("EUR 3590,33", Decimal("3590.33")),
    ("3 168,80", Decimal("3168.80")),
    ("1247.5", Decimal("1247.5")),
    ("-1247,50", Decimal("-1247.50")),
    ("0,00", Decimal("0")),
    ("1.247", Decimal("1247")),
])
def test_money_separator_order_decides_the_decimal_mark(raw, expected):
    value, status = parse_money(raw)
    assert status == "ok"
    assert value == expected


@pytest.mark.parametrize(("raw", "status"), [
    ("#REF!", "formula_error"), ("#N/B", "formula_error"), ("", "empty"),
    ("abc", "unparseable"), ("/", "unparseable"),
])
def test_money_refuses_what_it_cannot_defend(raw, status):
    value, got = parse_money(raw)
    assert got == status
    assert value is None


def test_dates_by_status():
    assert parse_date("2024-03-04") == (date(2024, 3, 4), "ok")
    assert parse_date("13/04/2024") == (date(2024, 4, 13), "ok")
    assert parse_date("46267")[1] == "serial"
    assert parse_date("01/01/1900") == (None, "sentinel")
    assert parse_date("9999-12-31") == (None, "sentinel")
    assert parse_date("rommel") == (None, "unparseable")


def test_a_date_valid_under_both_readings_is_flagged_not_guessed():
    value, status = parse_date("03/04/2024")
    assert status == "ambiguous"
    assert value == date(2024, 4, 3)  # a default, never a conclusion


def test_vat_checksum_and_placeholders():
    assert vat_status("BE0655523030")[1] == "ok"
    assert vat_status("BE 0655.523.030")[1] == "ok"
    assert vat_status("BE0000000000")[1] == "placeholder"
    assert vat_status("BE0655523031")[1] == "bad_checksum"
    assert vat_status("")[1] == "empty"
    assert extract_vat("Deveux Bouw (BE0655523030)") == "BE0655523030"
    assert extract_vat("Deveux Bouw") is None


def test_ean_padding_is_confirmed_by_the_check_digit():
    full, status = ean_fix("5421100788646")
    assert (full, status) == ("5421100788646", "ok")
    padded, status = ean_fix("123456789012")
    assert status == "padded"
    assert padded == "0123456789012"
    assert ean_fix("5421100788640")[1] == "bad_check"


def test_mojibake_survives_an_invisible_character_in_the_same_string():
    assert fix_mojibake("KortrÃ¯jk") == ("Kortrïjk", True)
    fixed, changed = fix_mojibake("VannÃ©ste bvba")
    assert changed and fixed.startswith("Vannéste")
    assert fix_mojibake("Vanacker bvba") == ("Vanacker bvba", False)


def test_scientific_notation_detection():
    assert is_scientific("5.42E+12")
    assert not is_scientific("SAN-0012")


def test_contact_details():
    assert email_status("info@x.be; bestel@x.be") == ("info@x.be", "multi")
    assert email_status("noreply@noreply.be")[1] == "placeholder"
    assert email_status("info@x.be") == ("info@x.be", "ok")
    assert phone_status("000000000")[1] == "placeholder"
    assert phone_status("051992498")[1] == "ok"
    assert country_status("B") == ("B", "unknown")
    assert country_status("BELGIE") == ("BE", "recoverable")
    assert country_status("BE") == ("BE", "ok")


def test_address_splitting():
    a = split_address("Nieuwstraat 12 bus 3, 8800 Roeselare")
    assert (a["street"], a["house_no"], a["box"]) == ("Nieuwstraat", "12", "3")
    assert (a["postcode"], a["city"]) == ("8800", "Roeselare")
    b = split_address("Molenstraat 12/3")
    assert (b["house_no"], b["box"]) == ("12", "3")


def test_a_delivery_instruction_is_not_an_address():
    c = split_address("achter de kerk, bellen bij de poort")
    assert c["status"] == "unparseable"
    assert c["house_no"] is None
