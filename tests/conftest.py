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
    render(attach_measurement(summary, out, raw.parent / "truth"
                              / "planted-defects.json"), out, site)
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
def planted(run) -> dict[str, list[set[str]]]:
    """Planted defects, each with the addresses the engine could report it under.

    Deliberately `measure.planted_addresses` rather than a copy of it. The test
    suite used to reimplement the scoring it guards, so the floors were
    enforced against one implementation while the README and the site published
    the other. They agreed, but only by coincidence.
    """
    return planted_addresses(run["truth"])
