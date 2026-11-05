"""The site reads the run; nothing was checking they still speak the same language.

docs/assets/site.js fetches run-summary.json and reaches into it by key. If a
key is renamed in the pipeline the page does not fail loudly — it renders an
empty cell, or stops halfway through with a console error nobody sees, and the
published site quietly stops saying anything. Everything else in this repository
is guarded against drifting from the run except the page built out of it.

A browser in CI would catch more, at the cost of a browser in CI. This checks
the thing that actually breaks: the contract between the two files.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE_JS = ROOT / "docs" / "assets" / "site.js"
SITE_HTML = ROOT / "docs" / "index.html"

# Keys site.js reads off the summary object, as `d.<key>`.
DATA_ACCESS = re.compile(r"\bd\.([a-z_]+)\b")
# Element ids the script writes into, where it names them outright.
JS_IDS = re.compile(r"getElementById\(\"([^\"]+)\"\)")

# And the ones it builds by concatenation — `getElementById("d-" + id)` — which
# no amount of regex over the source will find, and which happen to be the three
# headline counters and the diagram. Listed by hand because the alternative is
# pretending they are covered.
COMPUTED_IDS = [
    "d-par", "d-pur", "d-inf",
    "bar-par", "bar-pur", "bar-inf",
    "dg-par", "dg-pur", "dg-inf",
]


def summary(run) -> dict:
    return json.loads((run["site"] / "data" / "run-summary.json").read_text())


def test_every_key_the_page_reads_is_published(run):
    published = summary(run)
    read = set(DATA_ACCESS.findall(SITE_JS.read_text()))
    # names that are local variables in the script, not summary keys
    read -= {"length", "forEach", "map", "filter", "push", "textContent", "number"}
    missing = sorted(k for k in read if k not in published)
    assert not missing, f"site.js reads keys the run does not publish: {missing}"


def test_the_nested_shapes_the_page_depends_on(run):
    s = summary(run)
    assert set(s["totals"]) >= {"paradiso", "purgatorio", "inferno"}
    assert s["stats"].get("sources"), "the file strip needs stats.sources"
    for source in s["stats"]["sources"]:
        assert {"feed", "file", "rows", "columns"} <= set(source)
    for circle in s["circles"]:
        assert {"number", "name", "sin", "description", "findings", "rules"} <= set(circle)
        for rule in circle["rules"]:
            assert {"id", "title", "action", "owner", "entity", "findings",
                    "rationale"} <= set(rule)
    for gate in s["gates"]:
        assert {"rule", "title", "passed", "message", "evidence"} <= set(gate)
    for case in next(iter(s["desk"].values())):
        assert {"rule", "key", "field", "source", "entity", "message"} <= set(case)


def test_the_ninth_circle_panel_has_its_evidence(run):
    """The reconciliation grid names specific evidence fields."""
    gate = next(g for g in summary(run)["gates"] if g["rule"] == "R-IX-03")
    needed = {"trial_balance_total", "source_detail_total", "total_difference",
              "explained_orphan_detail", "explained_unquantifiable",
              "unexplained_net", "unexplained_gross", "worst"}
    assert needed <= set(gate["evidence"])
    assert len(gate["evidence"]["worst"]) >= 2, "the pair panel needs two customers"
    for row in gate["evidence"]["worst"][:2]:
        assert {"customer", "trial", "detail", "difference"} <= set(row)


@pytest.mark.parametrize(
    "element_id",
    sorted(set(JS_IDS.findall(SITE_JS.read_text())) | set(COMPUTED_IDS)))
def test_every_element_the_script_writes_into_exists(element_id):
    """A renamed id means a silent no-op, or a crash halfway down the page."""
    html = SITE_HTML.read_text()
    assert re.search(rf'id="{re.escape(element_id)}"', html), \
        f"site.js writes to #{element_id}, which is not in index.html"


def test_the_published_site_data_is_the_committed_one(run):
    """docs/data is what the live page reads, so it has to match a fresh run."""
    committed = json.loads((ROOT / "docs" / "data" / "run-summary.json").read_text())
    fresh = summary(run)
    assert committed["verdict"] == fresh["verdict"]
    assert committed["totals"] == fresh["totals"]
    assert committed["findings_by_rule"] == fresh["findings_by_rule"]


def test_the_hand_listed_ids_are_still_built_the_way_they_look():
    """If the script stops concatenating these, the hand-written list is a lie."""
    js = SITE_JS.read_text()
    for prefix in ("d-", "bar-", "dg-"):
        assert f'"{prefix}" + id' in js, (
            f"COMPUTED_IDS assumes the script builds {prefix}* by concatenation; "
            "it no longer does, so that list is out of date"
        )
