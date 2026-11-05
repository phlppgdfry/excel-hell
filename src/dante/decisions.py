"""The second pass — what the engine does with a human answer.

A migration is not one descent. You hand two thousand open questions to four
people, they answer some of them, and you run it again. If the engine cannot
take those answers back in, the triage is a report rather than a process, and
the business has no way to move the verdict.

So a decision file is the sheet the owner was given, with two columns filled
in. `out/purgatorio/sales.csv` goes out, `decisions/sales.csv` comes back, and
the rule, entity, key and field that identify the finding are already in it.
Nobody re-keys anything, which matters more than it sounds: re-keying is where
the second round of defects comes from.

Two kinds of answer, because real migrations have two kinds of question.

A **decision** answers one value, and has three verbs:

    accept    the value is right as it stands — migrate it
    correct   here is the right value — migrate that instead
    reject    do not migrate this record at all

A **ruling** answers an interpretation, and so applies to every record that
asked. "Is the receivables export day-first or month-first?" is not four
hundred questions about four hundred invoices; it is one question about one
file, and answering it four hundred times is how a migration loses a month.
A ruling is written with `*` as the key, and it carries the answer rather than
a value:

    R-VII-04,open_item,*,due_date,ruling,dmy,finance

Which rules may receive a ruling is declared in the registry, not in this
module. R-VII-04 already published both readings of every ambiguous date as
evidence, and the registry says which evidence field each answer selects, so a
ruling needs no rule-specific code here and cannot invent a value that the
engine did not already derive and show.

What an owner may *not* do is overturn a rejection. A rule whose action is
`reject` says the record cannot be migrated, not that nobody has looked at it
yet. A VAT number that fails the modulo-97 check does not become valid because
a sales manager signed a sheet, and a decision that claims otherwise is refused
by name and line number. That is the same argument the registry makes in the
other direction: the action says who is allowed to decide, and that holds for
people as firmly as for the engine.

A correction has to survive the parser the engine would have used on it.
"17/13/2024" is refused here rather than three circles later, because the point
of a second pass is that it is cleaner than the first.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .errors import MalformedDecisions, NoDecisions, RefusedDecisions
from .finding import EFFECT, Finding
from .normalise import parse_date, parse_money
from .pipeline import Context
from .triage import row_key

VERBS = tuple(EFFECT)
RULING = "ruling"
ANY = ("", "*")
REQUIRED = ("rule", "entity", "key", "field", "decision")
MONEY_FIELDS = ("credit_limit", "cost_price", "sales_price", "amount", "pct",
                "price")
DATE_FIELDS = ("created", "doc_date", "due_date")

# A finding names the field it found the problem in, which is the column of the
# file it was reading. That is not always the column the load file ships: the
# price rules read the 2024 price list, whose column is `price`, while the
# article that loads carries `sales_price`. Answering a question has to move the
# value that loads, so the few places where the two names differ are stated
# here rather than guessed at write time.
COLUMN_ALIAS = {("article", "price"): "sales_price"}


def load(path: Path) -> list[dict[str, Any]]:
    """Read every decision sheet in a directory, or one file.

    A row with an empty `decision` is not a decision — it is a question the
    owner has not answered yet, and the sheet they were given is full of them.
    """
    if not path.exists():
        raise NoDecisions(path)
    files = sorted(path.glob("*.csv")) if path.is_dir() else [path]
    if not files:
        raise NoDecisions(path)

    rows: list[dict[str, Any]] = []
    for f in files:
        # utf-8-sig: these come back out of Excel, and Excel writes a BOM
        with open(f, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
            if missing:
                raise MalformedDecisions(f, missing)
            for line, raw in enumerate(reader, start=2):
                verb = (raw.get("decision") or "").strip().lower()
                if not verb:
                    continue
                rows.append({
                    "rule": (raw.get("rule") or "").strip().upper(),
                    "entity": (raw.get("entity") or "").strip(),
                    "key": (raw.get("key") or "").strip(),
                    "field": (raw.get("field") or "").strip(),
                    "decision": verb,
                    "value": (raw.get("corrected_value") or "").strip(),
                    "decided_by": (raw.get("decided_by") or "").strip() or f.stem,
                    "file": f.name,
                    "line": line,
                })
    return rows


def apply(ctx: Context, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate every answer, then apply the ones that hold.

    All or nothing: one refused line stops the lot. A half-applied decision
    file is the worst of the three outcomes, because the run looks finished.
    """
    problems = [p for d in rows for p in _refuse(ctx, d)]
    if problems:
        raise RefusedDecisions(problems)

    open_findings = [f for f in ctx.findings
                     if f.action == "quarantine" and not f.decision]
    applied: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    touched = 0

    for d in rows:
        hits = [f for f in open_findings if _matches(d, f) and not f.decision]
        if not hits:
            # The answer is for a finding this run did not produce: the source
            # data moved, or the rule did. Not an error — the owner answered
            # the question they were asked — but it has to be counted, because
            # an answer that silently does nothing is how a decision gets lost.
            stale.append(d)
            continue
        n = 0
        for f in hits:
            if _answer(ctx, d, f):
                n += 1
        if not n:
            stale.append(d)
            continue
        touched += n
        applied.append({**d, "findings": n})

    by_owner: dict[str, int] = {}
    by_verb: dict[str, int] = {}
    for d in applied:
        by_owner[d["decided_by"]] = by_owner.get(d["decided_by"], 0) + d["findings"]
        by_verb[d["decision"]] = by_verb.get(d["decision"], 0) + d["findings"]
    decided = [f for f in ctx.findings if f.decision]
    return {
        "applied": touched,
        "answers": len(applied),
        "stale": len(stale),
        "by_owner": dict(sorted(by_owner.items())),
        "by_verdict": dict(sorted(by_verb.items())),
        "files": sorted({d["file"] for d in rows}),
        "released_rows": len({(f.entity, f.key) for f in decided
                              if f.decision != "reject"}),
        "rejected_rows": len({(f.entity, f.key) for f in decided
                              if f.decision == "reject"}),
    }


def _matches(d: dict[str, Any], f: Finding) -> bool:
    if d["rule"] != f.rule:
        return False
    for column, value in (("entity", f.entity), ("field", f.field), ("key", f.key)):
        if d[column] not in ANY and d[column] != value:
            return False
    return True


def _answer(ctx: Context, d: dict[str, Any], f: Finding) -> bool:
    """Attach one answer to one finding. False means it could not be applied."""
    if d["decision"] == RULING:
        evidence_key = ctx.rules[f.rule]["ruling"]["answers"][d["value"]]
        value = f.evidence.get(evidence_key)
        if value in (None, ""):
            # The ruling is sound and this record still cannot use it: the
            # engine never derived a value under the chosen reading. It stays
            # held rather than being released with nothing in the field.
            return False
        # Evidence is published as text, because a finding is something people
        # read. A column is typed, because something has to load it.
        value = _coerce(f.field, str(value))
    elif d["decision"] == "correct":
        value = _coerce(d["field"] if d["field"] not in ANY else f.field, d["value"])
    else:
        value = None

    f.decision = d["decision"]
    f.decided_by = d["decided_by"]
    if value is not None:
        f.repaired = value
        if not _write_back(ctx, f, value):
            # An answer that cannot reach a column is worse than a refused one,
            # because the run looks like it took the answer. Three circles once
            # reported a repair and shipped the original; this is that failure
            # mode with a human's name on it, so it stops the run.
            raise RefusedDecisions([
                f"{d['file']}:{d['line']}  {f.rule} answers {f.field!r} on "
                f"{f.entity} {f.key}, and nothing in the load file carries that "
                f"value — add the column to COLUMN_ALIAS in decisions.py or "
                f"answer a field the target has",
            ])
    return True


def _refuse(ctx: Context, d: dict[str, Any]) -> list[str]:
    """Everything an answer can be wrong about, said with a line number."""
    where = f"{d['file']}:{d['line']}"
    if d["decision"] not in (*VERBS, RULING):
        return [f"{where}  {d['decision']!r} is not an answer — use one of "
                f"{', '.join((*VERBS, RULING))}"]
    if d["rule"] not in ctx.rules:
        return [f"{where}  no rule {d['rule']!r} in the registry"]

    rule = ctx.rules[d["rule"]]
    if rule["action"] != "quarantine":
        return [f"{where}  {d['rule']} is a {rule['action']} rule, not an open "
                f"question — {_why_not(rule['action'])}"]

    if d["decision"] == RULING:
        if d["key"] not in ANY:
            return [f"{where}  a ruling answers an interpretation, so it applies "
                    f"to every record that asked — leave the key as '*', or use "
                    f"'correct' for just {d['key']}"]
        declared = rule.get("ruling")
        if not declared:
            return [f"{where}  {d['rule']} does not take a ruling: its questions "
                    f"are about values, not about how to read a file"]
        if d["value"] not in declared["answers"]:
            return [f"{where}  {d['value']!r} is not an answer to "
                    f"{d['rule']} — it takes "
                    f"{' or '.join(sorted(declared['answers']))}"]
        return []

    if d["key"] in ANY:
        return [f"{where}  {d['decision']!r} needs a key: it answers one record. "
                f"A blanket answer is a ruling, and only some rules take one"]
    if d["decision"] == "correct":
        if not d["value"]:
            return [f"{where}  {d['rule']} decided 'correct' with no corrected_value"]
        bad = _unparseable(d["field"], d["value"])
        if bad:
            return [f"{where}  corrected_value {d['value']!r} for {d['field']} {bad}"]
    return []


def _why_not(action: str) -> str:
    return {
        "repair": "the engine already fixed it and recorded what it did",
        "reject": "the record cannot be migrated at all, and a signature does "
                  "not make it loadable",
        "gate": "a reconciliation gate is evidence about the whole load, not a "
                "question about one record",
    }.get(action, "it is not an open question")


def _unparseable(fieldname: str, value: str) -> str | None:
    if fieldname in DATE_FIELDS:
        parsed, status = parse_date(value)
        if parsed is None or status != "ok":
            return f"is not a date the engine can read ({status})"
    if fieldname in MONEY_FIELDS:
        parsed, status = parse_money(value)
        if parsed is None or status != "ok":
            return f"is not an amount the engine can read ({status})"
    return None


def _coerce(fieldname: str, value: str) -> Any:
    if fieldname in DATE_FIELDS:
        parsed, _ = parse_date(value)
        return parsed.isoformat() if parsed else None
    if fieldname in MONEY_FIELDS:
        parsed, _ = parse_money(value)
        return float(parsed) if parsed is not None else None
    return value


def _write_back(ctx: Context, f: Finding, value: Any) -> bool:
    """Put the answered value where the load file will actually read it.

    A column that has a parsed twin is written on the twin, because that is the
    one `_load_ready` promotes over the raw value.

    Rows are found by key, preferring the file the finding came from. Both
    halves matter: the same customer number appears in two feeds, so a
    record-level answer has to land on the row that asked — but a rule reading
    an attribute file raises findings against an entity whose master row lives
    in a different file, and that row is the one that loads.
    """
    df = ctx.candidates.get(f.entity)
    if df is None:
        return False
    column = COLUMN_ALIAS.get((f.entity, f.field), f.field)
    if f"{column}_parsed" in df.columns:
        column = f"{column}_parsed"
    elif column not in df.columns:
        return False

    same_key = [i for i in df.index if row_key(df, i) == f.key]
    if not same_key:
        return False
    same_file = [i for i in same_key if str(df.at[i, "_source"]) == f.source]
    for idx in same_file or same_key:
        df.at[idx, column] = value
    return True
