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
    "R-II-01": (0.70, "a name shortened to its first and last word scores around 68 "
                      "on token_sort_ratio, below the auto-merge threshold"),
    "R-II-02": (0.30, "the grey band only sees subsidiaries whose name still scores 75; "
                      "a differently worded subsidiary reads as a new company"),
    "R-II-03": (0.85, "a survivorship conflict is only visible once the two records "
                      "actually clustered"),
    "R-II-04": (0.78, "a shared VAT number is invisible when one of the two records "
                      "has no VAT number left to share"),
    "R-IV-03": (0.80, "a row that is also priced below cost reports that instead; the "
                      "VAT contradiction is no longer the blocking defect"),
    "R-VII-02": (0.85, "a stock row whose article code became a float is quarantined "
                       "before its EAN is ever looked at"),
}
GENERAL_FLOOR = 0.90
OVERALL_FLOOR = 0.92


def _recall(planted: dict, detected: dict, rule: str) -> tuple[int, int]:
    keys = detected.get(rule, set())
    hits = sum(1 for addresses in planted[rule] if addresses & keys)
    return hits, len(planted[rule])


def test_overall_recall(planted, run):
    hits = total = 0
    for rule in planted:
        if rule.startswith("R-IX-"):
            continue
        h, n = _recall(planted, run["detected"], rule)
        hits += h
        total += n
    assert total > 4000, "the forge planted suspiciously little"
    assert hits / total >= OVERALL_FLOOR, f"overall recall {hits / total:.1%}"


@pytest.mark.parametrize("rule", sorted(KNOWN_LIMITS))
def test_rules_with_a_documented_limit(rule, planted, run):
    floor, _reason = KNOWN_LIMITS[rule]
    hits, n = _recall(planted, run["detected"], rule)
    assert hits / n >= floor, f"{rule} recall {hits / n:.1%} below its documented {floor:.0%}"


def test_every_other_rule_clears_the_general_floor(planted, run):
    weak = {}
    for rule in sorted(planted):
        if rule.startswith("R-IX-") or rule in KNOWN_LIMITS:
            continue
        hits, n = _recall(planted, run["detected"], rule)
        if hits / n < GENERAL_FLOOR:
            weak[rule] = f"{hits}/{n} = {hits / n:.0%}"
    assert not weak, f"undocumented recall gaps: {weak}"


def test_the_forge_plants_every_non_gate_rule(planted, run):
    import yaml

    from tests.conftest import ROOT
    rules = yaml.safe_load((ROOT / "rules/rules.yaml").read_text())["rules"]
    expected = {r["id"] for r in rules if r["action"] != "gate"}
    assert expected - set(planted) == set()
