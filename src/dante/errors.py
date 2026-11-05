"""Failures a person caused, told to that person rather than to a stack trace.

Every one of these is something a reader of this repository is likely to do:
run the CLI from the wrong directory, ask for a report before a run, or forget
that the source files are generated rather than committed-and-ready. A thirty
line traceback is a fine answer to a bug and a poor answer to a typo.
"""

from __future__ import annotations

from pathlib import Path


class DanteError(Exception):
    """Something the caller can fix, with a sentence saying how."""

    def __init__(self, problem: str, fix: str) -> None:
        super().__init__(problem)
        self.problem = problem
        self.fix = fix


class MissingSources(DanteError):
    def __init__(self, raw_dir: Path, missing: list[str]) -> None:
        shown = ", ".join(missing[:3]) + (f" and {len(missing) - 3} more"
                                          if len(missing) > 3 else "")
        super().__init__(
            f"{len(missing)} of the source files are not in {raw_dir}: {shown}",
            "run `dante forge` to generate them, or point --raw at the directory "
            "that has them",
        )


class MissingRegistry(DanteError):
    def __init__(self, path: Path) -> None:
        super().__init__(
            f"the rule registry is not at {path}",
            "run this from the repository root, or pass --rules <path to rules.yaml>",
        )


class NoRunYet(DanteError):
    def __init__(self, path: Path) -> None:
        super().__init__(
            f"there is no run to report on: {path} does not exist",
            "run `dante run` first — it writes the summary this reads",
        )


class NoDecisions(DanteError):
    def __init__(self, path: Path) -> None:
        super().__init__(
            f"there are no decision sheets at {path}",
            "the sheets to fill in are written to out/purgatorio/ by `dante run` — "
            "copy one, fill the decision column, and point --decisions at it",
        )


class MalformedDecisions(DanteError):
    def __init__(self, path: Path, missing: list[str]) -> None:
        super().__init__(
            f"{path.name} is missing the column(s) {', '.join(missing)}",
            "a decision sheet is a copy of out/purgatorio/<owner>.csv with a "
            "`decision` column added — keep the rule, entity, key and field "
            "columns, because they are what identifies the finding",
        )


class RefusedDecisions(DanteError):
    def __init__(self, problems: list[str]) -> None:
        shown = "\n  ".join(problems[:8])
        more = f"\n  … and {len(problems) - 8} more" if len(problems) > 8 else ""
        noun = "decision" if len(problems) == 1 else "decisions"
        super().__init__(
            f"{len(problems)} {noun} cannot be applied:\n  {shown}{more}",
            "fix the lines above and run again — nothing was applied, so the "
            "run you just made is the same one you had",
        )


class UnknownRecord(DanteError):
    def __init__(self, key: str, near: list[str]) -> None:
        hint = f" Did you mean {', '.join(near[:3])}?" if near else ""
        super().__init__(
            f"no record {key!r} in the last run.{hint}",
            "keys look like K00008 (customer), SAN-0025 (article), L0010 "
            "(supplier) or VF240006 (receivable). A row from a rep's file has "
            "no key of its own and is addressed as cust_jan#11. `dante why` "
            "reads out/report/placement.csv, so run `dante run` first",
        )
