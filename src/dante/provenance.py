"""Which bytes, which rules, which engine produced this verdict.

A verdict you cannot tie back to a rule set is not auditable. "The load was
blocked in November" is worth nothing in March unless somebody can say which
forty rules were in force, and show that the file on disk today is still that
rule set. So every run records a digest of the registry it read, a digest of
every source table it read, and the version of the engine that read them.
Change one word of one rationale and the registry digest moves.

Two decisions here are worth stating, because both look wrong at first.

The source digests are taken over the *values*, not over the file bytes. A
workbook that is opened and saved without a single edit gets new bytes — Excel
and openpyxl both stamp the zip container with a creation time — and a digest
that moves when nothing changed teaches people to ignore digests. This one is
taken over what came out of the cells, so re-saving a file is invisible to it
and editing one cell is not.

The timestamp honours `DANTE_RUN_AT` when it is set, the way a reproducible
build honours `SOURCE_DATE_EPOCH`. Everything else in a run is deterministic
from one seed, and CI holds the committed outputs against a fresh run byte for
byte. A wall clock inside those bytes would fail that check on every commit.
Pinning the clock is how an audit trail and a reproducible artefact stay true
at the same time.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import __version__

SHORT = 12
UNIT, RECORD = "\x1f", "\x1e"


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest_frame(df: pd.DataFrame) -> str:
    """Hash what was read out of the cells, not the container it arrived in."""
    cols = [c for c in df.columns if not c.startswith("_")]
    h = hashlib.sha256()
    h.update((UNIT.join(cols) + RECORD).encode("utf-8"))
    for row in df[cols].itertuples(index=False, name=None):
        cells = UNIT.join("" if v is None else str(v) for v in row)
        h.update((cells + RECORD).encode("utf-8"))
    return h.hexdigest()


def run_at() -> str:
    """Now, in UTC, to the second — unless the caller pinned the clock."""
    pinned = os.environ.get("DANTE_RUN_AT", "").strip()
    return pinned or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def collect(rules_path: Path, rules: dict[str, Any], circles: dict[int, Any],
            sources: dict[str, pd.DataFrame], raw_dir: Path) -> dict[str, Any]:
    tables = [
        {"feed": name, "file": str(df["_source"].iloc[0]), "rows": int(len(df)),
         "sha256": digest_frame(df)}
        for name, df in sorted(sources.items())
    ]
    return {
        "engine": f"dante {__version__}",
        "run_at": run_at(),
        "registry": {
            "path": str(rules_path),
            "sha256": digest_text(Path(rules_path).read_text()),
            "rules": len(rules),
            "circles": len(circles),
        },
        "sources": {
            "directory": str(raw_dir),
            "tables": len(tables),
            # one digest over all twelve, so a reader has a single value to
            # quote in a sign-off and the detail to prove it with
            "sha256": digest_text("\n".join(f"{t['feed']}:{t['sha256']}"
                                            for t in tables)),
            "detail": tables,
        },
    }
