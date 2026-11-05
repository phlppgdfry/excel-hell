"""How much of the planted filth the engine actually finds.

The forge records every defect it plants, and the engine never reads that file,
so these are measured recall rather than an assertion that the output looks
right. A matcher that claims to catch every duplicate is lying, and a test
suite that asserts it is helping.

The instrument depends on the sample. A percentage floor on a dozen planted
defects is noise — one miss moves it eight points — and floors derived from a
single seed turned out to be exactly that: five of them failed on other seeds
while the engine was unchanged. So a rule is held to a percentage only when the
forge planted enough of it for a percentage to be stable, and to an absolute
miss budget otherwise. Both were derived from five seeds, not one.
"""

from __future__ import annotations

import pytest

# Below this many planted defects, a percentage says more about the sample than
# about the engine.
STABLE_SAMPLE = 100

# Percentage floors for the rules the forge plants in quantity. Each sits a few
# points under the worst recall observed across seeds 1987, 2026, 7, 424242
# and 99, so it catches a regression without failing on sampling noise.
FLOORS = {
    "R-I-01": 0.93, "R-I-02": 0.90, "R-I-03": 0.95,
    "R-II-01": 0.75,
    "R-III-01": 0.90, "R-III-02": 0.88,
    "R-IV-01": 0.95, "R-IV-02": 0.95, "R-IV-03": 0.90,
    "R-V-02": 0.86,
    "R-VII-02": 0.82,
}

# For everything else: how many planted defects this rule may miss outright.
DEFAULT_MISS_BUDGET = 10
MISS_BUDGET = {
    "R-II-02": (22, "the grey band only sees a subsidiary whose name still "
                    "scores 75; a differently worded one reads as a new company, "
                    "which is the correct reading more often than not"),
    "R-II-03": (10, "a survivorship conflict is only visible once the two records "
                    "actually clustered, so a missed merge hides it"),
    "R-VII-04": (8, "a date is only ambiguous if the file proves both readings, and "
                    "how many rows prove it varies with the sample"),
}

OVERALL_FLOOR = 0.92
SEEDS_FOR_STABILITY = (2026, 424242)


def _measured(run: dict, rule: str) -> dict:
    return run["recall"]["per_rule"][rule]


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


def _held_to(rule: str, m: dict) -> tuple[bool, str]:
    """Pick the instrument from the sample actually observed, not in advance.

    R-I-02 plants between 94 and 114 defects depending on the seed, so a rule
    cannot be assigned to one instrument up front without failing whenever its
    sample drifts across the line.
    """
    if rule in FLOORS and m["planted"] >= STABLE_SAMPLE:
        return (m["recall"] >= FLOORS[rule],
                f"recall {m['recall']:.0%}, floor {FLOORS[rule]:.0%}, "
                f"n={m['planted']}")
    budget = MISS_BUDGET.get(rule, (DEFAULT_MISS_BUDGET, ""))[0]
    missed = m["planted"] - m["found"]
    return missed <= budget, f"missed {missed} of {m['planted']}, budget {budget}"


@pytest.mark.parametrize("rule", sorted(FLOORS))
def test_rules_with_a_stable_sample_hold_their_percentage(rule, run):
    m = _measured(run, rule)
    ok, how = _held_to(rule, m)
    assert ok, f"{rule}: {how}"


def test_every_other_rule_stays_within_its_miss_budget(run):
    """One miss out of twelve is eight points, so count misses, not percentages."""
    over = {}
    for rule, m in run["recall"]["per_rule"].items():
        if rule in FLOORS and m["planted"] >= STABLE_SAMPLE:
            continue
        ok, how = _held_to(rule, m)
        if not ok:
            over[rule] = how
    assert not over, f"rules over their miss budget: {over}"


def test_every_rule_is_held_to_something(run):
    """A rule in neither list would be measured and then quietly ignored."""
    for rule, m in run["recall"]["per_rule"].items():
        ok, how = _held_to(rule, m)
        assert isinstance(ok, bool), f"{rule} has no instrument: {how}"
        if m["planted"] >= STABLE_SAMPLE:
            assert rule in FLOORS or m["recall"] >= 0.95, (
                f"{rule} plants {m['planted']} defects and has no percentage floor"
            )


@pytest.mark.parametrize("seed", SEEDS_FOR_STABILITY)
def test_the_overall_figure_is_not_tuned_to_one_dataset(seed, tmp_path_factory):
    """The headline number has to survive data the floors were not drawn from.

    This is what caught the per-rule floors being overfit: the engine was
    unchanged and five of them failed on a second seed, because they had been
    read off a single sample of a noisy statistic.
    """
    from dante.forge import forge
    from dante.measure import detected_keys, planted_addresses, recall
    from dante.run import descend
    from tests.conftest import ROOT

    raw = tmp_path_factory.mktemp(f"raw-{seed}")
    out = tmp_path_factory.mktemp(f"out-{seed}")
    truth = forge(seed=seed, out=raw)
    descend(raw_dir=raw, out_dir=out, rules_path=ROOT / "rules/rules.yaml", quiet=True)
    scored = recall(planted_addresses(truth),
                    detected_keys(out / "report" / "findings.csv"))
    assert scored["overall"] >= OVERALL_FLOOR, (
        f"seed {seed}: overall recall {scored['overall']:.1%} below {OVERALL_FLOOR:.0%}"
    )


def test_the_forge_plants_every_non_gate_rule(planted):
    from pathlib import Path

    import yaml
    root = Path(__file__).resolve().parents[1]
    rules = yaml.safe_load((root / "rules/rules.yaml").read_text())["rules"]
    expected = {r["id"] for r in rules if r["action"] != "gate"}
    assert expected - set(planted) == set()
