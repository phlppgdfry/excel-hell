"""One descent, end to end."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from . import circles as C
from .assemble import assemble
from .ingest import load_sources
from .pipeline import Context, load_registry
from .triage import INFERNO, PARADISO, row_key, triage
from .world import CLIENT, LEGACY_SYSTEM

INTERNAL = ("_source", "_row", "_feed", "_match_name", "_cluster", "_header_row")


def descend(raw_dir: Path = Path("data/raw"), out_dir: Path = Path("out"),
            rules_path: Path = Path("rules/rules.yaml"),
            quiet: bool = False) -> dict[str, Any]:
    rules, circle_docs = load_registry(rules_path)
    ctx = Context(raw_dir=raw_dir, rules=rules, circles=circle_docs)
    ctx.sources = load_sources(raw_dir)

    def say(msg: str) -> None:
        if not quiet:
            print(msg)

    say(f"  reading {len(ctx.sources)} source tables from {raw_dir}")
    ctx.stats["sources"] = [
        {"feed": name, "file": str(df["_source"].iloc[0]), "rows": len(df),
         "columns": len([c for c in df.columns if not c.startswith("_")])}
        for name, df in ctx.sources.items()
    ]
    C.c1_limbo.run(ctx)
    say(_line(1, circle_docs, ctx))
    assemble(ctx)

    for circle_no, module in enumerate(C.DESCENT[1:8], start=2):
        before = len(ctx.findings)
        module.run(ctx)
        say(_line(circle_no, circle_docs, ctx, len(ctx.findings) - before))

    verdict = triage(ctx)
    recon = C.c9_treachery.run(ctx, verdict)
    say(_line(9, circle_docs, ctx, sum(1 for g in recon["gates"] if not g["passed"]),
              suffix="gates failed"))

    summary = _write_outputs(ctx, verdict, recon, out_dir)
    return summary


def _line(circle: int, docs: dict, ctx: Context, n: int | None = None,
          suffix: str = "findings") -> str:
    name = docs[circle]["name"]
    count = n if n is not None else sum(1 for f in ctx.findings if f.circle == circle)
    roman = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"][circle - 1]
    return f"  {roman:>4} {name:<10} {count:>6} {suffix}"


def _write_outputs(ctx: Context, verdict: dict[str, Any], recon: dict[str, Any],
                   out: Path) -> dict[str, Any]:
    for sub in ("paradiso", "purgatorio", "inferno", "report"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    findings = [f.as_dict() for f in ctx.findings]
    by_rule = Counter(f["rule"] for f in findings)
    by_circle = Counter(f["circle"] for f in findings)

    # ── load-ready data, actually cleaned ────────────────────────────────
    for entity, df in ctx.candidates.items():
        keys = {r["key"] for r in verdict["buckets"][entity][PARADISO]}
        clean = df[[row_key(df, i) in keys for i in df.index]].drop(
            columns=[c for c in INTERNAL if c in df.columns])
        clean.to_csv(out / "paradiso" / f"{entity}.csv", index=False)

        rejected = pd.DataFrame(verdict["buckets"][entity][INFERNO])
        if not rejected.empty:
            rejected.to_csv(out / "inferno" / f"{entity}.csv", index=False)

    # ── one decision sheet per owner, which is how the work gets done ────
    for owner, rows in verdict["backlog_by_owner"].items():
        pd.DataFrame(rows).to_csv(out / "purgatorio" / f"{owner}.csv", index=False)

    summary = {
        "client": CLIENT,
        "legacy_system": LEGACY_SYSTEM,
        "verdict": recon["verdict"],
        "source_rows": verdict["source_rows"],
        "totals": verdict["totals"],
        "counts": verdict["counts"],
        "findings_total": len(findings),
        "findings_by_rule": dict(sorted(by_rule.items())),
        "findings_by_circle": {str(k): v for k, v in sorted(by_circle.items())},
        "backlog_by_owner": {k: len(v) for k, v in verdict["backlog_by_owner"].items()},
        "backlog_total": verdict["backlog_total"],
        "unmatched_attribute_rows": verdict["unmatched_attribute_rows"],
        "gates": recon["gates"],
        "ledger": recon["ledger"],
        "stats": ctx.stats,
        "circles": [
            {**ctx.circles[n],
             "findings": by_circle.get(n, 0),
             "rules": [{k: v for k, v in r.items() if k != "rationale"}
                       | {"rationale": r["rationale"].strip(),
                          "findings": by_rule.get(r["id"], 0)}
                       for r in ctx.rules.values() if r["circle"] == n]}
            for n in sorted(ctx.circles)
        ],
        "samples": _samples(findings),
        "desk": _desk(verdict),
    }
    (out / "report" / "run-summary.json").write_text(json.dumps(summary, indent=1))
    pd.DataFrame(findings).to_csv(out / "report" / "findings.csv", index=False)
    return summary


def _desk(verdict: dict[str, Any], per_owner: int = 24) -> dict[str, list]:
    """A readable slice of the decision backlog, for whoever has to work it."""
    out: dict[str, list] = {}
    for owner, rows in verdict["backlog_by_owner"].items():
        seen: Counter = Counter()
        picked = []
        for r in rows:
            # spread the slice over the owner's rules rather than taking the
            # first two dozen rows of whichever rule happened to run first
            if seen[r["rule"]] >= max(2, per_owner // 4):
                continue
            seen[r["rule"]] += 1
            picked.append(r)
            if len(picked) >= per_owner:
                break
        out[owner] = picked
    return out


def _samples(findings: list[dict[str, Any]], per_rule: int = 6) -> dict[str, list]:
    out: dict[str, list] = {}
    for f in findings:
        bucket = out.setdefault(f["rule"], [])
        if len(bucket) < per_rule:
            bucket.append(f)
    return out
