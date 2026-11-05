"""Three destinations, and a decision backlog.

Row triage answers one question per source row: can this be loaded? The worst
finding on the row decides, because a row with one rejectable field is not
partially loadable.

The decision backlog is a different view on the same findings. Not every
decision is attached to a row that would otherwise load, and a migration is
run by people who need a work list per owner, not a count.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd

from .finding import ACTION_RANK, Finding
from .pipeline import Context

PARADISO, PURGATORIO, INFERNO = "paradiso", "purgatorio", "inferno"
BUCKET_OF = {"repair": PARADISO, "quarantine": PURGATORIO, "reject": INFERNO}


def row_key(df: pd.DataFrame, idx: Any) -> str:
    k = str(df.at[idx, "key"] or "").strip()
    if k and k not in ("None", "nan"):
        return k
    return f"{df.at[idx, '_feed']}#{df.at[idx, '_row']}"


def triage(ctx: Context) -> dict[str, Any]:
    by_key: dict[tuple[str, str], list[Finding]] = defaultdict(list)
    for f in ctx.findings:
        if f.circle == 9:
            continue
        by_key[(f.entity, f.key)].append(f)

    buckets: dict[str, dict[str, list[dict[str, Any]]]] = {}
    counts: dict[str, dict[str, int]] = {}
    matched_keys: set[tuple[str, str]] = set()

    for entity, df in ctx.candidates.items():
        buckets[entity] = {PARADISO: [], PURGATORIO: [], INFERNO: []}
        for idx in df.index:
            key = row_key(df, idx)
            findings = by_key.get((entity, key), [])
            matched_keys.add((entity, key))
            if findings:
                worst = max(findings, key=lambda f: ACTION_RANK[f.action])
                bucket = BUCKET_OF[worst.action]
            else:
                worst, bucket = None, PARADISO
            buckets[entity][bucket].append({
                "key": key,
                "source": str(df.at[idx, "_source"]),
                "row": int(df.at[idx, "_row"]),
                "findings": len(findings),
                "deciding_rule": worst.rule if worst else None,
                "owner": worst.owner if worst and bucket != PARADISO else None,
                "amount": _amount(df, idx),
            })
        counts[entity] = {b: len(v) for b, v in buckets[entity].items()}
        counts[entity]["source_rows"] = len(df)

    # findings that never attached to a migratable row: an attribute source row
    # that could not be matched to its entity. The row still needs a decision.
    orphan_findings = [f for (e, k), fs in by_key.items() if (e, k) not in matched_keys
                       for f in fs]

    backlog: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in ctx.findings:
        if f.action == "quarantine":
            backlog[f.owner].append(f.as_dict())

    return {
        "buckets": buckets,
        "counts": counts,
        "totals": {
            b: sum(counts[e][b] for e in counts) for b in (PARADISO, PURGATORIO, INFERNO)
        },
        "source_rows": sum(counts[e]["source_rows"] for e in counts),
        "backlog_by_owner": dict(sorted(backlog.items())),
        "backlog_total": sum(len(v) for v in backlog.values()),
        "unmatched_attribute_rows": len(orphan_findings),
    }


def _amount(df: pd.DataFrame, idx: Any) -> float | None:
    if "amount_parsed" not in df.columns:
        return None
    v = df.at[idx, "amount_parsed"]
    return None if pd.isna(v) else float(v)
