"""Load-ready for what.

The mapping is the answer to the only question a reviewer of a cleansing
pipeline really has: clean according to whom. These checks hold it against the
data it claims to shape, because a mapping that drifts from the output is worse
than none — it reads as proof and is not.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from dante.target import NothingToLoad, build, load_mapping, shape

ROOT = Path(__file__).resolve().parents[1]
MAPPING = load_mapping(ROOT / "mapping/business-central.yaml")
ENTITIES = MAPPING["entities"]


def sources(spec: dict) -> set[str]:
    out: set[str] = set()
    for f in spec["fields"]:
        out |= set(f["from"] if isinstance(f["from"], list) else [f["from"]])
    return out


@pytest.fixture(scope="session")
def loaded(run, tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("load")
    return build(run["out"] / "paradiso", out, MAPPING)


def test_every_load_ready_column_is_mapped_or_dropped_with_a_reason(run):
    for entity, spec in ENTITIES.items():
        df = pd.read_csv(run["out"] / "paradiso" / f"{entity}.csv", dtype=str)
        dropped = {d["column"] for d in (spec.get("drop") or [])}
        unaccounted = set(df.columns) - sources(spec) - dropped
        assert not unaccounted, \
            f"{entity}: {sorted(unaccounted)} reach Paradiso and go nowhere"


def test_a_dropped_column_says_why_in_a_sentence():
    for entity, spec in ENTITIES.items():
        for d in spec.get("drop") or []:
            assert len(d["why"].split()) >= 10, \
                f"{entity}.{d['column']} is dropped without a real reason"


def test_every_mapped_source_column_actually_exists(run):
    for entity, spec in ENTITIES.items():
        df = pd.read_csv(run["out"] / "paradiso" / f"{entity}.csv", dtype=str)
        missing = sources(spec) - set(df.columns)
        assert not missing, f"{entity}: mapping reads {sorted(missing)}, which is " \
                            "not in the load-ready data"


def test_a_field_that_needs_setup_first_says_what_and_why():
    needs = [(e, f) for e, spec in ENTITIES.items() for f in spec["fields"]
             if f.get("needs")]
    assert needs, "a Business Central mapping with nothing to set up is a fiction"
    for entity, f in needs:
        assert len(f["needs"].split()) >= 8, \
            f"{entity}.{f['to']} needs setup and does not say what"


def test_the_setup_codes_are_the_codes_that_are_really_there(run):
    """A mapping that lists the wrong codes is worse than one that lists none.

    These started as prose, and the prose was wrong twice: it named a unit the
    data does not use and left out a payment term it does. So the codes are
    data, and the data is held against the load-ready output on every run.
    """
    checked = 0
    for entity, spec in ENTITIES.items():
        df = pd.read_csv(run["out"] / "paradiso" / f"{entity}.csv", dtype=str)
        for f in spec["fields"]:
            if "setup_codes" not in f:
                continue
            column = f["from"]
            actual = sorted({str(v) for v in df[column].dropna() if str(v).strip()})
            assert [str(c) for c in f["setup_codes"]] == actual, \
                f"{entity}.{f['to']} lists {f['setup_codes']}, data has {actual}"
            checked += 1
    assert checked >= 4, "the fields that need setup records should list them"


def test_the_load_order_puts_the_parents_first():
    order = MAPPING["target"]["order"]
    assert set(order) == set(ENTITIES), "the load order has to cover every entity"
    assert order.index("supplier") < order.index("article"), \
        "Business Central refuses an item whose vendor does not exist yet"
    assert order.index("customer") < order.index("open_item")


def test_the_load_files_carry_the_target_field_names(loaded):
    tables = {t["entity"]: t for t in loaded["tables"]}
    assert tables["customer"]["table"] == "Customer"
    assert "VAT Registration No." in tables["customer"]["columns"]
    assert "Unit Price" in tables["article"]["columns"]
    assert loaded["rows"] > 2000


def test_a_constant_reaches_every_row(loaded):
    journal = next(t for t in loaded["tables"] if t["entity"] == "open_item")
    df = pd.read_csv(journal["file"], dtype=str)
    assert set(df["Account Type"]) == {"Customer"}
    assert set(df["Document Type"]) == {"Invoice"}


def test_an_address_is_joined_without_holes(loaded):
    customer = next(t for t in loaded["tables"] if t["entity"] == "customer")
    df = pd.read_csv(customer["file"], dtype=str, keep_default_na=False)
    assert not df["Address"].str.contains("  ").any(), \
        "a customer with no box number should not get a double space"
    assert not df["Address"].str.startswith(" ").any()
    assert not df["Address"].str.endswith(" ").any()
    assert (df["Address"].str.len() > 0).any()


def test_a_flag_is_translated_into_the_target_option():
    df = pd.DataFrame([{"key": "K1", "blocked": "J"}, {"key": "K2", "blocked": "N"}])
    spec = {"fields": [{"to": "Blocked", "from": "blocked",
                        "values": {"J": "All", "N": ""}, "default": ""}]}
    assert list(shape(df, spec)["Blocked"]) == ["All", ""]


def test_the_item_block_is_inverted():
    """The legacy flag says what may be sold; the target stores what may not."""
    spec = next(f for f in ENTITIES["article"]["fields"] if f["to"] == "Blocked")
    df = pd.DataFrame([{"sellable": "J"}, {"sellable": "N"}])
    assert list(shape(df, {"fields": [spec]})["Blocked"]) == ["false", "true"]


def test_an_unknown_flag_value_falls_back_to_the_safe_default():
    spec = next(f for f in ENTITIES["article"]["fields"] if f["to"] == "Blocked")
    df = pd.DataFrame([{"sellable": "?"}])
    assert shape(df, {"fields": [spec]}).at[0, "Blocked"] == "true", \
        "an article whose sellability is unknown is blocked, not sold"


def test_nothing_to_load_says_what_to_run_first(tmp_path):
    with pytest.raises(NothingToLoad) as err:
        build(tmp_path / "paradiso", tmp_path / "load", MAPPING)
    assert "dante run" in err.value.fix
