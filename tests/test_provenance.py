"""Can this verdict be tied back to the rules and the data that produced it.

The repository's claim is that a NO-GO is auditable. These checks hold the
mechanism that makes it so: a digest that moves when a rule moves, a digest
that does not move when a workbook is merely re-saved, and a clock that can be
pinned so the rest can be proven reproducible.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from dante import provenance as P
from dante.pipeline import load_registry

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "rules/rules.yaml"


def test_the_run_records_the_digest_of_the_registry_it_read(run):
    p = run["summary"]["provenance"]
    assert p["registry"]["sha256"] == hashlib.sha256(
        REGISTRY.read_bytes()).hexdigest()
    rules, circles = load_registry(REGISTRY)
    assert p["registry"]["rules"] == len(rules) == 40
    assert p["registry"]["circles"] == len(circles) == 9


def test_the_registry_digest_moves_when_one_word_of_one_rule_moves(tmp_path):
    original = REGISTRY.read_text()
    copy = tmp_path / "rules.yaml"
    copy.write_text(original.replace("Treachery", "Betrayal", 1))
    assert P.digest_text(copy.read_text()) != P.digest_text(original), \
        "a rule set that reads differently has to digest differently"


def test_the_source_digest_follows_the_values_and_not_the_container():
    """Two frames with the same cells digest the same, whatever carried them."""
    a = pd.DataFrame([{"klantnr": "K1", "naam": "Vermeulen", "_source": "a.csv",
                       "_row": 2}])
    b = pd.DataFrame([{"klantnr": "K1", "naam": "Vermeulen", "_source": "b.xlsx!x",
                       "_row": 97, "_header_row": 4}])
    assert P.digest_frame(a) == P.digest_frame(b)


def test_the_source_digest_moves_when_one_cell_moves():
    a = pd.DataFrame([{"klantnr": "K1", "naam": "Vermeulen"}])
    b = pd.DataFrame([{"klantnr": "K1", "naam": "Vermeulan"}])
    assert P.digest_frame(a) != P.digest_frame(b)


def test_a_reordered_column_is_a_different_table():
    a = pd.DataFrame([{"a": "1", "b": "2"}])
    assert P.digest_frame(a) != P.digest_frame(a[["b", "a"]])


def test_two_separators_keep_the_cells_apart():
    """A digest that concatenates can be fooled; this one may not be."""
    a = pd.DataFrame([{"x": "ab", "y": "c"}])
    b = pd.DataFrame([{"x": "a", "y": "bc"}])
    assert P.digest_frame(a) != P.digest_frame(b)


def test_the_clock_can_be_pinned(monkeypatch):
    monkeypatch.setenv("DANTE_RUN_AT", "2026-03-01T09:00:00Z")
    assert P.run_at() == "2026-03-01T09:00:00Z"
    monkeypatch.delenv("DANTE_RUN_AT")
    assert P.run_at().endswith("Z")
    assert len(P.run_at()) == len("2026-03-01T09:00:00Z")


def test_the_published_run_carries_a_whole_provenance_block(run):
    p = run["summary"]["provenance"]
    assert p["engine"].startswith("dante ")
    assert p["sources"]["tables"] == 13
    assert len({t["sha256"] for t in p["sources"]["detail"]}) == 13, \
        "thirteen tables should have thirteen digests"
    assert len(p["sources"]["sha256"]) == 64
