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
