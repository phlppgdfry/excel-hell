"""How much of the planted filth the engine actually finds.

The forge records every defect it plants, and the engine never reads that file.
So these are not assertions that the output "looks right": they are a measured
recall per rule, with a floor that is allowed to be well under 100 percent as
long as the reason is written down. A matcher that claims to catch every
duplicate is lying, and a test suite that asserts it is helping.
"""

from __future__ import annotations

import pytest

# Rules whose recall is knowingly below the general floor, and why. Raising one
# of these means the engine got better; lowering one needs a reason in writing.
KNOWN_LIMITS = {
    "R-II-01": (0.78, "a name shortened to its first and last word scores around 68 on "
                      "token_sort_ratio, below the auto-merge threshold of 92"),
    "R-II-02": (0.30, "the grey band only sees a subsidiary whose name still scores 75; "
                      "a differently worded one reads as a new company, which is the "
                      "correct reading more often than not"),
    "R-II-03": (0.85, "a survivorship conflict is only visible once the two records "
                      "actually clustered, so a missed merge hides it"),
    "R-IV-04": (0.85, "an article also priced at zero reports that instead: a row with "
                      "two defects is triaged on the blocking one"),
    "R-V-02": (0.86, "a warehouse description that normalises to the master's is no "
                      "longer a conflict by the time circle V compares them"),
}
GENERAL_FLOOR = 0.90
OVERALL_FLOOR = 0.92


def _recall(run: dict, rule: str) -> tuple[int, int]:
    m = run["recall"]["per_rule"][rule]
    return m["found"], m["planted"]


def test_overall_recall(run):
    scored = run["recall"]
    assert scored["planted"] > 4000, "the forge planted suspiciously little"
    assert scored["overall"] >= OVERALL_FLOOR, f"overall recall {scored['overall']:.1%}"


def test_the_published_figure_is_the_one_under_test(run):
    """The README number and the floors have to come from the same scorer.

    They used to be computed twice: once by measure.py for the report, and once
    by a copy of it in this file for the tests. Agreement was a coincidence
    waiting to end.
    """
    published = run["summary"].get("detection")
    assert published, "the run summary carries no measurement"
    assert published["found"] == run["recall"]["found"]
    assert published["planted"] == run["recall"]["planted"]
    assert published["overall"] == run["recall"]["overall"]


@pytest.mark.parametrize("rule", sorted(KNOWN_LIMITS))
def test_rules_with_a_documented_limit(rule, run):
    floor, _reason = KNOWN_LIMITS[rule]
    hits, n = _recall(run, rule)
    assert hits / n >= floor, f"{rule} recall {hits / n:.1%} below its documented {floor:.0%}"


def test_every_other_rule_clears_the_general_floor(run):
    weak = {}
    for rule in sorted(run["recall"]["per_rule"]):
        if rule in KNOWN_LIMITS:
            continue
        hits, n = _recall(run, rule)
        if hits / n < GENERAL_FLOOR:
            weak[rule] = f"{hits}/{n} = {hits / n:.0%}"
    assert not weak, f"undocumented recall gaps: {weak}"


def test_the_forge_plants_every_non_gate_rule(planted):
    from pathlib import Path

    import yaml
    root = Path(__file__).resolve().parents[1]
    rules = yaml.safe_load((root / "rules/rules.yaml").read_text())["rules"]
    expected = {r["id"] for r in rules if r["action"] != "gate"}
    assert expected - set(planted) == set()
