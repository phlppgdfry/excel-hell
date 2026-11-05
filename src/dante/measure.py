"""Measuring the engine against the defects the forge planted.

This lives outside the pipeline on purpose. The engine must never read the
ground truth, or the measurement stops meaning anything. The reporting layer
and the test suite may, because neither of them makes a migration decision.

A planted defect counts as found when the engine reported its rule against any
address that row legitimately has. A row in a keyless source file can only be
addressed as feed#row, and a merge is reported against the record that survives
it, so both count as the same defect being caught.
"""

from __future__ import annotations

import collections
from pathlib import Path
from typing import Any

import pandas as pd


def planted_addresses(truth: dict[str, Any]) -> dict[str, list[set[str]]]:
    out: dict[str, list[set[str]]] = collections.defaultdict(list)
    for d in truth["defects"]:
        out[d["rule"]].append({d["key"], d.get("engine_key", d["key"])})
    return dict(out)


def detected_keys(findings_csv: Path) -> dict[str, set[str]]:
    df = pd.read_csv(findings_csv)
    out: dict[str, set[str]] = collections.defaultdict(set)
    for rule, key in zip(df["rule"], df["key"], strict=False):
        out[rule].add(str(key))
    return dict(out)


def recall(planted: dict[str, list[set[str]]],
           detected: dict[str, set[str]]) -> dict[str, Any]:
    per_rule = {}
    hits = total = 0
    for rule in sorted(planted):
        if rule.startswith("R-IX-"):
            continue  # a gate is evaluated once per run, not per row
        keys = detected.get(rule, set())
        found = sum(1 for addresses in planted[rule] if addresses & keys)
        n = len(planted[rule])
        per_rule[rule] = {"planted": n, "found": found, "reported": len(keys),
                          "recall": round(found / n, 4) if n else None}
        hits += found
        total += n
    return {"per_rule": per_rule, "planted": total, "found": hits,
            "overall": round(hits / total, 4) if total else None}
