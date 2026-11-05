# The rule registry

Forty rules live in [`rules.yaml`](rules.yaml) as data rather than as code. The
engine reads this file; it does not contain a copy of these decisions in Python.
That matters for one reason: the interesting part of a cleansing pipeline is not
the regular expressions, it is **who is allowed to decide what**, and that is a
question the business has to be able to read, argue with and change without
touching the matcher.

## Schema

```yaml
circles:
  - number: 1            # I … IX, and the number is also the execution order
    name: Limbo
    sin: Data that is almost right
    description: >
      Prose that appears on the site, under the circle heading.

rules:
  - id: R-I-01           # R-<roman numeral of the circle>-<two digits>
    circle: 1
    title: Mojibake from a latin-1 export read as UTF-8
    entity: [customer, supplier]      # which entities it can fire on
    action: repair                    # repair | quarantine | reject | gate
    owner: engine                     # engine | sales | finance | purchasing | operations
    rationale: >
      Why this action and not another. At least twelve words, enforced by CI,
      because "obviously wrong" is not a reason anybody can audit later.
```

## The four actions

| action | meaning | who decides | lands in |
|---|---|---|---|
| `repair` | provable from the data; the engine fixes it and logs the original | engine | Paradiso |
| `quarantine` | not decidable from the data without inventing something | a named human | Purgatorio |
| `reject` | the value is unusable, so the row cannot be migrated | engine, reported loudly | Inferno |
| `gate` | a run-level control that blocks the whole load | finance | the verdict |

The line between `repair` and `quarantine` is the whole design. A stripped
leading zero on an EAN is a `repair` because the length is fixed and the check
digit confirms the result. A date that is valid under both the European and the
US reading is a `quarantine`, because both answers are defensible and guessing
is how an aging report starts lying.

`owner` is not decoration either: it is what sorts the backlog into
`out/purgatorio/<owner>.csv`, so a rule whose action is `quarantine` may never
name `engine` as its owner. CI asserts that.

## What CI enforces

From `tests/test_registry.py`:

- rule ids are unique, and each matches the circle it claims
- all nine circles exist and each has at least one rule
- every rule declares a valid action, a valid owner, at least one entity, and a
  rationale of twelve words or more
- **every non-gate rule fires at least once on the generated data** — a rule
  nobody triggers is documentation, not a control
- every gate is evaluated, and no `quarantine` rule is owned by the engine

## Adding a rule

1. Add the entry here, with a rationale that would survive being read aloud in a
   steering committee.
2. Implement it in the circle module it belongs to —
   `src/dante/circles/c<N>_<name>.py` — and emit it with
   `ctx.finding("R-...", entity, key, field, source, raw=..., repaired=...)`.
   The action and owner come from this file, not from the call site.
3. Make the forge plant it in `src/dante/forge.py`, so it is measurable.
4. Run `pytest -q`. The registry test will tell you if the rule never fires, and
   `tests/test_detection.py` will tell you how much of it the engine finds.

`dante rule R-IV-03` prints any rule with its rationale and the records it
caught in the last run.
