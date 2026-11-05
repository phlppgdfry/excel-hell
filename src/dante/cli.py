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
def report(out: Path = Path("out"), site: Path = Path("docs")) -> None:
    """Render the audit report and refresh the site data."""
    from .report import render

    summary = json.loads((out / "report" / "run-summary.json").read_text())
    paths = render(summary, out, site)
    for p in paths:
        typer.echo(f"  wrote {p}")


if __name__ == "__main__":
    app()
