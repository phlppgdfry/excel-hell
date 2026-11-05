"""One seed, one answer.

Reproducibility is a claim this repository makes on its front page, so it gets a
test. It has already been wrong once: the two halves of the compensating pair
tie on absolute size, and a tie broken by set iteration order made the whole run
vary between processes, because Python randomises string hashing per process.
"""

from __future__ import annotations

import json

from dante.forge import forge
from dante.run import descend

from tests.conftest import ROOT


def _run(tmp_path_factory, tag: str) -> dict:
    raw = tmp_path_factory.mktemp("raw-" + tag)
    out = tmp_path_factory.mktemp("out-" + tag)
    forge(seed=1987, out=raw)
    return descend(raw_dir=raw, out_dir=out, rules_path=ROOT / "rules/rules.yaml",
                   quiet=True)


def test_two_runs_of_the_same_seed_are_identical(tmp_path_factory):
    first = _run(tmp_path_factory, "a")
    second = _run(tmp_path_factory, "b")
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_a_different_seed_gives_a_different_world(tmp_path_factory):
    raw = tmp_path_factory.mktemp("raw-seeded")
    out = tmp_path_factory.mktemp("out-seeded")
    forge(seed=2026, out=raw)
    other = descend(raw_dir=raw, out_dir=out, rules_path=ROOT / "rules/rules.yaml",
                    quiet=True)
    baseline = _run(tmp_path_factory, "c")
    assert other["findings_total"] != baseline["findings_total"], \
        "a different seed should produce different data"
    # and the gates still mean something on data nobody tuned them against
    assert {g["rule"] for g in other["gates"]} == {g["rule"] for g in baseline["gates"]}
    assert other["totals"]["paradiso"] > 0
