"""dante — the command line around the descent."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .forge import forge as run_forge
from .run import descend

app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def forge(seed: int = 1987, out: Path = Path("data/raw")) -> None:
    """Rebuild the twelve filthy source files from the clean world."""
    payload = run_forge(seed=seed, out=out)
    typer.echo(f"  forged 12 source files in {out}")
    typer.echo(f"  planted {payload['planted_total']} defects across "
               f"{len(payload['planted_by_rule'])} rules")


@app.command()
def run(raw: Path = Path("data/raw"), out: Path = Path("out"),
        rules: Path = Path("rules/rules.yaml")) -> None:
    """Descend through the nine circles and triage every source row."""
    typer.echo("\n  DANTE — descent through nine circles\n")
    summary = descend(raw_dir=raw, out_dir=out, rules_path=rules)
    t = summary["totals"]
    typer.echo(
        f"\n  PARADISO {t['paradiso']:>6} rows load-ready"
        f"\n  PURGATORIO {t['purgatorio']:>4} rows held, "
        f"{summary['backlog_total']} decisions for "
        f"{len(summary['backlog_by_owner'])} owners"
        f"\n  INFERNO {t['inferno']:>7} rows rejected\n"
    )
    for g in summary["gates"]:
        mark = "pass" if g["passed"] else "FAIL"
        typer.echo(f"  [{mark}] {g['rule']}  {g['message']}")
    typer.echo(f"\n  verdict: {summary['verdict']}\n")
    raise typer.Exit(0 if summary["verdict"] == "GO" else 1)


@app.command()
def rule(rule_id: str, out: Path = Path("out"),
         rules: Path = Path("rules/rules.yaml"), limit: int = 8) -> None:
    """Explain one rule: what it does, who owns it, and what it caught."""
    import csv

    from .pipeline import load_registry

    registry, circles = load_registry(rules)
    key = rule_id.upper()
    if key not in registry:
        close = [r for r in registry if key.replace("-", "") in r.replace("-", "")]
        typer.echo(f"  no rule {rule_id!r}." + (f" Did you mean {close[0]}?" if close else ""))
        raise typer.Exit(2)

    r = registry[key]
    circle = circles[r["circle"]]
    roman = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"][r["circle"] - 1]
    typer.echo(f"\n  {r['id']}  {r['title']}")
    typer.echo(f"  circle {roman} · {circle['name']} — {circle['sin']}")
    typer.echo(f"  action: {r['action']}    owner: {r['owner']}    "
               f"entities: {', '.join(r['entity'])}\n")
    for line in _wrap(" ".join(r["rationale"].split()), 74):
        typer.echo(f"  {line}")

    findings = out / "report" / "findings.csv"
    if not findings.exists():
        typer.echo("\n  no findings yet — run `dante run` first\n")
        return
    with open(findings, newline="") as fh:
        hits = [row for row in csv.DictReader(fh) if row["rule"] == key]
    noun = "finding" if len(hits) == 1 else "findings"
    typer.echo(f"\n  {len(hits)} {noun} in the last run" + (":" if hits else "\n"))
    for row in hits[:limit]:
        raw = (row["raw"] or "")[:46]
        fixed = (row["repaired"] or "")[:40]
        arrow = f" -> {fixed}" if fixed else ""
        typer.echo(f"    {row['key']:<16} {row['field']:<12} {raw}{arrow}")
    if len(hits) > limit:
        typer.echo(f"    … and {len(hits) - limit} more in {findings}")
    typer.echo("")


def _wrap(text: str, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return lines


@app.command()
def report(out: Path = Path("out"), site: Path = Path("docs")) -> None:
    """Render the audit report and refresh the site data."""
    from .report import render

    summary = json.loads((out / "report" / "run-summary.json").read_text())
    paths = render(summary, out, site)
    for p in paths:
        typer.echo(f"  wrote {p}")


if __name__ == "__main__":
    app()
