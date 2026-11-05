"""One forge and one descent, shared by every test in the session."""

from __future__ import annotations

import collections
import json
from pathlib import Path

import pytest

from dante.forge import forge
from dante.run import descend

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def run(tmp_path_factory) -> dict:
    raw = tmp_path_factory.mktemp("raw")
    out = tmp_path_factory.mktemp("out")
    truth = forge(seed=1987, out=raw)
    summary = descend(raw_dir=raw, out_dir=out, rules_path=ROOT / "rules/rules.yaml",
                      quiet=True)
    findings = json.loads((out / "report" / "run-summary.json").read_text())
    import pandas as pd
    detail = pd.read_csv(out / "report" / "findings.csv")
    detected: dict[str, set[str]] = collections.defaultdict(set)
    for _, r in detail.iterrows():
        detected[r["rule"]].add(str(r["key"]))
    return {"truth": truth, "summary": summary, "findings": findings,
            "detected": dict(detected), "out": out, "raw": raw}


@pytest.fixture(scope="session")
def planted(run) -> dict[str, list[set[str]]]:
    """Planted defects, each with the addresses the engine could report it under.

    A row in a keyless source file can only be addressed as feed#row, and a
    merge is reported against the record that survives it. Both count as the
    same defect being found.
    """
    out: dict[str, list[set[str]]] = collections.defaultdict(list)
    for d in run["truth"]["defects"]:
        out[d["rule"]].append({d["key"], d.get("engine_key", d["key"])})
    return dict(out)
