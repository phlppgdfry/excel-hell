"""One forge and one descent, shared by every test in the session."""

from __future__ import annotations

import collections
import json
from pathlib import Path

import pytest

from dante.forge import forge
from dante.measure import planted_addresses, recall
from dante.report import attach_measurement, render
from dante.run import descend

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def run(tmp_path_factory) -> dict:
    raw = tmp_path_factory.mktemp("raw")
    out = tmp_path_factory.mktemp("out")
    site = tmp_path_factory.mktemp("site")
    truth = forge(seed=1987, out=raw)
    summary = descend(raw_dir=raw, out_dir=out, rules_path=ROOT / "rules/rules.yaml",
                      quiet=True)
    # The report step runs here too, so the audit report and the scoring are
    # exercised by the suite rather than only by whoever looks at the HTML, and
    # so the published figure exists to be held against the floors.
    answered = descend(raw_dir=raw, out_dir=tmp_path_factory.mktemp("out-two"),
                       rules_path=ROOT / "rules/rules.yaml",
                       decisions_dir=ROOT / "decisions", quiet=True)
    render(attach_measurement(summary, out, raw.parent / "truth"
                              / "planted-defects.json"), out, site, answered)
    summary = json.loads((out / "report" / "run-summary.json").read_text())
    findings = summary
    import pandas as pd
    detail = pd.read_csv(out / "report" / "findings.csv")
    detected: dict[str, set[str]] = collections.defaultdict(set)
    for _, r in detail.iterrows():
        detected[r["rule"]].add(str(r["key"]))
    return {"truth": truth, "summary": summary, "findings": findings,
            "detected": dict(detected), "out": out, "raw": raw, "site": site,
            "recall": recall(planted_addresses(truth), dict(detected))}


@pytest.fixture(scope="session")
def _second_pass(run, tmp_path_factory) -> tuple[dict, Path]:
    """The same descent, with the decision sheets this repository ships.

    Running the committed sheets in the suite is deliberate: a demonstration
    of the feedback loop that has gone stale against the rules is worse than
    no demonstration, and nothing else would notice.
    """
    out = tmp_path_factory.mktemp("out-decided")
    summary = descend(raw_dir=run["raw"], out_dir=out,
                      rules_path=ROOT / "rules/rules.yaml",
                      decisions_dir=ROOT / "decisions", quiet=True)
    return summary, out


@pytest.fixture(scope="session")
def decided(_second_pass) -> dict:
    return _second_pass[0]


@pytest.fixture(scope="session")
def decided_out(_second_pass) -> Path:
    return _second_pass[1]


@pytest.fixture(scope="session")
def planted(run) -> dict[str, list[set[str]]]:
    """Planted defects, each with the addresses the engine could report it under.

    Deliberately `measure.planted_addresses` rather than a copy of it. The test
    suite used to reimplement the scoring it guards, so the floors were
    enforced against one implementation while the README and the site published
    the other. They agreed, but only by coincidence.
    """
    return planted_addresses(run["truth"])
