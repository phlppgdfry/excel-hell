"""One seed, one answer.

Reproducibility is a claim this repository makes on its front page, so it gets a
test. It has already been wrong once: the two halves of the compensating pair
tie on absolute size, and a tie broken by set iteration order made the whole run
vary between processes, because Python randomises string hashing per process.
"""

from __future__ import annotations

import json
from pathlib import Path

from dante.forge import forge
from dante.run import descend

ROOT = Path(__file__).resolve().parents[1]


def _run(tmp_path_factory, tag: str) -> dict:
    raw = tmp_path_factory.mktemp("raw-" + tag)
    out = tmp_path_factory.mktemp("out-" + tag)
    forge(seed=1987, out=raw)
    summary = descend(raw_dir=raw, out_dir=out, rules_path=ROOT / "rules/rules.yaml",
                      quiet=True)
    # The directory a run read from is an input, and this test gives each run a
    # different one. Normalising it keeps the comparison about the engine; the
    # digest of what was in that directory is not normalised, and is the thing
    # actually being held equal.
    summary["provenance"]["sources"]["directory"] = "<tmp>"
    return summary


def test_two_runs_of_the_same_seed_are_identical(tmp_path_factory, monkeypatch):
    """Byte for byte, with the clock pinned the way CI pins it."""
    monkeypatch.setenv("DANTE_RUN_AT", "2026-01-01T00:00:00Z")
    first = _run(tmp_path_factory, "a")
    second = _run(tmp_path_factory, "b")
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_the_clock_is_the_only_thing_that_moves(tmp_path_factory, monkeypatch):
    """Nothing but run_at may differ between two runs of the same seed.

    This is the claim that lets CI diff the committed outputs against a fresh
    run: pin the one value that cannot be reproducible, and everything else has
    to match. Asserting it here rather than excusing it in the diff means a new
    source of non-determinism shows up as a failure and not as a flake.
    """
    monkeypatch.setenv("DANTE_RUN_AT", "2026-01-01T00:00:00Z")
    pinned = _run(tmp_path_factory, "pinned")
    monkeypatch.delenv("DANTE_RUN_AT")
    wall = _run(tmp_path_factory, "wall")

    assert wall["provenance"]["run_at"] != pinned["provenance"]["run_at"]
    wall["provenance"]["run_at"] = pinned["provenance"]["run_at"]
    assert json.dumps(wall, sort_keys=True) == json.dumps(pinned, sort_keys=True)


def test_a_resaved_workbook_does_not_move_the_source_digest(tmp_path_factory):
    """The digest is over the values, so re-forging a file does not move it.

    Every forge writes new bytes into the xlsx containers because openpyxl
    stamps a creation time, and a digest that moved with them would be noise
    nobody reads. Two forges of the same seed must therefore agree on the
    source digest while the files themselves differ on disk.
    """
    a = _run(tmp_path_factory, "digest-a")
    b = _run(tmp_path_factory, "digest-b")
    assert a["provenance"]["sources"]["sha256"] == b["provenance"]["sources"]["sha256"]
    assert len(a["provenance"]["sources"]["detail"]) == 13


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
