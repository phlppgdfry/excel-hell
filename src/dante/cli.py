"""dante — the command line around the descent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from .errors import DanteError, NoRunYet
from .forge import forge as run_forge
from .run import descend

app = typer.Typer(add_completion=False, help=__doc__, no_args_is_help=True)


def _version(show: bool) -> None:
    if show:
        from . import __version__
        typer.echo(f"dante {__version__}")
        raise typer.Exit()


@app.callback()
def main(version: bool = typer.Option(False, "--version", callback=_version,
                                      is_eager=True, help="Show the version and exit.")
         ) -> None:
    """DANTE — nine circles of dirty master data."""


@app.command()
def forge(seed: int = 1987, out: Path = Path("data/raw")) -> None:
    """Rebuild the twelve filthy source files from the clean world."""
    payload = run_forge(seed=seed, out=out)
    typer.echo(f"  forged 12 source files in {out}")
    typer.echo(f"  planted {payload['planted_total']} defects across "
               f"{len(payload['planted_by_rule'])} rules")


@app.command()
def run(raw: Path = Path("data/raw"), out: Path = Path("out"),
        rules: Path = Path("rules/rules.yaml"),
        decisions: Annotated[Path | None, typer.Option(
            help="Directory of answered decision sheets to feed back in.")] = None,
        ) -> None:
    """Descend through the nine circles and triage every source row."""
    typer.echo("\n  DANTE — descent through nine circles\n")
    try:
        summary = descend(raw_dir=raw, out_dir=out, rules_path=rules,
                          decisions_dir=decisions)
    except DanteError as err:
        _complain(err)
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
    typer.echo(f"\n  verdict: {summary['verdict']}")
    typer.echo(_provenance_line(summary["provenance"]) + "\n")
    raise typer.Exit(0 if summary["verdict"] == "GO" else 1)


def _provenance_line(p: dict) -> str:
    """Which rules and which data produced the verdict above it."""
    from .provenance import SHORT
    return (f"  {p['engine']} · ruleset {p['registry']['sha256'][:SHORT]} "
            f"({p['registry']['rules']} rules) · sources "
            f"{p['sources']['sha256'][:SHORT]} ({p['sources']['tables']} tables) "
            f"· {p['run_at']}")


@app.command()
def rule(rule_id: str, out: Path = Path("out"),
         rules: Path = Path("rules/rules.yaml"), limit: int = 8) -> None:
    """Explain one rule: what it does, who owns it, and what it caught."""
    import csv

    from .pipeline import load_registry

    try:
        registry, circles = load_registry(rules)
    except DanteError as err:
        _complain(err)
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


def _complain(err: DanteError) -> NoReturn:
    """One line on what went wrong, one on how to fix it, and a useful exit code."""
    typer.secho(f"\n  {err.problem}", err=True, fg=typer.colors.RED)
    typer.echo(f"  {err.fix}\n", err=True)
    raise typer.Exit(2)


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
def load(out: Path = Path("out"),
         mapping: Path = Path("mapping/business-central.yaml")) -> None:
    """Shape the load-ready data into the target system's own tables."""
    from .target import build, load_mapping

    try:
        result = build(out / "paradiso", out / "load", load_mapping(mapping))
    except DanteError as err:
        _complain(err)

    t = result["target"]
    typer.echo(f"\n  {t['system']} {t['release']}")
    typer.echo(f"  {t['loader']}\n")
    for table in result["tables"]:
        typer.echo(f"  {table['table_no']:>5}  {table['table']:<20} "
                   f"{table['rows']:>5} rows  {len(table['columns'])} fields")
    typer.echo(f"\n  {result['rows']} rows written to {out / 'load'}")
    if result["blocking"]:
        typer.echo(f"\n  {result['blocking']} fields will not insert until a "
                   f"setup record exists:")
        for table in result["tables"]:
            for need in table["needs"]:
                for line in _wrap(f"{table['table']}.{need['field']} — "
                                  f"{need['why']}", 68):
                    typer.echo(f"      {line}")
                if need["codes"]:
                    typer.echo(f"        codes: {', '.join(need['codes'])}")
    dropped = [(t2["table"], d) for t2 in result["tables"] for d in t2["dropped"]]
    if dropped:
        noun = "column" if len(dropped) == 1 else "columns"
        typer.echo(f"\n  {len(dropped)} source {noun} not migrated:")
        for table_name, d in dropped:
            for line in _wrap(f"{table_name}.{d['column']} — {d['why']}", 68):
                typer.echo(f"      {line}")
    typer.echo("")


@app.command()
def why(key: str, out: Path = Path("out"),
        rules: Path = Path("rules/rules.yaml")) -> None:
    """Why is this record where it is: one record, its findings and its ruling.

    The question a business owner actually asks during a migration is never
    "how many were held". It is "why is this one", and an answer that takes a
    consultant twenty minutes of grepping is an answer nobody asks for twice.
    """
    import csv

    from .errors import UnknownRecord
    from .pipeline import load_registry

    placement = out / "report" / "placement.csv"
    if not placement.exists():
        _complain(NoRunYet(placement))
    with open(placement, newline="") as fh:
        rows = list(csv.DictReader(fh))

    wanted = key.strip()
    hits = [r for r in rows if r["key"].lower() == wanted.lower()]
    if not hits:
        near = sorted({r["key"] for r in rows
                       if wanted.lower() in r["key"].lower()})
        _complain(UnknownRecord(wanted, near))

    findings = out / "report" / "findings.csv"
    detail: list[dict[str, str]] = []
    if findings.exists():
        with open(findings, newline="") as fh:
            detail = [r for r in csv.DictReader(fh)
                      if r["key"].lower() == wanted.lower()]
    try:
        registry, _ = load_registry(rules)
    except DanteError as err:
        _complain(err)

    for hit in hits:
        typer.echo(f"\n  {hit['key']}  ({hit['entity']})")
        typer.echo(f"  {hit['source']} row {hit['row']}")
        typer.echo(f"  → {hit['bucket'].upper()}, {_because(hit)}")

        mine = [d for d in detail if d["entity"] == hit["entity"]]
        if not mine:
            typer.echo("  not one of the forty rules fired on it\n")
            continue
        typer.echo(f"\n  {len(mine)} finding(s):")
        for d in mine:
            rule = registry.get(d["rule"], {})
            verdict = d["decision"] or d["action"]
            typer.echo(f"    {d['rule']:<10} {d['field']:<14} {verdict:<9} "
                       f"{rule.get('owner', '?')}")
            if d["raw"]:
                arrow = f"  ->  {d['repaired']}" if d["repaired"] else ""
                typer.echo(f"      {d['raw'][:48]}{arrow}")
            for ln in _wrap(d["message"], 64):
                typer.echo(f"      {ln}")
        held = [d for d in mine if d["action"] == "quarantine" and not d["decision"]]
        if held:
            owners = sorted({registry.get(d["rule"], {}).get("owner", "?")
                             for d in held})
            typer.echo(f"\n  loads once {' and '.join(owners)} answers "
                       f"{', '.join(sorted({d['rule'] for d in held}))}")
        typer.echo("")


def _because(hit: dict[str, str]) -> str:
    """One clause saying who put this row where it is."""
    rule, who = hit["deciding_rule"], hit["decided_by"]
    if hit["bucket"] == "inferno":
        return (f"rejected on {rule} by {who}" if hit["decision"]
                else f"rejected on {rule}, and nobody may overrule it")
    if hit["bucket"] == "purgatorio":
        return f"waiting on {hit['owner']} to answer {rule}"
    if hit["decision"]:
        return f"released by {who}, who answered {rule} with {hit['decision']}"
    return f"repaired by the engine under {rule}" if rule else "it arrived clean"


@app.command()
def report(out: Path = Path("out"), site: Path = Path("docs"),
           second_pass: Annotated[Path | None, typer.Option(
               help="Output directory of a run made with --decisions, to "
                    "publish the before and after.")] = None,
           ) -> None:
    """Render the audit report and refresh the site data."""
    from .report import render

    source = out / "report" / "run-summary.json"
    if not source.exists():
        _complain(NoRunYet(source))
    answered = None
    if second_pass is not None:
        other = second_pass / "report" / "run-summary.json"
        if not other.exists():
            _complain(NoRunYet(other))
        answered = json.loads(other.read_text())
        if not answered["decisions"]["applied"]:
            _complain(DanteError(
                f"{other} is a run with nobody's answers in it",
                "pass the output directory of a run made with --decisions, or "
                "leave --second-pass off",
            ))
    summary = json.loads(source.read_text())
    paths = render(summary, out, site, answered)
    for p in paths:
        typer.echo(f"  wrote {p}")


if __name__ == "__main__":
    app()
