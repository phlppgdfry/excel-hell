# Decision sheets

These are the four sheets from `out/purgatorio/`, answered.

A run writes one sheet per owner, listing every question that owner has to
settle, with the record, the raw value, the rule, the evidence, and two empty
columns on the end. The owner fills in `decision` and, where it applies,
`corrected_value`. Nothing is retyped — the rule, entity, key and field that
identify the finding are already in the row — which matters more than it
sounds, because retyping is where the second round of defects comes from.

```bash
dante run                                   # writes out/purgatorio/<owner>.csv
# … the owners answer what they can …
dante run --decisions decisions --out out2  # the second pass
```

## The four answers

| Verb | Means | Needs |
|---|---|---|
| `accept` | the value is right as it stands — migrate it | a key |
| `correct` | here is the right value — migrate that instead | a key and a `corrected_value` |
| `reject` | do not migrate this record at all | a key |
| `ruling` | an answer to the question, not to one record | `*` as the key, and an answer the rule declares |

A **ruling** is the one worth understanding. "Is this export day-first or
month-first?" is not four hundred questions about four hundred invoices; it is
one question about one file, and answering it four hundred times is how a
migration loses a month. Which rules may be answered that way is declared in
[`rules/rules.yaml`](../rules/rules.yaml), and each answer names the evidence
field the finding already published:

```yaml
    ruling:
      question: Which reading does this export use where both are possible?
      answers:
        dmy: european
        mdy: american
```

So a ruling can only select between values the engine itself derived and showed
its working for. It cannot invent one.

## What is refused

Nothing is applied unless every line holds, because a half-applied decision
file is the worst of the three outcomes: the run looks finished.

- **A decision on a `reject` rule.** A rule whose action is `reject` says the
  record cannot be migrated, not that nobody has looked at it yet. A VAT number
  that fails the modulo-97 check does not become valid because a sales manager
  signed a sheet.
- **A decision on a `repair` rule.** The engine already fixed it and logged the
  original; there is nothing to decide.
- **A ruling on a rule that does not declare one**, or an answer outside the
  declared set.
- **A `correct` whose value does not parse** under the same parser the engine
  would have used, or that does not reach a column the load file carries. An
  answer that quietly does nothing is worse than a refused one.

A line answering a question this run did not ask is not an error — the owner
answered what they were asked — but it is counted as *stale* and reported, so
an answer cannot silently vanish.

## These sheets

Twenty-five lines, four owners, four rulings. They close a thousand open
questions and move one reconciliation gate; they do not move the other, which
is the point. `pytest -q` runs them against the real descent, because a
demonstration that has gone stale against the rules is worse than none.

The `note` column is ignored by the engine and read by people.
